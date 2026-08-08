# IX Value Loop — 결정 로그

이 문서는 제품/개발계획을 구현 계약으로 변환하면서 확정한 결정을 기록한다.
결정을 변경할 때는 관련 데이터, 상태, LLM, API 문서도 같은 변경에서 수정한다.

## 확정 결정

| ID | 결정 | 이유 | 영향 문서 |
|---|---|---|---|
| D-001 | MVP는 주차별 대표 업무를 최대 1개만 지원한다. | 한 주 Loop 시연과 데이터 관계를 단순화한다. | DATA_MODEL, API |
| D-002 | 업무당 Evidence, Card, 최종 피드백은 각각 최대 1개다. | MVP의 기준 기록을 명확히 하고 중복 요청을 안전하게 처리한다. | DATA_MODEL, STATE_TRANSITIONS |
| D-003 | `onboarding_weeks`를 주차·핵심가치·업무 연결의 기준 엔터티로 둔다. | 커리큘럼 변경 후에도 과거 주차의 의미를 보존한다. | DATA_MODEL |
| D-004 | Action 배정 시 문구, 완료 기준, 권장 근거를 모두 스냅숏으로 저장한다. | Library 변경이 기존 기록을 바꾸지 않게 한다. | DATA_MODEL |
| D-005 | AI 최초 생성본과 사용자 최종본을 분리 저장한다. | 수정 항목 측정과 AI provenance를 보존한다. | DATA_MODEL, LLM |
| D-006 | Card 각 필드는 입력 근거를 가리키는 source reference를 가진다. | 근거 없는 요약과 환각을 탐지한다. | LLM, API |
| D-007 | 서버는 외부 링크에 접속하지 않고 URL을 LLM에 전달하지 않는다. | SSRF, 기밀 유출, 잘못된 “링크 읽기” 주장을 방지한다. | LLM, API |
| D-008 | 기본 Groq 모델은 `openai/gpt-oss-20b`, strict JSON Schema를 사용한다. | 구조화 출력과 운영 기간의 모델 안정성을 확보한다. | LLM |
| D-009 | Groq 전체 처리 시간 예산은 8초이며 이후 deterministic Mock으로 전환한다. | 1분 시연의 응답 시간을 보호한다. | LLM, STATE_TRANSITIONS |
| D-010 | Groq 실패 후 Mock 성공 시 Card 상태는 `user_review`다. | 사용 가능한 결과를 실패 상태로 표시하지 않는다. | STATE_TRANSITIONS |
| D-011 | 팀장은 Card 본문을 수정하지 않는다. 피드백 제출이 승인이다. | 직원 확정본의 작성 주체와 책임을 보존하고 MVP 상태를 단순화한다. | STATE_TRANSITIONS, API |
| D-012 | 팀장 반려·수정 요청 흐름은 MVP에서 제외한다. | 일정 내 핵심 Loop에 집중한다. | STATE_TRANSITIONS |
| D-013 | `manager_reviewed` Card만 완료된 리포트 기록으로 표시한다. | 팀장 확인 전 AI/직원 초안을 공식 기록으로 취급하지 않는다. | API |
| D-014 | 서버 측 opaque session과 DB 세션을 사용한다. | Autoscale 다중 인스턴스에서 logout과 만료를 일관되게 처리한다. | DATA_MODEL, API |
| D-015 | 인증 후 mutation은 Origin과 CSRF token을 모두 검사한다. | cookie 기반 인증의 CSRF 위험을 줄인다. | API |
| D-016 | 실사용 파일 업로드, 외부 링크 내용 수집, HR 쓰기 관리 기능은 MVP에서 제외한다. | 개인정보·기밀 위험과 개발 범위를 줄인다. | AGENTS, API |
| D-017 | 9~12주차 custom Action을 수용할 필드는 미리 두되 UI는 구현하지 않는다. | 향후 자율 설계를 위한 파괴적 schema 변경을 줄인다. | DATA_MODEL |
| D-018 | ERD에서 필수 관계로 정의된 FK는 표에 nullable 표시가 없더라도 `NOT NULL`로 구현하고 DATA_MODEL 표에 이를 명시한다. | 고아 세션·주차·Action·링크가 생성되는 것을 DB에서 차단한다. | DATA_MODEL |
| D-019 | `onboarding_weeks`의 DB check는 계약에 명시된 `ends_on >= starts_on`을 사용하고, 정확한 7일 구간은 seed/service가 `ends_on = starts_on + 6일`로 보장한다. 커리큘럼의 주차별 stage는 DB check로도 보호한다. | 문서의 설명과 명시 제약을 모두 보존하면서 잘못된 공식 커리큘럼 입력을 조기에 차단한다. | DATA_MODEL |
| D-020 | Phase 1 데모 계정·가치 코드/설명·Action·업무·stable key는 `DEMO_SCENARIO.md`의 허구 fixture 계약을 사용한다. 실제 공식 카탈로그나 임직원 데이터로 간주하지 않는다. | 비어 있던 fixture 입력을 재현 가능하게 고정하고 실제 정보의 임의 추론을 피한다. | DATA_MODEL, DEMO_SCENARIO |
| D-021 | Replit의 전달 헤더와 trusted proxy IP 범위가 검증되기 전에는 `Forwarded`와 `X-Forwarded-*`를 신뢰하지 않는다. 로그인 제한에는 ASGI 연결의 직접 peer 주소만 사용하고, 운영 cookie와 Origin 판단은 각각 `APP_ENV`와 `APP_ORIGIN` 설정을 사용한다. | 문서화되지 않은 전달 헤더를 신뢰해 클라이언트 주소나 요청 scheme이 위조되는 것을 방지한다. | DATA_MODEL, API, DEVELOPMENT_PLAN, AGENTS, README |
| D-022 | Phase 2는 인증 API와 서버 보안 기반을 구현하고, Phase 3의 첫 프론트엔드 작업으로 최소 공통 로그인 화면과 인증 초기화를 구현한다. | “직원 로그인부터 Evidence 제출까지”라는 Phase 3 완료 조건과 화면 구현 범위를 일치시킨다. | PRODUCT_SPEC, IMPLEMENTATION_ROADMAP |
| D-023 | `SESSION_SECRET`은 UTF-8 기준 최소 32바이트의 배포별 무작위 secret으로 관리하고 저장소에 커밋하지 않는다. Phase 2의 8시간 session과 10분/5회/15분 rate-limit 값은 계약 고정값으로 검증한다. | 토큰 관련 HMAC key의 추측 가능성을 낮추고 환경 변수 오설정으로 보안 정책이 약화되는 것을 막는다. | API, DEVELOPMENT_PLAN, README |
| D-024 | 직원 흐름은 `/employee` 홈, `/employee/assignment` 업무·Value Action, `/employee/evidence/new` 행동 근거 작성, `/employee/cards/:card_id` Evidence Card, `/employee/report` 누적 리포트의 독립 client route로 구분한다. 홈은 요약과 상태 기반 CTA만 제공하며 상세 작업은 버튼으로 해당 route에 진입한다. | 한 화면의 과도한 정보 밀도를 줄이고 사용자가 현재 단계와 다음 행동을 명확히 이해하게 한다. | PRODUCT_SPEC, DEVELOPMENT_PLAN, IMPLEMENTATION_ROADMAP |

## 구현 중 새 결정이 필요한 경우

다음 형식으로 행을 추가한다.

```text
ID:
결정:
선택지:
선택 이유:
데이터/API/상태/보안 영향:
변경한 문서:
```

코드만 변경하고 결정 로그와 계약 문서를 그대로 두지 않는다.
