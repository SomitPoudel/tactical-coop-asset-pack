#!/usr/bin/env bash
set -euo pipefail
BLENDER_BIN="${BLENDER_BIN:-blender}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if ! command -v "$BLENDER_BIN" >/dev/null 2>&1; then
	printf 'Blender executable not found: %s\n' "$BLENDER_BIN" >&2
	exit 127
fi
"$BLENDER_BIN" --version | head -n 1
mkdir -p Documentation Previews
rm -f Documentation/quality_sample_status.json Documentation/export_validation.json
"$BLENDER_BIN" --background --python-exit-code 1 \
	--python Scripts/generate_quality_sample.py -- --validate
test -s Documentation/quality_sample_status.json
"$BLENDER_BIN" --background Sources/quality_sample.blend \
	--python-exit-code 1 --python Scripts/export_to_unity.py -- --validate
test -s Documentation/export_validation.json
grep -q '"export_status": "passed"' Documentation/export_validation.json
printf '\nQuality sample generation, renders, validation, FBX export, and round-trip step finished. See Documentation/export_validation.json for exact check statuses.\n'
