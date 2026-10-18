import logging
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from codex_pet.status_bubble import ThreadTitles
from codex_pet.config import PetSettings
from codex_pet.state_machine import EventKind, MonitorEvent
from codex_pet.window import PetWindow


class StatusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_title_lookup_is_read_only_and_prefers_custom_name(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "state_5.sqlite"
            with sqlite3.connect(database) as connection:
                connection.execute("CREATE TABLE threads (id TEXT, title TEXT, name TEXT)")
                connection.execute("INSERT INTO threads VALUES ('task', 'Original title', 'My renamed chat')")
            connection.close()
            before = database.read_bytes()
            titles = ThreadTitles(Path(directory))
            self.assertEqual(titles.get("task"), "My renamed chat")
            self.assertEqual(titles.get("missing"), "Codex 任务")
            self.assertEqual(database.read_bytes(), before)

    def test_task_status_priority_and_hiding(self):
        root = Path(__file__).resolve().parent.parent
        window = PetWindow(PetSettings(), root / "assets/generated/asset-manifest.json", logging.getLogger("status-test"), demo_mode=True)
        window.monitor.stop()
        window.show()
        with patch.object(window.thread_titles, "get", side_effect=lambda value: "Chat " + value):
            window._handle_monitor_event(MonitorEvent(EventKind.TASK_STARTED, "a"))
            self.assertIn("正在处理", window.status_bubble.status.text())
            window._handle_monitor_event(MonitorEvent(EventKind.APPROVAL_REQUESTED, "a", call_id="approval"))
            window._handle_monitor_event(MonitorEvent(EventKind.TASK_STARTED, "b"))
            self.assertIn("等待确认", window.status_bubble.status.text())
            self.assertEqual(window.status_bubble.title.text(), "Chat a")
            window._handle_monitor_event(MonitorEvent(EventKind.APPROVAL_RESOLVED, "a", call_id="approval"))
            self.assertIn("2 个任务", window.status_bubble.status.text())
            window._handle_monitor_event(MonitorEvent(EventKind.TASK_COMPLETED, "a"))
            self.assertIn("正在处理", window.status_bubble.status.text())
            window._handle_monitor_event(MonitorEvent(EventKind.TASK_COMPLETED, "b"))
            self.assertEqual(window.status_bubble.status.text(), "任务已完成")
            window.hide()
            self.assertFalse(window.status_bubble.isVisible())
        window.quit_pet()
