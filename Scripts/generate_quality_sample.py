"""Generate the validated quality sample with Blender 3.6 LTS."""
from blender_asset_pack_common import *
import json
import bpy
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))


def main():
    args = cli_args()
    ensure_runtime()
    status_path = DIRS['Documentation']/'quality_sample_status.json'
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
