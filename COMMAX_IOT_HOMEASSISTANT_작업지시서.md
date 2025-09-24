# Commax IoT HomeAssistant 통합 구성요소 개발 작업지시서

## 프로젝트 개요
Commax IoT 시스템을 HomeAssistant에 연동하기 위한 Custom Integration 개발

## 지원 디바이스 유형
1. **조명 (Light)** - 스위치 제어
2. **보일러 (Thermostat)** - 온도 센서 및 온도 제어
3. **콘센트 (Switch)** - 대기전력 차단 스위치
4. **환기시스템 (Fan)** - 환기 모드 제어

## API 인증 정보

### 인증 엔드포인트
```
POST https://gauth-v2.commaxcloud.net/v2/oauth/user/authorize
```

### 필수 설정값
```yaml
- clientSecret: (사용자 제공 필요)
- mobileUuid: (사용자 제공 필요)
- userId: (사용자 아이디)
- userPass: (사용자 비밀번호)
- resourceNo: (리소스 번호)
```

### 인증 요청 구조
```json
{
  "clientSecret": "string",
  "user": {
    "mobileUuid": "string",
    "osCode": "IOS",
    "grantType": "password",
    "userPass": "string",
    "userId": "string",
    "password": "encoded_password"
  },
  "clientId": "APP-IOS-com.commax.iphomeiot"
}
```

### 인증 응답 구조
```json
{
  "resultCode": "E0000",
  "resultMessage": "string",
  "accessToken": "string",
  "tokenType": "Bearer",
  "refreshToken": "string",
  "expireIn": 3600
}
```

## API 엔드포인트

### 디바이스 목록 조회
```
GET https://iot-v2.commaxcloud.net:443/v2/resource/device/list?resourceNo={resourceNo}
Authorization: Bearer {accessToken}
```

### 디바이스 제어
```
POST https://iot-v2.commaxcloud.net:443/v2/command
Authorization: Bearer {accessToken}
```

## 디바이스 데이터 구조

### 공통 디바이스 구조
```json
{
  "commaxDevice": "light|boiler|standbyPowerSwitch|fanSystem",
  "rootDevice": "string",
  "rootUuid": "string",
  "nickname": "string",
  "subDevice": [
    {
      "subUuid": "string",
      "sort": "string",
      "type": "read|readWrite",
      "value": "string",
      "scale": ["array_of_values"],
      "subOption": ["array_of_options"]
    }
  ]
}
```

### 조명 디바이스
- **commaxDevice**: `"light"`
- **주요 subDevice.sort**: `"switchBinary"`
- **제어값**: `"0"` (꺼짐), `"1"` (켜짐)

### 보일러 디바이스
- **commaxDevice**: `"boiler"`
- **주요 subDevice.sort**:
  - `"airTemperature"` (현재온도, 읽기전용)
  - `"thermostatMode"` (난방모드)
  - `"thermostatSetpoint"` (목표온도)
- **thermostatMode 값**: `"0"` (꺼짐), `"1"` (켜짐)
- **온도값**: 문자열 (예: `"22.5"`)

### 콘센트 디바이스
- **commaxDevice**: `"standbyPowerSwitch"`
- **rootDevice**: `"switch"`
- **주요 subDevice.sort**: `"switchBinary"`
- **제어값**: `"0"` (꺼짐), `"1"` (켜짐)

### 환기시스템 디바이스
- **commaxDevice**: `"fanSystem"`
- **rootDevice**: `"switch"`
- **주요 subDevice.sort**: `"fanMode"`
- **제어값**: `"0"` (bypass), `"1"` (manual), `"2"` (auto)

## 제어 명령 구조

### 일반 디바이스 제어
```json
{
  "commands": {
    "cgpCommand": [
      {
        "cgp": {
          "command": "set",
          "object": {
            "subDevice": [
              {
                "value": "1",
                "funcCommand": "set",
                "type": "readWrite",
                "subUuid": "device_sub_uuid",
                "sort": "switchBinary"
              }
            ],
            "rootUuid": "device_root_uuid",
            "nickname": "device_nickname",
            "rootDevice": "device_root_device"
          }
        },
        "resourceNo": "user_resource_no"
      }
    ]
  }
}
```

## 개발 구현 요구사항

### 1. Configuration 설정
```python
DOMAIN = "commax_iot"

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required("client_secret"): cv.string,
        vol.Required("mobile_uuid"): cv.string,
        vol.Required("user_id"): cv.string,
        vol.Required("user_pass"): cv.string,
        vol.Required("resource_no"): cv.string,
        vol.Optional("update_interval", default=30): cv.positive_int,
    })
}, extra=vol.ALLOW_EXTRA)
```

### 2. 인증 관리자 클래스
```python
class CommaxAuthManager:
    async def authenticate() -> bool
    async def get_access_token() -> str
    async def refresh_token_if_needed() -> bool
    async def get_device_list() -> List[dict]
    async def send_device_command(device_data) -> bool
```

### 3. 플랫폼별 구현

#### Light Platform
```python
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    # light 디바이스 필터링 및 entity 생성
    pass

class CommaxLight(LightEntity):
    async def async_turn_on(**kwargs):
        # API 호출: value="1"
        pass

    async def async_turn_off(**kwargs):
        # API 호출: value="0"
        pass
```

#### Climate Platform (보일러)
```python
class CommaxThermostat(ClimateEntity):
    async def async_set_temperature(**kwargs):
        # thermostatSetpoint 제어
        pass

    async def async_set_hvac_mode(hvac_mode):
        # thermostatMode 제어
        pass
```

#### Switch Platform (콘센트)
```python
class CommaxSwitch(SwitchEntity):
    async def async_turn_on(**kwargs):
        # switchBinary value="1"
        pass

    async def async_turn_off(**kwargs):
        # switchBinary value="0"
        pass
```

#### Fan Platform (환기시스템)
```python
class CommaxFan(FanEntity):
    async def async_set_preset_mode(preset_mode):
        # fanMode 제어: bypass=0, manual=1, auto=2
        pass
```

### 4. 상태 업데이트
- 주기적으로 디바이스 상태 조회 (기본 30초)
- 토큰 만료 30분 전 자동 갱신
- 401 오류 시 토큰 재발급 후 재시도

### 5. 오류 처리
- 네트워크 오류 시 재시도 로직
- 인증 실패 시 사용자 알림
- API 응답 resultCode 검증 (성공: "E0000")

## 파일 구조
```
custom_components/commax_iot/
├── __init__.py
├── manifest.json
├── config_flow.py
├── const.py
├── auth.py
├── light.py
├── climate.py
├── switch.py
└── fan.py
```

## 주의사항
1. 모든 API 호출 시 Bearer 토큰 필수
2. 토큰 만료시간 관리 중요
3. subUuid와 sort 값으로 정확한 서브디바이스 식별
4. 모든 제어값은 문자열로 전송
5. 에러 응답 시 resultCode와 resultMessage 확인

## 참고 구현
기존 Homebridge 플러그인의 `src/commaxAuth.ts` 파일에 모든 API 호출 로직이 구현되어 있음