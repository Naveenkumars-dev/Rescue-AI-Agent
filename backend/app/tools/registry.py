"""Strands-compatible tool definitions.

In live mode these are handed to a Strands ``Agent`` (Amazon Bedrock) so the generative model can
call them itself. The orchestrator also calls the underlying ``app.tools.core`` functions directly
so the workflow is deterministic and every tool call is auditable regardless of the LLM.

Each tool keeps a one-line docstring the model reads to decide which tool fits a request, clear
typed parameters, and validation/error handling.
"""

from __future__ import annotations

from typing import Any

from . import core

try:
    from strands import tool as strands_tool

    STRANDS_AVAILABLE = True
except Exception:  # noqa: BLE001 - strands-agents optional; demo mode works without it
    STRANDS_AVAILABLE = False
    strands_tool = None  # type: ignore[assignment]


def _wrap(func):
    """Create a Strands @tool wrapper around a core function (preserves the docstring/schema)."""
    if not STRANDS_AVAILABLE:
        return None

    @strands_tool
    def _t(incident_id: str = "", incident_type: str = "", severity: int = 0, time_sensitivity: int = 0,
           affected_people: int = 0, hazard_level: int = 0, incident_ids: list[str] | None = None,
           report: str = "", priority: str = "", actions: str = "", resources: str = "",
           decision: dict[str, Any] | None = None) -> dict[str, Any]:  # noqa: PLR0913
        """RescueFlow tool. Selects the right core function from the arguments provided."""
        name = func.__name__
        if name == "get_incident_details":
            return core.get_incident_details(incident_id)
        if name == "list_active_incidents":
            return core.list_active_incidents()
        if name == "get_resource_status":
            return core.get_resource_status(incident_type)
        if name == "calculate_preliminary_risk":
            return core.calculate_preliminary_risk(severity, time_sensitivity, affected_people, hazard_level)
        if name == "identify_information_gaps":
            return core.identify_information_gaps(incident_id, report)
        if name == "compare_incidents":
            return core.compare_incidents(incident_ids or [])
        if name == "propose_response_plan":
            return core.propose_response_plan(incident_id, priority, actions, resources)
        if name == "save_decision_record":
            return core.save_decision_record(decision or {})
        return {"error": f"unknown tool {name}"}

    _t.__name__ = func.__name__
    _t.__doc__ = func.__doc__
    return _t


# Per-tool wrappers with proper signatures the Strands agent reads.
if STRANDS_AVAILABLE:

    @strands_tool
    def get_incident_details(incident_id: str) -> dict[str, Any]:
        """Look up a registered incident by its id (e.g. INC-001). Returns its full record."""
        return core.get_incident_details(incident_id)

    @strands_tool
    def list_active_incidents() -> dict[str, Any]:
        """List active registered incidents ranked by preliminary priority score, for comparison."""
        return core.list_active_incidents()

    @strands_tool
    def get_resource_status(incident_type: str) -> dict[str, Any]:
        """Check which simulated response resources are available and suited to an incident type."""
        return core.get_resource_status(incident_type)

    @strands_tool
    def calculate_preliminary_risk(severity: int, time_sensitivity: int, affected_people: int,
                                   hazard_level: int) -> dict[str, Any]:
        """Calculate a transparent preliminary risk score (0-100) from severity(1-5), time sensitivity(1-5), affected people count and hazard level(1-5)."""
        return core.calculate_preliminary_risk(severity, time_sensitivity, affected_people, hazard_level)

    @strands_tool
    def identify_information_gaps(incident_id: str = "", report: str = "") -> dict[str, Any]:
        """Identify missing or conflicting information for an incident, by id or from report text."""
        return core.identify_information_gaps(incident_id or None, report or None)

    @strands_tool
    def compare_incidents(incident_ids: list[str]) -> dict[str, Any]:
        """Prepare structured evidence for comparing competing incidents (pass the incident ids)."""
        return core.compare_incidents(incident_ids)

    @strands_tool
    def propose_response_plan(incident_id: str, priority: str, actions: str, resources: str) -> dict[str, Any]:
        """Propose a response plan: incident, priority, actions and resources, for human approval."""
        return core.propose_response_plan(incident_id, priority, actions, resources)

    @strands_tool
    def save_decision_record(decision: dict[str, Any]) -> dict[str, Any]:
        """Persist the proposed decision and its supporting evidence to the audit trail."""
        return core.save_decision_record(decision)

    STRANDS_TOOLS = [
        get_incident_details, list_active_incidents, get_resource_status, calculate_preliminary_risk,
        identify_information_gaps, compare_incidents, propose_response_plan, save_decision_record,
    ]
else:
    STRANDS_TOOLS = []


def get_strands_tools() -> list:
    """Return the Strands tool list for a live Agent (empty if strands is not installed)."""
    return list(STRANDS_TOOLS)


__all__ = ["STRANDS_AVAILABLE", "get_strands_tools", "STRANDS_TOOLS"]
