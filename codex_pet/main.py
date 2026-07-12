from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
from pathlib import Path

from PyQt6.QtCore import QLockFile
from PyQt6.QtWidgets import QApplication, QMessageBox

from .config import PetSettings, app_data_dir
from .window import PetWindow


def configure_logging() -> logging.Logger:
    directory = app_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("codex_kitty_pet")
    logger.setLevel(logging.INFO)
    if not logger.handlers:
        handler = logging.handlers.RotatingFileHandler(
            directory / "pet.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
    return logger


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Codex Kitty Desktop Pet")
    parser.add_argument("--demo", action="store_true", help="Cycle through all nine states")
    parser.add_argument("--idle-seconds", type=int, default=None, help="Demo-only idle timeout")
    parser.add_argument("--check", action="store_true", help="Validate the packaged runtime and exit")
    return parser.parse_args(argv)


def resource_root() -> Path:
    bundled = getattr(sys, "_MEIPASS", None)
    return Path(bundled) if bundled else Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    manifest_path = resource_root() / "assets" / "generated" / "asset-manifest.json"
    if args.check:
        if not manifest_path.exists():
            print(f"Missing asset manifest: {manifest_path}")
            return 1
        print("Codex Kitty Pet runtime check passed")
        return 0
    app = QApplication(sys.argv[:1])
    app.setApplicationName("Codex Kitty Pet")
    app.setQuitOnLastWindowClosed(False)
    logger = configure_logging()

    data_dir = app_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    lock = QLockFile(str(data_dir / "pet.lock"))
    lock.setStaleLockTime(10_000)
    if not lock.tryLock(100):
        logger.info("A desktop pet instance is already running")
        return 0

    settings = PetSettings.load()
    if args.demo and args.idle_seconds is not None:
        settings.idle_timeout_seconds = max(10, args.idle_seconds)

    if not manifest_path.exists():
        QMessageBox.critical(None, "Codex Kitty Pet", "动画资源缺失，请重新下载完整发布包。")
        return 1

    pid_path = data_dir / "pet.pid"
    pid_path.write_text(str(os.getpid()), encoding="ascii")
    window = PetWindow(settings, manifest_path, logger, demo_mode=args.demo)
    window.show()
    logger.info("Desktop pet started")
    try:
        return app.exec()
    finally:
        logger.info("Desktop pet stopped")
        try:
            pid_path.unlink(missing_ok=True)
        except OSError:
            pass
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
