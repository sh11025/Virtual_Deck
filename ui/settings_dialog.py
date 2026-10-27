"""
환경설정 창
'꾸미기 / 크기 / 편리한 기능 / 더보기' 4개 탭으로 구성되어 있으며,
바꾸는 즉시 버튼판에 미리 반영됩니다. (취소하면 원래대로 돌아감)
"""

import os
from typing import Dict

from PySide6.QtCore import Qt, Signal, QRectF, QRect, QSize
from PySide6.QtGui import QPainter, QColor, QFont, QPixmap, QPen
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSpinBox, QSlider, QStackedWidget, QComboBox,
    QFileDialog, QColorDialog, QAbstractButton, QGridLayout, QScrollArea, QFrame, QListWidget,
    QListWidgetItem, QSizePolicy,
)

from models.config_model import AppConfig, SIZE_PRESETS
from services.storage_service import BUILTIN_THEMES, StorageService
from ui import theme
from ui.theme import T
from ui.glass import paint_glass, rounded_path, make_aurora, with_alpha
from ui.widgets import (
    GlassDialog, GlassButton, GlassToggle, SegmentedTabs, KeyCaptureEdit, section_label, hint_label,
    no_wheel,
)


class ColorSwatch(QAbstractButton):
    """색을 보여 주고, 누르면 색 고르기 창을 여는 버튼"""

    colorChanged = Signal(str)

    def __init__(self, color: str, parent=None):
        super().__init__(parent)
        self.color = color
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(64, 38)
        self.clicked.connect(self._pick)

    def set_color(self, c: str):
        self.color = c
        self.update()

    def _pick(self):
        c = QColorDialog.getColor(QColor(self.color), self.window(), "색 고르기")
        if c.isValid():
            self.color = c.name()
            self.update()
            self.colorChanged.emit(self.color)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(3, 2, self.width() - 6, self.height() - 7)
        p.fillPath(rounded_path(r, 11), QColor(self.color))
        paint_glass(p, r, 11, fill=0.05, shadow_strength=0.7, rainbow=0.5)


def toggle_row(title: str, hint: str, toggle: GlassToggle) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(12)
    v = QVBoxLayout()
    v.setSpacing(1)
    lab = QLabel(title)
    lab.setStyleSheet("font-weight: 600; font-size: 15px;")
    v.addWidget(lab)
    if hint:
        v.addWidget(hint_label(hint))
    h.addLayout(v, 1)
    h.addWidget(toggle, 0, Qt.AlignVCenter)
    return h


def slider_row(title: str, slider: QSlider, value_label: QLabel) -> QHBoxLayout:
    h = QHBoxLayout()
    h.setSpacing(10)
    lab = QLabel(title)
    lab.setMinimumWidth(120)
    lab.setStyleSheet("font-size: 15px; font-weight: 500;")
    h.addWidget(lab)
    h.addWidget(slider, 1)
    value_label.setProperty("role", "value")
    value_label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
    h.addWidget(value_label)
    return h


def make_slider(lo, hi, val) -> QSlider:
    s = no_wheel(QSlider(Qt.Horizontal))
    s.setRange(lo, hi)
    s.setValue(val)
    return s


def page() -> (QWidget, QVBoxLayout):
    """스크롤 영역 안의 기본 페이지 생성 도우미"""
    scroll = QScrollArea()
    scroll.setWidgetResizable(True)
    scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    scroll.setFrameShape(QFrame.NoFrame)
    content = QWidget()
    content.setAttribute(Qt.WA_TranslucentBackground, True)
    content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
    v = QVBoxLayout(content)
    v.setContentsMargins(4, 6, 8, 12)
    v.setSpacing(14)
    scroll.setWidget(content)
    return scroll, v


# ------------------------------------------------------------------ 스타일 카드 썸네일 캐시 및 위젯
_STYLE_THUMB_CACHE: Dict[str, QPixmap] = {}


def get_style_thumbnail(name: str, theme_dict: dict) -> QPixmap:
    """make_aurora 샘플 배경 위에 실제 스타일 느낌을 그린 썸네일 (캐시 적용)"""
    if name in _STYLE_THUMB_CACHE:
        return _STYLE_THUMB_CACHE[name]

    w, h = 136, 62
    pix = QPixmap(w, h)
    pix.fill(Qt.transparent)
    p = QPainter(pix)
    p.setRenderHint(QPainter.Antialiasing)

    bg_t = theme_dict.get("bg_type", "glass")
    dark = theme_dict.get("theme") == "dark"
    tint = theme_dict.get("glass_tint", "")

    r = QRectF(0, 0, w, h)
    clip_path = rounded_path(r, 8)
    p.setClipPath(clip_path)

    if bg_t == "clear":
        p.fillRect(r, QColor(25, 30, 42, 190) if dark else QColor(228, 232, 240, 190))
    elif bg_t == "glass":
        p.drawPixmap(0, 0, make_aurora(QSize(w, h), dark, seed=2))
        frost = theme_dict.get("glass_frost", 20)
        p.fillRect(r, QColor(10, 14, 26, int(40 + frost * 1.5)) if dark else QColor(255, 255, 255, int(20 + frost * 1.8)))
        if tint:
            p.fillRect(r, with_alpha(QColor(theme.glass_tint_hex(tint)), 60))
    else:
        p.fillRect(r, QColor(40, 45, 60) if dark else QColor(240, 242, 248))

    # 미니 버튼 3개 배치
    bw, bh = 30, 30
    gap = 8
    start_x = (w - (3 * bw + 2 * gap)) / 2
    by = (h - bh) / 2
    for i in range(3):
        bx = start_x + i * (bw + gap)
        br = QRectF(bx, by, bw, bh)
        b_path = rounded_path(br, 6)
        if bg_t == "clear":
            p.fillPath(b_path, QColor(255, 255, 255, 160) if not dark else QColor(255, 255, 255, 60))
            p.setPen(QPen(QColor(255, 255, 255, 120), 1))
            p.drawPath(b_path)
        else:
            p.fillPath(b_path, QColor(255, 255, 255, 180) if not dark else QColor(255, 255, 255, 45))
            p.setPen(QPen(QColor(255, 255, 255, 140) if not dark else QColor(255, 255, 255, 30), 1))
            p.drawPath(b_path)

    p.end()
    _STYLE_THUMB_CACHE[name] = pix
    return pix


class StyleCard(QAbstractButton):
    """스타일 미리보기 카드 (작은 버튼판 그림 + 이름)"""

    def __init__(self, name: str, theme_dict: dict, parent=None):
        super().__init__(parent)
        self.name = name
        self.theme_dict = theme_dict
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(150, 102)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        checked = self.isChecked()

        path = rounded_path(r, 12)
        if checked:
            p.fillPath(path, QColor(255, 140, 0, 35))
            p.setPen(QPen(QColor("#ff8533"), 2))
        else:
            p.fillPath(path, QColor(255, 255, 255, 18) if T().dark else QColor(0, 0, 0, 12))
            p.setPen(QPen(QColor(255, 255, 255, 40) if T().dark else QColor(0, 0, 0, 22), 1))
        p.drawPath(path)

        pix = get_style_thumbnail(self.name, self.theme_dict)
        thumb_r = QRect(int((self.width() - 136) / 2), 6, 136, 62)
        p.drawPixmap(thumb_r, pix)

        p.setPen(QColor("#ff9944") if checked else QColor(T().text))
        p.setFont(theme.ui_font(13, QFont.Bold if checked else QFont.Medium))
        text_r = QRect(4, 72, self.width() - 8, 24)
        p.drawText(text_r, Qt.AlignCenter, self.name)


# ------------------------------------------------------------------ 환경설정 창 메인
class SettingsDialog(GlassDialog):
    preview = Signal(object)      # 바뀐 설정(AppConfig) 미리보기
    convert_icons = Signal()      # 이모지 아이콘 → 테마 아이콘 바꾸기 요청

    SIZE_KEYS = list(SIZE_PRESETS.keys())
    SIZE_DESC = {"SS": "아주 작게", "S": "작게", "M": "보통", "L": "크게", "EX": "아주 크게"}
    SPACING_MAP = [4, 8, 14]      # 좁게 / 보통 / 넓게

    def __init__(self, config: AppConfig, storage=None, parent=None, modeless: bool = True):
        super().__init__("환경설정", "바꾸면 버튼판에 바로 보여요", parent=parent, width=820, modeless=modeless)
        self.config = config
        self.storage = storage or StorageService()
        self.restore_path = None
        self._loading = True
        self.style_cards: Dict[str, StyleCard] = {}

        self.tabs = SegmentedTabs(["꾸미기", "크기", "편리한 기능", "더보기"])
        self.body.addWidget(self.tabs)
        self.stack = QStackedWidget()
        self.body.addWidget(self.stack, 1)
        self.tabs.currentChanged.connect(self.stack.setCurrentIndex)

        self._build_decorate_tab()
        self._build_size_tab()
        self._build_features_tab()
        self._build_more_tab()

        self.footer.addStretch(1)
        cancel = GlassButton("취소")
        cancel.clicked.connect(self.reject)
        self.footer.addWidget(cancel)
        ok = GlassButton("저장", tint="orange", icon_name="check")
        ok.clicked.connect(self.accept)
        self.footer.addWidget(ok)

        self._sync_controls()
        self._loading = False
        avail = (parent.screen() if parent else QApplication.primaryScreen()).availableGeometry()
        dialog_w = min(820, int(avail.width() * 0.90))
        dialog_h = min(int(avail.height() * 0.85), 680)
        self.resize(dialog_w, dialog_h)

    def _changed(self, *_):
        if self._loading:
            return
        self.preview.emit(self.config.copy())

    # ================================================================ 1. 꾸미기 탭
    def _build_decorate_tab(self):
        page_widget, v = page()
        c = self.config

        # 1. 스타일 카드 그리드 (한 줄 4개 x 2줄)
        v.addWidget(section_label("스타일"))
        self.cards_container = QWidget()
        self.cards_grid = QGridLayout(self.cards_container)
        self.cards_grid.setContentsMargins(0, 0, 0, 0)
        self.cards_grid.setSpacing(8)
        self._populate_style_cards()
        v.addWidget(self.cards_container)

        # 아래 두 칸 (왼쪽: 밝게/어둡게, 유리 맑기, 전체 진하기 / 오른쪽: 아이콘 모양, 버튼 이름 보이기)
        bot_cols = QHBoxLayout()
        bot_cols.setSpacing(20)

        # 왼쪽 칸
        left_bot = QVBoxLayout()
        left_bot.setSpacing(10)
        left_bot.addWidget(section_label("밝기 및 유리"))

        tb_row = QHBoxLayout()
        self.theme_tabs = SegmentedTabs(["밝은 테마", "어두운 테마"])
        self.theme_tabs.setCurrentIndex(1 if c.theme == "dark" else 0, animate=False)
        self.theme_tabs.currentChanged.connect(self._on_theme_changed)
        tb_row.addWidget(QLabel("테마 밝기"))
        tb_row.addWidget(self.theme_tabs, 1)
        left_bot.addLayout(tb_row)

        clarity_val = getattr(c, "glass_clarity", 20)
        self.clarity_slider = make_slider(0, 100, clarity_val)
        self.clarity_lab = QLabel(f"{clarity_val}")
        self.clarity_slider.valueChanged.connect(self._on_clarity_changed)
        left_bot.addLayout(slider_row("유리 맑기 / 흐림", self.clarity_slider, self.clarity_lab))

        self.opacity = make_slider(30, 100, int(c.opacity * 100))
        self.opacity_lab = QLabel(f"{int(c.opacity * 100)}%")
        self.opacity.valueChanged.connect(self._on_opacity_changed)
        left_bot.addLayout(slider_row("전체 진하기", self.opacity, self.opacity_lab))
        left_bot.addStretch(1)
        bot_cols.addLayout(left_bot, 1)

        # 오른쪽 칸
        right_bot = QVBoxLayout()
        right_bot.setSpacing(10)
        right_bot.addWidget(section_label("아이콘 및 이름"))

        self.icon_styles = ["line", "duotone", "emoji"]
        cur_icon_idx = self.icon_styles.index(c.icon_style) if c.icon_style in self.icon_styles else 0
        self.icon_tabs = SegmentedTabs(["선만", "색 채움", "이모지"])
        self.icon_tabs.setCurrentIndex(cur_icon_idx, animate=False)
        self.icon_tabs.currentChanged.connect(lambda i: self._set("icon_style", self.icon_styles[i]))
        right_bot.addWidget(self.icon_tabs)

        self.labels_toggle = GlassToggle(c.show_labels)
        self.labels_toggle.toggled.connect(lambda on: self._set("show_labels", on))
        right_bot.addLayout(toggle_row("버튼 이름 표시", "아이콘 아래에 버튼 이름을 함께 보여줍니다.", self.labels_toggle))
        right_bot.addStretch(1)
        bot_cols.addLayout(right_bot, 1)

        v.addLayout(bot_cols)
        v.addStretch(1)
        self.stack.addWidget(page_widget)

    def _populate_style_cards(self):
        """기본 스타일 7개 및 사용자 테마 카드를 그리드에 채웁니다."""
        # 기존 카드 정리
        for card in self.style_cards.values():
            card.deleteLater()
        self.style_cards.clear()

        all_styles = dict(BUILTIN_THEMES)
        if hasattr(self.config, "user_themes") and isinstance(self.config.user_themes, dict):
            all_styles.update(self.config.user_themes)

        row, col = 0, 0
        for name, data in all_styles.items():
            card = StyleCard(name, data, self.cards_container)
            card.clicked.connect(lambda _, n=name, d=data: self._apply_style(n, d))
            self.cards_grid.addWidget(card, row, col)
            self.style_cards[name] = card
            col += 1
            if col >= 4:
                col = 0
                row += 1

    def _apply_style(self, name: str, data: dict):
        self.config.apply_theme_dict(data)
        self._sync_controls()
        self._changed()

    def _on_theme_changed(self, idx: int):
        new_theme = "dark" if idx == 1 else "light"
        self._set("theme", new_theme)

    def _on_clarity_changed(self, val: int):
        self.clarity_lab.setText(str(val))
        self.config.set_clarity(val)
        self._sync_controls()
        self._changed()

    def _on_opacity_changed(self, val: int):
        self.opacity_lab.setText(f"{val}%")
        self._set("opacity", val / 100.0)

    # ================================================================ 2. 크기 탭
    def _build_size_tab(self):
        page_widget, v = page()
        c = self.config

        # 1. 세로 몇 줄 / 가로 몇 칸
        v.addWidget(section_label("칸 수"))
        grid_lay = QHBoxLayout()
        grid_lay.setSpacing(12)

        grid_lay.addWidget(QLabel("세로 줄 수"))
        self.rows_spin = no_wheel(QSpinBox())
        self.rows_spin.setRange(1, 8)
        self.rows_spin.setValue(c.rows)
        self.rows_spin.valueChanged.connect(lambda val: self._set("rows", val))
        grid_lay.addWidget(self.rows_spin)

        grid_lay.addSpacing(20)

        grid_lay.addWidget(QLabel("가로 칸 수"))
        self.cols_spin = no_wheel(QSpinBox())
        self.cols_spin.setRange(1, 8)
        self.cols_spin.setValue(c.cols)
        self.cols_spin.valueChanged.connect(lambda val: self._set("cols", val))
        grid_lay.addWidget(self.cols_spin)
        grid_lay.addStretch(1)
        v.addLayout(grid_lay)

        # 2. 버튼 크기
        v.addWidget(section_label("버튼 크기"))
        preset = c.size_preset()
        idx = self.SIZE_KEYS.index(preset) if preset in self.SIZE_KEYS else 2
        self.size_tabs = SegmentedTabs([self.SIZE_DESC[k] for k in self.SIZE_KEYS])
        self.size_tabs.setCurrentIndex(idx, animate=False)
        self.size_tabs.currentChanged.connect(self._on_size_preset)
        v.addWidget(self.size_tabs)

        # 3. 버튼 사이 간격 (좁게 / 보통 / 넓게 - px 숫자는 숨김)
        v.addWidget(section_label("버튼 사이 간격"))
        cur_spacing = c.spacing
        if cur_spacing <= 5:
            spacing_idx = 0
        elif cur_spacing >= 12:
            spacing_idx = 2
        else:
            spacing_idx = 1
        self.spacing_tabs = SegmentedTabs(["좁게", "보통", "넓게"])
        self.spacing_tabs.setCurrentIndex(spacing_idx, animate=False)
        self.spacing_tabs.currentChanged.connect(lambda i: self._set("spacing", self.SPACING_MAP[i]))
        v.addWidget(self.spacing_tabs)

        v.addStretch(1)
        self.stack.addWidget(page_widget)

    def _on_size_preset(self, idx: int):
        key = self.SIZE_KEYS[idx]
        px, radius = SIZE_PRESETS[key]
        self.config.button_size = px
        self.config.button_radius = radius
        self._changed()

    # ================================================================ 3. 편리한 기능 탭
    def _build_features_tab(self):
        page_widget, v = page()
        c = self.config

        cols = QHBoxLayout()
        cols.setSpacing(20)

        # 왼쪽: 항상 위, 숨기기 키, 자석, 흐려지기, 위쪽 메뉴 항상 보이기
        left = QVBoxLayout()
        left.setSpacing(10)

        self.top_toggle = GlassToggle(c.always_on_top)
        self.top_toggle.toggled.connect(lambda on: self._set("always_on_top", on))
        left.addLayout(toggle_row("항상 위에 표시", "다른 프로그램을 쓰더라도 버튼판이 가려지지 않고 위에 머뭅니다.", self.top_toggle))

        self.hotkey_toggle = GlassToggle(c.hotkey_enabled)
        self.hotkey_toggle.toggled.connect(self._on_hotkey_toggle)
        left.addLayout(toggle_row("단축키로 숨기기·보이기", "어디서나 이 키를 누르면 버튼판을 띄우거나 숨깁니다.", self.hotkey_toggle))

        hk_row = QHBoxLayout()
        hk_row.setSpacing(10)
        hk_row.addWidget(QLabel("단축키"))
        self.hotkey_edit = KeyCaptureEdit(c.hotkey)
        self.hotkey_edit.captured.connect(self._on_hotkey_captured)
        self.hotkey_edit.setEnabled(c.hotkey_enabled)
        hk_row.addWidget(self.hotkey_edit, 1)
        left.addLayout(hk_row)

        self.snap_toggle = GlassToggle(c.snap_edges)
        self.snap_toggle.toggled.connect(lambda on: self._set("snap_edges", on))
        left.addLayout(toggle_row("화면 끝에 자석처럼 붙기", "버튼판을 끌고 화면 모서리에 가까이 가면 찰칵 달라붙습니다.", self.snap_toggle))

        self.fade_toggle = GlassToggle(c.auto_fade)
        self.fade_toggle.toggled.connect(self._on_fade_toggle)
        left.addLayout(toggle_row("안 쓸 때 흐려지기", "마우스를 떼고 있으면 투명해져서 화면을 가리지 않습니다.", self.fade_toggle))

        self.fade_box = QWidget()
        fb = QVBoxLayout(self.fade_box)
        fb.setContentsMargins(12, 0, 0, 0)
        self.fade_delay = make_slider(1, 10, c.auto_fade_delay)
        self.fade_delay_lab = QLabel(f"{c.auto_fade_delay}초")
        self.fade_delay.valueChanged.connect(self._on_fade)
        fb.addLayout(slider_row("대기 시간", self.fade_delay, self.fade_delay_lab))

        self.fade_op = make_slider(10, 80, int(c.auto_fade_opacity * 100))
        self.fade_op_lab = QLabel(f"{int(c.auto_fade_opacity * 100)}%")
        self.fade_op.valueChanged.connect(self._on_fade)
        fb.addLayout(slider_row("흐려졌을 때 진하기", self.fade_op, self.fade_op_lab))
        self.fade_box.setVisible(c.auto_fade)
        left.addWidget(self.fade_box)

        self.always_header_toggle = GlassToggle(c.always_show_header)
        self.always_header_toggle.toggled.connect(lambda on: self._set("always_show_header", on))
        left.addLayout(toggle_row("위쪽 메뉴 항상 보이기", "마우스를 올리지 않아도 상단 알약 메뉴를 항상 표시합니다.", self.always_header_toggle))
        left.addStretch(1)
        cols.addLayout(left, 1)

        # 오른쪽: 나머지
        right = QVBoxLayout()
        right.setSpacing(10)

        self.auto_start_toggle = GlassToggle(c.auto_start)
        self.auto_start_toggle.toggled.connect(lambda on: self._set("auto_start", on))
        right.addLayout(toggle_row("컴퓨터 켤 때 자동 실행", "윈도우가 시작되면 Virtual Deck이 자동으로 켜집니다.", self.auto_start_toggle))

        self.toasts_toggle = GlassToggle(c.show_toast)
        self.toasts_toggle.toggled.connect(lambda on: self._set("show_toast", on))
        right.addLayout(toggle_row("알림 보이기", "프로필 전환이나 되돌리기 시 화면 아래에 작은 알림을 띄웁니다.", self.toasts_toggle))

        self.auto_profile_toggle = GlassToggle(c.auto_switch_profile)
        self.auto_profile_toggle.toggled.connect(lambda on: self._set("auto_switch_profile", on))
        right.addLayout(toggle_row("쓰는 프로그램에 맞춰 프로필 이동", "포토샵, 브라우저 등 실행 중인 창에 맞춰 지정한 프로필로 자동 전환합니다. 직접 고른 프로필은 다른 프로그램으로 옮겨 갈 때까지 유지돼요.", self.auto_profile_toggle))

        self.sync_mute_toggle = GlassToggle(c.sync_toggle_state)
        self.sync_mute_toggle.toggled.connect(lambda on: self._set("sync_toggle_state", on))
        right.addLayout(toggle_row("음소거·프로그램 버튼 불을 실제 상태와 맞추기", "윈도우 음소거 및 프로그램 실행 상태를 감지하여 버튼의 켜짐/꺼짐을 일치시킵니다.", self.sync_mute_toggle))
        right.addStretch(1)
        cols.addLayout(right, 1)

        v.addLayout(cols)
        v.addStretch(1)
        self.stack.addWidget(page_widget)

    # ================================================================ 4. 더보기 탭
    def _build_more_tab(self):
        page_widget, v = page()
        c = self.config

        cols = QHBoxLayout()
        cols.setSpacing(20)

        # 왼쪽: 되돌리기·보관 기간, 길게 누르는 시간, 컴퓨터 부담 줄이기, 소리 기능 설치
        left = QVBoxLayout()
        left.setSpacing(10)

        left.addWidget(section_label("자동 백업 및 되돌리기"))
        bk_row = QHBoxLayout()
        b_restore = GlassButton("백업 목록에서 되돌리기…", icon_name="undo")
        b_restore.clicked.connect(self._open_backup_dialog)
        bk_row.addWidget(b_restore)

        bk_row.addSpacing(12)
        bk_row.addWidget(QLabel("보관 기간"))
        self.retention_combo = no_wheel(QComboBox())
        self.retention_combo.addItem("7일", 7)
        self.retention_combo.addItem("14일", 14)
        self.retention_combo.addItem("30일", 30)
        self.retention_combo.addItem("무제한", 0)
        cur_days = getattr(c, "backup_retention_days", 14)
        self.retention_combo.setCurrentIndex(max(0, self.retention_combo.findData(cur_days)))
        self.retention_combo.currentIndexChanged.connect(lambda _: self._set("backup_retention_days", self.retention_combo.currentData()))
        bk_row.addWidget(self.retention_combo)
        bk_row.addStretch(1)
        left.addLayout(bk_row)

        left.addWidget(section_label("동작 세부 설정"))
        self.hold_slider = make_slider(200, 1000, c.hold_ms)
        self.hold_lab = QLabel(f"{c.hold_ms}ms")
        self.hold_slider.valueChanged.connect(self._on_hold_changed)
        left.addLayout(slider_row("길게 누르는 시간", self.hold_slider, self.hold_lab))

        self.low_spec_toggle = GlassToggle(getattr(c, "low_spec_mode", False))
        self.low_spec_toggle.toggled.connect(lambda on: self._set("low_spec_mode", on))
        left.addLayout(toggle_row("컴퓨터 부담 줄이기", "흐림 효과와 화면 캡처 주기를 완화하여 사양이 낮은 PC에서도 부드럽게 작동합니다.", self.low_spec_toggle))

        left.addWidget(section_label("소리 제어 확장"))
        sound_row = QHBoxLayout()
        from core.dependencies import has_pycaw
        available = has_pycaw()
        sound_status = QLabel("설치됨 (소리 감지 사용 가능)" if available else "미설치 (기본 음소거만 작동)")
        sound_status.setStyleSheet("color: #4ade80;" if available else "color: #fbbf24;")
        sound_row.addWidget(sound_status, 1)
        if not available:
            b_inst = GlassButton("소리 기능 설치")
            b_inst.clicked.connect(self._install_pycaw)
            sound_row.addWidget(b_inst)
        left.addLayout(sound_row)
        left.addStretch(1)
        cols.addLayout(left, 1)

        # 오른쪽: 직접 꾸민 배경, 내 스타일 저장·내보내기·불러오기, 이모지 아이콘 바꾸기
        right = QVBoxLayout()
        right.setSpacing(10)

        right.addWidget(section_label("직접 꾸민 배경"))
        self.custom_bg_modes = ["glass", "color", "gradient", "image"]
        cur_bg = c.bg_type if c.bg_type in self.custom_bg_modes else "glass"
        cur_bg_idx = self.custom_bg_modes.index(cur_bg)
        self.custom_bg_tabs = SegmentedTabs(["기본 스타일", "단색", "두 색 섞기", "사진"])
        self.custom_bg_tabs.setCurrentIndex(cur_bg_idx, animate=False)
        self.custom_bg_tabs.currentChanged.connect(self._on_custom_bg_tab)
        right.addWidget(self.custom_bg_tabs)

        self.custom_bg_stack = QStackedWidget()
        # 0: 기본 스타일 유지
        p0 = QWidget()
        p0_v = QVBoxLayout(p0)
        p0_v.addWidget(hint_label("선택한 스타일(유리 또는 투명)의 배경 효과를 그대로 사용합니다."))
        self.custom_bg_stack.addWidget(p0)

        # 1: 단색
        p1 = QWidget()
        p1_v = QVBoxLayout(p1)
        p1_row = QHBoxLayout()
        p1_row.addWidget(QLabel("배경 색상"))
        self.color_sw = ColorSwatch(c.bg_color)
        self.color_sw.colorChanged.connect(lambda col: self._set("bg_color", col))
        p1_row.addWidget(self.color_sw)
        p1_row.addStretch(1)
        p1_v.addLayout(p1_row)
        self.custom_bg_stack.addWidget(p1)

        # 2: 두 가지 색 섞기 (그라데이션)
        p2 = QWidget()
        p2_v = QVBoxLayout(p2)
        p2_row = QHBoxLayout()
        p2_row.addWidget(QLabel("시작 색"))
        self.grad_a = ColorSwatch(c.bg_gradient_start)
        self.grad_a.colorChanged.connect(lambda col: self._set("bg_gradient_start", col))
        p2_row.addWidget(self.grad_a)
        p2_row.addWidget(QLabel("끝 색"))
        self.grad_b = ColorSwatch(c.bg_gradient_end)
        self.grad_b.colorChanged.connect(lambda col: self._set("bg_gradient_end", col))
        p2_row.addWidget(self.grad_b)
        p2_row.addStretch(1)
        p2_v.addLayout(p2_row)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("방향"))
        self.grad_dir = no_wheel(QComboBox())
        self.grad_dir.addItem("위에서 아래로", "top_to_bottom")
        self.grad_dir.addItem("왼쪽에서 오른쪽으로", "left_to_right")
        self.grad_dir.addItem("대각선", "diagonal")
        self.grad_dir.setCurrentIndex(max(0, self.grad_dir.findData(c.bg_gradient_dir)))
        self.grad_dir.currentIndexChanged.connect(lambda _: self._set("bg_gradient_dir", self.grad_dir.currentData()))
        dir_row.addWidget(self.grad_dir, 1)
        p2_v.addLayout(dir_row)
        self.custom_bg_stack.addWidget(p2)

        # 3: 사진
        p3 = QWidget()
        p3_v = QVBoxLayout(p3)
        file_row = QHBoxLayout()
        self.img_path_lab = QLabel(os.path.basename(c.bg_image_path) if c.bg_image_path else "사진 없음")
        b_file = GlassButton("사진 고르기…")
        b_file.clicked.connect(self._pick_image)
        file_row.addWidget(b_file)
        file_row.addWidget(self.img_path_lab, 1)
        p3_v.addLayout(file_row)

        self.zoom = make_slider(50, 300, int(c.bg_image_zoom * 100))
        self.zoom_lab = QLabel(f"{int(c.bg_image_zoom * 100)}%")
        self.zoom.valueChanged.connect(lambda v: self._on_img_zoom(v / 100.0))
        p3_v.addLayout(slider_row("확대/축소", self.zoom, self.zoom_lab))

        self.img_x = make_slider(-200, 200, c.bg_image_x)
        self.img_x_lab = QLabel(f"{c.bg_image_x}")
        self.img_x.valueChanged.connect(lambda v: self._on_img_offset(x=v))
        p3_v.addLayout(slider_row("가로 위치", self.img_x, self.img_x_lab))

        self.img_y = make_slider(-200, 200, c.bg_image_y)
        self.img_y_lab = QLabel(f"{c.bg_image_y}")
        self.img_y.valueChanged.connect(lambda v: self._on_img_offset(y=v))
        p3_v.addLayout(slider_row("세로 위치", self.img_y, self.img_y_lab))
        self.custom_bg_stack.addWidget(p3)

        self.custom_bg_stack.setCurrentIndex(cur_bg_idx)
        right.addWidget(self.custom_bg_stack)

        right.addWidget(section_label("내 스타일 관리"))
        style_btn_row = QHBoxLayout()
        b_save_style = GlassButton("내 스타일 저장…")
        b_save_style.clicked.connect(self._save_user_style)
        b_export = GlassButton("파일 저장")
        b_export.clicked.connect(self._export_style)
        b_import = GlassButton("파일 불러오기")
        b_import.clicked.connect(self._import_style)
        style_btn_row.addWidget(b_save_style)
        style_btn_row.addWidget(b_export)
        style_btn_row.addWidget(b_import)
        right.addLayout(style_btn_row)

        right.addWidget(section_label("아이콘 변환"))
        icon_conv_row = QHBoxLayout()
        b_conv = GlassButton("이모지 → 테마 아이콘 변환", icon_name="refresh")
        b_conv.clicked.connect(self.convert_icons.emit)
        icon_conv_row.addWidget(b_conv)
        right.addLayout(icon_conv_row)
        right.addStretch(1)
        cols.addLayout(right, 1)

        v.addLayout(cols)
        v.addStretch(1)
        self.stack.addWidget(page_widget)

    def _on_custom_bg_tab(self, idx: int):
        self.custom_bg_stack.setCurrentIndex(idx)
        mode = self.custom_bg_modes[idx]
        self._set("bg_type", mode)

    def _pick_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "배경 사진 고르기", "", "그림 (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            self.config.bg_image_path = path
            self.img_path_lab.setText(os.path.basename(path))
            self._changed()

    def _on_img_zoom(self, z):
        self.zoom_lab.setText(f"{int(z * 100)}%")
        self._set("bg_image_zoom", z)

    def _on_img_offset(self, x=None, y=None):
        if x is not None:
            self.img_x_lab.setText(str(x))
            self.config.bg_image_x = x
        if y is not None:
            self.img_y_lab.setText(str(y))
            self.config.bg_image_y = y
        self._changed()

    def _on_hold_changed(self, val: int):
        self.hold_lab.setText(f"{val}ms")
        self._set("hold_ms", val)

    def _save_user_style(self):
        from ui.widgets import ask_text, inform
        name = ask_text(self, "내 스타일 저장", "이 스타일의 이름을 적어 주세요:")
        if not name:
            return
        td = self.config.theme_dict()
        if not hasattr(self.config, "user_themes") or not isinstance(self.config.user_themes, dict):
            self.config.user_themes = {}
        self.config.user_themes[name] = td
        self._populate_style_cards()
        self._sync_controls()
        inform(self, "저장 완료", f"‘{name}’ 스타일을 내 스타일에 저장했어요.")

    def _export_style(self):
        from ui.widgets import inform
        path, _ = QFileDialog.getSaveFileName(self, "스타일 파일로 내보내기", "virtual-deck-style.json", "스타일 (*.json)")
        if path:
            td = self.config.theme_dict()
            if self.storage.export_theme(td, path):
                inform(self, "내보내기 완료", "스타일을 파일로 저장했어요.")

    def _import_style(self):
        from ui.widgets import inform
        path, _ = QFileDialog.getOpenFileName(self, "스타일 파일 불러오기", "", "스타일 (*.json)")
        if path:
            data = self.storage.import_theme(path)
            if data:
                self.config.apply_theme_dict(data)
                self._sync_controls()
                self._changed()
                inform(self, "불러오기 완료", "스타일을 성공적으로 적용했어요.")

    def _install_pycaw(self):
        from ui.widgets import inform
        import subprocess, sys
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "pycaw"], check=True)
            inform(self, "설치 완료", "소리 제어 확장을 설치했어요. 프로그램을 다시 켜면 적용돼요.")
        except Exception as e:
            inform(self, "설치 실패", f"설치 중 오류가 발생했습니다: {e}")

    def _open_backup_dialog(self):
        dlg = BackupDialog(self.storage, parent=self)
        chosen = dlg.choose()
        if chosen:
            self.restore_path = chosen
            self.accept()

    # ================================================================ 컨트롤 동기화
    def _sync_controls(self):
        """테마나 스타일 변경 시 모든 탭의 위젯 값을 최신 설정에 맞춥니다."""
        c = self.config

        # 스타일 카드 체크 표시 동기화:
        # theme, bg_type, glass_tint 가 같은 카드 중에서 glass_clarity 가 지금 값과 가장 가까운 카드 하나만 선택.
        # 차이가 15 보다 크면 아무 카드도 선택하지 않기. 같은 조건이면 기본 스타일이 내 스타일보다 우선.
        current_clarity = getattr(c, "glass_clarity", 20)
        c_tint = getattr(c, "glass_tint", "")

        best_card_name = None
        best_diff = 999999
        best_is_builtin = False

        for name, card in self.style_cards.items():
            t_theme = card.theme_dict.get("theme")
            t_bg = card.theme_dict.get("bg_type")
            t_tint = card.theme_dict.get("glass_tint", "")
            if t_theme == c.theme and t_bg == c.bg_type and t_tint == c_tint:
                card_clarity = card.theme_dict.get("glass_clarity", 20)
                diff = abs(card_clarity - current_clarity)
                if diff <= 15:
                    is_builtin = (name in BUILTIN_THEMES)
                    if diff < best_diff or (diff == best_diff and is_builtin and not best_is_builtin):
                        best_diff = diff
                        best_card_name = name
                        best_is_builtin = is_builtin

        for name, card in self.style_cards.items():
            card.setChecked(name == best_card_name)

        # 꾸미기 탭
        if hasattr(self, "theme_tabs"):
            self.theme_tabs.setCurrentIndex(1 if c.theme == "dark" else 0, animate=False)
        if hasattr(self, "clarity_slider"):
            clarity = getattr(c, "glass_clarity", 20)
            self.clarity_slider.blockSignals(True)
            self.clarity_slider.setValue(clarity)
            self.clarity_slider.blockSignals(False)
            self.clarity_lab.setText(str(clarity))
        if hasattr(self, "icon_tabs"):
            idx = self.icon_styles.index(c.icon_style) if c.icon_style in self.icon_styles else 0
            self.icon_tabs.setCurrentIndex(idx, animate=False)
        if hasattr(self, "labels_toggle"):
            self.labels_toggle.setChecked(c.show_labels)
        if hasattr(self, "opacity"):
            self.opacity.setValue(int(c.opacity * 100))
            self.opacity_lab.setText(f"{int(c.opacity * 100)}%")

        # 크기 탭
        if hasattr(self, "rows_spin"):
            self.rows_spin.setValue(c.rows)
        if hasattr(self, "cols_spin"):
            self.cols_spin.setValue(c.cols)
        if hasattr(self, "size_tabs"):
            preset = c.size_preset()
            p_idx = self.SIZE_KEYS.index(preset) if preset in self.SIZE_KEYS else 2
            self.size_tabs.setCurrentIndex(p_idx, animate=False)
        if hasattr(self, "spacing_tabs"):
            sp = c.spacing
            sp_idx = 0 if sp <= 5 else (2 if sp >= 12 else 1)
            self.spacing_tabs.setCurrentIndex(sp_idx, animate=False)

        # 편리한 기능 탭
        if hasattr(self, "always_header_toggle"):
            self.always_header_toggle.setChecked(c.always_show_header)
        if hasattr(self, "top_toggle"):
            self.top_toggle.setChecked(c.always_on_top)
        if hasattr(self, "auto_start_toggle"):
            self.auto_start_toggle.setChecked(c.auto_start)
        if hasattr(self, "snap_toggle"):
            self.snap_toggle.setChecked(c.snap_edges)
        if hasattr(self, "fade_toggle"):
            self.fade_toggle.setChecked(c.auto_fade)
        if hasattr(self, "toasts_toggle"):
            self.toasts_toggle.setChecked(c.show_toast)
        if hasattr(self, "auto_profile_toggle"):
            self.auto_profile_toggle.setChecked(c.auto_switch_profile)
        if hasattr(self, "sync_mute_toggle"):
            self.sync_mute_toggle.setChecked(c.sync_toggle_state)

        # 더보기 탭
        if hasattr(self, "custom_bg_tabs"):
            bg_idx = self.custom_bg_modes.index(c.bg_type) if c.bg_type in self.custom_bg_modes else 0
            self.custom_bg_tabs.setCurrentIndex(bg_idx, animate=False)
            self.custom_bg_stack.setCurrentIndex(bg_idx)
        if hasattr(self, "hold_slider"):
            self.hold_slider.setValue(c.hold_ms)
            self.hold_lab.setText(f"{c.hold_ms}ms")

    def _set(self, key, value):
        setattr(self.config, key, value)
        self._changed()

    def _on_hotkey_toggle(self, on):
        self.config.hotkey_enabled = on
        self.hotkey_edit.setEnabled(on)
        self._changed()

    def _on_hotkey_captured(self, key, mods):
        if not mods:
            self.hotkey_edit.setText("Ctrl, Alt 등과 함께 눌러 주세요")
            return
        order = [m for m in ("Win", "Ctrl", "Alt", "Shift") if m in mods]
        value = " + ".join(order + [key])
        self.hotkey_edit.setText(value)
        self.config.hotkey = value
        self._changed()

    def _on_fade_toggle(self, on):
        self.config.auto_fade = on
        self.fade_box.setVisible(on)
        self._changed()

    def _on_fade(self, *_):
        self.config.auto_fade_delay = self.fade_delay.value()
        self.config.auto_fade_opacity = self.fade_op.value() / 100
        self.fade_delay_lab.setText(f"{self.fade_delay.value()}초")
        self.fade_op_lab.setText(f"{self.fade_op.value()}%")
        self._changed()


class BackupDialog(GlassDialog):
    """자동 백업 목록에서 하나를 골라 되돌리기"""

    def __init__(self, storage, parent=None):
        super().__init__("백업에서 되돌리기", "고른 날의 설정과 버튼으로 돌아가요", parent=parent, width=440)
        self.storage = storage
        self.chosen = None
        self.list = QListWidget()
        self.list.setMinimumHeight(260)
        for path, label in storage.list_backups():
            it = QListWidgetItem(label)
            it.setData(Qt.UserRole, path)
            self.list.addItem(it)
        if not self.list.count():
            it = QListWidgetItem("아직 백업이 없어요. 하루에 한 번 자동으로 만들어져요.")
            it.setFlags(Qt.NoItemFlags)
            self.list.addItem(it)
        self.list.itemDoubleClicked.connect(lambda _: self._ok())
        self.body.addWidget(self.list, 1)
        self.body.addWidget(hint_label("되돌리기 전의 지금 상태도 백업 폴더에 따로 저장해 두니 안심하세요."))
        self.footer.addStretch(1)
        cancel = GlassButton("취소")
        cancel.clicked.connect(self.reject)
        ok = GlassButton("이 백업으로 되돌리기", tint="orange", icon_name="undo")
        ok.clicked.connect(self._ok)
        self.footer.addWidget(cancel)
        self.footer.addWidget(ok)
        self.resize(self.width(), 480)

    def _ok(self):
        from ui.widgets import ask
        it = self.list.currentItem()
        path = it.data(Qt.UserRole) if it else None
        if path and ask(self, "되돌리기", f"{it.text()} 상태로 되돌릴까요?", ok_text="되돌리기"):
            self.chosen = path
            self.accept()

    def choose(self):
        return self.chosen if self.exec() else None
