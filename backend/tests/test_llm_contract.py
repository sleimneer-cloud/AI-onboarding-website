from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.core.config import REPOSITORY_ROOT, Settings
from app.models.enums import AIProvider
from app.schemas.llm import (
    CardContentV1,
    CardSourceReferenceError,
    EvidenceCardGenerationInputV1,
    validate_card_source_refs,
)
from app.services import evidence_generation
from app.services.evidence_generation import (
    EvidenceGenerationError,
    EvidenceGenerationOrchestrator,
    GroqEvidenceGenerator,
    MockEvidenceGenerator,
)


def generation_input() -> EvidenceCardGenerationInputV1:
    action_id = uuid4()
    evidence_id = uuid4()
    link_id = uuid4()
    return EvidenceCardGenerationInputV1.model_validate(
        {
            "schema_version": "1.0",
            "request_id": str(uuid4()),
            "language": "ko-KR",
            "core_value": {
                "code": "obsessive_curiosity",
                "name": "강박적 호기심",
                "definition": "질문과 검증으로 문제의 본질을 탐색합니다.",
            },
            "onboarding": {"week_number": 2, "stage": "guided"},
            "assignment": {
                "id": str(uuid4()),
                "title": "허구 HR 문의 분석",
                "description": "반복 문의의 원인을 확인하는 허구 업무입니다.",
                "work_type": "prototype_build",
                "description_source_ref": "assignment.description",
            },
            "actions": [
                {
                    "id": str(action_id),
                    "text": "담당자에게 현재 업무 흐름을 확인한다.",
                    "completion_criteria": "확인 기록이 있다.",
                    "source_ref": f"action:{action_id}",
                }
            ],
            "evidence": {
                "id": str(evidence_id),
                "performed_action": {
                    "text": "담당자 두 명을 인터뷰하고 실제 문의 흐름을 확인했습니다.",
                    "source_ref": "evidence.performed_action",
                },
                "discovery": {
                    "text": "문의 진입 경로가 분산된 것이 더 큰 원인이었습니다.",
                    "source_ref": "evidence.discovery",
                },
                "changed_judgment": {
                    "text": "FAQ 추가보다 단일 문의 진입점을 먼저 만들기로 했습니다.",
                    "source_ref": "evidence.changed_judgment",
                },
                "work_impact": {
                    "text": "프로토타입 범위를 단일 문의 흐름 중심으로 줄였습니다.",
                    "source_ref": "evidence.work_impact",
                },
                "next_action": {
                    "text": "다음 업무에서도 실제 사용자 흐름을 먼저 확인합니다.",
                    "source_ref": "evidence.next_action",
                },
                "links": [
                    {
                        "id": str(link_id),
                        "title": "허구 인터뷰 요약",
                        "description": "담당자 인터뷰 흐름을 정리한 허구 문서입니다.",
                        "source_ref": f"link:{link_id}",
                    }
                ],
            },
        }
    )


def test_generation_input_rejects_unknown_fields_and_never_contains_link_url() -> None:
    payload = generation_input().model_dump(mode="json")
    payload["unknown"] = True
    with pytest.raises(ValidationError):
        EvidenceCardGenerationInputV1.model_validate(payload)

    serialized = generation_input().model_dump_json()
    assert "external_url" not in serialized
    assert "https://" not in serialized


def test_pydantic_output_contract_matches_canonical_required_fields() -> None:
    canonical_path = Path(REPOSITORY_ROOT) / "docs" / "schemas" / "card_content_v1.schema.json"
    canonical = json.loads(canonical_path.read_text(encoding="utf-8"))
    generated = CardContentV1.model_json_schema()

    assert set(generated["required"]) == set(canonical["required"])
    assert generated["additionalProperties"] is False
    assert generated["properties"]["key_actions"]["minItems"] == 1
    assert generated["properties"]["key_actions"]["maxItems"] == 5
    assert generated["properties"]["grounding_warnings"]["maxItems"] == 7


def test_card_content_rejects_missing_extra_duplicate_and_unknown_source_refs() -> None:
    valid = {
        "schema_version": "1.0",
        "key_actions": [
            {
                "text": "담당자를 인터뷰했습니다.",
                "source_refs": ["evidence.performed_action"],
            }
        ],
        "value_connection": {
            "text": "공식 가치 정의와 기록한 행동을 함께 확인했습니다.",
            "source_refs": ["core_value.definition", "evidence.performed_action"],
        },
        "evidence_summary": {
            "text": "인터뷰 기록을 근거로 사용했습니다.",
            "source_refs": ["evidence.performed_action"],
        },
        "discovery": {
            "text": "문의 경로가 분산되어 있었습니다.",
            "source_refs": ["evidence.discovery"],
        },
        "judgment_change": {
            "text": "단일 문의 진입점을 우선하기로 했습니다.",
            "source_refs": ["evidence.changed_judgment"],
        },
        "work_impact": {
            "text": "프로토타입 범위를 줄였습니다.",
            "source_refs": ["evidence.work_impact"],
        },
        "next_action": {
            "text": "다음에도 사용자 흐름을 먼저 확인합니다.",
            "source_refs": ["evidence.next_action"],
        },
        "grounding_warnings": [],
    }
    parsed = CardContentV1.model_validate(valid)

    with pytest.raises(ValidationError):
        CardContentV1.model_validate({**valid, "unknown": True})
    with pytest.raises(ValidationError):
        CardContentV1.model_validate(
            {key: value for key, value in valid.items() if key != "next_action"}
        )
    duplicate = json.loads(json.dumps(valid))
    duplicate["discovery"]["source_refs"] = ["evidence.discovery", "evidence.discovery"]
    with pytest.raises(ValidationError):
        CardContentV1.model_validate(duplicate)

    with pytest.raises(CardSourceReferenceError):
        validate_card_source_refs(parsed, frozenset({"evidence.performed_action"}))


async def test_deterministic_mock_uses_only_input_and_valid_source_refs() -> None:
    input_data = generation_input()
    generator = MockEvidenceGenerator()

    first = await generator.generate(input_data, timeout_seconds=8)
    second = await generator.generate(input_data, timeout_seconds=8)

    assert first == second
    assert first.discovery.text == input_data.evidence.discovery.text
    assert first.work_impact.text == input_data.evidence.work_impact.text
    assert input_data.evidence.links[0].title in first.evidence_summary.text
    validate_card_source_refs(first, input_data.allowed_source_refs())


async def test_groq_adapter_requests_strict_schema_and_validates_response(monkeypatch) -> None:
    input_data = generation_input()
    expected = await MockEvidenceGenerator().generate(input_data, timeout_seconds=8)
    captured: dict[str, object] = {}

    class FakeCompletions:
        async def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=expected.model_dump_json())
                    )
                ]
            )

    class FakeClient:
        def __init__(self, **kwargs) -> None:
            captured["client"] = kwargs
            self.chat = SimpleNamespace(completions=FakeCompletions())

        def with_options(self, **kwargs):
            captured["options"] = kwargs
            return self

        async def close(self) -> None:
            captured["closed"] = True

    monkeypatch.setattr(evidence_generation, "AsyncGroq", FakeClient)
    generator = GroqEvidenceGenerator(api_key="test-key", model_name="openai/gpt-oss-20b")

    result = await generator.generate(input_data, timeout_seconds=3.5)

    assert result == expected
    assert captured["client"] == {"api_key": "test-key", "max_retries": 0}
    assert captured["options"] == {"timeout": 3.5}
    response_format = captured["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert captured["reasoning_effort"] == "low"
    assert captured["max_completion_tokens"] == 1200
    assert captured["closed"] is True


class FailingGenerator:
    def __init__(self, error: EvidenceGenerationError) -> None:
        self.error = error
        self.calls = 0

    async def generate(self, generation_input, *, timeout_seconds):
        del generation_input, timeout_seconds
        self.calls += 1
        raise self.error


class BrokenMock:
    async def generate(self, generation_input, *, timeout_seconds):
        del generation_input, timeout_seconds
        raise RuntimeError("mock failed")


async def test_groq_timeout_retries_once_then_uses_labeled_mock() -> None:
    settings = Settings(_env_file=None, app_env="test", ai_provider="groq")
    groq_generator = FailingGenerator(
        EvidenceGenerationError("AI_TIMEOUT", retryable=True)
    )
    orchestrator = EvidenceGenerationOrchestrator(
        settings=settings,
        groq_generator=groq_generator,
    )

    result = await orchestrator.generate(generation_input())

    assert groq_generator.calls == 2
    assert result.provider is AIProvider.MOCK
    assert result.model_name is None
    assert result.last_error_code == "AI_TIMEOUT"
    assert result.content is not None


async def test_long_rate_limit_retry_after_skips_retry_and_falls_back() -> None:
    settings = Settings(_env_file=None, app_env="test", ai_provider="groq")
    groq_generator = FailingGenerator(
        EvidenceGenerationError(
            "AI_RATE_LIMITED",
            retryable=True,
            retry_after_seconds=60,
        )
    )
    orchestrator = EvidenceGenerationOrchestrator(
        settings=settings,
        groq_generator=groq_generator,
    )

    result = await orchestrator.generate(generation_input())

    assert groq_generator.calls == 1
    assert result.provider is AIProvider.MOCK
    assert result.last_error_code == "AI_RATE_LIMITED"


async def test_generation_failed_only_when_groq_and_mock_both_fail() -> None:
    settings = Settings(_env_file=None, app_env="test", ai_provider="groq")
    orchestrator = EvidenceGenerationOrchestrator(
        settings=settings,
        groq_generator=FailingGenerator(
            EvidenceGenerationError("AI_UPSTREAM_ERROR", retryable=False)
        ),
        mock_generator=BrokenMock(),
    )

    result = await orchestrator.generate(generation_input())

    assert result.content is None
    assert result.provider is None
    assert result.last_error_code == "MOCK_GENERATION_FAILED"
