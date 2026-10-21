"""
알림(토스트)
덱 아래(또는 위)에 잠깐 떴다가 사라지는 작은 유리 알림입니다.
포커스를 빼앗지 않아서 작업을 방해하지 않습니다.
"""

from PySide6.QtCore import Qt, QTimer, QRectF, QPropertyAnimation, QEasingCurve, QPoint
from PySide6.QtGui import QPainter, QColor, QFont, QFontMetrics
from PySide6.QtWidgets import QWidget

from core import win32
from ui import theme
from ui.theme import T
from ui.glass import paint_glass, draw_icon


class Toast(QWidget):
    KINDS = {"ok": ("check", "#16a34a"), "error": ("warn", "#e23a3d"), "info": ("info", "#0ea5e9")}

    def __init__(self, anchor: QWidget):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint)
        self.anchor = anchor
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, True)
        self.text = ""
        self.kind = "info"
        self.font_ = theme.ui_font(13, QFont.DemiBold)
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._fade_out)
        self._anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.finished.connect(self._on_anim_done)
        self._hiding = False

    def show_message(self, text: str, kind: str = "info", ms: int = 2400):
        self.text = text
        self.kind = kind if kind in self.KINDS else "info"
        fm = QFontMetrics(self.font_)
        w = min(420, fm.horizontalAdvance(text) + 70)
        h = 50
        self.resize(w, h)
        self._place()
        self._hiding = False
        self._anim.stop()
        self.setWindowOpacity(0.0)
        self.show()
        win32.make_no_activate(int(self.winId()))
        self._anim.setDuration(180)
        self._anim.setStartValue(0.0)
        self._anim.setEndValue(1.0)
        self._anim.start()
        self._timer.start(ms)
        self.update()

    def _place(self):
        a = self.anchor.frameGeometry()
        screen = self.anchor.screen().availableGeometry()
        x = a.center().x() - self.width() // 2
        y = a.bottom() - 6
        if y + self.height() > screen.bottom():
            y = a.top() - self.height() + 6
        x = max(screen.left() + 4, min(x, screen.right() - self.width() - 4))
        self.move(QPoint(x, y))

    def _fade_out(self):
        self._hiding = True
        self._anim.stop()
        self._anim.setDuration(380)
        self._anim.setStartValue(self.windowOpacity())
        self._anim.setEndValue(0.0)
        self._anim.start()

    def _on_anim_done(self):
        if self._hiding:
            self.hide()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(6, 4, self.width() - 12, self.height() - 12)
        if T().dark:
            from ui.glass import rounded_path, soft_shadow
            soft_shadow(p, r, r.height() / 2, QColor(0, 0, 0, 140), spread=6, offset_y=3)
            p.fillPath(rounded_path(r, r.height() / 2), QColor(22, 28, 44, 238))
            paint_glass(p, r, r.height() / 2, fill=0.15, shadow=False)
        else:
            paint_glass(p, r, r.height() / 2, fill=0.9, shadow_strength=0.9)
        icon, color = self.KINDS[self.kind]
        draw_icon(p, icon, QRectF(r.left() + 13, r.center().y() - 9, 18, 18), QColor(color))
        p.setFont(self.font_)
        p.setPen(QColor(T().text))
        fm = QFontMetrics(self.font_)
        text_rect = QRectF(r.left() + 40, r.top(), r.width() - 54, r.height())
        p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft,
                   fm.elidedText(self.text, Qt.ElideRight, int(text_rect.width())))
