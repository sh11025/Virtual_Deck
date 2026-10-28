"""
예약 동작 관리자 (ScheduleManager)
정해진 시각에 시작 동작, 정해진 시각에 종료 동작을 자동 실행합니다.
"""

import json
from datetime import datetime, timedelta
from typing import Optional, Tuple, List, Dict, Any

from PySide6.QtCore import QObject, Signal


DEFAULT = {
    "start": "09:00",
    "start_type": "program",
    "start_data": "",
    "end": "18:00",
    "end_type": "close",
    "end_data": "",
    "days": [0, 1, 2, 3, 4, 5, 6],
}

VALID_TYPES = {"program", "url", "file", "folder", "close", "shortcut", "media"}


def _validate_time(val: Any) -> str:
    """HH:MM 형식 검증. 올바르지 않으면 빈 문자열 반환"""
    if not isinstance(val, str):
        return ""
    val = val.strip()
    if not val:
        return ""
    parts = val.split(":")
    if len(parts) != 2:
        return ""
    try:
        h, m = int(parts[0]), int(parts[1])
        if 0 <= h < 24 and 0 <= m < 60:
            return f"{h:02d}:{m:02d}"
    except ValueError:
        pass
    return ""


def parse_schedule(text: str) -> dict:
    """JSON 문자열을 파싱하여 예약 설정 딕셔너리로 변환합니다. 잘못된 값은 기본값으로 대체합니다."""
    res = dict(DEFAULT)
    if not text or not isinstance(text, str):
        return res
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return res
    except Exception:
        return res

    if "start" in data:
        res["start"] = _validate_time(data["start"])
    if "end" in data:
        res["end"] = _validate_time(data["end"])

    st = data.get("start_type")
    res["start_type"] = st if st in VALID_TYPES else DEFAULT["start_type"]
    res["start_data"] = str(data.get("start_data", "") or "")

    et = data.get("end_type")
    res["end_type"] = et if et in VALID_TYPES else DEFAULT["end_type"]
    res["end_data"] = str(data.get("end_data", "") or "")

    raw_days = data.get("days")
    if isinstance(raw_days, (list, tuple)):
        valid_days = []
        for d in raw_days:
            try:
                di = int(d)
                if 0 <= di <= 6 and di not in valid_days:
                    valid_days.append(di)
            except (ValueError, TypeError):
                continue
        valid_days.sort()
        res["days"] = valid_days if valid_days else list(DEFAULT["days"])
    else:
        res["days"] = list(DEFAULT["days"])

    return res


def dump_schedule(cfg: dict) -> str:
    """예약 설정 딕셔너리를 JSON 문자열로 변환합니다."""
    return json.dumps(cfg, ensure_ascii=False)


def due_events(cfg: dict, now: datetime, last_fired: dict) -> List[str]:
    """지금 실행해야 할 이벤트 목록 ('start', 'end' 중)을 반환합니다."""
    today_weekday = now.weekday()
    days = cfg.get("days", DEFAULT["days"])
    if today_weekday not in days:
        return []

    today_str = now.strftime("%Y-%m-%d")
    events = []

    for which in ("start", "end"):
        time_str = cfg.get(which)
        if not time_str:
            continue
        try:
            h, m = map(int, time_str.split(":"))
            target_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        except Exception:
            continue

        if target_dt <= now:
            diff_sec = (now - target_dt).total_seconds()
            if 0 <= diff_sec <= 90:
                if last_fired.get(which) != today_str:
                    events.append(which)

    return events


def next_event(cfg: dict, now: datetime) -> Optional[Tuple[str, datetime]]:
    """앞으로 가장 가까운 ('start' | 'end', 시각)을 반환합니다. 사용하는 시각이 없으면 None."""
    has_start = bool(cfg.get("start"))
    has_end = bool(cfg.get("end"))
    if not has_start and not has_end:
        return None

    days = cfg.get("days", DEFAULT["days"])
    if not days:
        return None

    candidates = []
    # 오늘 포함 향후 8일간 탐색
    for offset in range(9):
        day_date = (now + timedelta(days=offset)).date()
        if day_date.weekday() not in days:
            continue

        for which in ("start", "end"):
            t_str = cfg.get(which)
            if not t_str:
                continue
            try:
                h, m = map(int, t_str.split(":"))
                dt = datetime.combine(day_date, datetime.min.time()).replace(hour=h, minute=m, second=0, microsecond=0)
                if dt > now:
                    candidates.append((which, dt))
            except Exception:
                continue

    if not candidates:
        return None

    candidates.sort(key=lambda item: item[1])
    return candidates[0]


class ScheduleManager(QObject):
    """예약 버튼들의 시작·종료 동작을 주기적으로 검사하고 실행합니다."""

    fired = Signal(str, str, bool, str)  # key, which ("start"|"end"), ok, msg

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_fired: Dict[str, Dict[str, str]] = {}  # key -> {"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}

    def check(self, buttons_by_key: Dict[str, Any], now: Optional[datetime] = None) -> None:
        """모든 예약 버튼을 검사하여 실행 시각이 된 동작을 실행합니다."""
        from core.action_executor import ActionExecutor

        now = now or datetime.now()
        today_str = now.strftime("%Y-%m-%d")

        for key, btn in buttons_by_key.items():
            if getattr(btn, "action_type", "") != "schedule":
                continue
            cfg = parse_schedule(getattr(btn, "action_data", ""))
            lf = self.last_fired.setdefault(key, {})
            dues = due_events(cfg, now, lf)
            for which in dues:
                act_type = cfg.get(f"{which}_type", "program" if which == "start" else "close")
                act_data = cfg.get(f"{which}_data", "")
                if which == "end" and act_type == "close" and not act_data:
                    act_data = cfg.get("start_data", "")
                ok, msg = ActionExecutor.execute(act_type, act_data)
                lf[which] = today_str
                self.fired.emit(key, which, ok, msg)
