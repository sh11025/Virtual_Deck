"""
매크로 편집창
단계를 추가·수정·삭제하고 순서를 바꿉니다.
이미 넣은 단계는 두 번 클릭하면 아래 입력칸으로 불러와서 고칠 수 있습니다.
"""

import json
import time
from typing import Dict, List

from PySide6.QtCore import Qt, Signal, QRectF, QTimer, QTime
from PySide6.QtGui import QPainter, QColor, QFont, QKeyEvent
from PySide6.QtWidgets import (
    QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem, QComboBox, QLineEdit, QWidget,
    QStackedWidget, QFileDialog, QLabel, QTimeEdit, QSpinBox,
)

from core.macro_manager import STEP_TYPES, parse_steps, ms_to_unit, unit_to_ms
from core.shortcut_manager import ShortcutManager
from ui import theme
from ui.theme import T
from ui.glass import paint_slot, paint_glass
from ui.widgets import (
    GlassDialog, GlassButton, GlassToggle, ShortcutEditor, section_label, hint_label, inform, qt_key_to_name,
    no_wheel,
)


class MacroRecorder(QWidget):
    """
    매크로 녹화: 녹화를 켠 뒤 키보드로 직접 해 보이면 단계로 만들어 줍니다.
    - 글자는 모아서 '글자 입력' 한 단계로 (한글 입력도 OK)
    - Ctrl/Alt/Win 과 함께 누른 키, Enter 같은 특수 키는 '단축키' 단계로
    - 켜 두면 키 사이에 기다린 시간도 '기다리기' 단계로
    """

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.recording = False
        self.record_delays = True
        self.steps: List[Dict[str, str]] = []
        self._text = ""
        self._last = 0.0
        self.setFocusPolicy(Qt.StrongFocus)
        self.setAttribute(Qt.WA_InputMethodEnabled, True)
        self.setFixedHeight(64)
        self._blink = QTimer(self)
        self._blink.setInterval(500)
        self._blink.timeout.connect(self.update)
        self._dot = True

    def start(self):
        self.steps, self._text = [], ""
        self._last = 0.0
        self.recording = True
        self._blink.start()
        self.setFocus()
        self.update()

    def stop(self) -> List[Dict[str, str]]:
        self._flush_text()
        self.recording = False
        self._blink.stop()
        self.update()
        return list(self.steps)

    def _flush_text(self):
        if self._text:
            self.steps.append({"type": "text", "value": self._text})
            self._text = ""

    def _note_gap(self):
        now = time.monotonic()
        if self.record_delays and self._last and (self.steps or self._text):
            gap = now - self._last
            if gap > 0.35:
                self._flush_text()
                ms = min(10000, int(round(gap * 1000 / 50.0)) * 50)
                self.steps.append({"type": "delay", "value": str(ms)})
        self._last = now

    def focusNextPrevChild(self, nxt):
        return False if self.recording else super().focusNextPrevChild(nxt)

    def keyPressEvent(self, e: QKeyEvent):
        if not self.recording:
            return super().keyPressEvent(e)
        key = e.key()
        if key in (Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr):
            return
        m = e.modifiers()
        cmd = bool(m & (Qt.ControlModifier | Qt.AltModifier | Qt.MetaModifier))
        self._note_gap()
        text = e.text()
        if text and text.isprintable() and not cmd and key not in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Tab):
            self._text += text
        else:
            name = qt_key_to_name(key, text)
            if name:
                self._flush_text()
                mods = [n for n, flag in (("Win", Qt.MetaModifier), ("Ctrl", Qt.ControlModifier),
                                          ("Alt", Qt.AltModifier), ("Shift", Qt.ShiftModifier)) if m & flag]
                self.steps.append({"type": "shortcut", "value": " + ".join(mods + [name])})
        self.update()
        self.changed.emit()

    def inputMethodEvent(self, e):
        if self.recording and e.commitString():
            self._note_gap()
            self._text += e.commitString()
            self.update()
            self.changed.emit()
        e.accept()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(1, 2, self.width() - 2, self.height() - 6)
        if self.recording:
            paint_glass(p, r, 16, fill=0.85, shadow_strength=0.6, glow=QColor("#ef4444"), glow_amount=0.5)
        else:
            paint_slot(p, r, 16)
        p.setFont(theme.ui_font(13, QFont.DemiBold))
        if self.recording:
            self._dot = not self._dot
            if self._dot:
                p.setPen(Qt.NoPen)
                p.setBrush(QColor("#ef4444"))
                p.drawEllipse(QRectF(r.left() + 16, r.center().y() - 6, 12, 12))
            n = len(self.steps) + (1 if self._text else 0)
            typing = f"  ·  입력 중: “{self._text[-18:]}”" if self._text else ""
            p.setPen(QColor(T().text))
            p.drawText(r.adjusted(38, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft, f"녹화 중… {n}단계{typing}")
        else:
            p.setPen(QColor(T().text_dim))
            p.drawText(r.adjusted(16, 0, -10, 0), Qt.AlignVCenter | Qt.AlignLeft,
                       "‘녹화 시작’을 누르고 키보드로 직접 해 보세요. 여기 입력한 그대로 단계가 만들어져요.")


class MacroEditorDialog(GlassDialog):
    VOLUME_SET = "__volume_set__"   # '볼륨 · 미디어' 안의 "정확한 크기로 맞추기" 항목

    def __init__(self, macro_json: str = "", parent=None):
        super().__init__("연속 동작 만들기", "위에서 아래 순서로 차례대로 실행돼요", parent=parent, width=560)
        self.steps: List[Dict[str, str]] = parse_steps(macro_json)
        self.editing_row = -1

        self.list = QListWidget()
        self.list.setMinimumHeight(190)
        self.list.itemDoubleClicked.connect(lambda _: self._load_selected())
        self.list.currentRowChanged.connect(self._update_buttons)
        self.body.addWidget(self.list, 1)

        ctl = QHBoxLayout()
        ctl.setSpacing(6)
        self.up_btn = GlassButton("위로")
        self.up_btn.clicked.connect(lambda: self._move(-1))
        self.down_btn = GlassButton("아래로")
        self.down_btn.clicked.connect(lambda: self._move(1))
        self.edit_btn = GlassButton("수정", icon_name="edit")
        self.edit_btn.clicked.connect(self._load_selected)
        self.dup_btn = GlassButton("복제", icon_name="duplicate")
        self.dup_btn.clicked.connect(self._duplicate)
        self.del_btn = GlassButton("삭제", icon_name="trash")
        self.del_btn.clicked.connect(self._delete)
        for b in (self.up_btn, self.down_btn, self.edit_btn, self.dup_btn):
            ctl.addWidget(b)
        ctl.addStretch(1)
        ctl.addWidget(self.del_btn)
        self.body.addLayout(ctl)

        # 녹화
        rec_head = QHBoxLayout()
        rec_head.addWidget(section_label("녹화로 만들기"))
        rec_head.addStretch(1)
        rec_head.addWidget(QLabel("기다린 시간도 기록"))
        self.delay_toggle = GlassToggle(True)
        rec_head.addWidget(self.delay_toggle)
        self.body.addLayout(rec_head)
        rec_row = QHBoxLayout()
        self.recorder = MacroRecorder()
        rec_row.addWidget(self.recorder, 1)
        self.rec_btn = GlassButton("녹화 시작", tint="red", icon_name="stop")
        self.rec_btn.clicked.connect(self._toggle_record)
        rec_row.addWidget(self.rec_btn, 0, Qt.AlignVCenter)
        self.body.addLayout(rec_row)

        # 단계 입력
        self.editor_title = section_label("새 순서 추가")
        self.body.addWidget(self.editor_title)
        self.type_combo = no_wheel(QComboBox())
        for key, label in STEP_TYPES.items():
            if key == "volume_set":
                continue    # '볼륨 · 미디어' 안으로 합침 (예전에 만든 단계는 그대로 동작)
            self.type_combo.addItem(label, key)
        self.type_combo.currentIndexChanged.connect(self._on_type)
        self.body.addWidget(self.type_combo)

        self.stack = QStackedWidget()
        # 단축키
        self.sc_editor = ShortcutEditor()
        self.stack.addWidget(self.sc_editor)
        # 일반 입력 (글자, 기다리기, 프로그램, 웹)
        gen = QWidget()
        gl = QVBoxLayout(gen)
        gl.setContentsMargins(0, 0, 0, 0)
        gl.setSpacing(6)
        h = QHBoxLayout()
        self.val_edit = QLineEdit()
        h.addWidget(self.val_edit, 1)
        self.browse_btn = GlassButton("찾기", icon_name="folder")
        self.browse_btn.clicked.connect(self._browse)
        h.addWidget(self.browse_btn)
        gl.addLayout(h)
        self.val_hint = hint_label("")
        gl.addWidget(self.val_hint)
        self.stack.addWidget(gen)
        # 미디어
        med = QWidget()
        ml = QVBoxLayout(med)
        ml.setContentsMargins(0, 0, 0, 0)
        self.media_combo = no_wheel(QComboBox())
        for key, label in ShortcutManager.MEDIA_KEYS:
            self.media_combo.addItem(label, key)
        self.media_combo.addItem("🎚️ 볼륨을 정확히 ○%로 맞추기", self.VOLUME_SET)
        self.media_combo.currentIndexChanged.connect(self._on_media_pick)
        ml.addWidget(self.media_combo)
        self.vol_row = QWidget()
        vr = QHBoxLayout(self.vol_row)
        vr.setContentsMargins(0, 0, 0, 0)
        vr.addWidget(QLabel("소리 크기"))
        self.vol_spin = no_wheel(QSpinBox())
        self.vol_spin.setRange(0, 100)
        self.vol_spin.setSuffix(" %")
        self.vol_spin.setValue(50)
        self.vol_spin.setAlignment(Qt.AlignCenter)
        self.vol_spin.setFixedWidth(110)
        vr.addWidget(self.vol_spin)
        vr.addStretch(1)
        ml.addWidget(self.vol_row)
        self.vol_row.setVisible(False)
        self.stack.addWidget(med)

        # 기다리기 (delay)
        del_w = QWidget()
        dl = QVBoxLayout(del_w)
        dl.setContentsMargins(0, 0, 0, 0)
        dl.setSpacing(6)
        dh = QHBoxLayout()
        dh.setSpacing(8)
        self.delay_spin = no_wheel(QSpinBox())
        self.delay_spin.setRange(1, 999999)
        self.delay_spin.setValue(1)
        self.delay_spin.setAlignment(Qt.AlignCenter)
        self.delay_spin.setMinimumWidth(110)
        self.delay_unit = no_wheel(QComboBox())
        self.delay_unit.addItems(["초", "밀리초", "분", "시간"])
        self.delay_unit.setCurrentText("초")
        dh.addWidget(self.delay_spin, 1)
        dh.addWidget(self.delay_unit)
        dl.addLayout(dh)
        dl.addWidget(hint_label("다음 단계로 넘어가기 전에 잠시 기다립니다."))
        self.stack.addWidget(del_w)

        # 정해진 시각까지 기다리기 (wait_until)
        wu_w = QWidget()
        wl = QVBoxLayout(wu_w)
        wl.setContentsMargins(0, 0, 0, 0)
        wl.setSpacing(6)
        self.time_edit = no_wheel(QTimeEdit())
        self.time_edit.setDisplayFormat("HH:mm")
        self.time_edit.setTime(QTime.currentTime())
        self.time_edit.setAlignment(Qt.AlignCenter)
        self.time_edit.setFixedWidth(110)
        wl.addWidget(self.time_edit, 0, Qt.AlignLeft)
        wl.addWidget(hint_label("매일 이 시각이 될 때까지 기다립니다. 이미 지난 시각이면 내일 실행해요."))
        self.stack.addWidget(wu_w)


        self.body.addWidget(self.stack)

        act = QHBoxLayout()
        self.cancel_edit_btn = GlassButton("수정 취소")
        self.cancel_edit_btn.clicked.connect(self._reset_editor)
        self.cancel_edit_btn.hide()
        act.addWidget(self.cancel_edit_btn)
        act.addStretch(1)
        self.add_btn = GlassButton("단계 추가", tint="blue", icon_name="plus")
        self.add_btn.clicked.connect(self._commit_step)
        act.addWidget(self.add_btn)
        self.body.addLayout(act)

        self.footer.addStretch(1)
        cancel = GlassButton("취소")
        cancel.clicked.connect(self.reject)
        self.footer.addWidget(cancel)
        ok = GlassButton("완료", tint="orange", icon_name="check")
        ok.clicked.connect(self.accept)
        self.footer.addWidget(ok)

        self._on_type(0)
        self._refresh_list()
        self.resize(self.width(), 780)

    # ------------------------------------------------------------ 목록
    @staticmethod
    def _describe(step) -> str:
        t, v = step.get("type", ""), str(step.get("value", "")).strip()
        label = STEP_TYPES.get(t, t)
        if t == "delay":
            n, u = ms_to_unit(v)
            return f"⏱ {n}{u} 기다리기"
        elif t == "wait_until":
            return f"🕒 {v} 까지 기다리기"
        elif t == "volume_set":
            return f"🔊 볼륨 {v}% 로 맞추기"
        elif t == "media":
            v = ShortcutManager.media_label(v).split(" ", 1)[-1]
        elif t == "text":
            v = "“" + (v if len(v) <= 40 else v[:38] + "…").replace("\n", "⏎") + "”"
        return f"{label}    {v}"

    def _refresh_list(self, select: int = None):
        self.list.clear()
        for i, s in enumerate(self.steps):
            QListWidgetItem(f"{i + 1}.  {self._describe(s)}", self.list)
        if not self.steps:
            item = QListWidgetItem("아직 단계가 없어요. 아래에서 추가해 주세요.", self.list)
            item.setFlags(Qt.NoItemFlags)
        if select is not None and 0 <= select < len(self.steps):
            self.list.setCurrentRow(select)
        self._update_buttons()

    def _selected(self) -> int:
        r = self.list.currentRow()
        return r if 0 <= r < len(self.steps) else -1

    def _update_buttons(self, *_):
        r = self._selected()
        has = r >= 0
        self.up_btn.setEnabled(has and r > 0)
        self.down_btn.setEnabled(has and r < len(self.steps) - 1)
        for b in (self.edit_btn, self.dup_btn, self.del_btn):
            b.setEnabled(has)

    def _move(self, d):
        r = self._selected()
        n = r + d
        if r < 0 or not (0 <= n < len(self.steps)):
            return
        self.steps[r], self.steps[n] = self.steps[n], self.steps[r]
        self._refresh_list(n)

    def _duplicate(self):
        r = self._selected()
        if r >= 0:
            self.steps.insert(r + 1, dict(self.steps[r]))
            self._refresh_list(r + 1)

    def _delete(self):
        r = self._selected()
        if r >= 0:
            del self.steps[r]
            if self.editing_row == r:
                self._reset_editor()
            self._refresh_list(min(r, len(self.steps) - 1))

    # ------------------------------------------------------------ 입력
    def _on_type(self, idx):
        t = self.type_combo.itemData(idx)
        if t == "shortcut":
            self.stack.setCurrentIndex(0)
        elif t == "media":
            self.stack.setCurrentIndex(2)
        elif t == "delay":
            self.stack.setCurrentIndex(3)
        elif t == "wait_until":
            self.stack.setCurrentIndex(4)
        else:
            self.stack.setCurrentIndex(1)
            info = {
                "text": ("입력할 글자 (한글, 이모지도 돼요)", "지금 쓰는 프로그램에 글자를 직접 입력해요. 복사해 둔 내용은 그대로 남아요."),
                "program": ("프로그램 경로 또는 notepad.exe", "프로그램을 실행해요."),
                "url": ("예: https://www.google.com", "웹사이트를 열어요."),
            }[t]
            self.val_edit.setPlaceholderText(info[0])
            self.val_hint.setText(info[1])
            self.browse_btn.setVisible(t == "program")
        self.stack.setFixedHeight(self.stack.currentWidget().sizeHint().height())

    def _on_media_pick(self, *_):
        """'정확한 크기로 맞추기' 를 고르면 소리 크기 칸을 보여줌"""
        self.vol_row.setVisible(self.media_combo.currentData() == self.VOLUME_SET)
        page = self.stack.currentWidget()
        page.layout().invalidate()
        page.layout().activate()
        self.stack.setFixedHeight(page.sizeHint().height())

    def _browse(self):
        path, _ = QFileDialog.getOpenFileName(self, "프로그램 선택", "", "프로그램 (*.exe *.bat *.lnk);;모든 파일 (*.*)")
        if path:
            self.val_edit.setText(path)

    def _current_value(self):
        t = self.type_combo.currentData()
        if t == "shortcut":
            return t, self.sc_editor.value()
        if t == "media":
            if self.media_combo.currentData() == self.VOLUME_SET:
                return "volume_set", str(self.vol_spin.value())
            return t, self.media_combo.currentData()
        if t == "delay":
            ms = unit_to_ms(self.delay_spin.value(), self.delay_unit.currentText())
            return t, str(ms)
        if t == "wait_until":
            return t, self.time_edit.time().toString("HH:mm")
        v = self.val_edit.text()
        return t, (v if t == "text" else v.strip())

    def _commit_step(self):
        t, v = self._current_value()
        if t == "delay":
            try:
                if int(v) <= 0:
                    inform(self, "시간을 입력해 주세요", "기다릴 시간은 1 이상이어야 해요.")
                    return
            except ValueError:
                inform(self, "숫자를 적어 주세요", "기다릴 시간을 입력해 주세요.")
                return
        if t == "wait_until":
            if not v:
                inform(self, "시각을 입력해 주세요", "기다릴 시각을 HH:MM 형식으로 입력해 주세요.")
                return
        elif not v:
            inform(self, "내용이 비어 있어요", "단계에 들어갈 내용을 정해 주세요.")
            return
        step = {"type": t, "value": v}
        if self.editing_row >= 0:
            self.steps[self.editing_row] = step
            row = self.editing_row
        else:
            self.steps.append(step)
            row = len(self.steps) - 1
        self._reset_editor()
        self._refresh_list(row)

    def _load_selected(self):
        r = self._selected()
        if r < 0:
            return
        s = self.steps[r]
        self.editing_row = r
        # 볼륨 맞추기 단계는 '볼륨 · 미디어' 안의 항목으로 보여줌
        shown_type = "media" if s["type"] == "volume_set" else s["type"]
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(shown_type)))
        if s["type"] == "shortcut":
            self.sc_editor.set_value(s["value"])
        elif s["type"] == "media":
            self.media_combo.setCurrentIndex(max(0, self.media_combo.findData(s["value"])))
        elif s["type"] == "delay":
            num, unit = ms_to_unit(s["value"])
            self.delay_spin.setValue(max(1, num))
            idx = self.delay_unit.findText(unit)
            if idx >= 0:
                self.delay_unit.setCurrentIndex(idx)
        elif s["type"] == "wait_until":
            t = QTime.fromString(s["value"], "HH:mm")
            if t.isValid():
                self.time_edit.setTime(t)
        elif s["type"] == "volume_set":
            self.media_combo.setCurrentIndex(max(0, self.media_combo.findData(self.VOLUME_SET)))
            try:
                self.vol_spin.setValue(max(0, min(100, int(s["value"]))))
            except ValueError:
                self.vol_spin.setValue(50)
        else:
            self.val_edit.setText(s["value"])
        self.editor_title.setText(f"{r + 1}번 단계 수정 중")
        self.add_btn.setText("수정 적용")
        self.add_btn.icon_name = "check"
        self.cancel_edit_btn.show()

    def _reset_editor(self):
        self.editing_row = -1
        self.val_edit.clear()
        self.sc_editor.set_value("")
        self.delay_spin.setValue(1)
        self.delay_unit.setCurrentText("초")
        self.time_edit.setTime(QTime.currentTime())
        self.vol_spin.setValue(50)
        self.editor_title.setText("새 단계 추가")
        self.add_btn.setText("단계 추가")
        self.add_btn.icon_name = "plus"
        self.add_btn.updateGeometry()
        self.cancel_edit_btn.hide()

    def _toggle_record(self):
        if not self.recorder.recording:
            self.recorder.record_delays = self.delay_toggle.isChecked()
            self.recorder.start()
            self.rec_btn.setText("녹화 멈추기")
            self.rec_btn.set_tint("clear")
        else:
            steps = self.recorder.stop()
            self.rec_btn.setText("녹화 시작")
            self.rec_btn.set_tint("red")
            if steps:
                self.steps.extend(steps)
                self._refresh_list(len(self.steps) - 1)

    def reject(self):
        if self.recorder.recording:   # 녹화 중 Esc 는 녹화로 기록되므로 창을 닫지 않음
            return
        super().reject()

    def macro_json(self) -> str:
        return json.dumps(self.steps, ensure_ascii=False)
