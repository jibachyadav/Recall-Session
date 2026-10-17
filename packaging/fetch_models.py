"""Download the English speech models into packaging/models/ so the installer can carry them.

    python packaging/fetch_models.py
The installed app then works from the first minute, with no download step."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from faster_whisper.utils import download_model  # noqa: E402

from src import models  # noqa: E402

for name in models.required():
    target = ROOT / "packaging" / "models" / name
    if (target / "model.bin").exists():
        print(name, "already there")
        continue
    print("fetching", name, "...", flush=True)
    download_model(name, output_dir=str(target))
print("models ready in", ROOT / "packaging" / "models")
