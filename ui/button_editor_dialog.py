"""
버튼 편집창
이름, 유리 색, 아이콘(테마 아이콘 / 이모지 / 그림 파일), 아이콘 색,
누르면 할 일, 켜기/끄기 버튼 설정을 한 화면에서 정합니다.
왼쪽 위 미리보기에 바뀐 모습이 바로 보입니다.
"""

import os
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal, QRectF
from PySide6.QtGui import QPainter, QColor, QFont
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox, QStackedWidget,
    QFileDialog, QScrollArea, QFrame, QSpinBox, QSizePolicy,
)

from core import paths
from core.action_executor import ACTION_LABELS, ACTION_ICONS
from core.icon_fetcher import extract_file_icon, FaviconFetcher
from core.macro_manager import parse_steps
from core.shortcut_manager import ShortcutManager
from models.button_model import DeckButtonData
from ui import theme, icons
from ui.theme import T
from ui.deck_button import DeckButtonWidget
from ui.glass import paint_glass
from ui.widgets import (
    GlassDialog, GlassButton, GlassToggle, ColorChips, ShortcutEditor, SegmentedTabs,
    section_label, hint_label, inform, no_wheel,
)


class EmojiGrid(QWidget):
    """추천 이모지 고르기"""

    picked = Signal(str)
    ICONS = ["🌐", "📁", "📄", "🎵", "🎬", "🎨", "⚙️", "💻", "🔊", "📝", "🚀", "🎮",
             "💬", "⌨️", "⚡", "🪄", "🔍", "📊", "🎯", "🔔", "⭐", "🔥", "💡", "🛡️",
             "📸", "📋", "📌", "💾", "🔄", "↩️", "▶️", "⏯️", "🔇", "🎤", "☕", "🗂️"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cols = 6
        self.cell = 38
        self.current = ""
        self._hover = -1
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(6 * self.cell + 4)
        self._layout()

    def _layout(self):
        rows = (len(self.ICONS) + self.cols - 1) // self.cols
        self.setFixedHeight(rows * self.cell + 4)

    def resizeEvent(self, e):
        cols = max(6, (self.width() - 4) // self.cell)
        if cols != self.cols:
            self.cols = cols
            self._layout()
        super().resizeEvent(e)

    def set_current(self, text: str):
        self.current = text
        self.update()

    def _rect(self, i) -> QRectF:
        r, c = divmod(i, self.cols)
        return QRectF(2 + c * self.cell + 2, 2 + r * self.cell + 2, self.cell - 4, self.cell - 4)

    def _index(self, pos):
        for i in range(len(self.ICONS)):
            if self._rect(i).contains(pos):
                return i
        return -1

    def mouseMoveEvent(self, e):
        i = self._index(e.position())
        if i != self._hover:
            self._hover = i
            self.update()

    def leaveEvent(self, e):
        self._hover = -1
        self.update()

    def mousePressEvent(self, e):
        i = self._index(e.position())
        if i >= 0:
            self.current = self.ICONS[i]
            self.picked.emit(self.current)
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(theme.emoji_font(18))
        for i, ic in enumerate(self.ICONS):
            r = self._rect(i)
            if ic == self.current:
                paint_glass(p, r, 10, tint="blue", shadow_strength=0.5, rainbow=0.4)
            elif i == self._hover:
                paint_glass(p, r, 10, fill=0.8, shadow_strength=0.5, rainbow=0.4)
            p.setPen(QColor(T().text))
            p.drawText(r, Qt.AlignCenter, ic)


class ActionEditor(QWidget):
    """누르면 할 일 고르기 (종류 + 자세한 값)"""

    changed = Signal()
    path_picked = Signal(str, str)     # 종류, 경로
    url_done = Signal(str)

    def __init__(self, types, none_hint: str = "아무 일도 하지 않아요.", parent=None):
        super().__init__(parent)
        self.types = types
        self.macro_json = "[]"
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.combo = no_wheel(QComboBox())
        for t in types:
            icon = ACTION_ICONS.get(t, "▫️")
            self.combo.addItem(f"{icon}  {ACTION_LABELS[t]}", t)
        self.combo.currentIndexChanged.connect(self._on_type)
        lay.addWidget(self.combo)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)
        self.pages = {}
        for t in types:
            page = self._make_page(t, none_hint)
            self.pages[t] = page
            self.stack.addWidget(page)
        self._on_type(0)

    def _path_page(self, kind, placeholder, hint):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(6)
        h = QHBoxLayout()
        h.setSpacing(8)
        edit = QLineEdit()
        edit.setPlaceholderText(placeholder)
        edit.textChanged.connect(lambda _: self.changed.emit())
        h.addWidget(edit, 1)
        if kind != "url":
            browse = GlassButton("찾기…", icon_name="folder")
            browse.clicked.connect(lambda: self._browse(kind, edit))
            h.addWidget(browse)
        else:
            edit.editingFinished.connect(lambda: self.url_done.emit(edit.text()))
        v.addLayout(h)
        v.addWidget(hint_label(hint))
        w.edit = edit
        return w

    def _make_page(self, t, none_hint):
        if t == "url":
            return self._path_page("url", "예: https://www.youtube.com", "웹 주소를 적어 주세요. https:// 는 빼도 돼요.")
        if t == "program":
            return self._path_page("program", "예: C:\\Program Files\\...\\app.exe 또는 notepad.exe",
                                   "실행할 프로그램을 고르세요. 바로가기(.lnk)도 돼요.")
        if t == "file":
            return self._path_page("file", "열 파일 경로", "기본 연결 프로그램으로 파일을 열어요.")
        if t == "folder":
            return self._path_page("folder", "열 폴더 경로", "파일 탐색기로 폴더를 열어요.")
        if t == "close":
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.addWidget(hint_label("실행 중인 프로그램이나 열려 있는 폴더 창을 안전하게 닫습니다."))
            return w
        if t == "shortcut":
            w = ShortcutEditor()
            w.changed.connect(lambda _: self.changed.emit())
            return w
        if t == "media":
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            combo = no_wheel(QComboBox())
            for key, label in ShortcutManager.MEDIA_KEYS:
                combo.addItem(label, key)
            combo.currentIndexChanged.connect(lambda _: self.changed.emit())
            v.addWidget(combo)
            v.addWidget(hint_label("음악 앱이나 브라우저 영상에도 대부분 동작해요."))
            w.combo = combo
            return w
        if t == "macro":
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.setSpacing(6)
            h = QHBoxLayout()
            w.summary = QLabel()
            w.summary.setWordWrap(True)
            h.addWidget(w.summary, 1)
            btn = GlassButton("연속 동작 만들기…", tint="blue", icon_name="edit")
            btn.clicked.connect(self._edit_macro)
            h.addWidget(btn)
            v.addLayout(h)
            v.addWidget(hint_label("여러 동작을 차례대로 실행해요. 실행 중에 버튼을 다시 누르면 멈춰요."))
            return w
        if t == "timer":
            return self._timer_page()
        if t == "info":
            from core.system_info import INFO_KINDS
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            combo = no_wheel(QComboBox())
            for key, (label, _icon) in INFO_KINDS.items():
                combo.addItem(label, key)
            combo.currentIndexChanged.connect(lambda _: self.changed.emit())
            v.addWidget(combo)
            v.addWidget(hint_label("버튼에 값이 1초마다 새로 보여요. 볼륨 %는 소리 기능 추가 설치가 필요해요."))
            w.combo = combo
            return w
        if t == "group":
            w = QWidget()
            v = QVBoxLayout(w)
            v.setContentsMargins(0, 0, 0, 0)
            v.addWidget(hint_label("누르면 안에 버튼이 더 있어요. 저장한 뒤 버튼을 눌러 "
                                   "안쪽 칸을 채우세요. 위쪽 ‹ 버튼으로 다시 나올 수 있어요."))
            return w
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(hint_label(none_hint))
        return w

    def _timer_page(self):
        """타이머 설정: 카운트다운/스톱워치, 시간, 소리, 끝나면 할 일"""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(8)
        w.mode = SegmentedTabs(["⏳  카운트다운", "⏱  스톱워치"])
        v.addWidget(w.mode)
        w.count_box = QWidget()
        cb = QVBoxLayout(w.count_box)
        cb.setContentsMargins(0, 0, 0, 0)
        cb.setSpacing(8)
        presets = QHBoxLayout()
        presets.setSpacing(6)
        for label, sec in (("1분", 60), ("3분", 180), ("5분", 300), ("10분", 600), ("25분", 1500), ("1시간", 3600)):
            b = GlassButton(label)
            b.clicked.connect(lambda _=False, s_=sec: self._set_timer_seconds(w, s_))
            presets.addWidget(b)
        presets.addStretch(1)
        cb.addLayout(presets)
        tr = QHBoxLayout()
        w.minutes = no_wheel(QSpinBox())
        w.minutes.setRange(0, 1440)
        w.minutes.setSuffix(" 분")
        w.seconds = no_wheel(QSpinBox())
        w.seconds.setRange(0, 59)
        w.seconds.setSuffix(" 초")
        for sp in (w.minutes, w.seconds):
            sp.valueChanged.connect(lambda _: self.changed.emit())
            tr.addWidget(sp, 1)
        cb.addLayout(tr)
        sr = QHBoxLayout()
        sr.addWidget(QLabel("끝나면 소리 내기"))
        sr.addStretch(1)
        w.sound = GlassToggle(True)
        w.sound.toggled.connect(lambda _: self.changed.emit())
        sr.addWidget(w.sound)
        cb.addLayout(sr)
        cb.addWidget(hint_label("끝나면 할 일 (선택): 예) 끝나면 음악 일시정지, 메모장 열기"))
        w.then = ActionEditor(["none", "url", "program", "file", "folder", "shortcut", "media", "macro"],
                              none_hint="끝나면 소리와 알림만 보여 줘요.")
        w.then.changed.connect(self._refit)
        w.then.changed.connect(lambda: self.changed.emit())
        cb.addWidget(w.then)
        v.addWidget(w.count_box)
        v.addWidget(hint_label("누르면 시작 / 일시정지, 길게 누르면 처음으로. 버튼판을 숨겨도 계속 흘러가요."))
        w.mode.currentChanged.connect(lambda i: (w.count_box.setVisible(i == 0), self._refit(), self.changed.emit()))
        self._set_timer_seconds(w, 300)   # 기본 5분
        return w

    def _set_timer_seconds(self, w, sec: int):
        w.minutes.setValue(sec // 60)
        w.seconds.setValue(sec % 60)

    def _refit(self, *_):
        page = self.stack.currentWidget()
        if page is not None:
            self.stack.setFixedHeight(page.sizeHint().height())

    def _browse(self, kind, edit):
        if kind == "folder":
            path = QFileDialog.getExistingDirectory(self, "폴더 선택", edit.text() or "")
        elif kind == "program":
            path, _ = QFileDialog.getOpenFileName(self, "프로그램 선택", "",
                                                  "프로그램 (*.exe *.bat *.cmd *.lnk *.url);;모든 파일 (*.*)")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "파일 선택", "", "모든 파일 (*.*)")
        if path:
            path = os.path.normpath(path)
            edit.setText(path)
            self.path_picked.emit(kind, path)

    def _edit_macro(self):
        from ui.macro_editor_dialog import MacroEditorDialog
        dlg = MacroEditorDialog(self.macro_json, parent=self.window())
        if dlg.exec():
            self.macro_json = dlg.macro_json()
            self._update_macro_summary()
            self.changed.emit()

    def _update_macro_summary(self):
        steps = parse_steps(self.macro_json)
        page = self.pages.get("macro")
        if page is None:
            return
        if not steps:
            page.summary.setText("아직 순서가 없어요.")
        else:
            from core.macro_manager import STEP_TYPES
            first = ", ".join(STEP_TYPES.get(s["type"], s["type"]).split(" ", 1)[-1] for s in steps[:3])
            more = f" 외 {len(steps) - 3}개" if len(steps) > 3 else ""
            page.summary.setText(f"<b>{len(steps)}순서</b> · {first}{more}")

    def _on_type(self, idx):
        t = self.combo.itemData(idx)
        if t in self.pages:
            self.stack.setCurrentWidget(self.pages[t])
            page = self.pages[t]
            self.stack.setFixedHeight(page.sizeHint().height())
        self.changed.emit()

    def current_type(self) -> str:
        return self.combo.currentData()

    def value(self):
        t = self.current_type()
        page = self.pages[t]
        if t in ("url", "program", "file", "folder"):
            return t, page.edit.text().strip()
        if t == "shortcut":
            return t, page.value()
        if t in ("media", "info"):
            return t, page.combo.currentData()
        if t == "timer":
            from core.timer_manager import dump_timer
            then_t, then_d = page.then.value()
            return t, dump_timer({
                "mode": "stopwatch" if page.mode.index == 1 else "countdown",
                "seconds": max(1, page.minutes.value() * 60 + page.seconds.value()),
                "sound": page.sound.isChecked(),
                "then_type": then_t if then_d else "none", "then_data": then_d if then_d else "",
            })
        if t == "macro":
            return t, self.macro_json if parse_steps(self.macro_json) else ""
        return t, ""

    def get_type(self) -> str:
        return self.value()[0]

    def set_value(self, t: str, data: str):
        if t not in self.types:
            t = self.types[0]
        self.combo.setCurrentIndex(self.types.index(t))
        page = self.pages[t]
        if t in ("url", "program", "file", "folder"):
            page.edit.setText(data)
        elif t == "shortcut":
            page.set_value(data)
        elif t in ("media", "info"):
            i = page.combo.findData(data)
            page.combo.setCurrentIndex(max(0, i))
        elif t == "timer":
            from core.timer_manager import parse_timer
            cfg = parse_timer(data)
            page.mode.setCurrentIndex(1 if cfg["mode"] == "stopwatch" else 0, animate=False)
            page.count_box.setVisible(cfg["mode"] != "stopwatch")
            self._set_timer_seconds(page, cfg["seconds"])
            page.sound.setChecked(bool(cfg.get("sound", True)))
            page.then.set_value(cfg.get("then_type", "none"), cfg.get("then_data", ""))
            self._refit()
        elif t == "macro":
            self.macro_json = data or "[]"
        self._update_macro_summary()


class ThemeIconGrid(QWidget):
    """테마 아이콘 고르기 (분류별)"""

    picked = Signal(str)

    def __init__(self, style: str = "line", parent=None):
        super().__init__(parent)
        self.style = style
        self.cols = 6
        self.cell = 38
        self.current = ""
        self._hover = None
        self.setMouseTracking(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumWidth(6 * self.cell + 4)
        self._layout()

    def resizeEvent(self, e):
        cols = max(6, (self.width() - 4) // self.cell)
        if cols != self.cols:
            self.cols = cols
            self._layout()
        super().resizeEvent(e)

    def _layout(self):
        self.items = []     # (이름, QRectF)
        self.headers = []   # (글자, y)
        y = 2
        for cat in icons.CATEGORIES:
            self.headers.append((cat, y))
            y += 22
            names = [n for n, v in icons.REGISTRY.items() if v[3] == cat]
            for i, n in enumerate(names):
                r, c = divmod(i, self.cols)
                self.items.append((n, QRectF(2 + c * self.cell + 2, y + r * self.cell + 2, self.cell - 4, self.cell - 4)))
            y += ((len(names) + self.cols - 1) // self.cols) * self.cell + 6
        self.setFixedHeight(y)

    def set_style(self, style: str):
        self.style = style
        self.update()

    def set_current(self, icon: str):
        self.current = icons.icon_name(icon)
        self.update()

    def _at(self, pos):
        for n, r in self.items:
            if r.contains(pos):
                return n
        return None

    def mouseMoveEvent(self, e):
        n = self._at(e.position())
        if n != self._hover:
            self._hover = n
            self.setToolTip(icons.REGISTRY[n][0] if n else "")
            self.update()

    def leaveEvent(self, e):
        self._hover = None
        self.update()

    def mousePressEvent(self, e):
        n = self._at(e.position())
        if n:
            self.current = n
            self.picked.emit(icons.PREFIX + n)
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setFont(theme.ui_font(11, QFont.DemiBold))
        p.setPen(QColor(T().text_dim))
        for text, y in self.headers:
            p.drawText(QRectF(4, y, self.width(), 20), Qt.AlignVCenter | Qt.AlignLeft, text)
        color = QColor(T().text)
        for n, r in self.items:
            sel = n == self.current
            if sel:
                paint_glass(p, r, 10, tint="blue", shadow_strength=0.5, rainbow=0.4)
            elif n == self._hover:
                paint_glass(p, r, 10, fill=0.8, shadow_strength=0.5, rainbow=0.4)
            inner = r.adjusted(9, 9, -9, -9)
            c = QColor("#ffffff") if sel else color
            if not icons.paint_icon(p, icons.PREFIX + n, inner, c, self.style,
                                    QColor("#ffffff") if sel else QColor(T().accent)):
                p.setFont(theme.emoji_font(17))
                p.setPen(c)
                p.drawText(r, Qt.AlignCenter, icons.REGISTRY[n][1])
                p.setFont(theme.ui_font(11, QFont.DemiBold))


class IconPicker(QWidget):
    """아이콘 고르기: 테마 아이콘 / 이모지 / 그림 파일"""

    picked = Signal(str)
    fetch_requested = Signal(str)   # 'file' 또는 'web'

    def __init__(self, style: str, parent=None):
        super().__init__(parent)
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        self.tabs = SegmentedTabs(["테마 아이콘", "이모지", "그림 파일"])
        lay.addWidget(self.tabs)
        self.stack = QStackedWidget()
        lay.addWidget(self.stack)
        self.tabs.currentChanged.connect(self.stack.setCurrentIndex)

        # 테마 아이콘
        self.theme_grid = ThemeIconGrid(style)
        self.theme_grid.picked.connect(self.picked)
        sc = QScrollArea()
        sc.setWidgetResizable(True)
        sc.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sc.setFrameShape(QFrame.NoFrame)
        sc.setWidget(self.theme_grid)
        sc.setFixedHeight(184)
        self.stack.addWidget(sc)

        # 이모지
        ew = QWidget()
        ev = QVBoxLayout(ew)
        ev.setContentsMargins(0, 0, 0, 0)
        ev.setSpacing(6)
        self.emoji = EmojiGrid()
        self.emoji.picked.connect(self.picked)
        ev.addWidget(self.emoji)
        self.emoji_edit = QLineEdit()
        self.emoji_edit.setPlaceholderText("직접 입력: 이모지나 글자 한두 개 (Win + . 키로 이모지 창 열기)")
        self.emoji_edit.textEdited.connect(lambda t: t.strip() and self.picked.emit(t.strip()))
        ev.addWidget(self.emoji_edit)
        ev.addStretch(1)
        self.stack.addWidget(ew)

        # 그림 파일
        iw = QWidget()
        iv = QVBoxLayout(iw)
        iv.setContentsMargins(0, 0, 0, 0)
        iv.setSpacing(8)
        r1 = QHBoxLayout()
        pick = GlassButton("그림 파일 고르기…", tint="blue", icon_name="folder")
        pick.clicked.connect(self._browse)
        r1.addWidget(pick)
        r1.addStretch(1)
        iv.addLayout(r1)
        r2 = QHBoxLayout()
        b_file = GlassButton("프로그램·파일 아이콘 가져오기", icon_name="import")
        b_file.clicked.connect(lambda: self.fetch_requested.emit("file"))
        b_web = GlassButton("사이트 아이콘 가져오기", icon_name="import")
        b_web.clicked.connect(lambda: self.fetch_requested.emit("web"))
        r2.addWidget(b_file)
        r2.addWidget(b_web)
        r2.addStretch(1)
        iv.addLayout(r2)
        self.status = hint_label("PNG, JPG, ICO 등. 고른 그림은 자동으로 가져와 보관해요.")
        iv.addWidget(self.status)
        iv.addStretch(1)
        self.stack.addWidget(iw)
        self.stack.setFixedHeight(214)

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "아이콘 그림 선택", "",
                                              "그림 (*.png *.jpg *.jpeg *.ico *.bmp *.gif *.webp *.svg)")
        if path:
            self.picked.emit(paths.import_icon_file(path))

    def show_for(self, icon: str):
        """현재 아이콘 종류에 맞는 탭을 열고 선택 표시"""
        self.theme_grid.set_current(icon)
        self.emoji.set_current(icon)
        if icons.is_theme_icon(icon) or not icon:
            self.tabs.setCurrentIndex(0, animate=False)
            self.stack.setCurrentIndex(0)
        elif paths.looks_like_image_path(icon):
            self.tabs.setCurrentIndex(2, animate=False)
            self.stack.setCurrentIndex(2)
            self.status.setText(f"지금 그림: {os.path.basename(icon)}")
        else:
            self.tabs.setCurrentIndex(1, animate=False)
            self.stack.setCurrentIndex(1)


class ButtonEditorDialog(GlassDialog):
    PRIMARY_TYPES = ["url", "program", "file", "folder", "shortcut", "media", "macro", "group", "info", "timer"]
    SPANS = [(1, 1), (2, 1), (1, 2), (2, 2)]
    OFF_TYPES = ["none", "close", "url", "program", "file", "folder", "shortcut", "media", "macro"]

    def __init__(self, data: DeckButtonData, in_folder: bool = False, icon_style: str = "line",
                 parent=None, modeless: bool = True):
        super().__init__("버튼 설정", "모양과 누르면 할 일을 정해요", parent=parent, width=900, modeless=modeless)
        self.data = data
        self.in_folder = in_folder
        self.cleared = False
        self.icon_value = data.icon
        self.icon_style = icon_style
        self._manual_icon = bool(data.icon) and not self._is_default_icon(data.icon)
        self.fetcher = FaviconFetcher(self)
        self.fetcher.done.connect(self._on_favicon)
        types = [t for t in self.PRIMARY_TYPES if not (in_folder and t == "group")]

        cols_lay = QHBoxLayout()
        cols_lay.setSpacing(18)

        # ------------------------------------------------ 왼쪽: 무엇을 할까요
        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        left_scroll.setFrameShape(QFrame.NoFrame)
        left_content = QWidget()
        left_content.setAttribute(Qt.WA_TranslucentBackground, True)
        left_content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        left_v = QVBoxLayout(left_content)
        left_v.setContentsMargins(2, 0, 8, 0)
        left_v.setSpacing(10)
        left_scroll.setWidget(left_content)
        self.left_scroll = left_scroll
        self.left_content = left_content
        cols_lay.addWidget(left_scroll, 5)

        # 1. 이름 칸 + 켜기/끄기 스위치 (한 줄)
        name_toggle_row = QHBoxLayout()
        name_toggle_row.setSpacing(12)

        name_v = QVBoxLayout()
        name_v.setSpacing(4)
        name_v.addWidget(section_label("이름"))
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("버튼에 보일 이름 (비우면 자동)")
        self.name_edit.textChanged.connect(self._update_preview)
        name_v.addWidget(self.name_edit)
        name_toggle_row.addLayout(name_v, 1)

        toggle_v = QVBoxLayout()
        toggle_v.setSpacing(4)
        toggle_v.addWidget(section_label("스위치"))
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(6)
        self.toggle = GlassToggle()
        self.toggle.toggled.connect(self._on_toggle)
        toggle_lbl = QLabel("켜기/끄기")
        toggle_lbl.setFont(theme.ui_font(12))
        toggle_row.addWidget(self.toggle)
        toggle_row.addWidget(toggle_lbl)
        toggle_v.addLayout(toggle_row)
        name_toggle_row.addLayout(toggle_v)
        left_v.addLayout(name_toggle_row)

        self.toggle_hint = hint_label("누를 때마다 불이 켜지고 꺼져요")
        left_v.addWidget(self.toggle_hint)

        # 2. 누르면 할 일
        left_v.addWidget(section_label("누르면 할 일"))
        self.action = ActionEditor(types)
        self.action.changed.connect(self._on_action_changed)
        self.action.path_picked.connect(lambda *_: self._on_action_changed())
        left_v.addWidget(self.action)

        # 3. 버튼 크기
        left_v.addWidget(section_label("버튼 크기"))
        self.span_tabs = SegmentedTabs(["1칸", "가로 2칸", "세로 2칸", "4칸"])
        self.span_tabs.currentChanged.connect(lambda _: self._update_preview())
        left_v.addWidget(self.span_tabs)
        left_v.addWidget(hint_label("큰 버튼이 덮는 칸의 기존 버튼은 숨겨집니다."))

        # 4. 길게 누르면 할 일
        left_v.addWidget(section_label("길게 누르면 할 일"))
        left_v.addWidget(hint_label("꾹 누르고 있으면 이 동작을 실행합니다."))
        self.hold_action = ActionEditor(self.OFF_TYPES, none_hint="길게 눌러도 따로 하는 일이 없어요.")
        self.hold_action.changed.connect(self._update_preview)
        left_v.addWidget(self.hold_action)

        # 5. 켜진 상태에서 누르면 할 일 (켜기/끄기 스위치를 켰을 때만)
        self.off_box = QWidget()
        ob = QVBoxLayout(self.off_box)
        ob.setContentsMargins(0, 0, 0, 0)
        ob.setSpacing(6)
        ob.addWidget(section_label("켜진 상태에서 누르면 할 일"))
        ob.addWidget(hint_label("‘동작 없음’이면 켤 때와 같은 동작을 다시 실행합니다."))
        self.off_action = ActionEditor(self.OFF_TYPES, none_hint="켤 때와 같은 동작을 다시 실행해요.")
        ob.addWidget(self.off_action)
        left_v.addWidget(self.off_box)
        left_v.addStretch(1)

        # ------------------------------------------------ 오른쪽: 어떻게 보일까요
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_content = QWidget()
        right_content.setAttribute(Qt.WA_TranslucentBackground, True)
        right_content.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        right_v = QVBoxLayout(right_content)
        right_v.setContentsMargins(8, 0, 2, 0)
        right_v.setSpacing(10)
        right_scroll.setWidget(right_content)
        self.right_scroll = right_scroll
        self.right_content = right_content
        cols_lay.addWidget(right_scroll, 6)

        # 1. 미리보기 (중앙 정렬)
        preview_wrap = QHBoxLayout()
        preview_wrap.addStretch(1)
        self.preview_host = QWidget()
        self.preview_host.setFixedSize(124, 124)
        self.preview = DeckButtonWidget(data.clone(), 108, True, icon_style, self.preview_host)
        self.preview.preview_mode = True
        self.preview.move(8, 6)
        preview_wrap.addWidget(self.preview_host)
        preview_wrap.addStretch(1)
        right_v.addLayout(preview_wrap)

        # 2. 아이콘
        ih = QHBoxLayout()
        ih.addWidget(section_label("아이콘"))
        ih.addStretch(1)
        b_auto = GlassButton("자동", icon_name="refresh")
        b_auto.setToolTip("지금 고른 동작에 맞는 테마 아이콘으로")
        b_auto.clicked.connect(self._auto_icon)
        ih.addWidget(b_auto)
        right_v.addLayout(ih)
        self.picker = IconPicker(icon_style)
        self.picker.picked.connect(self._set_icon)
        self.picker.fetch_requested.connect(self._fetch_icon)
        right_v.addWidget(self.picker)

        # 3. 아이콘 색 · 유리 색
        colors_box = QVBoxLayout()
        colors_box.setSpacing(6)
        colors_box.addWidget(QLabel("아이콘 색"))
        self.icon_colors = ColorChips(mode="icon")
        self.icon_colors.changed.connect(lambda _: self._update_preview())
        colors_box.addWidget(self.icon_colors)

        colors_box.addWidget(QLabel("유리 색"))
        self.colors = ColorChips()
        self.colors.changed.connect(lambda _: self._update_preview())
        colors_box.addWidget(self.colors)
        right_v.addLayout(colors_box)
        right_v.addWidget(hint_label("아이콘 색의 ‘A’는 버튼 색에 맞춰 자동으로 고릅니다."))
        right_v.addStretch(1)

        self.body.addLayout(cols_lay, 1)

        # 아래 버튼 줄
        self.clear_btn = GlassButton("비우기", icon_name="trash")
        self.clear_btn.clicked.connect(self._on_clear)
        self.footer.addWidget(self.clear_btn)
        self.footer.addStretch(1)
        cancel = GlassButton("취소")
        cancel.clicked.connect(self.reject)
        self.footer.addWidget(cancel)
        save = GlassButton("저장", tint="orange", icon_name="check")
        save.clicked.connect(self._on_save)
        self.footer.addWidget(save)

        self._load()
        avail = (parent.screen() if parent else QApplication.primaryScreen()).availableGeometry()
        dialog_w = min(900, int(avail.width() * 0.92))
        dialog_h = min(int(avail.height() * 0.85), 680)
        self.resize(dialog_w, dialog_h)

    # ------------------------------------------------------------ 불러오기
    def _load(self):
        d = self.data
        self.name_edit.setText(d.name)
        self.colors.set_current(d.color)
        self.icon_colors.set_current(d.icon_color or "auto")
        self.action.set_value(d.action_type if d.action_type != "none" else "url", d.action_data)
        self.toggle.setChecked(d.toggle)
        self.off_action.set_value(d.off_action_type, d.off_action_data)
        self.hold_action.set_value(d.hold_action_type, d.hold_action_data)
        span = (d.span_cols, d.span_rows)
        self.span_tabs.setCurrentIndex(self.SPANS.index(span) if span in self.SPANS else 0, animate=False)
        self.off_box.setVisible(d.toggle)
        self.clear_btn.setVisible(not d.is_empty())
        if d.is_empty() and not d.icon:
            self.icon_value = ""
        self.picker.show_for(self.icon_value)
        self._sync_toggle_hint()
        self._update_preview()
        self._initial_data = self.result_data().clone()

    def load_button(self, data: DeckButtonData, in_folder: bool = False):
        """다른 버튼을 편집하도록 창의 내용을 교체합니다."""
        self.data = data
        self.in_folder = in_folder
        self.cleared = False
        self.icon_value = data.icon
        self._manual_icon = bool(data.icon) and not self._is_default_icon(data.icon)
        self._load()

    def update_button_id(self, new_id: str, new_row: int, new_col: int):
        """버튼을 끌어서 위치를 바꿨을 때 대상 id와 행/열을 갱신합니다."""
        self.data.id = new_id
        self.data.row = new_row
        self.data.col = new_col
        if getattr(self, "_initial_data", None) is not None:
            self._initial_data.id = new_id
            self._initial_data.row = new_row
            self._initial_data.col = new_col

    def has_unsaved_changes(self) -> bool:
        """사용자가 내용을 수정했는지 확인합니다."""
        if self.cleared:
            return True
        init = getattr(self, "_initial_data", None)
        if init is None:
            return False
        cur = self.result_data()
        attrs = [
            "name", "icon", "action_type", "action_data", "toggle",
            "off_action_type", "off_action_data", "hold_action_type", "hold_action_data",
            "span_cols", "span_rows", "color", "icon_color"
        ]
        return any(getattr(init, a) != getattr(cur, a) for a in attrs)

    def _sync_toggle_hint(self):
        on = self.toggle.isChecked()
        self.toggle_hint.setVisible(on)
        if on:
            act_type = self.action.get_type()
            if act_type in ("program", "folder"):
                self.toggle_hint.setText("켜져 있으면 불이 들어오고, 다시 누르면 닫아요")
            else:
                self.toggle_hint.setText("누를 때마다 불이 켜지고 꺼져요")

    def _on_toggle(self, on):
        self.off_box.setVisible(on)
        if on:
            cur_off = self.off_action.get_type()
            if not cur_off or cur_off == "none":
                act_type = self.action.get_type()
                if act_type in ("program", "folder"):
                    self.off_action.set_value("close", "")
        self._sync_toggle_hint()
        self._update_preview()

    def _set_icon(self, icon: str, manual: bool = True):
        self._manual_icon = manual
        self.icon_value = icon
        self.picker.theme_grid.set_current(icon)
        self.picker.emoji.set_current(icon)
        self._update_preview()

    def _on_action_changed(self, *_):
        self._sync_toggle_hint()
        if self.toggle.isChecked():
            act_type = self.action.get_type()
            cur_off = self.off_action.get_type()
            if cur_off == "close" and act_type not in ("program", "folder"):
                self.off_action.set_value("none", "")
            elif cur_off in ("none", "") and act_type in ("program", "folder"):
                self.off_action.set_value("close", "")
        # 아이콘을 직접 고르지 않았다면 동작에 맞는 테마 아이콘으로 따라 바꿔 줌
        if self._icon_is_auto():
            t, data = self.action.value()
            self.icon_value = ""
            self.picker.theme_grid.set_current(icons.default_icon_for(t, data))
        self._update_preview()

    def _icon_is_auto(self) -> bool:
        return not self._manual_icon or not (self.icon_value or "").strip()

    @staticmethod
    def _is_default_icon(cur: str) -> bool:
        defaults = {icons.PREFIX + n for n in icons.ACTION_DEFAULT_ICONS.values()}
        defaults |= {icons.PREFIX + n for n in icons.MEDIA_DEFAULT_ICONS.values()}
        return cur in defaults

    # ------------------------------------------------------------ 결과
    def result_data(self) -> DeckButtonData:
        a_type, a_data = self.action.value()
        o_type, o_data = self.off_action.value()
        name = self.name_edit.text().strip() or self._auto_name(a_type, a_data)
        icon = (self.icon_value or "").strip()
        if os.path.isabs(icon) and os.path.isfile(icon):
            icon = paths.import_icon_file(icon)
        if not icon or self._icon_is_auto():
            icon = icons.default_icon_for(a_type, a_data)
        on = self.toggle.isChecked()
        h_type, h_data = self.hold_action.value()
        sc, sr = self.SPANS[self.span_tabs.index]
        return DeckButtonData(
            span_cols=sc, span_rows=sr,
            hold_action_type=h_type if h_data else "none", hold_action_data=h_data if h_data else "",
            id=self.data.id, name=name, icon=icon, action_type=a_type, action_data=a_data,
            row=self.data.row, col=self.data.col, color=self.colors.current,
            icon_color=self.icon_colors.current, toggle=on,
            toggle_on=self.data.toggle_on if on else False,
            off_action_type=o_type if on else "none",
            off_action_data=o_data if on else "",
        )

    @staticmethod
    def _auto_name(t, data) -> str:
        if not data and t != "group":
            return ""
        if t == "url":
            text = data if "://" in data else "https://" + data
            host = (urlparse(text).hostname or data).replace("www.", "")
            return host.split(".")[0].capitalize()
        if t in ("program", "file", "folder"):
            base = os.path.basename(data.strip("\"'").rstrip("\\/")) or data
            return os.path.splitext(base)[0][:12]
        if t == "shortcut":
            return data.replace(" + ", "+")[:14]
        if t == "media":
            return ShortcutManager.media_label(data).split(" ", 1)[-1][:10]
        if t == "macro":
            return "연속 동작"
        if t == "group":
            return "묶음"
        if t == "info":
            return ""
        if t == "timer":
            from core.timer_manager import parse_timer, format_seconds
            cfg = parse_timer(data)
            return "스톱워치" if cfg["mode"] == "stopwatch" else format_seconds(cfg["seconds"]) + " 타이머"
        return ""

    def _update_preview(self, *_):
        d = self.result_data()
        if d.action_type == "info":
            from core.system_info import read_info
            self.preview.set_info(read_info(d.action_data))
        elif d.action_type == "timer":
            self.preview.set_timer_view(None)
        self.preview.update_data(d)

    # ------------------------------------------------------------ 아이콘 가져오기
    def _auto_icon(self):
        t, data = self.action.value()
        self._set_icon(icons.default_icon_for(t, data), manual=False)
        self.picker.tabs.setCurrentIndex(0)

    def _fetch_icon(self, kind: str):
        t, data = self.action.value()
        if kind == "file":
            path = (data or "").strip("\"'")
            if t == "program" and path and not os.path.exists(path):
                import shutil
                path = shutil.which(path) or path
            got = extract_file_icon(path) if t in ("program", "file", "folder") else ""
            if got:
                self._set_icon(got)
                self.picker.status.setText("프로그램 아이콘을 가져왔어요.")
            else:
                self.picker.status.setText("먼저 ‘누르면 할 일’에서 프로그램·파일·폴더를 골라 주세요.")
        else:
            if t == "url" and data and self.fetcher.fetch(data):
                self.picker.status.setText("사이트 아이콘을 가져오는 중…")
            else:
                self.picker.status.setText("먼저 ‘누르면 할 일’에서 웹 주소를 적어 주세요.")

    def _on_favicon(self, path):
        if path:
            self._set_icon(path)
            self.picker.status.setText("사이트 아이콘을 가져왔어요.")
        else:
            self.picker.status.setText("사이트 아이콘을 가져오지 못했어요.")

    # ------------------------------------------------------------ 버튼
    def _on_clear(self):
        self.cleared = True
        self.accept()

    def _on_save(self):
        t, data = self.action.value()
        if t not in ("group", "info", "timer") and not data:
            names = {"url": "웹 주소", "program": "프로그램", "file": "파일", "folder": "폴더",
                     "shortcut": "단축키", "media": "미디어 동작", "macro": "연속 동작 순서"}
            inform(self, "내용이 비어 있어요", f"{names.get(t, '동작')}을(를) 정해 주세요.")
            return
        ht, hd = self.hold_action.value()
        if ht != "none" and not hd:
            inform(self, "내용이 비어 있어요", "길게 누르면 할 일을 정하거나 ‘아무것도 안 함’으로 바꿔 주세요.")
            return
        if self.toggle.isChecked():
            ot, od = self.off_action.value()
            if ot != "none" and not od:
                inform(self, "내용이 비어 있어요", "켜진 상태에서 할 일을 정하거나 ‘아무것도 안 함’으로 바꿔 주세요.")
                return
        self.accept()
