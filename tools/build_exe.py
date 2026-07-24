#!/usr/bin/env python3
"""
Build RobmodVariantsGenerator.exe with PyInstaller.

Usage (from repo root):
  py -3 -m pip install pyinstaller openpyxl
  py -3 tools/build_exe.py

Output:
  dist/RobmodVariantsGenerator/
    RobmodVariantsGenerator.exe
    kit/geometries/...
    kit/templates/main.js
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TOOLS = REPO / "tools"
DIST = REPO / "dist"
BUILD = REPO / "build"
NAME = "RobmodVariantsGenerator"


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing pyinstaller…")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller", "openpyxl"]
        )

    # Clean previous
    for p in (BUILD / NAME, DIST / NAME):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    # onedir: kit folder sits next to exe (easy to update geos without rebuild)
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",  # no console flash
        "--name",
        NAME,
        "--onedir",
        "--paths",
        str(TOOLS),
        # Bundle apply_variants + openpyxl data
        "--hidden-import",
        "apply_variants",
        "--hidden-import",
        "openpyxl",
        str(TOOLS / "variant_generator_gui.py"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(REPO))

    out_dir = DIST / NAME
    # Copy kit beside exe
    kit_src = REPO / "kit"
    kit_dst = out_dir / "kit"
    if kit_dst.exists():
        shutil.rmtree(kit_dst)
    shutil.copytree(
        kit_src,
        kit_dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    # Short launcher note
    readme = out_dir / "README.txt"
    readme.write_text(
        "Robmod Bedrock Variants Generator\n"
        "=================================\n\n"
        "1. Double-click RobmodVariantsGenerator.exe\n"
        "2. Select your unpacked addon (or BP + RP folders)\n"
        "3. Enter namespace (e.g. robbrblocks)\n"
        "4. Prefer process_only.xlsx listing textures only to process\n"
        "5. Click Generate variants\n\n"
        "Keep the kit/ folder next to the .exe.\n"
        "Requires no Python install on the target PC.\n",
        encoding="utf-8",
    )

    print()
    print("Build complete:")
    print(" ", out_dir / f"{NAME}.exe")
    print(" ", kit_dst)
    print()
    print("Zip the entire folder for distribution:")
    print(f"  {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
