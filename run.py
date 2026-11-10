import os
import re
import subprocess
import sys
import time
import traceback
from pathlib import Path

from pywinauto import Desktop, mouse
from pywinauto.application import Application
from pywinauto.findwindows import ElementAmbiguousError
from pywinauto.keyboard import send_keys

# USERNAME = "H.Azizi"
USERNAME = "F.Sayare"

# PASSWORD = os.environ.get("BIME_PASSWORD","Ha@26652665")
PASSWORD = os.environ.get("BIME_PASSWORD","Fs@26652665")

SUBMIT_TITLE = "ورود"                                   # دکمهٔ «ورود» (مراحل ۱ تا ۳)
# \W* = هر فاصله/نویسهٔ نامرئی (ZWNJ, RLM, ...) را نادیده می‌گیرد
PASSWORD_LABEL_RE = r"^\W*رمز\W*عبور\W*$"               # برچسب «رمزعبور»
PASSWORD_PAGE_BUTTON_RE = r"^\W*دریافت\W+کد\W+ورود\W*$"  # فقط در صفحهٔ رمز وجود دارد

POLL_INTERVAL = 0.1
SHORT_CHECK = 0.1
PROBE_TIMEOUT = 0.5         # برای تشخیص صفحه (درخت UI برنامه سنگین است)

MAX_ATTEMPTS = 1            # فقط یک بار لاگین؛ بدون تلاش مجدد
RETRY_DELAY = 1.0           # مکث بین تلاش‌ها (ثانیه)
WARNING_WAIT_SECONDS = 15   # بعد از مرحلهٔ ۳ تا این مدت منتظر هشدار «OK» می‌ماند

ERROR_TITLE_RE = r"^خطا.*"                              # عنوان دیالوگ: «خطا(۱)»
ERROR_BUTTON_RE = r".*ارسال به پیغام.*"                  # دکمهٔ «ارسال به پیغام کاربران»
ERROR_TEXT_RE = r".*(CreateHubProxy|Bad Request).*"     # متن پیام خطا


class AppErrorDialog(Exception):
    """دیالوگ خطای خود برنامه (مثل CreateHubProxy 400) دیده شد"""


# ----------------------------------------------------------------------------
# ابزارهای عمومی
# ----------------------------------------------------------------------------

def wait_until(condition, timeout: float, interval: float = POLL_INTERVAL):
    end = time.time() + timeout
    while time.time() < end:
        try:
            result = condition()
        except Exception:
            result = None
        if result:
            return result
        time.sleep(interval)
    return None


def retry(func, attempts: int = 5, delay: float = 0.3, on_error=None):
    """عملیات UIA را در صورت خطای موقت دوباره امتحان می‌کند.
    on_error بعد از هر شکست صدا زده می‌شود (مثلاً برای تشخیص دیالوگ خطا)"""
    last = None
    for _ in range(attempts):
        try:
            return func()
        except AppErrorDialog:
            raise
        except Exception as e:
            last = e
            if on_error:
                on_error()
            time.sleep(delay)
    raise last


def escape_keys(text: str) -> str:
    special = {"{": "{{}", "}": "{}}", "(": "{(}", ")": "{)}",
               "+": "{+}", "^": "{^}", "%": "{%}", "~": "{~}"}
    return "".join(special.get(ch, ch) for ch in text)


def _spec_exists(make_spec, timeout: float = SHORT_CHECK) -> bool:
    try:
        return make_spec().exists(timeout=timeout)
    except ElementAmbiguousError:
        return True   # چند تطابق = وجود دارد
    except Exception:
        return False


# ----------------------------------------------------------------------------
# اجرا و اتصال به برنامه
# ----------------------------------------------------------------------------

def get_app_path(executable_name: str = "Bime.exe") -> Path:
    """
    مسیر فایل اجرایی را پیدا می‌کند.
    چون اسکریپت داخل پوشهٔ script است و Bime.exe در پوشهٔ اصلی پروژه قرار دارد،
    پوشه‌ها را از محل خود اسکریپت به سمت بالا می‌گردیم (مستقل از عمق فایل).
    همچنین امکان ست کردن متغیر محیطی BIME_APP_PATH وجود دارد.
    """
    # بررسی متغیر محیطی در صورت نیاز به تعیین مسیر مطلق از بیرون
    env_path = os.environ.get("BIME_APP_PATH")
    if env_path:
        app_path = Path(env_path)
        if not app_path.is_file():
            raise FileNotFoundError(f"Application not found at resolved path: {app_path}")
        return app_path

    # از پوشهٔ خود اسکریپت شروع می‌کنیم و تا ریشهٔ درایو بالا می‌رویم
    start_dir = Path(__file__).resolve().parent
    for folder in (start_dir, *start_dir.parents):
        candidate = folder / executable_name
        if candidate.is_file():
            return candidate

    raise FileNotFoundError(
        f"Application not found at resolved path: searched '{executable_name}' "
        f"upwards from {start_dir}. Set BIME_APP_PATH to override."
    )


def close_existing_application(executable_name: str = "Bime.exe") -> None:
    result = subprocess.run(
        ["taskkill", "/F", "/IM", executable_name, "/T"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode == 0:
        print(f"Closed existing {executable_name} process.")
        time.sleep(1)


def launch_application(app_path: Path) -> subprocess.Popen:
    try:
        # cwd باید پوشه‌ای باشد که Bime.exe در آن قرار دارد تا فایل‌های کانفیگ و دیتابیس (مثل BimeCache.db) را پیدا کند
        working_dir = app_path.parent
        return subprocess.Popen([str(app_path)], cwd=str(working_dir))
    except OSError as error:
        raise RuntimeError(f"Failed to launch {app_path.name}: {error}") from error


def find_main_window(pid: int, app_path: Path, require_edit: bool = True):
    """پنجرهٔ اصلی را تازه پیدا می‌کند و WindowSpecification برمی‌گرداند"""
    for kwargs in ({"process": pid}, {"path": str(app_path)}):
        try:
            app = Application(backend="uia").connect(**kwargs)
            best, best_area = None, -1
            for w in app.windows():
                try:
                    if not w.is_visible():
                        continue
                    if require_edit:
                        if w.descendants(control_type="Edit"):
                            return Desktop(backend="uia").window(handle=w.handle)
                        continue
                    r = w.rectangle()
                    area = r.width() * r.height()
                    if area > best_area:
                        best, best_area = w, area
                except Exception:
                    continue
            if best is not None:
                return Desktop(backend="uia").window(handle=best.handle)
        except Exception:
            pass
    return None


class LiveWindow:
    """پروکسی روی پنجرهٔ اصلی؛ spec را cache می‌کند و در صورت کهنه شدن handle دوباره پیدا می‌کند"""

    def __init__(self, pid: int, app_path: Path, spec):
        self.pid = pid
        self._path = app_path
        self._spec = spec

    def _is_alive(self) -> bool:
        try:
            return self._spec.exists(timeout=0.2)
        except Exception:
            return False

    def _resolve(self):
        if self._is_alive():
            return self._spec
        spec = wait_until(
            lambda: find_main_window(self.pid, self._path, require_edit=False),
            timeout=5, interval=0.2,
        )
        if spec is None:
            raise RuntimeError("Main window not found.")
        self._spec = spec
        return spec

    def __getattr__(self, name):
        return getattr(self._resolve(), name)


def connect_and_focus_window(process_pid: int, app_path: Path, timeout: int = 30) -> LiveWindow:
    spec = wait_until(lambda: find_main_window(process_pid, app_path),
                      timeout, interval=0.3)
    if spec is None:
        raise RuntimeError(f"Timeout: Application UI did not become ready within {timeout} seconds.")

    try:
        spec.set_focus()
    except Exception:
        pass
    time.sleep(0.3)
    return LiveWindow(process_pid, app_path, spec)


# ----------------------------------------------------------------------------
# عیب‌یابی، خطا و هشدار
# ----------------------------------------------------------------------------

def dump_controls(window, limit: int = 80) -> None:
    """برای عیب‌یابی: نوع و نام واقعی کنترل‌ها را چاپ می‌کند.
    repr نویسه‌های نامرئی (مثل \\u200c یا \\u200f) را آشکار می‌کند."""
    print("---- UI controls dump ----")
    try:
        items = window.wrapper_object().descendants()
    except Exception as e:
        print(f"(dump failed: {e})")
        return
    for i, c in enumerate(items[:limit]):
        try:
            info = c.element_info
            print(f"{i:3d} {info.control_type:<10} {info.name!r}")
        except Exception:
            continue
    if len(items) > limit:
        print(f"... ({len(items) - limit} more)")
    print("---- end dump ----")


def check_error_dialog(window) -> None:
    """اگر دیالوگ «خطا» باز باشد AppErrorDialog پرتاب می‌کند"""
    desk = Desktop(backend="uia")
    probes = [
        # پنجرهٔ سطح‌بالای همین پردازش
        lambda: desk.window(process=window.pid, title_re=ERROR_TITLE_RE),
        # پنجرهٔ سطح‌بالا در هر پردازشی
        lambda: desk.window(title_re=ERROR_TITLE_RE),
        # المان‌هایی درون پنجرهٔ اصلی
        lambda: window.child_window(title_re=ERROR_TITLE_RE),
        lambda: window.child_window(title_re=ERROR_BUTTON_RE, control_type="Button"),
        lambda: window.child_window(title_re=ERROR_TEXT_RE),
    ]
    for probe in probes:
        if _spec_exists(probe):
            raise AppErrorDialog("Application error dialog detected (خطا).")


def dismiss_warning_if_present(window) -> bool:
    """اگر پنجرهٔ هشدار با OK باز باشد می‌بندد؛ وگرنه فوراً برمی‌گردد"""
    try:
        ok_spec = window.child_window(title="OK", control_type="Button")
        if not ok_spec.exists(timeout=SHORT_CHECK):
            return False
        btn = ok_spec.wrapper_object()
        print("Warning dialog found; clicking OK.")
        try:
            btn.invoke()
        except Exception:
            btn.click_input()
        return True
    except Exception:
        return False


def wait_for_element(window, timeout: float = 15, **criteria):
    """منتظر ظاهر شدن المان می‌ماند و در همین حین هشدار/خطا را بررسی می‌کند"""
    end = time.time() + timeout
    while time.time() < end:
        check_error_dialog(window)
        dismiss_warning_if_present(window)
        try:
            target = window.child_window(**criteria)
            if target.exists(timeout=SHORT_CHECK):
                return target
        except Exception:
            pass
        time.sleep(POLL_INTERVAL)
    check_error_dialog(window)
    raise TimeoutError(f"Element not found within {timeout}s: {criteria}")


def wait_for_warning_then_finish(window, timeout: float = WARNING_WAIT_SECONDS) -> bool:
    """منتظر هشدار «OK» می‌ماند؛ با دیدن و بستن آن True برمی‌گرداند، وگرنه بعد از timeout False"""
    end = time.time() + timeout
    while time.time() < end:
        if dismiss_warning_if_present(window):
            return True
        time.sleep(POLL_INTERVAL)
    return False


# ----------------------------------------------------------------------------
# تشخیص صفحه‌ها
# ----------------------------------------------------------------------------

def is_password_step(window) -> bool:
    """صفحهٔ رمز عبور را با دو نشانه تشخیص می‌دهد:
    برچسب «رمزعبور» یا دکمهٔ «دریافت کد ورود» (در صفحهٔ نام کاربری وجود ندارد)"""
    probes = [
        lambda: window.child_window(title_re=PASSWORD_LABEL_RE),
        lambda: window.child_window(title_re=PASSWORD_PAGE_BUTTON_RE, control_type="Button"),
    ]
    return any(_spec_exists(p, timeout=PROBE_TIMEOUT) for p in probes)


def wait_for_password_step(window, timeout: float = 10) -> bool:
    """True برمی‌گرداند اگر صفحهٔ رمز عبور ظاهر شود؛ وگرنه False"""
    end = time.time() + timeout
    while time.time() < end:
        check_error_dialog(window)
        dismiss_warning_if_present(window)
        if is_password_step(window):
            time.sleep(0.3)
            return True
        time.sleep(POLL_INTERVAL)
    check_error_dialog(window)
    return False


# ----------------------------------------------------------------------------
# ورودی‌ها و دکمه‌ها
# ----------------------------------------------------------------------------

def release_input_focus(window, input_field) -> None:
    """برداشتن فوکوس از input تا برنامه مقدار را commit کند"""
    try:
        send_keys("{TAB}")
        time.sleep(0.15)
        if not input_field.has_keyboard_focus():
            return
    except Exception:
        return

    try:
        rect = window.rectangle()
        mouse.click(button="left", coords=(rect.mid_point().x, rect.top + 10))
        time.sleep(0.15)
    except Exception:
        pass


def clear_and_fill_input(window, text_to_type: str, edit_index: int = 0, timeout: int = 10) -> None:
    """فیلد Edit را پاک و سپس متن را تایپ می‌کند (برای نام کاربری و رمز عبور)"""
    on_error = lambda: check_error_dialog(window)

    def get_field():
        f = window.child_window(control_type="Edit", found_index=edit_index)
        f.wait("visible enabled", timeout=timeout)
        return f.wrapper_object()

    input_field = retry(get_field, on_error=on_error)

    retry(lambda: input_field.click_input(), on_error=on_error)
    retry(lambda: input_field.type_keys("^a{BACKSPACE}", with_spaces=True), on_error=on_error)
    retry(lambda: input_field.type_keys(escape_keys(text_to_type),
                                        with_spaces=True, pause=0.03),
          on_error=on_error)

    release_input_focus(window, input_field)


def check_checkbox(window, title_re: str = r"^زیر سیستم.*", timeout: int = 10) -> None:
    """تیک زدن چک‌باکس؛ اگر از قبل تیک خورده باشد کلیک نمی‌شود"""
    def get_cb():
        cb = window.child_window(title_re=title_re, control_type="CheckBox")
        cb.wait("visible enabled", timeout=timeout)
        return cb.wrapper_object()

    checkbox = retry(get_cb, on_error=lambda: check_error_dialog(window))

    try:
        if checkbox.get_toggle_state() == 1:
            print("Checkbox is already checked.")
            return
    except Exception:
        pass

    try:
        checkbox.toggle()
    except Exception as e:
        print(f"toggle failed: {e}. Trying click_input()...")
        checkbox.click_input()
    time.sleep(0.1)


def click_submit_button(window, title: str = SUBMIT_TITLE, timeout: int = 10) -> None:
    """دکمهٔ «ورود» را با تطبیق دقیق عنوان پیدا و کلیک می‌کند.
    ترتیب: کلیک واقعی موس ← invoke ← کلیک مختصاتی (دکمهٔ «دریافت کد ورود» انتخاب نمی‌شود)"""
    def get_btn():
        spec = window.child_window(title=title, control_type="Button")
        try:
            spec.wait("visible enabled", timeout=timeout)
        except Exception:
            print("Warning: button not reported enabled; trying anyway.")
        return spec.wrapper_object()

    btn = retry(get_btn, on_error=lambda: check_error_dialog(window))

    try:
        btn.click_input()
        return
    except Exception:
        pass

    try:
        btn.invoke()
        return
    except Exception:
        pass

    center = btn.rectangle().mid_point()
    mouse.click(button="left", coords=(center.x, center.y))


def fill_password(window, password: str) -> None:
    """رمز را در فیلد Edit صفحهٔ رمز عبور وارد می‌کند (تنها Edit این صفحه)"""
    clear_and_fill_input(window, password, edit_index=0)


# ----------------------------------------------------------------------------
# جریان اصلی
# ----------------------------------------------------------------------------

def run_once(app_path: Path) -> None:
    """یک دور کامل: بستن برنامه، اجرای مجدد و طی کردن سه مرحله"""
    close_existing_application("Bime.exe")

    process = launch_application(app_path)
    window = connect_and_focus_window(process.pid, app_path)
    print("Bime.exe is running and focused.")

    # مرحله ۱: نام کاربری و دکمهٔ ورود
    clear_and_fill_input(window, USERNAME)
    click_submit_button(window)
    print("Step 1 submitted.")

    # اگر صفحهٔ رمز ظاهر نشد، یک بار دیگر دکمه را می‌زنیم
    if not wait_for_password_step(window, timeout=8):
        print("Password step not visible yet; clicking submit again.")
        click_submit_button(window)
        if not wait_for_password_step(window, timeout=10):
            dump_controls(window)   # برای دیدن نام واقعی کنترل‌ها
            raise TimeoutError("Password step (رمزعبور) did not appear.")
    print("Password step detected.")

    # مرحله ۲: رمز عبور و دکمهٔ ورود (دکمه بعد از پر شدن رمز فعال می‌شود)
    fill_password(window, PASSWORD)
    click_submit_button(window)
    print("Step 2 submitted.")

    # مرحله ۳: تیک «زیر سیستم ها» و ادامه
    wait_for_element(window, title_re=r"^زیر سیستم.*", control_type="CheckBox")
    check_checkbox(window)
    click_submit_button(window)
    print("Step 3 submitted.")

    # بعد از مرحلهٔ ۳ فقط هشدار OK را می‌بندیم و همان‌جا تمام می‌کنیم
    if wait_for_warning_then_finish(window, WARNING_WAIT_SECONDS):
        print("Warning dismissed.")
    else:
        print("No warning appeared; finishing.")


def main() -> int:
    if not PASSWORD:
        print("Set the BIME_PASSWORD environment variable first.", file=sys.stderr)
        return 1

    try:
        app_path = get_app_path("Bime.exe")
    except Exception as error:
        print(f"Automation Error: {error}", file=sys.stderr)
        return 1

    for attempt in range(1, MAX_ATTEMPTS + 1):
        print(f"--- Attempt {attempt}/{MAX_ATTEMPTS} ---")
        try:
            run_once(app_path)
            print("Done.")
            return 0
        except AppErrorDialog as error:
            print(f"App error dialog on attempt {attempt}: {error}")
        except Exception as error:
            traceback.print_exc()
            print(f"Automation Error on attempt {attempt}: {error}", file=sys.stderr)

        if attempt < MAX_ATTEMPTS:
            print(f"Restarting in {RETRY_DELAY}s...")
            time.sleep(RETRY_DELAY)

    print(f"Failed after {MAX_ATTEMPTS} attempts.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
