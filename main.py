"""
Virtual Deck 시작 파일
프로그램을 준비하고 유리 덱 창을 띄웁니다.
"""

from datetime import datetime
import faulthandler
import os
import sys
import threading
import traceback


def main():
    if sys.platform == "win32":
        # 컬러 이모지가 흑백으로 보이지 않도록 글자 그리는 방식을 지정
        os.environ.setdefault("QT_QPA_PLATFORM", "windows:fontengine=directwrite")
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("VirtualDeck.App")
        except Exception:
            pass

    from PySide6.QtCore import Qt, QLockFile
    from PySide6.QtWidgets import QApplication

    QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)
    app = QApplication(sys.argv)
    app.setApplicationName("Virtual Deck")
    app.setOrganizationName("VirtualDeck")
    app.setQuitOnLastWindowClosed(False)   # 트레이로 숨겨도 계속 실행

    from core import paths
    from ui import theme

    try:
        from core.version import APP_VERSION as app_version
    except Exception:
        try:
            from core import version as _ver_mod
            app_version = getattr(_ver_mod, "APP_VERSION", "1.0.0")
        except Exception:
            app_version = "1.0.0"

    # 크래시 로그 파일 준비 (1MB 초과 시 .old 로 교체하고 새로 시작)
    crash_file = None
    try:
        os.makedirs(paths.data_dir(), exist_ok=True)
        crash_log_path = os.path.join(paths.data_dir(), "crash.log")
        if os.path.exists(crash_log_path) and os.path.getsize(crash_log_path) >= 1024 * 1024:
            old_log_path = os.path.join(paths.data_dir(), "crash.log.old")
            try:
                if os.path.exists(old_log_path):
                    os.remove(old_log_path)
                os.replace(crash_log_path, old_log_path)
            except Exception:
                pass
        crash_file = open(crash_log_path, "a", encoding="utf-8")
    except Exception:
        pass

    # 파이썬 밖(C 코드)에서 프로그램이 죽을 때도 기록이 남도록 설정
    if crash_file:
        try:
            faulthandler.enable(file=crash_file)
        except Exception:
            pass

    # 처리되지 않은 예외 발생 시 크래시 로그에 기록
    orig_excepthook = sys.excepthook

    def _excepthook(exc_type, exc_value, exc_tb):
        try:
            if crash_file:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                crash_file.write(f"[{now_str}] 버전 {app_version}\n")
                traceback.print_exception(exc_type, exc_value, exc_tb, file=crash_file)
                crash_file.flush()
        except Exception:
            pass
        try:
            orig_excepthook(exc_type, exc_value, exc_tb)
        except Exception:
            pass

    sys.excepthook = _excepthook

    orig_threading_excepthook = getattr(threading, "excepthook", None)

    def _threading_excepthook(args):
        try:
            if crash_file:
                now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                crash_file.write(f"[{now_str}] 버전 {app_version}\n")
                traceback.print_exception(args.exc_type, args.exc_value, args.exc_traceback, file=crash_file)
                crash_file.flush()
        except Exception:
            pass
        try:
            if orig_threading_excepthook:
                orig_threading_excepthook(args)
        except Exception:
            pass

    if hasattr(threading, "excepthook"):
        threading.excepthook = _threading_excepthook

    # 덱이 두 개 동시에 뜨지 않도록
    lock = QLockFile(os.path.join(paths.data_dir(), ".running.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        from ui.widgets import inform
        theme.load_fonts()
        app.setStyleSheet(theme.get_qss())
        inform(None, "이미 실행 중이에요", "Virtual Deck 이 이미 켜져 있어요.\n트레이 아이콘을 눌러 열어 주세요.")
        return 0

    if crash_file:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            crash_file.write(f"[{now_str}] 시작 ({app_version})\n")
            crash_file.flush()
        except Exception:
            pass

    theme.load_fonts()

    from services.storage_service import StorageService
    from ui.main_window import MainWindow

    storage = StorageService()
    cfg, _, _ = storage.load_data()
    theme.set_ui_scale(getattr(cfg, "font_size", "M"))
    app.setStyleSheet(theme.get_qss())

    window = MainWindow(storage)
    window.show()
    code = app.exec()
    lock.unlock()

    if crash_file:
        try:
            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            crash_file.write(f"[{now_str}] 정상 종료\n")
            crash_file.flush()
        except Exception:
            pass

    return code


if __name__ == "__main__":
    sys.exit(main())
