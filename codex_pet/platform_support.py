"""Native activity checks; no input injection or accessibility permissions."""
import ctypes
import sys
import time

if sys.platform == "win32":
    import psutil
    import win32gui
    import win32process

class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def last_input_tick() -> int:
    if sys.platform == "darwin":
        from Quartz import CGEventSourceSecondsSinceLastEventType, kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType
        idle = CGEventSourceSecondsSinceLastEventType(kCGEventSourceStateCombinedSessionState, kCGAnyInputEventType)
        return int((time.monotonic() - idle) * 1000) // 100
    if sys.platform != "win32":
        return 0
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0
    return int(info.dwTime)


def codex_is_foreground() -> bool:
    if sys.platform == "darwin":
        from AppKit import NSWorkspace
        app = NSWorkspace.sharedWorkspace().frontmostApplication()
        return bool(app and app.bundleIdentifier() == "com.openai.codex")
    if sys.platform != "win32":
        return False
    try:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return False
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)
        process = psutil.Process(process_id)
        executable = process.exe().lower()
        name = process.name().lower()
        return "openai.codex_" in executable or name in {"codex.exe", "chatgpt.exe"} and "windowsapps" in executable
    except (psutil.Error, OSError):
        return False


