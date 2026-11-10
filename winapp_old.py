"""CLI wrapper around pywinauto – replacement for the missing winapp tool."""
import argparse, json, re, subprocess, sys, time

try:
    from pywinauto import Desktop, Application
except ImportError:
    print("Error: pywinauto not installed. Install with: pip install pywinauto", file=sys.stderr)
    sys.exit(1)

_CONTROL_ROLE_MAP = {
    "Edit": "Edit", "Button": "Button", "Text": "Text", "MenuItem": "MenuItem",
    "CheckBox": "CheckBox", "RadioButton": "RadioButton", "ComboBox": "ComboBox",
    "ListItem": "ListItem", "TreeItem": "TreeItem", "Tab": "Tab", "Pane": "Pane",
    "Window": "Window", "Toolbar": "Toolbar", "GroupButton": "GroupButton",
    "HeaderItem": "HeaderItem", "Thumb": "Thumb", "ScrollBar": "ScrollBar",
}


def _get_app_window(app_name):
    for backend in ("uia", "win32"):
        try:
            app = Application(backend=backend).connect(title_re=f".*{re.escape(app_name)}.*", timeout=5)
            top = app.top_window()
            if top.is_visible():
                return top, backend
        except Exception:
            continue
    desktop = Desktop(backend="uia")
    for w in desktop.windows():
        if app_name.lower() in (w.window_text() or "").lower() and w.is_visible():
            return w, "uia"
    raise RuntimeError(f"App '{app_name}' not found (is it running?)")


def _walk_controls(ctrl, depth=0, max_depth=100):
    if depth > max_depth:
        return
    indent = "  " * depth
    role = ctrl.get_control_type()
    role_display = _CONTROL_ROLE_MAP.get(role, role)
    name = ctrl.window_text().strip() or ""
    ctrl_id = ""
    try:
        ctrl_id = ctrl.current_name()
    except Exception:
        pass
    bounds = ""
    try:
        rect = ctrl.rectangle()
        bounds = f"({rect.left}, {rect.top}, {rect.width()}x{rect.height()})"
    except Exception:
        pass
    expanded = ""
    try:
        ec_pattern = ctrl.expandcollapse
        if ec_pattern is not None:
            current_state = ec_pattern.current_expand_state
            if hasattr(ec_pattern, 'ExpandState'):
                from pywinauto.axinterface import ExpandState
                if current_state == ExpandState.MAXIMIZED:
                    expanded = " [expanded]"
                elif current_state == ExpandState.MINIMIZED:
                    expanded = " [collapsed]"
            else:
                # Fallback: use integer values directly
                if current_state == 3:   # MAXIMIZED
                    expanded = " [expanded]"
                elif current_state == 0:  # MINIMIZED
                    expanded = " [collapsed]"
    except Exception:
        pass
    line = f"{indent}{ctrl_id} {role_display}" + (f' "{name}"' if name else "") + bounds + expanded
    print(line)
    children = []
    try:
        children = ctrl.children()
    except Exception:
        pass
    for i, child in enumerate(children):
        _walk_controls(child, depth + 1, max_depth)


def cmd_inspect(args):
    app_name = args.app
    depth = args.depth if hasattr(args, "depth") else 100
    top, backend = _get_app_window(app_name)
    _walk_controls(top, max_depth=int(depth))


def cmd_invoke(args):
    ctrl_id = args.control_id
    app_name = args.app
    top, backend = _get_app_window(app_name)
    selectors = [
        lambda t, cid: t.child_window(auto_id=cid),
        lambda t, cid: t.child_window(title_re=f".*{re.escape(cid)}.*"),
        lambda t, cid: t.child_window(title=cid),
    ]
    ctrl = None
    for sel_fn in selectors:
        try:
            candidate = sel_fn(top, ctrl_id).wrapper_object()
            if candidate.exists(timeout=2):
                ctrl = candidate
                break
        except Exception:
            continue
    if ctrl is None:
        raise RuntimeError(f"Control '{ctrl_id}' not found")
    try:
        ctrl.invoke()
    except Exception:
        try:
            ctrl.click_input()
        except Exception:
            raise RuntimeError(f"Cannot invoke or click control '{ctrl_id}'")


def main():
    ap = argparse.ArgumentParser(description="UI automation CLI (pywinauto backend)")
    sub = ap.add_subparsers(dest="cmd")
    ui_p = sub.add_parser("ui")
    ui_sub = ui_p.add_subparsers(dest="subcmd")
    insp = ui_sub.add_parser("inspect")
    insp.add_argument("-a", "--app", required=True, help="Application name")
    insp.add_argument("--depth", type=int, default=100)
    insp.set_defaults(func=cmd_inspect)
    inv = ui_sub.add_parser("invoke")
    inv.add_argument("control_id")
    inv.add_argument("-a", "--app", required=True, help="Application name")
    inv.set_defaults(func=cmd_invoke)
    args = ap.parse_args()
    if not hasattr(args, "func"):
        ap.print_help()
        sys.exit(1)
    try:
        args.func(args)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
