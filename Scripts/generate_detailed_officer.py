"""Generate the independent detailed officer source, previews, LODs and FBX files."""
import argparse
import importlib
import sys
import traceback
from pathlib import Path

import bpy

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
common = importlib.import_module("blender_asset_pack_common")
builder = importlib.import_module("detailed_officer")


def main():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-render", action="store_true")
    parser.add_argument("--no-export", action="store_true")
    args = parser.parse_args(argv)
    common.ensure_runtime()
    common.setup_scene()
    report = builder.generate(render=not args.no_render,
                              export=not args.no_export)
    print("DETAILED_OFFICER_OK", report["height_m"],
          report["evaluated_triangles"], sep="\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
