"""Commax IoT 스위치 플랫폼"""
import asyncio
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
            return False

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return False

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._switch_subdevice.get("subUuid"):
                current_value = subdevice.get("value")
                possible_on_values = [DEVICE_ON, "1", "true", "True", "ON", "on"]
                return current_value in possible_on_values

        return False

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환"""
        return self.coordinator.last_update_success and self._switch_subdevice is not None

    @property
    def device_class(self) -> str:
        """디바이스 클래스 반환"""
        return "outlet"

    async def async_turn_on(self, **kwargs: Any) -> None:
        """스위치 켜기"""
        if not self._switch_subdevice:
            _LOGGER.error("스위치 서브디바이스를 찾을 수 없습니다")
            return
        await self._send_command(DEVICE_ON)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """스위치 끄기"""
        if not self._switch_subdevice:
            _LOGGER.error("스위치 서브디바이스를 찾을 수 없습니다")
            return

        await self._send_command(DEVICE_OFF)

    async def _send_command(self, value: str) -> None:
        """디바이스 제어 명령 전송"""
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

        success = await self._auth_manager.send_device_command(device_data)

        if not success and alternative_values:
            for alt_value in alternative_values:
                device_data["subDevice"][0]["value"] = alt_value
                success = await self._auth_manager.send_device_command(device_data)
                if success:
                    break

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
                break

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()