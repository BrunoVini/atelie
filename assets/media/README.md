# Media assets (BGM / SFX) — download on demand

To keep atelier lightweight, background-music tracks and a sound-effects library
are **not vendored** (they total tens of MB). The animation / video capability
degrades gracefully without them (silent export + a warning).

When a narrated animation or video export needs audio, fetch tracks from any
royalty-free music library into this directory:

- BGM: `bgm-tech.mp3`, `bgm-educational.mp3`, `bgm-tutorial.mp3`, `bgm-ad.mp3`, …
- SFX: organized by category under `sfx/`

`scripts/export_video.sh` looks here for `bgm-*.mp3` and `sfx/` and warns if they
are absent rather than failing.
