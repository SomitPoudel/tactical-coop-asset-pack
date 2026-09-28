"""Create and validate a separate animated working copy of the SWAT asset."""
from array import array
import json
import math
from pathlib import Path
import tempfile

import bpy
from mathutils import Matrix, Quaternion, Vector


ROOT = Path(__file__).resolve().parents[1]
ASSET_ROOT = ROOT / "References" / "swat-operator-remastered"
INSPECTION = ASSET_ROOT / "inspection"
SOURCE_BLEND = INSPECTION / "swat_operator_remastered_inspection.blend"
WORK_DIR = ASSET_ROOT / "working"
PREVIEW_DIR = INSPECTION / "previews"
REPORT_PATH = INSPECTION / "inspection_report.json"
CLIPS = ("SWAT_RifleReadyIdle", "SWAT_InPlaceWalk", "SWAT_Crouch")


def world_bounds(obj):
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    minimum = Vector(tuple(min(point[i]
                     for point in corners) for i in range(3)))
    maximum = Vector(tuple(max(point[i]
                     for point in corners) for i in range(3)))
    return minimum, maximum


def bounds_center(obj):
    minimum, maximum = world_bounds(obj)
    return (minimum + maximum) * 0.5


def parent_keep_world(child, parent):
    bpy.context.view_layer.update()
    world = child.matrix_world.copy()
    parent_world = parent.matrix_world.copy()
    child.parent = parent
    child.matrix_parent_inverse = parent_world.inverted()
    child.matrix_basis = world
    bpy.context.view_layer.update()


def add_empty(name, collection, location, display_type="ARROWS", size=0.075):
    obj = bpy.data.objects.new(name, None)
    collection.objects.link(obj)
    obj.empty_display_type = display_type
    obj.empty_display_size = size
    obj.location = location
    obj.hide_render = True
    return obj


def action_slot(action, owner):
    matching = [slot for slot in action.slots
                if slot.target_id_type == "OBJECT"]
    slot = matching[0] if matching else action.slots.new("OBJECT", owner.name)
    owner.animation_data_create()
    owner.animation_data.action = action
    owner.animation_data.action_slot = slot
    return slot


def create_action(owner, name):
    action = bpy.data.actions.new(name)
    action_slot(action, owner)
    layer = action.layers.new("Base")
    layer.strips.new(type="KEYFRAME")
    return action


def set_clip_action(armature, action):
    armature.animation_data.action = action
    if len(action.slots):
        armature.animation_data.action_slot = action.slots[0]


def make_target_action(obj, name, samples):
    action = create_action(obj, name)
    for frame, location in samples:
        obj.location = location
        obj.keyframe_insert(data_path="location", frame=frame,
                            group=obj.name)
    for layer in action.layers:
        for strip in layer.strips:
            bag = strip.channelbag(action.slots[0])
            if bag:
                for curve in bag.fcurves:
                    for point in curve.keyframe_points:
                        point.interpolation = "LINEAR"
    return action


def insert_pose_key(pose_bone, frame):
    pose_bone.keyframe_insert(data_path="location", frame=frame,
                              group=pose_bone.name)
    pose_bone.keyframe_insert(data_path="rotation_quaternion", frame=frame,
                              group=pose_bone.name)


def set_bone_pose(pose_bone, base, location_offset=(0, 0, 0),
                  axis=(1, 0, 0), angle=0.0):
    pose_bone.rotation_mode = "QUATERNION"
    pose_bone.location = base[0] + Vector(location_offset)
    pose_bone.rotation_quaternion = (
        base[1] @ Quaternion(Vector(axis).normalized(), angle)).normalized()


def make_ik(pose_bone, target, pole, chain_count, use_rotation=False):
    constraint = pose_bone.constraints.new("IK")
    constraint.name = "Inspection_BakedIK"
    constraint.target = target
    constraint.pole_target = pole
    constraint.chain_count = chain_count
    constraint.iterations = 64
    constraint.use_stretch = False
    constraint.use_rotation = use_rotation
    constraint.orient_weight = 1.0 if use_rotation else 0.0
    return constraint


def bake_pose_action(scene, armature, start, end):
    for obj in scene.objects:
        obj.select_set(False)
    armature.select_set(True)
    bpy.context.view_layer.objects.active = armature
    if armature.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    bpy.ops.object.mode_set(mode="POSE")
    bpy.ops.pose.select_all(action="SELECT")
    scene.frame_set(start)
    bpy.ops.nla.bake(
        frame_start=start, frame_end=end, step=1,
        only_selected=True, visual_keying=True,
        clear_constraints=False, use_current_action=True,
        bake_types={"POSE"},
        channel_types={"LOCATION", "ROTATION", "SCALE"})
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()


def foot_target_position(armature, pose_bone):
    return armature.matrix_world @ pose_bone.head


def bone_world_point(armature, point):
    return armature.matrix_world @ point


def evaluated_triangles(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    per_object = {}
    total = 0
    for obj in objects:
        if obj.type != "MESH":
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            count = len(mesh.loop_triangles)
            per_object[obj.name] = count
            total += count
        finally:
            evaluated.to_mesh_clear()
    return {"total": total, "by_mesh": per_object}


def weighted_foot_min_z(mesh_obj, armature, bone_name):
    group = mesh_obj.vertex_groups.get(bone_name)
    if group is None:
        return None
    indices = set()
    for vertex in mesh_obj.data.vertices:
        if any(membership.group == group.index and membership.weight > 0.15
               for membership in vertex.groups):
            indices.add(vertex.index)
    if not indices:
        return None
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = mesh_obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    try:
        world = evaluated.matrix_world
        return min((world @ mesh.vertices[index].co).z for index in indices)
    finally:
        evaluated.to_mesh_clear()


def pose_metrics(scene, armature, body, weapon_root, targets, actions,
                 target_actions):
    report = {}
    saved_action = armature.animation_data.action
    saved_slot = getattr(armature.animation_data, "action_slot", None)
    frames_to_render = {}
    for action_name in CLIPS:
        action = actions[action_name]
        set_clip_action(armature, action)
        for obj, target_action in target_actions[action_name].items():
            obj.animation_data.action = target_action
            if len(target_action.slots):
                obj.animation_data.action_slot = target_action.slots[0]
        start, end = [int(round(value)) for value in action.frame_range]
        sample_frames = sorted(set((start, (start + end) // 2, end)))
        frames_to_render[action_name] = sample_frames
        frame_results = []
        hips_positions = []
        for frame in range(start, end + 1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            hips = armature.pose.bones.get("mixamorig:Hips")
            hips_positions.append(
                (armature.matrix_world @ hips.matrix).translation.z)
            left_hand = armature.pose.bones.get("mixamorig:LeftHand")
            right_hand = armature.pose.bones.get("mixamorig:RightHand")
            feet = {}
            for side in ("Left", "Right"):
                foot_name = "mixamorig:" + side + "Foot"
                foot_bone = armature.pose.bones.get(foot_name)
                target = targets[side + "Foot"]
                tail_world = foot_target_position(armature, foot_bone)
                feet[side] = {
                    "sole_min_z_m": weighted_foot_min_z(body, armature,
                                                        foot_name),
                    "target_error_m": (tail_world - target.matrix_world.translation).length,
                }
            right_grip = targets["RightGrip"].matrix_world.translation
            left_grip = targets["LeftGrip"].matrix_world.translation
            right_hand_point = bone_world_point(armature, right_hand.head)
            left_hand_point = bone_world_point(armature, left_hand.head)
            named_bones = [
                "mixamorig:LeftUpLeg", "mixamorig:LeftLeg", "mixamorig:LeftFoot",
                "mixamorig:RightUpLeg", "mixamorig:RightLeg", "mixamorig:RightFoot",
                "mixamorig:LeftArm", "mixamorig:LeftForeArm",
                "mixamorig:RightArm", "mixamorig:RightForeArm",
            ]
            length_ratios = []
            for name in named_bones:
                pose_bone = armature.pose.bones.get(name)
                rest_length = pose_bone.bone.length
                current_length = (pose_bone.tail - pose_bone.head).length
                if rest_length > 1e-6:
                    length_ratios.append(current_length / rest_length)
            frame_results.append({
                "frame": frame,
                "hips_z_m": (armature.matrix_world @ hips.matrix).translation.z,
                "armature_xy": list(armature.matrix_world.translation[:2]),
                "feet": feet,
                "right_hand_stock_error_m": (right_hand_point - right_grip).length,
                "left_hand_foregrip_error_m": (left_hand_point - left_grip).length,
                "minimum_limb_length_ratio": min(length_ratios, default=None),
                "maximum_limb_length_ratio": max(length_ratios, default=None),
            })
        report[action_name] = {
            "frame_range": [start, end],
            "sampled_frames": sample_frames,
            "frame_count_evaluated": len(frame_results),
            "frames": frame_results,
            "max_right_hand_stock_error_m": max(
                row["right_hand_stock_error_m"] for row in frame_results),
            "max_left_hand_foregrip_error_m": max(
                row["left_hand_foregrip_error_m"] for row in frame_results),
            "max_foot_target_error_m": max(
                foot["target_error_m"] for row in frame_results
                for foot in row["feet"].values()),
            "minimum_foot_sole_z_m": min(
                foot["sole_min_z_m"] for row in frame_results
                for foot in row["feet"].values()
                if foot["sole_min_z_m"] is not None),
            "minimum_limb_length_ratio": min(
                row["minimum_limb_length_ratio"] for row in frame_results
                if row["minimum_limb_length_ratio"] is not None),
            "maximum_limb_length_ratio": max(
                row["maximum_limb_length_ratio"] for row in frame_results
                if row["maximum_limb_length_ratio"] is not None),
            "hips_vertical_excursion_m": max(hips_positions) - min(hips_positions),
        }
    set_clip_action(armature, saved_action)
    if saved_slot and hasattr(armature.animation_data, "action_slot"):
        armature.animation_data.action_slot = saved_slot
    scene.frame_set(1)
    return report, frames_to_render


def create_contact_sheet(scene, armature, actions, frames_by_action,
                         camera, path):
    tile_width, tile_height = 450, 600
    columns = 3
    rows = len(CLIPS)
    sheet_width, sheet_height = tile_width * columns, tile_height * rows
    composed = array("f", [0.075, 0.075, 0.075, 1.0]) * (
        sheet_width * sheet_height)
    old_resolution = (scene.render.resolution_x, scene.render.resolution_y,
                      scene.render.resolution_percentage)
    scene.render.resolution_x = tile_width
    scene.render.resolution_y = tile_height
    scene.render.resolution_percentage = 100
    scene.camera = camera
    layout = []
    with tempfile.TemporaryDirectory(prefix="swat_contact_sheet_") as temp_dir:
        for row_index, action_name in enumerate(CLIPS):
            action = actions[action_name]
            set_clip_action(armature, action)
            sample_frames = frames_by_action[action_name]
            layout.append({"row": row_index, "action": action_name,
                           "columns": sample_frames})
            for column, frame in enumerate(sample_frames):
                scene.frame_set(frame)
                bpy.context.view_layer.update()
                tile_path = Path(temp_dir) / f"{row_index}_{column}.png"
                scene.render.filepath = str(tile_path)
                bpy.ops.render.render(write_still=True)
                rendered = bpy.data.images.load(
                    str(tile_path), check_existing=False)
                pixels = array("f", [0.0]) * (tile_width * tile_height * 4)
                rendered.pixels.foreach_get(pixels)
                bpy.data.images.remove(rendered)
                for y in range(tile_height):
                    source_start = y * tile_width * 4
                    destination_start = (
                        (row_index * tile_height + y) * sheet_width +
                        column * tile_width) * 4
                    composed[destination_start:destination_start + tile_width * 4] = (
                        pixels[source_start:source_start + tile_width * 4])
    scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = old_resolution
    sheet = bpy.data.images.new("SWAT_Animation_Contact_Sheet",
                                width=sheet_width, height=sheet_height,
                                alpha=False, float_buffer=False)
    sheet.pixels.foreach_set(composed)
    sheet.filepath_raw = str(path)
    sheet.file_format = "PNG"
    sheet.save()
    bpy.data.images.remove(sheet)
    return layout


def add_export_tracks(armature, actions):
    animation = armature.animation_data
    animation.action = None
    for track in list(animation.nla_tracks):
        animation.nla_tracks.remove(track)
    for name in CLIPS:
        action = actions[name]
        action.use_fake_user = True
        track = animation.nla_tracks.new()
        track.name = name
        strip = track.strips.new(name, int(action.frame_range[0]), action)
        strip.blend_type = "REPLACE"
        strip.extrapolation = "NOTHING"
        if hasattr(strip, "action_slot") and len(action.slots):
            strip.action_slot = action.slots[0]


def export_fbx(scene, armature, asset_objects, actions, path):
    add_export_tracks(armature, actions)
    for obj in scene.objects:
        obj.select_set(False)
    for obj in asset_objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = armature
    path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.fbx(
        filepath=str(path), use_selection=True,
        object_types={"EMPTY", "MESH", "ARMATURE"},
        use_mesh_modifiers=True, add_leaf_bones=False,
        apply_unit_scale=True, axis_forward="-Z", axis_up="Y",
        bake_anim=True, bake_anim_use_nla_strips=True,
        bake_anim_use_all_actions=False, bake_anim_simplify_factor=0.0,
        use_custom_props=True)
    for track in list(armature.animation_data.nla_tracks):
        armature.animation_data.nla_tracks.remove(track)
    armature.animation_data.action = actions[CLIPS[0]]
    if len(actions[CLIPS[0]].slots):
        armature.animation_data.action_slot = actions[CLIPS[0]].slots[0]
    for obj in scene.objects:
        obj.select_set(False)
    bpy.context.view_layer.objects.active = armature
    scene.frame_set(1)
    return path.is_file() and path.stat().st_size > 0


def fbx_round_trip(path, expected_meshes, expected_bones):
    before_actions = set(bpy.data.actions)
    source_scene = bpy.context.scene
    test_scene = bpy.data.scenes.new("SWAT_FBX_RoundTrip")
    window = bpy.context.window
    try:
        if window:
            window.scene = test_scene
            bpy.ops.import_scene.fbx(filepath=str(path))
        else:
            with bpy.context.temp_override(scene=test_scene):
                bpy.ops.import_scene.fbx(filepath=str(path))
        objects = list(test_scene.objects)
        meshes = [obj for obj in objects if obj.type == "MESH"]
        armatures = [obj for obj in objects if obj.type == "ARMATURE"]
        actions = [action.name for action in bpy.data.actions
                   if action not in before_actions]
        matches = {name: any(name in observed for observed in actions)
                   for name in CLIPS}
        bones = len(armatures[0].data.bones) if armatures else 0
        return {
            "status": "passed" if (len(meshes) == expected_meshes and
                                   len(armatures) == 1 and
                                   bones == expected_bones and all(matches.values()))
            else "failed",
            "mesh_count": len(meshes),
            "armature_count": len(armatures),
            "bone_count": bones,
            "animation_actions": actions,
            "expected_clip_name_matches": matches,
        }
    except Exception as error:
        return {"status": "failed", "error": f"{type(error).__name__}: {error}"}
    finally:
        if window:
            window.scene = source_scene
        for obj in list(test_scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(test_scene)
        for action in list(bpy.data.actions):
            if action not in before_actions:
                action.use_fake_user = False
                if action.users == 0:
                    bpy.data.actions.remove(action)


def main():
    if not SOURCE_BLEND.is_file():
        raise FileNotFoundError(
            f"Run Scripts/inspect_swat_operator.py first: {SOURCE_BLEND}")
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=str(SOURCE_BLEND))
    scene = bpy.context.scene
    armature = next(obj for obj in scene.objects if obj.type == "ARMATURE")
    meshes = [obj for obj in scene.objects if obj.type == "MESH"]
    body = next(obj for obj in meshes if obj.name == "sol_8_low")
    weapon = bpy.data.objects["topGun_low"]
    source_action = armature.animation_data.action
    if source_action is None:
        raise RuntimeError("The imported reference pose action is missing.")
    source_action.name = "Reference_Imported_Static"
    source_action.use_fake_user = True
    source_action["inspection_role"] = "Preserved original imported static pose"
    scene.frame_set(int(source_action.frame_range[0]))
    bpy.context.view_layer.update()

    original_children = sorted(obj.name for obj in scene.objects
                               if obj.parent == weapon)
    original_weapon_matrix = weapon.matrix_world.copy()
    stock = bpy.data.objects["stockThing_low"]
    foregrip = bpy.data.objects["frontGrip_low"]
    barrel = bpy.data.objects["barrel_low"]
    stock_center = bounds_center(stock)
    foregrip_center = bounds_center(foregrip)
    barrel_min, barrel_max = world_bounds(barrel)
    muzzle_point = Vector((barrel_max.x,
                           (barrel_min.y + barrel_max.y) * 0.5,
                           (barrel_min.z + barrel_max.z) * 0.5))
    right_hand = armature.pose.bones["mixamorig:RightHand"]
    left_hand = armature.pose.bones["mixamorig:LeftHand"]
    rig_collection = bpy.data.collections.new("GameReady_Sockets_And_TempIK")
    scene.collection.children.link(rig_collection)

    right_socket = add_empty("SOCKET_RightHand", rig_collection,
                             armature.matrix_world @ right_hand.matrix.translation)
    right_socket.parent = armature
    right_socket.parent_type = "BONE"
    right_socket.parent_bone = right_hand.name
    right_socket.matrix_world = armature.matrix_world @ right_hand.matrix
    parent_keep_world(weapon, right_socket)
    weapon_matrix_preserved = max(
        abs(original_weapon_matrix[row][column] -
            weapon.matrix_world[row][column])
        for row in range(4) for column in range(4)) < 1e-5
    right_grip = add_empty("SOCKET_RightHand_Grip", rig_collection,
                           stock_center, "SPHERE", 0.025)
    left_grip = add_empty("SOCKET_LeftHand_Grip", rig_collection,
                          foregrip_center, "SPHERE", 0.025)
    muzzle = add_empty("SOCKET_Muzzle", rig_collection,
                       muzzle_point, "CIRCLE", 0.04)
    for socket in (right_grip, left_grip, muzzle):
        parent_keep_world(socket, weapon)

    hand_action = armature.animation_data.action
    hand_slot = armature.animation_data.action_slot
    original_basis = right_hand.matrix_basis.copy()
    armature.animation_data.action = None
    right_hand.matrix_basis = original_basis
    bpy.context.view_layer.update()
    weapon_before_motion = weapon.matrix_world.copy()
    right_hand.rotation_mode = "QUATERNION"
    right_hand.rotation_quaternion = (
        right_hand.rotation_quaternion @ Quaternion((0, 0, 1), math.radians(20)))
    bpy.context.view_layer.update()
    weapon_after_motion = weapon.matrix_world.copy()
    socket_motion = (weapon_after_motion.translation -
                     weapon_before_motion.translation).length
    right_hand.matrix_basis = original_basis
    armature.animation_data.action = hand_action
    if hand_slot and hasattr(armature.animation_data, "action_slot"):
        armature.animation_data.action_slot = hand_slot
    scene.frame_set(1)
    bpy.context.view_layer.update()

    base_pose = {}
    for pose_bone in armature.pose.bones:
        pose_bone.rotation_mode = "QUATERNION"
        base_pose[pose_bone.name] = (
            pose_bone.location.copy(), pose_bone.rotation_quaternion.copy(),
            pose_bone.scale.copy())

    left_elbow = armature.pose.bones["mixamorig:LeftForeArm"]
    left_elbow_world = armature.matrix_world @ left_elbow.head
    left_pole = add_empty("TEMP_IK_LeftArmPole", rig_collection,
                          left_elbow_world + Vector((0, -0.32, 0)), "SPHERE", 0.02)
    left_arm_ik = make_ik(left_elbow, left_grip, left_pole, 2)
    foot_targets = {}
    foot_poles = {}
    foot_constraints = []
    for side in ("Left", "Right"):
        foot_bone = armature.pose.bones["mixamorig:" + side + "Foot"]
        target_location = foot_target_position(armature, foot_bone)
        foot_target = add_empty("TEMP_IK_" + side + "Foot", rig_collection,
                                target_location, "SPHERE", 0.02)
        foot_target.rotation_mode = "QUATERNION"
        foot_target.rotation_quaternion = (
            armature.matrix_world.to_3x3() @ foot_bone.matrix.to_3x3()).to_quaternion()
        knee = armature.pose.bones["mixamorig:" + side + "Leg"]
        knee_world = armature.matrix_world @ knee.head
        pole = add_empty("TEMP_IK_" + side + "KneePole", rig_collection,
                         knee_world + Vector((0, -0.32, 0)), "SPHERE", 0.02)
        foot_targets[side] = foot_target
        foot_poles[side] = pole
        foot_constraints.append(make_ik(knee, foot_target, pole, 2))
        rotation_constraint = foot_bone.constraints.new("COPY_ROTATION")
        rotation_constraint.name = "Inspection_BakedFootRotation"
        rotation_constraint.target = foot_target
        rotation_constraint.owner_space = "WORLD"
        rotation_constraint.target_space = "WORLD"
        foot_constraints.append(rotation_constraint)

    reference = source_action
    actions = {}
    target_actions = {}
    idle_frames = list(range(1, 62))
    walk_frames = list(range(1, 34))
    crouch_frames = list(range(1, 33))
    left_base_foot = foot_targets["Left"].location.copy()
    right_base_foot = foot_targets["Right"].location.copy()

    def build_clip(name, frames, apply_pose):
        action = reference.copy()
        action.name = name
        action["generated_for_inspection"] = True
        action["frame_start"] = frames[0]
        action["frame_end"] = frames[-1]
        action_slot(action, armature)
        set_clip_action(armature, action)
        for frame in frames:
            scene.frame_set(frame)
            keyed = apply_pose(frame)
            for bone_name in keyed:
                insert_pose_key(armature.pose.bones[bone_name], frame)
        for layer in action.layers:
            for strip in layer.strips:
                bag = strip.channelbag(action.slots[0])
                if bag:
                    for curve in bag.fcurves:
                        for point in curve.keyframe_points:
                            point.interpolation = "BEZIER"
                            point.handle_left_type = "AUTO_CLAMPED"
                            point.handle_right_type = "AUTO_CLAMPED"
        actions[name] = action
        return action

    def idle_pose(frame):
        phase = math.tau * (frame - 1) / 60
        hips = armature.pose.bones["mixamorig:Hips"]
        spine = armature.pose.bones["mixamorig:Spine1"]
        set_bone_pose(hips, base_pose[hips.name],
                      location_offset=(0, 0.004 * math.sin(phase), 0),
                      angle=math.radians(0.35) * math.sin(phase))
        set_bone_pose(spine, base_pose[spine.name],
                      axis=(0, 1, 0),
                      angle=math.radians(0.7) * math.sin(phase))
        return {hips.name, spine.name}

    def walk_pose(frame):
        phase = math.tau * (frame - 1) / 32
        hips = armature.pose.bones["mixamorig:Hips"]
        set_bone_pose(hips, base_pose[hips.name],
                      location_offset=(0, 0.018 * (0.5 - 0.5 * math.cos(2 * phase)), 0))
        keyed = {hips.name}
        for side, side_phase in (("Left", phase), ("Right", phase + math.pi)):
            thigh = armature.pose.bones["mixamorig:" + side + "UpLeg"]
            shin = armature.pose.bones["mixamorig:" + side + "Leg"]
            foot = armature.pose.bones["mixamorig:" + side + "Foot"]
            set_bone_pose(thigh, base_pose[thigh.name],
                          angle=math.radians(22) * math.sin(side_phase))
            set_bone_pose(shin, base_pose[shin.name],
                          angle=math.radians(24) * max(0, math.sin(side_phase)))
            set_bone_pose(foot, base_pose[foot.name],
                          angle=-math.radians(10) * math.sin(side_phase))
            keyed.update((thigh.name, shin.name, foot.name))
        return keyed

    def crouch_pose(frame):
        progress = min(1.0, max(0.0, (frame - 1) / 19))
        progress = progress * progress * (3 - 2 * progress)
        hips = armature.pose.bones["mixamorig:Hips"]
        spine = armature.pose.bones["mixamorig:Spine1"]
        set_bone_pose(hips, base_pose[hips.name],
                      location_offset=(0, -0.22 * progress, 0),
                      angle=math.radians(3) * progress)
        set_bone_pose(spine, base_pose[spine.name],
                      axis=(1, 0, 0), angle=math.radians(-5) * progress)
        keyed = {hips.name, spine.name}
        for side in ("Left", "Right"):
            thigh = armature.pose.bones["mixamorig:" + side + "UpLeg"]
            shin = armature.pose.bones["mixamorig:" + side + "Leg"]
            foot = armature.pose.bones["mixamorig:" + side + "Foot"]
            set_bone_pose(thigh, base_pose[thigh.name],
                          angle=math.radians(-18) * progress)
            set_bone_pose(shin, base_pose[shin.name],
                          angle=math.radians(42) * progress)
            set_bone_pose(foot, base_pose[foot.name],
                          angle=-math.radians(22) * progress)
            keyed.update((thigh.name, shin.name, foot.name))
        return keyed

    for action_name, frames, pose_function in (
            (CLIPS[0], idle_frames, idle_pose),
            (CLIPS[1], walk_frames, walk_pose),
            (CLIPS[2], crouch_frames, crouch_pose)):
        target_actions[action_name] = {}
        for side, base_location in (("Left", left_base_foot),
                                    ("Right", right_base_foot)):
            samples = []
            for frame in frames:
                if action_name == CLIPS[1]:
                    phase = math.tau * (frame - 1) / 32
                    side_phase = phase if side == "Left" else phase + math.pi
                    stride = -0.095 * math.cos(side_phase)
                    lift = 0.075 * max(0, math.sin(side_phase))
                    location = base_location + Vector((0, stride, lift))
                else:
                    location = base_location.copy()
                samples.append((frame, location))
            target_action = make_target_action(
                foot_targets[side], action_name + "_" + side + "FootTarget",
                samples)
            target_actions[action_name][foot_targets[side]] = target_action
        action = build_clip(action_name, frames, pose_function)
        bake_pose_action(scene, armature, frames[0], frames[-1])
        set_clip_action(armature, reference)
        scene.frame_set(1)
        bpy.context.view_layer.update()

    for constraint in list(armature.pose.bones["mixamorig:LeftForeArm"].constraints):
        if constraint.name == "Inspection_BakedIK":
            armature.pose.bones["mixamorig:LeftForeArm"].constraints.remove(
                constraint)
    for side in ("Left", "Right"):
        for pose_bone in (armature.pose.bones["mixamorig:" + side + "Leg"],
                          armature.pose.bones["mixamorig:" + side + "Foot"]):
            for constraint in list(pose_bone.constraints):
                if constraint.name in {"Inspection_BakedIK",
                                       "Inspection_BakedFootRotation"}:
                    pose_bone.constraints.remove(constraint)
    scene.frame_start = 1
    scene.frame_end = max(
        int(action.frame_range[1]) for action in actions.values())
    set_clip_action(armature, actions[CLIPS[0]])
    bpy.context.view_layer.update()
    original_children_after = sorted(obj.name for obj in scene.objects
                                     if obj.parent == weapon)
    hierarchy_preserved = set(original_children).issubset(original_children_after) and all(
        bpy.data.objects[name].parent == weapon for name in original_children)
    triangles = evaluated_triangles(meshes)
    metrics, frame_layout = pose_metrics(
        scene, armature, body, weapon,
        {"RightGrip": right_grip, "LeftGrip": left_grip,
         "LeftFoot": foot_targets["Left"],
         "RightFoot": foot_targets["Right"]}, actions, target_actions)
    temporary = [left_pole] + \
        list(foot_targets.values()) + list(foot_poles.values())
    temporary_actions = {
        obj.animation_data.action for obj in temporary
        if obj.animation_data and obj.animation_data.action}
    for obj in temporary:
        bpy.data.objects.remove(obj, do_unlink=True)
    for action in temporary_actions:
        if action.users == 0:
            bpy.data.actions.remove(action)

    camera = bpy.data.objects.get("Inspection_gameplay_angle")
    if camera is None:
        camera = bpy.data.objects.get("Inspection_three_quarter")
    contact_path = PREVIEW_DIR / "swat_operator_animation_contact_sheet.png"
    contact_layout = create_contact_sheet(
        scene, armature, actions, frame_layout, camera, contact_path)

    right_hand_before = armature.animation_data.action
    set_clip_action(armature, actions[CLIPS[2]])
    scene.frame_set(int(actions[CLIPS[2]].frame_range[1]))
    crouch_hips_z = (armature.matrix_world @
                     armature.pose.bones["mixamorig:Hips"].matrix).translation.z
    set_clip_action(armature, actions[CLIPS[0]])
    scene.frame_set(int(actions[CLIPS[0]].frame_range[0]))
    idle_hips_z = (armature.matrix_world @
                   armature.pose.bones["mixamorig:Hips"].matrix).translation.z
    crouch_drop = idle_hips_z - crouch_hips_z
    set_clip_action(armature, right_hand_before)

    export_path = WORK_DIR / "SwatOperatorRemastered_GameReady.fbx"
    asset_objects = [obj for obj in scene.objects
                     if obj.type in {"MESH", "ARMATURE", "EMPTY"}
                     and not obj.name.startswith("TEMP_")]
    exported = export_fbx(scene, armature, asset_objects, actions, export_path)
    round_trip = fbx_round_trip(export_path, len(meshes), len(armature.data.bones)) if exported else {
        "status": "failed", "error": "FBX file was not produced"}

    working_blend = WORK_DIR / "SwatOperatorRemastered_GameReady.blend"
    scene.frame_set(1)
    bpy.ops.wm.save_as_mainfile(filepath=str(working_blend))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(working_blend))
    image_paths = [{"image": image.name, "path": image.filepath,
                    "relative": image.filepath.startswith("//"),
                    "resolves": Path(bpy.path.abspath(image.filepath)).is_file()}
                   for image in bpy.data.images if image.source == "FILE"]

    tests = {
        "reference_static_action_preserved": reference.name == "Reference_Imported_Static",
        "weapon_world_transform_preserved_on_attachment": weapon_matrix_preserved,
        "weapon_child_hierarchy_preserved": hierarchy_preserved,
        "weapon_follows_right_hand": socket_motion > 0.01,
        "relative_texture_paths_resolve": bool(image_paths) and all(
            item["relative"] and item["resolves"] for item in image_paths),
        "clip_actions_have_distinct_motion": all(
            result["frame_count_evaluated"] > 3 and
            result["hips_vertical_excursion_m"] > 0.001
            for result in metrics.values()),
        "crouch_pelvis_lowered": crouch_drop > 0.15,
        "fbx_export_created": exported,
        "fbx_round_trip": round_trip["status"] == "passed",
    }
    limits = {
        "right_hand_stock_error_m": 0.10,
        "left_hand_foregrip_error_m": 0.05,
        "foot_target_error_m": 0.015,
        "crouch_pelvis_drop_m": 0.15,
        "minimum_limb_length_ratio": 0.65,
        "maximum_limb_length_ratio": 1.35,
    }
    for name, result in metrics.items():
        result["checks"] = {
            "right_hand_stock_grip": result["max_right_hand_stock_error_m"] <=
            limits["right_hand_stock_error_m"],
            "left_hand_foregrip": result["max_left_hand_foregrip_error_m"] <=
            limits["left_hand_foregrip_error_m"],
            "feet_near_floor": result["minimum_foot_sole_z_m"] is not None and
            -0.015 <= result["minimum_foot_sole_z_m"] <= 0.04,
            "limb_lengths_not_collapsed": (
                result["minimum_limb_length_ratio"] >=
                limits["minimum_limb_length_ratio"] and
                result["maximum_limb_length_ratio"] <=
                limits["maximum_limb_length_ratio"]),
        }
    observed_passes = [name for name, passed in tests.items() if passed]
    observed_failures = [name for name, passed in tests.items() if not passed]
    untested = [
        "Unity rig/avatar and material import (Unity editor not found)",
        "Human gameplay acceptance and in-engine retargeting",
        "Full geometric self-intersection/clipping beyond rendered sample views",
    ]
    output_report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
    output_report["game_ready_working_copy"] = {
        "working_blend": str(working_blend),
        "unity_fbx": str(export_path),
        "preserved_reference_action": reference.name,
        "generated_clips": {
            name: {"frame_range": list(actions[name].frame_range),
                   "duration_seconds": (actions[name].frame_range[1] -
                                        actions[name].frame_range[0]) /
                   (scene.render.fps / scene.render.fps_base),
                   "keyframe_points": sum(
                       len(curve.keyframe_points)
                       for layer in actions[name].layers
                       for strip in layer.strips
                       for slot in actions[name].slots
                       for curve in (strip.channelbag(slot).fcurves
                                     if strip.channelbag(slot) else ()))}
            for name in CLIPS
        },
        "socket_checks": {
            "weapon_matrix_max_error_on_attach": 0.0 if weapon_matrix_preserved else None,
            "weapon_translation_followed_right_hand_m": socket_motion,
            "weapon_children_before": original_children,
            "weapon_children_after": original_children_after,
            "right_hand_grip_target": right_grip.name,
            "left_hand_grip_target": left_grip.name,
            "muzzle_socket": muzzle.name,
        },
        "crouch_pelvis_drop_m": crouch_drop,
        "evaluated_triangle_count": triangles,
        "clip_pose_checks": metrics,
        "animation_contact_sheet": str(contact_path),
        "contact_sheet_layout": contact_layout,
        "fbx_round_trip": round_trip,
        "texture_paths": image_paths,
        "limits": limits,
        "observed_passes": observed_passes,
        "observed_failures": observed_failures,
        "untested": untested,
        "unity_validation": {"status": "not_run",
                             "reason": "No Unity editor executable found."},
        "rendered_pose_review": {
            "status": "pending visual review",
            "frames_rendered": contact_layout,
            "keyframe_names_not_used_as_quality_evidence": True,
        },
    }
    REPORT_PATH.write_text(json.dumps(
        output_report, indent=2), encoding="utf-8")
    print("SWAT_GAME_READY_WORKING_COPY_OK")
    print(json.dumps(output_report["game_ready_working_copy"], indent=2))


if __name__ == "__main__":
    main()
