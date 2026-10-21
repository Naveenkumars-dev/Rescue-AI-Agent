"""Request/response models and the validated structured decision schema.

The structured decision output is the auditable artefact of one agent evaluation. It is always
validated with Pydantic; invalid model output is caught and surfaced as a ``NEEDS_REVIEW``
decision rather than crashing the API.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# --- enums -----------------------------------------------------------------------------


class Priority(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    NEEDS_REVIEW = "NEEDS_REVIEW"


class DecisionStatus(str, Enum):
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_INFORMATION = "NEEDS_MORE_INFORMATION"


class DecisionAction(str, Enum):
    """Internal triage verdict from the reusable decision pattern."""

    ALLOW = "allow"        # propose a response plan for human approval
    REVIEW = "review"      # hold for a human coordinator
    BLOCK = "block"        # escalate life-safety incident, never auto-recommend


# --- incidents -------------------------------------------------------------------------


class IncidentCreate(BaseModel):
    type: str = Field(..., description="Incident type, e.g. flood, fire, road obstruction")
    location: str = Field(..., min_length=1, description="Where the incident is happening")
    report: str = Field(..., min_length=1, description="The free-text incident report")
    severity: int = Field(1, ge=1, le=5, description="Reported severity (1-5)")
    time_sensitivity: int = Field(3, ge=1, le=5, description="Time sensitivity (1-5)")
    affected_people_num: int = Field(0, ge=0, description="Known number of people affected (0 if unknown)")
    hazard_level: int = Field(1, ge=1, le=5, description="Hazard level (1-5)")
    hazards: str = Field("none reported", description="Known hazards")


class IncidentOut(BaseModel):
    id: str
    type: str
    location: str
    affected_people: str
    affected_people_num: int
    hazards: str
    time_sensitivity: int
    severity: int
    hazard_level: int
    report_time: str
    status: str
    report: str
    preliminary_score: int | None = None


# --- the structured decision -----------------------------------------------------------


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any]
    result: dict[str, Any]
    latency_ms: int = 0


class DeciderEvidence(BaseModel):
    """The raw Strands Decider 2B answers that produced the verdict (live mode)."""

    priority_probabilities: dict[str, float] = Field(default_factory=dict)
    next_action: str | None = None
    next_action_probabilities: dict[str, float] = Field(default_factory=dict)
    life_safety_p_yes: float | None = None
    triage_action: str | None = None  # allow / review / block
    decider_latency_ms: int | None = None


class StructuredDecision(BaseModel):
    incident_id: str
    priority: Priority
    recommended_action: str
    reason_summary: str
    factors_considered: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    resource_recommendations: list[str] = Field(default_factory=list)
    alternatives_considered: list[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
    human_review_required: bool = True
    decision_status: DecisionStatus = DecisionStatus.PROPOSED

    # provenance / auditability
    response_plan: str | None = None
    preliminary_score: int | None = None
    triage_action: DecisionAction = DecisionAction.REVIEW
    live_decider: bool = False
    live_llm: bool = False
    mode: str = "demo"  # "live" | "demo"
    decider_evidence: DeciderEvidence | None = None


class DecisionResponse(BaseModel):
    decision_id: str
    decision: StructuredDecision
    tool_calls: list[ToolCall] = Field(default_factory=list)
    model_id: str
    latency_ms: int
    mode: str


# --- decision arena --------------------------------------------------------------------


class ArenaRequest(BaseModel):
    incident_ids: list[str] = Field(..., min_length=2, description="Two or more incident ids to compare")


class ArenaRanking(BaseModel):
    rank: int
    incident_id: str
    incident_type: str
    location: str
    priority: Priority
    priority_rank: float
    preliminary_score: int
    triage_action: DecisionAction
    recommended_action: str
    human_review_required: bool
    reason: str
    decision_id: str


class ArenaResponse(BaseModel):
    ranking: list[ArenaRanking]
    explanation: str
    trade_offs: list[str] = Field(default_factory=list)
    unresolved_uncertainties: list[str] = Field(default_factory=list)
    what_could_change_it: list[str] = Field(default_factory=list)
    comparison: dict[str, Any]
    tool_calls: list[ToolCall] = Field(default_factory=list)
    decisions: list[DecisionResponse] = Field(default_factory=list)
    mode: str
    model_id: str
    latency_ms: int


class ChangeConditionsRequest(BaseModel):
    """Change one incident's conditions, then re-run the arena."""

    incident_id: str
    changes: dict[str, Any] = Field(..., description="Fields to update on the incident, e.g. severity=5")
    note: str = ""


class ArenaReassessResponse(BaseModel):
    before: ArenaResponse
    after: ArenaResponse
    change_applied: dict[str, Any]
    note: str


# --- per-incident reassess -------------------------------------------------------------


class ReassessRequest(BaseModel):
    changes: dict[str, Any] = Field(..., description="Fields to update on the incident before re-evaluating")
    note: str = ""


class ReassessResponse(BaseModel):
    incident_id: str
    before: DecisionResponse
    after: DecisionResponse
    change_applied: dict[str, Any]
    note: str


# --- dashboard / misc ------------------------------------------------------------------


class DashboardSummary(BaseModel):
    active_incidents: int
    critical_count: int
    high_count: int
    pending_human_review: int
    total_decisions: int
    proposed: int
    approved: int
    rejected: int
    needs_more_information: int
    resources: list[dict[str, Any]]
    mode: str


class ApproveRequest(BaseModel):
    reviewer_note: str = ""


class ModeInfo(BaseModel):
    mode: str
    decider_live: bool
    decider_mode: str
    decider_model: str
    llm_live: bool
    llm_provider: str
    llm_model_id: str
    reason: str
    agent_name: str
    kit_credit: str
    checked_at: str


class HealthResponse(BaseModel):
    status: str
    mode: str
    decider_live: bool
    llm_live: bool
