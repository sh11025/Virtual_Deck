"""
매크로 실행 모듈
여러 단계(단축키 → 기다리기 → 글자 입력 …)를 차례대로 실행합니다.
- 별도 작업 줄(스레드)에서 실행해서 덱이 멈추지 않습니다.
- 실행 중인 버튼을 다시 누르면 바로 멈춥니다.
- 글자 입력은 클립보드를 쓰지 않아 안전합니다.

저장 형식(이전 버전과 동일): [{"type": "shortcut", "value": "Ctrl + S"}, ...]
"""

from datetime import datetime, timedelta
import json
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QObject, Signal

from core import win32
from core.shortcut_manager import ShortcutManager

STEP_TYPES = {
    "shortcut": "⌨️ 단축키",
    "text": "✏️ 글자 입력",
    "delay": "⏱ 잠시 기다리기",
    "wait_until": "🕒 정해진 시각까지 기다리기",
    "volume_set": "🔊 볼륨을 ○%로 맞추기",
    "media": "🔊 볼륨·미디어",
    "program": "🚀 프로그램 실행",
    "url": "🌐 웹사이트 열기",
}


def seconds_until(hhmm: str, now: Optional[datetime] = None) -> Optional[float]:
    """HH:MM 형식의 시각까지 남은 초를 계산. 이미 지났으면 내일 같은 시각."""
    if not isinstance(hhmm, str):
        return None
    parts = hhmm.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        h, m = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= h < 24 and 0 <= m < 60):
        return None
    if now is None:
        now = datetime.now()
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)
    return float((target - now).total_seconds())


DELAY_UNITS = [
    ("시간", 3_600_000),
    ("분", 60_000),
    ("초", 1_000),
    ("밀리초", 1),
]


def ms_to_unit(ms: Any) -> Tuple[int, str]:
    """밀리초를 나누어 떨어지는 가장 큰 단위와 값으로 변환합니다."""
    try:
        val = int(float(ms))
    except (ValueError, TypeError):
        return 0, "초"
    if val <= 0:
        return 0, "초"
    for unit, factor in DELAY_UNITS:
        if factor > 1 and val % factor == 0:
            return val // factor, unit
    return val, "밀리초"


def unit_to_ms(val: Any, unit: str) -> int:
    """값과 단위를 밀리초로 변환합니다."""
    factors = {"시간": 3_600_000, "분": 60_000, "초": 1_000, "밀리초": 1}
    factor = factors.get(unit, 1_000)
    try:
        return int(float(val) * factor)
    except (ValueError, TypeError):
        return 0


def parse_steps(macro_json: str) -> List[Dict[str, str]]:
    try:
        data = json.loads(macro_json or "[]")
        if isinstance(data, list):
            return [{"type": str(s.get("type", "")), "value": str(s.get("value", ""))}
                    for s in data if isinstance(s, dict)]
    except Exception:
        pass
    return []


def step_label(step: Dict[str, Any]) -> str:
    """진행 표시에 쓸 짧은 단계 이름 (버튼 위에 작게 보여줘요)"""
    t, v = step.get("type", ""), str(step.get("value", "")).strip()
    if t == "delay":
        n, u = ms_to_unit(v)
        return f"{n}{u} 기다리기"
    if t == "wait_until":
        return f"{v} 까지 기다리기"
    if t == "volume_set":
        return f"볼륨 {v}%"
    if t == "shortcut":
        return "단축키 " + v.replace(" + ", "+")
    if t == "text":
        return "글자 입력"
    if t == "media":
        return ShortcutManager.media_label(v).split(" ", 1)[-1].split("(", 1)[0].strip()
    if t == "program":
        return "프로그램 실행"
    if t == "url":
        return "웹사이트 열기"
    return STEP_TYPES.get(t, t)


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
        self._progress: Dict[str, Dict[str, Any]] = {}

    def progress(self, key: str) -> Optional[Dict[str, Any]]:
        """실행 중인 연속 동작의 진행 상황 (몇 번째 단계, 남은 시간, 다음 단계). 실행 중이 아니면 None"""
        cur = self._progress.get(key)
        if cur is None:
            return None
        out = dict(cur)
        end = out.get("end")
        out["remaining"] = None if end is None else max(0.0, end - time.monotonic())
        return out

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
            for idx, step in enumerate(steps):
                if cancel.is_set():
                    ok, msg = False, "매크로를 멈췄어요"
                    break
                self._progress[key] = {
                    "index": idx, "total": len(steps), "label": step_label(step),
                    "next": step_label(steps[idx + 1]) if idx + 1 < len(steps) else "", "end": None,
                }
                st, val = step.get("type", ""), str(step.get("value", "")).strip()
                if st == "delay":
                    try:
                        total = max(0.0, float(val or 0) / 1000.0)
                    except ValueError:
                        total = 0.3
                    end = time.monotonic() + total
                    self._progress[key]["end"] = end
                    while time.monotonic() < end and not cancel.is_set():
                        time.sleep(min(0.05, end - time.monotonic() + 0.001))
                    if cancel.is_set():   # 기다리는 도중에 멈춘 경우
                        ok, msg = False, "매크로를 멈췄어요"
                        break
                    continue
                if st == "wait_until":
                    wait_sec = seconds_until(val)
                    if wait_sec is None:
                        continue
                    end = time.monotonic() + wait_sec
                    self._progress[key]["end"] = end
                    while time.monotonic() < end and not cancel.is_set():
                        time.sleep(min(0.2, max(0.01, end - time.monotonic())))
                    if cancel.is_set():
                        ok, msg = False, "매크로를 멈췄어요"
                        break
                    continue
                if not val:
                    continue
                if st == "volume_set":
                    try:
                        pct = int(val)
                    except ValueError:
                        continue
                    from core.audio_state import set_master_volume
                    r_ok, r_msg = set_master_volume(pct, from_worker=True)
                    if not r_ok:
                        ok, msg = False, r_msg
                        break
                    time.sleep(0.05)
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
            self._progress.pop(key, None)
            # 신호는 자동으로 화면 쪽 작업 줄로 안전하게 전달됩니다.
            self.finished.emit(key, ok, msg)
