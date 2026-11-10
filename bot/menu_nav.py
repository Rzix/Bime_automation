"""ناوبری منوی Bime بر اساس خروجی واقعی explore_menu.py."""
from __future__ import annotations

import json
import time
from difflib import get_close_matches
from pathlib import Path

from . import winbot

__all__ = ["open_sidebar", "open_child", "open_menu", "MenuPathError"]
MENU_DIR = Path(__file__).resolve().parents[1] / "showTabel"


class MenuPathError(ValueError):
    """مسیر در ساختار استخراج‌شدهٔ منو وجود ندارد."""


def _load_tree(sidebar, tree_path=None):
    if sidebar < 1:
        raise ValueError("شمارهٔ آیکون باید از ۱ شروع شود")
    path = Path(tree_path) if tree_path is not None else MENU_DIR / (
        "menu_tree.json" if sidebar == 10 else f"menu_{sidebar}.json"
    )
    try:
        tree = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise MenuPathError(
            f"درخت منو موجود نیست: {path}\n"
            f"ابتدا explore_menu.py --gavel {sidebar} --out {path.name} را اجرا کنید."
        ) from exc
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise MenuPathError(f"فایل درخت منو معتبر نیست: {path}") from exc

    def validate(node):
        if (not isinstance(node, dict) or not isinstance(node.get("name"), str)
                or not node["name"].strip() or not isinstance(node.get("children"), list)):
            raise MenuPathError(f"ساختار گره‌های منو معتبر نیست: {path}")
        for child in node["children"]:
            validate(child)

    validate(tree)
    expected = f"btnSubsys#{sidebar}"
    if tree["name"] != expected:
        raise MenuPathError(f"این فایل برای {tree['name']} است؛ آیکون درخواستی {expected} است")
    if not tree["children"]:
        raise MenuPathError("درخت منو خالی است؛ استخراج منو را دوباره اجرا کنید")
    return tree


def _validate_path(tree, path):
    if not path:
        raise MenuPathError("حداقل یک نام برای مسیر منو وارد کنید")
    nodes = []
    current = tree
    for name in path:
        key = winbot._norm(name)
        matches = [n for n in current["children"] if winbot._norm(n["name"]) == key]
        if len(matches) != 1:
            names = [n["name"] for n in current["children"]]
            normalized = {winbot._norm(n): n for n in names}
            close = get_close_matches(key, normalized, n=3, cutoff=0.4)
            suggestions = [normalized[n] for n in close] or names[:5]
            raise MenuPathError(
                f"مسیر نامعتبر یا مبهم در «{name}»؛ گزینه‌ها: {', '.join(suggestions) or 'هیچ‌کدام'}. "
                "در صورت ناقص بودن درخت، explore_menu.py --deep را اجرا کنید."
            )
        current = matches[0]
        nodes.append(current)
    return nodes


def _visible(name, elements=None, parent=None, role=None, siblings=()):
    """فقط نام دقیق؛ انتخاب نزدیک‌ترین آیتم زیر والد و پیش از هم‌سطح بعدی."""
    elements = winbot.inspect() if elements is None else elements
    hits = [e for e in elements if winbot._shown(e)
            and winbot._norm(e.name) == winbot._norm(name)
            and (not role or e.role.lower() == role.lower())]
    if parent is not None:
        sibling_names = {winbot._norm(n) for n in siblings}
        limits = [e.y for e in elements if winbot._shown(e) and e.y > parent.y
                  and winbot._norm(e.name) in sibling_names]
        hits = [e for e in hits if e.y > parent.y and (not limits or e.y < min(limits))]
    return min(hits, key=lambda e: (e.y, e.x)) if hits else None


def _wait(check, timeout, interval=0.25):
    end = time.monotonic() + timeout
    while True:
        result = check()
        if result:
            return result
        remaining = end - time.monotonic()
        if remaining <= 0:
            return None
        time.sleep(min(interval, remaining))


def _click(el, mouse=False):
    """کلیک از طریق winbot؛ کلیک ماوس در صورت خطای invoke."""
    if not mouse:
        try:
            winbot.click(el.id)
            return
        except RuntimeError:
            pass
    winbot._mouse_click(el)
    time.sleep(winbot._cfg["pause"])


def _open_sidebar(index, tree, timeout):
    def opened():
        elements = winbot.inspect()
        return any(_visible(n["name"], elements, role=n.get("role"))
                   for n in tree["children"])

    if opened():
        return
    for mouse in (False, True):
        if opened():
            return
        el = winbot.find("btnSubsys", nth=index)
        _click(el, mouse=mouse)
        if _wait(opened, timeout):
            return
    raise TimeoutError(f"پنل آیکون {index} باز نشد")


def open_sidebar(index, *, tree_path=None, timeout=10):
    """پنل را فقط وقتی هیچ‌یک از آیتم‌های ریشه‌اش دیده نمی‌شوند باز می‌کند."""
    _open_sidebar(index, _load_tree(index, tree_path), timeout)


def open_child(parent, child, retries=2, *, timeout=4, parent_resolver=None,
               role=None, siblings=()):
    """والد باز را دوباره کلیک نمی‌کند و برای invoke بی‌اثر، ماوس را امتحان می‌کند."""
    resolve = parent_resolver or (lambda: _visible(parent))

    def locate():
        p = resolve()
        return _visible(child, parent=p, role=role, siblings=siblings) if p else None

    for _ in range(retries + 1):
        found = locate()
        if found:
            return found
        for mouse in (False, True):
            found = locate()
            if found:
                return found
            p = resolve()
            if p is None:
                raise winbot.ElementNotFound(f"والد «{parent}» قابل‌مشاهده نیست")
            _click(p, mouse=mouse)
            found = _wait(locate, timeout)
            if found:
                return found
    raise TimeoutError(f"«{child}» زیر «{parent}» ظاهر نشد")


def open_menu(*path, sidebar=10, tree_path=None, timeout=10):
    """مسیر را اعتبارسنجی می‌کند، والدها را باز می‌کند و روی مقصد کلیک می‌کند."""
    tree = _load_tree(sidebar, tree_path)
    nodes = _validate_path(tree, path)
    if _visible(nodes[0]["name"], role=nodes[0].get("role")) is None:
        _open_sidebar(sidebar, tree, timeout)

    def locate_at(index):
        elements = winbot.inspect()
        parent = None
        container = tree
        parent_siblings = ()
        for node in nodes[:index + 1]:
            parent = _visible(node["name"], elements, parent=parent,
                              role=node.get("role"), siblings=parent_siblings)
            if parent is None:
                return None
            parent_siblings = [n["name"] for n in container["children"]
                               if winbot._norm(n["name"]) != winbot._norm(node["name"])]
            container = node
        return parent

    if not _wait(lambda: locate_at(0), timeout):
        raise winbot.ElementNotFound(f"آیتم «{path[0]}» قابل‌مشاهده نیست")
    for index in range(len(nodes) - 1):
        container = tree if index == 0 else nodes[index - 1]
        siblings = [n["name"] for n in container["children"]
                    if winbot._norm(n["name"]) != winbot._norm(nodes[index]["name"])]
        open_child(nodes[index]["name"], nodes[index + 1]["name"],
                   timeout=timeout, parent_resolver=lambda i=index: locate_at(i),
                   role=nodes[index + 1].get("role"), siblings=siblings)

    final = locate_at(len(nodes) - 1)
    if final is None:
        raise winbot.ElementNotFound(f"مقصد «{path[-1]}» قابل‌مشاهده نیست")
    before = winbot.inspect()
    _click(final)
    # پس از invoke بی‌اثر، مقصد را تازه پیدا می‌کنیم و ماوس را امتحان می‌کنیم.
    if (winbot._cfg["click_mode"] != "mouse"
            and not _wait(lambda: winbot.inspect() != before, timeout)):
        fresh = locate_at(len(nodes) - 1)
        if fresh is not None:
            _click(fresh, mouse=True)
    return final
