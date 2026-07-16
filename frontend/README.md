# EchoLog Frontend

React 기반의 음성 녹음 및 시간순 기록 확인 UI입니다.
브라우저 마이크로 녹음하거나 음성 파일을 업로드하면, 백엔드 API를 통해 시간순 기록과 원본 전사를 받아 보여줍니다.

---

## 기술 스택

| 항목 | 기술 | 선택 이유 |
|------|------|-----------|
| 프레임워크 | React 19 + Vite | 빠른 개발 환경, HMR, ES Module 기반 빌드 |
| 스타일 | Vanilla CSS | 별도 라이브러리 없이 직접 제어 |
| 오디오 처리 | Web Audio API + ScriptProcessorNode | 브라우저 내장 API로 WAV 직접 인코딩 |
| HTTP 통신 | Fetch API | 별도 라이브러리 없이 `multipart/form-data` 전송 |
| 린터 | oxlint | Rust 기반 고속 린터 |

---

## 디렉토리 구조

```
frontend/
├── src/
│   ├── App.jsx                  # 단일 페이지 — 상태 기반 뷰 전환
│   ├── App.css                  # 컴포넌트 스타일
│   ├── index.css                # 전역 스타일 (폰트, 리셋)
│   ├── main.jsx                 # React 앱 진입점
│   ├── hooks/
│   │   └── useAudioRecorder.js  # 브라우저 녹음 훅
│   └── services/
│       └── api.js               # 백엔드 API 호출
├── index.html
├── package.json
└── vite.config.js
```

---

## 핵심 모듈 설명

### `useAudioRecorder.js` — 브라우저 녹음 훅

Web Audio API를 직접 사용해 브라우저에서 마이크 녹음을 처리합니다.

```
navigator.mediaDevices.getUserMedia()
    ↓ MediaStream → AudioContext
    ↓ ScriptProcessorNode (4096 샘플 단위 수집)
    ↓ Float32Array 버퍼에 누적
    ↓ stopRecording() 호출 시
    ↓ mergeAudioBuffers() → encodeWav()
    ↓ Blob (audio/wav) 반환
```

| 함수 | 역할 |
|------|------|
| `startRecording()` | 마이크 접근 요청 → 오디오 수집 시작, 타이머 시작 |
| `stopRecording()` | 수집된 버퍼를 WAV로 인코딩 → Blob 반환, 리소스 정리 |

**WAV 직접 인코딩 이유:**  
`MediaRecorder`는 브라우저마다 출력 포맷이 다릅니다 (Chrome: webm, Safari: mp4 등). RTZR API 호환성을 위해 WAV 헤더를 직접 작성해 일관된 포맷으로 변환합니다.

---

### `App.jsx` — 상태 기반 단일 페이지

앱 전체를 4가지 상태로 관리합니다. 상태에 따라 다른 화면을 렌더링합니다.

```
idle → recording → processing → done
  ↑                               |
  └───────── handleReset() ───────┘
```

| 상태 | 화면 |
|------|------|
| `idle` | 녹음 시작 버튼 + 파일 업로드 |
| `recording` | 경과 시간 + 녹음 완료 버튼 |
| `processing` | 스피너 + 대기 메시지 |
| `done` | 오늘 하루 요약 영역 + 시간순 기록 + 원본 전사 토글 |

파일 업로드도 지원합니다. wav, mp3, m4a, mp4, flac, amr 포맷을 받아 동일한 API 엔드포인트로 전송합니다.

---

### `services/api.js` — 백엔드 API 호출

```js
POST http://localhost:8000/api/transcribe
  Body: multipart/form-data { file: Blob, keywords?: string }
  Returns: { raw_transcript, timeline, paragraphs, processing, mode, processing_time }
```

요청은 최대 5분 30초 동안 기다리며, 시간 초과와 백엔드 연결 실패를 구분해
사용자에게 오류 메시지를 표시합니다.

---

## 실행 방법

```bash
cd frontend

# 의존성 설치
npm install

# 개발 서버 실행
npm run dev
```

`http://localhost:5173` 에서 확인할 수 있습니다.  
백엔드 서버(`http://localhost:8000`)가 함께 실행되어 있어야 합니다.

---

## 사용 흐름

1. **🎤 녹음 시작** — 마이크 권한 허용 후 하루를 편하게 말하기
2. **⏹ 녹음 완료** — 자동으로 WAV 인코딩 후 백엔드로 전송
3. **결과 확인** — 녹음 시작 후 경과 시각 순서로 정리된 문단 확인
4. **원본 전사 보기** (선택) — 필터 전 전사문과 비교

또는 **음성 파일 직접 업로드**로도 동일하게 동작합니다.
