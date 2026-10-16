"""Everything that differs between operating systems lives here, so the rest of the app doesn't care.

Linux is fully supported. Windows has the pieces that don't need audio capture (see the notes on each function).
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import config

IS_LINUX = sys.platform.startswith("linux")
IS_WINDOWS = sys.platform.startswith("win")


def ensure_data_dir():
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    return config.DATA_DIR


def migrate_legacy_data(log=lambda m: None):
    """Bring data from the old place (inside the program folder) to the user's data folder, once.

    Safe by design:
    - it copies first, checks the copy, and only then moves the originals into a backup folder.
      NOTHING is ever deleted, so a mistake can always be undone;
    - it does nothing when the new place already has data (never overwrites);
    - it does nothing when the data folder was chosen on purpose (RECALL_SESSION_DATA), as in tests.
    Returns the list of things brought over."""
    if os.environ.get("RECALL_SESSION_DATA") or config.APP_DIR == config.DATA_DIR:
        return []
    old_sessions, new_sessions = config.APP_DIR / "sessions", config.DATA_DIR / "sessions"
    ensure_data_dir()
    new_has_data = (config.DATA_DIR / "users.json").exists() or (new_sessions.exists() and any(new_sessions.iterdir()))
    if new_has_data:
        return []
    todo = []                                            # (source, destination)
    if old_sessions.exists():
        todo += [(d, new_sessions / d.name) for d in sorted(old_sessions.iterdir()) if d.is_dir()]
    todo += [(config.APP_DIR / n, config.DATA_DIR / n) for n in ("users.json", ".remember") if (config.APP_DIR / n).exists()]
    if not todo:
        return []
    new_sessions.mkdir(parents=True, exist_ok=True)
    created = []                                         # copies WE made, so a failure can remove exactly these

    def size(path):
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) if path.is_dir() else path.stat().st_size

    try:
        for src, dst in todo:                            # 1. copy everything
            shutil.copytree(src, dst) if src.is_dir() else shutil.copy2(src, dst)
            created.append(dst)
        for src, dst in todo:                            # 2. check every copy before touching an original
            if not dst.exists() or size(src) != size(dst):
                raise OSError(f"Copying {src.name} did not match the original.")
    except Exception as e:
        for dst in created:                              # undo our own partial copies; the originals were never touched
            shutil.rmtree(dst, ignore_errors=True) if dst.is_dir() else dst.unlink(missing_ok=True)
        raise OSError(f"Moving your data to its new place failed ({e}). Nothing was moved; your data is unchanged.") from e
    backup = config.APP_DIR / "migrated-backup"          # 3. keep the originals, out of the way
    backup.mkdir(exist_ok=True)
    for src, _ in todo:
        shutil.move(str(src), str(backup / src.name))
    old_env = config.APP_DIR / ".env"
    if old_env.exists() and not config.ENV_FILE.exists():
        shutil.copy2(old_env, config.ENV_FILE)           # keep the API key working
    names = [src.name for src, _ in todo]
    log(f"Copied {len(names)} item(s) to {config.DATA_DIR}. The originals are kept in {backup}")
    return names


def move_to_trash(path):
    """Send a file or folder to the Trash / Recycle Bin (recoverable). Raises OSError if it can't."""
    from send2trash import send2trash
    try:
        send2trash(str(path))
    except Exception as e:
        raise OSError(str(e)) from e


def take_screenshot(path):
    """Save a picture of the whole screen. Returns True on success."""
    path = Path(path)
    if IS_LINUX:                                   # Wayland (GNOME) only allows this through its own tool
        for cmd in (["gnome-screenshot", "-f", str(path)], ["grim", str(path)], ["scrot", str(path)]):
            if shutil.which(cmd[0]):
                subprocess.run(cmd, capture_output=True)
                if path.exists():
                    return True
        return False
    try:                                           # Windows / macOS
        import mss
        with mss.mss() as grabber:
            mss.tools.to_png(*(lambda shot: (shot.rgb, shot.size))(grabber.grab(grabber.monitors[0])), output=str(path))
        return path.exists()
    except Exception:
        return False


def call_detection_supported():
    """Can this computer tell that a Zoom/Teams/Meet call is running? (Linux with PipeWire, or Windows.)"""
    return IS_WINDOWS or (IS_LINUX and shutil.which("pw-dump") is not None)


def audio_recording_supported():
    """Can the app capture the sound of calls and videos? (Linux and Windows.)"""
    return IS_LINUX or IS_WINDOWS


def ffmpeg_path():
    """The ffmpeg program: the copy shipped with the installed app if there is one, else the one on this computer."""
    exe = "ffmpeg.exe" if IS_WINDOWS else "ffmpeg"
    for folder in (config.APP_DIR, config.APP_DIR.parent, Path(sys.executable).parent):
        if (folder / exe).exists():
            return str(folder / exe)
    return shutil.which("ffmpeg") or "ffmpeg"


def missing_tools():
    """Programs the app needs that are not installed, as (name, how to get it). Empty when all is well."""
    problems = []
    if IS_LINUX and not (shutil.which("ffmpeg") or Path(ffmpeg_path()).is_file()):   # (Windows records without ffmpeg)
        problems.append(("ffmpeg", "sudo apt install ffmpeg"))
    if IS_LINUX and not any(shutil.which(t) for t in ("gnome-screenshot", "grim", "scrot")):
        problems.append(("gnome-screenshot (for flag screenshots)", "sudo apt install gnome-screenshot"))
    if IS_LINUX and not shutil.which("pw-dump"):
        problems.append(("pipewire-bin (to detect online classes)", "sudo apt install pipewire-bin"))
    return problems


def hidden_window():
    """Extra subprocess arguments so helper programs don't flash a console window on Windows (nothing on Linux)."""
    if IS_WINDOWS:
        import subprocess as sp
        return {"creationflags": sp.CREATE_NO_WINDOW}
    return {}


# ---- Windows: who is using the microphone? ----------------------------------------------------------------------
_MIC_KEY = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
_OWN_PROGRAMS = {"recall-session.exe", "python.exe", "pythonw.exe", "ffmpeg.exe"}


def mic_users_from(entries):
    """entries: (registry key name, LastUsedTimeStart, LastUsedTimeStop) for each app Windows has seen use the
    microphone. An app is using it right now when it started and has not stopped (Stop == 0).
    Returns the program names, e.g. ["Zoom.exe", "chrome.exe"], leaving out our own."""
    users = []
    for name, start, stop in entries:
        exe = name.replace("#", "\\").rsplit("\\", 1)[-1]
        if start and not stop and exe.lower() not in _OWN_PROGRAMS:
            users.append(exe)
    return users


def windows_call_running():
    """Name of a program using the microphone right now (Zoom, Teams, a browser in a Meet call...), or None.

    Windows can't cheaply say "this program is also playing sound", so unlike on Linux the microphone alone is the
    signal. A voice recorder would also count; that is acceptable because it only decides when recording may begin."""
    try:
        import winreg
    except ImportError:
        return None
    entries = []
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, _MIC_KEY)
    except OSError:
        return None
    for parent in ("", "NonPackaged"):
        try:
            folder = winreg.OpenKey(root, parent) if parent else root
            for i in range(winreg.QueryInfoKey(folder)[0]):
                name = winreg.EnumKey(folder, i)
                if name == "NonPackaged":
                    continue
                try:
                    with winreg.OpenKey(folder, name) as app:
                        start = winreg.QueryValueEx(app, "LastUsedTimeStart")[0]
                        stop = winreg.QueryValueEx(app, "LastUsedTimeStop")[0]
                    entries.append((name, start, stop))
                except OSError:
                    continue
        except OSError:
            continue
    users = mic_users_from(entries)
    return users[0] if users else None
