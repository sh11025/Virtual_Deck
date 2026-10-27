@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Virtual Deck 동작 테스트를 실행합니다. (실제 설정은 건드리지 않아요)
echo.
python tests\test_deck.py
if errorlevel 1 exit /b 1
echo.
python tests\test_ui_fit.py
if errorlevel 1 exit /b 1
echo.
pause
