#!/usr/bin/env bash
set -euo pipefail
BLENDER_BIN="${BLENDER_BIN:-blender}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
"$BLENDER_BIN" --version | head -n 1
"$BLENDER_BIN" -b --python Scripts/generate_quality_sample.py -- --validate
"$BLENDER_BIN" -b Sources/quality_sample.blend --python Scripts/export_to_unity.py -- --validate
printf '\nQuality sample generated, rendered, validated, and exported.\n'
