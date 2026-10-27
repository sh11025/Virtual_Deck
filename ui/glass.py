"""
리퀴드 글라스 그리기 엔진
그림 파일 없이 코드로 유리를 그립니다. 그래서 어떤 크기에서도 선명하고 색도 자유롭게 바뀝니다.

유리 한 장은 아래 순서로 겹쳐 그립니다. (참고.jpg 의 유리 구조를 따름)
  1. 바닥 그림자 (색유리는 같은 색의 은은한 빛 번짐)
  2. 몸통: 뒤 배경을 살짝 확대해서 비춤(렌즈 효과) + 얇은 흰 막 / 색유리 채움
  3. 아래쪽 안쪽에서 퍼지는 빛 (빛이 유리를 통과해 모이는 느낌)
  4. 가장자리 두께 띠 (두꺼운 유리 테두리 느낌)
  5. 위쪽 넓은 반사광
  6. 밝은 윗면 / 어두운 아랫면 테두리
  7. 모서리 무지개빛 번짐
"""

import math
from typing import Optional

from PySide6.QtCore import Qt, QRectF, QPointF, QSize
from PySide6.QtGui import (
    QPainter, QPainterPath, QColor, QLinearGradient, QRadialGradient,
    QConicalGradient, QPen, QBrush, QPixmap, QImage,
)

from ui.theme import T, tint_colors


# ------------------------------------------------------------------ 기본 도형
def rounded_path(rect: QRectF, radius: float) -> QPainterPath:
    r = max(0.0, min(radius, rect.width() / 2, rect.height() / 2))
    path = QPainterPath()
    path.addRoundedRect(rect, r, r)
    return path


def with_alpha(c: QColor, a: float) -> QColor:
    q = QColor(c)
    q.setAlphaF(max(0.0, min(1.0, a)))
    return q


def lighter(c: QColor, f: float) -> QColor:
    """f(0~1)만큼 흰색 쪽으로"""
    return QColor(int(c.red() + (255 - c.red()) * f),
                  int(c.green() + (255 - c.green()) * f),
                  int(c.blue() + (255 - c.blue()) * f), c.alpha())


def soft_shadow(p: QPainter, rect: QRectF, radius: float, color: QColor,
                spread: float = 8.0, offset_y: float = 3.0, steps: int = 9) -> None:
    """여러 겹의 반투명 도형으로 부드러운 그림자를 만듭니다."""
    if spread <= 0 or color.alpha() == 0:
        return
    p.save()
    p.setPen(Qt.NoPen)
    base_alpha = color.alphaF()
    for i in range(steps):
        t = (i + 1) / steps
        grow = spread * t
        a = base_alpha * (1 - t) ** 1.6 / steps * 2.4
        p.setBrush(with_alpha(color, a))
        r = rect.translated(0, offset_y * (0.5 + t * 0.5)).adjusted(-grow * 0.8, -grow * 0.4, grow * 0.8, grow)
        p.drawPath(rounded_path(r, radius + grow * 0.8))
    p.restore()


def blur_pixmap(pix: QPixmap, radius: int) -> QPixmap:
    """작게 줄였다가 다시 키워서 빠르게 흐리게 만듭니다."""
    if pix.isNull() or radius <= 1:
        return pix
    w, h = pix.width(), pix.height()
    img = pix.toImage()
    factor = max(2.0, radius / 2.2)
    for _ in range(2):
        sw, sh = max(2, int(w / factor)), max(2, int(h / factor))
        img = img.scaled(sw, sh, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        img = img.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
        factor = max(2.0, factor * 0.6)
    return QPixmap.fromImage(img)


def make_aurora(size: QSize, dark: bool, seed: int = 0) -> QPixmap:
    """
    부드러운 파스텔 빛 번짐 배경. 뒤 비침을 쓸 수 없을 때나 설정창 배경으로 사용합니다.
    """
    w, h = max(4, size.width()), max(4, size.height())
    img = QImage(w, h, QImage.Format_ARGB32_Premultiplied)
    img.fill(QColor(14, 18, 32) if dark else QColor(238, 242, 249))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    if dark:
        blobs = [((0.15, 0.10), 0.75, "#3b4fd8", 0.55), ((0.95, 0.30), 0.70, "#9333ea", 0.40),
                 ((0.40, 1.05), 0.80, "#0ea5e9", 0.40), ((0.85, 0.95), 0.55, "#db2777", 0.30)]
    else:
        blobs = [((0.10, 0.05), 0.80, "#b9d7ff", 0.95), ((0.95, 0.20), 0.70, "#f9c9e3", 0.85),
                 ((0.35, 1.00), 0.85, "#c3f2e1", 0.85), ((0.90, 0.95), 0.60, "#ffd9bf", 0.80),
                 ((0.55, 0.45), 0.45, "#e2dcff", 0.70)]
    shift = (seed % 7) * 0.03
    span = max(w, h)
    for (cx, cy), rad, col, alpha in blobs:
        center = QPointF(w * (cx + shift) % (w * 1.1), h * cy)
        g = QRadialGradient(center, span * rad)
        c = QColor(col)
        g.setColorAt(0.0, with_alpha(c, alpha))
        g.setColorAt(1.0, with_alpha(c, 0.0))
        p.fillRect(QRectF(0, 0, w, h), g)
    p.end()
    return QPixmap.fromImage(img)


def paint_glass_under(p: QPainter, rect: QRectF, radius: float, *, tint: Optional[str] = None,
                      hover: float = 0.0, press: float = 0.0, shadow_strength: float = 1.0,
                      shadow_max: Optional[float] = None, glow: Optional[QColor] = None,
                      glow_amount: float = 0.0) -> None:
    """
    유리 아래쪽에 깔리는 것들(그림자, 색 빛 번짐, 바깥 빛)만 그립니다.
    덱 버튼은 이것을 버튼판이 한꺼번에 그려서 버튼 사이 여백 없이도 그림자가 잘리지 않습니다.
    """
    dark = T().dark
    colors = tint_colors(tint)
    press = max(0.0, press)
    w, h = rect.width(), rect.height()
    small = min(w, h)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    if shadow_strength > 0:
        lift = hover * (1 - press)
        if colors:
            sc = with_alpha(colors[1], (0.30 + 0.12 * lift) * shadow_strength * (0.6 if dark else 1.0))
        else:
            sc = QColor(0, 0, 0, 120) if dark else QColor(40, 62, 100, 70)
            sc = with_alpha(sc, sc.alphaF() * (1 + 0.35 * lift) * shadow_strength)
        spread = small * (0.10 + 0.06 * lift - 0.04 * press)
        off = small * (0.035 + 0.03 * lift - 0.02 * press)
        if shadow_max is not None:  # 위젯 밖으로 잘리지 않게 제한
            spread = min(spread, shadow_max)
            off = min(off, shadow_max * 0.5)
        soft_shadow(p, rect, radius, sc, spread=spread, offset_y=off)
        if colors:  # 색유리 아래로 번지는 빛 (참고 이미지의 주황 빛 번짐)
            glow_h = h * 0.62 if shadow_max is None else min(h * 0.62, h * 0.30 + shadow_max)
            glow_rect = QRectF(rect.left() + w * 0.08, rect.bottom() - h * 0.30, w * 0.84, glow_h)
            g = QRadialGradient(glow_rect.center(), max(glow_rect.width(), glow_rect.height()) * 0.5)
            g.setColorAt(0.0, with_alpha(lighter(colors[0], 0.1), 0.30 * shadow_strength))
            g.setColorAt(1.0, with_alpha(colors[0], 0.0))
            p.setPen(Qt.NoPen)
            p.setBrush(g)
            p.drawEllipse(glow_rect)

    # 바깥 빛 (켜짐/성공/실패)
    if glow is not None and glow_amount > 0.01:
        glow_span = small * 0.16 if shadow_max is None else min(small * 0.16, shadow_max)
        for i in range(6):
            k = (i + 1) / 6
            grow = glow_span * k
            pen = QPen(with_alpha(glow, glow.alphaF() * glow_amount * (1 - k) * 0.55), 2.2)
            p.setPen(pen)
            p.setBrush(Qt.NoBrush)
            p.drawPath(rounded_path(rect.adjusted(-grow, -grow, grow, grow), radius + grow))

    p.restore()


# ------------------------------------------------------------------ 유리 그리기
def paint_glass(
    p: QPainter,
    rect: QRectF,
    radius: float,
    *,
    tint: Optional[str] = None,
    hover: float = 0.0,
    press: float = 0.0,
    backdrop: Optional[QPixmap] = None,
    backdrop_rect: Optional[QRectF] = None,
    lens: float = 0.06,
    shadow: bool = True,
    shadow_strength: float = 1.0,
    shadow_max: Optional[float] = None,
    fill: Optional[float] = None,
    glow: Optional[QColor] = None,
    glow_amount: float = 0.0,
    rainbow: float = 1.0,
    highlight: float = 1.0,
    ripple: Optional[tuple] = None,
) -> None:
    """
    유리 한 장을 그립니다.

    rect/radius: 위치와 모서리 둥글기
    tint: None 또는 'clear' 이면 투명 유리, 그 외 theme.TINTS 의 색 이름
    hover/press: 0~1 (마우스 올림/누름 정도, 애니메이션 값)
    backdrop/backdrop_rect: 유리 뒤에 비칠 배경 그림과 그 안에서의 위치 (렌즈 효과)
    fill: 투명 유리의 흰 막 진하기(0~1). None 이면 상황에 맞게 자동
    glow: 바깥쪽 빛 (성공/실패/켜짐 표시)
    ripple: (누른 위치 QPointF, 진행도 0~1, 색 QColor) — 누른 자리에서 퍼지는 물결
    """
    t = T()
    dark = t.dark
    colors = tint_colors(tint)
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    path = rounded_path(rect, radius)
    w, h = rect.width(), rect.height()
    small = min(w, h)

    # 1. 그림자 · 바깥 빛 (따로 그리는 경우엔 shadow=False)
    if shadow:
        paint_glass_under(p, rect, radius, tint=tint, hover=hover, press=press,
                          shadow_strength=shadow_strength, shadow_max=shadow_max,
                          glow=glow, glow_amount=glow_amount)

    # 2. 몸통 --------------------------------------------------------
    p.save()
    p.setClipPath(path, Qt.IntersectClip)
    p.setPen(Qt.NoPen)
    if backdrop is not None and not backdrop.isNull() and backdrop_rect is not None:
        mag = 1.0 + lens * (1 + 0.4 * hover + 0.5 * max(0.0, press))
        src = QRectF(backdrop_rect)
        cx, cy = src.center().x(), src.center().y()
        sw, sh = src.width() / mag, src.height() / mag
        src = QRectF(cx - sw / 2, cy - sh / 2, sw, sh)
        p.drawPixmap(rect, backdrop, src)

    if colors:
        top, deep, _ = colors
        g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
        g.setColorAt(0.0, with_alpha(lighter(top, 0.15 + 0.12 * hover), 0.93))
        g.setColorAt(0.55, with_alpha(deep, 0.90))
        g.setColorAt(1.0, with_alpha(deep.darker(112), 0.94))
        p.fillRect(rect, g)
        # 가운데가 살짝 밝게 비치는 느낌
        g2 = QLinearGradient(rect.topLeft(), rect.topRight())
        g2.setColorAt(0.0, QColor(255, 255, 255, 0))
        g2.setColorAt(0.5, QColor(255, 255, 255, 28))
        g2.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(rect, g2)
    else:
        if fill is None:
            fill = 0.11 if backdrop is not None else 0.70
        if dark:
            a = (0.06 + fill * 0.16) + 0.08 * hover
            g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            g.setColorAt(0.0, QColor(255, 255, 255, int(255 * (a + 0.05))))
            g.setColorAt(1.0, QColor(255, 255, 255, int(255 * a * 0.6)))
        else:
            a = fill + 0.16 * hover
            g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
            g.setColorAt(0.0, QColor(255, 255, 255, int(255 * min(1, a + 0.12))))
            g.setColorAt(0.6, QColor(248, 251, 255, int(255 * min(1, a * 0.8))))
            g.setColorAt(1.0, QColor(240, 246, 253, int(255 * min(1, a * 0.95))))
        p.fillRect(rect, g)

    # 누른 자리에서 퍼지는 물결
    if ripple is not None and 0.0 < ripple[1] < 1.0:
        pos, prog, rc = ripple
        diag = math.hypot(w, h)
        rr = diag * (0.06 + 0.82 * prog)
        fade = (1 - prog) ** 0.85
        rg = QRadialGradient(pos, rr)
        rg.setColorAt(0.0, with_alpha(rc, rc.alphaF() * 0.42 * fade))
        rg.setColorAt(0.70, with_alpha(rc, rc.alphaF() * 0.28 * fade))
        rg.setColorAt(0.90, with_alpha(rc, rc.alphaF() * 0.85 * fade))
        rg.setColorAt(0.97, with_alpha(rc, rc.alphaF() * 0.35 * fade))
        rg.setColorAt(1.0, with_alpha(rc, 0.0))
        p.fillRect(rect, rg)

    # 누르면 살짝 어두워짐
    if press > 0:
        p.fillRect(rect, QColor(20, 40, 80, int(26 * press)) if not dark else QColor(0, 0, 0, int(50 * press)))

    # 3. 아래쪽 안쪽 빛 ----------------------------------------------
    gb = QRadialGradient(QPointF(rect.center().x(), rect.bottom() + h * 0.10), max(w * 0.62, h * 0.6))
    if colors:
        gb.setColorAt(0.0, with_alpha(lighter(colors[0], 0.55), 0.55))
    else:
        gb.setColorAt(0.0, QColor(255, 255, 255, 50 if dark else 120))
    gb.setColorAt(1.0, QColor(255, 255, 255, 0))
    p.fillRect(rect, gb)

    # 4. 가장자리 두께 띠 --------------------------------------------
    band = max(2.5, min(small * 0.085, 9.0))
    gpen = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    k = 1.0 if not colors else 0.75
    gpen.setColorAt(0.0, QColor(255, 255, 255, int((105 if not dark else 45) * k)))
    gpen.setColorAt(0.45, QColor(255, 255, 255, int((22 if not dark else 8) * k)))
    gpen.setColorAt(1.0, QColor(255, 255, 255, int((150 if not dark else 55) * k)))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QBrush(gpen), band * 2))
    p.drawPath(path)
    # 띠 안쪽 경계의 아주 옅은 선 (두께감)
    inner = rect.adjusted(band, band, -band, -band)
    if colors:
        p.setPen(QPen(QColor(255, 255, 255, 40), 1.0))
    elif dark:
        p.setPen(QPen(QColor(255, 255, 255, 16), 1.0))
    else:
        p.setPen(QPen(QColor(70, 95, 140, 30), 1.0))
    p.drawPath(rounded_path(inner, max(0, radius - band)))

    # 5. 위쪽 반사광 -------------------------------------------------
    if highlight > 0:
        inset = max(2.0, small * 0.06)
        hh = h * (0.46 if h < 120 else min(0.30, 60 / h + 0.1))
        hl = QRectF(rect.left() + inset, rect.top() + inset * 0.7, w - inset * 2, hh)
        gh = QLinearGradient(hl.topLeft(), hl.bottomLeft())
        top_a = (150 if not colors else 135) if not dark else 70
        top_a = int((top_a + 50 * hover) * highlight * (1 - 0.4 * max(0.0, press)))
        gh.setColorAt(0.0, QColor(255, 255, 255, min(255, top_a)))
        gh.setColorAt(0.6, QColor(255, 255, 255, int(top_a * 0.22)))
        gh.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.setPen(Qt.NoPen)
        p.setBrush(gh)
        p.drawPath(rounded_path(hl, max(0, radius - inset)))
        # 왼쪽 위 모서리의 작은 반짝임
        glint = QRadialGradient(QPointF(rect.left() + w * 0.2, rect.top() + h * 0.12), small * 0.35)
        glint.setColorAt(0.0, QColor(255, 255, 255, int(90 * highlight)))
        glint.setColorAt(1.0, QColor(255, 255, 255, 0))
        p.fillRect(rect, glint)
    p.restore()

    # 6. 테두리 ------------------------------------------------------
    edge = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    if dark:
        edge.setColorAt(0.0, QColor(255, 255, 255, 150))
        edge.setColorAt(0.5, QColor(255, 255, 255, 40))
        edge.setColorAt(1.0, QColor(255, 255, 255, 90))
    else:
        edge.setColorAt(0.0, QColor(255, 255, 255, 255))
        edge.setColorAt(0.5, QColor(255, 255, 255, 150))
        edge.setColorAt(1.0, QColor(255, 255, 255, 230))
    p.setBrush(Qt.NoBrush)
    p.setPen(QPen(QBrush(edge), 1.3))
    p.drawPath(rounded_path(rect.adjusted(0.65, 0.65, -0.65, -0.65), radius - 0.6))
    if not dark:
        # 흰 배경 위에서도 윤곽이 보이도록 아주 옅은 바깥 선
        line = with_alpha(colors[1], 0.55) if colors else QColor(110, 135, 175, 70)
        p.setPen(QPen(line, 0.8))
        p.drawPath(rounded_path(rect.adjusted(-0.4, -0.4, 0.4, 0.4), radius + 0.4))

    # 7. 무지개빛 번짐 -----------------------------------------------
    if rainbow > 0:
        cg = QConicalGradient(rect.center(), 0)
        a1 = int(150 * rainbow * (1 + 0.3 * hover))
        a2 = int(90 * rainbow)
        clear = QColor(255, 255, 255, 0)
        stops = [(0.00, clear), (0.27, clear),
                 (0.31, QColor(255, 120, 200, a2)), (0.35, QColor(120, 170, 255, a2)),
                 (0.39, QColor(120, 240, 200, a2)), (0.43, clear),
                 (0.76, clear),
                 (0.80, QColor(255, 90, 90, a1)), (0.83, QColor(255, 210, 90, a1)),
                 (0.86, QColor(120, 235, 140, a1)), (0.89, QColor(90, 200, 255, a1)),
                 (0.92, QColor(170, 120, 255, a1)), (0.95, clear), (1.0, clear)]
        for pos, c in stops:
            cg.setColorAt(pos, c)
        p.save()
        p.setClipPath(path, Qt.IntersectClip)
        p.setPen(QPen(QBrush(cg), max(1.6, small * 0.03)))
        p.drawPath(rounded_path(rect.adjusted(1.2, 1.2, -1.2, -1.2), radius - 1.2))
        p.restore()

    p.restore()


_glass_cache: dict[tuple, QPixmap] = {}


def clear_glass_cache():
    _glass_cache.clear()


def get_glass_pixmap(w: float, h: float, radius: float, tint: Optional[str],
                     dark: bool, dpr: float, hover_idx: int, fill: float = 0.11) -> QPixmap:
    """
    유리 층을 QPixmap으로 미리 그려 캐시합니다.
    (크기, 모서리, 색상, 테마, dpr, hover 0/1, fill)
    """
    key = (round(w, 1), round(h, 1), round(radius, 1), tint or "", dark, round(dpr, 2), int(hover_idx), round(fill, 2))
    pix = _glass_cache.get(key)
    if pix is not None and not pix.isNull():
        return pix
    pw, ph = max(1, int(round(w * dpr))), max(1, int(round(h * dpr)))
    img = QImage(pw, ph, QImage.Format_ARGB32_Premultiplied)
    img.fill(Qt.transparent)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.scale(dpr, dpr)
    paint_glass(p, QRectF(0, 0, w, h), radius, tint=tint, hover=float(hover_idx),
                press=0.0, backdrop=None, shadow=False, fill=fill)
    p.end()
    pix = QPixmap.fromImage(img)
    pix.setDevicePixelRatio(dpr)
    _glass_cache[key] = pix
    return pix


def paint_slot(p: QPainter, rect: QRectF, radius: float, hover: float = 0.0) -> None:
    """움푹 들어간 빈 홈 (빈 버튼, 꺼진 토글 바탕 등)"""
    dark = T().dark
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    path = rounded_path(rect, radius)
    p.setClipPath(path, Qt.IntersectClip)
    g = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    if dark:
        g.setColorAt(0.0, QColor(0, 0, 0, 70 + int(10 * hover)))
        g.setColorAt(1.0, QColor(255, 255, 255, 10 + int(16 * hover)))
    else:
        g.setColorAt(0.0, QColor(40, 62, 100, 34 + int(8 * hover)))
        g.setColorAt(0.35, QColor(255, 255, 255, 30 + int(40 * hover)))
        g.setColorAt(1.0, QColor(255, 255, 255, 80 + int(50 * hover)))
    p.fillRect(rect, g)
    # 안쪽 그림자 (위쪽)
    shade = QLinearGradient(rect.topLeft(), QPointF(rect.left(), rect.top() + min(14, rect.height() * 0.3)))
    shade.setColorAt(0.0, QColor(10, 25, 60, 45 if not dark else 90))
    shade.setColorAt(1.0, QColor(10, 25, 60, 0))
    p.fillRect(rect, shade)
    p.setClipping(False)
    # 아래쪽 밝은 가장자리 (빛이 홈 가장자리에 맺힘)
    edge = QLinearGradient(rect.topLeft(), rect.bottomLeft())
    edge.setColorAt(0.0, QColor(20, 40, 80, 40 if not dark else 70))
    edge.setColorAt(0.5, QColor(255, 255, 255, 30 if not dark else 10))
    edge.setColorAt(1.0, QColor(255, 255, 255, 230 if not dark else 70))
    p.setPen(QPen(QBrush(edge), 1.2))
    p.setBrush(Qt.NoBrush)
    p.drawPath(rounded_path(rect.adjusted(0.6, 0.6, -0.6, -0.6), radius - 0.6))
    p.restore()


# ------------------------------------------------------------------ 선 아이콘
def draw_icon(p: QPainter, name: str, rect: QRectF, color: QColor, width: float = None) -> None:
    """간단한 선 아이콘을 그립니다. (그림 파일이 필요 없어 늘 선명함)"""
    s = min(rect.width(), rect.height())
    width = width or max(1.4, s * 0.1)
    c = rect.center()
    u = s / 2  # 반지름 단위
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    pen = QPen(color, width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.NoBrush)

    def pt(x, y):
        return QPointF(c.x() + x * u, c.y() + y * u)

    if name == "close":
        p.drawLine(pt(-0.5, -0.5), pt(0.5, 0.5))
        p.drawLine(pt(0.5, -0.5), pt(-0.5, 0.5))
    elif name == "minus":
        p.drawLine(pt(-0.55, 0), pt(0.55, 0))
    elif name == "plus":
        p.drawLine(pt(-0.6, 0), pt(0.6, 0))
        p.drawLine(pt(0, -0.6), pt(0, 0.6))
    elif name == "check":
        path = QPainterPath(pt(-0.6, 0.0))
        path.lineTo(pt(-0.18, 0.42))
        path.lineTo(pt(0.62, -0.45))
        p.drawPath(path)
    elif name == "back":
        path = QPainterPath(pt(0.25, -0.6))
        path.lineTo(pt(-0.35, 0))
        path.lineTo(pt(0.25, 0.6))
        p.drawPath(path)
    elif name == "chevron":
        path = QPainterPath(pt(-0.45, -0.18))
        path.lineTo(pt(0, 0.27))
        path.lineTo(pt(0.45, -0.18))
        p.drawPath(path)
    elif name == "list":
        for y in (-0.5, 0, 0.5):
            p.drawLine(pt(-0.25, y), pt(0.65, y))
            p.setBrush(color)
            p.drawEllipse(pt(-0.58, y), width * 0.55, width * 0.55)
            p.setBrush(Qt.NoBrush)
    elif name == "gear":
        p.drawEllipse(c, u * 0.28, u * 0.28)
        path = QPainterPath()
        teeth = 8
        for i in range(teeth * 2):
            ang = math.pi * 2 * i / (teeth * 2)
            r1 = u * (0.78 if i % 2 == 0 else 0.58)
            a1, a2 = ang - math.pi / (teeth * 2) * 0.75, ang + math.pi / (teeth * 2) * 0.75
            q1 = QPointF(c.x() + math.cos(a1) * r1, c.y() + math.sin(a1) * r1)
            q2 = QPointF(c.x() + math.cos(a2) * r1, c.y() + math.sin(a2) * r1)
            if i == 0:
                path.moveTo(q1)
            else:
                path.lineTo(q1)
            path.lineTo(q2)
        path.closeSubpath()
        p.drawPath(path)
    elif name == "undo":
        path = QPainterPath(pt(-0.55, -0.15))
        path.cubicTo(pt(-0.2, -0.6), pt(0.6, -0.5), pt(0.6, 0.1))
        path.cubicTo(pt(0.6, 0.45), pt(0.3, 0.6), pt(0.0, 0.6))
        p.drawPath(path)
        head = QPainterPath(pt(-0.6, -0.6))
        head.lineTo(pt(-0.58, -0.12))
        head.lineTo(pt(-0.12, -0.18))
        p.drawPath(head)
    elif name == "copy":
        p.drawRoundedRect(QRectF(pt(-0.3, -0.3), pt(0.65, 0.65)), u * 0.15, u * 0.15)
        path = QPainterPath(pt(-0.3, 0.3))
        path.lineTo(pt(-0.65, 0.3))
        path.lineTo(pt(-0.65, -0.65))
        path.lineTo(pt(0.3, -0.65))
        path.lineTo(pt(0.3, -0.3))
        p.drawPath(path)
    elif name == "paste":
        p.drawRoundedRect(QRectF(pt(-0.55, -0.5), pt(0.55, 0.7)), u * 0.15, u * 0.15)
        p.drawRoundedRect(QRectF(pt(-0.25, -0.7), pt(0.25, -0.38)), u * 0.08, u * 0.08)
    elif name == "trash":
        p.drawLine(pt(-0.62, -0.42), pt(0.62, -0.42))
        p.drawLine(pt(-0.2, -0.62), pt(0.2, -0.62))
        path = QPainterPath(pt(-0.45, -0.3))
        path.lineTo(pt(-0.35, 0.65))
        path.lineTo(pt(0.35, 0.65))
        path.lineTo(pt(0.45, -0.3))
        p.drawPath(path)
    elif name == "edit":
        path = QPainterPath(pt(-0.6, 0.6))
        path.lineTo(pt(-0.55, 0.25))
        path.lineTo(pt(0.3, -0.6))
        path.lineTo(pt(0.6, -0.3))
        path.lineTo(pt(-0.25, 0.55))
        path.closeSubpath()
        p.drawPath(path)
    elif name == "folder":
        path = QPainterPath(pt(-0.7, -0.45))
        path.lineTo(pt(-0.2, -0.45))
        path.lineTo(pt(-0.05, -0.28))
        path.lineTo(pt(0.7, -0.28))
        path.lineTo(pt(0.7, 0.55))
        path.lineTo(pt(-0.7, 0.55))
        path.closeSubpath()
        p.drawPath(path)
    elif name == "info":
        p.drawEllipse(c, u * 0.75, u * 0.75)
        p.drawLine(pt(0, -0.05), pt(0, 0.4))
        p.setBrush(color)
        p.drawEllipse(pt(0, -0.35), width * 0.6, width * 0.6)
    elif name == "warn":
        p.drawEllipse(c, u * 0.75, u * 0.75)
        p.drawLine(pt(0, -0.4), pt(0, 0.08))
        p.setBrush(color)
        p.drawEllipse(pt(0, 0.38), width * 0.6, width * 0.6)
    elif name == "stop":
        p.setBrush(color)
        p.drawRoundedRect(QRectF(pt(-0.4, -0.4), pt(0.4, 0.4)), u * 0.12, u * 0.12)
    elif name == "eye":
        path = QPainterPath(pt(-0.75, 0))
        path.quadTo(pt(0, -0.75), pt(0.75, 0))
        path.quadTo(pt(0, 0.75), pt(-0.75, 0))
        p.drawPath(path)
        p.drawEllipse(c, u * 0.22, u * 0.22)
    elif name == "power":
        p.drawArc(QRectF(pt(-0.6, -0.55), pt(0.6, 0.65)), 120 * 16, -240 * 16 + 0)
        p.drawLine(pt(0, -0.7), pt(0, -0.05))
    elif name == "import":
        p.drawLine(pt(0, -0.65), pt(0, 0.25))
        path = QPainterPath(pt(-0.35, -0.1))
        path.lineTo(pt(0, 0.25))
        path.lineTo(pt(0.35, -0.1))
        p.drawPath(path)
        p.drawLine(pt(-0.62, 0.62), pt(0.62, 0.62))
    elif name == "export":
        p.drawLine(pt(0, 0.25), pt(0, -0.65))
        path = QPainterPath(pt(-0.35, -0.3))
        path.lineTo(pt(0, -0.65))
        path.lineTo(pt(0.35, -0.3))
        p.drawPath(path)
        p.drawLine(pt(-0.62, 0.62), pt(0.62, 0.62))
    elif name == "duplicate":
        p.drawRoundedRect(QRectF(pt(-0.65, -0.65), pt(0.3, 0.3)), u * 0.15, u * 0.15)
        p.drawRoundedRect(QRectF(pt(-0.3, -0.3), pt(0.65, 0.65)), u * 0.15, u * 0.15)
    elif name == "refresh":
        p.drawArc(QRectF(pt(-0.6, -0.6), pt(0.6, 0.6)), 30 * 16, 280 * 16)
        path = QPainterPath(pt(0.62, -0.62))
        path.lineTo(pt(0.55, -0.22))
        path.lineTo(pt(0.15, -0.3))
        p.drawPath(path)
    else:
        try:
            from ui.icons import paint_icon, PREFIX, REGISTRY
            k = name[len(PREFIX):] if name.startswith(PREFIX) else name
            if k in REGISTRY:
                paint_icon(p, PREFIX + k, rect, color)
        except Exception:
            pass
    p.restore()


def icon_pixmap(name: str, size: int, color: QColor, dpr: float = 2.0) -> QPixmap:
    pix = QPixmap(int(size * dpr), int(size * dpr))
    pix.setDevicePixelRatio(dpr)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    draw_icon(p, name, QRectF(size * 0.12, size * 0.12, size * 0.76, size * 0.76), color)
    p.end()
    return pix
