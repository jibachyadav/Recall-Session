"""The optional Claude API key, kept in the user's data folder. The key is never shown back on screen."""
import os

import config

KEY_NAME = "ANTHROPIC_API_KEY"


class SettingsError(Exception):
    """A problem the user can fix. The message is safe to show."""


def _read_lines():
    return config.ENV_FILE.read_text().splitlines() if config.ENV_FILE.exists() else []


def _write_lines(lines):
    config.ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = config.ENV_FILE.with_suffix(".tmp")
    tmp.write_text("\n".join(lines) + ("\n" if lines else ""))
    os.chmod(tmp, 0o600)
    tmp.replace(config.ENV_FILE)


def has_key():
    return bool(os.environ.get(KEY_NAME))


def key_hint():
    """'sk-ant-...wxyz' style hint so the user can recognise which key is saved, without revealing it."""
    key = os.environ.get(KEY_NAME, "")
    return f"{key[:7]}...{key[-4:]}" if len(key) > 14 else ("saved" if key else "")


def save_key(key):
    key = key.strip().strip("\"'")
    if not key:
        raise SettingsError("Paste your key first.")
    if " " in key or "\n" in key:
        raise SettingsError("A key has no spaces. Paste only the key itself.")
    if not key.startswith("sk-ant-"):
        raise SettingsError("That doesn't look like a Claude key. It should start with sk-ant-")
    lines = [ln for ln in _read_lines() if not ln.strip().startswith(KEY_NAME + "=")]
    _write_lines(lines + [f"{KEY_NAME}={key}"])
    os.environ[KEY_NAME] = key                    # takes effect straight away, no restart


def remove_key():
    _write_lines([ln for ln in _read_lines() if not ln.strip().startswith(KEY_NAME + "=")])
    os.environ.pop(KEY_NAME, None)


def test_key():
    """Make one tiny request. Returns (ok, message) in plain words."""
    if not has_key():
        return False, "No key saved yet."
    from src import llm
    try:
        llm.ask("Reply with the single word OK.", max_tokens=5)
        return True, "The key works. AI features are on."
    except Exception as e:
        name, text = type(e).__name__, str(e).lower()
        if "credit balance" in text:
            return False, "The key is valid, but the account has no credit. Add credit at console.anthropic.com."
        if name == "AuthenticationError" or "invalid x-api-key" in text or "authentication" in text:
            return False, "Claude didn't accept this key. It may be wrong or deleted."
        if name in ("APIConnectionError", "APITimeoutError") or "connect" in text:
            return False, "Can't reach Claude. Check your internet connection."
        if name == "RateLimitError":
            return False, "Too many requests right now. Try again in a minute."
        return False, f"Something went wrong ({name})."
