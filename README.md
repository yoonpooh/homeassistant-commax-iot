# Commax IoT HomeAssistant 통합 구성요소

Commax IoT 시스템을 HomeAssistant에 연동하기 위한 Custom Integration입니다.

## 지원 디바이스

- **조명 (Light)** - 스위치 제어
- **보일러 (Thermostat)** - 온도 센서 및 온도 제어
- **콘센트 (Switch)** - 대기전력 차단 스위치
- **환기시스템 (Fan)** - 환기 모드 제어 (bypass/manual/auto)

## 설치 방법

### HACS를 통한 설치 (권장)

1. HACS > Integrations > Custom repositories
2. 저장소 URL 추가: `https://github.com/yoonpooh/homeassistant-commax-iot`
3. Category: Integration 선택
4. "ADD" 클릭 후 설치

### 수동 설치

1. 이 저장소를 다운로드하거나 클론
2. `custom_components/commax_iot` 폴더를 HomeAssistant의 `config/custom_components/` 디렉토리로 복사
3. HomeAssistant 재시작

## 설정

### HomeAssistant 통합 구성요소 추가

1. **설정 > 기기 및 서비스 > 통합 구성요소 추가**
2. "Commax IoT" 검색 및 선택
3. 다음 정보 입력:
   - **Client Secret**: Commax 앱에서 발급받은 클라이언트 시크릿
   - **Mobile UUID**: 모바일 디바이스 고유 식별자
   - **사용자 ID**: Commax 계정 아이디
   - **비밀번호**: Commax 계정 비밀번호
   - **Resource No**: 리소스 번호
   - **업데이트 간격**: 상태 업데이트 주기 (기본값: 30초)

### YAML 설정 (선택사항)

```yaml
commax_iot:
  client_secret: "your_client_secret"
  mobile_uuid: "your_mobile_uuid"
  user_id: "your_user_id"
  user_pass: "your_password"
  resource_no: "your_resource_no"
  update_interval: 30
```

## 필요한 정보 획득 방법

### Client Secret 및 Mobile UUID

이 정보는 Commax 앱의 네트워크 트래픽을 분석하여 얻을 수 있습니다:

1. 네트워크 모니터링 도구 사용 (예: Charles Proxy, Wireshark)
2. Commax 앱에서 로그인 시도
3. `https://gauth-v2.commaxcloud.net/v2/oauth/user/authorize` 요청에서 확인

### Resource No

1. Commax 앱 로그인 후
2. 디바이스 목록 API 호출에서 확인
3. 또는 앱의 설정에서 확인 가능

## 사용법

### 조명 제어

```yaml
# 조명 켜기
service: light.turn_on
target:
  entity_id: light.commax_living_room

# 조명 끄기
service: light.turn_off
target:
  entity_id: light.commax_living_room
```

### 보일러 제어

```yaml
# 난방 켜기 및 온도 설정
service: climate.set_temperature
target:
  entity_id: climate.commax_thermostat
data:
  temperature: 22.5
  hvac_mode: heat

# 난방 끄기
service: climate.set_hvac_mode
target:
  entity_id: climate.commax_thermostat
data:
  hvac_mode: "off"
```

### 콘센트 제어

```yaml
# 콘센트 켜기
service: switch.turn_on
target:
  entity_id: switch.commax_outlet

# 콘센트 끄기
service: switch.turn_off
target:
  entity_id: switch.commax_outlet
```

### 환기시스템 제어

```yaml
# 환기시스템 모드 설정
service: fan.set_preset_mode
target:
  entity_id: fan.commax_ventilation
data:
  preset_mode: auto  # bypass, manual, auto 중 선택
```

## 문제 해결

### 인증 실패

- Client Secret, Mobile UUID가 올바른지 확인
- 사용자 ID/비밀번호가 정확한지 확인
- Commax 계정이 IoT 서비스에 등록되어 있는지 확인

### 디바이스가 표시되지 않음

- Resource No가 올바른지 확인
- 해당 계정에 연결된 디바이스가 있는지 확인
- HomeAssistant 로그에서 오류 메시지 확인

### 제어가 작동하지 않음

- 네트워크 연결 상태 확인
- API 토큰 만료 여부 확인 (자동으로 갱신됨)
- 디바이스가 온라인 상태인지 확인

## 로그 확인

HomeAssistant 로그에서 디버그 정보 확인:

```yaml
logger:
  default: info
  logs:
    custom_components.commax_iot: debug
```

## 지원

- **이슈 리포트**: [GitHub Issues](https://github.com/yoonpooh/homeassistant-commax-iot/issues)
- **기능 요청**: [GitHub Issues](https://github.com/yoonpooh/homeassistant-commax-iot/issues)

## 라이선스

MIT License

## 주의사항

- 이 통합 구성요소는 비공식적이며 Commax에서 공식 지원하지 않습니다
- API 변경으로 인해 작동이 중단될 수 있습니다
- 개인적인 사용 목적으로만 사용하시기 바랍니다
- 너무 짧은 업데이트 간격은 API 제한에 걸릴 수 있습니다