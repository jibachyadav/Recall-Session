# Recall-Session: the complete project guide

This is the "everything in one place" document. If you come back to this project after months, read this first.
It explains **why** the app exists, **what** it does, **how** it works inside, **which technologies** it uses and
why, **how it is built and released**, what went wrong along the way, and what is still open.

> Short and simple version with ready answers to common questions: [EXPLAIN-SIMPLY.md](EXPLAIN-SIMPLY.md).
>
> Written 2026-10-17, for version 0.1.2. Where something has not been tested, this guide says so.

## Contents

1. [Why this project exists](#1-why-this-project-exists)
2. [What the app does](#2-what-the-app-does)
3. [How it works, step by step](#3-how-it-works-step-by-step)
4. [Technologies used, and why](#4-technologies-used-and-why)
5. [Code map: what each file does](#5-code-map-what-each-file-does)
6. [Where data is stored](#6-where-data-is-stored)
7. [Important design decisions](#7-important-design-decisions)
8. [Languages: English, Nepali, Hindi](#8-languages-english-nepali-hindi)
9. [The AI: Claude, free local AI, offline](#9-the-ai-claude-free-local-ai-offline)
10. [Linux and Windows differences](#10-linux-and-windows-differences)
11. [How the app is built and released](#11-how-the-app-is-built-and-released)
12. [Running, developing and testing](#12-running-developing-and-testing)
13. [Settings you can change (config.py)](#13-settings-you-can-change-configpy)
14. [Problems we hit and how we fixed them](#14-problems-we-hit-and-how-we-fixed-them)
15. [Honest status and known limits](#15-honest-status-and-known-limits)
16. [Privacy, security and legal notes](#16-privacy-security-and-legal-notes)
17. [Roadmap](#17-roadmap)
18. [Troubleshooting](#18-troubleshooting)
19. [Command cheat sheet](#19-command-cheat-sheet)
20. [Glossary](#20-glossary)
21. [Project timeline](#21-project-timeline)

---

## 1. Why this project exists

**The problem.** The author attends online classes (Zoom, Teams, Meet) and watches YouTube lectures. English is not the
first language of the teachers they hear, so some parts are hard to follow in real time. Rewatching a whole lecture to
find the one confusing minute wastes time.

**The idea.** Record the class, keep a live transcript on screen, let the student press one button at a confusing
moment ("Flag"), and afterwards give them clean notes: a summary, the full transcript with the flagged moments and the
teacher's stressed points highlighted, and answers to questions.

**The goals, in the author's own priorities:**

1. Works on a normal laptop, without paying for anything (speech recognition runs locally, AI has free fallbacks).
2. Other people can install it from a download link (not just run it from source).
3. Looks clean and genuine, not like a generated dashboard.
4. A portfolio project that shows speech-to-text, LLM pipelines, desktop UI and release engineering.

**What it is not.** It is not a web app, not a phone app, and not a Zoom plugin. It listens to the sound your computer
plays and your microphone, so it works with any meeting app or video without being part of it.

## 2. What the app does

Three ways to start (the buttons on the home screen):

| Button | What it records | Needs |
|---|---|---|
| **Record a live class** | the teacher's sound + your microphone, mixed | an online call must be running (Zoom/Teams/Meet) |
| **Record a video** | whatever the computer is playing (YouTube, any video) | nothing |
| **Add a document** | nothing is recorded: a PDF, Word or text file is summarized | nothing |

While recording (a narrow panel on the right side of the screen):

- a **live transcript** appears as people speak: first a grey rough draft, then the accurate text replaces it;
- the **Flag** button (or the `f` key) marks "I don't understand" and silently saves a screenshot;
- an **Ask** tab suggests questions to ask the teacher, notices when the teacher asks *you* something and suggests an
  answer, and has an "Ask anything" box;
- a warning appears 5 minutes before the 2-hour recording limit; at the limit the app stops by itself.

After stopping (a result screen with tabs):

- **Summary**: key terms, main points, things to review;
- **Full transcript**: flowing paragraphs, flagged moments in yellow, stressed/important sentences in green;
- **Original (Nepali/Hindi)**: what was actually said, for those languages;
- **Flagged**: the list of flag times.

Also: local **accounts** (each person's sessions are private to them), a **library** with search and filters, select-all
and delete (to the Trash), an **Account** page (change password, API key, delete account), and a first-run screen.

## 3. How it works, step by step

### 3.1 Recording a live class or video

```
 You press "Record a live class"
        |
        v
 [call check]  Linux: pw-dump finds a program using mic AND speakers.   (src/quiet.py: call_running)
               Windows: the registry says which program uses the mic.   (src/osdep.py)
        |  no call -> wait up to 30 s, then say "no online class found"
        v
 [recorder]    Linux: one ffmpeg process mixes system sound + mic       (src/record.py)
               Windows: Python mixes loopback + mic                     (src/record_win.py)
        |   writes recording.wav (16 kHz mono)  AND  streams the same audio to the live transcriber
        v
 [live transcriber]  cuts the audio at pauses, runs Whisper twice (draft, accurate)   (src/live.py)
        |   -> events -> live panel shows text                                          (src/live_panel.py)
        v
 [Flag button]  saves the time + a screenshot (silent)                                 (src/hotkey_logger.py)
        v
 You press Stop
```

Key details:

- **One audio source of truth.** The same ffmpeg process writes the WAV file *and* feeds the live pipe, so the
  transcript and the saved recording can never drift apart.
- **Cutting at pauses.** Live audio is cut at a quiet moment (0.4 s pause) between 4 and 12 seconds, so words are never
  split in the middle (`LIVE_MIN/MAX_CHUNK_SECONDS`, `LIVE_PAUSE_SECONDS`).
- **Two passes.** A small fast model (`base`) shows a grey draft within about 2 seconds; the better model (`small`)
  replaces it a moment later. If the accurate pass falls more than 10 seconds behind, it is skipped so the screen
  never lags the audio.
- **Silent flags (GNOME).** GNOME plays a shutter sound and flashes the screen when a screenshot is taken. While
  recording, the app turns off two GNOME settings (event sounds, animations) and restores them afterwards, even after
  a crash (`src/quiet.py`).

### 3.2 After you press Stop

`process_session()` in `src/build_notes.py` runs the pipeline:

1. **Transcript.** For English, the live transcript is reused (instant). For Nepali/Hindi, the whole recording is
   transcribed again with the better model in its own language (see section 8).
2. **Summary.** Claude if available, else the free local AI, else a free offline summary (`src/summarize.py`,
   `src/free_summary.py`).
3. **Flag explanations** (Claude only): each flagged moment is explained using the transcript around it and the
   screenshot (`src/explain.py`).
4. **Important parts.** Claude picks sentences the teacher stresses; the free mode looks for cue phrases such as
   "this is important", "remember", "will be on the exam" (`src/important.py`).
5. **Notes.** Everything is stitched into `notes_final.md` (`build_notes()`).

If any AI step fails (no credit, no internet), the pipeline continues with the free version instead of stopping.

### 3.3 Documents

`src/documents.py`: read the file (PDF with the best of three readers, Word, text), clean up broken lines, then summarize.
Up to 5,000 words go to the AI in one call; longer documents are split into pieces of about 1,500 words and combined
(up to about 60,000 words). Order of preference: Claude, free local AI (`qwen2.5:3b`), offline summary.
The file picker uses the GNOME desktop portal on Linux and Tk's own dialog elsewhere (`src/filechooser.py`).

### 3.4 Accounts

`src/auth.py` and `src/auth_ui.py`: register (name optional, username, password of at least 8 characters), log in, "keep
me signed in", a recovery key shown once, change password, delete account. Passwords are never stored, only a salted
**scrypt** hash. Five wrong passwords in a row lock the account for 30 seconds. Each user's sessions live in their
own folder.

### 3.5 First run

`src/setup_ui.py` and `src/models.py`: if the speech models are not on the computer, a setup screen downloads them
with a progress bar. In the installers the English models are already inside, so this screen is skipped.

## 4. Technologies used, and why

| Technology | Used for | Why this one |
|---|---|---|
| **Python 3.12** | everything | fast to build, rich AI libraries |
| **Tkinter** (with `ttk`) | the whole window UI | ships with Python, no extra install, works on Linux and Windows. A custom dark theme is in `src/theme.py` |
| **faster-whisper** (CTranslate2) | speech to text, fully local | runs on an ordinary CPU, int8, no GPU, no internet, free |
| **Whisper models** `base`, `small`, `large-v3-turbo` | recognition quality levels | `base` for fast drafts, `small` for English, the big one for Nepali/Hindi |
| **Silero VAD** (inside faster-whisper, via onnxruntime) | skip silence | fewer wrong words in silent parts, faster |
| **ffmpeg** | Linux recording and mixing | one process can capture and mix several sources |
| **PipeWire / PulseAudio** (`pw-dump`) | Linux sound sources and call detection | the standard sound system on Ubuntu |
| **pyaudiowpatch** (WASAPI loopback) | Windows "what the speakers play" | ffmpeg on Windows cannot capture speaker output |
| **PyAV (`av`)** | read audio files; resample on Windows | bundles its own FFmpeg libraries. Pinned to `>=14,<17` because version 19 broke faster-whisper |
| **numpy** | audio buffers and mixing | standard |
| **Claude API** (`anthropic`) | best summaries, explanations, translation, questions | highest quality; optional |
| **Ollama** (`qwen2.5:1.5b`, `qwen2.5:3b`) | free local AI fallback | runs offline on a laptop |
| **pypdf, python-docx** | read PDF and Word | pure Python |
| **jeepney** (Linux) | talk to the GNOME file-chooser portal over D-Bus | the native chooser, without blocking the app |
| **send2trash** | delete to the Trash / Recycle Bin | recoverable deletes |
| **mss** (non-Linux) | screenshots on Windows | `gnome-screenshot` is the Linux tool |
| **gnome-screenshot** | Linux screenshots on Wayland | Wayland blocks simple screen capture |
| **hashlib.scrypt** | password hashing | standard library, strong |
| **PyInstaller** | bundle Python + libraries into a folder | one build recipe for Linux and Windows |
| **dpkg-deb** | make the `.deb` | standard Debian tool |
| **appimagetool** | make the AppImage | runs on any Linux |
| **Inno Setup** | the Windows `Setup.exe` | simple, reliable installer builder |
| **GitHub Actions** | builds on GitHub's Linux and Windows machines, publishes releases | free for public repos |
| **Git + GitHub** | version control, downloads | |

**Why not a database?** Everything is a folder of JSON and Markdown files. That is simple, easy to back up, and can be
opened by hand. A SQLite database would only be worth adding later if full-text search across sessions is wanted.

**Why local speech recognition?** It is free, private (audio never leaves the computer), and works offline. The
trade-off is speed and accuracy on weak laptops.

**Why Tkinter and not a web view or Qt?** Smallest dependency, and it ships with Python. The cost is a plainer look,
which `theme.py` works around.

## 5. Code map: what each file does

```
app.py                    launcher; "app.py --self-test" checks a packaged build
run.sh                    starts the app from the source folder
main.py                   the older command-line version (record / transcribe / explain / summarize / process)
config.py                 ALL settings in one place (models, limits, paths)
VERSION                   the release version number
requirements.txt          Python libraries (with platform rules)

src/app.py                the main window; every screen and the flow between them
src/dashboard.py          home screen: sidebar, start buttons, session list, search, delete
src/theme.py              colours, fonts, Markdown rendering for the dark theme
src/live_panel.py         the recording panel (live text, Flag, Stop, tabs)
src/ask_panel.py          the "Ask" tab (questions to ask, teacher's question, ask anything)
src/setup_ui.py           first-run model download screen
src/auth.py               accounts logic: hashing, login, lockout, recovery, remember-me
src/auth_ui.py            login / register / forgot password / account screens

src/record.py             Linux recorder (ffmpeg) and make_recorder() that picks the right one
src/record_win.py         Windows recorder (loopback + mic mixing)
src/live.py               live transcription: chunking, draft + accurate passes
src/transcribe.py         final transcription, language rules, model loading
src/models.py             which models exist, are they on this computer, download them
src/hotkey_logger.py      flags: time + screenshot
src/quiet.py              silence GNOME sounds/animations while recording; detect a running call (Linux)
src/osdep.py              everything that differs per OS (screenshots, trash, call detection, ffmpeg path)

src/build_notes.py        the after-class pipeline and the final notes file
src/summarize.py          whole-class summary (chunk, summarize, combine)
src/free_summary.py       offline summary with no AI
src/important.py          find the sentences the teacher stresses
src/explain.py            explain each flagged moment
src/translate.py          Nepali/Hindi to English with Claude
src/language.py           per-session language settings
src/assistant.py          live helper AI: Claude, then Ollama (questions, answers)
src/llm.py                the thin Claude wrapper
src/documents.py          read and summarize PDF / Word / text
src/filechooser.py        file picker (GNOME portal, zenity, Tk fallbacks)
src/settings.py           save/test/remove the Claude API key
src/sessions.py           read saved sessions for the home screen
src/transcript_view.py    paragraphs and highlight runs shared by the screens

packaging/                recall-session.spec (PyInstaller), make_icon.py, fetch_models.py,
                          linux/build.sh, windows/build.ps1 + recall-session.iss
.github/workflows/build.yml   the automatic build and release
assets/                   icon (svg, png, ico)
docs/                     this guide, screenshots, the original plan
```

About 4,900 lines of Python. The biggest files are `src/app.py` (screens), `dashboard.py` and `auth_ui.py`.

## 6. Where data is stored

**Your data is never inside the program folder.** It lives here:

| System | Folder |
|---|---|
| Linux | `~/.local/share/recall-session/` |
| Windows | `%APPDATA%\Recall-Session\` |
| any | set the environment variable `RECALL_SESSION_DATA` to use another folder (used by tests) |

```
recall-session/
  users.json                accounts (password hashes only)
  .remember                 "keep me signed in" token
  .env                      the optional Claude API key (file permissions 600)
  sessions/<user id>/<date>_<name>/
      recording.wav         the audio
      session.json          type, title, spoken language, english_source, live_complete, ...
      transcript_live.json  text made live
      transcript_final.json English text used by summaries (or original text if no English yet)
      transcript_original.json   Nepali/Hindi text as spoken
      confusion_log.json    flags: [{timestamp, screenshot}]
      screenshots/          one picture per flag
      important.json        which transcript segments are stressed
      summary.md            the summary
      explanations.json     explanations of flagged moments
      qa.json               suggested questions and answers
      notes_final.md        everything together
```

Speech models are stored in the normal Hugging Face cache (`~/.cache/huggingface`), or inside the installed app
(`models/` folder) for the English ones.

**Safety rules we follow** (see section 14, the data-loss incident): the code never deletes user data without a
copy; moving old data copies, verifies the copy, and only then moves the originals into `migrated-backup/`; tests run
against a throwaway folder, never the real one.

## 7. Important design decisions

| Decision | Why |
|---|---|
| Record **audio**, not video | Wayland blocks simple screen recording; a screenshot at each flag gives the screen context |
| One ffmpeg process for file **and** live pipe | transcript and recording cannot drift apart |
| Mix teacher sound + mic with `amix` | students ask questions too, and both should appear in the transcript |
| Cut live audio at **pauses** | cutting mid-word creates wrong words |
| **Draft then accurate** live text | text appears fast, then gets corrected |
| Live model `small`, not `base` | measured: keeps up (about 0.3x real time) and is more accurate |
| Reuse the live transcript as the final one (English) | notes are ready seconds after Stop |
| Live session requires a running call | stops people accidentally recording while idle; YouTube uses the video button |
| Call = one program using mic **and** speakers (Linux) | a YouTube video only plays sound; a phone call next to the laptop is not an app |
| Silence GNOME sounds, restore after | no shutter noise or flash while flagging, and never leave the user's settings changed |
| Claude optional, with two free fallbacks | the app is useful with no money spent |
| Local accounts, scrypt, lockout | several people can share one computer privately; no server needed |
| Data in a per-user folder outside the program | installing or updating the app never touches your sessions |
| Models downloaded or bundled, not in git | they are hundreds of MB |
| English models inside the installers | one download, then it works, even offline |
| Fixed download file names | one link that never changes |
| PyInstaller folder build | works the same on Linux and Windows |
| A `--self-test` flag | CI can prove a packaged build is complete without opening a window |

## 8. Languages: English, Nepali, Hindi

When naming a session you choose the spoken language: Auto, English, Nepali or Hindi.

- **English:** `small` model; the live transcript is reused as the final one.
- **Nepali / Hindi:** the live panel does not show Nepali. After you press Stop, the full recording is transcribed in
  its own language and saved as `transcript_original.json`. Nepali uses the big `large-v3-turbo` model because `small`
  was unusable (about 100% word errors in our test).
- **English version of Nepali/Hindi is optional.** With a Claude key it is translated by Claude
  (`src/translate.py`, better quality). Without one, a "Rough English (offline)" button makes Whisper's own
  translation. That is clearly labelled, because for Nepali it often invents text.
- **Summaries and highlights wait for an English version.** The `english_source` field says where the English came
  from: `None` (it was English), `"claude"`, `"whisper"` or `"none"`.
- **Speed.** The big model is slow on a weak laptop. Settings were tuned (batch 4, beam 1: 15% faster, 22% less
  memory, same accuracy on our test) and the app shows an estimated waiting time. Closing other programs helps a lot.

**Measured accuracy (3-minute Nepali samples from the FLEURS dataset):** the big model had roughly 40–50% word errors
in careful mode and about 67% in the fast mode; `small` about 100%. Nepali is genuinely hard for Whisper. The app is
honest about this in the interface and in the README.

## 9. The AI: Claude, free local AI, offline

```
 ask for something (summary, questions, answer...)
        |
        |-- Claude works?  (key present, has credit, internet)  -> use Claude
        |
        |-- else Ollama running with the model?  -> use the free local AI
        |        qwen2.5:1.5b for live Ask (fast)
        |        qwen2.5:3b for documents (more accurate)
        |
        '-- else: offline extractive summary (picks key sentences; no AI)
```

- The key is typed into the Account page and stored in the data folder's `.env` with permission 600. It is never shown
  back on screen. "Test key" explains failures in plain words.
- Claude is pay-as-you-go; check Anthropic's pricing page for current prices. The key test during development failed with
  "credit balance too low", so **Claude features were only tested with fake responses**, not with real output.
- If Claude fails once during a run, the app stops trying it for that run and uses the free path.

## 10. Linux and Windows differences

| Part | Linux | Windows |
|---|---|---|
| Recording | `ffmpeg -f pulse` mixing system monitor + mic | `pyaudiowpatch` WASAPI loopback + mic, mixed in Python (`record_win.py`) |
| Call detection | `pw-dump`: a program with mic input and speaker output | registry: a program using the microphone (less precise) |
| Screenshots | `gnome-screenshot` (also `grim`, `scrot`) | `mss` |
| File picker | GNOME portal via D-Bus, then zenity, then Tk | Tk's own dialog |
| Quiet flagging | switches off GNOME sounds/animations | not needed / not done |
| Installer | `.deb`, AppImage, tar.gz | `Setup.exe` (Inno Setup), zip |
| Needs installed | `ffmpeg`, `gnome-screenshot`, `pipewire-bin` | nothing extra |
| Tested | yes, on Ubuntu/GNOME/Wayland | **builds in CI; never run on a real PC** |

All OS-specific code is kept in `src/osdep.py`, `src/record.py`/`record_win.py` and `src/quiet.py`, so the rest of the app
does not care which system it runs on.

## 11. How the app is built and released

### 11.1 The big picture

```
 you change code
      |  git commit, git push main
      v
 GitHub Actions runs "Build installers"  (.github/workflows/build.yml)
      |-- linux job   (Ubuntu 22.04): packaging/linux/build.sh   -> .deb, AppImage, tar.gz
      '-- windows job (Windows):      packaging/windows/build.ps1 -> Setup.exe, zip
      |
 you push a tag like v0.1.3
      v
 the same build runs, then the "release" job publishes a GitHub Release with all files attached
      v
 people open  github.com/jibachyadav/Recall-Session/releases/latest
```

### 11.2 What the build scripts do

1. Make a clean virtual environment and install `requirements.txt` plus PyInstaller.
2. `make_icon.py` draws the icon (png and ico) with plain numpy, no image tools needed.
3. `fetch_models.py` downloads the English models (`base`, `small`) into `packaging/models/`.
4. **PyInstaller** (`packaging/recall-session.spec`) bundles Python, all libraries and the models into one folder.
   It collects the data files of faster-whisper, ctranslate2, av, onnxruntime, tokenizers and certifi.
5. **Self-test:** the built program is run with `--self-test`. It loads every library, finds the voice-detector file,
   loads a model and transcribes one second of silence. If this fails, the build fails.
6. Linux: build the `.deb` (`dpkg-deb`), the AppImage (`appimagetool`) and a tarball.
   Windows: zip the folder and build `Setup.exe` with Inno Setup (`recall-session.iss`).

### 11.3 Making a new release (the routine)

```bash
# 1. make and test your change, commit it
# 2. raise the number in VERSION (for example 0.1.3)
git add -A && git commit -m "describe the change"
git push origin main            # wait for the "Build installers" run to turn green
git tag v0.1.3
git push origin v0.1.3          # the build runs again and publishes the release
```

Check the result at https://github.com/jibachyadav/Recall-Session/releases/latest.

### 11.4 Things learned about releasing

- GitHub's `/releases/latest` link **ignores releases marked "pre-release"**. We first marked v0.1.1 as a pre-release, so
  the fixed links returned 404. v0.1.2 is a normal release, and the links work.
- Download file names have **no version number** (`Recall-Session-Setup.exe`), so
  `releases/latest/download/<name>` never changes. The version lives in the release tag.
- Ubuntu's double-click on a `.deb` often opens the Archive Manager, not the installer. The README gives the terminal
  command first (`sudo apt install ./recall-session_amd64.deb`).
- Windows shows "Windows protected your PC" because the installer is not signed. Signing needs a paid certificate.
- The packages are large (about 650–750 MB) because the English models are inside. The code itself is about 120–180 MB.

### 11.5 Build outputs are not in git

`.gitignore` excludes `build-linux/`, `dist-packages/`, `packaging/models/`, `.venv/`, `.env`, sessions and recordings.
The installers reach people only through GitHub Releases.

## 12. Running, developing and testing

**Run from the source folder (Linux):**

```bash
cd ~/Documents/Recall-Class
./run.sh                        # same as: .venv/bin/python app.py
```

**First-time set-up on a new machine:**

```bash
sudo apt install python3-venv python3-tk ffmpeg gnome-screenshot pipewire-bin
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**The command-line version:** `main.py` has `record`, `transcribe`, `explain`, `summarize`, `process`. It needs a
remembered login once accounts exist.

**How we tested.** There is **no automated test suite** (a gap, see the roadmap). Testing was done by hand with care:

- **Sandboxes.** Tests set `RECALL_SESSION_DATA` to a throwaway folder (and use a copy of the program folder when
  needed). **Never test against the real data folder** (see section 14).
- **`pyflakes`** (`.venv/bin/python -m pyflakes src`) finds undefined names before they crash the app.
- **Real speech samples.** Nepali and Hindi were tested with the FLEURS dataset.
- **Memory limit.** `systemd-run --user --scope -p MemoryMax=3500M -p MemorySwapMax=0 ...` caps a test so it cannot freeze the laptop.
- **Fake sound sources.** The Windows mixer was tested on Linux with fake sources and a fake clock.
- **Packaged-build checks.** `--self-test`, an empty model cache with no internet (proves the models are bundled), and
  screenshots of the packaged window.
- **README screenshots** are made by a script that builds sample sessions in a sandbox and photographs the real windows.

## 13. Settings you can change (config.py)

| Setting | Default | Meaning |
|---|---|---|
| `WHISPER_MODEL` | `small` | model for final English transcription |
| `LIVE_WHISPER_MODEL` | `small` | accurate live pass |
| `LIVE_DRAFT_MODEL` | `base` | fast live draft |
| `LIVE_MIN/MAX_CHUNK_SECONDS` | 4 / 12 | how long a live chunk is |
| `LIVE_PAUSE_SECONDS` | 0.4 | pause length that counts as a place to cut |
| `LIVE_MAX_LAG_SECONDS` | 10 | skip the accurate pass if this far behind |
| `MAX_RECORDING_SECONDS` | 2 hours | recording limit |
| `RECORDING_WARNING_SECONDS` | 5 minutes | warning before the limit |
| `LIVE_REQUIRE_CALL` | True | live sessions need a running call |
| `LIVE_WAIT_SECONDS` | 30 | how long to wait for a call |
| `USE_LIVE_TRANSCRIPT` | True | reuse the live text as the final one (English) |
| `FINAL_MODEL_FOR` | `{"ne": "large-v3-turbo"}` | bigger model per language |
| `LARGE_MODEL_BATCH_SIZE` / `BEAM_SIZE` | 4 / 1 | speed settings for big models |
| `OLLAMA_MODEL` / `DOCUMENT_MODEL` | `qwen2.5:1.5b` / `qwen2.5:3b` | free local AI |
| `CLAUDE_MODEL` | `claude-sonnet-5-5` | Claude model used |
| `PARAGRAPH_WORDS` / `GAP_SECONDS` | 60 / 2.0 | paragraph layout in transcripts |
| `FLAG_HIGHLIGHT_BEFORE/AFTER` | 10 s / 2 s | how much speech a flag highlights |

## 14. Problems we hit and how we fixed them

| Problem | What happened | Fix / lesson |
|---|---|---|
| **Data loss** | A test command with `rm -rf` deleted some of the user's real sessions. | Data moved to its own folder; safe migration (copy, verify, move to backup, never delete); every test uses a sandbox for both the data and program folders; a standing rule never to test on real data. The two lost documents were rebuilt. |
| **`av` 19 broke transcription** | faster-whisper 1.2.1 failed with the newest `av`. | Pinned `av>=14,<17`. |
| **Nepali unusable** | `small` model gave about 100% word errors. | Use the big model for Nepali; keep the original text; make English optional and clearly labelled. |
| **Transcription very slow** | The laptop ran out of memory with the big model. | Smaller batch, faster search, a visible time estimate, advice to close other programs. |
| **Account screen crash** | "Continue" read text boxes that had already been destroyed. | Read the values before switching pages. |
| **File chooser opened only once** | The D-Bus reply was never read. | Rewrote it with one live jeepney connection per request; verified by cancelling three times in the real dialog. |
| **Shutter sound / flash on flag** | GNOME does this for every screenshot. | Switch off two GNOME settings while recording, restore after, even after a crash. |
| **Dashboard looked "AI-generated"** | Cards and many colours. | Rebuilt as a plain library: sidebar, list, three visible start buttons. |
| **Claude key rejected** | "credit balance too low". | Claude features tested with fakes only; the free fallbacks make the app usable. |
| **A key pasted in chat** | The API key was shared in plain text. | Stored in `.env`, and the user was told to rotate it. **Still to do.** |
| **Latest-download links 404** | The release was a pre-release. | Publish normal releases. |
| **Double-click on `.deb`** | Opened the Archive Manager. | README says to use the terminal command. |
| **My own `pkill` killed my shell** | A test command matched its own text. | Use exact process IDs. (Test-only mistake.) |

## 15. Honest status and known limits

**Works and was tested:** Linux recording (live class and video), live transcript, flags with screenshots, highlights,
summaries (free paths), the Ask tab (free local AI), documents, accounts, English transcription, Nepali/Hindi
transcription in the original language, the Linux packages, the first-run screen, the bundled models (tested with an
empty cache and no internet), and the GitHub release pipeline.

**Built but not proven:**

- **Windows** recording, call detection and the installer. The mixing logic was tested with fake sources; the sound-card
  code and the real install have never run on a Windows PC. Treat it as a beta.
- **Claude-powered output** (translation, summaries, explanations): only tested with fake responses.
- **A real `apt install` of the `.deb`** on a clean Ubuntu (the unpacked package and the AppImage were tested).

**Limits:**

- Nepali accuracy is modest (section 8).
- The live panel needs a reasonably fast computer; weak laptops may lag.
- Call detection on Windows is less precise (microphone use only).
- Only Linux with PipeWire and GNOME is fully supported; other desktops may miss screenshots or call detection.
- No automatic tests, no code signing, no auto-update, light theme missing.
- Packages are large.

## 16. Privacy, security and legal notes

- **Audio and transcripts stay on the computer.** Nothing is uploaded unless a Claude key is added; then only text
  (transcript, document text, screenshots of flagged moments) is sent to Claude when an AI feature is used.
- **Consent.** Recording a call may need the other people's permission where you live. Tell the teacher or class,
  and follow the school's rules. The README says so.
- **Passwords:** salted scrypt hashes, lockout after five failures, recovery key. The API key file has permission 600.
- **Secrets never go into git:** `.env`, accounts, recordings and sessions are in `.gitignore`. The repository was
  scanned for keys before each push.
- **The exposed key:** rotate the key that was pasted into a chat early in the project.
- **License:** none chosen yet, so by default all rights are reserved. Add one (MIT is common) if others may reuse the code.

## 17. Roadmap

Most useful next:

1. A friend tests the **Windows** installer on a real PC; fix what breaks.
2. **Rotate the API key** and test Claude features with a funded key.
3. Add a **license** (MIT).
4. Add **automated tests** (accounts, transcript layout, the mixer, session reading).
5. **Smaller packages** (trim unused libraries, optional model download).

Later: light theme, code signing for Windows, auto-update, a tidy settings page, macOS, search across sessions
(SQLite), an invite-link that opens the app, a live-recording screenshot in the README, better Nepali.

## 18. Troubleshooting

| Symptom | Likely cause and fix |
|---|---|
| "No online class found" | Join the call first: it must use the microphone and play sound. For a video use **Record a video**. |
| Nothing transcribes / silence | Wrong sound source. On Linux check the default output and microphone in Sound settings. |
| Nepali takes very long | Big model on a weak laptop. Close other programs; the app shows an estimate. |
| "Something is missing" at start | Install `ffmpeg`, `gnome-screenshot`, `pipewire-bin` (`sudo apt install ...`). |
| Summary looks basic | No Claude key or no credit: this is the free offline summary. Add a key on the Account page. |
| Claude key "doesn't work" | The Account page's test explains: wrong key, no credit, or no internet. |
| First-run download fails | Check the internet connection and click **Try again**. |
| Windows "protected your PC" | Click **More info**, then **Run anyway** (the installer is unsigned). |
| Forgot password | Use "Forgot password" with the recovery key shown at registration. |
| App won't open | Run it from a terminal and read the text it prints. |
| Sounds off after a crash | The app restores them at the next start; or run `gsettings set org.gnome.desktop.sound event-sounds true`. |

## 19. Command cheat sheet

```bash
./run.sh                                         # start the app from the source folder
.venv/bin/python app.py --self-test              # check the libraries and a model
.venv/bin/python -m pyflakes src                 # find undefined names
.venv/bin/python packaging/make_icon.py          # redraw the icons
.venv/bin/python packaging/fetch_models.py       # download the bundled English models
packaging/linux/build.sh                         # build .deb, AppImage, tar.gz into dist-packages/
powershell -File packaging\windows\build.ps1     # on Windows: build Setup.exe and zip
RECALL_SESSION_DATA=/tmp/trial ./run.sh          # run with a separate empty data folder (safe trial)
git tag v0.1.3 && git push origin v0.1.3         # publish a release (after raising VERSION)
```

## 20. Glossary

- **Whisper / faster-whisper:** the speech-recognition model, and a fast CPU version of it.
- **int8:** a smaller number format that makes the model faster and lighter, with a tiny loss of accuracy.
- **VAD (voice activity detection):** skips silent parts of the audio.
- **WAV:** a simple uncompressed audio file.
- **16 kHz mono:** the audio format Whisper expects (16,000 samples per second, one channel).
- **ffmpeg:** a program that records, mixes and converts audio and video.
- **PipeWire / PulseAudio:** the Linux sound system.
- **WASAPI loopback:** the Windows way to record what the speakers are playing.
- **Wayland / GNOME:** the Linux display system and desktop of Ubuntu.
- **D-Bus / portal:** how a Linux program asks the desktop to show a file chooser.
- **Tkinter:** Python's built-in window toolkit.
- **LLM:** large language model (Claude, Qwen).
- **Claude API:** the paid service the app can use for better AI output.
- **Ollama:** a program that runs free AI models on your own computer.
- **scrypt:** a deliberately slow password-hashing method.
- **PyInstaller:** packs a Python program and its libraries so it runs without Python installed.
- **.deb / AppImage / Setup.exe:** installer formats for Debian-Ubuntu, any Linux, and Windows.
- **Inno Setup:** a tool that builds Windows installers.
- **CI / GitHub Actions:** servers that build and test your code automatically on every push.
- **Tag / release:** a named version of the code; GitHub attaches the downloads to it.
- **Pre-release:** a release marked "not final"; the "latest" link skips it.
- **Sandbox:** a throwaway folder used for testing so real data is never touched.

## 21. Project timeline

| Date | What happened |
|---|---|
| 2026-10-14 | Idea and plan (record, flag, explain); first steps: recording, flags, live panel, Whisper, summary |
| 2026-10-15 | Dashboard, live-session call gate, Ask tab, documents, accounts, data moved to its own folder after the data-loss incident; first git commit and push; Nepali/Hindi support |
| 2026-10-16 | Library-style home screen, faster Nepali/Hindi, README; first-run model screen; Linux packages; Windows code and CI; public release v0.1.0 |
| 2026-10-17 | Models bundled into installers (v0.1.1), fixed latest-download links (v0.1.2), README install fixes, this guide |

The original plan from the first day is kept in [original-plan.md](original-plan.md) for history. Parts of it were
changed on the way (the app is now a full desktop app, not a command-line tool).
