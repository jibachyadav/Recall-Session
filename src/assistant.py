"""Live helper AI: Claude when it works, otherwise a free local model (Ollama)."""
import atexit
import json
import sys
import os
import re
import shutil
import subprocess
import time
import urllib.request
from pathlib import Path

import config
from src import llm

OLLAMA_URL = "http://127.0.0.1:11434"
_state = {"claude_ok": None, "server": None}   # claude_ok: None = not tried yet, False = failed (no credit/internet)


class AIUnavailable(Exception):
    """Neither Claude nor the local model could answer."""


def claude_works():
    """True if Claude is configured and has not failed this run."""
    return llm.available() and _state["claude_ok"] is not False


def _ollama_bin():
    path = Path(config.OLLAMA_BIN).expanduser()
    if path.exists():
        return str(path)
    found = shutil.which("ollama")
    windows_default = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return found or (str(windows_default) if sys.platform.startswith("win") and windows_default.exists() else None)


def _api(path, payload=None, timeout=5):
    req = urllib.request.Request(OLLAMA_URL + path, data=json.dumps(payload).encode() if payload else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def _ollama_up():
    try:
        _api("/api/tags", timeout=1)
        return True
    except Exception:
        return False


def _ollama_ready(model=None):
    """Start the local server if needed. Returns None when ready, or a reason string."""
    model = model or config.OLLAMA_MODEL
    binary = _ollama_bin()
    if not binary:
        return "the free local AI is not installed"
    if not _ollama_up():
        _state["server"] = subprocess.Popen([binary, "serve"], stdout=subprocess.DEVNULL,
                                            stderr=subprocess.DEVNULL, start_new_session=True)
        atexit.register(lambda: _state["server"] and _state["server"].terminate())
        for _ in range(40):
            if _ollama_up():
                break
            time.sleep(0.5)
        else:
            return "the free local AI did not start"
    names = [m["name"] for m in _api("/api/tags").get("models", [])]
    if model not in names and f"{model}:latest" not in names:
        return f"the local model {model} is not downloaded"
    return None


def ask(prompt, max_tokens=400, model=None, on_token=None, num_ctx=None):
    """Returns (answer, provider) where provider is "Claude" or "free local AI".

    `model` picks the local model; `on_token(text)` is called with pieces of the answer as they arrive
    (the local AI streams; Claude gives the whole answer at once); `num_ctx` sets the local reading window."""
    reason = "no Claude key" if not llm.available() else "Claude is unavailable (no credit or internet)"
    if claude_works():
        try:
            text = llm.ask(prompt, max_tokens=max_tokens)
            _state["claude_ok"] = True
            if on_token:
                on_token(text)
            return text, "Claude"
        except Exception:
            _state["claude_ok"] = False
    model = model or config.OLLAMA_MODEL
    problem = _ollama_ready(model)
    if problem:
        raise AIUnavailable(f"{reason}, and {problem}.")
    options = {"num_predict": max_tokens, "temperature": 0.2}
    if num_ctx:
        options["num_ctx"] = num_ctx
    req = urllib.request.Request(OLLAMA_URL + "/api/generate",
                                 data=json.dumps({"model": model, "prompt": prompt, "stream": True,
                                                  "options": options}).encode(),
                                 headers={"Content-Type": "application/json"})
    out = []
    with urllib.request.urlopen(req, timeout=900) as r:
        for line in r:
            piece = json.loads(line).get("response", "")
            if piece:
                out.append(piece)
                if on_token:
                    on_token(piece)
    return "".join(out).strip(), "free local AI"


QUESTIONS_PROMPT = """A student is in a live class. Below is the last few minutes of what the teacher said
(rough speech-to-text, may contain errors). Suggest 3 short, specific questions the student could ask
the teacher to understand better: about points that were glossed over, unclear, or important.
Write one question per line, nothing else: no numbers, no bullets, no introduction.

Transcript:
{text}"""

ANSWER_PROMPT = """A student is watching a live class and asks you a question. Below is what the teacher
said recently (rough speech-to-text, may contain errors). Use it to see what the class is about, but answer
from your own knowledge too. Explain simply and briefly (under 120 words), like a patient tutor.

Recent transcript:
{text}

Student's question: {question}"""


def suggest_questions(text):
    """Up to 3 questions to ask the teacher. Returns (list_of_questions, provider)."""
    reply, provider = ask(QUESTIONS_PROMPT.format(text=text[-6000:]), max_tokens=200)
    lines = [re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", ln).strip() for ln in reply.splitlines()]
    return [ln for ln in lines if len(ln) > 8][:3], provider


def answer(question, text):
    """Explain something to the student. Returns (answer, provider)."""
    return ask(ANSWER_PROMPT.format(text=text[-6000:] or "(nothing said yet)", question=question), max_tokens=350)


# ---- the teacher asks the student a question -------------------------------------------------
_FILLER = re.compile(r"^(?:so |and |but |okay,? |ok,? |right,? )*(?:right|ok(?:ay)?|yeah|yes|you see|see|got it|"
                     r"does (?:that|this) make sense|make sense|do you (?:understand|follow|see)|is (?:that|this) clear|"
                     r"any questions|are you with me|you know|isn't it|aren't they|correct|clear|understood|"
                     r"everyone (?:ok|okay)|everybody (?:ok|okay)|can you hear me|can everyone hear me)\W*$", re.I)
_TAG = re.compile(r",\s*(?:right|ok(?:ay)?|yeah|yes|correct|see|you know|isn't it|aren't they|doesn't it|don't you|no)\s*\?$", re.I)
_STARTERS = re.compile(r"^(?:so |now |okay,? |ok,? )?(?:can (?:anyone|someone|anybody|you tell|you explain)|who (?:can|knows)|"
                       r"does (?:anyone|anybody) know|what (?:is|are|do you|does)|why (?:is|do|does)|how (?:do|does|would))", re.I)


def extract_questions(text):
    """Questions the teacher put to the class: sentences ending in '?' (or clear 'can anyone...' openers)."""
    found = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        sentence = sentence.strip()
        if len(sentence.split()) < 4 or _FILLER.match(sentence) or _TAG.search(sentence):
            continue
        if sentence.endswith("?") or (_STARTERS.match(sentence) and re.match(r"^(?:so |now |okay,? |ok,? )?(?:can|who|does) ", sentence, re.I)):
            found.append(sentence)
    return found


TEACHER_PROMPT = """In a live class the teacher just asked the student this question:

"{question}"

Give the student a short answer they could say out loud right now (1 to 3 sentences, plain words),
based on what the teacher said recently (below, rough speech-to-text) and general knowledge.
If the question can't be answered from that, say what the student could reply to buy time.

Recent transcript:
{text}"""


def suggest_answer(question, text):
    """A short answer the student could give. Returns (answer, provider)."""
    return ask(TEACHER_PROMPT.format(question=question, text=text[-6000:] or "(nothing said yet)"), max_tokens=250)


def ai_available():
    """True if some AI can answer: Claude (not failed) or the installed local model."""
    return claude_works() or _ollama_bin() is not None
