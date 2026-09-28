"""Export the quality sample with explicit per-asset action lists."""
from blender_asset_pack_common import DIRS, asset_descendants, evaluated_dimensions, validate
import json
import bpy
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


ASSETS = [
    ('Char_Officer', 'Officer_Quality.fbx', 'Characters',
     (('Rig_Officer', ('Anim_RifleReadyIdle', 'Anim_Walk_Forward',
                       'Anim_CrouchIdle', 'Anim_RifleRecoil')),)),
    ('Equip_Carbine', 'Carbine_Quality.fbx', 'Equipment', ()),
    ('Env_QualityRoom', 'QualityRoom.fbx', 'Environment',
     (('DoorPivot_L', ('Anim_Door_L',)),
      ('DoorPivot_R', ('Anim_Door_R',)))),
]


def set_nla_actions(owner, action_names):
    owner.animation_data_create()
    animation = owner.animation_data
    animation.action = None
    for track in list(animation.nla_tracks):
        animation.nla_tracks.remove(track)
    for name in action_names:
        clip = bpy.data.actions.get(name)
        if not clip:
            raise RuntimeError(f'Missing declared export action: {name}')
        track = animation.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, int(clip['frame_start']), clip)
        strip.blend_type = 'REPLACE'
        strip.extrapolation = 'NOTHING'


def round_trip_check(filepath, asset_name, expected_actions, source_dimensions):
    if not hasattr(bpy.ops.import_scene, 'fbx'):
        try:
            bpy.ops.preferences.addon_enable(module='io_scene_fbx')
        except (AttributeError, RuntimeError):
            pass
    if not hasattr(bpy.ops.import_scene, 'fbx'):
        return {'status': 'not_run', 'reason': 'FBX importer operator unavailable'}
    window = bpy.context.window
    source_scene = bpy.context.scene
    test_scene = bpy.data.scenes.new('ROUNDTRIP_'+asset_name)
    imported = []
    try:
        if window:
            window.scene = test_scene
            bpy.ops.import_scene.fbx(filepath=str(filepath))
        else:
            with bpy.context.temp_override(scene=test_scene):
                bpy.ops.import_scene.fbx(filepath=str(filepath))
        imported = list(test_scene.objects)
        meshes = [obj for obj in imported if obj.type == 'MESH']
        armatures = [obj for obj in imported if obj.type == 'ARMATURE']
        dimensions = evaluated_dimensions(imported)
        observed_actions = []
        for obj in imported:
            animation = obj.animation_data
            if not animation:
                continue
            if animation.action:
                observed_actions.append(animation.action.name)
            observed_actions.extend(strip.name for track in animation.nla_tracks
                                    for strip in track.strips)
        action_ok = all(any(name in observed for observed in observed_actions)
                        for name in expected_actions)
        dimensions_ok = all(abs(dimensions[i]-source_dimensions[i]) <= .08
                            for i in range(3))
        hierarchy_ok = bool(meshes) and (
            asset_name != 'Char_Officer' or bool(armatures))
        passed = dimensions_ok and hierarchy_ok and action_ok
        return {
            'status': 'passed' if passed else 'failed',
            'dimensions_m': dimensions,
            'source_dimensions_m': source_dimensions,
            'mesh_count': len(meshes),
            'armature_count': len(armatures),
            'expected_actions': list(expected_actions),
            'observed_actions': observed_actions,
            'checks': {'dimensions': dimensions_ok, 'hierarchy': hierarchy_ok,
                       'actions': action_ok},
        }
    except Exception as error:
        return {'status': 'failed', 'reason': str(error)}
    finally:
        if window:
            window.scene = source_scene
        for obj in list(test_scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(test_scene)


def ensure_fbx_exporter():
    if not hasattr(bpy.ops.export_scene, 'fbx'):
        try:
            bpy.ops.preferences.addon_enable(module='io_scene_fbx')
        except (AttributeError, RuntimeError):
            pass
    if not hasattr(bpy.ops.export_scene, 'fbx'):
        raise RuntimeError(
            'Blender FBX exporter is unavailable; enable or install the Blender FBX I/O extension.')


def export_asset(root_name, filename, folder, animation_tracks):
    root = bpy.data.objects.get(root_name)
    if not root:
        raise RuntimeError(f'Missing asset root: {root_name}')
    objects = [root] + asset_descendants(root)
    objects = [obj for obj in objects if obj.type in {'MESH', 'ARMATURE', 'EMPTY'}
               and not obj.get('exclude_from_asset_export')
               and not obj.name.startswith(('SHOWCASE_', 'REF_'))]
    if not objects:
        raise RuntimeError(f'Empty export hierarchy: {root_name}')
    expected_actions = []
    for animated_owner, action_names in animation_tracks:
        owner = bpy.data.objects.get(animated_owner)
        if not owner:
            raise RuntimeError(f'Missing animation owner: {animated_owner}')
        set_nla_actions(owner, action_names)
        expected_actions.extend(action_names)
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next(
        (obj for obj in objects if obj.type == 'ARMATURE'), root)
    dimensions = evaluated_dimensions(objects)
    output = DIRS[folder]/filename
    output.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(output), use_selection=True,
        object_types={'EMPTY', 'MESH', 'ARMATURE'},
        use_mesh_modifiers=True, add_leaf_bones=False,
        apply_unit_scale=True, axis_forward='-Z', axis_up='Y',
        bake_anim=bool(expected_actions),
        bake_anim_use_nla_strips=bool(expected_actions),
        bake_anim_use_all_actions=False, bake_anim_simplify_factor=0.0,
        use_custom_props=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f'Empty export: {output}')
    round_trip = round_trip_check(
        output, root_name, expected_actions, dimensions)
    return {
        'file': str(output),
        'asset_root': root_name,
        'dimensions_m': dimensions,
        'exported_actions': expected_actions,
        'round_trip': round_trip,
    }


def export_all(validate_exports=False):
    ensure_fbx_exporter()
    if validate_exports:
        validate(DIRS['Documentation']/'export_validation.json')
    results = [export_asset(*asset) for asset in ASSETS]
    round_trip_states = [result['round_trip']['status'] for result in results]
    if 'failed' in round_trip_states:
        raise RuntimeError('One or more FBX round-trip checks failed')
    report = {
        'export_status': 'passed',
        'exports': results,
        'round_trip_status': 'not_run' if 'not_run' in round_trip_states else 'passed',
        'unity_compatibility': 'not_run',
    }
    report_path = DIRS['Documentation']/'export_validation.json'
    report_path.write_text(json.dumps(report, indent=2), encoding='utf8')
    status_path = DIRS['Documentation']/'quality_sample_status.json'
    status = json.loads(status_path.read_text(
        encoding='utf8')) if status_path.exists() else {}
    status['export_status'] = 'passed'
    status['round_trip_status'] = report['round_trip_status']
    status_path.write_text(json.dumps(status, indent=2), encoding='utf8')
    print('EXPORTED', *(result['file'] for result in results), sep='\n')
    return [result['file'] for result in results]


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    export_all(validate_exports='--validate' in argv)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
