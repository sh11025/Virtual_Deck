"""
실행 중인 프로그램 및 열려 있는 탐색기 폴더 상태 확인 모듈
ctypes 표준 라이브러리만을 사용하여 추가 패키지 없이 동작합니다.
1초 결과를 캐시하여 시스템 부담을 최소화합니다.
"""

import os
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Dict, Tuple, List

from core.app_finder import is_app_command

# Windows API 상수
TH32CS_SNAPPROCESS = 0x00000002
WM_CLOSE = 0x0010

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

class PROCESSENTRY32W(ctypes.Structure):
    _fields_ = [
        ("dwSize", wintypes.DWORD),
        ("cntUsage", wintypes.DWORD),
        ("th32ProcessID", wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_size_t),
        ("th32ModuleID", wintypes.DWORD),
        ("cntThreads", wintypes.DWORD),
        ("th32ParentProcessID", wintypes.DWORD),
        ("pcPriClassBase", wintypes.LONG),
        ("dwFlags", wintypes.DWORD),
        ("szExeFile", wintypes.WCHAR * 260),
    ]

WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetClassNameW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
user32.PostMessageW.restype = wintypes.BOOL

kernel32.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
kernel32.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
kernel32.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32FirstW.restype = wintypes.BOOL
kernel32.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(PROCESSENTRY32W)]
kernel32.Process32NextW.restype = wintypes.BOOL
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL

# 캐시: {키: (타임스탬프, 결과)}
_PROGRAM_CACHE: Dict[str, Tuple[float, Optional[bool]]] = {}
_FOLDER_CACHE: Dict[str, Tuple[float, Optional[bool]]] = {}
CACHE_TTL = 1.0


def _extract_exe_name(command: str) -> str:
    """명령줄이나 경로에서 exe 파일 이름을 추출합니다."""
    if not command:
        return ""
    cmd = command.strip().strip('"').strip("'")
    # 공백으로 분리된 인자가 있을 경우 첫 토큰 확인
    if " " in cmd and not os.path.exists(cmd):
        cmd = cmd.split()[0].strip('"').strip("'")
    base = os.path.basename(cmd)
    if not base.lower().endswith(".exe"):
        base += ".exe"
    return base.lower()


def get_running_process_names() -> List[str]:
    """현재 실행 중인 모든 프로세스의 exe 파일 이름 목록을 반환합니다."""
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value or not snapshot:
        return []

    names = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
    while success:
        names.append(entry.szExeFile.lower())
        success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))

    kernel32.CloseHandle(snapshot)
    return names


def get_pids_by_exe(exe_name: str) -> List[int]:
    """특정 exe 이름을 가진 프로세스 ID 목록을 반환합니다."""
    target = exe_name.lower()
    kernel32 = ctypes.windll.kernel32
    snapshot = kernel32.CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if snapshot == wintypes.HANDLE(-1).value or not snapshot:
        return []

    pids = []
    entry = PROCESSENTRY32W()
    entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)

    success = kernel32.Process32FirstW(snapshot, ctypes.byref(entry))
    while success:
        if entry.szExeFile.lower() == target:
            pids.append(entry.th32ProcessID)
        success = kernel32.Process32NextW(snapshot, ctypes.byref(entry))

    kernel32.CloseHandle(snapshot)
    return pids


def is_program_running(command: str) -> Optional[bool]:
    """
    실행 파일 이름(또는 경로)으로 프로세스가 실행 중인지 확인합니다.
    1초 캐시를 사용하며 실패 시 None을 반환합니다.
    """
    if not command:
        return None
    if is_app_command(command):
        return None
    exe = _extract_exe_name(command)
    if not exe:
        return None

    now = time.perf_counter()
    if exe in _PROGRAM_CACHE:
        ts, val = _PROGRAM_CACHE[exe]
        if now - ts < CACHE_TTL:
            return val

    try:
        running = exe in get_running_process_names()
        _PROGRAM_CACHE[exe] = (now, running)
        return running
    except Exception:
        return None


def _find_folder_window_hwnds(path: str) -> List[int]:
    """특정 폴더를 보고 있는 윈도우 탐색기 창들의 HWND 목록을 반환합니다."""
    if not path:
        return []
    norm_path = os.path.abspath(path).rstrip("\\/")
    folder_name = os.path.basename(norm_path).lower()
    if not folder_name:
        folder_name = norm_path.lower()
    norm_path_lower = norm_path.lower()

    hwnds = []
    def enum_windows_proc(hwnd, _):
        if not user32.IsWindowVisible(hwnd):
            return True
        cls_buf = ctypes.create_unicode_buffer(256)
        user32.GetClassNameW(hwnd, cls_buf, 256)
        if cls_buf.value in ("CabinetWClass", "ExploreWClass"):
            title_buf = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, title_buf, 512)
            title = title_buf.value.lower()
            if folder_name in title or norm_path_lower in title:
                hwnds.append(hwnd)
        return True

    user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
    return hwnds


def is_folder_open(path: str) -> Optional[bool]:
    """
    해당 폴더를 보고 있는 윈도우 탐색기 창이 열려 있는지 확인합니다.
    1초 캐시를 사용하며 실패 시 None을 반환합니다.
    """
    if not path:
        return None
    norm_path = os.path.abspath(path).rstrip("\\/")

    now = time.perf_counter()
    if norm_path in _FOLDER_CACHE:
        ts, val = _FOLDER_CACHE[norm_path]
        if now - ts < CACHE_TTL:
            return val

    try:
        hwnds = _find_folder_window_hwnds(norm_path)
        found = len(hwnds) > 0
        _FOLDER_CACHE[norm_path] = (now, found)
        return found
    except Exception:
        return None


def close_program_windows(command: str) -> int:
    """
    해당 프로그램의 최상위 창들에 WM_CLOSE 메시지를 보냅니다.
    (TerminateProcess 같은 강제 종료는 절대 하지 않음)
    닫기 메시지를 보낸 창 개수를 반환합니다.
    """
    if is_app_command(command):
        return 0
    exe = _extract_exe_name(command)
    if not exe:
        return 0

    try:
        pids = set(get_pids_by_exe(exe))
        if not pids:
            return 0

        closed_count = 0
        def enum_windows_proc(hwnd, _):
            nonlocal closed_count
            if not user32.IsWindowVisible(hwnd):
                return True
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if pid.value in pids:
                user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
                closed_count += 1
            return True

        user32.EnumWindows(WNDENUMPROC(enum_windows_proc), 0)
        # 캐시 무효화
        _PROGRAM_CACHE.pop(exe, None)
        return closed_count
    except Exception:
        return 0


def close_folder_windows(path: str) -> int:
    """
    해당 폴더를 보고 있는 탐색기 창에 WM_CLOSE 메시지를 보냅니다.
    닫기 메시지를 보낸 창 개수를 반환합니다.
    """
    if not path:
        return 0
    norm_path = os.path.abspath(path).rstrip("\\/")

    try:
        hwnds = _find_folder_window_hwnds(norm_path)
        for hwnd in hwnds:
            user32.PostMessageW(hwnd, WM_CLOSE, 0, 0)
        _FOLDER_CACHE.pop(norm_path, None)
        return len(hwnds)
    except Exception:
        return 0
