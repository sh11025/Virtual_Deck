"""
덱 배경 만들기
- 유리 모드: 덱 뒤에 있는 바탕화면/창을 캡처해서 흐리게 만든 뒤 덱 배경으로 씁니다.
  (덱 창 자체는 캡처에서 빠지도록 설정하기 때문에 '유리 너머로 비치는' 효과가 됩니다)
- 단색 / 그라데이션 / 이미지 모드도 여기서 만듭니다.
"""

import os
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, QRect, QSize, Qt, QPointF, QRectF
from PySide6.QtGui import QPixmap, QPainter, QColor, QLinearGradient, QImage, QGuiApplication

from ui.glass import blur_pixmap, make_aurora, with_alpha
from ui import theme
from ui.theme import T


class ScreenGrabber(QObject):
    """창 뒤 화면을 주기적으로 캡처해서 흐린 그림을 만들어 줍니다."""

    updated = Signal()

    def __init__(self, window, parent=None):
        super().__init__(parent)
        self.window = window
        self.enabled = False
        self.paused = False                     # 멈춘 동안은 마지막 배경 그대로 (다시 찍지 않음)
        self.blur = 22
        self.margin = 300                       # 창 크기보다 사방 300px 넉넉히 캡처
        self.raw_pixmap: Optional[QPixmap] = None   # 흐리게 만들기 전 원본 캡처
        self.pixmap: Optional[QPixmap] = None       # 넉넉한 영역의 흐린 그림
        self.grab_rect: Optional[QRect] = None      # 캡처한 화면 절대 좌표 영역
        self._sig = None
        self._timer = QTimer(self)
        self._timer.setInterval(450)
        self._timer.timeout.connect(self.refresh)
        self._move_timer = QTimer(self)
        self._move_timer.setSingleShot(True)
        self._move_timer.setInterval(16)
        self._move_timer.timeout.connect(lambda: self.refresh(force=True))

    def set_enabled(self, on: bool, blur: int = 22):
        self.enabled = on
        self.blur = blur
        if on:
            self._timer.start()
            QTimer.singleShot(0, lambda: self.refresh(force=True))
        else:
            self._timer.stop()
            self.pixmap = None
            self.raw_pixmap = None
            self.grab_rect = None
            self.updated.emit()

    def set_interval(self, ms: int):
        """절전 모드: 마우스가 덱 위에 없을 때는 천천히 새로고침"""
        if self._timer.interval() != ms:
            self._timer.setInterval(ms)

    def pause(self, paused: bool):
        self.paused = paused
        if not self.enabled:
            return
        if paused:
            self._timer.stop()
        else:
            self._timer.start()

    def window_moved(self):
        """
        창을 끄는 동안: 이미 보관한 넉넉한 영역 안에 창이 있으면 새로 찍지 않고
        보관된 그림에서 현재 창 위치에 맞게 잘라만 쓰도록 알립니다.
        영역 밖으로 나갔을 때만 타이머로 새로 찍습니다.
        """
        if not self.enabled or not self.window.isVisible():
            return
        geo = self.window.geometry()
        if self.pixmap is not None and self.grab_rect is not None and self.grab_rect.contains(geo):
            # 보관 영역 안: 캡처 없이 배경 조각만 다시 자름 (0.1ms 이내 처리)
            self.updated.emit()
        else:
            if not self._move_timer.isActive():
                self._move_timer.start()

    def refresh(self, force: bool = False, reblur_only: bool = False):
        if not self.enabled or not self.window.isVisible():
            return

        # 멈춘 동안에는 새로 찍지 않음 (흐림만 다시 하는 것은 괜찮음)
        if self.paused and not reblur_only:
            return

        # 흐림 정도만 바뀌었을 때: 원본이 있으면 다시 찍지 않고 다시 흐리게만 수행
        if reblur_only and self.raw_pixmap is not None and not self.raw_pixmap.isNull():
            dpr = self.raw_pixmap.devicePixelRatio() or 1.0
            blurred = blur_pixmap(self.raw_pixmap, int(self.blur * dpr))
            blurred.setDevicePixelRatio(dpr)
            self.pixmap = blurred
            self.updated.emit()
            return

        screen = self.window.screen() or QGuiApplication.primaryScreen()
        if screen is None:
            return
        geo = self.window.geometry()
        sg = screen.geometry()

        # 창 크기보다 사방 300px 넉넉한 영역 (화면 밖은 자르기)
        target_rect = geo.adjusted(-self.margin, -self.margin, self.margin, self.margin).intersected(sg)
        if target_rect.width() <= 0 or target_rect.height() <= 0:
            return

        try:
            raw = screen.grabWindow(0, target_rect.x() - sg.x(), target_rect.y() - sg.y(),
                                    target_rect.width(), target_rect.height())
        except Exception:
            return
        if raw.isNull():
            return

        # 변화가 없으면 다시 그리지 않음 (컴퓨터 부담 줄이기)
        tiny = raw.toImage().scaled(12, 12, Qt.IgnoreAspectRatio, Qt.FastTransformation)
        sig = bytes(tiny.constBits())[: 12 * 12 * 4]
        if not force and sig == self._sig and self.pixmap is not None:
            return
        self._sig = sig
        self.raw_pixmap = raw
        self.grab_rect = target_rect

        dpr = raw.devicePixelRatio() or 1.0
        blurred = blur_pixmap(raw, int(self.blur * dpr))
        blurred.setDevicePixelRatio(dpr)
        self.pixmap = blurred
        self.updated.emit()


_image_cache = {}


def _load_image(path: str) -> Optional[QPixmap]:
    if not path or not os.path.exists(path):
        return None
    key = (path, os.path.getmtime(path))
    if key not in _image_cache:
        _image_cache.clear()
        _image_cache[key] = QPixmap(path)
    pix = _image_cache[key]
    return None if pix.isNull() else pix


def compose_background(config, size: QSize, dpr: float, grabbed: Optional[QPixmap],
                       offset_in_window: QPointF,
                       grab_rect: Optional[QRect] = None, window_geo: Optional[QRect] = None) -> QPixmap:
    """
    덱 본체(유리판) 크기에 맞는 배경 그림을 만듭니다.
    결과 그림은 물리 픽셀 크기이며 devicePixelRatio 가 설정됩니다.
    보관된 넓은 캡처 그림(grabbed)에서 현재 창의 위치에 해당하는 영역을 잘라 사용합니다.
    """
    w, h = max(2, int(size.width() * dpr)), max(2, int(size.height() * dpr))
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    mode = config.bg_type
    dark = T().dark
    frost = max(0, min(100, int(getattr(config, "glass_frost", 20))))

    if mode == "clear":
        # 투명 (버튼만) 모드에서는 배경이 완전히 투명
        img.fill(Qt.transparent)
        out = QPixmap.fromImage(img)
        out.setDevicePixelRatio(dpr)
        return out

    img.fill(T().base)
    p = QPainter(img)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    full = QRectF(0, 0, w, h)

    if mode == "glass":
        if grabbed is not None and not grabbed.isNull():
            gdpr = grabbed.devicePixelRatio() or 1.0
            # 보관 그림 기준 현재 창/패널의 위치 계산
            if grab_rect is not None and window_geo is not None:
                src_x = (window_geo.x() - grab_rect.x() + offset_in_window.x()) * gdpr
                src_y = (window_geo.y() - grab_rect.y() + offset_in_window.y()) * gdpr
            else:
                src_x = offset_in_window.x() * gdpr
                src_y = offset_in_window.y() * gdpr
            src = QRectF(src_x, src_y, size.width() * gdpr, size.height() * gdpr)
            p.drawPixmap(full, grabbed, src)
            # 아주 얇게 덮어서 글자가 보일 정도로만 (뿌옇기 설정으로 조절)
            if dark:
                p.fillRect(full, QColor(10, 14, 26, int(45 + frost * 1.7)))
            else:
                p.fillRect(full, QColor(255, 255, 255, int(12 + frost * 1.9)))
        else:
            p.drawPixmap(0, 0, make_aurora(QSize(w, h), dark, seed=1))
            p.fillRect(full, QColor(255, 255, 255, 40) if not dark else QColor(0, 0, 0, 40))

        # 색이 도는 유리 (glass_tint: 캡처 배경 여부와 관계없이 적용)
        tint_name = getattr(config, "glass_tint", "")
        if tint_name:
            c_str = theme.glass_tint_hex(tint_name, "")
            if c_str:
                tint_alpha = 75 if grabbed is not None else 85
                p.fillRect(full, with_alpha(QColor(c_str), tint_alpha))
    elif mode == "color":
        p.fillRect(full, QColor(config.bg_color))
    elif mode == "gradient":
        if config.bg_gradient_dir == "left_to_right":
            g = QLinearGradient(0, 0, w, 0)
        elif config.bg_gradient_dir == "diagonal":
            g = QLinearGradient(0, 0, w, h)
        else:
            g = QLinearGradient(0, 0, 0, h)
        g.setColorAt(0.0, QColor(config.bg_gradient_start))
        g.setColorAt(1.0, QColor(config.bg_gradient_end))
        p.fillRect(full, g)
    elif mode == "image":
        pix = _load_image(config.bg_image_path)
        if pix is None:
            p.drawPixmap(0, 0, make_aurora(QSize(w, h), dark, seed=1))
        else:
            zoom = max(0.2, min(5.0, float(config.bg_image_zoom)))
            base = pix.size().scaled(QSize(w, h), Qt.KeepAspectRatioByExpanding)
            tw, th = base.width() * zoom, base.height() * zoom
            x = (w - tw) / 2 + config.bg_image_x * dpr
            y = (h - th) / 2 + config.bg_image_y * dpr
            p.drawPixmap(QRectF(x, y, tw, th), pix, QRectF(pix.rect()))
            p.fillRect(full, QColor(255, 255, 255, 30) if not dark else QColor(0, 0, 0, 60))
    p.end()
    out = QPixmap.fromImage(img)
    out.setDevicePixelRatio(dpr)
    return out
