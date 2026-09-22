"""YouTube thumbnail generator for Horror Studio.

1280x720 horror thumbnail: darkest scare image as background, 3-5 ALL CAPS
words, one word in blood red. Text auto-derived from the script.
"""
import io
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

W, H = 1280, 720
BLOOD = (198, 12, 20)
WHITE = (245, 245, 245)

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "of", "in", "on", "at", "to",
    "for", "with", "as", "was", "were", "is", "are", "it", "its", "i",
    "me", "my", "we", "you", "he", "she", "they", "them", "his", "her",
    "that", "this", "then", "than", "from", "up", "down", "out", "so",
    "not", "no", "had", "has", "have", "did", "do", "be", "been", "by",
    "like", "into", "over", "under", "when", "while", "there", "their",
}

SHOCK_HINTS = [
    "scream", "screamed", "screaming", "blood", "dead", "death", "demon",
    "ghost", "devil", "monster", "nightmare", "terror", "darkness",
    "shadow", "whisper", "grave", "corpse", "haunted", "curse", "fear",
    "evil", "hell", "claws", "fangs", "eyes", "door", "stairs", "house",
    "midnight", "silence", "name",
]


def pick_thumbnail_words(script_lines):
    """Return (words: list[str], red_index: int). 3-5 ALL CAPS words."""
    scored = []
    for line in script_lines:
        low = line.lower()
        score = sum(1 for w in SHOCK_HINTS if w in low)
        scored.append((score, line))
    scored.sort(key=lambda x: -x[0])
    best = scored[0][1] if scored else ""
    words = [w for w in re.findall(r"[A-Za-z']+", best)
             if w.lower() not in STOPWORDS and len(w) > 2]
    # horror titles land hardest at the end — keep the tail
    words = words[-5:] if len(words) > 5 else words
    if len(words) < 3:
        words = (words + ["FEAR", "IN", "THE", "DARK"])[:5]
    words = [w.upper() for w in words[:5]]
    # reddest word: first shock-hint match, else the middle word
    red_idx = 0
    for i, w in enumerate(words):
        if w.lower() in SHOCK_HINTS:
            red_idx = i
            break
    else:
        red_idx = len(words) // 2
    return words, red_idx


def _font(size):
    for p in ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
              str(Path(__file__).parent / "fonts" / "DejaVuSans-Bold.ttf")):
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def make_thumbnail(image_bytes, words, red_idx, out_path):
    """Build the 1280x720 thumbnail, save to out_path. Returns out_path."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    # cover-crop to 16:9
    target_ratio, r = W / H, img.width / img.height
    if r > target_ratio:
        nw = int(img.height * target_ratio)
        x0 = (img.width - nw) // 2
        img = img.crop((x0, 0, x0 + nw, img.height))
    else:
        nh = int(img.width / target_ratio)
        y0 = (img.height - nh) // 2
        img = img.crop((0, y0, img.width, y0 + nh))
    img = img.resize((W, H), Image.LANCZOS)

    # darken + cold grade so text pops
    overlay = Image.new("RGB", (W, H), (5, 5, 12))
    img = Image.blend(img, overlay, 0.45)
    # bottom gradient for text legibility
    grad = Image.new("L", (1, H))
    for y in range(H):
        grad.putpixel((0, y), int(255 * max(0, (y - H * 0.45) / (H * 0.55)) ** 1.5))
    black = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(Image.blend(img, black, 0.55), img, grad.resize((W, H)))

    d = ImageDraw.Draw(img)
    # fit text: shrink until it fits both width AND height
    size = 150
    font = _font(size)
    while size > 40:
        widths = [d.textlength(w, font=font) for w in words]
        line_h = int(size * 1.12)
        if max(widths) < W - 160 and line_h * len(words) < H - 120:
            break
        size -= 8
        font = _font(size)
    line_h = int(size * 1.12)
    total_h = line_h * len(words)
    y = (H - total_h) // 2
    for i, w in enumerate(words):
        color = BLOOD if i == red_idx else WHITE
        tw = d.textlength(w, font=font)
        x = (W - tw) / 2
        d.text((x, y), w, font=font, fill=color,
               stroke_width=max(2, size // 28), stroke_fill=(0, 0, 0))
        y += line_h

    # erase generator watermark (bottom-right) — heavy blur, invisible on dark art
    wx, wy = int(W * 0.80), int(H * 0.85)
    zone = img.crop((wx, wy, W, H)).filter(ImageFilter.GaussianBlur(25))
    img.paste(zone, (wx, wy))

    out_path = Path(out_path)
    img.save(out_path, "JPEG", quality=90)
    return str(out_path)


def generate_thumbnail_for_script(script_lines, image_bytes_list, out_path):
    """Pick scariest image + words, build thumbnail. Returns (path, words)."""
    words, red_idx = pick_thumbnail_words(script_lines)
    # use the image of the highest-scoring line when counts match
    img_bytes = image_bytes_list[0]
    if len(image_bytes_list) == len(script_lines):
        scored = []
        for i, line in enumerate(script_lines):
            low = line.lower()
            scored.append((sum(1 for w in SHOCK_HINTS if w in low), i))
        scored.sort(reverse=True)
        img_bytes = image_bytes_list[scored[0][1]]
    make_thumbnail(img_bytes, words, red_idx, out_path)
    return str(out_path), " ".join(words)
