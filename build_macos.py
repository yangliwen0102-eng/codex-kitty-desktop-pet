"""Build a native macOS menu bar application on the current architecture."""
import os
import platform
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def main():
    if sys.platform != "darwin":
        raise SystemExit("Build this application on macOS")
    os.chdir(ROOT)
    os.environ.setdefault("PYINSTALLER_CONFIG_DIR", str(ROOT / "build/pyinstaller-cache"))
    arch = platform.machine()
    print(f"Building macOS {arch}", flush=True)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], env=env, check=True)
    from PIL import Image
    icon = ROOT / "build" / "kitty.icns"
    icon.parent.mkdir(exist_ok=True)
    atlas = Image.open(ROOT / "assets/pixel/kitty-atlas-refined.png")
    atlas.crop((77, 77, 361, 400)).resize((512, 512), Image.Resampling.NEAREST).save(icon)
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean",
                    "--windowed", "--onedir", "--name", "CodexKittyPet",
                    "--target-arch", arch, "--icon", str(icon),
                    "--osx-bundle-identifier", "local.codexkittypet.desktop",
                    "--add-data", "assets:assets", "run_pet.pyw"], check=True)
    import plistlib
    app = ROOT / "dist/CodexKittyPet.app"
    plist = app / "Contents/Info.plist"
    info = plistlib.loads(plist.read_bytes())
    info.update(LSUIElement=True, NSHighResolutionCapable=True)
    plist.write_bytes(plistlib.dumps(info))
    subprocess.run(["codesign", "--force", "--deep", "--sign", "-", str(app)], check=True)
    subprocess.run([str(app / "Contents/MacOS/CodexKittyPet"), "--check"], check=True)
    release = ROOT / "release"
    release.mkdir(exist_ok=True)
    subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(app),
                    str(release / f"CodexKittyPet-macos-{arch}.zip")], check=True)
    print(app)

if __name__ == "__main__":
    main()
