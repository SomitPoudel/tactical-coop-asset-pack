# Shared procedural helpers for the Blender asset pack

import bpy
import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CHARACTERS_DIR = ROOT / "Characters"
EQUIPMENT_DIR = ROOT / "Equipment"
ENVIRONMENT_DIR = ROOT / "Environment"
ANIMATIONS_DIR = ROOT / "Animations"
MATERIALS_DIR = ROOT / "Materials"
TEXTURES_DIR = ROOT / "Textures"
SOURCES_DIR = ROOT / "Sources"
PREVIEWS_DIR = ROOT / "Previews"
DOCS_DIR = ROOT / "Documentation"


def ensure_directories():
    for d in [
        CHARACTERS_DIR,
        EQUIPMENT_DIR,
        ENVIRONMENT_DIR,
        ANIMATIONS_DIR,
        MATERIALS_DIR,
        TEXTURES_DIR,
        SOURCES_DIR,
        PREVIEWS_DIR,
        DOCS_DIR,
    ]:
        d.mkdir(parents=True, exist_ok=True)


def clear_scene():
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for block in bpy.data.meshes:
        if block.users == 0:
            bpy.data.meshes.remove(block)
    for block in bpy.data.cameras:
        if block.users == 0:
            bpy.data.cameras.remove(block)
    for block in bpy.data.materials:
        if block.users == 0:
            bpy.data.materials.remove(block)
    for block in bpy.data.images:
        if block.users == 0:
            bpy.data.images.remove(block)


def setup_scene():
    clear_scene()
    scene = bpy.context.scene
    scene.unit_settings.system = 'METRIC'
    scene.unit_settings.scale_length = 1.0
    scene.render.engine = 'CYCLES'
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.film_transparent = False
    scene.world.use_nodes = True
    scene.world.color = (0.04, 0.05, 0.06, 1.0)

    # Add reference cube for 1-meter validation.
    bpy.ops.mesh.primitive_cube_add(location=(0, 0, 0.5), scale=(0.5, 0.5, 0.5))
    ref = bpy.context.object
    ref.name = 'Reference_1m'
    ref.display_type = 'TEXTURED'
    ref.scale = (0.5, 0.5, 0.5)

    # Add soft key light and fill light.
    bpy.ops.object.light_add(type='AREA', location=(3, -2, 4))
    key = bpy.context.object
    key.name = 'Key_Light'
    key.data.energy = 1500
    key.data.shape = 'RECTANGLE'
    key.data.size = 2.0
    key.data.size_y = 2.0

    bpy.ops.object.light_add(type='AREA', location=(-3, 2, 3))
    fill = bpy.context.object
    fill.name = 'Fill_Light'
    fill.data.energy = 800
    fill.data.shape = 'RECTANGLE'
    fill.data.size = 2.5
    fill.data.size_y = 2.5

    # Camera for angled top-down orientation.
    bpy.ops.object.camera_add(location=(6, -6, 5), rotation=(math.radians(70), 0, math.radians(45)))
    cam = bpy.context.object
    cam.name = 'GameplayCamera'
    cam.data.lens = 35
    cam.data.dof.use_dof = False
    bpy.context.scene.camera = cam


def write_manifest(path, payload):
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(payload, fh, indent=2)


def make_material(name, base_color=(0.5, 0.5, 0.5, 1.0), metallic=0.0, roughness=0.7, emission=None):
    mat = bpy.data.materials.new(name=name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = base_color
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = roughness
    if emission is not None:
        bsdf.inputs['Emission Color'].default_value = emission
        bsdf.inputs['Emission Strength'].default_value = 1.0
    return mat


def add_cube(name, location=(0, 0, 0), scale=(1, 1, 1), material=None):
    bpy.ops.mesh.primitive_cube_add(location=location)
    obj = bpy.context.object
    obj.name = name
    obj.scale = scale
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_cylinder(name, location=(0, 0, 0), radius=0.5, depth=1.0, material=None):
    bpy.ops.mesh.primitive_cylinder_add(vertices=16, radius=radius, depth=depth, location=location)
    obj = bpy.context.object
    obj.name = name
    if material is not None:
        obj.data.materials.append(material)
    return obj


def add_uv_sphere(name, location=(0, 0, 0), radius=0.5, material=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=10, radius=radius, location=location)
    obj = bpy.context.object
    obj.name = name
    if material is not None:
        obj.data.materials.append(material)
    return obj


def set_ground_origin(obj, z_offset=0.0):
    obj.location.z = z_offset
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='BOUNDS')
    obj.location.z = z_offset


def parent_to_bone(obj, armature, bone_name):
    obj.parent = armature
    obj.parent_type = 'BONE'
    obj.parent_bone = bone_name


def create_humanoid_rig(name='Rig_Humanoid'):
    bpy.ops.object.armature_add(location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = name
    arm.data.name = name + '_Data'
    arm.data.display_type = 'STICK'
    arm.show_in_front = True

    bones = {
        'root': (0, 0, 0.0),
        'pelvis': (0, 0, 0.9),
        'spine_01': (0, 0, 1.2),
        'spine_02': (0, 0, 1.5),
        'neck': (0, 0, 1.85),
        'head': (0, 0, 2.05),
        'shoulder_L': (-0.18, 0.0, 1.55),
        'upper_arm_L': (-0.32, 0.0, 1.35),
        'forearm_L': (-0.60, 0.0, 1.20),
        'hand_L': (-0.85, 0.0, 1.10),
        'shoulder_R': (0.18, 0.0, 1.55),
        'upper_arm_R': (0.32, 0.0, 1.35),
        'forearm_R': (0.60, 0.0, 1.20),
        'hand_R': (0.85, 0.0, 1.10),
        'hip_L': (-0.12, 0.0, 0.75),
        'thigh_L': (-0.18, 0.0, 0.40),
        'shin_L': (-0.18, 0.0, 0.05),
        'foot_L': (-0.18, 0.0, -0.18),
        'hip_R': (0.12, 0.0, 0.75),
        'thigh_R': (0.18, 0.0, 0.40),
        'shin_R': (0.18, 0.0, 0.05),
        'foot_R': (0.18, 0.0, -0.18),
    }

    edit_bones = arm.data.edit_bones
    built = {}
    for name, loc in bones.items():
        eb = edit_bones.new(name)
        eb.head = loc
        eb.tail = (loc[0], loc[1], loc[2] + 0.05)
        built[name] = eb

    # Connect the skeleton.
    for parent, child in [
        ('root', 'pelvis'),
        ('pelvis', 'spine_01'),
        ('spine_01', 'spine_02'),
        ('spine_02', 'neck'),
        ('neck', 'head'),
        ('spine_02', 'shoulder_L'),
        ('spine_02', 'shoulder_R'),
        ('shoulder_L', 'upper_arm_L'),
        ('upper_arm_L', 'forearm_L'),
        ('forearm_L', 'hand_L'),
        ('shoulder_R', 'upper_arm_R'),
        ('upper_arm_R', 'forearm_R'),
        ('forearm_R', 'hand_R'),
        ('pelvis', 'hip_L'),
        ('hip_L', 'thigh_L'),
        ('thigh_L', 'shin_L'),
        ('shin_L', 'foot_L'),
        ('pelvis', 'hip_R'),
        ('hip_R', 'thigh_R'),
        ('thigh_R', 'shin_R'),
        ('shin_R', 'foot_R'),
    ]:
        built[child].parent = built[parent]

    bpy.ops.object.mode_set(mode='OBJECT')
    return arm


def build_simple_officer(armature, variant='default'):
    body_material = make_material('Mat_Officer_Fabric', base_color=(0.22, 0.28, 0.34, 1.0), metallic=0.0, roughness=0.8)
    armor_material = make_material('Mat_Officer_Armor', base_color=(0.34, 0.40, 0.48, 1.0), metallic=0.2, roughness=0.55)
    accent_material = make_material('Mat_Officer_Accent', base_color=(0.58, 0.70, 0.80, 1.0), metallic=0.0, roughness=0.55)
    dark_material = make_material('Mat_Officer_Black', base_color=(0.12, 0.13, 0.14, 1.0), metallic=0.2, roughness=0.55)
    skin_material = make_material('Mat_Skin', base_color=(0.82, 0.72, 0.64, 1.0), metallic=0.0, roughness=0.7)

    # torso + pelvis proxy
    torso = add_cube('Officer_Torso', location=(0, 0, 1.45), scale=(0.42, 0.24, 0.62), material=body_material)
    pelvis = add_cube('Officer_Pelvis', location=(0, 0, 0.95), scale=(0.38, 0.22, 0.28), material=armor_material)
    chest = add_cube('Officer_ChestPlate', location=(0, 0, 1.55), scale=(0.44, 0.28, 0.25), material=armor_material)
    neck = add_cylinder('Officer_Neck', location=(0, 0, 1.92), radius=0.07, depth=0.18, material=skin_material)
    head = add_uv_sphere('Officer_Head', location=(0, 0, 2.12), radius=0.16, material=skin_material)
    helmet = add_uv_sphere('Officer_Helmet', location=(0, 0, 2.25), radius=0.2, material=dark_material)
    helmet.scale = (1.0, 1.0, 0.75)
    helmet.data.materials.clear(); helmet.data.materials.append(dark_material)

    # Lower limbs
    thigh_l = add_cylinder('Officer_Thigh_L', location=(-0.12, 0.0, 0.5), radius=0.12, depth=0.55, material=body_material)
    thigh_r = add_cylinder('Officer_Thigh_R', location=(0.12, 0.0, 0.5), radius=0.12, depth=0.55, material=body_material)
    shin_l = add_cylinder('Officer_Shin_L', location=(-0.12, 0.0, 0.08), radius=0.09, depth=0.55, material=dark_material)
    shin_r = add_cylinder('Officer_Shin_R', location=(0.12, 0.0, 0.08), radius=0.09, depth=0.55, material=dark_material)
    boot_l = add_cube('Officer_Boot_L', location=(-0.12, 0.12, -0.18), scale=(0.15, 0.24, 0.1), material=dark_material)
    boot_r = add_cube('Officer_Boot_R', location=(0.12, 0.12, -0.18), scale=(0.15, 0.24, 0.1), material=dark_material)

    # Upper limbs
    upper_l = add_cylinder('Officer_UpperArm_L', location=(-0.34, 0.0, 1.38), radius=0.08, depth=0.42, material=armor_material)
    forearm_l = add_cylinder('Officer_Forearm_L', location=(-0.62, 0.0, 1.16), radius=0.07, depth=0.42, material=armor_material)
    hand_l = add_cube('Officer_Hand_L', location=(-0.83, 0.0, 1.10), scale=(0.12, 0.12, 0.12), material=skin_material)
    upper_r = add_cylinder('Officer_UpperArm_R', location=(0.34, 0.0, 1.38), radius=0.08, depth=0.42, material=armor_material)
    forearm_r = add_cylinder('Officer_Forearm_R', location=(0.62, 0.0, 1.16), radius=0.07, depth=0.42, material=armor_material)
    hand_r = add_cube('Officer_Hand_R', location=(0.83, 0.0, 1.10), scale=(0.12, 0.12, 0.12), material=skin_material)

    # gear
    belt = add_cube('Officer_Belt', location=(0, 0, 1.06), scale=(0.46, 0.25, 0.08), material=accent_material)
    radio = add_cube('Officer_Radio', location=(0.25, 0.18, 1.05), scale=(0.12, 0.08, 0.05), material=dark_material)
    pouch = add_cube('Officer_MedicalPouch', location=(-0.25, 0.18, 1.04), scale=(0.12, 0.09, 0.08), material=accent_material)
    headset = add_cylinder('Officer_Headset', location=(0.0, 0.18, 2.04), radius=0.06, depth=0.12, material=dark_material)

    # parent to armature bones
    for obj in [torso, pelvis, chest, neck, head, helmet, thigh_l, thigh_r, shin_l, shin_r, boot_l, boot_r,
                upper_l, forearm_l, hand_l, upper_r, forearm_r, hand_r, belt, radio, pouch, headset]:
        obj.parent = armature
        obj.parent_type = 'BONE'
        obj.parent_bone = 'pelvis' if obj.name.startswith('Officer_Pelvis') else 'pelvis'

    # direct assignments by geo type
    for obj in [torso]: obj.parent_bone = 'spine_02'
    for obj in [pelvis]: obj.parent_bone = 'pelvis'
    for obj in [chest, belt, radio, pouch]: obj.parent_bone = 'spine_02'
    for obj in [neck, head, helmet, headset]: obj.parent_bone = 'neck'
    for obj in [thigh_l, shin_l, boot_l]: obj.parent_bone = 'thigh_L'
    for obj in [thigh_r, shin_r, boot_r]: obj.parent_bone = 'thigh_R'
    for obj in [upper_l, forearm_l, hand_l]: obj.parent_bone = 'upper_arm_L'
    for obj in [upper_r, forearm_r, hand_r]: obj.parent_bone = 'upper_arm_R'

    # name the whole character asset.
    officer_root = bpy.data.objects.new('Char_Officer', None)
    officer_root.name = 'Char_Officer'
    return armature


def build_carbine(name='Equip_Carbine'):
    mat = make_material('Mat_Weapon_Arid', base_color=(0.18, 0.20, 0.21, 1.0), metallic=0.35, roughness=0.45)
    grip = make_material('Mat_Weapon_Grip', base_color=(0.10, 0.09, 0.10, 1.0), metallic=0.0, roughness=0.78)

    body = add_cube(f'{name}_Body', location=(0, 0, 0), scale=(0.9, 0.08, 0.12), material=mat)
    stock = add_cube(f'{name}_Stock', location=(-0.55, 0, 0), scale=(0.28, 0.06, 0.12), material=mat)
    grip_block = add_cube(f'{name}_Grip', location=(0.18, -0.05, -0.08), scale=(0.15, 0.08, 0.22), material=grip)
    barrel = add_cylinder(f'{name}_Barrel', location=(0.62, 0.0, 0.0), radius=0.025, depth=0.34, material=mat)
    barrel.rotation_euler = (0, math.radians(90), 0)
    mag = add_cube(f'{name}_Magazine', location=(0.12, -0.14, -0.10), scale=(0.16, 0.05, 0.08), material=mat)
    front_sight = add_cube(f'{name}_FrontSight', location=(0.76, 0.0, 0.06), scale=(0.03, 0.025, 0.025), material=mat)
    rear_sight = add_cube(f'{name}_RearSight', location=(0.42, 0.0, 0.06), scale=(0.03, 0.025, 0.025), material=mat)

    for obj in [body, stock, grip_block, barrel, mag, front_sight, rear_sight]:
        obj.name = obj.name.replace('_Body', '') if obj.name.endswith('_Body') else obj.name

    return body


def create_sample_room():
    concrete = make_material('Mat_Concrete', base_color=(0.45, 0.46, 0.48, 1.0), metallic=0.0, roughness=0.85)
    floor = add_cube('Sample_Floor', location=(0, 0, 0), scale=(4.0, 4.0, 0.18), material=concrete)

    wall_n = add_cube('Sample_Wall_North', location=(0, 2.0, 1.5), scale=(4.0, 0.2, 3.0), material=concrete)
    wall_s = add_cube('Sample_Wall_South', location=(0, -2.0, 1.5), scale=(4.0, 0.2, 3.0), material=concrete)
    wall_e = add_cube('Sample_Wall_East', location=(2.0, 0, 1.5), scale=(0.2, 4.0, 3.0), material=concrete)
    wall_w = add_cube('Sample_Wall_West', location=(-2.0, 0, 1.5), scale=(0.2, 4.0, 3.0), material=concrete)

    # doorway opening in north wall
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=(0, 2.05, 0.0))
    door_pivot = bpy.context.object
    door_pivot.name = 'DoorPivot_01'

    frame_mat = make_material('Mat_Frame', base_color=(0.55, 0.48, 0.35, 1.0), metallic=0.1, roughness=0.7)
    door_leaves = []
    for i, x in enumerate([-0.52, 0.52]):
        door = add_cube(f'Sample_Door_{i}', location=(x, 1.95, 1.1), scale=(0.5, 0.08, 2.0), material=frame_mat)
        door.parent = door_pivot
        door.location = (x, 0.0, 1.1)
        door_leaves.append(door)

    # single door pivot at hinge side
    door_pivot.rotation_euler = (0, 0, math.radians(0))
    return door_pivot


def set_scene_camera_pose():
    cam = bpy.data.objects['GameplayCamera']
    cam.location = (6.0, -6.0, 5.5)
    cam.rotation_euler = (math.radians(70), 0, math.radians(45))


def write_sample_manifest():
    manifest = {
        'project_name': 'Tactical Co-op Asset Pack',
        'status': 'procedural scripts prepared; local Blender exports not generated in this session',
        'scene_units': 'meters',
        'camera': 'angled top-down',
        'rig': 'shared humanoid skeleton',
        'characters': ['Officer', 'Suspect', 'Civilian'],
        'equipment': ['Carbine', 'Pistol', 'Shotgun', 'Shield', 'Radio', 'Flashlight', 'Breaching Charge', 'Drone', 'Medical Pouch'],
        'architecture': ['Floor tile', 'wall segments', 'corner', 'doorway', 'single door', 'double door', 'window wall', 'shutter', 'pillar', 'stairs', 'roof'],
        'props': ['Crate', 'Pallet', 'Shelving', 'Barrel', 'Desk', 'Chair', 'Locker', 'Sofa', 'Monitor', 'Fire extinguisher', 'Pendant light', 'Wall light', 'Fluorescent light', 'Security camera', 'Fuse box', 'Briefcase', 'Extraction marker'],
        'triangles_estimated': 'to be measured after local Blender export',
        'rig_compatibility': 'shared humanoid rig target',
        'exports_generated': False,
    }
    write_manifest(ROOT / 'Documentation' / 'sample_manifest.json', manifest)


if __name__ == '__main__':
    ensure_directories()
    setup_scene()
    arm = create_humanoid_rig()
    build_simple_officer(arm)
    build_carbine()
    create_sample_room()
    set_scene_camera_pose()
    write_sample_manifest()
    print('Procedural sample setup complete. Run Blender locally to export .blend and FBX files.')
