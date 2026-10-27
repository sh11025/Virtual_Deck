"""
메인 덱 창
화면에 떠 있는 유리 덱입니다.

주요 동작
- 눌러도 포커스를 빼앗지 않음 → 단축키가 지금 쓰는 프로그램에 바로 전달됨
- 덱 뒤 화면이 흐리게 비치는 유리 배경
- 우클릭 메뉴(편집, 복사, 붙여넣기, 비우기, 되돌리기)
- 실행 결과 알림, 버튼 반짝임/흔들림
- 화면 가장자리에 자석처럼 붙기, 안 쓸 때 흐려지기
- 전역 단축키로 숨기기/보이기, 시스템 트레이
- 버튼 묶음(폴더 버튼), 켜기/끄기 버튼, 매크로 진행 표시와 멈추기
"""

from typing import Dict, List, Optional

from PySide6.QtCore import (
    Qt, QTimer, QPoint, QPointF, QRect, QRectF, QSize, QPropertyAnimation, QEasingCurve,
)
from PySide6.QtGui import QPainter, QColor, QFont, QAction, QCursor, QFontMetrics
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QApplication,
    QSystemTrayIcon, QSizePolicy, QGraphicsOpacityEffect,
)

from core import win32
from core.action_executor import ActionExecutor
from core.app_detector import AppDetector
from core.macro_manager import MacroRunner
from core.shortcut_manager import ShortcutManager
from core.system_integration import GlobalHotkey, set_autostart, is_autostart_enabled
from models.button_model import DeckButtonData
from models.config_model import AppConfig
from models.profile_model import DeckProfile
from services.storage_service import StorageService
from ui import theme
from ui.theme import T
from ui.app_icon import make_app_icon
from ui.backdrop import ScreenGrabber, compose_background
from ui.deck_button import DeckButtonWidget
from ui.glass import paint_glass, paint_glass_under, soft_shadow, rounded_path, draw_icon, with_alpha
from ui.toast import Toast
from ui.widgets import GlassButton, glass_menu, menu_icon, ask

MARGIN = 16          # 창 가장자리 그림자 자리 (Windows 흐림 모드에서는 0)
PANEL_RADIUS = 26    # 덱 모서리 둥글기 (Windows 흐림 모드에서는 Windows 11 모서리에 맞춰 8)
SNAP_DISTANCE = 18


class DeckPanel(QWidget):
    """덱 본체 유리판. 배경 그림을 가지고 있어 안쪽 버튼들이 비춰 볼 수 있습니다."""

    def __init__(self, owner: "MainWindow"):
        super().__init__(owner)
        self.owner = owner
        self._bg = None
        self.setAttribute(Qt.WA_TranslucentBackground, True)

    def backdrop_pixmap(self):
        return self._bg

    def rebuild_background(self):
        if self.width() < 4:
            return
        offset = QPointF(self.mapTo(self.owner, QPoint(0, 0)))
        self._bg = compose_background(self.owner.config, self.size(), self.devicePixelRatioF(),
                                      self.owner.grabber.pixmap, offset,
                                      grab_rect=self.owner.grabber.grab_rect,
                                      window_geo=self.owner.geometry())
        self.update()
        for w in self.findChildren(QWidget):
            w.update()

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self.rebuild_background()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(0.5, 0.5, -0.5, -0.5)
        radius = self.owner.panel_radius
        clear = self.owner.config.bg_type == "clear"
        path = rounded_path(rect, radius)
        p.save()
        if not clear:
            p.setClipPath(path)
            if self._bg is not None:
                p.drawPixmap(rect, self._bg, QRectF(self._bg.rect()))
        # 버튼들의 그림자와 빛을 여기서 한꺼번에 그림 (버튼 사이가 좁아도 잘리지 않게)
        for w in self.owner.button_widgets.values():
            params = w.under_params()
            if params is None:
                continue
            offset = QPointF(w.mapTo(self, QPoint(0, 0)))
            r = params.pop("rect").translated(offset)
            paint_glass_under(p, r, **params)
        p.restore()
        if clear:
            return   # 투명 (버튼만): 판의 테두리·반사광은 그리지 않음
        paint_glass(p, rect, radius, fill=0.0, shadow=False, highlight=0.32, rainbow=1.0)


class DragHandle(QWidget):
    """위쪽 메뉴 맨 왼쪽의 끄는 손잡이 (점 6개 ⠿). 어디서든 버튼판을 끌어 이동할 수 있습니다."""

    def __init__(self, owner: "MainWindow", parent=None):
        super().__init__(parent)
        self.owner = owner
        self.setFixedSize(18, 28)
        self.setCursor(Qt.SizeAllCursor)
        self.setToolTip("끌어서 이동")

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.setPen(Qt.NoPen)
        color = with_alpha(QColor(T().text), 0.55 if self.underMouse() else 0.35)
        p.setBrush(color)
        cx = self.width() / 2
        cy = self.height() / 2
        r = 1.6
        for dx in (-3.5, 3.5):
            for dy in (-6, 0, 6):
                p.drawEllipse(QPointF(cx + dx, cy + dy), r, r)

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.owner.mousePressEvent(e)

    def mouseMoveEvent(self, e):
        self.owner.mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        self.owner.mouseReleaseEvent(e)


class HeaderBar(QWidget):
    """버튼판 위에 떠 있는 별도 유리 알약 위젯"""

    def __init__(self, owner: "MainWindow"):
        super().__init__(owner)
        self.owner = owner
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedHeight(36)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        radius = rect.height() / 2
        dark = T().dark
        soft_shadow(p, rect, radius, QColor(0, 0, 0, 100) if dark else QColor(30, 50, 90, 50),
                    spread=4.0, offset_y=2)
        paint_glass(p, rect, radius, fill=0.25 if not dark else 0.35, shadow=False, highlight=0.25)


class ProfileButton(GlassButton):
    """프로필 이름 + ▾ 표시"""

    def __init__(self, parent=None):
        super().__init__("", parent=parent)
        self.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Fixed)
        self.setMinimumWidth(70)
        self.draw_text = False

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        w = max(70, min(140, fm.horizontalAdvance(self.text()) + 46))
        return QSize(w, 26 + 7)

    def paintEvent(self, e):
        # 글자는 아래에서 직접 그리므로 기본 글자 그리기를 끕니다(paintEvent 안 setText 는 재그리기를 유발).
        text = self.text()
        super().paintEvent(e)
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        l, t, r, b = self.MARGIN
        rect = QRectF(l, t, self.width() - l - r, self.height() - t - b)
        # 상태 점
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(theme.TOGGLE_ON_COLOR))
        p.drawEllipse(QPointF(rect.left() + 12, rect.center().y()), 3.5, 3.5)
        p.setFont(self.font())
        p.setPen(QColor(T().text))
        fm = QFontMetrics(self.font())
        tr = QRectF(rect.left() + 20, rect.top(), max(10, rect.width() - 38), rect.height())
        p.drawText(tr, Qt.AlignVCenter | Qt.AlignLeft, fm.elidedText(text, Qt.ElideRight, int(tr.width())))
        draw_icon(p, "chevron", QRectF(rect.right() - 18, rect.center().y() - 5, 10, 10), QColor(T().text_dim))


class MainWindow(QWidget):
    def __init__(self, storage_service: StorageService):
        super().__init__(None)
        self.storage = storage_service
        self.config, self.profiles, self.current_profile_id = self.storage.load_data()
        theme.set_theme(self.config.theme)
        QApplication.instance().setStyleSheet(theme.get_qss())
        if win32.IS_WINDOWS:
            self.config.auto_start = is_autostart_enabled()

        self.folder_id: Optional[str] = None          # 열려 있는 버튼 묶음
        self.button_widgets: Dict[str, DeckButtonWidget] = {}
        self.undo_stack: List[tuple] = []
        self.clipboard: Optional[dict] = None
        self.last_detected_key = None
        self.margin = MARGIN
        self.panel_radius = PANEL_RADIUS
        self._drag_offset: Optional[QPoint] = None
        self._dialog_open = set()
        self._menu_open = 0
        self._manual_hold_exe: Optional[str] = None
        self._last_external_exe: str = ""
        self._settings_dlg = None
        self._editor_dlg = None
        self._capture_ok = False
        self._native_ready = False

        self._setup_window()
        self.grabber = ScreenGrabber(self, self)
        self.grabber.updated.connect(lambda: self.panel.rebuild_background())
        self._build_ui()
        self._init_tray()
        self.toast = Toast(self)

        self.hotkey = GlobalHotkey(self)
        self.hotkey.activated.connect(self.toggle_visibility)

        from core.timer_manager import TimerManager
        self.timers = TimerManager(self)
        self.timers.finished.connect(self._on_timer_finished)

        runner = MacroRunner.instance()
        runner.started.connect(self._on_macro_started)
        runner.finished.connect(self._on_macro_finished)

        self._fade_anim = QPropertyAnimation(self, b"windowOpacity", self)
        self._fade_anim.setDuration(380)
        self._fade_anim.setEasingCurve(QEasingCurve.OutCubic)
        self._fade_timer = QTimer(self)
        self._fade_timer.setSingleShot(True)
        self._fade_timer.timeout.connect(self._fade_out)

        self.tracker = QTimer(self)
        self.tracker.setInterval(400)
        self.tracker.timeout.connect(self._on_tracker_tick)
        self.tracker.start()

        # 1초마다: 정보 버튼 값 갱신 + 음소거 등 실제 상태 맞추기
        self.live_timer = QTimer(self)
        self.live_timer.setInterval(1000)
        self.live_timer.timeout.connect(self._on_live_tick)
        self.live_timer.start()

        # 절전: 마우스가 덱을 떠나고 잠시 뒤 뒤 비침 새로고침을 천천히
        self._idle_timer = QTimer(self)
        self._idle_timer.setSingleShot(True)
        self._idle_timer.timeout.connect(self._enter_idle)

        self._rebuild_grid()
        self._restore_position()
        self.setWindowOpacity(self.config.opacity)

    # ================================================================ 창 설정
    def _setup_window(self):
        flags = Qt.Tool | Qt.FramelessWindowHint | Qt.WindowDoesNotAcceptFocus | Qt.NoDropShadowWindowHint
        if self.config.always_on_top:
            flags |= Qt.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setWindowTitle("Virtual Deck")
        self.setWindowIcon(make_app_icon())

    def showEvent(self, e):
        super().showEvent(e)
        QTimer.singleShot(0, self._after_native_ready)

    def _after_native_ready(self):
        """창이 실제로 만들어진 뒤 Windows 설정을 적용합니다."""
        hwnd = int(self.winId())
        ShortcutManager.add_own_hwnd(hwnd)
        AppDetector.add_own_hwnd(hwnd)
        ShortcutManager.add_own_hwnd(int(self.toast.winId()))
        win32.make_no_activate(hwnd)
        if self.config.always_on_top:
            win32.keep_topmost(hwnd, True)
        self._apply_background_mode()
        self._apply_hotkey()
        if not self._native_ready:
            QTimer.singleShot(1500, self._check_pycaw)
        self._native_ready = True

    # ================================================================ 추가 부품(pycaw) 확인
    def _check_pycaw(self):
        from core import dependencies as dep
        if dep.has_pycaw():
            return
        if dep.can_install():
            if not self.config.pycaw_prompt:
                return
            if ask(self, "추가 부품 설치",
                   "음소거 상태 맞추기 · 마이크 음소거 · 볼륨 % 기능에 필요한 'pycaw'가 설치되어 있지 않아요.\n"
                   "지금 설치할까요? (인터넷 연결 필요, 1분 이내)", ok_text="설치하기", cancel_text="나중에"):
                self.install_pycaw()
            else:
                self.config.pycaw_prompt = False
                self.save()
                self.show_toast("설정 → 동작에서 언제든 설치할 수 있어요", "info", 3200)
        else:
            self.show_toast("이 EXE 에는 pycaw 가 빠져 있어요. build_exe.py 로 다시 만들면 들어가요.", "info", 4000)

    def install_pycaw(self):
        from core.dependencies import PipInstaller
        if getattr(self, "_installer", None) is None:
            self._installer = PipInstaller(self)
            self._installer.finished.connect(self._on_pycaw_installed)
        if self._installer.install():
            self.show_toast("pycaw 설치 중… 끝나면 알려 드릴게요", "info", 4000)

    def _on_pycaw_installed(self, ok: bool, msg: str):
        if ok:
            self.config.pycaw_prompt = True
            self.save()
        self.show_toast(msg, "ok" if ok else "error", 4500)

    def _apply_background_mode(self):
        """
        배경 방식에 맞춰 Windows 설정을 바꿉니다.
        - glass: 버튼판 뒤를 직접 찍어서 흐리게 (버튼판은 캡처에서 빠짐)
        - clear: 투명(버튼만) - 화면 캡처 안 함 (캡처·화면 공유에도 보임)
        """
        mode = self.config.bg_type
        hwnd = int(self.winId())
        want_glass = mode == "glass"
        self._capture_ok = win32.set_exclude_from_capture(hwnd, want_glass) if want_glass else False
        if not want_glass:
            win32.set_exclude_from_capture(hwnd, False)
        # 대화상자가 열려 있으면 일시정지를 유지하고, 아니면 해제합니다(직접 대입 금지).
        self.grabber.pause(bool(self._dialog_open))
        self.grabber.set_enabled(want_glass and self._capture_ok, self.config.glass_blur)
        if hasattr(self, "act_capture"):
            self.act_capture.setVisible(want_glass)
        if getattr(self, "_capture_timer", None) is not None:
            self._capture_timer.stop()
        self.panel.rebuild_background()
        self.update()

    def _apply_hotkey(self):
        if self.config.hotkey_enabled and self.config.hotkey:
            ok = self.hotkey.register(int(self.winId()), self.config.hotkey)
            if not ok and win32.IS_WINDOWS:
                self.show_toast(f"단축키 {self.config.hotkey} 를 다른 프로그램이 쓰고 있어요.", "error")
        else:
            self.hotkey.unregister()

    # ================================================================ 화면 구성
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(self.margin, self.margin, self.margin, self.margin)
        outer.setSpacing(6)

        # 위쪽 메뉴 (떠 있는 유리 알약)
        self.header_bar = HeaderBar(self)
        sp_head = self.header_bar.sizePolicy()
        sp_head.setRetainSizeWhenHidden(True)
        self.header_bar.setSizePolicy(sp_head)
        head = QHBoxLayout(self.header_bar)
        head.setContentsMargins(6, 4, 6, 4)
        head.setSpacing(3)

        self.drag_handle = DragHandle(self, self.header_bar)
        head.addWidget(self.drag_handle)

        self.back_btn = GlassButton(icon_name="back", square=True, size=26)
        self.back_btn.setToolTip("묶음에서 나가기")
        self.back_btn.clicked.connect(self._leave_folder)
        head.addWidget(self.back_btn)

        self.profile_btn = ProfileButton(self.header_bar)
        self.profile_btn.setToolTip("프로필 바꾸기")
        self.profile_btn.clicked.connect(self._show_profile_menu)
        head.addWidget(self.profile_btn, 1)

        self.folder_label = QLabel()
        self.folder_label.setFont(theme.ui_font(13, QFont.Bold))
        head.addWidget(self.folder_label, 1)

        def icon_btn(name, tip, slot):
            b = GlassButton(icon_name=name, square=True, size=26)
            b.setToolTip(tip)
            b.clicked.connect(slot)
            head.addWidget(b)
            return b

        self.profiles_btn = icon_btn("list", "프로필 관리", self._open_profile_manager)
        self.settings_btn = icon_btn("gear", "환경설정", self._open_settings)
        self.min_btn = icon_btn("minus", "트레이로 숨기기", self.hide_to_tray)
        self.close_btn = icon_btn("close", "종료", self.quit_app)

        self.header_effect = QGraphicsOpacityEffect(self.header_bar)
        self.header_bar.setGraphicsEffect(self.header_effect)
        self.header_effect.setOpacity(0.0)
        self.header_bar.hide()

        self.header_anim = QPropertyAnimation(self.header_effect, b"opacity", self)
        self.header_anim.finished.connect(self._on_header_anim_finished)
        self.header_hide_timer = QTimer(self)
        self.header_hide_timer.setSingleShot(True)
        self.header_hide_timer.timeout.connect(self._hide_header_fade)

        outer.addWidget(self.header_bar, 0, Qt.AlignHCenter)

        # 버튼판 (DeckPanel)
        self.panel = DeckPanel(self)
        self.panel_layout = QVBoxLayout(self.panel)
        self.panel_layout.setContentsMargins(12, 12, 12, 12)
        self.panel_layout.setSpacing(0)

        self.grid_host = QWidget()
        self.grid_host.setAttribute(Qt.WA_TranslucentBackground, True)
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 0, 0, 0)
        self.panel_layout.addWidget(self.grid_host, 0, Qt.AlignCenter)

        outer.addWidget(self.panel, 0, Qt.AlignHCenter)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        if self.margin <= 0 or self.config.bg_type == "clear":
            return
        rect = QRectF(self.panel.geometry())
        soft_shadow(p, rect, self.panel_radius, QColor(0, 0, 0, 120) if T().dark else QColor(30, 50, 90, 75),
                    spread=self.margin * 0.8, offset_y=4)

    # ================================================================ 데이터 도우미
    @property
    def current_profile(self) -> DeckProfile:
        if self.current_profile_id not in self.profiles:
            self.current_profile_id = next(iter(self.profiles))
        return self.profiles[self.current_profile_id]

    def current_buttons(self) -> Dict[str, DeckButtonData]:
        prof = self.current_profile
        if self.folder_id and self.folder_id in prof.buttons:
            group = prof.buttons[self.folder_id]
            if group.action_type == "group":
                self.storage._fill(group.children, self.config.rows, self.config.cols)
                return group.children
        self.folder_id = None
        return prof.buttons

    def _macro_key(self, btn_id: str) -> str:
        return f"{self.current_profile_id}/{self.folder_id or ''}/{btn_id}"

    def save(self):
        self.storage.save_data(self.config, self.profiles, self.current_profile_id)

    # ================================================================ 그리드
    def _rebuild_grid(self):
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self.button_widgets.clear()
        self.storage.ensure_grid(self.current_profile, self.config.rows, self.config.cols)
        buttons = self.current_buttons()
        cfg = self.config
        self.grid.setSpacing(cfg.spacing)
        runner = MacroRunner.instance()
        covered = set()   # 큰 버튼에 가려진 칸
        for r in range(cfg.rows):
            for c in range(cfg.cols):
                if (r, c) in covered:
                    continue
                bid = DeckButtonData.make_id(r, c)
                data = buttons.get(bid) or DeckButtonData(id=bid, row=r, col=c)
                buttons[bid] = data
                sc, sr = self._fit_span(data, r, c, covered)
                for rr in range(r, r + sr):
                    for cc in range(c, c + sc):
                        covered.add((rr, cc))
                w = DeckButtonWidget(data, cfg.button_size, cfg.show_labels, cfg.icon_style, self.grid_host)
                w.under_host = self.panel
                w.hold_ms = cfg.hold_ms
                w.set_span(sc, sr, cfg.spacing)
                w.clicked.connect(self._handle_click)
                w.long_pressed.connect(self._handle_long_press)
                w.edit_requested.connect(self._edit_button)
                w.context_requested.connect(self._show_context_menu)
                w.swapped.connect(self._swap_buttons)
                if runner.is_running(self._macro_key(bid)):
                    w.set_running(True)
                self.grid.addWidget(w, r, c, sr, sc)
                self.button_widgets[bid] = w
        self._on_live_tick()
        self._update_header()
        self._adjust_size()

    def _fit_span(self, data: DeckButtonData, r: int, c: int, covered: set):
        """큰 버튼이 그리드 밖으로 나가거나 다른 큰 버튼과 겹치면 줄여서 맞춥니다."""
        if data.is_empty():
            return 1, 1
        sc = min(data.span_cols, self.config.cols - c)
        sr = min(data.span_rows, self.config.rows - r)
        while sc > 1 and any((rr, c + sc - 1) in covered for rr in range(r, r + sr)):
            sc -= 1
        while sr > 1 and any((r + sr - 1, cc) in covered for cc in range(c, c + sc)):
            sr -= 1
        return max(1, sc), max(1, sr)

    def _adjust_size(self):
        cfg = self.config
        grid_w = cfg.cols * cfg.button_size + (cfg.cols - 1) * cfg.spacing
        grid_h = cfg.rows * cfg.button_size + (cfg.rows - 1) * cfg.spacing
        self.grid_host.setFixedSize(grid_w, grid_h)

        pad = max(6, round(cfg.button_size * 0.09))
        self.panel_layout.setContentsMargins(pad, pad, pad, pad)
        panel_w = grid_w + pad * 2
        panel_h = grid_h + pad * 2
        self.panel.setFixedSize(panel_w, panel_h)

        header_min_w = 210
        header_w = max(header_min_w, min(panel_w, 290))
        self.header_bar.setFixedWidth(header_w)

        total_w = max(panel_w, header_w) + self.margin * 2
        total_h = 36 + 6 + panel_h + self.margin * 2
        self.setFixedSize(total_w, total_h)
        QTimer.singleShot(0, self.panel.rebuild_background)

    def _update_header(self):
        in_folder = self.folder_id is not None
        self.back_btn.setVisible(in_folder)
        self.folder_label.setVisible(in_folder)
        self.profile_btn.setVisible(not in_folder)
        self.profile_btn.setText(self.current_profile.name)
        self.profile_btn.update()
        if in_folder:
            g = self.current_profile.buttons.get(self.folder_id)
            name = (g.name if g and g.name else "버튼 묶음")
            fm = QFontMetrics(self.folder_label.font())
            self.folder_label.setText(fm.elidedText(name, Qt.ElideRight, 150))
            self.header_hide_timer.stop()
            self.header_bar.show()
            self.header_effect.setOpacity(1.0)
        elif self.config.always_show_header:
            self.header_hide_timer.stop()
            self.header_bar.show()
            self.header_effect.setOpacity(1.0)
        else:
            if not self.underMouse():
                self.header_effect.setOpacity(0.0)
                self.header_bar.hide()

    def _hide_header_fade(self):
        if self.config.always_show_header or (self.folder_id is not None) or self.underMouse():
            return
        self.header_anim.stop()
        self.header_anim.setDuration(250)
        self.header_anim.setStartValue(self.header_effect.opacity())
        self.header_anim.setEndValue(0.0)
        self.header_anim.start()

    def _on_header_anim_finished(self):
        if self.header_effect.opacity() <= 0.01 and not self.config.always_show_header and (self.folder_id is None):
            self.header_bar.hide()

    def refresh_button(self, btn_id: str):
        w = self.button_widgets.get(btn_id)
        data = self.current_buttons().get(btn_id)
        if w and data:
            w.update_data(data)

    # ================================================================ 버튼 동작
    def _handle_click(self, btn_id: str):
        buttons = self.current_buttons()
        btn = buttons.get(btn_id)
        if not btn or btn.is_empty():
            return
        if btn.action_type == "group":
            self._enter_folder(btn_id)
            return
        a_type, a_data = btn.action_type, btn.action_data
        widget = self.button_widgets.get(btn_id)

        if btn.toggle and btn.toggle_on:
            if btn.off_action_type not in ("", "none") and (btn.off_action_data or btn.off_action_type == "close"):
                a_type = btn.off_action_type
                a_data = btn.off_action_data or btn.action_data
            else:
                # 불이 켜진 상태에서 눌렀는데 off 동작이 비어 있으면 창 닫기 수행
                if btn.action_type in ("program", "folder"):
                    ok, msg = ActionExecutor.execute("close", btn.action_data)
                    btn.toggle_on = False
                    self.save()
                    if widget:
                        widget.update_data(btn)
                        widget.play_toggle(False)
                    if not ok:
                        self.show_toast(msg, "info")
                    return

        if a_type == "close" and not a_data:
            a_data = btn.action_data

        if a_type == "info":
            if widget:
                widget.flash(True)
            return
        if btn.action_type == "timer":
            self.timers.press(self._macro_key(btn_id))
            self._on_live_tick()
            return
        ok, msg = self._run_action(btn_id, a_type, a_data)
        if ok is None:   # 매크로 멈춤
            return

        if btn.toggle and ok:
            btn.toggle_on = not btn.toggle_on
            self.save()
            if widget:
                widget.update_data(btn)
                widget.play_toggle(btn.toggle_on)
        if widget and (a_type != "macro" or not ok):
            widget.flash(ok)
        if not ok:
            self.show_toast(msg, "error")

    def _run_action(self, btn_id: str, a_type: str, a_data: str, key_suffix: str = ""):
        """동작 하나 실행. 실행 중인 매크로를 다시 누른 경우 (None, '') — 멈춤"""
        if a_type == "macro":
            runner = MacroRunner.instance()
            key = self._macro_key(btn_id) + key_suffix
            if runner.is_running(key):
                runner.stop(key)
                return None, ""
            return runner.run(key, a_data)
        return ActionExecutor.execute(a_type, a_data)

    def _handle_long_press(self, btn_id: str):
        btn = self.current_buttons().get(btn_id)
        if btn and btn.action_type == "timer" and not btn.has_hold():
            self.timers.reset(self._macro_key(btn_id))   # 타이머: 길게 누르면 처음으로
            self._on_live_tick()
            self.show_toast("타이머를 처음으로 돌렸어요", "info", 1400)
            return
        if not btn or not btn.has_hold():
            return
        widget = self.button_widgets.get(btn_id)
        ok, msg = self._run_action(btn_id, btn.hold_action_type, btn.hold_action_data, "#hold")
        if ok is None:
            return
        if widget and (btn.hold_action_type != "macro" or not ok):
            widget.flash(ok)
        if not ok:
            self.show_toast(msg, "error")

    # ================================================================ 1초마다: 정보 버튼 · 실제 상태 맞추기
    def _on_live_tick(self):
        self._live_tick_count = getattr(self, "_live_tick_count", 0) + 1
        # 대화상자나 메뉴가 열려 있으면 덱이 대화상자/메뉴 위로 올라오지 않도록 재적용을 건너뜀
        if (self.config.always_on_top and self.isVisible() and self._native_ready
                and not self._dialog_open and not self._menu_open):
            win32.keep_topmost(int(self.winId()), True)
        # 타이머는 덱을 숨겨도 계속 흘러가야 하므로 먼저 확인
        self.timers.tick(self._timer_data_for_key)
        self.live_timer.setInterval(250 if self.timers.any_running() else 1000)
        if not self.isVisible() and self._native_ready:
            return
        from core.system_info import read_info
        from core import audio_state
        changed = False
        for bid, bw in self.button_widgets.items():
            d = bw.button_data
            btn_orig = self.current_buttons().get(bid)
            if d.action_type == "info":
                bw.set_info(read_info(d.action_data))
            elif d.action_type == "timer":
                bw.set_timer_view(self.timers.view(self._macro_key(bid), d.action_data))
            elif (self.config.sync_toggle_state and d.toggle and d.action_type == "media"
                  and d.action_data in ("VolumeMute", "MicMute")):
                actual = audio_state.get_mute("speaker" if d.action_data == "VolumeMute" else "mic")
                if actual is not None and actual != d.toggle_on:
                    d.toggle_on = actual
                    if btn_orig:
                        btn_orig.toggle_on = actual
                    bw.update_data(d)
                    changed = True
            elif self.config.sync_toggle_state and d.toggle and d.action_type in ("program", "folder"):
                if self._live_tick_count % 2 == 0:
                    from core import running_state
                    actual = running_state.is_program_running(d.action_data) if d.action_type == "program" else running_state.is_folder_open(d.action_data)
                    if actual is not None and actual != d.toggle_on:
                        d.toggle_on = actual
                        if btn_orig:
                            btn_orig.toggle_on = actual
                        bw.update_data(d)
                        changed = True
        if changed:
            self.save()

    # ================================================================ 타이머
    def _find_button(self, key: str) -> Optional[DeckButtonData]:
        """'프로필/묶음/버튼' 키로 버튼을 찾습니다."""
        try:
            pid, folder, bid = key.split("/", 2)
        except ValueError:
            return None
        prof = self.profiles.get(pid)
        if prof is None:
            return None
        buttons = prof.buttons
        if folder:
            group = prof.buttons.get(folder)
            if group is None:
                return None
            buttons = group.children
        return buttons.get(bid)

    def _timer_data_for_key(self, key: str):
        btn = self._find_button(key)
        return btn.action_data if btn is not None and btn.action_type == "timer" else None

    def _on_timer_finished(self, key: str):
        from core.timer_manager import parse_timer
        btn = self._find_button(key)
        if btn is None:
            return
        cfg = parse_timer(btn.action_data)
        name = btn.name.strip() or "타이머"
        if cfg.get("sound", True):
            win32.play_alert()
            QTimer.singleShot(900, win32.play_alert)
            QTimer.singleShot(1800, win32.play_alert)
        if self.isVisible():
            self.show_toast(f"⏱ {name} 끝!", "info", 5000)
        else:
            self.tray.showMessage("Virtual Deck", f"⏱ {name} 끝!", QSystemTrayIcon.Information, 5000)
        then_type, then_data = cfg.get("then_type", "none"), cfg.get("then_data", "")
        if then_type not in ("", "none") and then_data:
            bid = key.split("/", 2)[2]
            ok, msg = self._run_action(bid, then_type, then_data, "#timer") if key.startswith(
                f"{self.current_profile_id}/{self.folder_id or ''}/") else ActionExecutor.execute(then_type, then_data)
            if ok is False:
                self.show_toast(msg, "error")
        self._on_live_tick()

    # ================================================================ 절전
    def _enter_idle(self):
        if self.config.power_save and not self.underMouse():
            self.grabber.set_interval(1600)

    def _on_macro_started(self, key: str):
        bid = self._widget_id_for_key(key)
        if bid:
            self.button_widgets[bid].set_running(True)

    def _on_macro_finished(self, key: str, ok: bool, msg: str):
        bid = self._widget_id_for_key(key)
        if bid:
            w = self.button_widgets[bid]
            w.set_running(False)
            w.flash(ok)
        if not ok:
            self.show_toast(msg, "error" if "멈췄" not in msg else "info")

    def _widget_id_for_key(self, key: str) -> Optional[str]:
        prefix = f"{self.current_profile_id}/{self.folder_id or ''}/"
        if key.startswith(prefix):
            bid = key[len(prefix):].replace("#hold", "")
            return bid if bid in self.button_widgets else None
        return None

    # ================================================================ 묶음(폴더 버튼)
    def _enter_folder(self, btn_id: str):
        self.folder_id = btn_id
        self._rebuild_grid()

    def _leave_folder(self):
        self.folder_id = None
        self._rebuild_grid()

    # ================================================================ 편집 / 메뉴
    def push_undo(self, all_profiles: bool = False):
        if all_profiles:   # 모든 프로필이 바뀌는 작업 (아이콘 일괄 변환, 칸 줄이기)
            snap = {pid: p.to_dict() for pid, p in self.profiles.items()}
            self.undo_stack.append(("__all__", snap, None))
        else:
            self.undo_stack.append((self.current_profile_id, self.current_profile.to_dict(), self.folder_id))
        if len(self.undo_stack) > 40:
            self.undo_stack.pop(0)

    def undo(self):
        while self.undo_stack:
            pid, data, folder = self.undo_stack.pop()
            if pid == "__all__":
                self.profiles = {k: DeckProfile.from_dict(v) for k, v in data.items()}
                for prof in self.profiles.values():
                    self.storage.ensure_grid(prof, self.config.rows, self.config.cols)
                self.folder_id = None
                self.save()
                self._rebuild_grid()
                self.show_toast("되돌렸어요", "info", 1400)
                return
            if pid in self.profiles:
                self.profiles[pid] = DeckProfile.from_dict(data)
                self.current_profile_id = pid
                self.folder_id = folder
                self.save()
                self._rebuild_grid()
                self.show_toast("되돌렸어요", "info", 1400)
                return

    def _register_dialog(self, dlg: QWidget):
        """열린 대화상자를 추적하고, 자동 프로필 전환/흐림을 일시정지합니다."""
        self._dialog_open.add(dlg)
        if hasattr(self, "grabber"):
            self.grabber.pause(True)
        dlg.destroyed.connect(lambda *_: self._unregister_dialog(dlg))
        if hasattr(dlg, "finished"):
            dlg.finished.connect(lambda *_: self._unregister_dialog(dlg))

    def _unregister_dialog(self, dlg: QWidget):
        """대화상자가 닫혔을 때 추적에서 빼고 일시정지를 해제합니다."""
        try:
            self._dialog_open.discard(dlg)
            if self._dialog_open or not hasattr(self, "grabber"):
                return
            # '캡처할 때 보이게(1분)' 중에는 재촬영하면 자기 자신이 찍히므로 일시정지를 유지합니다.
            timer = getattr(self, "_capture_timer", None)
            if timer is not None and timer.isActive():
                return
            # 트레이로 숨은 동안에도 일시정지 유지
            if not self.isVisible():
                return
            self.grabber.pause(False)
        except RuntimeError:
            return

    def _position_dialog_beside(self, dlg: QWidget):
        """대화상자를 버튼판 옆(오른쪽 → 왼쪽 → 아래)에 적절히 배치합니다."""
        screen = self.screen() or QApplication.primaryScreen()
        avail = screen.availableGeometry() if screen else QRect(0, 0, 1920, 1080)
        mw_geo = self.geometry()
        dlg_w = dlg.width()
        dlg_h = dlg.height()
        gap = 12

        # 1. 오른쪽
        x = mw_geo.right() + gap
        y = mw_geo.top()
        if x + dlg_w > avail.right():
            # 2. 왼쪽
            x = mw_geo.left() - gap - dlg_w
            if x < avail.left():
                # 3. 아래
                x = mw_geo.left()
                y = mw_geo.bottom() + gap

        # 화면 밖으로 벗어나지 않게 보정
        x = max(avail.left(), min(x, avail.right() - dlg_w))
        y = max(avail.top(), min(y, avail.bottom() - dlg_h))
        dlg.move(x, y)

    def _edit_button(self, btn_id: str):
        from ui.button_editor_dialog import ButtonEditorDialog
        from ui.widgets import ask_save_changes
        buttons = self.current_buttons()
        target = buttons.get(btn_id)
        if target is None:
            return

        if self._editor_dlg and self._editor_dlg.isVisible():
            if self._editor_dlg.data.id == btn_id:
                self._editor_dlg.raise_()
                self._editor_dlg.activateWindow()
                return

            if self._editor_dlg.has_unsaved_changes():
                choice = ask_save_changes(self, "저장할까요?",
                                          "바꾼 내용이 있습니다. 저장하고 다른 버튼을 편집할까요?")
                if choice == "save":
                    self._save_editor_result(self._editor_dlg)
                elif choice == "cancel":
                    return
                # choice == "discard"면 저장하지 않고 새 버튼 로드

            self._editor_dlg.load_button(target.clone(), in_folder=self.folder_id is not None)
            self._editor_dlg.raise_()
            self._editor_dlg.activateWindow()
            return

        dlg = ButtonEditorDialog(target.clone(), in_folder=self.folder_id is not None,
                                 icon_style=self.config.icon_style, parent=self, modeless=True)
        self._editor_dlg = dlg
        self._register_dialog(dlg)

        def on_accepted():
            self._save_editor_result(dlg)
            self._editor_dlg = None

        def on_rejected():
            self._editor_dlg = None

        dlg.accepted.connect(on_accepted)
        dlg.rejected.connect(on_rejected)
        self._position_dialog_beside(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def _save_editor_result(self, dlg):
        btn_id = dlg.data.id
        buttons = self.current_buttons()
        original = buttons.get(btn_id)
        if original is None:
            return
        self.push_undo()
        if dlg.cleared:
            buttons[btn_id] = DeckButtonData(id=btn_id, row=original.row, col=original.col)
        else:
            new = dlg.result_data()
            new.id, new.row, new.col = btn_id, original.row, original.col
            if new.action_type == "group":
                new.children = original.children if original.action_type == "group" else {}
                self.storage._fill(new.children, self.config.rows, self.config.cols)
            else:
                new.children = {}
            buttons[btn_id] = new
        self.timers.reset(self._macro_key(btn_id))
        self.save()
        self._refresh_after_change(btn_id, original)

    def _refresh_after_change(self, btn_id: str, before: DeckButtonData):
        """큰 버튼이 생기거나 없어지면 칸 배치를 다시 하고, 아니면 버튼 하나만 다시 그립니다."""
        after = self.current_buttons().get(btn_id)
        spans = {(before.span_cols, before.span_rows)}
        if after is not None:
            spans.add((after.span_cols, after.span_rows))
        if spans != {(1, 1)}:
            self._rebuild_grid()
        else:
            self.refresh_button(btn_id)

    def _exec_menu(self, menu, pos):
        self._menu_open += 1
        try:
            menu.setWindowFlag(Qt.WindowStaysOnTopHint, True)
            return menu.exec(pos)
        finally:
            self._menu_open = max(0, self._menu_open - 1)

    def _show_context_menu(self, btn_id: str, pos: QPoint):
        buttons = self.current_buttons()
        btn = buttons.get(btn_id)
        if btn is None:
            return
        menu = glass_menu(self)
        empty = btn.is_empty()
        act_edit = menu.addAction(menu_icon("edit"), "편집…" if not empty else "버튼 만들기…")
        act_open = None
        if btn.action_type == "group":
            act_open = menu.addAction(menu_icon("folder"), "묶음 열기")
        act_timer = None
        if btn.action_type == "timer":
            act_timer = menu.addAction(menu_icon("refresh"), "타이머 처음으로")
        menu.addSeparator()
        act_copy = menu.addAction(menu_icon("copy"), "복사")
        act_copy.setEnabled(not empty)
        act_paste = menu.addAction(menu_icon("paste"), "붙여넣기")
        act_paste.setEnabled(self.clipboard is not None)
        act_clear = menu.addAction(menu_icon("trash"), "비우기")
        act_clear.setEnabled(not empty)
        menu.addSeparator()
        act_undo = menu.addAction(menu_icon("undo"), "되돌리기" + (f"  ({len(self.undo_stack)})" if self.undo_stack else ""))
        act_undo.setEnabled(bool(self.undo_stack))

        chosen = self._exec_menu(menu, pos)
        if chosen is None:
            return
        if chosen == act_edit:
            self._edit_button(btn_id)
        elif chosen == act_open:
            self._enter_folder(btn_id)
        elif chosen == act_timer:
            self.timers.reset(self._macro_key(btn_id))
            self._on_live_tick()
        elif chosen == act_copy:
            self.clipboard = btn.to_dict()
            self.show_toast("버튼을 복사했어요", "info", 1300)
        elif chosen == act_paste and self.clipboard is not None:
            data = DeckButtonData.from_dict(self.clipboard)
            if self.folder_id is not None and data.action_type == "group":
                self.show_toast("묶음 안에는 묶음을 넣을 수 없어요", "error")
                return
            self.push_undo()
            buttons[btn_id] = data.clone(new_id=btn_id, row=btn.row, col=btn.col)
            buttons[btn_id].toggle_on = False
            self.timers.reset(self._macro_key(btn_id))
            self.save()
            self._refresh_after_change(btn_id, btn)
        elif chosen == act_clear:
            self.push_undo()
            buttons[btn_id] = DeckButtonData(id=btn_id, row=btn.row, col=btn.col)
            self.timers.reset(self._macro_key(btn_id))
            self.save()
            self._refresh_after_change(btn_id, btn)
        elif chosen == act_undo:
            self.undo()

    def _swap_buttons(self, src_id: str, dst_id: str):
        buttons = self.current_buttons()
        a, b = buttons.get(src_id), buttons.get(dst_id)
        if a is None or b is None:
            return
        self.push_undo()
        buttons[src_id] = b.clone(new_id=src_id, row=a.row, col=a.col)
        buttons[dst_id] = a.clone(new_id=dst_id, row=b.row, col=b.col)
        ks, kd = self._macro_key(src_id), self._macro_key(dst_id)
        ts, td = self.timers.timers.pop(ks, None), self.timers.timers.pop(kd, None)
        if ts is not None:
            self.timers.timers[kd] = ts
        if td is not None:
            self.timers.timers[ks] = td
        self.save()
        if self._editor_dlg and self._editor_dlg.isVisible():
            if self._editor_dlg.data.id == src_id:
                self._editor_dlg.update_button_id(dst_id, b.row, b.col)
            elif self._editor_dlg.data.id == dst_id:
                self._editor_dlg.update_button_id(src_id, a.row, a.col)
        if (a.span_cols, a.span_rows, b.span_cols, b.span_rows) != (1, 1, 1, 1):
            self._rebuild_grid()
        else:
            self.refresh_button(src_id)
            self.refresh_button(dst_id)

    # ================================================================ 프로필
    def _show_profile_menu(self):
        menu = glass_menu(self)
        for pid, prof in self.profiles.items():
            label = prof.name + (f"   ·  {prof.target_process}" if prof.target_process else "")
            act = menu.addAction(label)
            act.setCheckable(True)
            act.setChecked(pid == self.current_profile_id)
            act.setData(pid)
            if pid == self.current_profile_id:
                act.setIcon(menu_icon("check"))
        menu.addSeparator()
        manage = menu.addAction(menu_icon("list"), "프로필 관리…")
        pos = self.profile_btn.mapToGlobal(QPoint(0, self.profile_btn.height()))
        chosen = self._exec_menu(menu, pos)
        if chosen is None:
            return
        if chosen == manage:
            self._open_profile_manager()
        elif chosen.data():
            self.switch_profile(chosen.data(), manual=True)

    def switch_profile(self, pid: str, manual: bool = False):
        if manual:
            self._manual_hold_exe = (self._last_external_exe or "").lower() or None
        if pid in self.profiles and pid != self.current_profile_id:
            self.current_profile_id = pid
            self.folder_id = None
            self._rebuild_grid()
            self.save()

    def _open_profile_manager(self):
        from ui.profile_manager_dialog import ProfileManagerDialog
        dlg = ProfileManagerDialog({k: v.copy() for k, v in self.profiles.items()},
                                   self.current_profile_id, self.storage, parent=self)
        self._register_dialog(dlg)
        try:
            if dlg.exec():
                self.profiles = dlg.profiles
                for prof in self.profiles.values():
                    self.storage.ensure_grid(prof, self.config.rows, self.config.cols)
                if dlg.selected_id in self.profiles:
                    self.switch_profile(dlg.selected_id, manual=True)
                self.folder_id = None
                self.undo_stack = [u for u in self.undo_stack if u[0] in self.profiles]  # 전체 되돌리기 기록은 프로필이 바뀌면 버림
                self.save()
                self._rebuild_grid()
        finally:
            self._unregister_dialog(dlg)

    # 지금 쓰는 프로그램(과 창 제목)에 맞춰 프로필 자동 전환
    def _on_tracker_tick(self):
        ShortcutManager.update_target_window()
        if not self.config.auto_switch_profile or self._dialog_open or self._menu_open:
            return
        exe, title, _ = AppDetector.get_foreground_app()
        if not exe:
            return
        self._last_external_exe = exe
        if self._manual_hold_exe:
            if exe.lower() == self._manual_hold_exe:
                return          # 같은 프로그램 안에서는 창 제목이 바뀌어도 자동 전환하지 않음
            self._manual_hold_exe = None   # 다른 프로그램으로 옮겨 가면 다시 자동
        key = (exe, title)
        if key == self.last_detected_key:
            return
        self.last_detected_key = key
        target = self.match_profile(exe, title)
        if target and target != self.current_profile_id:
            self.switch_profile(target)

    def match_profile(self, exe: str, title: str) -> Optional[str]:
        """
        창 제목 조건 + 프로그램 조건이 모두 맞는 프로필 > 창 제목만 맞는 프로필 > 프로그램만 맞는 프로필
        모든 프로필이 연결 없음이면 자동 전환하지 않고 현재 프로필을 유지합니다.
        연결 조건이 있는 프로필이 있을 때 일치하지 않으면 기본 프로필로 복귀합니다.
        """
        has_any_rules = any(
            bool((p.target_process or "").strip() or (p.target_title or "").strip())
            for p in self.profiles.values()
        )
        if not has_any_rules:
            return None

        exe_l, title_l = (exe or "").lower(), (title or "").lower()
        best, best_score = None, 0
        for pid, prof in self.profiles.items():
            procs = [p.strip().lower() for p in prof.target_process.replace(",", ";").split(";") if p.strip()]
            words = [w.strip().lower() for w in prof.target_title.split(",") if w.strip()]
            if not procs and not words:
                continue
            if procs and exe_l not in procs:
                continue
            if words and not any(w in title_l for w in words):
                continue
            score = (2 if words else 0) + (1 if procs else 0)
            if score > best_score:
                best, best_score = pid, score
        if best is None and "profile_default" in self.profiles:
            best = "profile_default"
        return best

    # ================================================================ 설정
    # 설정창이 소유하지 않아, 창이 열려 있는 동안에도 바뀔 수 있는 값들
    _RUNTIME_FIELDS = ("window_x", "window_y", "pycaw_prompt", "tray_hint_shown")

    def _carry_runtime_fields(self, cfg: AppConfig) -> None:
        """설정창을 열 때 복사해 둔 설정으로 덮어써도, 그동안 바뀐 실행 중 값은 잃지 않게 합니다."""
        for name in self._RUNTIME_FIELDS:
            if hasattr(self.config, name):
                setattr(cfg, name, getattr(self.config, name))

    def _open_settings(self):
        from ui.settings_dialog import SettingsDialog
        if self._settings_dlg and self._settings_dlg.isVisible():
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return

        if win32.IS_WINDOWS:
            self.config.auto_start = is_autostart_enabled()
        before = self.config.copy()
        dlg = SettingsDialog(self.config.copy(), storage=self.storage, parent=self, modeless=True)
        self._settings_dlg = dlg
        self._register_dialog(dlg)
        dlg.preview.connect(self.apply_config)
        dlg.convert_icons.connect(self._convert_emoji_icons)

        def on_accepted():
            new = dlg.config
            # 그리드를 줄이면 밖으로 밀려나는 버튼 확인
            lost = self.storage.count_outside(self.profiles, new.rows, new.cols)
            if lost and (new.rows < before.rows or new.cols < before.cols):
                if ask(self, "버튼이 지워져요",
                       f"칸 수를 줄이면 채워진 버튼 {lost}개가 그리드 밖으로 밀려나 지워집니다.\n계속할까요?",
                       ok_text="지우고 줄이기", danger=True):
                    self.push_undo(all_profiles=True)
                    self.storage.prune_outside(self.profiles, new.rows, new.cols)
                else:
                    new.rows, new.cols = max(new.rows, before.rows), max(new.cols, before.cols)
            elif new.rows < before.rows or new.cols < before.cols:
                self.storage.prune_outside(self.profiles, new.rows, new.cols)
            self._carry_runtime_fields(new)
            self.apply_config(new)
            if new.auto_start != is_autostart_enabled():
                if not set_autostart(new.auto_start) and win32.IS_WINDOWS:
                    self.show_toast("자동 실행 설정을 바꾸지 못했어요", "error")
            self._apply_hotkey()
            self.save()
            if getattr(dlg, "restore_path", None):
                self.restore_backup(dlg.restore_path)
            self._settings_dlg = None

        def on_rejected():
            before.user_themes = dlg.config.user_themes   # 저장한 테마는 취소해도 남김
            self._carry_runtime_fields(before)
            self.apply_config(before)
            self.save()
            self._settings_dlg = None

        dlg.accepted.connect(on_accepted)
        dlg.rejected.connect(on_rejected)
        self._position_dialog_beside(dlg)
        dlg.show()
        dlg.raise_()
        dlg.activateWindow()

    def restore_backup(self, path: str):
        """백업 파일로 설정과 버튼을 되돌립니다. (지금 상태는 먼저 따로 저장)"""
        parsed = self.storage.load_file(path)
        if parsed is None:
            self.show_toast("백업 파일을 읽지 못했어요", "error")
            return
        self.storage.make_backup_now()
        cfg, profiles, current = parsed
        cfg.window_x, cfg.window_y = self.x(), self.y()
        self.profiles, self.current_profile_id = profiles, current
        self.folder_id = None
        self.undo_stack.clear()
        self.apply_config(cfg)
        self._rebuild_grid()
        self._apply_hotkey()
        self.save()
        self.show_toast("백업으로 되돌렸어요", "ok")

    def apply_config(self, cfg: AppConfig):
        old = self.config
        self.config = cfg
        theme_changed = theme.T().name != cfg.theme
        if theme_changed:
            theme.set_theme(cfg.theme)
            QApplication.instance().setStyleSheet(theme.get_qss())
            from ui.glass import clear_glass_cache
            clear_glass_cache()
        if old.always_on_top != cfg.always_on_top and self._native_ready:
            pos = self.pos()
            self.setWindowFlag(Qt.WindowStaysOnTopHint, cfg.always_on_top)
            self.move(pos)
            self.show()
            win32.keep_topmost(int(self.winId()), cfg.always_on_top)
            for dlg in list(self._dialog_open):
                if dlg and dlg.isVisible():
                    dpos = dlg.pos()
                    dlg.setWindowFlag(Qt.WindowStaysOnTopHint, cfg.always_on_top)
                    dlg.move(dpos)
                    dlg.show()
        if self._native_ready:
            if old.bg_type != cfg.bg_type or theme_changed or not self.grabber.enabled:
                self._apply_background_mode()
            else:
                if old.glass_blur != cfg.glass_blur:
                    # 유리 흐림만 바뀌었으면 화면을 다시 찍지 않고 원본으로 다시 흐리게만 수행
                    self.grabber.blur = cfg.glass_blur
                    self.grabber.refresh(force=True, reblur_only=True)
                if (getattr(old, "glass_frost", 20) != getattr(cfg, "glass_frost", 20) or
                    getattr(old, "glass_tint", "") != getattr(cfg, "glass_tint", "")):
                    self.panel.rebuild_background()

        # 그리드 구조(칸 수, 버튼 크기, 간격)가 바뀔 때만 _rebuild_grid 호출
        structure_changed = (old.rows, old.cols, old.button_size, old.spacing) != \
                            (cfg.rows, cfg.cols, cfg.button_size, cfg.spacing)
        if structure_changed:
            self._rebuild_grid()
        else:
            # icon_style, show_labels, hold_ms 변경은 기존 위젯 속성만 변경
            if (old.icon_style, old.show_labels, old.hold_ms) != (cfg.icon_style, cfg.show_labels, cfg.hold_ms):
                for w in self.button_widgets.values():
                    w.icon_style = cfg.icon_style
                    w.show_labels = cfg.show_labels
                    w.hold_ms = cfg.hold_ms
                    w.update()
            self.panel.rebuild_background()
            self.update()
        self._fade_anim.stop()
        self.setWindowOpacity(cfg.opacity)
        self._update_header()

    def _convert_emoji_icons(self):
        """이모지 아이콘을 같은 뜻의 테마 아이콘으로 한꺼번에 바꿉니다. (되돌리기 가능)"""
        self.push_undo(all_profiles=True)
        n = self.storage.convert_emoji_icons(self.profiles)
        self.save()
        self._rebuild_grid()
        self.show_toast(f"아이콘 {n}개를 테마 아이콘으로 바꿨어요" if n else "바꿀 이모지 아이콘이 없어요", "info")
        return n

    # ================================================================ 창 이동 · 가장자리 붙이기
    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton:
            self._drag_offset = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
            e.accept()

    def mouseMoveEvent(self, e):
        if self._drag_offset is None or not (e.buttons() & Qt.LeftButton):
            return
        target = e.globalPosition().toPoint() - self._drag_offset
        if self.config.snap_edges:
            target = self._snapped(target)
        self.move(target)
        self.grabber.window_moved()

    def mouseReleaseEvent(self, e):
        if self._drag_offset is not None:
            self._drag_offset = None
            clamped = self._clamp_to_screen(self.pos())
            if clamped != self.pos():
                self.move(clamped)
            self.config.window_x, self.config.window_y = self.x(), self.y()
            self.save()
            self.grabber.refresh(force=True)

    def _clamp_to_screen(self, pos: QPoint) -> QPoint:
        """메뉴나 버튼판이 화면 밖으로 벗어나지 않도록 화면 안으로 밀어 넣습니다."""
        screen = QApplication.screenAt(pos) or QApplication.screenAt(QCursor.pos()) or self.screen()
        avail = screen.availableGeometry()
        gap = 6
        header_geo = self.header_bar.geometry().translated(pos)
        panel_geo = self.panel.geometry().translated(pos)
        combo = header_geo.united(panel_geo)

        x, y = pos.x(), pos.y()
        if combo.left() < avail.left() + gap:
            x += (avail.left() + gap) - combo.left()
        elif combo.right() > avail.right() - gap:
            x -= combo.right() - (avail.right() - gap)

        if header_geo.top() < avail.top() + gap:
            y += (avail.top() + gap) - header_geo.top()
        elif panel_geo.bottom() > avail.bottom() - gap:
            y -= panel_geo.bottom() - (avail.bottom() - gap)

        return QPoint(x, y)

    def _snapped(self, pos: QPoint) -> QPoint:
        screen = QApplication.screenAt(QCursor.pos()) or self.screen()
        avail = screen.availableGeometry()
        header_geo = self.header_bar.geometry().translated(pos)
        panel_geo = self.panel.geometry().translated(pos)
        combo = header_geo.united(panel_geo)
        x, y = pos.x(), pos.y()
        gap = 6

        # 좌우: 버튼판 + 메뉴 합친 사각형 기준
        if abs(combo.left() - avail.left()) < SNAP_DISTANCE:
            x += avail.left() + gap - combo.left()
        elif abs(combo.right() - avail.right()) < SNAP_DISTANCE:
            x += avail.right() - gap - combo.right()

        # 위쪽 끝: 메뉴 윗변 = 화면 위쪽 + 6
        if abs(header_geo.top() - avail.top()) < SNAP_DISTANCE:
            y += avail.top() + gap - header_geo.top()
        # 아래쪽 끝: 버튼판 아랫변 = 화면 아래쪽 - 6
        elif abs(panel_geo.bottom() - avail.bottom()) < SNAP_DISTANCE:
            y += avail.bottom() - gap - panel_geo.bottom()

        return QPoint(x, y)

    def moveEvent(self, e):
        super().moveEvent(e)
        self.grabber.window_moved()

    def _restore_position(self):
        x, y = self.config.window_x, self.config.window_y
        if x is not None and y is not None:
            for s in QApplication.screens():
                if s.availableGeometry().adjusted(-40, -40, 40, 40).contains(QPoint(x + 60, y + 30)):
                    clamped = self._clamp_to_screen(QPoint(x, y))
                    self.move(clamped)
                    return
        avail = QApplication.primaryScreen().availableGeometry()
        target = QPoint(avail.right() - self.width() - 24, avail.top() + 120)
        self.move(self._clamp_to_screen(target))

    # ================================================================ 안 쓸 때 흐려지기 & 위쪽 메뉴 애니메이션
    def enterEvent(self, e):
        self._idle_timer.stop()
        self.grabber.set_interval(450)
        self._fade_timer.stop()
        if self.windowOpacity() < self.config.opacity - 0.01:
            self._fade_anim.stop()
            self._fade_anim.setDuration(160)
            self._fade_anim.setStartValue(self.windowOpacity())
            self._fade_anim.setEndValue(self.config.opacity)
            self._fade_anim.start()

        # 위쪽 메뉴 스르륵 나타남 (150ms)
        self.header_hide_timer.stop()
        if not self.header_bar.isVisible():
            self.header_bar.show()
        if self.header_effect.opacity() < 0.99:
            self.header_anim.stop()
            self.header_anim.setDuration(150)
            self.header_anim.setStartValue(self.header_effect.opacity())
            self.header_anim.setEndValue(1.0)
            self.header_anim.start()

        if e is not None:
            super().enterEvent(e)

    def leaveEvent(self, e):
        self._idle_timer.start(4000)
        if self.config.auto_fade:
            self._fade_timer.start(self.config.auto_fade_delay * 1000)

        # 위쪽 메뉴: 1초 뒤 스르륵 사라짐 (always_show_header나 묶음 안이면 항상 유지)
        if not self.config.always_show_header and (self.folder_id is None):
            self.header_hide_timer.start(1000)

        if e is not None:
            super().leaveEvent(e)

    def _fade_out(self):
        if self._dialog_open or self.underMouse() or not self.config.auto_fade:
            return
        target = min(self.config.opacity, self.config.auto_fade_opacity)
        self._fade_anim.stop()
        self._fade_anim.setDuration(600)
        self._fade_anim.setStartValue(self.windowOpacity())
        self._fade_anim.setEndValue(target)
        self._fade_anim.start()

    # ================================================================ 알림 · 트레이
    def show_toast(self, text: str, kind: str = "info", ms: int = 2400):
        if self.config.show_toast and self.isVisible():
            self.toast.show_message(text, kind, ms)

    def _init_tray(self):
        self.tray = QSystemTrayIcon(make_app_icon(), self)
        self.tray.setToolTip("Virtual Deck")
        menu = glass_menu()
        self._tray_menu = menu
        self.act_toggle = QAction("버튼판 숨기기 / 보이기", self)
        self.act_toggle.triggered.connect(self.toggle_visibility)
        menu.addAction(self.act_toggle)
        act_settings = QAction("환경설정…", self)
        act_settings.triggered.connect(lambda: (self.show_deck(), self._open_settings()))
        menu.addAction(act_settings)
        # 유리판 스타일에서만: 1분 동안 화면 캡처·화면 공유에 버튼판이 보이게
        self.act_capture = QAction("캡처할 때 보이게 (1분)", self)
        self.act_capture.triggered.connect(self.allow_capture_for_a_minute)
        self.act_capture.setVisible(self.config.bg_type == "glass")
        menu.addAction(self.act_capture)
        menu.addSeparator()
        act_quit = QAction("종료", self)
        act_quit.triggered.connect(self.quit_app)
        menu.addAction(act_quit)
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def allow_capture_for_a_minute(self):
        """
        1분 동안 화면 캡처에서 빼지 않음. 그동안은 뒤 화면을 다시 찍지 않고
        마지막 배경을 그대로 쓰므로 모양은 같고 캡처에만 찍힙니다.
        """
        if self.config.bg_type != "glass":
            return
        if getattr(self, "_capture_timer", None) is None:
            self._capture_timer = QTimer(self)
            self._capture_timer.setSingleShot(True)
            self._capture_timer.timeout.connect(self._end_capture_allow)
        self.grabber.pause(True)
        win32.set_exclude_from_capture(int(self.winId()), False)
        self._capture_timer.start(60_000)
        self.show_toast("1분 동안 화면 캡처에 보여요", "info", 3000)

    def _end_capture_allow(self):
        if self._native_ready:
            self._apply_background_mode()
        self.show_toast("다시 캡처에서 숨겨졌어요", "info", 2400)

    def _on_tray_activated(self, reason):
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.toggle_visibility()

    def toggle_visibility(self):
        if self.isVisible():
            self.hide_to_tray()
        else:
            self.show_deck()

    def show_deck(self):
        self.show()
        self.raise_()
        self.setWindowOpacity(self.config.opacity)
        capture_allowed = getattr(self, "_capture_timer", None) is not None and self._capture_timer.isActive()
        if not capture_allowed:
            self.grabber.pause(False)
        if self.config.auto_fade and not self.underMouse():
            self._fade_timer.start(self.config.auto_fade_delay * 1000)

    def hide_to_tray(self):
        self.hide()
        self.grabber.pause(True)
        if not self.config.tray_hint_shown:
            hk = f" ({self.config.hotkey})" if self.config.hotkey_enabled else ""
            self.tray.showMessage("Virtual Deck", f"트레이에 숨었어요. 아이콘을 누르거나 단축키{hk}로 다시 열 수 있어요.",
                                  QSystemTrayIcon.Information, 3000)
            self.config.tray_hint_shown = True
            self.save()

    def quit_app(self):
        MacroRunner.instance().stop_all()
        self.hotkey.unregister()
        self.config.window_x, self.config.window_y = self.x(), self.y()
        self.save()
        self.tray.hide()
        QApplication.instance().quit()

    def closeEvent(self, e):
        self.quit_app()
        e.accept()
