# IX Value Loop — Phase 1 허구 데모 Fixture 계약

- 문서 상태: MVP 구현 기준안
- 기준 날짜: `2026-08-02`
- 현재 데모 주차: 2주차

이 문서의 사용자, 이메일, 업무, 링크와 산출물은 모두 허구다. 아래 가치 `code`와
설명도 MVP 동작 검증용 데모 카탈로그이며 실제 공식 카탈로그로 간주하지 않는다.
실제 공식 문구를 적용하려면 `DECISIONS.md`와 이 문서를 먼저 갱신한다.

## 1. 데모 계정

| fixture key | 이름 | 이메일 | 역할 | 직무 |
|---|---|---|---|---|
| `demo.employee` | 김가온 | `employee@ix-demo.test` | `employee` | `ax` |
| `demo.manager` | 박도윤 | `manager@ix-demo.test` | `manager` | 해당 없음 |
| `demo.hr` | 이서윤 | `hr@ix-demo.test` | `hr` | 해당 없음 |

- seed 비밀번호는 `DEMO_ACCOUNT_PASSWORD`에서 읽는다.
- DB에는 Argon2id hash만 저장하고 평문 비밀번호나 hash를 로그에 남기지 않는다.
- employee profile의 `start_date`는 `2026-07-20`, `demo_week_override`는 `2`다.
- manager는 `demo.manager` 계정으로 고정한다.

## 2. 데모 핵심가치와 커리큘럼

| 주차 | code | 이름 | stage | 데모용 짧은 설명 |
|---:|---|---|---|---|
| 1 | `relationship_based_strategic_communication` | 관계기반 전략소통 | `guided` | 관계와 맥락을 이해하고 목적에 맞게 소통합니다. |
| 2 | `obsessive_curiosity` | 강박적 호기심 | `guided` | 질문과 검증으로 문제의 본질을 탐색합니다. |
| 3 | `growth_oriented_feedback` | 성장지향 피드백 | `guided` | 구체적인 피드백을 주고받아 다음 행동을 개선합니다. |
| 4 | `value_centered_problem_solving` | 가치중심적 문제해결 | `guided` | 사용자와 조직의 가치를 기준으로 문제를 해결합니다. |
| 5 | `fundamental_critical_thinking` | 근본적 비판 사고 | `assisted` | 전제를 점검하고 근본 원인을 비판적으로 검토합니다. |
| 6 | `leading_quantitative_goal_orientation` | 선도적/정량 목표의식 | `assisted` | 측정 가능한 목표를 세우고 선제적으로 실행합니다. |
| 7 | `ultra_efficient_time_management` | 초효율적 시간관리 | `assisted` | 중요한 일에 시간을 집중하고 낭비를 줄입니다. |
| 8 | `innovation_process_acceleration` | 혁신 프로세스 가속화 | `assisted` | 새로운 도구와 방법으로 실행 과정을 빠르게 개선합니다. |
| 9 | `persistent_perseverance` | 집요한 끈기 | `autonomous` | 실패 원인을 학습하며 해결될 때까지 시도합니다. |
| 10 | `highest_standard_results` | 최고수준의 결과지향 | `autonomous` | 명확한 완료 기준으로 결과물의 완성도를 높입니다. |
| 11 | `self_driven_growth_motivation` | 자발적 성장동기 | `autonomous` | 스스로 성장 목표를 정하고 학습을 실행합니다. |
| 12 | `future_optimistic_challenge` | 미래낙관적 도전 | `autonomous` | 불확실성 속에서도 가능성을 보고 새로운 시도를 시작합니다. |

`full_description`은 같은 짧은 설명에 "실제 업무의 행동과 근거로 확인한다"는 데모
목적 문장을 덧붙인 값으로 seed한다. Core value와 curriculum row는 삭제·재생성하지
않고 각각 `code`, `week_number`로 upsert한다.

## 3. 2주차 대표 업무

- `seed_key`: `demo.week2.hr_inquiry_prototype`
- 제목: `반복적인 HR 문의 분석 및 자동화 프로토타입 구축`
- 업무 유형: `prototype_build`
- 기간: `2026-07-27` ~ `2026-08-02`
- 직원: `demo.employee`
- 팀장: `demo.manager`

업무 설명은 반복 문의의 원인을 확인하고 사용자가 쉽게 접근할 수 있는 단일 문의
진입점 프로토타입을 만드는 허구 시나리오로 고정한다.

## 4. Value Action Library와 초기 상태

| library key | Action | 완료 기준 | 초기 상태 |
|---|---|---|---|
| `demo.obsessive_curiosity.hypothesis` | 구현 전에 문제의 근본 원인에 대한 가설을 한 문장으로 작성한다. | 검증 가능한 가설이 한 문장으로 기록되어 있다. | `completed` |
| `demo.obsessive_curiosity.interview` | 실제 사용자 또는 업무 담당자 2명 이상에게 현재 업무 흐름을 확인한다. | 2명 이상의 인터뷰 또는 확인 기록이 있다. | `completed` |
| `demo.obsessive_curiosity.judgment_change` | 처음 가설과 조사 후 판단이 어떻게 달라졌는지 기록한다. | 조사 전후의 판단 변화가 한 문장 이상 기록되어 있다. | `pending` |

- 세 Action은 `core_value=obsessive_curiosity`, `job_role=ax`,
  `work_type=prototype_build`, `onboarding_stage=guided`로 seed한다.
- priority는 표 순서대로 `10`, `20`, `30`을 사용한다.
- 배정 시 문구, 완료 기준, 권장 근거를 `assigned_actions`에 스냅숏으로 복사한다.
- 초기 상태는 Action 3개 중 2개 완료, Evidence 0개다.

## 5. Seed와 reset allowlist

- 사용자 allowlist: `demo.employee`, `demo.manager`, `demo.hr`
- 업무 allowlist: `demo.week2.hr_inquiry_prototype`
- Action Library allowlist: `demo.obsessive_curiosity.*`의 위 세 stable key
- reset은 `APP_ENV=demo` 또는 `APP_ENV=test`에서만 실행한다.
- reset은 allowlist 업무의 진행 데이터와 데모 profile/week를 제거한 뒤 같은 transaction
  안에서 이 문서의 초기 상태로 다시 seed한다.
- Core value, curriculum, Action Library와 allowlist 밖의 데이터는 reset에서 삭제하지 않는다.
- 공개 reset API는 만들지 않는다.
