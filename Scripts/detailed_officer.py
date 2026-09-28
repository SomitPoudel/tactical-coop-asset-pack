"""Independent detailed officer asset builder; leaves the quality sample intact."""
from __future__ import annotations

from array import array
import json
import math
from pathlib import Path

import bpy
from mathutils import Vector

import blender_asset_pack_common as common

ROOT = common.ROOT
DIRS = common.DIRS
HEIGHT = 1.84
LOD0 = "Char_Officer_Detailed"
RIG = "Rig_Officer_Detailed"


def _mat(name, color, roughness, metallic=0.0):
    material = bpy.data.materials.new(name)
    material.diffuse_color = (*color, 1)
    material.use_nodes = True
    shader = material.node_tree.nodes.get("Principled BSDF")
    shader.inputs["Base Color"].default_value = (*color, 1)
    shader.inputs["Roughness"].default_value = roughness
    shader.inputs["Metallic"].default_value = metallic
    return material


def _texture_set(folder, name, color, roughness, woven=False):
    folder.mkdir(parents=True, exist_ok=True)
    size = 256
    images = {}
    for kind in ("BaseColor", "Roughness", "Normal"):
        image = bpy.data.images.new(
            f"Officer_{name}_{kind}", size, size, alpha=True)
        pixels = array("f")
        for y in range(size):
            for x in range(size):
                wave = (math.sin(x * 1.73 + y * .17) *
                        math.sin(y * 1.61 + x * .11)) if woven else 0.0
                grain = (math.sin(x * 12.9898 + y * 78.233) * 43758.5453) % 1
                if kind == "BaseColor":
                    factor = .965 + .035 * wave + .025 * (grain - .5)
                    pixels.extend((color[0] * factor, color[1] * factor,
                                   color[2] * factor, 1.0))
                elif kind == "Roughness":
                    value = max(0.0, min(1.0, roughness + .025 * wave))
                    pixels.extend((value, value, value, 1.0))
                else:
                    nx = .5 + .018 * math.sin(x * 1.73) if woven else .5
                    ny = .5 + .018 * math.sin(y * 1.61) if woven else .5
                    pixels.extend((nx, ny, .999, 1.0))
        image.pixels.foreach_set(pixels)
        image.file_format = "PNG"
        image.filepath_raw = str(folder / f"{name}_{kind}.png")
        image.save()
        images[kind] = image
    return images


def _pbr_material(name, color, roughness, folder, woven=False, metallic=0.0):
    material = _mat(name, color, roughness, metallic)
    images = _texture_set(folder, name.replace("MAT_", ""), color,
                          roughness, woven)
    nodes = material.node_tree.nodes
    shader = nodes.get("Principled BSDF")
    for kind, socket in (("BaseColor", "Base Color"),
                         ("Roughness", "Roughness"), ("Normal", "Normal")):
        texture = nodes.new("ShaderNodeTexImage")
        texture.image = images[kind]
        texture.label = f"{kind} texture"
        if kind == "Normal":
            normal = nodes.new("ShaderNodeNormalMap")
            material.node_tree.links.new(
                texture.outputs["Color"], normal.inputs["Color"])
            material.node_tree.links.new(
                normal.outputs["Normal"], shader.inputs[socket])
        else:
            material.node_tree.links.new(
                texture.outputs["Color"], shader.inputs[socket])
    return material


def _uv(obj):
    if obj.type != "MESH" or obj.data.uv_layers:
        return
    layer = obj.data.uv_layers.new(name="UVMap")
    for loop in obj.data.loops:
        point = obj.data.vertices[loop.vertex_index].co
        layer.data[loop.index].uv = (point.x * 2 + .5, point.z / HEIGHT)


def _mesh(name, vertices, faces, material, collection, arm=None,
          weight_rows=None, bone=None, bevel=0.0):
    data = bpy.data.meshes.new(name + "_Mesh")
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(name, data)
    collection.objects.link(obj)
    if material:
        obj.data.materials.append(material)
    _uv(obj)
    if bone:
        world = obj.matrix_world.copy()
        obj.parent = arm
        obj.parent_type = "BONE"
        obj.parent_bone = bone
        obj.matrix_world = world
    elif arm:
        obj.parent = arm
        obj.modifiers.new("Armature_Deform", "ARMATURE").object = arm
        if weight_rows:
            names = {key for row in weight_rows for key in row}
            groups = {key: obj.vertex_groups.new(name=key) for key in names}
            for index, row in enumerate(weight_rows):
                for group_name, weight in row.items():
                    if weight > 1e-5:
                        groups[group_name].add([index], weight, "REPLACE")
    if bevel:
        modifier = obj.modifiers.new("Tailored_Edge_Radius", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def _ring_surface(name, profiles, material, collection, arm, weight_fn,
                  sides=24, center_y=0.0, eye_opening=False):
    vertices, faces, weights = [], [], []
    for z, width, depth, offset_y in profiles:
        for i in range(sides):
            angle = math.tau * i / sides
            point = (math.cos(angle) * width,
                     center_y + offset_y + math.sin(angle) * depth, z)
            vertices.append(point)
            weights.append(weight_fn(z, point))
    for row in range(len(profiles) - 1):
        for i in range(sides):
            a = row * sides + i
            b = row * sides + (i + 1) % sides
            if eye_opening:
                points = (Vector(vertices[a]), Vector(vertices[b]),
                          Vector(vertices[b + sides]), Vector(vertices[a + sides]))
                center = sum(points, Vector()) / 4
                if (1.66 <= center.z <= 1.70 and center.y < -.06 and
                        abs(center.x) < .08):
                    continue
            faces.append((a, b, b + sides, a + sides))
    faces.extend((tuple(reversed(range(sides))),
                  tuple(range((len(profiles) - 1) * sides,
                              len(profiles) * sides))))
    return _mesh(name, vertices, faces, material, collection, arm, weights)


def _loft(name, start, end, profiles, material, collection, arm,
          bone, neighbor=None, center_offset=(0, 0), sides=16):
    start, end = Vector(start), Vector(end)
    axis = (end - start).normalized()
    side = Vector((1, 0, 0)) - axis * axis.dot(Vector((1, 0, 0)))
    if side.length < .1:
        side = Vector((0, 1, 0)) - axis * axis.dot(Vector((0, 1, 0)))
    side.normalize()
    depth = axis.cross(side).normalized()
    vertices, faces, weights = [], [], []
    for t, radius_x, radius_y in profiles:
        center = start.lerp(end, t) + \
            Vector((center_offset[0], center_offset[1], 0))
        for index in range(sides):
            angle = math.tau * index / sides
            point = center + side * \
                (math.cos(angle) * radius_x) + \
                depth * (math.sin(angle) * radius_y)
            vertices.append(tuple(point))
            blend = max(0.0, 1.0 - abs(t - .5) *
                        3.5) * .22 if neighbor else 0.0
            weights.append(
                {bone: 1.0 - blend, **({neighbor: blend} if neighbor else {})})
    for row in range(len(profiles) - 1):
        for index in range(sides):
            a = row * sides + index
            b = row * sides + (index + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.extend((tuple(reversed(range(sides))),
                  tuple(range((len(profiles) - 1) * sides,
                              len(profiles) * sides))))
    return _mesh(name, vertices, faces, material, collection, arm, weights)


def _box(name, location, dimensions, material, collection, arm=None,
         bone=None, bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    obj = bpy.context.object
    obj.name = name
    obj.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    for owner in list(obj.users_collection):
        owner.objects.unlink(obj)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    _uv(obj)
    if bone:
        matrix = obj.matrix_world.copy()
        obj.parent = arm
        obj.parent_type = "BONE"
        obj.parent_bone = bone
        obj.matrix_world = matrix
    if bevel:
        modifier = obj.modifiers.new("Soft_Garment_Edge", "BEVEL")
        modifier.width = bevel
        modifier.segments = 2
    return obj


def _rounded_panel(name, x_values, z_values, material, collection, arm,
                   bone, back=False):
    vertices, faces = [], []
    for row, z in enumerate(z_values):
        for column, x in enumerate(x_values):
            width = .24 if row in (1, 2, 3) else .21
            depth = .145 * math.sqrt(max(.15, 1 - (x / width) ** 2))
            y = depth + .018 if back else -depth - .018
            vertices.append((x, y, z))
    rows, columns = len(z_values), len(x_values)
    for row in range(rows - 1):
        for column in range(columns - 1):
            a = row * columns + column
            faces.append((a, a + 1, a + columns + 1, a + columns))
    obj = _mesh(name, vertices, faces, material, collection, arm, bone=bone)
    solidify = obj.modifiers.new("Rigid_Plate_Thickness", "SOLIDIFY")
    solidify.thickness = .018
    edge = obj.modifiers.new("Plate_Edge_Radius", "BEVEL")
    edge.width = .012
    edge.segments = 2
    return obj


def _build_rig(collection):
    bpy.ops.object.armature_add(enter_editmode=True)
    arm = bpy.context.object
    arm.name = RIG
    arm.data.name = RIG + "_Data"
    edit = arm.data.edit_bones
    for old in list(edit):
        edit.remove(old)
    specs = {
        "root": ((0, 0, 0), (0, 0, .12), None),
        "pelvis": ((0, 0, .88), (0, 0, 1.02), "root"),
        "spine_01": ((0, 0, 1.02), (0, 0, 1.24), "pelvis"),
        "spine_02": ((0, 0, 1.24), (0, 0, 1.45), "spine_01"),
        "neck": ((0, 0, 1.45), (0, 0, 1.57), "spine_02"),
        "head": ((0, 0, 1.57), (0, 0, 1.76), "neck"),
    }
    for side, sign in (("L", -1), ("R", 1)):
        specs.update({
            f"clavicle.{side}": ((sign * .06, 0, 1.43), (sign * .23, 0, 1.42), "spine_02"),
            f"upper_arm.{side}": ((sign * .23, 0, 1.42), (sign * .45, -.01, 1.32), f"clavicle.{side}"),
            f"forearm.{side}": ((sign * .45, -.01, 1.32), (sign * .62, -.035, 1.22), f"upper_arm.{side}"),
            f"hand.{side}": ((sign * .62, -.035, 1.22), (sign * .68, -.075, 1.20), f"forearm.{side}"),
            f"thigh.{side}": ((sign * .105, 0, .91), (sign * .12, 0, .50), "pelvis"),
            f"shin.{side}": ((sign * .12, 0, .50), (sign * .12, 0, .12), f"thigh.{side}"),
            f"foot.{side}": ((sign * .12, 0, .12), (sign * .12, -.22, .075), f"shin.{side}"),
        })
        finger_roots = [(-.045, "index"), (-.015, "middle"),
                        (.015, "ring"), (.043, "little")]
        for offset, finger in finger_roots:
            previous = f"hand.{side}"
            for segment in range(1, 4):
                bone = f"{finger}_{segment}.{side}"
                z0 = 1.20 - .03 * segment
                z1 = z0 - .025
                x0 = sign * (.65 + offset)
                x1 = sign * (.67 + offset)
                specs[bone] = ((x0, -.09, z0), (x1, -.095, z1), previous)
                previous = bone
        specs[f"thumb_1.{side}"] = (
            (sign * .64, -.06, 1.205), (sign * .655, -.10, 1.17), f"hand.{side}")
        specs[f"thumb_2.{side}"] = (
            (sign * .655, -.10, 1.17), (sign * .67, -.11, 1.145), f"thumb_1.{side}")
        specs[f"CTRL_Foot.{side}"] = (
            (sign * .12, 0, .12), (sign * .12, -.12, .12), "root")
        specs[f"CTRL_KneePole.{side}"] = (
            (sign * .12, -.48, .50), (sign * .12, -.48, .62), "root")
        specs[f"CTRL_Hand.{side}"] = (
            (sign * .62, -.035, 1.22), (sign * .62, -.15, 1.22), "root")
        specs[f"CTRL_ElbowPole.{side}"] = (
            (sign * .45, -.42, 1.32), (sign * .45, -.42, 1.44), "root")
    bones = {}
    for name, (head, tail, parent) in specs.items():
        bone = edit.new(name)
        bone.head, bone.tail = head, tail
        bones[name] = bone
        if name.startswith("CTRL_"):
            bone.use_deform = False
        if parent:
            bone.parent = bones[parent]
            bone.use_connect = (
                Vector(head) - Vector(bones[parent].tail)).length < .001
    bpy.ops.object.mode_set(mode="OBJECT")
    arm.show_in_front = True
    arm.data.display_type = "BBONE"
    for side in ("L", "R"):
        leg_ik = arm.pose.bones[f"shin.{side}"].constraints.new("IK")
        leg_ik.name = f"IK_Foot.{side}"
        leg_ik.target = arm
        leg_ik.subtarget = f"CTRL_Foot.{side}"
        leg_ik.pole_target = arm
        leg_ik.pole_subtarget = f"CTRL_KneePole.{side}"
        leg_ik.chain_count = 2
        leg_ik.use_stretch = False
        arm_ik = arm.pose.bones[f"forearm.{side}"].constraints.new("IK")
        arm_ik.name = f"IK_Hand.{side}"
        arm_ik.target = arm
        arm_ik.subtarget = f"CTRL_Hand.{side}"
        arm_ik.pole_target = arm
        arm_ik.pole_subtarget = f"CTRL_ElbowPole.{side}"
        arm_ik.chain_count = 2
        arm_ik.use_stretch = False
    for owner in list(arm.users_collection):
        owner.objects.unlink(arm)
    collection.objects.link(arm)
    return arm


def _face(geometry, collection, material, arm, bone="head"):
    vertices, faces = [], []
    center = Vector((0, -.005, 1.675))
    rings = ((-.11, .075, .085), (-.08, .105, .09), (-.03, .118, .095),
             (.035, .12, .10), (.09, .105, .09), (.13, .07, .065))
    sides = 32
    for dz, rx, ry in rings:
        for i in range(sides):
            angle = math.tau * i / sides
            vertices.append((center.x + math.cos(angle) * rx,
                             center.y + math.sin(angle) * ry,
                             center.z + dz))
    for row in range(len(rings) - 1):
        for i in range(sides):
            a = row * sides + i
            b = row * sides + (i + 1) % sides
            faces.append((a, b, b + sides, a + sides))
    faces.extend((tuple(reversed(range(sides))),
                  tuple(range((len(rings) - 1) * sides, len(rings) * sides))))
    return _mesh("Officer_Facial_Base", vertices, faces, material, collection,
                 arm, bone=bone)


def _helmet(collection, arm, helmet, rubber, cloth):
    _ring_surface("Officer_Helmet_Shell", (
        (1.725, .11, .12, -.005), (1.745, .145, .15, 0),
        (1.79, .155, .16, .008), (1.825, .13, .14, .012),
        (1.84, .07, .08, .012)), helmet, collection, arm,
        lambda z, p: {"head": 1.0}, sides=24, center_y=0)
    _box("Officer_Helmet_Rim", (0, -.01, 1.735), (.30, .29, .024), rubber,
         collection, arm, "head", .01)
    for side, sign in (("L", -1), ("R", 1)):
        bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=.047, depth=.055,
                                            location=(
                                                sign * .145, -.005, 1.665),
                                            rotation=(0, math.pi / 2, 0))
        cup = bpy.context.object
        cup.name = f"Officer_Headset_Earcup.{side}"
        for owner in list(cup.users_collection):
            owner.objects.unlink(cup)
        collection.objects.link(cup)
        cup.data.materials.append(helmet)
        cup.parent = arm
        cup.parent_type = "BONE"
        cup.parent_bone = "head"
        _box(f"Officer_ChinStrap.{side}", (sign * .095, -.06, 1.61),
             (.018, .022, .11), cloth, collection, arm, "head", .006)
    _loft("Officer_Headset_Microphone", (.13, -.12, 1.64), (.055, -.16, 1.61),
          ((0, .009, .009), (.5, .008, .008), (1, .007, .007)), rubber,
          collection, arm, "head", sides=8)


def _glove_hand(collection, arm, side, rubber, cloth, equipment):
    sign = -1 if side == "L" else 1
    palm = _box(f"Officer_Glove_Palm.{side}", (sign * .645, -.065, 1.195),
                (.095, .105, .075), rubber, collection, arm, "hand." + side, .025)
    palm["anatomy"] = "palm with articulated digits"
    for offset, finger in ((-.045, "index"), (-.015, "middle"),
                           (.015, "ring"), (.043, "little")):
        for segment in range(1, 4):
            z0 = 1.18 - .03 * (segment - 1)
            z1 = z0 - .027
            x0 = sign * (.65 + offset + .006 * segment)
            x1 = sign * (.67 + offset + .006 * segment)
            _loft(f"Officer_Glove_{finger}_{segment}.{side}",
                  (x0, -.10, z0), (x1, -.105, z1),
                  ((0, .012, .012), (.4, .011, .010), (1, .009, .009)),
                  rubber, collection, arm, f"{finger}_{segment}.{side}",
                  sides=8)
    for segment, (start, end) in enumerate((((.64, -.07, 1.205), (.655, -.105, 1.17)),
                                            ((.655, -.105, 1.17), (.67, -.11, 1.145))), 1):
        _loft(f"Officer_Glove_Thumb_{segment}.{side}", start, end,
              ((0, .018, .014), (.5, .015, .013), (1, .012, .011)),
              rubber, collection, arm, f"thumb_{segment}.{side}", sides=8)
    _box(f"Officer_Glove_Cuff.{side}", (sign * .62, -.025, 1.225),
         (.15, .11, .075), cloth, collection, arm, "forearm." + side, .014)
    _box(f"Officer_Glove_WristGuard.{side}", (sign * .62, -.09, 1.22),
         (.10, .018, .034), equipment, collection, arm, "hand." + side, .008)


def _build_clothes(collection, arm, materials):
    cloth, reinforced, trousers, rubber, armor, webbing, equipment = materials
    torso = ((.86, .18, .13, 0), (.90, .205, .145, 0),
             (.97, .19, .13, 0), (1.06, .185, .125, 0),
             (1.16, .215, .14, 0), (1.28, .235, .155, 0),
             (1.38, .255, .145, 0), (1.45, .235, .125, 0),
             (1.49, .14, .105, 0))

    def torso_weights(z, _):
        if z < 1.0:
            return {"pelvis": .65, "spine_01": .35}
        if z < 1.25:
            blend = (z - 1.0) / .25
            return {"spine_01": 1 - blend * .35, "spine_02": blend * .35}
        return {"spine_02": 1.0}
    _ring_surface("Officer_Combat_Shirt_Body", torso, cloth, collection, arm,
                  torso_weights, sides=32)
    _ring_surface("Officer_Cargo_Trousers_Waistband", (
        (.89, .195, .142, 0), (.91, .205, .15, 0), (.955, .202, .15, 0),
        (.975, .19, .14, 0)), webbing, collection, arm,
        lambda z, p: {"pelvis": 1.0}, sides=32)
    _box("Officer_Trouser_Fly_Closure", (0, -.151, .855), (.035, .014, .19),
         reinforced, collection, arm, "pelvis", .006)
    for side, sign in (("L", -1), ("R", 1)):
        # Tailored multi-loop sleeves and trouser legs use quad lofts with shaped joint profiles.
        shoulder = (sign * .23, 0, 1.42)
        elbow = (sign * .45, -.01, 1.32)
        wrist = (sign * .62, -.035, 1.22)
        _loft(f"Officer_Combat_Shirt_Sleeve.{side}", shoulder, elbow,
              ((0, .115, .105), (.12, .122, .105), (.38, .104, .091),
               (.52, .096, .084), (.58, .105, .09), (.65, .092, .08),
               (.82, .084, .073), (.96, .082, .071), (1, .078, .068)),
              cloth, collection, arm, "upper_arm." + side, "forearm." + side)
        _loft(f"Officer_Combat_Shirt_Forearm.{side}", elbow, wrist,
              ((0, .079, .068), (.12, .09, .075), (.35, .083, .07),
               (.50, .075, .064), (.58, .083, .069), (.66, .072, .06),
               (.88, .068, .057), (1, .066, .056)), cloth, collection,
              arm, "forearm." + side)
        _loft(f"Officer_Shirt_Cuff.{side}",
              (sign * .60, -.032, 1.235), wrist,
              ((0, .074, .062), (.35, .079, .068),
               (.65, .079, .068), (1, .074, .062)), reinforced,
              collection, arm, "forearm." + side, sides=16)
        hip = (sign * .105, 0, .91)
        knee = (sign * .12, 0, .50)
        ankle = (sign * .12, 0, .13)
        _loft(f"Officer_Cargo_Trouser_Thigh.{side}", hip, knee,
              ((0, .132, .12), (.10, .145, .125), (.25, .137, .116),
               (.42, .116, .10), (.50, .11, .094), (.57, .118, .10),
               (.65, .105, .09), (.82, .094, .08), (.94, .083, .072),
               (1, .079, .068)), trousers, collection, arm,
              "thigh." + side, "shin." + side)
        _loft(f"Officer_Cargo_Trouser_Shin.{side}", knee, ankle,
              ((0, .084, .073), (.10, .093, .078), (.27, .088, .074),
               (.43, .079, .068), (.52, .086, .072), (.61, .077, .066),
               (.82, .071, .061), (.94, .069, .059), (1, .07, .06)),
              trousers, collection, arm, "shin." + side)
        _loft(f"Officer_Trouser_Cuff.{side}",
              (sign * .12, 0, .17), ankle,
              ((0, .073, .062), (.35, .079, .067),
               (.65, .079, .067), (1, .073, .062)), reinforced,
              collection, arm, "shin." + side, sides=16)
        for pocket_side, offset in (("Outer", sign * .13),):
            _box(f"Officer_Cargo_ThighPocket_{pocket_side}.{side}",
                 (offset, -.109, .70), (.13, .045, .18), trousers,
                 collection, arm, "thigh." + side, .012)
            _box(f"Officer_Cargo_PocketFlap.{side}",
                 (offset, -.136, .785), (.14, .018, .045), reinforced,
                 collection, arm, "thigh." + side, .008)
            for seam_x in (-.045, .045):
                _box(f"Officer_Cargo_PocketSeam.{side}",
                     (offset + seam_x, -.135, .70), (.004, .004, .14),
                     webbing, collection, arm, "thigh." + side, .001)
        _box(f"Officer_KneePad_RigidShell.{side}",
             (sign * .12, -.096, .50), (.17, .055, .15), rubber,
             collection, arm, "shin." + side, .045)
        _box(f"Officer_KneePad_Face.{side}",
             (sign * .12, -.128, .50), (.142, .014, .115), equipment,
             collection, arm, "shin." + side, .026)
        for z in (.445, .555):
            _box(f"Officer_KneePad_Strap.{side}.{z}",
                 (sign * .12, -.082, z), (.19, .018, .018), webbing,
                 collection, arm, "shin." + side, .006)
        _build_boot(collection, arm, side, sign, equipment, rubber, webbing)
        _glove_hand(collection, arm, side, rubber, cloth, equipment)
        _box(f"Officer_Elbow_Reinforcement.{side}",
             (sign * .45, -.075, 1.32), (.14, .018, .09), reinforced,
             collection, arm, "upper_arm." + side, .025)


def _build_boot(collection, arm, side, sign, boot, rubber, webbing):
    cx = sign * .12
    # Foot points run toe-to-heel; footprint length is 0.295 m.
    outline = ((-.052, -.26), (.052, -.26), (.06, -.22), (.056, -.075),
               (.045, .035), (-.045, .035), (-.056, -.075), (-.06, -.22))
    vertices, faces = [], []
    for z in (.018, .042, .067):
        for x, y in outline:
            vertices.append((cx + x, y, z))
    for row in range(2):
        for i in range(8):
            a = row * 8 + i
            b = row * 8 + (i + 1) % 8
            faces.append((a, b, b + 8, a + 8))
    faces.extend((tuple(reversed(range(8))), tuple(range(16, 24))))
    sole = _mesh(f"Officer_Boot_Sole.{side}", vertices, faces, rubber,
                 collection, arm, [{"foot." + side: 1.0}] * len(vertices))
    sole["foot_length_m"] = .295
    _loft(f"Officer_Boot_Upper.{side}", (cx, -.12, .062),
          (cx, 0, .285), ((0, .053, .105), (.10, .056, .095),
          (.22, .054, .074), (.38, .049, .062), (.60, .046, .056),
          (.82, .045, .054), (.96, .047, .056), (1, .047, .056)),
          boot, collection, arm, "shin." + side, "foot." + side)
    _box(f"Officer_Boot_ToeCap.{side}", (cx, -.205, .085),
         (.101, .09, .047), boot, collection, arm, "foot." + side, .024)
    _box(f"Officer_Boot_Tongue.{side}", (cx, -.142, .155),
         (.068, .018, .105), webbing, collection, arm, "shin." + side, .015)
    for index in range(5):
        z = .12 + index * .025
        _box(f"Officer_Boot_Lace.{side}.{index}",
             (cx, -.154 - (index % 2) * .012, z), (.09, .012, .006),
             rubber, collection, arm, "shin." + side, .002)
    _box(f"Officer_Boot_HeelCounter.{side}", (cx, .005, .10),
         (.087, .05, .075), boot, collection, arm, "foot." + side, .014)


def _build_vest(collection, arm, materials):
    armor, webbing, pouch, equipment, rubber = materials
    levels = (1.13, 1.18, 1.26, 1.34, 1.40)
    for back in (False, True):
        _rounded_panel("Officer_PlateCarrier_Panel_" + ("Rear" if back else "Front"),
                       (-.21, -.16, -.08, 0, .08, .16, .21), levels,
                       armor, collection, arm, "spine_02" if back else "spine_01", back)
    for side, sign in (("L", -1), ("R", 1)):
        _box(f"Officer_Cummerbund_Side.{side}", (sign * .205, 0, 1.245),
             (.07, .25, .20), webbing, collection, arm, "spine_01", .018)
        _box(f"Officer_Shoulder_Str ap.{side}".replace(" ", ""),
             (sign * .135, 0, 1.43), (.078, .075, .22), webbing,
             collection, arm, "spine_02", .018)
        for row in range(3):
            z = 1.17 + row * .065
            _box(f"Officer_MOLLE_Webbing.{side}.{row}",
                 (sign * .205, -.132, z), (.012, .025, .205), equipment,
                 collection, arm, "spine_01", .003)
    for index, x in enumerate((-.135, -.045, .045, .135)):
        _box(f"Officer_Vest_MOLLE_Rail.{index}", (x, -.162, 1.245),
             (.012, .016, .205), webbing, collection, arm, "spine_01", .003)
        for row, z in enumerate((1.17, 1.22, 1.27, 1.32)):
            _box(f"Officer_Pouch_AttachmentLoop.{index}.{row}",
                 (x, -.174, z), (.052, .018, .018), webbing,
                 collection, arm, "spine_01", .004)
    for index, x in enumerate((-.135, -.045, .045, .135)):
        _box(f"Officer_Magazine_Pouch.{index}", (x, -.207, 1.205),
             (.075, .085, .135), pouch, collection, arm, "spine_01", .014)
        _box(f"Officer_Magazine_Flap.{index}", (x, -.255, 1.275),
             (.079, .018, .038), equipment, collection, arm, "spine_01", .008)
        _box(f"Officer_Magazine_RetentionTab.{index}",
             (x, -.267, 1.252), (.018, .012, .035), rubber,
             collection, arm, "spine_01", .004)
    for side, sign in (("L", -1), ("R", 1)):
        _box(f"Officer_Utility_Pouch.{side}", (sign * .19, -.17, 1.105),
             (.115, .085, .13), pouch, collection, arm, "spine_01", .014)
        _box(f"Officer_Utility_Pouch_Flap.{side}",
             (sign * .19, -.218, 1.17), (.12, .018, .035), equipment,
             collection, arm, "spine_01", .008)
    _box("Officer_Radio_Housing", (-.19, -.17, 1.32), (.075, .06, .16),
         equipment, collection, arm, "spine_02", .01)
    _box("Officer_Radio_Antenna", (-.21, -.165, 1.44), (.008, .01, .12),
         rubber, collection, arm, "spine_02", .003)
    _loft("Officer_Radio_Cable", (-.19, -.15, 1.40), (-.09, -.10, 1.34),
          ((0, .006, .006), (.5, .006, .006), (1, .006, .006)),
          rubber, collection, arm, "spine_02", sides=8)
    _box("Officer_Belt_Band", (0, 0, .96), (.41, .30, .052), webbing,
         collection, arm, "pelvis", .018)
    _box("Officer_Belt_Buckle", (0, -.158, .96), (.07, .025, .042),
         equipment, collection, arm, "pelvis", .007)
    _box("Officer_Duty_Holster", (.235, -.04, .83), (.105, .13, .205),
         pouch, collection, arm, "pelvis", .02)
    _box("Officer_Holster_Retention", (.235, -.115, .92), (.095, .018, .03),
         webbing, collection, arm, "pelvis", .006)
    _box("Officer_Belt_Utility_Pouch", (-.24, -.02, .97), (.10, .105, .10),
         pouch, collection, arm, "pelvis", .014)


def _build_head(collection, arm, materials):
    face, cloth, rubber, helmet, equipment = materials
    _face(None, collection, face, arm)
    _ring_surface("Officer_Neck", ((1.455, .072, .073, 0),
                  (1.48, .077, .076, 0), (1.57, .073, .072, 0)),
                  cloth, collection, arm,
                  lambda z, p: {"neck": 1.0}, sides=24)
    _ring_surface("Officer_Balaclava", (
        (1.57, .105, .08, 0), (1.59, .125, .10, 0),
        (1.63, .124, .103, 0), (1.66, .122, .102, 0),
        (1.70, .12, .10, 0), (1.715, .112, .092, 0)), cloth,
        collection, arm, lambda z, p: {"head": 1.0}, sides=32,
        eye_opening=True)
    for side, sign in (("L", -1), ("R", 1)):
        _box(f"Officer_Eye.{side}", (sign * .039, -.104, 1.687),
             (.025, .009, .012), equipment, collection, arm, "head", .005)
    _loft("Officer_Nose_Bridge", (0, -.085, 1.69), (0, -.115, 1.65),
          ((0, .025, .024), (.45, .022, .02), (1, .019, .018)),
          face, collection, arm, "head", sides=10)
    _box("Officer_Mask_MouthSeam", (0, -.103, 1.625), (.075, .008, .008),
         rubber, collection, arm, "head", .003)
    for side, sign in (("L", -1), ("R", 1)):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=16, ring_count=8,
                                             location=(sign * .122, 0, 1.655))
        ear = bpy.context.object
        ear.name = f"Officer_Ear.{side}"
        ear.scale = (.025, .035, .048)
        bpy.ops.object.transform_apply(
            location=False, rotation=False, scale=True)
        for owner in list(ear.users_collection):
            owner.objects.unlink(ear)
        collection.objects.link(ear)
        ear.data.materials.append(face)
        world = ear.matrix_world.copy()
        ear.parent = arm
        ear.parent_type = "BONE"
        ear.parent_bone = "head"
        ear.matrix_world = world
    _helmet(collection, arm, helmet, rubber, cloth)


def _build_animations(arm):
    scene = bpy.context.scene
    scene.render.fps = 24
    clips = {
        "Anim_Officer_Walk": (1, 25),
        "Anim_Officer_StandToCrouch": (1, 13),
        "Anim_Officer_CrouchIdle": (1, 25),
        "Anim_Officer_CrouchToStand": (1, 13),
    }
    pose_names = ("pelvis", "spine_01", "spine_02", "thigh.L", "shin.L",
                  "foot.L", "thigh.R", "shin.R", "foot.R", "upper_arm.L",
                  "forearm.L", "hand.L", "upper_arm.R", "forearm.R", "hand.R")
    for name, (start, end) in clips.items():
        action = bpy.data.actions.new(name)
        arm.animation_data_create()
        arm.animation_data.action = action
        for frame in range(start, end + 1):
            phase = math.tau * (frame - start) / max(1, end - start)
            crouch_weight = 0.0
            if "StandToCrouch" in name:
                crouch_weight = (frame - start) / (end - start)
            elif "CrouchToStand" in name:
                crouch_weight = 1.0 - (frame - start) / (end - start)
            elif "CrouchIdle" in name:
                crouch_weight = 1.0
            walk = "Walk" in name
            for side in ("L", "R"):
                influence = 0.0 if walk else 1.0
                for owner_name, constraint_name in (
                        (f"shin.{side}", f"IK_Foot.{side}"),
                        (f"forearm.{side}", f"IK_Hand.{side}")):
                    constraint = arm.pose.bones[owner_name].constraints[constraint_name]
                    constraint.influence = influence
                    arm.keyframe_insert(
                        data_path=f'pose.bones["{owner_name}"].constraints["{constraint_name}"].influence',
                        frame=frame, group=f"IK_{side}")
            for bone_name in pose_names:
                bone = arm.pose.bones[bone_name]
                bone.rotation_mode = "XYZ"
                bone.location = (0, 0, 0)
                bone.rotation_euler = (0, 0, 0)
                if bone_name == "pelvis":
                    bone.location.y = -.29 * crouch_weight
                    bone.location.z = -.035 * crouch_weight
                    if walk:
                        bone.location.z = .018 * math.sin(phase * 2)
                if bone_name.startswith("thigh."):
                    side_phase = phase + \
                        (math.pi if bone_name.endswith("L") else 0)
                    bone.rotation_euler.x = .30 * \
                        math.sin(side_phase) if walk else 0
                if bone_name.startswith("shin."):
                    side_phase = phase + \
                        (math.pi if bone_name.endswith("L") else 0)
                    bone.rotation_euler.x = (
                        .48 * max(0, math.sin(side_phase)) if walk else 0)
                if bone_name.startswith("foot."):
                    bone.rotation_euler.x = .08 * \
                        math.sin(phase) if walk else 0
                if bone_name == "spine_01":
                    bone.rotation_euler.x = -.12 * crouch_weight
                if bone_name.startswith("upper_arm."):
                    bone.rotation_euler.x = -.10 * crouch_weight
                bone.keyframe_insert("location", frame=frame, group=bone_name)
                bone.keyframe_insert(
                    "rotation_euler", frame=frame, group=bone_name)
        action["frame_start"] = start
        action["frame_end"] = end
        action["loop"] = name in {
            "Anim_Officer_Walk", "Anim_Officer_CrouchIdle"}
        for curve in common.action_fcurves(action):
            for key in curve.keyframe_points:
                key.interpolation = "BEZIER"
        action.use_fake_user = True
    for side in ("L", "R"):
        for bone_name, constraint_name in (
                (f"shin.{side}", f"IK_Foot.{side}"),
                (f"forearm.{side}", f"IK_Hand.{side}")):
            arm.pose.bones[bone_name].constraints[constraint_name].influence = 0.0
    arm.animation_data.action = None
    for track in list(arm.animation_data.nla_tracks):
        arm.animation_data.nla_tracks.remove(track)


def _make_lods(objects, arm, collection):
    counts = {"LOD0": 0, "LOD1": 0, "LOD2": 0}
    for source in objects:
        if source.type != "MESH":
            continue
        source["asset_lod"] = "LOD0"
        counts["LOD0"] += _triangles(source)
        for lod, ratio in (("LOD1", .55), ("LOD2", .24)):
            duplicate = source.copy()
            duplicate.data = source.data.copy()
            duplicate.name = source.name + "_" + lod
            duplicate.parent = arm
            duplicate.hide_render = True
            duplicate["asset_lod"] = lod
            duplicate["exclude_from_asset_export"] = True
            collection.objects.link(duplicate)
            duplicate.hide_set(True)
            decimate = duplicate.modifiers.new("LOD_Decimate", "DECIMATE")
            decimate.ratio = ratio
            counts[lod] += _triangles(duplicate)
    return counts


def _triangles(obj):
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    mesh = evaluated.to_mesh()
    try:
        mesh.calc_loop_triangles()
        return len(mesh.loop_triangles)
    finally:
        evaluated.to_mesh_clear()


def _descendants(root):
    found, pending = [], list(root.children)
    while pending:
        obj = pending.pop()
        found.append(obj)
        pending.extend(obj.children)
    return found


def build_officer():
    common.ensure_runtime()
    texture_dir = DIRS["Textures"] / "Officer_Detailed"
    source_collection = bpy.data.collections.new(
        "SRC_Officer_Detailed_HighDetail")
    bpy.context.scene.collection.children.link(source_collection)
    game_collection = bpy.data.collections.new(LOD0)
    bpy.context.scene.collection.children.link(game_collection)
    arm = _build_rig(game_collection)
    root = bpy.data.objects.new(LOD0, None)
    game_collection.objects.link(root)
    root["asset_type"] = "character"
    arm.parent = root

    cloth = _pbr_material("MAT_Officer_NavyCloth", (.035, .050, .065), .88,
                          texture_dir, woven=True)
    trouser = _pbr_material("MAT_Officer_CharcoalTrouser", (.045, .052, .058), .86,
                            texture_dir, woven=True)
    vest = _pbr_material("MAT_Officer_MatteCarrier", (.055, .066, .071), .84,
                         texture_dir, woven=True)
    rubber = _pbr_material("MAT_Officer_Rubber", (.018, .022, .024), .91,
                           texture_dir)
    equipment = _pbr_material("MAT_Officer_Polymer", (.035, .044, .048), .68,
                              texture_dir)
    pouch = _pbr_material("MAT_Officer_PouchFabric", (.050, .062, .065), .9,
                          texture_dir, woven=True)
    metal = _pbr_material("MAT_Officer_BlackenedMetal", (.075, .082, .083), .48,
                          texture_dir, metallic=.62)
    face = _mat("MAT_Officer_Face", (.24, .16, .12), .78)
    materials = (cloth, trouser, trouser, rubber, vest, pouch, equipment)
    start_objects = set(bpy.data.objects)
    _build_clothes(game_collection, arm, materials)
    _build_vest(game_collection, arm, (vest, pouch, pouch, equipment, rubber))
    _build_head(game_collection, arm, (face, cloth, rubber, equipment, metal))
    for side, sign in (("L", -1), ("R", 1)):
        _box(f"Officer_Belt_Retainer.{side}", (sign * .11, -.163, .96),
             (.018, .02, .048), metal, game_collection, arm, "pelvis", .003)
        _box(f"Officer_Hand_GripSocket.{side}", (sign * .66, -.1, 1.2),
             (.012, .012, .012), equipment, game_collection, arm,
             "hand." + side, .002)
    # Stable sockets retain the established attachment names and forward axis (-Y).
    for name, location, bone in (
            ("ATT_Officer_MainHand", (.66, -.10, 1.20), "hand.R"),
            ("ATT_Officer_SupportHand", (-.66, -.10, 1.20), "hand.L"),
            ("ATT_Back", (0, .17, 1.34), "spine_02"),
            ("ATT_Belt", (.27, -.10, .96), "pelvis")):
        socket = bpy.data.objects.new(name, None)
        game_collection.objects.link(socket)
        socket.location = location
        world = socket.matrix_world.copy()
        socket.parent = arm
        socket.parent_type = "BONE"
        socket.parent_bone = bone
        socket.matrix_world = world
        socket["attachment"] = True
    created = [obj for obj in bpy.data.objects if obj not in start_objects]
    game_objects = [obj for obj in created if obj.type == "MESH"]
    for obj in game_objects:
        _uv(obj)
        obj["source_detail"] = "controlled quad lofts and shaped garment panels"
    _build_animations(arm)
    counts = _make_lods(game_objects, arm, game_collection)
    # Keep the editable high-density authoring copy in the source .blend, outside FBX export.
    for obj in game_objects:
        if not obj.name.startswith(("Officer_Combat", "Officer_Cargo",
                                    "Officer_PlateCarrier")):
            continue
        detail = obj.copy()
        detail.data = obj.data.copy()
        detail.name = "SRC_" + obj.name
        source_collection.objects.link(detail)
        world = detail.matrix_world.copy()
        detail.parent = None
        detail.matrix_world = world
        detail.hide_render = True
        detail.hide_set(True)
        detail["exclude_from_asset_export"] = True
        detail["source_detail_copy"] = True
        subdiv = detail.modifiers.new("Sculpt_Source_Subdivision", "SUBSURF")
        subdiv.levels = 1
    source_collection.hide_render = True
    source_collection.hide_viewport = True
    for obj in created:
        if obj.type == "MESH":
            obj.hide_set(False)
    return root, arm, counts, texture_dir


def _export_lod(root, arm, lod, output):
    objects = [root, arm]
    for obj in _descendants(root):
        if obj.get("asset_lod", "LOD0") == lod and not obj.get("exclude_from_asset_export"):
            objects.append(obj)
        elif obj.type == "EMPTY" and obj.get("attachment"):
            objects.append(obj)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = arm
    bpy.ops.export_scene.fbx(
        filepath=str(output), use_selection=True,
        object_types={"EMPTY", "MESH", "ARMATURE"},
        use_mesh_modifiers=True, add_leaf_bones=False,
        apply_unit_scale=True, axis_forward="-Z", axis_up="Y",
        bake_anim=True, bake_anim_use_nla_strips=False,
        bake_anim_use_all_actions=True, bake_anim_simplify_factor=0.0,
        use_custom_props=True)
    if not output.is_file() or output.stat().st_size == 0:
        raise RuntimeError(f"FBX export failed: {output}")


def _roundtrip_check(filepath, source_dimensions):
    if not hasattr(bpy.ops.import_scene, "fbx"):
        try:
            bpy.ops.preferences.addon_enable(module="io_scene_fbx")
        except (AttributeError, RuntimeError):
            pass
    if not hasattr(bpy.ops.import_scene, "fbx"):
        return {"status": "not_run", "reason": "Blender FBX importer unavailable"}
    scene = bpy.context.scene
    check_scene = bpy.data.scenes.new("Officer_Detailed_FBX_RoundTrip")
    window = bpy.context.window
    actions_before = set(bpy.data.actions)
    try:
        if window:
            window.scene = check_scene
            bpy.ops.import_scene.fbx(filepath=str(filepath))
        else:
            with bpy.context.temp_override(scene=check_scene):
                bpy.ops.import_scene.fbx(filepath=str(filepath))
        meshes = [obj for obj in check_scene.objects if obj.type == "MESH"]
        arms = [obj for obj in check_scene.objects if obj.type == "ARMATURE"]
        imported_actions = sorted(action.name for action in bpy.data.actions
                                  if action not in actions_before)
        imported_names = {obj.name for obj in check_scene.objects}
        expected_actions = {"Anim_Officer_Walk", "Anim_Officer_StandToCrouch",
                            "Anim_Officer_CrouchIdle", "Anim_Officer_CrouchToStand"}
        expected_sockets = {"ATT_Officer_MainHand", "ATT_Officer_SupportHand",
                            "ATT_Back", "ATT_Belt"}
        action_names = {name.rsplit("|", 1)[-1] for name in imported_actions}
        action_ok = expected_actions.issubset(action_names)
        normalized_names = {
            name.rsplit(".", 1)[0] if name.rsplit(
                ".", 1)[-1].isdigit() else name
            for name in imported_names
        }
        socket_ok = expected_sockets.issubset(normalized_names)
        dimensions = common.evaluated_dimensions(list(check_scene.objects))
        dimensions_ok = all(abs(dimensions[index] - source_dimensions[index]) <= .08
                            for index in range(3))
        hierarchy_ok = bool(meshes and arms)
        return {"status": "passed" if hierarchy_ok and action_ok and
                socket_ok and dimensions_ok else "failed",
                "mesh_count": len(meshes), "armature_count": len(arms),
                "dimensions_m": dimensions, "imported_actions": imported_actions,
                "imported_attachment_names": sorted(
                    name for name in imported_names if "ATT_" in name),
                "source_dimensions_m": source_dimensions,
                "checks": {"hierarchy": hierarchy_ok, "actions": action_ok,
                           "sockets": socket_ok, "dimensions": dimensions_ok}}
    except Exception as error:
        return {"status": "failed", "reason": str(error)}
    finally:
        if window:
            window.scene = scene
        for obj in list(check_scene.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.scenes.remove(check_scene)


def _render_views(arm, output):
    output.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in {
        item.identifier for item in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items
    } else "BLENDER_EEVEE"
    scene.render.resolution_x = 1000
    scene.render.resolution_y = 1000
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False
    scene.render.filepath = str(output)
    camera = bpy.data.objects.get("SHOWCASE_Camera")
    if not camera:
        bpy.ops.object.camera_add(location=(3, -4, 2.5))
        camera = bpy.context.object
        camera.name = "SHOWCASE_Camera"
        scene.camera = camera
    scene.camera = camera
    grid = common.create_preview_grid()
    grid.hide_render = True
    key = bpy.data.objects.get("SHOWCASE_Key")
    if key and key.type == "LIGHT":
        key.data.energy = 1450
        key.data.shape = "DISK"
        key.data.size = 4
    specifications = (
        ("neutral_front", (0, -4.4, 1.0), (0, 0, .92), "neutral"),
        ("neutral_side", (4.4, 0, 1.0), (0, 0, .92), "neutral"),
        ("neutral_back", (0, 4.4, 1.0), (0, 0, .92), "neutral"),
        ("equipped_three_quarter", (3.1, -3.2, 1.35), (0, 0, .96), "neutral"),
        ("head_helmet_closeup", (1.1, -1.8, 1.72), (0, 0, 1.69), "neutral"),
        ("vest_hand_closeup", (1.0, -1.8, 1.25), (0, 0, 1.23), "neutral"),
        ("boots_knees_closeup", (1.2, -1.8, .43), (0, 0, .43), "neutral"),
        ("gameplay_distance", (3.2, -4.2, 6.8), (0, 0, .9), "neutral"),
    )
    arm.animation_data.action = None
    for name, location, target, mode in specifications:
        camera.location = location
        common.point_camera(camera, target)
        for obj in bpy.context.scene.objects:
            if obj.type == "MESH":
                obj.show_wire = mode == "wire"
                obj.show_all_edges = mode == "wire"
        scene.render.filepath = str(output / f"{name}.png")
        bpy.ops.render.render(write_still=True)
    for obj in bpy.context.scene.objects:
        if obj.type == "MESH":
            obj.show_wire = False
            obj.show_all_edges = False
    # Render actual garment edge loops; Object.show_wire alone is a viewport overlay.
    wire_material = _mat("MAT_Review_Topology", (.08, .74, .79), .45)
    wire_shader = wire_material.node_tree.nodes.get("Principled BSDF")
    wire_shader.inputs["Emission Color"].default_value = (.08, .74, .79, 1)
    wire_shader.inputs["Emission Strength"].default_value = 1.8
    wire_targets = ("Officer_Combat_Shirt_Body", "Officer_Combat_Shirt_Sleeve",
                    "Officer_Combat_Shirt_Forearm", "Officer_Cargo_Trouser_Thigh",
                    "Officer_Cargo_Trouser_Shin")
    originals, wire_copies = [], []
    for obj in _descendants(bpy.data.objects.get(LOD0)):
        if obj.type != "MESH" or not obj.name.startswith(wire_targets):
            continue
        originals.append((obj, obj.hide_render))
        obj.hide_render = True
        wire = obj.copy()
        wire.data = obj.data.copy()
        wire.name = "REVIEW_Topology_" + obj.name
        bpy.context.scene.collection.objects.link(wire)
        wire.data.materials.clear()
        wire.data.materials.append(wire_material)
        for modifier in list(wire.modifiers):
            if modifier.type != "ARMATURE":
                wire.modifiers.remove(modifier)
        wireframe = wire.modifiers.new("REVIEW_Real_Edge_Loops", "WIREFRAME")
        wireframe.thickness = .0012
        wireframe.use_replace = True
        wire_copies.append(wire)
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.05
    camera.location = (0, -4.4, 1.0)
    common.point_camera(camera, (0, 0, .92))
    scene.render.filepath = str(output / "wireframe_front.png")
    bpy.ops.render.render(write_still=True)
    for wire in wire_copies:
        bpy.data.objects.remove(wire, do_unlink=True)
    for obj, hidden in originals:
        obj.hide_render = hidden
    comparison_dir = output / "animations"
    camera.data.type = "ORTHO"
    camera.data.ortho_scale = 2.05
    camera.location = (4.4, 0, 1.0)
    common.point_camera(camera, (0, 0, .92))
    arm.animation_data.action = None
    scene.frame_set(1)
    standing_path = comparison_dir / "_standing_side.png"
    crouching_path = comparison_dir / "_crouching_side.png"
    scene.render.filepath = str(standing_path)
    bpy.ops.render.render(write_still=True)
    arm.animation_data.action = bpy.data.actions["Anim_Officer_CrouchIdle"]
    scene.frame_set(13)
    scene.render.filepath = str(crouching_path)
    bpy.ops.render.render(write_still=True)
    first = bpy.data.images.load(str(standing_path), check_existing=False)
    second = bpy.data.images.load(str(crouching_path), check_existing=False)
    width, height = first.size
    first_pixels = array("f", [0.0]) * (width * height * 4)
    second_pixels = array("f", [0.0]) * (width * height * 4)
    first.pixels.foreach_get(first_pixels)
    second.pixels.foreach_get(second_pixels)
    combined = array("f", [0.0]) * (width * height * 8)
    row_size = width * 4
    for row in range(height):
        source = row * row_size
        target = row * row_size * 2
        combined[target:target +
                 row_size] = first_pixels[source:source + row_size]
        combined[target + row_size:target + row_size *
                 2] = second_pixels[source:source + row_size]
    sheet = bpy.data.images.new("Officer_Standing_Crouched_SideComparison",
                                width * 2, height, alpha=True)
    sheet.pixels.foreach_set(combined)
    sheet.file_format = "PNG"
    sheet.filepath_raw = str(output / "standing_crouched_side_comparison.png")
    sheet.save()
    for image in (first, second, sheet):
        bpy.data.images.remove(image)
    standing_path.unlink(missing_ok=True)
    crouching_path.unlink(missing_ok=True)
    original_settings = (
        scene.render.image_settings.media_type,
        scene.render.image_settings.file_format, scene.render.filepath,
        scene.frame_start, scene.frame_end, scene.render.resolution_x,
        scene.render.resolution_y)
    scene.render.image_settings.media_type = "VIDEO"
    scene.render.image_settings.file_format = "FFMPEG"
    scene.render.ffmpeg.format = "MPEG4"
    scene.render.ffmpeg.codec = "H264"
    scene.render.resolution_x = 640
    scene.render.resolution_y = 640
    scene.render.resolution_percentage = 100
    grid.hide_render = False
    clip_specs = (
        ("Anim_Officer_Walk", "walk_review.mp4"),
        ("Anim_Officer_StandToCrouch", "stand_to_crouch_review.mp4"),
        ("Anim_Officer_CrouchIdle", "crouch_idle_review.mp4"),
        ("Anim_Officer_CrouchToStand", "crouch_to_stand_review.mp4"),
    )
    for clip_name, filename in clip_specs:
        action = bpy.data.actions[clip_name]
        arm.animation_data.action = action
        scene.frame_start = int(action["frame_start"])
        scene.frame_end = int(action["frame_end"])
        scene.render.filepath = str(comparison_dir / filename)
        bpy.ops.render.render(animation=True)
    arm.animation_data.action = None
    scene.frame_set(1)
    for side in ("L", "R"):
        for bone_name, constraint_name in (
                (f"shin.{side}", f"IK_Foot.{side}"),
                (f"forearm.{side}", f"IK_Hand.{side}")):
            arm.pose.bones[bone_name].constraints[constraint_name].influence = 0.0
    bpy.context.view_layer.update()
    (media_type, file_format, filepath, frame_start, frame_end,
     resolution_x, resolution_y) = original_settings
    scene.render.image_settings.media_type = media_type
    scene.render.image_settings.file_format = file_format
    scene.render.filepath = filepath
    scene.frame_start, scene.frame_end = frame_start, frame_end
    scene.render.resolution_x, scene.render.resolution_y = resolution_x, resolution_y
    scene.frame_set(1)
    arm.animation_data.action = None
    for name in ("Anim_Officer_Walk", "Anim_Officer_StandToCrouch",
                 "Anim_Officer_CrouchIdle", "Anim_Officer_CrouchToStand"):
        action = bpy.data.actions.get(name)
        if not action:
            continue
        grid.hide_render = False
        arm.animation_data.action = action
        start, end = int(action["frame_start"]), int(action["frame_end"])
        for frame in sorted({start, start + (end - start) // 2, end}):
            scene.frame_set(frame)
            scene.render.filepath = str(
                output / "animations" / f"{name}_{frame:03}.png")
            Path(scene.render.filepath).parent.mkdir(
                parents=True, exist_ok=True)
            bpy.ops.render.render(write_still=True)
        grid.hide_render = True
    arm.animation_data.action = None
    scene.frame_set(1)


def generate(render=True, export=True):
    root, arm, counts, texture_dir = build_officer()
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.frame_start, scene.frame_end = 1, 25
    meshes = [obj for obj in _descendants(root) if obj.type == "MESH" and
              obj.get("asset_lod", "LOD0") == "LOD0"]
    dims = common.evaluated_dimensions([root] + _descendants(root))
    crouch = bpy.data.actions["Anim_Officer_CrouchIdle"]
    arm.animation_data.action = crouch
    contact_samples = {}
    for frame in (int(crouch["frame_start"]), int(crouch["frame_end"])):
        scene.frame_set(frame)
        bpy.context.view_layer.update()
        contact_samples[str(frame)] = {
            side: tuple(arm.matrix_world @ arm.pose.bones[f"foot.{side}"].head)
            for side in ("L", "R")
        }
    foot_drift = {
        side: round((Vector(contact_samples[str(int(crouch["frame_end"]))][side]) -
                     Vector(contact_samples[str(int(crouch["frame_start"]))][side])).length, 5)
        for side in ("L", "R")
    }
    ankle_z = {
        side: round(
            contact_samples[str(int(crouch["frame_start"]))][side][2], 4)
        for side in ("L", "R")
    }
    crouch_contact_ok = (all(value <= .01 for value in foot_drift.values()) and
                         all(.10 <= value <= .14 for value in ankle_z.values()))
    arm.animation_data.action = None
    scene.frame_set(1)
    report = {
        "generation_status": "generated",
        "completion_status": "technical_completion_passed_visual_acceptance_not_accepted",
        "blender": bpy.app.version_string,
        "height_m": dims[2],
        "evaluated_triangles": counts,
        "game_mesh_object_count": len(meshes),
        "rig_bone_count": len(arm.data.bones),
        "crouch_foot_contact": {"pass": crouch_contact_ok,
                                "ankle_z_m": ankle_z,
                                "drift_m": foot_drift},
        "attachment_sockets": ["ATT_Officer_MainHand", "ATT_Officer_SupportHand",
                               "ATT_Back", "ATT_Belt"],
        "textures": str(texture_dir.relative_to(ROOT)),
        "animations": ["Anim_Officer_Walk", "Anim_Officer_StandToCrouch",
                       "Anim_Officer_CrouchIdle", "Anim_Officer_CrouchToStand"],
        "timed_animation_previews": [
            "walk_review.mp4", "stand_to_crouch_review.mp4",
            "crouch_idle_review.mp4", "crouch_to_stand_review.mp4"],
        "assistant_visual_review": {
            "status": "not_accepted",
            "findings": [
                "Rendered garment and body surfaces remain too segmented and procedural for the reference realism target.",
                "Facial, cloth-fold, seam, and equipment surface detail remain below the requested close-up quality.",
                "The rifle and final two-hand weapon contact are not present in this independent build.",
            ],
        },
        "human_visual_review": "pending user review",
        "limitations": [
            "Procedural authored geometry is not sculpted production retopology.",
            "Garment pieces remain modular surfaces rather than a continuous retopologized clothing shell.",
            "Texture maps are generated procedural maps; stitch and weave are not baked from a sculpt.",
            "Rifle geometry and runtime IK are not included in this independent officer build.",
            "Animation is keyframed procedural motion, not mocap; weapon grip and contact remain visual-review requirements.",
            "LOD triangle counts are measurements, not a mobile-performance claim.",
        ],
    }
    if render:
        _render_views(arm, DIRS["Previews"] / "officer_detailed")
    arm.animation_data.action = None
    scene.frame_set(1)
    for side in ("L", "R"):
        for bone_name, constraint_name in (
                (f"shin.{side}", f"IK_Foot.{side}"),
                (f"forearm.{side}", f"IK_Hand.{side}")):
            arm.pose.bones[bone_name].constraints[constraint_name].influence = 0.0
    bpy.context.view_layer.update()
    source_path = DIRS["Sources"] / "officer_detailed.blend"
    source_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(source_path))
    if export:
        export_dir = DIRS["Characters"] / "Officer_Detailed"
        export_dir.mkdir(parents=True, exist_ok=True)
        exports = []
        for lod in ("LOD0", "LOD1", "LOD2"):
            filename = export_dir / f"Officer_Detailed_{lod}.fbx"
            _export_lod(root, arm, lod, filename)
            roundtrip = (_roundtrip_check(filename, dims) if lod == "LOD0"
                         else {"status": "not_run"})
            exports.append(
                {"file": str(filename.relative_to(ROOT)), "round_trip": roundtrip})
        report["exports"] = exports
        report["round_trip_status"] = exports[0]["round_trip"]["status"]
    else:
        report["exports"] = []
        report["round_trip_status"] = "not_run"
    report["generation_status"] = "passed"
    report["completion_status"] = "technical_completion_passed_visual_acceptance_not_accepted"
    report_path = DIRS["Documentation"] / "detailed_officer_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf8")
    return report
