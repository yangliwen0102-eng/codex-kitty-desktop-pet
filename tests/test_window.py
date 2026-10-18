from __future__ import annotations

import logging
import os
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import QPointF, Qt, QEvent
from PyQt6.QtGui import QMouseEvent

from codex_pet.config import PetSettings  # noqa: E402
from codex_pet.state_machine import EventKind, MonitorEvent, PetState  # noqa: E402
from codex_pet.window import PetWindow  # noqa: E402
from codex_pet.usage import RateWindow, UsageSnapshot  # noqa: E402


ROOT = Path(__file__).resolve().parent.parent


class PetWindowTests(unittest.TestCase):
    def test_brief_monitor_states_do_not_change_pose(self) -> None:
        # Isolate timing assertions from this machine's running Codex tasks.
        with patch("codex_pet.window.CodexMonitor.start"):
            window = PetWindow(PetSettings(), ROOT / "assets/generated/asset-manifest.json",
                               logging.getLogger("quiet-state-test"))
        window.monitor.stop()
        window.state_machine.active_tasks.clear()
        window.state_machine.pending_approvals.clear()
        window.state_machine.celebrating = False
        window.state_machine.failed = False
        window.player.set_state(PetState.IDLE, restart=True)
        with patch("codex_pet.window.time.monotonic", return_value=100.0) as clock:
            window._handle_monitor_event(MonitorEvent(EventKind.TASK_STARTED, "quiet-thread"))
            self.assertEqual(window.player.current_state, PetState.IDLE)
            clock.return_value = 101.3
            window._refresh_state()
            self.assertEqual(window.player.current_state, PetState.WORKING)
            window._handle_monitor_event(MonitorEvent(EventKind.APPROVAL_REQUESTED, "quiet-thread", call_id="brief"))
            clock.return_value = 101.5
            window._handle_monitor_event(MonitorEvent(EventKind.APPROVAL_RESOLVED, "quiet-thread", call_id="brief"))
            self.assertEqual(window.player.current_state, PetState.WORKING)
        window.quit_pet()

    def test_click_opens_chat_but_drag_only_moves_pet(self) -> None:
        window = PetWindow(PetSettings(window_x=50, window_y=50),
                           ROOT / "assets/generated/asset-manifest.json",
                           logging.getLogger("click-test"), demo_mode=True)
        def event(kind, position, button, buttons):
            return QMouseEvent(kind, QPointF(30, 30), QPointF(position), button, buttons, Qt.KeyboardModifier.NoModifier)
        left = Qt.MouseButton.LeftButton
        with patch.object(window, "open_codex") as opened, patch.object(window.settings, "save") as saved:
            window.mousePressEvent(event(QEvent.Type.MouseButtonPress, QPointF(80, 80), left, left))
            window.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease, QPointF(80, 80), left, Qt.MouseButton.NoButton))
            opened.assert_called_once()
            saved.assert_not_called()
            opened.reset_mock()
            window.mousePressEvent(event(QEvent.Type.MouseButtonPress, QPointF(80, 80), left, left))
            window.mouseMoveEvent(event(QEvent.Type.MouseMove, QPointF(180, 180), Qt.MouseButton.NoButton, left))
            window.mouseReleaseEvent(event(QEvent.Type.MouseButtonRelease, QPointF(180, 180), left, Qt.MouseButton.NoButton))
            opened.assert_not_called()
            saved.assert_called_once()
        window.quit_pet()

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
