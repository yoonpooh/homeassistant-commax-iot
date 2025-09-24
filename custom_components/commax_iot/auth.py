"""Commax IoT 인증 관리자"""
import asyncio
import hashlib
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

            # homebridge 플러그인과 동일한 방식으로 패스워드 처리
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

            _LOGGER.info("=== Commax IoT 인증 시작 ===")
            _LOGGER.info(f"사용자 ID: {self._user_id}")
            _LOGGER.info(f"Mobile UUID: {self._mobile_uuid}")
            _LOGGER.info(f"Resource No: {self._resource_no}")
            _LOGGER.info(f"Client Secret: {self._client_secret[:10]}...")
            _LOGGER.info(f"Auth URL: {AUTH_URL}")
            _LOGGER.debug(f"전송할 인증 데이터: {auth_data}")

            async with self._session.post(AUTH_URL, json=auth_data) as response:
                _LOGGER.info(f"HTTP 응답 상태: {response.status}")
                if response.status != 200:
                    _LOGGER.error(f"인증 요청 실패: HTTP {response.status}")
                    return False

                result = await response.json()
                _LOGGER.info(f"인증 응답 코드: {result.get('resultCode')}")

                if result.get("resultCode") != API_SUCCESS_CODE:
                    _LOGGER.error(f"Commax IoT 인증 실패: {result.get('resultCode')} - {result.get('resultMessage', '알 수 없는 오류')}")
                    return False

                self._access_token = result.get("accessToken")
                self._refresh_token = result.get("refreshToken")
                expire_in = result.get("expireIn", 3600)
                self._token_expires_at = int(time.time()) + expire_in
                self._authenticated = True

                _LOGGER.info("=== Commax IoT 인증 성공 ===")
                _LOGGER.info(f"토큰 만료일: {time.ctime(self._token_expires_at)}")
                return True

        except Exception as e:
            _LOGGER.error(f"인증 중 예외 발생: {type(e).__name__}: {e}")
            import traceback
            _LOGGER.error(f"Auth Stack trace: {traceback.format_exc()}")
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
            _LOGGER.debug("토큰 갱신 필요")
            return await self.authenticate()

        return True

    async def get_device_list(self) -> List[Dict]:
        """디바이스 목록 조회"""
        token = await self.get_access_token()
        if not token:
            _LOGGER.error("액세스 토큰을 가져올 수 없음")
            return []

        try:
            headers = {"Authorization": f"Bearer {token}"}
            url = f"{DEVICE_LIST_URL}?resourceNo={self._resource_no}"
            _LOGGER.info(f"디바이스 목록 조회: {url}")

            async with self._session.get(url, headers=headers) as response:
                _LOGGER.info(f"디바이스 목록 HTTP 응답 상태: {response.status}")
                if response.status == 401:
                    self._authenticated = False
                    token = await self.get_access_token()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        async with self._session.get(url, headers=headers) as retry_response:
                            if retry_response.status != 200:
                                _LOGGER.error(f"디바이스 목록 조회 실패: HTTP {retry_response.status}")
                                return []
                            result = await retry_response.json()
                    else:
                        return []
                elif response.status != 200:
                    _LOGGER.error(f"디바이스 목록 조회 실패: HTTP {response.status}")
                    return []
                else:
                    result = await response.json()

                if result.get("resultCode") != API_SUCCESS_CODE:
                    _LOGGER.error(f"디바이스 목록 조회 실패: {result.get('resultMessage', '알 수 없는 오류')}")
                    return []

                # homebridge 플러그인과 동일한 구조로 수정
                resource = result.get("resource", {})
                devices = resource.get("devices", {}).get("object", [])
                _LOGGER.debug(f"{len(devices)}개의 디바이스를 찾았습니다")
                return devices

        except Exception as e:
            _LOGGER.error(f"디바이스 목록 조회 중 오류: {e}")
            return []

    async def send_device_command(self, device_data: Dict) -> bool:
        """디바이스 제어 명령 전송"""
        token = await self.get_access_token()
        if not token:
            _LOGGER.error("액세스 토큰을 가져올 수 없음")
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







            async with self._session.post(COMMAND_URL, json=command_data, headers=headers) as response:
                _LOGGER.info(f"HTTP 응답 상태: {response.status}")
                
                # 응답 헤더 로깅
                _LOGGER.debug(f"Response Headers: {dict(response.headers)}")
                
                if response.status == 401:
                    self._authenticated = False
                    token = await self.get_access_token()
                    if token:
                        headers["Authorization"] = f"Bearer {token}"
                        _LOGGER.info("재인증 후 재시도")
                        async with self._session.post(COMMAND_URL, json=command_data, headers=headers) as retry_response:
                            _LOGGER.info(f"재시도 HTTP 응답 상태: {retry_response.status}")
                            if retry_response.status != 200:
                                response_text = await retry_response.text()
                                _LOGGER.error(f"디바이스 제어 재시도 실패: HTTP {retry_response.status}")
                                _LOGGER.error(f"재시도 응답 내용: {response_text}")
                                return False
                            result = await retry_response.json()
                            _LOGGER.info(f"재시도 API 응답: {result}")
                    else:
                        _LOGGER.error("재인증 실패")
                        return False
                elif response.status != 200:
                    response_text = await response.text()
                    _LOGGER.error(f"디바이스 제어 실패: HTTP {response.status}")
                    _LOGGER.error(f"오류 응답 내용: {response_text}")
                    return False
                else:
                    result = await response.json()


                result_code = result.get("resultCode")
                result_message = result.get('resultMessage', '메시지 없음')
                


                
                if result_code != API_SUCCESS_CODE:
                    _LOGGER.error(f"❌ 디바이스 제어 API 실패: 코드={result_code}, 메시지={result_message}")
                    _LOGGER.error(f"전체 오류 응답: {result}")
                    return False



                return True

        except Exception as e:
            _LOGGER.error(f"디바이스 제어 중 예외 발생: {type(e).__name__}: {e}")
            import traceback
            _LOGGER.error(f"Stack trace: {traceback.format_exc()}")
            return False