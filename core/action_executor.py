"""
동작 실행 모듈
버튼을 눌렀을 때 웹사이트 열기, 프로그램 실행, 단축키 보내기 등을 실제로 수행합니다.
(매크로는 진행 표시와 멈추기가 필요해서 macro_manager 에서 따로 처리합니다)
"""

import os
import shutil
import subprocess
import webbrowser
from typing import Tuple

from core.shortcut_manager import ShortcutManager
from core.app_finder import is_app_command

ACTION_LABELS = {
    "none": "아무것도 안 함",
    "url": "웹사이트 열기",
    "program": "프로그램 실행",
    "file": "파일 열기",
    "folder": "폴더 열기",
    "shortcut": "단축키",
    "media": "볼륨 · 미디어",
    "macro": "연속 동작",
    "group": "버튼 묶음",
    "info": "정보 보여 주기 (시계·볼륨 등)",
    "timer": "타이머 · 스톱워치",
    "profile": "프로필 이동",
    "close": "다시 누르면 닫기",
}

ACTION_ICONS = {
    "url": "🌐", "program": "🚀", "file": "📄", "folder": "📁",
    "shortcut": "⌨️", "media": "🔊", "macro": "⚡", "group": "🗂️", "info": "🕒", "timer": "⏱️",
    "profile": "👤",
    "close": "✖️",
}


def describe_action(action_type: str, action_data: str) -> str:
    """툴팁 등에 보여 줄 짧은 설명"""
    label = ACTION_LABELS.get(action_type, action_type)
    if action_type == "profile":
        return "프로필 이동"
    if action_type == "media":
        return ShortcutManager.media_label(action_data)
    if action_type == "macro":
        try:
            import json
            n = len(json.loads(action_data or "[]"))
            return f"연속 동작 ({n}순서)"
        except Exception:
            return "연속 동작"
    if action_type == "group":
        return "버튼 묶음 열기"
    if action_type == "timer":
        from core.timer_manager import parse_timer, format_seconds
        t = parse_timer(action_data)
        return "스톱워치" if t["mode"] == "stopwatch" else f"타이머 {format_seconds(t['seconds'])}"
    if action_type == "info":
        from core.system_info import INFO_KINDS
        return "정보: " + INFO_KINDS.get(action_data, ("?",))[0]
    if action_type == "program" and is_app_command(action_data):
        return "설치된 앱 실행"
    if not action_data:
        return label
    short = action_data if len(action_data) <= 48 else "…" + action_data[-46:]
    return f"{label}: {short}"


class ActionExecutor:
    """사용자가 지정한 동작을 실행"""

    @staticmethod
    def execute(action_type: str, action_data: str) -> Tuple[bool, str]:
        data = (action_data or "").strip()
        if not data:
            return False, "실행할 내용이 비어 있어요."
        try:
            if action_type == "url":
                return ActionExecutor._open_url(data)
            if action_type == "program":
                return ActionExecutor._run_program(data)
            if action_type in ("file", "folder"):
                return ActionExecutor._open_path(data, action_type)
            if action_type == "media" and data == "MicMute":
                from core.audio_state import toggle_mic_mute
                return toggle_mic_mute()
            if action_type in ("shortcut", "media"):
                return ShortcutManager.send_shortcut(data)
            if action_type in ("info", "timer"):
                return True, ""
            if action_type == "close":
                from core.running_state import close_program_windows, close_folder_windows
                clean = os.path.expandvars(data.strip().strip("\"'"))
                if os.path.isdir(clean):
                    cnt = close_folder_windows(clean)
                else:
                    cnt = close_program_windows(clean)
                if cnt > 0:
                    return True, "창을 닫았어요"
                return False, "이미 꺼져 있어요"
            return False, f"지원하지 않는 동작이에요: {action_type}"
        except Exception as e:  # 어떤 경우에도 덱이 꺼지지 않도록
            return False, f"실행 중 오류: {e}"

    @staticmethod
    def _open_url(url: str) -> Tuple[bool, str]:
        raw = url.strip()
        if raw.lower().startswith("ms-settings:"):
            if os.name == "nt":
                os.startfile(raw)  # type: ignore[attr-defined]
                return True, "설정을 열었어요"
            return False, "Windows에서만 지원해요"
        if "://" not in raw and not raw.lower().startswith(("mailto:", "tel:")):
            raw = "https://" + raw
        if webbrowser.open(raw):
            return True, "웹사이트를 열었어요"
        return False, "웹 브라우저를 열지 못했어요."

    @staticmethod
    def _run_program(command: str) -> Tuple[bool, str]:
        clean = os.path.expandvars(command.strip().strip("\"'"))

        # 1) 경로가 실제로 있는 경우: 탐색기에서 더블클릭한 것과 똑같이 실행
        #    (띄어쓰기가 있는 경로, 관리자 권한이 필요한 프로그램, .bat/.lnk 모두 OK)
        if os.path.exists(clean):
            if os.name == "nt":
                os.startfile(clean, cwd=os.path.dirname(os.path.abspath(clean)))  # type: ignore[call-arg]
            else:
                subprocess.Popen([clean], cwd=os.path.dirname(os.path.abspath(clean)))
            return True, f"{os.path.basename(clean)} 실행"

        # 2) notepad.exe 처럼 이름만 적은 경우
        found = shutil.which(clean)
        if found:
            if os.name == "nt":
                os.startfile(found)  # type: ignore[attr-defined]
            else:
                subprocess.Popen([found])
            return True, f"{clean} 실행"

        # 3) '프로그램 경로 + 옵션' 형태의 명령줄 (예: notepad.exe C:\메모.txt)
        try:
            expanded = os.path.expandvars(command)
            subprocess.Popen(expanded, close_fds=True)
            return True, "명령을 실행했어요"
        except OSError:
            return False, f"프로그램을 찾을 수 없어요: {clean}"

    @staticmethod
    def _open_path(path: str, kind: str) -> Tuple[bool, str]:
        clean = os.path.expandvars(path.strip().strip("\"'"))
        if not os.path.exists(clean):
            word = "폴더" if kind == "folder" else "파일"
            return False, f"{word}을(를) 찾을 수 없어요: {clean}"
        if os.name == "nt":
            os.startfile(clean)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", clean])
        return True, f"{os.path.basename(clean) or clean} 열기"
