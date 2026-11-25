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

    def __init__(self, body: dict) -> None:
        self._body = body

    async def __aenter__(self) -> "_Response":
        return self

    async def __aexit__(self, *exc) -> None:
        return None

    async def json(self) -> dict:
        return self._body


class FakeCommax:
    """항상 E0000으로 수락하고, ignore 횟수만큼은 기기에 반영하지 않는 서버."""

    def __init__(self, ignore: int) -> None:
        self.ignore = ignore
        self.value = "off"
        self.commands: list[str] = []

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
            self.value = sent["value"]
        return _Response({"resultCode": "E0000"})

    def get(self, url: str, headers: dict | None = None) -> _Response:
        device = {"rootUuid": ROOT, "subDevice": [{"subUuid": SUB, "value": self.value}]}
        return _Response(
            {"resultCode": "E0000", "resource": {"devices": {"object": [device]}}}
        )


def _command(value: str) -> dict:
    return {
        "rootUuid": ROOT,
        "nickname": "전등07",
        "subDevice": [{"subUuid": SUB, "value": value, "sort": "switchBinary"}],
    }


async def _settle() -> None:
    """백그라운드 확인 작업이 모두 끝날 때까지 기다린다."""
    await asyncio.gather(
        *(asyncio.all_tasks() - {asyncio.current_task()}), return_exceptions=True
    )


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
        self.assertEqual(server.value, "on")

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
        server = FakeCommax(ignore=99)
        server.value = "dim"
        manager = self._manager(server)

        await manager.send_device_command(_command("on"))
        await manager.send_device_command(_command("off"))
        await _settle()

        self.assertEqual(server.commands, ["on", "off", "off", "off"])


if __name__ == "__main__":
    unittest.main()
