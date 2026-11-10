r"""تشخیص این‌که محتوای فرم Bime (المنت automationId=bime) چه فناوری‌ای است.

اجرا (فرم CMR باز و روی صفحه باشد):
    python .\made_elhaghie\probe_host.py
    python .\made_elhaghie\probe_host.py --no-sr      # بدون تست پرچم screen reader
    python .\made_elhaghie\probe_host.py --hwnd 2360974

خروجی: probe_out.txt کنار اجرا (همان چاپ‌شده در ترمینال).
نکته: تست دوم پرچم screen reader ویندوز را چند ثانیه روشن می‌کند و بعد خاموش (فقط اگر قبلاً خاموش بود).
"""
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes as wt
from pathlib import Path

user32 = ctypes.windll.user32
WNDENUMPROC = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [WNDENUMPROC, wt.LPARAM]
user32.EnumChildWindows.argtypes = [wt.HWND, WNDENUMPROC, wt.LPARAM]
user32.GetParent.argtypes = [wt.HWND]
user32.GetParent.restype = wt.HWND
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]

SPI_GETSCREENREADER, SPI_SETSCREENREADER, SPIF_SENDCHANGE = 0x0046, 0x0047, 2
LINES: list[str] = []


def out(s=""):
    print(s)
    LINES.append(s)


def norm(t):
    return t.replace("ي", "ی").replace("ك", "ک")


def cls(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(h, b, 256)
    return b.value


def txt(h):
    b = ctypes.create_unicode_buffer(256)
    user32.GetWindowTextW(h, b, 256)
    return b.value


def rect(h):
    r = wt.RECT()
    user32.GetWindowRect(h, ctypes.byref(r))
    return f"({r.left},{r.top},{r.right - r.left}x{r.bottom - r.top})"


def pid(h):
    p = wt.DWORD()
    user32.GetWindowThreadProcessId(h, ctypes.byref(p))
    return p.value


def top_windows():
    res = []

    @WNDENUMPROC
    def cb(h, _):
        res.append(h)
        return True
    user32.EnumWindows(cb, 0)
    return res


def find_main(arg_hwnd):
    if arg_hwnd:
        return arg_hwnd
    for h in top_windows():
        t = norm(txt(h))
        if "سرمد" in t or "(CMR)" in t:
            return h
    return None


def depth_of(h, root):
    d = 0
    while h and h != root:
        h = user32.GetParent(h)
        d += 1
        if d > 50:
            break
    return d


def children(root):
    res = []

    @WNDENUMPROC
    def cb(h, _):
        res.append(h)
        return True
    user32.EnumChildWindows(root, cb, 0)
    return res


def winapp_inspect():
    r = subprocess.run(["winapp", "ui", "inspect", "-a", "Bime", "--depth", "100", "--json"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode != 0 or not r.stdout.strip():
        return None, r.stderr.strip()[:300]
    try:
        d = json.loads(r.stdout)
    except json.JSONDecodeError as ex:
        return None, f"json: {ex}"
    w = d.get("windows", [{}])[0]
    return w.get("elementCount"), "تراکنش" in norm(r.stdout)


def main():
    arg = None
    if "--hwnd" in sys.argv:
        arg = int(sys.argv[sys.argv.index("--hwnd") + 1])
    hw = find_main(arg)
    if not hw:
        out("پنجرهٔ اصلی Bime پیدا نشد.")
        return 1
    p = pid(hw)
    out(f"main HWND={hw} PID={p} class={cls(hw)!r} rect={rect(hw)}")

    out("\n== HWND های فرزند (کلاس‌ها فناوری میزبان را نشان می‌دهند) ==")
    kids = children(hw)
    if not kids:
        out("هیچ HWND فرزندی نیست (کنترل‌ها احتمالاً بدون HWND و رندر شده‌اند: WPF/Skia/…).")
    for h in kids:
        out(f"{'  ' * depth_of(h, hw)}HWND={h} class={cls(h)!r} vis={bool(user32.IsWindowVisible(h))} "
            f"rect={rect(h)} text={txt(h)[:40]!r}")

    out("\n== سایر پنجره‌های سطح‌بالای همین پروسه ==")
    for h in top_windows():
        if h != hw and pid(h) == p:
            out(f"HWND={h} class={cls(h)!r} vis={bool(user32.IsWindowVisible(h))} rect={rect(h)} text={txt(h)[:40]!r}")

    out("\n== درخت UIA فعلی ==")
    out(f"elementCount, 'تراکنش' دیده شد؟ = {winapp_inspect()}")

    if "--no-sr" not in sys.argv:
        cur = wt.BOOL()
        user32.SystemParametersInfoW(SPI_GETSCREENREADER, 0, ctypes.byref(cur), 0)
        out(f"\n== تست پرچم screen reader (قبلاً: {bool(cur.value)}) ==")
        user32.SystemParametersInfoW(SPI_SETSCREENREADER, 1, None, SPIF_SENDCHANGE)
        try:
            for wait in (3, 5):
                time.sleep(wait)
                out(f"بعد از {wait}s: elementCount, 'تراکنش'؟ = {winapp_inspect()}")
        finally:
            if not cur.value:
                user32.SystemParametersInfoW(SPI_SETSCREENREADER, 0, None, SPIF_SENDCHANGE)
                out("پرچم screen reader به حالت قبل (خاموش) برگشت.")

    Path("probe_out.txt").write_text("\n".join(LINES), encoding="utf-8")
    print("\nذخیره شد: probe_out.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())