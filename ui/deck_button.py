"""
덱 버튼 위젯
유리 버튼 하나를 그리고, 마우스 올림/누름/성공/실패/실행 중 효과와
끌어서 위치 바꾸기(드래그 앤 드롭)를 처리합니다.

클릭 애니메이션
- 누르면 쏙 들어가고, 놓으면 젤리처럼 통 튀어 오름
- 누른 자리에서 물결이 퍼짐
- 켜기/끄기 버튼은 켜질 때 민트색이 누른 자리에서 번져 나감

그림자는 버튼판(under_host)이 한꺼번에 그려서, 버튼 사이 여백이 거의 없어도 잘리지 않습니다.
"""

import math
import os

from PySide6.QtCore import (
    Qt, Signal, QPoint, QPointF, QRectF, QMimeData, QTimer, QVariantAnimation, QEasingCurve,
)
from PySide6.QtGui import QPixmap, QPainter, QColor, QFont, QDrag, QPen, QFontMetrics, QPainterPath, QRadialGradient
from PySide6.QtWidgets import QWidget, QApplication

from core import paths
from core.action_executor import describe_action
from models.button_model import DeckButtonData
from ui import theme, icons
from ui.theme import T, tint_colors
from ui.glass import (
    paint_glass_under, paint_slot, draw_icon, with_alpha,
    rounded_path, get_glass_pixmap,
)
from ui.widgets import find_backdrop, _Anim

MIME_TYPE = "application/x-virtualdeck-button"

_icon_cache = {}


def load_icon_pixmap(icon: str, px: int):
    path = paths.resolve_icon(icon)
    if not path:
        return None
    key = (path, px, os.path.getmtime(path))
    pix = _icon_cache.get(key)
    if pix is None:
        src = QPixmap(path)
        if src.isNull():
            return None
        pix = src.scaled(px, px, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        if len(_icon_cache) > 300:
            _icon_cache.clear()
        _icon_cache[key] = pix
    return pix


def icon_color_for(data: DeckButtonData, fg: QColor) -> QColor:
    entry = theme.ICON_COLORS.get(data.icon_color or "auto")
    if not entry or entry[1] is None:
        return QColor(fg)
    return QColor(entry[1])


def paint_button_icon(p: QPainter, data: DeckButtonData, rect: QRectF, fg: QColor, style: str,
                      tinted: bool, dpr: float = 1.0) -> None:
    """버튼 아이콘 하나를 그립니다. (테마 아이콘 / 이모지 / 그림 파일 / 글자)"""
    icon = (data.icon or "").strip()
    color = icon_color_for(data, fg)
    halo = QColor(255, 255, 255, 150) if not T().dark and not tinted else QColor(0, 0, 0, 70)

    if icons.is_theme_icon(icon) and style != "emoji":
        accent = color if data.icon_color not in ("", "auto") else (
            QColor("#ffffff") if tinted else QColor(T().accent))
        inner = rect.adjusted(rect.width() * 0.07, rect.height() * 0.07, -rect.width() * 0.07, -rect.height() * 0.07)
        icons.paint_icon(p, icon, inner.translated(0, max(0.8, rect.height() * 0.02)), halo, style, halo)
        icons.paint_icon(p, icon, inner, color, style, accent)
        return

    if paths.looks_like_image_path(icon):
        pix = load_icon_pixmap(icon, int(rect.width() * dpr))
        if pix is not None:
            pix.setDevicePixelRatio(dpr)
            pw, ph = pix.width() / dpr, pix.height() / dpr
            p.drawPixmap(QPointF(rect.center().x() - pw / 2, rect.center().y() - ph / 2), pix)
            return

    text = icons.emoji_for(icon) if icons.is_theme_icon(icon) else icon
    if not text or paths.looks_like_image_path(text):
        text = data.name[:1] if data.name else "⚡"
    is_symbol = any(ord(ch) > 0x2000 for ch in text)
    size = rect.width()
    p.setFont(theme.emoji_font(size * 0.78) if is_symbol else theme.ui_font(size * 0.7, QFont.Bold))
    box = rect.adjusted(-size, -4, size, 4)
    if not is_symbol:
        p.setPen(halo)
        p.drawText(box.translated(0, 1), Qt.AlignCenter, text)
    p.setPen(color)
    p.drawText(box, Qt.AlignCenter, text)


class DeckButtonWidget(QWidget):
    clicked = Signal(str)
    long_pressed = Signal(str)
    edit_requested = Signal(str)
    context_requested = Signal(str, QPoint)
    swapped = Signal(str, str)

    def __init__(self, button_data: DeckButtonData, size: int = 94, show_labels: bool = True,
                 icon_style: str = "line", parent=None):
        super().__init__(parent)
        self.button_data = button_data
        self.button_size = size
        self.show_labels = show_labels
        self.icon_style = icon_style
        self.under_host = None       # 그림자를 대신 그려 줄 버튼판
        self.drag_start = QPoint()
        self.drop_target = False
        self.running = False
        self.preview_mode = False    # 편집창 미리보기용 (클릭/드래그 없음)
        self.span = (1, 1)           # (가로 칸, 세로 칸)
        self.spacing = 6
        self.info = None             # 정보 버튼 값 (큰 글자, 작은 글자, 게이지)
        self.timer_view = None       # 타이머 표시 (큰 글자, 작은 글자, 진행도, 상태)
        self.hold_ms = 550
        self._hold_fired = False
        self._hold_timer = QTimer(self)
        self._hold_timer.setSingleShot(True)
        self._hold_timer.timeout.connect(self._on_hold)

        self._hover = _Anim(self, 160)
        self._press = _Anim(self, 90)
        self._flash = _Anim(self, 700)
        self.flash_color = QColor("#22c55e")
        self._shake = self._make_anim(420)
        self._ripple = self._make_anim(700)
        self._ripple.setEasingCurve(QEasingCurve.OutQuad)
        self._ripple_pos = QPointF(size / 2, size / 2)
        self._ripple_color = QColor(255, 255, 255, 235)
        self._fill = self._make_anim(650)       # 켜기/끄기 색 번짐
        self._fill.setEasingCurve(QEasingCurve.InOutQuad)
        self._fill_was_on = False
        self._hold = self._make_anim(550)      # 길게 누르기 진행 고리
        self._hold.setEasingCurve(QEasingCurve.Linear)
        self._spin = 0.0
        self._spin_timer = QTimer(self)
        self._spin_timer.setInterval(16)
        self._spin_timer.timeout.connect(self._tick_spin)

        self.setAcceptDrops(True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(size, size)
        self._refresh_tooltip()

    def _make_anim(self, ms: int) -> QVariantAnimation:
        a = QVariantAnimation(self)
        a.setDuration(ms)
        a.setStartValue(0.0)
        a.setEndValue(1.0)
        a.setEasingCurve(QEasingCurve.OutCubic)
        a.valueChanged.connect(lambda _: self.update())
        a.finished.connect(self.update)
        return a

    @staticmethod
    def _value(anim: QVariantAnimation) -> float:
        return float(anim.currentValue()) if anim.state() == QVariantAnimation.Running else 0.0

    # 버튼이 다시 그려질 때 그림자를 그리는 버튼판도 함께 다시 그리기
    def update(self, *args):
        super().update(*args)
        host = self.under_host
        if host is not None and self.isVisible():
            tl = self.mapTo(host, QPoint(0, 0))
            pad = int(self.button_size * 0.25)
            host.update(tl.x() - pad, tl.y() - pad, self.width() + pad * 2, self.height() + pad * 2)

    # ------------------------------------------------------------ 데이터
    def update_data(self, data: DeckButtonData) -> None:
        self.button_data = data
        self._refresh_tooltip()
        self.update()

    def set_button_size(self, size: int, show_labels: bool = None) -> None:
        self.button_size = size
        if show_labels is not None:
            self.show_labels = show_labels
        self.set_span(*self.span, spacing=self.spacing)

    def set_span(self, cols: int, rows: int, spacing: int = None) -> None:
        """큰 버튼: 가로/세로로 칸을 합쳐서 차지합니다."""
        if spacing is not None:
            self.spacing = spacing
        self.span = (cols, rows)
        s, g = self.button_size, self.spacing
        self.setFixedSize(s * cols + g * (cols - 1), s * rows + g * (rows - 1))
        self.update()

    def set_timer_view(self, view) -> None:
        if view == self.timer_view:
            return
        self.timer_view = view
        done = bool(view) and view[3] == "done"
        if done and not self._spin_timer.isActive():
            self._spin_timer.start()      # 끝나면 빛이 깜빡이도록
        elif not done and not self.running and self._spin_timer.isActive():
            self._spin_timer.stop()
        self.update()

    def set_info(self, info) -> None:
        if info != self.info:
            self.info = info
            self.update()

    def _refresh_tooltip(self):
        d = self.button_data
        if d.is_empty():
            self.setToolTip("빈 칸 — 눌러서 버튼 만들기")
            return
        lines = [f"<b>{d.name}</b>" if d.name else ""]
        lines.append(describe_action(d.action_type, d.action_data))
        if d.toggle:
            lines.append("켜기/끄기 버튼 · 지금 " + ("켜짐" if d.toggle_on else "꺼짐"))
        if d.has_hold():
            lines.append("길게 누르면: " + describe_action(d.hold_action_type, d.hold_action_data))
        lines.append("<span style='color:gray'>우클릭: 메뉴 · 끌어서 위치 바꾸기</span>")
        self.setToolTip("<br>".join(x for x in lines if x))

    # ------------------------------------------------------------ 효과
    def flash(self, ok: bool) -> None:
        """성공하면 초록 반짝임, 실패하면 빨간 빛과 함께 좌우로 흔들림"""
        self.flash_color = QColor("#22c55e") if ok else QColor("#ef4444")
        self._flash.value = 1.0
        self._flash.to(0.0, 750)
        if not ok:
            self._shake.stop()
            self._shake.start()

    def play_toggle(self, now_on: bool) -> None:
        """켜기/끄기가 바뀔 때 누른 자리에서 새 색이 번져 나가게 합니다."""
        self._ripple_color = QColor("#d9fff0") if now_on else QColor(255, 255, 255, 235)
        self._fill_was_on = not now_on
        self._fill.stop()
        self._fill.start()

    def set_running(self, on: bool) -> None:
        self.running = on
        if on:
            self._spin_timer.start()
        else:
            self._spin_timer.stop()
        self._refresh_tooltip()
        self.update()

    def _tick_spin(self):
        self._spin = (self._spin + 6) % 360
        self.update()

    # ------------------------------------------------------------ 위치 계산
    def _base_rect(self) -> QRectF:
        m = max(3.0, self.button_size * 0.045)
        return QRectF(m, m * 0.8, self.width() - m * 2, self.height() - m * 2)

    def _shake_offset(self) -> float:
        if self._shake.state() == QVariantAnimation.Running:
            t = float(self._shake.currentValue())
            return math.sin(t * math.pi * 6) * (1 - t) * self.button_size * 0.05
        return 0.0

    def _glass_rect(self) -> QRectF:
        rect = self._base_rect().translated(self._shake_offset(), 0)
        k = 0.06 * self._press.value      # 놓을 때는 음수가 되어 살짝 커짐(젤리 반동)
        return rect.adjusted(rect.width() * k, rect.height() * k, -rect.width() * k, -rect.height() * k)

    def _state_tint(self, on: bool) -> str:
        """켜기/끄기 버튼은 꺼지면 투명 유리, 켜지면 고른 색(기본 민트)"""
        d = self.button_data
        tint = d.color or "clear"
        if d.toggle:
            return (tint if tint != "clear" else "mint") if on else "clear"
        return tint

    def _glow(self):
        d = self.button_data
        if self.drop_target:
            return QColor(T().accent), 1.0
        if self._flash.value > 0.01:
            return self.flash_color, self._flash.value
        if self.timer_view and self.timer_view[3] == "done":   # 타이머 끝: 빨간 빛이 깜빡임
            return QColor("#ef4444"), 0.55 + 0.45 * math.sin(math.radians(self._spin * 3))
        if d.toggle and d.toggle_on:
            return QColor(theme.TOGGLE_ON_COLOR), 0.55
        return None, 0.0

    def under_params(self):
        """버튼판이 그림자를 그릴 때 쓰는 정보 (빈 칸이면 None)"""
        if self.button_data.is_empty() or not self.isVisible():
            return None
        rect = self._glass_rect()
        glow, amount = self._glow()
        return dict(rect=rect, radius=min(rect.width(), rect.height()) * 0.26,
                    tint=self._state_tint(self.button_data.toggle_on),
                    hover=self._hover.value, press=self._press.value, glow=glow, glow_amount=amount,
                    shadow_max=self.button_size * 0.2)

    def _clear_mode(self):
        """지금 스타일이 '투명 (버튼만)' 인지와 유리 맑기 값(0~100)을 돌려줍니다."""
        cfg = getattr(getattr(self.under_host, "owner", None), "config", None)
        if cfg is None or getattr(cfg, "bg_type", "") != "clear":
            return False, 0
        return True, int(getattr(cfg, "glass_clarity", 30))

    # ------------------------------------------------------------ 그리기
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        d = self.button_data
        rect = self._glass_rect()
        radius = min(rect.width(), rect.height()) * 0.26
        hover, press = self._hover.value, self._press.value
        clear, clarity = self._clear_mode()

        if d.is_empty():
            if clear:   # 투명 모드: 빈 칸은 아주 옅게, 마우스를 올리면 또렷하게
                p.setOpacity(0.25 + 0.75 * hover)
            paint_slot(p, rect, radius, hover)
            if self.drop_target:
                p.setPen(QPen(QColor(T().accent), 2.0, Qt.DashLine))
                p.setBrush(Qt.NoBrush)
                p.drawRoundedRect(rect.adjusted(1, 1, -1, -1), radius, radius)
            c = QColor(T().accent) if hover > 0.5 else QColor(T().text_faint)
            s = rect.width() * 0.26
            draw_icon(p, "plus", QRectF(rect.center().x() - s / 2, rect.center().y() - s / 2, s, s), c,
                      width=max(1.6, rect.width() * 0.035))
            return

        backdrop, brect = find_backdrop(self)
        if clear:   # 투명 모드: 뒤 배경 조각 없이 그림
            backdrop, brect = None, None
        glass_fill = (0.30 + 0.40 * max(0, min(100, clarity)) / 100) if clear else 0.11
        if brect is not None:
            bdpr = backdrop.devicePixelRatio() or 1.0
            brect = QRectF(brect.left() + rect.left() * bdpr, brect.top() + rect.top() * bdpr,
                           rect.width() * bdpr, rect.height() * bdpr)
        own_shadow = self.under_host is None
        glow, glow_amount = self._glow()
        ripple_t = self._value(self._ripple)
        ripple = (self._ripple_pos, ripple_t, self._ripple_color) if ripple_t > 0 else None

        dpr = self.devicePixelRatioF()
        dark = T().dark
        fill_t = self._value(self._fill)
        active_tint = self._state_tint(d.toggle_on if (fill_t > 0.5 or not d.toggle) else self._fill_was_on)

        # 1. 그림자 (자체 그림자 필요한 경우)
        if own_shadow:
            paint_glass_under(p, rect, radius, tint=active_tint, hover=hover, press=press,
                              shadow_max=max(3.0, self.button_size * 0.045 * 0.9),
                              glow=glow, glow_amount=glow_amount)

        # 2. 뒤 배경 조각 (렌즈 효과, 가벼움)
        if backdrop is not None and not backdrop.isNull() and brect is not None:
            p.save()
            p.setClipPath(rounded_path(rect, radius), Qt.IntersectClip)
            mag = 1.0 + 0.14 * (1 + 0.4 * hover + 0.5 * max(0.0, press))
            src = QRectF(brect)
            cx, cy = src.center().x(), src.center().y()
            sw, sh = src.width() / mag, src.height() / mag
            src = QRectF(cx - sw / 2, cy - sh / 2, sw, sh)
            p.drawPixmap(rect, backdrop, src)
            p.restore()

        # 3. 유리 층 캐시 그리기 함수
        def draw_cached_glass(tint_name, alpha_mult=1.0):
            # 누름(press)은 가운데 기준으로 줄이기
            draw_r = rect
            if press > 0:
                shrink = min(rect.width(), rect.height()) * 0.035 * press
                draw_r = rect.adjusted(shrink, shrink, -shrink, -shrink)
            pix0 = get_glass_pixmap(rect.width(), rect.height(), radius, tint_name, dark, dpr, 0, fill=glass_fill)
            pix1 = get_glass_pixmap(rect.width(), rect.height(), radius, tint_name, dark, dpr, 1, fill=glass_fill)
            p.save()
            if alpha_mult < 1.0:
                p.setOpacity(alpha_mult)
            p.drawPixmap(draw_r, pix0, QRectF(pix0.rect()))
            if hover > 0.001:
                p.setOpacity(min(1.0, hover) * alpha_mult)
                p.drawPixmap(draw_r, pix1, QRectF(pix1.rect()))
            if press > 0:
                p.setClipPath(rounded_path(draw_r, radius), Qt.IntersectClip)
                p.fillRect(draw_r, QColor(20, 40, 80, int(26 * press)) if not dark else QColor(0, 0, 0, int(50 * press)))
            p.restore()

        if fill_t > 0 and d.toggle:
            # 이전 상태 유리 위에 누른 자리에서 커지는 원 모양으로 새 상태 유리 그림
            draw_cached_glass(self._state_tint(self._fill_was_on))
            r = math.hypot(rect.width(), rect.height()) * (0.05 + 1.0 * fill_t)
            clip = QPainterPath()
            clip.addEllipse(self._ripple_pos, r, r)
            p.save()
            p.setClipPath(clip)
            draw_cached_glass(self._state_tint(d.toggle_on))
            p.restore()
            tint = active_tint
        else:
            tint = self._state_tint(d.toggle_on)
            draw_cached_glass(tint)

        # 4. 누른 자리에서 퍼지는 물결
        if ripple is not None and 0.0 < ripple[1] < 1.0:
            pos, prog, rc = ripple
            diag = math.hypot(rect.width(), rect.height())
            rr = diag * (0.06 + 0.82 * prog)
            fade = (1 - prog) ** 0.85
            rg = QRadialGradient(pos, rr)
            rg.setColorAt(0.0, with_alpha(rc, rc.alphaF() * 0.42 * fade))
            rg.setColorAt(0.70, with_alpha(rc, rc.alphaF() * 0.28 * fade))
            rg.setColorAt(0.90, with_alpha(rc, rc.alphaF() * 0.85 * fade))
            rg.setColorAt(0.97, with_alpha(rc, rc.alphaF() * 0.35 * fade))
            rg.setColorAt(1.0, with_alpha(rc, 0.0))
            p.save()
            p.setClipPath(rounded_path(rect, radius), Qt.IntersectClip)
            p.fillRect(rect, rg)
            p.restore()

        # 5. 바깥 빛 (자체 빛)
        if own_shadow and glow is not None and glow_amount > 0:
            p.save()
            p.setRenderHint(QPainter.Antialiasing)
            glow_span = min(rect.width(), rect.height()) * 0.16
            for i in range(5):
                k = (i + 1) / 5
                grow = glow_span * k
                pen = QPen(with_alpha(glow, glow.alphaF() * glow_amount * (1 - k) * 0.55), 2.2)
                p.setPen(pen)
                p.setBrush(Qt.NoBrush)
                p.drawPath(rounded_path(rect.adjusted(-grow, -grow, grow, grow), radius + grow))
            p.restore()

        colors = tint_colors(tint)
        fg = colors[2] if colors else QColor(T().text)
        unit = min(rect.width(), rect.height())
        wide = rect.width() > rect.height() * 1.4
        halo = QColor(0, 0, 0, 60) if (colors or T().dark) else QColor(255, 255, 255, 120)
        if clear:   # 복잡한 바탕화면 위에서도 보이도록 둘레 빛을 진하게
            halo = QColor(0, 0, 0, 130) if (colors or T().dark) else QColor(255, 255, 255, 220)

        if d.action_type == "info":
            self._paint_info(p, rect, fg, halo, colors is not None)
        elif d.action_type == "timer":
            self._paint_timer(p, rect, radius, fg, halo, colors is not None)
        else:
            labels = self.show_labels and bool(d.name.strip()) and self.button_size >= 70
            if wide:
                # 가로로 긴 버튼: 아이콘 왼쪽, 이름 오른쪽
                icon_px = unit * 0.46
                icon_rect = QRectF(rect.left() + unit * 0.27, rect.center().y() - icon_px / 2, icon_px, icon_px)
                text_rect = QRectF(icon_rect.right() + unit * 0.14, rect.top(), rect.right() - icon_rect.right() - unit * 0.26, rect.height())
                fsize = max(11.0, self.button_size * 0.15)
                align = Qt.AlignVCenter | Qt.AlignLeft
                if not d.name.strip():
                    icon_rect.moveCenter(rect.center())
            else:
                icon_px = unit * (0.40 if labels else 0.52)
                icon_center_y = rect.top() + rect.height() * (0.41 if labels else 0.5)
                icon_rect = QRectF(rect.center().x() - icon_px / 2, icon_center_y - icon_px / 2, icon_px, icon_px)
                text_rect = QRectF(rect.left() + 4, rect.top() + rect.height() * 0.69,
                                   rect.width() - 8, rect.height() * 0.24)
                if rect.height() > rect.width() * 1.4:   # 세로로 긴 버튼
                    text_rect = QRectF(rect.left() + 4, icon_rect.bottom() + unit * 0.12, rect.width() - 8, unit * 0.3)
                fsize = max(10.0, self.button_size * (0.14 if unit > self.button_size * 1.2 else 0.125))
                align = Qt.AlignCenter
            if clear and (not d.icon or icons.is_theme_icon(d.icon)):
                # 테마 아이콘 둘레에 빛을 둘러 또렷하게
                for dx, dy in ((0, 1.2), (1.2, 0), (-1.2, 0), (0, -1.2)):
                    paint_button_icon(p, d, icon_rect.translated(dx, dy), halo, self.icon_style,
                                      colors is not None, self.devicePixelRatioF())
            paint_button_icon(p, d, icon_rect, fg, self.icon_style, colors is not None, self.devicePixelRatioF())

            if self.running:
                ring = icon_rect.adjusted(-icon_px * 0.2, -icon_px * 0.2, icon_px * 0.2, icon_px * 0.2)
                p.setPen(QPen(with_alpha(QColor(T().accent), 0.25), 2.4))
                p.setBrush(Qt.NoBrush)
                p.drawEllipse(ring)
                p.setPen(QPen(QColor(T().accent), 2.6, Qt.SolidLine, Qt.RoundCap))
                p.drawArc(ring, int(-self._spin * 16), 100 * 16)

            if (labels or wide) and d.name.strip():
                font = theme.ui_font(fsize, QFont.Bold)
                p.setFont(font)
                fm = QFontMetrics(font)
                text = fm.elidedText(d.name.strip(), Qt.ElideRight, int(text_rect.width()))
                # 투명한 유리 위에서도 글자가 잘 보이도록 은은한 빛을 둘러 줍니다.
                p.setPen(halo)
                for dx, dy in ((0, 1), (1, 0), (-1, 0), (0, -1)):
                    p.drawText(text_rect.translated(dx * 0.8, dy * 0.8), align, text)
                p.setPen(fg)
                p.drawText(text_rect, align, text)

        # 길게 누르기 진행 고리 (테두리를 따라 차오름)
        hold_t = self._value(self._hold)
        if hold_t > 0 and not self._hold_fired:
            path = QPainterPath()
            ring_rect = rect.adjusted(2.5, 2.5, -2.5, -2.5)
            path.addRoundedRect(ring_rect, radius - 2.5, radius - 2.5)
            width = max(2.5, unit * 0.04)
            length = path.length() / width
            pen = QPen(QColor(T().accent) if not colors else QColor("#ffffff"), width, Qt.CustomDashLine, Qt.RoundCap)
            pen.setDashPattern([max(0.01, length * hold_t), length + 10])
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(path)

        # 작은 표시들
        dot = max(5.0, rect.width() * 0.07)
        corner = QPointF(rect.right() - rect.width() * 0.14, rect.top() + rect.height() * 0.14)
        if d.action_type == "group":
            s = rect.width() * 0.16
            draw_icon(p, "folder", QRectF(corner.x() - s / 2, corner.y() - s / 2, s, s),
                      with_alpha(fg, 0.75), width=max(1.2, s * 0.1))
        elif d.toggle:
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#ffffff") if (d.toggle_on and colors) else
                       (QColor(theme.TOGGLE_ON_COLOR) if d.toggle_on else with_alpha(fg, 0.25)))
            p.drawEllipse(corner, dot / 2, dot / 2)

    def _paint_info(self, p, rect, fg, halo, tinted):
        """정보 버튼: 큰 값 + 작은 설명 + 아래쪽 게이지 막대"""
        from core.system_info import INFO_KINDS
        d = self.button_data
        big, small, gauge = self.info or ("…", INFO_KINDS.get(d.action_data, ("",))[0], None)
        if d.name.strip() and self.show_labels:
            small = d.name.strip()
        unit = min(rect.width(), rect.height())
        # 작은 아이콘 (왼쪽 위)
        s = unit * 0.2
        icons.paint_icon(p, d.icon if icons.is_theme_icon(d.icon) else icons.default_icon_for("info", d.action_data),
                         QRectF(rect.left() + unit * 0.13, rect.top() + unit * 0.12, s, s),
                         with_alpha(fg, 0.7), "line")
        font = theme.ui_font(unit * (0.27 if len(big) <= 4 else 0.22), QFont.Bold)
        p.setFont(font)
        big_rect = QRectF(rect.left(), rect.top() + rect.height() * 0.24, rect.width(), rect.height() * 0.42)
        p.setPen(halo)
        p.drawText(big_rect.translated(0, 1), Qt.AlignCenter, big)
        p.setPen(fg)
        p.drawText(big_rect, Qt.AlignCenter, big)
        p.setFont(theme.ui_font(max(9.0, unit * 0.115), QFont.DemiBold))
        p.setPen(with_alpha(fg, 0.8))
        fm = QFontMetrics(p.font())
        small_rect = QRectF(rect.left() + 4, rect.top() + rect.height() * 0.64, rect.width() - 8, rect.height() * 0.18)
        p.drawText(small_rect, Qt.AlignCenter, fm.elidedText(small, Qt.ElideRight, int(small_rect.width())))
        if gauge is not None:
            bar = QRectF(rect.left() + unit * 0.18, rect.bottom() - unit * 0.13, rect.width() - unit * 0.36, max(3.0, unit * 0.045))
            p.setPen(Qt.NoPen)
            p.setBrush(with_alpha(fg, 0.18))
            p.drawRoundedRect(bar, bar.height() / 2, bar.height() / 2)
            fill = QRectF(bar.left(), bar.top(), bar.width() * max(0.0, min(1.0, gauge)), bar.height())
            c = QColor(T().accent) if not tinted else QColor("#ffffff")
            if gauge > 0.85 and d.action_data in ("cpu", "memory"):
                c = QColor("#ef4444")
            p.setBrush(c)
            p.drawRoundedRect(fill, bar.height() / 2, bar.height() / 2)

    def _paint_timer(self, p, rect, radius, fg, halo, tinted):
        """타이머: 남은 시간 크게 + 상태 글자 + 테두리를 따라 줄어드는 고리"""
        from core.timer_manager import parse_timer, format_seconds
        d = self.button_data
        cfg = parse_timer(d.action_data)
        big, small, progress, state = self.timer_view or (
            format_seconds(0 if cfg["mode"] == "stopwatch" else cfg["seconds"]), "눌러서 시작", None, "idle")
        if d.name.strip() and self.show_labels and state in ("idle", "running"):
            small = d.name.strip() if state == "idle" else small
        unit = min(rect.width(), rect.height())
        accent = QColor("#ffffff") if tinted else QColor(T().accent)

        # 남은 시간 고리 (트랙 + 남은 부분)
        if progress is not None and state != "done":
            ring = rect.adjusted(3, 3, -3, -3)
            path = QPainterPath()
            path.addRoundedRect(ring, radius - 3, radius - 3)
            width = max(2.5, unit * 0.04)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(with_alpha(fg, 0.15), width))
            p.drawPath(path)
            length = path.length() / width
            pen = QPen(accent if state == "running" else with_alpha(fg, 0.45), width, Qt.CustomDashLine, Qt.RoundCap)
            pen.setDashPattern([max(0.01, length * (1 - progress)), length + 10])
            p.setPen(pen)
            p.drawPath(path)

        # 작은 아이콘 (왼쪽 위)
        s = unit * 0.2
        icon = d.icon if icons.is_theme_icon(d.icon) else icons.default_icon_for("timer")
        icons.paint_icon(p, icon, QRectF(rect.left() + unit * 0.13, rect.top() + unit * 0.12, s, s),
                         with_alpha(fg, 0.7), "line")
        if state == "paused":   # 일시정지 표시 (오른쪽 위)
            p.setPen(Qt.NoPen)
            p.setBrush(with_alpha(fg, 0.6))
            bx, by, bw, bh = rect.right() - unit * 0.28, rect.top() + unit * 0.13, unit * 0.045, unit * 0.15
            p.drawRoundedRect(QRectF(bx, by, bw, bh), bw / 2, bw / 2)
            p.drawRoundedRect(QRectF(bx + bw * 2, by, bw, bh), bw / 2, bw / 2)

        size = unit * (0.27 if len(big) <= 5 else 0.2)
        font = theme.ui_font(size, QFont.Bold)
        p.setFont(font)
        big_rect = QRectF(rect.left(), rect.top() + rect.height() * 0.24, rect.width(), rect.height() * 0.42)
        p.setPen(halo)
        p.drawText(big_rect.translated(0, 1), Qt.AlignCenter, big)
        p.setPen(QColor("#ef4444") if state == "done" and not tinted else (with_alpha(fg, 0.6) if state == "paused" else fg))
        p.drawText(big_rect, Qt.AlignCenter, big)
        p.setFont(theme.ui_font(max(9.0, unit * 0.11), QFont.DemiBold))
        p.setPen(with_alpha(fg, 0.8))
        fm = QFontMetrics(p.font())
        small_rect = QRectF(rect.left() + 4, rect.top() + rect.height() * 0.65, rect.width() - 8, rect.height() * 0.18)
        p.drawText(small_rect, Qt.AlignCenter, fm.elidedText(small, Qt.ElideRight, int(small_rect.width())))

    def _can_hold(self) -> bool:
        d = self.button_data
        return d.has_hold() or d.action_type == "timer"   # 타이머는 길게 누르면 초기화

    def _on_hold(self):
        """길게 누르기가 확정되면 신호를 보내고, 놓을 때 클릭으로 처리하지 않음"""
        if self._can_hold():
            self._hold_fired = True
            self._hold.stop()
            self._ripple_color = QColor(T().accent)
            self._ripple.stop()
            self._ripple.start()
            self._press.to(0.0, 520, QEasingCurve.OutBack)
            self.long_pressed.emit(self.button_data.id)

    # ------------------------------------------------------------ 마우스
    def enterEvent(self, e):
        self._hover.to(1.0)
        super().enterEvent(e)

    def _cancel_hold(self):
        self._hold_timer.stop()
        if self._hold.state() == QVariantAnimation.Running:
            self._hold.stop()
            self.update()

    def leaveEvent(self, e):
        self._cancel_hold()
        self._hover.to(0.0)
        if self._press.value > 0:
            self._press.to(0.0, 380, QEasingCurve.OutBack)
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if self.preview_mode:
            return
        if e.button() == Qt.LeftButton:
            self.drag_start = e.position().toPoint()
            self._ripple_pos = e.position()
            self._press.to(1.0, 90)
            self._hold_fired = False
            if self._can_hold() and not self.button_data.is_empty():
                self._hold.setDuration(self.hold_ms)
                self._hold.stop()
                self._hold.start()
                self._hold_timer.start(self.hold_ms)
            e.accept()
        elif e.button() == Qt.RightButton:
            e.accept()
            self.context_requested.emit(self.button_data.id, e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self.preview_mode or not (e.buttons() & Qt.LeftButton) or self.button_data.is_empty():
            return
        if (e.position().toPoint() - self.drag_start).manhattanLength() < QApplication.startDragDistance():
            return
        self._cancel_hold()
        if self._hold_fired:
            return
        self._press.to(0.0)
        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(MIME_TYPE, self.button_data.id.encode("utf-8"))
        drag.setMimeData(mime)
        drag.setPixmap(self.grab())
        drag.setHotSpot(e.position().toPoint())
        drag.exec(Qt.MoveAction)

    def mouseReleaseEvent(self, e):
        if self.preview_mode:
            return
        if e.button() == Qt.LeftButton:
            self._cancel_hold()
            if self._hold_fired:      # 길게 누르기로 이미 실행됨
                self._hold_fired = False
                return
            # 젤리 반동: 원래 크기보다 살짝 커졌다가 돌아옴
            self._press.to(0.0, 520, QEasingCurve.OutBack)
            if (e.position().toPoint() - self.drag_start).manhattanLength() < QApplication.startDragDistance():
                if self.rect().contains(e.position().toPoint()):
                    if self.button_data.is_empty():
                        self.edit_requested.emit(self.button_data.id)
                    else:
                        self._ripple_color = QColor(255, 255, 255, 235)
                        self._ripple.stop()
                        self._ripple.start()
                        self.clicked.emit(self.button_data.id)

    def mouseDoubleClickEvent(self, e):
        e.accept()

    # ------------------------------------------------------------ 끌어다 놓기
    def dragEnterEvent(self, e):
        if e.mimeData().hasFormat(MIME_TYPE):
            e.acceptProposedAction()
            self.drop_target = True
            self.update()

    def dragLeaveEvent(self, e):
        self.drop_target = False
        self.update()

    def dropEvent(self, e):
        self.drop_target = False
        self.update()
        src = bytes(e.mimeData().data(MIME_TYPE)).decode("utf-8")
        if src and src != self.button_data.id:
            self.swapped.emit(src, self.button_data.id)
        e.acceptProposedAction()
