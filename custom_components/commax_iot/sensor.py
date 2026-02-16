"""Commax IoT 센서 플랫폼 (전력/환경/미터링)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
    PERCENTAGE,
    UnitOfPower,
    UnitOfTemperature,
)
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


def _safe_device_class(name: str) -> SensorDeviceClass | None:
    """Return SensorDeviceClass attribute if available in current HA version."""
    return getattr(SensorDeviceClass, name, None)


def _safe_state_class(name: str) -> SensorStateClass | None:
    """Return SensorStateClass attribute if available in current HA version."""
    return getattr(SensorStateClass, name, None)


# 월패드/통합 센서 매핑
SENSOR_MAPPING: dict[str, dict[str, Any]] = {
    # electricMeter는 코맥스 API에서 순간 전력값으로 내려오는 케이스를 기본값으로 가정
    "electricMeter": {
        "label": "Electric Power",
        "device_class": _safe_device_class("POWER"),
        "unit": UnitOfPower.WATT,
        "state_class": _safe_state_class("MEASUREMENT"),
        "icon": "mdi:flash",
    },
    # 가스/수도/온수는 누적량으로 내려오는 경우가 많아 TOTAL_INCREASING 기본 적용
    # 환경에 따라 순간 유량이면 unit/state_class 조정이 필요할 수 있음.
    "gasMeter": {
        "label": "Gas",
        "device_class": _safe_device_class("GAS"),
        "unit": "m³",
        "state_class": _safe_state_class("TOTAL_INCREASING"),
        "icon": "mdi:fire",
    },
    "waterMeter": {
        "label": "Water",
        "device_class": _safe_device_class("WATER"),
        "unit": "m³",
        "state_class": _safe_state_class("TOTAL_INCREASING"),
        "icon": "mdi:water",
    },
    "warmMeter": {
        "label": "Warm Water",
        "device_class": _safe_device_class("WATER"),
        "unit": "m³",
        "state_class": _safe_state_class("TOTAL_INCREASING"),
        "icon": "mdi:water-boiler",
    },
    "heatMeter": {
        "label": "Heating Power",
        "device_class": _safe_device_class("POWER"),
        "unit": "kW",
        "state_class": _safe_state_class("MEASUREMENT"),
        "icon": "mdi:radiator",
    },
    "airQuality10": {
        "label": "PM10",
        "device_class": _safe_device_class("PM10"),
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "state_class": _safe_state_class("MEASUREMENT"),
        "icon": "mdi:blur",
    },
    "airQuality2.5": {
        "label": "PM2.5",
        "device_class": _safe_device_class("PM25"),
        "unit": CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "state_class": _safe_state_class("MEASUREMENT"),
        "icon": "mdi:blur",
    },
    "co2": {
        "label": "CO2",
        "device_class": _safe_device_class("CO2"),
        "unit": CONCENTRATION_PARTS_PER_MILLION,
        "state_class": _safe_state_class("MEASUREMENT"),
        "icon": "mdi:molecule-co2",
    },
    "airTemperature": {
        "label": "Temperature",
        "device_class": _safe_device_class("TEMPERATURE"),
        "unit": UnitOfTemperature.CELSIUS,
        "state_class": _safe_state_class("MEASUREMENT"),
        "icon": "mdi:thermometer",
    },
    "humidity": {
        "label": "Humidity",
        "device_class": _safe_device_class("HUMIDITY"),
        "unit": PERCENTAGE,
        "state_class": _safe_state_class("MEASUREMENT"),
        "icon": "mdi:water-percent",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """센서 플랫폼 설정."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]

    if not coordinator.data:
        await coordinator.async_refresh()

    if not coordinator.data:
        coordinator.data = {}

    entities: list[SensorEntity] = []
    entities.extend(_build_switch_power_sensors(coordinator))
    entities.extend(_build_generic_sensors(coordinator))

    if entities:
        _LOGGER.info("Commax IoT: 총 %d개의 센서를 등록했습니다.", len(entities))
        async_add_entities(entities, True)


def _build_switch_power_sensors(coordinator) -> list[SensorEntity]:
    """기존 스위치 대기전력 센서를 생성한다."""
    entities: list[SensorEntity] = []

    for device_data in coordinator.data.values():
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

    return entities


def _build_generic_sensors(coordinator) -> list[SensorEntity]:
    """월패드/통합 센서를 생성한다."""
    entities: list[SensorEntity] = []

    for device_data in coordinator.data.values():
        # 스위치는 전용 센서에서 처리하므로 중복 방지
        if (
            device_data.get("commaxDevice") == DEVICE_TYPE_SWITCH
            and device_data.get("rootDevice") == "switch"
        ):
            continue

        for subdevice in device_data.get("subDevice", []):
            sort_type = subdevice.get("sort", "")
            sensor_info = SENSOR_MAPPING.get(sort_type)
            if not sensor_info:
                continue

            entities.append(
                CommaxGenericSensor(
                    coordinator=coordinator,
                    device_data=device_data,
                    subdevice=subdevice,
                    sensor_info=sensor_info,
                    sensor_type=sort_type,
                )
            )

    return entities


class CommaxPowerSensor(CoordinatorEntity, SensorEntity):
    """(기존) 스마트 스위치 대기전력 센서."""

    def __init__(self, coordinator, device_data: dict, meter_subdevice: dict) -> None:
        super().__init__(coordinator)
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
                return _parse_subdevice_value(subdevice)

        return None

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환."""
        return self.coordinator.last_update_success and self._meter_subdevice is not None

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리."""
        self.async_write_ha_state()


class CommaxGenericSensor(CoordinatorEntity, SensorEntity):
    """범용 코맥스 센서 구현체."""

    def __init__(
        self,
        coordinator,
        device_data: dict,
        subdevice: dict,
        sensor_info: dict,
        sensor_type: str,
    ) -> None:
        super().__init__(coordinator)
        self._root_uuid = device_data.get("rootUuid")
        self._sub_uuid = subdevice.get("subUuid")
        device_name = device_data.get("nickname", "Commax Device")
        sensor_label = _resolve_subdevice_label(subdevice, sensor_info, sensor_type)

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_{self._sub_uuid}_{sensor_type}"
        self._attr_name = f"{device_name} {sensor_label}"
        self._attr_device_class = sensor_info.get("device_class")
        self._attr_native_unit_of_measurement = sensor_info.get("unit")
        self._attr_icon = sensor_info.get("icon")
        self._attr_state_class = sensor_info.get("state_class")

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=device_name,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Wallpad"),
        )

    @property
    def native_value(self) -> Optional[float]:
        """센서 값 반환 (정밀도 계산 포함)."""
        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return None

        target_sub = next(
            (
                sub
                for sub in device_data.get("subDevice", [])
                if sub.get("subUuid") == self._sub_uuid
            ),
            None,
        )
        if not target_sub:
            return None

        return _parse_subdevice_value(target_sub)

    @property
    def available(self) -> bool:
        """센서 사용 가능 여부."""
        return self.coordinator.last_update_success

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리."""
        self.async_write_ha_state()


def _resolve_subdevice_label(subdevice: dict, sensor_info: dict, sensor_type: str) -> str:
    """기존 통합 네이밍 컨벤션에 맞춰 서브센서 표시명을 결정한다."""
    for key in ("nickname", "name", "label", "title"):
        value = subdevice.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    mapping_label = sensor_info.get("label")
    if isinstance(mapping_label, str) and mapping_label.strip():
        return mapping_label.strip()

    return sensor_type


def _parse_subdevice_value(subdevice: dict) -> Optional[float]:
    """subDevice value/precision 조합을 float로 변환."""
    raw_value = subdevice.get("value")

    try:
        precision = int(subdevice.get("precision") or 0)
    except (TypeError, ValueError):
        precision = 0

    try:
        value = float(raw_value)
    except (TypeError, ValueError):
        return None

    if precision > 0:
        value /= 10**precision

    return value
