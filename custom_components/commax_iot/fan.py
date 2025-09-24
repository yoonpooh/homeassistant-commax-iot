"""Commax IoT 환기시스템 플랫폼"""
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.fan import FanEntity, PLATFORM_SCHEMA
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_TYPE_FAN,
    DOMAIN,
    FAN_MODE_AUTO,
    FAN_MODE_BYPASS,
    FAN_MODE_MANUAL,
    NAME,
    SUBDEVICE_FAN_MODE,
)

_LOGGER = logging.getLogger(__name__)

# 환기 모드 매핑
FAN_MODE_MAPPING = {
    FAN_MODE_BYPASS: "bypass",
    FAN_MODE_MANUAL: "manual",
    FAN_MODE_AUTO: "auto",
}

REVERSE_FAN_MODE_MAPPING = {v: k for k, v in FAN_MODE_MAPPING.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """환기시스템 플랫폼 설정"""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    auth_manager = hass.data[DOMAIN][entry.entry_id]["auth_manager"]

    entities = []

    await coordinator.async_refresh()

    for device_uuid, device_data in coordinator.data.items():
        if (
            device_data.get("commaxDevice") == DEVICE_TYPE_FAN
            and device_data.get("rootDevice") == "switch"
        ):
            entities.append(CommaxFan(coordinator, auth_manager, device_data))

    if entities:
        async_add_entities(entities, True)


class CommaxFan(CoordinatorEntity, FanEntity):
    """Commax IoT 환기시스템 엔터티"""

    def __init__(self, coordinator, auth_manager, device_data):
        """환기시스템 엔터티 초기화"""
        super().__init__(coordinator)
        self._auth_manager = auth_manager
        self._device_data = device_data
        self._root_uuid = device_data.get("rootUuid")
        self._nickname = device_data.get("nickname", "Commax Fan")

        self._fan_subdevice = None
        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("sort") == SUBDEVICE_FAN_MODE and subdevice.get("type") == "readWrite":
                self._fan_subdevice = subdevice
                break

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_fan"
        self._attr_name = self._nickname
        self._attr_preset_modes = list(FAN_MODE_MAPPING.values())

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=self._nickname,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Fan"),
        )

    @property
    def is_on(self) -> bool:
        """환기시스템이 작동 중인지 반환 (bypass가 아닌 경우)"""
        current_mode = self._get_current_fan_mode()
        return current_mode != FAN_MODE_BYPASS

    @property
    def preset_mode(self) -> Optional[str]:
        """현재 프리셋 모드 반환"""
        current_mode = self._get_current_fan_mode()
        return FAN_MODE_MAPPING.get(current_mode)

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환"""
        return self.coordinator.last_update_success and self._fan_subdevice is not None

    def _get_current_fan_mode(self) -> str:
        """현재 환기 모드 값 반환"""
        if not self._fan_subdevice:
            return FAN_MODE_BYPASS

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return FAN_MODE_BYPASS

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._fan_subdevice.get("subUuid"):
                return subdevice.get("value", FAN_MODE_BYPASS)

        return FAN_MODE_BYPASS

    async def async_turn_on(self, **kwargs: Any) -> None:
        """환기시스템 켜기 (manual 모드로 설정)"""
        await self.async_set_preset_mode("manual")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """환기시스템 끄기 (bypass 모드로 설정)"""
        await self.async_set_preset_mode("bypass")

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        """프리셋 모드 설정"""
        if preset_mode not in REVERSE_FAN_MODE_MAPPING:
            _LOGGER.error(f"지원하지 않는 프리셋 모드: {preset_mode}")
            return

        if not self._fan_subdevice:
            _LOGGER.error("환기 서브디바이스를 찾을 수 없습니다")
            return

        mode_value = REVERSE_FAN_MODE_MAPPING[preset_mode]
        await self._send_command(mode_value)

    async def _send_command(self, mode_value: str) -> None:
        """디바이스 제어 명령 전송"""
        device_data = {
            "subDevice": [
                {
                    "value": mode_value,
                    "funcCommand": "set",
                    "type": "readWrite",
                    "subUuid": self._fan_subdevice.get("subUuid"),
                    "sort": SUBDEVICE_FAN_MODE,
                }
            ],
            "rootUuid": self._root_uuid,
            "nickname": self._nickname,
            "rootDevice": self._device_data.get("rootDevice"),
        }

        success = await self._auth_manager.send_device_command(device_data)
        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error(f"환기시스템 제어 실패: {self._nickname}")

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()