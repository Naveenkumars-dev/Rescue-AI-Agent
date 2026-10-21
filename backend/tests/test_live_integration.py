"""Live Strands Decider 2B integration test.

Skipped automatically unless a real decider is reachable (DECIDER_API_KEY for the hosted UG
Madurai API, or a local `strands-decider serve`). Run explicitly:

    pytest tests/test_live_integration.py -rA

This calls the real model and asserts it returns calibrated probabilities for the triage
questions. It is never run in CI or unit tests, which mock the model.
"""

from __future__ import annotations

import os

import pytest

from decider_kit.config import load_dotenv

from app.config import ROOT

load_dotenv(ROOT / ".env")


def _decider_reachable() -> bool:
    from app.config import runtime_mode

    return runtime_mode().decider_live


@pytest.mark.skipif(not _decider_reachable(), reason="no live Strands Decider 2B configured")
def test_live_decider_returns_calibrated_probabilities():
    from app.agents import decision as dec
    from decider_kit import Decider

    d = Decider()
    state = dec.build_state(
        "Flood warning for Riverside. Water rising fast, residents may be trapped.",
        {"type": "flood", "location": "Riverside", "affected_people": "unknown",
         "hazards": "rising water", "time_sensitivity": 5, "preliminary_score": 80,
         "resources": "Boats x2"}, [], "Deploy swift-water rescue boats.")
    answers = d.ask(state, dec.QUESTIONS)
    assert "priority" in answers and "next_action" in answers and "life_safety" in answers
    # the decider returns probabilities summing to ~1 for each typed question
    pri_probs = answers["priority"].probabilities
    assert pri_probs and 0.9 < sum(pri_probs.values()) < 1.1
    assert answers["life_safety"].p_yes is not None
    # the verdict is one of allow/review/block
    v = dec.decide(answers)
    assert v.action in ("allow", "review", "block")
