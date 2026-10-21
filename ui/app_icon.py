"""
앱 아이콘
유리판 위에 작은 유리 버튼 네 개(주황, 파랑, 민트, 투명)가 놓인 아이콘을 코드로 그립니다.
트레이 아이콘과 EXE 아이콘에 함께 사용합니다.
"""

from PySide6.QtCore import Qt, QRectF, QSize
from PySide6.QtGui import QPixmap, QPainter, QIcon, QColor

from ui import theme
from ui.glass import paint_glass, make_aurora, rounded_path


def make_app_pixmap(size: int = 256) -> QPixmap:
    prev = theme.T().name
    theme.set_theme("light")
    pix = QPixmap(size, size)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)
    m = size * 0.06
    plate = QRectF(m, m, size - 2 * m, size - 2 * m)
    radius = plate.width() * 0.25
    bg = make_aurora(QSize(int(plate.width()), int(plate.height())), False, seed=2)
    p.save()
    p.setClipPath(rounded_path(plate, radius))
    p.drawPixmap(plate.topLeft(), bg)
    p.fillRect(plate, QColor(255, 255, 255, 60))
    p.restore()
    paint_glass(p, plate, radius, fill=0.05, shadow=False, rainbow=1.0, highlight=0.6)
    gap = plate.width() * 0.07
    cell = (plate.width() - gap * 3) / 2
    tints = ["orange", "blue", "mint", "clear"]
    for i, t in enumerate(tints):
        r, c = divmod(i, 2)
        rect = QRectF(plate.left() + gap + c * (cell + gap), plate.top() + gap + r * (cell + gap), cell, cell)
        paint_glass(p, rect, cell * 0.28, tint=t, fill=0.75, shadow_strength=0.8)
    p.end()
    theme.set_theme(prev)
    return pix


def make_app_icon() -> QIcon:
    icon = QIcon()
    for s in (16, 24, 32, 48, 64, 128, 256):
        icon.addPixmap(make_app_pixmap(s))
    return icon
