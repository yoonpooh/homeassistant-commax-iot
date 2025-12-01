"""Commax IoT 센서 플랫폼 (전력 사용량)."""
import logging
from typing import Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_TYPE_SWITCH,
    DOMAIN,
    SUBDEVICE_ELECTRIC_METER,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """센서 플랫폼 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    entities = []

    if not coordinator.data:
        await coordinator.async_refresh()

    if not coordinator.data:
        coordinator.data = {}

    for _, device_data in coordinator.data.items():
        if (
            device_data.get("commaxDevice") == DEVICE_TYPE_SWITCH
            and device_data.get("rootDevice") == "switch"
        ):
            meter_subdevice = next(
                (
                    subdevice
                    for subdevice in device_data.get("subDevice", [])
                    if subdevice.get("sort") == SUBDEVICE_ELECTRIC_METER
                ),
                None,
            )

            if meter_subdevice:
                entities.append(
                    CommaxPowerSensor(
                        coordinator=coordinator,
                        device_data=device_data,
                        meter_subdevice=meter_subdevice,
                    )
                )

    if entities:
        _LOGGER.info("총 %d개의 전력 센서 등록됨", len(entities))
        async_add_entities(entities, True)


class CommaxPowerSensor(CoordinatorEntity, SensorEntity):
    """전력 사용량 센서."""

    def __init__(self, coordinator, device_data: dict, meter_subdevice: dict) -> None:
        super().__init__(coordinator)
        self._device_data = device_data
        self._root_uuid = device_data.get("rootUuid")
        self._nickname = device_data.get("nickname", "Commax Outlet")
        self._meter_subdevice = meter_subdevice

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_{meter_subdevice.get('subUuid')}_power"
        self._attr_name = f"{self._nickname} Power"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_native_unit_of_measurement = UnitOfPower.WATT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=self._nickname,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Outlet"),
        )

    @property
    def native_value(self) -> Optional[float]:
        """현재 전력(W) 반환."""
        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return None

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._meter_subdevice.get("subUuid"):
                raw_value = subdevice.get("value")
                precision_raw = subdevice.get("precision") or self._meter_subdevice.get("precision")

                try:
                    precision = int(precision_raw) if precision_raw is not None else 0
                except (TypeError, ValueError):
                    precision = 0

                try:
                    value = float(raw_value)
                except (TypeError, ValueError):
                    _LOGGER.debug(
                        "전력 센서 값 변환 실패 - raw: %s, device: %s",
                        raw_value,
                        self._nickname,
                    )
                    return None

                if precision > 0:
                    value /= 10**precision

                return value

        return None

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환."""
        return self.coordinator.last_update_success and self._meter_subdevice is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리."""
        self.async_write_ha_state()
