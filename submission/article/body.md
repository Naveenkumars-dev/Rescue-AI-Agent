# RescueFlow AI: Building an Agentic Disaster Response Decision System with Strands Decider 2B on AWS

By Naveen Kumar

During a disaster, incident reports compete for the same limited response resources. A residential flood, a blocked access road, and a power outage can arrive simultaneously, each with incomplete information and a coordinator who must decide which deserves attention first. A fixed-rule system cannot read whether "residents may be trapped" is a life-safety signal. A general-purpose language model is too slow and too expensive to run on every incoming event. RescueFlow AI solves this with Strands Decider 2B: one forward pass per incident, calibrated probabilities the code can branch on, and a human coordinator who approves every consequential recommendation.

## The project

RescueFlow AI is a decision-support prototype for emergency coordinators. It accepts free-text incident reports, collects structured facts through eight explicitly defined agent tools, and uses Strands Decider 2B to classify each incident under a written response protocol: **allow** (propose a response plan for human approval), **review** (hold for a human coordinator), or **block** (life-safety incident -- escalate immediately, never auto-dispatch).

**Features:**
- Accepts incident reports in plain language and triages them against a written protocol.
- A transparent preliminary risk score is computed in code (arithmetic: severity, time sensitivity, people affected, hazard level) and placed in the state the decider reads -- so the decider reads language, not numbers.
- Strands Decider 2B classifies each incident in one forward pass, returning `priority` (score), `next_action` (choice), and `life_safety` (noul) with calibrated probabilities.
- Life-safety incidents (`life_safety.p_yes >= 0.60`, confident) are blocked and escalated; the prototype never auto-recommends or auto-dispatches a response for them.
- A **Decision Arena** compares three or more incidents simultaneously, ranks them by verdict and score, and re-evaluates in real time when a coordinator introduces new conditions.
- A live decision panel in the demo UI shows the probability bars, verdict, and reason for every Strands Decider 2B call.
- Every recommendation is `PROPOSED` until a human coordinator approves or rejects it.

Here is a real decision from the live run against the hosted Strands Decider 2B API (2026-10-22):

> **Coordinator:** Evaluate INC-001 -- flood warning for Riverside. Water rising fast, residents may be trapped.
>
> **RescueFlow AI:** [ESCALATE] ESCALATE -- life-safety incident
> Incident: INC-001 -- Flood at Riverside low-lying residential area
> Priority: CRITICAL | Preliminary risk score: 80/100
> Recommended action: Escalate to human coordinator
> Available resources: Swift-water Rescue Boat Team x2, Reconnaissance Drone Unit x2
> Triage decision (block): Life-safety incident detected. Escalate to professional emergency services and a human coordinator. This prototype must not auto-recommend or dispatch.
> Strands Decider 2B: life_safety p=0.82 * decider_ms=6728

After introducing "Resident confirmed trapped on first floor. Water now at chest height," the reassessment returned `life_safety.p_yes = 0.79`, verdict **BLOCK** -- the same escalation, re-confirmed with updated evidence.

## How I built it

The backend is FastAPI + Python. The agent uses the Strands Agents SDK with 13 `@tool`-decorated functions. Amazon Bedrock (Nova Pro) handles the conversational and tool-use layer; Strands Decider 2B handles the triage classification. The frontend is React + Vite + TypeScript + Tailwind CSS + Recharts, served as static files from the same FastAPI server. I used Kiro to spec the requirements, design the `#policy` decision pattern, generate the 26 labelled eval cases, write the 78-test suite, and build the React dashboard. The kit's `decider_kit/` library (`Decider`, the policy pattern, the benchmark runner) is by the AWS User Group Madurai.

The deployment target is Amazon Bedrock AgentCore Runtime via `./kit deploy`. The infrastructure CDK project is in `deploy/agentcore/cdk/`. AWS credentials were not configured during the submission period, so this section documents the planned deployment rather than a completed one.

## The decision I handed to Strands Decider 2B

Every incident triage decision requires reading language: does "residents may be trapped" imply a life-safety risk? Is the action premature? What should the coordinator do next? A rule engine can check `severity >= 4`; it cannot check whether a sentence implies danger.

Strands Decider 2B reads the assembled state -- the response protocol, the incident report, the tool-extracted facts (including the preliminary score), the other active incidents for comparison, and a draft recommendation -- and answers three typed questions in one forward pass. The state is encoded once; all three questions share it, so the cost is the same as one question.

```python
QUESTIONS = {
    "priority": Decider.score("How urgent is this incident for response priority?", PRIORITY_LEVELS),
    "next_action": Decider.choice(
        "Which response action fits this incident right now, given the facts and the other active incidents?",
        NEXT_ACTIONS,
    ),
    "life_safety": Decider.noul(
        "Does this incident describe an immediate or probable threat to life or serious harm (people trapped, injured, or a fast-moving danger) that the response protocol says must be escalated to professional emergency services and never auto-handled by a prototype?",
        {"true": "an immediate or probable threat to life or serious harm is described",
         "false": "no imminent threat to life or serious harm is described"},
    ),
}
```

The verdict thresholds are ordinary `if` statements in `agent/decision.py`:

| Condition | Verdict |
|---|---|
| `life_safety.p_yes >= 0.60` AND confident | **block** -- escalate immediately |
| `life_safety.p_yes` in [0.40, 0.60) | **review** -- uncertain; human must assess |
| `next_action == escalate_to_human` | **review** |
| `next_action == request_missing_information` | **review** |
| any answer confidence < 0.65 | **review** -- low-confidence fallback |
| `next_action == monitor` | **allow** -- propose monitoring |
| otherwise | **allow** -- propose response plan for human approval |

When confidence falls below 0.65 on any question, the system defers to a human rather than guessing. That is not a failure -- those are the borderline cases where automated action is most dangerous.

< FIGURE 1 of 5: upload submission/article/img/architecture.png here >
Alt text: Architecture: the user, the agent with its tools and decision, Amazon Bedrock and Strands Decider 2B

## Measured

The benchmark compares Strands Decider 2B (hosted ugmdu API, model `strands-decider-2B-hobson-v19`) against Amazon Nova Pro as an LLM baseline, on 12 held-out labelled cases from `agent/eval_cases.jsonl`. The decider ran on the AWS User Group Madurai hosted endpoint; its latency includes network round-trip.

| | Strands Decider 2B | Amazon Nova Pro |
|---|---|---|
| Accuracy | 79.2% | 95.8% |
| Latency p50 per decision | 295 ms | 1,276 ms |
| Latency p95 | 468 ms | 1,426 ms |
| Cost per 1,000 decisions | $0.00 (hosted API) | $0.18 |
| Answered alone at confidence >= 0.70 | 67% | 100% |
| Accuracy when confident | 93.8% | 95.8% |

At the median, the decider was **4.3x faster** than Nova Pro. On the 67% of cases it answered with high confidence, its accuracy (93.8%) is within 2 percentage points of the LLM (95.8%). The 33% it deferred to a human are the borderline cases -- the right outcome.

Honest caveat: 12 cases is a small benchmark. The results are directional signal, not a production-grade evaluation. The bench was split into tune (13 cases) and test (13 cases); the numbers above are from the combined run.

< FIGURE 2 of 5: upload submission/article/img/bench-accuracy.png here >
Alt text: Accuracy of Strands Decider 2B and the Bedrock LLM on the labelled cases

< FIGURE 3 of 5: upload submission/article/img/bench-latency.png here >
Alt text: Median latency per decision for both

< FIGURE 4 of 5: upload submission/article/img/bench-cost.png here >
Alt text: Cost per 1,000 decisions for both

< FIGURE 5 of 5: upload submission/article/img/bench-confidence.png here >
Alt text: Accuracy against the share of decisions answered without a human, as the confidence threshold moves

## The reusable decision pattern

The `#policy` pattern lives in `agent/decision.py` under the label `REUSABLE DECISION PATTERN: emergency-response triage policy (#policy)`. It documents what it does, the typed questions and options, the wiring (a `TriagePolicy` class whose `check()` method builds the state and calls the decider), and how to reuse it:

> Copy this file, rewrite `PROTOCOL` and the three questions for your safety-critical domain, and keep the `allow/review/block` thresholds in `decide()`. Keep the rule: compute every number in a tool and put the result in the state; let the decider read language, not do arithmetic.

Any builder can drop it into a Strands agent in three steps: (1) define a response protocol as a string, (2) write three typed questions for their domain, (3) call `TriagePolicy(Decider()).check(state)` after the agent's tools have run.

The five patterns in `decider_kit/patterns/` (by the AWS User Group Madurai) show the same approach for `#guardrails`, `#tool-selection`, `#model-routing`, and `#context-memory`.

## What I learned and what is next

The most important design decision was: **arithmetic in code, language judgement in the model**. The preliminary risk score (a weighted formula) gives the decider a fact to read; it does not replace the decider's verdict. A score of 80 from a flood and a score of 80 from a chemical spill warrant very different responses -- the prose carries that signal, and the model reads it.

The confidence fallback matters more than the accuracy headline. A decider that is right 79% of the time but defers the hard 33% to a human is more useful than one that is right 79% of the time and guesses the rest. The low-confidence cases in this benchmark are exactly the ambiguous ones where a human should decide.

**What is next:** real authorized disaster data feeds, geospatial visualisation, resource allocation across incidents (committing a rescue boat to one incident should reduce availability for others), calibrated confidence from a larger labelled dataset, and deployment to Amazon Bedrock AgentCore Runtime with CloudWatch logging.

---

Code: https://github.com/Naveenkumars-dev/Rescue-AI-Agent . Video: upload to YouTube/Vimeo then paste here . Tags: #strands-decider-2b #policy

Built with the AWS User Group Madurai Strands Decider hackathon kit
