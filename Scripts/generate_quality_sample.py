"""Generate the validated quality sample with Blender 3.6 LTS."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import bpy
from blender_asset_pack_common import *


def main():
    args=cli_args(); ensure_runtime(); setup_scene()
    char_col=collection('Char_Officer'); arm=create_humanoid_rig('Rig_Officer',char_col); build_officer(arm,'blue','Char_Officer')
    build_carbine(); build_room(); build_animations(arm)
    bpy.ops.wm.save_as_mainfile(filepath=str(DIRS['Sources']/'quality_sample.blend'))
    report=validate(DIRS['Documentation']/'quality_validation.json') if args.validate else None
    if not args.no_render:
        bpy.context.scene.render.filepath=str(DIRS['Previews']/'quality_sample.png'); bpy.ops.render.render(write_still=True)
    print('QUALITY_SAMPLE_OK', report['passed'] if report else 'generated')

if __name__=='__main__': main()
