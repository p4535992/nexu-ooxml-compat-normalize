@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_windows_portable.ps1"
if errorlevel 1 pause
