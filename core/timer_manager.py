"""
타이머 · 스톱워치
타이머 버튼마다 지금 상태(대기 / 진행 중 / 일시정지 / 끝)를 기억하고 남은 시간을 계산합니다.
프로필을 바꾸거나 묶음을 열어도 타이머는 계속 흘러갑니다.

버튼 설정(action_data)은 JSON 으로 저장됩니다.
  {"mode": "countdown" | "stopwatch", "seconds": 300, "sound": true,
   "then_type": "none", "then_data": ""}
"""

import json
import math
import time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple

from PySide6.QtCore import QObject, Signal

DEFAULT = {"mode": "countdown", "seconds": 300, "sound": True, "then_type": "none", "then_data": ""}


def parse_timer(data: str) -> dict:
    out = dict(DEFAULT)
    try:
        loaded = json.loads(data or "{}")
        if isinstance(loaded, dict):
            out.update(loaded)
    except Exception:
        pass
    out["mode"] = "stopwatch" if out.get("mode") == "stopwatch" else "countdown"
    out["seconds"] = max(1, min(24 * 3600, int(out.get("seconds") or 1)))
    return out


def dump_timer(cfg: dict) -> str:
    return json.dumps({k: cfg.get(k, DEFAULT[k]) for k in DEFAULT}, ensure_ascii=False)


def format_seconds(sec: float) -> str:
    """125 → '02:05', 3725 → '1:02:05'"""
    sec = max(0, int(round(sec)))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


@dataclass
class TimerState:
    state: str = "idle"          # 'idle' | 'running' | 'paused' | 'done'
    started_at: float = 0.0      # 진행 중일 때 시작(재개) 시각
    elapsed: float = 0.0         # 이전까지 흐른 시간 (일시정지 동안 보관)

    def total_elapsed(self) -> float:
        if self.state == "running":
            return self.elapsed + (time.monotonic() - self.started_at)
        return self.elapsed


class TimerManager(QObject):
    """모든 타이머 버튼의 상태를 관리 (프로그램 전체에서 하나)"""

    finished = Signal(str)     # 끝난 타이머의 키

    def __init__(self, parent=None):
        super().__init__(parent)
        self.timers: Dict[str, TimerState] = {}

    def state(self, key: str) -> TimerState:
        return self.timers.setdefault(key, TimerState())

    def any_running(self) -> bool:
        return any(t.state == "running" for t in self.timers.values())

    def press(self, key: str) -> str:
        """누를 때: 대기→시작, 진행→일시정지, 일시정지→다시 시작, 끝→처음으로. 바뀐 상태를 돌려줌"""
        t = self.state(key)
        now = time.monotonic()
        if t.state in ("idle",):
            t.state, t.started_at, t.elapsed = "running", now, 0.0
        elif t.state == "running":
            t.elapsed += now - t.started_at
            t.state = "paused"
        elif t.state == "paused":
            t.state, t.started_at = "running", now
        elif t.state == "done":
            t.state, t.elapsed = "idle", 0.0
        return t.state

    def reset(self, key: str) -> None:
        self.timers[key] = TimerState()

    def view(self, key: str, data: str) -> Tuple[str, str, Optional[float], str]:
        """버튼에 보여 줄 (큰 글자, 작은 글자, 진행도 0~1, 상태)"""
        cfg = parse_timer(data)
        t = self.state(key)
        el = t.total_elapsed()
        if cfg["mode"] == "stopwatch":
            small = {"idle": "눌러서 시작", "running": "스톱워치", "paused": "일시정지", "done": "스톱워치"}[t.state]
            return format_seconds(el), small, None, t.state
        total = cfg["seconds"]
        left = max(0.0, total - el)
        if t.state == "done":
            return "끝!", "눌러서 끄기", 1.0, "done"
        if t.state == "idle":
            return format_seconds(total), "눌러서 시작", None, "idle"
        small = "일시정지" if t.state == "paused" else "남은 시간"
        # 1초 단위로 올림해서 보여 주기 (0:00 이 되면 바로 끝)
        return format_seconds(math.ceil(left - 1e-6)), small, el / total, t.state

    def tick(self, data_for_key) -> None:
        """진행 중인 카운트다운 중 끝난 것을 찾아 finished 신호를 보냅니다.
        data_for_key: 키 → 버튼의 action_data 를 돌려주는 함수 (버튼이 지워졌으면 None)"""
        for key, t in list(self.timers.items()):
            if t.state != "running":
                continue
            data = data_for_key(key)
            if data is None:
                continue
            cfg = parse_timer(data)
            if cfg["mode"] == "countdown" and t.total_elapsed() >= cfg["seconds"]:
                t.elapsed, t.state = float(cfg["seconds"]), "done"
                self.finished.emit(key)
