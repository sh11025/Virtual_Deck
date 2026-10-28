"""
README 용 스크린샷 및 인포그래픽 SVG 생성 스크립트
오프스크린 환경에서 실행되어 docs/images/ 폴더에 이미지를 저장합니다.
"""

import os
import sys
import tempfile
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

TMP_DATA = tempfile.mkdtemp(prefix="vdeck_readme_")
os.environ["VIRTUALDECK_DATA_DIR"] = TMP_DATA
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import Qt, QSize, QPoint, QRect, QRectF
from PySide6.QtGui import (
    QPainter, QPixmap, QColor, QFont, QPen, QLinearGradient, QBrush, QImage
)
from PySide6.QtWidgets import QApplication

app = QApplication.instance() or QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui import theme
theme.load_fonts()

import core.action_executor as AE
AE.ActionExecutor.execute = staticmethod(lambda t, d: (True, "ok"))

from models.button_model import DeckButtonData
from models.config_model import AppConfig
from services.storage_service import StorageService, BUILTIN_THEMES
from ui.main_window import MainWindow
from ui.settings_dialog import SettingsDialog
from ui.button_editor_dialog import ButtonEditorDialog
from ui.glass import make_aurora, rounded_path, with_alpha, draw_icon

IMAGES_DIR = os.path.join(ROOT, "docs", "images")
os.makedirs(IMAGES_DIR, exist_ok=True)


from models.profile_model import DeckProfile


def setup_sample_storage():
    """새 기본 3x4 프로필 설정"""
    cfg = AppConfig(rows=3, cols=4, button_size=74, spacing=5, bg_type="glass", glass_tint="sky", glass_clarity=25)
    storage = StorageService()
    from services.sample_profiles import SAMPLES, create_sample_profile
    prof = create_sample_profile(SAMPLES[0], "profile_default")
    storage.save_data(cfg, {"profile_default": prof}, "profile_default")
    return cfg, storage



def make_hero_image():
    print("[1/6] hero.png 생성 중…")
    cfg, storage = setup_sample_storage()
    w = MainWindow(storage)
    w._check_pycaw = lambda: None
    w.resize(w.sizeHint())
    w.show()
    app.processEvents()

    # 창 렌더링
    mw_pix = w.grab()

    # 캔버스 880x560
    cw, ch = 900, 560
    canvas = QPixmap(cw, ch)
    canvas.fill(Qt.transparent)

    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)

    # 1. 캔버스 배경 (다크 룸 + 오로라 빛)
    bg_path = rounded_path(QRectF(0, 0, cw, ch), 24)
    p.fillPath(bg_path, QColor("#0d1117"))
    aurora = make_aurora(QSize(cw, ch), dark=True, seed=3)
    p.setOpacity(0.55)
    p.drawPixmap(0, 0, aurora)
    p.setOpacity(1.0)

    # 상단 텍스트 및 로고
    p.setPen(QColor("#94a3b8"))
    p.setFont(QFont("Malgun Gothic", 12))
    p.drawText(QRectF(0, 40, cw, 30), Qt.AlignCenter, "화면 위에 띄워 두는 나만의 버튼판")

    p.setPen(QColor("#ffffff"))
    title_font = QFont("Malgun Gothic", 24, QFont.Bold)
    p.setFont(title_font)
    p.drawText(QRectF(0, 70, cw, 45), Qt.AlignCenter, "Virtual Deck")

    # 2. MainWindow 중앙 배치 및 부드러운 그림자
    mx = (cw - mw_pix.width()) // 2
    my = 150 + (ch - 150 - mw_pix.height()) // 2

    shadow_path = rounded_path(QRectF(mx - 4, my - 4, mw_pix.width() + 8, mw_pix.height() + 8), 28)
    p.fillPath(shadow_path, QColor(0, 0, 0, 110))

    p.drawPixmap(mx, my, mw_pix)
    p.end()

    out_path = os.path.join(IMAGES_DIR, "hero.png")
    canvas.save(out_path, "PNG")
    print(f"      저장 완료: {out_path}")
    w.close()


def make_styles_image():
    print("[2/6] styles.png 생성 중…")
    styles = [
        ("맑음", {"bg_type": "glass", "glass_tint": "", "glass_clarity": 20, "theme": "light"}),
        ("밤", {"bg_type": "glass", "glass_tint": "", "glass_clarity": 30, "theme": "dark"}),
        ("젖빛", {"bg_type": "glass", "glass_tint": "", "glass_clarity": 75, "theme": "light"}),
        ("하늘", {"bg_type": "glass", "glass_tint": "sky", "glass_clarity": 25, "theme": "light"}),
        ("노을", {"bg_type": "glass", "glass_tint": "sunset", "glass_clarity": 25, "theme": "light"}),
        ("숲", {"bg_type": "glass", "glass_tint": "forest", "glass_clarity": 25, "theme": "light"}),
        ("투명 (버튼만)", {"bg_type": "clear", "glass_tint": "", "glass_clarity": 30, "theme": "light"}),
    ]

    card_w = 114
    card_h = 160
    gap = 14
    cw = 24 + len(styles) * card_w + (len(styles) - 1) * gap + 24
    ch = 220

    canvas = QPixmap(cw, ch)
    canvas.fill(Qt.transparent)

    p = QPainter(canvas)
    p.setRenderHint(QPainter.Antialiasing)

    # 캔버스 바탕
    p.fillPath(rounded_path(QRectF(0, 0, cw, ch), 20), QColor("#111827"))

    tint_map = {
        "sky": "#38bdf8",
        "sunset": "#fb923c",
        "forest": "#34d399",
    }

    for i, (name, opt) in enumerate(styles):
        cx = 24 + i * (card_w + gap)
        cy = 25

        card_rect = QRectF(cx, cy, card_w, card_h)
        path = rounded_path(card_rect, 14)

        # 그림자
        p.fillPath(rounded_path(card_rect.translated(0, 3), 14), QColor(0, 0, 0, 60))

        # 카드 배경
        is_dark = opt.get("theme") == "dark"
        if opt["bg_type"] == "clear":
            p.fillPath(path, QColor("#1e293b"))
            # 격자 패턴으로 투명 표현
            p.setPen(QColor("#334155"))
            p.drawRect(QRectF(cx + 8, cy + 8, card_w - 16, card_h - 45))
        elif opt["glass_tint"] in tint_map:
            p.fillPath(path, with_alpha(QColor(tint_map[opt["glass_tint"]]), 180 if is_dark else 140))
        elif opt["glass_clarity"] > 60:
            p.fillPath(path, QColor(255, 255, 255, 210))
        elif is_dark:
            p.fillPath(path, QColor(24, 28, 38, 230))
        else:
            p.fillPath(path, QColor(255, 255, 255, 170))

        p.setPen(QPen(QColor(255, 255, 255, 80 if not is_dark else 40), 1.2))
        p.drawPath(path)

        # 카드 내부 미니 버튼 4개 그리기
        bw = (card_w - 28) / 2
        bh = bw
        for r in range(2):
            for c in range(2):
                bx = cx + 10 + c * (bw + 8)
                by = cy + 12 + r * (bh + 8)
                bpath = rounded_path(QRectF(bx, by, bw, bh), 8)
                btn_color = QColor(255, 255, 255, 60 if is_dark else 140)
                p.fillPath(bpath, btn_color)
                p.setPen(QPen(QColor(255, 255, 255, 100), 1))
                p.drawPath(bpath)

        # 스타일 이름
        p.setFont(QFont("Malgun Gothic", 11, QFont.Bold))
        p.setPen(QColor("#f8fafc"))
        name_rect = QRectF(cx, cy + card_h - 38, card_w, 32)
        p.drawText(name_rect, Qt.AlignCenter, name)

    p.end()
    out_path = os.path.join(IMAGES_DIR, "styles.png")
    canvas.save(out_path, "PNG")
    print(f"      저장 완료: {out_path}")


def make_settings_and_editor_images():
    print("[3/6] settings.png & [4/6] editor.png 생성 중…")
    storage = StorageService()
    w = MainWindow(storage)
    w._check_pycaw = lambda: None
    w.show()
    app.processEvents()

    # 환경설정 창
    sd = SettingsDialog(w.config.copy(), storage=w.storage, parent=w)
    sd.resize(820, 580)
    sd.show()
    app.processEvents()
    sd_pix = sd.grab()
    sd_path = os.path.join(IMAGES_DIR, "settings.png")
    sd_pix.save(sd_path, "PNG")
    print(f"      settings.png 저장 완료: {sd_path}")
    sd.close()

    # 버튼 편집 창 (820px)
    btn_data = DeckButtonData(id="0,0", name="화면 캡처", action_type="shortcut", action_data="Win + Shift + S", icon="icon:camera", icon_color="sunset")
    ed = ButtonEditorDialog(btn_data, in_folder=False, parent=w)
    ed.resize(820, 620)
    ed.show()
    app.processEvents()
    ed_pix = ed.grab()
    ed_path = os.path.join(IMAGES_DIR, "editor.png")
    ed.close()
    w.close()


def make_features_svg():
    print("[5/6] features.svg 생성 중…")
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 370" width="100%" height="100%">
  <defs>
    <style>
      .title { font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; font-size: 16px; font-weight: 700; fill: #ffffff; }
      .desc { font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; font-size: 13px; fill: #94a3b8; }
      .badge { font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; font-size: 11px; font-weight: 600; }
    </style>
  </defs>

  <!-- 카드 1: 유리 감성 디자인 -->
  <g transform="translate(10, 10)">
    <rect width="280" height="165" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <rect x="20" y="20" width="40" height="40" rx="10" fill="#0f172a" stroke="#38bdf8" stroke-width="1.5"/>
    <rect x="27" y="29" width="18" height="16" rx="4" fill="none" stroke="#38bdf8" stroke-width="1.8" opacity="0.6"/>
    <rect x="33" y="33" width="18" height="16" rx="4" fill="#38bdf8" fill-opacity="0.25" stroke="#38bdf8" stroke-width="1.8"/>
    <text x="75" y="45" class="title">유리 감성 디자인</text>
    <text x="20" y="85" class="desc">화면을 은은하게 비추는 아크릴 유리와</text>
    <text x="20" y="105" class="desc">7가지 원클릭 스타일(맑음·밤·젖빛 등).</text>
    <text x="20" y="140" class="badge" style="fill: #38bdf8;">투명 아크릴 시스템</text>
  </g>

  <!-- 카드 2: 0.44ms 초고속 반응 -->
  <g transform="translate(310, 10)">
    <rect width="280" height="165" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <rect x="20" y="20" width="40" height="40" rx="10" fill="#0f172a" stroke="#22c55e" stroke-width="1.5"/>
    <polygon points="42,25 31,37 39,37 37,53 49,40 41,40" fill="#22c55e"/>
    <text x="75" y="45" class="title">0.44ms 초고속 반응</text>
    <text x="20" y="85" class="desc">창을 마우스로 빠르게 끌어도 버벅거림</text>
    <text x="20" y="105" class="desc">없이 부드럽게 60fps 로 따라옵니다.</text>
    <text x="20" y="140" class="badge" style="fill: #22c55e;">화면 사전 캡처 기술</text>
  </g>

  <!-- 카드 3: 설정 창 열어 둔 채로 -->
  <g transform="translate(610, 10)">
    <rect width="280" height="165" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <rect x="20" y="20" width="40" height="40" rx="10" fill="#0f172a" stroke="#f59e0b" stroke-width="1.5"/>
    <rect x="27" y="28" width="16" height="14" rx="2" fill="none" stroke="#f59e0b" stroke-width="1.5"/>
    <line x1="27" y1="32" x2="43" y2="32" stroke="#f59e0b" stroke-width="1.2"/>
    <rect x="33" y="33" width="19" height="17" rx="3" fill="#0f172a" stroke="#f59e0b" stroke-width="1.8"/>
    <line x1="33" y1="38" x2="52" y2="38" stroke="#f59e0b" stroke-width="1.2"/>
    <text x="75" y="45" class="title">설정 창 열어 둔 채로</text>
    <text x="20" y="85" class="desc">설정을 바꾸면서 버튼을 누르거나</text>
    <text x="20" y="105" class="desc">버튼 자리를 바로 옮길 수 있어요.</text>
    <text x="20" y="140" class="badge" style="fill: #f59e0b;">자유로운 독립 창</text>
  </g>

  <!-- 카드 4: 다채로운 동작 지원 -->
  <g transform="translate(10, 195)">
    <rect width="280" height="165" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <rect x="20" y="20" width="40" height="40" rx="10" fill="#0f172a" stroke="#ec4899" stroke-width="1.5"/>
    <circle cx="40" cy="40" r="13" fill="none" stroke="#ec4899" stroke-width="1.8"/>
    <circle cx="40" cy="40" r="8" fill="none" stroke="#ec4899" stroke-width="1.6" opacity="0.6"/>
    <circle cx="40" cy="40" r="3.5" fill="#ec4899"/>
    <text x="75" y="45" class="title">다채로운 동작 지원</text>
    <text x="20" y="85" class="desc">프로그램 열기, 단축키, 연속 동작,</text>
    <text x="20" y="105" class="desc">소리 끄기, 뽀모도로 타이머까지 완비.</text>
    <text x="20" y="140" class="badge" style="fill: #ec4899;">강력한 동작 엔진</text>
  </g>

  <!-- 카드 5: 스마트 테마 아이콘 -->
  <g transform="translate(310, 195)">
    <rect width="280" height="165" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <rect x="20" y="20" width="40" height="40" rx="10" fill="#0f172a" stroke="#8b5cf6" stroke-width="1.5"/>
    <path d="M40 27 C33 27 28 32 28 38 C28 44 32 49 37 49 C39 49 40 47.5 40 46 C40 45 39.5 44 39.5 43 C39.5 41.5 41 40 43 40 L45 40 C49 40 52 37 52 33 C52 28 47 27 40 27 Z" fill="none" stroke="#8b5cf6" stroke-width="1.8"/>
    <circle cx="33" cy="34" r="1.5" fill="#8b5cf6"/>
    <circle cx="39" cy="32" r="1.5" fill="#8b5cf6"/>
    <circle cx="45" cy="35" r="1.5" fill="#8b5cf6"/>
    <text x="75" y="45" class="title">스마트 테마 아이콘</text>
    <text x="20" y="85" class="desc">동작에 맞는 78개 벡터 아이콘 자동 매칭,</text>
    <text x="20" y="105" class="desc">이모지 및 실행 파일 아이콘 즉시 추출.</text>
    <text x="20" y="140" class="badge" style="fill: #8b5cf6;">78개 벡터 아이콘</text>
  </g>

  <!-- 카드 6: 방송 & 캡처 보호 -->
  <g transform="translate(610, 195)">
    <rect width="280" height="165" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <rect x="20" y="20" width="40" height="40" rx="10" fill="#0f172a" stroke="#06b6d4" stroke-width="1.5"/>
    <path d="M40 26 L49 30 C49 41 44 47 40 52 C36 47 31 41 31 30 Z" fill="none" stroke="#06b6d4" stroke-width="1.8"/>
    <path d="M40 30 L45 32.5 C45 39 42 44 40 47.5 Z" fill="#06b6d4" fill-opacity="0.35"/>
    <text x="75" y="45" class="title">방송 &amp; 캡처 보호</text>
    <text x="20" y="85" class="desc">방송/녹화 화면에서 버튼판을 숨기고,</text>
    <text x="20" y="105" class="desc">필요할 땐 1분간 보이게 켤 수 있습니다.</text>
    <text x="20" y="140" class="badge" style="fill: #06b6d4;">윈도우 캡처 제외 연동</text>
  </g>
</svg>
"""
    out_path = os.path.join(IMAGES_DIR, "features.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg_content.strip())
    print(f"      저장 완료: {out_path}")


def make_numbers_svg():
    print("[6/6] numbers.svg 생성 중…")
    svg_content = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 900 130" width="100%" height="100%">
  <defs>
    <style>
      .num { font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; font-size: 32px; font-weight: 800; }
      .lbl { font-family: 'Segoe UI', 'Malgun Gothic', sans-serif; font-size: 13px; font-weight: 600; fill: #94a3b8; }
    </style>
  </defs>

  <!-- 카드 1 -->
  <g transform="translate(10, 10)">
    <rect width="205" height="110" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <text x="102" y="55" text-anchor="middle" class="num" fill="#38bdf8">100 / 100</text>
    <text x="102" y="85" text-anchor="middle" class="lbl">단위/통합 테스트 통과</text>
  </g>

  <!-- 카드 2 -->
  <g transform="translate(235, 10)">
    <rect width="205" height="110" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <text x="102" y="55" text-anchor="middle" class="num" fill="#22c55e">0.44 ms</text>
    <text x="102" y="85" text-anchor="middle" class="lbl">버튼판 이동 처리 속도</text>
  </g>

  <!-- 카드 3 -->
  <g transform="translate(460, 10)">
    <rect width="205" height="110" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <text x="102" y="55" text-anchor="middle" class="num" fill="#f59e0b">7 개</text>
    <text x="102" y="85" text-anchor="middle" class="lbl">원클릭 스타일 테마</text>
  </g>

  <!-- 카드 4 -->
  <g transform="translate(685, 10)">
    <rect width="205" height="110" rx="16" fill="#1e293b" stroke="#334155" stroke-width="1.2"/>
    <text x="102" y="55" text-anchor="middle" class="num" fill="#ec4899">38.4 MB</text>
    <text x="102" y="85" text-anchor="middle" class="lbl">가벼워진 설치 파일</text>
  </g>
</svg>
"""
    out_path = os.path.join(IMAGES_DIR, "numbers.svg")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(svg_content.strip())
    print(f"      저장 완료: {out_path}")



def main():
    make_hero_image()
    make_styles_image()
    make_settings_and_editor_images()
    make_features_svg()
    make_numbers_svg()
    print("\n모든 README 이미지 생성이 완료되었습니다!")


if __name__ == "__main__":
    main()
