; ============================================================================
; Virtual Deck 설치 파일 스크립트 (Inno Setup 6)
; build_exe.py 가 자동으로 이 파일을 사용해 dist 폴더에 설치 파일을 만듭니다.
;
; - 관리자 권한 없이 내 사용자 폴더에 설치 (%LOCALAPPDATA%\Programs\Virtual Deck)
; - 시작 메뉴 / 바탕화면 바로가기, 컴퓨터 켤 때 자동 실행(선택)
; - 새 버전을 덮어 설치하면 설정과 버튼은 그대로 유지
; - 제거하면 프로그램 폴더, 설정·버튼·백업, 임시 파일, 자동 실행 등록까지 모두 삭제
; ============================================================================

#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppName "Virtual Deck"
#define MyAppExe "VirtualDeck.exe"

[Setup]
AppId={{8F3C2A51-6B7E-4D2C-9E1A-5A7B3C4D9E21}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher=Virtual Deck
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=VirtualDeck-{#MyAppVersion}-Setup
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\{#MyAppExe}
UninstallDisplayName={#MyAppName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
CloseApplications=force
RestartApplications=no

[Languages]
#ifdef NoKorean
Name: "default"; MessagesFile: "compiler:Default.isl"
#else
Name: "korean"; MessagesFile: "compiler:Languages\Korean.isl"
#endif

[Messages]
ConfirmUninstall=%1 을(를) 완전히 지울까요?%n%n프로그램과 함께 설정, 버튼, 백업, 임시 파일, 자동 실행 등록까지 모두 지워져요. (되돌릴 수 없어요)

[Tasks]
Name: "desktopicon"; Description: "바탕화면에 바로가기 만들기"; GroupDescription: "추가 작업:"
Name: "autostart"; Description: "컴퓨터를 켤 때 자동으로 실행"; GroupDescription: "추가 작업:"; Flags: unchecked

[InstallDelete]
; 새 버전을 덮어 설치할 때 예전 부품 폴더를 먼저 비워서 쓰지 않는 파일이 쌓이지 않게
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\VirtualDeck\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; 이 파일이 있으면 프로그램이 '설치판'으로 동작해서 설정을 사용자 폴더(%APPDATA%\VirtualDeck)에 저장
Source: "installed.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"
Name: "{autoprograms}\{#MyAppName} 제거"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExe}"; Tasks: desktopicon

[Registry]
; 자동 실행 (프로그램 설정창의 '자동 실행'과 같은 자리를 써서 서로 맞춰짐)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "VirtualDeck"; ValueData: """{app}\{#MyAppExe}"""; Tasks: autostart; Flags: uninsdeletevalue
; 설치 때 고르지 않았더라도, 나중에 설정창에서 켠 자동 실행을 제거할 때 지우기
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: none; ValueName: "VirtualDeck"; Flags: uninsdeletevalue

[Run]
Filename: "{app}\{#MyAppExe}"; Description: "Virtual Deck 바로 실행하기"; Flags: nowait postinstall skipifsilent

[UninstallRun]
; 실행 중이면 먼저 끄기 (파일이 잠겨서 남는 것 방지)
Filename: "{sys}\taskkill.exe"; Parameters: "/f /im {#MyAppExe}"; Flags: runhidden; RunOnceId: "StopVirtualDeck"

[UninstallDelete]
; 프로그램 폴더 (실행 중에 생긴 파일까지)
Type: filesandordirs; Name: "{app}"
; 설정, 버튼, 아이콘, 백업, 테마 배경, 임시 파일(cache)
Type: filesandordirs; Name: "{userappdata}\VirtualDeck"
; 예전 버전이 Windows 임시 폴더에 만들던 파일
Type: filesandordirs; Name: "{%TEMP}\virtual_deck_ui"

[Code]
procedure StopRunningApp();
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{sys}\taskkill.exe'), '/f /im {#MyAppExe}', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

function InitializeSetup(): Boolean;
begin
  { 설치(업데이트) 전에 실행 중인 덱을 꺼서 파일을 바꿀 수 있게 }
  StopRunningApp();
  Result := True;
end;
