"""
경로 관리 모듈
프로그램이 어디에서 실행되든(파이썬 실행 / EXE 실행) 같은 규칙으로
설정 파일, 아이콘, 글꼴 위치를 찾아 줍니다.

- 리소스(글꼴, 기본 아이콘): 프로그램에 함께 포함된 읽기 전용 파일
- 데이터(config.json, 사용자 아이콘, 백업):
    · 휴대용(압축 폴더)·파이썬 실행: 프로그램 옆 data 폴더 (폴더째 옮겨도 그대로 동작)
    · 설치판: 사용자 폴더 %APPDATA%/VirtualDeck (설치 프로그램이 EXE 옆에 installed.txt 를 만들어 둠)
- 프로그램이 만드는 임시 파일도 모두 데이터 폴더의 cache 안에 두어, 삭제할 때 흔적이 남지 않게 합니다.
"""

import os
import sys
import shutil
import hashlib
from typing import Optional

IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".ico", ".bmp", ".gif", ".svg", ".webp")


def is_frozen() -> bool:
    """PyInstaller로 만든 EXE에서 실행 중인지 여부"""
    return bool(getattr(sys, "frozen", False))


def project_dir() -> str:
    """소스 코드 기준 프로젝트 폴더 (core 폴더의 상위)"""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def app_dir() -> str:
    """사용자 데이터가 저장될 기준 폴더 (EXE면 EXE 옆, 아니면 프로젝트 폴더)"""
    if is_frozen():
        return os.path.dirname(os.path.abspath(sys.executable))
    return project_dir()


INSTALLED_MARKER = "installed.txt"


def is_installed() -> bool:
    """설치 프로그램으로 설치된 버전인지 (EXE 옆 installed.txt 로 판단)"""
    return is_frozen() and os.path.exists(os.path.join(app_dir(), INSTALLED_MARKER))


def resource_dir() -> str:
    """프로그램에 포함된 리소스 폴더 (EXE면 임시 압축 해제 폴더)"""
    if is_frozen():
        return getattr(sys, "_MEIPASS", app_dir())
    return project_dir()


def resource_path(*parts: str) -> str:
    return os.path.join(resource_dir(), "data", *parts)


def data_dir() -> str:
    # 테스트할 때는 VIRTUALDECK_DATA_DIR 로 다른 폴더를 써서 실제 설정을 건드리지 않음
    path = os.environ.get("VIRTUALDECK_DATA_DIR")
    if not path:
        if is_installed():
            base = os.environ.get("APPDATA") or os.path.expanduser("~")
            path = os.path.join(base, "VirtualDeck")
        else:
            path = os.path.join(app_dir(), "data")
    os.makedirs(path, exist_ok=True)
    return path


def cache_dir() -> str:
    """프로그램이 만드는 임시 파일 자리 (Windows 임시 폴더를 쓰지 않음)"""
    path = os.path.join(data_dir(), "cache")
    os.makedirs(path, exist_ok=True)
    return path


def icons_dir() -> str:
    path = os.path.join(data_dir(), "icons")
    os.makedirs(path, exist_ok=True)
    return path


def fonts_dir() -> str:
    return resource_path("fonts")


def ensure_default_icons() -> None:
    """EXE 첫 실행 시 기본 아이콘을 data/icons 로 복사합니다."""
    src = resource_path("icons")
    dst = icons_dir()
    if not os.path.isdir(src) or os.path.abspath(src) == os.path.abspath(dst):
        return
    for name in os.listdir(src):
        target = os.path.join(dst, name)
        if not os.path.exists(target):
            try:
                shutil.copy2(os.path.join(src, name), target)
            except OSError:
                pass


def looks_like_image_path(icon: str) -> bool:
    """아이콘 문자열이 이미지 파일 경로인지(이모지가 아닌지) 판단합니다."""
    if not icon:
        return False
    low = icon.strip().lower()
    return low.endswith(IMAGE_EXTS) or ("/" in low) or ("\\" in low)


def resolve_icon(icon: str) -> Optional[str]:
    """
    저장된 아이콘 문자열을 실제 파일 경로로 바꿉니다.
    예전 버전처럼 절대 경로가 저장돼 있고 폴더가 옮겨졌다면,
    파일 이름으로 data/icons 안에서 다시 찾아 깨진 아이콘을 복구합니다.
    """
    if not looks_like_image_path(icon):
        return None
    icon = icon.strip().strip("\"'")
    candidates = []
    if os.path.isabs(icon):
        candidates.append(icon)
    else:
        candidates.append(os.path.join(data_dir(), icon))
        candidates.append(os.path.join(resource_dir(), "data", icon))
    base = os.path.basename(icon.replace("\\", "/"))
    candidates.append(os.path.join(icons_dir(), base))
    candidates.append(resource_path("icons", base))
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    return None


def to_stored_icon(path: str) -> str:
    """data 폴더 안의 파일이면 'icons/xxx.png' 같은 상대 경로로 바꿔 저장합니다."""
    if not path or not looks_like_image_path(path):
        return path
    try:
        abs_path = os.path.abspath(path)
        root = os.path.abspath(data_dir())
        if os.path.commonpath([abs_path, root]) == root:
            return os.path.relpath(abs_path, root).replace("\\", "/")
    except ValueError:
        pass  # 다른 드라이브인 경우
    return path


def import_icon_file(src_path: str) -> str:
    """외부 이미지 파일을 data/icons 로 복사하고 저장용 상대 경로를 돌려줍니다."""
    if not src_path or not os.path.isfile(src_path):
        return src_path
    root = os.path.abspath(icons_dir())
    abs_src = os.path.abspath(src_path)
    try:
        if os.path.commonpath([abs_src, root]) == root:
            return to_stored_icon(abs_src)
    except ValueError:
        pass
    name, ext = os.path.splitext(os.path.basename(abs_src))
    with open(abs_src, "rb") as f:
        digest = hashlib.md5(f.read()).hexdigest()[:6]
    target = os.path.join(root, f"{name}_{digest}{ext.lower()}")
    if not os.path.exists(target):
        shutil.copy2(abs_src, target)
    return to_stored_icon(target)


def safe_file_name(text: str) -> str:
    keep = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in text)
    return keep.strip("._")[:40] or "icon"
