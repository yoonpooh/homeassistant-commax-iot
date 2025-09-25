"""Commax IoT 조명 플랫폼"""
import logging
from typing import Any

from homeassistant.components.light import LightEntity, ColorMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
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

    # 데이터가 준비될 때까지 기다림
    if not coordinator.data:
        await coordinator.async_refresh()

    # 데이터가 여전히 없으면 빈 리스트로 초기화
    if not coordinator.data:
        coordinator.data = {}

    for device_uuid, device_data in coordinator.data.items():
        if device_data.get("commaxDevice") == DEVICE_TYPE_LIGHT:
            # 필수 subDevice 확인
            has_switch = False
            for subdevice in device_data.get("subDevice", []):
                if (subdevice.get("sort") == SUBDEVICE_SWITCH_BINARY and
                    subdevice.get("type") == "readWrite"):
                    has_switch = True
                    break

            if has_switch:
                light_entity = CommaxLight(coordinator, auth_manager, device_data)
                entities.append(light_entity)
                _LOGGER.debug(
                    "조명 디바이스 등록: %s (UUID: %s)",
                    device_data.get("nickname"),
                    device_data.get("rootUuid"),
                )
            else:
                _LOGGER.debug(
                    "조명 디바이스에 제어 가능한 서브디바이스가 없습니다: %s",
                    device_data.get("nickname"),
                )

    if entities:
        _LOGGER.info("총 %d개의 조명 디바이스 등록됨", len(entities))
        async_add_entities(entities, True)
    else:
        _LOGGER.debug("등록할 조명 디바이스가 없습니다")

class CommaxLight(CoordinatorEntity, LightEntity):
    """Commax IoT 조명 엔터티"""

    def __init__(self, coordinator, auth_manager, device_data):
        """조명 엔터티 초기화"""
        super().__init__(coordinator)
        self._auth_manager = auth_manager
        self._device_data = device_data
        self._root_uuid = device_data.get("rootUuid")
        self._nickname = device_data.get("nickname", "Commax Light")

        self._switch_subdevice = None
        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("sort") == SUBDEVICE_SWITCH_BINARY and subdevice.get("type") == "readWrite":
                self._switch_subdevice = subdevice
                break

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_light"
        self._attr_name = self._nickname
        self._attr_supported_color_modes = {ColorMode.ONOFF}
        self._attr_color_mode = ColorMode.ONOFF
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=self._nickname,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Light"),
        )

    @property
    def is_on(self) -> bool:
        """조명이 켜져 있는지 반환"""
        if not self._switch_subdevice:
            _LOGGER.debug(f"is_on 체크: 스위치 서브디바이스 없음 - {self._nickname}")
            return False

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            _LOGGER.debug(f"is_on 체크: 디바이스 데이터를 찾을 수 없음 - {self._root_uuid}")
            return False

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._switch_subdevice.get("subUuid"):
                current_value = subdevice.get("value")
                # 다양한 형식의 "on" 값들 체크
                possible_on_values = [DEVICE_VALUE_ON, "1", "true", "True", "ON", "on"]
                is_on = current_value in possible_on_values
                
                _LOGGER.debug(f"조명 상태 상세 체크 - {self._nickname}:")
                _LOGGER.debug(f"  서브디바이스 UUID: {subdevice.get('subUuid')}")
                _LOGGER.debug(f"  현재 값: '{current_value}' (type: {type(current_value)})")
                _LOGGER.debug(f"  가능한 ON 값들: {possible_on_values}")
                _LOGGER.debug(f"  결과: {'ON' if is_on else 'OFF'}")
                
                return is_on

        _LOGGER.debug(f"is_on 체크: 서브디바이스를 찾을 수 없음 - UUID: {self._switch_subdevice.get('subUuid')}")
        return False

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환"""
        return self.coordinator.last_update_success and self._switch_subdevice is not None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """조명 켜기"""
        if not self._switch_subdevice:
            _LOGGER.error("스위치 서브디바이스를 찾을 수 없습니다")
            return

        await self._send_command(DEVICE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """조명 끄기"""
        if not self._switch_subdevice:
            _LOGGER.error("스위치 서브디바이스를 찾을 수 없습니다")
            return

        await self._send_command(DEVICE_OFF)

    async def _send_command(self, value: str) -> None:
        """디바이스 제어 명령 전송"""
        if not self._switch_subdevice:
            _LOGGER.error(f"스위치 서브디바이스가 없어 제어할 수 없음: {self._nickname}")
            return
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
        
        # 전송될 JSON 구조 상세 로깅

        
        # 중요: 에러 발생 가능성 체크
        validation_errors = []
        if not device_data.get('rootUuid'):
            validation_errors.append("rootUuid 누락")
        if not device_data.get('subDevice') or len(device_data.get('subDevice', [])) == 0:
            validation_errors.append("subDevice 누락 또는 비어있음")
        if not device_data['subDevice'][0].get('subUuid'):
            validation_errors.append("subDevice UUID 누락")

        if validation_errors:
            _LOGGER.error("데이터 유효성 검사 실패: %s", ", ".join(validation_errors))
            return

        _LOGGER.debug("조명 제어 요청: %s -> %s", self._nickname, value)
        success = await self._auth_manager.send_device_command(device_data)

        if not success:
            _LOGGER.error(
                "조명 제어 실패: %s (value=%s)",
                self._nickname,
                value,
            )

        await self.coordinator.async_request_refresh()


    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()