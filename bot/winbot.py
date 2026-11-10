"""
winbot.py - ماژول کمکی برای اتوماسیون برنامهٔ ویندوزی با winapp

استفاده در اسکریپت‌های دیگر:

    import winbot
    winbot.configure(app="Bime")

    winbot.click("btnSubsys", nth=10)                 # دکمهٔ دهم با نام btnSubsys
    winbot.populate_text("متن", "txtName", "replace")  # replace یا append
    winbot.wait_for_content("شرکت سرمد", timeout=20)

نام‌های camelCase هم موجودند: populateText, waitForContent

نیازمندی‌ها (فقط برای populate_text و حالت mouse):
    pip install pyautogui pyperclip
"""

from __future__ import annotations

import re
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

__all__ = [
    "configure", "inspect", "find", "is_visible", "click", "populate_text", "wait_for_content",
    "populateText", "waitForContent", "Element", "ElementNotFound",
]

# ----------------------------------------------------------------- تنظیمات
_cfg = {
    "app": "Bime",
    "depth": "100",
    "click_mode": "invoke",   # "invoke" (winapp) یا "mouse" (کلیک واقعی با pyautogui)
    "pause": 0.3,             # مکث کوتاه بعد از هر عمل (ثانیه)
}


def configure(**kwargs) -> None:
    """مثال: configure(app="Bime", click_mode="mouse", pause=0.5)"""
    for k, v in kwargs.items():
        if k not in _cfg:
            raise KeyError(f"تنظیم ناشناخته: {k}")
        _cfg[k] = v


class ElementNotFound(Exception):
    pass


# ----------------------------------------------------------------- ابزار متن
def _norm(text: str) -> str:
    return " ".join((text or "").replace("ك", "ک").replace("ي", "ی")
                    .replace("\u200c", " ").split())


def _winapp(args: list[str]) -> str:
    r = subprocess.run(
        ["winapp", *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip() or f"winapp {' '.join(args)} failed: {r.returncode}")
    return r.stdout


# ----------------------------------------------------------------- درخت UI
@dataclass
class Element:
    id: str
    role: str
    name: str
    x: Optional[int] = None
    y: Optional[int] = None
    w: Optional[int] = None
    h: Optional[int] = None

    @property
    def center(self):
        if any(value is None for value in (self.x, self.y, self.w, self.h)):
            return None
        return self.x + self.w // 2, self.y + self.h // 2


_START = re.compile(r"^[\s│├└─|`+\\-]*[\w.\-]+\s+[A-Z][A-Za-z]+\b")
_HEAD = re.compile(r"^[\s│├└─|`+\\-]*(?P<id>[\w.\-]+)\s+(?P<role>[A-Z][A-Za-z]+)\b(?P<rest>.*)$", re.S)
_NAME = re.compile(r'"(?P<name>.*)"', re.S)                         # از اولین " تا آخرین "
_RECT = re.compile(r"\((?P<x>-?\d+),\s*(?P<y>-?\d+)[\s,]+(?P<w>-?\d+)\s*[xX×]\s*(?P<h>-?\d+)\)")


def _parse(raw: str) -> list[Element]:
    # خروجی winapp خطوط بلند را می‌شکند؛ خطوط ادامه را به خط قبلی وصل می‌کنیم
    lines: list[str] = []
    for ln in raw.splitlines():
        if not ln.strip():
            continue
        if _START.match(ln) or not lines:
            lines.append(ln)
        else:
            lines[-1] = lines[-1].rstrip() + " " + ln.lstrip(" \t│|").rstrip()
    out = []
    for ln in lines:
        m = _HEAD.match(ln)
        if not m:
            continue
        rest = m.group("rest")
        # مختصات: آخرین (x,y wxh) در خط
        rects = list(_RECT.finditer(rest))
        r = rects[-1] if rects else None
        # نام: متن بین اولین و آخرین " (قبل از مختصات)
        head_part = rest[:r.start()] if r else rest
        nm = _NAME.search(head_part)
        name = nm.group("name") if nm else ""
        out.append(Element(
            m.group("id"), m.group("role"), _norm(name),
            *(int(r.group(k)) if r else None for k in ("x", "y", "w", "h")),
        ))
    return out


def inspect() -> list[Element]:
    """درخت المنت‌های برنامه را می‌گیرد و به لیست Element تبدیل می‌کند."""
    raw = _winapp(["ui", "inspect", "-a", _cfg["app"], "--depth", str(_cfg["depth"])])
    return _parse(raw)


def _shown(e: Element) -> bool:
    """المنت اندازهٔ واقعی دارد (مخفی/collapse نیست)."""
    return e.x is not None and e.y is not None and (e.w or 0) > 0 and (e.h or 0) > 0


def find(element: str, nth: int = 1, role: Optional[str] = None,
         elements: Optional[list[Element]] = None) -> Element:
    """
    المنت را پیدا می‌کند. element می‌تواند باشد:
      - id دقیق (مثل btnSearch یا btn-btnsubsys-f297)
      - نام دقیق (مثل "جستجو" یا "btnSubsys")
      - بخشی از نام
    اگر چند المنت منطبق بود، به ترتیب بالا→پایین و چپ→راست مرتب می‌شوند و nth (از 1) انتخاب می‌کند.
    """
    if nth < 1:
        raise ValueError("nth باید از ۱ شروع شود")
    els = elements if elements is not None else inspect()
    key = _norm(element)
    if role:
        els = [e for e in els if e.role.lower() == role.lower()]

    for test in (
        lambda e: e.id == key,
        lambda e: _norm(e.name) == key,
        lambda e: key in _norm(e.name) or key in e.id,
    ):
        hits = [e for e in els if test(e)]
        if hits:
            shown = [e for e in hits if _shown(e)]
            hits = shown or hits   # قابل‌مشاهده‌ها را ترجیح بده
            hits.sort(key=lambda e: (e.y if e.y is not None else 0, e.x if e.x is not None else 0))
            if nth > len(hits):
                raise ElementNotFound(f"{element!r}: فقط {len(hits)} مورد هست، nth={nth} خارج از محدوده است")
            return hits[nth - 1]
    raise ElementNotFound(f"المنت پیدا نشد: {element!r}")


def is_visible(element: str, elements: Optional[list[Element]] = None, nth: int = 1) -> bool:
    """True اگر دست‌کم یک المنت منطبق با اندازهٔ واقعی (غیر صفر) وجود داشته باشد."""
    try:
        return _shown(find(element, nth, elements=elements))
    except ElementNotFound:
        return False


# ----------------------------------------------------------------- عمل‌ها
def _mouse_click(el: Element) -> None:
    import pyautogui
    c = el.center
    if c is None or not _shown(el):
        raise ElementNotFound(f"{el.id} مختصات قابل کلیک ندارد")
    pyautogui.click(*c)


def click(element: str, nth: int = 1, role: Optional[str] = None) -> Element:
    """روی المنت کلیک می‌کند."""
    el = find(element, nth, role)
    if not _shown(el):
        raise ElementNotFound(f"{element!r} قابل‌مشاهده نیست")
    if _cfg["click_mode"] == "mouse":
        _mouse_click(el)
    else:
        _winapp(["ui", "invoke", el.id, "-a", _cfg["app"]])
    time.sleep(_cfg["pause"])
    return el


def populate_text(text: str, element: str, mode: str = "replace",
                  nth: int = 1, role: Optional[str] = None) -> Element:
    """
    متن را در یک فیلد می‌نویسد.
    mode: "replace" (جایگزین متن قبلی) یا "append" (اضافه به انتهای متن)
    نوشتن از طریق clipboard است تا فارسی درست وارد شود.
    """
    if mode not in ("replace", "append"):
        raise ValueError('mode باید "replace" یا "append" باشد')
    import pyautogui
    import pyperclip

    el = find(element, nth, role)
    _mouse_click(el)            # فوکوس روی فیلد
    time.sleep(_cfg["pause"])
    if mode == "replace":
        pyautogui.hotkey("ctrl", "a")
    else:
        pyautogui.hotkey("ctrl", "End")

    old = pyperclip.paste()
    try:
        pyperclip.copy(text)
        pyautogui.hotkey("ctrl", "v")
        time.sleep(_cfg["pause"])
    finally:
        pyperclip.copy(old)
    return el



def wait_for_content(text: str, timeout: float = 30, interval: float = 0.5) -> bool:
    """
    منتظر می‌ماند تا text در درخت UI برنامه ظاهر شود.
    اگر تا timeout نیامد، TimeoutError می‌دهد.
    نکته: winapp متن‌های خیلی بلند را با … کوتاه می‌کند؛ از بخش ابتدایی متن استفاده کنید.
    """
    key = _norm(text)
    end = time.monotonic() + timeout
    while True:
        raw = _winapp(["ui", "inspect", "-a", _cfg["app"], "--depth", str(_cfg["depth"])])
        # خطوط شکسته را یکی می‌کنیم تا متن بین دو خط گم نشود
        if key in _norm(raw):
            return True
        if time.monotonic() >= end:
            raise TimeoutError(f"متن {text!r} تا {timeout} ثانیه ظاهر نشد")
        time.sleep(interval)


# ----------------------------------------------------------------- نام‌های camelCase
populateText = populate_text
waitForContent = wait_for_content
