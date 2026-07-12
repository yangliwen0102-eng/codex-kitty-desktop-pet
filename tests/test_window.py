from __future__ import annotations

import logging
import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402

from codex_pet.config import PetSettings  # noqa: E402
from codex_pet.state_machine import EventKind, MonitorEvent, PetState  # noqa: E402
from codex_pet.window import PetWindow  # noqa: E402
from codex_pet.usage import RateWindow, UsageSnapshot  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent


class PetWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_closing_hides_and_tray_action_restores(self) -> None:
        logger = logging.getLogger("window-test")
        logger.addHandler(logging.NullHandler())
        window = PetWindow(
            PetSettings(window_x=0, window_y=0),
            ROOT / "assets" / "generated" / "asset-manifest.json",
            logger,
            demo_mode=False,
        )
        window.monitor.stop()
        window.show()
        self.app.processEvents()

        window.begin_close_animation()
        window.player.timer.stop()
        frame_count = len(window.player._frames)
        for _ in range(frame_count):
            window.player._advance()
            window.player.timer.stop()
        self.app.processEvents()
        self.assertFalse(window.isVisible())

        window.show_pet()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        self.assertNotEqual(window.player.current_state, PetState.CLOSING)

        window._quitting = True
        window.tray.hide()
        window.close()

    def test_log_failure_requires_active_task(self) -> None:
        logger = logging.getLogger("window-failure-test")
        logger.addHandler(logging.NullHandler())
        window = PetWindow(
            PetSettings(window_x=0, window_y=0),
            ROOT / "assets" / "generated" / "asset-manifest.json",
            logger,
            demo_mode=False,
        )
        window.monitor.stop()
        window.state_machine.active_tasks.clear()
        window.state_machine.failed = False

        window._handle_monitor_event(
            MonitorEvent(EventKind.TASK_FAILED, "thread-a", reason="network_error")
        )
        self.assertFalse(window.state_machine.failed)

        window._handle_monitor_event(MonitorEvent(EventKind.TASK_STARTED, "thread-a"))
        window._handle_monitor_event(
            MonitorEvent(EventKind.TASK_FAILED, "thread-a", reason="network_error")
        )
        self.assertTrue(window.state_machine.failed)

        window._quitting = True
        window.tray.hide()
        window.close()

    def test_usage_popup_displays_remaining_limits(self) -> None:
        logger = logging.getLogger("window-usage-test")
        logger.addHandler(logging.NullHandler())
        window = PetWindow(
            PetSettings(window_x=0, window_y=0),
            ROOT / "assets" / "generated" / "asset-manifest.json",
            logger,
            demo_mode=True,
        )
        snapshot = UsageSnapshot(
            RateWindow(20, 300, 5000),
            RateWindow(40, 10080, 9000),
            "session",
            1000,
        )
        window._usage_updated(snapshot)
        self.assertIn("80%", window.usage_popup.primary_label.text())
        self.assertIn("60%", window.usage_popup.secondary_label.text())
        self.assertEqual(window.usage_popup.primary_bar.value(), 80)
        window._quitting = True
        window.tray.hide()
        window.close()


if __name__ == "__main__":
    unittest.main()
