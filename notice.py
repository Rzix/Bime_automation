"""
بستن خودکار اعلامیهٔ «آگهی» (هشدار بیمه‌نامه‌هایی که مهلت بازدیدشان سپری شده).

استفاده در هر اسکریپت:
    from bot import winbot, notice
    notice.install()          # از این به بعد قبل از هر click / populate_text چک و بسته می‌شود

یا دستی بین مراحل:
    notice.dismiss()          # True اگر اعلامیه بود و بسته شد

اجرای مستقل برای تست (اعلامیه باید باز باشد):
    python .\\bot\\notice.py
    python .\\bot\\notice.py --watch     # هر ۲ ثانیه چک می‌کند تا Ctrl+C
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import winbot

TITLE = "آگهی"
MARKERS = ("هشدار بیمه نامه", "مهلت بازدید", "کد رایانه مربوط به بیمه نامه")
EXIT_BTN = "خروج"


def _find_notice(els):
    """عنصر عنوان «آگهی» را برمی‌گرداند؛ اگر نبود None."""
    for e in els:
        if winbot._shown(e) and e.name.strip() == winbot._norm(TITLE):
            return e
    # اگر عنوان جدا نبود، از متن پیام تشخیص بده
    for e in els:
        if winbot._shown(e) and any(winbot._norm(m) in e.name for m in MARKERS):
            return e
    return None


def _close_button(els, anchor):
    """دکمهٔ ضربدر: دکمه‌ای هم‌ردیف نوار عنوان و سمت چپ آن. در غیر این صورت دکمهٔ «خروج»."""
    # نوار عنوان: عنصر عنوان اگر خودش «آگهی» باشد
    if anchor.name.strip() == winbot._norm(TITLE):
        band = [
            e for e in els
            if e.role == "Button" and winbot._shown(e) and e.id != anchor.id
            and abs(e.center[1] - anchor.center[1]) <= max(anchor.h, 30)
            and e.center[0] < anchor.center[0]
        ]
        if band:
            return min(band, key=lambda e: e.center[0])      # چپ‌ترین دکمه = ×
    # fallback: دکمهٔ «خروج» داخل اعلامیه (نه btnCloseApp که برنامه را می‌بندد)
    for e in els:
        if (e.role == "Button" and winbot._shown(e) and e.id != "btnCloseApp"
                and e.name.strip() == winbot._norm(EXIT_BTN)):
            return e
    return None


def dismiss(elements=None, verbose=True) -> bool:
    """اگر اعلامیه باز بود می‌بندد و True برمی‌گرداند."""
    els = elements if elements is not None else winbot.inspect()
    anchor = _find_notice(els)
    if anchor is None:
        return False
    btn = _close_button(els, anchor)
    if btn is None:
        if verbose:
            print("[notice] اعلامیه هست ولی دکمهٔ بستن پیدا نشد", file=sys.stderr)
        return False
    if verbose:
        print(f"[notice] اعلامیه پیدا شد؛ بستن با {btn.id} {btn.name!r}", file=sys.stderr)
    # با id دقیق کلیک می‌کنیم (find اول id را تطبیق می‌دهد)
    winbot.click(btn.id)
    time.sleep(0.5)
    return True


def install() -> None:
    """click / populate_text / wait_for_content در winbot را طوری می‌پیچد که قبل از اجرا اعلامیه بسته شود."""
    if getattr(winbot, "_notice_installed", False):
        return
    busy = {"v": False}

    def wrap(fn):
        def inner(*a, **k):
            if not busy["v"]:
                busy["v"] = True
                try:
                    while dismiss():        # ممکن است چند اعلامیه پشت سر هم باشد
                        pass
                except Exception as ex:      # چک اعلامیه نباید مرحلهٔ اصلی را خراب کند
                    print(f"[notice] چک ناموفق: {ex}", file=sys.stderr)
                finally:
                    busy["v"] = False
            return fn(*a, **k)
        inner.__name__ = fn.__name__
        return inner

    winbot.click = wrap(winbot.click)
    winbot.populate_text = winbot.populateText = wrap(winbot.populate_text)
    winbot._notice_installed = True


if __name__ == "__main__":
    winbot.configure(app="Bime")
    if "--watch" in sys.argv:
        try:
            while True:
                dismiss()
                time.sleep(2)
        except KeyboardInterrupt:
            pass
    else:
        print("بسته شد" if dismiss() else "اعلامیه‌ای پیدا نشد")
