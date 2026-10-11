@echo off
chcp 65001 >nul
title 블로그 글쓰기 도우미
cd /d "%~dp0"

rem ---- 1. Python 찾기 (py 런처 우선, 없으면 python) ----
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (python --version >nul 2>nul && set "PY=python")
if not defined PY (
    echo.
    echo [!] Python이 설치되어 있지 않습니다.
    echo     열리는 페이지에서 Python을 설치하세요.
    echo     설치 첫 화면에서 "Add Python to PATH" 를 꼭 체크하세요.
    echo     설치가 끝나면 이 파일을 다시 더블클릭하세요.
    start "" https://www.python.org/downloads/
    pause
    exit /b 1
)

rem ---- 2. 처음 한 번만: 전용 환경 만들기 ----
if not exist ".venv\Scripts\python.exe" (
    echo 처음 실행이라 준비 중입니다. 1~3분 걸려요...
    %PY% -m venv .venv || goto :fail
)

rem ---- 3. 필요한 패키지 설치/업데이트 ----
echo 필요한 구성요소를 확인하는 중...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt || goto :fail

rem ---- 4. 실행 (몇 초 뒤 브라우저가 열립니다) ----
echo.
echo  블로그 글쓰기 도우미를 시작합니다.
echo  브라우저가 자동으로 열립니다: http://localhost:8501
echo  끝낼 때는 이 검은 창을 닫으세요.
echo.
start "" cmd /c "timeout /t 5 >nul & start http://localhost:8501"
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
goto :eof

:fail
echo.
echo [!] 준비 중 오류가 났습니다. 위 메시지를 캡처해서 알려 주세요.
pause
exit /b 1
