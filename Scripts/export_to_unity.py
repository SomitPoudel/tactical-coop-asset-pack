# Blender export and validation workflow for local environments

import bpy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES_DIR = ROOT / 'Sources'
ANIMATIONS_DIR = ROOT / 'Animations'
CHARACTERS_DIR = ROOT / 'Characters'
EQUIPMENT_DIR = ROOT / 'Equipment'
ENVIRONMENT_DIR = ROOT / 'Environment'
PREVIEWS_DIR = ROOT / 'Previews'


def export_all():
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    for name in ['quality_sample.blend', 'full_pack_procedural.blend']:
        path = SOURCES_DIR / name
        if path.exists():
            print(f'Found source: {path}')

    # Export command examples for local Blender usage.
    print('\nLocal Blender commands to export assets:')
    print('  blender --background --python Scripts/generate_quality_sample.py')
    print('  blender --background --python Scripts/generate_full_pack.py')
    print('  blender --background --python Scripts/generate_full_pack.py -- --export-fbx')
    print('  blender --background --python -c "import bpy; bpy.ops.export_scene.fbx(filepath=\'Characters/officer.fbx\')"')


def main():
    export_all()


if __name__ == '__main__':
    main()
