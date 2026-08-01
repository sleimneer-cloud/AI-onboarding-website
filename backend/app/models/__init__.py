"""Import every model so Alembic sees the complete metadata registry."""

from app.models.actions import ActionLibrary, AssignedAction, WorkAssignment
from app.models.auth import AuthRateLimit, AuthSession, User
from app.models.evidence import (
    EvidenceCard,
    EvidenceLink,
    EvidenceSubmission,
    EvidenceSubmissionAction,
    ManagerFeedback,
)
from app.models.onboarding import CoreValue, CurriculumWeek, OnboardingProfile, OnboardingWeek

__all__ = [
    "ActionLibrary",
    "AssignedAction",
    "AuthRateLimit",
    "AuthSession",
    "CoreValue",
    "CurriculumWeek",
    "EvidenceCard",
    "EvidenceLink",
    "EvidenceSubmission",
    "EvidenceSubmissionAction",
    "ManagerFeedback",
    "OnboardingProfile",
    "OnboardingWeek",
    "User",
    "WorkAssignment",
]
