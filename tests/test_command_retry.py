"""서버가 수락했지만 기기에 반영되지 않은 명령의 재전송 테스트."""

from __future__ import annotations

import asyncio
import unittest
from unittest import mock

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.commax_iot import auth  # noqa: E402
from custom_components.commax_iot.const import AUTH_URL, COMMAND_URL  # noqa: E402

ROOT = "root-1"
SUB = "sub-1"


class _Response:
    status = 200

    def __init__(self, body: dict, gate: asyncio.Event | None = None) -> None:
        self._body = body
        self._gate = gate

    async def __aenter__(self) -> "_Response":
        if self._gate:
            await self._gate.wait()
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def json(self) -> dict:
        return self._body


class FakeCommax:
    """항상 E0000으로 수락하고, ignore 횟수만큼은 기기에 반영하지 않는 서버."""

    def __init__(self, ignore: int, values: dict | None = None) -> None:
        self.ignore = ignore
        self.values = values or {SUB: "off"}
        self.commands: list[str] = []
        self.gate: asyncio.Event | None = None  # 첫 명령 응답을 붙잡아 둔다
        self.listed = True

    def post(self, url: str, json: dict, headers: dict | None = None) -> _Response:
        if url == AUTH_URL:
            return _Response(
                {"resultCode": "E0000", "accessToken": "t", "expireIn": 3600}
            )
        assert url == COMMAND_URL
        sent = json["commands"]["cgpCommand"][0]["cgp"]["object"]["subDevice"][0]
        self.commands.append(sent["value"])
        if self.ignore > 0:
            self.ignore -= 1
        else:
            self.values[sent["subUuid"]] = sent["value"]
        gate, self.gate = self.gate, None
        return _Response({"resultCode": "E0000"}, gate)

    def get(self, url: str, headers: dict | None = None) -> _Response:
        subs = [{"subUuid": k, "value": v} for k, v in self.values.items()]
        devices = [{"rootUuid": ROOT, "subDevice": subs}] if self.listed else []
        return _Response(
            {"resultCode": "E0000", "resource": {"devices": {"object": devices}}}
        )


def _command(value: str, sub: str = SUB) -> dict:
    return {
        "rootUuid": ROOT,
        "nickname": "전등07",
        "subDevice": [{"subUuid": sub, "value": value, "sort": "switchBinary"}],
    }


async def _settle() -> None:
    """백그라운드 확인 작업이 모두 끝날 때까지 기다린다."""
    results = await asyncio.gather(
        *(asyncio.all_tasks() - {asyncio.current_task()}), return_exceptions=True
    )
    for result in results:
        if isinstance(result, Exception):
            raise result


class CommandRetryTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        patcher = mock.patch.object(auth, "COMMAND_VERIFY_DELAY", 0, create=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _manager(self, server: FakeCommax) -> auth.CommaxAuthManager:
        return auth.CommaxAuthManager("uuid", "id", "pw", server, resource_no="r")

    async def test_resends_when_accepted_command_is_not_applied(self) -> None:
        server = FakeCommax(ignore=1)

        self.assertTrue(await self._manager(server).send_device_command(_command("on")))
        await _settle()

        self.assertEqual(server.commands, ["on", "on"])
        self.assertEqual(server.values[SUB], "on")

    async def test_does_not_resend_when_command_is_applied(self) -> None:
        server = FakeCommax(ignore=0)

        await self._manager(server).send_device_command(_command("on"))
        await _settle()

        self.assertEqual(server.commands, ["on"])

    async def test_gives_up_after_two_resends(self) -> None:
        server = FakeCommax(ignore=99)

        await self._manager(server).send_device_command(_command("on"))
        await _settle()

        self.assertEqual(server.commands, ["on", "on", "on"])

    async def test_newer_command_stops_resending_the_older_one(self) -> None:
        server = FakeCommax(ignore=99, values={SUB: "dim"})
        manager = self._manager(server)

        await manager.send_device_command(_command("on"))
        await manager.send_device_command(_command("off"))
        await _settle()

        self.assertEqual(server.commands, ["on", "off", "off", "off"])

    async def test_slow_response_does_not_revive_the_older_command(self) -> None:
        server = FakeCommax(ignore=99, values={SUB: "dim"})
        server.gate = gate = asyncio.Event()
        manager = self._manager(server)

        first = asyncio.create_task(manager.send_device_command(_command("on")))
        await asyncio.sleep(0.01)
        second = asyncio.create_task(manager.send_device_command(_command("off")))
        await asyncio.sleep(0.01)
        gate.set()
        await asyncio.gather(first, second)
        await _settle()

        self.assertEqual(server.commands, ["on", "off", "off", "off"])

    async def test_queued_resend_is_dropped_when_a_newer_command_arrives(self) -> None:
        server = FakeCommax(ignore=99, values={SUB: "dim", "speed": "low"})
        manager = self._manager(server)

        await manager.send_device_command(_command("on"))
        server.gate = gate = asyncio.Event()
        other = asyncio.create_task(
            manager.send_device_command(_command("high", sub="speed"))
        )
        await asyncio.sleep(0.01)  # on 재전송이 잠금을 기다린다
        newer = asyncio.create_task(manager.send_device_command(_command("off")))
        await asyncio.sleep(0.01)
        gate.set()
        await asyncio.gather(other, newer)
        await _settle()

        self.assertEqual(server.commands.count("on"), 1)

    async def test_turning_off_stops_resending_other_settings(self) -> None:
        server = FakeCommax(ignore=99, values={SUB: "on", "speed": "low"})
        manager = self._manager(server)

        await manager.send_device_command(_command("high", sub="speed"))
        await manager.send_device_command(_command("off"))
        await _settle()

        self.assertEqual(server.commands, ["high", "off", "off", "off"])

    async def test_numeric_on_counts_as_applied(self) -> None:
        server = FakeCommax(ignore=99, values={SUB: 1})

        await self._manager(server).send_device_command(_command("on"))
        await _settle()

        self.assertEqual(server.commands, ["on"])

    async def test_does_not_resend_when_device_is_missing_from_list(self) -> None:
        server = FakeCommax(ignore=99)
        server.listed = False

        await self._manager(server).send_device_command(_command("on"))
        await _settle()

        self.assertEqual(server.commands, ["on"])

    async def test_close_stops_resending(self) -> None:
        server = FakeCommax(ignore=99)
        manager = self._manager(server)

        await manager.send_device_command(_command("on"))
        manager.close()
        await _settle()

        self.assertEqual(server.commands, ["on"])


if __name__ == "__main__":
    unittest.main()
