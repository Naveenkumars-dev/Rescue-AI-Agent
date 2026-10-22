# RescueFlow AI — tasks

## Done ✅

- [x] Spec: requirements.md, design.md, tasks.md
- [x] Seed data: agent/data/incidents.json (10 incidents), agent/data/resources.json (8 types)
- [x] agent/decision.py — #policy triage pattern (QUESTIONS, build_state, TriagePolicy)
- [x] agent/tools.py — 13 tools (8 primary per spec + 5 backward-compat aliases)
- [x] agent/agent.py — HackathonAgent with TriagePolicy wired post-draft
- [x] agent/AGENT.md — use-case write-up
- [x] agent/eval_cases.jsonl — 26 labelled cases (13 tune / 13 test)
- [x] agent/demo_script.yaml — 4 demo turns
- [x] agent/features.yaml — Memory/Gateway off (Runtime alone)
- [x] tests/test_rescueflow_wiring.py — 12 wiring tests (FakeDecider, offline)
- [x] tests/test_rescueflow_api.py — 28 API endpoint tests (all 12 endpoints)
- [x] All 78 tests pass (.venv/bin/python -m pytest -q)
- [x] demo/server.py — all 12 required API endpoints + Decision Arena
- [x] React frontend — Vite + TypeScript + Tailwind + Recharts (frontend/dist built)
- [x] Decision Arena — compare 3 incidents, Change Conditions, reassessment
- [x] README.md — judge-ready (problem, architecture, how Decider is used, setup, deploy)
- [x] Demo server live at http://localhost:8501 (React dashboard + API)

## Needs your credentials (cannot be completed without them)

- [ ] ./kit run end-to-end (needs LLM + decider: run ./kit setup first)
- [ ] ./kit bench — accuracy vs LLM baseline (needs decider server/key)
- [ ] ./kit deploy — AgentCore Runtime (needs AWS account + Bedrock access)
- [ ] ./kit video — recorded demo (needs deployed agent)
- [ ] ./kit article — Builder Center bundle (needs video + bench numbers)
- [ ] ./kit publish — public GitHub repo (needs gh login + deploy done)

## How to get from here to submission

1. ./kit aws-login        (enter your AWS keys in the terminal)
2. ./kit setup --llm bedrock --mode ugmdu   (or --mode local if running decider yourself)
3. ./kit run              (smoke-test the agent end-to-end)
4. ./kit bench --split test   (measure the decision vs a Bedrock LLM)
5. ./kit deploy           (push to AgentCore Runtime)
6. ./kit video --target agentcore
7. ./kit article
8. ./kit publish <your-github-repo>
9. Upload video to YouTube/Vimeo, publish article on Builder Center, submit the 3 links.
