"""Core tool logic: deterministic, auditable, and used by the agent in both live and demo mode.

Each function operates on the shared in-memory ``store`` and appends an entry to the supplied
``tool_log`` so the UI can show the tools *actually* called during a decision (never fabricated).

The arithmetic (the preliminary risk score, incident ranking) is computed here in code and placed
in the state Strands Decider 2B reads; the decider reads language and makes the judgement, it does
not do arithmetic.
"""

from __future__ import annotations

import time
from typing import Any

from app.storage.store import store

# Required response protocol weights (tunable here; documented in the decision pattern).
SEVERITY_WEIGHT = 30
TIME_WEIGHT = 25
PEOPLE_WEIGHT = 20
HAZARD_WEIGHT = 25


def _log(tool_log: list[dict[str, Any]] | None, name: str, arguments: dict[str, Any],
         result: dict[str, Any], latency_ms: int = 0) -> dict[str, Any]:
    entry = {"name": name, "arguments": arguments, "result": result, "latency_ms": latency_ms}
    if tool_log is not None:
        tool_log.append(entry)
    return entry


def preliminary_score(severity: int, time_sensitivity: int, affected_people: int, hazard_level: int) -> int:
    """Transparent 0-100 preliminary priority score.

    This is arithmetic, not the decider's judgement: severity (1-5), time sensitivity (1-5),
    affected people count, hazard level (1-5). Weights: 30% severity, 25% time, 20% people, 25% hazard.
    It supports the decision; it does not dictate it.
    """
    s = max(1, min(5, int(severity))) / 5.0
    t = max(1, min(5, int(time_sensitivity))) / 5.0
    a = min(1.0, max(0, int(affected_people)) / 50.0)
    h = max(1, min(5, int(hazard_level))) / 5.0
    raw = SEVERITY_WEIGHT * s + TIME_WEIGHT * t + PEOPLE_WEIGHT * a + HAZARD_WEIGHT * h
    return int(round(min(100, max(0, raw))))


# --- tool 1 ---------------------------------------------------------------------------


def get_incident_details(incident_id: str, tool_log: list | None = None) -> dict[str, Any]:
    """Retrieve information about an incident by its id (e.g. INC-001)."""
    t0 = time.perf_counter()
    inc = store.get_incident(incident_id)
    if not inc:
        result = {"error": f"no incident with id {incident_id}"}
    else:
        inc = dict(inc)
        inc["preliminary_score"] = preliminary_score(
            inc["severity"], inc["time_sensitivity"], inc["affected_people_num"], inc["hazard_level"]
        )
        result = inc
    return _log(tool_log, "get_incident_details", {"incident_id": incident_id}, result,
                int((time.perf_counter() - t0) * 1000))["result"]


# --- tool 2 ---------------------------------------------------------------------------


def list_active_incidents(tool_log: list | None = None) -> dict[str, Any]:
    """Retrieve competing active incidents, ranked by preliminary priority score (highest first)."""
    t0 = time.perf_counter()
    ranked = sorted(
        (dict(i) for i in store.list_incidents() if i.get("status") == "active"),
        key=lambda i: preliminary_score(i["severity"], i["time_sensitivity"], i["affected_people_num"], i["hazard_level"]),
        reverse=True,
    )
    for i in ranked:
        i["preliminary_score"] = preliminary_score(
            i["severity"], i["time_sensitivity"], i["affected_people_num"], i["hazard_level"]
        )
    out = [{"id": i["id"], "type": i["type"], "location": i["location"],
            "preliminary_score": i["preliminary_score"], "affected_people": i["affected_people"],
            "status": i["status"]} for i in ranked]
    result = {"active_incidents": out, "count": len(out)}
    return _log(tool_log, "list_active_incidents", {}, result, int((time.perf_counter() - t0) * 1000))["result"]


# --- tool 3 ---------------------------------------------------------------------------


def get_resource_status(incident_type: str, tool_log: list | None = None) -> dict[str, Any]:
    """Check simulated resource availability suited to an incident type."""
    t0 = time.perf_counter()
    matching = store.get_resources_for_type(incident_type)
    available = [r for r in matching if r["status"] == "available"]
    summary = ", ".join(f"{r['name']} x{r['count']}" for r in available) or "no matching available resources"
    result = {"incident_type": incident_type, "available_resources": available,
              "matching_resources": matching, "summary": summary,
              "any_available": bool(available)}
    return _log(tool_log, "get_resource_status", {"incident_type": incident_type}, result,
                int((time.perf_counter() - t0) * 1000))["result"]


# --- tool 4 ---------------------------------------------------------------------------


def calculate_preliminary_risk(severity: int, time_sensitivity: int, affected_people: int,
                               hazard_level: int, tool_log: list | None = None) -> dict[str, Any]:
    """Calculate a transparent preliminary risk score (0-100) from configurable indicators."""
    t0 = time.perf_counter()
    score = preliminary_score(severity, time_sensitivity, affected_people, hazard_level)
    result = {
        "preliminary_score": score,
        "breakdown": {
            "severity": severity, "time_sensitivity": time_sensitivity,
            "affected_people": affected_people, "hazard_level": hazard_level,
        },
        "note": ("Transparent weighted score (30% severity, 25% time, 20% people, 25% hazard). "
                 "This supports the decision; it does not replace Strands Decider 2B's judgement."),
    }
    return _log(tool_log, "calculate_preliminary_risk",
                {"severity": severity, "time_sensitivity": time_sensitivity,
                 "affected_people": affected_people, "hazard_level": hazard_level},
                result, int((time.perf_counter() - t0) * 1000))["result"]


# --- tool 5 ---------------------------------------------------------------------------

_LIFE_SAFETY_WORDS = ("trapped", "injured", "injury", "injuries", "unconscious", "fire", "flame",
                      "smoke", "gas leak", "collapse", "collapsed", "explosion", "casualt",
                      "deaths", "drowning", "swept away", "imminent", "life-threatening")
_MISSING_HINTS = ("location", "people", "affected", "hazard", "time", "severity", "number")


def identify_information_gaps(incident_id: str | None = None, report: str | None = None,
                              tool_log: list | None = None) -> dict[str, Any]:
    """Identify missing or conflicting information for an incident."""
    t0 = time.perf_counter()
    missing: list[str] = []
    conflicts: list[str] = []
    inc = store.get_incident(incident_id) if incident_id else None
    text = report or (inc or {}).get("report", "")
    if inc:
        if inc.get("affected_people_num", 0) == 0 and "unknown" in str(inc.get("affected_people", "")).lower():
            missing.append("number of people affected (reported as unknown)")
        if inc.get("hazard_level", 1) <= 1 and str(inc.get("hazards", "none reported")).lower() in ("none reported", ""):
            missing.append("specific hazards present")
        if str(inc.get("location", "")).lower() in ("unknown", ""):
            missing.append("precise location")
    else:
        for hint in _MISSING_HINTS:
            if hint not in text.lower():
                missing.append(hint)
    # Heuristic conflict detection: severity vs reported hazards text.
    if inc:
        text_lower = text.lower()
        has_life = any(w in text_lower for w in _LIFE_SAFETY_WORDS)
        if has_life and inc.get("severity", 0) < 4:
            conflicts.append("report describes a life-safety hazard but severity is below 4")
    result = {"incident_id": incident_id, "missing_information": missing, "conflicts": conflicts,
              "has_gaps": bool(missing or conflicts)}
    return _log(tool_log, "identify_information_gaps",
                {"incident_id": incident_id, "report": (report or "")[:80]}, result,
                int((time.perf_counter() - t0) * 1000))["result"]


# --- tool 6 ---------------------------------------------------------------------------


def compare_incidents(incident_ids: list[str], tool_log: list | None = None) -> dict[str, Any]:
    """Prepare structured evidence for comparing competing incidents."""
    t0 = time.perf_counter()
    rows = []
    for iid in incident_ids:
        inc = store.get_incident(iid)
        if not inc:
            rows.append({"incident_id": iid, "error": "not found"})
            continue
        score = preliminary_score(inc["severity"], inc["time_sensitivity"],
                                  inc["affected_people_num"], inc["hazard_level"])
        res = store.get_resources_for_type(inc["type"])
        res_ok = any(r["status"] == "available" for r in res)
        gaps = identify_information_gaps(iid)["missing_information"]
        rows.append({
            "incident_id": inc["id"], "type": inc["type"], "location": inc["location"],
            "severity": inc["severity"], "time_sensitivity": inc["time_sensitivity"],
            "affected_people_num": inc["affected_people_num"], "hazard_level": inc["hazard_level"],
            "preliminary_score": score, "resources_available": res_ok,
            "missing_information": gaps,
        })
    ranked = sorted(rows, key=lambda r: r.get("preliminary_score", 0), reverse=True)
    result = {"comparison": ranked,
              "note": "Preliminary scores are a transparent input; the priority order is set by the agent."}
    return _log(tool_log, "compare_incidents", {"incident_ids": incident_ids}, result,
                int((time.perf_counter() - t0) * 1000))["result"]


# --- tool 7 ---------------------------------------------------------------------------


def propose_response_plan(incident_id: str, priority: str, actions: str, resources: str,
                          tool_log: list | None = None) -> dict[str, Any]:
    """Generate a recommended action plan (shown to a human coordinator for approval)."""
    t0 = time.perf_counter()
    plan = {
        "incident_id": incident_id, "priority": priority, "actions": actions, "resources": resources,
        "status": "PROPOSED", "human_review_required": True,
    }
    result = {"response_plan": plan}
    return _log(tool_log, "propose_response_plan",
                {"incident_id": incident_id, "priority": priority, "actions": actions, "resources": resources},
                result, int((time.perf_counter() - t0) * 1000))["result"]


# --- tool 8 ---------------------------------------------------------------------------


def save_decision_record(decision: dict[str, Any], tool_log: list | None = None) -> dict[str, Any]:
    """Persist the proposed decision and its supporting evidence."""
    t0 = time.perf_counter()
    record = store.add_decision(decision)
    store.add_activity({"event": "decision_saved", "decision_id": record["decision_id"],
                        "incident_id": decision.get("incident_id")})
    result = {"recorded": True, "decision_id": record["decision_id"],
              "decision_status": decision.get("decision_status")}
    return _log(tool_log, "save_decision_record", {"incident_id": decision.get("incident_id")}, result,
                int((time.perf_counter() - t0) * 1000))["result"]
