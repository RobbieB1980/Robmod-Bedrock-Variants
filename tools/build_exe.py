#!/usr/bin/env python3
"""
Build RB Variant Maker (onedir app) with PyInstaller.

Usage (from repo root):
  py -3 -m pip install pyinstaller openpyxl
  py -3 tools/build_exe.py

Output:
  dist/RBVariants/
    RB Variant Maker.exe
    kit/
    _internal/
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
APP_NAME = "RB Variant Maker"
OUT_FOLDER = "RBVariants"  # folder name users keep


def main() -> int:
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("Installing pyinstaller…")
        subprocess.check_call(
            [sys.executable, "-m", "pip", "install", "pyinstaller", "openpyxl"]
        )

    # Clean previous
    for p in (BUILD / APP_NAME, DIST / OUT_FOLDER, DIST / APP_NAME):
        if p.exists():
            shutil.rmtree(p, ignore_errors=True)

    # PyInstaller forbids some chars in --name for work paths; use safe build name
    build_name = "RBVariantMaker"

    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        build_name,
        "--onedir",
        "--paths",
        str(TOOLS),
        "--hidden-import",
        "apply_variants",
        "--hidden-import",
        "openpyxl",
        str(TOOLS / "variant_generator_gui.py"),
    ]
    print("Running:", " ".join(cmd))
    subprocess.check_call(cmd, cwd=str(REPO))

    built = DIST / build_name
    if not built.is_dir():
        raise SystemExit(f"Build folder missing: {built}")

    # Assemble final folder: dist/RBVariants/
    out_dir = DIST / OUT_FOLDER
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Rename exe to "RB Variant Maker.exe"
    src_exe = built / f"{build_name}.exe"
    if not src_exe.is_file():
        raise SystemExit(f"Built exe missing: {src_exe}")

    # Copy entire onedir contents
    for item in built.iterdir():
        dest = out_dir / item.name
        if item.is_dir():
            shutil.copytree(item, dest)
        else:
            shutil.copy2(item, dest)

    # Rename exe
    final_exe = out_dir / f"{APP_NAME}.exe"
    staged = out_dir / f"{build_name}.exe"
    if staged.is_file():
        if final_exe.exists():
            final_exe.unlink()
        staged.rename(final_exe)

    # kit beside exe
    kit_src = REPO / "kit"
    kit_dst = out_dir / "kit"
    if kit_dst.exists():
        shutil.rmtree(kit_dst)
    shutil.copytree(
        kit_src,
        kit_dst,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
    )

    readme = out_dir / "README.txt"
    readme.write_text(
        "RB Variant Maker\n"
        "================\n\n"
        "1. Double-click \"RB Variant Maker.exe\"\n"
        "2. Browse to your unpacked addon folder\n"
        "3. Set namespace / mod name / icon as needed\n"
        "4. Prefer process_only.xlsx for texture allow-list\n"
        "5. Generate → creates a NEW folder named after the namespace\n\n"
        "Keep this entire RBVariants folder together (kit + _internal required).\n"
        "No Python install needed.\n",
        encoding="utf-8",
    )

    print()
    print("App build complete:")
    print(" ", final_exe)
    print(" ", kit_dst)
    print()
    print(f"Folder ready for packaging: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
