@echo off
setlocal
set "GDI=%~1"
if "%GDI%"=="" set "GDI=%SC5_GDI%"
if not exist "%GDI%" (
  echo Space Channel 5 GDI was not found:
  echo   "%GDI%"
  echo Usage: %~nx0 "X:\path\Space Channel 5 (USA).gdi"
  exit /b 2
)
"%~dp0build\sc5-native-dev.exe" --gdi "%GDI%"
if errorlevel 1 pause
