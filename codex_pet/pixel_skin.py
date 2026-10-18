"""Render generated pixel atlas poses on a stable, low-resolution animation grid."""
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPixmap

from .state_machine import PetState


# Explicit source rectangles include every accessory; generated rows are not equal.
POSES = {
    PetState.IDLE: (77, 77, 284, 323),
    PetState.HOVER: (472, 72, 305, 328),
    PetState.DRAGGING: (874, 74, 354, 324),
    PetState.WORKING: (74, 470, 286, 322),
    PetState.BORED: (474, 479, 327, 316),
    PetState.PERMISSION: (899, 456, 327, 336),
    PetState.COMPLETED: (41, 857, 351, 337),
    PetState.FAILED: (489, 902, 285, 286),
    PetState.CLOSING: (929, 865, 246, 329),
}


def render_pixel_frames(atlas_path: Path, state: PetState, size: int) -> list[QPixmap]:
    atlas = QPixmap(str(atlas_path))
    if atlas.isNull():
        raise ValueError(f"Cannot load pixel atlas: {atlas_path}")
    pose = atlas.copy(*POSES[state]).scaled(
        112, 112, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.FastTransformation
    )
    frames = []
    offsets = [(0, 0), (0, 0), (0, -1), (0, 0)]
    opacities = [1.0] * len(offsets)
    if state is PetState.DRAGGING:
        offsets = [(0, 0)] * 4
    if state is PetState.CLOSING:
        offsets = [(0, 0)] * 5
        opacities = [1.0, 0.8, 0.5, 0.2, 0.0]
    for (dx, dy), opacity in zip(offsets, opacities):
        canvas = QPixmap(144, 144)
        canvas.fill(Qt.GlobalColor.transparent)
        painter = QPainter(canvas)
        painter.setOpacity(opacity)
        painter.drawPixmap((144 - pose.width()) // 2 + dx, 133 - pose.height() + dy, pose)
        painter.end()
        frames.append(canvas.scaled(size, size, Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.FastTransformation))
    return frames
