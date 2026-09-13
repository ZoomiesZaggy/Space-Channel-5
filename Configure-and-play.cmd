@echo off
cd /d "%~dp0"
python tools\launcher.py
if errorlevel 1 pause
