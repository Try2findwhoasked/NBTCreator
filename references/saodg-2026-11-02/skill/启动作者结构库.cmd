@echo off
python "%~dp0scripts\nbt_detail_web.py" --library %*
if errorlevel 1 pause
