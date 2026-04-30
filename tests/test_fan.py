"""Tests for fan helper behavior."""

from __future__ import annotations

import unittest

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.commax_iot.const import (
    DEVICE_TYPE_FAN,
    SUBDEVICE_FAN_SPEED,
    SUBDEVICE_SWITCH_BINARY,
)
from custom_components.commax_iot.fan import CommaxFan


class FakeCoordinator:
    def __init__(self, device_data: dict) -> None:
        self.last_update_success = True
        self._device_data = device_data

    def get_device_by_uuid(self, root_uuid: str) -> dict | None:
        if self._device_data.get("rootUuid") == root_uuid:
            return self._device_data
        return None


class FanHelperTest(unittest.TestCase):
    def setUp(self) -> None:
        self.device_data = {
            "rootUuid": "fan-root-1",
            "nickname": "Ventilation",
            "rootDevice": "switch",
            "commaxDevice": DEVICE_TYPE_FAN,
            "subDevice": [
                {
                    "sort": SUBDEVICE_SWITCH_BINARY,
                    "type": "readWrite",
                    "subUuid": "power-1",
                    "value": "on",
                },
                {
                    "sort": SUBDEVICE_FAN_SPEED,
                    "type": "readWrite",
                    "subUuid": "speed-1",
                    "subOption": ["low", "middle", "high"],
                    "value": "middle",
                },
            ],
        }
        self.entity = CommaxFan(FakeCoordinator(self.device_data), object(), self.device_data)

    def test_speed_to_percentage_uses_available_options(self) -> None:
        self.assertEqual(self.entity._speed_to_percentage("low"), 33)
        self.assertEqual(self.entity._speed_to_percentage("middle"), 67)
        self.assertEqual(self.entity._speed_to_percentage("high"), 100)
        self.assertIsNone(self.entity._speed_to_percentage("turbo"))

    def test_percentage_to_speed_uses_ceiling_bucket(self) -> None:
        self.assertEqual(self.entity._percentage_to_speed(1), "low")
        self.assertEqual(self.entity._percentage_to_speed(34), "middle")
        self.assertEqual(self.entity._percentage_to_speed(68), "high")
        self.assertIsNone(self.entity._percentage_to_speed(0))

    def test_current_percentage_reflects_coordinator_data(self) -> None:
        self.assertEqual(self.entity.percentage, 67)
        self.device_data["subDevice"][1]["value"] = "high"
        self.assertEqual(self.entity.percentage, 100)


if __name__ == "__main__":
    unittest.main()
