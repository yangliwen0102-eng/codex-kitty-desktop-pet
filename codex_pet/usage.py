from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RateWindow:
    used_percent: float
    window_minutes: int
    resets_at: float

    @property
    def remaining_percent(self) -> float:
        return max(0.0, min(100.0, 100.0 - self.used_percent))


@dataclass(frozen=True)
class UsageSnapshot:
    primary: RateWindow
    secondary: RateWindow
    source: str
    observed_at: float


def _find_rate_limits(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        candidate = value.get("rate_limits")
        if isinstance(candidate, dict):
            return candidate
        if isinstance(value.get("primary"), dict) and isinstance(value.get("secondary"), dict):
            return value
        for child in value.values():
            found = _find_rate_limits(child)
            if found is not None:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _find_rate_limits(child)
            if found is not None:
                return found
    return None


def _json_values(text: str) -> list[Any]:
    try:
        return [json.loads(text)]
    except (ValueError, TypeError):
        pass
    decoder = json.JSONDecoder()
    values: list[Any] = []
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except ValueError:
            continue
        values.append(value)
    return values


def parse_usage_snapshot(text: str, source: str, observed_at: float | None = None) -> UsageSnapshot | None:
    for value in _json_values(text):
        limits = _find_rate_limits(value)
        if limits is None:
            continue
        try:
            primary_data = limits["primary"]
            secondary_data = limits["secondary"]
            primary = RateWindow(
                float(primary_data["used_percent"]),
                int(primary_data["window_minutes"]),
                float(primary_data["resets_at"]),
            )
            secondary = RateWindow(
                float(secondary_data["used_percent"]),
                int(secondary_data["window_minutes"]),
                float(secondary_data["resets_at"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
        record_time = observed_at or time.time()
        if isinstance(value, dict) and isinstance(value.get("timestamp"), str):
            try:
                record_time = datetime.fromisoformat(
                    value["timestamp"].replace("Z", "+00:00")
                ).timestamp()
            except ValueError:
                pass
        return UsageSnapshot(primary, secondary, source, record_time)
    return None


def format_countdown(resets_at: float, now: float | None = None) -> str:
    seconds = max(0, int(resets_at - (now if now is not None else time.time())))
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        return f"{days}天 {hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
