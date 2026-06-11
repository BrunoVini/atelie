"""Structural regression test for live-client.js focus behavior (#241).

The focus-stealing fix is browser-only and can't be exercised deterministically in the
stdlib runner (no DOM). Instead we read the client source and assert the guards are PRESENT:
picker bar buttons must not steal focus (onmousedown + preventDefault, tabIndex -1), and an
isEditableTarget guard referencing the editable element shapes must exist. Assertions are
specific enough to catch removal of the guard but not brittle to whitespace/formatting.
"""
import os

CLIENT = os.path.abspath(os.path.join(
    os.path.dirname(__file__), "..", "scripts", "preview", "live-client.js"))


def _src():
    with open(CLIENT, "r", encoding="utf-8") as f:
        return f.read()


def test_buttons_prevent_default_on_mousedown():
    # Each bar button must keep focus where it is: onmousedown handler calling
    # e.preventDefault(). There are 3 button kinds (variant, accept, reject) so we expect
    # at least 3 such handlers.
    src = _src()
    assert "onmousedown" in src, "bar buttons must set onmousedown to avoid stealing focus"
    # Count handlers that preventDefault on mousedown.
    import re
    handlers = re.findall(r"onmousedown\s*=\s*function\s*\([^)]*\)\s*\{\s*[^}]*preventDefault", src)
    assert len(handlers) >= 3, (
        "expected onmousedown+preventDefault on all bar buttons (variant/accept/reject), "
        f"found {len(handlers)}")


def test_buttons_taken_out_of_tab_order():
    # tabIndex = -1 keeps the picker buttons out of the user's tab order entirely.
    src = _src()
    assert "tabIndex = -1" in src or "tabIndex=-1" in src, \
        "bar buttons should set tabIndex -1"


def test_is_editable_target_guard_exists():
    # The guard helper must exist and recognize editable targets (TEXTAREA / contenteditable)
    # so alt+click selection never blurs an input the user is typing in.
    src = _src()
    assert "isEditableTarget" in src, "missing isEditableTarget focus guard"
    assert "isContentEditable" in src, "isEditableTarget must check isContentEditable"
    assert "TEXTAREA" in src, "isEditableTarget must check TEXTAREA"


def test_alt_click_handler_preserves_active_element():
    # The alt+click selection handler must reference document.activeElement and the editable
    # guard so it can preserve focus when the user is mid-edit.
    src = _src()
    assert "activeElement" in src, "onClick must read document.activeElement to preserve focus"
    # The selection handler should never call .focus() on the *selected* element.
    assert "selected.focus" not in src, "selecting an element must not focus it (#241)"


def test_token_header_sent_on_post():
    # Same-origin client echoes the session token so the server's token gate accepts writes.
    src = _src()
    assert "X-Atelier-Token" in src
    assert "window.__atelierToken" in src
