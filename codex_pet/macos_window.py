"""Configure Qt's NSView-backed floating windows after native creation."""
import sys
import logging


def configure_overlay(widget):
    if sys.platform != "darwin":
        return
    from PyQt6.QtWidgets import QApplication
    if QApplication.platformName() != "cocoa":
        return
    import objc
    import AppKit
    # QWidget.winId() is an NSView pointer on Qt's Cocoa platform.
    view = objc.objc_object(c_void_p=int(widget.winId()))
    window = view.window()
    if window is None:
        return
    window.setHasShadow_(False)
    behavior = int(window.collectionBehavior())
    behavior &= ~int(AppKit.NSWindowCollectionBehaviorMoveToActiveSpace)
    behavior |= int(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces)
    behavior |= int(AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
    if hasattr(AppKit, "NSWindowCollectionBehaviorCanJoinAllApplications"):
        behavior &= ~int(AppKit.NSWindowCollectionBehaviorPrimary | AppKit.NSWindowCollectionBehaviorAuxiliary)
        behavior |= int(AppKit.NSWindowCollectionBehaviorCanJoinAllApplications)
    window.setCollectionBehavior_(behavior)

    logging.getLogger("codex_kitty_pet").info(
        "macOS overlay configured: shadow=%s behavior=%s",
        window.hasShadow(), int(window.collectionBehavior()))
