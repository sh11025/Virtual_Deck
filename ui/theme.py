"""
테마(색 정리) 모듈
밝은/어두운 테마의 색과 유리 색(투명, 주황, 파랑 …)을 한곳에서 관리합니다.
색을 바꾸고 싶으면 이 파일만 고치면 됩니다.
"""

import os
from dataclasses import dataclass

from PySide6.QtGui import QColor, QFontDatabase, QFont

from core import paths


@dataclass
class Palette:
    name: str
    dark: bool
    text: str
    text_dim: str
    text_faint: str
    accent: str          # 강조색(하늘색)
    accent_deep: str
    input_bg: str
    input_bg_focus: str
    input_border: str
    input_border_low: str
    popup_bg: str
    popup_border: str
    hover_bg: str
    select_bg: str
    select_text: str
    veil: QColor         # 뒤 비침 배경 위에 덮는 얇은 막
    base: QColor         # 기본 배경색


LIGHT = Palette(
    name="light", dark=False,
    text="#0f172a", text_dim="#475569", text_faint="#94a3b8",
    accent="#0ea5e9", accent_deep="#0369a1",
    input_bg="rgba(255,255,255,150)", input_bg_focus="rgba(255,255,255,230)",
    input_border="rgba(255,255,255,240)", input_border_low="rgba(148,168,200,120)",
    popup_bg="rgba(250,252,255,248)", popup_border="rgba(190,205,228,200)",
    hover_bg="rgba(14,165,233,28)", select_bg="rgba(14,165,233,45)", select_text="#0369a1",
    veil=QColor(255, 255, 255, 92), base=QColor(236, 241, 248),
)

DARK = Palette(
    name="dark", dark=True,
    text="#f1f5f9", text_dim="#a5b4c8", text_faint="#64748b",
    accent="#38bdf8", accent_deep="#7dd3fc",
    input_bg="rgba(255,255,255,22)", input_bg_focus="rgba(255,255,255,40)",
    input_border="rgba(255,255,255,55)", input_border_low="rgba(255,255,255,25)",
    popup_bg="rgba(24,30,44,250)", popup_border="rgba(255,255,255,40)",
    hover_bg="rgba(56,189,248,38)", select_bg="rgba(56,189,248,60)", select_text="#bae6fd",
    veil=QColor(10, 14, 26, 120), base=QColor(16, 20, 32),
)

# 유리 색: 이름 → (화면 이름, 위쪽 밝은 색, 아래쪽 진한 색, 글자색)
TINTS = {
    "clear": ("투명", None, None, None),
    "orange": ("주황", "#ffb07a", "#f0501c", "#ffffff"),
    "blue": ("파랑", "#86cbff", "#1f5fe0", "#ffffff"),
    "mint": ("민트", "#8df0c6", "#11b383", "#ffffff"),
    "purple": ("보라", "#cdb0ff", "#7a4cf5", "#ffffff"),
    "pink": ("분홍", "#ffb6d3", "#e8458f", "#ffffff"),
    "red": ("빨강", "#ffa3a3", "#e23a3d", "#ffffff"),
    "yellow": ("노랑", "#ffe88f", "#f2ae00", "#3b2a00"),
    # 색 유리 스타일용 틴트
    "sky": ("하늘", "#6cb8ff", "#257fe6", "#ffffff"),
    "sunset": ("노을", "#ffa085", "#f25542", "#ffffff"),
    "forest": ("숲", "#6ee7b7", "#10b981", "#ffffff"),
}

# 덱 배경 '색 유리' 스타일 전용 색(버튼 유리색 선택지에는 나오지 않음)
GLASS_TINT_COLORS = {
    "sky": "#3894f0",
    "sunset": "#ff6f61",
    "forest": "#2e9a58",
}

# 버튼 편집창의 '유리 색' 칩에 보여 줄 색 이름(배경 전용 sky/sunset/forest 제외)
BUTTON_TINT_KEYS = ("clear", "orange", "blue", "mint", "purple", "pink", "red", "yellow")

# 켜짐(토글 ON) 표시 색: 민트 틴트의 아래쪽 진한 색
TOGGLE_ON_COLOR = TINTS["mint"][2]


def glass_tint_hex(name: str, default: str = "#3894f0") -> str:
    """배경 유리 스타일 이름에 해당하는 대표 색(#rrggbb)을 돌려줍니다."""
    if name in GLASS_TINT_COLORS:
        return GLASS_TINT_COLORS[name]
    data = TINTS.get(name)
    return data[1] if data and data[1] else default

# 아이콘 색: 이름 → (화면 이름, 색). 'auto' 는 버튼 색에 맞춰 자동
ICON_COLORS = {
    "auto": ("자동", None),
    "white": ("흰색", "#ffffff"),
    "ink": ("진한 색", "#1e293b"),
    "blue": ("하늘", "#2f86f6"),
    "mint": ("민트", "#0fb882"),
    "orange": ("주황", "#f56a1f"),
    "pink": ("분홍", "#ec4899"),
    "yellow": ("노랑", "#f2ae00"),
    "purple": ("보라", "#7c4dff"),
}

_current = LIGHT


def set_theme(name: str) -> None:
    global _current
    _current = DARK if name == "dark" else LIGHT


def T() -> Palette:
    """현재 테마 색"""
    return _current


def tint_colors(tint: str):
    """(위 색, 아래 색, 글자색) — 투명이면 None"""
    data = TINTS.get(tint or "clear")
    if not data or data[1] is None:
        return None
    return QColor(data[1]), QColor(data[2]), QColor(data[3])


# ------------------------------------------------------------------ 글꼴
UI_FONT = "Pretendard"
EMOJI_FONTS = ["Segoe UI Emoji", "Apple Color Emoji", "Noto Color Emoji"]


def load_fonts() -> str:
    """프로그램에 포함된 Pretendard 글꼴을 등록합니다. 없으면 시스템 글꼴 사용."""
    global UI_FONT
    folder = paths.fonts_dir()
    loaded = False
    if os.path.isdir(folder):
        for name in sorted(os.listdir(folder)):
            if name.lower().endswith((".otf", ".ttf")):
                if QFontDatabase.addApplicationFont(os.path.join(folder, name)) >= 0:
                    loaded = True
    if not loaded:
        UI_FONT = "Malgun Gothic" if os.name == "nt" else "Sans Serif"
    return UI_FONT


def ui_font(size: float = 13, weight=QFont.Medium) -> QFont:
    f = QFont(UI_FONT)
    f.setPixelSize(max(1, int(round(size))))
    f.setWeight(weight)
    f.setHintingPreference(QFont.PreferNoHinting)
    return f


def emoji_font(size: float) -> QFont:
    f = QFont()
    f.setFamilies(EMOJI_FONTS + [UI_FONT])
    f.setPixelSize(max(1, int(round(size))))
    return f


# ------------------------------------------------------------------ 표준 위젯 스타일
def _arrow_files(color: str):
    """콤보상자/숫자칸의 화살표 그림을 임시 폴더에 만들어 둡니다."""
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QImage, QPainter
    from ui.glass import draw_icon
    folder = paths.cache_dir()   # 임시 폴더 대신 데이터 폴더 안에 (삭제할 때 같이 지워짐)
    out = []
    for name, flip in (("down", False), ("up", True)):
        path = os.path.join(folder, f"arrow_{name}_{color.strip('#')}.png").replace("\\", "/")
        if not os.path.exists(path):
            img = QImage(24, 24, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            p = QPainter(img)
            if flip:
                p.translate(0, 24)
                p.scale(1, -1)
            draw_icon(p, "chevron", QRectF(4, 4, 16, 16), QColor(color), width=2.6)
            p.end()
            img.save(path)
        out.append(path)
    return out


def get_qss() -> str:
    """입력창, 목록, 메뉴, 툴팁 등 기본 위젯의 유리 스타일 (버튼은 코드로 직접 그림)"""
    t = _current
    arrow_down, arrow_up = _arrow_files(t.text_dim)
    return f"""
    QWidget {{
        color: {t.text};
        font-family: '{UI_FONT}', 'Malgun Gothic', 'Segoe UI';
        font-size: 15px;
    }}
    QLabel {{ background: transparent; }}
    QLabel[role="section"] {{ font-size: 17px; font-weight: 700; color: {t.text}; padding-top: 4px; }}
    QLabel[role="hint"] {{ font-size: 13px; color: {t.text_dim}; }}
    QLabel[role="title"] {{ font-size: 20px; font-weight: 700; }}
    QLabel[role="value"] {{ font-size: 13px; font-weight: 600; color: {t.text_dim}; min-width: 44px; }}

    QLineEdit, QComboBox, QSpinBox, QPlainTextEdit {{
        background: {t.input_bg};
        border: 1px solid {t.input_border};
        border-bottom: 1px solid {t.input_border_low};
        border-radius: 12px;
        padding: 7px 12px;
        selection-background-color: {t.accent};
        selection-color: #ffffff;
        font-weight: 500;
    }}
    QLineEdit:hover, QComboBox:hover, QSpinBox:hover, QPlainTextEdit:hover {{
        border: 1px solid {t.accent};
    }}
    QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{
        background: {t.input_bg_focus};
        border: 1.5px solid {t.accent};
    }}
    QLineEdit[capturing="true"] {{
        border: 1.5px solid {t.accent};
        background: {t.select_bg};
    }}
    QComboBox::drop-down {{ border: none; width: 26px; }}
    QComboBox::down-arrow {{ image: url("{arrow_down}"); width: 14px; height: 14px; margin-right: 9px; }}
    QComboBox QAbstractItemView {{
        background: {t.popup_bg};
        border: 1px solid {t.popup_border};
        border-radius: 10px;
        padding: 4px;
        outline: none;
        selection-background-color: {t.select_bg};
        selection-color: {t.select_text};
    }}
    QComboBox QAbstractItemView::item {{ min-height: 28px; padding: 0 8px; border-radius: 6px; }}

    QSpinBox::up-button, QSpinBox::down-button {{
        subcontrol-origin: border; width: 20px; border: none; background: transparent;
    }}
    QSpinBox::up-button {{ subcontrol-position: top right; margin: 3px 4px 0 0; }}
    QSpinBox::down-button {{ subcontrol-position: bottom right; margin: 0 4px 3px 0; }}
    QSpinBox::up-arrow {{ image: url("{arrow_up}"); width: 10px; height: 10px; }}
    QSpinBox::down-arrow {{ image: url("{arrow_down}"); width: 10px; height: 10px; }}

    QListWidget {{
        background: {t.input_bg};
        border: 1px solid {t.input_border};
        border-bottom: 1px solid {t.input_border_low};
        border-radius: 14px;
        padding: 6px;
        outline: none;
    }}
    QListWidget::item {{ border-radius: 9px; padding: 7px 10px; margin: 1px 0; }}
    QListWidget::item:hover {{ background: {t.hover_bg}; }}
    QListWidget::item:selected {{ background: {t.select_bg}; color: {t.select_text}; font-weight: 700; }}

    QScrollArea, QScrollArea > QWidget > QWidget, QStackedWidget {{ background: transparent; border: none; }}
    QScrollBar:vertical {{ background: transparent; width: 8px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: rgba(140,160,190,110); border-radius: 3px; min-height: 24px; }}
    QScrollBar::handle:vertical:hover {{ background: rgba(120,145,180,170); }}
    QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QScrollBar:horizontal {{ height: 0; }}

    QSlider {{ min-height: 24px; }}
    QSlider::groove:horizontal {{
        height: 6px; border-radius: 3px;
        background: {"rgba(255,255,255,30)" if t.dark else "rgba(120,140,175,55)"};
    }}
    QSlider::sub-page:horizontal {{
        border-radius: 3px;
        background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #7dd3fc, stop:1 {t.accent});
    }}
    QSlider::handle:horizontal {{
        width: 18px; height: 18px; margin: -7px 0; border-radius: 9px;
        background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #ffffff, stop:0.55 #f4f8fc, stop:1 #dfe8f3);
        border: 1px solid rgba(140,165,200,170);
    }}
    QSlider::handle:horizontal:hover {{ border: 1px solid {t.accent}; }}

    QToolTip {{
        background: {t.popup_bg};
        color: {t.text};
        border: 1px solid {t.popup_border};
        border-radius: 8px;
        padding: 6px 9px;
        font-size: 12px;
    }}

    QMenu {{
        background: {t.popup_bg};
        border: 1px solid {t.popup_border};
        border-radius: 12px;
        padding: 6px;
    }}
    QMenu::item {{ padding: 7px 26px 7px 10px; border-radius: 8px; margin: 1px 0; }}
    QMenu::item:selected {{ background: {t.select_bg}; color: {t.select_text}; }}
    QMenu::item:disabled {{ color: {t.text_faint}; }}
    QMenu::icon {{ padding-left: 8px; }}
    QMenu::separator {{ height: 1px; margin: 5px 8px; background: {t.popup_border}; }}
    QMenu::indicator {{ width: 0; }}
    """
