# IX Value Loop 구현 로드맵

- 문서 상태: 작업 진행 추적용
- 최종 갱신일: 2026-08-08
- 대상: IX Value Loop MVP

## 1. 문서 역할

이 문서는 현재 구현 상태, 다음 작업, 작업 간 의존성, 완료 조건과 검증 결과를
기록한다. 제품 요구사항이나 데이터·상태·LLM·API 계약을 새로 정의하지 않는다.

구현 판단의 우선순위는 다음과 같다.

1. `docs/DECISIONS.md`
2. `docs/DATA_MODEL.md`
3. `docs/STATE_TRANSITIONS.md`
4. `docs/LLM_CONTRACT.md`
5. `docs/API_CONTRACT.md`
6. `docs/PRODUCT_SPEC.md`
7. `docs/DEVELOPMENT_PLAN.md`
8. `docs/DEMO_SCENARIO.md`
9. 이 문서

상위 계약과 이 문서가 다르면 상위 계약을 따른다. 계약 변경이 필요하면 코드만
수정하지 않고 `DECISIONS.md`와 관련 계약을 같은 변경에서 먼저 수정한다.

## 2. 상태 정의

| 상태 | 의미 |
|---|---|
| `not_started` | 선행 작업 또는 구현을 아직 시작하지 않음 |
| `in_progress` | 구현 또는 검증을 진행 중 |
| `in_review` | 구현과 로컬 검증이 끝났고 PR 검토·병합 대기 중 |
| `completed` | PR이 기준 브랜치에 병합되고 완료 조건을 충족함 |
| `blocked` | 외부 결정, 권한 또는 환경 없이는 진행할 수 없음 |

`completed`는 코드가 작성됐다는 의미가 아니라 테스트와 PR 병합까지 끝났다는 의미다.

## 3. 전체 진행 현황

| 단계 | 기능 영역 | 상태 | 선행 단계 | 브랜치/PR |
|---:|---|---|---|---|
| 0 | Project Scaffold | `completed` | 문서 계약 확정 | `codex/project-scaffold`, PR #2 병합 |
| 1 | PostgreSQL·Alembic·Demo Seed | `completed` | Phase 0 병합 | `codex/database-schema`, PR #4 병합 |
| 2 | 인증·Session·CSRF·권한 | `completed` | Phase 1 | `codex/auth-security`, PR #5 병합 |
| 3 | 직원 Dashboard·Action·Evidence | `in_review` | Phase 2 | `codex/employee-weekly-loop`, PR #6 |
| 4 | LLM·Mock·Evidence Card | `not_started` | Phase 3 | 예정 |
| 5 | 팀장 피드백·Report·HR 조회 | `not_started` | Phase 4 | 예정 |
| 6 | OpenAPI·E2E·Replit 배포 | `not_started` | Phase 5 | 예정 |

MVP의 최종 사용자 흐름은 다음과 같다.

```text
직원 로그인
→ 이번 주 핵심가치와 업무 확인
→ Value Action 완료
→ Evidence 제출
→ Evidence Card 생성·수정·확정
→ 팀장 피드백
→ manager_reviewed 기록을 가치별 리포트에 표시
```

## 4. 멀티에이전트 운영 원칙

### 메인 에이전트

- 계약 해석과 범위 결정을 소유한다.
- 공유 파일과 에이전트별 파일 소유 범위를 정한다.
- 서브에이전트 결과를 기다린 후 구현 또는 통합한다.
- 최종 diff, 테스트, 커밋과 PR을 검증한다.

### 구현 에이전트

- 지정된 디렉터리와 기능만 수정한다.
- 구현과 해당 기능의 집중 테스트를 함께 작성한다.
- 계약 변경이 필요하면 임의 구현하지 않고 메인 에이전트에 보고한다.

### 탐색·리뷰 에이전트

- 기본적으로 읽기 전용으로 사용한다.
- 계약 누락, 보안 위험, 상태 전이, 테스트 공백을 검토한다.
- 원시 로그보다 파일 위치와 결론 중심의 요약을 반환한다.

### 병렬 작업 제한

다음 파일과 영역에는 동시에 두 명 이상의 작성 에이전트를 배정하지 않는다.

- Alembic migration과 SQLAlchemy model registry
- 공통 FastAPI router 등록
- frontend route 등록
- `package.json`, `pnpm-lock.yaml`, `pyproject.toml`
- OpenAPI artifact
- `docs/DECISIONS.md`와 계약 문서

각 작성 작업은 별도 worktree와 `codex/` 브랜치에서 진행하고, 의존성이 있는 PR은
앞 단계 PR이 병합된 뒤 시작한다.

## 5. Phase 0 — Project Scaffold

- 상태: `completed`
- 브랜치: `codex/project-scaffold`
- 커밋: `f52f9a1`
- PR: [#2](https://github.com/sleimneer-cloud/AI-onboarding-website/pull/2)

### 목표

DB와 도메인 기능을 구현하기 전에 backend와 frontend를 독립적으로 실행하고 테스트할
수 있는 공통 기반을 만든다.

### 구현 완료

- FastAPI application factory와 기본 설정
- `GET /health`
  - DB와 Groq를 호출하지 않음
  - `200 {"status":"ok","service":"ix-value-loop","version":"0.1.0"}`
- `GET /ready`
  - 지연 생성한 PostgreSQL 연결로 제한 시간 내 `SELECT 1`
  - DB 미설정·실패 시 민감 정보 없이 503
- React, Vite, TypeScript application shell
- Vite development proxy
  - `/api`
  - `/health`
  - `/ready`
- Vite production build를 FastAPI가 같은 origin에서 제공
- React client route SPA fallback
- `/api`, `/health`, `/ready`, 누락된 asset은 SPA fallback에서 제외
- pytest, Vitest, Playwright 기본 구성
- `.env.example`과 `.gitignore`
- Windows/PowerShell 및 Replit/Linux 명령 문서화

### 주요 파일

- `backend/app/main.py`
- `backend/app/api/health.py`
- `backend/app/core/config.py`
- `backend/app/services/readiness.py`
- `backend/tests/`
- `frontend/src/`
- `frontend/e2e/smoke.spec.ts`
- `frontend/package.json`
- `README.md`
- `AGENTS.md`

### 검증 결과

| 검증 | 결과 |
|---|---|
| Backend pytest | 14 passed |
| Ruff | 통과 |
| Python dependency check | 통과 |
| Frontend Vitest | 1 passed |
| TypeScript typecheck | 통과 |
| Vite production build | 통과 |
| Playwright test discovery | smoke test 1개 확인 |
| pnpm frozen lockfile | 통과 |
| pnpm peer dependency | 문제 없음 |
| 실제 Uvicorn `/health` | 200 |
| DB 없는 Uvicorn `/ready` | 예상대로 503 |
| FastAPI root/client route/asset | 모두 200 |
| 실제 Vite root와 health proxy | 모두 200 |

### 의도적으로 제외한 기능

- SQLAlchemy 도메인 모델과 Alembic migration
- 인증, cookie, session, CSRF와 role 검사
- 업무, Action, Evidence API
- LLM request/response model과 Groq/Mock provider
- Evidence Card 상태 전이
- 팀장, 리포트, HR 기능 화면

### 병합 결과

- PR #2가 `main`에 병합됨 (`06e7a6e`)
- GitHub Actions를 추가하지 않은 현재 범위가 의도와 맞는지 확인

## 6. Phase 1 — PostgreSQL·Alembic·Demo Seed

- 상태: `completed`
- 브랜치: `codex/database-schema`
- 선행 조건: Phase 0 PR이 `main`에 병합됨
- PR: [#4](https://github.com/sleimneer-cloud/AI-onboarding-website/pull/4)

### 목표

`DATA_MODEL.md`를 그대로 구현하는 PostgreSQL 16+ schema와 재현 가능한 migration,
가상 demo fixture를 만든다.

### 구현 대상

1. `users`
2. `auth_sessions`
3. `auth_rate_limits`
4. `onboarding_profiles`
5. `core_values`
6. `curriculum_weeks`
7. `onboarding_weeks`
8. `work_assignments`
9. `action_library`
10. `assigned_actions`
11. `evidence_submissions`
12. `evidence_submission_actions`
13. `evidence_links`
14. `evidence_cards`
15. `manager_feedbacks`

### 세부 태스크

#### DB 기반

- 공통 engine/session과 transaction 경계
- PostgreSQL naming convention
- UUID v4, UTC `timestamptz`, `date`, JSONB
- 계약에 정의된 Enum 문자열
- migration head를 확인할 수 있는 readiness 확장 지점

#### 모델과 제약

- 모든 PK, FK, unique, check, partial unique 구현
- 조회에 필요한 FK와 계약상 필수 인덱스 구현
- cascade와 restrict 정책 구현
- Evidence, Card, feedback의 일대일 관계를 DB unique로 보호
- 낙관적 잠금 대상의 `version` 구현

#### Alembic

- 초기 Alembic 설정
- 전체 schema를 생성하는 초기 migration
- application startup에서 migration 자동 실행 금지
- 빈 테스트 DB에서 upgrade와 downgrade 검증

#### Demo seed

- 직원·팀장·HR 가상 계정
- 12개 핵심가치와 12주 커리큘럼
- Value Action Library
- 온보딩 profile, week, 대표 업무와 assigned Action
- stable key 기반 idempotent upsert
- 초기 상태: Action 3개 중 2개 완료, Evidence 미제출
- 공개 reset API 없이 허용된 환경의 CLI script만 제공

### 에이전트 배정

- 작성 에이전트 1명: models, Alembic, seed를 단독 소유
- 탐색 에이전트 1명: `DATA_MODEL.md`와 migration 누락 비교
- reviewer 1명: uniqueness, index, cascade, transaction 테스트 검토

Migration과 model registry는 여러 에이전트가 병렬로 수정하지 않는다.

### 완료 조건

- `alembic upgrade head` 성공
- disposable DB에서 downgrade 후 재-upgrade 성공
- seed를 두 번 실행해도 중복 없음
- 15개 테이블, Enum, index, constraint가 계약과 일치
- PostgreSQL에서 DB 집중 테스트 통과
- 실제 `DATABASE_URL`로 `/ready` 200 확인
- 실행 명령을 `README.md`와 `AGENTS.md`에 추가

### 현재 검증 결과

| 검증 | 결과 |
|---|---|
| 로컬 pytest (`not postgres`) | 23 passed |
| GitHub Actions PostgreSQL 16 | 29 passed |
| Alembic upgrade → downgrade → re-upgrade | 통과 |
| Alembic model/migration drift check | 통과 |
| 허구 demo seed 2회 및 reset | 통과 |
| 실제 PostgreSQL `/ready` | 200 |
| Ruff | 통과 |
| Python dependency check | 통과 |
| Alembic offline upgrade/downgrade SQL | 통과 |

### 병합 결과

- PR #4가 `main`에 병합됨

## 7. Phase 2 — 인증·Session·CSRF·권한

- 상태: `completed`
- 브랜치: `codex/auth-security`
- 선행 조건: Phase 1
- PR: [#5](https://github.com/sleimneer-cloud/AI-onboarding-website/pull/5)

### 구현 기능

- normalized email 기반 login
- Argon2id password hash와 dummy password verification
- 원본을 저장하지 않는 opaque session token
- session과 CSRF token SHA-256 hash 저장
- local/production cookie 정책 분리
- 로그인 포함 mutation의 Origin 검사
- 인증 후 mutation의 CSRF 검사
- DB 기반 로그인 rate limit
- Replit 검증 전 proxy header 비신뢰와 직접 peer 기반 rate-limit subject
- `APP_ENV` 기반 cookie와 `APP_ORIGIN` 기반 Origin 판단
- logout revoke와 session expiry
- employee, manager, hr role 검사
- 다른 사용자 resource를 404로 숨기는 ownership 검사

### API

- `POST /api/v1/auth/login`
- `GET /api/v1/auth/me`
- `GET /api/v1/auth/csrf`
- `POST /api/v1/auth/logout`

### 완료 조건

- 성공·실패·비활성 계정·rate limit 테스트
- session expiry와 logout revoke 테스트
- Origin과 CSRF 실패 테스트
- 위조된 `Forwarded`와 `X-Forwarded-For`가 rate-limit subject를 바꾸지 않는 테스트
- 역할별 접근 테스트
- 다른 사용자 IDOR 테스트
- credential, token, email 원문이 로그에 남지 않음

### 현재 구현

- strict Pydantic Auth request/response와 공통 API 오류 형식
- Argon2id password manager와 재사용 dummy verification hash
- opaque session/CSRF token 생성 및 SHA-256 hash 저장
- HMAC rate-limit subject와 PostgreSQL row lock 기반 실패 횟수 처리
- local/production cookie 정책과 session revoke/expiry
- Origin, CSRF, role, ownership 재사용 dependency/helper
- Auth API 4개와 request ID 응답 header
- 위조된 proxy header를 무시하는 직접 peer 주소 처리

### 현재 검증

| 검증 | 결과 |
|---|---|
| Phase 2 단위·API·권한 테스트 | 23 passed |
| 전체 로컬 pytest | 46 passed, 20 skipped (로컬 PostgreSQL 미설정) |
| Phase 2 PostgreSQL 통합 테스트 | 13 passed (GitHub Actions PostgreSQL 16) |
| GitHub Actions 전체 backend 테스트 | 66 passed |
| Ruff | 통과 |
| Python dependency check | 통과 |
| Frontend Vitest | 1 passed |
| Frontend typecheck | 통과 |
| Frontend production build | 통과 |

### 병합 결과

- PR #5가 `main`에 병합됨 (`b872dec`)

## 8. Phase 3 — 직원 Dashboard·Action·Evidence

- 상태: `in_review`
- 브랜치: `codex/employee-weekly-loop`
- 선행 조건: Phase 2
- PR: [#6](https://github.com/sleimneer-cloud/AI-onboarding-website/pull/6) — draft

### 구현 기능

- 현재 온보딩 주차와 stage 계산
- 주차·핵심가치·대표 업무 dashboard
- 배정 Action과 진행률
- Action pending/completed 전이와 version 충돌
- Evidence 생성 이후 Action 잠금
- 필수 Action 완료 검사
- Evidence와 완료 Action 연결
- 최대 3개 링크와 HTTP/HTTPS scheme 검증
- 외부 URL 접근 금지
- assignment당 Evidence 하나 보장

### API

- `GET /api/v1/employee/dashboard`
- `PATCH /api/v1/assigned-actions/{action_id}`
- `POST /api/v1/evidence`
- `GET /api/v1/evidence/{evidence_id}`

### Frontend

- 최소 공통 로그인 화면과 인증 상태 초기화
- 인증 성공 후 employee 기본 경로 이동과 미인증 사용자 로그인 경로 전환
- 직원 dashboard
- 핵심가치와 업무 표시
- Action checklist와 진행률
- Evidence form과 링크 입력
- loading, empty, validation, conflict 상태

### 현재 구현

- strict request/response schema와 employee service layer를 추가함
- Dashboard 조회, Action 전이, Evidence 생성·조회 endpoint를 추가함
- Action 멱등 처리, optimistic version 충돌, Evidence 이후 Action 잠금을 구현함
- DB transaction 안에서 필수 Action 완료, assignment 소속, Evidence 중복을 검사함
- React 로그인·직원 dashboard·Action checklist·Evidence form을 구현함
- API 요청은 cookie credential을 포함하고 mutation은 메모리 CSRF token을 사용함
- 외부 링크는 제목·설명·URL만 저장하며 URL 본문은 가져오지 않음
- Windows PostgreSQL 검증을 위해 pytest와 demo seed/reset의 async loop를 호환 방식으로 실행함

### 현재 검증

| 검증 | 결과 |
|---|---|
| Phase 3 service·schema·API 계약 테스트 | 11 passed |
| Backend 전체 테스트 | 84 passed — 로컬 PostgreSQL 16.14 포함 |
| Phase 3 PostgreSQL 통합 테스트 | 6 passed |
| Backend Ruff | 통과 |
| GitHub Actions PostgreSQL 16 | 통과 — run 31252962154 |
| Frontend Vitest | 4 passed |
| Frontend typecheck | 통과 |
| Frontend production build | 통과 |
| Playwright test list | 1 test 확인 |
| 브라우저 직원 전체 흐름 | login → Action 100% → Evidence·링크 제출 → 새로고침 후 잠금 확인 |

### PR #6 CI 수정 이력

- 최초 PostgreSQL 16 CI는 82 passed, 2 failed로 종료됨
- 실패 원인은 초기 migration의 완성된 Check Constraint 이름에 SQLAlchemy naming convention이
  다시 적용되어 `ck_<table>_ck_<table>_...` 형태가 된 것임
- 29개 Check Constraint 이름을 `op.f()`로 고정해 새 DB에서도 model metadata와 같은 이름을
  생성하도록 수정함
- 완전히 새로 만든 로컬 PostgreSQL 16.14 테스트 DB에서 Backend 84 passed와 Ruff 통과를 확인함
- 수정 후 [GitHub Actions PostgreSQL 16 재실행](https://github.com/sleimneer-cloud/AI-onboarding-website/actions/runs/31252962154)이 통과함

### 완료 조건

- 직원 login부터 Evidence 제출까지 실제 흐름 성공
- Action 멱등 요청과 version 충돌 테스트
- 필수 Action 미완료와 Evidence 중복 제출 차단
- 다른 직원 resource 접근 차단
- server와 UI 모두 계약에 없는 기능을 노출하지 않음

## 9. Phase 4 — LLM·Mock·Evidence Card

- 상태: `not_started`
- 권장 브랜치: `codex/evidence-card`
- 선행 조건: Phase 3

### 구현 순서

1. `EvidenceCardGenerationInputV1` Pydantic model
2. `CardContentV1` Pydantic model
3. JSON Schema와 Pydantic validation 일치
4. source reference 허용 목록 검증
5. deterministic Mock provider
6. Groq provider와 strict JSON Schema
7. 전체 8초 deadline과 최대 1회 재시도
8. Groq 실패 후 명확히 표시된 Mock fallback
9. Card 생성·조회·편집·확정 service와 API

### 상태 전이

```text
ai_processing → user_review
ai_processing → generation_failed
generation_failed → ai_processing
user_review → user_confirmed
```

### 핵심 규칙

- AI는 직원을 평가하거나 문화 적합도를 추론하지 않음
- 입력에 없는 사실, 수치, 성과와 인과관계를 만들지 않음
- URL 원문과 외부 링크 내용은 LLM에 보내지 않음
- Groq 호출 중 DB transaction을 열어두지 않음
- 최초 생성본과 사용자 최종본을 분리 저장
- 확정 이후 Card 수정과 재생성 차단
- unknown field 거부

### 완료 조건

- 정상 Groq와 deterministic Mock 결과가 동일 schema 검증 통과
- 잘못된 JSON, 누락 필드, extra field, source ref 오류 테스트
- timeout·429·5xx 후 Mock fallback 테스트
- 동시 Card 생성 요청에서 하나의 Card만 생성
- 사용자 편집 version 충돌과 확정 이후 변경 차단
- UI에 실제 provider가 명확히 표시됨

## 10. Phase 5 — 팀장 피드백·Report·HR 조회

- 상태: `not_started`
- 권장 브랜치: `codex/manager-reports`
- 선행 조건: Phase 4

### 구현 기능

- 담당 직원의 `user_confirmed` Card 검토 목록
- Card, assignment, Action과 Evidence 상세 조회
- 팀장 최종 피드백
- feedback 생성과 Card·assignment 전이를 한 transaction으로 처리
- 중복 feedback 제출 멱등 처리
- `manager_reviewed` Card만 직원 가치별 report에 포함
- HR 핵심가치·커리큘럼·Action Library·overview 읽기 전용 조회

### 상태 전이

```text
user_confirmed → manager_reviewed
active assignment → completed
```

### 완료 조건

- 담당 팀장만 feedback 제출 가능
- 팀장은 Card 본문을 수정할 수 없음
- manager rejection과 revision UI가 없음
- feedback과 상태 변경이 원자적으로 처리됨
- 검토 전 Card는 report의 완료 record에 포함되지 않음
- HR role로 mutation 불가

## 11. Phase 6 — OpenAPI·E2E·Replit 배포

- 상태: `not_started`
- 권장 브랜치: `codex/e2e-deployment`
- 선행 조건: Phase 5

### OpenAPI와 Frontend

- FastAPI Pydantic model에서 OpenAPI export
- frontend API type 생성 또는 Zod 대조
- cookie credentials와 CSRF header를 처리하는 공통 client
- backend schema 변경을 frontend typecheck에서 감지

### Playwright 핵심 시나리오

```text
직원 로그인
→ 마지막 Action 완료
→ Evidence와 링크 제출
→ Mock Evidence Card 생성
→ 직원 수정·확정
→ 팀장 로그인·피드백
→ 직원 로그인·가치별 리포트 확인
```

### 배포

- Replit PostgreSQL과 Secrets
- frontend production build
- Alembic migration 명시적 실행
- demo seed 명시적 실행
- Replit Autoscale 단일 application 배포
- `/health`, `/ready`, 세 역할 login smoke test
- Groq 실제 smoke와 Mock fallback
- cold start와 새로고침 후 데이터 유지 확인

### 완료 조건

- 핵심 pytest, Vitest와 Playwright E2E 통과
- frontend typecheck와 production build 통과
- 권한·IDOR·CSRF 보안 테스트 통과
- 배포 URL에서 전체 한 주 Loop 완료
- DB/Groq 장애 시 계약된 실패·fallback 동작 확인
- demo reset 후 같은 E2E 재실행 성공

## 12. 공통 완료 체크리스트

모든 구현 PR은 다음을 만족해야 한다.

- 관련 계약 문서를 먼저 읽고 diff와 대조함
- 구현 범위와 제외 범위를 PR에 기록함
- 집중 테스트를 추가하거나 수정함
- 가장 작은 관련 테스트부터 실행함
- frontend 계약 변경 시 typecheck와 production build를 실행함
- state transition은 route나 UI가 아니라 service 계층에 있음
- role과 ownership을 server에서 검사함
- secret과 Evidence/Card 원문이 로그에 없음
- 실행한 명령, 결과, 남은 계약 gap을 보고함
- 이 문서의 상태, PR, 검증 결과를 실제 결과에 맞게 갱신함

## 13. 현재 검증 공백과 후속 확인

다음 항목은 현재 단계 실패가 아니라 후속 단계에서 확인할 검증 공백이다.

- Replit runtime과 실제 `PORT`, PostgreSQL URL 형식은 배포 단계에서 확인
- 전체 직원 browser 흐름은 수동 회귀 검증으로 통과했으며 자동 Playwright 회귀 시나리오는
  Phase 6에서 추가

## 14. 문서 갱신 규칙

각 PR에서 다음 순서로 이 문서를 갱신한다.

1. 작업 시작 시 대상 Phase를 `in_progress`로 변경
2. 브랜치와 담당 파일 범위를 기록
3. 구현 후 실제 테스트 명령과 결과를 기록
4. 초안 PR 생성 후 `in_review`로 변경하고 PR 링크 추가
5. `main` 병합 확인 후에만 `completed`로 변경
6. 새 blocker나 계약 차이를 `현재 검증 공백과 후속 확인`에 기록

미래 계획을 완료된 기능처럼 기록하지 않고, 로컬에서 통과하지 않은 검증 결과를
추정해서 작성하지 않는다.
