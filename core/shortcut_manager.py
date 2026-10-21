"""
단축키 전송 모듈
'Ctrl + Shift + S' 같은 글자를 실제 키 입력으로 바꿔서 보내 줍니다.
덱 창은 포커스를 빼앗지 않기 때문에, 대부분은 지금 쓰고 있는 프로그램에 바로 전달됩니다.
"""

import time
from typing import List, Optional, Tuple

from core import win32


class ShortcutManager:
    """키 이름 ↔ 키 코드 변환과 단축키 전송을 담당"""

    VK_MAP = {
        # 조합 키
        "ctrl": 0x11, "control": 0x11, "shift": 0x10, "alt": 0x12,
        "win": 0x5B, "windows": 0x5B,
        # 특수 키
        "enter": 0x0D, "return": 0x0D, "esc": 0x1B, "escape": 0x1B,
        "space": 0x20, "tab": 0x09, "backspace": 0x08,
        "delete": 0x2E, "del": 0x2E, "insert": 0x2D, "ins": 0x2D,
        "home": 0x24, "end": 0x23, "pageup": 0x21, "pgup": 0x21,
        "pagedown": 0x22, "pgdn": 0x22,
        "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
        "printscreen": 0x2C, "prtsc": 0x2C, "capslock": 0x14,
        "numlock": 0x90, "scrolllock": 0x91, "pause": 0x13, "menu": 0x5D,
        # 볼륨 · 미디어
        "volumeup": 0xAF, "volumedown": 0xAE, "volumemute": 0xAD, "mute": 0xAD,
        "medianext": 0xB0, "mediaprev": 0xB1, "mediastop": 0xB2, "mediaplaypause": 0xB3,
        "playpause": 0xB3,
        # 숫자 패드
        "num0": 0x60, "num1": 0x61, "num2": 0x62, "num3": 0x63, "num4": 0x64,
        "num5": 0x65, "num6": 0x66, "num7": 0x67, "num8": 0x68, "num9": 0x69,
        "num*": 0x6A, "num+": 0x6B, "num-": 0x6D, "num.": 0x6E, "num/": 0x6F,
        # 기호 키 (미국 배열 기준)
        ";": 0xBA, "=": 0xBB, ",": 0xBC, "-": 0xBD, ".": 0xBE, "/": 0xBF,
        "`": 0xC0, "[": 0xDB, "\\": 0xDC, "]": 0xDD, "'": 0xDE,
        "plus": 0xBB, "minus": 0xBD, "comma": 0xBC, "period": 0xBE,
    }

    # 'Extended' 표시가 필요한 키 (방향키 등은 이 표시가 없으면 숫자패드로 인식되기도 함)
    EXTENDED = {0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x2D, 0x2E,
                0x5B, 0x5C, 0x5D, 0x6F, 0x90, 0x2C,
                0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2, 0xB3}

    MODIFIERS = ("Ctrl", "Shift", "Alt", "Win")

    # 편집창 "특수 키" 목록에 보여 줄 이름 (저장 이름, 화면 이름)
    SPECIAL_KEYS = [
        ("Enter", "Enter"), ("Esc", "Esc"), ("Space", "Space"), ("Tab", "Tab"),
        ("Backspace", "Backspace"), ("Delete", "Delete"), ("Insert", "Insert"),
        ("Home", "Home"), ("End", "End"), ("PageUp", "Page Up"), ("PageDown", "Page Down"),
        ("Up", "↑ 위"), ("Down", "↓ 아래"), ("Left", "← 왼쪽"), ("Right", "→ 오른쪽"),
        ("PrintScreen", "Print Screen"), ("CapsLock", "Caps Lock"), ("Menu", "메뉴 키"),
    ] + [(f"F{i}", f"F{i}") for i in range(1, 25)]

    MEDIA_KEYS = [
        ("VolumeUp", "🔊 볼륨 올리기"),
        ("VolumeDown", "🔉 볼륨 내리기"),
        ("VolumeMute", "🔇 음소거"),
        ("MediaPlayPause", "⏯ 재생 / 일시정지"),
        ("MediaNext", "⏭ 다음 곡"),
        ("MediaPrev", "⏮ 이전 곡"),
        ("MediaStop", "⏹ 정지"),
        ("MicMute", "🎙 마이크 음소거 켜기/끄기"),
    ]
    MEDIA_ICONS = {"VolumeUp": "🔊", "VolumeDown": "🔉", "VolumeMute": "🔇",
                   "MediaPlayPause": "⏯️", "MediaNext": "⏭️", "MediaPrev": "⏮️", "MediaStop": "⏹️", "MicMute": "🎙️"}

    _last_external_hwnd: int = 0
    _own_hwnds: set = set()

    @classmethod
    def add_own_hwnd(cls, hwnd: int) -> None:
        """Virtual Deck 자신의 창을 등록해서 '대상 창'으로 착각하지 않게 합니다."""
        if hwnd:
            cls._own_hwnds.add(int(hwnd))

    @classmethod
    def update_target_window(cls) -> None:
        """지금 앞에 있는 창이 다른 프로그램이면 기억해 둡니다."""
        hwnd = win32.get_foreground_window()
        if hwnd and hwnd not in cls._own_hwnds:
            cls._last_external_hwnd = hwnd

    @classmethod
    def get_vk_code(cls, key_name: str) -> Optional[int]:
        key = key_name.strip().lower().replace(" ", "")
        if key in cls.VK_MAP:
            return cls.VK_MAP[key]
        if len(key) == 1 and ("a" <= key <= "z" or "0" <= key <= "9"):
            return ord(key.upper())
        if key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24:
            return 0x70 + int(key[1:]) - 1
        return None

    @classmethod
    def parse(cls, shortcut_str: str) -> Tuple[List[int], str]:
        """단축키 글자를 키 코드 목록으로 바꿉니다. 실패하면 (빈 목록, 오류 메시지)"""
        if not shortcut_str or not shortcut_str.strip():
            return [], "단축키가 지정되지 않았습니다."
        text = shortcut_str.strip()
        # '+' 키 자체를 쓰는 경우(예: Ctrl + +)를 위해 ' + ' 기준으로 먼저 나눕니다.
        if " + " in text:
            parts = [p.strip() for p in text.split(" + ")]
        else:
            parts = [p.strip() for p in text.replace("+", " ").split()]
        codes = []
        for p in parts:
            if not p:
                continue
            if p == "+":
                p = "plus"
            vk = cls.get_vk_code(p)
            if vk is None:
                return [], f"알 수 없는 키예요: '{p}'"
            codes.append(vk)
        if not codes:
            return [], "올바른 키가 없어요."
        return codes, ""

    @classmethod
    def send_shortcut(cls, shortcut_str: str) -> Tuple[bool, str]:
        codes, err = cls.parse(shortcut_str)
        if not codes:
            return False, err
        if not win32.IS_WINDOWS:
            return False, "Windows에서만 단축키를 보낼 수 있어요."

        # 덱의 설정창 등이 앞에 있다면, 마지막으로 쓰던 프로그램을 다시 앞으로 가져옵니다.
        fg = win32.get_foreground_window()
        if fg in cls._own_hwnds and cls._last_external_hwnd:
            win32.focus_window(cls._last_external_hwnd)
            time.sleep(0.06)

        ok = win32.send_key_combo(codes, cls.EXTENDED)
        if not ok:
            return False, "키 입력을 보내지 못했어요. (관리자 권한 프로그램에는 보낼 수 없어요)"
        return True, f"'{shortcut_str}' 보냄"

    @classmethod
    def media_label(cls, key: str) -> str:
        for k, label in cls.MEDIA_KEYS:
            if k.lower() == key.lower():
                return label
        return key
