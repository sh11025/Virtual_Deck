"""
Windows 전용 기능 모음
키 입력 보내기, 창 포커스 관련 설정, 화면 캡처 제외 등 Windows 운영체제 기능을 다룹니다.
Windows가 아닌 환경(테스트용)에서는 모든 함수가 안전하게 아무 일도 하지 않습니다.
"""

import sys
import time
import ctypes
from typing import Iterable, List

IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    ULONG_PTR = ctypes.c_size_t

    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [("dx", wintypes.LONG), ("dy", wintypes.LONG),
                    ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
                    ("time", wintypes.DWORD), ("dwExtraInfo", ULONG_PTR)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [("wVk", wintypes.WORD), ("wScan", wintypes.WORD),
                    ("dwFlags", wintypes.DWORD), ("time", wintypes.DWORD),
                    ("dwExtraInfo", ULONG_PTR)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [("uMsg", wintypes.DWORD), ("wParamL", wintypes.WORD),
                    ("wParamH", wintypes.WORD)]

    class _INPUTUNION(ctypes.Union):
        _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _fields_ = [("type", wintypes.DWORD), ("u", _INPUTUNION)]

    user32.SendInput.argtypes = [wintypes.UINT, ctypes.POINTER(INPUT), ctypes.c_int]
    user32.SendInput.restype = wintypes.UINT
    user32.GetForegroundWindow.restype = wintypes.HWND
    user32.SetForegroundWindow.argtypes = [wintypes.HWND]
    user32.IsWindow.argtypes = [wintypes.HWND]
    # 32비트 파이썬에는 ...LongPtr 함수가 없어서 대신 ...Long 을 씁니다.
    _GetWindowLong = getattr(user32, "GetWindowLongPtrW", None) or user32.GetWindowLongW
    _SetWindowLong = getattr(user32, "SetWindowLongPtrW", None) or user32.SetWindowLongW
    _GetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int]
    _GetWindowLong.restype = ctypes.c_ssize_t
    _SetWindowLong.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]
    _SetWindowLong.restype = ctypes.c_ssize_t
    user32.SetWindowDisplayAffinity.argtypes = [wintypes.HWND, wintypes.DWORD]
    user32.SetWindowDisplayAffinity.restype = wintypes.BOOL
    user32.MapVirtualKeyW.argtypes = [wintypes.UINT, wintypes.UINT]
    user32.MapVirtualKeyW.restype = wintypes.UINT
    user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
    user32.SetWindowPos.restype = wintypes.BOOL

INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004

GWL_EXSTYLE = -20
WS_EX_NOACTIVATE = 0x08000000
WS_EX_TOOLWINDOW = 0x00000080
WDA_NONE = 0x0
WDA_EXCLUDEFROMCAPTURE = 0x11

HWND_TOPMOST = -1
HWND_NOTOPMOST = -2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
SWP_FRAMECHANGED = 0x0020

VK_RETURN = 0x0D


def _key_input(vk: int, up: bool, extended: bool):
    flags = KEYEVENTF_KEYUP if up else 0
    if extended:
        flags |= KEYEVENTF_EXTENDEDKEY
    scan = user32.MapVirtualKeyW(vk, 0) & 0xFF
    inp = INPUT(type=INPUT_KEYBOARD)
    inp.u.ki = KEYBDINPUT(wVk=vk, wScan=scan, dwFlags=flags, time=0, dwExtraInfo=0)
    return inp


def send_key_combo(vk_codes: List[int], extended: Iterable[int]) -> bool:
    """여러 키를 순서대로 누르고, 반대 순서로 뗍니다. (예: Ctrl → Shift → S)"""
    if not IS_WINDOWS or not vk_codes:
        return False
    ext = set(extended)
    seq = [_key_input(vk, False, vk in ext) for vk in vk_codes]
    seq += [_key_input(vk, True, vk in ext) for vk in reversed(vk_codes)]
    arr = (INPUT * len(seq))(*seq)
    sent = user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
    return sent == len(seq)


def send_text(text: str, cancel_check=None) -> bool:
    """
    글자를 직접 입력합니다(한글, 이모지 포함). 클립보드를 쓰지 않아서
    사용자가 복사해 둔 내용이 지워지지 않고, 작업 도중에도 안전합니다.
    """
    if not IS_WINDOWS:
        return False
    for ch in text:
        if cancel_check and cancel_check():
            return False
        if ch == "\n":
            send_key_combo([VK_RETURN], [])
        elif ch == "\r":
            continue
        else:
            # 이모지처럼 2칸짜리 글자는 두 조각으로 나눠 보냅니다.
            data = ch.encode("utf-16-le")
            units = [int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
            seq = []
            for u in units:
                for up in (False, True):
                    inp = INPUT(type=INPUT_KEYBOARD)
                    flags = KEYEVENTF_UNICODE | (KEYEVENTF_KEYUP if up else 0)
                    inp.u.ki = KEYBDINPUT(wVk=0, wScan=u, dwFlags=flags, time=0, dwExtraInfo=0)
                    seq.append(inp)
            arr = (INPUT * len(seq))(*seq)
            user32.SendInput(len(seq), arr, ctypes.sizeof(INPUT))
        time.sleep(0.004)
    return True


def get_foreground_window() -> int:
    if not IS_WINDOWS:
        return 0
    try:
        return int(user32.GetForegroundWindow() or 0)
    except Exception:
        return 0


def focus_window(hwnd: int) -> bool:
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        if not user32.IsWindow(hwnd):
            return False
        return bool(user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


def make_no_activate(hwnd: int) -> None:
    """창을 눌러도 포커스를 빼앗지 않게 설정합니다. (실제 스트림덱처럼 동작)"""
    if not IS_WINDOWS or not hwnd:
        return
    try:
        style = _GetWindowLong(hwnd, GWL_EXSTYLE)
        _SetWindowLong(hwnd, GWL_EXSTYLE, style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW)
        user32.SetWindowPos(hwnd, 0, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOZORDER | SWP_FRAMECHANGED)
    except Exception:
        pass


def keep_topmost(hwnd: int, enable: bool = True) -> bool:
    """Windows 레벨에서 HWND_TOPMOST Z-Order를 유지/강제합니다."""
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        h_insert_after = HWND_TOPMOST if enable else HWND_NOTOPMOST
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        return bool(user32.SetWindowPos(hwnd, h_insert_after, 0, 0, 0, 0, flags))
    except Exception:
        return False


def bring_to_front(hwnd: int, keep_on_top: bool) -> bool:
    """창을 활성화하지 않고 다른 창들 맨 앞으로 올립니다."""
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        flags = SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE
        ok = bool(user32.SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, flags))
        if not keep_on_top:
            ok = bool(user32.SetWindowPos(hwnd, HWND_NOTOPMOST, 0, 0, 0, 0, flags)) and ok
        return ok
    except Exception:
        return False


def is_visible_on_top(hwnd: int) -> bool:
    """창의 가운데 지점에서 맨 앞에 보이는 창이 이 창(또는 이 창의 자식/소유 창)인지."""
    if not IS_WINDOWS or not hwnd:
        return True
    try:
        from ctypes import wintypes
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return True
        pt = wintypes.POINT((rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2)
        top = user32.WindowFromPoint(pt)
        if not top:
            return True
        root = user32.GetAncestor(top, 2)   # GA_ROOT
        return int(root or top) == int(hwnd)
    except Exception:
        return True



def set_exclude_from_capture(hwnd: int, exclude: bool) -> bool:
    """
    화면 캡처에서 이 창을 빼도록 설정합니다(Windows 10 2004 이상).
    덱 뒤의 바탕화면을 캡처해서 '유리 너머로 비치는' 효과를 만들 때 사용합니다.
    성공하면 True.
    """
    if not IS_WINDOWS or not hwnd:
        return False
    try:
        return bool(user32.SetWindowDisplayAffinity(hwnd, WDA_EXCLUDEFROMCAPTURE if exclude else WDA_NONE))
    except Exception:
        return False




def play_alert() -> None:
    """알림 소리 (Windows 기본 소리)"""
    if IS_WINDOWS:
        try:
            import winsound
            winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
            return
        except Exception:
            pass
    try:
        from PySide6.QtWidgets import QApplication
        QApplication.beep()
    except Exception:
        pass


def register_hotkey(hwnd: int, hotkey_id: int, modifiers: int, vk: int) -> bool:
    if not IS_WINDOWS:
        return False
    try:
        return bool(user32.RegisterHotKey(hwnd, hotkey_id, modifiers | 0x4000, vk))  # 0x4000 = 꾹 눌러도 반복 안 함
    except Exception:
        return False


def unregister_hotkey(hwnd: int, hotkey_id: int) -> None:
    if not IS_WINDOWS:
        return
    try:
        user32.UnregisterHotKey(hwnd, hotkey_id)
    except Exception:
        pass
