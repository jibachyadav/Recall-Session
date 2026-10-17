# Recall-Session explained simply

Use this when someone asks: *"What did you build? How? Why?"* Everything here is short and in plain words.
For the full detail, see the [complete guide](GUIDE.md).

---

## The 30-second answer

> "Recall-Session is a desktop app that listens to online classes and videos. It writes a live transcript, lets me press a
> button when I don't understand something, and afterwards gives me a summary and notes. The speech recognition runs on
> my own computer, so it's free and private. I also built installers for Linux and Windows, and a pipeline that builds
> and publishes them automatically."

## The 2-minute answer

**The problem.** I watch online classes where some speakers are hard for me to follow. Rewatching a whole lecture to find
one confusing minute wastes time.

**The solution.** My app records the sound of the class and my microphone. While the class runs, it shows what is being
said as text. If I'm lost, I press **Flag**; it saves the time and a screenshot. When I stop, it gives me a summary, the
full transcript with my flags and the teacher's important sentences highlighted, and suggested questions.

**How it works inside.** Sound is recorded with ffmpeg. A speech model called Whisper turns the sound into text, running on
my own CPU. For smart tasks (summaries, questions) it uses the Claude AI if I add a key; if not, it uses a free AI on my
computer; if that is missing, it uses a simple method with no AI. So it always works.

**Then I made it shareable.** I packaged it into installers (a `.deb` and AppImage for Linux, a Setup.exe for Windows).
GitHub builds them automatically and puts them on a download page.

## The whole app in one picture

```
 class sound + my mic
        |
     ffmpeg  ----------------->  recording.wav (saved)
        |
        +--> Whisper (speech to text) --> live text on screen
                                              |
 I press Flag --> time + screenshot saved     |
                                              v
 I press Stop --> summary + highlights + notes (Claude, or free AI, or offline)
```

## Words you may need, in simple terms

| Word | Simple meaning |
|---|---|
| **Whisper** | a free model that turns speech into text |
| **faster-whisper** | a faster version that runs on a normal laptop CPU |
| **ffmpeg** | a program that records and mixes sound |
| **Claude** | a paid AI that writes very good summaries (optional) |
| **Ollama** | a program that runs a free AI on my own computer |
| **Tkinter** | Python's built-in tool for windows and buttons |
| **PyInstaller** | packs my program so people don't need Python |
| **GitHub Actions** | GitHub's computers that build my installers for me |
| **Release** | a version on GitHub with download files attached |

## Questions and answers

### About the idea

**Why did you build it?**
To save time. I can flag the confusing moments live and review only those, instead of rewatching whole lectures.

**Who is it for?**
Students who follow online classes or YouTube lectures, especially when the speaker is hard to understand.

**How is it different from Zoom's own transcript?**
It works with *any* app or video, not just one. It records my microphone too, lets me flag moments, highlights what the
teacher stresses, and keeps everything on my own computer.

**Does it work during a real Zoom call?**
Yes on Linux, where I tested it: it records the sound the computer plays plus my microphone. It does not join the call.

### About how it works

**How does it get the sound of the class?**
Linux: ffmpeg records the computer's output sound and the microphone together. Windows: a library captures "what the
speakers play" (WASAPI loopback) and I mix it with the microphone in Python.

**How does the live transcript work?**
The sound is cut at small pauses (so words aren't split). Each piece goes to Whisper. A fast small model shows a rough
grey draft within about 2 seconds, then a better model replaces it with the accurate text.

**What does "Flag" do?**
It saves the exact time and takes a screenshot, silently. Later, the transcript highlights that moment in yellow.

**How does it find the "important" sentences?**
With Claude it asks the AI which sentences the teacher stresses. Without Claude it looks for phrases like "this is
important", "remember" or "will be on the exam".

**How does it detect that a class is running?**
Linux: it asks the sound system which program is using the microphone *and* the speakers at the same time, which is what a
call looks like. Windows: it checks which program is using the microphone.

**How does it summarize a PDF?**
It reads the text, cleans broken lines, then sends it to the AI. Long documents are split into pieces, each piece is
summarized, and the summaries are combined.

**Where are my recordings stored?**
On my own computer, in a folder in my user account (`~/.local/share/recall-session` on Linux). Nothing is uploaded.

### About AI and cost

**Do I need to pay?**
No. Without a Claude key it uses a free local AI, or a simple offline summary. The key only makes the output better.

**What happens if Claude fails or runs out of credit?**
It switches to the free options for that run. The app never just stops.

**Why run Whisper locally instead of using an online service?**
It is free, private (the audio never leaves the computer) and works offline. The trade-off is that it is slower on a weak
laptop.

**Does it understand Nepali and Hindi?**
Yes, it transcribes them in their own language using a bigger model. The accuracy for Nepali is modest, because Whisper
is weak there. An English version is optional: Claude translates it well; the offline version is rough and labelled so.

### About the technology choices

**Why Python and Tkinter?**
Python has the best speech and AI libraries. Tkinter comes with Python, so there is nothing extra to install, and it works
on Linux and Windows.

**Why no database?**
Each class is a folder with JSON and Markdown files. It is simple and easy to back up. I would add SQLite only if I wanted
search across all sessions.

**How do you keep passwords safe?**
Passwords are never stored. Only a salted scrypt hash is saved. Five wrong tries lock the account for 30 seconds, and
there is a recovery key.

**Why record audio and not video?**
On Ubuntu's display system (Wayland) simple screen recording is blocked. A screenshot at each flag gives the same context
with much less data.

### About building and releasing

**How did you make installers?**
PyInstaller packs Python, all libraries and the speech models into a folder. Then I wrap that folder: `dpkg-deb` makes the
`.deb`, appimagetool makes the AppImage, and Inno Setup makes the Windows `Setup.exe`.

**What is GitHub Actions doing?**
Every time I push code, GitHub's Linux and Windows computers build the installers and check them. When I push a version
tag like `v0.1.2`, it also publishes a release with the files attached.

**How do people download it?**
From the Releases page. The file names have no version number, so one link always gives the newest version.

**Why are the downloads so big (about 700 MB)?**
Because the English speech models are inside, so the app works right after install, even without internet.

**How do you know the installer is not broken?**
The program has a `--self-test` option. The build runs it, and it checks that every library loads and that a model can
transcribe a second of silence. If it fails, the build fails. I also tested the models with no internet and an empty cache.

### About mistakes and honesty

**What went wrong while building?**
- A test command deleted some of my real sessions. I fixed it by moving data to its own folder, adding a safe copy-first
  migration, and testing only in throwaway folders from then on.
- A new version of a library (`av`) broke transcription, so I pinned the working version.
- My release was marked "pre-release", so the "latest" download link gave an error. I changed it to a normal release.
- The Nepali model was too slow and too wrong at first, so I used a bigger model and made the English version optional.

**What is not finished?**
- The Windows version builds and installs automatically, but I have not tested it on a real Windows PC yet.
- The Claude-powered features were only tested with fake answers (my account had no credit).
- There are no automatic tests yet, only careful manual testing.
- Nepali accuracy is modest.

**What would you do next?**
Test on Windows, add automatic tests, make the packages smaller, add a license, and improve Nepali.

**What are you proudest of?**
That it is a real, finished product: someone can click a link, install it and use it, and the whole build and release
runs automatically.

## Numbers worth remembering

| Fact | Value |
|---|---|
| Lines of Python | about 4,900 |
| Speech models inside the installer | `base` (about 145 MB) and `small` (about 485 MB) |
| Big model for Nepali/Hindi (downloaded once, when needed) | about 1.6 GB |
| Longest recording | 2 hours (warning 5 minutes before) |
| Installer size | about 650–750 MB |
| Live text delay | draft in about 2 seconds, then the accurate text |
| Password lock | 5 wrong tries, then 30 seconds |
| Platforms | Ubuntu/Linux (tested), Windows (beta, untested on a real PC) |

## If you get a question you can't answer

Say: *"I don't remember that detail, but I wrote it down."* Then open the [complete guide](GUIDE.md). Section 14 lists
the problems and fixes, and section 15 says what is and is not tested. Never claim something the guide marks as untested.
