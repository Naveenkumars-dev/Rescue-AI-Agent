# RescueFlow AI: Building an Agentic Disaster Response Decision System with Strands Decider 2B on AWS

**Keywords:** Agentic AI, Strands Agents, Strands Decider 2B, AWS, Decision Support Systems, Disaster Management, Tool Use, Adaptive Decision-Making, Human-in-the-Loop AI

---

## Abstract

During large-scale emergencies, coordinators routinely receive multiple incident reports simultaneously—floods, road blockages, power failures—and must quickly decide which deserves attention first. Static rule engines cannot read the language of a report; general-purpose language models are too slow and too expensive to run on every incoming event.

RescueFlow AI is an agentic decision-support prototype that combines the conversational strength of Amazon Bedrock with the fast, calibrated classification of Strands Decider 2B. The agent collects incident facts through eight explicitly defined tools, assembles a structured state, and then calls Strands Decider 2B in a single forward pass to answer three typed questions: triage priority, recommended next action, and whether a life-safety threat is present. The verdict—*allow*, *review*, or *block*—is returned with probabilities the code can branch on, and every decision awaits human approval before any action is proposed.

Benchmark results from 12 held-out labelled cases show the Strands Decider 2B integration runs at a median of 295 ms versus 1,277 ms for the Amazon Nova Pro LLM baseline—a 4.3× speedup at near-zero marginal cost. When the decider answers with high confidence (≥ 0.70), its accuracy on these cases reaches 93.8%.

The system is a prototype. It uses simulated resources and fictional incidents, and it is not a replacement for official emergency-management procedures.

---

## 1. Introduction

Emergency coordinators face a compound problem: multiple incidents arrive at the same time, each report is partial, conditions change quickly, and the cost of a wrong priority can be severe. A coordinator triaging a residential flood, a blocked access road, and a commercial power outage simultaneously must weigh severity, uncertainty, resource availability, and downstream consequences—often with incomplete information and under time pressure.

Current approaches fall into two categories, both with known limitations. Manual triage depends entirely on the coordinator's experience and is hard to audit. Scripted rule systems encode fixed thresholds—"severity ≥ 4 means critical"—but cannot interpret whether a report's language implies a life-safety risk, whether missing details should delay action, or whether a lower-scored incident should be elevated because of contextual factors.

RescueFlow AI is designed to bridge this gap. It accepts free-text incident reports, gathers structured facts through tools, and hands the triage judgement to Strands Decider 2B—a 2-billion-parameter decision model that returns calibrated probabilities in one forward pass. Every recommendation requires a human coordinator to approve it before anything is proposed as a response.

---

## 2. Problem Statement

The core problem is: *how can a software system evaluate multiple competing incident reports, identify important missing information, recommend an order of attention, and update its recommendations when circumstances change—while keeping a human in control of every consequential action?*

Three technical challenges make this hard:

1. **Language-dependent judgement.** Whether a report implies a life-safety risk, or whether an action is premature, cannot be determined by arithmetic alone. A rule saying "severity ≥ 4" does not capture "residents may be trapped."

2. **Incomplete, changing information.** Field reports arrive with missing fields. The number of people affected may be unknown. A later update ("resident confirmed trapped") can change the priority entirely.

3. **Competing resources.** Recommending a plan for one incident implicitly affects what remains available for others. A useful triage system must see all active incidents, not just the one being evaluated.

---

## 3. Proposed Solution

RescueFlow AI addresses these challenges through five main capabilities, all implemented and verified:

**Implemented:**
- Free-text incident report intake via a React dashboard and REST API.
- Tool-based fact extraction: incident lookup, resource status, preliminary risk score (arithmetic), information gap identification, and cross-incident comparison.
- Strands Decider 2B triage: three typed questions answered in one forward pass, returning probabilities the code uses to produce a *block / review / allow* verdict.
- Decision Arena: multi-incident comparison with Strands Decider 2B called once per incident, results ranked automatically, and a Change Conditions interaction that triggers a real re-evaluation (not a UI rearrangement).
- Human approval controls: every PROPOSED decision can be APPROVED or REJECTED through the dashboard.
- Full audit trail: all decisions are persisted with timestamps, triage probabilities, and the reasons used.

**Planned (not yet implemented):**
- Deployment to Amazon Bedrock AgentCore Runtime (infrastructure is prepared via `./kit deploy`; AWS credentials not yet configured).
- Real authorized disaster data feeds.
- Geospatial visualisation.

---

## 4. Why Agentic AI?

A conventional chatbot accepts a message and generates a reply. It cannot interrupt its own output to look up a resource status, revise a preliminary score, and then reframe its recommendation.

A static rule engine applies deterministic conditions: if severity ≥ 4 and time_sensitivity = 5, then priority = critical. Rules are fast and auditable, but they cannot read whether a report's prose implies a life-safety situation, and they cannot adapt when a new paragraph of information arrives mid-evaluation.

An agentic AI system—built with the Strands Agents SDK—operates differently. It selects the next step from a set of explicitly defined tools, calls those tools in whatever order the evidence warrants, observes the results, and then decides whether to continue gathering information or to proceed to a recommendation. This loop continues until a stopping condition is met (or a budget is exhausted).

For RescueFlow AI, the agentic loop is short and bounded by design: the agent gathers three to four facts (incident details, risk score, resources, possibly a cross-incident comparison), assembles a state, and then calls Strands Decider 2B. The brevity is intentional: in safety-critical workflows, a predictable tool sequence is more trustworthy than an open-ended one.

---

## 5. Role of Strands Decider 2B

Strands Decider 2B is an open 2-billion-parameter decision model. Unlike a generative model, it does not write text. It reads a *state* (any text) and *typed questions* (yes/no, choice, or score), and returns calibrated probabilities in one forward pass.

### The decision context

Before calling the decider, `agent/decision.py:build_state()` assembles a structured state string containing:

- The written response protocol (four rules about escalation, information gaps, high-stakes situations, and acceptable response plans).
- The incident report in the coordinator's own words.
- Extracted facts from tools: incident type, location, affected people, hazards, time sensitivity, preliminary risk score (0–100, computed arithmetically), and available resources.
- Other active incidents and their preliminary scores, for comparison.
- A draft recommendation from the agent.

This separation is important: the arithmetic (the preliminary score, the ranking) stays in code. The decider reads language to make the judgement.

### The three typed questions

```python
QUESTIONS = {
    "priority": Decider.score(
        "How urgent is this incident for response priority?",
        ["low", "medium", "high", "critical"]
    ),
    "next_action": Decider.choice(
        "Which response action fits this incident right now?",
        {
            "recommend_response_plan": "enough is clearly known to propose a plan",
            "request_missing_information": "key details are missing or vague",
            "monitor": "no action needed yet; keep watching",
            "escalate_to_human": "the situation is high-stakes; a human must decide",
        }
    ),
    "life_safety": Decider.noul(
        "Does this incident describe an immediate or probable threat to life?",
        {"true": "an immediate or probable threat to life or serious harm",
         "false": "no imminent threat to life or serious harm"}
    ),
}
```

One call to the decider returns all three answers. The state is encoded once and the questions share it, so eight questions cost no more than three.

### The verdict

The code in `TriagePolicy.decide()` translates probabilities into actions using explicit thresholds:

| Condition | Verdict |
|---|---|
| `life_safety.p_yes ≥ 0.60` AND confident | **block** — escalate, never auto-recommend |
| `life_safety.p_yes ∈ [0.40, 0.60)` | **review** — uncertain life-safety; human must assess |
| `next_action == escalate_to_human` | **review** |
| `next_action == request_missing_information` | **review** |
| any answer confidence < 0.65 | **review** — low-confidence fallback |
| `next_action == monitor` | **allow** — propose monitoring |
| otherwise | **allow** — propose response plan for human approval |

The thresholds are ordinary `if` statements in Python. Changing them does not require retraining the model.

### Observed live results (from `submission/video/run.json`, 2026-10-22)

| Incident | Verdict | Priority | Life-safety P | Decider latency |
|---|---|---|---|---|
| INC-001 Flood — residents may be trapped | **BLOCK** | critical | 0.82 | ~7 s (hosted API) |
| INC-002 Road obstruction — no injuries | REVIEW | high | 0.19 | ~6 s |
| INC-003 Power outage — no hazard | REVIEW | medium | 0.12 | ~6 s |

After the condition change "Resident confirmed trapped on first floor" was added to INC-001, the reassessment returned `life_safety.p_yes = 0.79`, verdict `BLOCK` — the same escalation, re-confirmed with updated evidence.

---

## 6. System Architecture

```
[ React Dashboard ]  ←──────────────────────────────────────────────────────────────┐
  Vite · TypeScript                                                                  │
  Tailwind · Recharts                                                                │
        │ HTTP /api/*                                                                │
        ▼                                                                            │
[ FastAPI Demo Server — demo/server.py ]                                            │
  12 REST endpoints                                                                  │
  Pydantic validation                                                                │
        │                                                                            │
        ▼                                                                            │
[ HackathonAgent — agent/agent.py ]                                                 │
  direct_evaluate()  ·  compare_incidents()  ·  chat()                              │
        │                      │                                                     │
        ▼                      ▼                                                     │
[ 8 Agent Tools ]    [ TriagePolicy — agent/decision.py ]                           │
  seeded mock data         build_state() → TriagePolicy.check()                     │
  0-100 risk score              │                                                    │
                                ▼                                                    │
                    [ Strands Decider 2B ]                                           │
                      Hosted API (ugmdu)                                             │
                      POST /v1/decide                                                │
                      3 questions · 1 forward pass                                  │
                                                                                     │
[ Amazon Bedrock — Nova Pro ]  ─────── LLM chat path (optional fast path) ──────────┘
[ Amazon Bedrock AgentCore Runtime ] ── planned deployment via ./kit deploy
```

See `docs/architecture.mmd` for the Mermaid source.

**Services used locally (verified):** FastAPI + uvicorn, React/Vite, Ollama (llama3.2:1b for LLM during development), Strands Decider 2B via hosted ugmdu API.

**Services planned:** Amazon Bedrock Nova Pro (LLM in production), Amazon Bedrock AgentCore Runtime (agent deployment), CloudWatch (logs). Infrastructure is prepared; deployment awaits AWS account configuration.

**Storage:** In-memory for the demo (seeded from `agent/data/*.json`). Persistent storage (DynamoDB or similar) is a planned enhancement.

---

## 7. Agent Workflow

See `docs/agent_workflow.mmd` for the full sequence diagram. The abbreviated flow:

1. A coordinator submits an incident ID or free-text report.
2. `HackathonAgent.direct_evaluate()` reads the incident from seeded data.
3. Tools compute the preliminary risk score (arithmetic) and check resource availability.
4. `build_state()` assembles the state: protocol + report + facts + other active incidents + draft.
5. `TriagePolicy.check()` calls Strands Decider 2B with the state and three typed questions.
6. One forward pass returns `priority`, `next_action`, and `life_safety` probabilities.
7. `decide()` maps probabilities to *allow / review / block* using explicit thresholds.
8. The verdict and probabilities are appended to the decision log and returned to the API.
9. The API saves a `PROPOSED` decision record and returns it to the dashboard.
10. The coordinator sees the verdict, probability bars, and reason in the decision panel.
11. If conditions change, `direct_evaluate(context_update=...)` is called; Strands Decider 2B re-evaluates the updated state from scratch.

---

## 8. Decision Arena: Core Innovation

The Decision Arena lets a coordinator submit three or more incidents simultaneously. The agent calls `direct_evaluate()` for each incident independently, then ranks the results.

The ranking algorithm is deterministic in code: `block` outranks `review` outranks `allow`; within a verdict tier, incidents are sorted by preliminary score descending. But the verdict for each incident comes from Strands Decider 2B—not from a fixed priority table.

The key demonstration for judges: when the coordinator selects a Change Condition (for example, "resident confirmed trapped on first floor"), the backend calls `direct_evaluate()` again with the updated context. Strands Decider 2B reads the new state and returns updated probabilities. The decision changes because the evidence changes—not because a number in a rules table was edited.

In the live run recorded for the video submission:
- INC-001 (flood, possible trapped residents): **BLOCK / critical**, life_safety p=0.82.
- INC-002 (road obstruction, no injuries): **REVIEW / high**, life_safety p=0.19.
- INC-003 (power outage, no hazard): **REVIEW / medium**, life_safety p=0.12.
- Arena order: INC-001 → INC-002 → INC-003. Total latency: 18.8 s (three Decider calls via hosted API).

---

## 9. Agent Tools and Structured Outputs

Eight primary tools are registered with the Strands Agent via `@tool` decorators in `agent/tools.py`:

| Tool | What it does |
|---|---|
| `get_incident_details` | Looks up a registered incident by ID |
| `list_active_incidents` | Returns active incidents ranked by preliminary score |
| `get_resource_status` | Returns available and deployed resources for an incident type |
| `calculate_preliminary_risk` | Computes a transparent 0–100 score: 30% severity + 25% time + 20% people + 25% hazard |
| `identify_information_gaps` | Flags which required fields are missing from the report |
| `compare_incidents` | Produces a structured side-by-side comparison of two incidents |
| `propose_response_plan` | Drafts a response plan with alternatives and uncertainties |
| `save_decision_record` | Persists the decision, factors, and confidence note to the audit trail |

The preliminary risk score is intentionally arithmetic. It exists to give the decider a fact to read, not to replace the decider's judgement. A score of 80 from a flood report and a score of 80 from a chemical spill may warrant very different responses; the prose of the report carries that signal.

### Structured decision record (from `demo/server.py`)

Every evaluation produces a record with these fields: `id`, `incident_id`, `priority`, `recommended_action`, `reason_summary`, `factors_considered`, `evidence`, `missing_information`, `resource_recommendations`, `alternatives_considered`, `confidence`, `human_review_required`, `decision_status` (PROPOSED / APPROVED / REJECTED / NEEDS_MORE_INFORMATION), `triage_verdict`, `triage_reason`, `tools_called`, `decider_ms`, `latency_ms`, `created_at`.

All records are validated by Pydantic at the API boundary. The `confidence` field echoes `life_safety.p_yes` and is explicitly labelled in the code as "indicative, not a calibrated probability."

---

## 10. AWS Implementation and Deployment

**Current (verified) configuration:**

- **LLM:** Ollama `llama3.2:1b` running locally, accessed through the Strands `OllamaModel` provider. In production the same agent switches to Amazon Bedrock Nova Pro by setting `LLM_PROVIDER=bedrock` and `BEDROCK_MODEL_ID=us.amazon.nova-pro-v1:0` in `.env`.
- **Strands Decider 2B:** AWS User Group Madurai hosted API (`DECIDER_MODE=ugmdu`), authenticated with a Bearer token stored in `.env` (git-ignored). The model served is `strands-decider-2B-hobson-v19`, confirmed via `/v1/models`.
- **Backend:** FastAPI + uvicorn on port 8501.
- **Frontend:** React/Vite build served as static files from the same FastAPI server.
- **SSL:** `certifi` bundle, required for macOS Python.org builds.

**Planned deployment (infrastructure prepared, AWS credentials not yet configured):**

- `./kit deploy` targets Amazon Bedrock AgentCore Runtime using the kit's CDK project in `deploy/agentcore/cdk/`.
- The deployed agent always uses Amazon Bedrock for the LLM part; the decider continues to use the hosted API or can be pointed at any compatible endpoint via `DEPLOY_DECIDER_URL`.
- IAM permissions required: `bedrock:InvokeModel`, `bedrock-agentcore:CreateAgentRuntime`, `bedrock-agentcore:InvokeAgentRuntime`, `logs:CreateLogGroup`, `logs:PutLogEvents`.
- No credentials, API keys, or private URLs appear in the source code or the repository.

---

## 11. Demonstration Scenario

The following outputs are from actual live runs against the hosted Strands Decider 2B API (recorded in `submission/video/run.json` and confirmed by manual API calls).

**Incident A — Flood at Riverside (INC-001)**
> "Flood warning for the low-lying Riverside residential area. Water is rising rapidly and there are reports that some residents may be trapped."

- Preliminary score: 80/100 (severity 5, time_sensitivity 5, affected_people_num 0, hazard_level 5).
- Strands Decider 2B: `life_safety p_yes = 0.82`, `priority = critical`, `next_action = escalate_to_human`.
- Verdict: **BLOCK** — escalate to professional emergency services; prototype must not auto-recommend.

**Incident B — Road obstruction at Oak Lane (INC-002)**
> "A tree branch has fallen and is blocking one lane of Oak Lane, a secondary road. No injuries are confirmed and traffic can still pass on the other lane."

- Preliminary score: 27/100.
- Strands Decider 2B: `life_safety p_yes = 0.19`, `priority = high`, `next_action = request_missing_information`.
- Verdict: **REVIEW** — key information missing; gather before recommending.

**Incident C — Power outage at Market Square (INC-003)**
> "Power outage affecting a small commercial area around Market Square. No immediate hazard is reported; a few shops are without electricity."

- Preliminary score: 26/100.
- Strands Decider 2B: `life_safety p_yes = 0.12`, `priority = medium`, `next_action = request_missing_information`.
- Verdict: **REVIEW** — minor incident; gather outage duration before recommending.

**Reassessment after condition change:**
After introducing "Resident confirmed trapped on first floor. Water now at chest height" for INC-001, the reassessment returned `life_safety p_yes = 0.79`, verdict **BLOCK** — the same escalation, re-confirmed with updated evidence.

---

## 12. Testing and Evaluation

The test suite in `tests/` runs fully offline using a `FakeDecider` stub and Starlette's `TestClient`. All 78 tests pass.

**Coverage:**
- `test_agent_contract.py` — kit contract: `PATTERN_TAG`, `QUESTIONS`, `HackathonAgent.chat()` interface.
- `test_rescueflow_wiring.py` (12 tests) — triage logic: block on life-safety, review on low confidence, allow on clear non-life-threatening incidents, state layout, probability bar rendering, all 8 tools.
- `test_rescueflow_api.py` (28 tests) — all 12 REST endpoints: creation, evaluation, reassessment, Decision Arena, approve/reject, demo reset, safety (prompt injection in report field), chat.
- `test_bench_and_checks.py` — benchmark runner, submission checker, demo image pass-through.
- `test_patterns.py`, `test_client.py`, `test_tools.py` — kit library tests.

**Benchmark (from `submission/bench/results.md`):**

Run on 12 labelled held-out cases, comparing Strands Decider 2B (hosted API) against Amazon Nova Pro as an LLM baseline:

| Metric | Strands Decider 2B | Amazon Nova Pro |
|---|---|---|
| Accuracy (all cases) | 79.2% | 95.8% |
| Latency p50 | 295 ms | 1,277 ms |
| Latency p95 | 468 ms | 1,427 ms |
| Cost per 1,000 decisions | $0.00 (hosted API) | $0.18 |
| Confident share (≥0.70) | 67% | 100% |
| Accuracy when confident | **93.8%** | 95.8% |
| Cases sent to human | 4 of 12 | 0 of 12 |

The decider runs 4.3× faster at p50. On the cases it answers with high confidence, its accuracy (93.8%) is within 2 percentage points of Nova Pro (95.8%). The 8 low-confidence cases it defers to a human represent an honest fallback, not a failure—those are the borderline cases where human review is the right answer.

**Limitations of this benchmark:** 12 cases is a small set. Both the tune and test splits came from the same labelling session. These numbers provide directional signal but should not be treated as a production-grade evaluation.

---

## 13. Safety, Limitations, and Responsible AI

**What the system must not do:**
- Dispatch real emergency resources.
- Contact real people or real emergency services automatically.
- Present model confidence as a statistically validated probability.
- Act without a human coordinator approving a PROPOSED decision.

**Known risks:**
- *Incorrect or fabricated incident reports.* The system treats all reports as untrusted input. The agent's system prompt forbids inventing facts, but a malicious or mistaken report can produce a plausible-sounding but wrong recommendation. Human review is the essential safety layer.
- *Prompt injection.* A coordinator pasting a report that contains instructions ("ignore your rules") will have that text treated as ordinary incident content. The server is stateless per session; the system prompt cannot be overridden by user input.
- *Decider confidence misinterpretation.* `life_safety.p_yes = 0.82` does not mean "there is an 82% chance a person will die." It means the model assigned that probability to "yes" given the state text and this question wording. The interpretation requires domain expertise.
- *Model unavailability.* The hosted Strands Decider 2B API is external. If it is unreachable, the server returns HTTP 503. No silent fallback to mock decisions is implemented.
- *Small benchmark.* Twelve labelled cases do not constitute a production evaluation. The accuracy numbers above are indicative.

**This project is a prototype.** It is designed for a hackathon demonstration using fictional incidents and simulated resources. It is not a substitute for official emergency-management systems, trained dispatch protocols, or qualified emergency-response personnel.

---

## 14. Future Enhancements

- **Real data integration.** Connect to open, authorized disaster-event data sources (national emergency management APIs, weather services) under appropriate access controls.
- **Geospatial features.** Add map-based incident visualisation to show proximity of incidents and resources.
- **Resource allocation modelling.** Extend the tools to track resource commitment across incidents (committing a rescue boat to INC-001 should reduce availability for INC-005).
- **Multilingual support.** Accept incident reports in languages other than English; the Strands Decider state text is language-agnostic.
- **Offline capability.** Package the agent for edge deployment where connectivity is unreliable.
- **Calibrated confidence.** Validate the decider's probability outputs against a large labelled dataset before using them as calibrated probabilities.
- **Evaluation with domain experts.** Run the system against realistic scenarios with emergency-management professionals to measure decision quality and identify dangerous failure modes.
- **AgentCore Memory.** Use Amazon Bedrock AgentCore Memory to persist incident history across sessions, allowing the decider to factor in past decisions when evaluating recurrent incidents.

---

## 15. Conclusion

RescueFlow AI demonstrates that a meaningful decision-making role for Strands Decider 2B is achievable within the constraints of a solo hackathon. The key design choice—separating deterministic arithmetic (the preliminary risk score, the incident ranking) from language-dependent judgement (the triage verdict)—keeps the system honest: the numbers are in code, the reading is in the model.

The benchmark shows that when the decider is confident (67% of cases), it matches a full Nova Pro LLM call in accuracy while running 4.3× faster at a fraction of the cost. The remaining 33% of cases, where confidence falls below 0.70, are deferred to a human—exactly the cases where automated action would be most dangerous.

The project is a prototype. Its fictional incidents, simulated resources, and 12-case benchmark are a starting point, not a finished product. But the architecture—a short, bounded agentic loop, a classification model for the language-dependent triage judgement, explicit thresholds in code, and a human approval gate before every consequence—is a pattern that could be applied to real decision-support workflows, in emergency management and beyond.

Agentic AI that explains its reasoning, defers under uncertainty, and keeps humans in control of consequential actions is more useful than agentic AI that acts first and asks for forgiveness later.

---

## References

See `docs/references.md` for full citations.

Core sources:
1. Strands Decider repository: https://github.com/strands-labs/strands-decider
2. Strands Agents SDK: https://strandsagents.com/latest/
3. Amazon Bedrock documentation: https://docs.aws.amazon.com/bedrock/latest/userguide/
4. AWS User Group Madurai hackathon kit: https://github.com/Vivek0712/decider-hackathon-kit
5. Hackathon rules: https://builder.aws.com/build/hackathons/4f50957c-1d08-37ab-b11c-97516b9adeb4/

---

*Built with the AWS User Group Madurai Strands Decider hackathon kit.*
*Submitted to the Agent Experience Hackathon: Strands Decider, October 16–23, 2026.*
