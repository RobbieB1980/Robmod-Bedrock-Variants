RB Variants — source tools (no decompile needed)
================================================

This folder ships the full editable source used to build the app.

Layout (same as the GitHub repo root for day-to-day work)
--------------------------------------------------------
  RB Variant Maker.exe   Windows GUI (no Python required to run)
  _internal\             Runtime for the .exe
  kit\                   Geometries + scripts template + simplify_walls.py
  tools\                 Full Python source (edit these)
  docs\                  Technical reference copies
  README.md              Project overview
  APPLY_TO_MCADDON.md    Unpack / apply / rezip guide
  WORKING_VARIANT_REFERENCE.md
  requirements.txt       pip deps for rebuild
  SOURCE_README.txt      This file

What to edit
------------
  tools\apply_variants.py         Block JSON generation (walls, stairs, …)
  tools\variant_generator_gui.py  Desktop GUI
  tools\run_generator.py          Interactive CLI
  kit\templates\main.js           In-game Script API (fence/wall/slab/gate)
  kit\geometries\                 Blockbench / Bedrock geo models
  kit\simplify_walls.py           Optional post-process for old packs

Rebuild the app (Windows)
-------------------------
  1. Install Python 3.12+ and open a terminal in THIS folder
     (the folder that contains tools\ and kit\).

  2. py -3 -m pip install -r requirements.txt

  3. Rebuild GUI onedir only:
       py -3 tools\build_exe.py
     Output: dist\RBVariants\

  4. Rebuild one-file installer (includes this source tree):
       py -3 tools\build_installer.py
     Output: dist\Install RB Variants.exe

Run without rebuilding
----------------------
  GUI:     double-click "RB Variant Maker.exe"
  CLI:     py -3 tools\run_generator.py
  Apply:   py -3 tools\apply_variants.py --help

GitHub
------
  https://github.com/RobbieB1980/Robmod-Bedrock-Variants

Do not decompile the .exe — edit tools\ and rebuild instead.
