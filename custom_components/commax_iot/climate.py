"""Commax IoT 보일러 플랫폼"""
import logging
from typing import Any, Optional

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DEVICE_OFF,
    DEVICE_TYPE_BOILER,
    DOMAIN,
    SUBDEVICE_AIR_TEMPERATURE,
    SUBDEVICE_THERMOSTAT_MODE,
    SUBDEVICE_THERMOSTAT_SETPOINT,
)
from .device import (
    build_device_command,
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
    """보일러 플랫폼 설정"""
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
        if device_data.get("commaxDevice") == DEVICE_TYPE_BOILER:
            entities.append(CommaxThermostat(coordinator, auth_manager, device_data))
            _LOGGER.debug(
                "보일러 디바이스 등록: %s (UUID: %s)",
                device_data.get("nickname"),
                device_data.get("rootUuid"),
            )

    if entities:
        _LOGGER.info("총 %d개의 보일러 디바이스 등록됨", len(entities))
        async_add_entities(entities, True)
    else:
        _LOGGER.debug("등록할 보일러 디바이스가 없습니다")


class CommaxThermostat(CoordinatorEntity, ClimateEntity):
    """Commax IoT 보일러 엔터티"""

    def __init__(self, coordinator, auth_manager, device_data):
        """보일러 엔터티 초기화"""
        super().__init__(coordinator)
        self._auth_manager = auth_manager
        self._device_data = device_data
        self._root_uuid = device_data.get("rootUuid")
        self._nickname = device_data.get("nickname", "Commax Thermostat")

        self._temp_subdevice = None
        self._mode_subdevice = None
        self._setpoint_subdevice = None

        for subdevice in device_data.get("subDevice", []):
            sort_type = subdevice.get("sort")
            if sort_type == SUBDEVICE_AIR_TEMPERATURE:
                self._temp_subdevice = subdevice
            elif sort_type == SUBDEVICE_THERMOSTAT_MODE and subdevice.get("type") == "readWrite":
                self._mode_subdevice = subdevice
            elif sort_type == SUBDEVICE_THERMOSTAT_SETPOINT and subdevice.get("type") == "readWrite":
                self._setpoint_subdevice = subdevice

        self._attr_unique_id = f"{DOMAIN}_{self._root_uuid}_climate"
        self._attr_name = self._nickname
        self._attr_temperature_unit = UnitOfTemperature.CELSIUS
        self._attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT]
        self._attr_supported_features = ClimateEntityFeature.TARGET_TEMPERATURE

        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._root_uuid)},
            name=self._nickname,
            manufacturer="Commax",
            model=device_data.get("rootDevice", "Thermostat"),
        )

        self._attr_min_temp = 5.0
        self._attr_max_temp = 40.0
        self._attr_target_temperature_step = 0.5

    @property
    def current_temperature(self) -> Optional[float]:
        """현재 온도 반환"""
        if not self._temp_subdevice:
            return None

        return self._live_float(self._temp_subdevice, 0)

    @property
    def target_temperature(self) -> Optional[float]:
        """목표 온도 반환"""
        if not self._setpoint_subdevice:
            return None

        return self._live_float(self._setpoint_subdevice, 20)

    def _live_float(self, subdevice: dict, missing: float) -> Optional[float]:
        current = get_current_subdevice(self.coordinator, self._root_uuid, subdevice.get("subUuid"))
        if current is None:
            return None
        try:
            return float(current.get("value", missing))
        except (ValueError, TypeError):
            return None

    @property
    def hvac_mode(self) -> HVACMode:
        """현재 HVAC 모드 반환"""
        if not self._mode_subdevice:
            _LOGGER.debug("보일러 %s: mode_subdevice가 없어 OFF 모드 반환", self._nickname)
            return HVACMode.OFF

        subdevice = get_current_subdevice(
            self.coordinator, self._root_uuid, self._mode_subdevice.get("subUuid")
        )
        if subdevice is None:
            _LOGGER.debug("보일러 %s: 모드 서브디바이스를 찾을 수 없어 OFF 모드 반환", self._nickname)
            return HVACMode.OFF

        current_value = str(subdevice.get("value", "")).lower()
        mode = HVACMode.HEAT if current_value == "heat" else HVACMode.OFF
        _LOGGER.debug("보일러 %s: 현재 모드 값 '%s' -> %s", self._nickname, current_value, mode)
        return mode

    @property
    def available(self) -> bool:
        """디바이스가 사용 가능한지 반환"""
        return (
            self.coordinator.last_update_success
            and self._mode_subdevice is not None
            and self._setpoint_subdevice is not None
        )

    async def async_set_temperature(self, **kwargs: Any) -> None:
        """목표 온도 설정"""
        hvac_mode_raw = kwargs.get("hvac_mode")
        normalized_mode = None

        if hvac_mode_raw is not None:
            normalized_mode = self._normalize_hvac_mode(hvac_mode_raw)
            if normalized_mode is None:
                _LOGGER.warning(
                    "보일러 %s: 지원하지 않는 HVAC 모드 요청 - %s",
                    self._nickname,
                    hvac_mode_raw,
                )
            else:
                await self.async_set_hvac_mode(normalized_mode)
                if normalized_mode == HVACMode.OFF:
                    _LOGGER.debug(
                        "보일러 %s: HVAC OFF 요청과 함께 받은 온도 명령을 무시합니다",
                        self._nickname,
                    )
                    return

        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None or not self._setpoint_subdevice:
            return

        effective_mode = normalized_mode or self.hvac_mode
        if effective_mode == HVACMode.OFF:
            _LOGGER.debug(
                "보일러 %s: 현재 HVAC 모드가 OFF라 온도 명령을 생략합니다",
                self._nickname,
            )
            return

        _LOGGER.debug(
            "보일러 온도 설정 요청: %s -> %s°C (HVAC 모드: %s)",
            self._nickname,
            temperature,
            effective_mode,
        )
        await self._send_command(self._setpoint_subdevice, str(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """HVAC 모드 설정"""
        normalized_mode = self._normalize_hvac_mode(hvac_mode)
        if normalized_mode is None:
            _LOGGER.warning(
                "보일러 %s: 알 수 없는 HVAC 모드 요청 - %s",
                self._nickname,
                hvac_mode,
            )
            return

        if not self._mode_subdevice:
            _LOGGER.warning("보일러 %s: mode_subdevice가 없어 HVAC 모드 설정 불가", self._nickname)
            return

        if normalized_mode not in (HVACMode.HEAT, HVACMode.OFF):
            _LOGGER.warning(
                "보일러 %s: 지원하지 않는 HVAC 모드 요청 - %s",
                self._nickname,
                normalized_mode,
            )
            return

        value = "heat" if normalized_mode == HVACMode.HEAT else DEVICE_OFF
        _LOGGER.debug(
            "보일러 %s: HVAC 모드 설정 요청 %s -> %s (값: %s)",
            self._nickname,
            normalized_mode,
            "heat" if normalized_mode == HVACMode.HEAT else "off",
            value,
        )
        await self._send_command(self._mode_subdevice, value)

    async def _send_command(self, subdevice: dict, value: str) -> None:
        current_device = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not current_device:
            _LOGGER.warning("보일러 %s: 코디네이터에서 디바이스 데이터를 찾을 수 없음", self._nickname)
            return

        device_data = build_device_command(
            current_device, current_device.get("nickname"), build_set_command(subdevice, value)
        )
        _LOGGER.debug("보일러 %s: API 명령 전송 - device_data: %s", self._nickname, device_data)
        success = await self._auth_manager.send_device_command(device_data)

        if success:
            if not update_subdevice_value(self.coordinator, self._root_uuid, subdevice.get("subUuid"), value):
                _LOGGER.warning(
                    "보일러 %s: 대상 서브디바이스 찾을 수 없음 - UUID: %s",
                    self._nickname,
                    subdevice.get("subUuid"),
                )
            self.async_write_ha_state()
        else:
            _LOGGER.warning("보일러 %s: API 명령 실패 - 로컬 상태 업데이트 안함", self._nickname)

        schedule_refresh(self.coordinator)

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()

    def _normalize_hvac_mode(self, hvac_mode: Any) -> Optional[HVACMode]:
        """HVAC 모드 입력을 표준 Enum으로 변환"""
        if isinstance(hvac_mode, HVACMode):
            return hvac_mode
        if isinstance(hvac_mode, str):
            try:
                return HVACMode(hvac_mode.lower())
            except ValueError:
                return None
        if isinstance(hvac_mode, (int, float)):
            try:
                hvac_int = int(hvac_mode)
            except (TypeError, ValueError):
                return None
            if hvac_int == 0:
                return HVACMode.OFF
            if hvac_int == 1:
                return HVACMode.HEAT
            return None
        return None
