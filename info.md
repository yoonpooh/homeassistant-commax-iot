# Commax IoT Integration

이 통합 구성요소는 Commax IoT 스마트홈 시스템을 HomeAssistant에 연결합니다.

## 지원 디바이스

- **조명**: 스위치 제어
- **보일러**: 온도 센서 및 온도 제어
- **콘센트**: 대기전력 차단 스위치
- **환기시스템**: 환기 모드 제어

## 설정 필요 사항

설치 후 다음 정보가 필요합니다:

- Client Secret (Commax 앱에서 추출)
- Mobile UUID (Commax 앱에서 추출)
- 사용자 ID 및 비밀번호
- Resource No

자세한 설정 방법은 [GitHub 저장소](https://github.com/yoonpooh/homeassistant-commax-iot)를 참조하세요.

## 주의사항

이는 비공식 통합 구성요소입니다. Commax에서 공식 지원하지 않으며, API 변경으로 인해 작동이 중단될 수 있습니다.