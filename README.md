# Recall-Session

A desktop app that listens to your online classes and videos, keeps a live transcript, and turns each session into
clear notes. It runs on your own computer: speech recognition is local, and the AI parts work without paying for anything.

> **Status:** works on Linux (Ubuntu / GNOME / Wayland) and installs from a `.deb`, AppImage or tarball. A Windows version
> is written and builds an installer through GitHub Actions, but it has **not been tested on a real Windows computer yet**.

## Download

**[Get the latest version from the Releases page](https://github.com/jibachyadav/Recall-Session/releases/latest)**

| Your computer | Download |
|---|---|
| Windows | [Recall-Session-0.1.0-Setup.exe](https://github.com/jibachyadav/Recall-Session/releases/download/v0.1.0/Recall-Session-0.1.0-Setup.exe) (beta, not tested on many PCs yet) |
| Ubuntu / Debian | [recall-session_0.1.0_amd64.deb](https://github.com/jibachyadav/Recall-Session/releases/download/v0.1.0/recall-session_0.1.0_amd64.deb) |
| Any Linux | [Recall-Session-0.1.0-x86_64.AppImage](https://github.com/jibachyadav/Recall-Session/releases/download/v0.1.0/Recall-Session-0.1.0-x86_64.AppImage) |

Install steps are under [Install](#install) below.

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

## Install

**Linux (easiest):** download from the Releases page and use one of:

```bash
sudo apt install ./recall-session_0.1.0_amd64.deb          # adds it to your app menu and installs ffmpeg etc.
# or, with no install:
chmod +x Recall-Session-0.1.0-x86_64.AppImage && ./Recall-Session-0.1.0-x86_64.AppImage
```

The AppImage and tarball need `ffmpeg`, `gnome-screenshot` and `pipewire-bin` already installed
(`sudo apt install ffmpeg gnome-screenshot pipewire-bin`); the app tells you if something is missing.

**Windows:** run `Recall-Session-0.1.0-Setup.exe` (untested, see the status above). Online classes are detected by
a program using your microphone, and the class sound is captured with WASAPI loopback.

**First run:** the app shows a one-time screen that downloads the speech models (about 630 MB for English, plus an
optional 1.6 GB for Nepali/Hindi). After that, transcription works offline.

### Run from source (Linux)

```bash
sudo apt install python3-venv python3-tk ffmpeg gnome-screenshot pipewire-bin
git clone https://github.com/jibachyadav/Recall-Session.git
cd Recall-Session
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
./run.sh
```

Optional free local AI:

```bash
# install Ollama from https://ollama.com, then:
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:3b
```

### Build the installers yourself

```bash
packaging/linux/build.sh                       # .deb + AppImage + tar.gz into dist-packages/
powershell -File packaging\windows\build.ps1   # on Windows: Setup.exe + zip (needs Inno Setup)
```

GitHub Actions (`.github/workflows/build.yml`) builds both on every push; pushing a tag such as `v0.1.0` also
publishes a GitHub Release with the downloads attached. `app.py --self-test` checks that a built package is complete.

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
src/record_win.py   Windows recording (speakers + microphone)
src/models.py       speech-model download (first-run screen: src/setup_ui.py)
packaging/          PyInstaller recipe, Linux and Windows build scripts
```

## Privacy and consent

Recording a call may need the other people's consent where you live. Tell your teacher or classmates before recording,
and follow your school's rules.

## Roadmap

- Test the Windows version on a real Windows computer (recording, call detection, installer)
- Smaller packages (they are about 120-160 MB before the models)
- Light theme

## License

No license has been chosen yet; all rights reserved by the author until one is added.
