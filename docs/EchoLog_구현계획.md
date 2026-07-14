# EchoLog - 개발 구현 계획

> **Speak naturally. Reflect clearly.**

---

## 프로젝트 개요

EchoLog는 사용자가 말한 하루 이야기를 **RTZR STT API**로 전사하고,  
전사 결과를 **후처리 파이프라인**을 통해 사람이 읽기 좋은 **회고(Reflection)**로 재구성하는 웹 앱입니다.

> 핵심은 STT API 활용 + 전사 결과 후처리 파이프라인입니다. UI는 기능 확인 수준으로 유지합니다.

---

## 기술 스택

| 레이어 | 기술 |
|--------|------|
| Frontend | React (Vite), Vanilla CSS |
| Backend | FastAPI (Python) |
| STT | RTZR Batch STT API |
| LLM (선택) | 미정 — LLM 없이도 Timeline 모드로 동작 |

---

## 시스템 아키텍처

```
[브라우저 녹음]
      ↓ audio file (webm/wav)
[React Frontend]
      ↓ POST /api/transcribe
[FastAPI Backend]
      ↓ POST /v1/authenticate
[RTZR Auth API] → JWT Token
      ↓ POST /v1/transcribe (multipart/form-data)
[RTZR Batch STT API] → transcribe_id
      ↓ GET /v1/transcribe/{id} (polling)
[RTZR STT 결과] → utterances (문단 분리, 추임새 제거 완료)
      ↓
[Transcript Post Processor]
  1. 문단 파싱
  2. 시간순 정렬 (start_at 기준)
  3. 중복 제거
  4. 사건 단위 정리
      ↓
[Reflection Generator]
  - LLM 있음: 구어체 → 서술체 변환
  - LLM 없음: Timeline 형태 그대로 반환
      ↓
[Response JSON] → Frontend 표시
```

---

## RTZR API 활용 근거

| RTZR 기능 | 사용 목적 |
|-----------|----------|
| Authentication | JWT 토큰 발급 (6시간 만료, 캐싱) |
| Batch STT | 음성 파일 전사 요청 |
| Polling | 비동기 전사 완료 확인 |
| `use_disfluency_filter: true` | 추임새(어, 음, 그) 제거 |
| `use_paragraph_splitter: true` | 의미 단위 문단 분리 |
| `use_itn: true` | 숫자/단위 표기 변환 |

**설계 원칙:** RTZR STT가 프로젝트의 중심이고, LLM은 문체를 다듬는 보조 역할만 수행합니다.

---

## 프로젝트 디렉토리 구조

```
echolog/
├── frontend/
│   ├── src/
│   │   ├── App.jsx                  # 단일 페이지 (상태별 뷰)
│   │   ├── App.css
│   │   ├── hooks/
│   │   │   └── useAudioRecorder.js  # Web MediaRecorder API 기반 녹음
│   │   └── services/
│   │       └── api.js               # Backend API 호출
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── backend/
│   ├── app/
│   │   ├── main.py                  # FastAPI 앱 진입점, CORS 설정
│   │   ├── config.py                # 환경변수 로드 (pydantic-settings)
│   │   ├── routers/
│   │   │   └── transcribe.py        # POST /api/transcribe 엔드포인트
│   │   └── services/
│   │       ├── rtzr_client.py       # RTZR API 클라이언트
│   │       ├── transcript_processor.py  # 후처리 파이프라인 (핵심)
│   │       └── reflection_generator.py  # Reflection 생성 (LLM or Timeline)
│   ├── requirements.txt
│   └── .env.example
│
├── .gitignore
├── .env.example
└── README.md
```

---

## 구현 계획 (Phase별)

### ✅ Phase 1 - 프로젝트 기초 설정

- [x] `.gitignore` 생성
- [x] `backend/requirements.txt` 생성
- [ ] 전체 디렉토리 구조 초기화

---

### 🔧 Phase 2 - RTZR STT 클라이언트 구현 (최우선)

**목표:** RTZR API를 정확하게 호출하고 전사 결과를 받아오는 클라이언트 완성

`backend/app/config.py`

- pydantic-settings로 `.env` 로드
- `RTZR_CLIENT_ID`, `RTZR_CLIENT_SECRET` 관리

`backend/app/services/rtzr_client.py`

| 메서드 | 역할 |
|--------|------|
| `get_token()` | JWT 토큰 발급. 6시간 만료 고려해 캐싱 처리 |
| `submit_transcription(audio_bytes)` | 음성 파일 전사 요청 → `transcribe_id` 반환 |
| `poll_result(transcribe_id)` | 완료까지 폴링 (interval 3초, 최대 5분) |
| `transcribe(audio_bytes)` | submit + poll 통합 |

**RTZR RequestConfig:**

```json
{
  "use_disfluency_filter": true,
  "use_paragraph_splitter": true,
  "paragraph_splitter": { "max": 100 },
  "use_itn": true
}
```

**검증:** 실제 음성 파일로 API 호출 후 응답 구조 확인

---

### 🔧 Phase 3 - Transcript Post Processor (프로젝트 핵심)

**목표:** RTZR 전사 결과 → 사람이 읽기 좋은 구조화된 텍스트

`backend/app/services/transcript_processor.py`

```
[RTZR 응답 utterances]
        ↓
1. parse_paragraphs()     — utterance → 문단 리스트로 파싱
        ↓
2. sort_by_time()         — start_at 기준 시간순 정렬
        ↓
3. remove_duplicates()    — SequenceMatcher로 유사 문장 제거 (임계값 0.8)
        ↓
4. group_into_events()    — 시간 간격 기준 사건 단위 그룹핑
        ↓
[ProcessedTranscript]     — 후처리 완료 결과
```

**LLM 없을 때 출력 예시 (Timeline 모드):**

```
• 오늘 발표가 있었는데 긴장이 됐어요. 근데 피드백이 좋았어요.
• 저녁에는 교회 연습을 다녀왔어요.
• 집에 와서 남은 과제를 했어요.
```

**검증:** 샘플 전사 결과로 각 단계 출력 확인

---

### 🔧 Phase 4 - FastAPI 엔드포인트 + Reflection Generator

**목표:** 브라우저에서 받은 음성 파일을 처리하고 결과 반환

`backend/app/services/reflection_generator.py`

- LLM API 키가 있으면 구어체 → 서술체 변환 (새로운 사실 생성 금지)
- 없으면 Timeline 형태 그대로 반환 (fallback)

`backend/app/routers/transcribe.py`

```
POST /api/transcribe
  Request: multipart/form-data { file: audio }
  Response: {
    "reflection": "...",        # 정제된 회고
    "raw_transcript": "...",    # RTZR 원본 전사
    "paragraphs": [...],        # 문단 목록
    "mode": "reflection|timeline"
  }
```

`backend/app/main.py`

- FastAPI 앱 생성
- CORS 설정 (Frontend 허용)
- 라우터 등록

---

### 🔧 Phase 5 - Frontend 최소 구현

**목표:** 녹음하고 결과를 확인할 수 있는 최소 UI

`frontend/src/hooks/useAudioRecorder.js`

- `startRecording()` / `stopRecording()` → Blob 반환
- 경과 시간 표시

`frontend/src/App.jsx` — 상태 기반 단일 페이지

| 상태 | 화면 |
|------|------|
| `idle` | 녹음 시작 버튼 |
| `recording` | 경과 시간 + 녹음 중지 버튼 |
| `processing` | "변환 중..." 텍스트 |
| `done` | Reflection 텍스트 + 원본 전사 토글 |

---

### 🔧 Phase 6 - 통합 테스트 + 디버깅

- 실제 음성 녹음 → 전사 → Reflection 전체 플로우 검증
- 에러 핸들링 보완 (네트워크 오류, STT 지연, 파일 형식 문제)
- API 키가 커밋 이력에 노출되지 않는지 확인

---

### 🔧 Phase 7 - README + 문서화

프로젝트 문서화 핵심 항목:

1. **프로젝트 소개** — 목적, 핵심 가치
2. **기술 스택**
3. **실행 방법** (step-by-step, 재현성)
4. **환경 변수 설정** (`.env.example` 기반)
5. **RTZR API 활용 방법** — 사용한 기능과 근거
6. **후처리 파이프라인 설명**
7. **프로젝트 구조**
8. **AI 코딩 에이전트 활용 방식**
