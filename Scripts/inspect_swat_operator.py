"""Import and inspect the downloaded SWAT Operator Remastered FBX without altering its mesh or rig."""
import argparse
import json
import math
from pathlib import Path
import sys

import bpy
from mathutils import Vector


def image_node(nodes, links, material, principled, texture_dir, filename,
               color_space, socket_name):
    path = texture_dir / filename
    if not path.is_file():
        material["missing_texture_" + socket_name] = filename
        return None
    image = bpy.data.images.load(str(path), check_existing=True)
    image.colorspace_settings.name = color_space
    node = nodes.new("ShaderNodeTexImage")
    node.image = image
    node.label = filename
    node.location = (-600, -180 * len(nodes))
    return node


def reconnect_material(material, texture_dir, missing_textures):
    name = material.name.lower()
    if "body" in name:
        kind = "Body"
        maps = {
            "Base Color": ("Body_Base_color.png", "sRGB"),
            "Ambient Occlusion": ("Body_Mixed_AO.png", "Non-Color"),
            "Normal": ("Body_Normal_OpenGL.png", "Non-Color"),
            "Roughness": ("Body_Roughness.png", "Non-Color"),
        }
    elif "headgear" in name or "head_gear" in name:
        kind = "HeadGear"
        maps = {
            "Base Color": ("HeadGear_Base_color.png", "sRGB"),
            "Ambient Occlusion": ("HeadGear_Mixed_AO.png", "Non-Color"),
            "Normal": ("HeadGear_Normal_OpenGL.png", "Non-Color"),
            "Roughness": ("HeadGear_Roughness.png", "Non-Color"),
            "Metallic": ("HeadGear_Metallic.png", "Non-Color"),
            "Emission Color": ("HeadGear_Emissive.png", "sRGB"),
            "Subsurface Weight": ("HeadGear_SSS.png", "Non-Color"),
        }
    elif "eyelash" in name:
        kind = "Eyelashes"
        maps = {"Base Color": ("eyelashes01.png", "sRGB")}
    elif "ksvr" in name:
        kind = "KSVR"
        maps = {
            "Base Color": ("KSVR_Base_color.png", "sRGB"),
            "Ambient Occlusion": ("KSVR_Mixed_AO.png", "Non-Color"),
            "Normal": ("KSVR_Normal_OpenGL.png", "Non-Color"),
            "Roughness": ("KSVR_Roughness.png", "Non-Color"),
            "Emission Color": ("KSVR_Emissive.png", "sRGB"),
        }
    else:
        return None

    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    output = nodes.new("ShaderNodeOutputMaterial")
    output.location = (300, 0)
    principled = nodes.new("ShaderNodeBsdfPrincipled")
    principled.location = (40, 0)
    material.node_tree.links.new(
        principled.outputs["BSDF"], output.inputs["Surface"])
    links = material.node_tree.links
    loaded = {}

    for socket_name, (filename, color_space) in maps.items():
        image = image_node(nodes, links, material, principled, texture_dir,
                           filename, color_space, socket_name)
        if image is None:
            missing_textures.append(
                {"material": material.name, "file": filename})
            continue
        loaded[socket_name] = image

    base = loaded.get("Base Color")
    ao = loaded.get("Ambient Occlusion")
    if base:
        color_output = base.outputs["Color"]
        if ao:
            multiply = nodes.new("ShaderNodeMixRGB")
            multiply.blend_type = "MULTIPLY"
            multiply.inputs["Fac"].default_value = 1.0
            multiply.location = (-180, 80)
            links.new(color_output, multiply.inputs["Color1"])
            links.new(ao.outputs["Color"], multiply.inputs["Color2"])
            color_output = multiply.outputs["Color"]
        links.new(color_output, principled.inputs["Base Color"])
        if base.image.channels == 4 and "Alpha" in principled.inputs:
            links.new(base.outputs["Alpha"], principled.inputs["Alpha"])
            try:
                material.surface_render_method = "DITHERED"
            except (AttributeError, TypeError, ValueError):
                pass

    for socket_name in ("Roughness", "Metallic", "Emission Color", "Subsurface Weight"):
        image = loaded.get(socket_name)
        if image and socket_name in principled.inputs:
            links.new(image.outputs["Color"], principled.inputs[socket_name])

    normal = loaded.get("Normal")
    if normal:
        normal_map = nodes.new("ShaderNodeNormalMap")
        normal_map.location = (-180, -280)
        links.new(normal.outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], principled.inputs["Normal"])

    return kind


def object_bounds(objects):
    corners = [obj.matrix_world @ Vector(corner)
               for obj in objects if obj.type == "MESH" for corner in obj.bound_box]
    if not corners:
        return None
    minimum = Vector(tuple(min(point[i]
                     for point in corners) for i in range(3)))
    maximum = Vector(tuple(max(point[i]
                     for point in corners) for i in range(3)))
    return {"min": list(minimum), "max": list(maximum),
            "dimensions": list(maximum - minimum),
            "center": list((maximum + minimum) / 2), "corners": corners}


def skin_report(meshes, scene):
    report = []
    saved_frame = scene.frame_current
    for mesh in meshes:
        modifiers = [modifier for modifier in mesh.modifiers
                     if modifier.type == "ARMATURE"]
        if not modifiers:
            continue
        weighted_vertices = sum(bool(vertex.groups)
                                for vertex in mesh.data.vertices)
        armatures = list({modifier.object for modifier in modifiers
                          if modifier.object})
        pose_positions = {armature: armature.data.pose_position
                          for armature in armatures}

        def evaluated_world_vertices():
            evaluated = mesh.evaluated_get(
                bpy.context.evaluated_depsgraph_get())
            evaluated_mesh = evaluated.to_mesh()
            try:
                return [evaluated.matrix_world @ vertex.co
                        for vertex in evaluated_mesh.vertices]
            finally:
                evaluated.to_mesh_clear()

        try:
            for armature in armatures:
                armature.data.pose_position = "REST"
            scene.frame_set(saved_frame)
            bpy.context.view_layer.update()
            rest_vertices = evaluated_world_vertices()
            for armature in armatures:
                armature.data.pose_position = "POSE"
            scene.frame_set(saved_frame)
            bpy.context.view_layer.update()
            posed_vertices = evaluated_world_vertices()
            displacements = [a - b for a,
                             b in zip(rest_vertices, posed_vertices)]
            max_displacement = max(
                (delta.length for delta in displacements), default=0.0)
            changed_vertices = sum(
                delta.length > 1e-5 for delta in displacements)
            finite_vertices = all(math.isfinite(value)
                                  for point in posed_vertices for value in point)
        finally:
            for armature, pose_position in pose_positions.items():
                armature.data.pose_position = pose_position
            scene.frame_set(saved_frame)
            bpy.context.view_layer.update()

        report.append({
            "object": mesh.name,
            "vertices": len(mesh.data.vertices),
            "vertex_groups": len(mesh.vertex_groups),
            "weighted_vertices": weighted_vertices,
            "unweighted_vertices": len(mesh.data.vertices) - weighted_vertices,
            "armature_modifiers": [modifier.object.name if modifier.object else None
                                   for modifier in modifiers],
            "pose_vs_rest_max_vertex_displacement_m": max_displacement,
            "pose_vs_rest_changed_vertices_at_1e-5m": changed_vertices,
            "evaluated_vertices_finite": finite_vertices,
        })
    return report


def action_curves(action):
    if hasattr(action, "fcurves"):
        return list(action.fcurves)
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for slot in action.slots:
                channelbag = strip.channelbag(slot)
                if channelbag:
                    curves.extend(channelbag.fcurves)
    return curves


def animation_report(scene, armatures):
    fps = scene.render.fps / scene.render.fps_base
    saved_frame = scene.frame_current
    saved_actions = {armature: (armature.animation_data.action
                                if armature.animation_data else None)
                     for armature in armatures}
    saved_tracks = {armature: [(track, track.mute)
                               for track in armature.animation_data.nla_tracks]
                    for armature in armatures if armature.animation_data}
    report = []
    for action in bpy.data.actions:
        start, end = map(float, action.frame_range)
        curves = action_curves(action)
        entry = {
            "name": action.name,
            "frame_start": start,
            "frame_end": end,
            "duration_seconds": max(0.0, end - start) / fps,
            "keyframe_points": sum(len(curve.keyframe_points) for curve in curves),
            "channels": len(curves),
        }
        motion_translation = 0.0
        motion_rotation_radians = 0.0
        sampled = False
        sampled_poses = []
        for armature in armatures:
            if not armature.animation_data:
                armature.animation_data_create()
            armature.animation_data.action = action
            if len(action.slots):
                armature.animation_data.action_slot = action.slots[0]
            for track in armature.animation_data.nla_tracks:
                track.mute = True
        sample_frames = sorted({start, (start + end) / 2, end})
        for frame in sample_frames:
            whole = math.floor(frame)
            scene.frame_set(whole, subframe=frame - whole)
            frame_poses = {}
            for armature in armatures:
                for pose_bone in armature.pose.bones:
                    rest = pose_bone.bone.matrix_local
                    delta = rest.inverted() @ pose_bone.matrix
                    frame_poses[(armature.name, pose_bone.name)
                                ] = pose_bone.matrix.copy()
                    motion_translation = max(motion_translation,
                                             delta.translation.length)
                    motion_rotation_radians = max(
                        motion_rotation_radians, delta.to_quaternion().angle)
                    sampled = True
            sampled_poses.append(frame_poses)
        interval_translation = 0.0
        interval_rotation_radians = 0.0
        for previous, current in zip(sampled_poses, sampled_poses[1:]):
            for key in previous.keys() & current.keys():
                delta = previous[key].inverted() @ current[key]
                interval_translation = max(
                    interval_translation, delta.translation.length)
                interval_rotation_radians = max(
                    interval_rotation_radians, delta.to_quaternion().angle)
        entry["sampled_max_pose_offset_from_rest_m"] = motion_translation if sampled else None
        entry["sampled_max_pose_rotation_from_rest_degrees"] = (
            math.degrees(motion_rotation_radians) if sampled else None)
        entry["sampled_max_frame_to_frame_bone_translation_m"] = (
            interval_translation if len(sampled_poses) > 1 else None)
        entry["sampled_max_frame_to_frame_bone_rotation_degrees"] = (
            math.degrees(interval_rotation_radians) if len(sampled_poses) > 1 else None)
        if not curves:
            entry["motion_assessment"] = "No animation curves"
        elif not sampled:
            entry["motion_assessment"] = "Curves present; no armature available to sample"
        elif len(sampled_poses) < 2:
            entry["motion_assessment"] = "Only one distinct frame sampled"
        elif (interval_translation < 0.001 and
              interval_rotation_radians < math.radians(1)):
            entry["motion_assessment"] = (
                "Effectively static between sampled frames; keyed pose differs from rest")
        else:
            entry["motion_assessment"] = "Bone motion present between sampled frames"
        report.append(entry)
    for armature, action in saved_actions.items():
        if armature.animation_data:
            armature.animation_data.action = action
    for tracks in saved_tracks.values():
        for track, was_muted in tracks:
            track.mute = was_muted
    scene.frame_set(saved_frame)
    return report


def weapon_parenting(objects):
    candidates = [obj for obj in objects
                  if any(word in obj.name.lower()
                         for word in ("weapon", "rifle", "gun", "pistol", "ksvr"))
                  or any(slot.material and "ksvr" in slot.material.name.lower()
                         for slot in obj.material_slots)]
    return [{
        "object": obj.name,
        "parent": obj.parent.name if obj.parent else None,
        "parent_type": obj.parent_type,
        "parent_bone": obj.parent_bone or None,
        "armature_modifiers": [modifier.object.name if modifier.object else None
                               for modifier in obj.modifiers
                               if modifier.type == "ARMATURE"],
    } for obj in candidates]


def render_previews(scene, bounds, output_dir):
    inspection = bpy.data.collections.new("Inspection_Cameras_And_Lights")
    scene.collection.children.link(inspection)

    def add_light(name, location, energy, size):
        data = bpy.data.lights.new(name, "AREA")
        data.energy = energy
        data.shape = "DISK"
        data.size = size
        obj = bpy.data.objects.new(name, data)
        inspection.objects.link(obj)
        obj.location = location
        obj.rotation_euler = (Vector(bounds["center"]) - obj.location).to_track_quat(
            "-Z", "Y").to_euler()

    center = Vector(bounds["center"])
    height = max(bounds["dimensions"])
    add_light("Inspection_Key", center +
              Vector((3, -4, height * 0.75)), 1400, height * 0.9)
    add_light("Inspection_Fill", center +
              Vector((-4, -2, height * 0.35)), 850, height * 0.8)
    add_light("Inspection_Rim", center +
              Vector((1, 3, height * 0.7)), 1200, height * 0.75)

    world = scene.world or bpy.data.worlds.new("Inspection_Neutral_World")
    scene.world = world
    world.use_nodes = True
    background = world.node_tree.nodes.get("Background")
    background.inputs["Color"].default_value = (0.32, 0.32, 0.32, 1)
    background.inputs["Strength"].default_value = 0.65
    engines = {item.identifier for item in
               bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items}
    scene.render.engine = ("BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines
                           else "BLENDER_EEVEE")
    scene.render.resolution_x = 900
    scene.render.resolution_y = 1200
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.fps = 30
    scene.view_settings.view_transform = "AgX"
    aspect = scene.render.resolution_x / scene.render.resolution_y
    frame_corners = bounds["corners"]
    views = {
        "front": Vector((0, -1, 0)),
        "side": Vector((1, 0, 0)),
        "three_quarter": Vector((1, -1, 0)).normalized(),
    }
    rendered = []
    for name, direction in views.items():
        camera_data = bpy.data.cameras.new("Inspection_" + name)
        camera_data.type = "ORTHO"
        camera = bpy.data.objects.new("Inspection_" + name, camera_data)
        inspection.objects.link(camera)
        camera.location = center + direction * height * 2.5
        camera.rotation_euler = (
            center - camera.location).to_track_quat("-Z", "Y").to_euler()
        right = camera.rotation_euler.to_quaternion() @ Vector((1, 0, 0))
        up = camera.rotation_euler.to_quaternion() @ Vector((0, 1, 0))
        projected_width = max(abs((point - center).dot(right))
                              for point in frame_corners) * 2
        projected_height = max(abs((point - center).dot(up))
                               for point in frame_corners) * 2
        camera_data.ortho_scale = max(
            projected_width, projected_height * aspect) * 1.18
        scene.camera = camera
        destination = output_dir / ("swat_operator_" + name + ".png")
        scene.render.filepath = str(destination)
        bpy.ops.render.render(write_still=True)
        rendered.append(str(destination))
    return rendered


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path,
                        default=Path.home() / "Downloads" / "swat-operator-remastered" /
                        "source" / "swat lp.fbx")
    parser.add_argument("--textures", type=Path)
    parser.add_argument("--output", type=Path)
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    args = parser.parse_args(argv)
    source = args.source.expanduser().resolve()
    asset_root = source.parent.parent
    texture_dir = (args.textures or asset_root /
                   "textures").expanduser().resolve()
    output_dir = (args.output or asset_root /
                  "inspection").expanduser().resolve()
    preview_dir = output_dir / "previews"
    output_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)
    blend_path = output_dir / "swat_operator_remastered_inspection.blend"
    report_path = output_dir / "inspection_report.json"
    report = {
        "source_fbx": str(source),
        "texture_directory": str(texture_dir),
        "blend_file": str(blend_path),
        "previews": [],
        "missing_textures": [],
        "import_errors": [],
        "licence_attribution_files_found": [],
    }

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    try:
        if not source.is_file():
            raise FileNotFoundError(source)
        if not texture_dir.is_dir():
            raise FileNotFoundError(texture_dir)
        bpy.ops.import_scene.fbx(filepath=str(source))
    except Exception as error:
        report["import_errors"].append(f"{type(error).__name__}: {error}")
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise

    imported_objects = list(scene.objects)
    meshes = [obj for obj in imported_objects if obj.type == "MESH"]
    auxiliary_meshes = [mesh for mesh in meshes
                        if mesh.name == "Cube" and len(mesh.data.vertices) == 8]
    asset_meshes = [mesh for mesh in meshes if mesh not in auxiliary_meshes]
    armatures = [obj for obj in imported_objects if obj.type == "ARMATURE"]
    materials = [
        material for material in bpy.data.materials if material.users > 0]
    material_map = {}
    for material in materials:
        kind = reconnect_material(
            material, texture_dir, report["missing_textures"])
        if kind:
            material_map[kind] = material.name
    report["import"] = {
        "objects": len(imported_objects),
        "mesh_objects": len(meshes),
        "asset_mesh_objects_excluding_auxiliary": len(asset_meshes),
        "auxiliary_meshes_retained": [mesh.name for mesh in auxiliary_meshes],
        "materials": [material.name for material in materials],
        "mapped_materials": material_map,
        "unmapped_materials": [material.name for material in materials
                               if material.name not in material_map.values()],
        "armatures": [armature.name for armature in armatures],
        "mesh_vertex_counts": {mesh.name: len(mesh.data.vertices) for mesh in meshes},
    }

    bounds = object_bounds(asset_meshes)
    report["scale_bounds_meters"] = (
        {key: value for key, value in bounds.items() if key != "corners"} if bounds else None)
    report["skin_deformation_setup"] = skin_report(asset_meshes, scene)
    report["weapon_parenting"] = weapon_parenting(imported_objects)
    report["animation_stacks"] = animation_report(scene, armatures)
    report["licence_attribution_note"] = (
        "No licence, readme, or attribution files were included in the downloaded bundle. "
        "The original download is preserved and this inspection output remains local; "
        "do not publish the asset until its licence and attribution requirements are verified.")

    if bounds:
        for mesh in auxiliary_meshes:
            mesh.hide_render = True
        report["previews"] = render_previews(scene, bounds, preview_dir)
        for mesh in auxiliary_meshes:
            mesh.hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_as_mainfile(filepath=str(blend_path))
    report["texture_paths"] = [{
        "image": image.name,
        "path_in_blend": image.filepath,
        "relative": image.filepath.startswith("//"),
        "resolves": Path(bpy.path.abspath(image.filepath)).is_file(),
    } for image in bpy.data.images if image.source == "FILE"]
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("SWAT_OPERATOR_INSPECTION_OK")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
