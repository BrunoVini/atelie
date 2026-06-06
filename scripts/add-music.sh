#!/usr/bin/env bash
# Mix a BGM track into an MP4 (trim to length, 0.3s fade-in, 1s fade-out).
#
# Usage:
#   add-music.sh <input.mp4> [--mood=<name>] [--music=<path>] [--out=<path>]
#
# Mood presets live in assets/media/ as bgm-<mood>.mp3 (download-on-demand — see
# assets/media/README.md). --music=<path> brings your own and wins over --mood.
# Default delivery for a narrated piece is an MP4 WITH audio — a silent one feels cheap.
set -e

command -v ffmpeg  >/dev/null 2>&1 || { echo "⚠ add-music: ffmpeg not found (brew/apt install ffmpeg)." >&2; exit 3; }
command -v ffprobe >/dev/null 2>&1 || { echo "⚠ add-music: ffprobe not found (comes with ffmpeg)." >&2; exit 3; }

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ASSETS_DIR="$SCRIPT_DIR/../assets/media"

INPUT=""; MOOD="tech"; CUSTOM_MUSIC=""; OUTPUT=""; POSITIONAL=()
for arg in "$@"; do
  case "$arg" in
    --mood=*)  MOOD="${arg#*=}" ;;
    --music=*) CUSTOM_MUSIC="${arg#*=}" ;;
    --out=*)   OUTPUT="${arg#*=}" ;;
    *)         POSITIONAL+=("$arg") ;;
  esac
done
INPUT="${POSITIONAL[0]}"
[ -z "$CUSTOM_MUSIC" ] && [ -n "${POSITIONAL[1]:-}" ] && CUSTOM_MUSIC="${POSITIONAL[1]}"
[ -z "$OUTPUT" ]       && [ -n "${POSITIONAL[2]:-}" ] && OUTPUT="${POSITIONAL[2]}"

if [ -z "$INPUT" ] || [ ! -f "$INPUT" ]; then
  echo "Usage: add-music.sh <input.mp4> [--mood=<name>] [--music=<path>] [--out=<path>]" >&2
  exit 1
fi

if [ -n "$CUSTOM_MUSIC" ]; then MUSIC="$CUSTOM_MUSIC"; SOURCE_LABEL="custom: $MUSIC"
else MUSIC="$ASSETS_DIR/bgm-${MOOD}.mp3"; SOURCE_LABEL="mood: $MOOD"; fi

if [ ! -f "$MUSIC" ]; then
  echo "✗ Music not found: $MUSIC" >&2
  echo "  BGM tracks are download-on-demand — see assets/media/README.md, or pass --music=<path>." >&2
  exit 3
fi

INPUT_DIR="$(cd "$(dirname "$INPUT")" && pwd)"; INPUT_NAME="$(basename "$INPUT" .mp4)"
[ -z "$OUTPUT" ] && OUTPUT="$INPUT_DIR/$INPUT_NAME-bgm.mp4"

DURATION=$(ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "$INPUT")
[ -z "$DURATION" ] && { echo "✗ Could not read video duration" >&2; exit 1; }
FADE_OUT_START=$(awk "BEGIN { d = $DURATION - 1; if (d < 0) d = 0; print d }")

echo "▸ Mixing BGM ($SOURCE_LABEL) into $INPUT → $OUTPUT" >&2
ffmpeg -y -loglevel error -i "$INPUT" -i "$MUSIC" \
  -filter_complex "[1:a]atrim=0:${DURATION},asetpts=PTS-STARTPTS,afade=t=in:st=0:d=0.3,afade=t=out:st=${FADE_OUT_START}:d=1[a]" \
  -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -shortest "$OUTPUT"
echo "✓ Done: $OUTPUT ($(du -h "$OUTPUT" | cut -f1))" >&2
