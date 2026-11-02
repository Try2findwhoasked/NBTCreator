@echo off
call npm --prefix "%~dp0" start -- %*
if errorlevel 1 pause
