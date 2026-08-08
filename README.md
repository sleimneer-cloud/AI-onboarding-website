# IX Value Loop

인터엑스 핵심가치와 신규 입사자의 실제 업무를 연결하는 온보딩 포털입니다. 현재
저장소는 FastAPI 백엔드, React/Vite/TypeScript 프론트엔드, PostgreSQL 데이터 모델,
Alembic migration, 허구 데모 seed/reset 및 단일 도메인 배포 구조를 제공합니다.

구현 전에는 `AGENTS.md`에 정의된 순서대로 `docs/` 계약 문서를 읽어야 합니다. 데이터,
상태, LLM, API 계약이 제품 및 개발계획보다 우선합니다.

현재 단계별 구현 상태, 다음 작업과 완료 기준은
[`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md)에서 확인합니다.

## 현재 범위

- FastAPI 애플리케이션과 `/health`, `/ready`
- SQLAlchemy 2 기반 15개 PostgreSQL 테이블과 8개 Enum
- Alembic 초기 migration과 model/migration drift 검사
- 반복 실행 가능한 허구 데모 seed 및 allowlist reset
- normalized email·Argon2id 기반 로그인과 DB opaque session
- Origin·CSRF 보호, 로그인 rate limit, 역할·소유권 검사 기반
- `/api/v1/auth/login`, `/me`, `/csrf`, `/logout`
- 직원 현재 주차·핵심가치·업무·Action을 집계하는 dashboard API
- Action 완료/취소, 낙관적 잠금, Evidence 이후 Action 잠금
- Evidence와 완료 Action·최대 3개 링크를 원자적으로 저장하는 API
- `/api/v1/employee/dashboard`, `/assigned-actions/{id}`, `/evidence`
- strict Pydantic `EvidenceCardGenerationInputV1`과 `CardContentV1`
- Groq strict JSON Schema, 전체 8초 예산·1회 재시도·deterministic Mock fallback
- Evidence Card 생성·조회·수정·확정 API와 서버 상태 전이
- React Router 기반 직원 홈·업무·Evidence·Card·리포트 독립 경로
- Card의 AI 최초본/사용자 최종본 분리와 읽기 전용 source reference 표시
- pytest, Vitest, Playwright 기본 구성
- Vite production build를 FastAPI가 같은 origin에서 제공하는 구조
- 환경 변수와 Windows/Replit 실행 명령

팀장 피드백, 검토 완료 가치별 리포트와 HR 조회 화면은 Phase 5 범위로 아직 구현하지
않았습니다. `/employee/report`는 Card 확정 후 다음 단계를 안내하는 placeholder만 제공합니다.

## 요구 환경

- Python 3.11 이상
- Node.js 22.12 이상
- pnpm 11.9.0
- PostgreSQL 16 이상(`/ready` 성공 확인 시 필요)

## 환경 변수

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Replit/Linux:

```bash
cp .env.example .env
```

`DATABASE_URL`이 비어 있거나 migration revision이 기대값과 다르면 서버는 실행되지만
`/ready`는 계약에 따라 503을 반환합니다. 실제 `.env` 파일은 커밋하지 않습니다.

인증 기능에는 32바이트 이상의 무작위 `SESSION_SECRET`이 필요합니다. Production에서는
값이 없으면 설정 검증에 실패합니다. `APP_ORIGIN`은 브라우저가 사용하는 정확한 단일
origin으로 설정하며 path나 trailing slash를 포함하지 않습니다.

`DEMO_ACCOUNT_PASSWORD`는 허구 데모 계정의 seed 입력이며 DB에는 Argon2id hash만
저장합니다. `DEMO_REFERENCE_DATE`의 기본값은 재현 가능한 시연을 위해
`2026-08-02`로 고정합니다.

Evidence Card는 기본적으로 `AI_PROVIDER=groq`와 `GROQ_API_KEY`를 사용합니다.
`GROQ_MODEL` 기본값은 `openai/gpt-oss-20b`이며 strict JSON Schema로 요청합니다. Groq
호출은 전체 8초 안에서 최대 한 번 재시도하고, 최종 실패하거나 key가 없으면
`AI_FALLBACK_TO_MOCK=true`일 때 화면에 명확히 표시되는 deterministic Mock으로
전환합니다. 로컬에서 외부 호출 없이 재현하려면 `.env`의 `AI_PROVIDER=mock`을 사용합니다.

## Windows/PowerShell 설치

저장소 루트에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
pnpm --dir frontend install --frozen-lockfile
```

## Windows/PowerShell 데이터베이스

`.env`에 PostgreSQL 16 이상의 `DATABASE_URL`을 설정한 뒤 실행합니다.

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
$env:APP_ENV='demo'
.\.venv\Scripts\python.exe -m app.scripts.seed_demo
.\.venv\Scripts\python.exe -m app.scripts.reset_demo
```

`reset_demo`는 `APP_ENV=demo` 또는 `APP_ENV=test`에서만 동작하며 allowlist 밖의 데이터는
변경하지 않습니다. 애플리케이션 startup에서는 migration이나 seed를 실행하지 않습니다.

## Windows/PowerShell 개발 서버

터미널 1:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

터미널 2:

```powershell
pnpm --dir frontend dev
```

확인:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:5173
```

## Windows/PowerShell 검증

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
.\.venv\Scripts\python.exe -m ruff check backend
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend test:e2e:list
```

PostgreSQL 전용 migration·constraint·seed·readiness 테스트는 이름에 `test`가 포함된 폐기
가능한 DB에서만 실행합니다. 테스트가 migration downgrade를 수행하므로 공유 DB URL을
사용하면 안 됩니다.

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ix_value_loop_test'
.\.venv\Scripts\python.exe -m pytest backend/tests/db/test_postgres_phase1.py backend/tests/db/test_postgres_phase2.py
```

브라우저가 설치된 환경에서 전체 scaffold E2E를 실행하려면 먼저 가상환경을 활성화합니다.

```powershell
.\.venv\Scripts\Activate.ps1
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

## Replit/Linux 설치

저장소 루트에서 실행합니다.

```bash
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e "backend[dev]"
pnpm --dir frontend install --frozen-lockfile
```

## Replit/Linux 데이터베이스

`.env` 또는 Replit Secrets에 PostgreSQL 16 이상의 `DATABASE_URL`을 설정합니다.

```bash
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
.venv/bin/python -m alembic -c backend/alembic.ini check
APP_ENV=demo .venv/bin/python -m app.scripts.seed_demo
APP_ENV=demo .venv/bin/python -m app.scripts.reset_demo
```

## Replit/Linux 개발 서버

터미널 1:

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

터미널 2:

```bash
pnpm --dir frontend dev --host 0.0.0.0
```

확인:

```bash
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:5173
```

## Replit/Linux 검증

```bash
.venv/bin/python -m pytest backend/tests
.venv/bin/python -m ruff check backend
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend test:e2e:list
```

폐기 가능한 PostgreSQL 테스트 DB에서 Phase 1 통합 테스트를 실행합니다.

```bash
TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ix_value_loop_test' \
  .venv/bin/python -m pytest backend/tests/db/test_postgres_phase1.py backend/tests/db/test_postgres_phase2.py
```

브라우저가 설치된 환경에서:

```bash
. .venv/bin/activate
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

## Production/Replit 실행

Migration과 seed는 애플리케이션 startup에서 자동 실행하지 않습니다. 배포 단계에서
명시적으로 실행해야 합니다.

```bash
pnpm --dir frontend build
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
APP_ENV=demo .venv/bin/python -m app.scripts.seed_demo
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}" --no-proxy-headers
```

production build 후 FastAPI가 `/`와 React client route, `/assets/*` 파일을 제공합니다.
`/api/*`, `/health`, `/ready`는 SPA fallback으로 처리하지 않습니다.

Replit의 전달 header와 trusted proxy IP 범위를 Phase 6에서 검증하기 전까지는
`--no-proxy-headers`를 유지하고 `FORWARDED_ALLOW_IPS=*`를 사용하지 않습니다.
Production cookie와 CSRF Origin은 각각 `APP_ENV`와 `APP_ORIGIN` 설정으로 결정합니다.

## 상태 확인

- `GET /health`: DB와 Groq를 호출하지 않고 프로세스 상태만 확인합니다.
- `GET /ready`: 제한 시간 내 PostgreSQL `SELECT 1`과 Alembic revision을 확인합니다.
  Groq는 확인하지 않습니다.
