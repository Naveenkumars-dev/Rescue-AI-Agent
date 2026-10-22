"""The generative half of the agent, always through the Strands Agents SDK when available.

In live mode a Strands ``Agent`` (Amazon Bedrock by default) reads the tool-gathered facts and
drafts the recommendation text and the explanation. In demo mode (no Strands / no credentials) the
draft is generated from templates and clearly labelled as such. Nothing here makes the decision:
the decision is Strands Decider 2B's job (``decision.py``).
"""

from __future__ import annotations

import time
from typing import Any

from app.config import runtime_mode

DRAFT_SYSTEM = (
    "You are RescueFlow AI, a decision-support assistant for emergency-response coordinators. "
    "You triage incident reports and propose response actions. You are a PROTOTYPE: never claim to "
    "dispatch real emergency services or contact real people. Be brief and factual. Never invent "
    "incident details, resource availability, or successful actions."
)


def _template_draft(inc: dict[str, Any], risk: dict[str, Any], resources: dict[str, Any],
                    gaps: dict[str, Any], active: dict[str, Any]) -> tuple[str, list[str]]:
    """Deterministic draft used in demo mode (no live LLM). Returns (draft_text, factors)."""
    factors = [
        f"incident type: {inc.get('type')}",
        f"location: {inc.get('location')}",
        f"preliminary risk score: {risk.get('preliminary_score')}/100",
        f"severity {inc.get('severity')}/5, time sensitivity {inc.get('time_sensitivity')}/5, "
        f"hazard {inc.get('hazard_level')}/5",
        f"available resources: {resources.get('summary')}",
    ]
    if gaps.get("missing_information"):
        factors.append(f"missing: {', '.join(gaps['missing_information'])}")
    n_other = active.get("count", 0)
    if n_other:
        factors.append(f"{n_other} other active incident(s) competing for the same resources")

    lines = [
        f"[DEMO MODE - no live LLM] Draft recommendation for {inc.get('id')}: {inc.get('type')} "
        f"at {inc.get('location')}.",
        f"Preliminary risk score is {risk.get('preliminary_score')}/100.",
    ]
    if gaps.get("missing_information"):
        lines.append(f"Gather missing information before committing resources: "
                     f"{', '.join(gaps['missing_information'])}.")
    if resources.get("any_available"):
        lines.append(f"Matching resources appear available ({resources.get('summary')}); propose a "
                     "response plan for human approval.")
    else:
        lines.append("No matching resources are currently available; flag for human coordination.")
    lines.append("This is a prototype simulation: a human coordinator must approve any action.")
    return "\n".join(lines), factors


def draft_recommendation(inc: dict[str, Any], risk: dict[str, Any], resources: dict[str, Any],
                         gaps: dict[str, Any], active: dict[str, Any]) -> tuple[str, list[str], bool, int]:
    """Return (draft_text, factors, live_llm, latency_ms).

    In live mode the draft is produced by a Strands Agent on Amazon Bedrock reading the same
    tool evidence. In demo mode a template draft is returned and clearly labelled.
    """
    rm = runtime_mode()
    t0 = time.perf_counter()
    if not rm.llm_live:
        draft, factors = _template_draft(inc, risk, resources, gaps, active)
        return draft, factors, False, int((time.perf_counter() - t0) * 1000)

    try:
        from strands import Agent

        from decider_kit.llm import agent_model, strip_thinking

        context = (
            f"Incident {inc.get('id')}: {inc.get('type')} at {inc.get('location')}.\n"
            f"Report: {inc.get('report')}\n"
            f"Severity {inc.get('severity')}/5, time sensitivity {inc.get('time_sensitivity')}/5, "
            f"hazard {inc.get('hazard_level')}/5, affected people (numeric) {inc.get('affected_people_num')}.\n"
            f"Preliminary risk score (from calculate_preliminary_risk tool): {risk.get('preliminary_score')}/100.\n"
            f"Available resources: {resources.get('summary')}.\n"
            f"Missing information: {', '.join(gaps.get('missing_information', [])) or 'none'}.\n"
            f"Other active incidents competing for resources: {active.get('count', 0)}.\n\n"
            "Draft a concise response recommendation in 4-6 lines: the priority level, the actions to "
            "take, the resources to commit, and what needs human verification. Note it is a prototype."
        )
        agent = Agent(model=agent_model(rm.llm_model_id), system_prompt=DRAFT_SYSTEM,
                      callback_handler=None)
        result = agent(context)
        draft = strip_thinking(str(result))
        factors = [
            f"drafted by Strands Agent ({rm.llm_provider}: {rm.llm_model_id})",
            f"preliminary risk score: {risk.get('preliminary_score')}/100",
            f"resources: {resources.get('summary')}",
        ]
        return draft, factors, True, int((time.perf_counter() - t0) * 1000)
    except Exception as e:  # noqa: BLE001 - fall back to template, never crash the API
        draft, factors = _template_draft(inc, risk, resources, gaps, active)
        factors.append(f"live LLM failed ({type(e).__name__}); used template draft")
        return draft, factors, False, int((time.perf_counter() - t0) * 1000)


def explain_arena(ranking: list[dict[str, Any]], comparison: dict[str, Any],
                  decisions: list[dict[str, Any]]) -> tuple[str, list[str], list[str], list[str], bool]:
    """Explain the arena priority order, trade-offs, uncertainties and what could change it.

    Returns (explanation, trade_offs, uncertainties, what_could_change_it, live_llm).
    """
    rm = runtime_mode()
    order_str = ", ".join(f"{r['rank']}. {r['incident_id']} ({r['priority']})" for r in ranking)
    trade_offs = [
        "Higher-priority incidents consume limited resources first, which can delay lower-priority ones.",
        "Missing information forces a conservative (review) stance that may over- or under-rank an incident.",
    ]
    uncertainties = [
        "The number of people affected is unknown for several incidents, which changes the risk score.",
        "Resource counts are simulated; real availability may differ.",
    ]
    what_could_change = [
        "A confirmed trapped resident raises a flood incident to a life-safety (block) escalation.",
        "Loss of a key route or a resource unit can re-order the priorities.",
        "New information about affected people changes the preliminary score and the decider's priority.",
    ]

    if not rm.llm_live:
        explanation = (
            f"[DEMO MODE - no live LLM] Recommended priority order: {order_str}. The order combines the "
            "Strands Decider 2B triage priority (live) or the preliminary score (demo) with the "
            "life-safety verdict. Life-safety incidents are escalated first regardless of score."
        )
        return explanation, trade_offs, uncertainties, what_could_change, False

    try:
        from strands import Agent

        from decider_kit.llm import agent_model, strip_thinking

        lines = "\n".join(
            f"{r['rank']}. {r['incident_id']} ({r['incident_type']}, {r['location']}): "
            f"priority {r['priority']}, action {r['triage_action']}, reason: {r['reason']}"
            for r in ranking
        )
        prompt = (
            "You are RescueFlow AI. Explain the recommended priority order for these competing "
            "incidents in 4-6 lines: why this order, the trade-offs, unresolved uncertainties, and "
            "what new information could change it. Be concise and factual.\n\n"
            f"RANKING:\n{lines}\n\nCOMPARISON:\n{comparison}\n"
        )
        agent = Agent(model=agent_model(rm.llm_model_id), system_prompt=DRAFT_SYSTEM,
                      callback_handler=None)
        explanation = strip_thinking(str(agent(prompt)))
        return explanation, trade_offs, uncertainties, what_could_change, True
    except Exception:  # noqa: BLE001
        explanation = (
            f"[DEMO MODE - live LLM unavailable] Recommended priority order: {order_str}. "
            "Life-safety incidents are escalated first; the rest follow the decider's priority."
        )
        return explanation, trade_offs, uncertainties, what_could_change, False
