"""Commax IoT 인증 관리자"""
from __future__ import annotations

import logging
import time
from typing import Dict, List, Optional

import aiohttp

from .const import (
    API_SUCCESS_CODE,
    AUTH_URL,
    COMMAND_URL,
    DEFAULT_CLIENT_ID,
    DEFAULT_GRANT_TYPE,
    DEFAULT_OS_CODE,
    DEVICE_LIST_URL,
    TOKEN_EXPIRE_BUFFER,
)

_LOGGER = logging.getLogger(__name__)


class CommaxAuthManager:
    """Commax IoT API 인증 관리자"""

    def __init__(
        self,
        client_secret: str,
        mobile_uuid: str,
        user_id: str,
        user_pass: str,
        resource_no: str,
        session: aiohttp.ClientSession,
    ):
        self._client_secret = client_secret
        self._mobile_uuid = mobile_uuid
        self._user_id = user_id
        self._user_pass = user_pass
        self._resource_no = resource_no
        self._session = session

        self._access_token: Optional[str] = None
        self._refresh_token: Optional[str] = None
        self._token_expires_at: Optional[int] = None
        self._authenticated = False

    async def authenticate(self) -> bool:
        """인증 수행"""
        try:
            import urllib.parse

            encoded_password = urllib.parse.quote(self._user_pass)
            auth_data = {
                "clientSecret": self._client_secret,
                "user": {
                    "mobileUuid": self._mobile_uuid,
                    "osCode": DEFAULT_OS_CODE,
                    "grantType": DEFAULT_GRANT_TYPE,
                    "userPass": self._user_pass,
                    "userId": self._user_id,
                    "password": encoded_password,
                },
                "clientId": DEFAULT_CLIENT_ID,
            }

            _LOGGER.debug(
                "Commax IoT 인증 요청: user_id=%s, resource_no=%s",
                self._user_id,
                self._resource_no,
            )

            async with self._session.post(AUTH_URL, json=auth_data) as response:
                _LOGGER.debug("Commax IoT 인증 HTTP 상태: %s", response.status)
                if response.status != 200:
                    _LOGGER.error(
                        "Commax IoT 인증 요청 실패: HTTP %s", response.status
                    )
                    return False

                result = await response.json()

            if result.get("resultCode") != API_SUCCESS_CODE:
                _LOGGER.error(
                    "Commax IoT 인증 실패: %s - %s",
                    result.get("resultCode"),
                    result.get("resultMessage", "알 수 없는 오류"),
                )
                return False

            self._access_token = result.get("accessToken")
            self._refresh_token = result.get("refreshToken")
            expire_in = result.get("expireIn", 3600)
            self._token_expires_at = int(time.time()) + expire_in
            self._authenticated = True

            _LOGGER.info(
                "Commax IoT 인증 성공 (토큰 만료: %s)",
                time.ctime(self._token_expires_at),
            )
            return True

        except Exception:
            _LOGGER.exception("Commax IoT 인증 중 예외 발생")
            return False

    async def get_access_token(self) -> Optional[str]:
        """액세스 토큰 반환"""
        if not self._authenticated:
            if not await self.authenticate():
                return None

        if await self.refresh_token_if_needed():
            return self._access_token

        return None

    async def refresh_token_if_needed(self) -> bool:
        """필요시 토큰 갱신"""
        if not self._token_expires_at:
            return False

        current_time = int(time.time())
        if current_time >= (self._token_expires_at - TOKEN_EXPIRE_BUFFER):
            _LOGGER.debug("Commax IoT 토큰 갱신 필요")
            return await self.authenticate()

        return True

    async def get_device_list(self) -> List[Dict]:
        """디바이스 목록 조회"""
        token = await self.get_access_token()
        if not token:
            _LOGGER.error("Commax IoT 액세스 토큰을 가져올 수 없습니다")
            return []

        try:
            headers = {"Authorization": f"Bearer {token}"}
            url = f"{DEVICE_LIST_URL}?resourceNo={self._resource_no}"
            _LOGGER.debug("Commax IoT 디바이스 목록 요청: %s", url)

            async with self._session.get(url, headers=headers) as response:
                _LOGGER.debug(
                    "Commax IoT 디바이스 목록 HTTP 상태: %s",
                    response.status,
                )
                if response.status == 401:
                    self._authenticated = False
                    token = await self.get_access_token()
                    if not token:
                        return []

                    headers["Authorization"] = f"Bearer {token}"
                    async with self._session.get(
                        url, headers=headers
                    ) as retry_response:
                        if retry_response.status != 200:
                            _LOGGER.error(
                                "디바이스 목록 재시도 실패: HTTP %s",
                                retry_response.status,
                            )
                            return []
                        result = await retry_response.json()
                elif response.status != 200:
                    _LOGGER.error(
                        "디바이스 목록 조회 실패: HTTP %s", response.status
                    )
                    return []
                else:
                    result = await response.json()

            if result.get("resultCode") != API_SUCCESS_CODE:
                _LOGGER.error(
                    "디바이스 목록 조회 실패: %s",
                    result.get("resultMessage", "알 수 없는 오류"),
                )
                return []

            resource = result.get("resource", {})
            devices = resource.get("devices", {}).get("object", [])
            _LOGGER.debug("Commax IoT 디바이스 %d개를 가져왔습니다", len(devices))
            return devices

        except Exception:
            _LOGGER.exception("디바이스 목록 조회 중 오류")
            return []

    async def send_device_command(self, device_data: Dict) -> bool:
        """디바이스 제어 명령 전송"""
        token = await self.get_access_token()
        if not token:
            _LOGGER.error("Commax IoT 액세스 토큰을 가져올 수 없습니다")
            return False

        try:
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
            command_data = {
                "commands": {
                    "cgpCommand": [
                        {
                            "cgp": {
                                "command": "set",
                                "object": device_data,
                            },
                            "resourceNo": self._resource_no,
                        }
                    ]
                }
            }

            async with self._session.post(
                COMMAND_URL, json=command_data, headers=headers
            ) as response:
                _LOGGER.debug(
                    "Commax IoT 디바이스 제어 HTTP 상태: %s",
                    response.status,
                )

                result: Optional[Dict] = None
                if response.status == 401:
                    self._authenticated = False
                    token = await self.get_access_token()
                    if not token:
                        _LOGGER.error("Commax IoT 재인증 실패")
                        return False

                    headers["Authorization"] = f"Bearer {token}"
                    _LOGGER.debug("Commax IoT 디바이스 제어 재시도")
                    async with self._session.post(
                        COMMAND_URL, json=command_data, headers=headers
                    ) as retry_response:
                        _LOGGER.debug(
                            "재시도 HTTP 상태: %s", retry_response.status
                        )
                        if retry_response.status != 200:
                            response_text = await retry_response.text()
                            _LOGGER.error(
                                "디바이스 제어 재시도 실패: HTTP %s",
                                retry_response.status,
                            )
                            _LOGGER.debug(
                                "디바이스 제어 재시도 응답: %s",
                                response_text,
                            )
                            return False
                        result = await retry_response.json()
                elif response.status != 200:
                    response_text = await response.text()
                    _LOGGER.error(
                        "디바이스 제어 실패: HTTP %s", response.status
                    )
                    _LOGGER.debug(
                        "디바이스 제어 오류 응답: %s", response_text
                    )
                    return False
                else:
                    result = await response.json()

            if not result:
                _LOGGER.error("디바이스 제어 응답을 받지 못했습니다")
                return False

            result_code = result.get("resultCode")
            result_message = result.get("resultMessage", "메시지 없음")

            if result_code != API_SUCCESS_CODE:
                _LOGGER.error(
                    "디바이스 제어 실패: 코드=%s, 메시지=%s",
                    result_code,
                    result_message,
                )
                _LOGGER.debug("디바이스 제어 실패 응답: %s", result)
                return False

            return True

        except Exception:
            _LOGGER.exception("디바이스 제어 중 예외 발생")
            return False
