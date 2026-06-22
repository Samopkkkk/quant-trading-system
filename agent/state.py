"""Persistent agent state.

A live auto-trader is a long-lived process that will restart — intraday on a
crash, or daily on a redeploy. Without persistence, every restart calls
RiskManager.initialize() and resets `peak_equity` to the current equity, which
makes the max-drawdown kill switch *forget* the prior peak. A real drawdown that
should have halted trading would be silently forgiven on restart.

StateStore persists the risk circuit-breaker state (and an optional trade log) to
a JSON file so the kill switch, daily-loss halt, and peak watermark survive
restarts. Writes are atomic (write-temp-then-rename) so a crash mid-write cannot
corrupt the file.
"""
from __future__ import annotations

import json
import logging
import os
from datetime import date, datetime

from .risk import RiskState

logger = logging.getLogger(__name__)


class StateStore:
    def __init__(self, path: str | None):
        self.path = path

    def _read(self) -> dict:
        if not self.path or not os.path.exists(self.path):
            return {}
        try:
            with open(self.path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read state file %s: %s", self.path, exc)
            return {}

    def _write(self, data: dict) -> None:
        if not self.path:
            return
        tmp = f"{self.path}.tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.path)  # atomic on POSIX

    # ---- risk state ----
    def load_risk_state(self) -> RiskState | None:
        rs = self._read().get("risk_state")
        if not rs:
            return None
        try:
            return RiskState(
                peak_equity=float(rs["peak_equity"]),
                day_start_equity=float(rs["day_start_equity"]),
                current_day=date.fromisoformat(rs["current_day"]),
                kill_switch_active=bool(rs["kill_switch_active"]),
                new_entries_halted=bool(rs["new_entries_halted"]),
            )
        except (KeyError, ValueError) as exc:
            logger.warning("Ignoring malformed risk_state: %s", exc)
            return None

    def save_risk_state(self, st: RiskState) -> None:
        data = self._read()
        data["risk_state"] = {
            "peak_equity": st.peak_equity,
            "day_start_equity": st.day_start_equity,
            "current_day": st.current_day.isoformat(),
            "kill_switch_active": st.kill_switch_active,
            "new_entries_halted": st.new_entries_halted,
            "updated_at": datetime.utcnow().isoformat(),
        }
        self._write(data)

    # ---- trade log (append-only) ----
    def append_trade(self, record: dict) -> None:
        data = self._read()
        data.setdefault("trades", []).append(record)
        self._write(data)
