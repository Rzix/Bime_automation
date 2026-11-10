"""اجرای ترتیبی چند اسکریپت پایتون.

اجرای ساده (لیست داخل همین فایل):
    python run_all.py
"""
import argparse
import subprocess
import sys
import time
from pathlib import Path

# ---------------- لیست اسکریپت‌ها به ترتیب اجرا ----------------
SCRIPTS = [
    # "run.py",
    "showTabel/step1.py",
    "showTabel/step2.py",
    "showTabel/step3.py",
]
DELAY = 1.0          # مکث بین اسکریپت‌ها (ثانیه)
STOP_ON_ERROR = True # اگر False باشد، با خطا هم ادامه می‌دهد
# ----------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description="اجرای ترتیبی اسکریپت‌ها")
    ap.add_argument("scripts", nargs="*", help="اگر بدهید، جای لیست داخلی را می‌گیرد")
    ap.add_argument("--continue", dest="keep_going", action="store_true",
                    help="با خطا هم ادامه بده")
    args = ap.parse_args()

    scripts = args.scripts or SCRIPTS
    stop_on_error = STOP_ON_ERROR and not args.keep_going
    if not scripts:
        print("لیست اسکریپت خالی است.")
        return 2

    base = Path(__file__).resolve().parent
    paths = []
    for s in scripts:
        p = Path(s) if Path(s).is_absolute() else base / s
        if not p.exists():
            print(f"✘ فایل پیدا نشد: {p}")
            return 2
        paths.append(p)

    results = []
    for i, p in enumerate(paths, 1):
        print(f"\n===== [{i}/{len(paths)}] {p.name} =====", flush=True)
        t0 = time.monotonic()
        code = subprocess.run([sys.executable, str(p)], cwd=p.parent).returncode
        dt = time.monotonic() - t0
        results.append((p.name, code, dt))

        if code == 0:
            print(f"✔ {p.name} تمام شد ({dt:.1f}s)")
        else:
            print(f"✘ {p.name} با کد {code} تمام شد")
            if stop_on_error:
                print("توقف به‌خاطر خطا.")
                break
        if i < len(paths):
            time.sleep(DELAY)

    print("\n----- خلاصه -----")
    for name, code, dt in results:
        print(f"{'✔' if code == 0 else '✘'} {name:30} {dt:6.1f}s")
    return 0 if len(results) == len(paths) and all(c == 0 for _, c, _ in results) else 1


if __name__ == "__main__":
    sys.exit(main())
