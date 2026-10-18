import logging
import sys
import unittest
from unittest.mock import Mock, patch

from codex_pet.activate import activate_codex


@unittest.skipUnless(sys.platform == "win32", "Windows native activation")
class ActivateTests(unittest.TestCase):
    @patch("codex_pet.activate.win32process")
    @patch("codex_pet.activate.win32gui")
    @patch("codex_pet.activate.psutil.Process")
    def test_restores_codex_window_and_ignores_unrelated_apps(self, process, gui, processes):
        gui.EnumWindows.side_effect = lambda callback, arg: [callback(11, arg), callback(22, arg)]
        gui.IsWindowVisible.return_value = True
        gui.GetWindowText.return_value = "ChatGPT"
        gui.GetForegroundWindow.return_value = 0
        processes.GetWindowThreadProcessId.side_effect = [(1, 100), (1, 200)]
        process.side_effect = [
            Mock(**{"exe.return_value": r"C:\unrelated\ChatGPT.exe", "name.return_value": "ChatGPT.exe"}),
            Mock(**{"exe.return_value": r"C:\Program Files\WindowsApps\OpenAI.Codex_1\app\ChatGPT.exe", "name.return_value": "ChatGPT.exe"}),
        ]
        gui.IsIconic.return_value = True
        self.assertTrue(activate_codex(logging.getLogger("test")))
        gui.ShowWindow.assert_called_once()
        gui.SetForegroundWindow.assert_called_once_with(22)

    @patch("codex_pet.activate.win32gui")
    def test_absent_window_returns_false(self, gui):
        self.assertFalse(activate_codex(logging.getLogger("test")))
        gui.SetForegroundWindow.assert_not_called()
