"""Tests for sensor helper functions."""

from __future__ import annotations

import unittest

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.commax_iot.sensor import (
    _parse_subdevice_value,
    _resolve_subdevice_label,
)


class SensorHelperTest(unittest.TestCase):
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
