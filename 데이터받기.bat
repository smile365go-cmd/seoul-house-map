@echo off
chcp 65001 > nul
cd /d "%~dp0"
title 서울시 집값 지도 - 데이터 받기

if not exist ".venv\Scripts\python.exe" (
    echo 먼저 지도열기.bat 을 한 번 실행해 주세요.
    pause
    exit /b
)

echo 최신 실거래가를 받습니다. 5~10분 걸립니다...
".venv\Scripts\python.exe" collect.py
echo.
echo 완료. 지도 화면에서 F5(새로고침)를 누르세요.
pause
