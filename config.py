"""Central settings for Recall-Session. Later steps read their values from here."""
from pathlib import Path

import os
import sys

APP_DIR = Path(__file__).resolve().parent        # where the program's own files are (code, icon)
BASE_DIR = APP_DIR                               # old name, kept so older code keeps working


def _data_dir():
    """Where the user's own data lives (accounts, classes, documents, settings): never inside the program folder."""
    override = os.environ.get("RECALL_SESSION_DATA")           # for tests, and for people who want it elsewhere
    if override:
        return Path(override).expanduser()
    if sys.platform.startswith("win"):
        return Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming") / "Recall-Session"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Recall-Session"
    return Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share") / "recall-session"


DATA_DIR = _data_dir()
SESSIONS_DIR = DATA_DIR / "sessions"             # becomes the signed-in user's own folder after login
ENV_FILE = DATA_DIR / ".env"                     # the Claude API key (optional) is kept here


def _load_env_file(path):
    """Read KEY=value lines from a .env file into the environment (existing variables win)."""
    if not path.exists():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_env_file(ENV_FILE)
_load_env_file(APP_DIR / ".env")                 # an older .env next to the code still works

# Added in later steps; defined now so every module shares one source of truth.
AUDIO_SOURCE = "default"          # microphone (PulseAudio/PipeWire source)
SYSTEM_AUDIO_SOURCE = "@DEFAULT_MONITOR@"  # whatever plays on the default output (YouTube, Zoom)
FLAG_KEY = "f"                    # terminal flag key (step 3)
WHISPER_MODEL = "small"           # tiny/base/small/medium (step 4)
CONTEXT_SECONDS = 45              # transcript window around a flag (step 6)
CLAUDE_MODEL = "claude-sonnet-5-5"  # explanations and summaries (steps 6-7)

# Step 5: live side panel
LIVE_WHISPER_MODEL = "small"      # measured on this laptop: keeps up live (0.30x real time) and is more accurate than "base"
LIVE_CHUNK_SECONDS = 8            # audio is transcribed in chunks this long
LIVE_SUMMARY_SECONDS = 60         # how often "now covering" refreshes (needs ANTHROPIC_API_KEY)
LIVE_SUMMARY_CONTEXT_SECONDS = 180  # how much recent speech the summary looks at
PANEL_WIDTH = 420

# Step 7: whole-class summary
SUMMARY_CHUNK_SECONDS = 600       # each chunk of the lecture is summarized separately

# Output language: what you read in the panel and the notes (speech language is auto-detected)
# Nepali is built but switched off for now. To turn it on, add: "ne": "Nepali" (needs API credit).
LANGUAGES = {"en": "English"}
DEFAULT_LANGUAGE = "en"

# Free offline summary (used when there is no Claude key or credit)
FREE_SUMMARY_SECTION_SECONDS = 300

# Transcript layout: paragraphs, with flagged moments highlighted
PARAGRAPH_WORDS = 60              # start a new paragraph at the next sentence end after this many words
PARAGRAPH_GAP_SECONDS = 2.0       # ...or after a pause this long in the speech
FLAG_HIGHLIGHT_BEFORE = 10        # highlight speech this many seconds before a flag (you react after hearing)
FLAG_HIGHLIGHT_AFTER = 2

# Longest single recording. At the limit the app stops and builds the notes by itself.
MAX_RECORDING_SECONDS = 2 * 60 * 60
RECORDING_WARNING_SECONDS = 5 * 60   # warn this long before the limit

WHISPER_BATCH_SIZE = 8            # final transcription: bigger = faster but uses more memory

# Use the transcript made live during the recording as the final one: results in seconds after Stop.
# Set to False to re-transcribe the whole recording instead (slower, a bit more accurate).
USE_LIVE_TRANSCRIPT = True

# Live chunking: audio is cut at pauses in speech, never in the middle of a word
LIVE_MIN_CHUNK_SECONDS = 4        # don't cut before this much audio...
LIVE_MAX_CHUNK_SECONDS = 12       # ...but always cut by this (at the quietest moment)
LIVE_PAUSE_SECONDS = 0.4          # a pause this long is a good place to cut

# Live text appears twice: a fast rough draft (grey), then the accurate version replaces it
LIVE_DRAFT_MODEL = "base"
LIVE_MAX_LAG_SECONDS = 10         # if transcription is this far behind the audio, skip the accurate pass

# Live helper: questions to ask the teacher, and answers to your questions
LIVE_QUESTIONS_SECONDS = 180      # with Claude, fresh questions to ask the teacher appear this often
ASK_CONTEXT_SECONDS = 300         # how much recent speech the helper reads when you ask
OLLAMA_MODEL = "qwen2.5:1.5b"     # free local fallback (used when Claude is unavailable)
OLLAMA_BIN = "~/.local/ollama/bin/ollama"

# Teacher asks you a question: the app notices it in the live transcript and suggests an answer
ASK_AUTO_SWITCH = True            # jump to the Ask tab when the teacher asks a question
ASK_AUTO_LOCAL = True             # also refresh "questions to ask" by itself with the free local AI

# Live text appears while a sentence is still being spoken
LIVE_PARTIAL_STEP_SECONDS = 2     # re-read the sentence being spoken this often (grey draft)
LIVE_PARTIAL_MAX_LAG_SECONDS = 4  # skip a draft update if the draft model is already this far behind

# Live session is for online classes: it starts only when a meeting app (Zoom, Teams, Meet...) is in a call
LIVE_REQUIRE_CALL = True
LIVE_WAIT_SECONDS = 30            # how long Live session waits for a call to start before giving up

# Documents: accuracy matters more than speed, so use a bigger free local model (about 2.5x slower than the live one)
DOCUMENT_MODEL = "qwen2.5:3b"

# Spoken language: tell the app what language the speaker uses (instead of letting it guess)
SPOKEN_LANGUAGES = {"auto": "Detect automatically", "en": "English", "ne": "Nepali", "hi": "Hindi"}
LANGUAGE_NAMES = {"en": "English", "ne": "Nepali", "hi": "Hindi"}
# Final (after-class) transcription model per language. The default `small` is unusable for Nepali (about
# 100% word errors in our test) so Nepali uses the big model (41%, about half real time on this laptop).
FINAL_MODEL_FOR = {"ne": "large-v3-turbo"}

# Big models (Nepali): measured on a 3-minute Nepali recording, batch 4 + quick search was 15% faster and used 22% less
# memory than batch 8 + careful search, with the same accuracy. Smaller models keep WHISPER_BATCH_SIZE and the default search.
LARGE_MODELS = {"large-v3-turbo", "large-v3", "large-v2", "medium"}
LARGE_MODEL_BATCH_SIZE = 4
LARGE_MODEL_BEAM_SIZE = 1
# Rough time the after-class pass takes, as a multiple of the recording length (measured on this laptop), used to
# tell the user how long to expect. Nepali = big model + the offline English pass.
SLOW_PASS_FACTOR = {"ne": 0.45, "hi": 0.3}
