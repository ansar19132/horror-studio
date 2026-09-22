"""Upload metadata generator for Horror Studio.

Auto-generates a YouTube title, description (with AI disclosure + hashtags)
and tags from the script. Delivered as an easy-copy text file.
"""
import re

BASE_TAGS = [
    "horror stories", "scary stories", "horror narration",
    "creepypasta", "scary storytime", "horror youtube",
    "dark stories", "true scary stories", "halloween horror",
    "midnight horror",
]

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
    "for", "with", "as", "was", "were", "is", "are", "it", "its", "i",
    "me", "my", "we", "you", "he", "she", "they", "them", "his", "her",
    "that", "this", "then", "than", "from", "up", "down", "out", "so",
    "not", "no", "had", "has", "have", "did", "do", "be", "been", "by",
    "like", "into", "over", "under", "when", "while", "there", "their",
    "what", "which", "who", "whom",
}


def _keywords(script_lines, n=12):
    freq = {}
    for line in script_lines:
        for w in re.findall(r"[a-zA-Z']{4,}", line.lower()):
            if w not in STOPWORDS:
                freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda w: -freq[w])
    return ranked[:n]


def _hook_line(script_lines):
    """First genuinely eerie line -> video hook for title/description."""
    for line in script_lines:
        s = line.strip()
        if len(s) > 25:
            return s
    return script_lines[0] if script_lines else "A horror story."


def make_metadata(script_lines, thumb_words=""):
    kws = _keywords(script_lines)
    hook = _hook_line(script_lines)

    # --- title: hook-flavoured, <= 100 chars ---
    core = " ".join(w.capitalize() for w in kws[:4])
    title = f"{core} | Horror Story"
    if len(title) > 100:
        title = f"{kws[0].capitalize()} {kws[1].capitalize()} | Horror Story"
    title = title[:100]

    tags = BASE_TAGS + [k for k in kws if k not in BASE_TAGS]
    tags = tags[:25]

    description = (
        f"{hook}\n\n"
        "A dark horror narration — best experienced with headphones, "
        "alone, after midnight.\n\n"
        "If you love scary stories, horror narration and tales from the dark, "
        "subscribe for a new nightmare every week.\n\n"
        "TAGS: " + ", ".join(tags[:10]) + "\n\n"
        "Disclosure: this video uses AI-generated narration and imagery; "
        "the story, direction and edit are original.\n\n"
        "#horror #scarystories #horrornarration"
    )
    if thumb_words:
        description = description.replace(
            "subscribe for a new nightmare every week.",
            f"subscribe for a new nightmare every week.\n\nVideo: \"{thumb_words}\"",
        )
    return {"title": title, "description": description,
            "tags": tags, "keywords": kws}


def metadata_text(meta):
    return (
        "TITLE\n"
        f"{meta['title']}\n\n"
        "DESCRIPTION\n"
        f"{meta['description']}\n\n"
        "TAGS (comma separated)\n"
        f"{', '.join(meta['tags'])}\n"
    )
