"""Thin Claude wrapper (live summary, explanations, class summary)."""
import base64
import os
from pathlib import Path

import config


def available():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def ask(prompt, image_path=None, max_tokens=1000):
    """Send a prompt (optionally with a PNG screenshot) and return Claude's text reply."""
    import anthropic

    content = []
    if image_path:
        data = base64.standard_b64encode(Path(image_path).read_bytes()).decode()
        content.append({"type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": data}})
    content.append({"type": "text", "text": prompt})
    msg = anthropic.Anthropic().messages.create(
        model=config.CLAUDE_MODEL, max_tokens=max_tokens,
        messages=[{"role": "user", "content": content}])
    return msg.content[0].text.strip()
