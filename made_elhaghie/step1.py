r"""کلیک روی دکمه‌های گروه «تراکنش» با تشخیص تصویر: الحاقیه | تمدید | کپی

فرم Bime در درخت UI Automation نیست (winapp دکمه را نمی‌بیند)، پس دکمه با تصویر پیدا می‌شود.

اجرا:
    python .\made_elhaghie\click_transaction.py                 # ایجاد الحاقیه/تراکنش
    python .\made_elhaghie\click_transaction.py تمدید
    python .\made_elhaghie\click_transaction.py کپی
    python .\made_elhaghie\click_transaction.py --regrab        # گرفتن دوبارهٔ تصویر دکمه
    python .\made_elhaghie\click_transaction.py --debug         # ذخیرهٔ screen_debug.png
بار اول (یا وقتی تصویر دکمه نیست) از شما می‌خواهد دو گوشهٔ دکمه را با موس نشان بدهید.
نیاز: pip install pyautogui pillow opencv-python
"""
import sys
import time
from pathlib import Path

import pyautogui

DIR = Path(__file__).resolve().parent
IMG = DIR / "img"
BUTTONS = {"الحاقیه": "الحاقیه", "تمدید": "تمدید", "کپی": "کپی"}
WAIT = 15          # حداکثر انتظار برای پیدا شدن دکمه (ثانیه)
CONF = 0.8


def grab(name: str, path: Path) -> bool:
    IMG.mkdir(exist_ok=True)
    print(f"فرم باز و دکمهٔ «{name}» روی صفحه دیده شود.")
    input("موس را روی گوشهٔ بالا-چپ دکمه ببرید و Enter بزنید: ")
    x1, y1 = pyautogui.position()
    input("موس را روی گوشهٔ پایین-راست دکمه ببرید و Enter بزنید: ")
    x2, y2 = pyautogui.position()
    if x2 <= x1 or y2 <= y1:
        print("مختصات نامعتبر؛ اول بالا-چپ، بعد پایین-راست.", file=sys.stderr)
        return False
    pyautogui.screenshot(region=(x1, y1, x2 - x1, y2 - y1)).save(path)
    print(f"ذخیره شد: {path} ({x2 - x1}x{y2 - y1})")
    return True


def locate(path: Path):
    try:
        return pyautogui.locateCenterOnScreen(str(path), confidence=CONF)
    except pyautogui.ImageNotFoundException:
        return None
    except TypeError:                      # OpenCV نصب نیست
        try:
            return pyautogui.locateCenterOnScreen(str(path))
        except pyautogui.ImageNotFoundException:
            return None


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    name = BUTTONS.get(args[0] if args else "الحاقیه")
    if name is None:
        print(f"نام نامعتبر؛ یکی از {list(BUTTONS)}", file=sys.stderr)
        return 1

    path = IMG / f"{name}.png"
    if "--regrab" in sys.argv or not path.exists():
        if not grab(name, path):
            return 1

    deadline = time.monotonic() + WAIT
    pos = None
    while True:
        pos = locate(path)
        if pos or time.monotonic() >= deadline:
            break
        time.sleep(0.5)

    if "--debug" in sys.argv or not pos:
        shot = DIR / "screen_debug.png"
        pyautogui.screenshot().save(shot)
        print(f"اسکرین‌شات: {shot} | اندازهٔ صفحه: {pyautogui.size()}", file=sys.stderr)
    if not pos:
        print(f"پیدا نشد: {name} (تا {WAIT} ثانیه). اگر اندازه/تم عوض شده: --regrab",
              file=sys.stderr)
        return 1

    pyautogui.click(pos.x, pos.y)
    print(f"کلیک شد: {name} در ({pos.x}, {pos.y})")
    return 0


if __name__ == "__main__":
    sys.exit(main())