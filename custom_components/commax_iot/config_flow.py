"""Commax IoT 설정 흐름"""
import logging
from typing import Any, Dict, Optional

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

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
    NAME,
)

_LOGGER = logging.getLogger(__name__)


class CommaxIoTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Commax IoT 설정 흐름"""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """설정 흐름 초기화"""
        self._errors: Dict[str, str] = {}

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """사용자 입력 단계"""
        self._errors = {}

        if user_input is not None:
            valid = await self._test_credentials(
                user_input[CONF_CLIENT_SECRET],
                user_input[CONF_MOBILE_UUID],
                user_input[CONF_USER_ID],
                user_input[CONF_USER_PASS],
                user_input[CONF_RESOURCE_NO],
            )

            if valid:
                return self.async_create_entry(
                    title=user_input.get(CONF_NAME, NAME),
                    data=user_input,
                )

            self._errors["base"] = "auth"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=NAME): str,
                    vol.Required(CONF_CLIENT_SECRET): str,
                    vol.Required(CONF_MOBILE_UUID): str,
                    vol.Required(CONF_USER_ID): str,
                    vol.Required(CONF_USER_PASS): str,
                    vol.Required(CONF_RESOURCE_NO): str,
                    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
                }
            ),
            errors=self._errors,
        )

    async def async_step_import(self, user_input: Optional[Dict[str, Any]] = None) -> FlowResult:
        """YAML에서 가져오기"""
        return await self.async_step_user(user_input)

    async def _test_credentials(
        self,
        client_secret: str,
        mobile_uuid: str,
        user_id: str,
        user_pass: str,
        resource_no: str,
    ) -> bool:
        """자격 증명 테스트"""
        try:
            session = async_get_clientsession(self.hass)
            auth_manager = CommaxAuthManager(
                client_secret=client_secret,
                mobile_uuid=mobile_uuid,
                user_id=user_id,
                user_pass=user_pass,
                resource_no=resource_no,
                session=session,
            )

            if await auth_manager.authenticate():
                devices = await auth_manager.get_device_list()
                if devices:
                    _LOGGER.info(f"인증 성공, {len(devices)}개의 디바이스 발견")
                    return True
                else:
                    _LOGGER.warning("인증은 성공했지만 디바이스가 없습니다")
                    return True

        except Exception as e:
            _LOGGER.error(f"자격 증명 테스트 실패: {e}")

        return False

    @staticmethod
    @config_entries.register_discovery_flow(
        DOMAIN,
        "Commax IoT",
        lambda: None,
        config_entries.CONN_CLASS_CLOUD_POLL,
    )
    def _async_config_flow_discovered(discovery_info):
        """자동 검색 흐름"""
        return CommaxIoTConfigFlow()