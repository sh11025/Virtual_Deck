"""
공용 유리 위젯 모음
유리 버튼, 켜기/끄기 스위치, 탭, 색 고르기, 유리 대화상자, 단축키 입력칸 등을 제공합니다.
모든 창(설정창, 편집창 …)이 같은 모양을 쓰도록 여기 한곳에 모았습니다.
"""

from typing import List, Optional

from PySide6.QtCore import (
    Qt, QRectF, QPointF, QSize, Signal, QVariantAnimation, QEasingCurve, QPoint,
    QEvent, QObject,
)
from PySide6.QtGui import (
    QPainter, QColor, QFont, QPixmap, QKeyEvent, QMouseEvent, QIcon, QPen, QRadialGradient,
    QFontMetrics,
)
from PySide6.QtWidgets import (
    QAbstractButton, QPushButton, QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QSizePolicy, QLineEdit, QComboBox, QMenu, QSpinBox, QColorDialog,
)

from models.config_model import clean_custom_colors
from ui import theme
from ui.theme import T, tint_colors
from ui.glass import (
    paint_glass, paint_glass_under, paint_slot, draw_icon, make_aurora, soft_shadow, rounded_path,
    icon_pixmap, get_glass_pixmap,
)


class _NoWheelFilter(QObject):
    def eventFilter(self, obj, event):
        if event.type() == QEvent.Wheel:
            if not obj.hasFocus():
                event.ignore()
                return True
        return super().eventFilter(obj, event)

_NO_WHEEL_FILTER = _NoWheelFilter()

def no_wheel(widget):
    """포커스가 없을 때 마우스 휠로 값이 바뀌는 것을 방지합니다."""
    widget.setFocusPolicy(Qt.StrongFocus)
    widget.installEventFilter(_NO_WHEEL_FILTER)
    return widget


def make_spin(min_val: int, max_val: int, value: Optional[int] = None, suffix: str = "", min_width: int = 110) -> QSpinBox:
    """가운데 정렬 및 [- 숫자 +] 모양의 숫자 조절 상자를 만듭니다."""
    spin = no_wheel(QSpinBox())
    spin.setRange(min_val, max_val)
    if value is not None:
        spin.setValue(value)
    if suffix:
        spin.setSuffix(suffix)
    spin.setAlignment(Qt.AlignCenter)
    spin.setMinimumWidth(min_width)
    return spin


# ------------------------------------------------------------------ 공통 도우미
def find_backdrop(widget: QWidget):
    """
    위젯 뒤에 비칠 배경 그림을 찾습니다.
    부모 중에 backdrop_pixmap() 을 가진 위젯(덱 본체, 유리 대화상자)이 있으면
    그 그림과 이 위젯의 위치를 돌려줍니다.
    """
    host = widget.parentWidget()
    while host is not None:
        fn = getattr(host, "backdrop_pixmap", None)
        if callable(fn):
            pix = fn()
            if pix is None or pix.isNull():
                return None, None
            top_left = widget.mapTo(host, QPoint(0, 0))
            dpr = pix.devicePixelRatio() or 1.0
            r = QRectF(top_left.x() * dpr, top_left.y() * dpr, widget.width() * dpr, widget.height() * dpr)
            return pix, r
        host = host.parentWidget()
    return None, None


class _Anim:
    """0~1 사이를 부드럽게 오가는 값 (마우스 올림/누름 효과용)"""

    def __init__(self, owner: QWidget, duration: int = 140):
        self.value = 0.0
        self._anim = QVariantAnimation(owner)
        self._anim.setDuration(duration)
        self._anim.setEasingCurve(QEasingCurve.OutCubic)
        self._anim.valueChanged.connect(self._set)
        self._owner = owner

    def _set(self, v):
        self.value = float(v)
        self._owner.update()

    def to(self, target: float, duration: int = None, easing=QEasingCurve.OutCubic):
        self._anim.stop()
        if duration is not None:
            self._anim.setDuration(duration)
        self._anim.setEasingCurve(easing)
        self._anim.setStartValue(self.value)
        self._anim.setEndValue(float(target))
        self._anim.start()


# ------------------------------------------------------------------ 유리 버튼
class GlassButton(QPushButton):
    """
    유리 버튼
    tint: 'clear'(투명) 또는 'orange', 'blue', 'mint', 'red' …
    icon_name: 선 아이콘 이름 (glass.draw_icon 참고)
    square: 아이콘만 있는 정사각 버튼
    """
    draw_text = True  # False 이면 기본 글자 그리기를 생략(서브클래스가 직접 그릴 때)
    MARGIN = (3, 2, 3, 5)  # 그림자 자리 (왼, 위, 오른, 아래)

    def __init__(self, text: str = "", tint: str = "clear", icon_name: str = "",
                 square: bool = False, size: int = None, parent=None):
        super().__init__(text, parent)
        self.tint = tint
        self.icon_name = icon_name
        self.square = square
        self.fixed = size
        self._hover = _Anim(self)
        self._press = _Anim(self, 90)
        self._ripple = _Anim(self, 600)
        self._ripple_pos = QPointF()
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover, True)
        self.setFont(theme.dialog_font(14, QFont.DemiBold))
        self.setSizePolicy(QSizePolicy.Fixed if square else QSizePolicy.Minimum, QSizePolicy.Fixed)
        self.setFocusPolicy(Qt.TabFocus)

    def set_tint(self, tint: str):
        self.tint = tint
        self.update()

    def sizeHint(self) -> QSize:
        l, t, r, b = self.MARGIN
        if self.square:
            s = self.fixed or 32
            return QSize(s + l + r, s + t + b)
        fm = self.fontMetrics()
        w = fm.horizontalAdvance(self.text()) + 34 + (20 if self.icon_name else 0)
        h = self.fixed or 38
        return QSize(max(w, 64) + l + r, h + t + b)

    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    def enterEvent(self, e):
        self._hover.to(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._hover.to(0.0)
        if self._press.value > 0:
            self._press.to(0.0, 360, QEasingCurve.OutBack)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._press.to(1.0, 90)
            self._ripple_pos = e.position()
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        # 놓으면 통 튀어 오르는 젤리 반동 + 누른 자리에서 물결
        self._press.to(0.0, 480, QEasingCurve.OutBack)
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self._ripple.value = 0.0
            self._ripple.to(1.0, 650, QEasingCurve.OutQuad)
        super().mouseReleaseEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        l, t, r, b = self.MARGIN
        rect = QRectF(l, t, self.width() - l - r, self.height() - t - b)
        press = self._press.value
        if press:
            k = 0.045 * press
            rect = rect.adjusted(rect.width() * k, rect.height() * k, -rect.width() * k, -rect.height() * k)
        enabled = self.isEnabled()
        rv = self._ripple.value
        ripple = (self._ripple_pos, rv, QColor(255, 255, 255, 235)) if 0 < rv < 1 else None
        if not enabled:
            p.setOpacity(0.45)
        radius = min(rect.height() / 2, 12 if self.square else rect.height() / 2)
        backdrop, brect = find_backdrop(self)
        checked = self.isCheckable() and self.isChecked()
        tint = self.tint if not checked else "blue"
        hv = self._hover.value if enabled else 0.0

        paint_glass_under(p, rect, radius, tint=tint, hover=hv, press=press,
                          shadow_strength=0.8, shadow_max=3.0)

        # 렌즈 효과
        if backdrop is not None and not backdrop.isNull() and brect is not None:
            p.save()
            p.setClipPath(rounded_path(rect, radius), Qt.IntersectClip)
            p.drawPixmap(rect, backdrop, brect)
            p.restore()

        # 유리 층 캐시 합성
        dpr = self.devicePixelRatioF()
        dark = T().dark
        fill_val = 0.15 if backdrop is not None else 0.70
        pix0 = get_glass_pixmap(rect.width(), rect.height(), radius, tint, dark, dpr, 0, fill=fill_val)
        pix1 = get_glass_pixmap(rect.width(), rect.height(), radius, tint, dark, dpr, 1, fill=fill_val)

        p.save()
        p.drawPixmap(rect, pix0, QRectF(pix0.rect()))
        if hv > 0.001:
            p.setOpacity(min(1.0, hv))
            p.drawPixmap(rect, pix1, QRectF(pix1.rect()))
        p.restore()

        if ripple is not None and 0.0 < rv < 1.0:
            p.save()
            p.setClipPath(rounded_path(rect, radius), Qt.IntersectClip)
            rg = QRadialGradient(self._ripple_pos, max(rect.width(), rect.height()) * rv)
            rg.setColorAt(0.0, QColor(255, 255, 255, int(100 * (1 - rv))))
            rg.setColorAt(1.0, QColor(255, 255, 255, 0))
            p.fillRect(rect, rg)
            p.restore()

        colors = tint_colors(tint)
        fg = colors[2] if colors else QColor(T().text)
        if not colors and self._hover.value > 0.5 and enabled:
            fg = QColor(T().accent_deep)
        if self.square and self.icon_name:
            s = rect.height() * 0.46
            draw_icon(p, self.icon_name, QRectF(rect.center().x() - s / 2, rect.center().y() - s / 2, s, s), fg)
        else:
            p.setFont(self.font())
            p.setPen(fg)
            label = self.text() if self.draw_text else ""
            fm = self.fontMetrics()
            if self.icon_name:
                avail_text_w = max(0, rect.width() - 16 - 6 - 16)
                if fm.horizontalAdvance(label) > avail_text_w:
                    label = fm.elidedText(label, Qt.ElideRight, int(avail_text_w))
                total = 16 + 6 + fm.horizontalAdvance(label)
                x0 = max(rect.left() + 8, rect.center().x() - total / 2)
                draw_icon(p, self.icon_name, QRectF(x0, rect.center().y() - 8, 16, 16), fg)
                text_rect = QRectF(x0 + 22, rect.top(), max(0, rect.right() - (x0 + 22) - 4), rect.height())
                p.drawText(text_rect, Qt.AlignVCenter | Qt.AlignLeft, label)
            elif label:
                avail_w = max(0, rect.width() - 12)
                if fm.horizontalAdvance(label) > avail_w:
                    label = fm.elidedText(label, Qt.ElideRight, int(avail_w))
                p.drawText(rect, Qt.AlignCenter, label)


# ------------------------------------------------------------------ 켜기/끄기 스위치
class GlassToggle(QAbstractButton):
    """
    참고 이미지의 민트색 유리 스위치
    - 손잡이가 움직이는 동안 물방울처럼 늘어났다 돌아옴
    - 누르고 있으면 손잡이가 살짝 넓어짐
    - 민트색이 손잡이를 따라 차오름
    """

    def __init__(self, checked: bool = False, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setChecked(checked)
        self.setCursor(Qt.PointingHandCursor)
        self._pos = _Anim(self, 320)
        self._pos.value = 1.0 if checked else 0.0
        self._hover = _Anim(self)
        self._hold = _Anim(self, 120)
        self.toggled.connect(lambda on: self._pos.to(1.0 if on else 0.0, 340, QEasingCurve.OutBack))
        self.setFixedSize(54, 32)

    def setChecked(self, on: bool):
        super().setChecked(on)
        if hasattr(self, "_pos"):
            self._pos.value = 1.0 if on else 0.0
            self.update()

    def enterEvent(self, e):
        self._hover.to(1.0)

    def leaveEvent(self, e):
        self._hover.to(0.0)
        self._hold.to(0.0)

    def mousePressEvent(self, e):
        self._hold.to(1.0)
        super().mousePressEvent(e)

    def mouseReleaseEvent(self, e):
        self._hold.to(0.0, 260, QEasingCurve.OutBack)
        super().mouseReleaseEvent(e)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        track = QRectF(2, 3, self.width() - 4, self.height() - 7)
        r = track.height() / 2
        v = self._pos.value                      # OutBack 이라 0~1 을 살짝 넘나듦
        vc = max(0.0, min(1.0, v))
        d = track.height() - 4
        # 움직이는 중간에 가장 길게 늘어남 (4v(1-v)), 누르고 있으면 조금 더 넓게
        stretch = d * (0.55 * 4 * vc * (1 - vc) + 0.22 * self._hold.value)
        kw = d + stretch
        travel = track.width() - kw - 4
        x = track.left() + 2 + travel * vc + (v - vc) * d * 0.6
        knob = QRectF(x, track.top() + 2 + stretch * 0.04, kw, d - stretch * 0.08)

        paint_slot(p, track, r, self._hover.value)
        if vc > 0.01:
            # 민트색이 손잡이 오른쪽 끝까지 차오름
            p.save()
            p.setClipRect(QRectF(track.left(), track.top(), knob.right() - track.left() + 1, track.height()))
            p.setOpacity(p.opacity() * min(1.0, vc * 2.5))
            paint_glass(p, track, r, tint="mint", shadow=False, rainbow=0.4, highlight=0.8)
            p.restore()
        paint_glass(p, knob, knob.height() / 2, fill=0.92, shadow_strength=0.9, hover=self._hover.value,
                    rainbow=0.5)


# ------------------------------------------------------------------ 탭 (알약 모양)
class SegmentedTabs(QWidget):
    """움푹한 홈 위에서 유리 알약이 미끄러지는 탭"""

    currentChanged = Signal(int)

    def __init__(self, labels: List[str], parent=None):
        super().__init__(parent)
        self.labels = labels
        self.index = 0
        self._l = _Anim(self, 260)      # 알약 왼쪽 끝
        self._r = _Anim(self, 260)      # 알약 오른쪽 끝
        self._r.value = 1.0
        self._hover_i = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedHeight(46)
        self.setFont(theme.dialog_font(14, QFont.DemiBold))

    def setCurrentIndex(self, i: int, animate=True):
        if i == self.index:
            return
        going_right = i > self.index
        self.index = i
        if animate:
            # 가는 쪽 끝은 빨리, 반대쪽 끝은 늦게 → 늘어났다가 따라붙는 액체 느낌
            fast, slow = 200, 420
            self._l.to(float(i), slow if going_right else fast, QEasingCurve.OutCubic if going_right else QEasingCurve.OutBack)
            self._r.to(float(i + 1), fast if going_right else slow, QEasingCurve.OutBack if going_right else QEasingCurve.OutCubic)
        else:
            self._l.value, self._r.value = float(i), float(i + 1)
            self.update()
        self.currentChanged.emit(i)

    def _seg_rect(self, pos: float) -> QRectF:
        track = QRectF(1, 2, self.width() - 2, self.height() - 6)
        w = (track.width() - 6) / max(1, len(self.labels))
        return QRectF(track.left() + 3 + w * pos, track.top() + 3, w, track.height() - 6)

    def mouseMoveEvent(self, e):
        w = self.width() / max(1, len(self.labels))
        i = int(e.position().x() // w)
        if i != self._hover_i:
            self._hover_i = i
            self.update()

    def leaveEvent(self, e):
        self._hover_i = -1
        self.update()

    def mousePressEvent(self, e):
        w = self.width() / max(1, len(self.labels))
        i = max(0, min(len(self.labels) - 1, int(e.position().x() // w)))
        self.setCurrentIndex(i)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        track = QRectF(1, 2, self.width() - 2, self.height() - 6)
        paint_slot(p, track, track.height() / 2)
        a, b = self._seg_rect(self._l.value), self._seg_rect(self._r.value - 1)
        left = min(a.left(), b.left())
        right = max(a.right(), b.right())
        stretch = max(0.0, (right - left) - a.width())
        seg = QRectF(left, a.top() + min(3.0, stretch * 0.03), right - left, a.height() - min(6.0, stretch * 0.06))
        paint_glass(p, seg, seg.height() / 2, fill=0.85, shadow_strength=0.7, rainbow=0.6,
                    backdrop=None)
        p.setFont(self.font())
        for i, label in enumerate(self.labels):
            r = self._seg_rect(i)
            sel = i == self.index
            c = QColor(T().text) if sel else QColor(T().text_dim)
            if not sel and i == self._hover_i:
                c = QColor(T().accent_deep)
            p.setPen(c)
            p.drawText(r, Qt.AlignCenter, label)


# ------------------------------------------------------------------ 색 고르기
def pick_color(parent, initial, title="색 고르기"):
    """맨 위에 뜨는 색 고르기 창. 고른 QColor를 돌려주고, 취소하면 None."""
    dlg = QColorDialog(QColor(initial), parent)
    dlg.setWindowTitle(title)
    dlg.setOption(QColorDialog.ColorDialogOption.DontUseNativeDialog, True)
    dlg.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, True)
    t = T()
    # 어두운 테마에서도 글자가 보이도록 배경과 버튼을 테마 색으로 직접 지정
    dlg.setStyleSheet(
        f"QColorDialog {{ background: {t.popup_bg}; }}"
        f"QColorDialog QLabel {{ color: {t.text}; background: transparent; }}"
        f"QColorDialog QPushButton {{ background: {t.input_bg}; color: {t.text};"
        f" border: 1px solid {t.input_border}; border-radius: 10px; padding: 6px 16px; }}"
        f"QColorDialog QPushButton:hover {{ border: 1px solid {t.accent}; }}"
    )
    owner = parent
    while owner is not None and not hasattr(owner, "_menu_open"):
        owner = owner.parent() if hasattr(owner, "parent") else None
    if owner is not None:
        owner._menu_open += 1
    try:
        ok = dlg.exec()
    finally:
        if owner is not None:
            owner._menu_open -= 1
    color = dlg.selectedColor()
    return color if ok and color.isValid() else None


class ColorChips(QWidget):
    """유리 색을 고르는 동그란 칩 줄"""

    ADD_KEY = "__add__"

    changed = Signal(str)
    custom_added = Signal(str)
    custom_removed = Signal(str)

    def __init__(self, parent=None, mode: str = "tint"):
        super().__init__(parent)
        self.mode = mode     # 'tint' = 유리 색, 'icon' = 아이콘 색
        self.table = theme.TINTS if mode == "tint" else theme.ICON_COLORS
        self.base_keys = list(theme.BUTTON_TINT_KEYS) if mode == "tint" else list(self.table.keys())
        self.custom = []
        self._temp = None
        self.keys = list(self.base_keys) + [self.ADD_KEY]
        self.current = self.keys[0]
        self._hover = -1
        self._pop = _Anim(self, 420)
        self._pop.value = 1.0
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.chip = 30
        self.gap = 10
        self.cols = max(4, len(self.keys))
        self.setMinimumWidth(4 * (self.chip + self.gap))
        self._update_layout()

    def set_custom(self, colors):
        self.custom = clean_custom_colors(colors)
        self._rebuild_keys()

    def _rebuild_keys(self):
        if theme.is_hex_color(self.current) and self.current not in self.custom:
            self._temp = self.current
        else:
            self._temp = None
        self.keys = self.base_keys + self.custom + ([self._temp] if self._temp and self._temp not in self.custom else []) + [self.ADD_KEY]
        self._update_layout()
        self.update()

    def _update_layout(self):
        rows = (len(self.keys) + self.cols - 1) // self.cols
        self.setFixedHeight(rows * (self.chip + self.gap) + 8)

    def resizeEvent(self, e):
        new_cols = max(4, (self.width() - 8) // (self.chip + self.gap))
        if new_cols != self.cols:
            self.cols = new_cols
            self._update_layout()
        super().resizeEvent(e)

    def set_current(self, key: str):
        if key == self.ADD_KEY:
            self.current = self.base_keys[0]
        elif key in self.keys:
            self.current = key
        elif theme.is_hex_color(key):
            self.current = key
            self._rebuild_keys()
        else:
            self.current = self.base_keys[0]
        self.update()

    def _pick_custom(self):
        initial = QColor(self.current if theme.is_hex_color(self.current) else "#4f8cff")
        c = pick_color(self.window(), initial, "색 고르기")
        if c is not None:
            self.add_custom(c.name().lower())

    def add_custom(self, hex_color: str):
        if not theme.is_hex_color(hex_color):
            return
        hex_color = hex_color.lower()
        self.custom = clean_custom_colors([hex_color] + self.custom)
        self.current = hex_color
        self._rebuild_keys()
        self.custom_added.emit(hex_color)
        self.changed.emit(self.current)

    def remove_custom(self, hex_color: str):
        prev = self.current
        self.custom = [c for c in self.custom if c.lower() != hex_color.lower()]
        if self.current.lower() == hex_color.lower():
            self.current = self.base_keys[0]
        self._rebuild_keys()
        self.custom_removed.emit(hex_color)
        if self.current != prev:
            self.changed.emit(self.current)

    def _tip(self, key: str) -> str:
        if theme.is_hex_color(key):
            return f"내 색 {key}"
        if key == self.ADD_KEY:
            return "색 직접 고르기"
        return self.table.get(key, ("",))[0]

    def _rect(self, i) -> QRectF:
        r, c = divmod(i, self.cols)
        return QRectF(4 + c * (self.chip + self.gap), 4 + r * (self.chip + self.gap), self.chip, self.chip)

    def _index_at(self, pos) -> int:
        for i in range(len(self.keys)):
            if self._rect(i).adjusted(-4, -4, 4, 4).contains(pos):
                return i
        return -1

    def _dirty(self, i):
        """칩 하나가 있던 자리만 다시 그리기 위한 영역"""
        if i < 0 or i >= len(self.keys):
            return
        self.update(self._rect(i).adjusted(-6, -6, 6, 6).toAlignedRect())

    def mouseMoveEvent(self, e):
        i = self._index_at(e.position())
        if i != self._hover:
            old = self._hover
            self._hover = i
            self.setToolTip(self._tip(self.keys[i]) if i >= 0 else "")
            self._dirty(old)
            self._dirty(i)

    def leaveEvent(self, e):
        old = self._hover
        self._hover = -1
        self._dirty(old)

    def mousePressEvent(self, e):
        i = self._index_at(e.position())
        if i < 0:
            return
        key = self.keys[i]
        if e.button() == Qt.LeftButton:
            if key == self.ADD_KEY:
                self._pick_custom()
                return
            self.current = key
            self._pop.value = 0.0
            self._pop.to(1.0, 420, QEasingCurve.OutBack)
            self.changed.emit(self.current)
        elif e.button() == Qt.RightButton:
            if key in self.custom and theme.is_hex_color(key):
                self._context_menu(key, e.globalPosition().toPoint())

    def _context_menu(self, key, pos):
        menu = glass_menu(self)
        act = menu.addAction("이 색 지우기")
        chosen = menu.exec(pos)
        if chosen is act:
            self.remove_custom(key)

    def paintEvent(self, ev):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        clip = QRectF(ev.rect())
        for i, key in enumerate(self.keys):
            r = self._rect(i)
            if not r.adjusted(-6, -6, 6, 6).intersects(clip):
                continue    # 바뀐 곳만 다시 그림 (렉 줄이기)
            sel = (key != self.ADD_KEY and key == self.current)
            if sel:  # 고른 칩은 톡 튀어나오는 효과
                k = (1 - self._pop.value) * 0.18
                r = r.adjusted(r.width() * k, r.height() * k, -r.width() * k, -r.height() * k)
                p.setPen(QPen(QColor(T().accent), 2.2))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(self._rect(i).adjusted(-3.5, -3.5, 3.5, 3.5))
            hov = 1.0 if i == self._hover else 0.0
            if key == self.ADD_KEY:
                paint_glass(p, r, r.height() / 2, hover=hov, shadow_strength=0.6, rainbow=0.5, fill=0.8)
                p.setFont(theme.dialog_font(int(self.chip * 0.6), QFont.Bold))
                p.setPen(QColor(T().text_dim))
                p.drawText(r, Qt.AlignCenter, "+")
            elif self.mode == "tint":
                paint_glass(p, r, r.height() / 2, tint=key, hover=hov, shadow_strength=0.6, rainbow=0.5, fill=0.8)
            else:
                paint_glass(p, r, r.height() / 2, hover=hov, shadow_strength=0.6, rainbow=0.5, fill=0.8)
                if theme.is_hex_color(key):
                    p.setPen(QPen(QColor(0, 0, 0, 40), 1))
                    p.setBrush(QColor(key))
                    p.drawEllipse(r.center(), r.width() * 0.26, r.width() * 0.26)
                else:
                    color = self.table[key][1]
                    if color is None:   # 자동: 'A' 표시
                        p.setFont(theme.dialog_font(12, QFont.Bold))
                        p.setPen(QColor(T().text_dim))
                        p.drawText(r, Qt.AlignCenter, "A")
                    else:
                        p.setPen(QPen(QColor(0, 0, 0, 40), 1))
                        p.setBrush(QColor(color))
                        p.drawEllipse(r.center(), r.width() * 0.26, r.width() * 0.26)


# ------------------------------------------------------------------ 유리 대화상자
class GlassDialog(QDialog):
    """
    테두리 없는 유리 대화상자. 제목줄(끌어서 이동 가능)과 닫기 버튼이 있고,
    본문은 self.body (QVBoxLayout) 에 넣으면 됩니다.
    """
    SHADOW = 22

    def __init__(self, title: str, subtitle: str = "", parent=None, width: int = 520, modeless: bool = False):
        super().__init__(parent)
        self.modeless = modeless
        flags = (Qt.Tool | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint) if modeless else (Qt.Dialog | Qt.FramelessWindowHint)
        if parent is not None:
            is_top = bool(parent.windowFlags() & Qt.WindowStaysOnTopHint) or getattr(parent, "is_always_on_top", False)
            if is_top:
                flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setWindowTitle(title)
        self.setModal(not modeless)
        self._drag = None
        self._bg_cache: Optional[QPixmap] = None
        self._bg_size = QSize()

        outer = QVBoxLayout(self)
        s = self.SHADOW
        outer.setContentsMargins(s, s - 6, s, s + 4)
        outer.setSpacing(0)

        self.panel = QWidget(self)
        self.panel.setObjectName("glassPanel")
        self.panel.setAttribute(Qt.WA_TranslucentBackground, True)
        self.panel.backdrop_pixmap = self.backdrop_pixmap   # 안쪽 유리 버튼들이 비춰 볼 배경
        outer.addWidget(self.panel)
        root = QVBoxLayout(self.panel)
        root.setContentsMargins(22, 16, 22, 20)
        root.setSpacing(12)

        # 제목줄
        head = QHBoxLayout()
        head.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(1)
        self.title_label = QLabel(title)
        self.title_label.setProperty("role", "title")
        titles.addWidget(self.title_label)
        if subtitle:
            sub = QLabel(subtitle)
            sub.setProperty("role", "hint")
            titles.addWidget(sub)
        head.addLayout(titles, 1)
        self.close_btn = GlassButton(icon_name="close", square=True, size=28)
        self.close_btn.setToolTip("닫기")
        self.close_btn.clicked.connect(self.reject)
        head.addWidget(self.close_btn, 0, Qt.AlignTop)
        root.addLayout(head)

        self.body = QVBoxLayout()
        self.body.setSpacing(10)
        root.addLayout(self.body, 1)

        self.footer = QHBoxLayout()
        self.footer.setSpacing(8)
        root.addLayout(self.footer)

        self.resize(width + s * 2, 200)

    # 배경 (덱과 같은 빛 번짐 + 유리 막) — (크기, 밝게/어둡게, dpr) 별 클래스 단위 캐시
    _aurora_dialog_cache = {}

    def backdrop_pixmap(self) -> QPixmap:
        size = self.panel.size()
        dpr = self.devicePixelRatioF()
        key = (size.width(), size.height(), T().dark, dpr)
        cached = GlassDialog._aurora_dialog_cache.get(key)
        if cached is not None and not cached.isNull():
            return cached
        pix = make_aurora(QSize(int(size.width() * dpr), int(size.height() * dpr)), T().dark, seed=3)
        vp = QPainter(pix)
        vp.fillRect(pix.rect(), QColor(255, 255, 255, 120) if not T().dark else QColor(14, 18, 30, 110))
        vp.end()
        pix.setDevicePixelRatio(dpr)
        GlassDialog._aurora_dialog_cache[key] = pix
        return pix

    def showEvent(self, e):
        super().showEvent(e)
        from core.shortcut_manager import ShortcutManager
        from core.app_detector import AppDetector
        ShortcutManager.add_own_hwnd(int(self.winId()))
        AppDetector.add_own_hwnd(int(self.winId()))
        if self.parentWidget() is not None and not getattr(self, "_placed", False):
            self._placed = True
            self._center_on_screen()

    def _center_on_screen(self):
        anchor = self.parentWidget().window()
        screen = anchor.screen() if anchor else self.screen()
        avail = screen.availableGeometry()
        geo = self.frameGeometry()
        center = anchor.frameGeometry().center() if anchor else avail.center()
        geo.moveCenter(center)
        x = max(avail.left(), min(geo.left(), avail.right() - geo.width()))
        y = max(avail.top(), min(geo.top(), avail.bottom() - geo.height()))
        self.move(x, y)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.panel.geometry())
        radius = 26
        dark = T().dark
        soft_shadow(p, rect, radius, QColor(0, 0, 0, 150) if dark else QColor(30, 50, 90, 90),
                    spread=18, offset_y=6)
        path = rounded_path(rect, radius)
        p.save()
        p.setClipPath(path)
        bg = self.backdrop_pixmap()
        p.drawPixmap(rect, bg, QRectF(bg.rect()))
        p.restore()
        paint_glass(p, rect, radius, fill=0.0, shadow=False, rainbow=0.9, highlight=0.35)

    def mousePressEvent(self, e: QMouseEvent):
        if e.button() == Qt.LeftButton and e.position().y() < self.SHADOW + 60:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e: QMouseEvent):
        if self._drag is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None


def section_label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "section")
    return lab


def hint_label(text: str) -> QLabel:
    lab = QLabel(text)
    lab.setProperty("role", "hint")
    lab.setWordWrap(True)
    return lab


def row(*widgets, stretch_index: int = -1, spacing: int = 8) -> QHBoxLayout:
    lay = QHBoxLayout()
    lay.setSpacing(spacing)
    for i, w in enumerate(widgets):
        if w is None:
            lay.addStretch(1)
        elif isinstance(w, QHBoxLayout) or isinstance(w, QVBoxLayout):
            lay.addLayout(w)
        else:
            lay.addWidget(w, 1 if i == stretch_index else 0)
    return lay


class GlassMessage(GlassDialog):
    """확인/알림 창"""

    def __init__(self, title: str, text: str, ok_text="확인", cancel_text: str = "",
                 danger=False, parent=None):
        super().__init__(title, parent=parent, width=400)
        lab = QLabel(text)
        lab.setWordWrap(True)
        lab.setMinimumHeight(40)
        self.body.addWidget(lab)
        self.footer.addStretch(1)
        if cancel_text:
            cancel = GlassButton(cancel_text)
            cancel.clicked.connect(self.reject)
            self.footer.addWidget(cancel)
        ok = GlassButton(ok_text, tint="red" if danger else "orange")
        ok.clicked.connect(self.accept)
        ok.setDefault(True)
        self.footer.addWidget(ok)
        self.adjustSize()


def ask(parent, title: str, text: str, ok_text="확인", cancel_text="취소", danger=False) -> bool:
    return GlassMessage(title, text, ok_text, cancel_text, danger, parent).exec() == QDialog.Accepted


def inform(parent, title: str, text: str) -> None:
    GlassMessage(title, text, parent=parent).exec()


def ask_text(parent, title: str, label: str, default: str = "", ok_text: str = "확인"):
    """글자 한 줄을 입력받는 창. 취소하면 None"""
    dlg = GlassDialog(title, parent=parent, width=380)
    lab = QLabel(label)
    lab.setWordWrap(True)
    dlg.body.addWidget(lab)
    edit = QLineEdit(default)
    edit.selectAll()
    dlg.body.addWidget(edit)
    dlg.footer.addStretch(1)
    cancel = GlassButton("취소")
    cancel.clicked.connect(dlg.reject)
    ok = GlassButton(ok_text, tint="orange")
    ok.clicked.connect(dlg.accept)
    edit.returnPressed.connect(dlg.accept)
    dlg.footer.addWidget(cancel)
    dlg.footer.addWidget(ok)
    dlg.adjustSize()
    edit.setFocus()
    if dlg.exec() == QDialog.Accepted and edit.text().strip():
        return edit.text().strip()
    return None


def ask_save_changes(parent, title: str = "저장할까요?",
                     text: str = "바꾼 내용이 있습니다. 저장하고 계속할까요?") -> str:
    """
    저장 / 저장 안 함 / 취소 3지선다 확인창.
    반환값: 'save' | 'discard' | 'cancel'
    """
    dlg = GlassDialog(title, parent=parent, width=420)
    lab = QLabel(text)
    lab.setWordWrap(True)
    lab.setMinimumHeight(40)
    dlg.body.addWidget(lab)
    dlg.footer.addStretch(1)

    choice = "cancel"

    def on_save():
        nonlocal choice
        choice = "save"
        dlg.accept()

    def on_discard():
        nonlocal choice
        choice = "discard"
        dlg.reject()

    def on_cancel():
        nonlocal choice
        choice = "cancel"
        dlg.reject()

    btn_cancel = GlassButton("취소")
    btn_cancel.clicked.connect(on_cancel)
    btn_discard = GlassButton("저장 안 함")
    btn_discard.clicked.connect(on_discard)
    btn_save = GlassButton("저장", tint="orange")
    btn_save.clicked.connect(on_save)
    btn_save.setDefault(True)

    dlg.footer.addWidget(btn_cancel)
    dlg.footer.addWidget(btn_discard)
    dlg.footer.addWidget(btn_save)
    dlg.adjustSize()
    dlg.exec()
    return choice


def glass_menu(parent=None) -> QMenu:
    """둥근 모서리가 깔끔하게 보이는 메뉴"""
    menu = QMenu(parent)
    menu.setWindowFlags(menu.windowFlags() | Qt.FramelessWindowHint | Qt.NoDropShadowWindowHint | Qt.WindowStaysOnTopHint)
    menu.setAttribute(Qt.WA_TranslucentBackground, True)
    return menu


def menu_icon(name: str) -> QIcon:
    return QIcon(icon_pixmap(name, 16, QColor(T().text_dim)))


# ------------------------------------------------------------------ 단축키 입력
def qt_key_to_name(key: int, text: str = "") -> str:
    """키보드 이벤트를 'S', 'F5', 'Enter' 같은 이름으로 바꿉니다."""
    if Qt.Key_F1 <= key <= Qt.Key_F24:
        return f"F{key - Qt.Key_F1 + 1}"
    if Qt.Key_A <= key <= Qt.Key_Z or Qt.Key_0 <= key <= Qt.Key_9:
        return chr(key)
    table = {
        Qt.Key_Return: "Enter", Qt.Key_Enter: "Enter", Qt.Key_Escape: "Esc",
        Qt.Key_Tab: "Tab", Qt.Key_Space: "Space", Qt.Key_Backspace: "Backspace",
        Qt.Key_Delete: "Delete", Qt.Key_Insert: "Insert", Qt.Key_Home: "Home", Qt.Key_End: "End",
        Qt.Key_PageUp: "PageUp", Qt.Key_PageDown: "PageDown",
        Qt.Key_Up: "Up", Qt.Key_Down: "Down", Qt.Key_Left: "Left", Qt.Key_Right: "Right",
        Qt.Key_Print: "PrintScreen", Qt.Key_CapsLock: "CapsLock", Qt.Key_Menu: "Menu",
        Qt.Key_Pause: "Pause",
        Qt.Key_Semicolon: ";", Qt.Key_Equal: "=", Qt.Key_Comma: ",", Qt.Key_Minus: "-",
        Qt.Key_Period: ".", Qt.Key_Slash: "/", Qt.Key_QuoteLeft: "`", Qt.Key_BracketLeft: "[",
        Qt.Key_Backslash: "\\", Qt.Key_BracketRight: "]", Qt.Key_Apostrophe: "'", Qt.Key_Plus: "plus",
        Qt.Key_VolumeUp: "VolumeUp", Qt.Key_VolumeDown: "VolumeDown", Qt.Key_VolumeMute: "VolumeMute",
        Qt.Key_MediaPlay: "MediaPlayPause", Qt.Key_MediaTogglePlayPause: "MediaPlayPause",
        Qt.Key_MediaNext: "MediaNext", Qt.Key_MediaPrevious: "MediaPrev", Qt.Key_MediaStop: "MediaStop",
    }
    return table.get(key, "")


class KeyCaptureEdit(QLineEdit):
    """클릭한 뒤 키를 누르면 그 키 이름이 들어가는 입력칸 (Ctrl 등과 함께 눌러도 OK)"""

    captured = Signal(str, list)   # 주 키, 함께 누른 조합 키 목록

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText("여기를 누른 뒤 키보드로 입력")
        self.setCursor(Qt.PointingHandCursor)

    def focusInEvent(self, e):
        self.setProperty("capturing", True)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusInEvent(e)

    def focusOutEvent(self, e):
        self.setProperty("capturing", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().focusOutEvent(e)

    def keyPressEvent(self, e: QKeyEvent):
        key = e.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr):
            return
        name = qt_key_to_name(key, e.text())
        if not name:
            return
        mods = []
        m = e.modifiers()
        if m & Qt.ControlModifier:
            mods.append("Ctrl")
        if m & Qt.ShiftModifier:
            mods.append("Shift")
        if m & Qt.AltModifier:
            mods.append("Alt")
        if m & Qt.MetaModifier:
            mods.append("Win")
        self.captured.emit(name, mods)


class ModifierChip(QAbstractButton):
    """Ctrl / Shift / Alt / Win 켜고 끄는 작은 유리 칩"""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setText(text)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = _Anim(self)
        self.toggled.connect(lambda _: self.update())
        self.setFont(theme.dialog_font(12, QFont.Bold))
        self.setFixedSize(60, 36)

    def enterEvent(self, e):
        self._hover.to(1.0)

    def leaveEvent(self, e):
        self._hover.to(0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(2, 2, self.width() - 4, self.height() - 6)
        if self.isChecked():
            paint_glass(p, r, 11, tint="blue", hover=self._hover.value, shadow_strength=0.6, rainbow=0.5)
            p.setPen(QColor("#ffffff"))
        else:
            paint_slot(p, r, 11, self._hover.value)
            p.setPen(QColor(T().text_dim))
        p.setFont(self.font())
        p.drawText(r, Qt.AlignCenter, self.text())


class GlassCheck(QAbstractButton):
    """
    체크박스 대신 쓰는 유리 버튼
    - 기본: "이름 ........ [작은 스위치]" 한 줄 (클릭하면 스위치가 미끄러지며 켜짐/꺼짐)
    - chip=True: 요일처럼 짧은 항목용 알약 (켜면 파란 유리 + 흰 글자)
    """

    def __init__(self, text: str = "", parent=None, chip: bool = False):
        super().__init__(parent)
        self.setText(text)
        self._chip = chip
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self._hover = _Anim(self)
        self._pos = _Anim(self, 260)
        self._pos.value = 0.0
        self.toggled.connect(self._on_toggled)
        self.setFont(theme.dialog_font(13, QFont.Bold))
        self.setMinimumHeight(40 if not chip else 38)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)

    def _on_toggled(self, on):
        self._pos.to(1.0 if on else 0.0, 280, QEasingCurve.OutBack)
        self.update()

    def setChecked(self, on: bool):
        super().setChecked(on)
        self._pos.value = 1.0 if on else 0.0
        self.update()

    def sizeHint(self):
        w = QFontMetrics(self.font()).horizontalAdvance(self.text())
        if self._chip:
            return QSize(max(60, w + 36), 38)
        return QSize(w + 28 + 14 + 44 + 12, 40)

    def minimumSizeHint(self):
        return self.sizeHint()

    def enterEvent(self, e):
        self._hover.to(1.0)

    def leaveEvent(self, e):
        self._hover.to(0.0)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if not self.isEnabled():
            p.setOpacity(0.45)
        r = QRectF(2, 2, self.width() - 4, self.height() - 6)
        p.setFont(self.font())
        if self._chip:
            if self.isChecked():
                paint_glass(p, r, 12, tint="blue", hover=self._hover.value, shadow_strength=0.6, rainbow=0.5)
                p.setPen(QColor("#ffffff"))
            else:
                paint_slot(p, r, 12, self._hover.value)
                p.setPen(QColor(T().text_dim))
            p.drawText(r, Qt.AlignCenter, self.text())
            return
        # 줄 모양: 움푹한 홈 위에 이름, 오른쪽 끝에 작은 스위치
        paint_slot(p, r, 12, self._hover.value)
        p.setPen(QColor(T().text if self.isChecked() else T().text_dim))
        p.drawText(QRectF(r.left() + 14, r.top(), r.width() - 80, r.height()),
                   Qt.AlignVCenter | Qt.AlignLeft, self.text())
        tw, th = 40.0, 20.0
        track = QRectF(r.right() - tw - 10, r.center().y() - th / 2, tw, th)
        v = self._pos.value
        vc = max(0.0, min(1.0, v))
        paint_slot(p, track, th / 2, self._hover.value)
        if vc > 0.01:
            p.save()
            p.setOpacity(p.opacity() * min(1.0, vc * 2.5))
            paint_glass(p, track, th / 2, tint="mint", shadow=False, rainbow=0.4, highlight=0.8)
            p.restore()
        d = th - 4
        x = track.left() + 2 + (tw - d - 4) * v
        paint_glass(p, QRectF(x, track.top() + 2, d, d), d / 2, fill=0.92, shadow_strength=0.7,
                    hover=self._hover.value, rainbow=0.5)


class ShortcutEditor(QWidget):
    """단축키 만들기: 조합 키 칩 + 키 입력칸 + 특수 키 고르기"""

    changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        from core.shortcut_manager import ShortcutManager
        self.SM = ShortcutManager
        self.main_key = ""
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)

        chips = QHBoxLayout()
        chips.setSpacing(6)
        self.chips = {}
        for m in ShortcutManager.MODIFIERS:
            c = ModifierChip(m)
            c.toggled.connect(self._emit)
            self.chips[m] = c
            chips.addWidget(c)
        chips.addWidget(QLabel("+"))
        self.capture = KeyCaptureEdit()
        self.capture.captured.connect(self._on_captured)
        chips.addWidget(self.capture, 1)
        lay.addLayout(chips)

        bottom = QHBoxLayout()
        bottom.setSpacing(8)
        self.special = no_wheel(QComboBox())
        self.special.addItem("특수 키 고르기…", "")
        for key, label in ShortcutManager.SPECIAL_KEYS:
            self.special.addItem(label, key)
        self.special.activated.connect(self._on_special)
        bottom.addWidget(self.special, 1)
        clear = GlassButton("지우기", icon_name="trash")
        clear.clicked.connect(lambda: self.set_value(""))
        bottom.addWidget(clear)
        lay.addLayout(bottom)

        self.preview = QLabel()
        self.preview.setProperty("role", "hint")
        self.preview.setWordWrap(True)
        lay.addWidget(self.preview)
        self._emit()

    def _on_captured(self, name: str, mods: list):
        self.main_key = name
        for m, chip in self.chips.items():
            chip.blockSignals(True)
            chip.setChecked(m in mods or (chip.isChecked() and not mods))
            chip.blockSignals(False)
        self._emit()

    def _on_special(self, idx: int):
        key = self.special.itemData(idx)
        if key:
            self.main_key = key
            self._emit()
        self.special.setCurrentIndex(0)

    def value(self) -> str:
        # 흔히 쓰는 순서로 적기: Win + Ctrl + Alt + Shift + 키
        parts = [m for m in ("Win", "Ctrl", "Alt", "Shift") if self.chips[m].isChecked()]
        if self.main_key:
            parts.append(self.main_key)
        return " + ".join(parts)

    def set_value(self, text: str):
        mods_found = []
        self.main_key = ""
        if text:
            parts = [x.strip() for x in (text.split(" + ") if " + " in text else text.replace("+", " ").split())]
            for prt in parts:
                low = prt.lower()
                matched = next((m for m in self.SM.MODIFIERS if m.lower() == low
                                or (m == "Ctrl" and low == "control")
                                or (m == "Win" and low == "windows")), None)
                if matched:
                    mods_found.append(matched)
                elif prt:
                    self.main_key = prt
        for m, chip in self.chips.items():
            chip.blockSignals(True)
            chip.setChecked(m in mods_found)
            chip.blockSignals(False)
        self._emit()

    def _emit(self, *_):
        v = self.value()
        self.capture.setText(self.main_key)
        self.preview.setText(f"보낼 단축키:  {v}" if v else "조합 키를 고르고 키를 누르세요.")
        self.changed.emit(v)
