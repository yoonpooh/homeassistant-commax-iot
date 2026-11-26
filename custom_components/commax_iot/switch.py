"""Commax IoT 스위치 플랫폼"""
import logging
from typing import Any, Optional

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_OFF,
    DEVICE_ON,
    DEVICE_TYPE_LIGHT,
    DEVICE_TYPE_SWITCH,
    DOMAIN,
    SUBDEVICE_ELECTRIC_METER,
    SUBDEVICE_SWITCH_BINARY,
)
from .device import (
    build_device_command,
    find_subdevice,
    get_current_subdevice,
    schedule_refresh,
    build_set_command,
    update_subdevice_value,
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
        # 대기전력 스위치와 범용 벽 스위치 처리
        if device_data.get("commaxDevice") == DEVICE_TYPE_LIGHT or (
            device_data.get("commaxDevice") == DEVICE_TYPE_SWITCH
            and device_data.get("rootDevice") == "switch"
        ):
            if find_subdevice(device_data, SUBDEVICE_SWITCH_BINARY):
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

        self._switch_subdevice = find_subdevice(device_data, SUBDEVICE_SWITCH_BINARY)
        self._electric_meter_subdevice = find_subdevice(
            device_data, SUBDEVICE_ELECTRIC_METER, read_write=False
        )

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

        subdevice = get_current_subdevice(
            self.coordinator, self._root_uuid, self._switch_subdevice.get("subUuid")
        )
        if subdevice is None or subdevice.get("value") is None:
            return False
        return str(subdevice.get("value")).lower() in {DEVICE_ON, "1", "true"}

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환"""
        return self.coordinator.last_update_success and self._switch_subdevice is not None

    @property
    def current_power_w(self) -> Optional[float]:
        """현재 소비 전력(W) 반환"""
        if not self._electric_meter_subdevice:
            return None

        subdevice = get_current_subdevice(
            self.coordinator, self._root_uuid, self._electric_meter_subdevice.get("subUuid")
        )
        if subdevice is None:
            return None

        raw_value = subdevice.get("value")
        precision_raw = subdevice.get("precision") or self._electric_meter_subdevice.get("precision")

        try:
            precision = int(precision_raw) if precision_raw is not None else 0
        except (TypeError, ValueError):
            precision = 0

        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            _LOGGER.debug(
                "전력 값 변환 실패 - raw: %s, device: %s",
                raw_value,
                self._nickname,
            )
            return None

        if precision > 0:
            value /= 10**precision

        return value

    @property
    def device_class(self) -> str:
        """디바이스 클래스 반환"""
        return (
            "outlet"
            if self._device_data.get("commaxDevice") == DEVICE_TYPE_SWITCH
            else "switch"
        )

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
        success = await self._auth_manager.send_device_command(
            build_device_command(
                self._device_data, self._nickname, build_set_command(self._switch_subdevice, value)
            ),
            extra_light_off_retry=value == DEVICE_OFF
            and self._device_data.get("commaxDevice") == DEVICE_TYPE_LIGHT,
        )

        if success:
            update_subdevice_value(
                self.coordinator, self._root_uuid, self._switch_subdevice.get("subUuid"), value
            )
            self.async_write_ha_state()

        schedule_refresh(self.coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()
