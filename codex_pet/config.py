from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path


APP_NAME = "CodexKittyPet"


def app_data_dir() -> Path:
    base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base / APP_NAME


@dataclass
class PetSettings:
    idle_timeout_seconds: int = 600
    display_size: int = 144
    window_x: int | None = None
    window_y: int | None = None
    codex_home: str = str(Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")))
    auto_start: bool = True

    @classmethod
    def load(cls, path: Path | None = None) -> "PetSettings":
        settings_path = path or app_data_dir() / "settings.json"
        if not settings_path.exists():
            return cls()
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return cls()
        defaults = asdict(cls())
        defaults.update({key: value for key, value in data.items() if key in defaults})
        defaults["idle_timeout_seconds"] = max(10, int(defaults["idle_timeout_seconds"]))
        defaults["display_size"] = min(320, max(96, int(defaults["display_size"])))
        return cls(**defaults)

    def save(self, path: Path | None = None) -> None:
        settings_path = path or app_data_dir() / "settings.json"
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = settings_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary.replace(settings_path)
