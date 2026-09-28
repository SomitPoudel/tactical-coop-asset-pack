"""Export the quality sample with explicit per-asset action lists."""
import importlib
import bpy
import json
import traceback
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
_common = importlib.import_module('blender_asset_pack_common')
DIRS = _common.DIRS
asset_descendants = _common.asset_descendants
evaluated_dimensions = _common.evaluated_dimensions
validate = _common.validate


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
    report_path = DIRS['Documentation']/'export_validation.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        'export_status': 'failed',
        'preflight_validation': 'not_requested',
        'exports': [],
        'failures': [],
        'round_trip_status': 'not_run',
        'unity_compatibility': 'not_run',
    }

    def save_report():
        report_path.write_text(json.dumps(report, indent=2), encoding='utf8')
        status_path = DIRS['Documentation']/'quality_sample_status.json'
        if status_path.is_file():
            try:
                status = json.loads(status_path.read_text(encoding='utf8'))
            except (OSError, json.JSONDecodeError):
                status = {}
            status['export_status'] = report['export_status']
            status['round_trip_status'] = report['round_trip_status']
            status_path.write_text(json.dumps(
                status, indent=2), encoding='utf8')

    try:
        ensure_fbx_exporter()
    except Exception as error:
        report['failures'].append({
            'stage': 'fbx_preflight', 'error': str(error),
        })
        save_report()
        raise RuntimeError(
            f'FBX export preflight failed; see {report_path}') from error

    if validate_exports:
        try:
            validate(DIRS['Documentation']/'export_validation.json')
            report['preflight_validation'] = 'passed'
        except Exception as error:
            report['preflight_validation'] = {
                'status': 'failed', 'error': str(error),
            }
            report['failures'].append({
                'stage': 'sample_validation', 'error': str(error),
            })
            save_report()
            raise RuntimeError(
                f'Export validation failed; see {report_path}') from error

    for asset in ASSETS:
        root_name, filename, folder = asset[:3]
        try:
            result = export_asset(*asset)
        except Exception as error:
            failure = {
                'asset_root': root_name,
                'file': str(DIRS[folder]/filename),
                'status': 'failed',
                'error': str(error),
            }
            report['exports'].append(failure)
            report['failures'].append(failure.copy())
        else:
            report['exports'].append(result)
            if result['round_trip']['status'] == 'failed':
                report['failures'].append({
                    'asset_root': root_name,
                    'stage': 'round_trip',
                    'error': result['round_trip'].get('reason',
                                                      result['round_trip'].get('checks')),
                })

    round_trip_states = [
        result['round_trip']['status'] for result in report['exports']
        if 'round_trip' in result
    ]
    if 'failed' in round_trip_states:
        report['round_trip_status'] = 'failed'
    elif 'not_run' in round_trip_states or len(round_trip_states) != len(ASSETS):
        report['round_trip_status'] = 'not_run'
    else:
        report['round_trip_status'] = 'passed'
    report['export_status'] = 'failed' if report['failures'] else 'passed'
    save_report()
    if report['failures']:
        raise RuntimeError(
            f'FBX export or round-trip checks failed; see {report_path}')

    exported = [result['file'] for result in report['exports']]
    print('EXPORTED', *exported, sep='\n')
    return exported


def main():
    argv = sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    export_all(validate_exports='--validate' in argv)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
