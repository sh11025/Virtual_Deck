"""
Windows 연동 기능
- 전역 단축키: 어떤 프로그램을 쓰고 있어도 단축키로 덱을 숨기거나 보이게 합니다.
- 자동 실행: 컴퓨터를 켤 때 Virtual Deck 이 자동으로 시작되게 합니다.
"""

import os
import sys

from PySide6.QtCore import QObject, Signal, QAbstractNativeEventFilter, QCoreApplication

from core import win32
from core.paths import is_frozen, project_dir
from core.shortcut_manager import ShortcutManager

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN = 0x1, 0x2, 0x4, 0x8
WM_HOTKEY = 0x0312
HOTKEY_ID = 0xBEEF


class _HotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, owner: "GlobalHotkey"):
        super().__init__()
        self.owner = owner

    def nativeEventFilter(self, event_type, message):
        try:
            if bytes(event_type) in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
                from ctypes import wintypes
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                    self.owner.activated.emit()
                    return True, 0
        except Exception:
            pass
        return False, 0


class GlobalHotkey(QObject):
    """전역 단축키 등록/해제"""

    activated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._hwnd = 0
        self._registered = False
        self._filter = _HotkeyFilter(self)
        if win32.IS_WINDOWS:
            QCoreApplication.instance().installNativeEventFilter(self._filter)

    def register(self, hwnd: int, shortcut: str) -> bool:
        self.unregister()
        if not win32.IS_WINDOWS or not shortcut:
            return False
        mods, vk = 0, None
        for part in [p.strip() for p in shortcut.split("+") if p.strip()]:
            low = part.lower()
            if low in ("ctrl", "control"):
                mods |= MOD_CONTROL
            elif low == "shift":
                mods |= MOD_SHIFT
            elif low == "alt":
                mods |= MOD_ALT
            elif low in ("win", "windows"):
                mods |= MOD_WIN
            else:
                vk = ShortcutManager.get_vk_code(part)
        if vk is None:
            return False
        self._hwnd = hwnd
        self._registered = win32.register_hotkey(hwnd, HOTKEY_ID, mods, vk)
        return self._registered

    def unregister(self) -> None:
        if self._registered:
            win32.unregister_hotkey(self._hwnd, HOTKEY_ID)
        self._registered = False


# ---------------------------------------------------------------- 자동 실행
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
_APP_NAME = "VirtualDeck"


def _launch_command() -> str:
    if is_frozen():
        return f'"{sys.executable}"'
    pyw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
    exe = pyw if os.path.exists(pyw) else sys.executable
    return f'"{exe}" "{os.path.join(project_dir(), "main.py")}"'


def is_autostart_enabled() -> bool:
    if not win32.IS_WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            winreg.QueryValueEx(key, _APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(enabled: bool) -> bool:
    if not win32.IS_WINDOWS:
        return False
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
            if enabled:
                winreg.SetValueEx(key, _APP_NAME, 0, winreg.REG_SZ, _launch_command())
            else:
                try:
                    winreg.DeleteValue(key, _APP_NAME)
                except OSError:
                    pass
        return True
    except OSError:
        return False
