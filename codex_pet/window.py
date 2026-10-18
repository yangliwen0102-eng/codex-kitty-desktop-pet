from __future__ import annotations

import ctypes
import logging
import time
from pathlib import Path

import psutil
import win32gui
import win32process
from PyQt6.QtCore import QPoint, QSize, Qt, QTimer
from PyQt6.QtGui import QAction, QCloseEvent, QCursor, QEnterEvent, QIcon, QMouseEvent
from PyQt6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QMenu,
    QProgressBar,
    QStyle,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from .animation import AnimationPlayer
from .activate import activate_codex
from .codex_monitor import CodexMonitor
from .config import PetSettings
from .state_machine import MonitorEvent, PetState, PetStateMachine
from .usage import UsageSnapshot, format_countdown
from .status_bubble import StatusBubble, ThreadTitles


class UsagePopup(QFrame):
    def __init__(self) -> None:
        super().__init__(None)
        self.snapshot: UsageSnapshot | None = None
        self.setWindowFlags(
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.WindowTransparentForInput
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(264, 150)
        self.setStyleSheet(
            "QFrame { background: rgba(255,255,255,224); border: 1px solid rgba(35,28,26,78); "
            "border-radius: 6px; } "
            "QLabel { color: #231c1a; background: transparent; border: none; font-size: 12px; } "
            "QLabel#title { font-size: 13px; font-weight: 600; } "
            "QLabel#source { color: #666; font-size: 10px; } "
            "QProgressBar { min-height: 8px; max-height: 8px; border: none; border-radius: 4px; "
            "background: rgba(35,28,26,28); text-align: center; color: transparent; } "
            "QProgressBar::chunk { border-radius: 4px; background: #0075c2; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 11, 14, 10)
        layout.setSpacing(4)
        self.title = QLabel("Codex 剩余用量")
        self.title.setObjectName("title")
        self.primary_label = QLabel("5 小时窗口：等待本地记录...")
        self.primary_bar = QProgressBar()
        self.primary_bar.setRange(0, 100)
        self.primary_bar.setValue(0)
        self.secondary_label = QLabel("7 天窗口：等待本地记录...")
        self.secondary_bar = QProgressBar()
        self.secondary_bar.setRange(0, 100)
        self.secondary_bar.setValue(0)
        self.source_label = QLabel("正在读取 Codex 会话与日志")
        self.source_label.setObjectName("source")
        for widget in (
            self.title,
            self.primary_label,
            self.primary_bar,
            self.secondary_label,
            self.secondary_bar,
            self.source_label,
        ):
            layout.addWidget(widget)

    def set_snapshot(self, snapshot: UsageSnapshot) -> None:
        self.snapshot = snapshot
        self.refresh()

    def refresh(self) -> None:
        if self.snapshot is None:
            return
        primary = self.snapshot.primary
        secondary = self.snapshot.secondary
        self.primary_label.setText(
            f"5 小时  {primary.remaining_percent:.0f}% 剩余  ·  刷新 {format_countdown(primary.resets_at)}"
        )
        self.secondary_label.setText(
            f"7 天  {secondary.remaining_percent:.0f}% 剩余  ·  刷新 {format_countdown(secondary.resets_at)}"
        )
        self.primary_bar.setValue(round(primary.remaining_percent))
        self.secondary_bar.setValue(round(secondary.remaining_percent))
        source = "实时会话记录" if self.snapshot.source == "session" else "本地日志兜底"
        self.source_label.setText(f"数据来源：{source}")


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]


def last_input_tick() -> int:
    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        return 0
    return int(info.dwTime)


def codex_is_foreground() -> bool:
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


class PetWindow(QWidget):
    def __init__(
        self,
        settings: PetSettings,
        manifest_path: Path,
        logger: logging.Logger,
        demo_mode: bool = False,
    ) -> None:
        super().__init__()
        self.settings = settings
        self.logger = logger
        self.demo_mode = demo_mode
        self.state_machine = PetStateMachine()
        self._quitting = False
        self._drag_offset: QPoint | None = None
        self._press_position: QPoint | None = None
        self._did_drag = False
        self._last_input_tick = last_input_tick()
        self._demo_index = -1
        self._demo_states = list(PetState)
        self._exit_after_closing = False
        self._pending_visual_state: PetState | None = None
        self._pending_visual_since = 0.0
        self.usage_popup = UsagePopup()
        self.status_bubble = StatusBubble()
        self.status_bubble.clicked.connect(self.open_codex)
        self.thread_titles = ThreadTitles(Path(settings.codex_home))
        self._latest_thread = ""
        self._last_terminal_text = ""
        self._last_terminal_at = 0.0
        self._status_enabled = True

        self.window_size = settings.display_size + 24
        self.setFixedSize(self.window_size, self.window_size)
        self.setWindowTitle("Codex Kitty Pet")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setMouseTracking(True)
        self.setToolTip("单击打开 Codex · 拖动移动 Kitty · 右键打开菜单")

        self.sprite = QLabel(self)
        self.sprite.setGeometry(12, 12, settings.display_size, settings.display_size)
        self.sprite.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sprite.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.close_button = QToolButton(self)
        self.close_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_TitleBarCloseButton)
        )
        self.close_button.setIconSize(QSize(14, 14))
        self.close_button.setGeometry(self.window_size - 34, 6, 28, 28)
        self.close_button.setToolTip("隐藏宠物")
        self.close_button.setStyleSheet(
            "QToolButton { background: rgba(255,255,255,220); border: 1px solid rgba(20,20,20,90); "
            "border-radius: 10px; padding: 3px; } "
            "QToolButton:hover { background: rgba(255,235,238,245); border-color: rgba(210,20,45,180); }"
        )
        self.close_button.clicked.connect(self.begin_close_animation)
        self.close_button.hide()

        self.close_hide_timer = QTimer(self)
        self.close_hide_timer.setSingleShot(True)
        self.close_hide_timer.setInterval(450)
        self.close_hide_timer.timeout.connect(self._hide_close_button_if_outside)

        self.player = AnimationPlayer(self.sprite, manifest_path, settings.display_size)
        self.player.animation_finished.connect(self._animation_finished)

        self.monitor = CodexMonitor(Path(settings.codex_home), logger)
        self.monitor.event_received.connect(self._handle_monitor_event)
        self.monitor.health_changed.connect(self._monitor_health_changed)
        self.monitor.usage_updated.connect(self._usage_updated)

        self.state_timer = QTimer(self)
        self.state_timer.setInterval(200)
        self.state_timer.timeout.connect(self._refresh_state)
        self.state_timer.start()

        self.input_timer = QTimer(self)
        self.input_timer.setInterval(1000)
        self.input_timer.timeout.connect(self._poll_codex_input)
        self.input_timer.start()

        self.usage_timer = QTimer(self)
        self.usage_timer.setInterval(1000)
        self.usage_timer.timeout.connect(self.usage_popup.refresh)
        self.usage_timer.start()

        self.tray = QSystemTrayIcon(self)
        self.player.set_state(PetState.IDLE)
        self.tray.setIcon(QIcon(self.sprite.pixmap()))
        self.tray.setToolTip("Codex Kitty Pet")
        self.tray.setContextMenu(self._make_tray_menu())
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self._restore_position()
        self.player.set_state(PetState.IDLE)
        if demo_mode:
            self._start_demo()
        else:
            self.monitor.start()
        QTimer.singleShot(
            1200,
            lambda: self.logger.info(
                "Window ready: visible=%s handle=%s position=%s,%s",
                self.isVisible(),
                int(self.winId()),
                self.x(),
                self.y(),
            ),
        )

    def _make_tray_menu(self) -> QMenu:
        menu = QMenu()
        show_action = QAction("显示宠物", menu)
        show_action.triggered.connect(self.show_pet)
        menu.addAction(show_action)
        open_action = QAction("打开 Codex / 查看授权", menu)
        open_action.triggered.connect(self.open_codex)
        menu.addAction(open_action)
        status_action = QAction("显示任务状态气泡", menu)
        status_action.setCheckable(True)
        status_action.setChecked(True)
        status_action.toggled.connect(self._toggle_status_bubble)
        menu.addAction(status_action)
        self.monitor_action = QAction("Codex 监听：正常", menu)
        self.monitor_action.setEnabled(False)
        menu.addAction(self.monitor_action)
        menu.addSeparator()
        hide_action = QAction("隐藏宠物（播放离开动画）", menu)
        hide_action.triggered.connect(self.begin_close_animation)
        menu.addAction(hide_action)
        menu.addSeparator()
        quit_action = QAction("彻底退出（播放离开动画）", menu)
        quit_action.triggered.connect(self.begin_exit_animation)
        menu.addAction(quit_action)
        return menu

    def _restore_position(self) -> None:
        if self.settings.window_x is not None and self.settings.window_y is not None:
            target = QPoint(self.settings.window_x, self.settings.window_y)
        else:
            screen = QApplication.primaryScreen()
            geometry = screen.availableGeometry()
            target = QPoint(
                geometry.right() - self.width() - 24,
                geometry.bottom() - self.height() - 24,
            )
        self.move(self._clamp_position(target))

    def _clamp_position(self, target: QPoint) -> QPoint:
        screen = QApplication.screenAt(target + QPoint(self.width() // 2, self.height() // 2))
        screen = screen or QApplication.primaryScreen()
        area = screen.availableGeometry()
        return QPoint(
            max(area.left(), min(target.x(), area.right() - self.width() + 1)),
            max(area.top(), min(target.y(), area.bottom() - self.height() + 1)),
        )

    def _refresh_state(self) -> None:
        self._update_status_bubble()
        if self.demo_mode:
            return
        self.state_machine.update_boredom(time.time(), self.settings.idle_timeout_seconds)
        desired_state = self.state_machine.state
        if self.player.current_state is desired_state:
            self._pending_visual_state = None
            return
        interaction_states = {PetState.HOVER, PetState.DRAGGING, PetState.CLOSING}
        if desired_state not in interaction_states and self.player.current_state not in interaction_states:
            now = time.monotonic()
            if self._pending_visual_state is not desired_state:
                self._pending_visual_state = desired_state
                self._pending_visual_since = now
                return
            if now - self._pending_visual_since < 1.2:
                return
        self._pending_visual_state = None
        if self.player.current_state is not desired_state:
            self.logger.info("Pet state: %s", desired_state.value)
        self.player.set_state(desired_state)

    def _handle_monitor_event(self, event: MonitorEvent) -> None:
        if (
            event.kind.value == "task_failed"
            and event.reason in {"network_error", "terminal_error"}
            and not self.state_machine.active_tasks
        ):
            self.logger.info("Ignored %s outside an active task", event.reason)
            return
        self.logger.info("Codex event: %s reason=%s", event.kind.value, event.reason or "-")
        if event.thread_id and event.thread_id != "global":
            self._latest_thread = event.thread_id
        terminal = {"task_completed": "任务已完成", "task_aborted": "任务已停止", "task_failed": "任务出错，请查看 Codex"}
        if event.kind.value in terminal:
            self._last_terminal_text = terminal[event.kind.value]
            self._last_terminal_at = time.monotonic()
        self.state_machine.handle(event)
        self._refresh_state()

    def _monitor_health_changed(self, healthy: bool) -> None:
        self.monitor_action.setText("Codex 监听：正常" if healthy else "Codex 监听：降级")

    def _toggle_status_bubble(self, enabled: bool) -> None:
        self._status_enabled = enabled
        self._update_status_bubble()

    def _update_status_bubble(self) -> None:
        if not self.isVisible() or not self._status_enabled or self._quitting or self.state_machine.closing:
            self.status_bubble.hide()
            return
        thread = self._latest_thread
        pending = list(self.state_machine.pending_approvals.values())
        active = self.state_machine.active_tasks
        if pending:
            thread = thread if thread in pending else pending[-1]
            status = "等待确认 · 点击查看 Codex"
        elif active:
            thread = thread if thread in active else sorted(active)[0]
            status = "正在处理任务"
            if len(active) > 1:
                status += f" · 共 {len(active)} 个任务运行中"
        elif self._last_terminal_text and time.monotonic() - self._last_terminal_at < 8:
            status = self._last_terminal_text
        else:
            status = "当前空闲"
        if not self.monitor._healthy:
            status = "状态监听暂不可用"
        self.status_bubble.set_status(self.thread_titles.get(thread), status)
        area = (QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()).availableGeometry()
        x = self.x() + self.width() // 2 - self.status_bubble.width() // 2
        y = self.y() - self.status_bubble.height() - 8
        if y < area.top():
            y = self.y() + self.height() + 8
        x = max(area.left(), min(x, area.right() - self.status_bubble.width() + 1))
        y = max(area.top(), min(y, area.bottom() - self.status_bubble.height() + 1))
        self.status_bubble.move(x, y)
        self.status_bubble.show()

    def hideEvent(self, event) -> None:
        self.status_bubble.hide()
        super().hideEvent(event)

    def _poll_codex_input(self) -> None:
        tick = last_input_tick()
        if tick != self._last_input_tick:
            self._last_input_tick = tick
            if codex_is_foreground():
                self.state_machine.mark_activity()

    def enterEvent(self, event: QEnterEvent) -> None:  # noqa: N802 - Qt API
        self.close_hide_timer.stop()
        self.close_button.show()
        self._show_usage_popup()
        if not self.demo_mode:
            self.state_machine.set_hovered(True)
            self._refresh_state()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt API
        self.close_hide_timer.start()
        self.usage_popup.hide()
        if not self.demo_mode:
            self.state_machine.set_hovered(False)
            self._refresh_state()
        super().leaveEvent(event)

    def _hide_close_button_if_outside(self) -> None:
        local_cursor = self.mapFromGlobal(QCursor.pos())
        hover_zone = self.rect().adjusted(-10, -10, 10, 10)
        if hover_zone.contains(local_cursor) or self.close_button.underMouse():
            self.close_hide_timer.start()
            return
        self.close_button.hide()

    def _usage_updated(self, snapshot: UsageSnapshot) -> None:
        self.usage_popup.set_snapshot(snapshot)
        self.logger.info(
            "Usage updated: source=%s primary_remaining=%.0f%% secondary_remaining=%.0f%%",
            snapshot.source,
            snapshot.primary.remaining_percent,
            snapshot.secondary.remaining_percent,
        )

    def _show_usage_popup(self) -> None:
        screen = QApplication.screenAt(self.frameGeometry().center()) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        gap = 8
        left_x = self.x() - self.usage_popup.width() - gap
        right_x = self.x() + self.width() + gap
        x = left_x if left_x >= area.left() else right_x
        x = max(area.left(), min(x, area.right() - self.usage_popup.width() + 1))
        y = max(area.top(), min(self.y() + 30, area.bottom() - self.usage_popup.height() + 1))
        self.usage_popup.move(x, y)
        self.usage_popup.refresh()
        self.usage_popup.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            self._press_position = event.globalPosition().toPoint()
            self._did_drag = False
            event.accept()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self.tray.contextMenu().popup(QCursor.pos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            if not self._did_drag:
                if (event.globalPosition().toPoint() - self._press_position).manhattanLength() < QApplication.startDragDistance():
                    event.accept()
                    return
                self._did_drag = True
                if not self.demo_mode:
                    self.state_machine.set_dragging(True)
                    self._refresh_state()
            self.move(self._clamp_position(event.globalPosition().toPoint() - self._drag_offset))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt API
        if event.button() == Qt.MouseButton.LeftButton and self._drag_offset is not None:
            clicked = not self._did_drag
            self._drag_offset = None
            self._press_position = None
            if not self.demo_mode:
                self.state_machine.set_dragging(False)
                self._refresh_state()
            if clicked:
                self.open_codex()
            else:
                self.settings.window_x = self.x()
                self.settings.window_y = self.y()
                self.settings.save()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def open_codex(self) -> None:
        self.usage_popup.hide()
        if not activate_codex(self.logger):
            self.tray.showMessage("Codex Kitty", "请先打开 Codex 桌面应用，再点击 Kitty。", QSystemTrayIcon.MessageIcon.Information, 4000)

    def begin_close_animation(self) -> None:
        self._exit_after_closing = False
        self.close_button.hide()
        self.usage_popup.hide()
        if self.demo_mode:
            self.player.set_state(PetState.CLOSING, restart=True)
            return
        self.state_machine.begin_closing()
        self._refresh_state()

    def begin_exit_animation(self) -> None:
        self._exit_after_closing = True
        self.close_button.hide()
        self.usage_popup.hide()
        self.state_machine.begin_closing()
        self._refresh_state()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt API
        if self._quitting:
            event.accept()
            return
        event.ignore()
        self.begin_close_animation()

    def _animation_finished(self, state_value: str) -> None:
        state = PetState(state_value)
        if self.demo_mode:
            if state is PetState.CLOSING:
                self.show()
            return
        if state is PetState.CLOSING:
            self.state_machine.finish_animation(state)
            if self._exit_after_closing:
                self.quit_pet()
            else:
                self.hide()
            return
        self.state_machine.finish_animation(state)
        self._refresh_state()

    def show_pet(self) -> None:
        self._exit_after_closing = False
        if not self.demo_mode:
            self.state_machine.cancel_closing()
        self.show()
        self.raise_()
        self.player.set_state(self.state_machine.state if not self.demo_mode else PetState.IDLE, restart=True)

    def quit_pet(self) -> None:
        self._quitting = True
        self.status_bubble.close()
        self.usage_popup.close()
        self.monitor.stop()
        self.player.stop()
        self.tray.hide()
        self.close()
        QApplication.quit()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in {
            QSystemTrayIcon.ActivationReason.DoubleClick,
            QSystemTrayIcon.ActivationReason.Trigger,
        }:
            self.show_pet()

    def _start_demo(self) -> None:
        self.demo_timer = QTimer(self)
        self.demo_timer.setInterval(3000)
        self.demo_timer.timeout.connect(self._advance_demo)
        self.demo_timer.start()
        self._advance_demo()

    def _advance_demo(self) -> None:
        self._demo_index = (self._demo_index + 1) % len(self._demo_states)
        state = self._demo_states[self._demo_index]
        if not self.isVisible():
            self.show()
        self.player.set_state(state, restart=True)
