@echo off
python "%~dp0scripts\nbt_detail_web.py" %*
if errorlevel 1 pause
