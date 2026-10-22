"""RescueFlow AI demo server — chat UI + all required REST API endpoints.

    ./kit demo            # http://localhost:8501  (the original chat+decision UI)
    ./kit demo-bg         # background mode

All 12 API endpoints from the spec are implemented here so the frontend can call them
without needing a separate FastAPI process.

    GET  /health
    GET  /api/incidents                         list seeded incidents
    POST /api/incidents                         add a new incident
    GET  /api/incidents/{id}                    get one incident
    POST /api/incidents/{id}/evaluate           evaluate via the agent chat
    POST /api/incidents/{id}/reassess           reassess with new context
    GET  /api/decisions                         list all decision records
    GET  /api/decisions/{id}                    get one decision record
    POST /api/decisions/evaluate                Decision Arena: compare multiple incidents
    POST /api/decisions/{id}/approve            mark as APPROVED
    POST /api/decisions/{id}/reject             mark as REJECTED
    GET  /api/dashboard/summary                 overview stats
    POST /api/demo/reset                        reset demo data + agent sessions
    GET  /api/info                              agent + model metadata
    POST /api/chat                              raw chat turn (used by both UIs)
    POST /api/reset                             alias for /api/demo/reset
"""

from __future__ import annotations

import json
import os
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from decider_kit.config import load_dotenv

load_dotenv()

STATIC = Path(__file__).parent / "static"
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

app = FastAPI(title="RescueFlow AI", version="1.0.0")

# ── In-memory stores (reset on demo reset) ───────────────────────────────────

def _load_seed_incidents() -> list[dict[str, Any]]:
    p = Path(__file__).parent.parent / "agent" / "data" / "incidents.json"
    return json.loads(p.read_text()) if p.exists() else []

def _load_seed_resources() -> list[dict[str, Any]]:
    p = Path(__file__).parent.parent / "agent" / "data" / "resources.json"
    return json.loads(p.read_text()) if p.exists() else []

_INCIDENTS: list[dict[str, Any]] = _load_seed_incidents()
_DECISIONS: list[dict[str, Any]] = []
_agent: Any = None  # module-level agent object; kit tests patch this name directly


def _get_agent() -> Any:
    """Return the agent, initialising it on first call."""
    global _agent
    if _agent is None or not callable(getattr(_agent, "chat", None)):
        if os.environ.get("DEMO_TARGET") == "agentcore":
            _agent = _AgentCoreClient(os.environ["AGENTCORE_ARN"])
        else:
            from agent.agent import HackathonAgent
            _agent = HackathonAgent()
    return _agent
def _reset_stores() -> None:
    global _INCIDENTS, _DECISIONS, _agent
    _INCIDENTS = _load_seed_incidents()
    _DECISIONS = []
    _agent = None
    try:
        from agent.tools import DECISIONS as TOOL_DECISIONS, clear_turn_context
        TOOL_DECISIONS.clear()
        clear_turn_context()
    except Exception:
        pass


# ── Pydantic models ───────────────────────────────────────────────────────────

class ChatTurn(BaseModel):
    message: str
    session_id: str = "demo"
    images: list[str] = []


class NewIncident(BaseModel):
    type: str = "unknown"
    location: str = "unknown"
    report: str
    affected_people: str = "unknown"
    affected_people_num: int = 0
    hazards: str = "unknown"
    time_sensitivity: int = 3
    severity: int = 3
    hazard_level: int = 3
    status: str = "active"
    report_time: str = ""


class EvaluateRequest(BaseModel):
    context: str = ""


class ReassessRequest(BaseModel):
    update: str


class ArenaRequest(BaseModel):
    incident_ids: list[str]
    context: str = ""


class ApproveRequest(BaseModel):
    pass


class RejectRequest(BaseModel):
    reason: str = ""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_incident(incident_id: str) -> dict[str, Any]:
    iid = incident_id.strip().upper()
    inc = next((i for i in _INCIDENTS if i["id"].upper() == iid), None)
    if not inc:
        raise HTTPException(status_code=404, detail=f"incident {incident_id} not found")
    return inc


def _find_decision(decision_id: str) -> dict[str, Any]:
    dec = next((d for d in _DECISIONS if d.get("id") == decision_id), None)
    if not dec:
        raise HTTPException(status_code=404, detail=f"decision {decision_id} not found")
    return dec


def _record_decision(chat_result: dict[str, Any], incident_id: str) -> dict[str, Any]:
    triage = chat_result.get("decisions", [])
    verdict = triage[0].get("verdict", "review") if triage else "review"
    priority_map = {"critical": "CRITICAL", "high": "HIGH", "medium": "MEDIUM",
                    "low": "LOW", "needs_review": "NEEDS_REVIEW"}
    pri_raw = (triage[0].get("priority", "medium") if triage else "medium").lower()
    priority = priority_map.get(pri_raw, "NEEDS_REVIEW")
    dec = {
        "id": f"DEC-{uuid.uuid4().hex[:6].upper()}",
        "incident_id": incident_id.upper(),
        "priority": priority,
        "recommended_action": chat_result.get("reply", "")[:300],
        "reason_summary": chat_result.get("reply", "")[:200],
        "factors_considered": [],
        "evidence": [],
        "missing_information": [],
        "resource_recommendations": [],
        "alternatives_considered": [],
        "confidence": round(triage[0].get("life_safety_p_yes", 0.5) if triage else 0.5, 3),
        "human_review_required": verdict in ("review", "block"),
        "decision_status": "PROPOSED",
        "triage_verdict": verdict,
        "triage_reason": triage[0].get("reason", "") if triage else "",
        "tools_called": [t.get("stage", "") for t in triage],
        "decider_ms": triage[0].get("decider_ms", 0) if triage else 0,
        "latency_ms": chat_result.get("latency_ms", 0),
        "created_at": time.strftime("%Y-%m-%d %H:%M"),
    }
    _DECISIONS.append(dec)
    return dec


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "agent": "RescueFlow AI", "version": "1.0.0"}


# ── Info ──────────────────────────────────────────────────────────────────────

@app.get("/api/info")
def info() -> dict[str, Any]:
    from decider_kit.config import settings
    from decider_kit.llm import describe
    s = settings()
    name = "RescueFlow AI"
    try:
        from agent import agent as mod
        name = getattr(mod, "NAME", name)
    except Exception:
        pass
    return {"agent": name, "llm": describe(), "bedrock_model": s.bedrock_model,
            "decider": s.decider_mode, "target": os.environ.get("DEMO_TARGET", "local")}


# ── Incidents ─────────────────────────────────────────────────────────────────

@app.get("/api/incidents")
def list_incidents() -> list[dict[str, Any]]:
    return _INCIDENTS


@app.post("/api/incidents", status_code=201)
def create_incident(body: NewIncident) -> dict[str, Any]:
    new_id = f"INC-{str(len(_INCIDENTS) + 1).zfill(3)}"
    inc = {
        "id": new_id, "type": body.type, "location": body.location,
        "affected_people": body.affected_people,
        "affected_people_num": body.affected_people_num,
        "hazards": body.hazards, "time_sensitivity": body.time_sensitivity,
        "severity": body.severity, "hazard_level": body.hazard_level,
        "report_time": body.report_time or time.strftime("%Y-%m-%d %H:%M"),
        "status": body.status, "report": body.report,
    }
    _INCIDENTS.append(inc)
    return inc


@app.get("/api/incidents/{incident_id}")
def get_incident(incident_id: str) -> dict[str, Any]:
    return _find_incident(incident_id)


@app.post("/api/incidents/{incident_id}/evaluate")
def evaluate_incident(incident_id: str, body: EvaluateRequest) -> dict[str, Any]:
    inc = _find_incident(incident_id)
    try:
        result = _get_agent().direct_evaluate(incident_id, context_update=body.context or "")
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        dec = _record_decision(result, incident_id)
        return {"incident": inc, "decision": dec, "reply": result.get("reply", ""),
                "model_decisions": result.get("decisions", [])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Agent unavailable: {e}")


@app.post("/api/incidents/{incident_id}/reassess")
def reassess_incident(incident_id: str, body: ReassessRequest) -> dict[str, Any]:
    inc = _find_incident(incident_id)
    try:
        result = _get_agent().direct_evaluate(incident_id, context_update=body.update)
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        dec = _record_decision(result, incident_id)
        return {"incident": inc, "decision": dec, "reply": result.get("reply", ""),
                "model_decisions": result.get("decisions", [])}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Agent unavailable: {e}")


# ── Decisions ─────────────────────────────────────────────────────────────────

@app.get("/api/decisions")
def list_decisions() -> list[dict[str, Any]]:
    return _DECISIONS


@app.get("/api/decisions/{decision_id}")
def get_decision(decision_id: str) -> dict[str, Any]:
    return _find_decision(decision_id)


@app.post("/api/decisions/evaluate")
def evaluate_arena(body: ArenaRequest) -> dict[str, Any]:
    """Decision Arena: compare multiple incidents using direct Strands Decider 2B evaluation."""
    # validate all IDs exist first
    for iid in body.incident_ids:
        _find_incident(iid)
    try:
        result = _get_agent().compare_incidents(body.incident_ids, context=body.context or "")
        return {"reply": result.get("reply", ""), "decisions": result.get("decisions", []),
                "latency_ms": result.get("latency_ms", 0),
                "incidents_compared": result.get("priority_order", body.incident_ids)}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Agent unavailable: {e}")


@app.post("/api/decisions/{decision_id}/approve")
def approve_decision(decision_id: str) -> dict[str, Any]:
    dec = _find_decision(decision_id)
    dec["decision_status"] = "APPROVED"
    return dec


@app.post("/api/decisions/{decision_id}/reject")
def reject_decision(decision_id: str, body: RejectRequest) -> dict[str, Any]:
    dec = _find_decision(decision_id)
    dec["decision_status"] = "REJECTED"
    if body.reason:
        dec["rejection_reason"] = body.reason
    return dec


# ── Dashboard summary ─────────────────────────────────────────────────────────

@app.get("/api/dashboard/summary")
def dashboard_summary() -> dict[str, Any]:
    resources = _load_seed_resources()
    active = [i for i in _INCIDENTS if i.get("status") == "active"]
    return {
        "total_active": len(active),
        "critical_count": sum(1 for i in active if i.get("severity", 0) >= 5),
        "high_count": sum(1 for i in active if i.get("severity", 0) == 4),
        "pending_review": sum(1 for d in _DECISIONS if d.get("decision_status") == "PROPOSED"),
        "available_resources": sum(r["count"] for r in resources if r["status"] == "available"),
        "incidents": _INCIDENTS,
        "decisions": _DECISIONS[-20:],
        "resources": resources,
    }


# ── Demo reset ────────────────────────────────────────────────────────────────

@app.post("/api/demo/reset")
@app.post("/api/reset")
def reset_demo() -> dict[str, Any]:
    _reset_stores()
    return {"ok": True, "message": "Demo data reset to seed incidents; agent sessions cleared."}


# ── Chat (used by both kit UI and React dashboard) ────────────────────────────

@app.post("/api/chat")
def chat(t: ChatTurn) -> JSONResponse:
    try:
        a = _agent if callable(getattr(_agent, "chat", None)) else _get_agent()
        if t.images:
            import inspect
            if "images" not in inspect.signature(a.chat).parameters:
                return JSONResponse({"error": "agent does not accept images"}, status_code=400)
            return JSONResponse(a.chat(t.message, t.session_id, images=t.images))
        return JSONResponse(a.chat(t.message, t.session_id))
    except Exception as e:
        return JSONResponse({"error": f"{type(e).__name__}: {e}"}, status_code=500)

# ── Static files: React build > kit demo UI ───────────────────────────────────

if FRONTEND_DIST.exists():
    # Serve built React app
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/")
    def react_root() -> FileResponse:
        return FileResponse(FRONTEND_DIST / "index.html")

    # Catch-all for React Router (if needed)
    @app.get("/{full_path:path}")
    def react_spa(full_path: str) -> FileResponse:
        # API paths are handled above
        if full_path.startswith("api/") or full_path == "health":
            raise HTTPException(status_code=404)
        idx = FRONTEND_DIST / "index.html"
        return FileResponse(idx)
else:
    # Fall back to kit's original single-page chat UI
    @app.get("/")
    def kit_ui() -> FileResponse:
        return FileResponse(STATIC / "index.html")


# ── AgentCore client (unchanged from kit) ─────────────────────────────────────

class _AgentCoreClient:
    def __init__(self, arn: str):
        import boto3
        self.arn = arn
        self.client = boto3.client("bedrock-agentcore",
                                   region_name=os.environ.get("AWS_REGION", "us-east-1"))
        self.sessions: dict[str, str] = {}

    def chat(self, message: str, session_id: str = "demo",
             images: list[str] | None = None) -> dict[str, Any]:
        sid = self.sessions.setdefault(session_id, f"demo-{session_id}-{uuid.uuid4().hex}")
        payload: dict[str, Any] = {"prompt": message}
        if images:
            payload["images"] = images
        r = self.client.invoke_agent_runtime(
            agentRuntimeArn=self.arn, runtimeSessionId=sid,
            payload=json.dumps(payload).encode())
        body = r["response"].read() if hasattr(r["response"], "read") else r["response"]
        out = json.loads(body)
        out["served_by"] = "Amazon Bedrock AgentCore Runtime"
        return out
