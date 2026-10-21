"""
프로필 데이터 모델
작업 환경(기본, 크롬, 포토샵 …)마다 따로 가지는 버튼 구성을 담습니다.
"""

from dataclasses import dataclass, field
from typing import Any, Dict

from models.button_model import DeckButtonData


@dataclass
class DeckProfile:
    """
    Attributes:
        id: 프로필 고유 ID
        name: 화면에 보이는 이름
        target_process: 이 프로그램을 쓰면 자동으로 전환 (예: 'chrome.exe')
        target_title: 창 제목에 이 글자가 있으면 전환 (쉼표로 여러 개, 예: 'YouTube, 유튜브')
        buttons: 버튼 ID → 버튼 데이터
    """
    id: str
    name: str
    target_process: str = ""
    target_title: str = ""
    buttons: Dict[str, DeckButtonData] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "target_process": self.target_process,
            "target_title": self.target_title,
            "buttons": {k: v.to_dict() for k, v in self.buttons.items()},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DeckProfile":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", "새 프로필"),
            target_process=data.get("target_process", ""),
            target_title=data.get("target_title", ""),
            buttons={k: DeckButtonData.from_dict(v) for k, v in (data.get("buttons") or {}).items()},
        )

    def copy(self) -> "DeckProfile":
        return DeckProfile.from_dict(self.to_dict())
