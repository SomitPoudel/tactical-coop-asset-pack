"""Generate the validated quality sample with Blender 3.6 LTS."""
import importlib
import json
import sys
import traceback
from pathlib import Path

import bpy

sys.path.insert(0, str(Path(__file__).resolve().parent))
_common = importlib.import_module('blender_asset_pack_common')
DIRS = _common.DIRS
cli_args = _common.cli_args
ensure_runtime = _common.ensure_runtime
setup_scene = _common.setup_scene
collection = _common.collection
create_humanoid_rig = _common.create_humanoid_rig
build_carbine = _common.build_carbine
build_officer = _common.build_officer
build_room = _common.build_room
build_animations = _common.build_animations
validate = _common.validate
render_quality_previews = _common.render_quality_previews


def main():
    args = cli_args()
    ensure_runtime()
    status_path = DIRS['Documentation']/'quality_sample_status.json'
    if args.preview_only:
        arm = bpy.data.objects.get('Rig_Officer')
        if not arm:
            raise RuntimeError(
                'Preview-only mode requires Sources/quality_sample.blend to be opened first.')
        if not status_path.is_file():
            raise RuntimeError(
                'Preview-only mode requires a successful generation status report.')
        views = args.preview_views or ['officer_front', 'gameplay_angle']
        previews = render_quality_previews(arm, DIRS['Previews'], views)
        status = json.loads(status_path.read_text(encoding='utf8'))
        status['preview_status'] = 'passed'
        status['previews'] = previews
        status_path.write_text(json.dumps(status, indent=2), encoding='utf8')
        print('QUALITY_SAMPLE_PREVIEWS_OK', *previews, sep='\n')
        return
    status_path.unlink(missing_ok=True)
    setup_scene()
    char_col = collection('Char_Officer')
    arm = create_humanoid_rig('Rig_Officer', char_col)
    build_carbine()
    build_officer(arm, 'blue', 'Char_Officer')
    build_room()
    build_animations(arm)
    report = validate(DIRS['Documentation'] /
                      'quality_validation.json') if args.validate else None
    previews = [] if args.no_render else render_quality_previews(
        arm, DIRS['Previews'])
    bpy.ops.wm.save_as_mainfile(
        filepath=str(DIRS['Sources']/'quality_sample.blend'))
    exports = []
    if args.export:
        from export_to_unity import export_all
        exports = export_all(validate_exports=args.validate)
    status = {
        'generation_status': 'passed',
        'structural_validation': report['structural_validation']['status'] if report else 'not_run',
        'visual_quality_metrics': report['visual_quality_validation']['status'] if report else 'not_run',
        'human_visual_review': 'pending rendered inspection',
        'previews': previews,
        'exports': exports,
        'unity_compatibility': 'not_run',
    }
    if args.export:
        export_report = json.loads(
            (DIRS['Documentation']/'export_validation.json').read_text(encoding='utf8'))
        status['export_status'] = export_report['export_status']
        status['round_trip_status'] = export_report['round_trip_status']
    status_path.write_text(json.dumps(status, indent=2), encoding='utf8')
    print('QUALITY_SAMPLE_OK', report['passed'] if report else 'generated')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        raise SystemExit(1)
