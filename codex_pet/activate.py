"""Bring an existing Codex desktop window forward without sending input."""
import logging
import ctypes

import psutil
import sys

if sys.platform == "win32":
    import win32con
    import win32gui
    import win32process


def activate_codex(logger: logging.Logger) -> bool:
    if sys.platform == "darwin":
        from AppKit import NSWorkspace, NSApplicationActivateIgnoringOtherApps
        for app in NSWorkspace.sharedWorkspace().runningApplications():
            if app.bundleIdentifier() == "com.openai.codex":
                return bool(app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps))
        logger.warning("No running Codex application found")
        return False
    if sys.platform != "win32":
        return False
    return _activate_windows(logger)


def _activate_windows(logger: logging.Logger) -> bool:
    candidates = []

    def collect(hwnd, _):
        if not win32gui.IsWindowVisible(hwnd) or not win32gui.GetWindowText(hwnd):
            return
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            path = process.exe().lower()
            name = process.name().lower()
            if name in {"codex.exe", "chatgpt.exe"} and (
                "\\windowsapps\\openai.codex_" in path or "\\openai\\codex\\" in path
            ):
                candidates.append(hwnd)
        except (psutil.Error, OSError):
            pass

    try:
        win32gui.EnumWindows(collect, None)
        if not candidates:
            logger.warning("No Codex desktop window found")
            return False
        hwnd = candidates[0]
        if win32gui.IsIconic(hwnd):
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
        foreground = win32gui.GetForegroundWindow()
        foreground_thread = win32process.GetWindowThreadProcessId(foreground)[0] if foreground else 0
        current_thread = ctypes.windll.kernel32.GetCurrentThreadId()
        attached = False
        try:
            if foreground_thread and foreground_thread != current_thread:
                attached = bool(ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, True))
            win32gui.BringWindowToTop(hwnd)
            if win32gui.GetForegroundWindow() != hwnd:
                win32gui.SetForegroundWindow(hwnd)
        finally:
            if attached:
                ctypes.windll.user32.AttachThreadInput(current_thread, foreground_thread, False)
        logger.info("Codex window activated")
        return True
    except Exception:
        logger.exception("Could not activate Codex window")
        return False
