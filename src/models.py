"""The speech models the app needs, and downloading them the first time (with progress).

An installed copy of the app does not carry the models (they are large); this module checks which are on the
computer and fetches the missing ones. Models live in the normal Hugging Face cache, shared with other programs.
"""
import threading
import time
from pathlib import Path

import config

# name -> (what it is for, approximate download size in MB). Sizes are only used for the progress bar.
CATALOG = {
    "base": ("quick live drafts", 145),
    "small": ("English transcripts", 485),
    "large-v3-turbo": ("Nepali and Hindi accuracy", 1620),
}


def required():
    """Models every user needs to record in English."""
    return sorted({config.LIVE_DRAFT_MODEL, config.LIVE_WHISPER_MODEL, config.WHISPER_MODEL})


def optional():
    """Big models only needed for Nepali / Hindi."""
    return sorted(set(config.FINAL_MODEL_FOR.values()))


def size_mb(name):
    return CATALOG.get(name, ("", 500))[1]


def purpose(name):
    return CATALOG.get(name, ("speech recognition", 0))[0]


def bundled_dir():
    """Models shipped inside the installed app (the installers include the English ones)."""
    return config.APP_DIR / "models"


def local_path(name):
    """Folder of a model that came with the app, or None (then it is read from / downloaded to the cache)."""
    folder = bundled_dir() / name
    return str(folder) if (folder / "model.bin").exists() else None


def is_downloaded(name):
    if local_path(name):
        return True
    from faster_whisper.utils import download_model
    try:
        download_model(name, local_files_only=True)
        return True
    except Exception:
        return False


def missing(names):
    return [n for n in names if not is_downloaded(n)]


def _cache_bytes(name):
    """Bytes of this model already on disk (finished or partial), for the progress bar."""
    from faster_whisper.utils import _MODELS
    import huggingface_hub
    repo = _MODELS.get(name, name).replace("/", "--")
    folder = Path(huggingface_hub.constants.HF_HUB_CACHE) / f"models--{repo}"
    total = 0
    for f in folder.rglob("*"):
        try:
            if f.is_file() and not f.is_symlink():
                total += f.stat().st_size
        except OSError:
            pass
    return total


def download(names, progress=lambda done_mb, total_mb, name: None, cancelled=lambda: False):
    """Download each model in turn. Calls progress(done_mb, total_mb, current_name) about twice a second.

    Raises OSError with a plain-language message if the internet is unavailable. Models already present are skipped,
    and a half-finished download is resumed by the next call."""
    from faster_whisper.utils import download_model
    names = missing(names)
    total = sum(size_mb(n) for n in names)
    finished = 0
    for name in names:
        before = _cache_bytes(name)
        box = {}

        def work(name=name):
            try:
                download_model(name)
            except Exception as e:            # reported on the calling thread
                box["error"] = e

        t = threading.Thread(target=work, daemon=True)
        t.start()
        while t.is_alive():
            if cancelled():
                raise OSError("Download cancelled. You can finish it later.")
            have = max(0, _cache_bytes(name) - before) / 1e6
            progress(min(finished + have, total), total, name)
            time.sleep(0.5)
        if "error" in box:
            raise OSError("Couldn't download the speech model. Check your internet connection and try again.\n"
                          f"({box['error']})") from box["error"]
        finished += size_mb(name)
        progress(min(finished, total), total, name)
