"""Application configuration.

RescueFlow AI uses the official AWS User Group Madurai Strands Decider hackathon kit
(``decider_kit``) for the decision model. The generative part runs through the Strands Agents
SDK (Amazon Bedrock by default).

The app runs in two modes:

* **live** — Strands Decider 2B answers the typed triage questions, and a Strands Agent on
  Amazon Bedrock drafts the recommendation. Requires ``DECIDER_API_KEY`` (hosted) or a local
  ``strands-decider serve`` (``DECIDER_MODE=local``), plus AWS credentials for Bedrock.
* **demo** — no external model is reachable. Tools still run for real (they read the seeded
  registry), but the decision is produced by a clearly-labelled deterministic fallback and the
  recommendation draft is generated from templates. Nothing is ever presented as coming from
  Strands Decider 2B in this mode.

Mode is detected from configuration and (for the local decider) a short health probe. The
orchestrator also falls back to demo mode at runtime if a live call fails, and records which
mode produced each decision.
"""

from __future__ import annotations

import os
import sys
import time
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

# Make the bundled official decider_kit importable from the repository root.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from decider_kit.config import load_dotenv, settings  # noqa: E402

load_dotenv(ROOT / ".env")


@dataclass
class RuntimeMode:
    """Snapshot of what is available right now."""

    decider_live: bool
    decider_mode: str
    decider_url: str
    decider_model: str
    llm_live: bool
    llm_provider: str
    llm_model_id: str
    label: str  # "live" | "demo"
    reason: str


def _strands_available() -> bool:
    try:
        import strands  # noqa: F401

        return True
    except Exception:  # noqa: BLE001
        return False


def _bedrock_reachable() -> bool:
    """Verify the AWS account can actually be reached for Bedrock (STS GetCallerIdentity).

    A real check, so the UI never claims a live Amazon Bedrock connection that does not exist.
    IMDS is disabled for the probe so a machine with no AWS credentials fails fast instead of
    waiting on the metadata service timeout. Cached implicitly via the lru_cache on runtime_mode.
    """
    old = os.environ.get("AWS_EC2_METADATA_DISABLED")
    os.environ["AWS_EC2_METADATA_DISABLED"] = "true"
    try:
        import boto3
        from botocore.config import Config
        from botocore.exceptions import ClientError, NoCredentialsError

        sts = boto3.client(
            "sts",
            region_name=os.environ.get("AWS_REGION", "us-east-1"),
            config=Config(connect_timeout=2, read_timeout=2, retries={"max_attempts": 0}),
        )
        sts.get_caller_identity()
        return True
    except (NoCredentialsError, ClientError):
        return False
    except Exception:  # noqa: BLE001 - any failure means not reachable
        return False
    finally:
        if old is None:
            os.environ.pop("AWS_EC2_METADATA_DISABLED", None)
        else:
            os.environ["AWS_EC2_METADATA_DISABLED"] = old


def _ollama_reachable(url: str = "http://127.0.0.1:11434") -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url + "/api/tags", timeout=2) as r:  # noqa: S310
            return r.status == 200
    except Exception:  # noqa: BLE001
        return False


@lru_cache(maxsize=1)
def runtime_mode() -> RuntimeMode:
    s = settings()
    provider = os.environ.get("LLM_PROVIDER", "bedrock").lower()

    # --- Decider availability ------------------------------------------------------------
    decider_live = False
    decider_reason = ""
    if s.decider_mode == "ugmdu":
        if s.decider_api_key:
            decider_live = True
        else:
            decider_reason = "DECIDER_MODE=ugmdu but DECIDER_API_KEY is not set"
    elif s.decider_mode == "custom":
        decider_live = bool(s.decider_api_key)
        if not decider_live:
            decider_reason = "DECIDER_MODE=custom but DECIDER_API_KEY is not set"
    elif s.decider_mode == "local":
        # Probe the local strands-decider server once.
        try:
            from decider_kit import Decider, DeciderError

            d = Decider()
            d.health()
            decider_live = True
        except DeciderError as e:
            decider_reason = f"local decider not reachable: {e}"
        except Exception as e:  # noqa: BLE001
            decider_reason = f"local decider probe failed: {e}"
    else:
        decider_reason = f"unknown DECIDER_MODE={s.decider_mode!r}"

    # --- LLM availability ---------------------------------------------------------------
    llm_live = False
    llm_reason = ""
    if not _strands_available():
        llm_reason = "strands-agents is not installed"
    elif provider == "bedrock":
        llm_live = _bedrock_reachable()
        if not llm_live:
            llm_reason = "LLM_PROVIDER=bedrock but no reachable AWS credentials"
    elif provider == "local":
        llm_live = _ollama_reachable(os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434"))
        if not llm_live:
            llm_reason = "LLM_PROVIDER=local but Ollama is not running"
    elif provider == "ugmdu":
        llm_live = bool(s.decider_api_key)
        if not llm_live:
            llm_reason = "LLM_PROVIDER=ugmdu but DECIDER_API_KEY is not set"
    else:
        llm_reason = f"unknown LLM_PROVIDER={provider!r}"

    live = decider_live and llm_live
    label = "live" if live else "demo"
    reason = "" if live else " | ".join(filter(None, [decider_reason, llm_reason])) or "not configured"
    if live:
        reason = "Strands Decider 2B + Strands Agent (Bedrock) reachable"

    from decider_kit.llm import default_model_id  # local import to avoid heavy import at module load

    return RuntimeMode(
        decider_live=decider_live,
        decider_mode=s.decider_mode,
        decider_url=s.decider_url,
        decider_model=s.decider_model,
        llm_live=llm_live,
        llm_provider=provider,
        llm_model_id=default_model_id(provider),
        label=label,
        reason=reason,
    )


def mode_info() -> dict[str, Any]:
    rm = runtime_mode()
    return {
        "mode": rm.label,
        "decider_live": rm.decider_live,
        "decider_mode": rm.decider_mode,
        "decider_model": rm.decider_model,
        "llm_live": rm.llm_live,
        "llm_provider": rm.llm_provider,
        "llm_model_id": rm.llm_model_id,
        "reason": rm.reason,
        "agent_name": "RescueFlow AI — emergency-response triage",
        "kit_credit": "Built with the AWS User Group Madurai Strands Decider hackathon kit",
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }


def reset_mode_cache() -> None:
    """Invalidate the cached mode probe (used by the demo reset / config change endpoints)."""
    runtime_mode.cache_clear()
