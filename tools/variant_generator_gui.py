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
    Canvas,
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
        self.root.title("RB Variant Maker")
        self.root.minsize(900, 700)
        # Maximize so all options stay visible (Windows)
        try:
            self.root.state("zoomed")
        except Exception:
            self.root.attributes("-fullscreen", True)
            self._fullscreen = True
        else:
            self._fullscreen = False

        self.mode = StringVar(value="addon")
        self.addon_dir = StringVar()
        self.bp_path = StringVar()
        self.rp_path = StringVar()
        self.ns = StringVar(value="mymod")
        self.original_ns = StringVar(value="")
        self.change_ns = BooleanVar(value=False)
        self.pack_version = StringVar(value="1.0.0")
        self.rename_mod = BooleanVar(value=True)
        self.mod_name = StringVar(value="")
        self.use_process_only = BooleanVar(value=True)
        self.process_only_path = StringVar()
        self.change_icon = BooleanVar(value=False)
        self.pack_icon_path = StringVar(value="")
        self.keep_uuids = BooleanVar(value=False)
        self.write_new_folder = BooleanVar(value=True)
        self.make_mcaddon = BooleanVar(value=True)
        self.output_parent = StringVar(value="")
        self.busy = False
        self.log_q: queue.Queue = queue.Queue()

        self._build()
        self.root.after(100, self._drain_log)
        self.root.bind("<Escape>", self._exit_fullscreen)

    def _exit_fullscreen(self, _event=None) -> None:
        if getattr(self, "_fullscreen", False):
            self.root.attributes("-fullscreen", False)
            self._fullscreen = False
            try:
                self.root.state("zoomed")
            except Exception:
                pass

    def _build(self) -> None:
        pad = {"padx": 10, "pady": 4}

        # Outer layout: scrollable form (top) + fixed log (bottom)
        outer = ttk.Frame(self.root, padding=8)
        outer.pack(fill="both", expand=True)

        # Scrollable options area
        canvas = Canvas(outer, highlightthickness=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        canvas.pack(side="top", fill="both", expand=True)

        frm = ttk.Frame(canvas, padding=12)
        form_window = canvas.create_window((0, 0), window=frm, anchor="nw")

        def _on_frame_configure(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def _on_canvas_configure(event) -> None:
            canvas.itemconfigure(form_window, width=event.width)

        frm.bind("<Configure>", _on_frame_configure)
        canvas.bind("<Configure>", _on_canvas_configure)

        def _on_mousewheel(event) -> None:
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        self._form_canvas = canvas

        ttk.Label(
            frm,
            text="Generate stairs / slab / fence / wall / fence gate for Bedrock 1.26+",
            font=("", 10, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", **pad)

        # Mode
        mode_fr = ttk.LabelFrame(frm, text="1. Where is your pack? (Browse to select)", padding=8)
        mode_fr.grid(row=1, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Radiobutton(
            mode_fr,
            text="Unpacked addon folder (recommended) — folder that contains both BP and RP",
            variable=self.mode,
            value="addon",
            command=self._toggle_mode,
        ).grid(row=0, column=0, columnspan=2, sticky="w")
        ttk.Radiobutton(
            mode_fr,
            text="Separate behaviour pack + resource pack folders",
            variable=self.mode,
            value="split",
            command=self._toggle_mode,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.addon_row = ttk.Frame(frm)
        self.addon_row.grid(row=2, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Label(self.addon_row, text="Addon folder:").pack(side="left")
        ttk.Entry(self.addon_row, textvariable=self.addon_dir, width=62).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(
            self.addon_row,
            text="Browse for folder…",
            command=self._browse_addon,
        ).pack(side="left")

        self.split_row = ttk.Frame(frm)
        # packed later by mode
        r1 = ttk.Frame(self.split_row)
        r1.pack(fill="x", pady=2)
        ttk.Label(r1, text="Behaviour pack:", width=16).pack(side="left")
        ttk.Entry(r1, textvariable=self.bp_path, width=55).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(r1, text="Browse…", command=self._browse_bp).pack(side="left")
        r2 = ttk.Frame(self.split_row)
        r2.pack(fill="x", pady=2)
        ttk.Label(r2, text="Resource pack:", width=16).pack(side="left")
        ttk.Entry(r2, textvariable=self.rp_path, width=55).pack(
            side="left", fill="x", expand=True, padx=6
        )
        ttk.Button(r2, text="Browse…", command=self._browse_rp).pack(side="left")

        # Detected BP/RP status (updates after Browse)
        self.detect_var = StringVar(
            value="No pack selected yet — click “Browse for folder…” and pick the unpacked addon "
            "(e.g. F:\\Grok Working\\robbrblocks)."
        )
        ttk.Label(
            frm, textvariable=self.detect_var, foreground="#1a5276", wraplength=780
        ).grid(row=3, column=0, columnspan=3, sticky="w", padx=12, pady=(0, 6))

        # Namespace / version / mod name / icon
        meta = ttk.LabelFrame(frm, text="2. Namespace, version, name & icon", padding=8)
        meta.grid(row=4, column=0, columnspan=3, sticky="ew", **pad)
        row_a = ttk.Frame(meta)
        row_a.pack(fill="x", pady=2)
        ttk.Label(row_a, text="Namespace:").pack(side="left")
        self.ns_entry = ttk.Entry(row_a, textvariable=self.ns, width=18)
        self.ns_entry.pack(side="left", padx=6)
        ttk.Label(row_a, text="Pack version:").pack(side="left", padx=(12, 0))
        ttk.Entry(row_a, textvariable=self.pack_version, width=10).pack(side="left", padx=6)
        ttk.Label(
            row_a, text="(block ids = namespace:name)", foreground="#666"
        ).pack(side="left", padx=8)
        row_ns = ttk.Frame(meta)
        row_ns.pack(fill="x", pady=2)
        ttk.Checkbutton(
            row_ns,
            text="Change namespace for entire pack (rewrites all block ids)",
            variable=self.change_ns,
            command=self._toggle_change_ns,
        ).pack(side="left")
        ttk.Label(row_ns, textvariable=self.original_ns, foreground="#666").pack(
            side="left", padx=8
        )
        row_b = ttk.Frame(meta)
        row_b.pack(fill="x", pady=4)
        ttk.Checkbutton(
            row_b,
            text="Rename mod display name (shown in Minecraft pack list)",
            variable=self.rename_mod,
            command=self._toggle_mod_name,
        ).pack(side="left")
        row_c = ttk.Frame(meta)
        row_c.pack(fill="x", pady=2)
        ttk.Label(row_c, text="Mod name:").pack(side="left")
        self.mod_name_entry = ttk.Entry(row_c, textvariable=self.mod_name, width=40)
        self.mod_name_entry.pack(side="left", padx=6, fill="x", expand=True)
        ttk.Label(
            row_c,
            text="e.g. Rob BR Blocks Variants",
            foreground="#666",
        ).pack(side="left", padx=4)
        row_icon = ttk.Frame(meta)
        row_icon.pack(fill="x", pady=4)
        ttk.Checkbutton(
            row_icon,
            text="Change pack icon",
            variable=self.change_icon,
            command=self._toggle_pack_icon,
        ).pack(side="left")
        ttk.Label(row_icon, text="(leave unchecked to keep existing pack_icon.png)").pack(
            side="left", padx=6
        )
        row_icon2 = ttk.Frame(meta)
        row_icon2.pack(fill="x", pady=2)
        ttk.Label(row_icon2, text="Icon PNG:").pack(side="left")
        self.icon_entry = ttk.Entry(row_icon2, textvariable=self.pack_icon_path, width=50)
        self.icon_entry.pack(side="left", padx=6, fill="x", expand=True)
        self.icon_btn = ttk.Button(row_icon2, text="Browse…", command=self._browse_pack_icon)
        self.icon_btn.pack(side="left")

        # Output folder (new mcaddon workspace named after namespace)
        out_fr = ttk.LabelFrame(
            frm,
            text="3. Output — new folder for the generated mcaddon",
            padding=8,
        )
        out_fr.grid(row=5, column=0, columnspan=3, sticky="ew", **pad)
        ttk.Checkbutton(
            out_fr,
            text="Write to a NEW folder named after the namespace (recommended — leaves source untouched)",
            variable=self.write_new_folder,
            command=self._toggle_output,
        ).pack(anchor="w")
        ttk.Label(
            out_fr,
            text="Creates:  {parent}/{namespace}/{namespace}_BP  +  {namespace}_RP  "
            "and optional {namespace}.mcaddon",
            foreground="#666",
            wraplength=900,
        ).pack(anchor="w", pady=2)
        out_row = ttk.Frame(out_fr)
        out_row.pack(fill="x", pady=4)
        ttk.Label(out_row, text="Parent folder:").pack(side="left")
        self.output_entry = ttk.Entry(out_row, textvariable=self.output_parent, width=55)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.output_btn = ttk.Button(
            out_row, text="Browse…", command=self._browse_output_parent
        )
        self.output_btn.pack(side="left")
        ttk.Checkbutton(
            out_fr,
            text="Also build .mcaddon zip for double-click install",
            variable=self.make_mcaddon,
        ).pack(anchor="w")
        self.output_preview = StringVar(
            value="Output preview: (select pack + namespace)"
        )
        ttk.Label(
            out_fr, textvariable=self.output_preview, foreground="#1a5276", wraplength=900
        ).pack(anchor="w", pady=4)
        self.ns.trace_add("write", lambda *_: self._update_output_preview())
        self.output_parent.trace_add("write", lambda *_: self._update_output_preview())
        self.write_new_folder.trace_add("write", lambda *_: self._update_output_preview())

        # process_only
        po = ttk.LabelFrame(
            frm,
            text="4. Textures only to process (recommended)",
            padding=8,
        )
        po.grid(row=6, column=0, columnspan=3, sticky="ew", **pad)
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
        ).grid(row=7, column=0, columnspan=3, sticky="w", **pad)

        # Actions
        act = ttk.Frame(frm)
        act.grid(row=8, column=0, columnspan=3, sticky="ew", **pad)
        self.run_btn = ttk.Button(act, text="5. Generate variants", command=self._run)
        self.run_btn.pack(side="left")
        ttk.Button(act, text="UUID only (in-place)", command=self._run_uuids_only).pack(
            side="left", padx=8
        )
        ttk.Button(act, text="Quit", command=self.root.destroy).pack(side="right")

        # Log sits below the scroll canvas (fixed)
        log_fr = ttk.LabelFrame(outer, text="Log", padding=6)
        log_fr.pack(side="bottom", fill="both", expand=False, pady=(8, 0))
        self.log = ScrolledText(log_fr, height=12, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)

        frm.columnconfigure(0, weight=1)

        self._toggle_mode()
        self._toggle_process_only()
        self._toggle_mod_name()
        self._toggle_pack_icon()
        self._toggle_output()
        self._log(
            "Ready. Window is maximized (Esc exits true-fullscreen if used).\n"
            "1. Browse for your UNPACKED addon folder (contains BP + RP).\n"
            "2. Set namespace / mod name / icon as needed.\n"
            "3. Output goes to a NEW folder named after the namespace (source left intact).\n"
            "4. Optional process_only.xlsx, then Generate.\n"
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
        self._refresh_detected()

    def _toggle_process_only(self) -> None:
        state = "normal" if self.use_process_only.get() else "disabled"
        self.po_entry.configure(state=state)
        self.po_btn.configure(state=state)

    def _toggle_mod_name(self) -> None:
        state = "normal" if self.rename_mod.get() else "disabled"
        self.mod_name_entry.configure(state=state)

    def _toggle_change_ns(self) -> None:
        # Namespace field always editable; when change_ns is on we rewrite whole pack
        if self.change_ns.get():
            self._log(
                "Namespace change ON — will rewrite all block ids from original → new namespace.\n"
            )
        else:
            self._log(
                "Namespace change OFF — new variants use the Namespace field; "
                "other blocks keep their existing ids.\n"
            )

    def _toggle_pack_icon(self) -> None:
        state = "normal" if self.change_icon.get() else "disabled"
        self.icon_entry.configure(state=state)
        self.icon_btn.configure(state=state)

    def _toggle_output(self) -> None:
        state = "normal" if self.write_new_folder.get() else "disabled"
        self.output_entry.configure(state=state)
        self.output_btn.configure(state=state)
        self._update_output_preview()

    def _browse_output_parent(self) -> None:
        initial = self.output_parent.get().strip()
        if not initial:
            initial = self.addon_dir.get().strip() or str(Path.home())
        p = filedialog.askdirectory(
            title="Select parent folder for the NEW namespace output",
            initialdir=initial if Path(initial).is_dir() else str(Path.home()),
        )
        if p:
            self.output_parent.set(p)
            self._update_output_preview()

    def _default_output_parent(self) -> Path:
        if self.mode.get() == "addon" and self.addon_dir.get().strip():
            return Path(self.addon_dir.get().strip()).resolve().parent
        if self.bp_path.get().strip():
            return Path(self.bp_path.get().strip()).resolve().parent
        return Path.home()

    def _update_output_preview(self) -> None:
        ns = self.ns.get().strip() or "{namespace}"
        if not self.write_new_folder.get():
            self.output_preview.set(
                "Output: IN PLACE (source packs will be modified directly)"
            )
            return
        parent = self.output_parent.get().strip()
        if not parent:
            parent = str(self._default_output_parent())
            # don't write back into StringVar here to avoid recursion loops on every keypress
        root = Path(parent) / ns
        self.output_preview.set(
            f"Output preview:\n"
            f"  {root}\\{ns}_BP\\\n"
            f"  {root}\\{ns}_RP\\\n"
            f"  {Path(parent) / (ns + '.mcaddon')}  (if zip enabled)"
        )

    def _browse_pack_icon(self) -> None:
        p = filedialog.askopenfilename(
            title="Select pack icon image (.png)",
            filetypes=[
                ("PNG image", "*.png"),
                ("Images", "*.png *.jpg *.jpeg"),
                ("All files", "*.*"),
            ],
        )
        if p:
            self.pack_icon_path.set(p)
            self.change_icon.set(True)
            self._toggle_pack_icon()
            self._log(f"Pack icon selected:\n  {p}\n")

    def _browse_addon(self) -> None:
        initial = self.addon_dir.get().strip() or str(Path.home())
        p = filedialog.askdirectory(
            title="Select UNPACKED addon folder (contains BP + RP subfolders)",
            initialdir=initial if Path(initial).is_dir() else str(Path.home()),
        )
        if p:
            self.addon_dir.set(p)
            self._log(f"Selected addon folder:\n  {p}\n")
            # Default output parent = same parent as the source addon
            if not self.output_parent.get().strip():
                self.output_parent.set(str(Path(p).resolve().parent))
            self._guess_process_only(Path(p))
            self._guess_namespace(Path(p))
            self._refresh_detected()
            self._update_output_preview()

    def _browse_bp(self) -> None:
        p = filedialog.askdirectory(title="Select behaviour pack folder")
        if p:
            self.bp_path.set(p)
            self._guess_process_only(Path(p).parent)
            self._guess_namespace(Path(p))
            self._refresh_detected()

    def _browse_rp(self) -> None:
        p = filedialog.askdirectory(title="Select resource pack folder")
        if p:
            self.rp_path.set(p)
            self._refresh_detected()

    def _browse_process_only(self) -> None:
        initial = self.process_only_path.get().strip()
        if not initial:
            initial = self.addon_dir.get().strip() or self.bp_path.get().strip()
        p = filedialog.askopenfilename(
            title="Select process_only.xlsx (texture list)",
            initialdir=str(Path(initial).parent) if initial else str(Path.home()),
            filetypes=[
                ("Excel", "*.xlsx *.xls"),
                ("All files", "*.*"),
            ],
        )
        if p:
            self.process_only_path.set(p)
            self._log(f"process_only list:\n  {p}\n")

    def _guess_process_only(self, root: Path) -> None:
        for name in (
            "process_only.xlsx",
            "process_only.xls",
            "files to create variants.xlsx",
        ):
            cand = root / name
            if cand.is_file():
                self.process_only_path.set(str(cand))
                self.use_process_only.set(True)
                self._toggle_process_only()
                self._log(f"Found {name} in folder — will use it as texture allow-list.\n")
                return

    def _guess_namespace(self, root: Path) -> None:
        """Try to read first block JSON identifier namespace + pack display name."""
        if av is None:
            return
        try:
            if self.mode.get() == "addon":
                bp, _rp = av.find_bp_rp(root)
            else:
                bp = Path(self.bp_path.get().strip()) if self.bp_path.get().strip() else root
            import json

            # Pack display name from BP manifest
            man_path = bp / "manifest.json"
            if man_path.is_file():
                man = json.loads(man_path.read_text(encoding="utf-8"))
                cur = (man.get("header") or {}).get("name") or ""
                if cur and not self.mod_name.get().strip():
                    if "variant" not in cur.lower():
                        self.mod_name.set(f"{cur} Variants")
                    else:
                        self.mod_name.set(cur)
                    self._log(
                        f"Current pack name: {cur} → suggested: {self.mod_name.get()}\n"
                    )
            # Namespace
            det = av.detect_pack_namespace(bp) if hasattr(av, "detect_pack_namespace") else None
            if det:
                self.original_ns.set(f"(original: {det})")
                self.ns.set(det)
                self._log(f"Detected namespace: {det}\n")
                return
            blocks = bp / "blocks"
            if not blocks.is_dir():
                return
            for f in sorted(blocks.glob("*.json"))[:20]:
                if any(
                    f.stem.endswith(s)
                    for s in ("_stairs", "_slab", "_fence", "_wall", "_gate")
                ):
                    continue
                data = json.loads(f.read_text(encoding="utf-8"))
                ident = (
                    data.get("minecraft:block", {})
                    .get("description", {})
                    .get("identifier", "")
                )
                if ":" in ident:
                    ns = ident.split(":", 1)[0]
                    self.original_ns.set(f"(original: {ns})")
                    self.ns.set(ns)
                    self._log(f"Detected namespace from {f.name}: {ns}\n")
                    return
        except Exception as e:
            self._log(f"(Could not auto-detect namespace: {e})\n")

    def _refresh_detected(self) -> None:
        """Show which BP/RP will be used after Browse."""
        if av is None:
            self.detect_var.set("ERROR: apply_variants module not loaded.")
            return
        try:
            if self.mode.get() == "addon":
                d = self.addon_dir.get().strip()
                if not d:
                    self.detect_var.set(
                        "No pack selected yet — click “Browse for folder…” and pick the "
                        "unpacked addon (e.g. F:\\Grok Working\\robbrblocks)."
                    )
                    return
                root = Path(d)
                if not root.is_dir():
                    self.detect_var.set(f"Folder not found: {d}")
                    return
                bp, rp = av.find_bp_rp(root)
            else:
                bp_s = self.bp_path.get().strip()
                rp_s = self.rp_path.get().strip()
                if not bp_s or not rp_s:
                    self.detect_var.set("Select both behaviour pack and resource pack folders.")
                    return
                bp, rp = Path(bp_s), Path(rp_s)
                if not bp.is_dir() or not rp.is_dir():
                    self.detect_var.set("BP or RP path is not a valid folder.")
                    return
            if self.write_new_folder.get():
                parent = self.output_parent.get().strip() or str(
                    self._default_output_parent()
                )
                ns = self.ns.get().strip() or "{namespace}"
                self.detect_var.set(
                    f"Source (read-only):\n  BP → {bp}\n  RP → {rp}\n"
                    f"Output (new folder):\n  {Path(parent) / ns}\\"
                )
            else:
                self.detect_var.set(
                    f"Will modify IN PLACE:\n  BP → {bp}\n  RP → {rp}"
                )
            self._log(f"Detected packs:\n  BP: {bp}\n  RP: {rp}\n")
            if not self.output_parent.get().strip():
                self.output_parent.set(str(self._default_output_parent()))
            self._update_output_preview()
        except SystemExit as e:
            self.detect_var.set(str(e.code) if e.code else str(e))
        except Exception as e:
            self.detect_var.set(f"Could not detect packs: {e}")

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

        mod_name = self.mod_name.get().strip() if self.rename_mod.get() else ""
        if self.rename_mod.get() and not mod_name:
            messagebox.showerror(
                "Mod name",
                "Enter a mod display name, or uncheck “Rename mod display name”.",
            )
            return

        if self.change_icon.get():
            icon = self.pack_icon_path.get().strip()
            if not icon or not Path(icon).is_file():
                messagebox.showerror(
                    "Pack icon",
                    "Browse for a .png icon, or uncheck “Change pack icon”.",
                )
                return
        else:
            icon = ""

        # Original namespace from detection label or pack
        orig = self.original_ns.get()
        from_ns = ""
        if orig.startswith("(original:") and orig.endswith(")"):
            from_ns = orig[len("(original:") : -1].strip()
        if self.change_ns.get() and from_ns and from_ns != ns:
            rewrite_note = f"Rewrite namespace: {from_ns} → {ns}\n"
        elif self.change_ns.get():
            rewrite_note = f"Namespace change requested (target: {ns})\n"
        else:
            rewrite_note = ""

        out_parent = self.output_parent.get().strip()
        if self.write_new_folder.get():
            if not out_parent:
                out_parent = str(self._default_output_parent())
            out_note = (
                f"NEW folder: {Path(out_parent) / ns}\n"
                f"  {ns}_BP + {ns}_RP"
                + (" + .mcaddon" if self.make_mcaddon.get() else "")
                + "\nSource packs will NOT be modified.\n"
            )
        else:
            out_note = "IN PLACE — source BP/RP will be modified.\n"

        if not messagebox.askyesno(
            "Confirm",
            f"Generate variants for namespace '{ns}'?\n\n"
            f"Source BP: {bp}\nSource RP: {rp}\n"
            + out_note
            + (f"Mod name: {mod_name}\n" if mod_name else "")
            + rewrite_note
            + (f"Pack icon: {icon}\n" if icon else "Pack icon: keep existing\n")
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
        if self.write_new_folder.get():
            argv += ["--output-dir", out_parent]
            if self.make_mcaddon.get():
                argv.append("--make-mcaddon")
        else:
            argv.append("--in-place")
        if mod_name:
            argv += ["--mod-name", mod_name]
        if self.change_ns.get():
            argv.append("--rewrite-namespace")
            if from_ns:
                argv += ["--from-ns", from_ns]
        if icon:
            argv += ["--pack-icon", icon]
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
        if self.rename_mod.get() and self.mod_name.get().strip():
            argv += ["--mod-name", self.mod_name.get().strip()]
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
