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
    DEVICE_ON,
    DEVICE_TYPE_BOILER,
    DOMAIN,
    SUBDEVICE_AIR_TEMPERATURE,
    SUBDEVICE_THERMOSTAT_MODE,
    SUBDEVICE_THERMOSTAT_SETPOINT,
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

    await coordinator.async_refresh()

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

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return None

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._temp_subdevice.get("subUuid"):
                try:
                    return float(subdevice.get("value", 0))
                except (ValueError, TypeError):
                    return None

        return None

    @property
    def target_temperature(self) -> Optional[float]:
        """목표 온도 반환"""
        if not self._setpoint_subdevice:
            return None

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return None

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._setpoint_subdevice.get("subUuid"):
                try:
                    return float(subdevice.get("value", 20))
                except (ValueError, TypeError):
                    return None

        return None

    @property
    def hvac_mode(self) -> HVACMode:
        """현재 HVAC 모드 반환"""
        if not self._mode_subdevice:
            return HVACMode.OFF

        device_data = self.coordinator.get_device_by_uuid(self._root_uuid)
        if not device_data:
            return HVACMode.OFF

        for subdevice in device_data.get("subDevice", []):
            if subdevice.get("subUuid") == self._mode_subdevice.get("subUuid"):
                return HVACMode.HEAT if subdevice.get("value") == DEVICE_ON else HVACMode.OFF

        return HVACMode.OFF

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
        temperature = kwargs.get(ATTR_TEMPERATURE)
        if temperature is None or not self._setpoint_subdevice:
            _LOGGER.error(f"온도 설정 불가 - temperature: {temperature}, setpoint_subdevice: {self._setpoint_subdevice is not None}")
            return

        _LOGGER.debug("보일러 온도 설정 요청: %s -> %s°C", self._nickname, temperature)
        await self._send_temperature_command(str(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        """HVAC 모드 설정"""
        if not self._mode_subdevice:
            _LOGGER.error(f"HVAC 모드 설정 불가 - mode_subdevice가 없음: {self._nickname}")
            return

        value = DEVICE_ON if hvac_mode == HVACMode.HEAT else DEVICE_OFF
        _LOGGER.debug(
            "보일러 모드 설정 요청: %s -> %s (값: %s)",
            self._nickname,
            hvac_mode,
            value,
        )
        await self._send_mode_command(value)

    async def _send_temperature_command(self, temperature: str) -> None:
        """온도 설정 명령 전송"""
        _LOGGER.debug("보일러 온도 제어 요청: %s -> %s°C", self._nickname, temperature)

        device_data = {
            "subDevice": [
                {
                    "value": temperature,
                    "funcCommand": "set",
                    "type": "readWrite",
                    "subUuid": self._setpoint_subdevice.get("subUuid"),
                    "sort": SUBDEVICE_THERMOSTAT_SETPOINT,
                }
            ],
            "rootUuid": self._root_uuid,
            "nickname": self._nickname,
            "rootDevice": self._device_data.get("rootDevice"),
        }

        _LOGGER.debug("전송할 온도 명령 데이터: %s", device_data)
        success = await self._auth_manager.send_device_command(device_data)
        
        # 온도 설정에는 대안 값 시도를 하지 않음 (숫자 값이므로)
        
        if not success:
            _LOGGER.error(
                "보일러 온도 제어 실패: %s (temperature=%s)",
                self._nickname,
                temperature,
            )

        await self.coordinator.async_request_refresh()

    async def _send_mode_command(self, mode_value: str) -> None:
        """모드 설정 명령 전송"""
        _LOGGER.debug(
            "보일러 모드 제어 요청: %s -> %s",
            self._nickname,
            mode_value,
        )
        
        # 대안 값들 준비
        alternative_values = []
        if mode_value == DEVICE_ON:
            alternative_values = ["on", "true", "True", "1", "ON"]
        elif mode_value == DEVICE_OFF:
            alternative_values = ["off", "false", "False", "0", "OFF"]
        
        device_data = {
            "subDevice": [
                {
                    "value": mode_value,
                    "funcCommand": "set",
                    "type": "readWrite",
                    "subUuid": self._mode_subdevice.get("subUuid"),
                    "sort": SUBDEVICE_THERMOSTAT_MODE,
                }
            ],
            "rootUuid": self._root_uuid,
            "nickname": self._nickname,
            "rootDevice": self._device_data.get("rootDevice"),
        }

        _LOGGER.debug("전송할 모드 명령 데이터: %s", device_data)
        success = await self._auth_manager.send_device_command(device_data)
        
        # 첫 번째 시도가 실패한 경우 대안 값들 시도
        if not success and alternative_values:
            _LOGGER.debug("기본 모드 값 '%s' 실패, 대안 값 시도", mode_value)
            for alt_value in alternative_values:
                _LOGGER.debug("대안 모드 값 시도: '%s'", alt_value)
                device_data["subDevice"][0]["value"] = alt_value
                success = await self._auth_manager.send_device_command(device_data)
                if success:
                    _LOGGER.debug("대안 모드 값 '%s' 성공", alt_value)
                    break
                else:
                    _LOGGER.debug("대안 모드 값 '%s' 실패", alt_value)

        if not success:
            _LOGGER.error(
                "보일러 모드 제어 실패: %s (mode_value=%s)",
                self._nickname,
                mode_value,
            )

        await self.coordinator.async_request_refresh()

    @callback
    def _handle_coordinator_update(self) -> None:
        """코디네이터 업데이트 처리"""
        self.async_write_ha_state()