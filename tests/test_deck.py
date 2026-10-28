"""
Virtual Deck 동작 테스트
고친 뒤에 이 파일을 실행하면 주요 기능이 그대로 동작하는지 한 번에 확인할 수 있습니다.

실행:  python tests/test_deck.py      (또는 run_tests.bat 더블클릭)

- 실제 설정(data 폴더)은 건드리지 않고 임시 폴더를 씁니다.
- 실제로 키를 보내거나 소리를 바꾸지 않도록 실행 부분은 가짜로 바꿔서 테스트합니다.
- 창이 화면에 뜨지 않게 '화면 없는 모드'로 실행합니다.
"""

import json
import os
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
TMP = tempfile.mkdtemp(prefix="vdeck_test_")
os.environ["VIRTUALDECK_DATA_DIR"] = TMP
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QPoint, QEventLoop, QTimer, Qt, QEvent  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication(sys.argv)
app.setQuitOnLastWindowClosed(False)

from ui import theme, icons  # noqa: E402
theme.load_fonts()

import core.action_executor as AE  # noqa: E402
from core import paths  # noqa: E402
from core.shortcut_manager import ShortcutManager as SM  # noqa: E402
from models.button_model import DeckButtonData as B  # noqa: E402
from models.button_model import DeckButtonData  # noqa: E402
from models.config_model import AppConfig  # noqa: E402
from services.storage_service import StorageService  # noqa: E402

# ---- 실제 동작은 가짜로 (키 보내기, 전역 단축키 등록 없음)
executed = []
REAL_EXECUTE = AE.ActionExecutor.execute
AE.ActionExecutor.execute = staticmethod(lambda t, d: (executed.append((t, d)) or (True, "ok")))
import core.app_finder as AF  # noqa: E402
AF.list_start_apps = lambda force=False: [
    ("Claude", "Anthropic.Claude_xxx"),
    ("ChatGPT", "OpenAI.ChatGPT_xxx"),
    ("Gemini", "Google.Gemini_xxx"),
    ("Antigravity", "Google.Antigravity_xxx"),
]

from ui.main_window import MainWindow  # noqa: E402
MainWindow._check_pycaw = lambda self: None   # 테스트 중에는 설치 질문 창을 띄우지 않음

results = []


def check(cond, msg):
    results.append(bool(cond))
    print(("  OK  " if cond else "  실패 ") + msg)


def wait(ms):
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def section(title):
    print(f"\n[{title}]")


# ====================================================================
section("단축키 해석")
for text, n in [("Ctrl + Shift + S", 3), ("Alt + Left", 2), ("Win + Shift + S", 3), ("Ctrl + +", 2),
                ("F13", 1), ("VolumeUp", 1), ("Ctrl+C", 2)]:
    codes, err = SM.parse(text)
    check(len(codes) == n, f"{text} → 키 {len(codes)}개 {err}")
check(SM.parse("Ctrl + Foo")[0] == [], "모르는 키는 거절")

# ====================================================================
section("메인 덱 · 버튼 편집")
st = StorageService()
w = MainWindow(st)
w.show()
app.processEvents()
btns = w.current_buttons()
check(len(btns) >= 9, "기본 버튼 생성")

a, b = btns["btn_0_0"].name, btns["btn_0_1"].name
w._swap_buttons("btn_0_0", "btn_0_1")
btns = w.current_buttons()
check(btns["btn_0_0"].name == b and btns["btn_0_1"].name == a, "끌어서 위치 바꾸기")
w.undo()
check(w.current_buttons()["btn_0_0"].name == a, "되돌리기")

btns = w.current_buttons()
btns["btn_2_0"] = B("btn_2_0", "묶음", "icon:grid", "group", "", 2, 0)
w._handle_click("btn_2_0")
check(w.folder_id == "btn_2_0" and len(w.current_buttons()) >= 9, "버튼 묶음 열기")
w.current_buttons()["btn_0_0"] = B("btn_0_0", "안쪽", "icon:star", "url", "example.com", 0, 0)
w._leave_folder()
check(w.current_profile.buttons["btn_2_0"].children["btn_0_0"].name == "안쪽", "묶음 안 버튼 유지")
w.save()
cfg, profs, cur = st.load_data()
check(profs[cur].buttons["btn_2_0"].children["btn_0_0"].name == "안쪽", "저장 후 다시 읽기")

# 나가기(back) 버튼 테스트
btn_back_test = B("btn_back", "나가기", "icon:back", "back", "", 0, 1)
w.current_profile.buttons["btn_2_0"].children["btn_back"] = btn_back_test
w.folder_id = "btn_2_0"
w._handle_click("btn_back")
check(w.folder_id is None, "묶음 안에서 back 버튼 누르면 묶음에서 나감 (folder_id is None)")

# 묶음 밖에서 back 버튼 클릭
w.current_buttons()["btn_back_root"] = B("btn_back_root", "나가기", "icon:back", "back", "", 0, 1)
w._handle_click("btn_back_root")
check(w.folder_id is None, "묶음 밖에서 back 버튼 눌러도 오류 없이 folder_id is None")

# ActionExecutor, describe_action, to_dict/from_dict 검사
check(REAL_EXECUTE("back", "") == (True, ""), "ActionExecutor.execute('back', '') == (True, '')")
check(REAL_EXECUTE("schedule", "") == (True, ""), "ActionExecutor.execute('schedule', '') == (True, '')")
check(REAL_EXECUTE("url", "")[0] is False, "내용이 비면 url 은 실패")
check("나가기" in AE.describe_action("back", ""), "describe_action('back', '') 에 '나가기' 포함됨")
b_rt = DeckButtonData.from_dict(btn_back_test.to_dict())
check(b_rt.action_type == "back", "to_dict -> from_dict 왕복 후에도 action_type 가 'back'")
check(icons.is_theme_icon(icons.default_icon_for("back", "")), "back 기본 아이콘이 테마 아이콘으로 등록됨")
check(DeckButtonData.from_dict({"id": "x", "action_type": "back", "icon": "back"}).icon == "icon:arrow_left", "back 버튼 icon 보정 (back -> icon:arrow_left)")
check("QTimeEdit" in theme.get_qss(), "theme.get_qss 에 QTimeEdit 포함됨")

check(st.count_outside(w.profiles, 2, 2) > 0, "칸 줄일 때 지워질 버튼 세기")
p2 = {k: v.copy() for k, v in w.profiles.items()}
st.prune_outside(p2, 2, 2)
check(all(x.row < 2 and x.col < 2 for p in p2.values() for x in p.buttons.values()), "칸 줄이기 정리")

# ====================================================================
section("켜기/끄기 · 길게 누르기 · 큰 버튼 · 정보 버튼")
btns = w.current_buttons()
tb = B("btn_0_0", "t", "icon:volume_mute", "url", "a.com", 0, 0, toggle=True)
btns["btn_0_0"] = tb
w._rebuild_grid()
w._handle_click("btn_0_0")
check(tb.toggle_on, "켜기/끄기: 누르면 켜짐")
w._handle_click("btn_0_0")
check(not tb.toggle_on, "켜기/끄기: 다시 누르면 꺼짐")
wid = w.button_widgets["btn_0_0"]
check(wid._state_tint(False) == "clear" and wid._state_tint(True) == "mint", "꺼짐=투명, 켜짐=민트")

executed.clear()
btns["btn_0_1"] = B("btn_0_1", "h", "icon:play", "url", "a.com", 0, 1,
                    hold_action_type="shortcut", hold_action_data="Ctrl + Z")
w._rebuild_grid()
w._handle_long_press("btn_0_1")
check(executed == [("shortcut", "Ctrl + Z")], "길게 누르면 다른 동작 실행")
hw = w.button_widgets["btn_0_1"]
hw._on_hold()
check(hw._hold_fired, "길게 누르기 확정 후에는 클릭으로 처리 안 함")

btns["btn_1_0"] = B("btn_1_0", "큰 버튼", "icon:star", "url", "a.com", 1, 0, span_cols=2)
btns["btn_1_1"] = B("btn_1_1", "가려짐", "icon:heart", "url", "b.com", 1, 1)
w._rebuild_grid()
big = w.button_widgets["btn_1_0"]
check(big.width() > big.height() * 1.5, "가로 2칸 버튼 크기")
check("btn_1_1" not in w.button_widgets and btns["btn_1_1"].name == "가려짐", "가려진 칸은 숨기고 지우지 않음")
_last = B.make_id(0, w.config.cols - 1)
btns[_last] = B(_last, "끝", "icon:star", "url", "a.com", 0, w.config.cols - 1, span_cols=2)
w._rebuild_grid()
check(w.button_widgets[_last].span == (1, 1), "그리드 밖으로 나가는 큰 버튼은 줄임")
btns["btn_1_0"].span_cols = 1
w._rebuild_grid()
check("btn_1_1" in w.button_widgets, "1칸으로 바꾸면 숨었던 버튼 다시 보임")

btns["btn_2_2"] = B("btn_2_2", "", "", "info", "clock", 2, 2)
w._rebuild_grid()
info = w.button_widgets["btn_2_2"].info
check(info is not None and ":" in info[0], f"정보 버튼(시계) 값 표시: {info}")

# 작업 N: 정보 버튼 시계 옵션 검사
from core.system_info import clock_kind, clock_options, parse_kinds, read_info  # noqa: E402
from ui.button_editor_dialog import ActionEditor  # noqa: E402
check(
    clock_kind(False, False) == "clock"
    and clock_kind(False, True) == "clock_sec"
    and clock_kind(True, False) == "clock12"
    and clock_kind(True, True) == "clock12_sec",
    "clock_kind 옵션별 변환",
)
check(
    clock_options("clock12_sec") == (True, True) and clock_options("battery") is None,
    "clock_options 시계 종류 판별 및 옵션 반환",
)
check(
    parse_kinds("clock,clock_sec,battery", 4) == ["clock", "battery"],
    "parse_kinds 시계 중복 제거",
)
r_info = read_info("clock12_sec")
check(
    r_info[0].count(":") == 2 and ("오전" in r_info[0] or "오후" in r_info[0]),
    f"read_info('clock12_sec') 초와 오전/오후 표시: {r_info[0]}",
)
ed_info = ActionEditor(["info"])
page_info = ed_info.pages["info"]
check("시계(초 포함)" not in [cb.text() for cb in page_info.checkboxes.values()], "목록 체크박스에 '시계(초 포함)' 없음")
page_info.checkboxes["clock"].setChecked(True)
page_info.cb_ampm.setChecked(True)
page_info.cb_sec.setChecked(True)
check(ed_info.value() == ("info", "clock12_sec"), "시계+오전/오후+초 체크 시 value() == ('info', 'clock12_sec')")

# 작업 O: 볼륨 조절 계획 및 연속 동작 볼륨 맞추기 검사
from core.audio_state import volume_key_plan  # noqa: E402
from core.macro_manager import STEP_TYPES, parse_steps  # noqa: E402

check(
    volume_key_plan(0) == (50, 0)
    and volume_key_plan(50) == (50, 25)
    and volume_key_plan(100) == (50, 50)
    and volume_key_plan(150) == (50, 50),
    "volume_key_plan 비율 계산",
)
check("volume_set" in STEP_TYPES, "'volume_set' 가 STEP_TYPES 에 있음")
check(
    parse_steps('[{"type":"volume_set","value":"30"}]') == [{"type": "volume_set", "value": "30"}],
    "parse_steps 가 volume_set 단계를 그대로 읽음",
)
check("2%" in SM.media_label("VolumeUp"), "media_label('VolumeUp') 에 '2%' 포함됨")

# ====================================================================
section("프로필 자동 전환 (프로그램 + 창 제목)")
from models.profile_model import DeckProfile  # noqa: E402
w.profiles["p_yt"] = DeckProfile(id="p_yt", name="유튜브", target_process="chrome.exe", target_title="YouTube, 유튜브")
b_pid = "profile_browser" if "profile_browser" in w.profiles else "profile_chrome"
w.profiles[b_pid].target_process = "chrome.exe"
check(w.match_profile("chrome.exe", "고양이 영상 - YouTube") == "p_yt", "크롬 + 제목에 YouTube → 유튜브 프로필")
check(w.match_profile("chrome.exe", "네이버") == b_pid, "크롬 + 다른 제목 → 브라우저 프로필")
check(w.match_profile("notepad.exe", "메모") == "profile_default", "연결 없는 프로그램 → 기본")
del w.profiles["p_yt"]

# ====================================================================
section("아이콘 테마 · 변환")
from ui import icons as IC  # noqa: E402
check(len(IC.REGISTRY) >= 115, f"테마 아이콘 {len(IC.REGISTRY)}개")
check(all(c in IC.CATEGORIES for c in ("AI · 개발", "시스템", "문서 · 도구", "생활 · 여가")), "카테고리에 새 묶음 4개 포함")

NEW_ICON_NAMES = [
    "robot", "sparkle", "chip", "git", "bug", "database", "server", "braces", "wifi",
    "battery", "bluetooth", "laptop", "headphones", "mouse", "shutdown", "sliders",
    "info", "warning", "question", "key", "eye", "book", "checklist", "printer",
    "wrench", "calculator", "archive", "layers", "filter", "flag", "cart", "gift",
    "map_pin", "plane", "car", "dumbbell", "school", "leaf", "umbrella", "wallet",
    "tv", "crown", "droplet",
]
check(all(n in IC.REGISTRY for n in NEW_ICON_NAMES), "새 테마 아이콘 43개가 REGISTRY에 모두 있음")

from PySide6.QtGui import QImage, QPainter, QColor  # noqa: E402
from PySide6.QtCore import QRectF  # noqa: E402

all_painted = True
for n in NEW_ICON_NAMES:
    for style in ("line", "duotone"):
        img = QImage(64, 64, QImage.Format_ARGB32_Premultiplied)
        p = QPainter(img)
        ok = icons.paint_icon(p, f"icon:{n}", QRectF(0, 0, 64, 64), QColor("white"), style)
        p.end()
        if not ok:
            all_painted = False
            break
    if not all_painted:
        break
check(all_painted, "새 아이콘 43개 모두 line 및 duotone 스타일 그리기 성공 (True 반환)")

from ui.profile_manager_dialog import ProfileManagerDialog  # noqa: E402
from ui.widgets import GlassButton  # noqa: E402
pm_dlg = ProfileManagerDialog(dict(w.profiles), w.current_profile_id, w.storage, parent=w)
pm_btn_texts = [btn.text() for btn in pm_dlg.findChildren(GlassButton)]
check("추가" in pm_btn_texts and "템플릿" in pm_btn_texts, "프로필 관리 창 버튼 글자에 '추가' 와 '템플릿' 이 있음")
pm_dlg.close()
for p_ in w.profiles.values():
    p_.buttons["btn_0_0"].icon = "🔥"
w._convert_emoji_icons()
check(all(p_.buttons["btn_0_0"].icon == "icon:fire" for p_ in w.profiles.values()), "이모지 → 테마 아이콘 (모든 프로필)")
w.undo()
check(all(p_.buttons["btn_0_0"].icon == "🔥" for p_ in w.profiles.values()), "전체 되돌리기")

from ui.button_editor_dialog import ButtonEditorDialog  # noqa: E402
dlg = ButtonEditorDialog(B("btn_0_0"), parent=w)
dlg.action.set_value("url", "www.youtube.com/watch")
rd = dlg.result_data()
check(rd.name == "Youtube" and rd.icon == "icon:globe", f"자동 이름/아이콘: {rd.name} {rd.icon}")
dlg._set_icon("icon:heart")
dlg.action.set_value("folder", "C:/x")
check(dlg.result_data().icon == "icon:heart", "직접 고른 아이콘은 유지")
dlg.action.set_value("media", "MicMute")
dlg._auto_icon()
check(dlg.result_data().icon == "icon:mic_off", "마이크 음소거 자동 아이콘")
dlg.span_tabs.setCurrentIndex(1, animate=False)
check((dlg.result_data().span_cols, dlg.result_data().span_rows) == (2, 1), "편집창: 가로 2칸 저장")

# ====================================================================
section("설정 · 테마 · 백업")
old = AppConfig.from_dict({"button_size": 65, "spacing": 6, "glass_blur": 22})
check(old.spacing == 4 and 0 <= old.glass_clarity <= 100, "예전 설정 간격 자동 변환")
check(AppConfig.from_dict(old.to_dict()).spacing == 4, "두 번 변환하지 않음")

from services.storage_service import BUILTIN_THEMES  # noqa: E402
c = w.config.copy()
c.apply_theme_dict(BUILTIN_THEMES["밤 유리"])
w.apply_config(c)
app.processEvents()
check(theme.T().dark and w.config.bg_type == "glass", "덱 테마 적용 (밤 유리)")
c = w.config.copy()
c.apply_theme_dict(BUILTIN_THEMES["투명 (버튼만)"])
w.apply_config(c)
check(w.config.bg_type == "clear", "투명 (버튼만) 전환 (오류 없음)")
w.panel.rebuild_background()
_bg = w.panel.backdrop_pixmap()
check(not w.grabber.enabled and _bg is not None and _bg.toImage().pixelColor(5, 5).alpha() == 0,
      "투명 (버튼만): 화면 캡처 안 함 + 판 배경 투명")
check(not w.act_capture.isVisible(), "투명 (버튼만): '캡처할 때 보이게' 숨김")
c = w.config.copy()
c.apply_theme_dict(BUILTIN_THEMES["맑은 유리"])
w.apply_config(c)

ok, _ = st.export_theme("t", w.config.theme_dict(), os.path.join(TMP, "t.vdtheme.json"))
name, th = st.import_theme(os.path.join(TMP, "t.vdtheme.json"))
check(ok and name == "t" and th["bg_type"] == "glass", "테마 내보내기/가져오기")

w.save()
backups = st.list_backups()
check(len(backups) >= 1, f"자동 백업 생성 ({len(backups)}개)")
check(st.load_file(backups[0][0]) is not None, "백업 파일 읽기")

with open(st.file_path, "w") as f:
    f.write("{broken")
check(len(st.load_data()[1]) >= 1, "설정 파일이 깨지면 .bak 사용")

# ====================================================================
section("매크로")
from core.macro_manager import MacroRunner  # noqa: E402
r = MacroRunner.instance()
fin = []
r.finished.connect(lambda k, ok, m: fin.append((k, ok, m)))
ok, _ = r.run("k1", json.dumps([{"type": "delay", "value": "3000"}]))
check(ok and r.is_running("k1"), "매크로 시작")
r.stop("k1")
t0 = time.time()
while not fin and time.time() - t0 < 2:
    app.processEvents()
    time.sleep(0.01)
check(fin and not fin[0][1], f"실행 중 다시 누르면 멈춤 {fin}")

from ui.macro_editor_dialog import MacroRecorder  # noqa: E402
rec = MacroRecorder()
rec.record_delays = False
rec.start()
for ch in "hi":
    rec.keyPressEvent(QKeyEvent(QEvent.KeyPress, ord(ch.upper()), Qt.NoModifier, ch))
rec.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_S, Qt.ControlModifier, "\x13"))
rec.keyPressEvent(QKeyEvent(QEvent.KeyPress, Qt.Key_Return, Qt.NoModifier, "\r"))
steps = rec.stop()
check(steps == [{"type": "text", "value": "hi"}, {"type": "shortcut", "value": "Ctrl + S"},
                {"type": "shortcut", "value": "Enter"}], f"매크로 녹화: {steps}")

# wait_until 및 시간/단위 검사
from datetime import datetime  # noqa: E402
from core.macro_manager import seconds_until, ms_to_unit, unit_to_ms, parse_steps  # noqa: E402

check(seconds_until("09:30", datetime(2026, 1, 1, 9, 0)) == 1800, "seconds_until 같은 날 30분 차이 (1800초)")
check(seconds_until("09:30", datetime(2026, 1, 1, 10, 0)) == 23.5 * 3600, "seconds_until 이미 지난 시각은 내일 (23.5시간)")
check(seconds_until("abc") is None and seconds_until("25:61") is None, "seconds_until 잘못된 형식은 None")
check(ms_to_unit(600000) == (10, "분") and unit_to_ms(10, "분") == 600000, "단위 환산 600000 ↔ (10, '분') 왕복 일치")
check(ms_to_unit(1500) == (1500, "밀리초") and unit_to_ms(1500, "밀리초") == 1500, "단위 환산 1500 ↔ (1500, '밀리초') 왕복 일치")
parsed_wait = parse_steps(json.dumps([{"type": "wait_until", "value": "09:30"}]))
check(len(parsed_wait) == 1 and parsed_wait[0] == {"type": "wait_until", "value": "09:30"}, "parse_steps 가 wait_until 단계를 그대로 읽음")

# ====================================================================
section("타이머 · 스톱워치")
from core.timer_manager import TimerManager, dump_timer, parse_timer, format_seconds  # noqa: E402
check(format_seconds(125) == "02:05" and format_seconds(3725) == "1:02:05", "시간 표시 형식")
tm = TimerManager()
cd = dump_timer({"mode": "countdown", "seconds": 1, "sound": False})
done = []
tm.finished.connect(done.append)
check(tm.view("t1", cd)[0] == "00:01" and tm.view("t1", cd)[3] == "idle", "처음에는 설정한 시간 표시")
check(tm.press("t1") == "running", "누르면 시작")
check(tm.press("t1") == "paused", "다시 누르면 일시정지")
paused_view = tm.view("t1", cd)
time.sleep(0.3)
check(tm.view("t1", cd)[0] == paused_view[0], "일시정지 중에는 시간이 멈춤")
tm.press("t1")
time.sleep(1.1)
tm.tick(lambda k: cd)
check(done == ["t1"] and tm.view("t1", cd)[0] == "끝!", "시간이 다 되면 끝 알림")
check(tm.press("t1") == "idle", "끝난 뒤 누르면 처음으로")
sw = dump_timer({"mode": "stopwatch"})
tm.press("s1")
time.sleep(1.05)
check(tm.view("s1", sw)[0] == "00:01", "스톱워치는 올라감")
tm.reset("s1")
check(tm.view("s1", sw)[3] == "idle", "초기화")

btns = w.current_buttons()
btns["btn_2_1"] = B("btn_2_1", "라면", "icon:timer", "timer", dump_timer({"seconds": 180, "sound": False}), 2, 1)
w._rebuild_grid()
w._handle_click("btn_2_1")
w._on_live_tick()
view = w.button_widgets["btn_2_1"].timer_view
check(view and view[3] == "running" and view[0] in ("03:00", "02:59"), f"덱 타이머 버튼 시작: {view}")
check(w.live_timer.interval() == 250, "타이머가 돌 때는 화면을 자주 새로 그림")
w._handle_long_press("btn_2_1")
check(w.button_widgets["btn_2_1"].timer_view[3] == "idle", "길게 누르면 타이머 처음으로")
dlg = ButtonEditorDialog(btns["btn_2_1"].clone(), parent=w)
page = dlg.action.pages["timer"]
check(page.minutes.value() == 3 and page.seconds.value() == 0, "편집창에 타이머 시간 불러오기")
dlg._set_timer_seconds = dlg.action._set_timer_seconds
dlg.action._set_timer_seconds(page, 1500)
cfg_t = parse_timer(dlg.result_data().action_data)
check(cfg_t["seconds"] == 1500 and cfg_t["mode"] == "countdown", "편집창에서 25분으로 바꾸기")

section("추가 부품(pycaw)")
from core import dependencies as dep  # noqa: E402
check(isinstance(dep.has_pycaw(), bool), f"pycaw 확인 (있음: {dep.has_pycaw()}, 설치 가능: {dep.can_install()})")

# ====================================================================
section("설치판 / 휴대용 저장 위치")
fake_exe_dir = os.path.join(TMP, "fake_install")
os.makedirs(fake_exe_dir, exist_ok=True)
saved = (getattr(sys, "frozen", None), sys.executable, os.environ.pop("VIRTUALDECK_DATA_DIR"), os.environ.get("APPDATA"))
try:
    sys.frozen = True
    sys.executable = os.path.join(fake_exe_dir, "VirtualDeck.exe")
    os.environ["APPDATA"] = os.path.join(TMP, "fake_appdata")
    check(not paths.is_installed() and paths.data_dir() == os.path.join(fake_exe_dir, "data"),
          "휴대용: 프로그램 옆 data 폴더에 저장")
    open(os.path.join(fake_exe_dir, "installed.txt"), "w").close()
    check(paths.is_installed() and paths.data_dir() == os.path.join(TMP, "fake_appdata", "VirtualDeck"),
          "설치판: 사용자 폴더(APPDATA)에 저장")
    check(paths.cache_dir().startswith(paths.data_dir()), "임시 파일도 데이터 폴더 안에 (삭제 시 함께 지워짐)")
finally:
    if saved[0] is None:
        del sys.frozen
    sys.executable = saved[1]
    os.environ["VIRTUALDECK_DATA_DIR"] = saved[2]
    if saved[3] is None:
        os.environ.pop("APPDATA", None)
    else:
        os.environ["APPDATA"] = saved[3]

# ====================================================================
# ====================================================================
section("기타")
check(paths.resolve_icon(r"C:\옛날폴더\Virtual Deck\data\icons\없는파일.png") is None, "없는 아이콘은 None")
avail = app.primaryScreen().availableGeometry()
# B-4: 위쪽 끝 스냅 검사 (header_bar 윗변이 화면 위쪽 + 6)
snap_top = w._snapped(QPoint(300, avail.top() - w.header_bar.y() + 10))
header_top = snap_top.y() + w.header_bar.y()
check(header_top == avail.top() + 6, f"위쪽 끝 스냅 시 header_bar 윗변이 화면 위쪽 + 6 ({header_top} == {avail.top() + 6})")

# B-4: 메뉴 숨김/표시 시 창 위치 유지 검사
initial_pos = w.pos()
w._hide_header_fade()
w._on_header_anim_finished()
pos_hidden = w.pos()
w.enterEvent(None)
pos_shown = w.pos()
check(initial_pos == pos_hidden == pos_shown, f"메뉴를 숨겼다 보였다 해도 self.pos() 그대로 ({initial_pos})")

# ====================================================================
section("위쪽 메뉴 및 여백")
w.config.always_show_header = False
w._update_header()
check(not w.header_bar.isVisible() or w.header_effect.opacity() == 0.0, "처음엔 위쪽 메뉴 숨김")

w.enterEvent(None)
wait(200)
app.processEvents()
check(w.header_bar.isVisible() and w.header_effect.opacity() > 0.0, "enterEvent 뒤에 메뉴 보임")

w.config.always_show_header = True
w.apply_config(w.config)
app.processEvents()
check(w.header_bar.isVisible() and w.header_effect.opacity() == 1.0, "always_show_header=True 면 항상 보임")

w.config.button_size = 64
w.config.spacing = 4
w.config.rows, w.config.cols = 3, 3
w._adjust_size()
pad = max(6, round(64 * 0.09))
expected_panel_w = 3 * 64 + 2 * 4 + 2 * pad
check(w.panel.width() == expected_panel_w, f"SS 3x3 버튼판 너비 ({w.panel.width()} == {expected_panel_w})")

# B-4: SS 3x3 에서 왼쪽 끝 스냅 시 header_bar 왼쪽 변이 화면 안
combo = w.panel.geometry().united(w.header_bar.geometry())
snap_left = w._snapped(QPoint(avail.left() - combo.left() + 10, 300))
check(snap_left.x() + combo.left() == avail.left() + 6, f"SS 3x3 왼쪽 끝 스냅 시 합친 사각형 스냅 ({snap_left.x() + combo.left()})")
check(snap_left.x() + w.header_bar.x() >= avail.left() + 6, f"SS 3x3 왼쪽 끝 스냅 시 header_bar 왼쪽 변이 화면 안 ({snap_left.x() + w.header_bar.x()})")

# ====================================================================
section("트레이 숨기기 및 안 쓸 때 흐려지기 연동")
from PySide6.QtCore import QPropertyAnimation  # noqa: E402
orig_auto_fade = w.config.auto_fade
try:
    w.config.auto_fade = True
    w._fade_timer.start(50)
    w.hide_to_tray()
    check(w._fade_timer.isActive() is False, "hide_to_tray() 후 _fade_timer 가 멈춤")

    w.show_deck()
    check(abs(w.windowOpacity() - w.config.opacity) < 0.02, "show_deck() 후 창 투명도가 config.opacity 로 복원됨")

    w._fade_anim.setEndValue(0.1)
    w._fade_anim.start()
    w.hide_to_tray()
    check(w._fade_anim.state() != QPropertyAnimation.State.Running, "hide_to_tray() 후 _fade_anim 이 Running 이 아님")
finally:
    w.config.auto_fade = orig_auto_fade
    w.show_deck()

# ====================================================================
section("모달 없는 대화상자 (환경설정·버튼 설정)")
from ui.widgets import GlassDialog
gd = GlassDialog("테스트 모달리스", modeless=True)
check(not gd.isModal(), "GlassDialog(modeless=True) 는 모달이 아님")
gd.close()

# 환경설정 창 열기
w._open_settings()
check(w._settings_dlg is not None and w._settings_dlg.isVisible(), "환경설정 창 열림")
check(not w._settings_dlg.isModal(), "환경설정 창은 모달이 아님")
old_sd = w._settings_dlg
w._open_settings()
check(w._settings_dlg is old_sd, "다시 열어도 창은 하나만 유지")
w._settings_dlg.reject()
check(w._settings_dlg is None, "취소 시 설정 창 정리됨")

# 버튼 설정 창 열기 및 다른 버튼 전환
w._edit_button("btn_0_0")
check(w._editor_dlg is not None and w._editor_dlg.isVisible(), "버튼 설정 창 열림")
check(not w._editor_dlg.isModal(), "버튼 설정 창은 모달이 아님")
check(w._editor_dlg.data.id == "btn_0_0", "편집 중인 버튼 ID 확인")

# 내용 변경 없이 다른 버튼 편집 시 바로 전환
w._edit_button("btn_0_1")
check(w._editor_dlg.data.id == "btn_0_1", "다른 버튼으로 내용 전환됨")

# 버튼 위치 바꾸기 시 편집 대상 ID 동기화
w._swap_buttons("btn_0_1", "btn_0_2")
check(w._editor_dlg.data.id == "btn_0_2", "버튼 교체 시 편집 창 대상 ID 동기화됨")

# 5단계 테스트: 켜기/끄기 스위치와 "켜진 상태에서 할 일" 연동
w._editor_dlg.toggle.setChecked(False)
app.processEvents()
check(not w._editor_dlg.off_box.isVisible(), "스위치 끄면 '켜진 상태에서 할 일' 숨겨짐")
w._editor_dlg.toggle.setChecked(True)
app.processEvents()
check(w._editor_dlg.off_box.isVisible(), "스위치 켜면 '켜진 상태에서 할 일' 보임")

w._editor_dlg.reject()
check(w._editor_dlg is None, "취소 시 편집 창 정리됨")

# ====================================================================
section("환경설정 개편 및 7개 스타일")
from services.storage_service import BUILTIN_THEMES, get_builtin_theme
expected_styles = ["맑음", "밤", "젖빛", "하늘", "노을", "숲", "투명 (버튼만)"]
check(all(s in BUILTIN_THEMES for s in expected_styles), f"스타일 7개 이름이 BUILTIN_THEMES 에 있음 ({list(BUILTIN_THEMES.keys())})")

legacy_sea = get_builtin_theme("깊은 바다")
check(legacy_sea is not None, "예전 이름 '깊은 바다' 로 불러와도 오류 없음")

sky_style = BUILTIN_THEMES.get("하늘", {})
check(bool(sky_style.get("glass_tint")), "하늘 스타일 적용 시 glass_tint 가 비어 있지 않음")

# 환경설정 창 열기 및 탭 4개 확인
w._open_settings()
sd = w._settings_dlg
check(sd is not None and len(sd.tabs.labels) == 4, f"환경설정 탭이 4개 ({sd.tabs.labels if sd else []})")

# A-3. 스타일 카드 선택 및 glass_clarity 연동 테스트
sd._apply_style("맑음", BUILTIN_THEMES["맑음"])
selected_cards = [name for name, card in sd.style_cards.items() if card.isChecked()]
check(selected_cards == ["맑음"], f"맑음 적용 시 '맑음' 하나만 선택됨 ({selected_cards})")

sd._apply_style("젖빛", BUILTIN_THEMES["젖빛"])
selected_cards = [name for name, card in sd.style_cards.items() if card.isChecked()]
check(selected_cards == ["젖빛"], f"젖빛 적용 시 '젖빛' 하나만 선택됨 ({selected_cards})")

blur_before = sd.config.glass_blur
frost_before = sd.config.glass_frost
reloaded = AppConfig.from_dict(sd.config.to_dict())
check(reloaded.glass_blur == blur_before and reloaded.glass_frost == frost_before,
      f"젖빛 적용 후 to_dict->from_dict 동기화 유지 (blur={reloaded.glass_blur}, frost={reloaded.glass_frost})")

sd._on_clarity_changed(50)
selected_cards = [name for name, card in sd.style_cards.items() if card.isChecked()]
check(len(selected_cards) == 0, f"슬라이더 50일 때 선택된 카드 없음 ({selected_cards})")

sd.reject()

# ====================================================================
section("C: 휠 오작동 방지 (no_wheel)")
from ui.widgets import no_wheel
from PySide6.QtWidgets import QComboBox
from PySide6.QtGui import QWheelEvent
test_cb = no_wheel(QComboBox())
test_cb.addItems(["첫번째", "두번째", "세번째"])
test_cb.setCurrentIndex(0)
test_cb.clearFocus()
# 휠을 아래로 굴리는 이벤트 생성
we = QWheelEvent(QPointF(10, 10), QPointF(10, 10), QPoint(0, 0), QPoint(0, -120), Qt.NoButton, Qt.NoModifier, Qt.NoScrollPhase, False)
app.sendEvent(test_cb, we)
check(test_cb.currentIndex() == 0, "포커스 없는 드롭다운은 휠로 안 바뀜")

# ====================================================================
section("F: 켜기/끄기 실제 프로그램·폴더 상태 연동")
from core import running_state

w.config.sync_toggle_state = True
w.show()
p_id = DeckButtonData.make_id(0, 0)
p_btn = DeckButtonData(id=p_id, row=0, col=0, name="테스트앱", action_type="program", action_data="notepad.exe", toggle=True, toggle_on=False)
w.current_buttons()[p_id] = p_btn
w._rebuild_grid()

# 1. 실제 상태 True -> 다음 tick에 toggle_on True
running_state.is_program_running = lambda cmd: True
w._live_tick_count = 1
w._on_live_tick()
check(p_btn.toggle_on is True, f"실제 상태 True 시 toggle_on이 True로 동기화됨 ({p_btn.toggle_on})")

# 2. 실제 상태 False -> 다음 tick에 toggle_on False
running_state.is_program_running = lambda cmd: False
w._live_tick_count = 1
w._on_live_tick()
check(p_btn.toggle_on is False, f"실제 상태 False 시 toggle_on이 False로 동기화됨 ({p_btn.toggle_on})")

# 3. 실제 상태 None -> 그대로 유지
p_btn.toggle_on = True
running_state.is_program_running = lambda cmd: None
w._live_tick_count = 1
w._on_live_tick()
check(p_btn.toggle_on is True, f"실제 상태 None 시 toggle_on 상태 유지 ({p_btn.toggle_on})")

# 4. 켜진 상태에서 누름 + off 동작 비어 있음 -> close 호출
executed.clear()
p_btn.toggle_on = True
p_btn.off_action_type = "none"
p_btn.off_action_data = ""
w._handle_click(p_id)
check(("close", "notepad.exe") in executed, f"켜진 상태에서 누르면 close 호출됨 ({executed})")
check(p_btn.toggle_on is False, f"close 호출 후 toggle_on False로 변경됨 ({p_btn.toggle_on})")

# 5. 단축키 버튼은 누를 때마다 뒤집힘
sc_id = DeckButtonData.make_id(0, 1)
sc_btn = DeckButtonData(id=sc_id, row=0, col=1, name="단축키", action_type="shortcut", action_data="Ctrl + S", toggle=True, toggle_on=False)
w.current_buttons()[sc_id] = sc_btn
w._rebuild_grid()
w._handle_click(sc_id)
check(sc_btn.toggle_on is True, f"단축키 버튼 1회 클릭 시 True ({sc_btn.toggle_on})")
w._handle_click(sc_id)
check(sc_btn.toggle_on is False, f"단축키 버튼 2회 클릭 시 False ({sc_btn.toggle_on})")


# ====================================================================
section("일상 용어 검사 (덱 → 버튼판 등)")
from core.action_executor import ACTION_LABELS
check("버튼판" in w.act_toggle.text() and "덱" not in w.act_toggle.text(), f"트레이 메뉴 토글 문구 검사: {w.act_toggle.text()}")
check(ACTION_LABELS["none"] == "아무것도 안 함", f"ACTION_LABELS none 검사: {ACTION_LABELS['none']}")
check(ACTION_LABELS["macro"] == "연속 동작", f"ACTION_LABELS macro 검사: {ACTION_LABELS['macro']}")
check(ACTION_LABELS["group"] == "버튼 묶음", f"ACTION_LABELS group 검사: {ACTION_LABELS['group']}")
check("정보 보여 주기" in ACTION_LABELS["info"], f"ACTION_LABELS info 검사: {ACTION_LABELS['info']}")

# ====================================================================
section("6차 종합 검증")
# 1. system -> clear 자동 변환
sys_cfg = AppConfig.from_dict({"bg_type": "system"})
check(sys_cfg.bg_type == "clear", f"system 모드가 clear 로 변환됨 ({sys_cfg.bg_type})")

# 2. 스타일 바꾸기 시간 < 0.2초
import time
t0 = time.perf_counter()
w.apply_config(w.config)
app.processEvents()
dt = time.perf_counter() - t0
check(dt < 0.2, f"스타일 바꾸기 시간 0.2초 이내 ({dt*1000:.1f}ms)")

# 3. 화면 캡처 그림이 있을 때 색 유리(하늘/노을/숲) 오류 없이 그려지는지 확인
from ui.backdrop import compose_background
from PySide6.QtCore import QSize
from PySide6.QtGui import QPixmap
g = QPixmap(400, 400)
g.fill()
for tint_name in ("sky", "sunset", "forest"):
    tint_cfg = AppConfig.from_dict({"bg_type": "glass", "glass_tint": tint_name})
    res_pm = compose_background(tint_cfg, QSize(200, 200), 1.0, g, QPointF(0, 0))
    check(isinstance(res_pm, QPixmap) and not res_pm.isNull(), f"색 유리({tint_name}) 화면 캡처 시 배경 합성 성공")

# ====================================================================
section("L5: 버튼 설정 창 및 환경설정 창 잘림/넘침 검사")
from PySide6.QtWidgets import QWidget, QScrollArea
from ui.button_editor_dialog import ButtonEditorDialog
from ui.settings_dialog import SettingsDialog

# 1. 버튼 설정 창 가로 760, 820, 900
test_b_data = DeckButtonData(id="btn_0_0", row=0, col=0, name="테스트버튼")
dlg = ButtonEditorDialog(test_b_data, parent=w, modeless=True)

for target_w in (760, 820, 900):
    dlg.resize(target_w, 650)
    dlg.show()
    app.processEvents()
    for sc, content, side_name in [(dlg.left_scroll, dlg.left_content, "왼쪽"), (dlg.right_scroll, dlg.right_content, "오른쪽")]:
        vp = sc.viewport()
        vp_w = vp.width()
        for child in content.findChildren(QWidget):
            if child.isVisible() and child.width() > 0:
                right_pt = child.mapTo(vp, QPoint(child.width(), 0))
                right_x = right_pt.x()
                overflow = right_x - (vp_w + 1)
                text = ""
                if hasattr(child, "text") and callable(child.text):
                    try:
                        text = child.text()
                    except Exception:
                        pass
                check(overflow <= 0,
                      f"버튼설정창({target_w}px {side_name}) {child.__class__.__name__}"
                      f"{f'({text[:15]})' if text else ''} 넘침 없음 (overflow={overflow}px, right={right_x}, vp={vp_w})")

dlg.close()

# 2. 환경설정 창 가로 720, 860 (4개 탭)
sd = SettingsDialog(w.config, parent=w, modeless=True)
for target_w in (720, 860):
    sd.resize(target_w, 620)
    sd.show()
    app.processEvents()
    for tab_idx in range(4):
        sd.tabs.setCurrentIndex(tab_idx, animate=False)
        sd.stack.setCurrentIndex(tab_idx)
        app.processEvents()
        page_widget = sd.stack.widget(tab_idx)  # QScrollArea
        if isinstance(page_widget, QScrollArea):
            vp = page_widget.viewport()
            vp_w = vp.width()
            content = page_widget.widget()
            for child in content.findChildren(QWidget):
                if child.isVisible() and child.width() > 0:
                    right_pt = child.mapTo(vp, QPoint(child.width(), 0))
                    right_x = right_pt.x()
                    overflow = right_x - (vp_w + 1)
                    text = ""
                    if hasattr(child, "text") and callable(child.text):
                        try:
                            text = child.text()
                        except Exception:
                            pass
                    check(overflow <= 0,
                          f"환경설정창({target_w}px 탭{tab_idx}) {child.__class__.__name__}"
                          f"{f'({text[:15]})' if text else ''} 넘침 없음 (overflow={overflow}px, right={right_x}, vp={vp_w})")

sd.close()

# ====================================================================
section("P4: 한국 사용자용 프로필 예시 모음 검증")
from services.sample_profiles import SAMPLES, create_sample_profile
from core.timer_manager import parse_timer

# 1. 모든 예시 생성 및 기본 속성 검증
check(len(SAMPLES) == 10, f"예시 프로필 총 10개 정의됨 ({len(SAMPLES)})")

all_sample_profiles = [create_sample_profile(s) for s in SAMPLES]
check(len(all_sample_profiles) == 10, "모든 예시 프로필 인스턴스 생성 성공")

# 2. 모든 버튼의 아이콘이 REGISTRY에 존재하는지 확인
all_buttons = []
for p in all_sample_profiles:
    for btn in p.buttons.values():
        all_buttons.append(btn)
        if btn.children:
            all_buttons.extend(btn.children.values())

valid_icons = True
invalid_icon_names = []
for b in all_buttons:
    if b.icon.startswith("icon:"):
        iname = b.icon[5:]
        if iname not in IC.REGISTRY:
            valid_icons = False
            invalid_icon_names.append(iname)

check(valid_icons and len(invalid_icon_names) == 0,
      f"모든 예시 버튼의 테마 아이콘이 REGISTRY에 존재함 (잘못된 아이콘: {invalid_icon_names})")

# 3. 모든 단축키를 ShortcutManager.parse가 정상 해석하는지 검증
valid_shortcuts = True
failed_shortcuts = []
for b in all_buttons:
    if b.action_type == "shortcut":
        codes, err = SM.parse(b.action_data)
        if not codes or err:
            valid_shortcuts = False
            failed_shortcuts.append((b.name, b.action_data, err))

check(valid_shortcuts, f"모든 단축키 문자열이 정상 해석됨 (실패: {failed_shortcuts})")

# 4. 모든 timer가 parse_timer로 읽히는지 검증
valid_timers = True
failed_timers = []
for b in all_buttons:
    if b.action_type == "timer":
        t = parse_timer(b.action_data)
        if t["mode"] not in ("countdown", "stopwatch") or t["seconds"] <= 0:
            valid_timers = False
            failed_timers.append((b.name, b.action_data))

check(valid_timers, f"모든 타이머 데이터가 parse_timer로 정상 해석됨 (실패: {failed_timers})")

# 5. 다중 target_process 매칭 검증 (대소문자 무시, whale.exe, MSEDGE.EXE)
w.profiles["profile_browser"] = all_sample_profiles[2]  # 인터넷 프로필
check(w.match_profile("whale.exe", "") == "profile_browser", "whale.exe 자동 매칭 성공")
check(w.match_profile("MSEDGE.EXE", "") == "profile_browser", "대문자 MSEDGE.EXE 자동 매칭 성공")
check(w.match_profile("chrome.exe", "") == "profile_browser", "chrome.exe 자동 매칭 성공")

# 6. 빈 데이터 폴더 테스트: 프로필 3개, 기본 3x4, 더보기 안 8개
import tempfile
import shutil
empty_tmp = tempfile.mkdtemp(prefix="vdeck_empty_test_")
empty_storage = StorageService(data_dir=empty_tmp)
c_empty, p_empty, cur_empty = empty_storage.load_data()

check(len(p_empty) == 3, f"빈 데이터 폴더 로드 시 프로필 3개 생성됨 ({list(p_empty.keys())})")
check(c_empty.rows == 3 and c_empty.cols == 4, f"기본 그리드 크기가 3행 4열임 ({c_empty.rows}x{c_empty.cols})")
def_p = p_empty.get("profile_default")
more_btn = def_p.buttons.get(DeckButtonData.make_id(2, 3)) if def_p else None
more_count = len([b for b in more_btn.children.values() if not b.is_empty()]) if (more_btn and more_btn.children) else 0
check(more_count == 8, f"더보기 버튼 안의 자식 버튼 개수가 8개임 ({more_count}개)")
shutil.rmtree(empty_tmp, ignore_errors=True)

# 7. 기존 프로필 + 예시 2개 추가 테스트 (이름 중복 시 '(예시)' 추가 및 ensure_grid 보존)
from ui.profile_manager_dialog import ProfileManagerDialog, SampleProfilesDialog
pm = ProfileManagerDialog({k: v.copy() for k, v in w.profiles.items()}, w.current_profile_id, w.storage, parent=w)
sp_dlg = SampleProfilesDialog(pm, parent=w)
# '한글', '기본' 2개 체크
for cb, item in sp_dlg.checkboxes:
    if item["key"] in ("default", "hwp"):
        cb.setChecked(True)

orig_count = len(pm.profiles)
sp_dlg._add_selected()
check(len(pm.profiles) == orig_count + 2, f"예시 2개 추가 성공 (총 {len(pm.profiles)}개)")
names = [p.name for p in pm.profiles.values()]
check("기본 (예시)" in names, f"중복된 '기본' 이름이 '기본 (예시)'로 생성됨 ({names})")
check("한글" in names, f"새로운 '한글' 예시가 정상 추가됨 ({names})")
pm.close()

# ====================================================================
section("프로필 메뉴 및 수동 프로필 유지 (1.6.6)")
# 1. _exec_menu 테스트: QMenu.exec 가짜 함수로 대체
from PySide6.QtWidgets import QMenu
dummy_menu = QMenu()
dummy_menu_open_val = None


def fake_menu_exec(pos=None):
    global dummy_menu_open_val
    dummy_menu_open_val = w._menu_open
    return None


dummy_menu.exec = fake_menu_exec
w._exec_menu(dummy_menu, QPoint(0, 0))
check(dummy_menu_open_val == 1 and w._menu_open == 0,
      f"_exec_menu 실행 중 _menu_open == 1, 종료 후 0 (중간={dummy_menu_open_val}, 끝={w._menu_open})")

# 2. _menu_open 이 1 일 때 keep_topmost 호출 방지
import core.win32 as win32_mod
topmost_calls = []
orig_keep_topmost = win32_mod.keep_topmost
win32_mod.keep_topmost = lambda hwnd, enable: topmost_calls.append((hwnd, enable))
try:
    w.config.always_on_top = True
    w._native_ready = True
    w._dialog_open.clear()

    topmost_calls.clear()
    w._menu_open = 1
    w._on_live_tick()
    check(len(topmost_calls) == 0, f"_menu_open == 1 일 때 keep_topmost 미호출 ({len(topmost_calls)}회)")

    topmost_calls.clear()
    w._menu_open = 0
    w._on_live_tick()
    check(len(topmost_calls) == 1, f"_menu_open == 0 일 때 keep_topmost 정상 호출 ({len(topmost_calls)}회)")
finally:
    win32_mod.keep_topmost = orig_keep_topmost
    w._menu_open = 0

# 3. 자동 전환 및 수동 선택 프로필 유지 (manual hold)
from core.app_detector import AppDetector, _is_own_pid
import os
check(_is_own_pid(os.getpid()) is True and _is_own_pid(9999999) is False,
      "_is_own_pid PID 검증 정상 (자기 자신 True, 타 PID False)")

# 프로필 설정: 기존 profile_browser (chrome.exe 타겟)와 profile_default 준비
w.config.auto_switch_profile = True
w._dialog_open.clear()
w._menu_open = 0
chrome_pid = "profile_browser"
w.current_profile_id = "profile_default"
w.last_detected_key = None
w._manual_hold_exe = None
w._last_external_exe = ""

# 1) ("chrome.exe", "A") -> 크롬 프로필로 자동 전환
AppDetector.get_foreground_app = lambda: ("chrome.exe", "A", 1234)
w._on_tracker_tick()
check(w.current_profile_id == chrome_pid, f"1) 크롬 포커스 시 크롬 프로필 자동 전환 ({w.current_profile_id})")

# 2) 수동으로 기본 프로필 선택 후 ("chrome.exe", "B") -> 기본 프로필 유지
w.switch_profile("profile_default", manual=True)
check(w.current_profile_id == "profile_default" and w._manual_hold_exe == "chrome.exe",
      f"2-1) 수동 전환 시 _manual_hold_exe 설정됨 (hold={w._manual_hold_exe})")
AppDetector.get_foreground_app = lambda: ("chrome.exe", "B", 1234)
w._on_tracker_tick()
check(w.current_profile_id == "profile_default",
      f"2-2) 같은 exe 내 창 제목 변경 시 수동 프로필 유지 ({w.current_profile_id})")

# 3) 다른 프로그램 ("notepad.exe", "C") -> hold 해제 및 자동 전환 (기본 프로필)
AppDetector.get_foreground_app = lambda: ("notepad.exe", "C", 5678)
w._on_tracker_tick()
check(w._manual_hold_exe is None and w.current_profile_id == "profile_default",
      "3) 다른 프로그램 포커스 시 _manual_hold_exe 초기화됨")

# 4) 다시 크롬 포커스 ("chrome.exe", "D") -> 크롬 프로필로 자동 전환
AppDetector.get_foreground_app = lambda: ("chrome.exe", "D", 1234)
w._on_tracker_tick()
check(w.current_profile_id == chrome_pid,
      f"4) 다시 크롬 포커스 시 크롬 프로필로 정상 자동 전환 ({w.current_profile_id})")

# ================================================================ 프로필 이동 버튼 테스트
check(AE.ACTION_LABELS.get("profile") == "프로필 이동", "ACTION_LABELS 에 profile 라벨 등록 확인")
check(AE.ACTION_ICONS.get("profile") == "👤", "ACTION_ICONS 에 profile 아이콘 등록 확인")
check(AE.describe_action("profile", "__next__") == "프로필 이동", "describe_action profile 확인")
check(IC.ACTION_DEFAULT_ICONS.get("profile") == "user", "ui/icons ACTION_DEFAULT_ICONS profile 확인")

# 프로필 A, B, C 준비
prof_a_id = "test_prof_a"
prof_b_id = "test_prof_b"
prof_c_id = "test_prof_c"
w.profiles[prof_a_id] = DeckProfile(id=prof_a_id, name="프로필A", buttons={})
w.profiles[prof_b_id] = DeckProfile(id=prof_b_id, name="프로필B", buttons={})
w.profiles[prof_c_id] = DeckProfile(id=prof_c_id, name="프로필C", buttons={})
w.storage.ensure_grid(w.profiles[prof_a_id], w.config.rows, w.config.cols)
w.storage.ensure_grid(w.profiles[prof_b_id], w.config.rows, w.config.cols)
w.storage.ensure_grid(w.profiles[prof_c_id], w.config.rows, w.config.cols)

w.switch_profile(prof_a_id, manual=False)
w._last_external_exe = "test_app.exe"
w._manual_hold_exe = None

# 프로필 A의 버튼에 프로필 B로 이동하는 버튼 설정
btn_0_0 = DeckButtonData.make_id(0, 0)
w.profiles[prof_a_id].buttons[btn_0_0] = DeckButtonData(
    id=btn_0_0, name="B로 이동", action_type="profile", action_data=prof_b_id, row=0, col=0
)
w._rebuild_grid()

exec_count_before = len([e for e in executed if e[0] == "profile"])
w._handle_click(btn_0_0)
check(w.current_profile_id == prof_b_id, f"profile 버튼 클릭으로 프로필 B로 이동함 ({w.current_profile_id})")
check(w._manual_hold_exe == "test_app.exe", f"수동 우선 _manual_hold_exe 가 _last_external_exe 에 맞게 설정됨 ({w._manual_hold_exe})")
exec_count_after = len([e for e in executed if e[0] == "profile"])
check(exec_count_before == exec_count_after, "ActionExecutor.execute 로 가지 않고 main_window 에서 처리됨")

# 3개 프로필에서 __next__ 3번 누르면 한 바퀴 돌아 처음으로, __prev__는 반대로
orig_profiles = w.profiles.copy()
w.profiles = {
    prof_a_id: orig_profiles[prof_a_id],
    prof_b_id: orig_profiles[prof_b_id],
    prof_c_id: orig_profiles[prof_c_id],
}
w.current_profile_id = prof_a_id

w._switch_profile_by_action("__next__")
check(w.current_profile_id == prof_b_id, f"__next__ 1회: B로 이동 ({w.current_profile_id})")
w._switch_profile_by_action("__next__")
check(w.current_profile_id == prof_c_id, f"__next__ 2회: C로 이동 ({w.current_profile_id})")
w._switch_profile_by_action("__next__")
check(w.current_profile_id == prof_a_id, f"__next__ 3회: A로 복귀 ({w.current_profile_id})")

w._switch_profile_by_action("__prev__")
check(w.current_profile_id == prof_c_id, f"__prev__ 1회: C로 이동 ({w.current_profile_id})")
w._switch_profile_by_action("__prev__")
check(w.current_profile_id == prof_b_id, f"__prev__ 2회: B로 이동 ({w.current_profile_id})")
w._switch_profile_by_action("__prev__")
check(w.current_profile_id == prof_a_id, f"__prev__ 3회: A로 복귀 ({w.current_profile_id})")

w.profiles = orig_profiles

# 없는 프로필 id -> current_profile_id 그대로, 오류 없이 지나감
cur = w.current_profile_id
ok, msg = w._switch_profile_by_action("non_existent_profile_id")
check(not ok and w.current_profile_id == cur, f"없는 프로필 id 전달 시 current_profile_id 유지 ({w.current_profile_id})")

# 길게 누르기에 profile을 넣은 버튼: w._handle_long_press(id) -> 프로필이 이동함
w.switch_profile(prof_a_id, manual=False)
w.profiles[prof_a_id].buttons[btn_0_0] = DeckButtonData(
    id=btn_0_0, name="길게눌러C", action_type="url", action_data="https://example.com",
    hold_action_type="profile", hold_action_data=prof_c_id, row=0, col=0
)
w._rebuild_grid()
w._handle_long_press(btn_0_0)
check(w.current_profile_id == prof_c_id, f"길게 누르기 profile 동작으로 프로필 C로 이동함 ({w.current_profile_id})")

# 버튼 설정 창 테스트
b_edit_data = DeckButtonData(id="btn_1_1", row=1, col=1, name="", action_type="profile", action_data=prof_b_id)
editor_dlg = ButtonEditorDialog(b_edit_data, parent=w, modeless=True)

# profile 콤보에 프로필 이름들이 들어 있음
p_page = editor_dlg.action.pages["profile"]
combo_items = [p_page.combo.itemText(i) for i in range(p_page.combo.count())]
check("▶ 다음 프로필" in combo_items and "◀ 이전 프로필" in combo_items, "profile 콤보에 특별 항목 포함됨")
check("프로필A" in combo_items and "프로필B" in combo_items and "프로필C" in combo_items, "profile 콤보에 프로필 이름들 포함됨")

# value() 가 ("profile", id)
check(editor_dlg.action.value() == ("profile", prof_b_id), f"editor_dlg.action.value()가 ('profile', '{prof_b_id}')임")

# set_value 왕복
editor_dlg.action.set_value("profile", "__next__")
check(editor_dlg.action.value() == ("profile", "__next__"), "set_value __next__ 왕복 확인")
editor_dlg.action.set_value("profile", prof_a_id)
check(editor_dlg.action.value() == ("profile", prof_a_id), "set_value 프로필 id 왕복 확인")

# 없는 id를 set_value 해도 오류 없음
editor_dlg.action.set_value("profile", "unknown_missing_id")
check(editor_dlg.action.value() == ("profile", "unknown_missing_id"), "없는 id set_value 시 오류 없이 선택됨")

# 저장 시 이름 자동 채움
editor_dlg.name_edit.setText("")
editor_dlg.action.set_value("profile", "__next__")
editor_dlg._on_save()
check(editor_dlg.name_edit.text() == "다음 프로필", f"저장 시 이름 자동 채움 확인 ({editor_dlg.name_edit.text()})")

editor_dlg.name_edit.setText("")
editor_dlg.action.set_value("profile", prof_b_id)
editor_dlg._on_save()
check(editor_dlg.name_edit.text() == "프로필B", f"저장 시 프로필 이름으로 자동 채움 확인 ({editor_dlg.name_edit.text()})")

# "profile" 일 때 켜기/끄기 스위치 비활성
check(not editor_dlg.toggle.isEnabled(), "profile 동작일 때 켜기/끄기 스위치 비활성화됨")
check(not editor_dlg.toggle.isChecked(), "profile 동작일 때 켜기/끄기 스위치 꺼짐")

# 다른 동작으로 바꾸면 다시 활성화
editor_dlg.action.set_value("url", "https://google.com")
editor_dlg._on_action_changed()
check(editor_dlg.toggle.isEnabled(), "url 동작으로 변경 시 켜기/끄기 스위치 다시 활성화됨")

editor_dlg.close()

# ====================================================================
section("P8: 설치된 앱 고르기 및 AI 모음 검증")
from core.app_finder import (
    parse_start_apps_json, find_app, app_launch_command, is_app_command,
)
from core.running_state import is_program_running, close_program_windows
from ui.app_picker_dialog import AppPickerDialog
from ui.button_editor_dialog import ButtonEditorDialog

# 1. parse_start_apps_json 검증
# 목록
json_list = json.dumps([
    {"Name": "Beta App", "AppID": "id.beta"},
    {"Name": "Alpha App", "AppID": "id.alpha"},
    {"Name": "Alpha App", "AppID": "id.alpha2"},  # 중복 제거
])
parsed_list = parse_start_apps_json(json_list)
check(len(parsed_list) == 2, f"중복 제거 및 2개 파싱됨 ({len(parsed_list)})")
check(parsed_list[0][0] == "Alpha App" and parsed_list[1][0] == "Beta App", "가나다/ABC 정렬됨")

# 객체 하나
json_single = json.dumps({"Name": "Single App", "AppID": "id.single"})
check(len(parse_start_apps_json(json_single)) == 1, "단일 객체 JSON 파싱 성공")

# 빈 글자
check(parse_start_apps_json("") == [], "빈 글자 파싱 시 빈 목록")
check(parse_start_apps_json("   ") == [], "공백 글자 파싱 시 빈 목록")

# 깨진 JSON
check(parse_start_apps_json("{broken json") == [], "깨진 JSON 파싱 시 빈 목록")

# 이름이나 AppID가 빈 항목 건너뜀
json_empty_fields = json.dumps([
    {"Name": "", "AppID": "id1"},
    {"Name": "Valid", "AppID": "id2"},
    {"Name": "NoId", "AppID": ""},
])
parsed_empty = parse_start_apps_json(json_empty_fields)
check(len(parsed_empty) == 1 and parsed_empty[0][0] == "Valid", "이름/AppID 비어있으면 건너뜀")

# 2. find_app 검증
fake_apps = [
    ("Claude Desktop", "id.claude.desktop"),
    ("Claude", "id.claude"),
    ("MyClaudeTool", "id.myclaude"),
    ("클로드 번역기", "id.korean.claude"),
]
# 정확히 같음 > 시작함 > 포함 순서
found = find_app("Claude", fake_apps)
check(found is not None and found[0] == "Claude" and found[1] == "id.claude", "정확히 같은 앱 우선 반환")

found_prefix = find_app("클로드", fake_apps)
check(found_prefix is not None and found_prefix[0] == "클로드 번역기", "시작하는 앱 반환")

found_contains = find_app("Tool", fake_apps)
check(found_contains is not None and found_contains[0] == "MyClaudeTool", "포함하는 앱 반환")

# "Claude|클로드" 후보 지원
found_multi = find_app("없는앱|클로드", fake_apps)
check(found_multi is not None and found_multi[0] == "클로드 번역기", "다중 후보 지원")

# 대소문자 무시
found_case = find_app("cLaUdE", fake_apps)
check(found_case is not None and found_case[0] == "Claude", "대소문자 무시 검색")

# 없으면 None
check(find_app("NonExistentAppXYZ", fake_apps) is None, "일치하는 앱 없으면 None")

# 3. app_launch_command / is_app_command 검증
cmd1 = app_launch_command("Microsoft.WindowsNotepad_8wekyb3d8bbwe!App")
check(cmd1.startswith(r"explorer.exe shell:AppsFolder\\"), f"일반 AppID 변환 확인: {cmd1}")
check(is_app_command(cmd1), "is_app_command True 확인")
check(is_app_command(cmd1.upper()), "is_app_command 대소문자 무시 확인")

real_file = os.path.abspath(__file__)
check(app_launch_command(real_file) == real_file, "실존 파일 경로는 그대로 반환")
check(not is_app_command("notepad.exe"), "일반 명령은 is_app_command False")
check(not is_app_command(""), "빈 문자열은 is_app_command False")

# 4. running_state 안전장치 검증
check(is_program_running(cmd1) is None, "앱 이름표 명령은 is_program_running이 None")
check(close_program_windows(cmd1) == 0, "앱 이름표 명령은 close_program_windows가 0 (탐색기 보호)")

# 5. 버튼 설정 창 (ButtonEditorDialog) 검증
test_btn = DeckButtonData(id="btn_0_0", row=0, col=0, name="테스트", action_type="program", action_data="notepad.exe")
beditor = ButtonEditorDialog(test_btn, parent=w, modeless=True)
prog_page = beditor.action.pages.get("program")
check(prog_page is not None, "program 설정 페이지 존재")
pick_btns = [child for child in prog_page.findChildren(object) if getattr(child, "text", lambda: "")() == "앱 목록"]
check(len(pick_btns) >= 1, "program 페이지에 '앱 목록' 버튼이 있음")

# app_picked 흉내 -> 이름 칸 자동 채움
beditor.name_edit.setText("")
beditor.action.app_picked.emit("테스트앱")
check(beditor.name_edit.text() == "테스트앱", f"app_picked 수신 시 이름 자동 채움 ({beditor.name_edit.text()})")

# 앱 이름표 명령일 때 끄기 때 할 일이 close 로 자동 설정되지 않음
beditor.toggle.setChecked(True)
beditor.off_action.set_value("close", "")
beditor.action.set_value("program", cmd1)
beditor._on_action_changed()
check(beditor.off_action.get_type() != "close", "앱 이름표 명령일 때 off_action이 close로 유지/설정되지 않음")

# 저장 시 경고 없이 저장됨
beditor._on_save()
check(beditor.result() == 1, "앱 이름표 명령 저장 시 경고 없이 저장 완료")
beditor.close()

# 6. AppPickerDialog 검증 (가짜 목록, exec 없이 객체만 생성)
picker_dlg = AppPickerDialog(parent=w, initial_apps=[("Claude", "id.claude"), ("Gemini", "id.gemini")])
check(picker_dlg.list_widget.count() == 2, "초기 앱 목록 2개 표시")
picker_dlg.search_edit.setText("gem")
check(picker_dlg.list_widget.count() == 1 and picker_dlg.list_widget.item(0).text() == "Gemini", "검색 필터 작동")
picker_dlg.close()

# 빈 목록일 때 안내 문구
empty_picker = AppPickerDialog(parent=w, initial_apps=[])
check(not empty_picker.status_label.isHidden(), "빈 목록일 때 안내 문구 표시됨")
check("가져오지 못했어요" in empty_picker.status_label.text(), "안내 문구 내용 확인")
empty_picker.close()

# 7. 예시 모음 "AI 모음" 변환 검증
ai_sample = next(s for s in SAMPLES if s["key"] == "ai")

# 1) 전부 찾음 -> program 4개가 앱 이름표 명령
import core.app_finder as AF_MOD
orig_find = AF_MOD.find_app
AF_MOD.find_app = lambda kw, apps=None: (kw.split("|")[0], f"id.{kw.split('|')[0].lower()}")
prof_all_found = create_sample_profile(ai_sample)
prog_btns = [b for b in prof_all_found.buttons.values() if b.name in ("Claude", "ChatGPT", "Gemini", "Antigravity")]
check(len(prog_btns) == 4, "AI 모음 앱 버튼 4개 존재")
check(all(b.action_type == "program" and is_app_command(b.action_data) for b in prog_btns), "전부 찾았을 때 program 4개가 앱 이름표 명령")
check(not any("app:" in b.action_data for b in prof_all_found.buttons.values()), "app: 문자열이 남지 않음 (모두 찾음)")

# 2) 전부 못 찾음 -> url 4개가 대체주소
AF_MOD.find_app = lambda kw, apps=None: None
prof_none_found = create_sample_profile(ai_sample)
url_btns = [b for b in prof_none_found.buttons.values() if b.name in ("Claude", "ChatGPT", "Gemini", "Antigravity")]
check(all(b.action_type == "url" and b.action_data.startswith("http") for b in url_btns), "전부 못 찾았을 때 url 4개가 대체주소로 변환")
check(not any("app:" in b.action_data for b in prof_none_found.buttons.values()), "app: 문자열이 남지 않음 (모두 못 찾음)")

# 3) 일부만 찾음 혼합
AF_MOD.find_app = lambda kw, apps=None: ("Claude", "id.claude") if "Claude" in kw else None
prof_mixed = create_sample_profile(ai_sample)
claude_b = next(b for b in prof_mixed.buttons.values() if b.name == "Claude")
gpt_b = next(b for b in prof_mixed.buttons.values() if b.name == "ChatGPT")
check(claude_b.action_type == "program" and is_app_command(claude_b.action_data), "찾은 앱은 program 앱 이름표 명령")
check(gpt_b.action_type == "url" and gpt_b.action_data == "https://chatgpt.com", "못 찾은 앱은 url 대체주소")
check(not any("app:" in b.action_data for b in prof_mixed.buttons.values()), "app: 문자열이 남지 않음 (일부 찾음)")

AF_MOD.find_app = orig_find

# ====================================================================
section("색·글꼴")
from PySide6.QtGui import QColor  # noqa: E402

# 1. 색 이름 검사
new_tints = ["teal", "lime", "navy", "brown", "gray", "black", "white"]
check(len(theme.BUTTON_TINT_KEYS) == 18 and all(k in theme.TINTS for k in theme.BUTTON_TINT_KEYS),
      f"BUTTON_TINT_KEYS 18개이고 모두 TINTS에 있음 ({len(theme.BUTTON_TINT_KEYS)}개)")
check(all(k in theme.TINTS for k in new_tints), f"새 틴트 {new_tints}가 모두 TINTS에 있음")
check(all(theme.tint_colors(k) is not None and len(theme.tint_colors(k)) == 3 for k in new_tints),
      "새 틴트들의 tint_colors가 각각 투명이 아닌 3색을 돌려줌")
new_icons = ["red", "teal", "lime", "sky", "gray", "black"]
check(all(k in theme.ICON_COLORS for k in new_icons), f"ICON_COLORS에 {new_icons}가 있음")

# 2. hex 검사
check(theme.is_hex_color("#a1B2c3") is True and not theme.is_hex_color("#12345") and not theme.is_hex_color("red") and not theme.is_hex_color(None),
      "is_hex_color hex 검증 (#a1B2c3 True, #12345/red/None False)")
check(theme.tint_colors("#ffe66d")[2].name() == "#1f2937", "밝은 hex 틴트 글자색 진한 색(#1f2937)")
check(theme.tint_colors("#1b2a49")[2].name() == "#ffffff", "어두운 hex 틴트 글자색 흰색(#ffffff)")
check(theme.tint_colors("nonexist") is None and theme.tint_colors("clear") is None, "없는 틴트와 clear는 None")
check(theme.glass_tint_hex("#123456") == "#123456", "glass_tint_hex hex 반환")
check(theme.icon_color_hex("#112233") == "#112233" and theme.icon_color_hex("auto") is None, "icon_color_hex 동작")

# 3. config.custom_colors 검사
from models.config_model import clean_custom_colors  # noqa: E402
check(clean_custom_colors(["#ABCDEF", "#abcdef", "bad", "#123456"]) == ["#abcdef", "#123456"],
      "clean_custom_colors 소문자/중복제거/유효값 정리")
check(len(clean_custom_colors([f"#{i:06x}" for i in range(15)])) == 12, "clean_custom_colors 최대 12개 제한")
check(AppConfig.from_dict({"custom_colors": ["#ABCDEF", "x"]}).custom_colors == ["#abcdef"],
      "AppConfig.from_dict custom_colors 정리")
c_custom_test = AppConfig(custom_colors=["#112233", "#445566"])
check(AppConfig.from_dict(c_custom_test.to_dict()).custom_colors == ["#112233", "#445566"],
      "custom_colors to_dict 후 from_dict 유지")

# 4. ui_font 검사
check(AppConfig.from_dict({"ui_font": 123}).ui_font == "" and AppConfig.from_dict({"ui_font": " Foo "}).ui_font == "Foo",
      "AppConfig ui_font 공백제거 및 비문자열 처리")

orig_qf = theme.QFontDatabase
orig_ui_font = theme.UI_FONT
class FakeFontDatabase:
    Korean = 1
    Any = 0
    class WritingSystem:
        Korean = 1
        Any = 0
    @staticmethod
    def families(*args, **kwargs):
        return ["Pretendard", "Fake Font", "@Vertical Font"]

theme.QFontDatabase = FakeFontDatabase
try:
    check(theme.set_ui_font("Fake Font") == "Fake Font", "set_ui_font 설치된 글꼴 설정")
    check(theme.set_ui_font("없는글꼴XYZ") == theme.DEFAULT_UI_FONT, "set_ui_font 없는 글꼴 기본값 복구")
    check(theme.set_ui_font("") == theme.DEFAULT_UI_FONT, "set_ui_font 빈 글꼴 기본값 복구")
    k_fams = theme.korean_font_families()
    check(theme.DEFAULT_UI_FONT not in k_fams and not any(f.startswith("@") for f in k_fams) and k_fams == sorted(k_fams) and "Fake Font" in k_fams,
          "korean_font_families DEFAULT_UI_FONT 및 @ 제외 및 정렬 확인")
finally:
    theme.QFontDatabase = orig_qf
    theme.UI_FONT = orig_ui_font

# 5. ColorChips 위젯 동작 검사
from ui.widgets import ColorChips  # noqa: E402
chips = ColorChips()
n = len(chips.keys)
check(n == 19, f"ColorChips 기본 키 개수 19개 ({n}개)")
added_signals = []
chips.custom_added.connect(added_signals.append)
chips.add_custom("#ff8800")
check(len(chips.keys) == n + 1 and chips.current == "#ff8800" and chips.keys[-1] == "__add__" and chips.keys[-2] == "#ff8800" and chips.custom == ["#ff8800"],
      "add_custom 후 키/현재선택/custom 배열 확인")
check(added_signals == ["#ff8800"], "custom_added 시그널 1회 발생")
chips.add_custom("#ff8800")
check(len(chips.custom) == 1, "동일 색상 재추가 시 custom 길이 1 유지")

removed_signals = []
chips.custom_removed.connect(removed_signals.append)
chips.remove_custom("#ff8800")
check(len(chips.keys) == n and chips.current == "clear" and chips.custom == [],
      "remove_custom 후 키 수/현재선택(clear)/custom([]) 복구")
check(removed_signals == ["#ff8800"], "custom_removed 시그널 발생")

for i in range(15):
    chips.add_custom(f"#{i:06x}")
check(len(chips.custom) == 12, "ColorChips custom 최대 12개 제한")
chips.add_custom("bad")
check("bad" not in chips.custom, "유효하지 않은 색상 무시")

chips_icon = ColorChips(mode="icon")
chips_icon.set_current("#123456")
check(chips_icon.current == "#123456" and chips_icon.keys[-2] == "#123456" and chips_icon.keys[-1] == "__add__",
      "아이콘 모드 임시 hex 칩 확인")
chips_icon.set_current("모르는이름")
check(chips_icon.current == chips_icon.keys[0], "모르는 이름 선택 시 첫 번째 키 선택")

# 6. ColorChips 가짜 선택창 검사
from ui.widgets import pick_color  # noqa: E402
check(callable(pick_color), "pick_color 함수 존재 및 호출 가능")

import ui.widgets as widgets_mod  # noqa: E402
orig_pick_color = widgets_mod.pick_color
try:
    widgets_mod.pick_color = lambda parent, initial, title="색 고르기": QColor("#34c759")
    chips._pick_custom()
    check(chips.current == "#34c759" and "#34c759" in chips.custom, "가짜 pick_color 선택 색상 추가 및 선택")
    cur_before = chips.current
    custom_before = list(chips.custom)
    widgets_mod.pick_color = lambda parent, initial, title="색 고르기": None
    chips._pick_custom()
    check(chips.current == cur_before and chips.custom == custom_before, "pick_color 취소(None) 시 색상 변경 없음")
finally:
    widgets_mod.pick_color = orig_pick_color

# settings_dialog 쪽 ColorSwatch 검사
from ui.settings_dialog import ColorSwatch  # noqa: E402
import ui.settings_dialog as settings_mod  # noqa: E402
swatch = ColorSwatch("#112233")
orig_swatch_pick = settings_mod.pick_color
try:
    settings_mod.pick_color = lambda parent, initial, title="색 고르기": QColor("#ff5500")
    swatch._pick()
    check(swatch.color == "#ff5500", "ColorSwatch pick_color 선택 반영")
    settings_mod.pick_color = lambda parent, initial, title="색 고르기": None
    swatch._pick()
    check(swatch.color == "#ff5500", "ColorSwatch pick_color 취소(None) 시 유지")
finally:
    settings_mod.pick_color = orig_swatch_pick

# 7. 오른쪽 클릭 메뉴 검사
orig_glass_menu = widgets_mod.glass_menu
sentinel_act = object()
exec_return = sentinel_act
class FakeMenu:
    def addAction(self, text):
        return sentinel_act
    def exec(self, pos):
        return exec_return

try:
    widgets_mod.glass_menu = lambda parent=None: FakeMenu()
    exec_return = sentinel_act
    chips._context_menu("#34c759", QPoint(0, 0))
    check("#34c759" not in chips.custom, "우클릭 메뉴 선택 시 custom 색상 삭제")
    chips.add_custom("#34c759")
    exec_return = None
    chips._context_menu("#34c759", QPoint(0, 0))
    check("#34c759" in chips.custom, "우클릭 메뉴 취소 시 custom 색상 유지")
finally:
    widgets_mod.glass_menu = orig_glass_menu

# 8. 편집창 연동 검사
from ui.button_editor_dialog import ButtonEditorDialog  # noqa: E402
bedit_btn = DeckButtonData(id="btn_custom_test", row=0, col=0, name="색테스트")
bedit_dlg = ButtonEditorDialog(bedit_btn, parent=w, modeless=True)
try:
    bedit_dlg.colors.add_custom("#aa5500")
    check(len(w.config.custom_colors) > 0 and w.config.custom_colors[0] == "#aa5500",
          "편집창 색 추가 시 w.config.custom_colors 에 반영")
    check("#aa5500" in bedit_dlg.icon_colors.custom, "다른 쪽 칩(icon_colors)에도 커스텀 색상 반영")
    bedit_dlg.icon_colors.remove_custom("#aa5500")
    check("#aa5500" not in w.config.custom_colors, "편집창 색 삭제 시 w.config.custom_colors 에서 제거")
    check("#aa5500" not in bedit_dlg.colors.custom, "다른 쪽 칩(colors)에서도 커스텀 색상 제거")
finally:
    bedit_dlg.close()

# 9. 글자색 label_color 검사 (글자색 == 아이콘색)
from ui.deck_button import label_color, icon_color_for  # noqa: E402
d_lbl = DeckButtonData(id="btn_lbl", name="라벨", icon_color="auto")
fg_sample = QColor("#112233")
face_sample = QColor("#ffffff")
check(label_color(d_lbl, face_sample, fg_sample) == fg_sample, "icon_color='auto' 이면 label_color == fg")
d_lbl.icon_color = "purple"
check(label_color(d_lbl, face_sample, fg_sample).name() == icon_color_for(d_lbl, fg_sample).name(),
      "icon_color='purple' 이면 label_color(...).name() == icon_color_for(...).name()")
d_lbl.icon_color = "모르는이름"
check(label_color(d_lbl, face_sample, fg_sample) == fg_sample, "모르는 아이콘 색 이름은 fg 유지")

glass_list = ["blue", "orange", "yellow", "purple", "clear"]
icon_list = ["yellow", "white", "blue", "pink"]
all_combos_ok = True
for g_tint in glass_list:
    colors = theme.tint_colors(g_tint)
    g_fg = colors[2] if colors else QColor(theme.T().text)
    g_face = QColor((colors[0].red() + colors[1].red()) // 2,
                    (colors[0].green() + colors[1].green()) // 2,
                    (colors[0].blue() + colors[1].blue()) // 2) if colors else QColor(theme.T().base)
    for ico in icon_list:
        test_btn = DeckButtonData(id="combo_test", name="조합", icon_color=ico)
        if label_color(test_btn, g_face, g_fg) != icon_color_for(test_btn, g_fg):
            all_combos_ok = False
            break
    if not all_combos_ok:
        break
check(all_combos_ok, "유리색 5종 × 아이콘색 4종 모든 조합에서 글자색 == 아이콘색")

# 10. 설정창 글꼴 드롭다운 및 미리보기 라벨 검사
from ui.settings_dialog import SettingsDialog  # noqa: E402
cfg_set = w.config.copy()
cfg_set.ui_font = ""
sdlg = SettingsDialog(cfg_set, storage=w.storage, parent=w, modeless=True)
try:
    check(hasattr(sdlg, "font_combo") and hasattr(sdlg, "font_preview_lab"), "설정창에 font_combo 와 font_preview_lab 존재")
    check(sdlg.font_combo.currentData() == "" and sdlg.font_combo.count() >= 1, "font_combo 첫 항목 currentData == '' 및 항목 1개 이상")
    if sdlg.font_combo.count() > 1:
        target_font = sdlg.font_combo.itemData(1)
        cfg_with_font = w.config.copy()
        cfg_with_font.ui_font = target_font
        sdlg_font = SettingsDialog(cfg_with_font, storage=w.storage, parent=w, modeless=True)
        check(sdlg_font.font_combo.currentData() == target_font, "설정된 글꼴이 font_combo 에서 선택됨")
        sdlg_font.close()
    cfg_bad = w.config.copy()
    cfg_bad.ui_font = "없는글꼴ABCXYZ"
    sdlg_bad = SettingsDialog(cfg_bad, storage=w.storage, parent=w, modeless=True)
    check(sdlg_bad.font_combo.currentData() == "", "없는 글꼴은 '기본' 항목 선택")
    sdlg_bad.close()
finally:
    sdlg.close()
    theme.set_ui_font("")

# 11. 정보 버튼 다중 표시 및 종류 파싱 테스트
from core.system_info import parse_kinds, capacity, read_info  # noqa: E402
from ui.deck_button import DeckButtonWidget  # noqa: E402

check(parse_kinds("clock", 1) == ["clock"] and parse_kinds("clock,date,battery", 2) == ["clock", "date"],
      "parse_kinds 기본 및 limit 동작")
check(parse_kinds("foo,clock,clock", 4) == ["clock"] and parse_kinds("", 4) == ["clock"],
      "parse_kinds 없는 종류 버림, 중복 제거, 빈 값 처리")
check(capacity(1, 1) == 1 and capacity(2, 1) == 2 and capacity(1, 2) == 2 and capacity(2, 2) == 4,
      "capacity 칸 수별 용량 (1칸->1, 2칸->2, 4칸->4)")

val_sec, _, _ = read_info("clock_sec")
val_12, _, _ = read_info("clock12")
check(val_sec.count(":") == 2, f"read_info('clock_sec') 초 포함 시계 ({val_sec})")
check(("오전" in val_12 or "오후" in val_12), f"read_info('clock12') 오전/오후 시계 ({val_12})")

multi_info_btn = DeckButtonData(id="btn_multi_info", name="정보테스트", action_type="info",
                                action_data="clock,date,battery,cpu", span_cols=2, span_rows=2)
info_widget = DeckButtonWidget(multi_info_btn, 88, True, "line", parent=w)
info_widget.set_span(2, 2)
info_pixmap = info_widget.grab()
check(not info_pixmap.isNull() and info_pixmap.width() > 0 and info_pixmap.height() > 0,
      "2x2 정보 버튼(clock,date,battery,cpu) DeckButtonWidget grab 이미지 생성")
info_widget.deleteLater()

# 12. 예약(schedule) 버튼 관리자 및 동작 테스트
from core.schedule_manager import parse_schedule, due_events, next_event, ScheduleManager  # noqa: E402
from core.action_executor import ActionExecutor  # noqa: E402

# due_events: 09:00 시작, now=09:00:30 -> ["start"], now=09:05 -> [] (90초 지남), now=08:59 -> []
cfg_test = {"start": "09:00", "end": "", "days": [0, 1, 2, 3, 4, 5, 6]}
base_mon = datetime(2026, 10, 26, 9, 0, 30)
check(due_events(cfg_test, base_mon, {}) == ["start"], "due_events 09:00:30에 start 감지")
check(due_events(cfg_test, datetime(2026, 10, 26, 9, 5, 0), {}) == [], "due_events 09:05:00에 90초 경과로 빈 목록")
check(due_events(cfg_test, datetime(2026, 10, 26, 8, 59, 59), {}) == [], "due_events 08:59:59에 아직 시각 전으로 빈 목록")

# 요일 제외: days=[1](화요일)인 경우 월요일에는 [], 화요일 09:00:10에는 ["start"]
cfg_tue = {"start": "09:00", "end": "", "days": [1]}
check(due_events(cfg_tue, datetime(2026, 10, 26, 9, 0, 10), {}) == [], "days=[1]인 경우 월요일에 빈 목록")
check(due_events(cfg_tue, datetime(2026, 10, 27, 9, 0, 10), {}) == ["start"], "days=[1]인 경우 화요일 09:00:10에 start 감지")

# last_fired 에 오늘 날짜가 있으면 [] (중복 실행 방지)
check(due_events(cfg_test, base_mon, {"start": "2026-10-26"}) == [], "last_fired에 오늘 날짜 있으면 중복 실행 안 됨")

# next_event: now=10:00 이고 start 09:00, end 18:00 → ("end", 오늘 18:00); now=19:00 → ("start", 내일 09:00)
cfg_se = {"start": "09:00", "end": "18:00", "days": [0, 1, 2, 3, 4, 5, 6]}
nxt_10 = next_event(cfg_se, datetime(2026, 10, 26, 10, 0, 0))
check(nxt_10 is not None and nxt_10[0] == "end" and nxt_10[1] == datetime(2026, 10, 26, 18, 0, 0),
      "next_event: 10:00일 때 오늘 18:00 종료 반환")
nxt_19 = next_event(cfg_se, datetime(2026, 10, 26, 19, 0, 0))
check(nxt_19 is not None and nxt_19[0] == "start" and nxt_19[1] == datetime(2026, 10, 27, 9, 0, 0),
      "next_event: 19:00일 때 내일 09:00 시작 반환")

# parse_schedule("깨진 글자") 가 기본값을 돌려주고 days 가 7개
bad_cfg = parse_schedule("깨진 글자")
check(bad_cfg.get("start") == "09:00" and len(bad_cfg.get("days", [])) == 7, "parse_schedule 깨진 글자 기본값 복원")

# ScheduleManager.check 를 가짜 ActionExecutor(monkeypatch)로 실행해, 한 번만 호출되고 같은 분에 다시 check 해도 호출되지 않음
sm = ScheduleManager()
fake_btn = DeckButtonData(id="sched_btn", name="가짜예약", action_type="schedule",
                          action_data='{"start":"09:00","start_type":"program","start_data":"dummy","days":[0,1,2,3,4,5,6]}')
exec_calls = []
orig_execute = ActionExecutor.execute
ActionExecutor.execute = lambda t, d: (exec_calls.append((t, d)), (True, "가짜실행"))[1]
try:
    sm.check({"k1": fake_btn}, now=datetime(2026, 10, 26, 9, 0, 15))
    check(len(exec_calls) == 1, "ScheduleManager.check 첫 번째 호출에서 1회 실행")
    sm.check({"k1": fake_btn}, now=datetime(2026, 10, 26, 9, 0, 45))
    check(len(exec_calls) == 1, "같은 날짜/시각 재검사 시 중복 실행되지 않음")
finally:
    ActionExecutor.execute = orig_execute

# 예약 버튼을 DeckButtonWidget 으로 그려서(grab) 오류 없이 이미지가 나옴
sched_widget_btn = DeckButtonData(id="btn_sched_render", name="출근예약", action_type="schedule",
                                  action_data='{"start":"09:00","end":"18:00","days":[0,1,2,3,4,5,6]}',
                                  span_cols=2, span_rows=1)
sched_widget = DeckButtonWidget(sched_widget_btn, 88, True, "line", parent=w)
sched_widget.set_span(2, 1)
sched_pixmap = sched_widget.grab()
check(not sched_pixmap.isNull() and sched_pixmap.width() > 0 and sched_pixmap.height() > 0,
      "예약 버튼 DeckButtonWidget grab 이미지 생성")
sched_widget.deleteLater()

# 묶음 안의 예약 버튼 검사 및 예약 버튼이 없을 때 w._check_schedules() 검증
orig_exec_for_chk = ActionExecutor.execute
ActionExecutor.execute = lambda t, d: (True, "")
try:
    w._check_schedules()
    check(True, "예약 버튼이 없을 때 w._check_schedules() 오류 없음")

    grp_btn = DeckButtonData(id="btn_grp_test", name="묶음", action_type="group")
    inner_sched = DeckButtonData(id="btn_inner_sched", name="묶음안예약", action_type="schedule",
                                 action_data='{"start":"03:00","start_type":"program","days":[0,1,2,3,4,5,6]}')
    grp_btn.children = {"btn_inner_sched": inner_sched}
    cur_prof = w.current_profile
    cur_prof.buttons["btn_grp_test"] = grp_btn
    w._check_schedules()
    check(True, "묶음 안에 schedule 버튼이 있을 때 w._check_schedules() 오류 없음")
    del cur_prof.buttons["btn_grp_test"]
finally:
    ActionExecutor.execute = orig_exec_for_chk

# 13. 단축키 창 표시 상태에 따른 토글(가려짐 감지) 테스트
from core import win32  # noqa: E402
check(win32.is_visible_on_top(0) is True, "win32.is_visible_on_top(0) == True")
check(win32.bring_to_front(0, True) is False, "win32.bring_to_front(0, True) == False")

orig_is_visible_on_top = win32.is_visible_on_top
try:
    w.show_deck()
    win32.is_visible_on_top = lambda hwnd: True
    w.toggle_visibility()
    check(not w.isVisible(), "맨 앞일 때 toggle_visibility() -> 숨겨짐 (isVisible()==False)")
    w.toggle_visibility()
    check(w.isVisible(), "숨겨진 상태에서 toggle_visibility() -> 보임 (isVisible()==True)")

    win32.is_visible_on_top = lambda hwnd: False
    w.toggle_visibility()
    check(w.isVisible(), "가려져 있을 때 toggle_visibility() -> 숨겨지지 않고 유지 (isVisible()==True)")
finally:
    win32.is_visible_on_top = orig_is_visible_on_top
    w.show_deck()

passed = sum(results)
print(f"\n결과: {passed} / {len(results)} 통과")
import shutil  # noqa: E402
shutil.rmtree(TMP, ignore_errors=True)   # 테스트용 임시 폴더도 남기지 않음
sys.exit(0 if passed == len(results) else 1)
