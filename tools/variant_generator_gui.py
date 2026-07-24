#!/usr/bin/env python3
"""
Robmod Bedrock Variants — desktop GUI.

Pick packs, optionally load process_only.xlsx (texture allow-list), then run
the generator without typing CLI commands.

Build Windows .exe (from repo root):
  py -3 -m pip install pyinstaller openpyxl
  py -3 tools/build_exe.py
"""
from __future__ import annotations

import queue
import io
import queue
import sys
import threading
import traceback
from pathlib import Path
from tkinter import (
    BooleanVar,
    END,
    StringVar,
    Tk,
    filedialog,
    messagebox,
    ttk,
)
from tkinter.scrolledtext import ScrolledText

# Resolve kit/tools whether running as script or frozen exe
if getattr(sys, "frozen", False):
    # PyInstaller onefile extracts to _MEIPASS; kit ships beside the exe
    APP_DIR = Path(sys.executable).resolve().parent
    BUNDLE_DIR = Path(getattr(sys, "_MEIPASS", APP_DIR))
    TOOLS_DIR = BUNDLE_DIR
    REPO_DIR = APP_DIR
    DEFAULT_GEO = APP_DIR / "kit" / "geometries"
    DEFAULT_SCRIPT = APP_DIR / "kit" / "templates" / "main.js"
    if not DEFAULT_GEO.is_dir():
        DEFAULT_GEO = BUNDLE_DIR / "kit" / "geometries"
    if not DEFAULT_SCRIPT.is_file():
        DEFAULT_SCRIPT = BUNDLE_DIR / "kit" / "templates" / "main.js"
else:
    TOOLS_DIR = Path(__file__).resolve().parent
    REPO_DIR = TOOLS_DIR.parent
    DEFAULT_GEO = REPO_DIR / "kit" / "geometries"
    DEFAULT_SCRIPT = REPO_DIR / "kit" / "templates" / "main.js"

sys.path.insert(0, str(TOOLS_DIR))

try:
    import apply_variants as av
except ImportError:
    av = None  # type: ignore


class GuiLog(io.TextIOBase):
    """Redirect print() into the GUI log via a thread-safe queue."""

    def __init__(self, q: queue.Queue):
        super().__init__()
        self.q = q

    def write(self, s: str) -> int:
        if s:
            self.q.put(s)
        return len(s) if s else 0

    def flush(self) -> None:
        pass


class VariantApp:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("Robmod Bedrock Variants Generator")
        self.root.minsize(720, 560)
        self.root.geometry("820x640")

        self.mode = StringVar(value="addon")
        self.addon_dir = StringVar()
        self.bp_path = StringVar()
        self.rp_path = StringVar()
        self.ns = StringVar(value="mymod")
        self.pack_version = StringVar(value="1.0.0")
        self.use_process_only = BooleanVar(value=True)
        self.process_only_path = StringVar()
        self.keep_uuids = BooleanVar(value=False)
        self.busy = False
        self.log_q: queue.Queue = queue.Queue()

        self._build()
        self.root.after(100, self._drain_log)

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}
        frm = ttk.Frame(self.root, padding=12)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Generate stairs / slab / fence / wall / fence gate for Bedrock 1.26+",
            font=("", 10, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        # Mode
        mode_fr = ttk.LabelFrame(frm, text="Pack location", padding=8)
        mode_fr.grid(row=1, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Radiobutton(
            mode_fr,
            text="Unpacked addon folder (contains BP + RP)",
            variable=self.mode,
            value="addon",
            command=self._toggle_mode,
        ).grid(row=0, column=0, sticky="w")
        ttk.Radiobutton(
            mode_fr,
            text="Separate behaviour + resource packs",
            variable=self.mode,
            value="split",
            command=self._toggle_mode,
        ).grid(row=0, column=1, sticky="w", padx=12)

        self.addon_row = ttk.Frame(frm)
        self.addon_row.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Label(self.addon_row, text="Addon folder:").pack(side="left")
        ttk.Entry(self.addon_row, textvariable=self.addon_dir, width=70).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(self.addon_row, text="Browse…", command=self._browse_addon).pack(
            side="left"
        )

        self.split_row = ttk.Frame(frm)
        # packed later by mode
        r1 = ttk.Frame(self.split_row)
        r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Behaviour pack:", width=16).pack(side="left")
        ttk.Entry(r1, textvariable=self.bp_path, width=60).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(r1, text="Browse…", command=self._browse_bp).pack(side="left")
        r2 = ttk.Frame(self.split_row)
        r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Resource pack:", width=16).pack(side="left")
        ttk.Entry(r2, textvariable=self.rp_path, width=60).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(r2, text="Browse…", command=self._browse_rp).pack(side="left")

        # Namespace / version
        meta = ttk.Frame(frm)
        meta.grid(row=3, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Label(meta, text="Namespace:").pack(side="left")
        ttk.Entry(meta, textvariable=self.ns, width=20).pack(side="left", padx=6)
        ttk.Label(meta, text="Pack version:").pack(side="left", padx=(16, 0))
        ttk.Entry(meta, textvariable=self.pack_version, width=12).pack(side="left", padx=6)

        # process_only
        po = ttk.LabelFrame(
            frm,
            text="Textures only to process (recommended)",
            padding=8,
        )
        po.grid(row=4, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Checkbutton(
            po,
            text="Use a file that lists textures only to process (process_only.xlsx)",
            variable=self.use_process_only,
            command=self._toggle_process_only,
        ).pack(anchor="w")
        ttk.Label(
            po,
            text="Column A: one texture name per row, e.g. brushedbrick_001.png — "
            "not every file under /blocks.",
            wraplength=760,
        ).pack(anchor="w", pady=4)
        po_row = ttk.Frame(po)
        po_row.pack(fill="x")
        self.po_entry = ttk.Entry(po_row, textvariable=self.process_only_path, width=70)
        self.po_entry.pack(side="left", fill="x", expand=True, padx=(0, 6))
        self.po_btn = ttk.Button(po_row, text="Browse…", command=self._browse_process_only)
        self.po_btn.pack(side="left")

        ttk.Checkbutton(
            frm,
            text="Keep existing pack UUIDs (normally leave unchecked — generate fresh)",
            variable=self.keep_uuids,
        ).grid(row=5, column=0, columnspan=3, sticky="w", **pad)

        # Actions
        act = ttk.Frame(frm)
        act.grid(row=6, column=0, columnspan=3, sticky="ew", **pad)
        self.run_btn = ttk.Button(act, text="Generate variants", command=self._run)
        self.run_btn.pack(side="left")
        ttk.Button(act, text="UUID only", command=self._run_uuids_only).pack(
            side="left", padx=8
        )
        ttk.Button(act, text="Quit", command=self.root.destroy).pack(side="right")

        # Log
        ttk.Label(frm, text="Log").grid(row=7, column=0, sticky="w", padx=10)
        self.log = ScrolledText(frm, height=18, wrap="word", state="disabled")
        self.log.grid(row=8, column=0, columnspan=3, sticky="nsew", padx=10, pady=4)
        frm.rowconfigure(8, weight=1)
        frm.columnconfigure(0, weight=1)

        self._toggle_mode()
        self._toggle_process_only()
        self._log(
            "Ready. Select your pack, optionally process_only.xlsx, then Generate.\n"
            f"Kit geos: {DEFAULT_GEO}\n"
        )
        if av is None:
            self._log("ERROR: apply_variants module not found.\n")

    def _toggle_mode(self) -> None:
        if self.mode.get() == "addon":
            self.split_row.grid_forget()
            self.addon_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=4)
        else:
            self.addon_row.grid_forget()
            self.split_row.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=4)

    def _toggle_process_only(self) -> None:
        state = "normal" if self.use_process_only.get() else "disabled"
        self.po_entry.configure(state=state)
        self.po_btn.configure(state=state)

    def _browse_addon(self) -> None:
        p = filedialog.askdirectory(title="Select unpacked addon folder")
        if p:
            self.addon_dir.set(p)
            self._guess_process_only(Path(p))

    def _browse_bp(self) -> None:
        p = filedialog.askdirectory(title="Select behaviour pack folder")
        if p:
            self.bp_path.set(p)
            self._guess_process_only(Path(p).parent)

    def _browse_rp(self) -> None:
        p = filedialog.askdirectory(title="Select resource pack folder")
        if p:
            self.rp_path.set(p)

    def _browse_process_only(self) -> None:
        p = filedialog.askopenfilename(
            title="Select process_only.xlsx",
            filetypes=[
                ("Excel", "*.xlsx *.xls"),
                ("All files", "*.*"),
            ],
        )
        if p:
            self.process_only_path.set(p)

    def _guess_process_only(self, root: Path) -> None:
        if self.process_only_path.get():
            return
        for name in ("process_only.xlsx", "process_only.xls", "files to create variants.xlsx"):
            cand = root / name
            if cand.is_file():
                self.process_only_path.set(str(cand))
                self.use_process_only.set(True)
                self._toggle_process_only()
                return

    def _log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert(END, text)
        self.log.see(END)
        self.log.configure(state="disabled")

    def _drain_log(self) -> None:
        try:
            while True:
                s = self.log_q.get_nowait()
                self._log(s)
        except queue.Empty:
            pass
        self.root.after(100, self._drain_log)

    def _resolve_bp_rp(self) -> tuple[Path, Path]:
        if self.mode.get() == "addon":
            d = Path(self.addon_dir.get().strip())
            if not d.is_dir():
                raise ValueError("Select a valid addon folder.")
            return av.find_bp_rp(d)
        bp = Path(self.bp_path.get().strip())
        rp = Path(self.rp_path.get().strip())
        if not bp.is_dir() or not rp.is_dir():
            raise ValueError("Select valid BP and RP folders.")
        return bp, rp

    def _set_busy(self, busy: bool) -> None:
        self.busy = busy
        self.run_btn.configure(state="disabled" if busy else "normal")

    def _run(self) -> None:
        if self.busy:
            return
        if av is None:
            messagebox.showerror("Error", "apply_variants module missing.")
            return
        try:
            bp, rp = self._resolve_bp_rp()
        except Exception as e:
            messagebox.showerror("Pack location", str(e))
            return
        ns = self.ns.get().strip()
        if not ns:
            messagebox.showerror("Namespace", "Namespace is required (e.g. robbrblocks).")
            return

        use_po = self.use_process_only.get()
        po = self.process_only_path.get().strip()
        if use_po:
            if not po or not Path(po).is_file():
                messagebox.showerror(
                    "process_only.xlsx",
                    "Select a process_only.xlsx file that lists textures only to process,\n"
                    "or uncheck that option to process ALL full-cube blocks.",
                )
                return
        else:
            if not messagebox.askyesno(
                "Process all blocks?",
                "No texture allow-list selected.\n\n"
                "Generate variants for ALL full-cube blocks?\n"
                "(This can be very large.)",
            ):
                return

        if not messagebox.askyesno(
            "Confirm",
            f"Generate variants for namespace '{ns}'?\n\n"
            f"BP: {bp}\nRP: {rp}\n"
            + (
                f"Only textures in:\n{po}"
                if use_po
                else "Mode: ALL full-cube blocks"
            ),
        ):
            return

        argv = [
            "--bp",
            str(bp),
            "--rp",
            str(rp),
            "--ns",
            ns,
            "--pack-version",
            self.pack_version.get().strip() or "1.0.0",
            "--geo-dir",
            str(DEFAULT_GEO),
            "--script-template",
            str(DEFAULT_SCRIPT),
        ]
        if use_po:
            argv += ["--process-only", po]
        else:
            argv.append("--all")
        if self.keep_uuids.get():
            argv.append("--keep-uuids")

        self._start_worker(argv)

    def _run_uuids_only(self) -> None:
        if self.busy or av is None:
            return
        try:
            bp, rp = self._resolve_bp_rp()
        except Exception as e:
            messagebox.showerror("Pack location", str(e))
            return
        argv = [
            "--bp",
            str(bp),
            "--rp",
            str(rp),
            "--uuids-only",
            "--pack-version",
            self.pack_version.get().strip() or "1.0.0",
        ]
        self._start_worker(argv)

    def _start_worker(self, argv: list[str]) -> None:
        self._set_busy(True)
        self._log("\n" + "=" * 60 + "\nStarting…\n")
        self._log(" ".join(argv) + "\n\n")
        # Resolve kit paths at click-time (exe-safe)
        geo = DEFAULT_GEO if DEFAULT_GEO.is_dir() else (REPO_DIR / "kit" / "geometries")
        script = (
            DEFAULT_SCRIPT
            if DEFAULT_SCRIPT.is_file()
            else (REPO_DIR / "kit" / "templates" / "main.js")
        )
        # Inject absolute kit paths if caller used relative defaults
        if "--geo-dir" not in argv:
            argv = argv + ["--geo-dir", str(geo)]
        if "--script-template" not in argv and "--uuids-only" not in argv:
            argv = argv + ["--script-template", str(script)]
        self._log(f"geo-dir={geo} exists={geo.is_dir()}\n")
        self._log(f"script={script} exists={script.is_file()}\n\n")

        result: dict = {"ok": False, "msg": ""}

        def worker() -> None:
            old_out, old_err = sys.stdout, sys.stderr
            sys.stdout = sys.stderr = GuiLog(self.log_q)
            try:
                if not geo.is_dir() and "--uuids-only" not in argv and "--no-geometries" not in argv:
                    raise SystemExit(
                        f"Kit geometries missing:\n{geo}\n"
                        "Keep the kit\\ folder next to the .exe."
                    )
                av.main(argv)
                result["ok"] = True
                result["msg"] = (
                    "Finished successfully.\n\n"
                    "If /give fails in game:\n"
                    "• Copy BP and RP into development_*_packs (two separate folders)\n"
                    "• Enable BOTH packs on the world\n"
                    "• Use the namespace you typed, e.g. /give @s robbrblocks:brbrickblock_001_stairs\n"
                    "• Need Minecraft Bedrock 1.26+\n"
                    "Check the log for the exact BP/RP paths written."
                )
                self.log_q.put("\n*** Finished successfully ***\n")
            except SystemExit as e:
                code = e.code if isinstance(e.code, int) else 1
                msg = e.code if isinstance(e.code, str) else str(e)
                if code in (0, None) and not isinstance(e.code, str):
                    result["ok"] = True
                    result["msg"] = "Finished successfully. Check the log for install paths."
                    self.log_q.put("\n*** Finished successfully ***\n")
                else:
                    result["ok"] = False
                    result["msg"] = msg if isinstance(e.code, str) else f"Failed (exit {code}). See log."
                    self.log_q.put(f"\n*** FAILED: {result['msg']} ***\n")
            except Exception as e:
                result["ok"] = False
                result["msg"] = str(e)
                self.log_q.put("\n*** ERROR ***\n")
                self.log_q.put(traceback.format_exc())
            finally:
                sys.stdout, sys.stderr = old_out, old_err

                def done() -> None:
                    self._set_busy(False)
                    if result["ok"]:
                        messagebox.showinfo("Success", result["msg"])
                    else:
                        messagebox.showerror("Failed", result["msg"] or "See log panel.")

                self.root.after(0, done)

        threading.Thread(target=worker, daemon=True).start()

    def run(self) -> None:
        self.root.mainloop()


def main() -> None:
    # HiDPI-ish on Windows
    try:
        from ctypes import windll

        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    VariantApp().run()


if __name__ == "__main__":
    main()
