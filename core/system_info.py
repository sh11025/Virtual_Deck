"""
정보 버튼에 보여 줄 값
시계, 날짜, 볼륨, 배터리, CPU, 메모리를 읽습니다. (추가 설치 없이 Windows 기능만 사용)
"""

import sys
import time
import ctypes
from datetime import datetime
from typing import Optional, Tuple

from core import audio_state

IS_WINDOWS = sys.platform == "win32"

# 종류 → (화면 이름, 테마 아이콘 이름)
INFO_KINDS = {
    "clock": ("시계", "clock"),
    "date": ("날짜", "calendar"),
    "volume": ("볼륨 %", "volume_up"),
    "battery": ("배터리", "power"),
    "cpu": ("CPU 사용량", "chart"),
    "memory": ("메모리 사용량", "monitor"),
}

WEEKDAYS = "월화수목금토일"

_cpu_prev = None


def _cpu_percent() -> Optional[int]:
    global _cpu_prev
    if not IS_WINDOWS:
        return None
    try:
        from ctypes import wintypes
        idle, kernel, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetSystemTimes(ctypes.byref(idle), ctypes.byref(kernel), ctypes.byref(user)):
            return None
        to_int = lambda ft: (ft.dwHighDateTime << 32) | ft.dwLowDateTime
        cur = (to_int(idle), to_int(kernel), to_int(user))
        prev, _cpu_prev = _cpu_prev, cur
        if prev is None:
            return None
        d_idle, d_kernel, d_user = (cur[i] - prev[i] for i in range(3))
        total = d_kernel + d_user   # kernel 시간에 idle 이 포함되어 있음
        if total <= 0:
            return None
        return max(0, min(100, int(round((total - d_idle) * 100 / total))))
    except Exception:
        return None


def _memory_percent() -> Optional[int]:
    if not IS_WINDOWS:
        return None
    try:
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        st = MEMORYSTATUSEX()
        st.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
            return int(st.dwMemoryLoad)
    except Exception:
        pass
    return None


def _battery() -> Tuple[Optional[int], bool]:
    if not IS_WINDOWS:
        return None, False
    try:
        class SYSTEM_POWER_STATUS(ctypes.Structure):
            _fields_ = [("ACLineStatus", ctypes.c_ubyte), ("BatteryFlag", ctypes.c_ubyte),
                        ("BatteryLifePercent", ctypes.c_ubyte), ("SystemStatusFlag", ctypes.c_ubyte),
                        ("BatteryLifeTime", ctypes.c_ulong), ("BatteryFullLifeTime", ctypes.c_ulong)]
        st = SYSTEM_POWER_STATUS()
        if ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(st)):
            if st.BatteryFlag == 128 or st.BatteryLifePercent == 255:   # 배터리 없음
                return None, st.ACLineStatus == 1
            return int(st.BatteryLifePercent), st.ACLineStatus == 1
    except Exception:
        pass
    return None, False


_memo = {}   # 같은 종류를 1초 안에 여러 번 읽으면 이전 값을 그대로 사용 (CPU 계산이 꼬이지 않게)


def read_info(kind: str) -> Tuple[str, str, Optional[float]]:
    """(크게 보여 줄 값, 작게 보여 줄 설명, 0~1 게이지 또는 None)"""
    hit = _memo.get(kind)
    if hit and time.monotonic() - hit[0] < 0.8:
        return hit[1]
    result = _read(kind)
    _memo[kind] = (time.monotonic(), result)
    return result


def _read(kind: str) -> Tuple[str, str, Optional[float]]:
    now = datetime.now()
    if kind == "clock":
        return now.strftime("%H:%M"), f"{now.month}/{now.day} ({WEEKDAYS[now.weekday()]})", None
    if kind == "date":
        return f"{now.month}.{now.day}", f"{WEEKDAYS[now.weekday()]}요일", None
    if kind == "volume":
        v = audio_state.get_volume()
        if v is None:
            return "–", "볼륨", None
        muted = audio_state.get_mute("speaker")
        return f"{v}%", "음소거" if muted else "볼륨", v / 100
    if kind == "battery":
        pct, charging = _battery()
        if pct is None:
            return "AC", "전원 연결" if charging else "배터리 없음", None
        return f"{pct}%", "충전 중" if charging else "배터리", pct / 100
    if kind == "cpu":
        v = _cpu_percent()
        return (f"{v}%" if v is not None else "…"), "CPU", (v / 100 if v is not None else None)
    if kind == "memory":
        v = _memory_percent()
        return (f"{v}%" if v is not None else "–"), "메모리", (v / 100 if v is not None else None)
    return "?", kind, None
