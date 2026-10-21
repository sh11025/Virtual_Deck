"""
추가 부품(pycaw) 확인 · 설치
pycaw 는 음소거 상태 맞추기, 마이크 음소거, 볼륨 % 에 쓰입니다.

- 파이썬으로 실행할 때: 없으면 설치할지 물어보고, 백그라운드에서 pip 로 설치합니다.
- EXE 로 실행할 때: EXE 안에는 pip 가 없어서 설치할 수 없습니다.
  대신 build_exe.py 가 EXE 를 만들 때 pycaw 를 자동으로 설치해서 함께 넣습니다.
"""

import importlib
import sys

from PySide6.QtCore import QObject, QProcess, Signal

from core.paths import is_frozen

PACKAGE = "pycaw"


def has_pycaw() -> bool:
    if sys.platform != "win32":
        return True        # Windows 가 아니면 필요 없음
    try:
        importlib.invalidate_caches()
        importlib.import_module("pycaw.pycaw")
        return True
    except Exception:
        return False


def can_install() -> bool:
    """파이썬으로 실행 중일 때만 pip 설치가 가능합니다."""
    return sys.platform == "win32" and not is_frozen()


class PipInstaller(QObject):
    """pip install 을 화면이 멈추지 않게 백그라운드에서 실행합니다."""

    finished = Signal(bool, str)   # 성공 여부, 메시지

    def __init__(self, parent=None):
        super().__init__(parent)
        self.proc = None
        self._out = b""

    def install(self, package: str = PACKAGE) -> bool:
        if not can_install() or self.proc is not None:
            return False
        self.proc = QProcess(self)
        self.proc.setProcessChannelMode(QProcess.MergedChannels)
        self.proc.readyReadStandardOutput.connect(self._read)
        self.proc.finished.connect(self._done)
        self.proc.errorOccurred.connect(self._error)
        # pythonw.exe 로 실행 중이어도 pip 는 python.exe 로 돌려야 함
        exe = sys.executable
        if exe.lower().endswith("pythonw.exe"):
            exe = exe[:-len("pythonw.exe")] + "python.exe"
        self.proc.start(exe, ["-m", "pip", "install", "--disable-pip-version-check", package])
        return True

    def _read(self):
        self._out += bytes(self.proc.readAllStandardOutput())

    def _error(self, err):
        if err == QProcess.FailedToStart:
            self._finish(False, "pip 를 실행하지 못했어요. 명령 창에서 'pip install pycaw' 를 직접 실행해 주세요.")

    def _done(self, code, _status):
        if code == 0 and has_pycaw():
            from core import audio_state
            audio_state.reset()
            self._finish(True, "pycaw 설치 완료! 음소거 상태 맞추기·마이크 음소거·볼륨 %를 쓸 수 있어요.")
        else:
            tail = self._out.decode("utf-8", "ignore").strip().splitlines()[-1:] or [""]
            self._finish(False, "pycaw 설치에 실패했어요. " + tail[0][:120])

    def _finish(self, ok: bool, msg: str):
        self.proc = None
        self.finished.emit(ok, msg)
