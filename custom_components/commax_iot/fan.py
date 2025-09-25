"""Commax IoT 환기시스템 플랫폼"""
import asyncio
import logging
from typing import Any, Optional

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_OFF,
    DEVICE_ON,
    DEVICE_TYPE_FAN,
    DOMAIN,
    FAN_DEFAULT_MODE,
    SUBDEVICE_FAN_MODE,
    SUBDEVICE_SWITCH_BINARY,
)

_LOGGER = logging.getLogger(__name__)


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
            has_switch = any(
                sub.get("sort") == SUBDEVICE_SWITCH_BINARY and sub.get("type") == "readWrite"
                for sub in device_data.get("subDevice", [])
            )

            if not has_switch:
                _LOGGER.debug(
                    "환기시스템 전원 서브디바이스가 없어 스킵: %s (UUID: %s)",
                    device_data.get("nickname"),
                    device_data.get("rootUuid"),
                )
                continue

            entities.append(CommaxFan(coordinator, auth_manager, device_data))
            _LOGGER.debug(
                "환기시스템 디바이스 등록: %s (UUID: %s)",
                device_data.get("nickname"),
                device_data.get("rootUuid"),
            )

    if entities:
        _LOGGER.info("총 %d개의 환기시스템 디바이스 등록됨", len(entities))
        async_add_entities(entities, True)
    else:
        _LOGGER.debug("등록할 환기시스템 디바이스가 없습니다")


class CommaxFan(CoordinatorEntity, FanEntity):
    """Commax IoT 환기시스템 엔터티"""

    def __init__(self, coordinator, auth_manager, device_data):
        """환기시스템 엔터티 초기화"""
        super().__init__(coordinator)
        self._auth_manager = auth_manager
        self._device_data = device_data
        self._root_uuid = device_data.get("rootUuid")
        self._nickname = device_data.get("nickname", "Commax Fan")

        self._switch_subdevice = None
        self._mode_subdevice = None
        for subdevice in device_data.get("subDevice", []):
            if (
                subdevice.get("sort") == SUBDEVICE_SWITCH_BINARY
                and subdevice.get("type") == "readWrite"
            ):
                self._switch_subdevice = subdevice
            elif (
                subdevice.get("sort") == SUBDEVICE_FAN_MODE
                and subdevice.get("type") == "readWrite"
            ):
                self._mode_subdevice = subdevice

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_fan"
        self._attr_name = self._nickname
        self._attr_supported_features = FanEntityFeature.TURN_ON | FanEntityFeature.TURN_OFF
        self._attr_preset_modes = None

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=self._nickname,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Fan"),
        )

    @property
    def is_on(self) -> bool:
        """환기시스템이 작동 중인지 반환 (bypass가 아닌 경우)"""
        return self._get_switch_state()

    @property
    def preset_mode(self) -> Optional[str]:
        """현재 프리셋 모드 반환"""
        mode = self._get_current_mode()
        return mode

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환"""
        return self.coordinator.last_update_success and self._switch_subdevice is not None

    def _get_switch_state(self) -> bool:
        """전원 상태 확인"""
        value = self._get_subdevice_value(self._switch_subdevice)
        if value is None:
            return False

        return str(value).lower() in {DEVICE_ON, "on", "1", "true"}

    def _get_current_mode(self) -> Optional[str]:
        """현재 모드 반환"""
        value = self._get_subdevice_value(self._mode_subdevice)
        if value is None:
            return None

        return str(value)

    def _get_subdevice_value(self, subdevice: Optional[dict]) -> Optional[str]:
        """서브 디바이스 현재 값 조회"""
        if not subdevice:
            return None

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return subdevice.get("value")

        target_uuid = subdevice.get("subUuid")
        for candidate in device_data.get("subDevice", []):
            if candidate.get("subUuid") == target_uuid:
                return candidate.get("value")

        return subdevice.get("value")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """환기시스템 켜기 및 자동 모드 적용"""
        if not self._switch_subdevice:
            _LOGGER.error("환기 전원 서브디바이스를 찾을 수 없습니다: %s", self._nickname)
            return

        _LOGGER.debug("환기시스템 켜기 요청: %s", self._nickname)
        payloads = [self._build_switch_payload(DEVICE_ON)]

        if self._mode_subdevice:
            payloads.append(self._build_mode_payload(FAN_DEFAULT_MODE))

        await self._send_command(payloads)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """환기시스템 끄기"""
        if not self._switch_subdevice:
            _LOGGER.error("환기 전원 서브디바이스를 찾을 수 없습니다: %s", self._nickname)
            return

        _LOGGER.debug("환기시스템 끄기 요청: %s", self._nickname)
        await self._send_command([self._build_switch_payload(DEVICE_OFF)])

    def _build_switch_payload(self, value: str) -> dict:
        return {
            "value": value,
            "funcCommand": "set",
            "type": "readWrite",
            "subUuid": self._switch_subdevice.get("subUuid"),
            "sort": SUBDEVICE_SWITCH_BINARY,
        }

    def _build_mode_payload(self, value: str) -> dict:
        return {
            "value": value,
            "funcCommand": "set",
            "type": "readWrite",
            "subUuid": self._mode_subdevice.get("subUuid"),
            "sort": SUBDEVICE_FAN_MODE,
        }

    async def _send_command(self, subdevice_payloads: list[dict]) -> None:
        """디바이스 제어 명령 전송"""
        if not subdevice_payloads:
            _LOGGER.error("환기시스템 제어 페이로드가 비어 있습니다: %s", self._nickname)
            return

        device_data = {
            "subDevice": subdevice_payloads,
            "rootUuid": self._root_uuid,
            "nickname": self._nickname,
            "rootDevice": self._device_data.get("rootDevice"),
        }

        _LOGGER.debug("전송할 환기 명령 데이터: %s", device_data)
        success = await self._auth_manager.send_device_command(device_data)

        if success:
            for payload in subdevice_payloads:
                self._update_local_subdevice_value(payload.get("subUuid"), payload.get("value"))
            self.async_write_ha_state()
        else:
            _LOGGER.error("환기시스템 제어 실패: %s", self._nickname)

        asyncio.create_task(self._delayed_refresh())

    async def _delayed_refresh(self) -> None:
        """1초 후 상태 새로고침"""
        await asyncio.sleep(1)
        await self.coordinator.async_request_refresh()

    def _update_local_subdevice_value(self, sub_uuid: Optional[str], value: str) -> None:
        """로컬 서브디바이스 값을 즉시 업데이트"""
        if not sub_uuid:
            return

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == sub_uuid:
                subdevice["value"] = value
                break

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()
