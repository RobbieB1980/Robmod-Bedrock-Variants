#!/usr/bin/env python3
"""
Build the one-file installer: "Install RB Variants.exe"

1. Builds the onedir app into dist/RBVariants/ (RB Variant Maker.exe + kit)
2. Packages that folder into a single-file installer that extracts to RBVariants/

Usage (repo root):
  py -3 tools/build_installer.py

Output:
  dist/Install RB Variants.exe   ← single file to distribute
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
DIST = REPO / "dist"
APP_FOLDER = "RBVariants"
INSTALLER_BUILD_NAME = "InstallRBVariants"
INSTALLER_FINAL_NAME = "Install RB Variants.exe"


def main() -> int:
    # 1) Build the app onedir
    print("=== Step 1/2: Build RB Variant Maker (onedir) ===")
    subprocess.check_call([sys.executable, str(TOOLS / "build_exe.py")], cwd=str(REPO))

    payload = DIST / APP_FOLDER
    if not payload.is_dir():
        raise SystemExit(f"Missing app folder: {payload}")
    exe = payload / "RB Variant Maker.exe"
    if not exe.is_file():
        raise SystemExit(f"Missing app exe: {exe}")
    if not (payload / "kit" / "geometries").is_dir():
        raise SystemExit(f"Missing kit/geometries under {payload}")
    if not (payload / "tools" / "apply_variants.py").is_file():
        raise SystemExit(
            f"Missing tools/apply_variants.py under {payload} "
            "(source must ship inside the installer)"
        )

    # 2) One-file installer embedding the whole RBVariants tree
    print("=== Step 2/2: Build one-file installer ===")
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller", "openpyxl"]
        )

    # Windows PyInstaller add-data: source;dest
    # Embed as RBVariants/... inside _MEIPASS
    sep = ";" if sys.platform.startswith("win") else ":"
    add_data = f"{payload}{sep}RBVariants"

    # Clean old installer artifacts
    for p in (
        DIST / INSTALLER_BUILD_NAME,
        DIST / f"{INSTALLER_BUILD_NAME}.exe",
        REPO / "build" / INSTALLER_BUILD_NAME,
    ):
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.is_file():
            p.unlink(missing_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--onefile",
        "--name",
        INSTALLER_BUILD_NAME,
        "--add-data",
        add_data,
        str(TOOLS / "install_rb_variants.py"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(REPO))

    built = DIST / f"{INSTALLER_BUILD_NAME}.exe"
    if not built.is_file():
        raise SystemExit(f"Installer exe missing: {built}")

    final = DIST / INSTALLER_FINAL_NAME
    if final.exists():
        final.unlink()
    built.rename(final)

    # Convenience copies (best-effort)
    for home_copy in (
        Path(r"F:\Grok Working") / INSTALLER_FINAL_NAME,
        Path(r"H:\GrokBuild Master Folder\Completed Projects\Bedrock")
        / INSTALLER_FINAL_NAME,
    ):
        try:
            home_copy.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(final, home_copy)
            print(f"Copied installer → {home_copy}")
        except Exception as e:
            print(f"(Could not copy installer to {home_copy}: {e})")

    # Also refresh the extracted app folder used for day-to-day work
    app_home = Path(
        r"H:\GrokBuild Master Folder\Completed Projects\Bedrock\RBVariants"
    )
    # Tooling names to refresh (preserve user packs e.g. Rob's Block)
    refresh_names = (
        "RB Variant Maker.exe",
        "README.txt",
        "SOURCE_README.txt",
        "README.md",
        "APPLY_TO_MCADDON.md",
        "WORKING_VARIANT_REFERENCE.md",
        "requirements.txt",
        ".gitignore",
        "kit",
        "tools",
        "docs",
        "_internal",
        "Install RB Variants.exe",
    )
    try:
        if app_home.exists():
            for name in refresh_names:
                src = payload / name
                if name == "Install RB Variants.exe":
                    src = final
                dst = app_home / name
                if not src.exists():
                    continue
                if dst.is_dir():
                    shutil.rmtree(dst)
                elif dst.is_file():
                    dst.unlink()
                if src.is_dir():
                    shutil.copytree(src, dst)
                else:
                    shutil.copy2(src, dst)
            print(f"Refreshed app tooling + source → {app_home}")
    except Exception as e:
        print(f"(Could not refresh {app_home}: {e})")

    size_mb = final.stat().st_size / (1024 * 1024)
    print()
    print("ONE-FILE INSTALLER READY:")
    print(f"  {final}")
    print(f"  Size: {size_mb:.1f} MB")
    print()
    print("User steps:")
    print(f'  1. Double-click "{INSTALLER_FINAL_NAME}"')
    print(f'  2. It creates folder "{APP_FOLDER}" next to the installer')
    print(f'  3. Runs / contains "RB Variant Maker.exe"')
    print(f'  4. Full editable source is inside {APP_FOLDER}\\tools\\')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
