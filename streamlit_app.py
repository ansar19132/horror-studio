"""Horror Studio — complete horror video tool (Streamlit).

CapCut-style layout: left sidebar me saare panels (Script, Voice, Images,
Edit & Video, Thumbnail, Metadata, Dubs) + Gemini key manager. Beech me
har panel ka apna frame — preview, timeline, live studio.

One pipeline: script -> voiceover -> AI images -> auto-edited horror video
with pro transitions, effects, captions. Plus: thumbnail, upload metadata,
multi-language dubs, bundled music.

Deploy: Streamlit Community Cloud.
"""
import json
import shutil
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))

import streamlit as st

import horror_edit
import image_gen
import thumbnail_gen
import metadata_gen
import gemini_helper
import dub as dub_mod
from horror_voice import engine as voice_engine

# bundled font for captions
horror_edit.FONT_BOLD = str(APP_DIR / "fonts" / "DejaVuSans-Bold.ttf")
horror_edit.FONTS_DIR = str(APP_DIR / "fonts")

MUSIC_BUNDLED = APP_DIR / "music" / "dark_ambient.mp3"

st.set_page_config(page_title="Horror Studio", layout="wide")

# ---------------- session state ----------------
for k, v in {
    "lines": [], "script_text": "",
    "voice_path": None, "timings": None,
    "images": {},      # idx -> bytes
    "img_src": {},     # idx -> "ai" | "upload" | "stock"
    "img_seeds": {},
    "workdir": None,
    "render_cfg": None,
    "long_video": None, "shorts": [],
    "thumb_path": None, "thumb_words": "",
    "meta": None,
    "gemini_titles": None, "thumb_ai_path": None,
    "gemini_keys_ok": None,
    "dubs": {},        # lang_key -> {"video": path, "shorts": [...], "voice": path}
}.items():
    st.session_state.setdefault(k, v)

# ---------------- project auto-save / resume ----------------
# Har step ke baad progress disk par save hota hai. App band ho jaye ya
# browser refresh ho jaye to dobara kholne par wahi se continue hota hai.
# Clear SIRF user ke button se hota hai — khud kuch delete nahi hota.
PROJECTS_DIR = APP_DIR / "projects"
AUTOSAVE_DIR = PROJECTS_DIR / "autosave"
AUTOSAVE_JSON = AUTOSAVE_DIR / "project.json"
AUTOSAVE_IMG_DIR = AUTOSAVE_DIR / "images"
PROJECTS_DIR.mkdir(exist_ok=True)
AUTOSAVE_DIR.mkdir(exist_ok=True)
AUTOSAVE_IMG_DIR.mkdir(exist_ok=True)

SAVE_KEYS = ["lines", "script_text", "voice_path", "timings", "img_src",
             "img_seeds", "workdir", "render_cfg", "long_video", "shorts",
             "thumb_path", "thumb_words", "meta", "dubs",
             "gemini_titles", "thumb_ai_path"]


def _write_image_to_disk(i, data):
    try:
        (AUTOSAVE_IMG_DIR / f"{int(i):03d}.jpg").write_bytes(data)
        return True
    except Exception:  # noqa: BLE001
        return False


def save_project():
    """Persist current progress to disk. Must never break the app."""
    try:
        data = {}
        for k in SAVE_KEYS:
            v = st.session_state.get(k)
            try:
                json.dumps(v)
                data[k] = v
            except (TypeError, ValueError):
                data[k] = None
        images = st.session_state.get("images", {}) or {}
        idx_done = []
        for i, b in images.items():
            if not b:
                continue
            p = AUTOSAVE_IMG_DIR / f"{int(i):03d}.jpg"
            if not p.exists():
                _write_image_to_disk(i, b)
            idx_done.append(int(i))
        data["image_idx"] = sorted(idx_done)
        AUTOSAVE_JSON.write_text(json.dumps(data), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def has_saved_project():
    return AUTOSAVE_JSON.exists()


def load_project():
    """Restore auto-saved project into session state."""
    try:
        data = json.loads(AUTOSAVE_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return False
    for k in SAVE_KEYS:
        if k in data and data[k] is not None:
            st.session_state[k] = data[k]
    for k in ("img_src", "img_seeds"):
        d = st.session_state.get(k) or {}
        try:
            st.session_state[k] = {int(kk): vv for kk, vv in d.items()}
        except Exception:  # noqa: BLE001
            pass
    images = {}
    for i in data.get("image_idx", []):
        try:
            p = AUTOSAVE_IMG_DIR / f"{int(i):03d}.jpg"
            if p.exists():
                images[int(i)] = p.read_bytes()
        except Exception:  # noqa: BLE001
            pass
    st.session_state["images"] = images
    for k in ("voice_path", "long_video", "thumb_path"):
        p = st.session_state.get(k)
        if p and not Path(p).exists():
            st.session_state[k] = None
    st.session_state["shorts"] = [
        s for s in (st.session_state.get("shorts") or []) if Path(s).exists()]
    dubs = st.session_state.get("dubs") or {}
    st.session_state["dubs"] = {
        k: v for k, v in dubs.items()
        if isinstance(v, dict) and v.get("video") and Path(v["video"]).exists()}
    return True


def reset_autosave_disk():
    """Sirf disk ka save wipe karo (naya project) — session state waisi rahe."""
    shutil.rmtree(AUTOSAVE_DIR, ignore_errors=True)
    AUTOSAVE_DIR.mkdir(exist_ok=True)
    AUTOSAVE_IMG_DIR.mkdir(exist_ok=True)


def clear_saved_project():
    """Full clear — sirf user ke clear button se call hota hai."""
    reset_autosave_disk()
    for k, v in {
        "lines": [], "script_text": "",
        "voice_path": None, "timings": None,
        "images": {}, "img_src": {}, "img_seeds": {},
        "workdir": None, "render_cfg": None,
        "long_video": None, "shorts": [],
        "thumb_path": None, "thumb_words": "",
        "meta": None, "dubs": {},
        "gemini_titles": None, "thumb_ai_path": None,
    }.items():
        st.session_state[k] = v


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

STEPS = ["📝 Script", "🎙 Voice", "🖼 Images", "🎞 Edit & Video",
         "🖼️ Thumbnail", "🏷 Metadata", "🌍 Dubs"]


def do_voiceover(lines, voice_id, whisper_mode, workdir):
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
        save_project()
        bar.progress(1.0, text="Ho gaya! ✅")
        st.success(f"Voiceover tayyar — {len(lines)} lines, "
                   f"{timings[-1]['end']:.1f}s audio ✅")
    except Exception as e:  # noqa: BLE001
        st.error(f"Voiceover fail: {e}")


def current_script_lines():
    txt = st.session_state.get("script_text") or ""
    ls = [l.strip() for l in txt.splitlines() if l.strip()]
    return ls or list(st.session_state.get("lines") or [])


def _paint_line_status(slot, i, line):
    """Left pane: ek line ka live status."""
    data = st.session_state["images"].get(i)
    src = st.session_state["img_src"].get(i, "")
    icon = "✅" if data else "⏳"
    src_tag = {"ai": "🤖", "upload": "📤", "stock": "📷"}.get(src, "")
    tag = f" {src_tag}" if src_tag else ""
    slot.caption(f"{icon}{tag} **{i + 1}.** {line[:80]}")


def _paint_image_actions(i, line):
    """Right pane: ek image ke neeche correction buttons."""
    img_model = st.session_state.get("img_model", "flux")
    pexels_key = st.session_state.get("pexels_key", "")
    b1, b2 = st.columns(2)
    with b1:
        if st.button("🔄 Dobara", key=f"regen_{i}"):
            try:
                seed = st.session_state["img_seeds"].get(i, 1) + 913
                data = image_gen.generate_image(
                    image_gen.horror_prompt(line), seed=seed,
                    model=img_model)
                st.session_state["images"][i] = data
                st.session_state["img_src"][i] = "ai"
                st.session_state["img_seeds"][i] = seed
                _write_image_to_disk(i, data)
                save_project()
                st.rerun()
            except Exception as e:  # noqa: BLE001
                st.error(f"Fail: {e}")
    with b2:
        up = st.file_uploader("📤", type=["jpg", "jpeg", "png", "webp"],
                              key=f"up_{i}", label_visibility="collapsed")
        if up is not None:
            data = up.getvalue()
            if st.session_state["images"].get(i) != data:
                st.session_state["images"][i] = data
                st.session_state["img_src"][i] = "upload"
                _write_image_to_disk(i, data)
                save_project()
                st.rerun()
    if pexels_key:
        if st.button("📷 Stock photo", key=f"stock_{i}"):
            try:
                import re
                kw = " ".join(re.findall(r"[a-zA-Z]{4,}", line)[:4])
                res = image_gen.pexels_search(
                    f"horror dark {kw}", pexels_key, per_page=1)
                if res:
                    data = image_gen.download_url(res[0]["url"])
                    st.session_state["images"][i] = data
                    st.session_state["img_src"][i] = "stock"
                    _write_image_to_disk(i, data)
                    save_project()
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


def run_auto_pipeline():
    """🤖 Auto Pilot: ek click me script -> voiceover -> images -> video.

    Har step complete hote hi agla khud start hota hai — kuch dabane ki
    zaroorat nahi. Beech me ruke to wahi panel se manually continue karo.
    """
    st.header("🤖 Auto Pilot chal raha hai...")
    st.caption("Step complete hote hi agla khud start hoga. Roko mat — "
               "kuch minute lag sakte hain.")
    lines = current_script_lines()
    if not lines:
        st.error("Script khaali hai — pehle 📝 Script panel me likho.")
        return

    # ---- step 1/3: voiceover ----
    st.subheader("1/3 — 🎙 Voiceover")
    reset_autosave_disk()
    st.session_state["lines"] = lines
    tmp = AUTOSAVE_DIR / "work"
    if tmp.exists():
        shutil.rmtree(tmp)
    tmp.mkdir(parents=True, exist_ok=True)
    st.session_state["workdir"] = str(tmp)
    for k, v in {"images": {}, "img_src": {}, "img_seeds": {},
                 "long_video": None, "shorts": [],
                 "thumb_path": None, "thumb_words": "",
                 "gemini_titles": None, "thumb_ai_path": None,
                 "meta": None, "dubs": {}, "render_cfg": None}.items():
        st.session_state[k] = v
    vname = st.session_state.get("voice_sel_name", list(VOICE_CHOICES)[0])
    do_voiceover(lines, VOICE_CHOICES[vname],
                 st.session_state.get("whisper_mode", True), tmp)
    if not st.session_state["voice_path"]:
        st.error("Voiceover fail — Auto Pilot ruk gaya.")
        return

    # ---- step 2/3: images ----
    st.subheader("2/3 — 🖼 Images")
    bar = st.progress(0, text="Images ban rahi hain...")
    for i, line in enumerate(lines):
        try:
            seed = 1000 + i * 77
            data = image_gen.generate_image(
                image_gen.horror_prompt(line), seed=seed, model="flux")
            st.session_state["images"][i] = data
            st.session_state["img_src"][i] = "ai"
            st.session_state["img_seeds"][i] = seed
            _write_image_to_disk(i, data)
        except Exception as e:  # noqa: BLE001
            st.warning(f"Clip {i + 1} fail: {e} — baad me 🖼 Images panel se dobara banao")
        bar.progress((i + 1) / len(lines),
                     text=f"Image {i + 1}/{len(lines)}")
    save_project()

    # ---- step 3/3: render ----
    st.subheader("3/3 — 🎞 Video render")
    workdir = Path(st.session_state["workdir"])
    music_path = MUSIC_BUNDLED if MUSIC_BUNDLED.exists() else None
    proj = build_project(lines, st.session_state["voice_path"],
                         st.session_state["images"], music_path,
                         workdir, "project")
    cfg = dict(horror_edit.DEFAULT_CONFIG)
    cfg["delogo_idx"] = {i for i, s in st.session_state["img_src"].items()
                         if s == "ai"}
    bar2 = st.progress(0, text="Render ho raha hai...")
    n_clips = len(lines)
    try:
        with st.status("Video render ho rahi hai...", expanded=True):
            long_out, shorts_made = horror_edit.run_pipeline(
                str(proj), cfg, model="tiny",
                progress_cb=lambda p: bar2.progress(
                    p, text=f"Clip {min(int(p * n_clips) + 1, n_clips)}/{n_clips}"),
                captions=True, language="en",
            )
        st.session_state["long_video"] = str(long_out)
        st.session_state["shorts"] = [str(s) for s in shorts_made]
        st.session_state["render_cfg"] = {
            "captions": True, "shorts": cfg["shorts"],
            "music": bool(music_path),
        }
        save_project()
        bar2.progress(1.0, text="Ho gaya! ✅")
        st.success("🎉 Auto Pilot complete! Video tayyar — "
                   "🎞 Edit & Video panel me dekho.")
        st.balloons()
    except Exception as e:  # noqa: BLE001
        st.error(f"Render fail: {e}")


# ============================ SIDEBAR ============================
with st.sidebar:
    st.title("🎃 Horror Studio")
    st.caption("CapCut-style panels — sab kuch ek jaga")
    st.radio("🌓 Theme", ["🌙 Night", "🌞 Day"], key="app_theme",
             horizontal=True)
    if st.button("🤖 Auto: Script → Video", type="primary",
                 help="Ek click — voiceover, images aur final video khud ban jayenge"):
        st.session_state["auto_run"] = True
        st.rerun()
    st.divider()
    step = st.radio("Panels", STEPS, key="nav_step")

    st.divider()
    # project status
    _lines = st.session_state.get("lines") or []
    _n_img = sum(1 for i in range(len(_lines))
                 if st.session_state["images"].get(i))
    st.caption(
        f"🎙 {'✅' if st.session_state['voice_path'] else '⬜'}"
        f" · 🖼 {_n_img}/{len(_lines)}"
        f" · 🎞 {'✅' if st.session_state['long_video'] else '⬜'}"
        f" · 🖼️ {'✅' if st.session_state['thumb_path'] or st.session_state.get('thumb_ai_path') else '⬜'}"
    )

    st.divider()
    # Gemini key manager — har panel se reachable
    st.subheader("🔑 Gemini API")
    st.link_button("🆓 Free API key lo",
                   "https://aistudio.google.com/apikey",
                   help="Google AI Studio khulega — 'Get API key' dabao, bilkul free")
    st.text_area("Keys (har line me ek — ek ya zyada accounts ki)",
                 height=70, key="gemini_keys_raw",
                 help="Keys sirf isi session me rehti hain — save nahi hotin.")
    if st.button("🔌 Connect",
                 disabled=not (st.session_state.get("gemini_keys_raw") or "").strip()):
        keys = [k.strip() for k in
                (st.session_state.get("gemini_keys_raw") or "").splitlines()
                if k.strip()]
        working = []
        for k in keys:
            ok, msg = gemini_helper.test_key(k)
            mark = "✅" if ok else "❌"
            st.caption(f"{mark} `...{k[-4:]}` — {msg}")
            if ok:
                working.append(k)
        st.session_state["gemini_keys_ok"] = working
        if working:
            st.success(f"{len(working)}/{len(keys)} connected ✅")
        else:
            st.error("Koi key connect nahi hui")
    _conn = st.session_state.get("gemini_keys_ok") or []
    if _conn:
        st.caption(f"🔌 {len(_conn)} key(s) connected")

    st.divider()
    with st.expander("⚙️ Project"):
        st.caption("💾 Har step ke baad auto-save. Server restart par save "
                   "khatam ho sakta hai — final video download karke rakho.")
        st.session_state.setdefault("_clear_confirm2", False)
        if st.button("🗑️ Naya project (sab clear)"):
            st.session_state["_clear_confirm2"] = True
        if st.session_state["_clear_confirm2"]:
            st.error("⚠️ Pakka? Sab kuch delete ho jayega.")
            if st.button("Haan, sab clear karo", key="clear_yes",
                         type="primary"):
                clear_saved_project()
                st.session_state["_clear_confirm2"] = False
                st.rerun()
            if st.button("Rehne do", key="clear_no"):
                st.session_state["_clear_confirm2"] = False
                st.rerun()

# ============================ MAIN ============================
st.title("🎃 Horror Studio")
st.caption("Script → voiceover → images → final video. Sidebar se panel badlo.")

# day theme (night default config.toml se aata hai)
if st.session_state.get("app_theme") == "🌞 Day":
    st.markdown("""<style>
    .stApp { background-color: #f4f4f5; }
    section[data-testid="stSidebar"] { background-color: #ffffff; }
    .stApp h1, .stApp h2, .stApp h3, .stApp p, .stApp span,
    .stApp div, .stApp label, .stApp caption { color: #18181b; }
    .stTextInput input, .stTextArea textarea { background-color: #ffffff; color: #18181b; }
    .stRadio div[role="radiogroup"] label { color: #18181b; }
    </style>""", unsafe_allow_html=True)

# resume banner
st.session_state.setdefault("_booted", False)
st.session_state.setdefault("_clear_confirm", False)
if (not st.session_state["_booted"] and has_saved_project()
        and not st.session_state.get("lines")):
    try:
        _saved = json.loads(AUTOSAVE_JSON.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        _saved = {}
    _n_lines = len(_saved.get("lines") or [])
    _n_imgs = len(_saved.get("image_idx") or [])
    _has_video = bool(_saved.get("long_video"))
    st.warning(
        f"💾 Pichla project mila — {_n_lines} lines, {_n_imgs} images"
        + (" — video bhi bani hui hai ✅" if _has_video else "")
        + ". Wahi se continue karo, ya clear karke naya shuru karo."
    )
    _rc1, _rc2 = st.columns(2)
    with _rc1:
        if st.button("▶️ Wahi se continue karo", type="primary"):
            if load_project():
                st.session_state["_booted"] = True
                st.success("Project wapas load ho gaya ✅")
                st.rerun()
            else:
                st.error("Save load nahi ho saka — naya shuru karo.")
    with _rc2:
        if st.button("🗑️ Clear karke naya shuru karo"):
            st.session_state["_clear_confirm"] = True
    if st.session_state["_clear_confirm"]:
        st.error("⚠️ Pakka? Pichla project hamesha ke liye delete ho jayega.")
        _cc1, _cc2 = st.columns(2)
        with _cc1:
            if st.button("Haan, sab clear karo", type="primary"):
                clear_saved_project()
                st.session_state["_booted"] = True
                st.session_state["_clear_confirm"] = False
                st.rerun()
        with _cc2:
            if st.button("Rehne do"):
                st.session_state["_clear_confirm"] = False
                st.rerun()
else:
    st.session_state["_booted"] = True

# 🤖 Auto Pilot — ek click me saare steps
st.session_state.setdefault("auto_run", False)
if st.session_state.pop("auto_run", False):
    run_auto_pipeline()
    st.divider()


# ============================ PANELS ============================
def panel_script():
    st.header("📝 Script")
    if st.session_state.get("lines") and not st.session_state.get("script_text"):
        st.session_state["script_text"] = "\n".join(
            st.session_state["lines"])
    st.text_area("Script (ek sentence per line — har line = ek clip)",
                 height=320, key="script_text",
                 placeholder="The house had been empty for forty years.\n"
                             "Nobody who entered ever came back.\n"
                             "Then something screamed my name.")
    n = len(current_script_lines())
    st.caption(f"📊 {n} lines — har line ek clip banegi")


def panel_voice():
    st.header("🎙 Voiceover")
    lines = current_script_lines()
    if not lines:
        st.info("Pehle 📝 Script panel me script likho.")
        return
    st.caption(f"📊 {len(lines)} lines")
    c1, c2 = st.columns(2)
    with c1:
        st.selectbox("Narrator voice", list(VOICE_CHOICES.keys()), index=0,
                     key="voice_sel_name")
    with c2:
        st.checkbox("Supernatural lines par auto-whisper", value=True,
                    key="whisper_mode",
                    help="Quoted aur paranormal lines whisper me")
    if st.button("🎙️ Voiceover banao", type="primary"):
        reset_autosave_disk()
        st.session_state["lines"] = lines
        tmp = AUTOSAVE_DIR / "work"
        if tmp.exists():
            shutil.rmtree(tmp)
        tmp.mkdir(parents=True, exist_ok=True)
        st.session_state["workdir"] = str(tmp)
        for k, v in {"images": {}, "img_src": {}, "img_seeds": {},
                     "long_video": None, "shorts": [],
                     "thumb_path": None, "thumb_words": "",
                     "gemini_titles": None, "thumb_ai_path": None,
                     "meta": None, "dubs": {}, "render_cfg": None}.items():
            st.session_state[k] = v
        do_voiceover(lines, VOICE_CHOICES[st.session_state["voice_sel_name"]],
                     st.session_state["whisper_mode"], tmp)
    if st.session_state["voice_path"]:
        st.audio(st.session_state["voice_path"])
        c1, c2 = st.columns(2)
        with c1:
            with open(st.session_state["voice_path"], "rb") as f:
                st.download_button("⬇️ Voiceover MP3", f,
                                   file_name="voiceover.mp3",
                                   mime="audio/mpeg")
        with c2:
            if st.button("🔄 Voiceover dobara banao"):
                do_voiceover(st.session_state["lines"],
                             VOICE_CHOICES[st.session_state["voice_sel_name"]],
                             st.session_state["whisper_mode"],
                             Path(st.session_state["workdir"]))


def panel_images():
    st.header("🖼 Images")
    lines = st.session_state["lines"]
    if not lines:
        st.info("Pehle 🎙 Voice panel me voiceover banao.")
        return
    colA, colB = st.columns(2)
    with colA:
        st.selectbox("Image model", ["flux", "turbo"], index=0, key="img_model",
                     help="flux = behtar quality, turbo = tez")
    with colB:
        st.text_input("Pexels API key (optional — stock photos ke liye)",
                      type="password", key="pexels_key",
                      help="pexels.com se free key — stock photo fallback ke liye")
    st.button("🖼️ Sab images banao (AI)", type="primary", key="go_images")

    st.subheader("🎬 Live Studio")
    overall_slot = st.empty()
    _done0 = sum(1 for i in range(len(lines))
                 if st.session_state["images"].get(i))
    overall_slot.caption(f"📊 {_done0}/{len(lines)} images tayyar")
    pane_script, pane_visual = st.columns([1, 1.15])
    status_slots, img_slots = {}, {}
    with pane_script:
        st.caption("📜 Script + live status")
        for i, line in enumerate(lines):
            status_slots[i] = st.empty()
            _paint_line_status(status_slots[i], i, line)
    with pane_visual:
        st.caption("🖼️ Images — bante hi yahan nazar aayengi")
        vcols = st.columns(2)
        for i, line in enumerate(lines):
            with vcols[i % 2]:
                st.caption(f"🎞️ Clip {i + 1}: {line[:55]}")
                img_slots[i] = st.empty()
                data = st.session_state["images"].get(i)
                if data:
                    img_slots[i].image(data, use_container_width=True)
                else:
                    img_slots[i].caption("⏳ Abhi nahi bani")
                _paint_image_actions(i, line)

    if st.session_state.get("go_images"):
        st.session_state["go_images"] = False
        ok, fail, done = 0, [], _done0
        for i, line in enumerate(lines):
            if st.session_state["images"].get(i):
                continue
            status_slots[i].caption(f"🎨 **{i + 1}.** {line[:80]} — ban rahi hai...")
            img_slots[i].caption("🎨 Ban rahi hai...")
            try:
                seed = 1000 + i * 77
                data = image_gen.generate_image(
                    image_gen.horror_prompt(line), seed=seed,
                    model=st.session_state.get("img_model", "flux"))
                st.session_state["images"][i] = data
                st.session_state["img_src"][i] = "ai"
                st.session_state["img_seeds"][i] = seed
                _write_image_to_disk(i, data)
                save_project()
                ok += 1
                done += 1
                _paint_line_status(status_slots[i], i, line)
                img_slots[i].image(data, use_container_width=True)
                overall_slot.caption(f"📊 {done}/{len(lines)} images tayyar")
            except Exception as e:  # noqa: BLE001
                fail.append(i + 1)
                status_slots[i].caption(f"❌ **{i + 1}.** {line[:80]} — fail")
                img_slots[i].caption("❌ Nahi ban saki — dobara try karo")
        if fail:
            st.warning(f"Ye clips ki images nahi ban saki: {fail} — "
                       "🔄 Dobara dabao ya upload karo.")
        else:
            st.success(f"{ok} nayi images tayyar ✅ — sab {done}/{len(lines)} ready")


def panel_edit():
    st.header("🎞 Edit & Video")
    lines = st.session_state["lines"]
    if not lines:
        st.info("Pehle 🎙 Voice panel me voiceover banao.")
        return

    # preview frame
    st.subheader("🖥 Preview")
    if st.session_state["long_video"]:
        st.video(st.session_state["long_video"])
        with open(st.session_state["long_video"], "rb") as f:
            st.download_button("⬇️ Final video download karo", f,
                               file_name="horror_final.mp4",
                               mime="video/mp4")
    else:
        st.info("Render ke baad final video yahan preview hogi.")

    # timeline frame — saare clips ek jaga
    with st.expander("🎞 Timeline — saare clips (image order)", expanded=False):
        tcols = st.columns(6)
        for i in range(len(lines)):
            with tcols[i % 6]:
                d = st.session_state["images"].get(i)
                if d:
                    st.image(d, caption=f"Clip {i + 1}",
                             use_container_width=True)
                else:
                    st.caption(f"⬜ Clip {i + 1}")

    st.divider()
    if (not st.session_state["images"]
            or len(st.session_state["images"]) != len(lines)):
        st.info("Sab clips ki images tayyar karo (🖼 Images panel) — phir video banegi.")
        return

    with st.form("edit_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            fx_grade = st.checkbox("🎨 Horror grade (cold + dark)", value=True)
            fx_grain = st.checkbox("🎞️ Film grain", value=True)
            fx_vignette = st.checkbox("◼ Vignette", value=True)
        with c2:
            fx_letterbox = st.checkbox("🎬 Letterbox (cinematic bars)", value=True)
            fx_flash = st.checkbox("⚡ Scare par flash-cut + red flash", value=True)
            captions_on = st.checkbox("💬 Captions (horror karaoke)", value=True)
            hl_intro = st.checkbox("⚡ Highlight intro (20s teaser @1.65x, start me)",
                                   value=True,
                                   help="Video ka sab se interesting 20s hissa tez karke shuru me lagao")
        with c3:
            trans_speed = st.selectbox("Transition style", ["Smooth", "Snappy"],
                                       index=0)
            music_opt = st.selectbox(
                "🎵 Background music",
                ["Built-in dark ambient (auto)", "Apni upload karo",
                 "Koi music nahi"], index=0)
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
        cfg["delogo_idx"] = {i for i, s in st.session_state["img_src"].items()
                             if s == "ai"}
        cfg["highlight_intro"] = hl_intro
        if trans_speed == "Snappy":
            cfg["xfade_duration"] = 0.25
        try:
            cfg["shorts"] = parse_shorts(shorts_text)
        except Exception:  # noqa: BLE001
            st.warning("Shorts ka format samajh nahi aaya — default istemal hoga.")

        bar = st.progress(0, text="Render ho raha hai...")
        render_slot = st.empty()
        n_clips = len(lines)

        def _render_cb(p):
            clip = min(int(p * n_clips) + 1, n_clips) if n_clips else 0
            bar.progress(p, text=f"Clip {clip}/{n_clips} — edit ho raha hai...")
            render_slot.caption(
                f"🎬 Clip {clip}/{n_clips} — transitions, effects, captions lag rahe hain...")

        try:
            with st.status("Video render ho rahi hai... (kuch minute lag sakte hain)",
                           expanded=True):
                long_out, shorts_made = horror_edit.run_pipeline(
                    str(proj), cfg, model="tiny",
                    progress_cb=_render_cb,
                    captions=captions_on, language="en",
                )
            st.session_state["long_video"] = str(long_out)
            st.session_state["shorts"] = [str(s) for s in shorts_made]
            st.session_state["render_cfg"] = {
                "captions": captions_on, "shorts": cfg["shorts"],
                "music": bool(music_path),
            }
            save_project()
            bar.progress(1.0, text="Ho gaya! ✅")
            st.success("Video tayyar! ✅ Oopar preview me dekho.")
            st.rerun()
        except Exception as e:  # noqa: BLE001
            st.error(f"Render fail: {e}")

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


def panel_thumbnail():
    st.header("🖼️ Thumbnail")
    lines = st.session_state["lines"]
    if not (st.session_state["long_video"] and st.session_state["images"]):
        st.info("Pehle 🎞 Edit & Video panel me final video banao.")
        return
    connected = st.session_state.get("gemini_keys_ok") or []

    if st.button("🖼️ Thumbnail banao (simple wala)", type="primary"):
        try:
            img_list = [st.session_state["images"][i]
                        for i in range(len(lines))]
            out = Path(st.session_state["workdir"]) / "thumbnail.jpg"
            _, words = thumbnail_gen.generate_thumbnail_for_script(
                lines, img_list, out)
            st.session_state["thumb_path"] = str(out)
            st.session_state["thumb_words"] = words
            save_project()
            st.success("Thumbnail tayyar ✅")
        except Exception as e:  # noqa: BLE001
            st.error(f"Thumbnail fail: {e}")

    if st.button("🎨 Gemini se AI Thumbnail", disabled=not connected,
                 help="Sidebar me 🔑 Gemini keys Connect karo"):
        try:
            with st.spinner("Gemini thumbnail bana raha hai... (1-2 min)"):
                img_bytes = gemini_helper.generate_thumbnail(
                    connected, lines,
                    st.session_state.get("thumb_words", ""))
            out = Path(st.session_state["workdir"]) / "thumbnail_gemini.jpg"
            out.write_bytes(img_bytes)
            st.session_state["thumb_ai_path"] = str(out)
            save_project()
            st.success("AI Thumbnail tayyar ✅")
        except Exception as e:  # noqa: BLE001
            st.error(f"Gemini fail: {e}")

    t1, t2 = st.columns(2)
    with t1:
        if st.session_state["thumb_path"]:
            st.caption("Simple thumbnail")
            st.image(st.session_state["thumb_path"], use_container_width=True)
            with open(st.session_state["thumb_path"], "rb") as f:
                st.download_button("⬇️ Simple download karo", f,
                                   file_name="thumbnail.jpg",
                                   mime="image/jpeg")
    with t2:
        if st.session_state.get("thumb_ai_path"):
            st.caption("✨ Gemini AI thumbnail")
            st.image(st.session_state["thumb_ai_path"],
                     use_container_width=True)
            with open(st.session_state["thumb_ai_path"], "rb") as f:
                st.download_button("⬇️ AI thumbnail download karo", f,
                                   file_name="thumbnail_ai.jpg",
                                   mime="image/jpeg", key="dl_thumb_ai")


def panel_metadata():
    st.header("🏷 Upload Metadata")
    if not (st.session_state["long_video"] and st.session_state["images"]):
        st.info("Pehle 🎞 Edit & Video panel me final video banao.")
        return
    connected = st.session_state.get("gemini_keys_ok") or []

    if st.button("✨ Gemini se Titles banao", disabled=not connected,
                 help="Sidebar me 🔑 Gemini keys Connect karo"):
        try:
            with st.spinner("Gemini titles soch raha hai..."):
                titles = gemini_helper.generate_titles(
                    connected, st.session_state["lines"])
            st.session_state["gemini_titles"] = titles
            save_project()
        except Exception as e:  # noqa: BLE001
            st.error(f"Gemini fail: {e}")

    if st.session_state.get("gemini_titles"):
        pick = st.radio("Gemini ke titles — jo pasand aaye use chuno:",
                        st.session_state["gemini_titles"])
        if st.button("✅ Is title ko lagao"):
            if st.session_state.get("meta"):
                st.session_state["meta"]["title"] = pick
            else:
                st.session_state["meta"] = {"title": pick,
                                            "description": "", "tags": []}
            save_project()
            st.success("Title laga diya ✅")

    if st.button("📝 Title / Description / Tags banao"):
        meta = metadata_gen.make_metadata(
            st.session_state["lines"], st.session_state["thumb_words"])
        st.session_state["meta"] = meta
        save_project()
    if st.session_state["meta"]:
        meta = st.session_state["meta"]
        st.text_input("Title (copy karo)", meta["title"])
        st.text_area("Description (copy karo)", meta["description"],
                     height=180)
        st.text_area("Tags (copy karo)", ", ".join(meta["tags"]), height=80)
        st.download_button("⬇️ Metadata .txt download karo",
                           metadata_gen.metadata_text(meta),
                           file_name="upload_metadata.txt",
                           mime="text/plain")


def panel_dubs():
    st.header("🌍 Doosri Languages me Dub (optional)")
    if not (st.session_state["long_video"] and st.session_state["images"]):
        st.info("Pehle 🎞 Edit & Video panel me final video banao.")
        return
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
                progress_cb=lambda p: bar.progress(
                    p * 0.3, text="Translate ho raha hai..."),
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
                                 music_path, workdir,
                                 f"project_dub_{lang_key}")
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
            save_project()
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


_PANELS = {
    "📝 Script": panel_script,
    "🎙 Voice": panel_voice,
    "🖼 Images": panel_images,
    "🎞 Edit & Video": panel_edit,
    "🖼️ Thumbnail": panel_thumbnail,
    "🏷 Metadata": panel_metadata,
    "🌍 Dubs": panel_dubs,
}
_PANELS[st.session_state.get("nav_step", STEPS[0])]()

st.caption("💡 Tip: Horror Voice Studio wali voice yahin banti hai — alag app kholne ki zaroorat nahi.")
