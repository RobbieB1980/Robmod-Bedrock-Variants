#!/usr/bin/env python3
"""
Interactive master entry for Robmod-Bedrock-Variants.

Asks whether you have a process_only.xlsx (texture allow-list) before running
the generator — so you do NOT process every texture under /blocks by default.
"""
from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
APPLY = Path(__file__).resolve().parent / "apply_variants.py"


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        val = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        val = ""
    return val if val else default


def ask_yes_no(prompt: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    try:
        val = input(f"{prompt} ({d}): ").strip().lower()
    except EOFError:
        val = ""
    if not val:
        return default
    return val in ("y", "yes", "1", "true")


def main() -> int:
    print("=" * 60)
    print("  Robmod Bedrock Variants — generator")
    print("=" * 60)
    print()
    print("This tool upgrades full blocks with stairs / slab / fence / wall / gate.")
    print("By default you should limit work with process_only.xlsx (texture list).")
    print()

    mode = ask(
        "Pack location mode: (1) --addon-dir  (2) separate --bp / --rp",
        "1",
    )

    cmd: list[str] = [sys.executable, str(APPLY)]

    if mode.strip() == "2":
        bp = ask("Path to behaviour pack folder")
        rp = ask("Path to resource pack folder")
        if not bp or not rp:
            print("BP and RP paths are required.")
            return 1
        cmd += ["--bp", bp, "--rp", rp]
        search_roots = [Path(bp).resolve().parent, Path(rp).resolve().parent, Path.cwd()]
    else:
        addon = ask("Path to unpacked addon folder (contains BP + RP)")
        if not addon:
            print("addon-dir is required.")
            return 1
        cmd += ["--addon-dir", addon]
        search_roots = [Path(addon).resolve(), Path.cwd()]

    ns = ask("Namespace (block id prefix, e.g. robbrblocks)")
    if not ns:
        print("Namespace is required.")
        return 1
    cmd += ["--ns", ns]

    pack_ver = ask("Pack version to write into manifests", "1.0.0")
    cmd += ["--pack-version", pack_ver]

    if ask_yes_no("Rename the mod display name (shown in Minecraft pack list)?", default=True):
        mod_name = ask("New mod name", f"{ns} Variants")
        if mod_name:
            cmd += ["--mod-name", mod_name]

    if ask_yes_no("Change the block namespace for the entire pack?", default=False):
        old_ns = ns
        new_ns = ask("New namespace", ns)
        if new_ns and new_ns != old_ns:
            # Replace existing --ns value in cmd
            for i, c in enumerate(cmd):
                if c == "--ns" and i + 1 < len(cmd):
                    cmd[i + 1] = new_ns
                    break
            cmd += ["--from-ns", old_ns, "--rewrite-namespace"]
            ns = new_ns

    if ask_yes_no("Change the pack icon (.png)?", default=False):
        icon = ask("Path to icon PNG file")
        if icon:
            cmd += ["--pack-icon", icon]

    print()
    # ---- THE prompt the user requested ----
    use_list = ask_yes_no(
        "Did you want to include a file that lists textures only to process?",
        default=True,
    )

    if use_list:
        default_path = ""
        for root in search_roots:
            for name in (
                "process_only.xlsx",
                "process_only.xls",
                "files to create variants.xlsx",
            ):
                cand = root / name
                if cand.is_file():
                    default_path = str(cand)
                    break
            if default_path:
                break
        if not default_path:
            default_path = str(search_roots[0] / "process_only.xlsx")

        print()
        print("  Put one texture filename per row in column A, e.g.:")
        print("    brushedbrick_001.png")
        print("    brushedmetal_012.png")
        print("  Only those textures' full blocks get variants — not all of /blocks.")
        print()
        excel = ask("Path to process_only.xlsx (or other texture list)", default_path)
        p = Path(excel)
        if not p.is_file():
            print(f"ERROR: file not found: {p}")
            print("Create process_only.xlsx and run again, or answer N to process all full blocks.")
            return 1
        cmd += ["--process-only", str(p.resolve())]
        print(f"Using texture allow-list: {p.resolve()}")
    else:
        print()
        print("WARNING: No allow-list — the generator will process ALL full-cube blocks.")
        if not ask_yes_no("Continue with --all full blocks?", default=False):
            print("Cancelled.")
            return 0
        cmd.append("--all")

    if ask_yes_no("Keep existing pack UUIDs? (normally N = generate fresh UUIDs)", default=False):
        cmd.append("--keep-uuids")

    print()
    print("Command:")
    print(" ", " ".join(shlex.quote(c) for c in cmd))
    print()
    if not ask_yes_no("Run generator now?", default=True):
        print("Cancelled.")
        return 0

    print()
    rc = subprocess.call(cmd)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
