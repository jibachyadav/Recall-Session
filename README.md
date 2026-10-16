# Recall-Session

A desktop app that listens to your online classes and videos, keeps a live transcript, and turns each session into
clear notes. It runs on your own computer: speech recognition is local, and the AI parts work without paying for anything.

> **Status:** works on Linux (Ubuntu / GNOME / Wayland). The Windows port and installers are not done yet.

## What it does

Start in one of three ways from the home screen:

| Start | What happens |
|---|---|
| **Record a live class** | Captures the teacher's sound (Zoom, Teams, Meet…) and your microphone together. It only starts once a call is actually running. |
| **Record a video** | Captures what is playing on your computer (YouTube or any video). |
| **Add a document** | Summarizes a PDF, Word or text file. |

While a class is recording you get:

- **Live transcript** that appears as people speak.
- **Flags**: press the flag hotkey (or button) at a confusing moment. It silently saves a screenshot and highlights that
  moment in the transcript. No sound, no blinking.
- **Important sentences** are highlighted automatically.
- **Ask tab** (live classes): suggested questions you could ask the teacher, an instant suggested answer when the teacher
  asks *you* something, and an "Ask anything" box.

When you stop, you get a **Summary**, the **Full transcript**, an **Original** transcript (for Nepali/Hindi) and the
**Flagged** moments, all saved under your account. Recordings are limited to 2 hours.

Also included: local accounts (register, login, remember me, recovery key), a searchable library with per-type filters,
select-all and delete (to the Trash), and a dark theme.

## Languages

You pick the spoken language when you name a session: Auto, English, Nepali or Hindi.

- **English** is fast and accurate.
- **Nepali and Hindi** are transcribed in their own language first (Nepali uses the larger `large-v3-turbo` model for the
  final pass). An English version is **optional**: with a Claude API key you can press *Translate with Claude*; without one,
  *Rough English (offline)* is available but is labelled rough.
- Honest limits: Nepali accuracy is modest (roughly half the words can still be wrong in the plain mode, more in the fast
  mode). Closing other programs makes the big model noticeably faster.

## AI: free by default, Claude optional

1. **Claude** (best quality) if you add an API key on the Account page. Keys are stored only on your computer.
2. **Ollama**, a free local model, if it is installed (`qwen2.5:1.5b` for live Ask, `qwen2.5:3b` for documents).
3. **Offline summary**, a built-in extractive fallback, otherwise.

Speech-to-text is always local ([faster-whisper](https://github.com/SYSTRAN/faster-whisper)).

## Install (Linux)

You need Python 3.12, `ffmpeg`, PipeWire (with `pw-dump`) and `gnome-screenshot`.

```bash
sudo apt install python3-venv python3-tk ffmpeg gnome-screenshot
git clone https://github.com/jibachyadav/Recall-Session.git
cd Recall-Session
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

The first transcription downloads the Whisper model once (large models are over 1 GB), so do it on a good connection.

Optional free local AI:

```bash
# install Ollama from https://ollama.com, then:
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:3b
```

## Where your data lives

Everything is stored in `~/.local/share/recall-session/` (accounts, per-user `sessions/<id>/`, and the `.env` holding
your API key). Set `RECALL_SESSION_DATA` to use another folder. Each session folder holds the audio, transcripts
(`transcript_original.json`, `transcript_final.json`), flags, screenshots, summary and notes.

Nothing is uploaded unless you add a Claude key, and then only transcript/document text goes to Claude when you use an AI feature.

## Command line

`main.py` is an older command-line version (`record`, `transcribe`, `explain`, `summarize`, `process`). It needs you to be
logged in once through the app.

## Project layout

```
app.py, run.sh      launchers
config.py           all settings (models, limits, paths)
src/app.py          main window and screens
src/dashboard.py    library home screen
src/live*.py        live transcription and panels
src/record.py       ffmpeg recording (system sound + mic)
src/transcribe.py   Whisper pipeline, language logic
src/translate.py    Claude translation / improve
src/documents.py    PDF / Word / text summaries
src/auth*.py        local accounts
src/osdep.py        OS-specific bits (screenshots, trash, call detection)
```

## Privacy and consent

Recording a call may need the other people's consent where you live. Tell your teacher or classmates before recording,
and follow your school's rules.

## Roadmap

- Linux installer (AppImage / .deb) and a first-run model download screen
- Windows version (needs a Windows tester)
- Light theme

## License

No license has been chosen yet; all rights reserved by the author until one is added.
