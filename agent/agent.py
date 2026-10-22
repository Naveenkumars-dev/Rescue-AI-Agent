"""RescueFlow AI: Strands Decider 2B makes the triage decision; an LLM handles conversation.

Two evaluation paths:
- direct_evaluate(incident_id):  fast path - reads seeded data directly, no LLM tool calls.
  Strands Decider 2B gets the full state and produces the verdict in one forward pass (~2s).
  Used by the dashboard "Evaluate" button and the Decision Arena.
- chat(message):  conversation path - LLM gathers facts via tools, then Decider classifies.
  Slower because it depends on the LLM model quality.

    from agent.agent import HackathonAgent
    out = HackathonAgent().direct_evaluate("INC-001")
    out["reply"], out["decisions"]   # decisions has the Strands Decider 2B verdict
"""

from __future__ import annotations

import time
from typing import Any

from strands import Agent

from decider_kit import Decider
from decider_kit.llm import agent_model, default_model_id, image_blocks, strip_thinking

from .decision import TriagePolicy, build_state
from .tools import (
    INCIDENTS, RESOURCES, TOOLS, TURN_CONTEXT, clear_turn_context, preliminary_score,
)

NAME = "RescueFlow AI — emergency-response triage"

SYSTEM_PROMPT = """You are RescueFlow AI, an emergency-response triage assistant (PROTOTYPE — no real dispatch).

For each message:
1. If it mentions an incident ID (INC-001 etc), call get_incident_details then calculate_preliminary_risk.
2. Otherwise extract the incident type, call calculate_preliminary_risk with your best estimate of severity/time_sensitivity/affected_people/hazard_level (each 1-5).
3. Call get_resource_status with the incident type.
4. Reply in one short paragraph: priority, recommended action, key resources. Never invent facts."""


class HackathonAgent:
    """Triage agent: Strands Decider 2B classifies every incident; LLM handles conversation."""

    def __init__(self, decider: Decider | None = None, model_id: str | None = None,
                 eager: bool | None = None):
        import os
        self.decider = decider or Decider()
        self.eager = eager if eager is not None else os.environ.get("DEMO_EAGER") == "1"
        self.model_id = model_id or default_model_id()
        self.sessions: dict[str, tuple[Agent, TriagePolicy]] = {}

    # ── Direct evaluation path (fast, no LLM tool-calls) ─────────────────────

    def direct_evaluate(self, incident_id: str,
                        context_update: str = "") -> dict[str, Any]:
        """Evaluate a seeded incident directly using its stored facts + Strands Decider 2B.

        This is the reliable demo path: facts come from agent/data/incidents.json, the
        preliminary score is computed in code, and one Strands Decider 2B call produces
        the triage verdict. No slow LLM tool-calling round-trips.
        """
        iid = incident_id.strip().upper()
        inc = next((i for i in INCIDENTS if i["id"].upper() == iid), None)
        if not inc:
            return {"error": f"incident {incident_id} not found", "decisions": [],
                    "reply": f"No registered incident {incident_id}.", "model_id": self.model_id,
                    "latency_ms": 0, "agent": NAME, "eager": self.eager}

        t0 = time.perf_counter()

        # Compute preliminary score in code (arithmetic, not the model's job)
        score = preliminary_score(inc["severity"], inc["time_sensitivity"],
                                   inc["affected_people_num"], inc["hazard_level"])

        # Match resources
        itype = inc["type"].lower()
        suited = [r for r in RESOURCES
                  if any(itype in s.lower() or s.lower() in itype for s in r["suited_for"])]
        avail = [r for r in suited if r["status"] == "available"]
        res_summary = (", ".join(f"{r['name']} x{r['count']}" for r in avail)
                       or "no matching available resources")

        # Other active incidents for comparison
        others = [{"id": i["id"], "type": i["type"], "location": i["location"],
                   "preliminary_score": preliminary_score(i["severity"], i["time_sensitivity"],
                                                          i["affected_people_num"], i["hazard_level"])}
                  for i in INCIDENTS if i.get("status") == "active" and i["id"] != iid]

        # Build facts dict
        facts: dict[str, Any] = {
            "type": inc["type"], "location": inc["location"],
            "affected_people": inc["affected_people"], "hazards": inc["hazards"],
            "time_sensitivity": inc["time_sensitivity"], "preliminary_score": score,
            "resources": res_summary,
        }
        if context_update:
            facts["update"] = context_update

        # Build the state Strands Decider 2B reads
        report = f"{context_update}\nOriginal: {inc['report']}" if context_update else inc["report"]
        state = build_state(report, facts, others,
                            "Draft recommendation to be shown pending triage approval.")

        # One forward pass through Strands Decider 2B
        policy = TriagePolicy(self.decider)
        verdict = policy.check(state)

        reply = self._compose_direct(inc, score, res_summary, verdict, context_update)
        latency_ms = round((time.perf_counter() - t0) * 1000)

        return {"reply": reply, "decisions": policy.log,
                "model_id": f"direct+{self.model_id}", "latency_ms": latency_ms,
                "agent": NAME, "eager": self.eager,
                "incident": inc, "preliminary_score": score,
                "resources": res_summary}

    def _compose_direct(self, inc: dict, score: int, resources: str,
                        verdict: Any, update: str = "") -> str:
        priority_labels = {
            "critical": "🔴 CRITICAL", "high": "🟠 HIGH",
            "medium": "🟡 MEDIUM", "low": "🟢 LOW",
        }
        pri = priority_labels.get(verdict.priority, verdict.priority.upper())
        action_labels = {
            "recommend_response_plan": "Recommend response plan",
            "request_missing_information": "Gather more information",
            "monitor": "Monitor — no immediate action needed",
            "escalate_to_human": "Escalate to human coordinator",
        }
        action = action_labels.get(verdict.next_action, verdict.next_action)
        verdict_head = {
            "allow": "✅ Proposed response (awaiting human approval)",
            "review": "⚠️  Held for human review",
            "block": "🚨 ESCALATE — life-safety incident",
        }[verdict.action]

        lines = [verdict_head, ""]
        if update:
            lines += [f"Updated condition: {update}", ""]
        lines += [
            f"Incident: {inc['id']} — {inc['type'].title()} at {inc['location']}",
            f"Report: {inc['report']}",
            "",
            f"Priority: {pri}",
            f"Preliminary risk score: {score}/100 (arithmetic — severity/time/people/hazard)",
            f"Recommended action: {action}",
            f"Available resources: {resources}",
            "",
            f"Triage decision ({verdict.action}): {verdict.reason}",
        ]
        return "\n".join(lines)

    # ── Compare multiple incidents (Decision Arena) ───────────────────────────

    def compare_incidents(self, incident_ids: list[str],
                          context: str = "") -> dict[str, Any]:
        """Evaluate multiple incidents and recommend a priority order.

        Each incident goes through direct_evaluate (one Decider call each). The results are
        ranked and a combined explanation is produced without any LLM call.
        """
        t0 = time.perf_counter()
        results = []
        for iid in incident_ids:
            r = self.direct_evaluate(iid, context if context else "")
            if "error" not in r:
                results.append(r)

        if not results:
            return {"error": "no valid incidents", "decisions": [], "reply": "No valid incidents found.",
                    "model_id": self.model_id, "latency_ms": 0, "agent": NAME, "eager": self.eager}

        # Rank: block > review > allow, then by preliminary_score desc
        order_map = {"block": 0, "review": 1, "allow": 2}
        pri_map = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        ranked = sorted(results, key=lambda r: (
            order_map.get(r["decisions"][0]["verdict"] if r["decisions"] else "allow", 2),
            pri_map.get(r["decisions"][0]["priority"] if r["decisions"] else "low", 3),
            -r.get("preliminary_score", 0),
        ))

        lines = ["Decision Arena — Priority Order\n"]
        all_decisions = []
        for pos, r in enumerate(ranked, 1):
            inc = r["incident"]
            dec = r["decisions"][0] if r["decisions"] else {}
            verdict = dec.get("verdict", "?")
            pri = dec.get("priority", "?")
            score = r.get("preliminary_score", "?")
            v_icon = {"block": "🚨", "review": "⚠️ ", "allow": "✅"}.get(verdict, "·")
            lines.append(f"{pos}. {v_icon} {inc['id']} — {inc['type'].title()} at {inc['location']}")
            lines.append(f"   Priority: {pri.upper()}  |  Score: {score}/100  |  Verdict: {verdict.upper()}")
            lines.append(f"   {dec.get('reason','')}")
            lines.append("")
            all_decisions.extend(r["decisions"])

        if context:
            lines.append(f"Context applied: {context}")
            lines.append("")

        lines.append("Trade-offs: higher-scored incidents consume more resources but may have uncertain details.")
        lines.append("What could change this: confirmed trapped persons, resource depletion, or new hazard reports.")

        return {
            "reply": "\n".join(lines),
            "decisions": all_decisions,
            "model_id": f"direct+{self.model_id}",
            "latency_ms": round((time.perf_counter() - t0) * 1000),
            "agent": NAME, "eager": self.eager,
            "priority_order": [r["incident"]["id"] for r in ranked],
        }

    # ── Conversation path (LLM + tools, slower) ───────────────────────────────

    def _session(self, session_id: str) -> tuple[Agent, TriagePolicy]:
        if session_id not in self.sessions:
            policy = TriagePolicy(self.decider)
            strands_agent = Agent(model=agent_model(self.model_id),
                                  system_prompt=SYSTEM_PROMPT, tools=TOOLS,
                                  callback_handler=None)
            self.sessions[session_id] = (strands_agent, policy)
        return self.sessions[session_id]

    def chat(self, message: str, session_id: str = "default",
             images: list[Any] | None = None) -> dict[str, Any]:
        """LLM-driven conversation with tool use. Falls back to direct_evaluate when the
        message references a single known incident ID and the LLM is slow/unavailable."""
        import re

        # Fast path: if message contains exactly one known INC-xxx, use direct_evaluate
        ids_in_msg = re.findall(r'INC-\d+', message.upper())
        if len(ids_in_msg) == 1:
            known = {i["id"].upper() for i in INCIDENTS}
            if ids_in_msg[0] in known:
                return self.direct_evaluate(ids_in_msg[0])

        # Multi-incident comparison
        if len(ids_in_msg) >= 2:
            known = {i["id"].upper() for i in INCIDENTS}
            valid = [iid for iid in ids_in_msg if iid in known]
            if len(valid) >= 2:
                return self.compare_incidents(valid)

        # Full LLM path
        strands_agent, policy = self._session(session_id)
        clear_turn_context()
        before = len(policy.log)
        t0 = time.perf_counter()
        try:
            result = strands_agent(
                [*image_blocks(images), {"text": message}] if images else message,
                invocation_state={"images": list(images or [])})
            draft = strip_thinking(str(result))
        except Exception as e:
            draft = f"(LLM error: {e})"

        facts = self._facts_from_context()
        others = self._others_list()
        state = build_state(message, facts, others, draft)
        verdict = policy.check(state, images=list(images or []))
        reply = self._compose_chat(draft, verdict)

        return {"reply": reply, "decisions": policy.log[before:],
                "model_id": self.model_id,
                "latency_ms": round((time.perf_counter() - t0) * 1000),
                "agent": NAME, "eager": self.eager}

    def _facts_from_context(self) -> dict[str, Any]:
        facts: dict[str, Any] = {
            "type": "unknown", "location": "unknown", "affected_people": "unknown",
            "hazards": "unknown", "time_sensitivity": "unknown",
            "preliminary_score": "unknown", "resources": "unknown",
        }
        for rec in TURN_CONTEXT:
            stage = rec.get("stage", "")
            if stage == "get_incident_details" and rec.get("incident"):
                i = rec["incident"]
                facts.update(type=i.get("type", "?"), location=i.get("location", "?"),
                             affected_people=i.get("affected_people", "?"),
                             hazards=i.get("hazards", "?"),
                             time_sensitivity=i.get("time_sensitivity", "?"))
            elif stage in ("estimate_response_priority", "calculate_preliminary_risk"):
                facts["preliminary_score"] = rec.get("preliminary_score")
            elif stage in ("check_resource_availability", "get_resource_status"):
                facts["resources"] = rec.get("resources_summary", "checked")
            elif stage == "request_missing_information":
                facts["missing"] = rec.get("missing_fields", [])
        return facts

    def _others_list(self) -> list[dict[str, Any]]:
        return [{"id": i["id"], "type": i["type"], "location": i["location"],
                 "preliminary_score": preliminary_score(i["severity"], i["time_sensitivity"],
                                                        i["affected_people_num"], i["hazard_level"])}
                for i in INCIDENTS if i.get("status") == "active"]

    def _compose_chat(self, draft: str, verdict: Any) -> str:
        head = {"allow": "✅ Proposed response (awaiting human approval):",
                "review": "⚠️  Held for human review:",
                "block": "🚨 ESCALATE — life-safety incident:"}[verdict.action]
        note = f"\n\n— Triage decision ({verdict.action}): {verdict.reason}"
        return f"{head}\n\n{draft.strip() or '(no draft)'}{note}"


if __name__ == "__main__":
    import json, sys
    a = HackathonAgent()
    for msg in sys.argv[1:] or ["INC-001", "INC-002", "INC-003"]:
        print(json.dumps(a.direct_evaluate(msg) if msg.startswith("INC-") else a.chat(msg),
                         indent=1, default=str))
