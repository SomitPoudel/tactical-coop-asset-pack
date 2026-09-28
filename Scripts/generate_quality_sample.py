# Quality-sample generation script for the tactical asset pack

import bpy
import math

from pathlib import Path
from blender_asset_pack_common import (
    ROOT,
    ensure_directories,
    setup_scene,
    create_humanoid_rig,
    build_simple_officer,
    build_carbine,
    create_sample_room,
    write_sample_manifest,
    write_manifest,
)


if __name__ == '__main__':
    ensure_directories()
    setup_scene()
    arm = create_humanoid_rig()
    build_simple_officer(arm, variant='default')
    build_carbine(name='Equip_Carbine_Quality')
    door_pivot = create_sample_room()

    # add simple door animation for a sample open state
    door_pivot.rotation_euler = (0, 0, 0)
    door_pivot.keyframe_insert(data_path='rotation_euler', frame=1)
    door_pivot.rotation_euler = (0, math.radians(-55), 0)
    door_pivot.keyframe_insert(data_path='rotation_euler', frame=24)

    # save a Blender source file in Sources/ for the local environment
    blend_path = ROOT / 'Sources' / 'quality_sample.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    manifest = {
        'name': 'QualitySample_Officer_Rifle_Room',
        'status': 'Quality sample prepared; not validated in this environment',
        'characters': ['Officer'],
        'supporting_assets': ['Carbine', 'room', 'hinge door', 'reference cube'],
        'camera': 'angled top-down',
        'export_targets': ['.blend', '.fbx', '.glb'],
        'notes': 'Door pivot is at the hinge side and the sample remains to be exported and inspected locally.'
    }
    write_manifest(ROOT / 'Documentation' / 'quality_sample_manifest.json', manifest)
    print('Quality sample generated procedurally. Export locally with Blender to create final source and FBX files.')
