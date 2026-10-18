import os
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PyQt6.QtWidgets import QApplication
from codex_pet.pixel_skin import render_pixel_frames
from codex_pet.state_machine import PetState
from codex_pet.animation import AnimationPlayer
from PyQt6.QtWidgets import QLabel


class PixelSkinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.atlas = Path(__file__).resolve().parent.parent / "assets/pixel/kitty-atlas-refined.png"

    def test_all_states_render_at_small_size_with_transparent_margins(self):
        for state in PetState:
            with self.subTest(state=state):
                frames = render_pixel_frames(self.atlas, state, 144)
                self.assertGreater(len(frames), 1)
                for frame in frames:
                    self.assertEqual((frame.width(), frame.height()), (144, 144))
                    self.assertTrue(frame.hasAlphaChannel())
                    self.assertEqual(frame.toImage().pixelColor(0, 0).alpha(), 0)

    def test_leaving_animation_finishes_transparent(self):
        last = render_pixel_frames(self.atlas, PetState.CLOSING, 144)[-1].toImage()
        self.assertTrue(all(last.pixelColor(x, y).alpha() == 0 for x in range(144) for y in range(144)))

    def test_quiet_motion_stays_within_one_pixel_and_takes_six_seconds(self):
        frames = render_pixel_frames(self.atlas, PetState.IDLE, 144)
        bounds = []
        for frame in frames:
            image = frame.toImage()
            occupied = [(x, y) for y in range(144) for x in range(144)
                        if image.pixelColor(x, y).alpha() > 128]
            bounds.append((min(x for x, y in occupied), min(y for x, y in occupied)))
        self.assertEqual(len({x for x, y in bounds}), 1)
        self.assertLessEqual(max(y for x, y in bounds) - min(y for x, y in bounds), 1)
        label = QLabel()
        player = AnimationPlayer(label, self.atlas.parent.parent / "generated/asset-manifest.json", 144)
        player.set_state(PetState.IDLE)
        self.assertEqual(sum(player._durations), 6000)
        player.stop()
