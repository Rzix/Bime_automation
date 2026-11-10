"""صدور ← مسئولیت حمل و نقل در منوی بیمه‌های مسئولیت."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import winbot

APP = "Bime"
TARGET = "مسئولیت حمل و نقل"

winbot.configure(app=APP, click_mode="mouse", pause=0.5)
winbot.wait_for_content("بیمه های مسئولیت", timeout=30)
time.sleep(1)


def menu_state(el_id: str) -> str:
    raw = winbot._winapp(["ui", "inspect", "-a", APP, "--depth", "100"])
    for line in raw.splitlines():
        if el_id in line:
            if "[expanded]" in line:
                return "expanded"
            if "[collapsed]" in line:
                return "collapsed"
    return "?"


def target_visible() -> bool:
    try:
        return winbot.is_visible(TARGET)
    except winbot.ElementNotFound:
        return False


issue = winbot.find("صدور", role="MenuItem")


if not target_visible():
    winbot.click(issue.id)
    for _ in range(10):
        time.sleep(0.5)
        if target_visible():
            break
    print("وضعیت صدور:", menu_state(issue.id))

if not target_visible():
    raise SystemExit(f"{TARGET!r} بعد از باز کردن صدور دیده نشد")

winbot.click(TARGET)
print("کلیک شد روی:", TARGET)