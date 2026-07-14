# EchoLog Backend

FastAPI 기반의 음성 전사 및 회고 생성 서버입니다.  
RTZR STT API로 음성을 전사하고, 후처리 파이프라인을 통해 읽기 좋은 Reflection으로 재구성합니다.

---

## 기술 스택

| 항목 | 기술 | 선택 이유 |
|------|------|-----------|
| 프레임워크 | FastAPI | 비동기 처리, 자동 문서화(Swagger), Pydantic 통합 |
| 환경변수 관리 | pydantic-settings | `.env` 파일을 타입 안전하게 로드 |
| HTTP 클라이언트 | requests | RTZR API 호출 |
| 파일 업로드 | python-multipart | `multipart/form-data` 음성 파일 수신 |
| 테스트 | pytest + httpx | 라우터 및 서비스 단위 테스트 |

---

## 디렉토리 구조

```
backend/
├── app/
│   ├── main.py                   # FastAPI 앱 진입점, CORS 설정
│   ├── config.py                 # 환경변수 로드 (pydantic-settings)
│   ├── routers/
│   │   └── transcribe.py         # POST /api/transcribe 엔드포인트
│   └── services/
│       ├── rtzr_client.py        # RTZR API 클라이언트
│       ├── transcript_processor.py  # 후처리 파이프라인 (핵심)
│       └── reflection_generator.py  # Timeline Reflection 생성
├── tests/
│   ├── conftest.py
│   ├── test_reflection_generator.py
│   ├── test_rtzr_client.py
│   ├── test_transcribe_router.py
│   └── test_transcript_processor.py
├── requirements.txt
└── .env.example
```

---

## 핵심 모듈 설명

### `rtzr_client.py` — RTZR STT 클라이언트

RTZR API와의 모든 통신을 담당합니다.

| 메서드 | 역할 |
|--------|------|
| `get_token()` | JWT 인증 토큰 발급. 만료 5분 전 자동 갱신 (6시간 유효) |
| `submit_transcription()` | 음성 파일 전사 요청 → `transcribe_id` 반환 |
| `get_result()` | 전사 결과 단건 조회 |
| `transcribe()` | submit + polling 통합 (3초 간격, 최대 5분 대기) |

외부 요청에는 연결 10초·응답 60초 timeout을 적용합니다. 네트워크 오류와
잘못된 응답 형식은 `RTZRError`로 변환하여 API가 일관된 오류를 반환하도록 합니다.

**RTZR 요청 설정:**

원본 전사와 시간순 기록을 같은 오디오로 각각 요청합니다.

원본 전사는 필터를 끄고 사용자가 말한 흐름을 보존합니다.

```json
{
  "use_disfluency_filter": false,
  "use_paragraph_splitter": false,
  "use_itn": false
}
```

시간순 기록용 전사는 RTZR 기능을 적용해 짧은 분석 단위를 만듭니다.

```json
{
  "use_disfluency_filter": true,
  "use_paragraph_splitter": true,
  "paragraph_splitter": { "max": 50 },
  "use_itn": true,
  "use_word_timestamp": true
}
```
- `use_disfluency_filter` — "어, 음, 그" 같은 추임새 제거
- `use_paragraph_splitter` — 의미 단위로 문단 분리 (후처리에 유리한 구조)
- `use_itn` — 숫자/단위를 자연어에서 표기로 변환 (예: "삼십분" → "30분")

---

### `transcript_processor.py` — 후처리 파이프라인

이 프로젝트의 핵심 모듈입니다. RTZR 전사 결과를 사람이 읽기 좋은 형태로 변환합니다.

```
RTZR utterances
    ↓ parse_utterances()   — utterance 목록 파싱 (ms → 초 변환)
    ↓ sort_by_time()       — start_at 기준 시간순 정렬
    ↓ remove_duplicates()  — 인접한 유사 문장 제거 (임계값 0.8, 최대 간격 3초)
    ↓ build_timeline()      — 시간 표현·문장 경계로 시간순 문단 생성
    ↓ ProcessedTranscript  — 후처리 완료 결과
```

**설계 포인트:**
- **중복 제거**: 직전 발화와의 간격이 3초 이내이고 유사도 0.8 이상일 때만 STT 중복으로 판단. 다른 사건에서 반복된 내용은 보존.
- **시간순 문단**: 문장 맨 앞에 `아침`, `저녁`, `퇴근 후`, `오후 3시` 등이 나오면 새 문단의 힌트로 사용합니다. 화면에는 발화의 실제 `start_at`을 `00:42` 형태로 일관되게 표시합니다.
- **문장 경계**: 문단은 문장이 끝난 지점에서만 2~3문장씩 묶습니다. 침묵 길이와 문맥 유사도 점수는 사용하지 않습니다.

---

### `reflection_generator.py` — Reflection 생성

후처리된 전사 결과를 최종 Reflection 텍스트로 변환합니다.

- **현재 버전** → Timeline 형태로 반환
- **향후 확장** → LLM을 이용한 자연스러운 서술체 변환

---

### `routers/transcribe.py` — API 엔드포인트

```
POST /api/transcribe
  Request:  multipart/form-data { file: audio }
  Response: {
    "reflection": str,        # 정제된 회고 텍스트
    "raw_transcript": str,    # 필터 전 RTZR 원본 전사 텍스트
    "timeline": [...],        # 시간순 기록 목록 (label, text, start_at)
    "mode": "timeline",       # 현재 사용 모드
    "processing_time": float  # 처리 시간(초)
  }
```

`RTZRClient`는 앱 생명주기 동안 싱글턴으로 유지되어 토큰 캐싱 효과를 얻습니다.
완료까지 오래 걸리는 STT 폴링은 스레드 풀에서 실행하여 FastAPI 이벤트 루프를 차단하지 않습니다.

---

## 환경변수 설정

`.env.example`을 복사해 `.env`를 만든 뒤 값을 채웁니다.

```bash
cp .env.example .env
```

```env
RTZR_CLIENT_ID=your_rtzr_client_id
RTZR_CLIENT_SECRET=your_rtzr_client_secret
LLM_API_KEY=                # 향후 LLM 연동 확장용 (현재 미사용)
```

---

## 실행 방법

```bash
cd backend

# 가상환경 생성 및 의존성 설치
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 서버 실행
uvicorn app.main:app --reload
```

서버 기동 후 `http://localhost:8000/docs` 에서 Swagger UI로 API를 직접 테스트할 수 있습니다.

---

## 테스트 실행

```bash
cd backend
pytest tests/ -v
```
