"""Multi-language dub for Horror Studio.

Translate the English script -> synthesize with a per-language locked
signature voice -> re-render the same images into a dubbed video.

v1 languages: Urdu, Spanish (DejaVu covers both scripts for captions).
Hindi lands in v2 (needs a Devanagari caption font bundled).
"""
import re

DUB_VOICES = {
    "urdu": {
        "label": "Urdu",
        "lang": "ur",          # whisper language code
        "voice": "ur-PK-AsadNeural",
        "src": "en", "dest": "ur",
    },
    "spanish": {
        "label": "Spanish",
        "lang": "es",
        "voice": "es-ES-AlvaroNeural",
        "src": "en", "dest": "es",
    },
}

# per-language locked signature voice (voice lock, like Christopher for EN)
LOCKED_DUB_VOICE = {k: v["voice"] for k, v in DUB_VOICES.items()}


def translate_lines(lines, dest, src="en", progress_cb=None):
    """Translate script lines via free Google Translate (deep-translator).

    Retries with backoff on rate limits; falls back to per-line on batch
    failure.
    """
    import time
    from deep_translator import GoogleTranslator
    from deep_translator.exceptions import TooManyRequests
    t = GoogleTranslator(source=src, target=dest)

    def _one(line, tries=4):
        last = None
        for k in range(tries):
            try:
                if k:
                    time.sleep(2 * k)
                txt = t.translate(line)
                if txt:
                    return txt.strip()
                last = RuntimeError("empty translation")
            except TooManyRequests as e:
                last = e
                time.sleep(3 * (k + 1))
            except Exception as e:  # noqa: BLE001
                last = e
                time.sleep(2)
        raise RuntimeError(f"translation failed: {last}")

    out = []
    for i, line in enumerate(lines):
        out.append(_one(line))
        time.sleep(0.4)  # stay under the rate limit
        if progress_cb:
            progress_cb((i + 1) / len(lines))
    return out


def normalize_punctuation(lines):
    """Map script punctuation to ASCII so the voice engine splits sentences."""
    return [l.replace("\u06d4", ".").replace("\u061f", "?").replace("\u060c", ",")
            for l in lines]


def dub_voiceover(translated_lines, lang_key, out_dir, progress_cb=None):
    """Synthesize dubbed voiceover with the locked voice for lang_key."""
    from horror_voice import engine as voice_engine
    cfg = DUB_VOICES[lang_key]
    lines = normalize_punctuation(translated_lines)
    mp3, timings = voice_engine.generate_voiceover(
        "\n".join(lines),
        voice=cfg["voice"],
        out_dir=str(out_dir),
        progress_cb=progress_cb,
    )
    return mp3, timings, lines
