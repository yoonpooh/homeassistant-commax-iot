"""Commax IoT 설정 흐름"""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import CommaxApiError, CommaxAuthManager, CommaxAuthenticationError
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
    """Commax IoT 설정 흐름 핸들러"""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """사용자 입력 단계 처리"""
        errors = {}

        if user_input is not None:
            try:
                # 중복 확인
                await self.async_set_unique_id(user_input[CONF_USER_ID])
                self._abort_if_unique_id_configured()

                # 인증 테스트
                session = async_get_clientsession(self.hass)
                auth_manager = CommaxAuthManager(
                    client_secret=user_input[CONF_CLIENT_SECRET],
                    mobile_uuid=user_input[CONF_MOBILE_UUID],
                    user_id=user_input[CONF_USER_ID],
                    user_pass=user_input[CONF_USER_PASS],
                    resource_no=user_input[CONF_RESOURCE_NO],
                    session=session,
                )

                try:
                    devices = await auth_manager.get_device_list()
                except CommaxAuthenticationError:
                    _LOGGER.warning("Commax 인증에 실패했습니다 - 사용자 ID: %s", user_input[CONF_USER_ID])
                    errors["base"] = "auth"
                except CommaxApiError as err:
                    _LOGGER.warning("Commax API 통신 중 오류가 발생했습니다: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    if not devices:
                        _LOGGER.warning(
                            "리소스 번호에 해당하는 디바이스가 없습니다 - resource_no: %s",
                            user_input[CONF_RESOURCE_NO],
                        )
                        errors["base"] = "no_devices"
                    else:
                        return self.async_create_entry(
                            title=user_input.get(CONF_NAME, NAME),
                            data=user_input,
                        )

            except Exception:
                _LOGGER.exception("설정 중 예상치 못한 오류 발생")
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Optional(CONF_NAME, default=NAME): str,
                vol.Required(CONF_CLIENT_SECRET, description={"type": "password"}): str,
                vol.Required(CONF_MOBILE_UUID): str,
                vol.Required(CONF_USER_ID): str,
                vol.Required(CONF_USER_PASS, description={"type": "password"}): str,
                vol.Required(CONF_RESOURCE_NO): str,
                vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
            }),
            errors=errors,
        )