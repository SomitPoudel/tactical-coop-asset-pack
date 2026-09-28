"""Expanded procedural pack entry point. The quality sample is authoritative."""
from blender_asset_pack_common import *
import bpy
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def prop_set():
    c = collection('Env_Props')
    wood = mat('MAT_Wood', (.35, .18, .07, 1), 0, .8)
    metal = mat('MAT_PropMetal', (.25, .28, .30, 1), .5, .45)
    red = mat('MAT_Red', (.65, .04, .03, 1), 0, .6)
    add_cube('Prop_Crate', (4, 1, .35), (.7, .7, .7), wood, .05, c)
    add_cube('Prop_Pallet', (4, -1, .08), (1.2, 1, .16), wood, .02, c)
    for x in (-2.3, -1.7):
        add_cube('Prop_Shelf_Upright', (x, 1, .9),
                 (.08, .45, 1.8), metal, .02, c)
    for z in (.25, .85, 1.45):
        add_cube('Prop_Shelf_Shelf', (-2, 1, z),
                 (1.2, .45, .06), metal, .01, c)
    add_cylinder('Prop_Barrel', (-2, -1, .45), .3, .9, metal, c)
    add_cube('Prop_Desk', (2, -1, .75), (1.4, .7, .1), wood, .03, c)
    for x in (1.45, 2.55):
        add_cube('Prop_Desk_Leg', (x, -1, .35), (.08, .08, .7), wood, .01, c)
    add_cube('Prop_Locker', (-4, 0, .9), (.6, .6, 1.8), metal, .03, c)
    add_cube('Prop_FireExtinguisher', (-1, 2, .5), (.16, .16, .7), red, .05, c)


def main():
    args = cli_args()
    ensure_runtime()
    setup_scene()
    char_col = collection('Char_Officer')
    arm = create_humanoid_rig('Rig_Officer', char_col)
    build_carbine()
    build_officer(arm, 'blue', 'Char_Officer')
    build_room()
    build_animations(arm)
    prop_set()
    bpy.ops.wm.save_as_mainfile(filepath=str(
        DIRS['Sources']/'full_pack_procedural.blend'))
    validate(DIRS['Documentation']/'full_pack_validation.json')
    if args.export:
        from export_to_unity import export_all
        export_all(validate_exports=True)
    print('FULL_PACK_OK')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
