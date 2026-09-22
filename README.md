# 🎃 Horror Studio

All-in-one faceless horror story video tool — script se final YouTube video tak, ek hi app me.

## Kya karta hai

1. **Script likho** (ek sentence per line) → built-in voiceover engine (Edge TTS, 5 horror voices, auto emotion + whisper)
2. **AI images** — har sentence ke liye ek horror image (Pollinations, key-free), preview + regenerate + upload + Pexels stock fallback
3. **Auto edit** — voice timing se clip durations, Ken Burns motion, crossfades, dip-to-black, scare flash-cuts, red flash, film grain, vignette, letterbox, horror color grade
4. **Captions** — word-by-word horror karaoke (white + blood-red active word)
5. **Music** — bundled copyright-free dark ambient bed, auto-ducked under narration
6. **Thumbnail** — auto-generated 1280×720 YouTube thumbnail
7. **Metadata** — auto title / description / tags (easy-copy file)
8. **Dub** — Urdu + Spanish dubbed videos, per-language locked signature voices
9. **Shorts** — vertical 9:16 Shorts auto-rendered

## Chalana (local)

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

System me `ffmpeg` chahiye.

## Deploy (Streamlit Community Cloud)

`packages.txt` me ffmpeg already listed hai — repo connect karo aur deploy karo. Pehla render cloud resources par test karna zaroori hai.

## Notes

- Voiceover: Edge TTS (no API key). Internet chahiye.
- Images: Pollinations (no key). Heavy load par slow ho sakta hai.
- Stock fallback: Pexels (user ki apni free API key).
- Bundled music `music/dark_ambient.mp3` procedurally generated hai project ke andar, bina kisi third-party sample ke.
