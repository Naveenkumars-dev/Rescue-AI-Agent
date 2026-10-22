# RescueFlow AI — design

## Pattern tag
`#policy` — an emergency-response triage policy gate. Strands Decider 2B classifies one incident
against a written response protocol and returns allow / review / block before any recommendation
is shown. Different tag from the kit's #guardrails example (originality).

## State layout (what the decider reads, exactly as built at run time)

```
RescueFlow AI — emergency-response triage. The decider classifies one incident under the
response protocol below, before any recommendation is shown to a coordinator.

--- RESPONSE PROTOCOL ---
- Life-safety incidents (people trapped, injured, or a fast-moving danger) must be escalated to
  professional emergency services and a human coordinator. This prototype never auto-dispatches
  or auto-recommends a response for them.
- When key details are missing or vague, gather them before recommending.
- When the situation is high-stakes or borderline, a human coordinator must confirm.
- Otherwise the prototype may propose a response plan with available resources, for human approval.

--- INCIDENT REPORT ---
<report>

--- EXTRACTED FACTS (from tools) ---
incident type: ...
location: ...
affected people: ...
hazards: ...
time sensitivity: ...
preliminary priority score: ... (0 low, 100 critical; computed by the estimate_response_priority tool)
available resources: ...

--- OTHER ACTIVE INCIDENTS (for comparison) ---
- INC-002: road obstruction at Oak Lane — prelim score 30

--- DRAFT RECOMMENDATION (from the assistant, not yet shown) ---
<draft>
```

`agent/decision.py:build_state()` builds this; the eval cases use the same layout (generated from
build_state so they cannot drift).

## Typed questions and options
- `priority` (score): ["low", "medium", "high", "critical"] — triage priority of THIS incident.
- `next_action` (choice):
  - recommend_response_plan: enough is clearly known, with resources available, to propose a specific response plan
  - request_missing_information: key details are missing or vague (location, number affected, hazard) and must be gathered before recommending
  - monitor: no response action is needed yet; the incident is minor or already contained; keep watching and re-evaluate if it changes
  - escalate_to_human: the situation is high-stakes or borderline; a human emergency coordinator must decide
- `life_safety` (noul): does the report describe an immediate or probable threat to life or serious
  harm that the protocol says must be escalated and never auto-handled?

## Thresholds and actions (code in decide())
- life_safety p_yes >= 0.6 AND confident (>=0.65) → **block** (escalate; never auto-recommend).
- life_safety p_yes in [0.4, 0.6) → **review** (uncertain life-safety; human must assess).
- next_action == escalate_to_human → **review**.
- next_action == request_missing_information → **review**.
- any answer confidence < 0.65 → **review** (low-confidence fallback).
- next_action == monitor → **allow** (propose: monitor).
- else → **allow** (propose response plan for human approval).

## Seam
Post-draft, before-sent (canonical #policy seam): the Strands agent (on Amazon Bedrock) gathers
facts with its tools and drafts a recommendation; `agent/agent.py` then runs `TriagePolicy.check`
on the assembled state and composes the final reply from the verdict (block → escalation message,
review → held-for-human note, allow → draft + approval note). One decider call per turn; the
verdict record is appended to `.log` and returned in `decisions`.

## Tools (agent/tools.py, mock data)
get_incident_details, list_active_incidents (ranked by preliminary score), estimate_response_priority
(transparent weighted 0-100 score), check_resource_availability, request_missing_information,
recommend_response_plan, record_decision. Data: agent/data/incidents.json, agent/data/resources.json.
Per-turn tool results are captured in a module-level TURN_CONTEXT that chat() reads to build the state.

## Eval-case plan (26 cases, ~half tune / half test)
Covers: life_safety clear yes (fire with people inside, gas leak, multi-vehicle injuries), life_safety
clear no (road obstruction, power outage, water leak, noise), near-misses ("may be trapped", "someone
might be", live wire, overdue hiker), every next_action branch, every priority level, and cases where
other active incidents inform the action. Labelled by each question's own definition.

## AgentCore features
None (Runtime alone puts the agent on AWS). Memory/Gateway off.
