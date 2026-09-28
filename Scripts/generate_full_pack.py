# Full-pack procedural generation script for Blender

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
    make_material,
    add_cube,
    add_cylinder,
    add_uv_sphere,
    write_manifest,
)


def generate_character_variants():
    officer_materials = {
        'default': make_material('Mat_Officer_Default', base_color=(0.28, 0.38, 0.46, 1.0), metallic=0.18, roughness=0.52),
        'alt': make_material('Mat_Officer_Alt', base_color=(0.34, 0.42, 0.40, 1.0), metallic=0.16, roughness=0.58),
    }

    # Build two officer variants using the same armature logic.
    officer_1 = create_humanoid_rig()
    officer_2 = create_humanoid_rig()
    build_simple_officer(officer_1, variant='default')
    build_simple_officer(officer_2, variant='alt')
    officer_1.name = 'Char_Officer_01'
    officer_2.name = 'Char_Officer_02'
    officer_1.location.x = -1.0
    officer_2.location.x = 1.0

    suspect_material = make_material('Mat_Suspect_Cloth', base_color=(0.42, 0.30, 0.28, 1.0), metallic=0.0, roughness=0.85)
    suspect_1 = add_cube('Char_Suspect_01_Body', location=(-2.5, 0.0, 1.2), scale=(0.42, 0.24, 0.6), material=suspect_material)
    suspect_2 = add_cube('Char_Suspect_02_Body', location=(2.5, 0.0, 1.2), scale=(0.42, 0.24, 0.6), material=make_material('Mat_Suspect_Alt', base_color=(0.30, 0.36, 0.27, 1.0), metallic=0.0, roughness=0.8))

    civilian_m1 = make_material('Mat_Civilian_01', base_color=(0.62, 0.53, 0.45, 1.0), metallic=0.0, roughness=0.9)
    civilian_m2 = make_material('Mat_Civilian_02', base_color=(0.60, 0.78, 0.72, 1.0), metallic=0.0, roughness=0.88)
    civilian_1 = add_cube('Char_Civilian_01_Body', location=(-4.5, 0.0, 1.1), scale=(0.38, 0.22, 0.55), material=civilian_m1)
    civilian_2 = add_cube('Char_Civilian_02_Body', location=(4.5, 0.0, 1.1), scale=(0.38, 0.22, 0.55), material=civilian_m2)


def generate_equipment_assets():
    build_carbine('Equip_Carbine')
    build_carbine('Equip_Carbine_Alt')

    pistol_mat = make_material('Mat_Weapon_Pistol', base_color=(0.12, 0.13, 0.14, 1.0), metallic=0.18, roughness=0.42)
    pistol_body = add_cube('Equip_Pistol', location=(-3.0, 1.4, 0.3), scale=(0.28, 0.08, 0.12), material=pistol_mat)
    pistol_grip = add_cube('Equip_Pistol_Grip', location=(-3.0, 1.32, 0.15), scale=(0.08, 0.12, 0.07), material=pistol_mat)

    shotgun_mat = make_material('Mat_Weapon_Shotgun', base_color=(0.24, 0.26, 0.25, 1.0), metallic=0.23, roughness=0.5)
    shotgun = add_cube('Equip_Shotgun', location=(3.0, 1.4, 0.35), scale=(0.85, 0.09, 0.14), material=shotgun_mat)

    shield_mat = make_material('Mat_Shield', base_color=(0.35, 0.36, 0.40, 1.0), metallic=0.38, roughness=0.48)
    shield = add_cube('Equip_Shield', location=(-3.0, -1.5, 0.9), scale=(0.7, 0.05, 0.9), material=shield_mat)
    shield_handle = add_cube('Equip_Shield_Handle', location=(-3.0, -1.45, 0.5), scale=(0.08, 0.18, 0.12), material=shield_mat)

    radio_mat = make_material('Mat_Radio', base_color=(0.18, 0.19, 0.18, 1.0), metallic=0.15, roughness=0.55)
    radio = add_cube('Equip_Radio', location=(3.0, -1.5, 0.35), scale=(0.16, 0.09, 0.05), material=radio_mat)

    flashlight_mat = make_material('Mat_Flashlight', base_color=(0.15, 0.16, 0.18, 1.0), metallic=0.22, roughness=0.4)
    flashlight = add_cube('Equip_Flashlight', location=(3.2, -1.0, 0.6), scale=(0.12, 0.05, 0.05), material=flashlight_mat)

    breach_mat = make_material('Mat_BreachingCharge', base_color=(0.75, 0.62, 0.24, 1.0), metallic=0.05, roughness=0.4)
    breach = add_cube('Equip_BreachingCharge', location=(-3.1, -1.1, 0.3), scale=(0.18, 0.14, 0.13), material=breach_mat)

    drone_mat = make_material('Mat_Drone', base_color=(0.20, 0.22, 0.24, 1.0), metallic=0.35, roughness=0.3)
    drone = add_cube('Equip_Drone', location=(0.0, 3.2, 0.35), scale=(0.25, 0.25, 0.12), material=drone_mat)

    med_mat = make_material('Mat_MedicalPouch', base_color=(0.46, 0.31, 0.26, 1.0), metallic=0.0, roughness=0.8)
    med_pouch = add_cube('Equip_MedicalPouch', location=(0.5, 3.2, 0.22), scale=(0.14, 0.09, 0.08), material=med_mat)


def generate_environment_assets():
    concrete = make_material('Mat_Concrete_Heavy', base_color=(0.47, 0.49, 0.52, 1.0), metallic=0.05, roughness=0.82)
    wood = make_material('Mat_Wood', base_color=(0.44, 0.32, 0.19, 1.0), metallic=0.0, roughness=0.82)
    metal = make_material('Mat_Metal', base_color=(0.44, 0.46, 0.50, 1.0), metallic=0.55, roughness=0.4)
    glass = make_material('Mat_Glass', base_color=(0.35, 0.52, 0.72, 0.55), metallic=0.0, roughness=0.2)

    # floor tile and walls
    floor = add_cube('Env_FloorTile_3x3', location=(0, 0, 0.0), scale=(3.0, 3.0, 0.12), material=concrete)
    wall = add_cube('Env_Wall_3m', location=(0, 3.0, 1.5), scale=(3.0, 0.18, 3.0), material=concrete)
    corner = add_cube('Env_Corner_3m', location=(-3.0, 0.0, 1.5), scale=(0.18, 3.0, 3.0), material=concrete)
    door_frame = add_cube('Env_DoorFrame', location=(0, 4.0, 1.5), scale=(1.2, 0.18, 3.0), material=wood)

    # props
    crate = add_cube('Env_Crate', location=(2.4, 2.2, 0.45), scale=(0.7, 0.7, 0.7), material=wood)
    pallet = add_cube('Env_Pallet', location=(2.4, -2.1, 0.12), scale=(1.2, 1.0, 0.12), material=wood)
    shelf = add_cube('Env_Shelf', location=(-2.4, 2.2, 1.0), scale=(1.8, 0.45, 1.05), material=metal)
    barrel = add_cylinder('Env_Barrel', location=(-2.4, -2.4, 0.5), radius=0.28, depth=0.88, material=metal)
    desk = add_cube('Env_Desk', location=(3.0, 0.0, 0.48), scale=(1.1, 0.7, 0.1), material=wood)
    chair = add_cube('Env_Chair', location=(3.2, 0.8, 0.45), scale=(0.45, 0.45, 0.7), material=wood)
    locker = add_cube('Env_Locker', location=(-3.6, 0.0, 0.9), scale=(0.5, 0.6, 1.8), material=metal)
    sofa = add_cube('Env_Sofa', location=(-3.8, 2.0, 0.45), scale=(1.8, 0.8, 0.9), material=concrete)
    monitor = add_cube('Env_Monitor', location=(3.2, -1.3, 0.9), scale=(0.45, 0.05, 0.3), material=glass)
    extinguisher = add_cylinder('Env_FireExtinguisher', location=(-0.7, 2.8, 0.5), radius=0.1, depth=0.55, material=make_material('Mat_Extinguisher', base_color=(0.82, 0.1, 0.12, 1.0), metallic=0.15, roughness=0.45))
    extraction_marker = add_cube('Env_ExtractionMarker', location=(0.0, -3.6, 0.25), scale=(0.15, 0.15, 0.5), material=make_material('Mat_Extraction', base_color=(0.18, 0.65, 0.35, 1.0), metallic=0.0, roughness=0.55))


if __name__ == '__main__':
    ensure_directories()
    setup_scene()
    generate_character_variants()
    generate_equipment_assets()
    generate_environment_assets()

    # save a full-pack source file in Sources/
    blend_path = ROOT / 'Sources' / 'full_pack_procedural.blend'
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))

    manifest = {
        'project': 'Tactical Co-op Asset Pack',
        'generation_mode': 'procedural Blender script',
        'status': 'full-pack procedural layout prepared; exports not generated in this session',
        'characters': ['Officer_01', 'Officer_02', 'Suspect_01', 'Suspect_02', 'Civilian_01', 'Civilian_02'],
        'equipment': ['Carbine', 'Pistol', 'Shotgun', 'Shield', 'Radio', 'Flashlight', 'Breaching Charge', 'Drone', 'Medical Pouch'],
        'architecture': ['Floor tile', 'Wall segment', 'Corner', 'Door frame', 'Warehouse props'],
        'animations': ['to be authored locally with the shared humanoid rig'],
        'unity_validation_required': True,
    }
    write_manifest(ROOT / 'Documentation' / 'full_pack_manifest.json', manifest)
    print('Full pack procedural build written. Run Blender locally to export the final sources and FBX assets.')
