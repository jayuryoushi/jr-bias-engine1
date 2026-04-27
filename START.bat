@echo off
title JR Bias Engine — Launcher
color 0A

echo.
echo  ============================================
echo    JR Bias Engine — Local Launcher
echo  ============================================
echo.
echo  Starting Telegram feed monitor...
start "WalterBloomberg Feed" cmd /k "cd /d %~dp0 && python tg_feed.py"

timeout /t 2 /nobreak >nul

echo  Starting proxy + dashboard server...
start "BiasEngine Proxy" cmd /k "cd /d %~dp0 && python proxy.py"

timeout /t 3 /nobreak >nul

echo  Opening dashboard in browser...
start http://localhost:8765

echo.
echo  Both services are running.
echo  Dashboard: http://localhost:8765
echo  Close the two terminal windows to stop.
echo.
pause
