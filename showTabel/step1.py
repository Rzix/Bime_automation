"""حذف جدول با کلیک روی آیکون چکش (دهمین دکمهٔ btnSubsys)."""
import sys
from pathlib import Path

# پوشهٔ script را به مسیر جست‌وجوی پایتون اضافه می‌کنیم تا پکیج bot پیدا شود
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from bot import winbot

winbot.configure(app="Bime")

winbot.wait_for_content("شرکت بیمه سرمد", timeout=30)

winbot.click("btnSubsys", nth=10)

# نمونهٔ نوشتن در فیلد (نام فیلد را از inspect بردارید)
# winbot.populate_text("متن تست", "txtName", "replace")