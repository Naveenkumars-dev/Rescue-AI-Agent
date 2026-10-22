"""RescueFlow AI tools: an emergency-response registry with a transparent, deterministic score.

Mock data (agent/data/) keeps the demo and tests working anywhere. The LLM-driven part extracts
incident facts from a report; the arithmetic (the preliminary priority score, the ranking of active
incidents) is computed here in code, and the result goes into the state Strands Decider 2B reads.
Keep a clear one-line docstring on each tool: the model reads it to decide which tool to call.

Tools (8 primary, matching the spec):
    get_incident_details        – look up one incident by id
    list_active_incidents       – all active incidents ranked by preliminary score
    get_resource_status         – simulated resource availability
    calculate_preliminary_risk  – transparent 0-100 weighted risk score
    identify_information_gaps   – flag which fields are missing or vague
    compare_incidents           – structured side-by-side comparison of two incidents
    propose_response_plan       – draft a response plan for human approval
    save_decision_record        – persist a decision + reasoning to the audit trail
"""

from __future__ import annotations

from typing import Any

from strands import tool

from decider_kit.data import load

INCIDENTS: list[dict[str, Any]] = load("incidents")   # seeded registry
RESOURCES: list[dict[str, Any]] = load("resources")

# Per-turn tool context. chat() clears this before each turn and reads it after to build the
# triage state. Module-level (like the kit example's ACTIONS list); the demo is single-user.
TURN_CONTEXT: list[dict[str, Any]] = []
DECISIONS: list[dict[str, Any]] = []  # audit trail appended to by save_decision_record


def clear_turn_context() -> None:
    TURN_CONTEXT.clear()


def _note(stage: str, payload: dict[str, Any]) -> dict[str, Any]:
    rec = {"stage": stage, **payload}
    TURN_CONTEXT.append(rec)
    return rec


def preliminary_score(severity: int, time_sensitivity: int, affected_people: int, hazard_level: int) -> int:
    """Transparent 0-100 preliminary priority score (arithmetic only, not the model's judgement).
    severity 1-5, time_sensitivity 1-5, affected_people count, hazard_level 1-5.
    Weights: 30% severity, 25% time, 20% people, 25% hazard. Tunable here."""
    s = max(1, min(5, int(severity))) / 5.0
    t = max(1, min(5, int(time_sensitivity))) / 5.0
    a = min(1.0, max(0, int(affected_people)) / 50.0)
    h = max(1, min(5, int(hazard_level))) / 5.0
    raw = 30 * s + 25 * t + 20 * a + 25 * h
    return int(round(min(100, max(0, raw))))


def _score(inc: dict[str, Any]) -> int:
    return preliminary_score(inc["severity"], inc["time_sensitivity"],
                              inc["affected_people_num"], inc["hazard_level"])


# ─── 1. Incident lookup ───────────────────────────────────────────────────────

@tool
def get_incident_details(incident_id: str) -> dict:
    """Look up a registered incident by its id (e.g. INC-001)."""
    iid = incident_id.strip().upper()
    inc = next((i for i in INCIDENTS if i["id"].upper() == iid), None)
    if not inc:
        return {"error": f"no registered incident {incident_id}"}
    _note("get_incident_details", {"incident_id": iid, "incident": inc})
    return inc


# ─── 2. Active incident list ─────────────────────────────────────────────────

@tool
def list_active_incidents() -> dict:
    """List active registered incidents, ranked by preliminary priority score (highest first), so competing incidents can be compared."""
    ranked = sorted((i for i in INCIDENTS if i.get("status") == "active"),
                    key=_score, reverse=True)
    out = [{"id": i["id"], "type": i["type"], "location": i["location"],
            "preliminary_score": _score(i), "affected_people": i["affected_people"],
            "status": i["status"]} for i in ranked]
    _note("list_active_incidents", {"count": len(out), "incidents": out})
    return {"active_incidents": out, "count": len(out)}


# ─── 3. Resource status ───────────────────────────────────────────────────────

@tool
def get_resource_status(incident_type: str) -> dict:
    """Check which simulated response resources are available and suited to this incident type."""
    itype = (incident_type or "").strip().lower()
    matching = [r for r in RESOURCES
                if any(itype in s.lower() or s.lower() in itype for s in r["suited_for"])]
    available = [r for r in matching if r["status"] == "available"]
    deployed = [r for r in matching if r["status"] == "deployed"]
    summary = (", ".join(f"{r['name']} x{r['count']}" for r in available)
               or "no matching available resources")
    _note("get_resource_status", {"incident_type": incident_type, "available": available,
                                   "deployed": deployed, "resources_summary": summary})
    return {"incident_type": incident_type, "available_resources": available,
            "deployed_resources": deployed, "summary": summary}


# ─── 4. Preliminary risk score ────────────────────────────────────────────────

@tool
def calculate_preliminary_risk(severity: int, time_sensitivity: int,
                                affected_people: int, hazard_level: int) -> dict:
    """Calculate a transparent preliminary risk score (0-100) from severity (1-5), time sensitivity (1-5), affected people count, and hazard level (1-5). This is arithmetic — the decider reads the result as a fact, not as its final decision."""
    score = preliminary_score(severity, time_sensitivity, affected_people, hazard_level)
    _note("calculate_preliminary_risk", {
        "severity": severity, "time_sensitivity": time_sensitivity,
        "affected_people": affected_people, "hazard_level": hazard_level,
        "preliminary_score": score,
    })
    return {"preliminary_score": score, "breakdown": {
        "severity": severity, "time_sensitivity": time_sensitivity,
        "affected_people": affected_people, "hazard_level": hazard_level,
        "note": ("Transparent weighted score (30% severity, 25% time, "
                 "20% people, 25% hazard). Not the model's judgement."),
    }}


# ─── 5. Information gaps ──────────────────────────────────────────────────────

@tool
def identify_information_gaps(incident_id: str, provided_fields: str) -> dict:
    """Identify which key fields are missing or vague for an incident, given what is already known. incident_id is the incident; provided_fields is a comma-separated list of fields the report already has."""
    required = ["location", "incident_type", "affected_people", "hazards", "time_sensitivity"]
    have = {f.strip().lower() for f in (provided_fields or "").split(",") if f.strip()}
    missing = [f for f in required if f not in have]
    _note("identify_information_gaps", {"incident_id": incident_id,
                                         "have": sorted(have), "missing": missing})
    return {"incident_id": incident_id, "provided": sorted(have),
            "missing": missing, "complete": len(missing) == 0}


# ─── 6. Compare incidents ─────────────────────────────────────────────────────

@tool
def compare_incidents(incident_id_a: str, incident_id_b: str) -> dict:
    """Prepare a structured side-by-side comparison of two incidents (preliminary scores, hazards, resources) to support the triage decision."""
    def _lookup(iid: str) -> dict | None:
        return next((i for i in INCIDENTS
                     if i["id"].upper() == iid.strip().upper()), None)

    a = _lookup(incident_id_a)
    b = _lookup(incident_id_b)
    if not a:
        return {"error": f"no registered incident {incident_id_a}"}
    if not b:
        return {"error": f"no registered incident {incident_id_b}"}

    score_a, score_b = _score(a), _score(b)
    comparison = {
        "incident_a": {"id": a["id"], "type": a["type"], "location": a["location"],
                       "affected_people": a["affected_people"], "hazards": a["hazards"],
                       "preliminary_score": score_a},
        "incident_b": {"id": b["id"], "type": b["type"], "location": b["location"],
                       "affected_people": b["affected_people"], "hazards": b["hazards"],
                       "preliminary_score": score_b},
        "higher_score": a["id"] if score_a >= score_b else b["id"],
        "score_difference": abs(score_a - score_b),
        "note": ("preliminary_score is arithmetic (not the model's judgement). "
                 "The model weighs all evidence."),
    }
    _note("compare_incidents", comparison)
    return comparison


# ─── 7. Response plan ─────────────────────────────────────────────────────────

@tool
def propose_response_plan(incident_id: str, priority: str, actions: str,
                          resources: str, alternatives: str = "",
                          uncertainties: str = "") -> dict:
    """Propose a response plan for human approval: the incident, its priority, the actions to take, the resources to commit, alternatives considered, and known uncertainties."""
    plan = {
        "incident_id": incident_id, "priority": priority,
        "actions": actions, "resources": resources,
        "alternatives_considered": [a.strip() for a in (alternatives or "").split(";")
                                    if a.strip()],
        "known_uncertainties": [u.strip() for u in (uncertainties or "").split(";")
                                if u.strip()],
        "status": "PROPOSED", "human_review_required": True,
    }
    _note("propose_response_plan", plan)
    return plan


# ─── 8. Decision record ───────────────────────────────────────────────────────

@tool
def save_decision_record(incident_id: str, decision: str, reason: str,
                         factors: str, status: str,
                         confidence_note: str = "") -> dict:
    """Persist a decision and its supporting evidence to the audit trail. factors is a semicolon-separated list of factors considered. status: PROPOSED, APPROVED, REJECTED, or NEEDS_MORE_INFORMATION."""
    rec = {
        "incident_id": incident_id, "decision": decision, "reason": reason,
        "status": status,
        "factors_considered": [f.strip() for f in (factors or "").split(";") if f.strip()],
        "confidence_note": (confidence_note
                            or "confidence is indicative, not a calibrated probability"),
    }
    DECISIONS.append(rec)
    _note("save_decision_record", rec)
    return {"recorded": True, "decision": rec}


# ─── Backward-compatible aliases (system prompt + older eval cases use these) ─

@tool
def estimate_response_priority(severity: int, time_sensitivity: int,
                                affected_people: int, hazard_level: int) -> dict:
    """Compute a transparent preliminary priority score (0-100) — alias for calculate_preliminary_risk."""
    score = preliminary_score(severity, time_sensitivity, affected_people, hazard_level)
    _note("estimate_response_priority", {
        "severity": severity, "time_sensitivity": time_sensitivity,
        "affected_people": affected_people, "hazard_level": hazard_level,
        "preliminary_score": score,
    })
    return {"preliminary_score": score, "breakdown": {
        "severity": severity, "time_sensitivity": time_sensitivity,
        "affected_people": affected_people, "hazard_level": hazard_level,
        "note": "Transparent weighted score. Not the model's judgement.",
    }}


@tool
def check_resource_availability(incident_type: str) -> dict:
    """Check which simulated response resources are available — alias for get_resource_status."""
    itype = (incident_type or "").strip().lower()
    matching = [r for r in RESOURCES
                if any(itype in s.lower() or s.lower() in itype for s in r["suited_for"])]
    available = [r for r in matching if r["status"] == "available"]
    summary = (", ".join(f"{r['name']} x{r['count']}" for r in available)
               or "no matching available resources")
    _note("check_resource_availability", {"incident_type": incident_type,
                                           "available": available,
                                           "resources_summary": summary})
    return {"incident_type": incident_type, "available_resources": available, "summary": summary}


@tool
def request_missing_information(missing_fields: str) -> dict:
    """Record which information is still missing before a recommendation — alias for identify_information_gaps."""
    fields = [f.strip() for f in (missing_fields or "").split(",") if f.strip()]
    _note("request_missing_information", {"missing_fields": fields})
    return {"missing_information": fields}


@tool
def recommend_response_plan(incident_id: str, priority: str, actions: str,
                            resources: str) -> dict:
    """Propose a response plan for human approval — alias for propose_response_plan."""
    plan = {
        "incident_id": incident_id, "priority": priority, "actions": actions,
        "resources": resources, "status": "PROPOSED", "human_review_required": True,
    }
    _note("recommend_response_plan", plan)
    return plan


@tool
def record_decision(incident_id: str, decision: str, reason: str, status: str) -> dict:
    """Save a decision to the audit trail — alias for save_decision_record."""
    rec = {"incident_id": incident_id, "decision": decision,
           "reason": reason, "status": status}
    DECISIONS.append(rec)
    _note("record_decision", rec)
    return {"recorded": True, "decision": rec}


TOOLS = [
    # 8 primary tools (matching spec)
    get_incident_details,
    list_active_incidents,
    get_resource_status,
    calculate_preliminary_risk,
    identify_information_gaps,
    compare_incidents,
    propose_response_plan,
    save_decision_record,
    # backward-compat aliases (system prompt uses these names)
    estimate_response_priority,
    check_resource_availability,
    request_missing_information,
    recommend_response_plan,
    record_decision,
]
