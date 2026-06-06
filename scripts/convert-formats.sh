#!/usr/bin/env bash
# Convert an MP4 animation to a 60fps MP4 + an optimized GIF (derivatives).
#
# Usage:
#   convert-formats.sh input.mp4 [gif_width] [--minterpolate]
#
# Produces next to the input:
#   <name>-60fps.mp4   (60fps; frame-duplicated by default — broad compatibility)
#   <name>.gif         (gif_width wide, 15fps, palette-optimized)
#
#   --minterpolate   motion-compensated interpolation (true 60fps, higher quality,
#                    but the H.264 elementary stream has a known QuickTime/Safari
#                    compat bug — test your target player before delivering).
set -e

command -v ffmpeg >/dev/null 2>&1 || {
  echo "⚠ convert-formats: ffmpeg not found — install it (brew install ffmpeg / apt install ffmpeg)." >&2
  exit 3
}

INPUT=""
GIF_WIDTH="960"
USE_MINTERPOLATE=0
for arg in "$@"; do
  case "$arg" in
    --minterpolate) USE_MINTERPOLATE=1 ;;
    --*) echo "Unknown flag: $arg" >&2; exit 1 ;;
    *) if [ -z "$INPUT" ]; then INPUT="$arg"; else GIF_WIDTH="$arg"; fi ;;
  esac
done
[ -z "$INPUT" ] && { echo "Usage: $0 input.mp4 [gif_width] [--minterpolate]" >&2; exit 1; }

DIR=$(dirname "$INPUT"); BASE=$(basename "$INPUT" .mp4)
OUT60="$DIR/$BASE-60fps.mp4"; OUTGIF="$DIR/$BASE.gif"; PAL="$DIR/.palette-$BASE.png"

if [ "$USE_MINTERPOLATE" = "1" ]; then
  echo "▸ 60fps interpolate (minterpolate): $OUT60" >&2
  VFILTER="minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
else
  echo "▸ 60fps frame-duplicate (compat): $OUT60" >&2
  VFILTER="fps=60"
fi
ffmpeg -y -loglevel error -i "$INPUT" -vf "$VFILTER" \
  -c:v libx264 -pix_fmt yuv420p -profile:v high -level 4.0 \
  -crf 18 -preset medium -movflags +faststart "$OUT60"
echo "  ✓ $(du -h "$OUT60" | cut -f1)" >&2

echo "▸ GIF (${GIF_WIDTH}w, 15fps, palette-optimized): $OUTGIF" >&2
ffmpeg -y -loglevel error -i "$INPUT" \
  -vf "fps=15,scale=${GIF_WIDTH}:-1:flags=lanczos,palettegen=stats_mode=diff" "$PAL"
ffmpeg -y -loglevel error -i "$INPUT" -i "$PAL" \
  -lavfi "fps=15,scale=${GIF_WIDTH}:-1:flags=lanczos[x];[x][1:v]paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  "$OUTGIF"
rm -f "$PAL"
echo "  ✓ $(du -h "$OUTGIF" | cut -f1)" >&2
