"""کلیک روی گزینهٔ صدور در منوی بیمه‌های مسئولیت."""
import sys
import time
from pathlib import Path

import pyautogui

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import winbot

APP = "Bime"

winbot.configure(app=APP, click_mode="mouse", pause=0.5)
winbot.wait_for_content("بیمه های مسئولیت", timeout=30)
time.sleep(1)


def menu_state(el_id: str) -> str:
    """وضعیت آیتم منو را از خروجی خام winapp می‌خواند: collapsed / expanded / ?"""
    raw = winbot._winapp(["ui", "inspect", "-a", APP, "--depth", "100"])
    for line in raw.splitlines():
        if el_id in line:
            if "[expanded]" in line:
                return "expanded"
            if "[collapsed]" in line:
                return "collapsed"
    return "?"


el = winbot.find("صدور", role="MenuItem")

if menu_state(el.id) == "expanded":
    print("منوی صدور از قبل باز است.")
else:
    winbot.click("صدور", role="MenuItem")
    time.sleep(1)
    winbot.click("", role="MenuItem")
    print("وضعیت بعد از کلیک:", menu_state(el.id))
