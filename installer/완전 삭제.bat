@echo off
chcp 65001 >nul
setlocal
set "HERE=%~dp0"
echo.
echo  Virtual Deck 휴대용 버전을 완전히 지웁니다.
echo  - 프로그램 (VirtualDeck.exe, _internal 폴더)
echo  - 설정 · 버튼 · 백업 · 임시 파일 (data 폴더)
echo  - 이 폴더를 가리키는 '컴퓨터 켤 때 자동 실행' 등록
echo.
echo  위치: %HERE%
echo.
choice /c YN /m "정말 지울까요? (Y = 예, N = 아니오)"
if errorlevel 2 (
  echo 취소했어요.
  pause
  exit /b
)

rem 1) 실행 중이면 끄기
taskkill /f /im VirtualDeck.exe >nul 2>nul
timeout /t 1 /nobreak >nul

rem 2) 자동 실행 등록 지우기 (이 폴더의 프로그램을 가리킬 때만)
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v VirtualDeck 2>nul | find /i "%HERE%" >nul
if not errorlevel 1 reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v VirtualDeck /f >nul 2>nul

rem 3) 예전 버전이 Windows 임시 폴더에 만들던 파일
if exist "%TEMP%\virtual_deck_ui" rmdir /s /q "%TEMP%\virtual_deck_ui"

rem 4) 프로그램 파일과 데이터 (Virtual Deck 이 만든 것만 지움 - 다른 파일은 건드리지 않음)
if exist "%HERE%VirtualDeck.exe" del /f /q "%HERE%VirtualDeck.exe"
if exist "%HERE%_internal" rmdir /s /q "%HERE%_internal"
if exist "%HERE%data" rmdir /s /q "%HERE%data"

echo.
echo  다 지웠어요. 이 창을 닫으면 삭제 파일과 빈 폴더도 정리돼요.
pause
rem 5) 마지막으로 이 삭제 파일과 (비어 있으면) 폴더 지우기
cd /d "%TEMP%"
start "" /b cmd /c "timeout /t 1 /nobreak >nul & del /f /q "%HERE%완전 삭제.bat" & rmdir "%HERE%" 2>nul"
exit /b
