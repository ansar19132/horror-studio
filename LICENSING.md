# Licensing Notes — Horror Studio (2026-09-22)

Researched 2026-09-22. Do not present the app output as "100% commercially safe".

## Pollinations (AI images)
- Pollinations ToS: user retains ownership; commercial use allowed "subject to legality
  and ethical standards" — BUT they explicitly say to review the licenses of the
  underlying open-source models before commercial use.
- Verdict: generally usable, but commercial safety depends on WHICH model generated
  the image (e.g. FLUX.1-dev is non-commercial, FLUX.1-schnell is Apache 2.0).
  The app's default model choice matters — document it per project.
- Free tier has usage limits; Pollinations now sells paid tiers. Never promise it
  stays free.

## Pexels (stock fallback)
- Pexels license: free for personal and commercial use, no attribution required.
- Restrictions: identifiable people, defamation/offensive contexts, implying
  endorsement, trademarks, resale of unaltered assets.
- Verdict: safe fallback within those restrictions.

## Edge TTS (voiceover engine)
- The endpoint used is UNOFFICIAL (Edge "Read Aloud" service, not a public API).
  Microsoft publishes no terms permitting third-party/commercial use.
- Community consensus: personal use tolerated (rate-limiting, not enforcement so
  far); commercial use likely conflicts with Microsoft's terms.
- Verdict: DO NOT call Edge TTS output commercially cleared.
- Licensed fallback: Azure AI Speech (same neural voices, paid, official license).

## Bundled music (music/dark_ambient.mp3)
- Procedurally generated inside the project (make_drone.py), no third-party samples.
- Verdict: safest component; no external rights involved.

## Captions / editing / thumbnail / metadata
- All generated in-app with bundled fonts (DejaVu Sans, free license). No issues.
