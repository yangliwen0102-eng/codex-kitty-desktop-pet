from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel

from .state_machine import PetState
from .pixel_skin import render_pixel_frames


class AnimationPlayer(QObject):
    animation_finished = pyqtSignal(str)

    def __init__(self, label: QLabel, manifest_path: Path, display_size: int) -> None:
        super().__init__(label)
        self.label = label
        self.manifest_path = manifest_path
        self.assets_root = manifest_path.parent
        self.display_size = display_size
        self.manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self._advance)
        self.current_state: PetState | None = None
        self.frame_index = 0
        self._frames: list[QPixmap] = []
        self._durations: list[int] = []
        self._loop = True

    def set_state(self, state: PetState, restart: bool = False) -> None:
        if self.current_state is state and not restart:
            return
        record = self.manifest["states"][state.value]
        self.current_state = state
        self.frame_index = 0
        self._durations = [int(value) for value in record["durationsMs"]]
        self._loop = bool(record["loop"])
        pixel_atlas = self.manifest.get("pixelAtlas")
        if pixel_atlas:
            self._frames = render_pixel_frames(self.assets_root / pixel_atlas, state, self.display_size)
            self._durations = [2000, 1000, 1000, 2000]
            if state is PetState.CLOSING:
                self._durations = [220] * len(self._frames)
            elif state is PetState.COMPLETED:
                self._durations = [500] * len(self._frames)
            self._show_current()
            return
        self._frames = [
            QPixmap(str(self.assets_root / relative_path)).scaled(
                self.display_size,
                self.display_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            for relative_path in record["frames"]
        ]
        self._show_current()

    def stop(self) -> None:
        self.timer.stop()

    def _show_current(self) -> None:
        if not self._frames or self.current_state is None:
            return
        self.label.setPixmap(self._frames[self.frame_index])
        duration = self._durations[min(self.frame_index, len(self._durations) - 1)]
        self.timer.start(max(20, duration))

    def _advance(self) -> None:
        if not self._frames or self.current_state is None:
            return
        next_index = self.frame_index + 1
        if next_index >= len(self._frames):
            if self._loop:
                next_index = 0
            else:
                finished = self.current_state
                self.animation_finished.emit(finished.value)
                return
        self.frame_index = next_index
        self._show_current()
