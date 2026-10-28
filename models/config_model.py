"""
환경설정 데이터 모델
그리드 크기, 모양, 배경, 동작 방식 등 프로그램 전체 설정을 담습니다.
"""

import re
from dataclasses import dataclass, asdict, fields, field
from typing import Any, Dict, Optional, List

# 버튼 크기 규격: 이름 → (버튼 크기, 권장 간격)
SIZE_PRESETS = {
    "SS": (64, 4),
    "S": (78, 5),
    "M": (94, 6),
    "L": (114, 7),
    "EX": (134, 8),
}


def clean_custom_colors(values) -> List[str]:
    """내 색 목록 정리: '#rrggbb' 만, 소문자, 중복 제거, 앞에서부터 최대 12개"""
    out = []
    if isinstance(values, list):
        for v in values:
            if isinstance(v, str) and re.match(r"^#[0-9a-fA-F]{6}$", v):
                v = v.lower()
                if v not in out:
                    out.append(v)
    return out[:12]


@dataclass
class AppConfig:
    # 배치
    rows: int = 3
    cols: int = 3
    button_size: int = 94
    spacing: int = 6
    layout_version: int = 3         # 2차 개선(간격 계산 방식 변경) 이후 버전

    # 창
    window_x: Optional[int] = None
    window_y: Optional[int] = None
    always_on_top: bool = True
    opacity: float = 1.0

    # 모양
    theme: str = "light"            # 'light' | 'dark'
    font_size: str = "M"            # 'S' | 'M' | 'L'
    show_labels: bool = True        # 버튼 이름 표시
    icon_style: str = "line"        # 'line' | 'duotone' | 'emoji'

    # 배경: 'glass'(뒤가 비치는 유리) | 'clear'(투명 - 버튼만) | 'color' | 'gradient' | 'image'
    bg_type: str = "glass"
    glass_clarity: int = 25         # 유리: 맑게 ↔ 뿌옇게 (0 = 가장 맑음, 100 = 가장 뿌얌)
    glass_blur: int = 14            # 뒤 비침 흐림 정도 (glass_clarity 에서 연동)
    glass_frost: int = 20           # 유리 뿌옇기 (glass_clarity 에서 연동)
    glass_tint: str = ""            # 유리판 옅은 색 ('sky', 'sunset', 'forest' 등 theme.TINTS)
    bg_color: str = "#dfe7f3"
    bg_gradient_start: str = "#c7d8f5"
    bg_gradient_end: str = "#f4d9e8"
    bg_gradient_dir: str = "top_to_bottom"   # 'top_to_bottom' | 'left_to_right' | 'diagonal'
    bg_image_path: str = ""
    bg_image_zoom: float = 1.0
    bg_image_x: int = 0
    bg_image_y: int = 0

    # 동작
    auto_switch_profile: bool = True
    always_show_header: bool = False  # 위쪽 메뉴 항상 보이기
    auto_start: bool = False
    auto_fade: bool = False
    auto_fade_delay: int = 6        # 초
    auto_fade_opacity: float = 0.35
    snap_edges: bool = True
    show_toast: bool = True
    power_save: bool = True         # 마우스가 덱 위에 없으면 뒤 비침 새로고침을 천천히
    sync_toggle_state: bool = True  # 음소거 등 켜기/끄기 버튼을 실제 상태와 맞추기
    hold_ms: int = 550              # 길게 누르기로 판단하는 시간
    backup_days: int = 7            # 자동 백업 보관 일수
    pycaw_prompt: bool = True       # pycaw 가 없을 때 설치할지 물어보기
    user_themes: Dict[str, Any] = field(default_factory=dict)   # 내가 저장한 덱 테마
    custom_colors: List[str] = field(default_factory=list)   # 내가 고른 색 (#rrggbb, 최대 12개)
    ui_font: str = ""   # 화면 글꼴 (비면 기본 Pretendard)
    tray_hint_shown: bool = False

    def copy(self) -> "AppConfig":
        return AppConfig.from_dict(self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        known = {f.name: f for f in fields(cls)}
        cfg = cls()
        raw = data or {}
        for key, value in raw.items():
            if key in known and (value is not None or key in ("window_x", "window_y")):
                setattr(cfg, key, value)
        # 예전 시스템 흐림("system") → "clear"(투명 버튼만) 자동 변환
        if cfg.bg_type == "system":
            cfg.bg_type = "clear"
        elif cfg.bg_type == "transparent":
            cfg.bg_type = "glass"
        if cfg.bg_type not in ("glass", "clear", "color", "gradient", "image"):
            cfg.bg_type = "glass"

        # 유리 슬라이더 변환: glass_clarity 하나로 합침
        if "glass_clarity" in raw:
            clarity_val = int(raw["glass_clarity"])
        elif "glass_frost" in raw:
            clarity_val = int(raw["glass_frost"])
        else:
            clarity_val = 20
        cfg.set_clarity(clarity_val)

        # 예전 버전 값 정리
        if int(raw.get("layout_version", 1)) < 3:
            cfg.spacing = max(2, round(int(cfg.spacing) * 0.6))
            cfg.layout_version = 3
        if cfg.icon_style not in ("line", "duotone", "emoji"):
            cfg.icon_style = "line"
        if getattr(cfg, "font_size", None) not in ("S", "M", "L"):
            cfg.font_size = "M"
        if not isinstance(getattr(cfg, "ui_font", None), str):
            cfg.ui_font = ""
        else:
            cfg.ui_font = cfg.ui_font.strip()
            if len(cfg.ui_font) > 80:
                cfg.ui_font = ""
        cfg.hold_ms = max(300, min(1500, int(cfg.hold_ms)))
        cfg.backup_days = max(1, min(60, int(cfg.backup_days)))
        if not isinstance(cfg.user_themes, dict):
            cfg.user_themes = {}
        cfg.custom_colors = clean_custom_colors(cfg.custom_colors)
        if cfg.theme not in ("light", "dark"):
            cfg.theme = "light"
        cfg.rows = max(1, min(8, int(cfg.rows)))
        cfg.cols = max(1, min(8, int(cfg.cols)))
        cfg.button_size = max(56, min(160, int(cfg.button_size)))
        cfg.spacing = max(0, min(30, int(cfg.spacing)))
        cfg.opacity = max(0.3, min(1.0, float(cfg.opacity)))
        cfg.bg_image_zoom = float(cfg.bg_image_zoom)
        cfg.auto_fade_delay = max(1, min(60, int(cfg.auto_fade_delay)))
        cfg.auto_fade_opacity = max(0.1, min(0.9, float(cfg.auto_fade_opacity)))
        return cfg

    # 덱 테마로 함께 저장되는 항목 (모양 관련 설정만)
    THEME_KEYS = ("theme", "icon_style", "show_labels", "opacity", "bg_type", "glass_clarity",
                  "glass_blur", "glass_frost", "glass_tint",
                  "bg_color", "bg_gradient_start", "bg_gradient_end", "bg_gradient_dir",
                  "bg_image_path", "bg_image_zoom", "bg_image_x", "bg_image_y", "ui_font")

    def set_clarity(self, val: int) -> None:
        """유리 맑기(0=가장 맑음 ~ 100=가장 뿌얌)를 설정하고 blur 및 frost를 연동 계산합니다."""
        v = max(0, min(100, int(val)))
        self.glass_clarity = v
        self.glass_blur = int(round(10 + v * 0.32))
        self.glass_frost = v

    def theme_dict(self) -> Dict[str, Any]:
        return {k: getattr(self, k) for k in self.THEME_KEYS}

    def apply_theme_dict(self, data: Dict[str, Any]) -> None:
        for k in self.THEME_KEYS:
            if k in data:
                setattr(self, k, data[k])
        if "glass_clarity" in data:
            self.set_clarity(data["glass_clarity"])

    def size_preset(self) -> str:
        for key, (size, _) in SIZE_PRESETS.items():
            if abs(size - self.button_size) <= 3:
                return key
        return "M"
