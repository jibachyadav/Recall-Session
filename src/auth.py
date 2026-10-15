"""Local accounts: register, log in, log out, recovery key, change password, delete account.

Everything is stored on this computer (users.json). Passwords are never stored: only a salted scrypt hash.
Each user's classes and documents live in their own folder, sessions/<user id>/.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import time
from datetime import datetime
from pathlib import Path

import config

USERS_FILE = config.DATA_DIR / "users.json"
REMEMBER_FILE = config.DATA_DIR / ".remember"
MIN_PASSWORD = 8
MAX_ATTEMPTS = 5            # wrong passwords in a row before a short lockout
LOCKOUT_SECONDS = 30
_SCRYPT = dict(n=2 ** 14, r=8, p=1, dklen=32)


class AuthError(Exception):
    """A problem the user can fix. The message is safe to show on screen."""


# ---------------------------------------------------------------- storage
def _load():
    if USERS_FILE.exists():
        try:
            return json.loads(USERS_FILE.read_text())
        except json.JSONDecodeError:
            raise AuthError("The accounts file is damaged. Restore users.json from a backup.")
    return {"users": {}}


def _save(data):
    USERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = USERS_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    os.chmod(tmp, 0o600)
    tmp.replace(USERS_FILE)             # an interrupted save can never leave a half-written file


def _hash(secret, salt=None):
    salt = salt or secrets.token_bytes(16)
    return salt.hex(), hashlib.scrypt(secret.encode(), salt=salt, **_SCRYPT).hex()


def _check(secret, salt_hex, hash_hex):
    candidate = hashlib.scrypt(secret.encode(), salt=bytes.fromhex(salt_hex), **_SCRYPT)
    return hmac.compare_digest(candidate, bytes.fromhex(hash_hex))


def _key(username):
    return username.strip().lower()


# ------------------------------------------------------------- validation
def check_username(username):
    username = username.strip()
    if not 3 <= len(username) <= 24:
        raise AuthError("Choose a username of 3 to 24 characters.")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", username):
        raise AuthError("A username can only use letters, numbers, dots, dashes and underscores.")
    return username


def check_password(password):
    if len(password) < MIN_PASSWORD:
        raise AuthError(f"Choose a password of at least {MIN_PASSWORD} characters.")
    if password.lower() in {"password", "password1", "12345678", "123456789", "qwertyui", "11111111"}:
        raise AuthError("That password is too easy to guess. Pick something harder.")
    if password.strip() != password:
        raise AuthError("A password can't start or end with a space.")


def password_strength(password):
    """0 (empty) to 4 (strong), for the little meter on the register screen."""
    if not password:
        return 0
    score = sum([len(password) >= 8, len(password) >= 12,
                 bool(re.search(r"[a-z]", password)) and bool(re.search(r"[A-Z]", password)),
                 bool(re.search(r"\d", password)) and bool(re.search(r"[^A-Za-z0-9]", password))])
    return max(1, score)


# ----------------------------------------------------------- the accounts
def user_dir(user):
    return config.DATA_DIR / "sessions" / user["id"]


def has_users():
    return bool(_load()["users"])


def legacy_sessions():
    """Folders recorded before accounts existed (directly inside sessions/)."""
    root = config.DATA_DIR / "sessions"
    if not root.exists():
        return []
    users = {u["id"] for u in _load()["users"].values()}
    return [d for d in root.iterdir() if d.is_dir() and d.name not in users]


def register(username, password, confirm, display_name=""):
    """Create an account. Returns (user, recovery_key); the key is shown once and never stored in plain form."""
    username = check_username(username)
    if password != confirm:
        raise AuthError("The two passwords are not the same.")
    check_password(password)
    data = _load()
    if _key(username) in data["users"]:
        raise AuthError("That username is taken. Try another one.")
    salt, pw_hash = _hash(password)
    recovery = "-".join(secrets.token_hex(2).upper() for _ in range(4))          # e.g. 3F9A-0C21-B7D4-9E15
    rsalt, rhash = _hash(recovery.replace("-", ""))
    user = {"id": secrets.token_hex(6), "username": username, "name": display_name.strip() or username,
            "salt": salt, "hash": pw_hash, "recovery_salt": rsalt, "recovery_hash": rhash,
            "created": datetime.now().isoformat(timespec="seconds"), "failed": 0, "locked_until": 0, "token": None}
    first = not data["users"]
    data["users"][_key(username)] = user
    _save(data)
    user_dir(user).mkdir(parents=True, exist_ok=True)
    if first:                                   # the first account keeps everything recorded before accounts existed
        for d in legacy_sessions():
            shutil.move(str(d), str(user_dir(user) / d.name))
    return _public(user), recovery


def _public(user):
    return {"id": user["id"], "username": user["username"], "name": user["name"]}


def login(username, password, remember=False):
    """Check the password. Returns the user. Raises AuthError with a safe message otherwise."""
    data = _load()
    user = data["users"].get(_key(username))
    wrong = AuthError("Wrong username or password.")          # same message for both: don't reveal which one failed
    if user is None:
        _hash(password)                                       # spend the same time, so timing doesn't reveal it
        raise wrong
    if user["locked_until"] > time.time():
        raise AuthError(f"Too many wrong passwords. Try again in {int(user['locked_until'] - time.time()) + 1} seconds.")
    if not _check(password, user["salt"], user["hash"]):
        user["failed"] += 1
        if user["failed"] >= MAX_ATTEMPTS:
            user.update(failed=0, locked_until=time.time() + LOCKOUT_SECONDS)
        _save(data)
        raise wrong
    user.update(failed=0, locked_until=0)
    if remember:
        token = secrets.token_urlsafe(32)
        user["token"] = hashlib.sha256(token.encode()).hexdigest()
        REMEMBER_FILE.write_text(json.dumps({"user": user["username"], "token": token}))
        os.chmod(REMEMBER_FILE, 0o600)
    _save(data)
    return _public(user)


def remembered_user():
    """The user who chose 'keep me signed in' on this computer, or None."""
    try:
        saved = json.loads(REMEMBER_FILE.read_text())
        user = _load()["users"].get(_key(saved["user"]))
        if user and user.get("token") and hmac.compare_digest(user["token"], hashlib.sha256(saved["token"].encode()).hexdigest()):
            return _public(user)
    except (OSError, ValueError, KeyError, AuthError):
        pass
    return None


def logout():
    """Forget the 'keep me signed in' choice (the user's data stays)."""
    try:
        saved = json.loads(REMEMBER_FILE.read_text())
        data = _load()
        user = data["users"].get(_key(saved["user"]))
        if user:
            user["token"] = None
            _save(data)
    except (OSError, ValueError, KeyError, AuthError):
        pass
    REMEMBER_FILE.unlink(missing_ok=True)


def change_password(username, old, new, confirm):
    if new != confirm:
        raise AuthError("The two new passwords are not the same.")
    check_password(new)
    data = _load()
    user = data["users"].get(_key(username))
    if user is None or not _check(old, user["salt"], user["hash"]):
        raise AuthError("Your current password is wrong.")
    user["salt"], user["hash"] = _hash(new)
    user["token"] = None
    _save(data)
    REMEMBER_FILE.unlink(missing_ok=True)


def reset_with_recovery_key(username, recovery, new, confirm):
    """Forgot password: set a new one with the recovery key. Returns a NEW recovery key (the old one is used up)."""
    if new != confirm:
        raise AuthError("The two new passwords are not the same.")
    check_password(new)
    data = _load()
    user = data["users"].get(_key(username))
    code = re.sub(r"[^0-9A-Fa-f]", "", recovery).upper()
    if user is None or not _check(code, user["recovery_salt"], user["recovery_hash"]):
        raise AuthError("That username and recovery key don't match.")
    user["salt"], user["hash"] = _hash(new)
    fresh = "-".join(secrets.token_hex(2).upper() for _ in range(4))
    user["recovery_salt"], user["recovery_hash"] = _hash(fresh.replace("-", ""))
    user.update(failed=0, locked_until=0, token=None)
    _save(data)
    REMEMBER_FILE.unlink(missing_ok=True)
    return fresh


def delete_account(username, password):
    """Delete the account AND all of that user's classes and documents."""
    data = _load()
    user = data["users"].get(_key(username))
    if user is None or not _check(password, user["salt"], user["hash"]):
        raise AuthError("Your password is wrong.")
    folder = user_dir(user)
    del data["users"][_key(username)]
    _save(data)
    REMEMBER_FILE.unlink(missing_ok=True)
    if folder.exists() and folder.parent == config.DATA_DIR / "sessions":
        shutil.rmtree(folder)


def use(user):
    """Point the whole app at this user's own folder."""
    folder = config.DATA_DIR / "sessions" / user["id"]
    folder.mkdir(parents=True, exist_ok=True)
    config.SESSIONS_DIR = folder
