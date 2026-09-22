"""Horror Studio — complete horror video tool (Streamlit).

One pipeline: script -> voiceover (built-in voice tool) -> AI images ->
auto-edited horror video with pro transitions, effects, captions.
Plus: thumbnail, upload metadata, multi-language dubs, bundled music.

Deploy: Streamlit Community Cloud.
"""
import shutil
import sys
import tempfile
from pathlib import Path

APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

import streamlit as st

import horror_edit
import image_gen
import thumbnail_gen
import metadata_gen
import dub as dub_mod
from horror_voice import engine as voice_engine
from horror_voice.script_parser import parse_script

# bundled font for captions
horror_edit.FONT_BOLD = str(APP_DIR / "fonts" / "DejaVuSans-Bold.ttf")
horror_edit.FONTS_DIR = str(APP_DIR / "fonts")

MUSIC_BUNDLED = APP_DIR / "music" / "dark_ambient.mp3"

st.set_page_config(page_title="Horror Studio", layout="wide")
st.title("🎃 Horror Studio — complete horror video tool")
st.write("Script likho → voiceover bane → images bane → final video ready. Sab ek jaga.")

# ---------------- session state ----------------
for k, v in {
    "lines": [], "voice_path": None, "timings": None,
    "images": {},      # idx -> bytes
    "img_src": {},     # idx -> "ai" | "upload" | "stock"
    "img_seeds": {},
    "long_video": None, "shorts": [],
    "thumb_path": None, "thumb_words": "",
    "meta": None,
    "dubs": {},        # lang_key -> {"video": path, "shorts": [...], "voice": path}
}.items():
    st.session_state.setdefault(k, v)

VOICE_CHOICES = {
    "Christopher (Signature Narrator)": "en-US-ChristopherNeural",
    "Guy (Grave Elder)": "en-US-GuyNeural",
    "Roger (Deep Modern)": "en-US-RogerNeural",
    "Eric (Dark Whisper)": "en-US-EricNeural",
    "Davis (Cold Authority)": "en-US-DavisNeural",
}

SUPERNATURAL_HINTS = [
    "ghost", "spirit", "demon", "devil", "shadow", "darkness", "whisper",
    "whispered", "haunt", "curse", "soul", "grave", "dead", "scream",
    "blood", "midnight", "moon",
]


def do_voiceover(lines, voice_id, whisper_mode, workdir, key_prefix=""):
    """Generate (or re-generate) the English voiceover."""
    manual = None
    if whisper_mode:
        manual = {}
        for i, line in enumerate(lines):
            low = line.lower()
            if '"' in line or "'" in line or any(
                    h in low for h in SUPERNATURAL_HINTS):
                manual[i] = {"emotion": "whisper"}
        if not manual:
            manual = None
    bar = st.progress(0, text="Voiceover ban raha hai...")
    try:
        mp3, timings = voice_engine.generate_voiceover(
            "\n".join(lines),
            voice=voice_id,
            manual=manual,
            out_dir=str(workdir / "voice"),
            progress_cb=lambda p, msg: bar.progress(p, text=msg),
        )
        st.session_state["voice_path"] = mp3
        st.session_state["timings"] = timings
        bar.progress(1.0, text="Ho gaya! ✅")
        st.success(f"Voiceover tayyar — {len(lines)} lines, "
                   f"{timings[-1]['end']:.1f}s audio ✅")
    except Exception as e:  # noqa: BLE001
        st.error(f"Voiceover fail: {e}")


# ================= STEP 1 — script + voiceover =================
st.header("1️⃣ Script + Voiceover")

with st.form("step1"):
    script_text = st.text_area(
        "Script (ek sentence per line — har line = ek clip)",
        height=200,
        placeholder="The house had been empty for forty years.\nNobody who entered ever came back.\nThen something screamed my name.",
    )
    col1, col2 = st.columns(2)
    with col1:
        voice_name = st.selectbox("Narrator voice", list(VOICE_CHOICES.keys()), index=0)
    with col2:
        whisper_mode = st.checkbox(
            "Supernatural lines par auto-whisper", value=True,
            help="Quoted aur paranormal lines whisper me — asli farq parega",
        )
    go_voice = st.form_submit_button("🎙️ Voiceover banao", type="primary")

if go_voice:
    lines = [l.strip() for l in script_text.splitlines() if l.strip()]
    if not lines:
        st.error("Script khaali hai — pehle lines likho.")
    else:
        st.session_state["lines"] = lines
        tmp = Path(tempfile.mkdtemp(prefix="horror_studio_"))
        st.session_state["workdir"] = str(tmp)
        st.session_state["images"] = {}
        st.session_state["img_src"] = {}
        st.session_state["img_seeds"] = {}
        st.session_state["long_video"] = None
        st.session_state["shorts"] = []
        st.session_state["thumb_path"] = None
        st.session_state["meta"] = None
        st.session_state["dubs"] = {}
        do_voiceover(lines, VOICE_CHOICES[voice_name], whisper_mode, tmp)

if st.session_state["voice_path"]:
    st.audio(st.session_state["voice_path"])
    c1, c2 = st.columns(2)
    with c1:
        with open(st.session_state["voice_path"], "rb") as f:
            st.download_button("⬇️ Voiceover MP3", f, file_name="voiceover.mp3",
                               mime="audio/mpeg")
    with c2:
        if st.button("🔄 Voiceover dobara banao"):
            do_voiceover(st.session_state["lines"],
                         VOICE_CHOICES[voice_name], whisper_mode,
                         Path(st.session_state["workdir"]))

# ================= STEP 2 — images =================
st.header("2️⃣ Images (AI khud banayega)")

lines = st.session_state["lines"]
if not lines:
    st.info("Pehle step 1 me voiceover banao — phir images.")
else:
    colA, colB = st.columns(2)
    with colA:
        img_model = st.selectbox("Image model", ["flux", "turbo"], index=0,
                                 help="flux = behtar quality, turbo = tez")
    with colB:
        pexels_key = st.text_input("Pexels API key (optional — stock photos ke liye)",
                                   type="password",
                                   help="pexels.com se free key — stock photo fallback ke liye")

    if st.button("🖼️ Sab images banao (AI)", type="primary"):
        bar = st.progress(0, text="Images ban rahi hain...")
        ok, fail = 0, []
        for i, line in enumerate(lines):
            try:
                seed = 1000 + i * 77
                data = image_gen.generate_image(
                    image_gen.horror_prompt(line), seed=seed, model=img_model)
                st.session_state["images"][i] = data
                st.session_state["img_src"][i] = "ai"
                st.session_state["img_seeds"][i] = seed
                ok += 1
            except Exception as e:  # noqa: BLE001
                fail.append(i + 1)
            bar.progress((i + 1) / len(lines),
                         text=f"Image {i + 1}/{len(lines)}...")
        bar.progress(1.0, text="Ho gaya! ✅")
        if fail:
            st.warning(f"Ye lines ki images nahi ban saki: {fail} — dobara try karo ya upload karo.")
        else:
            st.success(f"{ok} images tayyar ✅")

    # per-image grid: preview + regenerate + upload + stock
    if st.session_state["images"]:
        st.subheader("Images ka jaiza (pasand na aaye to dobara banao)")
        cols = st.columns(3)
        for i, line in enumerate(lines):
            with cols[i % 3]:
                st.caption(f"Clip {i + 1}: {line[:60]}")
                data = st.session_state["images"].get(i)
                if data:
                    st.image(data, use_container_width=True)
                b1, b2 = st.columns(2)
                with b1:
                    if st.button("🔄 Dobara", key=f"regen_{i}"):
                        try:
                            seed = st.session_state["img_seeds"].get(i, 1) + 913
                            st.session_state["images"][i] = image_gen.generate_image(
                                image_gen.horror_prompt(line), seed=seed,
                                model=img_model)
                            st.session_state["img_src"][i] = "ai"
                            st.session_state["img_seeds"][i] = seed
                            st.rerun()
                        except Exception as e:  # noqa: BLE001
                            st.error(f"Fail: {e}")
                with b2:
                    up = st.file_uploader("📤 Upload", type=["jpg", "jpeg", "png", "webp"],
                                          key=f"up_{i}", label_visibility="collapsed")
                    if up is not None:
                        st.session_state["images"][i] = up.getvalue()
                        st.session_state["img_src"][i] = "upload"
                        st.rerun()
                if pexels_key:
                    if st.button("📷 Stock photo", key=f"stock_{i}"):
                        try:
                            import re
                            kw = " ".join(re.findall(r"[a-zA-Z]{4,}", line)[:4])
                            res = image_gen.pexels_search(
                                f"horror dark {kw}", pexels_key, per_page=1)
                            if res:
                                st.session_state["images"][i] = image_gen.download_url(
                                    res[0]["url"])
                                st.session_state["img_src"][i] = "stock"
                                st.rerun()
                            else:
                                st.warning("Stock nahi mila.")
                        except Exception as e:  # noqa: BLE001
                            st.error(f"Stock fail: {e}")


def build_project(lines, voice_path, images, music_path, workdir, name="project"):
    """Assemble a render project folder. Returns proj Path."""
    proj = Path(workdir) / name
    if proj.exists():
        shutil.rmtree(proj)
    (proj / "images").mkdir(parents=True, exist_ok=True)
    (proj / "script.txt").write_text("\n".join(lines), encoding="utf-8")
    shutil.copy(voice_path, proj / "voiceover.mp3")
    for i in range(len(lines)):
        (proj / "images" / f"{i + 1:02d}.jpg").write_bytes(images[i])
    if music_path:
        shutil.copy(music_path, proj / "music.mp3")
    return proj


def parse_shorts(text):
    shorts = []
    for part in text.split(";"):
        part = part.strip()
        if part:
            a, b = part.split(",")
            shorts.append([int(a), int(b)])
    return shorts


# ================= STEP 3 — edit + render =================
st.header("3️⃣ Edit + Final Video")

if not st.session_state["images"] or len(st.session_state["images"]) != len(lines):
    st.info("Sab clips ki images tayyar karo (step 2) — phir video banegi.")
else:
    with st.form("step3"):
        c1, c2, c3 = st.columns(3)
        with c1:
            fx_grade = st.checkbox("🎨 Horror grade (cold + dark)", value=True)
            fx_grain = st.checkbox("🎞️ Film grain", value=True)
            fx_vignette = st.checkbox("◼ Vignette", value=True)
        with c2:
            fx_letterbox = st.checkbox("🎬 Letterbox (cinematic bars)", value=True)
            fx_flash = st.checkbox("⚡ Scare par flash-cut + red flash", value=True)
            captions_on = st.checkbox("💬 Captions (horror karaoke)", value=True)
        with c3:
            trans_speed = st.selectbox("Transition style", ["Smooth", "Snappy"], index=0)
            music_opt = st.selectbox(
                "🎵 Background music",
                ["Built-in dark ambient (auto)", "Apni upload karo", "Koi music nahi"],
                index=0)
            shorts_text = st.text_input("Shorts (line numbers: start,end; ...)",
                                        value="1,4")
        music_upload = None
        if music_opt == "Apni upload karo":
            music_upload = st.file_uploader("Music file", type=["mp3", "wav"])
        go_video = st.form_submit_button("🚀 Video banao", type="primary")

    if go_video:
        workdir = Path(st.session_state["workdir"])
        music_path = None
        if music_opt == "Built-in dark ambient (auto)" and MUSIC_BUNDLED.exists():
            music_path = MUSIC_BUNDLED
        elif music_opt == "Apni upload karo" and music_upload is not None:
            music_path = workdir / "custom_music.mp3"
            music_path.write_bytes(music_upload.getvalue())

        proj = build_project(lines, st.session_state["voice_path"],
                             st.session_state["images"], music_path,
                             workdir, "project")

        cfg = dict(horror_edit.DEFAULT_CONFIG)
        cfg["horror_grade"] = fx_grade
        cfg["film_grain"] = 6 if fx_grain else 0
        cfg["vignette"] = fx_vignette
        cfg["letterbox"] = fx_letterbox
        cfg["shock_flash"] = fx_flash
        # erase Pollinations watermark only on AI-generated images
        cfg["delogo_idx"] = {i for i, s in st.session_state["img_src"].items()
                             if s == "ai"}
        if trans_speed == "Snappy":
            cfg["xfade_duration"] = 0.25
        try:
            cfg["shorts"] = parse_shorts(shorts_text)
        except Exception:  # noqa: BLE001
            st.warning("Shorts ka format samajh nahi aaya — default istemal hoga.")

        bar = st.progress(0, text="Render ho raha hai...")
        try:
            with st.status("Video render ho rahi hai... (kuch minute lag sakte hain)",
                           expanded=True):
                long_out, shorts_made = horror_edit.run_pipeline(
                    str(proj), cfg, model="tiny",
                    progress_cb=lambda p: bar.progress(p, text="Render ho raha hai..."),
                    captions=captions_on, language="en",
                )
            st.session_state["long_video"] = str(long_out)
            st.session_state["shorts"] = [str(s) for s in shorts_made]
            st.session_state["render_cfg"] = {
                "captions": captions_on, "shorts": cfg["shorts"],
                "music": bool(music_path),
            }
            bar.progress(1.0, text="Ho gaya! ✅")
            st.success("Video tayyar! ✅ Neeche dekho aur download karo.")
        except Exception as e:  # noqa: BLE001
            st.error(f"Render fail: {e}")

if st.session_state["long_video"]:
    st.subheader("🎬 Final video (16:9)")
    st.video(st.session_state["long_video"])
    with open(st.session_state["long_video"], "rb") as f:
        st.download_button("⬇️ Final video download karo", f,
                           file_name="horror_final.mp4", mime="video/mp4")
if st.session_state["shorts"]:
    st.subheader("📱 Shorts (9:16)")
    cols = st.columns(3)
    for i, sp in enumerate(st.session_state["shorts"]):
        with cols[i % 3]:
            st.video(sp)
            with open(sp, "rb") as f:
                st.download_button(f"⬇️ Short {i + 1}", f,
                                   file_name=f"short_{i + 1}.mp4",
                                   mime="video/mp4", key=f"dl_s_{i}")

# ================= STEP 4 — thumbnail + metadata =================
st.header("4️⃣ Thumbnail + Upload Metadata")

if st.session_state["long_video"] and st.session_state["images"]:
    if st.button("🖼️ Thumbnail banao", type="primary"):
        try:
            img_list = [st.session_state["images"][i]
                        for i in range(len(st.session_state["lines"]))]
            out = Path(st.session_state["workdir"]) / "thumbnail.jpg"
            _, words = thumbnail_gen.generate_thumbnail_for_script(
                st.session_state["lines"], img_list, out)
            st.session_state["thumb_path"] = str(out)
            st.session_state["thumb_words"] = words
            st.success("Thumbnail tayyar ✅")
        except Exception as e:  # noqa: BLE001
            st.error(f"Thumbnail fail: {e}")

    if st.session_state["thumb_path"]:
        st.image(st.session_state["thumb_path"], width=480)
        with open(st.session_state["thumb_path"], "rb") as f:
            st.download_button("⬇️ Thumbnail download karo", f,
                               file_name="thumbnail.jpg", mime="image/jpeg")

    if st.button("📝 Title / Description / Tags banao"):
        meta = metadata_gen.make_metadata(
            st.session_state["lines"], st.session_state["thumb_words"])
        st.session_state["meta"] = meta
    if st.session_state["meta"]:
        meta = st.session_state["meta"]
        st.text_input("Title (copy karo)", meta["title"])
        st.text_area("Description (copy karo)", meta["description"], height=180)
        st.text_area("Tags (copy karo)", ", ".join(meta["tags"]), height=80)
        st.download_button("⬇️ Metadata .txt download karo",
                           metadata_gen.metadata_text(meta),
                           file_name="upload_metadata.txt", mime="text/plain")
else:
    st.info("Pehle final video banao (step 3) — phir thumbnail aur metadata.")

# ================= STEP 5 — multi-language dub =================
st.header("5️⃣ Doosri Languages me Dub (optional)")

if st.session_state["long_video"] and st.session_state["images"]:
    lang_key = st.selectbox(
        "Dub language",
        list(dub_mod.DUB_VOICES.keys()),
        format_func=lambda k: dub_mod.DUB_VOICES[k]["label"],
    )
    if st.button(f"🌍 {dub_mod.DUB_VOICES[lang_key]['label']} dub banao",
                 type="primary"):
        workdir = Path(st.session_state["workdir"])
        try:
            bar = st.progress(0, text="Translate ho raha hai...")
            tlines = dub_mod.translate_lines(
                st.session_state["lines"],
                dub_mod.DUB_VOICES[lang_key]["dest"],
                progress_cb=lambda p: bar.progress(p * 0.3, text="Translate ho raha hai..."),
            )
            st.session_state[f"dub_lines_{lang_key}"] = tlines
            bar.progress(0.35, text="Dub voiceover ban raha hai...")
            dub_dir = workdir / f"dub_{lang_key}"
            dub_dir.mkdir(exist_ok=True)
            mp3, timings, norm_lines = dub_mod.dub_voiceover(
                tlines, lang_key, dub_dir / "voice",
                progress_cb=lambda p, msg: bar.progress(
                    0.35 + p * 0.25, text="Dub voiceover ban raha hai..."),
            )
            st.session_state[f"dub_voice_{lang_key}"] = mp3

            cfg = dict(horror_edit.DEFAULT_CONFIG)
            cfg["shorts"] = st.session_state.get("render_cfg", {}).get(
                "shorts", [[1, 4]])
            cfg["delogo_idx"] = {i for i, s in st.session_state["img_src"].items()
                                 if s == "ai"}
            captions_on = st.session_state.get("render_cfg", {}).get(
                "captions", True)
            music_path = MUSIC_BUNDLED if (
                st.session_state.get("render_cfg", {}).get("music")
                and MUSIC_BUNDLED.exists()) else None
            proj = build_project(norm_lines, mp3, st.session_state["images"],
                                 music_path, workdir, f"project_dub_{lang_key}")
            with st.status(f"{dub_mod.DUB_VOICES[lang_key]['label']} video render ho rahi hai...",
                           expanded=True):
                long_out, shorts_made = horror_edit.run_pipeline(
                    str(proj), cfg, model="tiny",
                    progress_cb=lambda p: bar.progress(
                        0.6 + p * 0.4, text="Dub video render ho rahi hai..."),
                    captions=captions_on,
                    language=dub_mod.DUB_VOICES[lang_key]["lang"],
                )
            st.session_state["dubs"][lang_key] = {
                "video": str(long_out),
                "shorts": [str(s) for s in shorts_made],
                "voice": mp3,
            }
            bar.progress(1.0, text="Ho gaya! ✅")
            st.success(f"{dub_mod.DUB_VOICES[lang_key]['label']} dub tayyar ✅")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Dub fail: {e}")

    for lk, info in st.session_state["dubs"].items():
        label = dub_mod.DUB_VOICES[lk]["label"]
        st.subheader(f"🌍 {label} dub")
        st.video(info["video"])
        with open(info["video"], "rb") as f:
            st.download_button(f"⬇️ {label} video download karo", f,
                               file_name=f"horror_{lk}.mp4", mime="video/mp4",
                               key=f"dl_dub_{lk}")
        with open(info["voice"], "rb") as f:
            st.download_button(f"⬇️ {label} voiceover MP3", f,
                               file_name=f"voiceover_{lk}.mp3",
                               mime="audio/mpeg", key=f"dl_dubv_{lk}")
else:
    st.info("Pehle final video banao (step 3) — phir dub.")

st.caption("💡 Tip: Horror Voice Studio wali voice yahin banti hai — alag app kholne ki zaroorat nahi.")
