"""Commax IoT 통합 구성요소"""
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .auth import CommaxApiError, CommaxAuthManager, CommaxAuthenticationError
from .const import (
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


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """통합 구성요소 설정"""
    hass.data.setdefault(DOMAIN, {})
    return True


def _get_update_interval(entry: ConfigEntry) -> int:
    """설정/옵션에서 업데이트 주기를 가져온다."""
    return int(
        entry.options.get(
            CONF_UPDATE_INTERVAL,
            entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )
    )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """설정 항목에서 통합 구성요소 설정"""
    session = async_get_clientsession(hass)

    auth_manager = CommaxAuthManager(
        mobile_uuid=entry.data[CONF_MOBILE_UUID],
        user_id=entry.data[CONF_USER_ID],
        user_pass=entry.data[CONF_USER_PASS],
        session=session,
        resource_no=entry.data[CONF_RESOURCE_NO],
    )

    coordinator = CommaxDataUpdateCoordinator(
        hass,
        auth_manager,
        update_interval=_get_update_interval(entry),
    )

    await coordinator.async_config_entry_first_refresh()

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "auth_manager": auth_manager,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """옵션 변경 시 통합을 재로드해 새 설정을 반영한다."""
    await hass.config_entries.async_reload(entry.entry_id)


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

        except (CommaxAuthenticationError, CommaxApiError) as err:
            raise UpdateFailed(f"Commax API 오류: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"데이터 업데이트 실패: {err}") from err

    def get_device_by_uuid(self, root_uuid: str):
        """UUID로 디바이스 조회"""
        return self._devices.get(root_uuid)
