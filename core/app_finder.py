"""설치된 앱(시작 메뉴 등록 앱) 검색 및 실행 명령 생성 모듈."""

from __future__ import annotations

import json
import os
import subprocess
import sys

_CACHE: list[tuple[str, str]] | None = None


def parse_start_apps_json(text: str) -> list[tuple[str, str]]:
    """PowerShell Get-StartApps JSON 출력을 파싱하여 (이름, AppID) 목록을 반환합니다.

    - 단일 객체 또는 리스트 형태 모두 지원
    - 이름이나 AppID가 비어 있으면 건너뜀
    - 이름 기준 가나다/ABC 정렬 및 중복 이름 제거
    """
    if not text or not text.strip():
        return []

    try:
        data = json.loads(text)
    except Exception:
        return []

    if isinstance(data, dict):
        items = [data]
    elif isinstance(data, list):
        items = data
    else:
        return []

    seen_names: set[str] = set()
    unique: list[tuple[str, str]] = []

    for item in items:
        if not isinstance(item, dict):
            continue
        name = str(item.get("Name") or item.get("name") or "").strip()
        app_id = str(item.get("AppID") or item.get("app_id") or item.get("AppId") or "").strip()
        if not name or not app_id:
            continue
        name_key = name.lower()
        if name_key in seen_names:
            continue
        seen_names.add(name_key)
        unique.append((name, app_id))

    unique.sort(key=lambda x: (x[0].lower(), x[0]))
    return unique


def list_start_apps(force: bool = False) -> list[tuple[str, str]]:
    """Windows 시작 메뉴에 등록된 앱의 (이름, AppID) 목록을 반환합니다.

    - Windows가 아니면 빈 목록을 반환합니다.
    - 캐시를 활용하여 force=True가 아니면 재실행하지 않습니다.
    - 실행 중 어떤 오류가 발생해도 예외를 던지지 않고 빈 목록을 반환합니다.
    """
    global _CACHE
    if sys.platform != "win32":
        return []

    if not force and _CACHE is not None:
        return list(_CACHE)

    try:
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [
            "powershell",
            "-NoProfile",
            "-Command",
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress",
        ]
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            timeout=15,
        )
        if res.returncode == 0 and res.stdout.strip():
            _CACHE = parse_start_apps_json(res.stdout)
        else:
            _CACHE = []
    except Exception:
        _CACHE = []

    return list(_CACHE)


def find_app(
    keywords: str | list[str],
    apps: list[tuple[str, str]] | None = None,
) -> tuple[str, str] | None:
    """키워드로 설치된 앱을 찾아 (이름, AppID) 튜플을 반환합니다.

    keywords는 "|"로 구분된 여러 후보(예: "Claude|클로드")를 지원합니다.
    각 후보마다 대소문자를 무시하고:
    1) 이름이 정확히 같은 것
    2) 이름이 해당 글자로 시작하는 것
    3) 이름에 해당 글자가 포함된 것
    순서로 첫 번째 일치 항목을 반환합니다. 없으면 None을 반환합니다.
    """
    if apps is None:
        apps = list_start_apps()
    if not apps:
        return None

    if isinstance(keywords, str):
        candidates = [k.strip() for k in keywords.split("|") if k.strip()]
    else:
        candidates = [k.strip() for k in keywords if k.strip()]

    for cand in candidates:
        cand_lower = cand.lower()
        # 1. 정확히 같은 것
        for app in apps:
            if app[0].lower() == cand_lower:
                return app
        # 2. 그 글자로 시작하는 것
        for app in apps:
            if app[0].lower().startswith(cand_lower):
                return app
        # 3. 이름에 들어 있는 것
        for app in apps:
            if cand_lower in app[0].lower():
                return app

    return None


def app_launch_command(app_id: str) -> str:
    """AppID로부터 실행 명령 문자열을 생성합니다.

    실제로 존재하는 파일 경로면 그대로 반환하고,
    그렇지 않으면 "explorer.exe shell:AppsFolder\\AppID" 형태로 반환합니다.
    """
    if os.path.exists(app_id):
        return app_id
    return r"explorer.exe shell:AppsFolder\\" + app_id


def is_app_command(command: str) -> bool:
    """주어진 명령이 앱 실행 명령("explorer.exe shell:AppsFolder\\")인지 확인합니다."""
    if not command or not isinstance(command, str):
        return False
    prefix = r"explorer.exe shell:appsfolder\\"
    return command.strip().lower().startswith(prefix)
