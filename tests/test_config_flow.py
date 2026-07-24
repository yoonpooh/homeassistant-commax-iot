"""Tests for config flow helpers."""

from __future__ import annotations

import unittest

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.commax_iot.config_flow import _validate_update_interval


class UpdateIntervalValidationTest(unittest.TestCase):
    def test_accepts_bounds_and_string_numbers(self) -> None:
        self.assertEqual(_validate_update_interval(1), 1)
        self.assertEqual(_validate_update_interval("30"), 30)
        self.assertEqual(_validate_update_interval(3600), 3600)

    def test_rejects_out_of_range_values(self) -> None:
        for value in (0, 3601):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _validate_update_interval(value)

    def test_rejects_non_numeric_values(self) -> None:
        with self.assertRaises(ValueError):
            _validate_update_interval("fast")


if __name__ == "__main__":
    unittest.main()
