"""FastAPI routes for RescueFlow AI.

All endpoints use Pydantic request/response models, correct HTTP status codes, input validation
and useful error messages. The agent's decision is always returned with its provenance
(live_decider / live_llm / mode) so the UI can label simulated vs live decisions.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.agents.orchestrator import orchestrator
from app.config import mode_info, reset_mode_cache, runtime_mode
from app.schemas.models import (
    ApproveRequest,
    ArenaRequest,
    ArenaResponse,
    ChangeConditionsRequest,
    DashboardSummary,
    DecisionResponse,
    HealthResponse,
    IncidentCreate,
    IncidentOut,
    ModeInfo,
    ReassessRequest,
    ReassessResponse,
)
from app.storage.store import store
from app.tools import core as tools

router = APIRouter()


def _priority_score(inc: dict[str, Any]) -> int:
    return tools.preliminary_score(inc["severity"], inc["time_sensitivity"],
                                   inc["affected_people_num"], inc["hazard_level"])


def _to_out(inc: dict[str, Any]) -> IncidentOut:
    fields = {k: inc.get(k) for k in IncidentOut.model_fields if k != "preliminary_score"}
    fields["preliminary_score"] = _priority_score(inc)
    return IncidentOut(**fields)


# --- health / info --------------------------------------------------------------------


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    rm = runtime_mode()
    return HealthResponse(status="ok", mode=rm.label, decider_live=rm.decider_live, llm_live=rm.llm_live)


@router.get("/api/info", response_model=ModeInfo)
def info() -> ModeInfo:
    return ModeInfo(**mode_info())


# --- incidents ------------------------------------------------------------------------


@router.get("/api/incidents", response_model=list[IncidentOut])
def list_incidents(status: str | None = None) -> list[IncidentOut]:
    return [_to_out(i) for i in store.list_incidents(status)]


@router.post("/api/incidents", response_model=IncidentOut, status_code=201)
def create_incident(body: IncidentCreate) -> IncidentOut:
    inc = store.add_incident(body.model_dump())
    store.add_activity({"event": "incident_created", "incident_id": inc["id"], "type": inc["type"]})
    return _to_out(inc)


@router.get("/api/incidents/{incident_id}", response_model=IncidentOut)
def get_incident(incident_id: str) -> IncidentOut:
    inc = store.get_incident(incident_id)
    if not inc:
        raise HTTPException(status_code=404, detail=f"no incident with id {incident_id}")
    return _to_out(inc)


# --- decisions ------------------------------------------------------------------------


class EvaluateRequest(BaseModel):
    incident_id: str


@router.post("/api/decisions/evaluate", response_model=DecisionResponse)
def evaluate_decision(body: EvaluateRequest) -> DecisionResponse:
    if not store.get_incident(body.incident_id):
        raise HTTPException(status_code=404, detail=f"no incident with id {body.incident_id}")
    try:
        return orchestrator.evaluate_incident(body.incident_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"agent error: {type(e).__name__}: {e}") from e


@router.post("/api/incidents/{incident_id}/reassess", response_model=ReassessResponse)
def reassess_incident(incident_id: str, body: ReassessRequest) -> ReassessResponse:
    if not store.get_incident(incident_id):
        raise HTTPException(status_code=404, detail=f"no incident with id {incident_id}")
    try:
        return orchestrator.reassess(incident_id, body.changes, body.note)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"agent error: {type(e).__name__}: {e}") from e


@router.get("/api/decisions/{decision_id}")
def get_decision(decision_id: str) -> dict[str, Any]:
    d = store.get_decision(decision_id)
    if not d:
        raise HTTPException(status_code=404, detail=f"no decision with id {decision_id}")
    return d


@router.get("/api/decisions")
def list_decisions(incident_id: str | None = None) -> list[dict[str, Any]]:
    return store.list_decisions(incident_id)


@router.post("/api/decisions/{decision_id}/approve")
def approve_decision(decision_id: str, body: ApproveRequest) -> dict[str, Any]:
    d = orchestrator.approve(decision_id, body.reviewer_note)
    if not d:
        raise HTTPException(status_code=404, detail=f"no decision with id {decision_id}")
    return {"decision_id": decision_id, "decision_status": "APPROVED", "record": d}


@router.post("/api/decisions/{decision_id}/reject")
def reject_decision(decision_id: str, body: ApproveRequest) -> dict[str, Any]:
    d = orchestrator.reject(decision_id, body.reviewer_note)
    if not d:
        raise HTTPException(status_code=404, detail=f"no decision with id {decision_id}")
    return {"decision_id": decision_id, "decision_status": "REJECTED", "record": d}


# --- decision arena -------------------------------------------------------------------


@router.post("/api/arena/evaluate", response_model=ArenaResponse)
def evaluate_arena(body: ArenaRequest) -> ArenaResponse:
    for iid in body.incident_ids:
        if not store.get_incident(iid):
            raise HTTPException(status_code=404, detail=f"no incident with id {iid}")
    try:
        return orchestrator.evaluate_arena(body.incident_ids)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"agent error: {type(e).__name__}: {e}") from e


class ArenaReassessRequest(BaseModel):
    incident_ids: list[str]
    change: ChangeConditionsRequest


@router.post("/api/arena/reassess")
def arena_reassess(body: ArenaReassessRequest) -> dict[str, Any]:
    """Change one incident's conditions, then re-run the arena (before/after comparison)."""
    if not store.get_incident(body.change.incident_id):
        raise HTTPException(status_code=404, detail=f"no incident with id {body.change.incident_id}")
    try:
        return orchestrator.arena_reassess(
            body.incident_ids,
            {"incident_id": body.change.incident_id, "changes": body.change.changes,
             "note": body.change.note},
        )
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"agent error: {type(e).__name__}: {e}") from e


# --- dashboard ------------------------------------------------------------------------


@router.get("/api/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary() -> DashboardSummary:
    incidents = store.list_incidents()
    active = [i for i in incidents if i.get("status") == "active"]
    decisions = store.list_decisions()
    rm = runtime_mode()

    def count_priority(level: str) -> int:
        return sum(1 for d in decisions if d.get("priority") == level)

    return DashboardSummary(
        active_incidents=len(active),
        critical_count=count_priority("CRITICAL"),
        high_count=count_priority("HIGH"),
        pending_human_review=sum(1 for d in decisions if d.get("human_review_required")),
        total_decisions=len(decisions),
        proposed=sum(1 for d in decisions if d.get("decision_status") == "PROPOSED"),
        approved=sum(1 for d in decisions if d.get("decision_status") == "APPROVED"),
        rejected=sum(1 for d in decisions if d.get("decision_status") == "REJECTED"),
        needs_more_information=sum(1 for d in decisions if d.get("decision_status") == "NEEDS_MORE_INFORMATION"),
        resources=store.list_resources(),
        mode=rm.label,
    )


# --- activity / demo reset ------------------------------------------------------------


@router.get("/api/activity")
def list_activity(limit: int = 100) -> dict[str, Any]:
    return {"activity": store.list_activity(limit)}


@router.post("/api/demo/reset")
def reset_demo() -> dict[str, Any]:
    store.reset()
    reset_mode_cache()
    return {"ok": True, "message": "demo data reset to seed incidents and resources"}


__all__ = ["router"]


# --- streaming agent execution (SSE) ------------------------------------------------

import asyncio
import json as _json
import time as _time
from fastapi.responses import StreamingResponse


async def _stream_evaluate(incident_id: str):
    """Stream the agent workflow step-by-step as Server-Sent Events."""
    steps = [
        ("🔍", "get_incident_details", f"Fetching incident {incident_id}…"),
        ("📋", "list_active_incidents", "Scanning all active incidents…"),
        ("📊", "calculate_preliminary_risk", "Computing preliminary risk score…"),
        ("🚒", "get_resource_status", "Checking resource availability…"),
        ("⚠️",  "identify_information_gaps", "Identifying information gaps…"),
        ("🤖", "draft_recommendation", "Drafting recommendation…"),
        ("🧠", "strands_decider_2b", "Invoking Strands Decider 2B triage…"),
        ("📝", "propose_response_plan", "Proposing response plan…"),
        ("💾", "save_decision_record", "Saving decision record…"),
    ]

    def sse(data: dict) -> str:
        return f"data: {_json.dumps(data)}\n\n"

    yield sse({"type": "start", "incident_id": incident_id, "total_steps": len(steps)})
    await asyncio.sleep(0.05)

    for i, (icon, tool, msg) in enumerate(steps):
        yield sse({"type": "step", "step": i + 1, "icon": icon, "tool": tool, "message": msg})
        await asyncio.sleep(0.35)

    # Run actual evaluation
    try:
        result = orchestrator.evaluate_incident(incident_id)
        yield sse({"type": "complete", "result": result.model_dump(mode="json")})
    except Exception as e:
        yield sse({"type": "error", "message": str(e)})


@router.get("/api/decisions/stream/{incident_id}")
async def stream_evaluate(incident_id: str):
    if not store.get_incident(incident_id):
        raise HTTPException(status_code=404, detail=f"no incident with id {incident_id}")
    return StreamingResponse(
        _stream_evaluate(incident_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_arena(incident_ids: list[str]):
    """Stream Decision Arena evaluation step-by-step."""
    def sse(data: dict) -> str:
        return f"data: {_json.dumps(data)}\n\n"

    yield sse({"type": "start", "incident_ids": incident_ids, "count": len(incident_ids)})
    await asyncio.sleep(0.05)

    for i, iid in enumerate(incident_ids):
        inc = store.get_incident(iid) or {}
        yield sse({"type": "evaluating", "incident_id": iid,
                   "incident_type": inc.get("type", "?"), "index": i, "total": len(incident_ids)})
        await asyncio.sleep(0.1)
        for icon, tool, msg in [
            ("🔍", "get_incident_details", f"Fetching {iid}…"),
            ("📊", "calculate_preliminary_risk", f"Risk scoring {iid}…"),
            ("🧠", "strands_decider_2b", f"Decider triage for {iid}…"),
        ]:
            yield sse({"type": "tool", "incident_id": iid, "icon": icon, "tool": tool, "message": msg})
            await asyncio.sleep(0.25)

    yield sse({"type": "ranking", "message": "Ranking incidents by priority…"})
    await asyncio.sleep(0.3)

    try:
        result = orchestrator.evaluate_arena(incident_ids)
        yield sse({"type": "complete", "result": result.model_dump(mode="json")})
    except Exception as e:
        yield sse({"type": "error", "message": str(e)})


@router.post("/api/arena/stream")
async def stream_arena(body: ArenaRequest):
    for iid in body.incident_ids:
        if not store.get_incident(iid):
            raise HTTPException(status_code=404, detail=f"no incident with id {iid}")
    return StreamingResponse(
        _stream_arena(body.incident_ids),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
