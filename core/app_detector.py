"""
현재 활성 프로그램 감지 모듈
Windows API를 활용하여 현재 사용자가 작업 중인 포커스 창의 프로세스 파일명과 창 제목을 실시간 감지합니다.
"""

import ctypes
import os
from typing import Tuple, List, Set


import sys
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes
    # Windows API 라이브러리 및 상수 정의
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    PROCESS_QUERY_INFORMATION = 0x0400

    # 64비트 Windows 호환성을 위한 함수 서명 명시
    kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel32.OpenProcess.restype = wintypes.HANDLE

    kernel32.QueryFullProcessImageNameW.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        wintypes.LPWSTR,
        ctypes.POINTER(wintypes.DWORD)
    ]
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL

    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int
    user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    user32.GetWindowTextW.restype = ctypes.c_int
    user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    user32.IsWindowVisible.argtypes = [wintypes.HWND]
    user32.IsWindowVisible.restype = wintypes.BOOL

    EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
    user32.EnumWindows.restype = wintypes.BOOL



def _is_own_pid(pid: int) -> bool:
    """주어진 PID가 Virtual Deck 자신의 프로세스인지 확인합니다."""
    return pid == os.getpid()


class AppDetector:
    """Windows 활성 윈도우 및 실행 중인 프로세스를 감지하는 클래스"""

    _own_hwnds: set = set()

    @classmethod
    def add_own_hwnd(cls, hwnd: int) -> None:
        """Virtual Deck 자신의 창(덱, 설정창 등)을 감지 대상에서 제외합니다."""
        if hwnd:
            cls._own_hwnds.add(int(hwnd))

    @staticmethod
    def get_foreground_app() -> Tuple[str, str, int]:
        """
        현재 전면(Foreground)에서 활성화된 윈도우의 실행 파일명, 창 제목, HWND를 반환합니다.
        
        Returns:
            Tuple[str, str, int]: (실행 파일명 예: 'chrome.exe', 창 제목, 윈도우 핸들)
        """
        if not IS_WINDOWS:
            return "", "", 0
        try:
            hwnd = user32.GetForegroundWindow()
            if not hwnd or int(hwnd) in AppDetector._own_hwnds:
                return "", "", 0

            # 1. 창 제목 가져오기
            length = user32.GetWindowTextLengthW(hwnd)
            window_title = ""
            if length > 0:
                title_buffer = ctypes.create_unicode_buffer(length + 1)
                user32.GetWindowTextW(hwnd, title_buffer, length + 1)
                window_title = title_buffer.value

            # 2. 프로세스 ID (PID) 가져오기
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pid.value:
                return "", window_title, hwnd
            if _is_own_pid(pid.value):
                return "", "", 0

            # 3. 프로세스 파일명 추출
            exe_name = AppDetector._get_process_name_by_pid(pid.value)
            return exe_name, window_title, hwnd

        except Exception:
            return "", "", 0

    @staticmethod
    def _get_process_name_by_pid(pid: int) -> str:
        """PID로부터 실행 파일 이름(.exe)을 반환합니다."""
        h_process = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not h_process:
            h_process = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)

        if not h_process:
            return ""

        try:
            exe_buffer = ctypes.create_unicode_buffer(1024)
            exe_size = wintypes.DWORD(1024)
            if kernel32.QueryFullProcessImageNameW(h_process, 0, exe_buffer, ctypes.byref(exe_size)):
                return os.path.basename(exe_buffer.value)
            return ""
        finally:
            kernel32.CloseHandle(h_process)

    @staticmethod
    def get_visible_windows_processes() -> List[str]:
        """
        현재 화면에 표시되어 있는 일반 GUI 프로그램들의 실행 파일명 목록을 중복 없이 반환합니다.
        
        Returns:
            List[str]: 정렬된 실행 파일명 목록 (예: ['chrome.exe', 'Code.exe', 'notepad.exe'])
        """
        processes: Set[str] = set()
        if not IS_WINDOWS:
            return []

        # 주요 추천 기본 프로그램 목록 (기본적으로 상단에 편리하게 제공)
        common_candidates = [
            "chrome.exe", "msedge.exe", "whale.exe", "firefox.exe",
            "notepad.exe", "Code.exe", "Photoshop.exe", "Premiere.exe",
            "Discord.exe", "spotify.exe", "obs64.exe", "calc.exe"
        ]

        EnumWindowsProc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HWND,
            wintypes.LPARAM
        )

        def enum_windows_callback(hwnd, lparam):
            if not user32.IsWindowVisible(hwnd):
                return True
            if hwnd and int(hwnd) in AppDetector._own_hwnds:
                return True

            length = user32.GetWindowTextLengthW(hwnd)
            if length == 0:
                return True

            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value:
                name = AppDetector._get_process_name_by_pid(pid.value)
                if name and name.lower() not in (
                    "explorer.exe", "shellexperiencehost.exe", "searchhost.exe",
                    "applicationframehost.exe", "systemsettings.exe"
                ):
                    processes.add(name)

            return True

        cb = EnumWindowsProc(enum_windows_callback)
        user32.EnumWindows(cb, 0)

        # 현재 열려있는 프로세스 목록 + 추천 후보군 중 중복 제거 합치기
        result_set = processes.union(set(common_candidates))
        return sorted(list(result_set), key=lambda s: s.lower())
