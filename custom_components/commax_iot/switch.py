"""Commax IoT 스위치 플랫폼"""
import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_OFF,
    DEVICE_ON,
    DEVICE_TYPE_SWITCH,
    DOMAIN,
    SUBDEVICE_SWITCH_BINARY,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """스위치 플랫폼 설정"""
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
        if (
            device_data.get("commaxDevice") == DEVICE_TYPE_SWITCH
            and device_data.get("rootDevice") == "switch"
        ):
            # 필수 subDevice 확인
            has_switch = False
            for subdevice in device_data.get("subDevice", []):
                if (subdevice.get("sort") == SUBDEVICE_SWITCH_BINARY and
                    subdevice.get("type") == "readWrite"):
                    has_switch = True
                    break

            if has_switch:
                entities.append(CommaxSwitch(coordinator, auth_manager, device_data))
                _LOGGER.debug(
                    "스위치 디바이스 등록: %s (UUID: %s)",
                    device_data.get("nickname"),
                    device_data.get("rootUuid"),
                )
            else:
                _LOGGER.debug(
                    "스위치 디바이스에 제어 가능한 서브디바이스가 없습니다: %s",
                    device_data.get("nickname"),
                )

    _LOGGER.info("총 %d개의 스위치 디바이스 등록됨", len(entities))
    if entities:
        async_add_entities(entities, True)


class CommaxSwitch(CoordinatorEntity, SwitchEntity):
    """Commax IoT 스위치 엔터티"""

    def __init__(self, coordinator, auth_manager, device_data):
        """스위치 엔터티 초기화"""
        super().__init__(coordinator)
        self._auth_manager = auth_manager
        self._device_data = device_data
        self._root_uuid = device_data.get("rootUuid")
        self._nickname = device_data.get("nickname", "Commax Switch")

        self._switch_subdevice = None
        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("sort") == SUBDEVICE_SWITCH_BINARY and subdevice.get("type") == "readWrite":
                self._switch_subdevice = subdevice
                break

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_switch"
        self._attr_name = self._nickname
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=self._nickname,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Switch"),
        )

    @property
    def is_on(self) -> bool:
        """스위치가 켜져 있는지 반환"""
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
                possible_on_values = [DEVICE_ON, "1", "true", "True", "ON", "on"]
                is_on = current_value in possible_on_values
                
                _LOGGER.debug(f"스위치 상태 상세 체크 - {self._nickname}:")
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
        """스위치 켜기"""
        if not self._switch_subdevice:
            _LOGGER.error("스위치 서브디바이스를 찾을 수 없습니다")
            return
        _LOGGER.debug("스위치 켜기 요청: %s", self._nickname)
        await self._send_command(DEVICE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """스위치 끄기"""
        if not self._switch_subdevice:
            _LOGGER.error("스위치 서브디바이스를 찾을 수 없습니다")
            return

        _LOGGER.debug("스위치 끄기 요청: %s", self._nickname)
        await self._send_command(DEVICE_OFF)

    async def _send_command(self, value: str) -> None:
        """디바이스 제어 명령 전송"""
        _LOGGER.debug(
            "스위치 제어 요청: %s -> %s",
            self._nickname,
            value,
        )
        
        # 대안 값들 준비
        alternative_values = []
        if value == DEVICE_ON:
            alternative_values = ["on", "true", "True", "1", "ON"]
        elif value == DEVICE_OFF:
            alternative_values = ["off", "false", "False", "0", "OFF"]
        
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

        _LOGGER.debug("전송할 스위치 명령 데이터: %s", device_data)
        success = await self._auth_manager.send_device_command(device_data)

        # 첫 번째 시도가 실패한 경우 대안 값들 시도
        if not success and alternative_values:
            _LOGGER.debug("기본 값 '%s' 실패, 대안 값 시도", value)
            for alt_value in alternative_values:
                _LOGGER.debug("대안 값 시도: '%s'", alt_value)
                device_data["subDevice"][0]["value"] = alt_value
                success = await self._auth_manager.send_device_command(device_data)
                if success:
                    _LOGGER.debug("대안 값 '%s' 성공", alt_value)
                    break
                else:
                    _LOGGER.debug("대안 값 '%s' 실패", alt_value)

        if success:
            await self.coordinator.async_request_refresh()
        else:
            _LOGGER.error("스위치 제어 실패: %s (value=%s)", self._nickname, value)
            await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()