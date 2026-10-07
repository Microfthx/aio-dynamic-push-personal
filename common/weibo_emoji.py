import base64
import os
import re
from functools import lru_cache
from pathlib import Path


DEFAULT_EMOJI_ROOT = Path(__file__).resolve().parents[1] / "vendor" / "weibo-emoji" / "icon"
EMOJI_TOKEN_PATTERN = re.compile(r"\[([^\[\]\r\n]+)\]")


def get_emoji_root():
    configured_root = os.environ.get("WEIBO_EMOJI_ROOT")
    return Path(configured_root).expanduser().resolve() if configured_root else DEFAULT_EMOJI_ROOT


@lru_cache(maxsize=512)
def load_emoji_as_base64(name, emoji_root):
    if not name or "/" in name or "\\" in name:
        return None

    image_path = Path(emoji_root) / f"{name}.png"
    if not image_path.is_file():
        return None

    encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
    return f"base64://{encoded}"


def build_onebot_content_segments(content, emoji_root=None):
    if not isinstance(content, str) or not content:
        return []

    root = str(Path(emoji_root) if emoji_root else get_emoji_root())
    segments = []
    cursor = 0

    def append_text(value):
        if not value:
            return
        if segments and segments[-1]["type"] == "text":
            segments[-1]["data"]["text"] += value
        else:
            segments.append({"type": "text", "data": {"text": value}})

    for match in EMOJI_TOKEN_PATTERN.finditer(content):
        append_text(content[cursor:match.start()])
        image_data = load_emoji_as_base64(match.group(1), root)
        if image_data:
            segments.append({"type": "image", "data": {"file": image_data}})
        else:
            append_text(match.group(0))
        cursor = match.end()

    append_text(content[cursor:])
    return segments
