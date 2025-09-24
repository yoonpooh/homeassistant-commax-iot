"""Commax IoT 조명 플랫폼"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.light import LightEntity, PLATFORM_SCHEMA, ColorMode
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
    NAME,
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
                _LOGGER.info(f"=== 조명 디바이스 등록 성공 ===")
                _LOGGER.info(f"이름: {device_data.get('nickname')}")
                _LOGGER.info(f"UUID: {device_data.get('rootUuid')}")
                _LOGGER.info(f"unique_id: {light_entity._attr_unique_id}")
                _LOGGER.info(f"초기 상태: {'켜짐' if light_entity.is_on else '꺼짐'}")
            else:
                _LOGGER.debug(f"사용 가능한 서브디바이스들:")
                for idx, subdev in enumerate(device_data.get("subDevice", [])):
                    _LOGGER.debug(f"  [{idx}] sort={subdev.get('sort')}, type={subdev.get('type')}, value={subdev.get('value')}")

    if entities:
        _LOGGER.info(f"=== 조명 플랫폼 설정 완료 ===")
        _LOGGER.info(f"총 {len(entities)}개의 조명 디바이스 등록됨")
        for entity in entities:
            _LOGGER.info(f"  - {entity._nickname} (UUID: {entity._root_uuid})")
        async_add_entities(entities, True)
    else:


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

        # 현재 디바이스 상태 로깅
        _LOGGER.debug(f"스위치 서브디바이스 전체 정보: {self._switch_subdevice}")
        
        # 원본 디바이스 데이터도 로깅
        current_device = self.coordinator.get_device_by_uuid(self._root_uuid)
        if current_device:
            _LOGGER.debug(f"현재 디바이스 전체 정보: {current_device}")
            for idx, subdev in enumerate(current_device.get('subDevice', [])):
                _LOGGER.debug(f"서브디바이스[{idx}]: UUID={subdev.get('subUuid')}, 타입={subdev.get('sort')}, 값={subdev.get('value')}, 권한={subdev.get('type')}")


        
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
            _LOGGER.error(f"❌ 데이터 유효성 검사 실패: {', '.join(validation_errors)}")
            return
        else:

        success = await self._auth_manager.send_device_command(device_data)

        # 첫 번째 시도가 실패한 경우 대안 값들 시도
        if success:
            # 잠시 대기 후 상태 업데이트
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
            
            # 업데이트 후 상태 확인
            await asyncio.sleep(1)
            updated_device = self.coordinator.get_device_by_uuid(self._root_uuid)
            if updated_device:
                for subdev in updated_device.get('subDevice', []):
                    if subdev.get('subUuid') == self._switch_subdevice.get('subUuid'):
                        _LOGGER.info(f"업데이트 후 상태: {subdev.get('value')} (예상: {DEVICE_VALUE_ON if value == DEVICE_ON else DEVICE_VALUE_OFF})")
                        expected_value = DEVICE_VALUE_ON if value == DEVICE_ON else DEVICE_VALUE_OFF
                        actual_value = subdev.get('value')
                        
                        if actual_value == expected_value:
                        else:
                        break
        else:
            _LOGGER.error(f"❌ 조명 제어 API 호출 실패 - {self._nickname}: value={value}")
            _LOGGER.error("모든 값 형식 시도 실패")
            # 실패 시에도 상태 업데이트를 시도하여 현재 상태 동기화
            await self.coordinator.async_request_refresh()


    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()