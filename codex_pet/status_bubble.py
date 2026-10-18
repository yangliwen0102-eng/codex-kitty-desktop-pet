"""Quiet status card and read-only task title lookup."""
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen
from PyQt6.QtWidgets import QFrame, QLabel, QVBoxLayout


class ThreadTitles:
    def __init__(self, codex_home: Path):
        self.home = codex_home
        self._cache = {}

    def get(self, thread_id: str) -> str:
        if not thread_id:
            return "Codex"
        cached = self._cache.get(thread_id)
        if cached and time.monotonic() - cached[0] < 5:
            return cached[1]
        title = "Codex 任务"
        databases = sorted(self.home.glob("state_*.sqlite"),
                           key=lambda p: int(p.stem.split("_")[-1]) if p.stem.split("_")[-1].isdigit() else -1,
                           reverse=True)
        for database in databases:
            try:
                with closing(sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True, timeout=0.1)) as connection:
                    columns = {row[1] for row in connection.execute("PRAGMA table_info(threads)")}
                    title_column = "COALESCE(NULLIF(name, ''), title)" if "name" in columns else "title"
                    row = connection.execute(f"SELECT {title_column} FROM threads WHERE id = ?", (thread_id,)).fetchone()
                if row and row[0]:
                    title = " ".join(str(row[0]).split())[:200]
                    break
            except (sqlite3.Error, OSError):
                continue
        self._cache[thread_id] = (time.monotonic(), title)
        if len(self._cache) > 100:
            self._cache.pop(next(iter(self._cache)))
        return title


class StatusBubble(QFrame):
    clicked = pyqtSignal()

    def __init__(self):
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        if sys.platform == "darwin":
            self.setAttribute(Qt.WidgetAttribute.WA_MacAlwaysShowToolWindow, True)
        self.setFixedSize(300, 76)
        self.setObjectName("statusCard")
        self.setStyleSheet(
            "QFrame#statusCard { background: rgba(255,255,255,242); border: 1px solid #dedee5; border-radius: 24px; }"
            "QLabel { border: none; background: transparent; color: #252531; font-family: 'PingFang SC', 'Microsoft YaHei UI'; }"
            "QLabel#taskTitle { font-size: 13px; font-weight: 600; }"
            "QLabel#taskStatus { font-size: 12px; color: #737382; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(3)
        self.title = QLabel()
        self.title.setObjectName("taskTitle")
        self.status = QLabel()
        self.status.setObjectName("taskStatus")
        for label in (self.title, self.status):
            label.setTextFormat(Qt.TextFormat.PlainText)
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            layout.addWidget(label)
        self.setToolTip("点击打开 Codex，查看任务或处理授权")

    def set_status(self, title: str, status: str):
        self.title.setText(self.title.fontMetrics().elidedText(title, Qt.TextElideMode.ElideRight, self.width() - 36))
        self.status.setText(status)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#dedee5"), 1))
        painter.setBrush(QColor(255, 255, 255, 245))
        painter.drawRoundedRect(QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5), 24, 24)
