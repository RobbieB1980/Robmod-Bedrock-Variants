#!/usr/bin/env python3
"""
Build RB Variant Maker (onedir app) with PyInstaller.

Usage (from repo root — or from an installed RBVariants folder that contains tools/ + kit/):
  py -3 -m pip install -r requirements.txt
  py -3 tools/build_exe.py

Output:
  dist/RBVariants/
    RB Variant Maker.exe
    kit/                 geometries + script template
    tools/               full editable Python source (no decompile needed)
    docs/                technical reference
    _internal/
    SOURCE_README.txt    how to edit + rebuild
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

IGNORE = shutil.ignore_patterns(
    "__pycache__",
    "*.pyc",
    "*.pyo",
    ".DS_Store",
    "Thumbs.db",
)

# Root-level docs / meta shipped next to the exe so the install is self-contained
ROOT_SHIP_FILES = (
    "README.md",
    "APPLY_TO_MCADDON.md",
    "WORKING_VARIANT_REFERENCE.md",
    "requirements.txt",
    "SOURCE_README.txt",
    ".gitignore",
)


def _copytree(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst, ignore=IGNORE)


def ship_source_tree(out_dir: Path) -> None:
    """Copy editable source + docs into the distribution folder."""
    # tools/ — full generator, GUI, build scripts
    tools_src = REPO / "tools"
    if not tools_src.is_dir():
        raise SystemExit(f"Missing tools source: {tools_src}")
    _copytree(tools_src, out_dir / "tools")

    # kit/ — geometries + templates (also used at generate time by the GUI)
    kit_src = REPO / "kit"
    if not kit_src.is_dir():
        raise SystemExit(f"Missing kit: {kit_src}")
    _copytree(kit_src, out_dir / "kit")

    # docs/
    docs_src = REPO / "docs"
    if docs_src.is_dir():
        _copytree(docs_src, out_dir / "docs")

    for name in ROOT_SHIP_FILES:
        src = REPO / name
        if src.is_file():
            shutil.copy2(src, out_dir / name)


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

    # Editable source + kit + docs (self-contained; no decompile needed later)
    ship_source_tree(out_dir)

    readme = out_dir / "README.txt"
    readme.write_text(
        "RB Variant Maker\n"
        "================\n\n"
        "1. Double-click \"RB Variant Maker.exe\"\n"
        "2. Browse to your unpacked addon folder\n"
        "3. Set namespace / mod name / icon as needed\n"
        "4. Prefer process_only.xlsx for texture allow-list\n"
        "5. Generate → creates a NEW folder named after the namespace\n\n"
        "Keep this entire RBVariants folder together "
        "(kit + _internal required for the .exe).\n"
        "No Python install needed to RUN the app.\n\n"
        "Source tools (edit without decompiling)\n"
        "---------------------------------------\n"
        "  tools\\     Python generator, GUI, build scripts\n"
        "  kit\\       geometries + scripts template\n"
        "  docs\\      technical reference\n"
        "  SOURCE_README.txt  how to rebuild after edits\n\n"
        "Rebuild after source changes (Python 3.12+):\n"
        "  py -3 -m pip install -r requirements.txt\n"
        "  py -3 tools\\build_exe.py\n"
        "  py -3 tools\\build_installer.py\n",
        encoding="utf-8",
    )

    print()
    print("App build complete:")
    print(" ", final_exe)
    print(" ", out_dir / "kit")
    print(" ", out_dir / "tools")
    print(" ", out_dir / "SOURCE_README.txt")
    print()
    print(f"Folder ready for packaging: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
