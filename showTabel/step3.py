"""صدور ← مسئولیت حمل و نقل ← بیمه نامه مسئولیت شرکت های حمل و نقل بین المللی (CMR)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import winbot

APP = "Bime"
# بخشی از نام که یکتاست (winapp متن بلند را کوتاه می‌کند و ي/ك نرمال می‌شود)
TARGET = "مسئولیت شرکت های حمل"

winbot.configure(app=APP, click_mode="mouse", pause=0.5)
winbot.wait_for_content("بیمه های مسئولیت", timeout=30)
time.sleep(1)


def visible(name: str) -> bool:
    try:
        return winbot.is_visible(name)
    except winbot.ElementNotFound:
        return False


def open_if_hidden(parent: str, child: str) -> None:
    
    if visible(child):
        return
    el = winbot.find(parent, role="MenuItem")
    winbot.click(el.id)
    for _ in range(10):
        time.sleep(0.5)
        if visible(child):
            return
    raise SystemExit(f"{child!r} بعد از باز کردن {parent!r} دیده نشد")


open_if_hidden("صدور", "مسئولیت حمل و نقل")
open_if_hidden("مسئولیت حمل و نقل", TARGET)

winbot.click(TARGET)
print("کلیک شد روی بیمه نامه مسئولیت شرکت های حمل و نقل بین المللی")