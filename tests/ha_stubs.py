"""Lightweight Home Assistant stubs for helper-level tests.

These stubs intentionally cover only the import surface needed by the tests.
They are not a replacement for Home Assistant runtime tests.
"""

from __future__ import annotations

import sys
import types
from enum import IntFlag


def install_homeassistant_stubs() -> None:
    """Install minimal Home Assistant modules into sys.modules."""
    if "homeassistant" in sys.modules:
        return

    aiohttp = types.ModuleType("aiohttp")
    voluptuous = types.ModuleType("voluptuous")
    ha = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    config_entries = types.ModuleType("homeassistant.config_entries")
    const = types.ModuleType("homeassistant.const")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    entity = types.ModuleType("homeassistant.helpers.entity")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    restore_state = types.ModuleType("homeassistant.helpers.restore_state")
    sensor = types.ModuleType("homeassistant.components.sensor")
    fan = types.ModuleType("homeassistant.components.fan")
    light = types.ModuleType("homeassistant.components.light")
    switch = types.ModuleType("homeassistant.components.switch")

    class ConfigFlow:
        def __init_subclass__(cls, **kwargs):
            super().__init_subclass__()

    class ConfigEntry:
        pass

    class OptionsFlowWithConfigEntry:
        pass

    class DataUpdateCoordinator:
        def __init__(self, *args, **kwargs):
            pass

    class UpdateFailed(Exception):
        pass

    class ClientSession:
        pass

    class ClientError(Exception):
        pass

    class Schema:
        def __init__(self, schema):
            self.schema = schema

    class _Marker:
        def __init__(self, key, default=None):
            self.key = key
            self.default = default

    def Optional(key, default=None):
        return _Marker(key, default)

    def Required(key, default=None):
        return _Marker(key, default)

    class HomeAssistant:
        pass

    class DeviceInfo(dict):
        pass

    class AddEntitiesCallback:
        pass

    class CoordinatorEntity:
        def __init__(self, coordinator):
            self.coordinator = coordinator

    class SensorEntity:
        pass

    class FanEntity:
        pass

    class LightEntity:
        pass

    class SwitchEntity:
        pass

    class RestoreEntity:
        pass

    class FanEntityFeature(IntFlag):
        TURN_ON = 1
        TURN_OFF = 2
        SET_SPEED = 4
        PRESET_MODE = 8

    class SensorDeviceClass:
        POWER = "power"
        GAS = "gas"
        WATER = "water"
        PM10 = "pm10"
        PM25 = "pm25"
        CO2 = "co2"
        TEMPERATURE = "temperature"
        HUMIDITY = "humidity"

    class SensorStateClass:
        MEASUREMENT = "measurement"
        TOTAL_INCREASING = "total_increasing"

    class ColorMode:
        ONOFF = "onoff"

    def callback(func):
        return func

    def async_get_clientsession(hass):
        return None

    config_entries.ConfigFlow = ConfigFlow
    config_entries.ConfigEntry = ConfigEntry
    config_entries.OptionsFlowWithConfigEntry = OptionsFlowWithConfigEntry

    const.CONF_NAME = "name"
    const.STATE_ON = "on"
    const.CONCENTRATION_MICROGRAMS_PER_CUBIC_METER = "ug/m3"
    const.CONCENTRATION_PARTS_PER_MILLION = "ppm"
    const.PERCENTAGE = "%"

    class UnitOfPower:
        WATT = "W"

    class UnitOfTemperature:
        CELSIUS = "C"

    class Platform:
        LIGHT = "light"
        CLIMATE = "climate"
        SWITCH = "switch"
        FAN = "fan"
        SENSOR = "sensor"

    const.Platform = Platform
    const.UnitOfPower = UnitOfPower
    const.UnitOfTemperature = UnitOfTemperature

    core.HomeAssistant = HomeAssistant
    core.callback = callback

    aiohttp_client.async_get_clientsession = async_get_clientsession
    entity.DeviceInfo = DeviceInfo
    entity_platform.AddEntitiesCallback = AddEntitiesCallback
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.UpdateFailed = UpdateFailed
    restore_state.RestoreEntity = RestoreEntity

    sensor.SensorDeviceClass = SensorDeviceClass
    sensor.SensorEntity = SensorEntity
    sensor.SensorStateClass = SensorStateClass

    fan.FanEntity = FanEntity
    fan.FanEntityFeature = FanEntityFeature
    light.LightEntity = LightEntity
    light.ColorMode = ColorMode
    switch.SwitchEntity = SwitchEntity
    aiohttp.ClientSession = ClientSession
    aiohttp.ClientError = ClientError
    voluptuous.Schema = Schema
    voluptuous.Optional = Optional
    voluptuous.Required = Required

    sys.modules.update(
        {
            "aiohttp": aiohttp,
            "voluptuous": voluptuous,
            "homeassistant": ha,
            "homeassistant.components": components,
            "homeassistant.config_entries": config_entries,
            "homeassistant.const": const,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.aiohttp_client": aiohttp_client,
            "homeassistant.helpers.entity": entity,
            "homeassistant.helpers.entity_platform": entity_platform,
            "homeassistant.helpers.update_coordinator": update_coordinator,
            "homeassistant.helpers.restore_state": restore_state,
            "homeassistant.components.sensor": sensor,
            "homeassistant.components.fan": fan,
            "homeassistant.components.light": light,
            "homeassistant.components.switch": switch,
        }
    )
