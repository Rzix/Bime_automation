"""صدور ← مسئولیت حمل و نقل ← بیمه نامه مسئولیت شرکت های حمل و نقل بین المللی (CMR).
بعد از کلیک، منتظر یکی از فرم‌ها می‌ماند و وقتی ظاهر شد F5 را می‌زند."""
import sys
import time
from pathlib import Path

import pyautogui

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import winbot

APP = "Bime"
TARGET = "مسئولیت شرکت های حمل"

# هر کدام از این متن‌ها که در درخت UI ظاهر شود، کافی است
EXPECTED = [
    "بیمه نامه مسئولیت شرکت های حمل",
    "بیمه نامه مسئولیت متصدیان حمل و نقل",
    "برای نمایش اطلاعات، جستجو کنید",
]

winbot.configure(app=APP, click_mode="mouse", pause=0.5)
winbot.wait_for_content("بیمه های مسئولیت", timeout=30)
time.sleep(1)


def visible(name: str) -> bool:
    try:
        return winbot.is_visible(name)
    except winbot.ElementNotFound:
        return False


def open_if_hidden(parent: str, child: str) -> None:
    """parent را فقط وقتی باز می‌کند که child دیده نمی‌شود (تا بسته نشود)."""
    if visible(child):
        return
    el = winbot.find(parent, role="MenuItem")
    winbot.click(el.id)
    for _ in range(10):
        time.sleep(0.5)
        if visible(child):
            return
    raise SystemExit(f"{child!r} بعد از باز کردن {parent!r} دیده نشد")


def wait_any(texts: list[str], timeout: float = 60, interval: float = 0.5) -> str:
    """منتظر می‌ماند تا یکی از texts در درخت UI ظاهر شود و همان متن را برمی‌گرداند."""
    keys = {t: " ".join(winbot._norm(t).split()) for t in texts}
    end = time.monotonic() + timeout
    while True:
        raw = winbot._winapp(["ui", "inspect", "-a", APP, "--depth", "100"])
        flat = " ".join(winbot._norm(raw).split())
        for t, k in keys.items():
            if k in flat:
                return t
        if time.monotonic() >= end:
            raise TimeoutError(f"هیچ‌کدام از {texts} تا {timeout} ثانیه ظاهر نشد")
        time.sleep(interval)


open_if_hidden("صدور", "مسئولیت حمل و نقل")
open_if_hidden("مسئولیت حمل و نقل", TARGET)

winbot.click(TARGET)
print("کلیک شد روی بیمه نامه مسئولیت شرکت های حمل و نقل بین المللی")

found = wait_any(EXPECTED, timeout=60)
print("فرم ظاهر شد:", found)

pyautogui.press("f5")
print("F5 زده شد")