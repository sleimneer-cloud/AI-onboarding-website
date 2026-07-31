# IX Value Loop — REST API 계약

- 문서 상태: MVP 구현 기준안
- Base path: `/api/v1`
- Content type: `application/json`
- 인증: 서버 측 opaque session + HttpOnly cookie
- 관련 문서:
  - `docs/DATA_MODEL.md`
  - `docs/LLM_CONTRACT.md`
  - `docs/STATE_TRANSITIONS.md`

이 문서는 프론트엔드와 백엔드 사이의 구현 계약이다. FastAPI의 Pydantic
request/response model과 프론트엔드 Zod schema는 이 문서의 이름과 필드를 따른다.

## 1. 공통 규칙

### 1.1 URL과 필드명

- API path는 복수 명사와 kebab-case를 사용한다.
- JSON 필드는 snake_case를 사용한다.
- 리소스 ID는 UUID 문자열이다.
- timestamp는 ISO 8601 UTC다.
- 클라이언트가 보내지 않은 필드를 서버가 임의의 null로 덮어쓰지 않는다.
- request body의 정의되지 않은 필드는 `422 VALIDATION_ERROR`로 거부한다.

### 1.2 성공 응답

단일 리소스는 별도 `data` wrapper 없이 리소스 JSON을 반환한다.

목록은 다음 형식을 사용한다.

```json
{
  "items": [],
  "next_cursor": null
}
```

### 1.3 오류 응답

모든 오류는 다음 형식이다.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "입력값을 확인해 주세요.",
    "field_errors": [
      {
        "field": "performed_action",
        "reason": "최소 10자 이상 입력해 주세요."
      }
    ],
    "details": {},
    "request_id": "44f0f741-73bd-4b21-85ab-8b9c6991016f"
  }
}
```

`field_errors`와 `details`는 해당 내용이 없으면 빈 배열과 빈 object를 반환한다.
내부 예외, SQL, stack trace, Groq 원문 오류는 반환하지 않는다.

### 1.4 공통 HTTP 상태

| HTTP | 사용 |
|---:|---|
| 200 | 조회, 수정, 멱등 재요청 성공 |
| 201 | 새 리소스 생성 |
| 202 | 동일 Card가 이미 생성 처리 중 |
| 204 | body 없는 logout 성공 |
| 400 | 잘못된 JSON 또는 지원하지 않는 형식 |
| 401 | 인증 없음/만료 |
| 403 | 역할 자체가 허용되지 않음 |
| 404 | 리소스 없음 또는 소유권 없음 |
| 409 | 상태 전이, 중복, version 충돌 |
| 422 | 필드 검증 실패 |
| 429 | 로그인 요청 제한 |
| 500 | 복구하지 못한 내부 오류 |
| 503 | DB 준비 상태 실패 |

## 2. 인증, Cookie, CSRF

### 2.1 Session cookie

Production:

```text
Name: __Host-ix_session
HttpOnly: true
Secure: true
SameSite: Lax
Path: /
Domain: 지정하지 않음
Max-Age: 8시간
```

Local HTTP 개발에서는 이름을 `ix_session`으로 사용하고 `Secure=false`로 설정한다.
원본 token은 cookie에만 전달하고 DB에는 SHA-256 hash만 저장한다.

### 2.2 CSRF

- 로그인 요청을 포함한 모든 상태 변경 요청은 `Origin`이 `APP_ORIGIN`과 정확히
  일치해야 한다.
- 인증 후 상태 변경 요청은 `X-CSRF-Token` header가 필요하다.
- login 응답과 `GET /auth/csrf`가 원본 CSRF token을 반환한다.
- 프론트엔드는 CSRF token을 메모리에 보관하며 localStorage에 저장하지 않는다.
- 모든 fetch는 같은 origin에서 `credentials: "include"`를 사용한다.

### 2.3 역할과 소유권

| 영역 | employee | manager | hr |
|---|---:|---:|---:|
| 본인 dashboard/Action/Evidence/Card | O | X | X |
| 본인 가치 리포트 | O | X | X |
| 담당 직원 review/feedback | X | O | X |
| Core value/curriculum/library 조회 | X | X | O |
| 전체 데모 진행 현황 | X | X | O |

역할이 맞지만 다른 사용자의 리소스에 접근하면 존재 여부를 숨기기 위해 404를 반환한다.

## 3. Health API

### `GET /health`

인증 없음. 프로세스와 event loop가 응답 가능한지만 확인한다. DB나 Groq를 호출하지 않는다.

```json
{
  "status": "ok",
  "service": "ix-value-loop",
  "version": "0.1.0"
}
```

### `GET /ready`

인증 없음. 제한 시간 내 PostgreSQL `SELECT 1`을 확인한다. migration head가 기대 revision과
다르면 ready=false로 처리할 수 있다. Groq는 확인하지 않는다.

성공:

```json
{
  "status": "ready",
  "database": "ok"
}
```

실패: HTTP 503

```json
{
  "status": "not_ready",
  "database": "unavailable"
}
```

## 4. Auth API

### `POST /api/v1/auth/login`

인증 없음. Origin 검사는 적용한다.

Request:

```json
{
  "email": "employee@ix-demo.test",
  "password": "DemoPassword!"
}
```

검증:

- email trim 및 소문자 정규화
- email 최대 254자
- password 1~200자
- 성공/실패 여부와 관계없이 없는 사용자에도 dummy Argon2 검증 수행

Response 200:

```json
{
  "user": {
    "id": "d3474f47-b779-472b-b1ff-bf6385569f92",
    "name": "김인터",
    "email": "employee@ix-demo.test",
    "role": "employee"
  },
  "csrf_token": "raw-random-csrf-token",
  "expires_at": "2026-07-31T12:30:00Z",
  "default_path": "/employee"
}
```

오류:

- 401 `INVALID_CREDENTIALS`
- 403 `USER_INACTIVE`
- 429 `LOGIN_RATE_LIMITED`

로그인 실패 메시지는 이메일 존재 여부와 무관하게 동일하게 한다.

### `GET /api/v1/auth/me`

Response 200:

```json
{
  "id": "d3474f47-b779-472b-b1ff-bf6385569f92",
  "name": "김인터",
  "email": "employee@ix-demo.test",
  "role": "employee"
}
```

### `GET /api/v1/auth/csrf`

인증 필요. Response에 `Cache-Control: no-store`를 사용한다.
호출할 때마다 새 CSRF token을 만들고 session의 `csrf_token_hash`를 교체한다.

```json
{
  "csrf_token": "raw-random-csrf-token"
}
```

### `POST /api/v1/auth/logout`

인증과 CSRF 필요. 현재 session의 `revoked_at`을 기록하고 cookie를 삭제한다.
이미 revoke된 세션의 logout도 성공으로 처리한다.

Response: `204 No Content`

## 5. Employee API

### `GET /api/v1/employee/dashboard`

employee 인증 필요. 현재 주차의 가치, 대표 업무, Action, Evidence/Card 상태를 한 번에
반환한다.

Response 200:

```json
{
  "onboarding": {
    "profile_id": "f9dc4ce5-58ea-4c52-84ad-65af8942cb96",
    "overall_status": "active",
    "week_number": 2,
    "stage": "guided",
    "week_status": "in_progress",
    "starts_on": "2026-07-27",
    "ends_on": "2026-08-02"
  },
  "core_value": {
    "id": "40a58d4c-fcd1-43ed-adba-706464e805b4",
    "code": "obsessive_curiosity",
    "name": "강박적 호기심",
    "short_description": "질문과 검증으로 문제의 본질을 탐색합니다."
  },
  "assignment": {
    "id": "76590868-bcbc-4a96-b2e5-4628372d28a7",
    "title": "반복적인 HR 문의 분석 및 자동화 프로토타입 구축",
    "description": "반복 문의의 원인을 파악하고 자동화 프로토타입을 만듭니다.",
    "work_type": "prototype_build",
    "start_date": "2026-07-27",
    "due_date": "2026-08-02",
    "status": "active"
  },
  "actions": [
    {
      "id": "12f6a31a-540f-47fc-919a-a392d8f20dd1",
      "text": "구현 전에 문제의 근본 원인에 대한 가설을 한 문장으로 작성한다.",
      "completion_criteria": "검증 가능한 가설이 한 문장으로 기록되어 있다.",
      "recommended_evidence": [
        "문제 가설 문서"
      ],
      "is_required": true,
      "display_order": 1,
      "status": "completed",
      "completed_at": "2026-07-30T03:20:00Z",
      "version": 2
    }
  ],
  "progress": {
    "completed_actions": 2,
    "total_actions": 3,
    "percentage": 67
  },
  "evidence": null,
  "evidence_card": null,
  "permissions": {
    "can_update_actions": true,
    "can_submit_evidence": false
  }
}
```

assignment가 없는 경우 `assignment=null`, `actions=[]`, progress는 모두 0으로 반환하고
`week_status=not_configured`를 사용한다.

### `PATCH /api/v1/assigned-actions/{action_id}`

employee 인증 및 CSRF 필요.

Request:

```json
{
  "status": "completed",
  "version": 1
}
```

Response 200:

```json
{
  "id": "12f6a31a-540f-47fc-919a-a392d8f20dd1",
  "status": "completed",
  "completed_at": "2026-07-31T04:10:22Z",
  "version": 2
}
```

오류:

- 404 `RESOURCE_NOT_FOUND`
- 409 `ACTION_LOCKED_BY_EVIDENCE`
- 409 `RESOURCE_VERSION_CONFLICT`
- 409 `ASSIGNMENT_NOT_ACTIVE`

같은 status를 다시 보내면 version을 증가시키지 않고 현재 값을 반환한다.

### `POST /api/v1/evidence`

employee 인증 및 CSRF 필요.

Request:

```json
{
  "assignment_id": "76590868-bcbc-4a96-b2e5-4628372d28a7",
  "assigned_action_ids": [
    "12f6a31a-540f-47fc-919a-a392d8f20dd1",
    "6438fc54-ab01-4d90-96ce-b5a5e68de1b2"
  ],
  "performed_action": "HR 담당자 두 명을 인터뷰하고 반복 문의가 발생하는 경로를 정리했다.",
  "discovery": "FAQ 내용 부족보다 문의 진입 경로가 여러 곳으로 분산된 것이 더 큰 원인이었다.",
  "changed_judgment": "FAQ 추가보다 단일 문의 진입점을 우선 제공하는 방향으로 변경했다.",
  "work_impact": "프로토타입 범위를 단일 진입점과 문의 분류 기능으로 줄였다.",
  "next_action": "다음 업무에서도 구현 전에 사용 흐름과 문제 원인을 먼저 확인한다.",
  "links": [
    {
      "external_url": "https://example.test/hr-interview-summary",
      "title": "HR 담당자 인터뷰 요약",
      "description": "담당자 두 명의 현재 문의 처리 흐름과 반복 문의 유형을 정리한 문서"
    }
  ]
}
```

Response 201:

```json
{
  "id": "dd106a8a-d601-4d32-9bf0-abff8caf7a18",
  "assignment_id": "76590868-bcbc-4a96-b2e5-4628372d28a7",
  "assigned_action_ids": [
    "12f6a31a-540f-47fc-919a-a392d8f20dd1",
    "6438fc54-ab01-4d90-96ce-b5a5e68de1b2"
  ],
  "performed_action": "HR 담당자 두 명을 인터뷰하고 반복 문의가 발생하는 경로를 정리했다.",
  "discovery": "FAQ 내용 부족보다 문의 진입 경로가 여러 곳으로 분산된 것이 더 큰 원인이었다.",
  "changed_judgment": "FAQ 추가보다 단일 문의 진입점을 우선 제공하는 방향으로 변경했다.",
  "work_impact": "프로토타입 범위를 단일 진입점과 문의 분류 기능으로 줄였다.",
  "next_action": "다음 업무에서도 구현 전에 사용 흐름과 문제 원인을 먼저 확인한다.",
  "links": [
    {
      "id": "5d06ac08-504a-41db-810f-32c49695ad2b",
      "external_url": "https://example.test/hr-interview-summary",
      "title": "HR 담당자 인터뷰 요약",
      "description": "담당자 두 명의 현재 문의 처리 흐름과 반복 문의 유형을 정리한 문서"
    }
  ],
  "submitted_at": "2026-07-31T04:20:00Z"
}
```

오류:

- 409 `REQUIRED_ACTIONS_INCOMPLETE`
- 409 `EVIDENCE_ALREADY_EXISTS`
- 409 `ASSIGNMENT_NOT_ACTIVE`
- 422 `ACTION_NOT_COMPLETED`
- 422 `ACTION_ASSIGNMENT_MISMATCH`
- 422 `INVALID_LINK_SCHEME`

### `GET /api/v1/evidence/{evidence_id}`

본인 Evidence만 조회할 수 있다. 응답은 Evidence 생성 응답과 같은 형식이다.

### `POST /api/v1/evidence/{evidence_id}/card`

Card 생성 또는 `generation_failed` 재시도 endpoint다. 클라이언트는 prompt, model,
핵심가치, LLM 입력을 전달하지 않는다.

Request body: 없음

정상 동작:

- 처음 생성하면 `201`
- 기존 `user_review` 이상 Card면 외부 호출 없이 `200`
- 기존 Card가 `ai_processing`이면 `202`, `Retry-After: 1`
- `generation_failed`이면 재생성 후 `200`

Response 201/200:

```json
{
  "id": "17229a4b-a5da-443f-8990-ce6a7e3724af",
  "evidence_id": "dd106a8a-d601-4d32-9bf0-abff8caf7a18",
  "status": "user_review",
  "content": {
    "schema_version": "1.0",
    "key_actions": [
      {
        "text": "HR 담당자 두 명을 인터뷰해 실제 업무 흐름을 확인했다.",
        "source_refs": [
          "evidence.performed_action"
        ]
      }
    ],
    "value_connection": {
      "text": "실제 업무 흐름을 질문하고 초기 판단을 수정한 행동은 문제의 본질을 탐색하는 강박적 호기심과 연결된다.",
      "source_refs": [
        "core_value.definition",
        "evidence.performed_action",
        "evidence.changed_judgment"
      ]
    },
    "evidence_summary": {
      "text": "인터뷰 요약과 사용자가 기록한 업무 흐름을 행동 근거로 활용했다.",
      "source_refs": [
        "evidence.performed_action",
        "link:5d06ac08-504a-41db-810f-32c49695ad2b"
      ]
    },
    "discovery": {
      "text": "반복 문의의 주된 원인이 문의 경로의 분산임을 발견했다.",
      "source_refs": [
        "evidence.discovery"
      ]
    },
    "judgment_change": {
      "text": "FAQ 추가보다 단일 문의 진입점을 우선하는 방향으로 판단을 변경했다.",
      "source_refs": [
        "evidence.changed_judgment"
      ]
    },
    "work_impact": {
      "text": "프로토타입 범위를 단일 진입점과 문의 분류 기능 중심으로 조정했다.",
      "source_refs": [
        "evidence.work_impact"
      ]
    },
    "next_action": {
      "text": "다음 업무에서도 구현 전에 사용 흐름과 문제 원인을 먼저 확인한다.",
      "source_refs": [
        "evidence.next_action"
      ]
    },
    "grounding_warnings": []
  },
  "generation": {
    "provider": "groq",
    "model_name": "openai/gpt-oss-20b",
    "prompt_version": "v1",
    "schema_version": "1.0",
    "latency_ms": 842
  },
  "version": 1,
  "confirmed_at": null,
  "manager_reviewed_at": null,
  "permissions": {
    "can_edit": true,
    "can_confirm": true,
    "can_retry": false
  }
}
```

`generation_failed`도 Card resource 생성 자체는 성공했으므로 200/201로 반환한다.
`content=null`, `permissions.can_retry=true`로 표시한다.

### `GET /api/v1/evidence-cards/{card_id}`

본인 Card만 조회한다. 응답은 Card 생성 응답과 같은 형식이다.

### `PATCH /api/v1/evidence-cards/{card_id}`

`user_review` 상태에서 최종본을 수정한다.

Request:

```json
{
  "version": 1,
  "content": {
    "schema_version": "1.0",
    "key_actions": [
      {
        "text": "HR 담당자 두 명을 인터뷰하고 실제 문의 흐름을 직접 확인했다.",
        "source_refs": [
          "evidence.performed_action"
        ]
      }
    ],
    "value_connection": {
      "text": "담당자에게 실제 흐름을 질문하고 판단을 수정한 행동은 문제의 본질을 탐색하는 강박적 호기심과 연결된다.",
      "source_refs": [
        "core_value.definition",
        "evidence.performed_action",
        "evidence.changed_judgment"
      ]
    },
    "evidence_summary": {
      "text": "인터뷰 요약과 업무 흐름 기록을 근거로 활용했다.",
      "source_refs": [
        "evidence.performed_action",
        "link:5d06ac08-504a-41db-810f-32c49695ad2b"
      ]
    },
    "discovery": {
      "text": "반복 문의의 주된 원인이 문의 경로 분산임을 발견했다.",
      "source_refs": [
        "evidence.discovery"
      ]
    },
    "judgment_change": {
      "text": "FAQ 추가보다 단일 문의 진입점을 우선하는 방향으로 판단을 변경했다.",
      "source_refs": [
        "evidence.changed_judgment"
      ]
    },
    "work_impact": {
      "text": "프로토타입 범위를 단일 진입점과 문의 분류 기능으로 조정했다.",
      "source_refs": [
        "evidence.work_impact"
      ]
    },
    "next_action": {
      "text": "다음 업무에서도 구현 전에 사용 흐름을 먼저 확인한다.",
      "source_refs": [
        "evidence.next_action"
      ]
    },
    "grounding_warnings": []
  }
}
```

Response 200: 갱신된 Card. `version`은 2가 된다.

오류:

- 409 `CARD_NOT_EDITABLE`
- 409 `RESOURCE_VERSION_CONFLICT`
- 422 `CARD_SCHEMA_INVALID`
- 422 `CARD_SOURCE_REF_INVALID`

### `POST /api/v1/evidence-cards/{card_id}/confirm`

Request:

```json
{
  "version": 2
}
```

Response 200: `status=user_confirmed`, `confirmed_at`과 새 version을 포함한 Card.

오류:

- 409 `INVALID_CARD_TRANSITION`
- 409 `RESOURCE_VERSION_CONFLICT`

이미 `user_confirmed`인 Card에 같은 요청을 보내면 현재 Card를 반환한다.

### `GET /api/v1/employee/value-report`

12개 가치의 진행 상태와 검토가 끝난 Card를 반환한다.

```json
{
  "employee": {
    "id": "d3474f47-b779-472b-b1ff-bf6385569f92",
    "name": "김인터"
  },
  "summary": {
    "completed_values": 1,
    "total_values": 12,
    "percentage": 8
  },
  "values": [
    {
      "week_number": 1,
      "core_value": {
        "code": "relationship_based_communication",
        "name": "관계기반 전략소통"
      },
      "status": "completed",
      "record": {
        "assignment_title": "신규 프로젝트 이해관계자 인터뷰",
        "card_id": "17229a4b-a5da-443f-8990-ce6a7e3724af",
        "card_content": {
          "schema_version": "1.0",
          "key_actions": [
            {
              "text": "이해관계자에게 질문의 목적을 설명하고 실제 업무 흐름을 확인했다.",
              "source_refs": [
                "evidence.performed_action"
              ]
            }
          ],
          "value_connection": {
            "text": "상대방의 상황을 확인하고 질문 방식을 조정한 행동은 관계기반 전략소통과 연결된다.",
            "source_refs": [
              "core_value.definition",
              "evidence.performed_action",
              "evidence.changed_judgment"
            ]
          },
          "evidence_summary": {
            "text": "인터뷰 기록을 행동 근거로 활용했다.",
            "source_refs": [
              "evidence.performed_action"
            ]
          },
          "discovery": {
            "text": "담당자마다 필요한 정보의 범위가 다름을 확인했다.",
            "source_refs": [
              "evidence.discovery"
            ]
          },
          "judgment_change": {
            "text": "공통 질문만 사용하지 않고 담당자별 질문을 추가하기로 했다.",
            "source_refs": [
              "evidence.changed_judgment"
            ]
          },
          "work_impact": {
            "text": "후속 확인 횟수를 줄일 수 있도록 인터뷰 항목을 보완했다.",
            "source_refs": [
              "evidence.work_impact"
            ]
          },
          "next_action": {
            "text": "다음 인터뷰에서도 상대방의 역할에 따라 질문을 조정한다.",
            "source_refs": [
              "evidence.next_action"
            ]
          },
          "grounding_warnings": []
        },
        "manager_feedback": {
          "observed_behavior": "질문의 목적을 먼저 설명하고 인터뷰를 진행했습니다.",
          "work_impact": "필요한 정보를 짧은 시간 안에 확보했습니다.",
          "positive_feedback": "상대방의 상황을 확인한 점이 좋았습니다.",
          "next_action": "다음에는 인터뷰 결과를 팀에 더 빨리 공유해 주세요."
        }
      }
    },
    {
      "week_number": 2,
      "core_value": {
        "code": "obsessive_curiosity",
        "name": "강박적 호기심"
      },
      "status": "awaiting_manager",
      "record": null
    }
  ]
}
```

`record`는 manager_reviewed 상태에서만 포함한다.

## 6. Manager API

### `GET /api/v1/manager/reviews`

manager 인증 필요. 기본적으로 본인 담당의 `user_confirmed` Card만 반환한다.

Query:

- `status`: 기본 `pending`, 허용 `pending`, `completed`
- `limit`: 기본 20, 최대 50
- `cursor`: opaque string

Response 200:

```json
{
  "items": [
    {
      "card_id": "17229a4b-a5da-443f-8990-ce6a7e3724af",
      "status": "user_confirmed",
      "employee": {
        "id": "d3474f47-b779-472b-b1ff-bf6385569f92",
        "name": "김인터",
        "job_role": "ax"
      },
      "week_number": 2,
      "core_value_name": "강박적 호기심",
      "assignment_title": "반복적인 HR 문의 분석 및 자동화 프로토타입 구축",
      "confirmed_at": "2026-07-31T04:40:00Z"
    }
  ],
  "next_cursor": null
}
```

### `GET /api/v1/manager/reviews/{card_id}`

본인 담당 Card의 상세를 반환한다.

```json
{
  "card": {
    "id": "17229a4b-a5da-443f-8990-ce6a7e3724af",
    "status": "user_confirmed",
    "content": {
      "schema_version": "1.0",
      "key_actions": [
        {
          "text": "HR 담당자 두 명을 인터뷰해 실제 문의 흐름을 확인했다.",
          "source_refs": [
            "evidence.performed_action"
          ]
        }
      ],
      "value_connection": {
        "text": "실제 업무 흐름을 질문하고 초기 판단을 수정한 행동은 문제의 본질을 탐색하는 강박적 호기심과 연결된다.",
        "source_refs": [
          "core_value.definition",
          "evidence.performed_action",
          "evidence.changed_judgment"
        ]
      },
      "evidence_summary": {
        "text": "인터뷰 요약과 업무 흐름 기록을 근거로 활용했다.",
        "source_refs": [
          "evidence.performed_action"
        ]
      },
      "discovery": {
        "text": "반복 문의의 주된 원인이 문의 경로 분산임을 발견했다.",
        "source_refs": [
          "evidence.discovery"
        ]
      },
      "judgment_change": {
        "text": "FAQ 추가보다 단일 문의 진입점을 우선하는 방향으로 판단을 변경했다.",
        "source_refs": [
          "evidence.changed_judgment"
        ]
      },
      "work_impact": {
        "text": "프로토타입 범위를 단일 진입점과 문의 분류 기능 중심으로 조정했다.",
        "source_refs": [
          "evidence.work_impact"
        ]
      },
      "next_action": {
        "text": "다음 업무에서도 구현 전에 사용 흐름을 먼저 확인한다.",
        "source_refs": [
          "evidence.next_action"
        ]
      },
      "grounding_warnings": []
    },
    "version": 3,
    "generation": {
      "provider": "groq",
      "model_name": "openai/gpt-oss-20b"
    }
  },
  "employee": {
    "id": "d3474f47-b779-472b-b1ff-bf6385569f92",
    "name": "김인터",
    "job_role": "ax"
  },
  "onboarding": {
    "week_number": 2,
    "stage": "guided"
  },
  "core_value": {
    "code": "obsessive_curiosity",
    "name": "강박적 호기심",
    "full_description": "표면적인 현상에 머무르지 않고 질문과 검증을 통해 문제의 본질을 탐색한다."
  },
  "assignment": {
    "id": "76590868-bcbc-4a96-b2e5-4628372d28a7",
    "title": "반복적인 HR 문의 분석 및 자동화 프로토타입 구축",
    "description": "반복 문의의 원인을 파악하고 자동화 프로토타입을 만듭니다.",
    "work_type": "prototype_build"
  },
  "actions": [
    {
      "id": "6438fc54-ab01-4d90-96ce-b5a5e68de1b2",
      "text": "실제 사용자 또는 업무 담당자 2명 이상에게 현재 업무 흐름을 확인한다.",
      "completion_criteria": "2명 이상의 확인 기록이 있다.",
      "status": "completed"
    }
  ],
  "evidence": {
    "id": "dd106a8a-d601-4d32-9bf0-abff8caf7a18",
    "performed_action": "HR 담당자 두 명을 인터뷰했다.",
    "discovery": "문의 경로의 분산이 더 큰 원인이었다.",
    "changed_judgment": "단일 문의 진입점을 우선하기로 했다.",
    "work_impact": "프로토타입 범위를 조정했다.",
    "next_action": "다음에도 사용 흐름을 먼저 확인한다.",
    "links": []
  },
  "feedback": null,
  "permissions": {
    "can_submit_feedback": true
  }
}
```

### `POST /api/v1/evidence-cards/{card_id}/feedback`

manager 인증 및 CSRF 필요. 피드백 제출이 승인과 리포트 반영을 의미한다.

Request:

```json
{
  "observed_behavior": "구현 전에 담당자를 직접 인터뷰하고 실제 문의 흐름을 확인했습니다.",
  "work_impact": "프로토타입 범위가 실제 문제에 맞게 단순해졌습니다.",
  "positive_feedback": "초기 가설을 고집하지 않고 조사 결과에 따라 판단을 바꾼 점이 좋았습니다.",
  "next_action": "다음 업무에서는 변경 전후의 처리 시간을 함께 측정해 보세요."
}
```

Response 201:

```json
{
  "feedback": {
    "id": "35aa784a-e183-4a9b-94b1-e7b42825bd10",
    "evidence_card_id": "17229a4b-a5da-443f-8990-ce6a7e3724af",
    "observed_behavior": "구현 전에 담당자를 직접 인터뷰하고 실제 문의 흐름을 확인했습니다.",
    "work_impact": "프로토타입 범위가 실제 문제에 맞게 단순해졌습니다.",
    "positive_feedback": "초기 가설을 고집하지 않고 조사 결과에 따라 판단을 바꾼 점이 좋았습니다.",
    "next_action": "다음 업무에서는 변경 전후의 처리 시간을 함께 측정해 보세요.",
    "submitted_at": "2026-07-31T04:50:00Z"
  },
  "card_status": "manager_reviewed",
  "assignment_status": "completed"
}
```

이미 피드백이 있으면 `200`과 기존 피드백을 반환한다.

오류:

- 404 `RESOURCE_NOT_FOUND`
- 409 `CARD_NOT_READY_FOR_MANAGER`

## 7. HR API

모든 endpoint는 hr 인증이 필요하며 읽기 전용이다.

### `GET /api/v1/hr/core-values`

12개 핵심가치를 `display_order` 순으로 반환한다.

### `GET /api/v1/hr/curriculum`

주차, 핵심가치, stage를 week 순으로 반환한다.

### `GET /api/v1/hr/action-library`

Query:

- `core_value_code`
- `job_role`
- `work_type`
- `stage`
- `is_active`
- `limit`, `cursor`

### `GET /api/v1/hr/overview`

데모 온보딩 진행 상태를 반환한다.

```json
{
  "summary": {
    "employees": 1,
    "active_onboardings": 1,
    "awaiting_manager_reviews": 1,
    "completed_cards": 1
  },
  "employees": [
    {
      "employee_id": "d3474f47-b779-472b-b1ff-bf6385569f92",
      "display_name": "김인터",
      "job_role": "ax",
      "current_week": 2,
      "week_status": "awaiting_manager",
      "completed_values": 1
    }
  ]
}
```

MVP의 모든 데이터는 가상 데모 데이터다. 실제 운영 전에는 HR overview를 익명화된
집계 응답으로 변경해야 한다.

## 8. 오류 코드 목록

### 인증/권한

- `AUTH_REQUIRED`
- `SESSION_EXPIRED`
- `INVALID_CREDENTIALS`
- `USER_INACTIVE`
- `ROLE_FORBIDDEN`
- `CSRF_INVALID`
- `ORIGIN_FORBIDDEN`
- `LOGIN_RATE_LIMITED`
- `RESOURCE_NOT_FOUND`

### Action/Evidence

- `ASSIGNMENT_NOT_ACTIVE`
- `ACTION_LOCKED_BY_EVIDENCE`
- `REQUIRED_ACTIONS_INCOMPLETE`
- `ACTION_NOT_COMPLETED`
- `ACTION_ASSIGNMENT_MISMATCH`
- `EVIDENCE_ALREADY_EXISTS`
- `INVALID_LINK_SCHEME`

### Card/Feedback

- `CARD_GENERATION_IN_PROGRESS`
- `CARD_NOT_EDITABLE`
- `CARD_SCHEMA_INVALID`
- `CARD_SOURCE_REF_INVALID`
- `INVALID_CARD_TRANSITION`
- `CARD_NOT_READY_FOR_MANAGER`
- `RESOURCE_VERSION_CONFLICT`

### 공통

- `VALIDATION_ERROR`
- `INVALID_JSON`
- `DATABASE_UNAVAILABLE`
- `INTERNAL_ERROR`

## 9. OpenAPI와 타입 동기화

- FastAPI Pydantic model이 OpenAPI의 source of truth다.
- CI에서 `/openapi.json`을 파일로 export한다.
- 프론트엔드의 API 타입을 OpenAPI에서 생성하거나 Zod schema와 대조한다.
- 배포된 demo 환경에서는 Swagger UI를 공개하지 않고 OpenAPI artifact를 저장소에 둔다.
- endpoint 구현이 문서와 다르면 코드를 임의로 맞추지 말고 먼저 계약 문서를 변경한다.

권장 Pydantic model 이름:

```text
LoginRequest / LoginResponse
UserResponse
EmployeeDashboardResponse
AssignedActionUpdateRequest / AssignedActionResponse
EvidenceCreateRequest / EvidenceResponse
EvidenceCardResponse
EvidenceCardUpdateRequest
EvidenceCardConfirmRequest
ManagerReviewListResponse / ManagerReviewDetailResponse
ManagerFeedbackCreateRequest / ManagerFeedbackResponse
ValueReportResponse
ApiErrorResponse
```

## 10. API 테스트 필수 목록

1. 로그인 성공/실패/비활성 계정/rate limit
2. session expiry와 logout revoke
3. Origin 및 CSRF 실패
4. 역할별 endpoint 접근
5. 다른 직원/팀장 리소스 IDOR
6. dashboard의 assignment 없음/Action 0개
7. Action version 충돌과 멱등 상태 변경
8. 필수 Action 미완료 Evidence 차단
9. Evidence 중복 제출
10. 잘못된 scheme과 링크 4개 제출
11. Card 최초 생성/기존 결과/처리 중/실패 재시도
12. Card content schema와 source reference 검증
13. 확정 후 수정 차단
14. 담당하지 않는 직원 피드백 차단
15. 피드백 중복 요청 멱등 처리
16. manager_reviewed Card만 report에 표시
17. `/health`는 DB 장애 중에도 200
18. `/ready`는 DB 장애 시 503
