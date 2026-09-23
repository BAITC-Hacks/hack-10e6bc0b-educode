"""Validated contracts for the SANA FORGE product flow."""

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

Topic = Literal["AI-ML", "Education", "FinTech", "Smart City", "Healthcare", "Other"]
Readiness = Literal["RAW", "SHAPING", "READY", "FORGED"]
ProposalStatus = Literal["PENDING", "SELECTED", "DECLINED"]
StageStatus = Literal["PENDING", "COMPLETED"]

CANVAS_FIELDS = (
    "title",
    "context",
    "need",
    "users",
    "data_materials",
    "constraints",
    "expected_result",
    "success_criteria",
    "contact",
    "interaction_format",
)


class ChallengeCanvas(BaseModel):
    title: str | None = None
    context: str | None = None
    need: str | None = None
    users: str | None = None
    data_materials: str | None = None
    constraints: str | None = None
    expected_result: str | None = None
    success_criteria: str | None = None
    contact: str | None = None
    interaction_format: str | None = None

    @field_validator("*")
    @classmethod
    def normalize_empty_values(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class MissionQuestion(BaseModel):
    mission: Literal[
        "DEFINE THE WIN",
        "UNLOCK THE DATA",
        "SET THE BOUNDARIES",
        "CONNECT WITH TEAM",
    ]
    target_field: Literal[
        "context",
        "need",
        "expected_result",
        "success_criteria",
        "data_materials",
        "constraints",
        "users",
        "contact",
        "interaction_format",
    ]
    question: str = Field(min_length=5)
    hint: str


class AIAnalysis(BaseModel):
    known_information: dict[str, str]
    missing_information: list[str]
    questions: list[MissionQuestion] = Field(min_length=3)
    canvas: ChallengeCanvas
    challenge_health: list[str]
    fallback_used: bool = False


class RefinementRequest(BaseModel):
    question: MissionQuestion
    answer: str = Field(min_length=2, max_length=2000)

    @field_validator("answer")
    @classmethod
    def answer_is_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 2:
            raise ValueError("Ответ должен содержать минимум 2 символа")
        return normalized


class AIQuestionAdvice(BaseModel):
    """Structured model output. Score and field selection stay outside the model."""

    target_field: Literal[
        "context",
        "need",
        "expected_result",
        "success_criteria",
        "data_materials",
        "constraints",
        "users",
        "contact",
        "interaction_format",
    ]
    feedback: str = Field(min_length=2, max_length=500)
    question: str = Field(min_length=5, max_length=500)
    hint: str = Field(min_length=2, max_length=500)


class DraftCreate(BaseModel):
    raw_idea: str = Field(min_length=20, max_length=3000)
    topic: Topic = "Other"

    @field_validator("raw_idea")
    @classmethod
    def raw_idea_is_not_blank(cls, value: str) -> str:
        normalized = value.strip()
        if len(normalized) < 20:
            raise ValueError("Опишите проблему минимум в 20 символах")
        return normalized


class CanvasUpdate(BaseModel):
    canvas: ChallengeCanvas
    topic: Topic


class ConfirmationRequest(BaseModel):
    confirmed: Literal[True]


class ProposalCreate(BaseModel):
    team_id: int = Field(gt=0)
    idea: str = Field(min_length=10, max_length=2000)
    plan: str = Field(min_length=10, max_length=3000)
    deadline: str = Field(min_length=2, max_length=100)
    prototype_url: HttpUrl | None = None


class ProposalDecision(BaseModel):
    status: ProposalStatus

    @field_validator("status")
    @classmethod
    def pending_is_not_a_business_decision(cls, value: ProposalStatus) -> ProposalStatus:
        if value == "PENDING":
            raise ValueError("Business decision must be SELECTED or DECLINED")
        return value


class ScoreBreakdownItem(BaseModel):
    label: str
    points: int
    max_points: int
    complete: bool
    missing_fields: list[str]


class ScoreResult(BaseModel):
    total: int = Field(ge=0, le=100)
    level: Readiness
    breakdown: dict[str, ScoreBreakdownItem]
    missing_information: list[str]
    history: list[int]
