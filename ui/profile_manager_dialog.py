"""
프로필 관리 창
프로필 만들기 / 이름 바꾸기 / 연결 프로그램 지정 / 복제 / 삭제 / 내보내기 / 가져오기를 합니다.
'저장'을 누르기 전까지는 실제 덱에 반영되지 않습니다.
"""

import time
from typing import Dict

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem, QLineEdit, QComboBox,
    QFileDialog,
)

from core.app_detector import AppDetector
from models.profile_model import DeckProfile
from ui.widgets import GlassDialog, GlassButton, section_label, hint_label, ask, inform


class ProfileManagerDialog(GlassDialog):
    def __init__(self, profiles: Dict[str, DeckProfile], current_id: str, storage, parent=None):
        super().__init__("프로필 관리", "프로그램마다 다른 버튼 구성을 쓸 수 있어요", parent=parent, width=620)
        self.profiles = profiles
        self.selected_id = current_id
        self.storage = storage
        self._loading = False

        main = QHBoxLayout()
        main.setSpacing(16)
        left = QVBoxLayout()
        left.setSpacing(8)
        self.list = QListWidget()
        self.list.setMinimumWidth(220)
        self.list.currentItemChanged.connect(self._on_select)
        left.addWidget(self.list, 1)
        lb = QHBoxLayout()
        lb.setSpacing(6)
        add = GlassButton("새로", tint="blue", icon_name="plus")
        add.clicked.connect(self._add)
        dup = GlassButton("복제", icon_name="duplicate")
        dup.clicked.connect(self._duplicate)
        self.del_btn = GlassButton("삭제", icon_name="trash")
        self.del_btn.clicked.connect(self._delete)
        lb.addWidget(add)
        lb.addWidget(dup)
        lb.addStretch(1)
        lb.addWidget(self.del_btn)
        left.addLayout(lb)
        main.addLayout(left, 1)

        right = QVBoxLayout()
        right.setSpacing(8)
        right.addWidget(section_label("이름"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self._on_name)
        right.addWidget(self.name_edit)
        right.addWidget(section_label("연결 프로그램"))
        right.addWidget(hint_label("이 프로그램을 쓰면 자동으로 이 프로필로 바뀌어요. 비우면 연결 없음."))
        self.proc_edit = QLineEdit()
        self.proc_edit.setPlaceholderText("예: chrome.exe")
        self.proc_edit.textChanged.connect(self._on_proc)
        right.addWidget(self.proc_edit)
        pr = QHBoxLayout()
        self.proc_combo = QComboBox()
        self.proc_combo.activated.connect(self._on_proc_pick)
        pr.addWidget(self.proc_combo, 1)
        refresh = GlassButton(icon_name="refresh", square=True, size=34)
        refresh.setToolTip("지금 실행 중인 프로그램 다시 불러오기")
        refresh.clicked.connect(self._refresh_processes)
        pr.addWidget(refresh)
        right.addLayout(pr)
        right.addWidget(section_label("창 제목 조건 (선택)"))
        right.addWidget(hint_label("창 제목에 이 글자가 있을 때만 바뀌어요. 쉼표로 여러 개. "
                                   "예: 연결 프로그램 chrome.exe + 창 제목 ‘YouTube’ → 크롬에서 유튜브를 볼 때만"))
        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("예: YouTube, 유튜브")
        self.title_edit.textChanged.connect(self._on_title)
        right.addWidget(self.title_edit)

        right.addSpacing(8)
        right.addWidget(section_label("파일로 주고받기"))
        right.addWidget(hint_label("프로필을 파일 하나로 저장해서 다른 컴퓨터로 옮기거나 공유할 수 있어요. 아이콘 그림도 함께 담겨요."))
        io = QHBoxLayout()
        exp = GlassButton("내보내기", icon_name="export")
        exp.clicked.connect(self._export)
        imp = GlassButton("가져오기", icon_name="import")
        imp.clicked.connect(self._import)
        io.addWidget(exp)
        io.addWidget(imp)
        io.addStretch(1)
        right.addLayout(io)
        right.addStretch(1)
        main.addLayout(right, 1)
        self.body.addLayout(main, 1)

        self.footer.addStretch(1)
        cancel = GlassButton("취소")
        cancel.clicked.connect(self.reject)
        self.footer.addWidget(cancel)
        ok = GlassButton("저장", tint="orange", icon_name="check")
        ok.clicked.connect(self.accept)
        self.footer.addWidget(ok)

        self._refresh_processes()
        self._populate(current_id)
        self.resize(self.width(), 560)

    def _populate(self, select_id=None):
        self.list.blockSignals(True)
        self.list.clear()
        for pid, prof in self.profiles.items():
            label = self._label(prof)
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, pid)
            self.list.addItem(item)
            if pid == select_id:
                self.list.setCurrentItem(item)
        self.list.blockSignals(False)
        if self.list.currentItem() is None and self.list.count():
            self.list.setCurrentRow(0)
        self._on_select(self.list.currentItem(), None)

    @staticmethod
    def _label(prof) -> str:
        cond = []
        if prof.target_process:
            cond.append(prof.target_process)
        if prof.target_title:
            cond.append(f"제목: {prof.target_title}")
        return prof.name + "\n" + (" · ".join(cond) if cond else "연결 없음")

    def _current(self):
        item = self.list.currentItem()
        return self.profiles.get(item.data(Qt.UserRole)) if item else None

    def _on_select(self, item, _prev):
        prof = self._current()
        self._loading = True
        self.name_edit.setText(prof.name if prof else "")
        self.proc_edit.setText(prof.target_process if prof else "")
        self.title_edit.setText(prof.target_title if prof else "")
        self._loading = False
        if prof:
            self.selected_id = prof.id
        self.del_btn.setEnabled(len(self.profiles) > 1)

    def _refresh_item(self):
        prof, item = self._current(), self.list.currentItem()
        if prof and item:
            item.setText(self._label(prof))

    def _on_name(self, text):
        prof = self._current()
        if prof and not self._loading:
            prof.name = text.strip() or "이름 없음"
            self._refresh_item()

    def _on_proc(self, text):
        prof = self._current()
        if prof and not self._loading:
            prof.target_process = text.strip()
            self._refresh_item()

    def _on_title(self, text):
        prof = self._current()
        if prof and not self._loading:
            prof.target_title = text.strip()
            self._refresh_item()

    def _refresh_processes(self):
        self.proc_combo.clear()
        self.proc_combo.addItem("실행 중인 프로그램에서 고르기…", "")
        for name in AppDetector.get_visible_windows_processes():
            self.proc_combo.addItem(name, name)

    def _on_proc_pick(self, idx):
        name = self.proc_combo.itemData(idx)
        if name:
            self.proc_edit.setText(name)
        self.proc_combo.setCurrentIndex(0)

    def _new_id(self) -> str:
        pid = f"profile_{int(time.time() * 1000)}"
        while pid in self.profiles:
            pid += "_1"
        return pid

    def _add(self):
        pid = self._new_id()
        self.profiles[pid] = DeckProfile(id=pid, name="새 프로필")
        self._populate(pid)
        self.name_edit.setFocus()
        self.name_edit.selectAll()

    def _duplicate(self):
        prof = self._current()
        if not prof:
            return
        pid = self._new_id()
        copy = prof.copy()
        copy.id, copy.name, copy.target_process = pid, prof.name + " 복사본", ""
        self.profiles[pid] = copy
        self._populate(pid)

    def _delete(self):
        prof = self._current()
        if not prof or len(self.profiles) <= 1:
            return
        if ask(self, "프로필 삭제", f"‘{prof.name}’ 프로필을 지울까요?\n안에 있는 버튼도 함께 지워져요.",
               ok_text="삭제", danger=True):
            del self.profiles[prof.id]
            self._populate(next(iter(self.profiles)))

    def _export(self):
        prof = self._current()
        if not prof:
            return
        path, _ = QFileDialog.getSaveFileName(self, "프로필 내보내기", f"{prof.name}.vdeck.json",
                                              "Virtual Deck 프로필 (*.vdeck.json *.json)")
        if path:
            ok, msg = self.storage.export_profile(prof, path)
            inform(self, "내보내기" if ok else "실패", msg)

    def _import(self):
        path, _ = QFileDialog.getOpenFileName(self, "프로필 가져오기", "",
                                              "Virtual Deck 프로필 (*.vdeck.json *.json)")
        if not path:
            return
        prof, msg = self.storage.import_profile(path, set(self.profiles))
        if prof is None:
            inform(self, "가져오기 실패", msg)
            return
        names = {p.name for p in self.profiles.values()}
        if prof.name in names:
            prof.name += " (가져옴)"
        self.profiles[prof.id] = prof
        self._populate(prof.id)
