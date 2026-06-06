#!/usr/bin/env bash
# export_video.sh — render an HTML animation to MP4 (or GIF).
#
# Usage:
#   export_video.sh <input.html> <output.mp4|output.gif> [seconds] [fps]
#
# Pipeline: a headless browser captures frames from the animation HTML, then
# ffmpeg assembles them. BGM/SFX mixing is layered on top when media assets are
# present (see assets/media/README.md). Degrades gracefully: if a dependency is
# missing it explains exactly what to install instead of failing opaquely.
set -euo pipefail

IN="${1:-}"
OUT="${2:-}"
SECONDS_LEN="${3:-8}"
FPS="${4:-30}"
GIF_WIDTH="${5:-960}"   # GIFs are downscaled + frame-reduced for small, shareable files
GIF_FPS="${6:-15}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [[ -z "$IN" || -z "$OUT" ]]; then
  echo "usage: export_video.sh <input.html> <output.mp4|.gif> [seconds] [fps] [gif_width] [gif_fps]" >&2
  exit 2
fi

# --- dependency checks (graceful degradation) -------------------------------
missing=()
command -v ffmpeg >/dev/null 2>&1 || missing+=("ffmpeg (brew install ffmpeg / apt install ffmpeg)")
command -v node   >/dev/null 2>&1 || missing+=("node (https://nodejs.org)")
if ! node -e "require('playwright')" >/dev/null 2>&1 \
   && ! node -e "require('puppeteer')" >/dev/null 2>&1; then
  missing+=("playwright or puppeteer (npm i -D playwright && npx playwright install chromium)")
fi
if (( ${#missing[@]} )); then
  echo "⚠ export_video: cannot render — missing dependencies:" >&2
  for m in "${missing[@]}"; do echo "   - $m" >&2; done
  echo "   The animation HTML is still valid; open it in a browser, or install the above to export." >&2
  exit 3
fi

# --- capture frames ---------------------------------------------------------
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
FRAMES=$(( SECONDS_LEN * FPS ))
echo "Capturing ${FRAMES} frames @ ${FPS}fps from $IN ..." >&2

node - "$IN" "$TMP" "$FRAMES" "$FPS" <<'NODE'
const path = require('path');
const [, , input, outDir, frames, fps] = process.argv;
(async () => {
  let browser;
  try { browser = await require('playwright').chromium.launch(); }
  catch { browser = await require('puppeteer').launch(); }
  const page = await (browser.newPage ? browser.newPage() : browser.pages().then(p => p[0]));
  await page.setViewportSize ? page.setViewportSize({ width: 1280, height: 720 })
                             : await page.setViewport({ width: 1280, height: 720 });
  const url = /^https?:\/\//.test(input) ? input : 'file://' + path.resolve(input);
  await page.goto(url, { waitUntil: 'networkidle' });
  // Wait for web fonts so frames aren't a fallback-font "raw HTML" render.
  await page.evaluate(() => (document.fonts ? document.fonts.ready : null)).catch(() => {});
  const interval = 1000 / Number(fps);
  for (let i = 0; i < Number(frames); i++) {
    const f = String(i).padStart(5, '0');
    await page.screenshot({ path: path.join(outDir, `frame-${f}.png`) });
    await new Promise(r => setTimeout(r, interval));
  }
  await browser.close();
})().catch(e => { console.error(e); process.exit(1); });
NODE

# --- assemble ---------------------------------------------------------------
if [[ "$OUT" == *.gif ]]; then
  # High-quality GIF: downsample fps, scale (lanczos), per-frame palette (stats_mode
  # =diff) + Bayer dithering, in one filtergraph.
  ffmpeg -y -loglevel error -framerate "$FPS" -i "$TMP/frame-%05d.png" -vf \
    "fps=${GIF_FPS},scale=${GIF_WIDTH}:-1:flags=lanczos,split[s0][s1];[s0]palettegen=stats_mode=diff[p];[s1][p]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
    -loop 0 "$OUT"
else
  ffmpeg -y -loglevel error -framerate "$FPS" -i "$TMP/frame-%05d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart "$OUT"
fi

echo "✓ wrote $OUT" >&2
# BGM/SFX: if assets/media/bgm-*.mp3 exist, mix with:
#   ffmpeg -i "$OUT" -i assets/media/bgm-tech.mp3 -shortest -c:v copy out-with-audio.mp4
