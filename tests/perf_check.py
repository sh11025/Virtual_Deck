"""
Virtual Deck 성능 측정 스크립트 (오프스크린)
측정 항목:
1. 4x4 버튼판 한 번 다시 그리기
2. 버튼 hover 애니메이션 1프레임 그리기
3. 스타일 바꾸기(apply_config) 1회
4. 끄는 동안 위치 1회 바꾸기
"""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="vdeck_perf_")
os.environ["VIRTUALDECK_DATA_DIR"] = TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui import theme
theme.load_fonts()

import core.action_executor as AE
AE.ActionExecutor.execute = staticmethod(lambda t, d: (True, "ok"))

from services.storage_service import StorageService

from ui.main_window import MainWindow
MainWindow._check_pycaw = lambda self: None

def run_perf_check():
    st = StorageService()
    win = MainWindow(st)
    win.config.rows = 4
    win.config.cols = 4
    win.config.button_size = 94
    win.config.spacing = 6
    win.config.bg_type = "glass"
    win._rebuild_grid()
    win.show()
    app.processEvents()

    # 1. 4x4 버튼판 한 번 다시 그리기
    pix = QPixmap(win.size())
    t0 = time.perf_counter()
    win.render(pix)
    t_redraw = (time.perf_counter() - t0) * 1000

    # 2. 버튼 hover 애니메이션 1프레임
    from ui.deck_button import DeckButtonWidget
    btns = win.findChildren(DeckButtonWidget)
    first_btn = btns[0] if btns else None

    t_hover = 0.0
    if first_btn:
        first_btn._hover.value = 0.5
        btn_pix = QPixmap(first_btn.size())
        t0 = time.perf_counter()
        first_btn.render(btn_pix)
        t_hover = (time.perf_counter() - t0) * 1000

    # 3. 스타일 바꾸기(apply_config) 1회
    new_cfg = win.config.copy()
    new_cfg.theme = "dark" if new_cfg.theme == "light" else "light"
    new_cfg.show_labels = not new_cfg.show_labels
    t0 = time.perf_counter()
    win.apply_config(new_cfg)
    app.processEvents()
    t_apply_config = (time.perf_counter() - t0) * 1000

    # 4. 끄는 동안 위치 1회 바꾸기
    win._dragging = True
    win._drag_pos = QPoint(10, 10)
    t0 = time.perf_counter()
    win.move(win.x() + 15, win.y() + 15)
    win.grabber.window_moved()
    app.processEvents()
    t_drag_move = (time.perf_counter() - t0) * 1000
    win._dragging = False

    print("=" * 50)
    print("Virtual Deck 성능 측정 결과:")
    print(f"1. 4x4 버튼판 1회 다시 그리기: {t_redraw:.2f} ms")
    print(f"2. 버튼 hover 애니메이션 1프레임: {t_hover:.2f} ms")
    print(f"3. 스타일 바꾸기(apply_config) 1회: {t_apply_config:.2f} ms ({t_apply_config/1000:.3f} s)")
    print(f"4. 끄는 동안 위치 1회 바꾸기: {t_drag_move:.2f} ms")
    print("=" * 50)
    win.close()
    return t_redraw, t_hover, t_apply_config, t_drag_move

if __name__ == "__main__":
    run_perf_check()
