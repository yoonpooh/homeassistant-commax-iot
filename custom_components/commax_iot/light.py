"""Commax IoT 조명 플랫폼"""
import asyncio
import logging
from typing import Any

from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_ON
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_OFF,
    DEVICE_ON,
    DEVICE_VALUE_OFF,
    DEVICE_VALUE_ON,
    DEVICE_TYPE_LIGHT,
    DOMAIN,
    SUBDEVICE_SWITCH_BINARY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """조명 플랫폼 설정"""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    auth_manager = hass.data[DOMAIN][entry.entry_id]["auth_manager"]

    entities = []

    await coordinator.async_refresh()

    for device_uuid, device_data in coordinator.data.items():
        if device_data.get("commaxDevice") == DEVICE_TYPE_LIGHT:
            has_switch = any(
                subdevice.get("sort") == SUBDEVICE_SWITCH_BINARY and
                subdevice.get("type") == "readWrite"
                for subdevice in device_data.get("subDevice", [])
            )

            if has_switch:
                entities.append(CommaxLight(coordinator, auth_manager, device_data))
                _LOGGER.debug(
                    "조명 디바이스 등록: %s (UUID: %s)",
                    device_data.get("nickname"),
                    device_data.get("rootUuid"),
                )

    if entities:
        async_add_entities(entities, True)

class CommaxLight(CoordinatorEntity, RestoreEntity, LightEntity):
    """Commax IoT 조명 엔터티"""

    def __init__(self, coordinator, auth_manager, device_data):
        """조명 엔터티 초기화"""
        super().__init__(coordinator)
        self._auth_manager = auth_manager
        self._device_data = device_data
        self._root_uuid = device_data.get("rootUuid")
        self._nickname = device_data.get("nickname", "Commax Light")

        self._switch_subdevice = next(
            (
                subdevice
                for subdevice in device_data.get("subDevice", [])
                if subdevice.get("sort") == SUBDEVICE_SWITCH_BINARY
                and subdevice.get("type") == "readWrite"
            ),
            None,
        )

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_light"
        self._attr_name = self._nickname
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_is_on = False
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=self._nickname,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Light"),
        )

    async def async_added_to_hass(self) -> None:
        """엔터티 추가 시 마지막 상태 복원"""
        await super().async_added_to_hass()

        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == STATE_ON

    @property
    def is_on(self) -> bool:
        """조명이 켜져 있는지 반환"""
        if not self._switch_subdevice:
            return False

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return self._attr_is_on

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._switch_subdevice.get("subUuid"):
                current_value = subdevice.get("value")
                if current_value is None:
                    return self._attr_is_on

                normalized = str(current_value).lower()
                possible_on_values = {
                    DEVICE_ON,
                    DEVICE_VALUE_ON,
                    DEVICE_VALUE_ON.lower(),
                    "1",
                    "true",
                }
                is_on = normalized in possible_on_values
                self._attr_is_on = is_on
                return is_on

        return self._attr_is_on

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환"""
        return self.coordinator.last_update_success and self._switch_subdevice is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """조명 켜기"""
        if self._switch_subdevice:
            await self._send_command(DEVICE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """조명 끄기"""
        if self._switch_subdevice:
            await self._send_command(DEVICE_OFF)

    async def _send_command(self, value: str) -> None:
        """디바이스 제어 명령 전송"""
        device_data = {
            "subDevice": [
                {
                    "value": value,
                    "funcCommand": "set",
                    "type": "readWrite",
                    "subUuid": self._switch_subdevice.get("subUuid"),
                    "sort": SUBDEVICE_SWITCH_BINARY,
                }
            ],
            "rootUuid": self._root_uuid,
            "nickname": self._nickname,
            "rootDevice": self._device_data.get("rootDevice"),
        }

        success = await self._auth_manager.send_device_command(device_data)

        if success:
            self._update_local_subdevice_value(
                self._switch_subdevice.get("subUuid"), value
            )
            self.async_write_ha_state()

        asyncio.create_task(self._delayed_refresh())


    async def _delayed_refresh(self) -> None:
        """1초 후 상태 새로고침"""
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    def _update_local_subdevice_value(self, sub_uuid: str, value: str) -> None:
        """로컬 서브디바이스 값을 즉시 업데이트"""
        if not sub_uuid:
            return

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == sub_uuid:
                subdevice["value"] = value
                normalized = str(value).lower()
                self._attr_is_on = normalized in {
                    DEVICE_ON,
                    DEVICE_VALUE_ON,
                    DEVICE_VALUE_ON.lower(),
                    "1",
                    "true",
                }
                break

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()
