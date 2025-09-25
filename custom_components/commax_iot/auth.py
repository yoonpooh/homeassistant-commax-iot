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


            async with self._session.post(AUTH_URL, json=auth_data) as response:
                if response.status != 200:
                    return False
                result = await response.json()

            if result.get("resultCode") != API_SUCCESS_CODE:
                return False

            self._access_token = result.get("accessToken")
            self._refresh_token = result.get("refreshToken")
            expire_in = result.get("expireIn", 3600)
            self._token_expires_at = int(time.time()) + expire_in
            self._authenticated = True

            return True

        except Exception:
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
            return await self.authenticate()

        return True

    async def get_device_list(self) -> List[Dict]:
        """디바이스 목록 조회"""
        token = await self.get_access_token()
        if not token:
            return []

        try:
            headers = {"Authorization": f"Bearer {token}"}
            url = f"{DEVICE_LIST_URL}?resourceNo={self._resource_no}"

            async with self._session.get(url, headers=headers) as response:
                if response.status == 401:
                    self._authenticated = False
                    token = await self.get_access_token()
                    if not token:
                        return []
                    headers["Authorization"] = f"Bearer {token}"
                    async with self._session.get(url, headers=headers) as retry_response:
                        if retry_response.status != 200:
                            return []
                        result = await retry_response.json()
                elif response.status != 200:
                    return []
                else:
                    result = await response.json()

            if result.get("resultCode") != API_SUCCESS_CODE:
                return []

            resource = result.get("resource", {})
            return resource.get("devices", {}).get("object", [])

        except Exception:
            return []

    async def send_device_command(self, device_data: Dict) -> bool:
        """디바이스 제어 명령 전송"""
        _LOGGER.warning("API 명령 전송 시작 - device: %s", device_data.get('nickname', 'Unknown'))

        token = await self.get_access_token()
        if not token:
            _LOGGER.warning("API 명령 전송 실패 - 토큰 없음")
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
                        return False
                    headers["Authorization"] = f"Bearer {token}"
                    async with self._session.post(
                        COMMAND_URL, json=command_data, headers=headers
                    ) as retry_response:
                        if retry_response.status != 200:
                            return False
                        result = await retry_response.json()
                elif response.status != 200:
                    return False
                else:
                    result = await response.json()

            success = result and result.get("resultCode") == API_SUCCESS_CODE
            _LOGGER.warning("API 응답 결과 - success: %s, resultCode: %s, resultMessage: %s",
                          success,
                          result.get("resultCode") if result else "No result",
                          result.get("resultMessage", "No message") if result else "No result")
            return success

        except Exception as e:
            _LOGGER.warning("API 명령 전송 예외 발생: %s", str(e))
            return False
