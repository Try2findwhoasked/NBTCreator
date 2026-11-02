@echo off
python "%~dp0scripts\nbt_detail_web.py" --mod-structures %*
if errorlevel 1 pause
