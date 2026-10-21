"""
소리 상태 읽기/바꾸기
Windows 소리 장치에서 스피커·마이크 음소거 상태와 볼륨을 읽습니다.
- 음소거 버튼이 실제 상태와 어긋나지 않게 맞출 때
- '마이크 음소거' 동작
- 볼륨 % 정보 버튼
에 사용합니다. (pycaw 라이브러리가 없거나 Windows가 아니면 조용히 건너뜀)
"""

import sys
import time
from typing import Optional

_cache = {}          # 'speaker' / 'mic' → (장치 객체, 가져온 시각)
_CACHE_SECONDS = 10  # 기본 장치가 바뀔 수 있어 10초마다 다시 가져옴
_failed = False


def reset() -> None:
    """pycaw 를 새로 설치한 뒤 다시 시도할 수 있게 초기화"""
    global _failed
    _failed = False
    _cache.clear()


def is_available() -> bool:
    if sys.platform != "win32" or _failed:
        return False
    try:
        import pycaw  # noqa: F401
        return True
    except Exception:
        return False


def _endpoint(kind: str, use_cache: bool = True):
    global _failed
    if not is_available():
        return None
    now = time.monotonic()
    hit = _cache.get(kind)
    if use_cache and hit and now - hit[1] < _CACHE_SECONDS:
        return hit[0]
    try:
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
        dev = AudioUtilities.GetSpeakers() if kind == "speaker" else AudioUtilities.GetMicrophone()
        if dev is None:
            _cache[kind] = (None, now)
            return None
        ev = getattr(dev, "EndpointVolume", None)   # pycaw 새 버전
        if ev is None:                               # pycaw 예전 버전
            from ctypes import cast, POINTER
            from comtypes import CLSCTX_ALL
            iface = dev.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            ev = cast(iface, POINTER(IAudioEndpointVolume))
        if use_cache:
            _cache[kind] = (ev, now)
        return ev
    except Exception as e:
        print(f"[소리 장치 읽기 실패] {e}")
        _cache[kind] = (None, now)
        return None


def get_mute(kind: str = "speaker") -> Optional[bool]:
    ev = _endpoint(kind)
    if ev is None:
        return None
    try:
        return bool(ev.GetMute())
    except Exception:
        _cache.pop(kind, None)
        return None


def set_mute(kind: str, mute: bool) -> bool:
    ev = _endpoint(kind)
    if ev is None:
        return False
    try:
        ev.SetMute(1 if mute else 0, None)
        return True
    except Exception:
        _cache.pop(kind, None)
        return False


def toggle_mic_mute(from_worker: bool = False):
    """
    마이크 음소거를 바꾸고 (성공 여부, 메시지)를 돌려줍니다.
    from_worker: 매크로처럼 별도 작업 줄에서 부를 때 True (장치를 새로 열어서 사용)
    """
    if not is_available():
        return False, "마이크 음소거에는 pycaw 설치가 필요해요. (pip install pycaw)"
    try:
        if from_worker:
            import comtypes
            comtypes.CoInitialize()
        ev = _endpoint("mic", use_cache=not from_worker)
        if ev is None:
            return False, "마이크를 찾지 못했어요."
        cur = bool(ev.GetMute())
        ev.SetMute(0 if cur else 1, None)
        return True, "마이크 켜짐" if cur else "마이크 꺼짐"
    except Exception as e:
        _cache.pop("mic", None)
        return False, f"마이크 음소거를 바꾸지 못했어요: {e}"


def get_volume() -> Optional[int]:
    ev = _endpoint("speaker")
    if ev is None:
        return None
    try:
        return int(round(ev.GetMasterVolumeLevelScalar() * 100))
    except Exception:
        _cache.pop("speaker", None)
        return None
