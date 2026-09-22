"""Gemini (Google AI) helper for Horror Studio.

Uses the free Gemini API (key from https://aistudio.google.com/apikey)
for two jobs:
  1. Catchy YouTube horror titles from the script (text model).
  2. AI-generated thumbnails (image model).

The API key is entered at runtime in the app and is never written to disk.
"""
import base64
import re

import requests

TEXT_MODEL = "gemini-2.0-flash"
IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"
BASE = "https://generativelanguage.googleapis.com/v1beta/models"


def _url(model, key):
    return f"{BASE}/{model}:generateContent?key={key}"


def generate_titles(api_key, script_lines, n=5):
    """Return n catchy English horror YouTube titles for the script."""
    script = "\n".join(script_lines[:40])
    prompt = (
        "You are a YouTube horror-channel strategist. Write "
        f"{n} catchy, click-worthy YouTube titles (ENGLISH, max 70 characters each) "
        "for the horror story below. Style: ALL CAPS words for the scary hook, "
        "e.g. 'The HOUSE That WHISPERS At Night | Horror Story'. "
        "No numbering explanations, just the titles, one per line.\n\n"
        f"STORY:\n{script}"
    )
    r = requests.post(
        _url(TEXT_MODEL, api_key),
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0.9}},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    titles = []
    for line in text.splitlines():
        line = re.sub(r"^[\d\-\.\)\*\s]+", "", line).strip().strip('"')
        if 10 < len(line) <= 100:
            titles.append(line)
        if len(titles) >= n:
            break
    if not titles:
        raise RuntimeError("Gemini se titles nahi mile.")
    return titles


def generate_thumbnail(api_key, script_lines, words=""):
    """Generate a 16:9 horror YouTube thumbnail image. Returns JPEG bytes."""
    hook = ""
    for line in script_lines:
        if len(line.strip()) > 25:
            hook = line.strip()
            break
    big_text = words or " ".join(w.upper() for w in
                                 re.findall(r"[a-zA-Z]{4,}", hook)[:3]) or ["HORROR"]
    prompt = (
        "YouTube horror thumbnail, 16:9 widescreen, 1280x720. Terrifying cinematic scene: "
        f"{hook} Dark fog, moonlight, deep shadows, blood-red accents, film grain. "
        f"Bold 3D horror-movie text '{big_text}' in dripping blood-red letters across the top. "
        "High contrast, extremely scary, professional YouTube thumbnail, no watermark."
    )
    r = requests.post(
        _url(IMAGE_MODEL, api_key),
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"responseModalities": ["TEXT", "IMAGE"]}},
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    for part in data["candidates"][0]["content"]["parts"]:
        inline = part.get("inlineData")
        if inline and inline.get("mimeType", "").startswith("image/"):
            return base64.b64decode(inline["data"])
    raise RuntimeError("Gemini se image nahi mili.")
