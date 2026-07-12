from __future__ import annotations

import json
import logging
import re
import sqlite3
import time
from collections import defaultdict, deque
from pathlib import Path

from PyQt6.QtCore import QObject, QTimer, pyqtSignal

from .state_machine import EventKind, MonitorEvent
from .usage import UsageSnapshot, parse_usage_snapshot


UUID_RE = re.compile(
    r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})",
    re.IGNORECASE,
)
TERMINAL_ERROR_WORDS = (
    "usage_limit",
    "usage limit",
    "quota",
    "no credits",
    "insufficient",
    "unauthorized",
    "authentication",
    "rate limit",
)
NETWORK_ERROR_WORDS = (
    "network",
    "connection",
    "connect error",
    "connection reset",
    "dns",
    "timeout",
    "timed out",
    "transport error",
    "failed to send",
)


class CodexEventParser:
    """Extracts lifecycle signals without persisting conversation contents."""

    def parse_line(self, line: str, thread_id: str) -> list[MonitorEvent]:
        try:
            record = json.loads(line)
        except (ValueError, TypeError):
            return []

        payload = record.get("payload") or {}
        record_type = record.get("type")
        payload_type = payload.get("type")
        now = time.time()

        if record_type == "event_msg":
            if payload_type == "task_started":
                return [
                    MonitorEvent(EventKind.ACTIVITY, thread_id, occurred_at=now),
                    MonitorEvent(EventKind.TASK_STARTED, thread_id, occurred_at=now),
                ]
            if payload_type == "task_complete":
                return [MonitorEvent(EventKind.TASK_COMPLETED, thread_id, occurred_at=now)]
            if payload_type == "turn_aborted":
                return [MonitorEvent(EventKind.TASK_ABORTED, thread_id, occurred_at=now)]
            if payload_type == "error":
                message = str(payload.get("codex_error_info") or payload.get("message") or "error")
                return [
                    MonitorEvent(
                        EventKind.TASK_FAILED,
                        thread_id,
                        reason=message[:240],
                        occurred_at=now,
                    )
                ]
            if payload_type == "user_message":
                return [MonitorEvent(EventKind.ACTIVITY, thread_id, occurred_at=now)]

        if record_type == "response_item":
            call_id = str(payload.get("call_id") or "")
            name = str(payload.get("name") or "")
            raw_input = str(payload.get("input") or payload.get("arguments") or "")
            if payload_type in {"function_call", "custom_tool_call"}:
                is_approval = (
                    "require_escalated" in raw_input
                    or "request_user_input" in name
                    or "request_user_input" in raw_input
                )
                if is_approval:
                    return [
                        MonitorEvent(EventKind.ACTIVITY, thread_id, occurred_at=now),
                        MonitorEvent(
                            EventKind.APPROVAL_REQUESTED,
                            thread_id,
                            call_id=call_id,
                            occurred_at=now,
                        ),
                    ]
            if payload_type in {"function_call_output", "custom_tool_call_output"} and call_id:
                return [
                    MonitorEvent(
                        EventKind.APPROVAL_RESOLVED,
                        thread_id,
                        call_id=call_id,
                        occurred_at=now,
                    )
                ]
        return []


class CodexMonitor(QObject):
    event_received = pyqtSignal(object)
    health_changed = pyqtSignal(bool)
    usage_updated = pyqtSignal(object)

    def __init__(self, codex_home: Path, logger: logging.Logger | None = None) -> None:
        super().__init__()
        self.codex_home = codex_home
        self.sessions_root = codex_home / "sessions"
        self.logs_db = codex_home / "logs_2.sqlite"
        self.logger = logger or logging.getLogger(__name__)
        self.parser = CodexEventParser()
        self._offsets: dict[Path, int] = {}
        self._buffers: dict[Path, str] = {}
        self._network_errors: dict[str, deque[float]] = defaultdict(deque)
        self._last_log_id = 0
        self._healthy = True
        self._started_at = 0.0
        self._last_usage_signature: tuple | None = None
        self._usage_source = ""
        self._last_usage_observed_at = 0.0
        self._bootstrapping_usage = False
        self._pending_usage: UsageSnapshot | None = None

        self.session_timer = QTimer(self)
        self.session_timer.setInterval(750)
        self.session_timer.timeout.connect(self.poll_sessions)
        self.log_timer = QTimer(self)
        self.log_timer.setInterval(2000)
        self.log_timer.timeout.connect(self.poll_logs)

    def start(self) -> None:
        self._started_at = time.time()
        self._bootstrapping_usage = True
        self._bootstrap_sessions()
        self._bootstrap_logs()
        self._bootstrapping_usage = False
        if self._pending_usage is not None:
            self.usage_updated.emit(self._pending_usage)
            self._pending_usage = None
        self.session_timer.start()
        self.log_timer.start()

    def stop(self) -> None:
        self.session_timer.stop()
        self.log_timer.stop()

    def poll_sessions(self) -> None:
        try:
            files = list(self.sessions_root.rglob("rollout-*.jsonl")) if self.sessions_root.exists() else []
            for path in files:
                if path not in self._offsets:
                    stat = path.stat()
                    is_new_session = stat.st_mtime >= self._started_at - 1.0
                    self._offsets[path] = 0 if is_new_session else stat.st_size
                    self._buffers[path] = ""
                self._read_appended(path)
            self._set_health(True)
        except Exception as exc:  # noqa: BLE001 - monitor must degrade without taking down the pet
            self.logger.warning("Session monitor degraded: %s", type(exc).__name__)
            self._set_health(False)

    def poll_logs(self) -> None:
        if not self.logs_db.exists():
            return
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                f"file:{self.logs_db}?mode=ro", uri=True, timeout=0.25
            )
            rows = connection.execute(
                "SELECT id, ts, level, target, feedback_log_body, thread_id "
                "FROM logs WHERE id > ? ORDER BY id LIMIT 1000",
                (self._last_log_id,),
            ).fetchall()
            for row_id, timestamp, level, target, body, thread_id in rows:
                self._last_log_id = max(self._last_log_id, int(row_id))
                self._consider_usage(str(body or ""), "logs_2.sqlite", float(timestamp))
                if str(level).upper() not in {"WARN", "WARNING", "ERROR"}:
                    continue
                self._consider_log_error(
                    float(timestamp), str(target or ""), str(body or ""), str(thread_id or "")
                )
        except (sqlite3.Error, OSError) as exc:
            self.logger.debug("Log monitor temporarily unavailable: %s", type(exc).__name__)
        finally:
            if connection is not None:
                connection.close()

    def _bootstrap_sessions(self) -> None:
        if not self.sessions_root.exists():
            self._set_health(False)
            return
        recent = sorted(
            self.sessions_root.rglob("rollout-*.jsonl"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )[:10]
        now = time.time()
        for path in reversed(recent):
            size = path.stat().st_size
            self._offsets[path] = size
            self._buffers[path] = ""
            if now - path.stat().st_mtime > 6 * 3600:
                continue
            thread_id = self._thread_id(path)
            try:
                tail_size = 8 * 1024 * 1024
                with path.open("rb") as handle:
                    handle.seek(max(0, size - tail_size))
                    data = handle.read().decode("utf-8", errors="ignore")
                if size > tail_size and "\n" in data:
                    data = data.split("\n", 1)[1]
                relevant: list[MonitorEvent] = []
                for line in data.splitlines():
                    self._consider_usage(line, "session", path.stat().st_mtime)
                    relevant.extend(self.parser.parse_line(line, thread_id))
                last_terminal = -1
                last_start = -1
                pending: dict[str, MonitorEvent] = {}
                for index, event in enumerate(relevant):
                    if event.kind is EventKind.TASK_STARTED:
                        last_start = index
                    elif event.kind in {
                        EventKind.TASK_COMPLETED,
                        EventKind.TASK_ABORTED,
                        EventKind.TASK_FAILED,
                    }:
                        last_terminal = index
                    elif event.kind is EventKind.APPROVAL_REQUESTED:
                        pending[event.call_id] = event
                    elif event.kind is EventKind.APPROVAL_RESOLVED:
                        pending.pop(event.call_id, None)
                if last_start > last_terminal:
                    self.event_received.emit(
                        MonitorEvent(EventKind.TASK_STARTED, thread_id, occurred_at=path.stat().st_mtime)
                    )
                for event in pending.values():
                    self.event_received.emit(event)
            except OSError:
                continue

    def _bootstrap_logs(self) -> None:
        if not self.logs_db.exists():
            return
        connection: sqlite3.Connection | None = None
        try:
            connection = sqlite3.connect(
                f"file:{self.logs_db}?mode=ro", uri=True, timeout=0.25
            )
            row = connection.execute("SELECT COALESCE(MAX(id), 0) FROM logs").fetchone()
            self._last_log_id = int(row[0] if row else 0)
            recent = connection.execute(
                "SELECT ts, feedback_log_body FROM logs "
                "WHERE feedback_log_body LIKE '%rate_limit%' "
                "ORDER BY id DESC LIMIT 200"
            ).fetchall()
            for timestamp, body in reversed(recent):
                self._consider_usage(str(body or ""), "logs_2.sqlite", float(timestamp))
        except sqlite3.Error:
            self._last_log_id = 0
        finally:
            if connection is not None:
                connection.close()

    def _read_appended(self, path: Path) -> None:
        size = path.stat().st_size
        offset = self._offsets.get(path, 0)
        if size < offset:
            offset = 0
        if size == offset:
            return
        with path.open("rb") as handle:
            handle.seek(offset)
            chunk = handle.read().decode("utf-8", errors="ignore")
        self._offsets[path] = size
        data = self._buffers.get(path, "") + chunk
        lines = data.split("\n")
        self._buffers[path] = lines.pop() if lines else data
        thread_id = self._thread_id(path)
        for line in lines:
            self._consider_usage(line, "session", path.stat().st_mtime)
            for event in self.parser.parse_line(line, thread_id):
                self.event_received.emit(event)

    def _consider_usage(self, text: str, source: str, observed_at: float) -> None:
        snapshot = parse_usage_snapshot(text, source, observed_at)
        if snapshot is None:
            return
        if source == "logs_2.sqlite" and self._usage_source == "session":
            return
        if snapshot.observed_at < self._last_usage_observed_at:
            return
        signature = (
            snapshot.primary.used_percent,
            snapshot.primary.resets_at,
            snapshot.secondary.used_percent,
            snapshot.secondary.resets_at,
        )
        if signature == self._last_usage_signature:
            return
        self._last_usage_signature = signature
        self._usage_source = source
        self._last_usage_observed_at = snapshot.observed_at
        if self._bootstrapping_usage:
            self._pending_usage = snapshot
        else:
            self.usage_updated.emit(snapshot)

    def _consider_log_error(
        self, timestamp: float, target: str, body: str, thread_id: str
    ) -> None:
        lowered = f"{target} {body}".lower()
        if any(word in lowered for word in TERMINAL_ERROR_WORDS):
            self.event_received.emit(
                MonitorEvent(
                    EventKind.TASK_FAILED,
                    thread_id or "global",
                    reason="terminal_error",
                    occurred_at=timestamp,
                )
            )
            return
        if not any(word in lowered for word in NETWORK_ERROR_WORDS):
            return
        key = thread_id or "global"
        errors = self._network_errors[key]
        errors.append(timestamp)
        while errors and timestamp - errors[0] > 15:
            errors.popleft()
        if len(errors) >= 3:
            errors.clear()
            self.event_received.emit(
                MonitorEvent(
                    EventKind.TASK_FAILED,
                    key,
                    reason="network_error",
                    occurred_at=timestamp,
                )
            )

    @staticmethod
    def _thread_id(path: Path) -> str:
        matches = UUID_RE.findall(path.name)
        return matches[-1] if matches else path.stem

    def _set_health(self, healthy: bool) -> None:
        if self._healthy == healthy:
            return
        self._healthy = healthy
        self.health_changed.emit(healthy)
