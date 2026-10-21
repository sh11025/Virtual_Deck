"""
Virtual Deck 시작 파일
프로그램을 준비하고 유리 덱 창을 띄웁니다.
"""

import os
import sys


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

    # 덱이 두 개 동시에 뜨지 않도록
    lock = QLockFile(os.path.join(paths.data_dir(), ".running.lock"))
    lock.setStaleLockTime(0)
    if not lock.tryLock(200):
        from ui.widgets import inform
        theme.load_fonts()
        app.setStyleSheet(theme.get_qss())
        inform(None, "이미 실행 중이에요", "Virtual Deck 이 이미 켜져 있어요.\n트레이 아이콘이나 단축키로 열어 주세요.")
        return 0

    theme.load_fonts()

    from services.storage_service import StorageService
    from ui.main_window import MainWindow

    window = MainWindow(StorageService())
    window.show()
    code = app.exec()
    lock.unlock()
    return code


if __name__ == "__main__":
    sys.exit(main())
