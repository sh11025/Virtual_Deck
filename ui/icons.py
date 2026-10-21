"""
아이콘 테마
코드로 그린 기본 아이콘 세트입니다. 모든 아이콘이 같은 선 굵기와 둥근 끝을 써서
덱 전체가 통일돼 보입니다.

버튼에는 'icon:이름' 형태로 저장됩니다. (예: icon:volume_up)
스타일
  - line   : 선 아이콘
  - duotone: 선 + 옅은 색 채움
  - emoji  : 같은 뜻의 이모지로 표시
"""

import math
from typing import Callable, Dict, Optional, Tuple

from PySide6.QtCore import Qt, QRectF, QPointF
from PySide6.QtGui import QPainter, QPainterPath, QPen, QColor

PREFIX = "icon:"
STYLES = {"line": "선", "duotone": "두 톤", "emoji": "이모지"}


def is_theme_icon(icon: str) -> bool:
    return bool(icon) and icon.startswith(PREFIX) and icon[len(PREFIX):] in REGISTRY


def icon_name(icon: str) -> str:
    return icon[len(PREFIX):] if icon and icon.startswith(PREFIX) else ""


# ------------------------------------------------------------------ 그리기 도우미 ([-1, 1] 좌표)
def poly(*pts, close=False) -> QPainterPath:
    path = QPainterPath(QPointF(*pts[0]))
    for p in pts[1:]:
        path.lineTo(QPointF(*p))
    if close:
        path.closeSubpath()
    return path


def circle(cx, cy, r) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), r, r)
    return path


def ellipse(cx, cy, rx, ry) -> QPainterPath:
    path = QPainterPath()
    path.addEllipse(QPointF(cx, cy), rx, ry)
    return path


def rrect(x, y, w, h, r) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(QRectF(x, y, w, h), r, r)
    return path


def arc(cx, cy, r, start, span) -> QPainterPath:
    """start/span: 도(3시 방향 0도, 반시계 방향 +)"""
    rect = QRectF(cx - r, cy - r, 2 * r, 2 * r)
    path = QPainterPath()
    path.arcMoveTo(rect, start)
    path.arcTo(rect, start, span)
    return path


class Ctx:
    def __init__(self, p: QPainter, color: QColor, style: str, accent: QColor):
        self.p = p
        self.color = color
        self.style = style
        self.accent = accent
        self.width = 0.13

    def stroke(self, path: QPainterPath, width: float = None):
        self.p.setBrush(Qt.NoBrush)
        self.p.setPen(QPen(self.color, width or self.width, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.p.drawPath(path)

    def fill(self, path: QPainterPath):
        """두 톤 스타일에서만 칠해지는 옅은 면"""
        if self.style != "duotone":
            return
        c = QColor(self.accent)
        c.setAlphaF(0.30)
        self.p.setPen(Qt.NoPen)
        self.p.setBrush(c)
        self.p.drawPath(path)

    def solid(self, path: QPainterPath):
        self.p.setPen(QPen(self.color, self.width * 0.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        self.p.setBrush(self.color)
        self.p.drawPath(path)

    def both(self, path: QPainterPath):
        self.fill(path)
        self.stroke(path)


# ------------------------------------------------------------------ 아이콘들
def _globe(c):
    c.fill(circle(0, 0, .82))
    c.stroke(circle(0, 0, .82))
    c.stroke(ellipse(0, 0, .36, .82))
    c.stroke(poly((-.82, 0), (.82, 0)))
    c.stroke(poly((-.7, -.42), (.7, -.42)))
    c.stroke(poly((-.7, .42), (.7, .42)))


def _folder(c):
    path = poly((-.85, -.55), (-.3, -.55), (-.12, -.35), (.85, -.35), (.85, .62), (-.85, .62), close=True)
    c.both(path)
    c.stroke(poly((-.85, -.15), (.85, -.15)))


def _file(c):
    path = poly((-.55, -.85), (.2, -.85), (.6, -.45), (.6, .85), (-.55, .85), close=True)
    c.both(path)
    c.stroke(poly((.2, -.85), (.2, -.45), (.6, -.45)))
    c.stroke(poly((-.3, .05), (.35, .05)))
    c.stroke(poly((-.3, .4), (.35, .4)))


def _note(c):
    c.both(rrect(-.68, -.8, 1.36, 1.6, .2))
    for y in (-.38, 0, .38):
        c.stroke(poly((-.38, y), (.38, y)))


def _music(c):
    c.solid(ellipse(-.48, .5, .26, .2))
    c.solid(ellipse(.52, .32, .26, .2))
    c.stroke(poly((-.24, .5), (-.24, -.62), (.76, -.82), (.76, .32)))
    c.stroke(poly((-.24, -.3), (.76, -.5)))


def _video(c):
    c.both(rrect(-.85, -.6, 1.7, 1.2, .25))
    c.solid(poly((-.2, -.3), (.35, 0), (-.2, .3), close=True))


def _image(c):
    c.both(rrect(-.85, -.65, 1.7, 1.3, .22))
    c.stroke(poly((-.7, .5), (-.2, -.05), (.2, .3), (.4, .12), (.75, .5)))
    c.solid(circle(.38, -.28, .13))


def _palette(c):
    path = QPainterPath(QPointF(0, -.85))
    path.cubicTo(QPointF(.6, -.85), QPointF(.9, -.4), QPointF(.85, 0))
    path.cubicTo(QPointF(.8, .35), QPointF(.35, .25), QPointF(.3, .5))
    path.cubicTo(QPointF(.25, .8), QPointF(.05, .85), QPointF(-.1, .85))
    path.cubicTo(QPointF(-.6, .85), QPointF(-.85, .45), QPointF(-.85, 0))
    path.cubicTo(QPointF(-.85, -.5), QPointF(-.5, -.85), QPointF(0, -.85))
    c.both(path)
    for x, y in ((-.45, -.05), (-.2, -.48), (.28, -.45)):
        c.solid(circle(x, y, .1))


def _gear(c):
    path = QPainterPath()
    teeth = 8
    for i in range(teeth * 2):
        ang = math.pi * 2 * i / (teeth * 2)
        r1 = .85 if i % 2 == 0 else .62
        half = math.pi / (teeth * 2) * .72
        q1 = QPointF(math.cos(ang - half) * r1, math.sin(ang - half) * r1)
        q2 = QPointF(math.cos(ang + half) * r1, math.sin(ang + half) * r1)
        if i == 0:
            path.moveTo(q1)
        else:
            path.lineTo(q1)
        path.lineTo(q2)
    path.closeSubpath()
    c.both(path)
    c.stroke(circle(0, 0, .27))


def _code(c):
    c.stroke(poly((-.35, -.5), (-.8, 0), (-.35, .5)))
    c.stroke(poly((.35, -.5), (.8, 0), (.35, .5)))
    c.stroke(poly((.15, -.7), (-.15, .7)))


def _terminal(c):
    c.both(rrect(-.85, -.7, 1.7, 1.4, .22))
    c.stroke(poly((-.5, -.25), (-.2, 0), (-.5, .25)))
    c.stroke(poly((0, .3), (.45, .3)))


def _keyboard(c):
    c.both(rrect(-.9, -.55, 1.8, 1.1, .2))
    for y in (-.22, .05):
        for x in (-.55, -.25, .05, .35, .6):
            c.solid(circle(x, y, .055))
    c.stroke(poly((-.4, .32), (.4, .32)))


def _window(c):
    c.both(rrect(-.85, -.7, 1.7, 1.4, .2))
    c.stroke(poly((-.85, -.32), (.85, -.32)))
    c.solid(circle(-.6, -.51, .06))
    c.solid(circle(-.4, -.51, .06))


def _monitor(c):
    c.both(rrect(-.88, -.72, 1.76, 1.1, .16))
    c.stroke(poly((0, .38), (0, .72)))
    c.stroke(poly((-.4, .75), (.4, .75)))


def _rocket(c):
    body = QPainterPath(QPointF(0, -.9))
    body.cubicTo(QPointF(.45, -.55), QPointF(.42, .1), QPointF(.28, .45))
    body.lineTo(QPointF(-.28, .45))
    body.cubicTo(QPointF(-.42, .1), QPointF(-.45, -.55), QPointF(0, -.9))
    c.both(body)
    c.stroke(circle(0, -.25, .14))
    c.stroke(poly((-.3, .1), (-.62, .42), (-.28, .45)))
    c.stroke(poly((.3, .1), (.62, .42), (.28, .45)))
    c.stroke(poly((-.12, .62), (-.12, .82)))
    c.stroke(poly((.12, .62), (.12, .82)))


def _bolt(c):
    path = poly((.15, -.9), (-.55, .1), (-.02, .1), (-.15, .9), (.55, -.1), (.02, -.1), close=True)
    c.both(path)


def _speaker(c):
    path = poly((-.85, -.28), (-.5, -.28), (-.05, -.68), (-.05, .68), (-.5, .28), (-.85, .28), close=True)
    c.both(path)


def _volume_up(c):
    _speaker(c)
    c.stroke(arc(.05, 0, .38, -45, 90))
    c.stroke(arc(.05, 0, .72, -45, 90))


def _volume_down(c):
    _speaker(c)
    c.stroke(arc(.05, 0, .42, -45, 90))


def _volume_mute(c):
    _speaker(c)
    c.stroke(poly((.3, -.3), (.85, .3)))
    c.stroke(poly((.85, -.3), (.3, .3)))


def _mic(c):
    c.both(rrect(-.3, -.88, .6, 1.1, .3))
    c.stroke(arc(0, -.05, .58, 180, 180))
    c.stroke(poly((0, .53), (0, .85)))
    c.stroke(poly((-.3, .85), (.3, .85)))


def _mic_off(c):
    _mic(c)
    c.stroke(poly((-.8, -.85), (.8, .85)))


def _play(c):
    c.solid(poly((-.45, -.7), (.7, 0), (-.45, .7), close=True))


def _pause(c):
    c.solid(rrect(-.55, -.7, .36, 1.4, .1))
    c.solid(rrect(.19, -.7, .36, 1.4, .1))


def _play_pause(c):
    c.solid(poly((-.85, -.6), (.05, 0), (-.85, .6), close=True))
    c.solid(rrect(.28, -.6, .2, 1.2, .07))
    c.solid(rrect(.62, -.6, .2, 1.2, .07))


def _next(c):
    c.solid(poly((-.8, -.6), (0, 0), (-.8, .6), close=True))
    c.solid(poly((-.05, -.6), (.65, 0), (-.05, .6), close=True))
    c.solid(rrect(.66, -.6, .16, 1.2, .06))


def _prev(c):
    c.solid(poly((.8, -.6), (0, 0), (.8, .6), close=True))
    c.solid(poly((.05, -.6), (-.65, 0), (.05, .6), close=True))
    c.solid(rrect(-.82, -.6, .16, 1.2, .06))


def _stop(c):
    c.solid(rrect(-.58, -.58, 1.16, 1.16, .18))


def _copy(c):
    c.both(rrect(-.3, -.3, 1.05, 1.1, .18))
    c.stroke(poly((-.3, .45), (-.75, .45), (-.75, -.82), (.45, -.82), (.45, -.3)))


def _paste(c):
    c.both(rrect(-.65, -.65, 1.3, 1.5, .18))
    c.solid(rrect(-.28, -.88, .56, .38, .1))
    c.stroke(poly((-.3, .05), (.3, .05)))
    c.stroke(poly((-.3, .4), (.3, .4)))


def _cut(c):
    c.stroke(circle(-.45, .5, .28))
    c.stroke(circle(.45, .5, .28))
    c.stroke(poly((-.25, .3), (.55, -.85)))
    c.stroke(poly((.25, .3), (-.55, -.85)))


def _undo(c):
    path = QPainterPath(QPointF(-.6, -.2))
    path.cubicTo(QPointF(-.2, -.65), QPointF(.75, -.6), QPointF(.75, .1))
    path.cubicTo(QPointF(.75, .5), QPointF(.4, .7), QPointF(0, .7))
    c.stroke(path)
    c.stroke(poly((-.62, -.72), (-.62, -.18), (-.1, -.2)))


def _redo(c):
    path = QPainterPath(QPointF(.6, -.2))
    path.cubicTo(QPointF(.2, -.65), QPointF(-.75, -.6), QPointF(-.75, .1))
    path.cubicTo(QPointF(-.75, .5), QPointF(-.4, .7), QPointF(0, .7))
    c.stroke(path)
    c.stroke(poly((.62, -.72), (.62, -.18), (.1, -.2)))


def _save(c):
    path = poly((-.8, -.8), (.45, -.8), (.8, -.45), (.8, .8), (-.8, .8), close=True)
    c.both(path)
    c.stroke(poly((-.45, -.8), (-.45, -.38), (.3, -.38), (.3, -.8)))
    c.stroke(rrect(-.45, .15, .9, .65, .08))


def _search(c):
    c.both(circle(-.15, -.15, .55))
    c.stroke(poly((.25, .25), (.8, .8)), c.width * 1.3)


def _star(c):
    pts = []
    for i in range(10):
        r = .88 if i % 2 == 0 else .38
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((math.cos(a) * r, math.sin(a) * r + .06))
    c.both(poly(*pts, close=True))


def _heart(c):
    path = QPainterPath(QPointF(0, .78))
    path.cubicTo(QPointF(-.95, .05), QPointF(-.75, -.85), QPointF(0, -.42))
    path.cubicTo(QPointF(.75, -.85), QPointF(.95, .05), QPointF(0, .78))
    c.both(path)


def _home(c):
    c.both(poly((-.72, -.05), (0, -.75), (.72, -.05), (.72, .8), (-.72, .8), close=True))
    c.stroke(poly((-.2, .8), (-.2, .3), (.2, .3), (.2, .8)))


def _mail(c):
    c.both(rrect(-.88, -.6, 1.76, 1.2, .18))
    c.stroke(poly((-.8, -.48), (0, .1), (.8, -.48)))


def _chat(c):
    path = QPainterPath()
    path.addRoundedRect(QRectF(-.85, -.75, 1.7, 1.25), .35, .35)
    c.fill(path)
    c.stroke(path)
    c.stroke(poly((-.4, .5), (-.55, .85), (-.05, .5)))
    for x in (-.4, 0, .4):
        c.solid(circle(x, -.12, .08))


def _bell(c):
    path = QPainterPath(QPointF(-.62, .45))
    path.lineTo(QPointF(-.55, -.1))
    path.cubicTo(QPointF(-.5, -.85), QPointF(.5, -.85), QPointF(.55, -.1))
    path.lineTo(QPointF(.62, .45))
    path.lineTo(QPointF(.8, .55))
    path.lineTo(QPointF(-.8, .55))
    path.closeSubpath()
    c.both(path)
    c.stroke(arc(0, .6, .2, 180, 180))


def _lock(c):
    c.both(rrect(-.65, -.1, 1.3, .95, .18))
    c.stroke(arc(0, -.15, .38, 0, 180))
    c.stroke(poly((-.38, -.15), (-.38, -.1)))
    c.stroke(poly((.38, -.15), (.38, -.1)))
    c.solid(circle(0, .35, .1))


def _power(c):
    c.stroke(arc(0, .05, .7, 125, 290))
    c.stroke(poly((0, -.85), (0, -.1)))


def _refresh(c):
    c.stroke(arc(0, 0, .68, 40, 280))
    c.solid(poly((.62, -.82), (.75, -.25), (.2, -.36), close=True))


def _plus(c):
    c.stroke(poly((-.65, 0), (.65, 0)), c.width * 1.2)
    c.stroke(poly((0, -.65), (0, .65)), c.width * 1.2)


def _close(c):
    c.stroke(poly((-.55, -.55), (.55, .55)), c.width * 1.2)
    c.stroke(poly((.55, -.55), (-.55, .55)), c.width * 1.2)


def _check(c):
    c.stroke(poly((-.65, 0), (-.18, .45), (.68, -.48)), c.width * 1.25)


def _arrow_left(c):
    c.stroke(poly((.75, 0), (-.7, 0)))
    c.stroke(poly((-.15, -.55), (-.7, 0), (-.15, .55)))


def _arrow_right(c):
    c.stroke(poly((-.75, 0), (.7, 0)))
    c.stroke(poly((.15, -.55), (.7, 0), (.15, .55)))


def _bookmark(c):
    c.both(poly((-.55, -.85), (.55, -.85), (.55, .85), (0, .42), (-.55, .85), close=True))


def _tab_new(c):
    c.both(poly((-.88, .7), (-.88, -.45), (-.65, -.7), (-.05, -.7), (.15, -.45), (.88, -.45), (.88, .7), close=True))
    c.stroke(poly((-.25, .15), (.35, .15)))
    c.stroke(poly((.05, -.15), (.05, .45)))


def _tab_close(c):
    c.both(poly((-.88, .7), (-.88, -.45), (-.65, -.7), (-.05, -.7), (.15, -.45), (.88, -.45), (.88, .7), close=True))
    c.stroke(poly((-.18, -.05), (.28, .4)))
    c.stroke(poly((.28, -.05), (-.18, .4)))


def _camera(c):
    c.both(poly((-.85, -.4), (-.4, -.4), (-.25, -.65), (.25, -.65), (.4, -.4), (.85, -.4),
                (.85, .7), (-.85, .7), close=True))
    c.stroke(circle(0, .12, .3))


def _screenshot(c):
    for sx in (-1, 1):
        for sy in (-1, 1):
            c.stroke(poly((sx * .85, sy * .4), (sx * .85, sy * .78), (sx * .45, sy * .78)))
    c.fill(rrect(-.45, -.35, .9, .7, .12))
    c.stroke(poly((-.2, -.1), (.2, .25)))
    c.stroke(poly((.2, -.1), (-.2, .25)))


def _coffee(c):
    c.both(poly((-.75, -.3), (.45, -.3), (.38, .65), (-.68, .65), close=True))
    c.stroke(arc(.45, .05, .25, -90, 180))
    c.stroke(poly((-.35, -.85), (-.35, -.55)))
    c.stroke(poly((.05, -.85), (.05, -.55)))


def _game(c):
    path = QPainterPath()
    path.addRoundedRect(QRectF(-.9, -.45, 1.8, 1.0), .5, .5)
    c.both(path)
    c.stroke(poly((-.6, .05), (-.25, .05)))
    c.stroke(poly((-.42, -.13), (-.42, .23)))
    c.solid(circle(.35, -.05, .08))
    c.solid(circle(.58, .15, .08))


def _chart(c):
    c.stroke(poly((-.85, -.85), (-.85, .8), (.85, .8)))
    c.fill(rrect(-.55, .0, .3, .65, .06))
    c.stroke(rrect(-.55, .0, .3, .65, .06))
    c.fill(rrect(-.1, -.45, .3, 1.1, .06))
    c.stroke(rrect(-.1, -.45, .3, 1.1, .06))
    c.fill(rrect(.35, -.2, .3, .85, .06))
    c.stroke(rrect(.35, -.2, .3, .85, .06))


def _brush(c):
    c.stroke(poly((.8, -.8), (-.05, .2)), c.width * 1.3)
    path = QPainterPath(QPointF(-.1, .1))
    path.cubicTo(QPointF(-.5, .1), QPointF(-.45, .55), QPointF(-.85, .8))
    path.cubicTo(QPointF(-.35, .88), QPointF(.15, .65), QPointF(.05, .28))
    path.closeSubpath()
    c.both(path)


def _bulb(c):
    path = QPainterPath(QPointF(-.28, .35))
    path.cubicTo(QPointF(-.3, .05), QPointF(-.65, -.1), QPointF(-.65, -.38))
    path.cubicTo(QPointF(-.65, -.75), QPointF(-.35, -.9), QPointF(0, -.9))
    path.cubicTo(QPointF(.35, -.9), QPointF(.65, -.75), QPointF(.65, -.38))
    path.cubicTo(QPointF(.65, -.1), QPointF(.3, .05), QPointF(.28, .35))
    path.closeSubpath()
    c.both(path)
    c.stroke(poly((-.25, .58), (.25, .58)))
    c.stroke(poly((-.15, .8), (.15, .8)))


def _calendar(c):
    c.both(rrect(-.8, -.62, 1.6, 1.45, .18))
    c.stroke(poly((-.8, -.22), (.8, -.22)))
    c.stroke(poly((-.4, -.85), (-.4, -.45)))
    c.stroke(poly((.4, -.85), (.4, -.45)))
    for x in (-.4, 0, .4):
        c.solid(circle(x, .2, .07))
        c.solid(circle(x, .5, .07))


def _clock(c):
    c.both(circle(0, 0, .82))
    c.stroke(poly((0, -.45), (0, 0), (.35, .2)))


def _cloud(c):
    path = QPainterPath(QPointF(-.55, .55))
    path.cubicTo(QPointF(-1.0, .55), QPointF(-1.0, -.05), QPointF(-.55, -.05))
    path.cubicTo(QPointF(-.5, -.55), QPointF(.2, -.75), QPointF(.4, -.2))
    path.cubicTo(QPointF(.95, -.25), QPointF(1.0, .55), QPointF(.55, .55))
    path.closeSubpath()
    c.both(path)


def _download(c):
    c.stroke(poly((0, -.85), (0, .3)))
    c.stroke(poly((-.42, -.1), (0, .32), (.42, -.1)))
    c.stroke(poly((-.8, .45), (-.8, .8), (.8, .8), (.8, .45)))


def _upload(c):
    c.stroke(poly((0, .35), (0, -.82)))
    c.stroke(poly((-.42, -.4), (0, -.82), (.42, -.4)))
    c.stroke(poly((-.8, .45), (-.8, .8), (.8, .8), (.8, .45)))


def _link(c):
    c.stroke(rrect(-.92, -.3, 1.0, .6, .3))
    c.stroke(rrect(-.08, -.3, 1.0, .6, .3))
    c.fill(rrect(-.92, -.3, 1.84, .6, .3))


def _user(c):
    c.both(circle(0, -.38, .38))
    path = QPainterPath(QPointF(-.78, .85))
    path.cubicTo(QPointF(-.78, .2), QPointF(.78, .2), QPointF(.78, .85))
    path.closeSubpath()
    c.both(path)


def _trash(c):
    c.stroke(poly((-.8, -.55), (.8, -.55)))
    c.stroke(poly((-.25, -.55), (-.18, -.82), (.18, -.82), (.25, -.55)))
    c.both(poly((-.6, -.4), (-.5, .82), (.5, .82), (.6, -.4), close=True))
    c.stroke(poly((-.15, -.15), (-.12, .55)))
    c.stroke(poly((.15, -.15), (.12, .55)))


def _edit(c):
    c.both(poly((-.75, .75), (-.68, .32), (.38, -.74), (.75, -.37), (-.3, .68), close=True))
    c.stroke(poly((.15, -.5), (.5, -.15)))


def _sun(c):
    c.both(circle(0, 0, .38))
    for i in range(8):
        a = i * math.pi / 4
        c.stroke(poly((math.cos(a) * .6, math.sin(a) * .6), (math.cos(a) * .85, math.sin(a) * .85)))


def _moon(c):
    path = QPainterPath()
    path.addEllipse(QPointF(0, 0), .78, .78)
    cut = QPainterPath()
    cut.addEllipse(QPointF(.42, -.3), .6, .6)
    c.both(path.subtracted(cut))


def _pin(c):
    c.both(poly((-.38, -.85), (.38, -.85), (.28, -.2), (.6, .15), (-.6, .15), (-.28, -.2), close=True))
    c.stroke(poly((0, .15), (0, .9)))


def _grid(c):
    for x in (-.82, .12):
        for y in (-.82, .12):
            c.both(rrect(x, y, .7, .7, .18))


def _fire(c):
    path = QPainterPath(QPointF(0, .88))
    path.cubicTo(QPointF(-.75, .85), QPointF(-.8, .1), QPointF(-.35, -.3))
    path.cubicTo(QPointF(-.3, .0), QPointF(-.15, .05), QPointF(-.1, .05))
    path.cubicTo(QPointF(-.25, -.45), QPointF(.05, -.8), QPointF(.15, -.9))
    path.cubicTo(QPointF(.2, -.45), QPointF(.75, -.25), QPointF(.7, .3))
    path.cubicTo(QPointF(.68, .7), QPointF(.35, .88), QPointF(0, .88))
    c.both(path)


def _target(c):
    c.fill(circle(0, 0, .82))
    c.stroke(circle(0, 0, .82))
    c.stroke(circle(0, 0, .5))
    c.solid(circle(0, 0, .17))


def _shield(c):
    path = QPainterPath(QPointF(0, -.88))
    path.lineTo(QPointF(.72, -.6))
    path.cubicTo(QPointF(.72, .15), QPointF(.45, .62), QPointF(0, .88))
    path.cubicTo(QPointF(-.45, .62), QPointF(-.72, .15), QPointF(-.72, -.6))
    path.closeSubpath()
    c.both(path)
    c.stroke(poly((-.28, .02), (-.05, .25), (.32, -.18)))


def _magic(c):
    c.stroke(poly((-.8, .8), (.3, -.3)), c.width * 1.3)
    for x, y, s in ((.55, -.6, .22), (.1, -.75, .12), (.72, -.1, .12)):
        c.stroke(poly((x - s, y), (x + s, y)))
        c.stroke(poly((x, y - s), (x, y + s)))


def _timer(c):
    c.both(circle(0, .12, .72))
    c.stroke(poly((-.22, -.88), (.22, -.88)))
    c.stroke(poly((0, -.88), (0, -.6)))
    c.stroke(poly((.58, -.58), (.72, -.72)))
    c.stroke(poly((0, .12), (0, -.3)))
    c.stroke(poly((0, .12), (.28, .3)))


def _hourglass(c):
    c.stroke(poly((-.55, -.85), (.55, -.85)))
    c.stroke(poly((-.55, .85), (.55, .85)))
    c.both(poly((-.45, -.85), (.45, -.85), (.08, 0), (.45, .85), (-.45, .85), (-.08, 0), close=True))


def _app(c):
    c.both(rrect(-.75, -.75, 1.5, 1.5, .4))
    c.solid(circle(0, 0, .2))


# 이름 → (화면 이름, 같은 뜻 이모지, 그리기 함수, 분류)
REGISTRY: Dict[str, Tuple[str, str, Callable, str]] = {}


def _reg(cat, items):
    for name, label, emoji, fn in items:
        REGISTRY[name] = (label, emoji, fn, cat)


_reg("자주 쓰는", [
    ("globe", "웹", "🌐", _globe), ("folder", "폴더", "📁", _folder), ("file", "파일", "📄", _file),
    ("note", "메모", "📝", _note), ("rocket", "실행", "🚀", _rocket), ("bolt", "번개", "⚡", _bolt),
    ("window", "창", "🪟", _window), ("app", "앱", "📱", _app), ("grid", "묶음", "🗂️", _grid),
    ("search", "검색", "🔍", _search), ("gear", "설정", "⚙️", _gear), ("home", "홈", "🏠", _home),
])
_reg("편집", [
    ("copy", "복사", "📋", _copy), ("paste", "붙여넣기", "📥", _paste), ("cut", "자르기", "✂️", _cut),
    ("undo", "되돌리기", "↩️", _undo), ("redo", "다시 실행", "↪️", _redo), ("save", "저장", "💾", _save),
    ("edit", "편집", "✏️", _edit), ("trash", "삭제", "🗑️", _trash), ("screenshot", "화면 캡처", "📸", _screenshot),
    ("keyboard", "키보드", "⌨️", _keyboard), ("refresh", "새로고침", "🔄", _refresh), ("link", "링크", "🔗", _link),
])
_reg("미디어", [
    ("volume_up", "볼륨 +", "🔊", _volume_up), ("volume_down", "볼륨 -", "🔉", _volume_down),
    ("volume_mute", "음소거", "🔇", _volume_mute), ("play_pause", "재생/정지", "⏯️", _play_pause),
    ("play", "재생", "▶️", _play), ("pause", "일시정지", "⏸️", _pause), ("next", "다음", "⏭️", _next),
    ("prev", "이전", "⏮️", _prev), ("stop", "정지", "⏹️", _stop), ("mic", "마이크", "🎤", _mic),
    ("mic_off", "마이크 끔", "🎙️", _mic_off), ("music", "음악", "🎵", _music), ("video", "영상", "🎬", _video),
    ("camera", "카메라", "📷", _camera), ("image", "그림", "🖼️", _image),
])
_reg("브라우저 · 화살표", [
    ("arrow_left", "뒤로", "◀️", _arrow_left), ("arrow_right", "앞으로", "▶️", _arrow_right),
    ("tab_new", "새 탭", "➕", _tab_new), ("tab_close", "탭 닫기", "✖️", _tab_close),
    ("bookmark", "북마크", "🔖", _bookmark), ("star", "별", "⭐", _star), ("plus", "더하기", "➕", _plus),
    ("close", "닫기", "❌", _close), ("check", "확인", "✅", _check), ("download", "다운로드", "⬇️", _download),
    ("upload", "업로드", "⬆️", _upload),
])
_reg("작업 · 생활", [
    ("code", "코드", "💻", _code), ("terminal", "터미널", "🖥️", _terminal), ("monitor", "모니터", "🖥️", _monitor),
    ("palette", "팔레트", "🎨", _palette), ("brush", "붓", "🖌️", _brush), ("chart", "차트", "📊", _chart),
    ("mail", "메일", "✉️", _mail), ("chat", "채팅", "💬", _chat), ("bell", "알림", "🔔", _bell),
    ("calendar", "달력", "📅", _calendar), ("clock", "시계", "🕒", _clock),
    ("timer", "타이머", "⏱️", _timer), ("hourglass", "모래시계", "⏳", _hourglass), ("cloud", "클라우드", "☁️", _cloud),
    ("user", "사람", "👤", _user), ("lock", "잠금", "🔒", _lock), ("power", "전원", "🔌", _power),
    ("game", "게임", "🎮", _game), ("coffee", "커피", "☕", _coffee), ("bulb", "아이디어", "💡", _bulb),
    ("heart", "하트", "❤️", _heart), ("fire", "불꽃", "🔥", _fire), ("target", "목표", "🎯", _target),
    ("shield", "보안", "🛡️", _shield), ("magic", "마법", "🪄", _magic), ("pin", "고정", "📌", _pin),
    ("sun", "해", "☀️", _sun), ("moon", "달", "🌙", _moon),
])

CATEGORIES = []
for _n, (_l, _e, _f, _c) in REGISTRY.items():
    if _c not in CATEGORIES:
        CATEGORIES.append(_c)

# 이모지 → 테마 아이콘 (기존 버튼 변환용)
EMOJI_TO_ICON: Dict[str, str] = {}
for _n, (_l, _e, _f, _c) in REGISTRY.items():
    EMOJI_TO_ICON.setdefault(_e, _n)
    EMOJI_TO_ICON.setdefault(_e.replace("️", ""), _n)
EMOJI_TO_ICON.update({
    "▶️": "arrow_right", "▶": "arrow_right", "➕": "tab_new", "✖️": "tab_close", "✖": "tab_close",
    "📑": "file", "📌": "pin", "📋": "copy", "🖥️": "monitor", "⚙": "gear", "🎙️": "mic",
    "💻": "code", "🪄": "magic", "📸": "screenshot", "📷": "camera", "🗂️": "grid", "🗂": "grid",
})

# 동작별 기본 아이콘
ACTION_DEFAULT_ICONS = {
    "url": "globe", "program": "rocket", "file": "file", "folder": "folder", "shortcut": "keyboard",
    "media": "volume_up", "macro": "bolt", "group": "grid", "info": "clock", "timer": "timer",
}
MEDIA_DEFAULT_ICONS = {
    "VolumeUp": "volume_up", "VolumeDown": "volume_down", "VolumeMute": "volume_mute",
    "MediaPlayPause": "play_pause", "MediaNext": "next", "MediaPrev": "prev", "MediaStop": "stop",
    "MicMute": "mic_off",
}


def default_icon_for(action_type: str, action_data: str = "") -> str:
    if action_type == "info":
        from core.system_info import INFO_KINDS
        return PREFIX + INFO_KINDS.get(action_data, ("", "clock"))[1]
    if action_type == "media":
        return PREFIX + MEDIA_DEFAULT_ICONS.get(action_data, "volume_up")
    return PREFIX + ACTION_DEFAULT_ICONS.get(action_type, "bolt")


def emoji_for(icon: str) -> str:
    entry = REGISTRY.get(icon_name(icon))
    return entry[1] if entry else ""


def paint_icon(p: QPainter, icon: str, rect: QRectF, color: QColor, style: str = "line",
               accent: Optional[QColor] = None) -> bool:
    """테마 아이콘을 rect 안에 그립니다. 이모지 스타일이면 False를 돌려줘 이모지로 그리게 합니다."""
    entry = REGISTRY.get(icon_name(icon))
    if entry is None or style == "emoji":
        return False
    s = min(rect.width(), rect.height()) / 2
    p.save()
    p.setRenderHint(QPainter.Antialiasing)
    p.translate(rect.center())
    p.scale(s, s)
    ctx = Ctx(p, color, style, accent or color)
    if s < 9:  # 아주 작을 때는 선을 조금 두껍게
        ctx.width = 0.16
    entry[2](ctx)
    p.restore()
    return True
