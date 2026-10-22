"""
한국 사용자용 프로필 예시 모음
기본 작업, 오피스 프로그램(한글, 워드, 엑셀, PPT), 디자인/영상 툴(포토샵, 프리미어) 등의
자주 쓰는 단축키와 기능을 미리 구성해 둔 프로필 목록입니다.
"""

from typing import Dict, List, Any
from core.timer_manager import dump_timer
from models.button_model import DeckButtonData
from models.profile_model import DeckProfile


def _btn(row: int, col: int, name: str, action_type: str, action_data: str,
         icon: str, color: str = "clear", icon_color: str = "auto",
         toggle: bool = False, off_type: str = "none", off_data: str = "",
         children: Dict[str, DeckButtonData] = None) -> DeckButtonData:
    bid = DeckButtonData.make_id(row, col)
    return DeckButtonData(
        id=bid,
        name=name,
        icon=f"icon:{icon}" if not icon.startswith("icon:") else icon,
        action_type=action_type,
        action_data=action_data,
        row=row,
        col=col,
        color=color,
        icon_color=icon_color,
        toggle=toggle,
        off_action_type=off_type,
        off_action_data=off_data,
        children=children or {},
    )


# 더보기 버튼 안쪽 버튼 목록 (3행 4열 중 7개)
_MORE_CHILDREN: Dict[str, DeckButtonData] = {
    DeckButtonData.make_id(0, 0): _btn(0, 0, "메모장", "program", "notepad.exe", "note", "clear"),
    DeckButtonData.make_id(0, 1): _btn(0, 1, "화면 잠금", "shortcut", "Win + L", "lock", "sunset"),
    DeckButtonData.make_id(0, 2): _btn(0, 2, "작업 관리자", "shortcut", "Ctrl + Shift + Esc", "chart", "sunset"),
    DeckButtonData.make_id(0, 3): _btn(0, 3, "설정", "url", "ms-settings:", "gear", "clear"),
    DeckButtonData.make_id(1, 0): _btn(1, 0, "창 왼쪽", "shortcut", "Win + Left", "arrow_left", "mint"),
    DeckButtonData.make_id(1, 1): _btn(1, 1, "창 오른쪽", "shortcut", "Win + Right", "arrow_right", "mint"),
    DeckButtonData.make_id(1, 2): _btn(1, 2, "시계", "info", "clock", "clock", "blue"),
}


SAMPLES: List[Dict[str, Any]] = [
    {
        "key": "default",
        "name": "기본",
        "description": "자주 쓰는 웹사이트와 폴더, 볼륨 조절",
        "target_process": "",
        "rows": 3,
        "cols": 4,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "네이버", "url", "https://www.naver.com", "globe", "mint"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "유튜브", "url", "https://www.youtube.com", "video", "pink"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "화면 캡처", "shortcut", "Win + Shift + S", "camera", "sunset"),
            DeckButtonData.make_id(0, 3): _btn(0, 3, "계산기", "program", "calc.exe", "grid", "clear"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "탐색기", "shortcut", "Win + E", "folder", "yellow"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "다운로드", "folder", r"%USERPROFILE%\Downloads", "download", "yellow"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "바탕화면", "shortcut", "Win + D", "home", "clear"),
            DeckButtonData.make_id(1, 3): _btn(1, 3, "재생/정지", "media", "MediaPlayPause", "play_pause", "blue"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "볼륨 -", "media", "VolumeDown", "volume_down", "blue"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "음소거", "media", "VolumeMute", "volume_mute", "blue", toggle=True),
            DeckButtonData.make_id(2, 2): _btn(2, 2, "볼륨 +", "media", "VolumeUp", "volume_up", "blue"),
            DeckButtonData.make_id(2, 3): _btn(2, 3, "더보기", "group", "", "grid", "purple", children=_MORE_CHILDREN),
        },
    },
    {
        "key": "study",
        "name": "공부·집중",
        "description": "집중 타이머와 음악, 시계",
        "target_process": "",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "집중 25분", "timer", dump_timer({"mode": "countdown", "seconds": 1500}), "hourglass", "orange"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "쉬기 5분", "timer", dump_timer({"mode": "countdown", "seconds": 300}), "coffee", "mint"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "스톱워치", "timer", dump_timer({"mode": "stopwatch", "seconds": 1}), "timer", "blue"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "시계", "info", "clock", "clock", "blue"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "유튜브", "url", "https://www.youtube.com", "video", "pink"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "재생/정지", "media", "MediaPlayPause", "play_pause", "blue"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "음소거", "media", "VolumeMute", "volume_mute", "blue", toggle=True),
        },
    },
    {
        "key": "browser",
        "name": "인터넷",
        "description": "크롬, 엣지, 웨일 브라우저 탭 관리",
        "target_process": "chrome.exe;msedge.exe;whale.exe",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "뒤로", "shortcut", "Alt + Left", "arrow_left", "clear"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "새로고침", "shortcut", "F5", "refresh", "clear"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "앞으로", "shortcut", "Alt + Right", "arrow_right", "clear"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "새 탭", "shortcut", "Ctrl + T", "tab_new", "blue"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "탭 닫기", "shortcut", "Ctrl + W", "tab_close", "red"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "닫은 탭 열기", "shortcut", "Ctrl + Shift + T", "undo", "blue"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "즐겨찾기", "shortcut", "Ctrl + D", "star", "yellow"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "확대", "shortcut", "Ctrl + =", "plus", "mint"),
            DeckButtonData.make_id(2, 2): _btn(2, 2, "축소", "shortcut", "Ctrl + -", "search", "mint"),
        },
    },
    {
        "key": "hwp",
        "name": "한글",
        "description": "한글 문서 작성 및 서식 단축키",
        "target_process": "Hwp.exe",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "저장", "shortcut", "Alt + S", "save", "blue"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "다른 이름", "shortcut", "Alt + V", "file", "blue"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "글자 모양", "shortcut", "Alt + L", "edit", "mint"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "문단 모양", "shortcut", "Alt + T", "palette", "mint"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "쪽 나누기", "shortcut", "Ctrl + Enter", "copy", "clear"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "맞춤법", "shortcut", "F8", "check", "clear"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "인쇄", "shortcut", "Alt + P", "terminal", "clear"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "되돌리기", "shortcut", "Ctrl + Z", "undo", "orange"),
            DeckButtonData.make_id(2, 2): _btn(2, 2, "문자표", "shortcut", "Ctrl + F10", "keyboard", "yellow"),
        },
    },
    {
        "key": "word",
        "name": "워드",
        "description": "워드 문서 편집 및 서식 단축키",
        "target_process": "WINWORD.EXE",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "저장", "shortcut", "Ctrl + S", "save", "blue"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "굵게", "shortcut", "Ctrl + B", "edit", "blue"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "가운데", "shortcut", "Ctrl + E", "grid", "mint"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "쪽 나누기", "shortcut", "Ctrl + Enter", "copy", "mint"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "찾아 바꾸기", "shortcut", "Ctrl + H", "search", "yellow"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "인쇄", "shortcut", "Ctrl + P", "file", "clear"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "되돌리기", "shortcut", "Ctrl + Z", "undo", "orange"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "다시 실행", "shortcut", "Ctrl + Y", "redo", "orange"),
        },
    },
    {
        "key": "excel",
        "name": "엑셀",
        "description": "엑셀 수식 및 표 작업 단축키",
        "target_process": "EXCEL.EXE",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "저장", "shortcut", "Ctrl + S", "save", "mint"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "되돌리기", "shortcut", "Ctrl + Z", "undo", "orange"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "다시 실행", "shortcut", "Ctrl + Y", "redo", "orange"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "필터", "shortcut", "Ctrl + Shift + L", "grid", "mint"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "합계", "shortcut", "Alt + =", "plus", "mint"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "오늘 날짜", "shortcut", "Ctrl + ;", "calendar", "yellow"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "셀 서식", "shortcut", "Ctrl + 1", "palette", "yellow"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "찾기", "shortcut", "Ctrl + F", "search", "blue"),
        },
    },
    {
        "key": "ppt",
        "name": "파워포인트",
        "description": "슬라이드 쇼 및 개체 편집",
        "target_process": "POWERPNT.EXE",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "새 슬라이드", "shortcut", "Ctrl + M", "tab_new", "sunset"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "처음부터", "shortcut", "F5", "play", "sunset"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "지금부터", "shortcut", "Shift + F5", "play_pause", "sunset"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "복제", "shortcut", "Ctrl + D", "copy", "yellow"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "그룹", "shortcut", "Ctrl + G", "grid", "clear"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "그룹 해제", "shortcut", "Ctrl + Shift + G", "app", "clear"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "저장", "shortcut", "Ctrl + S", "save", "blue"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "되돌리기", "shortcut", "Ctrl + Z", "undo", "orange"),
        },
    },
    {
        "key": "photoshop",
        "name": "포토샵",
        "description": "포토샵 도구 선택 및 레이어 작업",
        "target_process": "Photoshop.exe",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "이동", "shortcut", "V", "target", "blue"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "브러시", "shortcut", "B", "brush", "blue"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "지우개", "shortcut", "E", "trash", "red"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "자유 변형", "shortcut", "Ctrl + T", "window", "yellow"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "새 레이어", "shortcut", "Ctrl + Shift + N", "tab_new", "yellow"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "되돌리기", "shortcut", "Ctrl + Z", "undo", "orange"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "다시 실행", "shortcut", "Ctrl + Shift + Z", "redo", "orange"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "저장", "shortcut", "Ctrl + S", "save", "blue"),
            DeckButtonData.make_id(2, 2): _btn(2, 2, "내보내기", "shortcut", "Ctrl + Alt + Shift + W", "upload", "mint"),
        },
    },
    {
        "key": "premiere",
        "name": "프리미어 프로",
        "description": "영상 컷 편집 및 타임라인 단축키",
        "target_process": "Adobe Premiere Pro.exe",
        "rows": 3,
        "cols": 3,
        "buttons": {
            DeckButtonData.make_id(0, 0): _btn(0, 0, "선택", "shortcut", "V", "target", "purple"),
            DeckButtonData.make_id(0, 1): _btn(0, 1, "자르기", "shortcut", "C", "cut", "purple"),
            DeckButtonData.make_id(0, 2): _btn(0, 2, "편집 추가", "shortcut", "Ctrl + K", "bolt", "purple"),
            DeckButtonData.make_id(1, 0): _btn(1, 0, "잔물결 삭제", "shortcut", "Shift + Delete", "trash", "red"),
            DeckButtonData.make_id(1, 1): _btn(1, 1, "재생/정지", "shortcut", "Space", "play_pause", "blue"),
            DeckButtonData.make_id(1, 2): _btn(1, 2, "마커", "shortcut", "M", "pin", "yellow"),
            DeckButtonData.make_id(2, 0): _btn(2, 0, "확대", "shortcut", "=", "plus", "clear"),
            DeckButtonData.make_id(2, 1): _btn(2, 1, "축소", "shortcut", "-", "search", "clear"),
            DeckButtonData.make_id(2, 2): _btn(2, 2, "내보내기", "shortcut", "Ctrl + M", "video", "mint"),
        },
    },
]


def create_sample_profile(sample_item: Dict[str, Any], profile_id: str = None) -> DeckProfile:
    """SAMPLES 의 항목을 기반으로 새 DeckProfile 객체를 생성합니다."""
    pid = profile_id or f"profile_{sample_item['key']}"
    # 버튼 복제
    buttons = {bid: btn.clone() for bid, btn in sample_item["buttons"].items()}
    return DeckProfile(
        id=pid,
        name=sample_item["name"],
        target_process=sample_item.get("target_process", ""),
        target_title="",
        buttons=buttons,
    )
