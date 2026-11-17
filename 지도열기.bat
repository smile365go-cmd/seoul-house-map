@echo off
chcp 65001 > nul
cd /d "%~dp0"
title 서울시 집값 지도

if not exist ".venv\Scripts\python.exe" (
    echo [처음 실행] 필요한 프로그램을 설치합니다. 몇 분 걸립니다...
    python -m venv .venv
    ".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
)

if not exist ".env" (
    echo.
    echo [안내] .env 파일이 없습니다.
    echo .env.example 을 복사해 이름을 .env 로 바꾸고 API 키를 넣어 주세요.
    echo.
    pause
    exit /b
)

if not exist "data\realestate.db" (
    echo [처음 실행] 실거래가 데이터를 받습니다. 5~10분 걸립니다...
    ".venv\Scripts\python.exe" collect.py
)

echo.
echo 지도를 여는 중입니다. 잠시 후 브라우저가 열립니다.
echo 이 창을 닫으면 지도도 꺼집니다.
echo.
".venv\Scripts\python.exe" -m streamlit run app.py
pause
