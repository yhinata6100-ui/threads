@echo off
cd /d "%~dp0.."

where python >nul 2>nul
if errorlevel 1 (
  echo Pythonが見つかりません。https://www.python.org/ からインストールしてください。
  echo インストーラーの画面で "Add python.exe to PATH" に必ずチェックを入れてください。
  pause
  exit /b 1
)

echo 依存パッケージをインストールします...
python -m pip install -r requirements.txt

echo.
python windows\setup_env.py

pause
