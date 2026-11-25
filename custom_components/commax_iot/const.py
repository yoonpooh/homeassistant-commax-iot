"""Commax IoT 통합 구성요소의 상수 정의"""

DOMAIN = "commax_iot"
NAME = "COMMAX IoT"
VERSION = "2026.11.26"

# API 엔드포인트
AUTH_URL = "https://gauth-v2.commaxcloud.net/v2/oauth/user/authorize"
GROUP_URL = "https://gauth-v2.commaxcloud.net/v2/group"
IOT_BASE_URL = "https://iot-v2.commaxcloud.net:443/v2"
DEVICE_LIST_URL = f"{IOT_BASE_URL}/resource/device/list"
COMMAND_URL = f"{IOT_BASE_URL}/command"

# 설정 키
CONF_MOBILE_UUID = "mobile_uuid"
CONF_USER_ID = "user_id"
CONF_USER_PASS = "user_pass"
CONF_RESOURCE_NO = "resource_no"
CONF_UPDATE_INTERVAL = "update_interval"

# 기본값
DEFAULT_UPDATE_INTERVAL = 30
DEFAULT_CLIENT_ID = "APP-IOS-com.commax.iphomeiot"
DEFAULT_CLIENT_SECRET = "Yb6SbSWIBMlV59F43eZo-a"
DEFAULT_OS_CODE = "IOS"
DEFAULT_GRANT_TYPE = "password"

# 디바이스 타입
DEVICE_TYPE_LIGHT = "light"
DEVICE_TYPE_BOILER = "boiler"
DEVICE_TYPE_SWITCH = "standbyPowerSwitch"
DEVICE_TYPE_FAN = "fanSystem"

# 서브 디바이스 타입
SUBDEVICE_SWITCH_BINARY = "switchBinary"
SUBDEVICE_ELECTRIC_METER = "electricMeter"
SUBDEVICE_AIR_TEMPERATURE = "airTemperature"
SUBDEVICE_THERMOSTAT_MODE = "thermostatMode"
SUBDEVICE_THERMOSTAT_SETPOINT = "thermostatSetpoint"
SUBDEVICE_FAN_MODE = "modeBinary"
SUBDEVICE_FAN_SPEED = "fanSpeed"

# 디바이스 값
DEVICE_OFF = "off"
DEVICE_ON = "on"

# 실제 API에서 반환되는 값들 (로그 확인 결과)
DEVICE_VALUE_OFF = "off"
DEVICE_VALUE_ON = "on"

# 환기시스템 모드
FAN_MODE_BYPASS = "bypass"
FAN_MODE_MANUAL = "manual"
FAN_MODE_AUTO = "auto"
FAN_DEFAULT_MODE = FAN_MODE_AUTO

# API 응답 코드
API_SUCCESS_CODE = "E0000"

# 토큰 만료 관련 설정 (초)
DEFAULT_TOKEN_EXPIRE = 259200  # 기본 만료 3일
TOKEN_EXPIRE_BUFFER = 60  # 만료 1분 전 재인증 시도

# 명령 반영 확인 (서버가 E0000으로 수락하고도 기기에 전달하지 않는 경우 대비)
COMMAND_VERIFY_DELAY = 5  # 전송 후 반영 여부를 확인하기까지 대기 (초)
COMMAND_RETRY_COUNT = 2  # 반영되지 않았을 때 재전송 횟수

# 플랫폼 목록
PLATFORMS = ["climate", "switch", "fan", "sensor"]
