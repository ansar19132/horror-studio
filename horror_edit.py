#!/usr/bin/env python3
"""
Horror Studio — Auto Edit Engine
Input:  script.txt (one narration sentence per line)
        voiceover.mp3 (from the built-in voice tool)
        images/ (one image per script line, sorted; AI-generated or stock)
        music.mp3 (optional background drone/music)
Output: output/horror_final.mp4  (16:9, 1080p, horror grade + FX + captions)
        output/short_1..3.mp4    (9:16 vertical Shorts)

Horror look: cold desaturated grade, film grain, vignette, letterbox,
flash-cut transitions on scare beats, red flash frames, zoom punch-ins,
blood-red karaoke captions.

Usage:
    python horror_edit.py --project /path/to/project [--model tiny] [--no-shorts]
"""
import argparse, difflib, json, os, re, subprocess, sys
from pathlib import Path

FPS = 30
W, H = 1920, 1080
SHORT_W, SHORT_H = 1080, 1920

# font locations (overridable, e.g. by the web app)
FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONTS_DIR = "/usr/share/fonts"

# ---------------------------------------------------------------- config
DEFAULT_CONFIG = {
    "xfade_duration": 0.5,          # normal transition length (seconds)
    "shock_xfade_duration": 0.15,  # flash-cut into scare beats
    "section_xfade_duration": 0.9, # dip-to-black between sections
    "section_pattern": r"^number\s+\w+\s*:",
    "music_volume": 0.15,
    "kenburns_cycle": ["zin", "zout", "panr", "panl"],
    "caption_fontsize": 64,
    # --- horror look ---
    "horror_grade": True,          # cold desaturated cinematic grade
    "film_grain": 6,               # 0 = off
    "vignette": True,
    "letterbox": True,             # cinematic black bars
    "shock_flash": True,           # red flash frame on scare beats
    "shock_words": [
        "scream", "screamed", "screaming", "suddenly", "blood", "bloody",
        "dead", "death", "die", "died", "corpse", "demon", "ghost",
        "horror", "terrified", "terror", "nightmare", "shadow", "darkness",
        "whisper", "whispered", "claw", "fangs", "teeth", "eyes",
        "behind me", "it moved", "don't look", "run", "hide",
    ],
    "shorts": [
        [1, 4],
        [16, 19],
        [37, 40],
    ],
    "short_max_seconds": 40,
}

# ---------------------------------------------------------------- helpers
def norm_text(t):
    t = t.lower()
    t = re.sub(r"[^a-z0-9'\s]", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def ts(seconds):
    """seconds -> ASS timestamp h:mm:ss.cc"""
    if seconds < 0:
        seconds = 0
    h = int(seconds // 3600); m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"

def run(cmd, **kw):
    print("+", " ".join(cmd[:4]), "..." if len(cmd) > 4 else "")
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        raise SystemExit(f"command failed: {cmd[0]}")
    return r

# ---------------------------------------------------------------- alignment
def resolve_model(model_name):
    local = Path(f"/opt/hatch-image/models/asr/faster-whisper-{model_name}")
    if local.is_dir() and (local / "model.bin").exists():
        print(f"      using local model: {local}")
        return str(local)
    return model_name

def transcribe_words(voiceover, model_name="tiny", language="en"):
    from faster_whisper import WhisperModel
    print(f"[1/5] Transcribing voiceover ({model_name}, lang={language})...")
    model = WhisperModel(resolve_model(model_name), device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(voiceover), word_timestamps=True,
                                   language=language)
    words = []
    for seg in segments:
        if seg.words:
            for w in seg.words:
                words.append({"w": norm_text(w.word), "start": w.start, "end": w.end})
    words = [x for x in words if x["w"]]
    print(f"      {len(words)} words transcribed")
    if not words:
        raise SystemExit("No words transcribed — check the voiceover file.")
    return words

def align_sentences(script_lines, twords):
    """Map each script sentence -> (start, end) in audio via word alignment."""
    print("[2/5] Aligning sentences to voiceover (auto clip adjust)...")
    sw, bounds = [], []
    for i, line in enumerate(script_lines):
        ws = norm_text(line).split()
        bounds.append((len(sw), len(sw) + len(ws), i))
        sw.extend(ws)
    tw = [x["w"] for x in twords]
    sm = difflib.SequenceMatcher(None, sw, tw, autojunk=False)
    mapping = {}
    prev_si, prev_ti = 0, 0
    for tag, a, b, c, d in sm.get_opcodes():
        if tag == "equal":
            gap_s = a - prev_si
            gap_t = c - prev_ti
            for k in range(gap_s):
                frac = (k + 1) / (gap_s + 1)
                mapping[prev_si + k] = prev_ti + int(round(frac * gap_t))
            for k in range(b - a):
                mapping[a + k] = c + k
            prev_si, prev_ti = b, d
    gap_s = len(sw) - prev_si
    gap_t = len(tw) - prev_ti
    for k in range(gap_s):
        frac = (k + 1) / (gap_s + 1)
        mapping[prev_si + k] = min(prev_ti + int(round(frac * gap_t)), len(tw) - 1)
    sentences = []
    for s0, s1, i in bounds:
        t0 = max(0, mapping.get(s0, 0))
        t1 = min(len(twords) - 1, mapping.get(s1 - 1, len(twords) - 1))
        if t1 < t0:
            t0, t1 = t0, t0
        start = max(0.0, twords[t0]["start"] - 0.12)
        end = twords[t1]["end"] + 0.30
        if end - start < 1.0:
            end = start + 1.0
        sentences.append({"line": script_lines[i], "start": start, "end": end,
                          "w0": t0, "w1": t1})
    for i in range(1, len(sentences)):
        if sentences[i]["start"] < sentences[i - 1]["end"] - 0.05:
            sentences[i]["start"] = sentences[i - 1]["end"] - 0.05
        if sentences[i]["end"] <= sentences[i]["start"]:
            sentences[i]["end"] = sentences[i]["start"] + 1.0
    for s in sentences:
        s["dur"] = s["end"] - s["start"]
    total_audio = twords[-1]["end"]
    print(f"      {len(sentences)} sentences aligned, audio {total_audio:.1f}s")
    return sentences, twords

def detect_shock(sentences, cfg):
    """Flag scare beats via horror keyword list (drives flash-cut transitions)."""
    words = cfg.get("shock_words", [])
    n_shock = 0
    for s in sentences:
        low = s["line"].lower()
        s["shock"] = any(w in low for w in words)
        n_shock += s["shock"]
    print(f"      {n_shock} scare beat(s) detected")
    return sentences

# ---------------------------------------------------------------- captions (ASS karaoke, horror style)
def build_caption_words(sentences, twords):
    for s in sentences:
        sw_orig = s["line"].split()
        sw_norm = []
        norm_to_orig = []
        for oi, w in enumerate(sw_orig):
            for p in norm_text(w).split():
                sw_norm.append(p)
                norm_to_orig.append(oi)
        tw = twords[s["w0"]:s["w1"] + 1]
        sm = difflib.SequenceMatcher(None, sw_norm, [t["w"] for t in tw], autojunk=False)
        caps = []
        for tag, a, b, c, d in sm.get_opcodes():
            if tag == "equal":
                for k in range(b - a):
                    oi = norm_to_orig[a + k]
                    caps.append((sw_orig[oi], tw[c + k]["start"], tw[c + k]["end"]))
            elif tag == "replace" and (b - a) == (d - c):
                for k in range(b - a):
                    oi = norm_to_orig[a + k]
                    r = difflib.SequenceMatcher(None, sw_norm[a + k], tw[c + k]["w"]).ratio()
                    txt = sw_orig[oi] if r > 0.55 else tw[c + k]["w"]
                    caps.append((txt, tw[c + k]["start"], tw[c + k]["end"]))
            elif tag == "insert":
                for k in range(d - c):
                    caps.append((tw[c + k]["w"], tw[c + k]["start"], tw[c + k]["end"]))
            elif tag == "replace":
                for k in range(b - a):
                    oi = norm_to_orig[a + k]
                    st = tw[c]["start"] if c < d else None
                    en = tw[d - 1]["end"] if c < d else None
                    caps.append((sw_orig[oi], st, en))
            elif tag == "delete":
                for k in range(b - a):
                    oi = norm_to_orig[a + k]
                    caps.append((sw_orig[oi], None, None))
        i = 0
        while i < len(caps):
            txt, st, en = caps[i]
            if st is None:
                prev_en = caps[i - 1][2] if i > 0 else s["start"]
                if prev_en is None:
                    prev_en = s["start"]
                j = i
                while j < len(caps) and caps[j][1] is None:
                    j += 1
                nxt_st = caps[j][1] if j < len(caps) else s["end"]
                run_n = j - i
                slot = max(0.01, (nxt_st - prev_en) / run_n)
                for k in range(run_n):
                    caps[i + k] = (caps[i + k][0], prev_en + slot * k,
                                   prev_en + slot * (k + 1))
                i = j
            else:
                i += 1
        if not caps:
            caps = [(w, t["start"], t["end"]) for w, t in zip(sw_orig, tw)]
        merged = []
        for txt, st, en in caps:
            if merged and merged[-1][0] == txt:
                merged[-1] = (txt, merged[-1][1], en)
            else:
                merged.append((txt, st, en))
        s["caps"] = merged

def write_ass(path, sentences, play_w, play_h, fontsize, margin_v):
    # Horror style: white text, BLOOD-RED karaoke fill, thick black outline
    head = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {play_w}
PlayResY: {play_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,{fontsize},&H00FFFFFF,&H000000FF,&H90000000,&H90000000,-1,0,0,0,100,100,0,0,1,4,1,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    events = []
    for s in sentences:
        parts = []
        for (txt, st, en) in s["caps"]:
            cs = max(1, int(round((en - st) * 100)))
            parts.append("{\\k%d}%s " % (cs, txt))
        text = "".join(parts).strip()
        est, een = s["caps"][0][1], s["caps"][-1][2]
        events.append(f"Dialogue: 0,{ts(est)},{ts(een)},Cap,,0,0,0,,{text}")
    path.write_text(head + "\n".join(events) + "\n", encoding="utf-8")

# ---------------------------------------------------------------- video build
def kenburns(i, dur, style, F, ow=W, oh=H, delogo=False):
    sw, sh = int(ow * 1.34), int(oh * 1.34)
    base = f"scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},setsar=1"
    if delogo and ow >= oh:
        # Pollinations burns a small logo bottom-right despite nologo=true;
        # interpolate it away. (Vertical crops cut it off anyway.)
        # Watermark sits at ~83-100% x, ~85-99% y of the scaled frame.
        dx0, dy0 = int(sw * 0.82), int(sh * 0.845)
        dw, dh = int(sw * 0.18), int(sh * 0.15)
        base += f",delogo=x={dx0}:y={dy0}:w={dw}:h={dh}:show=0"
    if style == "zin":
        zb = f"z='1+0.14*on/{F}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif style == "zout":
        zb = f"z='1.14-0.14*on/{F}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    elif style == "panr":
        zb = f"z=1.14:x='(iw-iw/zoom)*on/{F}':y='ih/2-(ih/zoom/2)'"
    elif style == "punch":  # scare beat: fast push-in
        zb = f"z='1+0.32*on/{F}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    else:  # panl
        zb = f"z=1.14:x='(iw-iw/zoom)*(1-on/{F})':y='ih/2-(ih/zoom/2)'"
    return f"[{i}:v]{base},zoompan={zb}:d={F}:s={ow}x{oh}:fps={FPS},setsar=1[v{i}]"

def build_filter(sentences, cfg, total_dur, has_music, D, dx, is_section,
                 is_shock, audio_t0, ow=W, oh=H, ass_path=None,
                 delogo_idx=None):
    filt = []
    cycle = cfg["kenburns_cycle"]
    n = len(sentences)
    for i in range(n):
        ext = dx[i] if i < n - 1 else 0.0
        F = max(2, int(round((D[i] + ext) * FPS)))
        style = "punch" if sentences[i].get("shock") else cycle[i % len(cycle)]
        filt.append(kenburns(i, D[i], style, F, ow, oh,
                             delogo=bool(delogo_idx and i in delogo_idx)))
    # xfade chain — flash-cut into scare beats, dip-to-black on sections
    prev = "v0"
    cum = D[0]
    for i in range(n - 1):
        if is_shock[i + 1]:
            trans, dur = "fadewhite", cfg["shock_xfade_duration"]
        elif is_section[i + 1]:
            trans, dur = "fadeblack", cfg["section_xfade_duration"]
        else:
            trans, dur = "fade", dx[i]
        filt.append(f"[{prev}][v{i + 1}]xfade=transition={trans}:duration={dur}:offset={cum:.3f}[x{i + 1}]")
        prev = f"x{i + 1}"
        if i < n - 2:
            cum += D[i + 1]
    vout = prev
    gstarts = [0.0]
    for i in range(n - 1):
        gstarts.append(gstarts[-1] + D[i])
    # ---- horror FX stack (global) ----
    fx = []
    if cfg.get("horror_grade"):
        fx.append("eq=saturation=0.70:contrast=1.07:brightness=-0.03")
        fx.append("colorbalance=bs=0.06:gm=0.02:bh=-0.03")
    if cfg.get("film_grain", 0):
        fx.append(f"noise=alls={cfg['film_grain']}:allf=t")
    if cfg.get("vignette"):
        fx.append("vignette=PI/4.5")
    if fx:
        filt.append(f"[{vout}]{','.join(fx)}[fx]")
        vout = "fx"
    # red flash frames on scare beats
    if cfg.get("shock_flash"):
        for i, s in enumerate(sentences):
            if s.get("shock"):
                st = gstarts[i] + 0.05
                en = st + 0.15
                filt.append(
                    f"[{vout}]drawbox=x=0:y=0:w=iw:h=ih:color=red@0.35:t=fill"
                    f":enable='between(t,{st:.2f},{en:.2f})'[fl{i}]"
                )
                vout = f"fl{i}"
    # cinematic letterbox
    if cfg.get("letterbox"):
        bar = int(oh * 0.08)
        filt.append(
            f"[{vout}]drawbox=x=0:y=0:w=iw:h={bar}:color=black:t=fill,"
            f"drawbox=x=0:y=ih-{bar}:w=iw:h={bar}:color=black:t=fill[lb]"
        )
        vout = "lb"
    filt.append(f"[{vout}]format=yuv420p[vfinal]")
    if ass_path:
        filt.append(f"[vfinal]subtitles='{ass_path}':fontsdir='{FONTS_DIR}'[vout]")
    else:
        filt.append("[vfinal]null[vout]")
    # audio
    a_in = n
    voice_chain = (
        f"[{a_in}:a]atrim=start={audio_t0:.2f},asetpts=PTS-STARTPTS,aresample=48000,"
        f"apad,atrim=0:{total_dur:.2f}"
    )
    if has_music:
        # voice feeds two filters (sidechain + mix) -> split it
        filt.append(voice_chain + ",asplit=2[voice][vside]")
    else:
        filt.append(voice_chain + "[voice]")
    if has_music:
        m_in = n + 1
        filt.append(
            f"[{m_in}:a]aresample=48000,atrim=0:{total_dur:.2f},asetpts=PTS-STARTPTS,"
            f"volume={cfg['music_volume']}[mm]"
        )
        filt.append(
            "[mm][vside]sidechaincompress=threshold=0.03:ratio=10:attack=300:release=1200[ducked]"
        )
        filt.append(
            "[voice][ducked]amix=inputs=2:duration=first:dropout_transition=0,"
            "alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5:LRA=11[afinal]"
        )
    else:
        filt.append("[voice]alimiter=limit=0.95,loudnorm=I=-16:TP=-1.5:LRA=11[afinal]")
    return ";".join(filt)

def build_long_video(proj, sentences, twords, cfg, out_path, ass_path,
                     voiceover, music, audio_t0):
    print("[3/5] Building horror video (grade + FX + transitions + captions)...")
    n = len(sentences)
    is_section = [bool(re.match(cfg["section_pattern"], s["line"], flags=re.I))
                  for s in sentences]
    is_shock = [bool(s.get("shock")) for s in sentences]
    xf, sxf, shxf = (cfg["xfade_duration"], cfg["section_xfade_duration"],
                     cfg["shock_xfade_duration"])
    D = [max(1.0, sentences[i + 1]["start"] - sentences[i]["start"]) for i in range(n - 1)]
    D.append(max(1.0, sentences[-1]["end"] - sentences[-1]["start"] + 1.0))
    dx = [(shxf if is_shock[i + 1] else sxf if is_section[i + 1] else xf)
          for i in range(n - 1)]
    total_dur = sum(D)
    has_music = music is not None and music.exists()
    filt = build_filter(sentences, cfg, total_dur, has_music, D, dx,
                        is_section, is_shock, audio_t0, ass_path=ass_path,
                        delogo_idx=cfg.get("delogo_idx"))
    cmd = ["ffmpeg", "-y"]
    for img in proj["images"]:
        cmd += ["-i", str(img)]
    cmd += ["-i", str(voiceover)]
    if has_music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
    cmd += ["-filter_complex", filt,
            "-map", "[vout]", "-map", "[afinal]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "19",
            "-r", str(FPS), "-c:a", "aac", "-b:a", "192k",
            "-t", f"{total_dur:.2f}", "-movflags", "+faststart",
            str(out_path)]
    run(cmd)
    print(f"      done -> {out_path} ({total_dur:.0f}s)")
    return total_dur

# ---------------------------------------------------------------- shorts
def build_shorts(proj, sentences, cfg, out_dir, voiceover, audio_t0,
                 captions=True):
    print("[4/5] Rendering Shorts (9:16)...")
    made = []
    for idx, (a, b) in enumerate(cfg.get("shorts", []), start=1):
        a = max(1, a) - 1
        b = min(len(sentences), b) - 1
        if b < a:
            continue
        seg = sentences[a:b + 1]
        s = seg[0]["start"]
        e = min(seg[-1]["end"], s + cfg["short_max_seconds"])
        rel = []
        for k, x in enumerate(seg):
            caps = [(t, a2 - s, b2 - s) for (t, a2, b2) in x["caps"] if b2 > s and a2 < e]
            if not caps:
                continue
            rel.append({"line": x["line"], "img": a + k, "shock": x.get("shock", False),
                        "start": x["start"] - s, "end": min(x["end"], e) - s,
                        "caps": caps})
        if not rel:
            continue
        n = len(rel)
        is_section = [bool(re.match(cfg["section_pattern"], x["line"], flags=re.I)) for x in rel]
        is_shock = [bool(x.get("shock")) for x in rel]
        xf, sxf, shxf = (cfg["xfade_duration"], cfg["section_xfade_duration"],
                         cfg["shock_xfade_duration"])
        D = [max(1.0, rel[i + 1]["start"] - rel[i]["start"]) for i in range(n - 1)]
        D.append(max(1.0, rel[-1]["end"] - rel[-1]["start"] + 0.5))
        dx = [(shxf if is_shock[i + 1] else sxf if is_section[i + 1] else xf)
              for i in range(n - 1)]
        total = sum(D)
        ass = None
        if captions:
            ass = out_dir / f"short_{idx}.ass"
            write_ass(ass, rel, SHORT_W, SHORT_H, 76, 340)
        filt = build_filter(rel, cfg, total, False, D, dx, is_section, is_shock,
                            s + audio_t0, ow=SHORT_W, oh=SHORT_H, ass_path=ass,
                            delogo_idx={k for k, x in enumerate(rel)
                                        if x["img"] in (cfg.get("delogo_idx") or set())})
        cmd = ["ffmpeg", "-y"]
        for x in rel:
            cmd += ["-i", str(proj["images"][x["img"]])]
        cmd += ["-i", str(voiceover)]
        out = out_dir / f"short_{idx}.mp4"
        cmd += ["-filter_complex", filt,
                "-map", "[vout]", "-map", "[afinal]",
                "-c:v", "libx264", "-preset", "medium", "-crf", "20",
                "-r", str(FPS), "-c:a", "aac", "-b:a", "160k",
                "-t", f"{total:.2f}", "-movflags", "+faststart", str(out)]
        run(cmd)
        made.append(out)
        print(f"      short_{idx}.mp4 ({total:.0f}s, sentences {a + 1}-{a + n})")
    return made

# ---------------------------------------------------------------- main
def load_project(proj_dir):
    proj = Path(proj_dir)
    script = proj / "script.txt"
    if not script.exists():
        raise SystemExit("script.txt not found in project dir")
    lines = [l.strip() for l in script.read_text(encoding="utf-8").splitlines() if l.strip()]
    voice = None
    for ext in ("mp3", "wav", "m4a"):
        c = proj / f"voiceover.{ext}"
        if c.exists():
            voice = c
            break
    if not voice:
        raise SystemExit("voiceover.mp3 (or .wav/.m4a) not found in project dir")
    imgdir = proj / "images"
    if not imgdir.is_dir():
        raise SystemExit("images/ folder not found in project dir")
    images = sorted([p for p in imgdir.iterdir()
                     if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp")])
    if len(images) != len(lines):
        raise SystemExit(f"images ({len(images)}) != script lines ({len(lines)}). "
                         "Name them 01..N in order.")
    music = proj / "music.mp3"
    if not music.exists():
        music = None
    return {"dir": proj, "lines": lines, "voice": voice, "images": images, "music": music}

def run_pipeline(proj_dir, cfg, model="tiny", no_shorts=False, progress_cb=None,
                 captions=True, language="en"):
    """Full pipeline callable from the web app. Returns (long_path, [shorts])."""
    proj = load_project(proj_dir)
    out_dir = Path(proj_dir) / "output"
    out_dir.mkdir(exist_ok=True)

    twords = transcribe_words(proj["voice"], model, language=language)
    if progress_cb:
        progress_cb(0.30)
    sentences, twords = align_sentences(proj["lines"], twords)
    sentences = detect_shock(sentences, cfg)
    audio_t0 = sentences[0]["start"]
    for x in sentences:
        x["start"] -= audio_t0
        x["end"] -= audio_t0
    for w in twords:
        w["start"] -= audio_t0
        w["end"] -= audio_t0
    build_caption_words(sentences, twords)
    if progress_cb:
        progress_cb(0.40)

    ass_path = None
    if captions:
        ass_path = out_dir / "captions.ass"
        write_ass(ass_path, sentences, W, H, cfg["caption_fontsize"], 70)

    long_out = out_dir / "horror_final.mp4"
    build_long_video(proj, sentences, twords, cfg, long_out, ass_path,
                     proj["voice"], proj["music"], audio_t0)
    if progress_cb:
        progress_cb(0.85)

    shorts_made = []
    if not no_shorts:
        shorts_made = build_shorts(proj, sentences, cfg, out_dir,
                                   proj["voice"], audio_t0, captions=captions)
    if progress_cb:
        progress_cb(1.0)
    return long_out, shorts_made

def main():
    ap = argparse.ArgumentParser(description="Horror Studio — auto edit engine")
    ap.add_argument("--project", required=True, help="project folder")
    ap.add_argument("--model", default="tiny", help="whisper model (tiny/base/small/medium)")
    ap.add_argument("--no-shorts", action="store_true")
    args = ap.parse_args()

    tool_dir = Path(__file__).parent
    cfg = dict(DEFAULT_CONFIG)
    for p in (tool_dir / "config.json", Path(args.project) / "config.json"):
        if p.exists():
            cfg.update(json.loads(p.read_text()))
            print(f"config loaded: {p}")

    long_out, shorts_made = run_pipeline(args.project, cfg, args.model, args.no_shorts)
    print("[5/5] ALL DONE")
    print(f"  long : {long_out}")
    for f in shorts_made:
        print(f"  short: {f}")

if __name__ == "__main__":
    main()
