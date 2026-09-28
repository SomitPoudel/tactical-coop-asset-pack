"""Render identical officer review views from a saved Blender source file."""
import argparse
import importlib
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
common = importlib.import_module('blender_asset_pack_common')
VIEWS = ('officer_front', 'officer_side', 'officer_three_quarter',
         'officer_boots_knees', 'officer_side_by_side',
         'officer_gameplay_distance')


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    source = (ROOT/args.source).resolve()
    output = (ROOT/args.output).resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    bpy.ops.wm.open_mainfile(filepath=str(source))
    arm = bpy.data.objects.get('Rig_Officer')
    if not arm:
        raise RuntimeError('Review source has no Rig_Officer armature.')
    previews = common.render_quality_previews(arm, output, VIEWS)
    print('OFFICER_REVIEW_PREVIEWS_OK', *previews, sep='\n')


if __name__ == '__main__':
    main()
