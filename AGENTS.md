# IX Value Loop repository guidance

## Read before implementation

Before changing application code, read the contract documents in this order:

1. `docs/DECISIONS.md`
2. `docs/DATA_MODEL.md`
3. `docs/STATE_TRANSITIONS.md`
4. `docs/LLM_CONTRACT.md`
5. `docs/API_CONTRACT.md`
6. `docs/PRODUCT_SPEC.md`
7. `docs/DEVELOPMENT_PLAN.md`
8. `docs/DEMO_SCENARIO.md`

After the contract documents, read `docs/IMPLEMENTATION_ROADMAP.md` to understand
the current implementation status, dependencies, and verification history. The
roadmap tracks work; it never overrides a contract document.

The data, state, LLM, and API contracts are the implementation source of truth.
If a product or development plan conflicts with a contract, do not silently choose
one. Update `docs/DECISIONS.md` and the affected contract first.

## Non-negotiable product rules

- The MVP implements one complete weekly loop.
- One onboarding week has at most one primary assignment in the MVP.
- One assignment has at most one Evidence, one Evidence Card, and one final manager feedback.
- AI structures user-provided evidence; it does not evaluate employees or culture fit.
- Never infer facts, achievements, scores, or causal impact absent from the evidence.
- External link contents are never fetched. Only user-entered link titles and descriptions may be sent to the LLM.
- Store the initial generated Card separately from the employee-edited final Card.
- Employees cannot edit a Card after confirmation.
- Managers cannot edit Card content. Submitting feedback means approval and report inclusion.
- Only `manager_reviewed` Cards appear as completed report records.
- Groq failure must fall back to a clearly labeled deterministic Mock within the total AI time budget.
- Use fictional demo data only.

## Engineering rules

- Enforce role and ownership checks on the server for every protected resource.
- Treat another user's resource as not found.
- Keep state transitions in the service layer, not in route handlers or UI components.
- Use DB uniqueness and transactions to protect one-to-one MVP relationships.
- Do not keep a DB transaction open during a Groq network request.
- State-changing requests must verify Origin and CSRF.
- Do not log evidence text, Card text, link URLs, credentials, tokens, API keys, or upstream response bodies.
- Reject unknown fields in API and LLM Pydantic models.
- Never render user or AI text as raw HTML.
- Do not add file upload, external URL crawling, HR write management, manager rejection, or Card revision UI to the MVP.

## Verification

For every implementation task:

1. Add or update focused tests.
2. Run the smallest relevant tests.
3. Run type checking and the production frontend build when frontend contracts change.
4. Review the diff against the contract documents.
5. Report commands, results, and any remaining contract gap.

When project commands are created, add their exact Windows/local and Replit/Linux forms
to this file and `README.md`.

## Project commands

Run commands from the repository root. Do not run migrations, seeds, or AI calls during
application startup.

### Windows/PowerShell setup

```powershell
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
pnpm --dir frontend install --frozen-lockfile
```

### Windows/PowerShell run

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
pnpm --dir frontend dev
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-WebRequest http://127.0.0.1:5173
```

### Windows/PowerShell database

Use a configured PostgreSQL 16+ `DATABASE_URL`. Migration and seed never run at
application startup.

```powershell
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini upgrade head
.\.venv\Scripts\python.exe -m alembic -c backend/alembic.ini check
$env:APP_ENV='demo'
.\.venv\Scripts\python.exe -m app.scripts.seed_demo
.\.venv\Scripts\python.exe -m app.scripts.reset_demo
```

### Windows/PowerShell verify

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests
.\.venv\Scripts\python.exe -m ruff check backend
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend test:e2e:list
```

Use only a disposable PostgreSQL database whose name contains `test`; the migration test
performs downgrade and re-upgrade.

```powershell
$env:TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ix_value_loop_test'
.\.venv\Scripts\python.exe -m pytest backend/tests/db/test_postgres_phase1.py backend/tests/db/test_postgres_phase2.py
```

For the browser smoke test:

```powershell
.\.venv\Scripts\Activate.ps1
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

### Replit/Linux setup

```bash
cp .env.example .env
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e "backend[dev]"
pnpm --dir frontend install --frozen-lockfile
```

### Replit/Linux run

```bash
.venv/bin/python -m uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
pnpm --dir frontend dev --host 0.0.0.0
curl --fail http://127.0.0.1:8000/health
curl --fail http://127.0.0.1:5173
```

### Replit/Linux database

```bash
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
.venv/bin/python -m alembic -c backend/alembic.ini check
APP_ENV=demo .venv/bin/python -m app.scripts.seed_demo
APP_ENV=demo .venv/bin/python -m app.scripts.reset_demo
```

### Replit/Linux verify

```bash
.venv/bin/python -m pytest backend/tests
.venv/bin/python -m ruff check backend
pnpm --dir frontend test
pnpm --dir frontend typecheck
pnpm --dir frontend build
pnpm --dir frontend test:e2e:list
```

Use only a disposable PostgreSQL database whose name contains `test`.

```bash
TEST_DATABASE_URL='postgresql+psycopg://postgres:postgres@127.0.0.1:5432/ix_value_loop_test' \
  .venv/bin/python -m pytest backend/tests/db/test_postgres_phase1.py backend/tests/db/test_postgres_phase2.py
```

For the browser smoke test:

```bash
. .venv/bin/activate
pnpm --dir frontend exec playwright install chromium
pnpm --dir frontend test:e2e
```

### Production/Replit start

```bash
pnpm --dir frontend build
.venv/bin/python -m alembic -c backend/alembic.ini upgrade head
APP_ENV=demo .venv/bin/python -m app.scripts.seed_demo
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port "${PORT:-8000}" --no-proxy-headers
```

Replit의 전달 header와 trusted proxy IP 범위를 Phase 6에서 검증하기 전까지
`--no-proxy-headers`를 유지한다. `FORWARDED_ALLOW_IPS=*`는 사용하지 않는다.
