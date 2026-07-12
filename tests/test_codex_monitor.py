from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from codex_pet.codex_monitor import CodexEventParser, CodexMonitor
from codex_pet.state_machine import EventKind


def record(record_type: str, payload: dict) -> str:
    return json.dumps({"type": record_type, "payload": payload})


class CodexEventParserTests(unittest.TestCase):
    def setUp(self) -> None:
        self.parser = CodexEventParser()

    def kinds(self, line: str) -> list[EventKind]:
        return [event.kind for event in self.parser.parse_line(line, "thread-a")]

    def test_task_lifecycle(self) -> None:
        self.assertEqual(
            self.kinds(record("event_msg", {"type": "task_started"})),
            [EventKind.ACTIVITY, EventKind.TASK_STARTED],
        )
        self.assertEqual(
            self.kinds(record("event_msg", {"type": "task_complete"})),
            [EventKind.TASK_COMPLETED],
        )
        self.assertEqual(
            self.kinds(record("event_msg", {"type": "turn_aborted"})),
            [EventKind.TASK_ABORTED],
        )

    def test_escalated_shell_call_is_permission(self) -> None:
        line = record(
            "response_item",
            {
                "type": "function_call",
                "name": "shell_command",
                "call_id": "call-1",
                "arguments": json.dumps(
                    {"sandbox_permissions": "require_escalated", "justification": "Allow?"}
                ),
            },
        )
        events = self.parser.parse_line(line, "thread-a")
        self.assertEqual([event.kind for event in events], [EventKind.ACTIVITY, EventKind.APPROVAL_REQUESTED])
        self.assertEqual(events[-1].call_id, "call-1")

        output = record(
            "response_item",
            {"type": "function_call_output", "call_id": "call-1", "output": "ok"},
        )
        resolved = self.parser.parse_line(output, "thread-a")
        self.assertEqual(resolved[0].kind, EventKind.APPROVAL_RESOLVED)
        self.assertEqual(resolved[0].call_id, "call-1")

    def test_request_user_input_is_permission(self) -> None:
        line = record(
            "response_item",
            {
                "type": "custom_tool_call",
                "name": "exec",
                "call_id": "call-2",
                "input": "await tools.request_user_input({questions: []})",
            },
        )
        self.assertIn(EventKind.APPROVAL_REQUESTED, self.kinds(line))

    def test_usage_limit_is_failure(self) -> None:
        line = record(
            "event_msg",
            {
                "type": "error",
                "message": "You've hit your usage limit.",
                "codex_error_info": "usage_limit_exceeded",
            },
        )
        events = self.parser.parse_line(line, "thread-a")
        self.assertEqual(events[0].kind, EventKind.TASK_FAILED)
        self.assertEqual(events[0].reason, "usage_limit_exceeded")

    def test_invalid_lines_are_ignored(self) -> None:
        self.assertEqual(self.parser.parse_line("not-json", "thread-a"), [])

    def test_old_discovered_sessions_are_not_replayed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            codex_home = Path(temporary)
            sessions = codex_home / "sessions"
            sessions.mkdir()
            old_path = sessions / "rollout-old.jsonl"
            old_path.write_text(
                record("event_msg", {"type": "task_complete"}) + "\n", encoding="utf-8"
            )
            old_time = time.time() - 30
            os.utime(old_path, (old_time, old_time))

            monitor = CodexMonitor(codex_home)
            monitor._started_at = time.time()
            events = []
            monitor.event_received.connect(events.append)
            monitor.poll_sessions()
            self.assertEqual(events, [])

            new_path = sessions / "rollout-new.jsonl"
            new_path.write_text(
                record("event_msg", {"type": "task_started"}) + "\n", encoding="utf-8"
            )
            monitor.poll_sessions()
            self.assertIn(EventKind.TASK_STARTED, [event.kind for event in events])

    def test_three_network_errors_trigger_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            monitor = CodexMonitor(Path(temporary))
            events = []
            monitor.event_received.connect(events.append)
            for timestamp in (100.0, 104.0, 108.0):
                monitor._consider_log_error(
                    timestamp,
                    "codex_http_client::transport",
                    "connection timeout while sending request",
                    "thread-a",
                )
            failures = [event for event in events if event.kind is EventKind.TASK_FAILED]
            self.assertEqual(len(failures), 1)
            self.assertEqual(failures[0].reason, "network_error")


if __name__ == "__main__":
    unittest.main()
