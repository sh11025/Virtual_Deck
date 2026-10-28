"""
버튼 데이터 모델
버튼 하나에 담기는 정보(이름, 아이콘, 색, 동작, 켜기/끄기, 묶음 안의 버튼들)를 정의합니다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class DeckButtonData:
    """
    Attributes:
        id: 버튼 고유 ID (예: 'btn_0_0' → 0행 0열)
        name: 버튼에 표시될 이름
        icon: 테마 아이콘('icon:이름'), 이모지, 또는 이미지 경로(data 폴더 기준 상대 경로)
        icon_color: 아이콘 색 ('auto' 또는 ui.theme.ICON_COLORS 의 이름)
        action_type: 'none' | 'url' | 'program' | 'file' | 'folder' | 'shortcut' | 'media' | 'macro' | 'group'
        action_data: 동작에 필요한 값 (주소, 경로, 단축키 글자, 매크로 JSON 등)
        color: 유리 색 ('clear', 'orange', 'blue', 'mint', 'purple', 'pink', 'red', 'yellow')
        toggle: 켜기/끄기 버튼으로 쓸지 여부
        toggle_on: 지금 켜져 있는지
        off_action_type / off_action_data: 켜진 상태에서 누를 때 실행할 동작(비우면 같은 동작 반복)
        children: 버튼 묶음(폴더 버튼) 안에 들어 있는 버튼들
        span_cols / span_rows: 버튼이 차지하는 칸 수 (1 또는 2) — 큰 버튼
        hold_action_type / hold_action_data: 길게 눌렀을 때 할 일
    """
    id: str
    name: str = ""
    icon: str = ""
    action_type: str = "none"
    action_data: str = ""
    row: int = 0
    col: int = 0
    color: str = "clear"
    icon_color: str = "auto"
    toggle: bool = False
    toggle_on: bool = False
    off_action_type: str = "none"
    off_action_data: str = ""
    span_cols: int = 1
    span_rows: int = 1
    hold_action_type: str = "none"
    hold_action_data: str = ""
    children: Dict[str, "DeckButtonData"] = field(default_factory=dict)

    def has_hold(self) -> bool:
        return self.hold_action_type not in ("", "none") and bool(self.hold_action_data)

    def is_empty(self) -> bool:
        if self.action_type in ("group", "info", "back"):
            return False
        return self.action_type == "none" or not self.action_data

    def clone(self, new_id: str = None, row: int = None, col: int = None) -> "DeckButtonData":
        d = self.to_dict()
        if new_id is not None:
            d["id"] = new_id
        if row is not None:
            d["row"] = row
        if col is not None:
            d["col"] = col
        return DeckButtonData.from_dict(d)

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "name": self.name,
            "icon": self.icon,
            "action_type": self.action_type,
            "action_data": self.action_data,
            "row": self.row,
            "col": self.col,
            "color": self.color,
            "icon_color": self.icon_color,
            "toggle": self.toggle,
            "toggle_on": self.toggle_on,
            "off_action_type": self.off_action_type,
            "off_action_data": self.off_action_data,
            "span_cols": self.span_cols,
            "span_rows": self.span_rows,
            "hold_action_type": self.hold_action_type,
            "hold_action_data": self.hold_action_data,
        }
        if self.children:
            d["children"] = {k: v.to_dict() for k, v in self.children.items()}
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeckButtonData":
        action_type = data.get("action_type", "none")
        icon = data.get("icon", "")
        if action_type == "back" and icon in ("", "back", "icon:back"):
            icon = "icon:arrow_left"
        children = {k: cls.from_dict(v) for k, v in (data.get("children") or {}).items()}
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            icon=icon,
            action_type=action_type,
            action_data=data.get("action_data", ""),
            row=int(data.get("row", 0)),
            col=int(data.get("col", 0)),
            color=data.get("color", "clear") or "clear",
            icon_color=data.get("icon_color", "auto") or "auto",
            toggle=bool(data.get("toggle", False)),
            toggle_on=bool(data.get("toggle_on", False)),
            off_action_type=data.get("off_action_type", "none") or "none",
            off_action_data=data.get("off_action_data", ""),
            span_cols=max(1, min(2, int(data.get("span_cols", 1) or 1))),
            span_rows=max(1, min(2, int(data.get("span_rows", 1) or 1))),
            hold_action_type=data.get("hold_action_type", "none") or "none",
            hold_action_data=data.get("hold_action_data", ""),
            children=children,
        )

    @staticmethod
    def make_id(row: int, col: int) -> str:
        return f"btn_{row}_{col}"
