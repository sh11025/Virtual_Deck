"""
Windows 연동 기능
- 자동 실행: 컴퓨터를 켤 때 Virtual Deck 이 자동으로 시작되게 합니다.
"""

import os
import sys

from core import win32
from core.paths import is_frozen, project_dir


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
