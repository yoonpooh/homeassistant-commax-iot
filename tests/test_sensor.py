"""Tests for sensor helper functions."""

from __future__ import annotations

import unittest
from unittest.mock import Mock

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.commax_iot.sensor import (
    CommaxGenericSensor,
    CommaxPowerSensor,
    _parse_subdevice_value,
    _resolve_subdevice_label,
)


class SensorHelperTest(unittest.TestCase):
    def test_sensors_read_latest_value_and_keep_entity_ids(self) -> None:
        meter = {"subUuid": "meter-1", "value": "1234", "precision": "2"}
        device = {"rootUuid": "room-1", "subDevice": [meter]}
        coordinator = Mock()
        coordinator.get_device_by_uuid.return_value = device
        power = CommaxPowerSensor(coordinator, device, meter)
        generic = CommaxGenericSensor(coordinator, device, meter, {}, "electricMeter")

        self.assertEqual(power._attr_unique_id, "commax_iot_room-1_meter-1_power")
        self.assertEqual(generic._attr_unique_id, "commax_iot_room-1_meter-1_electricMeter")
        for sensor in (power, generic):
            self.assertEqual(sensor.native_value, 12.34)

        coordinator.get_device_by_uuid.return_value = {
            "subDevice": [{**meter, "value": "500"}]
        }
        for sensor in (power, generic):
            self.assertEqual(sensor.native_value, 5)

        coordinator.get_device_by_uuid.return_value = {"subDevice": []}
        for sensor in (power, generic):
            self.assertIsNone(sensor.native_value)

    def test_parse_subdevice_value_applies_precision(self) -> None:
        self.assertEqual(_parse_subdevice_value({"value": "1234", "precision": "2"}), 12.34)

    def test_parse_subdevice_value_handles_invalid_values(self) -> None:
        self.assertIsNone(_parse_subdevice_value({"value": "not-number", "precision": "2"}))
        self.assertEqual(_parse_subdevice_value({"value": "42", "precision": "bad"}), 42.0)

    def test_resolve_subdevice_label_prefers_subdevice_name(self) -> None:
        label = _resolve_subdevice_label(
            {"nickname": "Living Room PM2.5"},
            {"label": "PM2.5"},
            "airQuality2.5",
        )

        self.assertEqual(label, "Living Room PM2.5")

    def test_resolve_subdevice_label_falls_back_to_mapping_then_type(self) -> None:
        self.assertEqual(
            _resolve_subdevice_label({}, {"label": "Humidity"}, "humidity"),
            "Humidity",
        )
        self.assertEqual(
            _resolve_subdevice_label({}, {}, "unknownSensor"),
            "unknownSensor",
        )


if __name__ == "__main__":
    unittest.main()
