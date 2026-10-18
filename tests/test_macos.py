import logging
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from codex_pet.config import app_data_dir
from codex_pet.activate import activate_codex
from codex_pet.platform_support import codex_is_foreground, last_input_tick


@unittest.skipUnless(sys.platform == "darwin", "macOS native integration")
class MacTests(unittest.TestCase):
    def test_settings_location(self):
        self.assertEqual(app_data_dir(), Path.home() / "Library/Application Support/CodexKittyPet")

    def test_native_input_check(self):
        self.assertIsInstance(last_input_tick(), int)
        self.assertIsInstance(codex_is_foreground(), bool)

    def test_activates_only_codex(self):
        unrelated = Mock()
        unrelated.bundleIdentifier.return_value = "unrelated.app"
        codex = Mock()
        codex.bundleIdentifier.return_value = "com.openai.codex"
        codex.activateWithOptions_.return_value = True
        with patch("AppKit.NSWorkspace") as workspace:
            workspace.sharedWorkspace().runningApplications.return_value = [unrelated, codex]
            self.assertTrue(activate_codex(logging.getLogger("test")))
        unrelated.activateWithOptions_.assert_not_called()
        codex.activateWithOptions_.assert_called_once()

    def test_absent_codex(self):
        with patch("AppKit.NSWorkspace") as workspace:
            workspace.sharedWorkspace().runningApplications.return_value = []
            self.assertFalse(activate_codex(logging.getLogger("test")))

    def test_overlay_disables_shadow_and_joins_spaces(self):
        from codex_pet.macos_window import configure_overlay
        from AppKit import (NSWindowCollectionBehaviorCanJoinAllSpaces,
                            NSWindowCollectionBehaviorFullScreenAuxiliary,
                            NSWindowCollectionBehaviorMoveToActiveSpace)
        native = Mock()
        native.collectionBehavior.return_value = NSWindowCollectionBehaviorMoveToActiveSpace
        view = Mock()
        view.window.return_value = native
        widget = Mock()
        widget.winId.return_value = 123
        with patch("PyQt6.QtWidgets.QApplication.platformName", return_value="cocoa"), patch("objc.objc_object", return_value=view):
            configure_overlay(widget)
        native.setHasShadow_.assert_called_once_with(False)
        flags = native.setCollectionBehavior_.call_args.args[0]
        self.assertTrue(flags & NSWindowCollectionBehaviorCanJoinAllSpaces)
        self.assertTrue(flags & NSWindowCollectionBehaviorFullScreenAuxiliary)
        self.assertFalse(flags & NSWindowCollectionBehaviorMoveToActiveSpace)
