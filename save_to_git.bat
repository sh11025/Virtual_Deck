@echo off
chcp 65001 >nul
cd /d "%~dp0"
where git >nul 2>nul
if errorlevel 1 (
  echo Git 이 설치되어 있지 않아요.
  echo https://git-scm.com 에서 설치한 뒤 다시 실행해 주세요.
  pause
  exit /b
)
if not exist ".git" (
  echo 처음이라 Git 저장소를 만듭니다.
  git init
  git branch -M main
)
git config user.name >nul 2>nul || git config user.name "Virtual Deck"
git config user.email >nul 2>nul || git config user.email "virtualdeck@localhost"
git add -A
set /p MSG=이번에 바꾼 내용을 짧게 적어 주세요 (그냥 Enter = 날짜로 저장): 
if "%MSG%"=="" set MSG=작업 저장 %date% %time:~0,5%
git commit -m "%MSG%"
echo.
echo 깃허브에 올리는 중...
git push
echo.
echo 최근 기록:
git log --oneline -5
pause

