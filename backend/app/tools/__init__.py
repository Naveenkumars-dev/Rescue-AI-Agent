"""Agent tools: eight Strands-compatible tools for the RescueFlow AI triage agent."""

from .core import (
    calculate_preliminary_risk,
    compare_incidents,
    get_incident_details,
    get_resource_status,
    identify_information_gaps,
    list_active_incidents,
    preliminary_score,
    propose_response_plan,
    save_decision_record,
)
from .registry import STRANDS_AVAILABLE, get_strands_tools

__all__ = [
    "STRANDS_AVAILABLE",
    "calculate_preliminary_risk",
    "compare_incidents",
    "get_incident_details",
    "get_resource_status",
    "get_strands_tools",
    "identify_information_gaps",
    "list_active_incidents",
    "preliminary_score",
    "propose_response_plan",
    "save_decision_record",
]
