"""
Virtual Deck 배포 파일 만들기
명령 하나로 친구에게 줄 파일을 모두 만듭니다.

사용법:  python build_exe.py            (전부 만들기)
         python build_exe.py --no-setup (설치 파일은 빼고)

결과물 (dist 폴더):
  - VirtualDeck-<버전>-Setup.exe      설치 파일 (추천) — 이것 하나만 친구에게 보내면 됩니다
  - VirtualDeck-<버전>-portable.zip   휴대용 압축 파일 — 압축 풀고 VirtualDeck.exe 실행, '완전 삭제.bat' 로 삭제
  - VirtualDeck/                      프로그램 폴더 (위 두 파일의 재료)

버전은 core/version.py 의 APP_VERSION 을 따릅니다.
"""

import os
import shutil
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
APP_DIR = os.path.join(DIST, "VirtualDeck")
INSTALLER_DIR = os.path.join(ROOT, "installer")


def ensure_package(module: str, package: str) -> bool:
    """필요한 부품이 없으면 설치합니다. 성공하면 True"""
    try:
        __import__(module)
        print(f"[확인] {package} 준비됨")
        return True
    except ImportError:
        print(f"[설치] {package} 를 설치합니다…")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])
            __import__(module)
            return True
        except Exception as e:
            print(f"[경고] {package} 설치 실패: {e}")
            return False


def app_version() -> str:
    sys.path.insert(0, ROOT)
    from core.version import APP_VERSION
    return APP_VERSION


def make_icon() -> str:
    """유리 앱 아이콘을 그려서 .ico 파일로 저장합니다."""
    sys.path.insert(0, ROOT)
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication(sys.argv)  # noqa: F841
    from ui.app_icon import make_app_pixmap
    os.makedirs(os.path.join(ROOT, "assets"), exist_ok=True)
    path = os.path.join(ROOT, "assets", "app_icon.ico")
    make_app_pixmap(256).save(path, "ICO")
    print(f"[생성] 아이콘: {path}")
    return path


# ---------------------------------------------------------------- 1. 프로그램 폴더
EXCLUDE_MODULES = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebChannel",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DExtras", "PySide6.Qt3DAnimation", "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    "PySide6.QtPdf", "PySide6.QtPdfWidgets", "PySide6.QtSql", "PySide6.QtTest",
    "PySide6.QtBluetooth", "PySide6.QtSensors", "PySide6.QtSerialPort",
    "PySide6.QtDesigner", "PySide6.QtOpenGL", "PySide6.QtOpenGLWidgets",
    "PySide6.QtPositioning", "PySide6.QtRemoteObjects", "PySide6.QtScxml",
    "PySide6.QtSpatialAudio", "PySide6.QtStateMachine", "PySide6.QtSvgWidgets",
    "PySide6.QtVirtualKeyboard", "PySide6.QtXml",
    "tkinter", "unittest", "pydoc",
]


def cleanup_app_dir(app_dir: str):
    """
    빌드된 프로그램 폴더에서 불필요한 대용량 파일들을 자동 삭제하여 용량을 최적화합니다.
    - opengl32sw.dll (~20MB, 소프트웨어 OpenGL 불필요)
    - qtbase_ko.qm 외 나머지 다국어 번역 파일
    - 미사용 imageformats 플러그인 (png/ico/jpeg/svg 만 유지)
    """
    print("      불필요한 파일 정리 중 (용량 다이어트)…")
    deleted_bytes = 0

    # 1. opengl32sw.dll 삭제
    for root, _, files in os.walk(app_dir):
        for f in files:
            if f.lower() == "opengl32sw.dll":
                p = os.path.join(root, f)
                try:
                    deleted_bytes += os.path.getsize(p)
                    os.remove(p)
                    print(f"      - 삭제: {os.path.relpath(p, app_dir)}")
                except Exception:
                    pass

    # 2. translations 정리 (qtbase_ko.qm 만 유지)
    for root, _, files in os.walk(app_dir):
        if os.path.basename(root) == "translations":
            for f in files:
                if f.endswith(".qm") and f != "qtbase_ko.qm":
                    p = os.path.join(root, f)
                    try:
                        deleted_bytes += os.path.getsize(p)
                        os.remove(p)
                    except Exception:
                        pass

    # 3. imageformats 정리 (png, ico, jpeg, svg 만 남기기)
    keep_formats = {"qpng", "qico", "qjpeg", "qsvg"}
    for root, _, files in os.walk(app_dir):
        if os.path.basename(root) == "imageformats":
            for f in files:
                name_low = f.lower()
                base_name = os.path.splitext(name_low)[0]
                if not any(base_name.startswith(k) for k in keep_formats):
                    p = os.path.join(root, f)
                    try:
                        deleted_bytes += os.path.getsize(p)
                        os.remove(p)
                    except Exception:
                        pass

    print(f"      다이어트 완료: 약 {deleted_bytes / (1024*1024):.1f} MB 절약!")


def build_app(icon: str, has_pycaw: bool) -> bool:
    """
    PyInstaller 로 프로그램 폴더(dist/VirtualDeck)를 만듭니다.
    EXE 하나로 묶는 방식보다 켜지는 속도가 빠르고 백신에 덜 걸려서 폴더 방식을 씁니다.
    """
    sep = os.pathsep  # Windows 는 ';'
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--noconsole", "--onedir", "--clean", "--noconfirm",
        "--name", "VirtualDeck",
        f"--icon={icon}",
        "--add-data", f"{os.path.join(ROOT, 'data', 'fonts')}{sep}data/fonts",
        "--add-data", f"{os.path.join(ROOT, 'data', 'icons')}{sep}data/icons",
    ]
    for mod in EXCLUDE_MODULES:
        cmd += ["--exclude-module", mod]
    if has_pycaw:
        cmd += ["--hidden-import", "pycaw.pycaw", "--collect-submodules", "pycaw",
                "--collect-submodules", "comtypes"]
    cmd.append(os.path.join(ROOT, "main.py"))
    print("\n[1/3] 프로그램 폴더 만드는 중… (1~3분)")
    result = subprocess.run(cmd, cwd=ROOT)
    exe = "VirtualDeck.exe" if os.name == "nt" else "VirtualDeck"
    ok = result.returncode == 0 and os.path.exists(os.path.join(APP_DIR, exe))
    if ok:
        cleanup_app_dir(APP_DIR)
        print("      완료: " + APP_DIR)
    else:
        print("      실패: 위쪽 오류 메시지를 확인해 주세요.")
    return ok



# ---------------------------------------------------------------- 2. 휴대용 압축 파일
def build_zip(version: str) -> str:
    """프로그램 폴더 + '완전 삭제.bat' 을 압축합니다. (설정은 압축을 푼 폴더의 data 에 저장)"""
    print("\n[2/3] 휴대용 압축 파일 만드는 중…")
    target = os.path.join(DIST, f"VirtualDeck-{version}-portable.zip")
    if os.path.exists(target):
        os.remove(target)
    uninstall_bat = os.path.join(INSTALLER_DIR, "완전 삭제.bat")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        for folder, _, files in os.walk(APP_DIR):
            for f in files:
                full = os.path.join(folder, f)
                rel = os.path.relpath(full, DIST)          # VirtualDeck/... 로 시작
                if os.path.basename(full) == "installed.txt":
                    continue                               # 휴대용에는 설치판 표시를 넣지 않음
                z.write(full, rel)
        z.write(uninstall_bat, os.path.join("VirtualDeck", "완전 삭제.bat"))
    print("      완료: " + target)
    return target


# ---------------------------------------------------------------- 3. 설치 파일
def find_iscc():
    """Inno Setup 컴파일러(ISCC.exe) 위치를 찾습니다."""
    found = shutil.which("iscc") or shutil.which("ISCC")
    if found:
        return found
    candidates = [
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Inno Setup 6", "ISCC.exe"),
        r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        r"C:\Program Files\Inno Setup 6\ISCC.exe",
    ]
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles")):
        if base:
            candidates.append(os.path.join(base, "Inno Setup 6", "ISCC.exe"))
    for cand in candidates:
        if cand and os.path.exists(cand):
            return cand
    return None


def install_inno_setup() -> bool:
    """Inno Setup 이 없으면 winget 으로 묻지 않고 바로 자동 설치합니다."""
    if not shutil.which("winget"):
        return False
    print("      Inno Setup 을 찾지 못해 winget 으로 자동 설치합니다…")
    r = subprocess.run([
        "winget", "install", "--id", "JRSoftware.InnoSetup", "-e",
        "--scope", "user",
        "--accept-source-agreements", "--accept-package-agreements",
    ])
    return r.returncode == 0


def build_setup(version: str) -> str:
    print("\n[3/3] 설치 파일 만드는 중…")
    iscc = find_iscc()
    if not iscc and install_inno_setup():
        iscc = find_iscc()
    if not iscc:
        print("      Inno Setup 을 찾지 못해 설치 파일은 건너뛰어요.")
        print("      https://jrsoftware.org/isdl.php 에서 설치하거나, 명령 창에서")
        print("      winget install --id JRSoftware.InnoSetup -e   를 실행한 뒤 다시 만들어 주세요.")
        return ""
    args = [iscc, f"/DMyAppVersion={version}"]
    if not os.path.exists(os.path.join(os.path.dirname(iscc), "Languages", "Korean.isl")):
        args.append("/DNoKorean")   # 한국어 언어 파일이 없으면 기본 언어로
    args.append(os.path.join(INSTALLER_DIR, "VirtualDeck.iss"))
    r = subprocess.run(args, cwd=INSTALLER_DIR)
    target = os.path.join(DIST, f"VirtualDeck-{version}-Setup.exe")
    if r.returncode == 0 and os.path.exists(target):
        print("      완료: " + target)
        return target
    print("      설치 파일 만들기에 실패했어요. 위쪽 오류 메시지를 확인해 주세요.")
    return ""


def archive_old_dist(current_version: str):
    """현재 버전이 아닌 이전 exe/zip 파일을 dist/old 로 이동합니다."""
    if not os.path.exists(DIST):
        return
    old_dir = os.path.join(DIST, "old")
    keep_files = {
        f"VirtualDeck-{current_version}-Setup.exe",
        f"VirtualDeck-{current_version}-portable.zip",
    }
    for item in os.listdir(DIST):
        path = os.path.join(DIST, item)
        if not os.path.isfile(path):
            continue
        if (item.endswith(".exe") or item.endswith(".zip")) and item not in keep_files:
            os.makedirs(old_dir, exist_ok=True)
            dst = os.path.join(old_dir, item)
            try:
                shutil.move(path, dst)
                print(f"[보관] 이전 버전 파일 이동: {item} -> dist/old/{item}")
            except Exception as e:
                print(f"[경고] 이전 파일 이동 실패 ({item}): {e}")


def update_readme(version: str, setup_path: str):
    """README.md 의 버전 배지, 파일명, 크기 표기를 새 버전에 맞게 자동 갱신합니다."""
    readme_path = os.path.join(ROOT, "README.md")
    if not os.path.exists(readme_path):
        return
    try:
        size_mb = ""
        if setup_path and os.path.exists(setup_path):
            size_mb = f"{os.path.getsize(setup_path) / (1024 * 1024):.1f} MB"

        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()

        import re
        content = re.sub(r'badge/version-[0-9.]+-blue', f'badge/version-{version}-blue', content)
        content = re.sub(r'alt="버전 [0-9.]+"', f'alt="버전 {version}"', content)
        content = re.sub(r'VirtualDeck-[0-9.]+-Setup\.exe', f'VirtualDeck-{version}-Setup.exe', content)
        if size_mb:
            content = re.sub(r'\|\s*`VirtualDeck-[0-9.]+-Setup\.exe`\s*\|\s*\*\*[0-9.]+\s*MB\*\*',
                             f'| `VirtualDeck-{version}-Setup.exe` | **{size_mb}**', content)

        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[갱신] README.md 버전을 {version} ({size_mb})으로 갱신했습니다.")
    except Exception as e:
        print(f"[경고] README.md 자동 갱신 실패: {e}")


def build():
    version = app_version()
    print("=" * 60)
    print(f" Virtual Deck {version} 배포 파일 만들기")
    print("=" * 60)
    archive_old_dist(version)
    if not ensure_package("PyInstaller", "pyinstaller"):
        sys.exit("PyInstaller 를 설치하지 못해 만들 수 없어요.")
    # pycaw: EXE 안에는 pip 가 없어서 실행 중에 설치할 수 없으므로, 만들 때 미리 넣어 둡니다.
    has_pycaw = ensure_package("pycaw.pycaw", "pycaw")
    if not has_pycaw:
        print("[안내] pycaw 없이 만들어요. 음소거 상태 맞추기·마이크 음소거·볼륨 %는 동작하지 않아요.")
    icon = make_icon()

    if not build_app(icon, has_pycaw):
        return 1
    zip_path = build_zip(version)
    setup_path = "" if "--no-setup" in sys.argv else build_setup(version)
    archive_old_dist(version)
    update_readme(version, setup_path)


    print("\n" + "=" * 60)
    print(" 다 만들었어요! 친구에게는 아래 파일 중 하나를 보내 주세요.")
    if setup_path:
        print(f"  ★ 설치 파일 (추천): {setup_path}")
    print(f"  · 휴대용 압축 파일: {zip_path}")
    print("  처음 실행할 때 파란 'Windows의 PC 보호' 창이 뜨면 '추가 정보 → 실행'을 누르면 돼요.")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(build())
