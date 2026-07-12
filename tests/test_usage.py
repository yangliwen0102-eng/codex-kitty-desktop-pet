from __future__ import annotations

import json
import unittest

from codex_pet.usage import format_countdown, parse_usage_snapshot


class UsageTests(unittest.TestCase):
    def test_parses_session_rate_limits(self) -> None:
        line = json.dumps(
            {
                "timestamp": "2026-07-12T03:25:59.250Z",
                "type": "event_msg",
                "payload": {
                    "type": "token_count",
                    "rate_limits": {
                        "primary": {
                            "used_percent": 21.0,
                            "window_minutes": 300,
                            "resets_at": 2000,
                        },
                        "secondary": {
                            "used_percent": 50.0,
                            "window_minutes": 10080,
                            "resets_at": 9000,
                        },
                    },
                },
            }
        )
        snapshot = parse_usage_snapshot(line, "session", observed_at=1000)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.primary.remaining_percent, 79.0)
        self.assertEqual(snapshot.secondary.remaining_percent, 50.0)
        self.assertEqual(snapshot.primary.window_minutes, 300)
        self.assertEqual(snapshot.secondary.window_minutes, 10080)
        self.assertGreater(snapshot.observed_at, 1_700_000_000)

    def test_parses_json_embedded_in_log_text(self) -> None:
        body = (
            'rate limit update: {"rate_limits":{"primary":{"used_percent":5,'
            '"window_minutes":300,"resets_at":4000},"secondary":{"used_percent":7,'
            '"window_minutes":10080,"resets_at":8000}}}'
        )
        snapshot = parse_usage_snapshot(body, "logs_2.sqlite", observed_at=1000)
        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.source, "logs_2.sqlite")
        self.assertEqual(snapshot.primary.remaining_percent, 95.0)

    def test_countdown_formats_short_and_week_windows(self) -> None:
        self.assertEqual(format_countdown(4661, now=1000), "01:01:01")
        self.assertEqual(format_countdown(91461, now=1000), "1天 01:07:41")


if __name__ == "__main__":
    unittest.main()
