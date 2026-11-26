"""Characterize the commands sent by the supported control entities."""

import unittest
from unittest.mock import AsyncMock, Mock

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.commax_iot.climate import CommaxThermostat
from custom_components.commax_iot.fan import CommaxFan
from custom_components.commax_iot.switch import CommaxSwitch


def subdevice(sort, value, **options):
    return {
        "sort": sort,
        "type": "readWrite",
        "subUuid": f"{sort}-1",
        "value": value,
        **options,
    }


class EntityCommandTest(unittest.IsolatedAsyncioTestCase):
    def make_entity(self, entity_class, *subdevices, accepted=True):
        device = {
            "rootUuid": "room-1",
            "nickname": "Room",
            "rootDevice": "switch",
            "subDevice": list(subdevices),
        }
        coordinator = Mock(
            get_device_by_uuid=Mock(return_value=device),
            async_request_refresh=AsyncMock(),
            last_update_success=True,
        )
        auth = Mock(send_device_command=AsyncMock(return_value=accepted))
        entity = entity_class(coordinator, auth, device)
        entity.async_write_ha_state = Mock()
        return entity, auth.send_device_command

    def assert_commands(self, send, *updates):
        self.assertEqual(
            [call.args[0] for call in send.await_args_list],
            [
                {
                    "rootUuid": "room-1",
                    "nickname": "Room",
                    "rootDevice": "switch",
                    "subDevice": [{
                        "value": value,
                        "funcCommand": "set",
                        "type": "readWrite",
                        "subUuid": f"{sort}-1",
                        "sort": sort,
                    }],
                }
                for sort, value in updates
            ],
        )

    async def test_switch_updates_state_only_when_command_is_accepted(self):
        for accepted in (True, False):
            with self.subTest(accepted=accepted):
                entity, send = self.make_entity(
                    CommaxSwitch, subdevice("switchBinary", "off"), accepted=accepted
                )
                await entity.async_turn_on()
                self.assert_commands(send, ("switchBinary", "on"))
                self.assertEqual(entity.is_on, accepted)
                self.assertEqual(entity.async_write_ha_state.call_count, int(accepted))

    async def test_fan_sends_power_mode_and_speed_in_separate_requests(self):
        entity, send = self.make_entity(
            CommaxFan,
            subdevice("switchBinary", "off"),
            subdevice("modeBinary", "manual"),
            subdevice("fanSpeed", "low", subOption=["low", "high"]),
        )
        await entity.async_turn_on(percentage=100)
        self.assert_commands(
            send, ("switchBinary", "on"), ("modeBinary", "auto"), ("fanSpeed", "high")
        )
        self.assertTrue(entity.is_on)
        self.assertEqual(entity.preset_mode, "auto")
        self.assertEqual(entity.percentage, 100)

    async def test_thermostat_ignores_temperature_when_switching_off(self):
        entity, send = self.make_entity(
            CommaxThermostat,
            subdevice("thermostatMode", "off"),
            subdevice("thermostatSetpoint", "20"),
        )
        await entity.async_set_temperature(hvac_mode="heat", temperature=22.5)
        await entity.async_set_temperature(hvac_mode="off", temperature=18)
        self.assert_commands(
            send, ("thermostatMode", "heat"), ("thermostatSetpoint", "22.5"),
            ("thermostatMode", "off"),
        )
        self.assertEqual(entity.hvac_mode, "off")
        self.assertEqual(entity.target_temperature, 22.5)
