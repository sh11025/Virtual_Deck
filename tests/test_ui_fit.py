# -*- coding: utf-8 -*-
"""UI 화면 잘림, 위젯 경계 초과, 레이아웃 적합성 자동 점검 테스트."""

import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QPoint, QRect
from PySide6.QtGui import QScreen
from PySide6.QtWidgets import (
    QApplication, QAbstractButton, QLabel, QSpinBox, QScrollArea, QWidget
)

app = QApplication.instance()
if app is None:
    app = QApplication(sys.argv)

from ui import theme
theme.load_fonts()

from services.storage_service import StorageService
from ui.main_window import MainWindow
from ui.widgets import GlassButton
from ui.settings_dialog import SettingsDialog, BackupDialog
from ui.button_editor_dialog import ButtonEditorDialog
from ui.profile_manager_dialog import ProfileManagerDialog, SampleProfilesDialog
from ui.app_picker_dialog import AppPickerDialog
from ui.macro_editor_dialog import MacroEditorDialog
from models.button_model import DeckButtonData

# 자동 점검 시 실제 외부 연동 차단
MainWindow._check_pycaw = lambda self: None

def wait_ui(ms=250):
    start = time.time()
    while (time.time() - start) * 1000 < ms:
        app.processEvents()
        time.sleep(0.01)

def save_snapshot(dlg, name):
    shot_dir = os.environ.get("VD_SHOT")
    if shot_dir:
        os.makedirs(shot_dir, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in name)
        pixmap = dlg.grab()
        pixmap.save(os.path.join(shot_dir, f"{safe_name}.png"))

def find_scroll_viewport(widget):
    p = widget.parent()
    while p:
        if isinstance(p, QScrollArea):
            return p.viewport()
        p = p.parent()
    return None

def inspect_dialog(dlg, dlg_name):
    """지정된 다이얼로그의 모든 위젯에 대해 6가지 규칙 검사."""
    errors = []
    
    # 5. 스크롤 영역에 가로 스크롤바가 보이지 않음
    for scroll in dlg.findChildren(QScrollArea):
        if scroll.isVisible() and scroll.horizontalScrollBar() and scroll.horizontalScrollBar().isVisible():
            errors.append(f"[{dlg_name}] 스크롤 영역 가로 스크롤바 노출")

    # 7. 큰 화면에서 바깥 스크롤 없음 (설정창 4개 탭 및 편집창에 적용)
    if isinstance(dlg, (SettingsDialog, ButtonEditorDialog)):
        for scroll in dlg.findChildren(QScrollArea):
            if scroll.isVisible() and scroll.objectName() != "inner_scroll":
                vbar = scroll.verticalScrollBar()
                if vbar and vbar.maximum() > 0:
                    errors.append(f"[{dlg_name}] 바깥 스크롤 {vbar.maximum()} px 넘침")

    # 8. 편집창 두 색 칩이 창 안(스크롤 없이 보이는 영역, 푸터 위)에 완전히 들어옴
    if isinstance(dlg, ButtonEditorDialog):
        footer_btns = [
            b for b in dlg.findChildren(GlassButton)
            if b.text() in ("취소", "저장", "비우기") and b.isVisible()
        ]
        if footer_btns:
            footer_top = min(b.mapTo(dlg, QPoint(0, 0)).y() for b in footer_btns)
            for chip_name, chip in (("아이콘색칩", getattr(dlg, "icon_colors", None)),
                                    ("유리색칩", getattr(dlg, "colors", None))):
                if chip and chip.isVisible():
                    chip_bottom = chip.mapTo(dlg, QPoint(0, 0)).y() + chip.height()
                    if chip_bottom > footer_top:
                        errors.append(
                            f"[{dlg_name}] {chip_name} 하단 푸터 침범 (칩 하단 {chip_bottom}px > 푸터 상단 {footer_top}px)"
                        )

    for w in dlg.findChildren(QWidget):
        if not w.isVisible():
            continue
        if w.width() <= 0 or w.height() <= 0:
            continue

        # 3. 모든 QSpinBox alignment가 AlignCenter를 포함
        if isinstance(w, QSpinBox):
            align = w.alignment()
            if not (align & Qt.AlignCenter):
                errors.append(f"[{dlg_name}] QSpinBox 가운데 정렬 누락 (alignment={align})")

        # 1 & 6. 보이는 버튼 글자 및 아이콘 폭 검사
        if isinstance(w, QAbstractButton):
            txt = w.text().strip()
            if txt:
                fm = w.fontMetrics()
                txt_w = fm.horizontalAdvance(txt)
                has_icon = bool(getattr(w, "icon_name", None))
                req_w = txt_w + 12 + (20 if has_icon else 0)
                if w.width() < req_w:
                    errors.append(
                        f"[{dlg_name}] 버튼 폭 부족: '{txt}' (현재 {w.width()}px < 필요 {req_w}px)"
                    )
                if has_icon and isinstance(w, GlassButton):
                    if w.width() < txt_w + 32:
                        errors.append(
                            f"[{dlg_name}] GlassButton 아이콘-글자 겹침 위험: '{txt}' (현재 {w.width()}px < 최소 {txt_w + 32}px)"
                        )
                if isinstance(w, GlassButton):
                    margin_lr = w.contentsMargins().left() + w.contentsMargins().right()
                    req_hint = w.sizeHint().width() - margin_lr - 2
                    if w.width() < req_hint:
                        errors.append(
                            f"[{dlg_name}] GlassButton 폭 부족: '{txt}' (현재 {w.width()}px < 필요 {req_hint}px)"
                        )

        # 2. QLabel 검사
        if isinstance(w, QLabel):
            raw_text = w.text()
            if raw_text and ("<" not in raw_text or ">" not in raw_text):
                fm = w.fontMetrics()
                txt_w = fm.horizontalAdvance(raw_text)
                if not w.wordWrap():
                    # 줄바꿈 없는 라벨은 폭이 글자보다 작으면 잘림
                    if w.width() + 2 < txt_w:
                        errors.append(
                            f"[{dlg_name}] 줄바꿈 없는 QLabel 폭 부족: '{raw_text[:20]}' (폭 {w.width()}px < 글자폭 {txt_w}px)"
                        )
                else:
                    # 줄바꿈 있는 라벨은 heightForWidth 필요 높이 이상인지 확인
                    req_h = w.heightForWidth(w.width())
                    if req_h > 0 and w.height() + 2 < req_h:
                        errors.append(
                            f"[{dlg_name}] 줄바꿈 QLabel 높이 부족: '{raw_text}' (라벨폭 {w.width()}px, 현재높이 {w.height()}px < 필요높이 {req_h}px)"
                        )

        # 4. 보이는 자식 위젯이 창(또는 스크롤 viewport)의 오른쪽 경계를 넘지 않음
        container = find_scroll_viewport(w)
        if container is None:
            container = dlg
        try:
            pt = w.mapTo(container, QPoint(0, 0))
            right_edge = pt.x() + w.width()
            # 컨테이너 내부에 위치한 정상 위젯에 대해서만 검사
            if 0 <= pt.x() < container.width():
                if right_edge > container.width() + 2:
                    w_desc = getattr(w, "text", lambda: "")() if hasattr(w, "text") else type(w).__name__
                    errors.append(
                        f"[{dlg_name}] 오른쪽 경계 초과: {type(w).__name__}('{w_desc[:15]}') (우측 {right_edge}px > 컨테이너 {container.width()}px)"
                    )
        except Exception:
            pass

    return errors

def run_all_dialog_checks(scale_tag="scale_M", scale_key="M"):
    orig_available_geometry = QScreen.availableGeometry
    QScreen.availableGeometry = lambda self, *args, **kwargs: QRect(0, 0, 1920, 1040)
    try:
        return _run_all_dialog_checks_impl(scale_tag, scale_key)
    finally:
        QScreen.availableGeometry = orig_available_geometry

def _run_all_dialog_checks_impl(scale_tag="scale_M", scale_key="M"):
    results = []
    theme.apply_ui_scale(scale_key)
    
    def report_check(name, errs):
        if not errs:
            results.append((True, f"[{scale_tag}] {name} UI 적합"))
        else:
            for e in errs:
                print(f"실패: [{scale_tag}] {e}")
            results.append((False, f"[{scale_tag}] {name} (오류 {len(errs)}건)"))

    temp_dir = tempfile.mkdtemp(prefix="vd_ui_fit_")
    st = StorageService(data_dir=temp_dir)
    main_win = MainWindow(st)
    main_win.config.font_size = scale_key
    main_win.show()
    wait_ui(100)

    # --- 1. SettingsDialog 검사 ---
    sd = SettingsDialog(main_win.config, parent=main_win, modeless=True)
    sd.show()
    wait_ui(250)

    # 4개 탭 순회 (꾸미기, 크기, 편리한 기능, 더보기)
    tab_names = ["꾸미기", "크기", "편리한기능", "더보기"]
    for idx, tname in enumerate(tab_names):
        sd.tabs.setCurrentIndex(idx)
        wait_ui(250)
        if idx == 3:  # 더보기 탭
            bg_names = ["기본", "단색", "두색", "사진"]
            for bg_idx, bg_name in enumerate(bg_names):
                sd.custom_bg_tabs.setCurrentIndex(bg_idx)
                wait_ui(150)
                errs = inspect_dialog(sd, f"설정_더보기_{bg_name}")
                save_snapshot(sd, f"SettingsDialog_더보기_{bg_name}_{scale_tag}")
                report_check(f"설정_더보기_{bg_name}", errs)
        else:
            errs = inspect_dialog(sd, f"설정_{tname}")
            save_snapshot(sd, f"SettingsDialog_{tname}_{scale_tag}")
            report_check(f"설정_{tname}", errs)
    sd.close()

    # --- 2. ButtonEditorDialog 검사 ---
    btn_model = DeckButtonData(id="btn_0_0", name="테스트", action_type="url", action_data="https://test.com")
    ed = ButtonEditorDialog(btn_model, parent=main_win)
    ed.show()
    wait_ui(250)

    for action_type in ButtonEditorDialog.PRIMARY_TYPES:
        idx = ed.action.combo.findData(action_type)
        if idx >= 0:
            ed.action.combo.setCurrentIndex(idx)
            wait_ui(150)
            errs = inspect_dialog(ed, f"버튼설정_{action_type}")
            save_snapshot(ed, f"ButtonEditor_{action_type}_{scale_tag}")
            report_check(f"버튼설정_{action_type}", errs)
    ed.close()

    # 내 색 12개 추가 상태 검사
    custom_12 = [f"#{i*20:02x}{i*15:02x}{255-i*10:02x}" for i in range(12)]
    ed_custom = ButtonEditorDialog(btn_model, parent=main_win)
    ed_custom.colors.set_custom(custom_12)
    ed_custom.icon_colors.set_custom(custom_12)
    ed_custom.show()
    wait_ui(250)
    errs = inspect_dialog(ed_custom, "버튼설정_내색12개")
    save_snapshot(ed_custom, f"ButtonEditor_내색12개_{scale_tag}")
    report_check("버튼설정_내색12개", errs)
    ed_custom.close()

    # --- 3. ProfileManagerDialog & SampleProfilesDialog 검사 ---
    pm = ProfileManagerDialog(main_win.profiles, main_win.current_profile_id, st, parent=main_win)
    pm.show()
    wait_ui(250)
    errs = inspect_dialog(pm, "프로필관리")
    save_snapshot(pm, f"ProfileManager_{scale_tag}")
    report_check("프로필관리", errs)

    sp = SampleProfilesDialog(pm, parent=main_win)
    sp.show()
    wait_ui(250)
    errs = inspect_dialog(sp, "예시모음")
    save_snapshot(sp, f"SampleProfiles_{scale_tag}")
    report_check("예시모음", errs)
    sp.close()
    pm.close()

    # --- 4. AppPickerDialog 검사 ---
    fake_apps = [
        ("메모장", "notepad.exe"),
        ("계산기", "calc.exe"),
        ("Google Chrome", "C:\\Program Files\\Chrome\\chrome.exe"),
    ]
    ap = AppPickerDialog(parent=main_win, initial_apps=fake_apps)
    ap.show()
    wait_ui(250)
    errs = inspect_dialog(ap, "앱선택")
    save_snapshot(ap, f"AppPicker_{scale_tag}")
    report_check("앱선택", errs)
    ap.close()

    # --- 5. MacroEditorDialog 검사 ---
    me = MacroEditorDialog(macro_json="", parent=main_win)
    me.show()
    wait_ui(250)
    errs = inspect_dialog(me, "매크로편집")
    save_snapshot(me, f"MacroEditor_{scale_tag}")
    report_check("매크로편집", errs)
    me.close()

    # --- 6. BackupDialog 검사 ---
    bd = BackupDialog(st, parent=main_win)
    bd.show()
    wait_ui(250)
    errs = inspect_dialog(bd, "백업창")
    save_snapshot(bd, f"BackupDialog_{scale_tag}")
    report_check("백업창", errs)
    bd.close()

    main_win.close()
    return results

def main():
    all_results = []
    scales = [("S", "scale_S"), ("M", "scale_M"), ("L", "scale_L")]
    for key, tag in scales:
        all_results.extend(run_all_dialog_checks(tag, key))

    passed = sum(1 for ok, _ in all_results if ok)
    total = len(all_results)
    
    print("-" * 50)
    print(f"결과: {passed} / {total} 통과")
    
    if passed < total:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
