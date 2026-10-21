"""Shared fixtures and a fake Strands Decider for unit tests.

Unit tests mock the model. A separate live integration test (``test_live_integration.py``) runs
only when real Strands Decider 2B credentials are configured.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

# Make the repo root (decider_kit) and backend importable.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from app.storage.store import store  # noqa: E402


@pytest.fixture(autouse=True)
def reset_store():
    """Every test starts from the seeded demo data."""
    store.reset()
    yield
    store.reset()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c


class FakeDecision:
    """Mimics decider_kit.Decision for unit tests."""

    def __init__(self, kind: str, label: str | None = None, p_yes: float | None = None,
                 probabilities: dict[str, float] | None = None, confidence: float = 0.9):
        self.kind = kind
        self.label = label
        self.p_yes = p_yes
        self.probabilities = probabilities or {}
        self.confidence = confidence

    @property
    def yes(self) -> bool:
        return bool(self.p_yes is not None and self.p_yes >= 0.5)


class FakeDecider:
    """A controllable in-process stand-in for Strands Decider 2B, used by unit tests only.

    It never makes a network call. Tests set ``responses`` to drive the verdict.
    """

    def __init__(self):
        self.responses: dict[str, Any] = {}
        self.calls = 0
        self.last_latency_ms = 12.0
        self.last_server_ms = 10.0
        self.input_tokens = 0

    def ask(self, state: str, questions: dict[str, Any], images: Any = None) -> dict[str, FakeDecision]:
        self.calls += 1
        out: dict[str, FakeDecision] = {}
        for name, q in questions.items():
            r = self.responses.get(name, {})
            kind = q["type"]
            if kind == "noul":
                out[name] = FakeDecision("noul", p_yes=float(r.get("p_yes", 0.1)), confidence=0.9)
            elif kind == "choice":
                probs = r.get("probabilities")
                label = r.get("label")
                if probs and not label:
                    label = max(probs, key=probs.get)
                out[name] = FakeDecision("choice", label=label, probabilities=probs or {},
                                         confidence=max(probs.values()) if probs else 0.9)
            elif kind == "score":
                probs = r.get("probabilities", {})
                legend = {str(i): lvl for i, lvl in enumerate(q["criteria"])}
                label = r.get("label")
                if probs and not label:
                    top = max(probs, key=probs.get)
                    label = legend.get(top, top)
                out[name] = FakeDecision("score", label=label, probabilities=probs or {},
                                        confidence=max(probs.values()) if probs else 0.9)
        return out

    def health(self) -> dict[str, Any]:
        return {"status": "ok"}


@pytest.fixture
def fake_decider(monkeypatch):
    """Patch the orchestrator's decider with a FakeDecider (live path, no network)."""
    fake = FakeDecider()

    def _get_decider(self):
        return fake

    from app.agents import orchestrator as orch

    monkeypatch.setattr(orch.Orchestrator, "_get_decider", _get_decider)
    # Force the runtime to report a live decider so the live code path is exercised.
    from app.config import RuntimeMode

    live_mode = RuntimeMode(
        decider_live=True, decider_mode="ugmdu", decider_url="http://fake", decider_model="fake",
        llm_live=False, llm_provider="bedrock", llm_model_id="fake", label="live-ish", reason="test",
    )
    monkeypatch.setattr(orch.orchestrator, "_decider", fake, raising=False)
    monkeypatch.setattr("app.agents.orchestrator.runtime_mode", lambda: live_mode)
    monkeypatch.setattr("app.config.runtime_mode", lambda: live_mode)
    return fake
