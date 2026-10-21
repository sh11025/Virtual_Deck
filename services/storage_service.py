"""
저장/불러오기 서비스
설정과 프로필을 data/config.json 에 저장하고 불러옵니다.

개선된 점
- 저장 위치를 '프로그램이 있는 폴더' 기준으로 고정 (EXE, 바로가기 실행에도 안전)
- 저장 도중 꺼져도 파일이 깨지지 않도록 임시 파일에 쓴 뒤 교체, 직전 파일은 .bak 로 보관
- 예전 버전의 깨진 아이콘 경로를 자동 복구하고 상대 경로로 정리
- 프로필 내보내기/가져오기 (아이콘 그림까지 파일 하나에 담아서)
"""

import base64
import json
import os
import shutil
import time
from typing import Any, Dict, Optional, Tuple

from core import paths
from models.button_model import DeckButtonData
from models.config_model import AppConfig
from models.profile_model import DeckProfile

EXPORT_FORMAT = "virtual-deck-profile"
THEME_FORMAT = "virtual-deck-theme"

LEGACY_THEMES = {
    "맑은 유리": "맑음",
    "젖빛 유리": "젖빛",
    "밤 유리": "밤",
    "파스텔": "노을",
    "깊은 바다": "하늘",
    "윈도우 흐림": "투명 (버튼만)",
}


class _ThemeDict(dict):
    def __getitem__(self, key):
        mapped = LEGACY_THEMES.get(key, key)
        return super().__getitem__(mapped)

    def get(self, key, default=None):
        mapped = LEGACY_THEMES.get(key, key)
        return super().get(mapped, default)

    def __contains__(self, key):
        mapped = LEGACY_THEMES.get(key, key)
        return super().__contains__(mapped)


# 기본으로 들어 있는 덱 스타일 7개 (모양 관련 설정 묶음)
BUILTIN_THEMES = _ThemeDict({
    "맑음": {"theme": "light", "bg_type": "glass", "glass_clarity": 20, "glass_tint": "", "icon_style": "line"},
    "밤": {"theme": "dark", "bg_type": "glass", "glass_clarity": 30, "glass_tint": "", "icon_style": "line"},
    "젖빛": {"theme": "light", "bg_type": "glass", "glass_clarity": 80, "glass_tint": "", "icon_style": "duotone"},
    "하늘": {"theme": "light", "bg_type": "glass", "glass_clarity": 25, "glass_tint": "sky", "icon_style": "line"},
    "노을": {"theme": "light", "bg_type": "glass", "glass_clarity": 25, "glass_tint": "sunset", "icon_style": "line"},
    "숲": {"theme": "light", "bg_type": "glass", "glass_clarity": 25, "glass_tint": "forest", "icon_style": "line"},
    "투명 (버튼만)": {"theme": "light", "bg_type": "clear", "glass_clarity": 30, "glass_tint": "", "icon_style": "line"},
})



def get_builtin_theme(name: str) -> Optional[Dict[str, Any]]:
    """이름(또는 구 이름)으로 기본 테마를 돌려줍니다."""
    mapped = LEGACY_THEMES.get(name, name)
    return BUILTIN_THEMES.get(mapped)


class StorageService:
    def __init__(self, file_name: str = "config.json"):
        self.data_dir = paths.data_dir()
        self.file_path = os.path.join(self.data_dir, file_name)
        paths.ensure_default_icons()

    # ------------------------------------------------------------ 불러오기
    def load_data(self) -> Tuple[AppConfig, Dict[str, DeckProfile], str]:
        for candidate in (self.file_path, self.file_path + ".bak"):
            if os.path.exists(candidate):
                parsed = self.load_file(candidate)
                if parsed is not None:
                    return parsed
        return self._create_default_data()

    def load_file(self, path: str):
        """설정 파일 하나를 읽어 (설정, 프로필들, 현재 프로필) 로 돌려줍니다. 실패하면 None"""
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
        except Exception as e:
            print(f"[설정 읽기 실패] {path}: {e}")
            return None
        config = AppConfig.from_dict(raw.get("config", {}))
        profiles: Dict[str, DeckProfile] = {}
        for pid, pdata in (raw.get("profiles") or {}).items():
            prof = DeckProfile.from_dict(pdata)
            prof.id = prof.id or pid
            profiles[prof.id] = prof
        if not profiles:
            return None
        for prof in profiles.values():
            self._repair_icons(prof.buttons)
            self.ensure_grid(prof, config.rows, config.cols)
        current = raw.get("current_profile_id", "")
        if current not in profiles:
            current = next(iter(profiles))
        return config, profiles, current

    def _repair_icons(self, buttons: Dict[str, DeckButtonData]) -> None:
        for btn in buttons.values():
            if paths.looks_like_image_path(btn.icon):
                found = paths.resolve_icon(btn.icon)
                if found:
                    btn.icon = paths.to_stored_icon(found)
            if btn.children:
                self._repair_icons(btn.children)

    # ------------------------------------------------------------ 저장
    def save_data(self, config: AppConfig, profiles: Dict[str, DeckProfile], current_profile_id: str) -> bool:
        data = {
            "version": 2,
            "config": config.to_dict(),
            "current_profile_id": current_profile_id,
            "profiles": {pid: p.to_dict() for pid, p in profiles.items()},
        }
        tmp = self.file_path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            if os.path.exists(self.file_path):
                shutil.copy2(self.file_path, self.file_path + ".bak")
            os.replace(tmp, self.file_path)
            self._daily_backup(config.backup_days)
            return True
        except Exception as e:
            print(f"[설정 저장 실패] {e}")
            return False

    # ------------------------------------------------------------ 자동 백업
    @property
    def backup_dir(self) -> str:
        path = os.path.join(self.data_dir, "backups")
        os.makedirs(path, exist_ok=True)
        return path

    def _daily_backup(self, keep_days: int) -> None:
        """하루에 한 번 설정 파일을 backups 폴더에 복사하고, 오래된 것은 지웁니다."""
        try:
            name = time.strftime("config_%Y-%m-%d.json")
            target = os.path.join(self.backup_dir, name)
            if not os.path.exists(target):
                shutil.copy2(self.file_path, target)
            files = sorted(f for f in os.listdir(self.backup_dir) if f.startswith("config_") and f.endswith(".json"))
            for old in files[:-max(1, keep_days)]:
                os.remove(os.path.join(self.backup_dir, old))
        except Exception as e:
            print(f"[자동 백업 실패] {e}")

    def make_backup_now(self) -> str:
        """지금 상태를 따로 백업 (되돌리기 직전 안전장치용)"""
        target = os.path.join(self.backup_dir, time.strftime("config_%Y-%m-%d_%H%M%S_before_restore.json"))
        if os.path.exists(self.file_path):
            shutil.copy2(self.file_path, target)
        return target

    def list_backups(self):
        """[(경로, 보여 줄 이름)] — 최신이 먼저"""
        out = []
        for f in sorted(os.listdir(self.backup_dir), reverse=True):
            if f.startswith("config_") and f.endswith(".json"):
                path = os.path.join(self.backup_dir, f)
                label = time.strftime("%Y년 %m월 %d일 %H:%M", time.localtime(os.path.getmtime(path)))
                if "before_restore" in f:
                    label += "  (되돌리기 전 자동 저장)"
                out.append((path, label))
        return out

    # ------------------------------------------------------------ 덱 테마
    def export_theme(self, name: str, theme: dict, file_path: str) -> Tuple[bool, str]:
        try:
            data = {"format": THEME_FORMAT, "version": 1, "name": name, "theme": dict(theme)}
            img = theme.get("bg_image_path")
            if theme.get("bg_type") == "image" and img and os.path.isfile(img):
                with open(img, "rb") as f:
                    data["image"] = {"ext": os.path.splitext(img)[1].lower(),
                                     "data": base64.b64encode(f.read()).decode("ascii")}
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, "테마를 내보냈어요."
        except Exception as e:
            return False, f"내보내기 실패: {e}"

    def import_theme(self, file_path: str):
        """(이름, 테마) 또는 (None, 오류 메시지)"""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("format") != THEME_FORMAT:
                return None, "Virtual Deck 테마 파일이 아니에요."
            theme = dict(data.get("theme") or {})
            img = data.get("image")
            if img:
                folder = os.path.join(self.data_dir, "backgrounds")
                os.makedirs(folder, exist_ok=True)
                target = os.path.join(folder, paths.safe_file_name(data.get("name", "theme")) + img.get("ext", ".png"))
                with open(target, "wb") as f:
                    f.write(base64.b64decode(img["data"]))
                theme["bg_image_path"] = target
            return data.get("name") or "가져온 테마", theme
        except Exception as e:
            return None, f"가져오기 실패: {e}"

    # ------------------------------------------------------------ 그리드 관리
    @staticmethod
    def ensure_grid(profile: DeckProfile, rows: int, cols: int) -> None:
        """빈 칸을 채워 그리드 크기에 맞춥니다. (버튼 묶음 안쪽도 함께)"""
        StorageService._fill(profile.buttons, rows, cols)
        for btn in profile.buttons.values():
            if btn.action_type == "group":
                StorageService._fill(btn.children, rows, cols)

    @staticmethod
    def _fill(buttons: Dict[str, DeckButtonData], rows: int, cols: int) -> None:
        for r in range(rows):
            for c in range(cols):
                bid = DeckButtonData.make_id(r, c)
                if bid not in buttons:
                    buttons[bid] = DeckButtonData(id=bid, row=r, col=c)

    @staticmethod
    def count_outside(profiles: Dict[str, DeckProfile], rows: int, cols: int) -> int:
        """그리드를 줄였을 때 밖으로 밀려나는 '채워진' 버튼 수"""
        n = 0
        for prof in profiles.values():
            for btn in prof.buttons.values():
                outside = btn.row >= rows or btn.col >= cols
                if outside and not btn.is_empty():
                    n += 1
                for child in btn.children.values():
                    if (child.row >= rows or child.col >= cols) and not child.is_empty():
                        n += 1
        return n

    @staticmethod
    def prune_outside(profiles: Dict[str, DeckProfile], rows: int, cols: int) -> None:
        for prof in profiles.values():
            prof.buttons = {k: b for k, b in prof.buttons.items() if b.row < rows and b.col < cols}
            for b in prof.buttons.values():
                if b.children:
                    b.children = {k: c for k, c in b.children.items() if c.row < rows and c.col < cols}

    # ------------------------------------------------------------ 아이콘 테마 변환
    @staticmethod
    def convert_emoji_icons(profiles: Dict[str, DeckProfile]) -> int:
        """이모지 아이콘을 같은 뜻의 테마 아이콘('icon:이름')으로 바꾸고, 바꾼 개수를 돌려줍니다."""
        from ui.icons import EMOJI_TO_ICON, PREFIX
        count = 0

        def walk(buttons):
            nonlocal count
            for b in buttons.values():
                key = (b.icon or "").strip()
                name = EMOJI_TO_ICON.get(key) or EMOJI_TO_ICON.get(key.replace("\ufe0f", ""))
                if name:
                    b.icon = PREFIX + name
                    count += 1
                if b.children:
                    walk(b.children)

        for prof in profiles.values():
            walk(prof.buttons)
        return count

    # ------------------------------------------------------------ 내보내기 / 가져오기
    def export_profile(self, profile: DeckProfile, file_path: str) -> Tuple[bool, str]:
        try:
            icons = {}
            self._collect_icons(profile.buttons, icons)
            data = {"format": EXPORT_FORMAT, "version": 1,
                    "profile": profile.to_dict(), "icons": icons}
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, "프로필을 내보냈어요."
        except Exception as e:
            return False, f"내보내기 실패: {e}"

    def _collect_icons(self, buttons: Dict[str, DeckButtonData], icons: Dict[str, str]) -> None:
        for btn in buttons.values():
            path = paths.resolve_icon(btn.icon)
            if path and btn.icon not in icons:
                with open(path, "rb") as f:
                    icons[btn.icon] = base64.b64encode(f.read()).decode("ascii")
            if btn.children:
                self._collect_icons(btn.children, icons)

    def import_profile(self, file_path: str, existing_ids) -> Tuple[DeckProfile, str]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("format") != EXPORT_FORMAT:
                return None, "Virtual Deck 프로필 파일이 아니에요."
            prof = DeckProfile.from_dict(data.get("profile", {}))
            mapping = {}
            for old, b64 in (data.get("icons") or {}).items():
                name = paths.safe_file_name(os.path.splitext(os.path.basename(old.replace("\\", "/")))[0])
                ext = os.path.splitext(old)[1].lower() or ".png"
                target = os.path.join(paths.icons_dir(), f"{name}_imp{int(time.time()) % 100000}{ext}")
                with open(target, "wb") as f:
                    f.write(base64.b64decode(b64))
                mapping[old] = paths.to_stored_icon(target)
            self._remap_icons(prof.buttons, mapping)
            new_id = f"profile_{int(time.time() * 1000)}"
            while new_id in existing_ids:
                new_id += "_1"
            prof.id = new_id
            return prof, "프로필을 가져왔어요."
        except Exception as e:
            return None, f"가져오기 실패: {e}"

    def _remap_icons(self, buttons, mapping) -> None:
        for btn in buttons.values():
            if btn.icon in mapping:
                btn.icon = mapping[btn.icon]
            if btn.children:
                self._remap_icons(btn.children, mapping)

    # ------------------------------------------------------------ 기본 데이터
    def _create_default_data(self) -> Tuple[AppConfig, Dict[str, DeckProfile], str]:
        config = AppConfig()
        B = DeckButtonData

        def profile(pid, name, proc, items):
            prof = DeckProfile(id=pid, name=name, target_process=proc)
            for b in items:
                prof.buttons[b.id] = b
            self.ensure_grid(prof, config.rows, config.cols)
            return prof

        default = profile("profile_default", "기본", "", [
            B("btn_0_0", "Google", "icon:globe", "url", "https://www.google.com", 0, 0, color="blue"),
            B("btn_0_1", "메모장", "icon:note", "program", "notepad.exe", 0, 1),
            B("btn_0_2", "복사", "icon:copy", "shortcut", "Ctrl + C", 0, 2),
            B("btn_1_0", "볼륨 -", "icon:volume_down", "media", "VolumeDown", 1, 0),
            B("btn_1_1", "음소거", "icon:volume_mute", "media", "VolumeMute", 1, 1, color="mint", toggle=True),
            B("btn_1_2", "붙여넣기", "icon:paste", "shortcut", "Ctrl + V", 1, 2),
            B("btn_2_0", "볼륨 +", "icon:volume_up", "media", "VolumeUp", 2, 0),
            B("btn_2_1", "재생/정지", "icon:play_pause", "media", "MediaPlayPause", 2, 1, color="orange"),
            B("btn_2_2", "캡처", "icon:screenshot", "shortcut", "Win + Shift + S", 2, 2, color="purple"),
        ])
        chrome = profile("profile_chrome", "Chrome", "chrome.exe", [
            B("btn_0_0", "뒤로", "icon:arrow_left", "shortcut", "Alt + Left", 0, 0),
            B("btn_0_1", "새로고침", "icon:refresh", "shortcut", "F5", 0, 1, color="blue"),
            B("btn_0_2", "앞으로", "icon:arrow_right", "shortcut", "Alt + Right", 0, 2),
            B("btn_1_0", "새 탭", "icon:tab_new", "shortcut", "Ctrl + T", 1, 0, color="mint"),
            B("btn_1_1", "탭 닫기", "icon:tab_close", "shortcut", "Ctrl + W", 1, 1, color="red"),
            B("btn_1_2", "북마크", "icon:star", "shortcut", "Ctrl + D", 1, 2, color="yellow"),
        ])
        photoshop = profile("profile_photoshop", "Photoshop", "Photoshop.exe", [
            B("btn_0_0", "되돌리기", "icon:undo", "shortcut", "Ctrl + Z", 0, 0),
            B("btn_0_1", "다시 실행", "icon:redo", "shortcut", "Ctrl + Shift + Z", 0, 1),
            B("btn_0_2", "저장", "icon:save", "shortcut", "Ctrl + S", 0, 2, color="orange"),
            B("btn_1_0", "다른 이름", "icon:file", "shortcut", "Ctrl + Shift + S", 1, 0),
        ])
        profiles = {p.id: p for p in (default, chrome, photoshop)}
        self.save_data(config, profiles, "profile_default")
        return config, profiles, "profile_default"
