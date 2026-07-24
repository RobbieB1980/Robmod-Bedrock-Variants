#!/usr/bin/env python3
"""
Install RB Variants — one-file installer.

When frozen as "Install RB Variants.exe", extracts the bundled RBVariants
application folder next to this installer (or into the chosen directory).

Build:
  py -3 tools/build_installer.py
"""
from __future__ import annotations

import os
import shutil
import sys
import traceback
from pathlib import Path


APP_FOLDER = "RBVariants"
APP_EXE = "RB Variant Maker.exe"


def payload_root() -> Path:
    """Where PyInstaller put the embedded RBVariants payload."""
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
        # Prefer nested RBVariants/ payload
        cand = meipass / "RBVariants"
        if cand.is_dir():
            return cand
        # Or payload files at root of meipass
        if (meipass / APP_EXE).is_file() or (meipass / "kit").is_dir():
            return meipass
        return meipass
    # Dev mode: use dist/RBVariants from repo
    repo = Path(__file__).resolve().parents[1]
    return repo / "dist" / "RBVariants"


def install_target_dir() -> Path:
    """Install next to the installer .exe (or cwd when running as script)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / APP_FOLDER
    return Path.cwd() / APP_FOLDER


def copy_payload(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    # If src is the payload root containing exe/kit/_internal
    for item in src.iterdir():
        # skip installer leftovers
        name = item.name.lower()
        if name in ("install rb variants.exe",):
            continue
        target = dest / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        else:
            shutil.copy2(item, target)

    # Ensure final exe name
    wrong = dest / "RBVariantMaker.exe"
    right = dest / APP_EXE
    if wrong.is_file() and not right.is_file():
        wrong.rename(right)


def launch_app(dest: Path) -> None:
    exe = dest / APP_EXE
    if exe.is_file():
        try:
            os.startfile(str(exe))  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> int:
    # Prefer a tiny GUI if tkinter available; else console
    use_gui = True
    try:
        import tkinter as tk
        from tkinter import messagebox
    except Exception:
        use_gui = False

    src = payload_root()
    dest = install_target_dir()

    if not src.is_dir():
        msg = (
            f"Installer payload missing.\nExpected bundled app data, looked in:\n{src}\n\n"
            "Rebuild with: py -3 tools/build_installer.py"
        )
        if use_gui:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Install RB Variants", msg)
            root.destroy()
        else:
            print(msg)
        return 1

    try:
        copy_payload(src, dest)
    except Exception as e:
        msg = f"Install failed:\n{e}\n\n{traceback.format_exc()}"
        if use_gui:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Install RB Variants", msg)
            root.destroy()
        else:
            print(msg)
        return 1

    exe = dest / APP_EXE
    ok = exe.is_file()
    msg = (
        f"Installed successfully to:\n\n{dest}\n\n"
        f"App: {APP_EXE}\n\n"
        + ("Launch now?" if ok else "WARNING: app exe not found after extract.")
    )

    if use_gui:
        root = tk.Tk()
        root.withdraw()
        if ok:
            if messagebox.askyesno("Install RB Variants", msg):
                launch_app(dest)
        else:
            messagebox.showwarning("Install RB Variants", msg)
        root.destroy()
    else:
        print(msg)
        if ok:
            launch_app(dest)
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
