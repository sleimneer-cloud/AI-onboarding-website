# IX Value Loop 웹 서비스 개발계획서

> 문서 역할: MVP의 기술 스택, 기능 범위, 개발 일정, 테스트 및 배포 방향을
> 설명한다. 상세 구현은 `DECISIONS.md`, `DATA_MODEL.md`,
> `STATE_TRANSITIONS.md`, `LLM_CONTRACT.md`, `API_CONTRACT.md`를 우선한다.

## 1. 프로젝트 개요

### 1.1 프로젝트명

IX Value Loop

인터엑스 핵심가치 연계형 신규 입사자 온보딩 포털

### 1.2 개발 목적

IX Value Loop는 신규 입사자가 회사의 핵심가치를 단순히 읽고 학습하는 데서 끝나지 않고, 실제 업무에서 행동으로 실천하고 그 근거와 피드백을 축적하도록 지원하는 웹 서비스다.

팀장이 배정한 실제 업무를 온보딩 활동으로 활용하며, 해당 주차의 핵심가치와 신규 입사자의 직무·업무 유형에 적합한 Value Action을 함께 제공한다.

신규 입사자가 업무 과정에서 발견한 내용과 판단 변화를 행동 근거로 등록하면 AI가 이를 Evidence Card로 정리한다. 신규 입사자는 AI 결과를 직접 수정하고 확정하며, 팀장의 피드백까지 완료된 기록은 가치별 리포트에 누적된다.

### 1.3 개발 목표

2026년 8월 6일까지 다음 한 주의 온보딩 흐름이 처음부터 끝까지 동작하는 MVP를 완성한다.

핵심 흐름은 다음과 같다.

```text
핵심가치 확인
→ 실제 업무 확인
→ Value Action 수행
→ 행동 근거 등록
→ AI Evidence Card 생성
→ 사용자 수정 및 확정
→ 팀장 피드백
→ 가치별 리포트 반영
```

2026년 8월 7일부터 8월 28일까지는 신규 기능을 개발하지 않고 배포 유지, 오류 대응, 데모 데이터 복구 및 심사 대응만 수행한다.

### 1.4 개발 원칙

- 한 주의 온보딩 Loop를 완결성 있게 구현한다.
- 12주 전체 흐름은 데이터 구조로만 확장 가능하게 설계한다.
- 실제 업무와 온보딩을 분리하지 않는다.
- AI는 직원을 평가하지 않고 사용자가 등록한 근거를 구조화한다.
- Value Action은 생성형 AI가 아니라 검증된 Library에서 조회한다.
- 실제 임직원 개인정보와 회사 기밀을 사용하지 않는다.
- AI나 외부 서비스가 실패해도 핵심 시연 흐름을 완료할 수 있어야 한다.
- 8월 6일까지 완성 가능한 기능만 필수 범위에 포함한다.

## 2. 사용자 구성

### 2.1 신규 입사자

신규 입사자는 다음 기능을 사용한다.

- 현재 온보딩 주차 확인
- 이번 주 핵심가치와 설명 확인
- 사전에 배정된 실제 업무 확인
- 업무와 연결된 Value Action 확인
- Value Action 완료 처리
- 행동 근거 작성 및 제출
- 업무 관련 링크 첨부
- AI Evidence Card 생성
- Evidence Card 수정 및 확정
- 팀장 피드백 확인
- 가치별 리포트 확인

### 2.2 팀장

팀장은 다음 기능을 사용한다.

- 검토 대상 Evidence Card 목록 확인
- 신규 입사자의 업무와 행동 근거 확인
- 확정된 Evidence Card 검토
- 실제로 관찰한 행동 작성
- 잘 적용된 부분 작성
- 업무 결과에 미친 영향 작성
- 다음 업무에서 강화할 행동 작성
- 피드백 제출 및 리포트 반영

MVP에서는 팀장이 업무를 새로 배정하는 관리 화면을 만들지 않는다. 업무와 Value Action은 데모 데이터로 미리 등록한다.

### 2.3 인사팀

인사팀은 다음 정보를 읽기 전용으로 확인한다.

- 12개 핵심가치
- 12주 핵심가치 커리큘럼
- Value Action Library
- 데모 신규 입사자의 온보딩 진행 상태

Action 등록·수정과 복잡한 인사 통계는 MVP에서 제외한다.

## 3. MVP 범위

### 3.1 필수 구현 기능

공통 기능:

- 직원·팀장·인사팀 데모 계정 로그인
- 로그인 상태 유지 및 로그아웃
- 역할별 페이지와 API 접근 제한
- 모바일·데스크톱 기본 반응형 UI
- 서버 상태 확인
- 데모 데이터 생성 및 초기화 스크립트

신규 입사자 기능:

- 주간 대시보드
- 현재 주차와 핵심가치 표시
- 실제 업무 표시
- Value Action 체크리스트
- 진행률 표시
- 행동 근거 작성 및 제출
- 링크 첨부
- Groq 기반 Evidence Card 생성
- Groq 장애 시 Mock Evidence Card 생성
- Evidence Card 사용자 수정 및 확정
- 팀장 피드백 확인
- 가치별 리포트 확인

팀장 기능:

- 검토 대기 목록
- Evidence와 Evidence Card 상세 확인
- 팀장 피드백 입력
- 피드백 제출
- 리포트 반영

인사팀 기능:

- 핵심가치 목록 조회
- 12주 커리큘럼 조회
- Value Action Library 조회
- 간단한 온보딩 진행 상태 조회

### 3.2 시드 데이터로 제공하는 기능

다음 데이터는 관리 화면 없이 seed 스크립트로 생성한다.

- 직원·팀장·인사팀 데모 계정
- 12개 핵심가치
- 12주 핵심가치 커리큘럼
- Value Action Library
- 신규 입사자 온보딩 프로필
- 팀장이 배정한 실제 업무
- 업무에 매칭된 Value Action

### 3.3 제외 기능

다음 기능은 MVP에서 구현하지 않는다.

- 실제 회사 SSO
- Microsoft Entra ID
- 실제 사내 업무 시스템 연동
- 팀장 업무 배정 관리 화면
- 인사팀 Action 등록·수정 화면
- PDF 및 DOCX 내용 분석
- 파일 업로드 및 미리보기
- 외부 링크 내용 자동 수집
- 복잡한 인사 통계
- 실제 임직원 데이터 익명화 분석
- 벡터 데이터베이스
- Redis 및 별도 Worker
- 이메일 및 Teams 알림
- 실시간 공동 편집
- 모바일 애플리케이션
- 문화 적합도 및 직원 평가 점수
- 12주 전체 주간 기능의 개별 구현
- Evidence Card revision 비교 기능

MVP에서는 텍스트 Evidence와 링크 첨부만 지원한다.

## 4. 기술 스택

### 4.1 개발 및 배포

- Codex
- Git
- GitHub
- Replit Autoscale

GitHub를 원본 소스 저장소로 사용하고, Replit 애플리케이션 하나에 프론트엔드와 백엔드를 함께 배포한다.

### 4.2 프론트엔드

- React
- Vite
- TypeScript
- Tailwind CSS
- shadcn/ui
- React Router
- TanStack Query
- React Hook Form
- Zod

### 4.3 백엔드

- Python
- FastAPI
- Pydantic
- SQLAlchemy 2
- Alembic
- Uvicorn

### 4.4 데이터베이스

- Replit PostgreSQL

### 4.5 AI

- Groq API
- Groq Python SDK
- Mock AI Provider
- Pydantic 기반 출력 검증

### 4.6 테스트

- pytest
- Vitest
- Playwright

## 5. 시스템 구조

전체 서비스는 하나의 Replit 애플리케이션으로 구성한다.

```text
사용자 브라우저
        ↓
Replit 배포 주소
        ↓
FastAPI
├─ React 정적 파일 제공
├─ REST API 제공
├─ 인증 및 권한 처리
├─ Value Action 처리
├─ Evidence 및 Evidence Card 처리
├─ 팀장 피드백 및 리포트 처리
└─ Groq 또는 Mock AI 호출
        ↓
Replit PostgreSQL
```

React/Vite의 production build 결과를 FastAPI가 제공한다.

프론트엔드와 백엔드가 같은 도메인을 사용하므로 별도의 복잡한 CORS 구성은 사용하지 않는다.

`/health`는 애플리케이션 프로세스 상태를 확인하고, `/ready`는 PostgreSQL 연결을 포함한 요청 처리 준비 상태를 확인한다.

## 6. 핵심 기능 설계

### 6.1 로그인과 역할 관리

심사용 데모 계정은 다음 세 가지 역할로 제공한다.

- 신규 입사자
- 팀장
- 인사팀

비밀번호는 평문으로 저장하지 않고 Argon2id 또는 bcrypt로 해시한다.

로그인 성공 후 역할에 맞는 기본 화면으로 이동한다. 프론트엔드에서 메뉴를 숨기는 것과 별개로 FastAPI에서 모든 요청의 역할과 데이터 소유권을 검사한다.

### 6.2 온보딩 주차

온보딩 주차는 입사일과 서비스 기준 날짜를 이용해 계산한다.

```text
경과 일수 = 기준 날짜 - 입사일
현재 주차 = 경과 일수 // 7 + 1
```

상태는 다음과 같이 구분한다.

- 입사일 이전: `not_started`
- 입사일부터 83일까지: `active`
- 입사일로부터 84일 이상: `completed`

심사 버전에서는 항상 원하는 주차를 보여줄 수 있도록 `demo_week_override`를 제공한다. 허용 범위는 1부터 12까지다.

테스트와 데모 결과가 실제 날짜에 따라 변하지 않도록 비즈니스 로직에서 `date.today()`를 직접 사용하지 않고 별도의 기준 날짜 서비스를 사용한다.

### 6.3 Value Action 매칭

Value Action은 AI가 새로 생성하지 않고 Action Library에서 조회한다.

조회 순서는 다음과 같다.

1. 핵심가치, 직무, 업무 유형, 온보딩 단계가 모두 일치
2. 업무 유형만 공통인 Action
3. 직무만 공통인 Action
4. 해당 핵심가치의 전사 공통 Action
5. 같은 조건이면 우선순위와 ID 순서로 정렬
6. 상위 2~3개 선택

선택된 Action은 `assigned_actions`에 스냅숏으로 저장한다. 이후 Library가 수정되어도 기존 직원에게 배정된 문구와 완료 기준은 변경되지 않는다.

MVP에서는 seed 스크립트가 위 로직을 사용해 데모 업무와 Action을 사전에 연결한다.

### 6.4 Action 진행 상태

Action 상태는 다음 두 가지로 단순화한다.

- `pending`
- `completed`

직원은 본인에게 배정된 Action만 변경할 수 있다.

진행률은 서버에서 다음과 같이 계산한다.

```text
완료된 Action 수 / 전체 Action 수 × 100
```

AI는 Action 완료 여부와 진행률 계산에 관여하지 않는다.

### 6.5 행동 근거 등록

신규 입사자는 다음 내용을 작성한다.

- 완료한 Value Action
- 실제로 수행한 행동
- 업무 중 발견한 내용
- 처음과 달라진 판단
- 업무 결과에 미친 영향
- 다음 업무에서 이어갈 행동
- 관련 업무 링크와 설명

MVP에서는 임시 저장을 제공하지 않는다. 사용자가 제출 버튼을 누르면 Evidence가 생성된다.

Evidence 제출 후 Evidence Card를 생성할 수 있다.

### 6.6 Evidence Card

Evidence Card에는 다음 항목이 포함된다.

- 적용한 핵심가치
- 수행한 핵심 행동
- 행동 근거 요약
- 업무 중 발견한 내용
- 판단 또는 접근 방식의 변화
- 업무 결과에 미친 영향
- 다음 업무에서 이어갈 행동

AI 결과는 JSON 형태로 반환받고 Pydantic으로 검증한다.

신규 입사자는 생성 결과를 직접 수정할 수 있다. 사용자 확정 전에는 리포트에 반영되지 않는다.

확정 이후에는 Evidence Card를 수정하거나 다시 생성할 수 없다.

### 6.7 Evidence Card 상태

Evidence Card는 다음 상태를 사용한다.

- `ai_processing`
- `generation_failed`
- `user_review`
- `user_confirmed`
- `manager_reviewed`

상태 전이는 다음과 같다.

```text
ai_processing → user_review
ai_processing → generation_failed
generation_failed → ai_processing
user_review → user_confirmed
user_confirmed → manager_reviewed
```

팀장은 Evidence Card 본문을 수정하지 않고 별도의 피드백만 작성한다.

### 6.8 팀장 피드백

팀장은 `user_confirmed` 상태의 Evidence Card에 다음 내용을 작성한다.

- 실제로 관찰한 행동
- 업무 결과에 미친 영향
- 잘 적용된 부분
- 다음 업무에서 강화할 행동

피드백 제출이 완료되면 Evidence Card 상태를 `manager_reviewed`로 변경한다.

하나의 Evidence Card에는 하나의 최종 팀장 피드백만 허용한다.

### 6.9 가치별 리포트

리포트에는 `manager_reviewed` 상태의 Evidence Card만 포함한다.

리포트는 별도 테이블에 복제하지 않고 조회 시 다음 데이터를 조합해 생성한다.

- 핵심가치
- 실제 업무
- Value Action
- 행동 근거
- Evidence Card
- 팀장 피드백

MVP에서는 한 개의 핵심가치 기록을 중심으로 보여주되 12개 핵심가치의 전체 진행 상태도 함께 표시한다.

## 7. 데이터베이스 설계

주요 테이블은 다음과 같다.

### `users`

사용자와 역할 정보를 저장한다.

주요 필드:

- `id`
- `name`
- `email`
- `password_hash`
- `role`
- `is_active`
- `created_at`

`email`은 unique로 설정한다.

### `onboarding_profiles`

신규 입사자의 온보딩 정보를 저장한다.

주요 필드:

- `id`
- `user_id`
- `job_role`
- `start_date`
- `manager_id`
- `demo_week_override`
- `status`

`user_id`는 unique로 설정한다.

### `core_values`

12개 핵심가치를 저장한다.

주요 필드:

- `id`
- `name`
- `short_description`
- `full_description`
- `display_order`

### `curriculum_weeks`

주차와 핵심가치의 연결을 저장한다.

주요 필드:

- `id`
- `week_number`
- `core_value_id`
- `stage`

`week_number`는 unique로 설정한다.

### `work_assignments`

팀장이 배정한 실제 업무를 저장한다.

주요 필드:

- `id`
- `employee_id`
- `manager_id`
- `title`
- `description`
- `work_type`
- `start_date`
- `due_date`
- `status`

### `action_library`

검증된 Value Action을 저장한다.

주요 필드:

- `id`
- `core_value_id`
- `job_role`
- `work_type`
- `onboarding_stage`
- `action_text`
- `recommended_evidence`
- `completion_criteria`
- `priority`
- `is_active`

### `assigned_actions`

실제 업무에 연결된 Action을 저장한다.

주요 필드:

- `id`
- `assignment_id`
- `source_action_id`
- `action_text_snapshot`
- `completion_criteria_snapshot`
- `status`
- `completed_at`

`assignment_id`와 `source_action_id` 조합은 unique로 설정한다.

### `evidence_submissions`

신규 입사자가 제출한 행동 근거를 저장한다.

주요 필드:

- `id`
- `assignment_id`
- `employee_id`
- `performed_action`
- `discovery`
- `changed_judgment`
- `work_impact`
- `next_action`
- `submitted_at`
- `created_at`

### `evidence_submission_actions`

Evidence와 완료한 Action의 연결을 저장한다.

주요 필드:

- `evidence_id`
- `assigned_action_id`

두 필드의 조합은 unique로 설정한다.

### `evidence_links`

Evidence에 첨부한 업무 링크를 저장한다.

주요 필드:

- `id`
- `evidence_id`
- `external_url`
- `title`
- `description`
- `created_at`

### `evidence_cards`

AI 생성 결과와 사용자의 수정 결과를 저장한다.

주요 필드:

- `id`
- `evidence_id`
- `status`
- `content_json`
- `generated_by`
- `model_name`
- `prompt_version`
- `confirmed_at`
- `manager_reviewed_at`
- `created_at`
- `updated_at`

`evidence_id`는 unique로 설정한다.

`generated_by`는 `groq` 또는 `mock` 값을 사용한다.

### `manager_feedback`

팀장 피드백을 저장한다.

주요 필드:

- `id`
- `evidence_card_id`
- `manager_id`
- `observed_behavior`
- `work_impact`
- `positive_feedback`
- `next_action`
- `submitted_at`
- `created_at`

`evidence_card_id`는 unique로 설정한다.

## 8. Groq AI 설계

### 8.1 Provider 구조

AI 공급자를 교체할 수 있도록 공통 인터페이스를 사용한다.

```text
EvidenceGenerator
├─ GroqEvidenceGenerator
└─ MockEvidenceGenerator
```

개념적인 인터페이스는 다음과 같다.

```python
generate_evidence_card(
    input: EvidenceCardInput
) -> EvidenceCardOutput
```

입력과 출력은 모두 Pydantic 모델로 정의한다.

### 8.2 환경 변수

```env
AI_PROVIDER=groq
GROQ_API_KEY=
GROQ_MODEL=
AI_TIMEOUT_SECONDS=15
AI_MAX_RETRIES=1
AI_FALLBACK_TO_MOCK=true
AI_PROMPT_VERSION=v1
```

모델 ID는 코드에 직접 고정하지 않고 Replit Secrets의 `GROQ_MODEL`로 관리한다.

### 8.3 AI 출력 구조

Groq는 다음 구조의 JSON을 반환해야 한다.

```json
{
  "core_value": "강박적 호기심",
  "key_actions": [
    "사용자 인터뷰를 통해 실제 업무 흐름을 확인했다."
  ],
  "evidence_summary": "인터뷰 기록과 프로토타입 링크를 근거로 등록했다.",
  "discovery": "반복 문의의 원인이 접근 경로의 분산임을 발견했다.",
  "judgment_change": "FAQ 추가보다 단일 진입점 제공이 우선이라고 판단했다.",
  "work_impact": "프로토타입의 기능 범위가 단순화되었다.",
  "next_action": "다음 업무에서도 구현 전에 실제 사용 흐름을 먼저 확인한다."
}
```

Structured Outputs를 지원하는 모델에서는 JSON Schema를 사용한다.

지원하지 않는 모델에서는 JSON Object Mode를 사용하되, 모든 결과를 서버에서 Pydantic으로 다시 검증한다.

### 8.4 장애 대응

다음 상황은 AI 호출 실패로 처리한다.

- 요청 시간 초과
- 네트워크 오류
- HTTP 429
- HTTP 5xx
- 빈 응답
- 잘못된 JSON
- Pydantic 검증 실패

처리 순서는 다음과 같다.

1. Groq API 호출
2. 일시적인 오류이면 한 번 재시도
3. 재시도 실패 시 Mock Provider 호출
4. Mock 결과도 동일한 Pydantic Schema로 검증
5. 실제 사용된 Provider와 모델을 Evidence Card에 기록

Mock 결과는 Groq 결과인 것처럼 표시하지 않는다.

### 8.5 데이터 정책

Groq에는 다음 데이터만 전달한다.

- 핵심가치 공식 정의
- 배정된 Value Action
- 사용자가 직접 작성한 행동 내용
- 발견 내용
- 판단 변화
- 업무 영향
- 다음 행동
- 링크 제목과 설명

다음 데이터는 전송하지 않는다.

- 실제 임직원 개인정보
- 실제 회사 기밀
- 비밀번호와 세션 정보
- API Key
- 외부 링크에서 자동 수집한 내용
- 파일 원본

심사 버전에서는 모든 사용자와 업무를 가상 데이터로 구성한다.

## 9. 화면 구성

### 직원 정보 구조와 client route

직원 화면은 하나의 긴 페이지로 구성하지 않는다. `/employee` 홈에는 이번 주 요약과 다음
행동을 안내하는 상태 기반 CTA만 두고, 실제 작업은 독립 client route에서 수행한다.

| 경로 | 책임 | 주요 진입 버튼 |
|---|---|---|
| `/employee` | 핵심가치·대표 업무·진행 상태 요약 | 상태에 따라 다음 단계 CTA 하나 표시 |
| `/employee/assignment` | 업무 상세 확인과 배정된 Value Action 완료 | `이번 주 업무 시작하기`, `계속하기` |
| `/employee/evidence/new` | 행동 근거 작성과 제출 | `행동 근거 작성하기` |
| `/employee/cards/:card_id` | Card 생성 상태, 사용자 검토·수정·확정 | `Evidence Card 확인하기` |
| `/employee/report` | 검토 완료된 가치별 누적 기록 | `가치 리포트 보기` |

- React Router가 client route, 직접 진입, 새로고침, 뒤로 가기와 앞으로 가기를 처리한다.
- 서버 session 복원 후 현재 사용자 역할에 허용되지 않는 route는 역할별 기본 경로로 보낸다.
- 프론트엔드 route 분리와 관계없이 모든 API는 서버에서 role과 resource ownership을 검사한다.
- Action 문구 작성·편집은 직원 기능이 아니다. 직원은 배정된 Action의 완료 상태와 Evidence만 기록한다.

### 9.1 로그인

- 서비스 소개
- 이메일
- 비밀번호
- 로그인 버튼
- 데모 계정 안내

### 9.2 신규 입사자 대시보드

- 현재 온보딩 주차
- 이번 주 핵심가치
- 핵심가치 설명
- 배정된 실제 업무 요약
- Value Action 완료 수와 전체 수
- Evidence Card 진행 상태
- 현재 상태에 맞는 기본 CTA 하나

### 9.3 업무 및 Value Action

- 이번 주 핵심가치와 실제 업무 상세
- 배정된 Value Action 체크리스트
- Action별 완료 기준과 권장 근거
- 진행률
- 필수 Action 완료 전 비활성화된 행동 근거 작성 버튼
- Evidence 제출 이후 읽기 전용 상태

### 9.4 행동 근거 등록

- 완료한 Value Action 선택
- 실제 수행 행동
- 업무 중 발견 내용
- 변경된 판단
- 업무 결과에 미친 영향
- 다음 행동
- 관련 링크
- 제출 버튼

### 9.5 Evidence Card

- AI 생성 상태
- 핵심가치
- 핵심 행동
- 근거 요약
- 발견 내용
- 판단 변화
- 업무 영향
- 다음 행동
- 사용자 편집
- 사용자 확정

### 9.6 팀장 검토

- 검토 대상 목록
- 신규 입사자 정보
- 실제 업무
- 원본 Evidence
- Evidence Card
- 관찰한 행동
- 잘한 부분
- 업무 영향
- 다음 행동
- 피드백 제출

### 9.7 가치별 리포트

- 12개 핵심가치 진행 현황
- 가치별 완료 상태
- 실제 업무 사례
- Evidence Card
- 팀장 피드백
- 판단 변화
- 다음 행동 원칙

### 9.8 인사팀 조회

- 12개 핵심가치
- 12주 커리큘럼
- Value Action Library
- 데모 온보딩 진행 상태

## 10. 주요 API

상세 API 계약은 `API_CONTRACT.md`를 따른다. 개발계획 수립 당시의 상위 수준 목록은 다음과 같다.

인증:

```text
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me
```

신규 입사자:

```text
GET   /api/employee/dashboard
PATCH /api/assigned-actions/{id}/status
POST  /api/evidence
POST  /api/evidence-cards/generate
GET   /api/evidence-cards/{id}
PATCH /api/evidence-cards/{id}
POST  /api/evidence-cards/{id}/confirm
GET   /api/reports/values
```

팀장:

```text
GET  /api/manager/reviews
GET  /api/manager/reviews/{id}
POST /api/evidence-cards/{id}/feedback
```

인사팀:

```text
GET /api/hr/overview
GET /api/hr/core-values
GET /api/hr/curriculum
GET /api/hr/actions
```

상태 확인:

```text
GET /health
GET /ready
```

## 11. 보안 계획

- 비밀번호 해시 저장
- HttpOnly 인증 쿠키 사용
- Replit 환경에서 Secure 쿠키 적용
- SameSite=Lax 적용
- 상태 변경 요청의 Origin 검사
- 역할별 API 접근 검사
- 직원·팀장별 데이터 소유권 검사
- Pydantic 서버 입력 검증
- SQLAlchemy 기반 DB 접근
- API Key와 Secret을 Replit Secrets에 저장
- `SESSION_SECRET`은 UTF-8 기준 최소 32바이트의 배포별 무작위 값으로 관리
- 내부 오류와 스택 트레이스 비공개
- 로그인 요청 횟수 제한
- Replit trusted proxy 범위를 검증하기 전까지 전달 헤더를 신뢰하지 않고 Uvicorn을
  `--no-proxy-headers`로 실행
- 로그인 제한의 주소 입력은 ASGI 연결의 직접 peer 주소를 사용하며 이메일, 주소,
  전달 헤더 원문은 저장하거나 로그에 기록하지 않음
- Production cookie와 CSRF Origin은 전달 헤더가 아니라 `APP_ENV`와 `APP_ORIGIN`으로 결정
- 실제 임직원 데이터 사용 금지
- 다른 사용자의 ID를 이용한 접근 차단 테스트

필수 환경 변수는 다음과 같다.

```env
DATABASE_URL=
SESSION_SECRET=
APP_ORIGIN=
GROQ_API_KEY=
GROQ_MODEL=
AI_PROVIDER=groq
AI_FALLBACK_TO_MOCK=true
AI_TIMEOUT_SECONDS=15
AI_MAX_RETRIES=1
AI_PROMPT_VERSION=v1
APP_ENV=demo
```

## 12. 데모 데이터 관리

데모 데이터는 idempotent seed 스크립트로 생성한다.

```bash
python -m app.scripts.seed_demo
```

초기화는 공개 API가 아니라 서버 명령으로 제공한다.

```bash
python -m app.scripts.reset_demo
```

초기화 스크립트는 다음 조건을 만족해야 한다.

- `APP_ENV=demo`에서만 실행
- 가상 데모 데이터만 변경
- 트랜잭션 사용
- 실패 시 전체 롤백
- 반복 실행해도 데이터가 중복되지 않음
- 실행 결과 로그 출력

## 13. 테스트 계획

### 13.1 백엔드 테스트

- 로그인 성공 및 실패
- 역할별 접근 권한
- 다른 사용자 데이터 접근 차단
- 온보딩 시작 전·1주차·12주차·종료 계산
- 데모 주차 고정
- Value Action 매칭
- Action 완료와 진행률
- Evidence 등록
- Evidence 없는 Card 생성 차단
- Evidence Card 상태 전이
- Groq 출력 검증
- Groq 실패 시 Mock 전환
- 팀장 피드백 권한
- 검토 완료 기록만 리포트에 표시
- seed 중복 방지

### 13.2 프론트엔드 테스트

- 로그인 폼 검증
- 대시보드 렌더링
- Action 완료 처리
- Evidence 필수값 검증
- AI 생성 로딩과 오류 표시
- Evidence Card 수정 및 확정
- 팀장 피드백 폼
- 모바일 기본 레이아웃

### 13.3 E2E 테스트

Playwright로 다음 시나리오를 자동화한다.

```text
직원 로그인
→ 대시보드 확인
→ 마지막 Action 완료
→ Evidence와 링크 등록
→ Evidence Card 생성
→ 사용자 수정 및 확정
→ 로그아웃
→ 팀장 로그인
→ Evidence Card 검토
→ 팀장 피드백 제출
→ 로그아웃
→ 직원 로그인
→ 가치별 리포트 확인
```

E2E 테스트에서는 Mock Provider를 사용한다.

Groq 실제 연결은 별도의 smoke test로 확인한다.

## 14. 개발 일정

### 7월 31일: 개발 기반

- 최종 개발계획 확정
- API와 DB 구조 확정
- Git 저장소 초기화
- FastAPI와 React 프로젝트 생성
- 환경 변수 설정
- 테스트 기본 구조
- `/health` 구현

### 8월 1일: DB와 인증

- SQLAlchemy 모델
- Alembic 초기 migration
- 로그인 및 로그아웃
- 역할별 권한
- 데모 계정
- 핵심가치·커리큘럼·업무·Action seed
- Replit PostgreSQL 연결

### 8월 2일: 신규 입사자 기능

- 대시보드 API와 화면
- 온보딩 주차 계산
- Value Action 표시
- Action 완료 처리
- 진행률
- Evidence 등록
- 링크 첨부

### 8월 3일: AI Evidence Card

- Groq Provider
- Mock Provider
- Pydantic 출력 Schema
- Evidence Card 생성
- 오류와 429 처리
- 자동 Mock fallback
- 사용자 수정 및 확정

### 8월 4일: 팀장과 리포트

- 팀장 검토 목록
- 검토 상세 화면
- 팀장 피드백
- Evidence Card 상태 변경
- 가치별 리포트
- 인사팀 읽기 전용 화면
- 프론트엔드와 API 전체 연결

### 8월 5일: 테스트와 배포

- 핵심 pytest
- 프론트엔드 테스트 및 production build
- Playwright E2E
- 권한 및 IDOR 테스트
- Alembic 운영 migration
- Replit Secrets
- Replit 배포
- Groq smoke test
- Mock fallback 확인
- Cold Start 확인
- 데이터 유지 확인

### 8월 6일: 안정화 및 완료

- 치명적 오류 수정
- 모바일 화면 점검
- 데모 계정 확인
- 데모 초기화 확인
- Groq 장애 시나리오 확인
- DB 및 GitHub 백업
- 1분 시연 흐름 반복
- 발표 영상 촬영
- 최종 배포
- 기능 동결

8월 6일 이후에는 신규 기능을 추가하지 않는다.

## 15. 배포 계획

Replit Autoscale 애플리케이션 하나에 전체 서비스를 배포한다.

배포 절차는 다음과 같다.

1. 프론트엔드 production build
2. 백엔드 의존성 설치
3. Replit Secrets 등록
4. Alembic migration 실행
5. 데모 seed 실행
6. 애플리케이션 게시
7. `/health`와 `/ready` 확인
8. 세 가지 데모 계정 로그인 확인
9. Groq 실제 호출 확인
10. Mock fallback 확인
11. Playwright 핵심 시나리오 확인
12. 새로고침 후 데이터 유지 확인

Migration과 seed는 애플리케이션이 시작될 때마다 자동으로 실행하지 않는다. 배포 과정에서 명시적으로 실행한다.

영구 데이터는 PostgreSQL에 저장하며 Replit 배포 파일시스템에는 저장하지 않는다.

## 16. 장애 대응

### Groq 장애

- 짧은 일시적 오류는 한 번 재시도
- 재시도 실패 시 Mock Provider 사용
- 기존 Evidence Card 보존
- 사용된 Provider를 결과에 표시

### 데이터베이스 장애

- `/ready` 실패 처리
- 사용자에게 재시도 화면 표시
- 기존 데이터 자동 초기화 금지
- 최근 정상 DB 백업 유지

### Replit Cold Start

- 서버 시작 시 AI를 호출하지 않음
- 서버 시작 시 migration과 seed를 실행하지 않음
- 무거운 초기화 작업 금지
- 초기 API 오류에 재시도 UI 제공

### 데모 데이터 훼손

- reset 스크립트 실행
- seed 스크립트 재실행
- 서비스 재접속 및 로그인 확인
- 핵심 E2E 재실행

## 17. 8월 7일~8월 28일 운영

이 기간에는 다음 사항만 점검한다.

- Replit 배포 URL
- Cold Start 이후 정상 응답
- 직원·팀장·인사팀 로그인
- PostgreSQL 데이터 유지
- Groq API
- Mock fallback
- 데모 데이터 상태
- Replit 클라우드 크레딧
- 게시 만료 예정일
- GitHub 백업

장애가 발생하면 다음 순서로 대응한다.

1. Replit 배포 상태와 로그 확인
2. `/health`와 `/ready` 확인
3. PostgreSQL 연결 확인
4. `AI_PROVIDER=mock` 전환
5. 데모 데이터 초기화
6. 마지막 안정 버전 재배포

8월 7일 이후에는 다음 변경을 금지한다.

- DB 구조의 대규모 변경
- 인증 방식 변경
- 새 라이브러리 도입
- 새 화면 추가
- 새 AI 기능 추가
- 핵심 상태 전이 변경

## 18. 완료 기준

다음 조건을 모두 충족하면 2026년 8월 6일 개발이 완료된 것으로 본다.

- Replit 배포 URL에 접속할 수 있다.
- 세 가지 역할의 데모 계정으로 로그인할 수 있다.
- 역할과 데이터 소유권 검사가 적용된다.
- 직원이 핵심가치와 실제 업무를 확인할 수 있다.
- 직원이 Value Action을 완료할 수 있다.
- 직원이 행동 근거와 링크를 제출할 수 있다.
- Groq가 Evidence Card를 생성할 수 있다.
- Groq 실패 시 Mock Provider로 흐름을 계속할 수 있다.
- AI 결과가 Pydantic Schema 검증을 통과한다.
- 직원이 Evidence Card를 수정하고 확정할 수 있다.
- 팀장이 확정된 Evidence Card를 검토할 수 있다.
- 팀장이 피드백을 제출할 수 있다.
- 검토된 기록이 가치별 리포트에 표시된다.
- 새로고침 후 데이터가 유지된다.
- 다른 사용자의 데이터에 접근할 수 없다.
- 데모 seed가 중복 없이 실행된다.
- 데모 데이터를 초기 상태로 복구할 수 있다.
- 핵심 pytest가 통과한다.
- 프론트엔드 production build가 성공한다.
- Playwright 핵심 E2E가 통과한다.
- GitHub에 최종 소스가 백업된다.
- 8월 28일까지 배포를 유지할 수 있는 상태다.

## 19. 최종 산출물

- Replit 배포 웹 서비스
- GitHub 소스 코드
- FastAPI 백엔드
- React/Vite 프론트엔드
- PostgreSQL 스키마
- Alembic migration
- 데모 데이터 seed 및 reset 스크립트
- Groq 및 Mock AI Provider
- 핵심 백엔드 테스트
- 핵심 Playwright E2E
- 환경 변수 예시
- 실행 및 배포 설명서
- 데모 계정 안내
- 심사 전 점검표
- 1분 시연 영상

## 20. 최종 요약

IX Value Loop MVP는 React와 FastAPI로 개발하고 Replit Autoscale 애플리케이션 하나에 배포한다.

데이터는 Replit PostgreSQL에 저장한다. AI Evidence Card는 Groq API로 생성하고, 장애와 무료 한도 초과에 대비해 Mock Provider를 제공한다.

2026년 8월 6일까지 다음 흐름을 완성하는 것을 최우선 목표로 한다.

```text
실제 업무
→ 핵심가치
→ Value Action
→ 행동 근거
→ AI Evidence Card
→ 사용자 확정
→ 팀장 피드백
→ 성장 기록
```

MVP의 성공 기준은 많은 기능을 구현하는 것이 아니라, Groq가 정상일 때와 장애가 발생했을 때 모두 이 흐름을 처음부터 끝까지 안정적으로 시연할 수 있는가이다.
