# Recall-Session: Project Plan

2026-10-14

## What we are building

Recall-Session is a Python tool that records a class and lets you press one key whenever you are confused. Afterward it explains only those moments, not the whole lecture.

The flow:

1. Start a session before class; the tool records the audio.
2. Press a key at any moment you don't understand; it logs the timestamp and grabs a screenshot.
3. Stop recording; the tool transcribes the audio.
4. For each flagged moment, an LLM explains it using the transcript around it and the screenshot.
5. You get one notes file per class: a whole-class summary on top, your flagged moments with explanations below.

## Why

Students lose time rewatching whole lectures to find the one part they missed. This tool turns that into a short, targeted review.

- **Real use:** it is built for the author's own classes, online lectures and YouTube.
- **Less rewatching:** only flagged moments get explained, with the exact transcript and slide or code on screen.
- **Portfolio value:** it covers speech-to-text, vision and LLM pipelines in one project with a clear demo story.

## Features

v1 covers record, flag, a live side panel, transcribe, explain and summarize.

| Stage | v1 | Later |
| --- | --- | --- |
| Recording | Start/stop audio recording of any source (YouTube, Zoom, Meet, lecture files) | Auto-start when a class app or tab is active |
| During class | Side panel on the right of the screen shows what is being taught live (rolling transcript plus "now covering: X" summary); a button or key flags "I didn't understand" and saves a screenshot | Global hotkey; auto-detect class start |
| After class | Full timestamped transcript; whole-class summary; explanation per flagged moment | Chat with your notes ("what did she say about X?") |
| Storage | One folder per class: audio, log, transcript, screenshots, notes | Search by date or class; multi-class dashboard |

## How it works

```
During class
  Record audio (ffmpeg) ──────────────┐
  Flag key (timestamp + screenshot) ──┼──┐
                                      │  │
After class                           ▼  │
  Transcribe (faster-whisper) ──┬─> Explain each flag (Claude + screenshot) <┘
                                │            │
                                └─> Summarize class (chunked, then combined)
                                             │
                                             ▼
                                       notes_final.md
```

During class only two things run: audio recording and the flag key. Everything else, from transcript to notes, is built after you stop. The tool records audio rather than video because Wayland blocks simple screen capture; a screenshot at each flag gives the same on-screen context.

## Tech stack and folders

Everything is Python, with local folders and JSON/markdown files instead of a database.

- **ffmpeg:** records audio.
- **gnome-screenshot:** captures the screen at each flag (this machine runs GNOME on Wayland).
- **faster-whisper:** local, offline transcription.
- **Claude API:** explanations and summaries; accepts the screenshot as an image.

```
Recall-Class/
  main.py              # entry point: record -> stop -> process -> build notes
  config.py            # model names, keys, window sizes, audio source
  requirements.txt
  src/
    record.py          # ffmpeg audio recording
    hotkey_logger.py   # flag key, timestamps, screenshots
    live_panel.py      # right-side window: live transcript, summary, Flag button
    transcribe.py      # faster-whisper wrapper
    explain.py         # flagged moment -> LLM explanation
    summarize.py       # transcript -> chunked summary
    build_notes.py     # stitches the final markdown
    utils.py
  sessions/
    2026-10-14_data-structures/
      recording.wav
      confusion_log.json
      transcript_final.json
      screenshots/
      summary.md
      notes_final.md
```

## Build plan

We build one step at a time. Each step is tested and approved before the next starts.

1. **Project setup:** folders, virtual environment, `config.py`. *Test:* `python main.py` runs without errors.
2. **Recorder:** ffmpeg starts and stops audio capture. *Test:* record 1 minute and play it back.
3. **Flag key and screenshots:** pressing `f` logs a timestamp and saves a screenshot. *Test:* press 3 times; check `confusion_log.json` and the images.
4. **Transcription:** faster-whisper produces timestamped segments. *Test:* transcribe the 1-minute recording.
5. **Live side panel:** a window docked on the right shows a rolling transcript (audio transcribed in 5-10 second chunks in a background thread), a "now covering" summary, and a Flag button. *Test:* speak or play a video and watch the panel update within about 10 seconds.
6. **Explainer:** flagged timestamp plus nearby transcript plus screenshot goes to Claude. *Test:* explain the 3 flags.
7. **Whole-class summary:** chunk the transcript, summarize each chunk, then combine. *Test:* run on the same recording.
8. **Notes builder:** one `notes_final.md` per session. *Test:* a full end-to-end run on a real class.
9. **Later:** global hotkey, auto-start, search and dashboard.

## Open decisions and risks

- [ ] **LLM provider:** Claude or GPT for explanations? The plan assumes Claude.
- [ ] **Audio source:** microphone only, or system audio (a `.monitor` source) for YouTube and Zoom?
- [ ] **Live panel toolkit:** Tkinter (built in, simple) or PyQt (nicer, extra install)? Wayland may not let the window pin itself to the right edge, so it may need to be placed by hand once.
- [ ] **Flag key:** a terminal key works only while the terminal has focus. A global hotkey needs a GNOME custom shortcut because Wayland blocks global key listeners.
- [ ] **Audio only vs. video:** v1 skips video and takes screenshots live. Say so if you want full screen recording.
- [ ] **Cost and speed:** the Whisper model size (`small` assumed) trades accuracy for speed on CPU; LLM calls need an API key and cost money.
