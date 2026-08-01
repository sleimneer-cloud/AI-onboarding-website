from enum import StrEnum
from typing import TypeVar

from sqlalchemy import Enum as SQLAlchemyEnum


class UserRole(StrEnum):
    EMPLOYEE = "employee"
    MANAGER = "manager"
    HR = "hr"


class OnboardingStage(StrEnum):
    GUIDED = "guided"
    ASSISTED = "assisted"
    AUTONOMOUS = "autonomous"


class WorkType(StrEnum):
    USER_INTERVIEW = "user_interview"
    PROCESS_ANALYSIS = "process_analysis"
    PROBLEM_DEFINITION = "problem_definition"
    DATA_ANALYSIS = "data_analysis"
    SERVICE_PLANNING = "service_planning"
    PROTOTYPE_BUILD = "prototype_build"
    USER_VALIDATION = "user_validation"
    COLLABORATION = "collaboration"
    RESULT_IMPROVEMENT = "result_improvement"


class AssignmentStatus(StrEnum):
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ActionSourceKind(StrEnum):
    LIBRARY = "library"
    CUSTOM = "custom"


class ActionStatus(StrEnum):
    PENDING = "pending"
    COMPLETED = "completed"


class EvidenceCardStatus(StrEnum):
    AI_PROCESSING = "ai_processing"
    GENERATION_FAILED = "generation_failed"
    USER_REVIEW = "user_review"
    USER_CONFIRMED = "user_confirmed"
    MANAGER_REVIEWED = "manager_reviewed"


class AIProvider(StrEnum):
    GROQ = "groq"
    MOCK = "mock"


EnumType = TypeVar("EnumType", bound=StrEnum)


def enum_values(enum_class: type[EnumType]) -> list[str]:
    return [member.value for member in enum_class]


def database_enum(
    enum_class: type[EnumType],
    name: str,
) -> SQLAlchemyEnum:
    return SQLAlchemyEnum(
        enum_class,
        name=name,
        native_enum=True,
        validate_strings=True,
        values_callable=enum_values,
    )
