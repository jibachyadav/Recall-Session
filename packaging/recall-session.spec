# PyInstaller recipe: builds a self-contained folder (Python + all libraries) for Linux or Windows.
#   pyinstaller packaging/recall-session.spec --noconfirm
# The speech models are NOT included (the app downloads them on first run).
import sys
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

ROOT = Path(SPECPATH).parent
datas, binaries, hidden = [(str(ROOT / "assets"), "assets")], [], []
for pkg in ("faster_whisper", "ctranslate2", "av", "onnxruntime", "tokenizers", "certifi"):
    d, b, h = collect_all(pkg)
    datas += d; binaries += b; hidden += h
if (ROOT / "packaging" / "models").exists():          # English speech models, fetched by packaging/fetch_models.py
    datas += [(str(ROOT / "packaging" / "models"), "models")]
if sys.platform.startswith("win"):
    hidden += ["pyaudiowpatch"]

a = Analysis([str(ROOT / "app.py")], pathex=[str(ROOT)], datas=datas, binaries=binaries, hiddenimports=hidden,
             excludes=["matplotlib", "scipy", "pandas", "torch", "IPython", "pytest"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="recall-session", console=False,
          icon=str(ROOT / "assets" / "icon.ico") if sys.platform.startswith("win") else None)
coll = COLLECT(exe, a.binaries, a.datas, name="recall-session")
