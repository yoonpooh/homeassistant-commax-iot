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
        _LOGGER.warning("디바이스 데이터를 가져올 수 없어 조명 엔터티를 생성할 수 없습니다")
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
                _LOGGER.warning(f"⚠️ 조명 디바이스에 제어 가능한 스위치가 없음: {device_data.get('nickname')}")
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
        _LOGGER.warning("등록된 조명 디바이스가 없습니다")


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

        _LOGGER.warning(f"홍어시스턴트에서 조명 켜기 요청: {self._nickname}")
        await self._send_command(DEVICE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """조명 끄기"""
        if not self._switch_subdevice:
            _LOGGER.error("스위치 서브디바이스를 찾을 수 없습니다")
            return

        _LOGGER.warning(f"홍어시스턴트에서 조명 끄기 요청: {self._nickname}")
        await self._send_command(DEVICE_OFF)

    async def _send_command(self, value: str) -> None:
        """디바이스 제어 명령 전송"""
        if not self._switch_subdevice:
            _LOGGER.error(f"스위치 서브디바이스가 없어 제어할 수 없음: {self._nickname}")
            return

        # 현재 디바이스 상태 로깅
        _LOGGER.warning(f"=== 조명 제어 시작 - {self._nickname} ===")
        _LOGGER.warning(f"요청된 동작: {value} ({'켜기' if value == DEVICE_ON else '끄기'})")
        _LOGGER.warning(f"현재 상태: {'켜짐' if self.is_on else '꺼짐'}")
        _LOGGER.warning(f"루트 UUID: {self._root_uuid}")
        _LOGGER.warning(f"스위치 서브디바이스 UUID: {self._switch_subdevice.get('subUuid')}")
        _LOGGER.debug(f"스위치 서브디바이스 전체 정보: {self._switch_subdevice}")
        
        # 원본 디바이스 데이터도 로깅
        current_device = self.coordinator.get_device_by_uuid(self._root_uuid)
        if current_device:
            _LOGGER.debug(f"현재 디바이스 전체 정보: {current_device}")
            for idx, subdev in enumerate(current_device.get('subDevice', [])):
                _LOGGER.debug(f"서브디바이스[{idx}]: UUID={subdev.get('subUuid')}, 타입={subdev.get('sort')}, 값={subdev.get('value')}, 권한={subdev.get('type')}")

        # 다양한 값 형식으로 시도해보기 위한 로깅
        _LOGGER.warning(f"const.py에서 정의된 값들:")
        _LOGGER.warning(f"  DEVICE_ON = '{DEVICE_ON}' (켜기)")
        _LOGGER.warning(f"  DEVICE_OFF = '{DEVICE_OFF}' (끄기)")
        _LOGGER.warning(f"  DEVICE_VALUE_ON = '{DEVICE_VALUE_ON}' (상태 체크용)")
        _LOGGER.warning(f"  DEVICE_VALUE_OFF = '{DEVICE_VALUE_OFF}' (상태 체크용)")
        _LOGGER.warning(f"기본 전송할 값: '{value}'")
        
        # 대안 값들 준비 (실패 시 시도해볼 값들)
        alternative_values = []
        if value == DEVICE_ON:
            alternative_values = ["on", "true", "True", "1", "ON"]
        elif value == DEVICE_OFF:
            alternative_values = ["off", "false", "False", "0", "OFF"]
        
        _LOGGER.warning(f"대안 값들: {alternative_values}")
        
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
        _LOGGER.warning(f"JSON 구조 상세:")
        _LOGGER.warning(f"  rootUuid: {device_data['rootUuid']}")
        _LOGGER.warning(f"  nickname: {device_data['nickname']}")
        _LOGGER.warning(f"  rootDevice: {device_data['rootDevice']}")
        _LOGGER.warning(f"  subDevice[0].value: {device_data['subDevice'][0]['value']}")
        _LOGGER.warning(f"  subDevice[0].subUuid: {device_data['subDevice'][0]['subUuid']}")
        _LOGGER.warning(f"  subDevice[0].sort: {device_data['subDevice'][0]['sort']}")
        _LOGGER.warning(f"  subDevice[0].funcCommand: {device_data['subDevice'][0]['funcCommand']}")
        _LOGGER.warning(f"  subDevice[0].type: {device_data['subDevice'][0]['type']}")

        _LOGGER.warning(f"전송할 명령 데이터: {device_data}")
        
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
            _LOGGER.warning("✅ 데이터 유효성 검사 통과")

        success = await self._auth_manager.send_device_command(device_data)

        # 첫 번째 시도가 실패한 경우 대안 값들 시도
        if not success and alternative_values:
            _LOGGER.warning(f"기본 값 '{value}' 실패, 대안 값들 시도 중...")
            for i, alt_value in enumerate(alternative_values, 1):
                _LOGGER.warning(f"대안 값 시도 [{i}/{len(alternative_values)}]: '{alt_value}'")
                
                # device_data 업데이트
                device_data["subDevice"][0]["value"] = alt_value
                _LOGGER.debug(f"수정된 명령 데이터: {device_data}")
                
                success = await self._auth_manager.send_device_command(device_data)
                if success:
                    _LOGGER.warning(f"✅ 대안 값 '{alt_value}' 성공! ({i}/{len(alternative_values)})")
                    _LOGGER.warning(f"⚠️ 추후 const.py에서 DEVICE_ON/DEVICE_OFF 값을 '{alt_value}' 스타일로 변경 고려")
                    break
                else:
                    _LOGGER.warning(f"❌ 대안 값 '{alt_value}' 실패 ({i}/{len(alternative_values)})")
                    
            if not success:
                _LOGGER.error(f"❌ 기본 값 및 모든 대안 값 실패. 시도한 값들: [{value}] + {alternative_values}")

        if success:
            _LOGGER.warning(f"✅ 조명 제어 API 호출 성공 - {self._nickname}")
            # 잠시 대기 후 상태 업데이트
            await asyncio.sleep(1)
            await self.coordinator.async_request_refresh()
            _LOGGER.warning(f"조명 상태 업데이트 요청 완료 - {self._nickname}")
            
            # 업데이트 후 상태 확인
            await asyncio.sleep(1)
            updated_device = self.coordinator.get_device_by_uuid(self._root_uuid)
            if updated_device:
                for subdev in updated_device.get('subDevice', []):
                    if subdev.get('subUuid') == self._switch_subdevice.get('subUuid'):
                        _LOGGER.info(f"업데이트 후 상태: {subdev.get('value')} (예상: {DEVICE_VALUE_ON if value == DEVICE_ON else DEVICE_VALUE_OFF})")
                        expected_value = DEVICE_VALUE_ON if value == DEVICE_ON else DEVICE_VALUE_OFF
                        actual_value = subdev.get('value')
                        _LOGGER.warning(f"상태 변경 결과 분석:")
                        _LOGGER.warning(f"  전송한 값: {value}")
                        _LOGGER.warning(f"  예상 상태: {expected_value}")
                        _LOGGER.warning(f"  실제 상태: {actual_value}")
                        
                        if actual_value == expected_value:
                            _LOGGER.warning("✅ 상태 변경 성공 확인")
                        else:
                            _LOGGER.warning("⚠️ 상태 변경이 반영되지 않음")
                            _LOGGER.warning(f"가능한 원인: API 성공했지만 하드웨어에서 반영 지연 또는 다른 값 형식 필요")
                        break
        else:
            _LOGGER.error(f"❌ 조명 제어 API 호출 실패 - {self._nickname}: value={value}")
            _LOGGER.error("모든 값 형식 시도 실패")
            # 실패 시에도 상태 업데이트를 시도하여 현재 상태 동기화
            await self.coordinator.async_request_refresh()
            
        _LOGGER.warning(f"=== 조명 제어 완료 - {self._nickname} ===")

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()