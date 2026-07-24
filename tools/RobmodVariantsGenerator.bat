@echo off
REM Quick launcher when Python is installed (no .exe build needed)
cd /d "%~dp0\.."
py -3 tools\variant_generator_gui.py
if errorlevel 1 (
  python tools\variant_generator_gui.py
)
if errorlevel 1 pause
