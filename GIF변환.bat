@echo off
chcp 65001 >nul
setlocal

if "%~1"=="" (
  echo.
  echo   Drag ^& drop webp / mp4 files or folders onto this .bat
  echo.
  pause
  exit /b 1
)

python "%~dp0to_gif.py" %*

echo.
pause
