"""Commax IoT 통합 구성요소"""
import asyncio
import logging
from datetime import timedelta

import aiohttp
import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth import CommaxAuthManager
from .const import (
    CONF_CLIENT_SECRET,
    CONF_MOBILE_UUID,
    CONF_RESOURCE_NO,
    CONF_UPDATE_INTERVAL,
    CONF_USER_ID,
    CONF_USER_PASS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Required(CONF_CLIENT_SECRET): cv.string,
                vol.Required(CONF_MOBILE_UUID): cv.string,
                vol.Required(CONF_USER_ID): cv.string,
                vol.Required(CONF_USER_PASS): cv.string,
                vol.Required(CONF_RESOURCE_NO): cv.string,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): cv.positive_int,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """통합 구성요소 설정"""
    hass.data.setdefault(DOMAIN, {})

    if DOMAIN in config:
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN, context={"source": "import"}, data=config[DOMAIN]
            )
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """설정 항목에서 통합 구성요소 설정"""
    session = async_get_clientsession(hass)

    auth_manager = CommaxAuthManager(
        client_secret=entry.data[CONF_CLIENT_SECRET],
        mobile_uuid=entry.data[CONF_MOBILE_UUID],
        user_id=entry.data[CONF_USER_ID],
        user_pass=entry.data[CONF_USER_PASS],
        resource_no=entry.data[CONF_RESOURCE_NO],
        session=session,
    )

    coordinator = CommaxDataUpdateCoordinator(
        hass,
        auth_manager,
        update_interval=entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
    )

    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "auth_manager": auth_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """설정 항목 언로드"""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


class CommaxDataUpdateCoordinator(DataUpdateCoordinator):
    """Commax IoT 데이터 업데이트 코디네이터"""

    def __init__(self, hass: HomeAssistant, auth_manager: CommaxAuthManager, update_interval: int):
        """코디네이터 초기화"""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=update_interval),
        )
        self.auth_manager = auth_manager
        self._devices = {}

    async def _async_update_data(self):
        """데이터 업데이트"""
        try:
            devices = await self.auth_manager.get_device_list()

            device_data = {}
            for device in devices:
                root_uuid = device.get("rootUuid")
                if root_uuid:
                    device_data[root_uuid] = device

            self._devices = device_data
            return device_data

        except Exception as err:
            raise UpdateFailed(f"데이터 업데이트 실패: {err}") from err

    def get_device_by_uuid(self, root_uuid: str):
        """UUID로 디바이스 조회"""
        return self._devices.get(root_uuid)