@echo off
title Igris OS CLI Terminal
cd /d %~dp0

:: Optional visual style tweaks
mode con: cols=120 lines=40
color 0a

:: Launch Igris CLI with config + identity
python igris_cli_final_enhanced.py --config ../config/task_intents_gui_tags.json --identity ../config/assistant_identity.json --debug

:: Keep the terminal open after exit
echo.
echo [Press any key to exit...]
pause >nul
