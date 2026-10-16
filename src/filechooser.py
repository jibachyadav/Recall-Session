"""Ask the user to pick a document with the desktop's own file chooser (GNOME portal), without blocking the app.

One live D-Bus connection is used per request: it calls the portal's FileChooser and receives the answer
(file picked / cancelled / closed) on that same connection, so every request completes on its own.
"""
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

try:
    from jeepney import DBusAddress, MatchRule, message_bus, new_method_call
    from jeepney.io.blocking import open_dbus_connection
except ImportError:                                     # Windows / macOS: the app falls back to Tk's own chooser
    DBusAddress = None

PATTERNS = ["*.pdf", "*.PDF", "*.docx", "*.DOCX", "*.txt", "*.TXT", "*.md"]
PORTAL = DBusAddress("/org/freedesktop/portal/desktop", bus_name="org.freedesktop.portal.Desktop",
                     interface="org.freedesktop.portal.FileChooser") if DBusAddress else None
_open_requests = {}       # request path -> connection, so a request can be closed (used by tests)


def _options(folder):
    return {
        "filters": ("a(sa(us))", [("Documents (PDF, Word, text)", [(0, p) for p in PATTERNS]),
                                  ("All files", [(0, "*")])]),
        "current_folder": ("ay", folder.encode() + b"\x00"),
    }


def answer_path(body):
    """The path from a portal Response body (code, results); "" if the user cancelled or closed it."""
    code, results = body
    if code != 0:
        return ""                                      # 1 = cancelled, 2 = closed
    uris = results.get("uris", ("as", []))[1]
    return unquote(urlparse(uris[0]).path) if uris else ""


def portal_choose(title, folder, timeout=None, on_request=None):
    """Show the chooser and wait. Returns a path, "" if the user cancelled or closed it, or None if the
    portal can't be used. `on_request(path)` is called with the request's D-Bus path once it is open."""
    try:
        conn = open_dbus_connection(bus="SESSION")
    except Exception:
        return None
    try:
        rule = MatchRule(type="signal", interface="org.freedesktop.portal.Request", member="Response")
        conn.send_and_get_reply(message_bus.AddMatch(rule), timeout=5)
        reply = conn.send_and_get_reply(
            new_method_call(PORTAL, "OpenFile", "ssa{sv}", ("", title, _options(folder))), timeout=10)
        if reply.header.message_type.name == "error":
            return None
        request = reply.body[0]
        _open_requests[request] = conn
        if on_request:
            on_request(request)
        while True:                                   # wait for OUR request's answer, however long it takes
            msg = conn.receive(timeout=timeout)
            h = msg.header
            if h.message_type.name != "signal" or h.fields.get(1) != request:
                continue
            return answer_path(msg.body)
    except TimeoutError:
        return ""
    except Exception:
        return None
    finally:
        _open_requests.pop(locals().get("request"), None)
        conn.close()


def close_request(request):
    """Close an open chooser from the same connection that opened it (the portal only allows that)."""
    conn = _open_requests.get(request)
    if conn:
        conn.send(new_method_call(DBusAddress(request, bus_name="org.freedesktop.portal.Desktop",
                                              interface="org.freedesktop.portal.Request"), "Close"))


def _zenity_choose(title, folder):
    if not shutil.which("zenity"):
        return None
    out = subprocess.run(["zenity", "--file-selection", f"--title={title}", f"--filename={folder}/"],
                         capture_output=True, text=True)
    return out.stdout.strip()


def choose_document_async(callback, title="Choose a PDF, Word or text file"):
    """Open the chooser in the background; callback(path) gets a path, "" (cancelled) or None (no chooser)."""
    home = Path.home()
    folder = str(home / "Documents" if (home / "Documents").exists() else home)

    def work():
        if PORTAL is None:
            return callback(None)
        path = portal_choose(title, folder)
        if path is None:
            path = _zenity_choose(title, folder)
        callback(path)

    threading.Thread(target=work, daemon=True).start()
