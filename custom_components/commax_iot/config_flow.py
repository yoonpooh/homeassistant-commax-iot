"""Commax IoT 설정 흐름"""
import logging
import uuid

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .auth import CommaxApiError, CommaxAuthManager, CommaxAuthenticationError
from .const import (
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

MIN_UPDATE_INTERVAL = 5
MAX_UPDATE_INTERVAL = 3600


def _validate_update_interval(value) -> int:
    """업데이트 간격을 검증하고 정수로 반환."""
    interval = int(value)
    if interval < MIN_UPDATE_INTERVAL or interval > MAX_UPDATE_INTERVAL:
        raise ValueError
    return interval


class CommaxIoTConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Commax IoT 설정 흐름 핸들러"""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """옵션 플로우 핸들러 반환."""
        return CommaxIoTOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        """사용자 입력 단계 처리"""
        errors = {}

        if user_input is not None:
            try:
                try:
                    update_interval = _validate_update_interval(
                        user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                    )
                except (TypeError, ValueError):
                    errors["base"] = "invalid_interval"
                else:
                    # 중복 확인
                    await self.async_set_unique_id(user_input[CONF_USER_ID])
                    self._abort_if_unique_id_configured()

                    # mobileUuid 자동 생성
                    mobile_uuid = str(uuid.uuid4()).upper()

                    # 인증 테스트
                    session = async_get_clientsession(self.hass)
                    auth_manager = CommaxAuthManager(
                        mobile_uuid=mobile_uuid,
                        user_id=user_input[CONF_USER_ID],
                        user_pass=user_input[CONF_USER_PASS],
                        session=session,
                    )

                    try:
                        # 리소스 번호 자동 획득
                        resource_no = await auth_manager.get_resource_no()
                        if not resource_no:
                            _LOGGER.warning("리소스 번호를 찾을 수 없습니다")
                            errors["base"] = "no_resource"
                        else:
                            # 리소스 번호 설정 후 디바이스 목록 조회
                            auth_manager.set_resource_no(resource_no)
                            devices = await auth_manager.get_device_list()
                            if not devices:
                                _LOGGER.warning(
                                    "리소스에 등록된 디바이스가 없습니다 - resource_no: %s",
                                    resource_no,
                                )
                                errors["base"] = "no_devices"
                            else:
                                # 자동 생성/획득된 값들을 data에 추가
                                entry_data = {
                                    **user_input,
                                    CONF_UPDATE_INTERVAL: update_interval,
                                    CONF_MOBILE_UUID: mobile_uuid,
                                    CONF_RESOURCE_NO: resource_no,
                                }
                                return self.async_create_entry(
                                    title=user_input.get(CONF_NAME, NAME),
                                    data=entry_data,
                                )
                    except CommaxAuthenticationError:
                        _LOGGER.warning(
                            "Commax 인증에 실패했습니다 - 사용자 ID: %s",
                            user_input[CONF_USER_ID],
                        )
                        errors["base"] = "auth"
                    except CommaxApiError as err:
                        _LOGGER.warning("Commax API 통신 중 오류가 발생했습니다: %s", err)
                        errors["base"] = "cannot_connect"

            except Exception:
                _LOGGER.exception("설정 중 예상치 못한 오류 발생")
                errors["base"] = "unknown"

        password_field = str

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=NAME): str,
                    vol.Required(CONF_USER_ID): str,
                    vol.Required(CONF_USER_PASS): password_field,
                    vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL): int,
                }
            ),
            errors=errors,
        )


class CommaxIoTOptionsFlow(config_entries.OptionsFlow):
    """Commax IoT 옵션 설정 흐름."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """옵션 초기 단계."""
        errors = {}

        if user_input is not None:
            try:
                update_interval = _validate_update_interval(
                    user_input.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
                )
                return self.async_create_entry(
                    title="",
                    data={CONF_UPDATE_INTERVAL: update_interval},
                )
            except (TypeError, ValueError):
                errors["base"] = "invalid_interval"

        current_interval = self.config_entry.options.get(
            CONF_UPDATE_INTERVAL,
            self.config_entry.data.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL, default=current_interval): int,
                }
            ),
            errors=errors,
        )
