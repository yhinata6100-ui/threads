@echo off
cd /d "%~dp0..\docs"
echo ダッシュボード: http://localhost:8765/
echo 終了するにはこのウィンドウを閉じるか Ctrl+C を押してください。
start "" http://localhost:8765/
python -m http.server 8765
