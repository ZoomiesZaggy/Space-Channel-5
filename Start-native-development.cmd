@echo off
setlocal
set "GDI=%~1"
if "%GDI%"=="" set "GDI=%SC5_GDI%"
if not "%GDI%"=="" goto explicit_disc
"%~dp0build\sc5-native-dev.exe"
goto finished
:explicit_disc
if not exist "%GDI%" (
  echo Space Channel 5 GDI was not found:
  echo   "%GDI%"
  echo Usage: %~nx0 "X:\path\Space Channel 5 (USA).gdi"
  exit /b 2
)
"%~dp0build\sc5-native-dev.exe" --gdi "%GDI%"
:finished
if errorlevel 1 pause
