"""AI image generation for Horror Studio — Pollinations.ai (free, no API key).

Each script sentence gets a cinematic horror still. Optional Pexels stock
fallback when the user supplies a (free) Pexels API key.
"""
import time
import urllib.parse
import urllib.request

HORROR_STYLE = (
    "cinematic horror film still, dark moody atmosphere, fog, moonlight, "
    "deep shadows, 35mm film look, eerie, hyper-detailed"
)

POLLINATIONS_BASE = "https://image.pollinations.ai/prompt"


def horror_prompt(sentence: str) -> str:
    """Turn a narration sentence into an image prompt."""
    s = sentence.strip().strip('"').strip("'")
    # strip leading "Number X:" style markers if ever present
    return f"{HORROR_STYLE}, scene: {s}"


def generate_image(prompt: str, width: int = 1280, height: int = 720,
                   seed: int | None = None, model: str = "flux",
                   timeout: int = 120, retries: int = 2) -> bytes:
    """Generate one image via Pollinations, return JPEG bytes."""
    q = {
        "width": width, "height": height, "model": model,
        "nologo": "true",
    }
    if seed is not None:
        q["seed"] = seed
    url = f"{POLLINATIONS_BASE}/{urllib.parse.quote(prompt)}?{urllib.parse.urlencode(q)}"
    last_err = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "HorrorStudio/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if data[:2] == b"\xff\xd8":  # JPEG magic
                return data
            last_err = ValueError("not a JPEG response")
        except Exception as e:  # noqa: BLE001
            last_err = e
        time.sleep(2)
    raise RuntimeError(f"image generation failed: {last_err}")


def pexels_search(query: str, api_key: str, per_page: int = 3,
                  orientation: str = "landscape") -> list[dict]:
    """Search Pexels stock photos. Returns [{url, photographer}]."""
    params = urllib.parse.urlencode({
        "query": query, "per_page": per_page, "orientation": orientation,
    })
    req = urllib.request.Request(
        f"https://api.pexels.com/v1/search?{params}",
        headers={"Authorization": api_key, "User-Agent": "HorrorStudio/1.0"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        import json
        payload = json.loads(r.read().decode("utf-8"))
    out = []
    for p in payload.get("photos", []):
        src = p.get("src", {})
        url = src.get("large2x") or src.get("large") or src.get("original")
        if url:
            out.append({"url": url, "photographer": p.get("photographer", "")})
    return out


def download_url(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "HorrorStudio/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()
