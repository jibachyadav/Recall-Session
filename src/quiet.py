"""Make flagging silent and unobtrusive on GNOME while recording.

GNOME itself plays the shutter sound and flashes the screen on every screenshot, and
no screenshot tool can turn either off. While recording we therefore switch off two
GNOME settings and put them back afterwards:
  - event sounds (the shutter sound): verified silent.
  - desktop animations (the flash is a fade animation): meant to remove the blink; not verified.
The original values are saved in a small file so they are restored even after a crash
(the next launch restores them).
"""
import atexit
import json
import subprocess

import config

SETTINGS = {
    "sounds": ("org.gnome.desktop.sound", "event-sounds"),
    "animations": ("org.gnome.desktop.interface", "enable-animations"),
}
BACKUP = config.DATA_DIR / ".gnome_settings_backup.json"


def _gsettings(*args):
    try:
        return subprocess.run(["gsettings", *args], capture_output=True, text=True, timeout=5).stdout.strip()
    except Exception:
        return ""


def mute():
    """Turn the settings off (remembering the values they had)."""
    if BACKUP.exists():  # already muted by us
        return
    saved = {}
    for name, (schema, key) in SETTINGS.items():
        if _gsettings("get", schema, key) == "true":
            saved[name] = "true"
    if not saved:
        return
    BACKUP.write_text(json.dumps(saved))
    for name in saved:
        _gsettings("set", *SETTINGS[name], "false")
    atexit.register(restore)


def restore():
    """Put the settings back if we turned them off. Safe to call any time."""
    if not BACKUP.exists():
        return
    try:
        saved = json.loads(BACKUP.read_text())
    except Exception:
        saved = {name: "true" for name in SETTINGS}
    for name, value in saved.items():
        if name in SETTINGS:
            _gsettings("set", *SETTINGS[name], value)
    BACKUP.unlink(missing_ok=True)


# Programs that are ours (or players/recorders), never a meeting
_OWN = {"ffmpeg", "ffplay", "ffprobe", "python", "python3", "pw-record", "pw-play", "pw-cat", "aplay", "arecord",
        "parecord", "paplay", "gnome-screenshot", "gnome-shell"}


def call_running():
    """Name of an app that is in a call right now, or None.

    A call is one program that is using the microphone AND playing sound at the same time
    (Zoom, Teams, Meet in a browser...). A YouTube video only plays sound, and a phone
    conversation next to the laptop is not an app at all, so neither counts.
    """
    import json
    import os

    from src import osdep
    if osdep.IS_WINDOWS:
        return osdep.windows_call_running()
    try:
        dump = json.loads(subprocess.run(["pw-dump"], capture_output=True, text=True, timeout=5).stdout)
    except Exception:
        return None
    streams = {}   # pid -> {"in": bool, "out": bool, "name": str}
    for obj in dump:
        info = obj.get("info") or {}
        props = info.get("props") or {}
        kind = str(props.get("media.class", ""))
        if info.get("state") != "running" or not kind.startswith("Stream/") or not kind.endswith("/Audio"):
            continue
        binary = os.path.basename(str(props.get("application.process.binary", ""))).lower()
        pid = props.get("application.process.id")
        if pid is None or binary in _OWN or pid == os.getpid():
            continue
        entry = streams.setdefault(pid, {"in": False, "out": False, "name": props.get("application.name") or binary})
        if kind.startswith("Stream/Input"):
            entry["in"] = True
        elif kind.startswith("Stream/Output"):
            entry["out"] = True
    for entry in streams.values():
        if entry["in"] and entry["out"]:
            return entry["name"]
    return None
