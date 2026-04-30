"""Tests for platform setup behavior."""

from __future__ import annotations

import unittest

from tests.ha_stubs import install_homeassistant_stubs

install_homeassistant_stubs()

from custom_components.commax_iot import const
from custom_components.commax_iot.fan import async_setup_entry as async_setup_fan
from custom_components.commax_iot.light import async_setup_entry as async_setup_light


class FakeCoordinator:
    def __init__(self, data: dict, refreshed_data: dict | None = None) -> None:
        self.data = data
        self._refreshed_data = refreshed_data
        self.last_update_success = True
        self.refresh_count = 0

    async def async_refresh(self) -> None:
        self.refresh_count += 1
        if self._refreshed_data is not None:
            self.data = self._refreshed_data

    def get_device_by_uuid(self, root_uuid: str) -> dict | None:
        return self.data.get(root_uuid)


class FakeEntry:
    entry_id = "entry-1"


def _make_hass(coordinator: FakeCoordinator) -> object:
    class FakeHass:
        pass

    hass = FakeHass()
    hass.data = {
        const.DOMAIN: {
            FakeEntry.entry_id: {
                "coordinator": coordinator,
                "auth_manager": object(),
            }
        }
    }
    return hass


class PlatformSetupTest(unittest.IsolatedAsyncioTestCase):
    async def test_light_setup_uses_existing_first_refresh_data(self) -> None:
        coordinator = FakeCoordinator(
            {
                "light-root-1": {
                    "rootUuid": "light-root-1",
                    "nickname": "Living Room Light",
                    "rootDevice": "light",
                    "commaxDevice": const.DEVICE_TYPE_LIGHT,
                    "subDevice": [
                        {
                            "sort": const.SUBDEVICE_SWITCH_BINARY,
                            "type": "readWrite",
                            "subUuid": "light-switch-1",
                            "value": "off",
                        }
                    ],
                }
            }
        )
        added_entities = []

        await async_setup_light(
            _make_hass(coordinator),
            FakeEntry(),
            lambda entities, update_before_add=False: added_entities.extend(entities),
        )

        self.assertEqual(coordinator.refresh_count, 0)
        self.assertEqual(len(added_entities), 1)

    async def test_fan_setup_uses_existing_first_refresh_data(self) -> None:
        coordinator = FakeCoordinator(
            {
                "fan-root-1": {
                    "rootUuid": "fan-root-1",
                    "nickname": "Ventilation",
                    "rootDevice": "switch",
                    "commaxDevice": const.DEVICE_TYPE_FAN,
                    "subDevice": [
                        {
                            "sort": const.SUBDEVICE_SWITCH_BINARY,
                            "type": "readWrite",
                            "subUuid": "fan-switch-1",
                            "value": "on",
                        }
                    ],
                }
            }
        )
        added_entities = []

        await async_setup_fan(
            _make_hass(coordinator),
            FakeEntry(),
            lambda entities, update_before_add=False: added_entities.extend(entities),
        )

        self.assertEqual(coordinator.refresh_count, 0)
        self.assertEqual(len(added_entities), 1)

    async def test_light_setup_keeps_fallback_refresh_when_data_is_missing(self) -> None:
        coordinator = FakeCoordinator(
            {},
            {
                "light-root-1": {
                    "rootUuid": "light-root-1",
                    "nickname": "Living Room Light",
                    "rootDevice": "light",
                    "commaxDevice": const.DEVICE_TYPE_LIGHT,
                    "subDevice": [
                        {
                            "sort": const.SUBDEVICE_SWITCH_BINARY,
                            "type": "readWrite",
                            "subUuid": "light-switch-1",
                            "value": "off",
                        }
                    ],
                }
            },
        )
        added_entities = []

        await async_setup_light(
            _make_hass(coordinator),
            FakeEntry(),
            lambda entities, update_before_add=False: added_entities.extend(entities),
        )

        self.assertEqual(coordinator.refresh_count, 1)
        self.assertEqual(len(added_entities), 1)

    async def test_fan_setup_keeps_fallback_refresh_when_data_is_missing(self) -> None:
        coordinator = FakeCoordinator(
            {},
            {
                "fan-root-1": {
                    "rootUuid": "fan-root-1",
                    "nickname": "Ventilation",
                    "rootDevice": "switch",
                    "commaxDevice": const.DEVICE_TYPE_FAN,
                    "subDevice": [
                        {
                            "sort": const.SUBDEVICE_SWITCH_BINARY,
                            "type": "readWrite",
                            "subUuid": "fan-switch-1",
                            "value": "on",
                        }
                    ],
                }
            },
        )
        added_entities = []

        await async_setup_fan(
            _make_hass(coordinator),
            FakeEntry(),
            lambda entities, update_before_add=False: added_entities.extend(entities),
        )

        self.assertEqual(coordinator.refresh_count, 1)
        self.assertEqual(len(added_entities), 1)


if __name__ == "__main__":
    unittest.main()
