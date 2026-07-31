# IX Value Loop

인터엑스 핵심가치와 신규 입사자의 실제 업무를 연결하는 온보딩 포털입니다. 현재
저장소는 FastAPI 백엔드, React/Vite/TypeScript 프론트엔드, 테스트 및 단일 도메인
배포를 위한 project scaffold를 제공합니다.

구현 전에는 `AGENTS.md`에 정의된 순서대로 `docs/` 계약 문서를 읽어야 합니다. 데이터,
상태, LLM, API 계약이 제품 및 개발계획보다 우선합니다.

현재 단계별 구현 상태, 다음 작업과 완료 기준은
[`docs/IMPLEMENTATION_ROADMAP.md`](docs/IMPLEMENTATION_ROADMAP.md)에서 확인합니다.

## 현재 범위

- FastAPI 애플리케이션과 `/health`, `/ready`
- React/Vite/TypeScript 애플리케이션 shell
- pytest, Vitest, Playwright 기본 구성
- Vite production build를 FastAPI가 같은 origin에서 제공하는 구조
- 환경 변수와 Windows/Replit 실행 명령

아직 DB 테이블, Alembic migration, 인증, 업무 API, Evidence Card 및 LLM 기능은
구현하지 않았습니다.

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

`DATABASE_URL`이 비어 있으면 서버는 정상 실행되고 `/health`는 200을 반환하지만,
`/ready`는 계약에 따라 503을 반환합니다. 실제 `.env` 파일은 커밋하지 않습니다.

## Windows/PowerShell 설치

저장소 루트에서 실행합니다.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
pnpm --dir frontend install --frozen-lockfile
```

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

브라우저가 설치된 환경에서:

```bash
. .venv/bin/activate
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

## Production/Replit 실행

Migration과 seed는 애플리케이션 startup에서 자동 실행하지 않습니다. 배포 단계에서
명시적으로 실행해야 합니다. 현재 scaffold에는 아직 migration과 seed가 없습니다.

```bash
pnpm --dir frontend build
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}"
```

production build 후 FastAPI가 `/`와 React client route, `/assets/*` 파일을 제공합니다.
`/api/*`, `/health`, `/ready`는 SPA fallback으로 처리하지 않습니다.

## 상태 확인

- `GET /health`: DB와 Groq를 호출하지 않고 프로세스 상태만 확인합니다.
- `GET /ready`: 제한 시간 내 PostgreSQL `SELECT 1`을 실행합니다. Groq는 확인하지
  않습니다.
