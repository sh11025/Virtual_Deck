"""
매크로 실행 모듈
여러 단계(단축키 → 기다리기 → 글자 입력 …)를 차례대로 실행합니다.
- 별도 작업 줄(스레드)에서 실행해서 덱이 멈추지 않습니다.
- 실행 중인 버튼을 다시 누르면 바로 멈춥니다.
- 글자 입력은 클립보드를 쓰지 않아 안전합니다.

저장 형식(이전 버전과 동일): [{"type": "shortcut", "value": "Ctrl + S"}, ...]
"""

import json
import threading
import time
from typing import Any, Dict, List, Tuple

from PySide6.QtCore import QObject, Signal

from core import win32
from core.shortcut_manager import ShortcutManager

STEP_TYPES = {
    "shortcut": "⌨️ 단축키",
    "text": "✏️ 글자 입력",
    "delay": "⏱ 잠시 기다리기",
    "media": "🔊 볼륨·미디어",
    "program": "🚀 프로그램 실행",
    "url": "🌐 웹사이트 열기",
}


def parse_steps(macro_json: str) -> List[Dict[str, str]]:
    try:
        data = json.loads(macro_json or "[]")
        if isinstance(data, list):
            return [{"type": str(s.get("type", "")), "value": str(s.get("value", ""))}
                    for s in data if isinstance(s, dict)]
    except Exception:
        pass
    return []


class MacroRunner(QObject):
    """매크로 실행기 (프로그램 전체에서 하나만 사용)"""

    started = Signal(str)                 # 버튼 ID
    finished = Signal(str, bool, str)     # 버튼 ID, 성공 여부, 메시지

    _instance = None

    @classmethod
    def instance(cls) -> "MacroRunner":
        if cls._instance is None:
            cls._instance = MacroRunner()
        return cls._instance

    def __init__(self):
        super().__init__()
        self._running: Dict[str, threading.Event] = {}

    def is_running(self, key: str) -> bool:
        return key in self._running

    def stop(self, key: str) -> None:
        ev = self._running.get(key)
        if ev:
            ev.set()

    def stop_all(self) -> None:
        for ev in list(self._running.values()):
            ev.set()

    def run(self, key: str, macro_json: str) -> Tuple[bool, str]:
        steps = parse_steps(macro_json)
        if not steps:
            return False, "매크로 단계가 비어 있어요."
        if key in self._running:
            return False, "이미 실행 중이에요."
        cancel = threading.Event()
        self._running[key] = cancel
        self.started.emit(key)
        t = threading.Thread(target=self._worker, args=(key, steps, cancel), daemon=True)
        t.start()
        return True, f"매크로 시작 ({len(steps)}단계)"

    def _worker(self, key: str, steps: List[Dict[str, Any]], cancel: threading.Event) -> None:
        ok, msg = True, "매크로 완료"
        try:
            for step in steps:
                if cancel.is_set():
                    ok, msg = False, "매크로를 멈췄어요"
                    break
                st, val = step.get("type", ""), str(step.get("value", "")).strip()
                if st == "delay":
                    try:
                        total = max(0.0, float(val or 0) / 1000.0)
                    except ValueError:
                        total = 0.3
                    end = time.monotonic() + total
                    while time.monotonic() < end and not cancel.is_set():
                        time.sleep(min(0.05, end - time.monotonic() + 0.001))
                    if cancel.is_set():   # 기다리는 도중에 멈춘 경우
                        ok, msg = False, "매크로를 멈췄어요"
                        break
                    continue
                if not val:
                    continue
                if st == "media" and val == "MicMute":
                    from core.audio_state import toggle_mic_mute
                    r_ok, r_msg = toggle_mic_mute(from_worker=True)
                    if not r_ok:
                        ok, msg = False, r_msg
                        break
                elif st in ("shortcut", "media"):
                    r_ok, r_msg = ShortcutManager.send_shortcut(val)
                    if not r_ok:
                        ok, msg = False, r_msg
                        break
                    time.sleep(0.05)
                elif st == "text":
                    # 원본 값은 앞뒤 공백까지 그대로 입력
                    win32.send_text(str(step.get("value", "")), cancel.is_set)
                    time.sleep(0.05)
                elif st in ("program", "url"):
                    from core.action_executor import ActionExecutor
                    r_ok, r_msg = ActionExecutor.execute(st, val)
                    if not r_ok:
                        ok, msg = False, r_msg
                        break
                    time.sleep(0.15)
        except Exception as e:
            ok, msg = False, f"매크로 오류: {e}"
        finally:
            self._running.pop(key, None)
            # 신호는 자동으로 화면 쪽 작업 줄로 안전하게 전달됩니다.
            self.finished.emit(key, ok, msg)
