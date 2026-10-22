"""In-memory store for incidents, resources and decision records.

This is a simulation and decision-support prototype. All data is fictional. The store is seeded
from ``seed_incidents.json`` / ``seed_resources.json`` on startup and on ``POST /api/demo/reset``.

A persistent backend (Amazon DynamoDB) is documented in ``infrastructure/``; the in-memory store
keeps the demo and tests deterministic and dependency-free.
"""

from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).resolve().parent

# The fictional demo incidents described in the hackathon brief (A: flood, B: road, C: power)
# plus a few extra so competing-incident comparison and the Decision Arena have material to work with.
SEED_INCIDENTS_FILE = SEED_DIR / "seed_incidents.json"
SEED_RESOURCES_FILE = SEED_DIR / "seed_resources.json"


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


class Store:
    """Thread-safe in-memory state."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.incidents: list[dict[str, Any]] = []
        self.resources: list[dict[str, Any]] = []
        self.decisions: list[dict[str, Any]] = []  # structured decision records
        self.activity: list[dict[str, Any]] = []  # agent activity timeline
        self._decision_seq = 0
        self._incident_seq = 0
        self.reset()

    # --- seeding / reset -----------------------------------------------------------------

    def reset(self) -> None:
        import json

        with self._lock:
            self.incidents = json.loads(SEED_INCIDENTS_FILE.read_text())
            self.resources = json.loads(SEED_RESOURCES_FILE.read_text())
            self.decisions = []
            self.activity = []
            self._decision_seq = 0
            self._incident_seq = 0
            # Re-number incident sequences from the highest existing id.
            nums = []
            for i in self.incidents:
                try:
                    nums.append(int(i["id"].replace("INC-", "")))
                except ValueError:
                    pass
            self._incident_seq = max(nums) if nums else 0

    # --- incidents -----------------------------------------------------------------------

    def list_incidents(self, status: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            if status:
                return [dict(i) for i in self.incidents if i.get("status") == status]
            return [dict(i) for i in self.incidents]

    def get_incident(self, incident_id: str) -> dict[str, Any] | None:
        iid = (incident_id or "").strip().upper()
        with self._lock:
            for i in self.incidents:
                if i["id"].upper() == iid:
                    return dict(i)
        return None

    def add_incident(self, data: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._incident_seq += 1
            inc = {
                "id": f"INC-{self._incident_seq:03d}",
                "type": data.get("type", "unknown"),
                "location": data.get("location", "unknown"),
                "affected_people": data.get("affected_people", "unknown"),
                "affected_people_num": int(data.get("affected_people_num", 0) or 0),
                "hazards": data.get("hazards", "none reported"),
                "time_sensitivity": int(data.get("time_sensitivity", 3) or 3),
                "severity": int(data.get("severity", 3) or 3),
                "hazard_level": int(data.get("hazard_level", 1) or 1),
                "report_time": data.get("report_time", _now()),
                "status": "active",
                "report": data.get("report", data.get("type", "incident") + " reported."),
            }
            self.incidents.append(inc)
            return dict(inc)

    def update_incident(self, incident_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        iid = (incident_id or "").strip().upper()
        with self._lock:
            for i in self.incidents:
                if i["id"].upper() == iid:
                    for k, v in updates.items():
                        if k in i and v is not None:
                            i[k] = v
                    return dict(i)
        return None

    def set_incident_status(self, incident_id: str, status: str) -> dict[str, Any] | None:
        return self.update_incident(incident_id, {"status": status})

    # --- resources -----------------------------------------------------------------------

    def list_resources(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self.resources]

    def get_resources_for_type(self, incident_type: str) -> list[dict[str, Any]]:
        itype = (incident_type or "").strip().lower()
        with self._lock:
            return [dict(r) for r in self.resources
                    if any(itype in s.lower() or s.lower() in itype for s in r["suited_for"])]

    def update_resource(self, name: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for r in self.resources:
                if r["name"].lower() == name.lower():
                    for k, v in updates.items():
                        if k in r and v is not None:
                            r[k] = v
                    return dict(r)
        return None

    # --- decisions -----------------------------------------------------------------------

    def add_decision(self, decision: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._decision_seq += 1
            decision = dict(decision)
            decision["decision_id"] = f"DEC-{self._decision_seq:04d}"
            decision["recorded_at"] = _now()
            self.decisions.append(decision)
            return dict(decision)

    def get_decision(self, decision_id: str) -> dict[str, Any] | None:
        with self._lock:
            for d in self.decisions:
                if d["decision_id"] == decision_id:
                    return dict(d)
        return None

    def list_decisions(self, incident_id: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            out = [dict(d) for d in self.decisions]
        if incident_id:
            iid = incident_id.strip().upper()
            out = [d for d in out if d.get("incident_id", "").upper() == iid]
        return out

    def update_decision(self, decision_id: str, updates: dict[str, Any]) -> dict[str, Any] | None:
        with self._lock:
            for d in self.decisions:
                if d["decision_id"] == decision_id:
                    for k, v in updates.items():
                        d[k] = v
                    return dict(d)
        return None

    def set_decision_status(self, decision_id: str, status: str, reviewer_note: str = "") -> dict[str, Any] | None:
        return self.update_decision(decision_id, {
            "decision_status": status,
            "reviewer_note": reviewer_note,
            "reviewed_at": _now(),
        })

    # --- activity timeline ---------------------------------------------------------------

    def add_activity(self, event: dict[str, Any]) -> None:
        with self._lock:
            self.activity.append({**event, "at": _now()})

    def list_activity(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(a) for a in self.activity[-limit:]]


# Module-level singleton (the demo is single-user; reset() reseeds it).
store = Store()
