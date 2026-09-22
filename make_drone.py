#!/usr/bin/env python3
"""Generate bundled copyright-free dark ambient beds for Horror Studio.

Synthesized from scratch with ffmpeg lavfi — no samples, no licensing risk:
layered low rumble + dissonant shimmer + filtered noise wash, slow-evolving.

Output: music/dark_ambient.mp3 (10 min, loopable under narration).
"""
import subprocess
from pathlib import Path

OUT = Path(__file__).parent / "music"
DUR = 600  # 10 minutes


def build():
    OUT.mkdir(exist_ok=True)
    out = OUT / "dark_ambient.mp3"
    if out.exists():
        print("exists:", out)
        return str(out)

    # Three layers, all slow-evolving:
    # 1. sub rumble: 48Hz + 48.7Hz beating sines, very low
    # 2. dissonant shimmer: 622Hz + 659Hz (tritone-ish dread), tremolo
    # 3. noise wash: pink noise, lowpassed, breathing via slow volume LFO
    fc = (
        "sine=frequency=48:duration=600,volume=0.5[r1];"
        "sine=frequency=48.7:duration=600,volume=0.5[r2];"
        "[r1][r2]amix=inputs=2:duration=longest:dropout_transition=0,"
        "lowpass=f=120,volume=0.55[rumble];"
        "sine=frequency=622:duration=600,volume=0.16[s1];"
        "sine=frequency=659:duration=600,volume=0.16[s2];"
        "[s1][s2]amix=inputs=2:duration=longest:dropout_transition=0,"
        "tremolo=f=0.1:d=0.7,highpass=f=400,volume=0.35[shimmer];"
        f"anoisesrc=color=pink:duration={DUR}:seed=11,"
        "lowpass=f=320,volume=0.05,"
        "tremolo=f=0.1:d=0.8[wash];"
        "[rumble][shimmer][wash]amix=inputs=3:duration=longest:dropout_transition=0,"
        "alimiter=limit=0.5,volume=0.8[mix]"
    )
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"sine=frequency=1:duration={DUR}",
        "-filter_complex", fc,
        "-map", "[mix]", "-c:a", "libmp3lame", "-b:a", "96k",
        "-ar", "44100", "-ac", "2", str(out),
    ]
    print("+ generating dark ambient bed (10 min)...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-2000:])
        raise SystemExit("drone generation failed")
    print("saved:", out)
    return str(out)


if __name__ == "__main__":
    build()
