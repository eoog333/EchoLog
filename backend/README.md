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
│       └── reflection_generator.py  # Reflection 생성 (LLM or Timeline)
├── tests/
│   ├── conftest.py
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

**RTZR 요청 설정:**
```json
{
  "use_disfluency_filter": true,
  "use_paragraph_splitter": true,
  "paragraph_splitter": { "max": 100 },
  "use_itn": true
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
    ↓ remove_duplicates()  — SequenceMatcher로 유사 문장 제거 (임계값 0.8)
    ↓ group_into_events()  — 10초 이상 침묵이면 새 사건으로 그룹핑
    ↓ ProcessedTranscript  — 후처리 완료 결과
```

**설계 포인트:**
- **중복 제거**: `difflib.SequenceMatcher`를 사용해 유사도 0.8 이상인 발화를 중복으로 판단. STT 특성상 같은 말을 반복하거나 재발화하는 경우가 있어 필요.
- **사건 그룹핑**: 발화 사이 침묵이 10초 이상이면 다른 사건으로 분리. 하루를 사건 단위로 구조화해 Reflection 품질을 높임.
- **Timeline 출력**: LLM 없이도 `• 사건 내용` 형태로 바로 사용 가능.

---

### `reflection_generator.py` — Reflection 생성

후처리된 전사 결과를 최종 Reflection 텍스트로 변환합니다.

- **LLM API 키 있음** → 구어체를 자연스러운 서술체로 변환
- **LLM API 키 없음** → Timeline 형태 그대로 반환 (fallback)
- LLM은 문체만 다듬으며, 새로운 사실을 추가하거나 내용을 변형하지 않습니다.

---

### `routers/transcribe.py` — API 엔드포인트

```
POST /api/transcribe
  Request:  multipart/form-data { file: audio }
  Response: {
    "reflection": str,        # 정제된 회고 텍스트
    "raw_transcript": str,    # RTZR 원본 전사 텍스트
    "paragraphs": [...],      # 사건별 그룹 목록 (text, start_at)
    "mode": "timeline|llm",   # 사용된 모드
    "processing_time": float  # 처리 시간(초)
  }
```

`RTZRClient`는 앱 생명주기 동안 싱글턴으로 유지되어 토큰 캐싱 효과를 얻습니다.

---

## 환경변수 설정

`.env.example`을 복사해 `.env`를 만든 뒤 값을 채웁니다.

```bash
cp .env.example .env
```

```env
RTZR_CLIENT_ID=your_rtzr_client_id
RTZR_CLIENT_SECRET=your_rtzr_client_secret
LLM_API_KEY=                # 선택 사항. 비워두면 Timeline 모드로 동작
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
