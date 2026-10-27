"""설치된 앱(시작 메뉴 등록 앱) 선택 대화상자 모듈."""

from __future__ import annotations

import threading

from PySide6.QtCore import Qt, Signal, QObject
from PySide6.QtWidgets import (
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
)

from core.app_finder import list_start_apps, app_launch_command
from ui.widgets import GlassDialog, GlassButton
from ui.theme import T


class _AppLoadWorker(QObject):
    loaded = Signal(list)


class AppPickerDialog(GlassDialog):
    """시작 메뉴에 등록된 앱 목록에서 실행할 앱을 고르는 유리 대화상자."""

    def __init__(
        self,
        parent=None,
        initial_apps: list[tuple[str, str]] | None = None,
    ):
        super().__init__(
            "설치된 앱 고르기",
            "실행할 앱을 시작 메뉴에서 골라 주세요",
            parent=parent,
            width=460,
            modeless=False,
        )
        self._closed = False
        self._apps: list[tuple[str, str]] = []
        self._selected_name: str = ""
        self._selected_command: str = ""

        # 검색창
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("앱 이름을 입력하세요")
        self.search_edit.textChanged.connect(self._on_search_text_changed)
        self.body.addWidget(self.search_edit)

        # 상태 안내 라벨
        self.status_label = QLabel("앱 목록을 불러오는 중…")
        self.status_label.setStyleSheet(f"color: {T().text_dim}; font-size: 12px; padding: 4px 2px;")
        self.body.addWidget(self.status_label)

        # 앱 목록 리스트
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.list_widget.itemSelectionChanged.connect(self._on_selection_changed)
        self.body.addWidget(self.list_widget, 1)

        # 하단 푸터 버튼
        self.footer.addStretch(1)
        self.cancel_btn = GlassButton("취소")
        self.cancel_btn.clicked.connect(self.reject)
        self.footer.addWidget(self.cancel_btn)

        self.choose_btn = GlassButton("고르기", tint="blue", icon_name="check")
        self.choose_btn.clicked.connect(self._on_choose)
        self.choose_btn.setEnabled(False)
        self.footer.addWidget(self.choose_btn)

        self.resize(460, 480)

        # 백그라운드 로더 설정
        self._worker = _AppLoadWorker()
        self._worker.loaded.connect(self._on_apps_loaded)

        if initial_apps is not None:
            self._on_apps_loaded(initial_apps)
        else:
            threading.Thread(target=self._fetch_apps_async, daemon=True).start()

    def _fetch_apps_async(self):
        try:
            apps = list_start_apps()
        except Exception:
            apps = []
        try:
            self._worker.loaded.emit(apps)
        except RuntimeError:
            pass

    def _on_apps_loaded(self, apps: list[tuple[str, str]]):
        if self._closed:
            return
        try:
            self._apps = list(apps)
            if not self._apps:
                self.status_label.setText("앱 목록을 가져오지 못했어요. 찾기… 로 직접 골라 주세요.")
                self.status_label.show()
                self.list_widget.clear()
            else:
                self.status_label.hide()
                self._filter_list()
        except RuntimeError:
            pass

    def _on_search_text_changed(self, _text: str):
        self._filter_list()

    def _filter_list(self):
        query = self.search_edit.text().strip().lower()
        self.list_widget.clear()

        matched = [
            (name, app_id)
            for name, app_id in self._apps
            if not query or query in name.lower()
        ]

        for name, app_id in matched:
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, (name, app_id))
            self.list_widget.addItem(item)

        if matched:
            self.list_widget.setCurrentRow(0)
            self.choose_btn.setEnabled(True)
        else:
            self.choose_btn.setEnabled(False)

    def _on_selection_changed(self):
        has_sel = bool(self.list_widget.selectedItems())
        self.choose_btn.setEnabled(has_sel)

    def _on_item_double_clicked(self, item: QListWidgetItem):
        self._apply_item(item)

    def _on_choose(self):
        item = self.list_widget.currentItem()
        if item is not None:
            self._apply_item(item)

    def _apply_item(self, item: QListWidgetItem):
        data = item.data(Qt.UserRole)
        if data:
            name, app_id = data
            self._selected_name = name
            self._selected_command = app_launch_command(app_id)
            self.accept()

    def selected_app(self) -> tuple[str, str]:
        """고른 앱의 (이름, 실행 명령)을 반환합니다."""
        return self._selected_name, self._selected_command

    def reject(self):
        self._closed = True
        super().reject()

    def closeEvent(self, event):
        self._closed = True
        super().closeEvent(event)
