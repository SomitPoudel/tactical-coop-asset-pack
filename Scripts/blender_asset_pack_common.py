"""Shared Blender 3.6 LTS helpers for the tactical asset pack.

Run scripts from any working directory with Blender 3.6 LTS:
  blender -b --python Scripts/generate_quality_sample.py -- --validate
"""
from __future__ import annotations

import argparse
from array import array
import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

BLENDER_MIN = (3, 6, 0)
ROOT = Path(__file__).resolve().parents[1]
DIRS = {n: ROOT / n for n in ("Characters", "Equipment", "Environment", "Animations",
                              "Materials", "Textures", "Sources", "Previews", "Documentation")}


def ensure_runtime():
    v = bpy.app.version
    if v < BLENDER_MIN:
        raise RuntimeError(
            f"Blender 3.6 LTS or newer is required; found {bpy.app.version_string}")
    for p in DIRS.values():
        p.mkdir(parents=True, exist_ok=True)


def cli_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--validate", action="store_true")
    p.add_argument("--export", action="store_true")
    p.add_argument("--no-render", action="store_true")
    p.add_argument("--preview-only", action="store_true")
    p.add_argument("--preview-views", nargs="+", choices=(
        "officer_front", "officer_side", "officer_three_quarter",
        "officer_boots_knees", "officer_side_by_side",
        "officer_gameplay_distance",
        "gameplay_angle", "door_closed", "door_open", "animations"))
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.mode_set(
        mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.armatures, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0:
                datablocks.remove(block)


def setup_scene():
    clear_scene()
    s = bpy.context.scene
    s.unit_settings.system = 'METRIC'
    s.unit_settings.scale_length = 1.0
    s.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in {
        i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE'
    s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = 1280, 720, 100
    w = s.world or bpy.data.worlds.new('World')
    s.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get('Background')
    bg.inputs['Color'].default_value = (0.025, 0.035, 0.05, 1)
    bg.inputs['Strength'].default_value = 0.35
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .5))
    ref = bpy.context.object
    ref.name = 'REF_1M_DO_NOT_EXPORT'
    ref.hide_render = True
    bpy.ops.object.light_add(type='AREA', location=(3, -4, 6))
    key = bpy.context.object
    key.name = 'SHOWCASE_Key'
    key.data.energy = 1000
    key.data.size = 5
    point_camera(key, (0, 0, 1.0))
    bpy.ops.object.light_add(type='AREA', location=(-4, 2, 3))
    fill = bpy.context.object
    fill.name = 'SHOWCASE_Fill'
    fill.data.energy = 500
    fill.data.size = 4
    point_camera(fill, (0, 0, 1.0))
    bpy.ops.object.camera_add(location=(6, -7, 5.5))
    cam = bpy.context.object
    cam.name = 'SHOWCASE_Camera'
    cam.data.lens = 38
    s.camera = cam
    point_camera(cam, (0, 0, 1.0))


def point_camera(obj, target): obj.rotation_euler = (
    Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children:
        bpy.context.scene.collection.children.link(c)
    return c


def move_to(obj, col):
    for c in list(obj.users_collection):
        c.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def mat(name, color, metallic=0.0, roughness=.7, emission=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF')
    bs.inputs['Base Color'].default_value = (
        *color[:3], color[3] if len(color) > 3 else 1)
    bs.inputs['Metallic'].default_value = metallic
    bs.inputs['Roughness'].default_value = roughness
    if emission:
        if 'Emission Color' in bs.inputs:
            bs.inputs['Emission Color'].default_value = (*emission, 1)
            bs.inputs['Emission Strength'].default_value = 2
        elif 'Emission' in bs.inputs:
            bs.inputs['Emission'].default_value = (*emission, 1)
    return m


def assign_mat(o, m):
    o.data.materials.clear()
    o.data.materials.append(m)
    return o


def add_cube(name, location, dimensions, material=None, bevel=.02, col=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location)
    o = bpy.context.object
    o.name = name
    o.dimensions = dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b = o.modifiers.new('Bevel', 'BEVEL')
        b.width = bevel
        b.segments = 2
    if material:
        assign_mat(o, material)
    if col:
        move_to(o, col)
    return o


def add_cylinder(name, location, radius, depth, material=None, col=None, vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(
        vertices=vertices, radius=radius, depth=depth, location=location)
    o = bpy.context.object
    o.name = name
    if material:
        assign_mat(o, material)
    if col:
        move_to(o, col)
    return o


def add_uv(name, location, scale, material=None, col=None):
    bpy.ops.mesh.primitive_uv_sphere_add(
        segments=12, ring_count=8, location=location)
    o = bpy.context.object
    o.name = name
    o.scale = scale
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material:
        assign_mat(o, material)
    if col:
        move_to(o, col)
    return o


def ground_pivot(o, z=0.0):
    bpy.context.view_layer.update()
    minz = min((o.matrix_world @ Vector(c)).z for c in o.bound_box)
    o.location.z += z-minz
    bpy.context.view_layer.update()
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    o.select_set(False)
    return o


def parent_keep_world(o, parent, bone=None):
    bpy.context.view_layer.update()
    world = o.matrix_world.copy()
    o.parent = parent
    if bone:
        o.parent_type = 'BONE'
        o.parent_bone = bone
    o.matrix_world = world
    bpy.context.view_layer.update()


def create_humanoid_rig(name='Rig_Humanoid', col=None):
    bpy.ops.object.armature_add(enter_editmode=True, location=(0, 0, 0))
    arm = bpy.context.object
    arm.name = name
    arm.data.name = name+'_Data'
    eb = arm.data.edit_bones
    for b in list(eb):
        eb.remove(b)
    specs = {
        'root': ((0, 0, 0), (0, 0, .12), None), 'pelvis': ((0, 0, .82), (0, 0, 1.02), 'root'),
        'spine_01': ((0, 0, 1.02), (0, 0, 1.27), 'pelvis'), 'spine_02': ((0, 0, 1.27), (0, 0, 1.47), 'spine_01'),
        'neck': ((0, 0, 1.47), (0, 0, 1.58), 'spine_02'), 'head': ((0, 0, 1.58), (0, 0, 1.76), 'neck'),
        'clavicle.L': ((-.03, 0, 1.44), (-.22, -.03, 1.44), 'spine_02'), 'upper_arm.L': ((-.22, -.03, 1.44), (-.05, -.30, 1.34), 'clavicle.L'), 'forearm.L': ((-.05, -.30, 1.34), (.04, -.62, 1.34), 'upper_arm.L'), 'hand.L': ((.04, -.62, 1.34), (-.02, -.70, 1.34), 'forearm.L'),
        'clavicle.R': ((.03, 0, 1.44), (.22, -.03, 1.44), 'spine_02'), 'upper_arm.R': ((.22, -.03, 1.44), (.40, -.22, 1.31), 'clavicle.R'), 'forearm.R': ((.40, -.22, 1.31), (.155, -.405, 1.27), 'upper_arm.R'), 'hand.R': ((.155, -.405, 1.27), (.23, -.47, 1.26), 'forearm.R'),
        'thigh.L': ((-.12, 0, .82), (-.15, 0, .43), 'pelvis'), 'shin.L': ((-.15, 0, .43), (-.15, 0, .08), 'thigh.L'), 'foot.L': ((-.15, 0, .08), (-.15, -.24, .04), 'shin.L'),
        'thigh.R': ((.12, 0, .82), (.15, 0, .43), 'pelvis'), 'shin.R': ((.15, 0, .43), (.15, 0, .08), 'thigh.R'), 'foot.R': ((.15, 0, .08), (.15, -.24, .04), 'shin.R')}
    bones = {}
    for n, (h, t, p) in specs.items():
        b = eb.new(n)
        b.head = h
        b.tail = t
        bones[n] = b
        b.parent = bones.get(p)
    bpy.ops.object.mode_set(mode='OBJECT')
    arm.data.display_type = 'BBONE'
    arm.show_in_front = True
    if col:
        move_to(arm, col)
    return arm


def weighted_mesh(name, vertices, faces, material, arm, weights, col):
    mesh = bpy.data.meshes.new(name+'_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    if material:
        assign_mat(obj, material)
    bone_names = {bone for row in weights for bone in row}
    groups = {bone: obj.vertex_groups.new(name=bone) for bone in bone_names}
    for index, row in enumerate(weights):
        for bone, weight in row.items():
            if weight > 0:
                groups[bone].add([index], weight, 'REPLACE')
    world = obj.matrix_world.copy()
    obj.parent = arm
    obj.matrix_world = world
    obj.modifiers.new('Armature_Deform', 'ARMATURE').object = arm
    return obj


def tapered_limb(name, head, tail, radius_start, radius_end, material, arm, bone, col, neighbor=None):
    start = Vector(head)
    end = Vector(tail)
    axis = (end-start).normalized()
    side = Vector((1, 0, 0))-axis*axis.dot(Vector((1, 0, 0)))
    if side.length < .1:
        side = Vector((0, 1, 0))-axis*axis.dot(Vector((0, 1, 0)))
    side.normalize()
    depth = axis.cross(side).normalized()
    vertices = []
    faces = []
    weights = []
    profiles = ((0.0, .78), (.12, 1.0), (.50, .88), (.88, .76), (1.0, .58))
    sides = 10
    for t, scale in profiles:
        center = start.lerp(end, t)
        radius = radius_start*(1-t)+radius_end*t
        for index in range(sides):
            angle = 2*math.pi*index/sides
            point = center+side*(math.cos(angle)*radius*scale) + \
                depth*(math.sin(angle)*radius*.78*scale)
            vertices.append(tuple(point))
            blend = max(0.0, 1-abs(t-.5)*2.8)*.18 if neighbor else 0.0
            weights.append({bone: 1-blend, neighbor: blend}
                           if neighbor else {bone: 1.0})
    for ring in range(len(profiles)-1):
        for index in range(sides):
            a = ring*sides+index
            b = ring*sides+(index+1) % sides
            faces.append((a, b, b+sides, a+sides))
    faces.extend((tuple(reversed(range(sides))),
                  tuple(range((len(profiles)-1)*sides, len(profiles)*sides))))
    return weighted_mesh(name, vertices, faces, material, arm, weights, col)


def torso_mesh(name, material, arm, col):
    profiles = ((.84, .17, .12), (.94, .20, .14), (1.12, .22, .145),
                (1.34, .235, .15), (1.47, .28, .14))
    sides = 12
    vertices = []
    faces = []
    weights = []
    for z, width, depth in profiles:
        for index in range(sides):
            angle = 2*math.pi*index/sides
            vertices.append((math.cos(angle)*width, math.sin(angle)*depth, z))
            if z < 1.0:
                row = {'pelvis': .55, 'spine_01': .45}
            elif z < 1.30:
                row = {'spine_01': .55, 'spine_02': .45}
            else:
                row = {'spine_02': 1.0}
            weights.append(row)
    for ring in range(len(profiles)-1):
        for index in range(sides):
            a = ring*sides+index
            b = ring*sides+(index+1) % sides
            faces.append((a, b, b+sides, a+sides))
    faces.extend((tuple(reversed(range(sides))),
                  tuple(range((len(profiles)-1)*sides, len(profiles)*sides))))
    return weighted_mesh(name, vertices, faces, material, arm, weights, col)


def append_profiled_segment(vertices, faces, start, end, profile, sides=12):
    start = Vector(start)
    end = Vector(end)
    axis = (end-start).normalized()
    side = Vector((1, 0, 0))-axis*axis.dot(Vector((1, 0, 0)))
    if side.length < .1:
        side = Vector((0, 1, 0))-axis*axis.dot(Vector((0, 1, 0)))
    side.normalize()
    depth = axis.cross(side).normalized()
    first = len(vertices)
    for t, radius_x, radius_y in profile:
        center = start.lerp(end, t)
        for index in range(sides):
            angle = math.tau*index/sides
            point = center+side*(math.cos(angle)*radius_x) + \
                depth*(math.sin(angle)*radius_y)
            vertices.append(tuple(point))
    for ring in range(len(profile)-1):
        for index in range(sides):
            a = first+ring*sides+index
            b = first+ring*sides+(index+1) % sides
            faces.append((a, b, b+sides, a+sides))
    faces.extend((tuple(reversed(range(first, first+sides))),
                  tuple(range(first+(len(profile)-1)*sides,
                              first+len(profile)*sides))))


def append_torso_profiles(vertices, faces, profiles, sides=16):
    first = len(vertices)
    for z, center_y, radius_x, radius_y in profiles:
        for index in range(sides):
            angle = math.tau*index/sides
            vertices.append((math.cos(angle)*radius_x,
                             center_y+math.sin(angle)*radius_y, z))
    for ring in range(len(profiles)-1):
        for index in range(sides):
            a = first+ring*sides+index
            b = first+ring*sides+(index+1) % sides
            faces.append((a, b, b+sides, a+sides))
    faces.extend((tuple(reversed(range(first, first+sides))),
                  tuple(range(first+(len(profiles)-1)*sides,
                              first+len(profiles)*sides))))


def uniform_body_mesh(name, material, arm, col):
    vertices = []
    faces = []
    append_torso_profiles(vertices, faces, (
        (.77, 0, .145, .105), (.82, 0, .19, .13),
        (.91, 0, .185, .125), (1.00, 0, .17, .115),
        (1.08, 0, .19, .12), (1.16, 0, .215, .13),
        (1.28, 0, .235, .14), (1.38, 0, .255, .135),
        (1.45, 0, .235, .125), (1.50, 0, .13, .11),
    ))
    limb_profiles = {
        'clavicle': ((0, .075, .07), (.25, .105, .085),
                     (.75, .11, .09), (1, .12, .095)),
        'upper_arm': ((0, .12, .095), (.12, .12, .09),
                      (.42, .105, .082), (.78, .09, .073),
                      (.94, .088, .072), (1, .085, .07)),
        'forearm': ((0, .083, .07), (.12, .09, .074),
                    (.36, .086, .07), (.72, .075, .062),
                    (.91, .071, .06), (1, .067, .057)),
        'thigh': ((0, .12, .108), (.12, .135, .115),
                  (.35, .13, .105), (.70, .108, .087),
                  (.90, .094, .078), (1, .086, .072)),
        'shin': ((0, .09, .076), (.12, .096, .08),
                 (.32, .092, .078), (.55, .082, .07),
                 (.78, .073, .063), (.94, .07, .06), (1, .068, .057)),
    }
    for side in ('L', 'R'):
        for bone_name in ('clavicle', 'upper_arm', 'forearm', 'thigh', 'shin'):
            bone = arm.data.bones[bone_name+'.'+side]
            append_profiled_segment(
                vertices, faces, bone.head_local, bone.tail_local,
                limb_profiles[bone_name])

    mesh = bpy.data.meshes.new(name+'_SourceMesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    col.objects.link(obj)
    assign_mat(obj, material)
    remesh = obj.modifiers.new('Uniform_Surface_Voxel_Fuse', 'REMESH')
    remesh.mode = 'VOXEL'
    remesh.voxel_size = .03
    if hasattr(remesh, 'use_smooth_shade'):
        remesh.use_smooth_shade = True
    bpy.ops.object.select_all(action='DESELECT')
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.modifier_apply(modifier=remesh.name)
    for polygon in obj.data.polygons:
        polygon.use_smooth = True
    uv_layer = obj.data.uv_layers.new(name='Uniform_UV')
    for loop in obj.data.loops:
        point = obj.data.vertices[loop.vertex_index].co
        uv_layer.data[loop.index].uv = (point.x+.5, point.z/1.85)

    skeleton = [arm.data.bones[name] for name in (
        'pelvis', 'spine_01', 'spine_02')]
    skeleton.extend(arm.data.bones[name+'.'+side]
                    for side in ('L', 'R')
                    for name in ('clavicle', 'upper_arm', 'forearm',
                                 'thigh', 'shin'))
    weights = []
    for vertex in obj.data.vertices:
        distances = []
        for bone in skeleton:
            start = bone.head_local
            segment = bone.tail_local-start
            fraction = max(0.0, min(1.0,
                                    (vertex.co-start).dot(segment)/segment.length_squared))
            nearest = start+segment*fraction
            distances.append(((vertex.co-nearest).length, bone.name))
        distances.sort()
        minimum = distances[0][0]
        nearby = [(distance, bone) for distance, bone in distances[:3]
                  if distance <= minimum+.035]
        raw = [(bone, math.exp(-(distance-minimum)/.018))
               for distance, bone in nearby]
        total = sum(weight for _, weight in raw)
        weights.append({bone: weight/total for bone, weight in raw})
    world = obj.matrix_world.copy()
    obj.parent = arm
    obj.matrix_world = world
    bone_names = {bone for row in weights for bone in row}
    groups = {bone: obj.vertex_groups.new(name=bone)
              for bone in bone_names}
    for index, row in enumerate(weights):
        for bone, weight in row.items():
            groups[bone].add([index], weight, 'REPLACE')
    obj.modifiers.new('Armature_Deform', 'ARMATURE').object = arm
    return obj


def fitted_vest_plate(name, material, arm, col, back=False):
    profiles = ((1.12, .155, .20, .12), (1.18, .17, .215, .13),
                (1.32, .175, .23, .14), (1.39, .15, .24, .135),
                (1.42, .125, .24, .13))
    columns = 5
    front = []
    back_vertices = []
    weights = []
    for z, width, body_width, body_depth in profiles:
        for column in range(columns):
            fraction = column/(columns-1)*2-1
            x = fraction*width
            surface = -body_depth*math.sqrt(
                max(.08, 1-(x/body_width)**2))
            offset = .012 if back else -.012
            front.append((x, surface+offset, z))
            back_vertices.append((x, surface-offset, z))
            upper = max(0.0, min(1.0, (z-1.18)/.16))
            weights.append({'spine_01': 1-upper, 'spine_02': upper})
    vertices = front+back_vertices
    weights.extend(weights.copy())
    faces = []
    row_count = len(profiles)
    offset = row_count*columns
    for row in range(row_count-1):
        for column in range(columns-1):
            first = row*columns+column
            second = first+columns
            faces.append((first, first+1, second+1, second))
            faces.append((offset+first, offset+second,
                          offset+second+1, offset+first+1))
    boundary = ([column for column in range(columns)] +
                [row*columns+columns-1 for row in range(1, row_count)] +
                [((row_count-1)*columns+column)
                 for column in range(columns-2, -1, -1)] +
                [row*columns for row in range(row_count-2, 0, -1)])
    for index, first in enumerate(boundary):
        second = boundary[(index+1) % len(boundary)]
        faces.append((first, second, offset+second, offset+first))
    return weighted_mesh(name, vertices, faces, material, arm, weights, col)


def belt_mesh(name, material, arm, col):
    vertices = []
    faces = []
    append_torso_profiles(vertices, faces, (
        (.955, 0, .182, .13), (.968, 0, .198, .145),
        (1.015, 0, .198, .145), (1.03, 0, .182, .13),
    ), sides=20)
    weights = [{'pelvis': 1.0} for _ in vertices]
    return weighted_mesh(name, vertices, faces, material, arm, weights, col)


def low_profile_ellipsoid(name, material, arm, col, profiles, bone='head'):
    vertices = []
    faces = []
    append_torso_profiles(vertices, faces, profiles, sides=16)
    return weighted_mesh(
        name, vertices, faces, material, arm,
        [{bone: 1.0} for _ in vertices], col)


def weighted_ellipsoid(name, location, scale, material, arm, bone_weights, col):
    obj = add_uv(name, location, scale, material, col)
    groups = {bone: obj.vertex_groups.new(name=bone) for bone in bone_weights}
    for bone, weight in bone_weights.items():
        groups[bone].add(list(range(len(obj.data.vertices))),
                         weight, 'REPLACE')
    world = obj.matrix_world.copy()
    obj.parent = arm
    obj.matrix_world = world
    obj.modifiers.new('Armature_Deform', 'ARMATURE').object = arm
    return obj


def action_fcurves(action):
    if hasattr(action, 'fcurves'):
        return list(action.fcurves)
    curves = []
    for layer in action.layers:
        for strip in layer.strips:
            for channelbag in strip.channelbags:
                curves.extend(channelbag.fcurves)
    return curves


def build_officer(arm, variant='blue', root_name='Char_Officer'):
    col = collection(root_name)
    colors = {'blue': (.12, .25, .38, 1), 'orange': (.42, .20, .08, 1)}
    cloth = mat('MAT_Officer_'+variant,
                colors.get(variant, colors['blue']), 0, .8)
    cloth_nodes = cloth.node_tree.nodes
    cloth_links = cloth.node_tree.links
    cloth_bsdf = cloth_nodes.get('Principled BSDF')
    fabric_noise = cloth_nodes.new('ShaderNodeTexNoise')
    fabric_noise.inputs['Scale'].default_value = 360
    fabric_noise.inputs['Detail'].default_value = 2
    fabric_bump = cloth_nodes.new('ShaderNodeBump')
    fabric_bump.inputs['Strength'].default_value = .12
    fabric_bump.inputs['Distance'].default_value = .003
    cloth_links.new(fabric_noise.outputs['Fac'], fabric_bump.inputs['Height'])
    cloth_links.new(fabric_bump.outputs['Normal'], cloth_bsdf.inputs['Normal'])
    armor = mat('MAT_Armor', (.105, .135, .16, 1), .12, .68)
    dark = mat('MAT_Rubber', (.025, .032, .038, 1), .04, .78)
    pouch = mat('MAT_Officer_Pouch', (.055, .075, .082, 1), 0, .9)
    skin = mat('MAT_Skin', (.62, .38, .27, 1), 0, .75)
    accent = mat('MAT_Accent', (.65, .72, .76, 1), .1, .55)
    root = bpy.data.objects.new(root_name, None)
    col.objects.link(root)
    root['asset_type'] = 'character'
    arm.parent = root

    uniform_body_mesh('Officer_Uniform', cloth, arm, col)
    fitted_vest_plate('Officer_Plate', armor, arm, col)
    fitted_vest_plate('Officer_VestRearPanel', armor, arm, col, back=True)

    def boot_mesh(name, side, foot_x, profiles, material):
        vertices = []
        faces = []
        ring_size = 8
        for z, half_width, front, back in profiles:
            vertices.extend((
                (foot_x+half_width*.62, front, z),
                (foot_x+half_width, front+.035, z),
                (foot_x+half_width, back-.025, z),
                (foot_x+half_width*.62, back, z),
                (foot_x-half_width*.62, back, z),
                (foot_x-half_width, back-.025, z),
                (foot_x-half_width, front+.035, z),
                (foot_x-half_width*.62, front, z),
            ))
        for ring in range(len(profiles)-1):
            for index in range(ring_size):
                a = ring*ring_size+index
                b = ring*ring_size+(index+1) % ring_size
                faces.append((a, b, b+ring_size, a+ring_size))
        faces.extend((tuple(reversed(range(ring_size))),
                      tuple(range((len(profiles)-1)*ring_size,
                                  len(profiles)*ring_size))))
        return weighted_mesh(
            name, vertices, faces, material, arm,
            [{'foot.'+side: 1.0} for _ in vertices], col)

    for side in ('L', 'R'):
        elbow = arm.data.bones['forearm.'+side].head_local
        knee = arm.data.bones['shin.'+side].head_local
        knee_pad = add_cube('Officer_KneePad.'+side,
                            (knee.x, knee.y-.077, knee.z),
                            (.108, .035, .085), dark, .022, col)
        parent_keep_world(knee_pad, arm)
        knee_pad_groups = {
            bone: knee_pad.vertex_groups.new(name=bone)
            for bone in ('thigh.'+side, 'shin.'+side)}
        for vertex_index in range(len(knee_pad.data.vertices)):
            knee_pad_groups['thigh.'+side].add([vertex_index], .5, 'REPLACE')
            knee_pad_groups['shin.'+side].add([vertex_index], .5, 'REPLACE')
        knee_pad.modifiers.new('Armature_Deform', 'ARMATURE').object = arm
        hand = arm.data.bones['hand.'+side].head_local
        weighted_ellipsoid('Officer_Glove.'+side, hand, (.09, .09, .065),
                           dark, arm,
                           {'hand.'+side: .7, 'forearm.'+side: .3}, col)
        thumb = add_uv(
            'Officer_GloveThumb.'+side,
            (hand.x+(-.043 if side == 'L' else .043), hand.y-.065,
             hand.z-.006), (.034, .055, .043), dark, col)
        parent_keep_world(thumb, arm)
        thumb_groups = {bone: thumb.vertex_groups.new(name=bone)
                        for bone in ('forearm.'+side, 'hand.'+side)}
        for vertex_index in range(len(thumb.data.vertices)):
            thumb_groups['forearm.'+side].add([vertex_index], .15, 'REPLACE')
            thumb_groups['hand.'+side].add([vertex_index], .85, 'REPLACE')
        thumb.modifiers.new('Armature_Deform', 'ARMATURE').object = arm
        for name, location, dimensions in (
                ('Officer_GloveCuff.'+side,
                 (hand.x, hand.y+.055, hand.z), (.13, .055, .07)),
                ('Officer_GloveGuard.'+side,
                 (hand.x, hand.y-.035, hand.z+.035), (.075, .025, .038))):
            detail = add_cube(name, location, dimensions, armor, .012, col)
            parent_keep_world(detail, arm)
            groups = {bone: detail.vertex_groups.new(name=bone)
                      for bone in ('forearm.'+side, 'hand.'+side)}
            for vertex_index in range(len(detail.data.vertices)):
                groups['forearm.'+side].add([vertex_index], .35, 'REPLACE')
                groups['hand.'+side].add([vertex_index], .65, 'REPLACE')
            detail.modifiers.new('Armature_Deform', 'ARMATURE').object = arm
        foot = arm.data.bones['foot.'+side].head_local
        boot_mesh('Officer_Boot.'+side, side, foot.x,
                  ((.043, .048, -.235, .060),
                   (.075, .053, -.232, .058),
                   (.105, .052, -.215, .055),
                   (.145, .046, -.180, .048),
                   (.205, .042, -.125, .046),
                   (.255, .041, -.065, .042),
                   (.278, .042, -.045, .038)), dark)
        boot_mesh('Officer_BootSole.'+side, side, foot.x,
                  ((0.0, .052, -.240, .060),
                   (.045, .052, -.240, .060)), armor)

    weighted_ellipsoid('Officer_Head', (0, -.005, 1.63), (.125, .12, .155),
                       skin, arm, {'head': 1.0}, col)
    low_profile_ellipsoid('Officer_HelmetShell', dark, arm, col, (
        (1.685, .008, .105, .12), (1.705, .012, .15, .16),
        (1.75, .018, .16, .175), (1.79, .025, .13, .15),
        (1.805, .025, .07, .09),
    ))
    low_profile_ellipsoid('Officer_HelmetBrim', armor, arm, col, (
        (1.685, -.045, .145, .15), (1.70, -.045, .17, .17),
        (1.715, -.045, .145, .145),
    ))
    for side in ('L', 'R'):
        strap = add_cube('Officer_ChinStrap.'+side,
                         ((-.105 if side == 'L' else .105), -.073, 1.615),
                         (.018, .018, .112), pouch, .007, col)
        strap.rotation_euler.y = math.radians(-23 if side == 'L' else 23)
        parent_keep_world(strap, arm, 'head')
        earcup = add_cylinder('Officer_Headset.'+side,
                              ((-.132 if side == 'L' else .132), .0, 1.655),
                              .042, .035, armor, col, 12)
        earcup.rotation_euler.y = math.radians(90)
        parent_keep_world(earcup, arm, 'head')
    for x in (-.046, .046):
        weighted_ellipsoid('Officer_Eye', (x, -.112, 1.645), (.018, .012, .012),
                           dark, arm, {'head': 1.0}, col)

    vest_details = [
        ('Officer_VestSide.L', (-.205, 0, 1.27),
         (.055, .225, .30), .022, 'spine_02'),
        ('Officer_VestSide.R', (.205, 0, 1.27),
         (.055, .225, .30), .022, 'spine_02'),
        ('Officer_VestStrap.L', (-.125, -.015, 1.405),
         (.065, .075, .235), .024, 'spine_02'),
        ('Officer_VestStrap.R', (.125, -.015, 1.405),
         (.065, .075, .235), .024, 'spine_02'),
        ('Officer_MagPouch.L', (-.125, -.205, 1.19),
         (.092, .075, .145), .018, 'spine_01'),
        ('Officer_MagPouch.C', (0, -.205, 1.19),
         (.092, .075, .145), .018, 'spine_01'),
        ('Officer_MagPouch.R', (.125, -.205, 1.19),
         (.092, .075, .145), .018, 'spine_01'),
        ('Officer_Pouch.L', (-.235, -.075, .99),
         (.082, .075, .085), .018, 'pelvis'),
        ('Officer_Pouch.R', (.235, -.075, .99),
         (.082, .075, .085), .018, 'pelvis'),
        ('Officer_ShoulderPatch', (-.30, -.11, 1.40),
         (.10, .025, .075), .008, 'upper_arm.L'),
    ]
    for name, location, dimensions, bevel, bone in vest_details:
        material = pouch if 'Pouch' in name or 'Mag' in name else armor
        accessory = add_cube(name, location, dimensions, material, bevel, col)
        parent_keep_world(accessory, arm, bone)

    belt_mesh('Officer_Belt', armor, arm, col)

    attachments = [
        ('ATT_Officer_MainHand', (.155, -.405, 1.27), 'hand.R'),
        ('ATT_Officer_SupportHand', (.04, -.62, 1.34), 'hand.L'),
        ('ATT_Back', (0, .16, 1.35), 'spine_02'),
        ('ATT_Belt', (.27, -.10, 1.00), 'pelvis'),
    ]
    for name, location, bone in attachments:
        empty = bpy.data.objects.new(name, None)
        col.objects.link(empty)
        empty.location = location
        parent_keep_world(empty, arm, bone)
        empty['attachment'] = True

    weapon = bpy.data.objects.get('Equip_Carbine')
    if weapon:
        display = bpy.data.objects.new('SHOWCASE_Carbine', None)
        col.objects.link(display)
        parent_keep_world(display, arm, 'hand.R')
        display.matrix_world = Matrix.Translation(Vector((.08, -.42, 1.42)))
        display['exclude_from_asset_export'] = True
        parts = [obj for obj in asset_descendants(
            weapon) if obj.parent == weapon]
        for source in parts:
            instance = source.copy()
            instance.data = source.data if source.data else None
            col.objects.link(instance)
            instance.hide_render = False
            instance.parent = display
            instance.matrix_parent_inverse = Matrix.Identity(4)
            instance.matrix_local = source.matrix_local.copy()
            instance['exclude_from_asset_export'] = True
    return root


def build_carbine():
    c = collection('Equip_Carbine')
    root = bpy.data.objects.new('Equip_Carbine', None)
    c.objects.link(root)
    root['asset_type'] = 'equipment'
    metal = mat('MAT_Weapon_Metal', (.08, .10, .11, 1), .5, .4)
    polymer = mat('MAT_Weapon_Polymer', (.025, .03, .035, 1), .05, .7)
    stock_pad = mat('MAT_Weapon_StockPad', (.015, .02, .024, 1), .02, .82)
    parts = [
        add_cube('Carbine_Receiver', (0, 0, 0),
                 (.14, .34, .125), metal, .025, c),
        add_cube('Carbine_UpperReceiver', (0, -.015, .066),
                 (.105, .31, .035), polymer, .012, c),
        add_cube('Carbine_Stock', (0, .275, -.012),
                 (.105, .28, .09), polymer, .018, c),
        add_cube('Carbine_StockCheek', (0, .275, .042),
                 (.078, .22, .025), polymer, .012, c),
        add_cube('Carbine_StockPad', (0, .418, -.012),
                 (.115, .035, .105), stock_pad, .012, c),
        add_cube('Carbine_Handguard', (0, -.245, .005),
                 (.112, .39, .095), polymer, .025, c),
        add_cube('Carbine_HandguardRail', (0, -.245, .062),
                 (.038, .37, .018), metal, .006, c),
        add_cube('Carbine_Grip', (.075, .015, -.15),
                 (.078, .11, .19), polymer, .018, c),
        add_cube('Carbine_Magazine', (-.005, -.025, -.19),
                 (.09, .13, .21), metal, .014, c),
        add_cylinder('Carbine_Barrel',
                     (0, -.29, .005), .018, .42, metal, c, 12),
        add_cylinder('Carbine_MuzzleDevice',
                     (0, -.486, .005), .025, .055, metal, c, 12),
        add_cube('Carbine_SightFront', (0, -.43, .105),
                 (.035, .035, .07), metal, .006, c),
        add_cube('Carbine_SightRear', (0, -.11, .105),
                 (.035, .035, .07), metal, .006, c),
    ]
    parts[9].rotation_euler.x = math.radians(90)
    parts[10].rotation_euler.x = math.radians(90)
    guard_vertices = [
        (.035, -.045, -.075), (.095, -.045, -.075),
        (.115, -.045, -.105), (.105, -.045, -.175),
        (.075, -.045, -.205), (.045, -.045, -.185),
        (.045, -.012, -.075), (.095, -.012, -.075),
        (.115, -.012, -.105), (.105, -.012, -.175),
        (.075, -.012, -.205), (.045, -.012, -.185),
    ]
    guard_faces = [
        (0, 1, 2, 3, 4, 5), (6, 11, 10, 9, 8, 7),
        (0, 6, 7, 1), (1, 7, 8, 2), (2, 8, 9, 3),
        (3, 9, 10, 4), (4, 10, 11, 5), (5, 11, 6, 0),
    ]
    guard_mesh = bpy.data.meshes.new('Carbine_TriggerGuard_Mesh')
    guard_mesh.from_pydata(guard_vertices, [], guard_faces)
    guard_mesh.update()
    guard = bpy.data.objects.new('Carbine_TriggerGuard', guard_mesh)
    c.objects.link(guard)
    assign_mat(guard, metal)
    parts.append(guard)
    for o in parts:
        parent_keep_world(o, root)
    for n, loc in [('ATT_Carbine_Muzzle', (0, -.50, .005)), ('ATT_Carbine_MainHand', (.075, .015, -.15)), ('ATT_Carbine_SupportHand', (-.04, -.20, -.08))]:
        e = bpy.data.objects.new(n, None)
        c.objects.link(e)
        e.location = loc
        parent_keep_world(e, root)
    for part in parts:
        part.hide_render = True
    return root


def build_room():
    col = collection('Env_QualityRoom')
    created_before = set(bpy.data.objects)
    concrete = mat('MAT_Concrete', (.32, .35, .38, 1), 0, .9)
    floor_mat = mat('MAT_ConcreteFloor', (.22, .25, .245, 1), 0, .88)
    floor_nodes = floor_mat.node_tree.nodes
    floor_links = floor_mat.node_tree.links
    floor_bsdf = floor_nodes.get('Principled BSDF')
    floor_noise = floor_nodes.new('ShaderNodeTexNoise')
    floor_noise.inputs['Scale'].default_value = 5.0
    floor_noise.inputs['Detail'].default_value = 2.0
    floor_ramp = floor_nodes.new('ShaderNodeValToRGB')
    floor_ramp.color_ramp.elements[0].color = (.16, .19, .185, 1)
    floor_ramp.color_ramp.elements[1].color = (.28, .30, .285, 1)
    floor_links.new(floor_noise.outputs['Fac'], floor_ramp.inputs['Fac'])
    floor_links.new(floor_ramp.outputs['Color'],
                    floor_bsdf.inputs['Base Color'])
    frame = mat('MAT_DoorFrame', (.20, .12, .07, 1), .1, .7)
    door_mat = mat('MAT_Door', (.12, .16, .18, 1), .2, .6)
    hardware = mat('MAT_DoorHardware', (.045, .055, .06, 1), .55, .4)
    camera_walls = collection('Env_CameraFacingWalls')
    upper = collection('Env_Upper')

    add_cube('Room_Floor', (0, 0, -.06), (6, 6, .12), floor_mat, .01, col)
    add_cube('Room_Wall_South', (0, -3, 1.5),
             (6, .20, 3), concrete, .02, camera_walls)
    add_cube('Room_Wall_East', (3, 0, 1.5), (.20, 6, 3), concrete, .02, col)
    add_cube('Room_Wall_West', (-3, 0, 1.5),
             (.20, 6, 3), concrete, .02, camera_walls)
    add_cube('Room_Wall_North_L', (-2.1, 3, 1.5),
             (1.8, .20, 3), concrete, .02, col)
    add_cube('Room_Wall_North_R', (2.1, 3, 1.5),
             (1.8, .20, 3), concrete, .02, col)
    add_cube('Room_Wall_North_Header', (0, 3, 2.71),
             (2.4, .20, .58), concrete, .02, upper)

    add_cube('DoorFrame_Left', (-1.24, 2.92, 1.21),
             (.12, .12, 2.42), frame, .015, col)
    add_cube('DoorFrame_Right', (1.24, 2.92, 1.21),
             (.12, .12, 2.42), frame, .015, col)
    add_cube('DoorFrame_Top', (0, 2.92, 2.38),
             (2.52, .12, .08), frame, .012, col)

    for side, center_x, width in (('L', -2.1, 1.8), ('R', 2.1, 1.8)):
        for level, z in (('Low', .18), ('High', 2.62)):
            add_cube(f'Room_NorthTrim_{side}_{level}',
                     (center_x, 2.86, z), (width, .07, .07),
                     frame, .012, col)
    for level, z in (('Low', .18), ('High', 2.62)):
        add_cube(f'Room_EastTrim_{level}',
                 (2.86, 0, z), (.07, 5.72, .07), frame, .012, col)

    for side, sign in (('L', -1), ('R', 1)):
        hinge_x = sign*1.18
        pivot = bpy.data.objects.new(f'DoorPivot_{side}', None)
        col.objects.link(pivot)
        pivot.location = (hinge_x, 2.84, .02)
        pivot['hinge'] = 'outside'
        pivot['axis'] = 'Z'
        pivot['doorway_clear_width_m'] = 2.36
        pivot['doorway_clear_height_m'] = 2.32
        for hinge_z in (.32, 1.18, 2.05):
            hinge = add_cylinder(
                f'DoorHinge_{side}_{int(hinge_z*100):03d}',
                (hinge_x, 2.89, hinge_z), .035, .16, hardware, col, 12)
            parent_keep_world(hinge, pivot)
        local_center_x = -sign*.585
        leaf = add_cube(f'DoorLeaf_{side}', (hinge_x+local_center_x, 2.84, 1.18),
                        (1.17, .08, 2.32), door_mat, .012, col)
        leaf.parent = pivot
        leaf.location = (local_center_x, 0, 1.16)
        handle_plate = add_cube(
            f'DoorHandlePlate_{side}', (hinge_x+local_center_x, 2.775, 1.12),
            (.115, .025, .19), hardware, .012, col)
        parent_keep_world(handle_plate, leaf)
        handle_bar = add_cube(
            f'DoorHandle_{side}',
            (hinge_x+local_center_x-sign*.015, 2.75, 1.13),
            (.13, .035, .028), hardware, .012, col)
        parent_keep_world(handle_bar, leaf)
        proxy = add_cube(f'Collision_Door_{side}', leaf.location,
                         (1.17, .08, 2.32), None, 0, col)
        proxy.parent = leaf
        proxy.location = (0, 0, 0)
        proxy.hide_render = True
        proxy.display_type = 'WIRE'
        proxy['collision_proxy'] = True

        clip = bpy.data.actions.new(f'Anim_Door_{side}')
        clip.use_fake_user = True
        clip['frame_start'] = 1
        clip['frame_end'] = 24
        clip['loop'] = False
        pivot.animation_data_create()
        pivot.animation_data.action = clip
        pivot.rotation_euler = (0, 0, 0)
        pivot.keyframe_insert('rotation_euler', frame=1, group='Door')
        pivot.rotation_euler.z = math.radians(-90 if side == 'L' else 90)
        pivot.keyframe_insert('rotation_euler', frame=24, group='Door')
        for curve in action_fcurves(clip):
            for key in curve.keyframe_points:
                key.interpolation = 'LINEAR'

    for name, location, dimensions in [
            ('Collision_Floor', (0, 0, -.06), (6, 6, .12)),
            ('Collision_Wall_South', (0, -3, 1.5), (6, .20, 3)),
            ('Collision_Wall_East', (3, 0, 1.5), (.20, 6, 3)),
            ('Collision_Wall_West', (-3, 0, 1.5), (.20, 6, 3)),
            ('Collision_Wall_North_L', (-2.1, 3, 1.5), (1.8, .20, 3)),
            ('Collision_Wall_North_R', (2.1, 3, 1.5), (1.8, .20, 3)),
            ('Collision_Wall_North_Header', (0, 3, 2.71), (2.4, .20, .58))]:
        proxy = add_cube(name, location, dimensions, None, 0, col)
        proxy.hide_render = True
        proxy.display_type = 'WIRE'
        proxy['collision_proxy'] = True

    add_cube('Room_Roof_Section', (0, 0, 3.1),
             (6, 6, .15), concrete, .01, upper)
    root = bpy.data.objects.new('Env_QualityRoom', None)
    col.objects.link(root)
    root['asset_type'] = 'environment'
    root['doorway_clear_width_m'] = 2.36
    root['doorway_clear_height_m'] = 2.32
    for obj in set(bpy.data.objects)-created_before-{root}:
        if obj.parent is None:
            parent_keep_world(obj, root)
    return root


def reset_pose(arm):
    for pose_bone in arm.pose.bones:
        pose_bone.rotation_mode = 'XYZ'
        pose_bone.location = (0, 0, 0)
        pose_bone.rotation_euler = (0, 0, 0)
        pose_bone.scale = (1, 1, 1)


def action(arm, name, frame_end, poses, loop=False):
    arm.animation_data_create()
    arm.animation_data.action = None
    reset_pose(arm)
    clip = bpy.data.actions.new(name)
    clip.use_fake_user = True
    clip['loop'] = loop
    clip['frame_start'] = 1
    clip['frame_end'] = frame_end
    arm.animation_data.action = clip
    for frame, pose in poses:
        reset_pose(arm)
        for bone_name, channels in pose.items():
            pose_bone = arm.pose.bones.get(bone_name)
            if not pose_bone:
                continue
            if isinstance(channels, dict):
                if 'location' in channels:
                    pose_bone.location = channels['location']
                if 'rotation' in channels:
                    pose_bone.rotation_euler = channels['rotation']
            else:
                pose_bone.rotation_euler = channels
        for pose_bone in arm.pose.bones:
            pose_bone.keyframe_insert(
                'location', frame=frame, group=pose_bone.name)
            pose_bone.keyframe_insert(
                'rotation_euler', frame=frame, group=pose_bone.name)
            pose_bone.keyframe_insert(
                'scale', frame=frame, group=pose_bone.name)
    for curve in action_fcurves(clip):
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
    return clip


def asset_descendants(root):
    result = []
    for obj in bpy.data.objects:
        parent = obj.parent
        while parent:
            if parent == root:
                result.append(obj)
                break
            parent = parent.parent
    return result


def evaluated_dimensions(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    points = []
    for obj in objects:
        if obj.type != 'MESH' or obj.get('exclude_from_asset_export'):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        points.extend(evaluated.matrix_world @ Vector(corner)
                      for corner in evaluated.bound_box)
    if not points:
        return [0.0, 0.0, 0.0]
    return [round(max(point[i] for point in points)-min(point[i] for point in points), 4)
            for i in range(3)]


def evaluated_triangle_count(objects):
    depsgraph = bpy.context.evaluated_depsgraph_get()
    count = 0
    for obj in objects:
        if obj.type != 'MESH' or obj.get('exclude_from_asset_export'):
            continue
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            count += len(mesh.loop_triangles)
        finally:
            evaluated.to_mesh_clear()
    return count


def mesh_component_count(mesh):
    neighbors = [set() for _ in mesh.vertices]
    for edge in mesh.edges:
        first, second = edge.vertices
        neighbors[first].add(second)
        neighbors[second].add(first)
    unseen = set(range(len(mesh.vertices)))
    components = 0
    while unseen:
        components += 1
        pending = [unseen.pop()]
        while pending:
            for neighbor in neighbors[pending.pop()]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    pending.append(neighbor)
    return components


def world_aabb(obj):
    bpy.context.view_layer.update()
    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
    points = [evaluated.matrix_world @ Vector(corner)
              for corner in evaluated.bound_box]
    return ([min(point[i] for point in points) for i in range(3)],
            [max(point[i] for point in points) for i in range(3)])


def validate(path):
    roots = {
        obj.name: obj for obj in bpy.data.objects if obj.get('asset_type')}
    structural = []
    visual = []

    def check(group, name, passed, details=None):
        group.append({'name': name, 'pass': bool(passed), 'details': details})

    check(structural, 'metric_units',
          bpy.context.scene.unit_settings.system == 'METRIC')
    expected_roots = {
        'Char_Officer': 'character',
        'Equip_Carbine': 'equipment',
        'Env_QualityRoom': 'environment',
    }
    for name, asset_type in expected_roots.items():
        root = roots.get(name)
        check(structural, 'asset_root_'+name,
              bool(root and root.get('asset_type') == asset_type))
    assets = {name: asset_descendants(roots[name]) if name in roots else []
              for name in expected_roots}
    char_objects = assets['Char_Officer']
    equip_objects = assets['Equip_Carbine']
    room_objects = assets['Env_QualityRoom']

    def has_asset_object(objects, name):
        return any(obj.name == name for obj in objects)

    check(structural, 'character_hand_attachments', all(
        has_asset_object(char_objects, name) for name in
        ('ATT_Officer_MainHand', 'ATT_Officer_SupportHand')))
    check(structural, 'weapon_attachments', all(
        has_asset_object(equip_objects, name) for name in
        ('ATT_Carbine_Muzzle', 'ATT_Carbine_MainHand',
         'ATT_Carbine_SupportHand')))
    muzzle = next((obj for obj in equip_objects
                   if obj.name == 'ATT_Carbine_Muzzle'), None)
    barrel = next((obj for obj in equip_objects
                   if obj.name == 'Carbine_Barrel'), None)
    muzzle_error = None
    barrel_forward = False
    if muzzle and barrel:
        barrel_tip = barrel.matrix_world @ Vector((0, 0, .21))
        muzzle_error = round(
            (muzzle.matrix_world.translation-barrel_tip).length, 4)
        barrel_axis = barrel.matrix_world.to_3x3() @ Vector((0, 0, 1))
        barrel_forward = barrel_axis.dot(Vector((0, -1, 0))) > .999
    check(structural, 'weapon_barrel_and_muzzle_alignment',
          muzzle_error is not None and muzzle_error <= .02 and barrel_forward,
          {'muzzle_tip_error_m': muzzle_error, 'faces_character_forward': barrel_forward})
    check(structural, 'door_pivots_and_proxies', all(
        has_asset_object(room_objects, name) for name in
        ('DoorPivot_L', 'DoorPivot_R', 'DoorLeaf_L', 'DoorLeaf_R',
         'Collision_Door_L', 'Collision_Door_R')))

    arm = bpy.data.objects.get('Rig_Officer')
    expected_actions = {
        'Anim_RifleReadyIdle', 'Anim_Walk_Forward',
        'Anim_StandToCrouch', 'Anim_CrouchIdle',
        'Anim_CrouchToStand', 'Anim_RifleRecoil',
    }
    check(structural, 'armature_and_sample_actions', bool(
        arm and expected_actions.issubset(
            {clip.name for clip in bpy.data.actions})))
    arm_lengths = {}
    if arm:
        for side in ('L', 'R'):
            arm_lengths[side] = {
                'upper_arm_m': round(arm.data.bones['upper_arm.'+side].length, 4),
                'forearm_m': round(arm.data.bones['forearm.'+side].length, 4),
            }
    balanced = bool(arm_lengths) and all(
        abs(values['upper_arm_m']-values['forearm_m']) <= .06
        for values in arm_lengths.values())
    balanced = balanced and all(
        abs(arm_lengths['L'][part]-arm_lengths['R'][part]) <= .06
        for part in ('upper_arm_m', 'forearm_m'))
    check(structural, 'balanced_arm_segment_lengths', balanced, arm_lengths)
    deforming = [obj for obj in char_objects if obj.type == 'MESH' and any(
        modifier.type == 'ARMATURE' for modifier in obj.modifiers)]
    check(structural, 'single_armature_skinning', bool(deforming) and all(
        obj.parent == arm and obj.parent_type != 'BONE' and obj.vertex_groups
        for obj in deforming), {'deforming_meshes': len(deforming)})
    display = bpy.data.objects.get('SHOWCASE_Carbine')
    check(structural, 'showcase_weapon_excluded_from_character_export', bool(
        display and display.parent == arm and
        display.get('exclude_from_asset_export')))

    action_metadata = {}
    missing_metadata = []
    loop_mismatches = []
    for clip in bpy.data.actions:
        frame_start = clip.get('frame_start')
        frame_end = clip.get('frame_end')
        try:
            actual_range = list(clip.frame_range)
        except (AttributeError, RuntimeError, TypeError):
            actual_range = []
        try:
            metadata_ok = (frame_start is not None and frame_end is not None and
                           float(frame_end) >= float(frame_start))
        except (TypeError, ValueError):
            metadata_ok = False
        action_metadata[clip.name] = {
            'metadata_range': [frame_start, frame_end] if metadata_ok else None,
            'actual_range': [round(value, 2) for value in actual_range],
            'loop': bool(clip.get('loop', False)),
            'metadata_valid': metadata_ok,
        }
        if not metadata_ok:
            missing_metadata.append(clip.name)
        if metadata_ok and clip.get('loop', False):
            for curve in action_fcurves(clip):
                keys = curve.keyframe_points
                if not keys or abs(keys[0].co.y-keys[-1].co.y) > 1e-4:
                    loop_mismatches.append(clip.name+':'+curve.data_path)
                    break
    check(structural, 'action_frame_metadata', not missing_metadata,
          {'missing_or_invalid': missing_metadata})
    check(structural, 'loop_endpoint_channels_match', not loop_mismatches,
          {'mismatched_channels': loop_mismatches})
    action_coverage = {}
    if arm:
        for name in expected_actions:
            clip = bpy.data.actions.get(name)
            start = clip.get('frame_start') if clip else None
            end = clip.get('frame_end') if clip else None
            curves = action_fcurves(clip) if clip else []
            action_coverage[name] = bool(curves and start is not None and
                                         end is not None and all(curve.keyframe_points and
                                                                 abs(curve.keyframe_points[0].co.x-start) < 1e-4 and
                                                                 abs(
                                                                     curve.keyframe_points[-1].co.x-end) < 1e-4
                                                                 for curve in curves))
    check(structural, 'explicit_action_start_end_channels',
          bool(action_coverage) and all(action_coverage.values()), action_coverage)

    old_frame = bpy.context.scene.frame_current
    proxy_errors = {}
    frame_collisions = []
    depsgraph = bpy.context.evaluated_depsgraph_get()

    def world_bvh(obj):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            vertices = [evaluated.matrix_world @ vertex.co
                        for vertex in mesh.vertices]
            polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
            return BVHTree.FromPolygons(vertices, polygons, epsilon=1e-5)
        finally:
            evaluated.to_mesh_clear()

    frame_bvhs = {
        name: world_bvh(bpy.data.objects[name])
        for name in ('DoorFrame_Left', 'DoorFrame_Right', 'DoorFrame_Top')
    }
    for frame in range(1, 25):
        bpy.context.scene.frame_set(frame)
        frame_errors = {}
        for side in ('L', 'R'):
            leaf = bpy.data.objects.get('DoorLeaf_'+side)
            proxy = bpy.data.objects.get('Collision_Door_'+side)
            if not leaf or not proxy:
                frame_errors[side] = None
                continue
            leaf_min, leaf_max = world_aabb(leaf)
            proxy_min, proxy_max = world_aabb(proxy)
            frame_errors[side] = max(
                abs(leaf_min[i]-proxy_min[i]) for i in range(3))+max(
                abs(leaf_max[i]-proxy_max[i]) for i in range(3))
            leaf_bvh = world_bvh(leaf)
            for frame_name, frame_bvh in frame_bvhs.items():
                if leaf_bvh.overlap(frame_bvh):
                    frame_collisions.append({
                        'frame': frame, 'leaf': leaf.name,
                        'frame_mesh': frame_name,
                    })
        proxy_errors[str(frame)] = frame_errors
    bpy.context.scene.frame_set(old_frame)
    proxies_aligned = all(error is not None and error <= .002
                          for values in proxy_errors.values()
                          for error in values.values())
    check(structural, 'door_proxy_alignment_full_swing', proxies_aligned,
          proxy_errors)
    check(structural, 'door_leaf_frame_clearance_full_swing',
          not frame_collisions, {'intersections': frame_collisions})

    char_main = next((obj for obj in char_objects
                      if obj.name == 'ATT_Officer_MainHand'), None)
    char_support = next((obj for obj in char_objects
                         if obj.name == 'ATT_Officer_SupportHand'), None)
    socket_errors = {}
    if display and char_main and char_support:
        main_grip = display.matrix_world @ Vector((.075, .015, -.15))
        support_grip = display.matrix_world @ Vector((-.04, -.20, -.08))
        socket_errors = {
            'main_hand_m': round(
                (char_main.matrix_world.translation-main_grip).length, 4),
            'support_hand_m': round(
                (char_support.matrix_world.translation-support_grip).length, 4),
        }
    check(structural, 'two_hand_weapon_grip_alignment', bool(socket_errors) and
          all(value <= .035 for value in socket_errors.values()), socket_errors)

    asset_meshes = {
        'Char_Officer': char_objects,
        'Equip_Carbine': equip_objects,
        'Env_QualityRoom': room_objects,
    }
    dimensions = {name: evaluated_dimensions(objects)
                  for name, objects in asset_meshes.items()}
    targets = {
        'Char_Officer': ([.92, .95, 1.82], [.28, .35, .08]),
        'Equip_Carbine': ([.14, .93, .44], [.05, .15, .06]),
        'Env_QualityRoom': ([6.2, 6.2, 3.30], [.15, .15, .12]),
    }
    for name, (target, tolerance) in targets.items():
        measured = dimensions[name]
        within = all(abs(measured[i]-target[i]) <= tolerance[i]
                     for i in range(3))
        check(visual, 'dimensions_'+name, within, {
            'target_m': target,
            'tolerance_m': tolerance,
            'measured_m': measured,
        })
    triangles = {name: evaluated_triangle_count(objects)
                 for name, objects in asset_meshes.items()}
    budgets = {'Char_Officer': 12000,
               'Equip_Carbine': 2000, 'Env_QualityRoom': 12000}
    check(visual, 'evaluated_triangle_budgets', all(
        0 < triangles[name] <= budgets[name] for name in triangles), {
            name: {'count': count, 'budget': budgets[name]}
            for name, count in triangles.items()
    })
    officer_uniform = bpy.data.objects.get('Officer_Uniform')
    uniform_components = (mesh_component_count(officer_uniform.data)
                          if officer_uniform else 0)
    check(structural, 'connected_uniform_surface', bool(
        officer_uniform and uniform_components == 1), {
            'mesh_object': officer_uniform.name if officer_uniform else None,
            'connected_face_components': uniform_components,
    })
    boot_dimensions = {}
    for side in ('L', 'R'):
        boot = bpy.data.objects.get('Officer_BootSole.'+side)
        bounds = world_aabb(boot) if boot else None
        boot_dimensions[side] = (
            [round(bounds[1][axis]-bounds[0][axis], 4)
             for axis in range(3)] if bounds else None)
    boots_in_range = all(dimensions and .28 <= dimensions[1] <= .31 and
                         .10 <= dimensions[0] <= .12
                         for dimensions in boot_dimensions.values())
    check(visual, 'boot_footprint_dimensions', boots_in_range,
          {'sole_dimensions_m': boot_dimensions,
           'target_length_m': [.28, .31], 'target_width_m': [.10, .12]})
    environment = roots.get('Env_QualityRoom')
    doorway = {
        'clear_width_m': environment.get('doorway_clear_width_m') if environment else None,
        'clear_height_m': environment.get('doorway_clear_height_m') if environment else None,
    }
    clear_width = doorway['clear_width_m']
    clear_height = doorway['clear_height_m']
    try:
        doorway_ok = bool(environment and clear_width is not None and
                          clear_height is not None and
                          abs(float(clear_width)-2.36) < .001 and
                          abs(float(clear_height)-2.32) < .001)
    except (TypeError, ValueError):
        doorway_ok = False
    check(visual, 'explicit_doorway_clearance', doorway_ok, doorway)

    all_checks = structural+visual
    data = {
        'blender': bpy.app.version_string,
        'structural_validation': {
            'status': 'passed' if all(item['pass'] for item in structural) else 'failed',
            'checks': structural,
        },
        'visual_quality_validation': {
            'status': 'passed' if all(item['pass'] for item in visual) else 'failed',
            'checks': visual,
            'human_visual_review': 'pending rendered inspection',
        },
        'unity_compatibility': {
            'status': 'not_tested_no_workspace_project',
            'reason': 'No Unity project metadata exists in this workspace; no Unity import was attempted.',
            'checks': ['Humanoid avatar mapping', 'animation playback',
                       'materials and import settings'],
        },
        'round_trip': {
            'status': 'not_run',
            'reason': 'run FBX export and clean-scene import verification',
        },
        'completion_status': 'pending_rendered_visual_review_and_round_trip',
        'passed': all(item['pass'] for item in all_checks),
        'dimensions_m': dimensions,
        'evaluated_triangle_counts': triangles,
        'officer_surface': {
            'connected_face_components': uniform_components,
            'boot_sole_dimensions_m': boot_dimensions,
        },
        'actions': action_metadata,
    }
    Path(path).write_text(json.dumps(data, indent=2), encoding='utf8')
    if not data['passed']:
        failures = [item['name'] for item in all_checks if not item['pass']]
        raise RuntimeError('Quality validation failed: '+', '.join(failures))
    return data


def create_preview_grid():
    ground = mat('MAT_ReviewGround', (.19, .22, .22, 1), 0, .92)
    lines = mat('MAT_ReviewGrid', (.095, .125, .13, 1), 0, .9)
    vertices = [(-1.3, -1.3, -.001), (1.3, -1.3, -.001),
                (1.3, 1.3, -.001), (-1.3, 1.3, -.001)]
    faces = [(0, 1, 2, 3)]
    material_indices = [0]
    for step in range(-12, 13):
        coordinate = step*.1
        for horizontal in (True, False):
            center = coordinate
            first = len(vertices)
            half = .0012
            if horizontal:
                vertices.extend(((-1.3, center-half, -.0005),
                                 (1.3, center-half, -.0005),
                                 (1.3, center+half, -.0005),
                                 (-1.3, center+half, -.0005)))
            else:
                vertices.extend(((center-half, -1.3, -.0005),
                                 (center+half, -1.3, -.0005),
                                 (center+half, 1.3, -.0005),
                                 (center-half, 1.3, -.0005)))
            faces.append((first, first+1, first+2, first+3))
            material_indices.append(1)
    mesh = bpy.data.meshes.new('ReviewGroundGrid_Mesh')
    mesh.from_pydata(vertices, [], faces)
    mesh.materials.append(ground)
    mesh.materials.append(lines)
    for polygon, material_index in zip(mesh.polygons, material_indices):
        polygon.material_index = material_index
    grid = bpy.data.objects.new('REVIEW_GroundGrid', mesh)
    bpy.context.scene.collection.objects.link(grid)
    return grid


def render_quality_previews(arm, output_dir, views=None):
    output_dir = Path(output_dir)
    animation_dir = output_dir/'animations'
    requested_views = set(views) if views else {
        'officer_front', 'officer_side', 'officer_three_quarter',
        'officer_boots_knees', 'officer_side_by_side', 'gameplay_angle',
        'door_closed', 'door_open', 'animations',
    }
    if 'animations' in requested_views:
        animation_dir.mkdir(parents=True, exist_ok=True)
    scene = bpy.context.scene
    camera = bpy.data.objects['SHOWCASE_Camera']
    environment = bpy.data.objects.get('Env_QualityRoom')
    room_objects = asset_descendants(environment) if environment else []
    character = bpy.data.objects.get('Char_Officer')
    character_objects = asset_descendants(character) if character else []
    room_visibility = {obj: obj.hide_render for obj in room_objects}
    collision_visibility = {
        obj: obj.hide_render for obj in bpy.data.objects
        if obj.get('collision_proxy')
    }
    character_visibility = {obj: obj.hide_render for obj in character_objects}
    old_camera = scene.camera
    old_frame = scene.frame_current
    old_size = (scene.render.resolution_x, scene.render.resolution_y,
                scene.render.resolution_percentage)
    old_filepath = scene.render.filepath
    old_camera_type = camera.data.type
    old_ortho_scale = camera.data.ortho_scale
    scene.render.resolution_x = 900
    scene.render.resolution_y = 900
    scene.render.resolution_percentage = 100
    scene.camera = camera
    previews = []
    door_light = None
    grid = create_preview_grid()

    def render(path, track=True):
        path.parent.mkdir(parents=True, exist_ok=True)
        for proxy in collision_visibility:
            proxy.hide_render = True
        scene.render.filepath = str(path)
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
        if track:
            previews.append(str(path.relative_to(ROOT)))

    def compose_pair(first_path, second_path, output_path):
        first = bpy.data.images.load(str(first_path), check_existing=False)
        second = bpy.data.images.load(str(second_path), check_existing=False)
        width, height = first.size
        first_pixels = array('f', [0.0])*(width*height*4)
        second_pixels = array('f', [0.0])*(width*height*4)
        first.pixels.foreach_get(first_pixels)
        second.pixels.foreach_get(second_pixels)
        combined = array('f', [0.0])*(width*height*8)
        row_size = width*4
        for row in range(height):
            source = row*row_size
            target = row*row_size*2
            combined[target:target+row_size] = \
                first_pixels[source:source+row_size]
            combined[target+row_size:target+row_size*2] = \
                second_pixels[source:source+row_size]
        sheet = bpy.data.images.new(
            'Officer_Standing_Crouched_Comparison', width*2, height, alpha=True)
        sheet.pixels.foreach_set(combined)
        sheet.file_format = 'PNG'
        sheet.filepath_raw = str(output_path)
        sheet.save()
        bpy.data.images.remove(first)
        bpy.data.images.remove(second)
        bpy.data.images.remove(sheet)
        previews.append(str(output_path.relative_to(ROOT)))

    try:
        for obj in room_objects:
            obj.hide_render = True
        grid.hide_render = False
        arm.animation_data.action = bpy.data.actions.get('Anim_RifleReadyIdle')
        scene.frame_set(1)
        view_specs = [
            ('officer_front', 'officer_front.png',
             (0, -4.2, 1.0), (0, 0, .93)),
            ('officer_side', 'officer_side.png',
             (4.0, 0, 1.0), (0, 0, .93)),
            ('officer_three_quarter', 'officer_three_quarter.png',
             (3.2, -3.2, 1.25), (0, -.05, .96)),
        ]
        for view_name, filename, location, target in view_specs:
            if view_name not in requested_views:
                continue
            camera.data.type = 'PERSP'
            camera.location = location
            point_camera(camera, target)
            render(output_dir/filename)

        if 'officer_boots_knees' in requested_views:
            arm.animation_data.action = bpy.data.actions.get('Anim_CrouchIdle')
            scene.frame_set(1)
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = 1.0
            camera.location = (1.2, -2.1, .72)
            point_camera(camera, (0, -.12, .35))
            render(output_dir/'officer_boots_knees.png')
            arm.animation_data.action = bpy.data.actions.get(
                'Anim_RifleReadyIdle')
            scene.frame_set(1)

        if 'officer_side_by_side' in requested_views:
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = 1.95
            camera.location = (4.0, 0, 1.0)
            point_camera(camera, (0, 0, .92))
            standing = animation_dir/'_standing_side.png'
            crouched = animation_dir/'_crouched_side.png'
            render(standing, track=False)
            arm.animation_data.action = bpy.data.actions.get('Anim_CrouchIdle')
            scene.frame_set(1)
            render(crouched, track=False)
            comparison = output_dir/'officer_standing_crouched.png'
            compose_pair(standing, crouched, comparison)
            standing.unlink(missing_ok=True)
            crouched.unlink(missing_ok=True)
            arm.animation_data.action = bpy.data.actions.get(
                'Anim_RifleReadyIdle')
            scene.frame_set(1)
            camera.data.type = 'PERSP'
            camera.data.ortho_scale = old_ortho_scale

        if 'officer_gameplay_distance' in requested_views:
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = 3.8
            camera.location = (2.8, -3.6, 6.5)
            point_camera(camera, (0, -.05, .86))
            render(output_dir/'officer_gameplay_distance.png')

        if 'gameplay_angle' in requested_views:
            for obj in room_objects:
                obj.hide_render = False
                if obj.name in {'Room_Roof_Section', 'Room_Wall_South',
                                'Room_Wall_West', 'Room_Floor'}:
                    obj.hide_render = True
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = 12.5
            camera.location = (0, -2.0, 14.0)
            point_camera(camera, (0, 0, 0))
            render(output_dir/'gameplay_angle.png')
            camera.data.type = old_camera_type
            camera.data.ortho_scale = old_ortho_scale

        door_views = [view for view in ('door_closed', 'door_open')
                      if view in requested_views]
        if door_views:
            grid.hide_render = True
            for obj in character_objects:
                obj.hide_render = True
            for obj in room_objects:
                obj.hide_render = False
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = 5.2
            camera.location = (3.4, 6.2, 2.35)
            point_camera(camera, (0, 2.82, 1.2))
            light_data = bpy.data.lights.new('Preview_Door_Neutral', 'AREA')
            light_data.energy = 1200
            light_data.color = (1, 1, 1)
            light_data.shape = 'DISK'
            light_data.size = 4.0
            door_light = bpy.data.objects.new(
                'Preview_Door_Neutral', light_data)
            scene.collection.objects.link(door_light)
            door_light.location = (2.0, 5.5, 3.8)
            point_camera(door_light, (0, 2.82, 1.2))
            for side, frame in (('closed', 1), ('open', 24)):
                if f'door_{side}' not in door_views:
                    continue
                camera.data.ortho_scale = 3.6 if side == 'closed' else 5.2
                scene.frame_set(frame)
                render(output_dir/f'door_{side}.png')

        if 'animations' in requested_views:
            grid.hide_render = False
            for obj in room_objects:
                obj.hide_render = True
            floor = bpy.data.objects.get('Room_Floor')
            if floor:
                floor.hide_render = True
            for obj in character_objects:
                obj.hide_render = False
            scene.render.resolution_x = 480
            scene.render.resolution_y = 480
            camera.data.type = 'ORTHO'
            camera.data.ortho_scale = 2.7
            camera.location = (2.7, -4.8, 2.05)
            point_camera(camera, (0, -.2, .93))
            for name in ('Anim_RifleReadyIdle', 'Anim_Walk_Forward',
                         'Anim_StandToCrouch', 'Anim_CrouchIdle',
                         'Anim_CrouchToStand', 'Anim_RifleRecoil'):
                clip = bpy.data.actions[name]
                arm.animation_data.action = clip
                start = int(clip['frame_start'])
                end = int(clip['frame_end'])
                if name in {'Anim_Walk_Forward', 'Anim_RifleRecoil'}:
                    frames = list(range(start, end+1))
                else:
                    step = max(1, math.ceil((end-start)/7))
                    frames = list(range(start, end+1, step))
                if frames[-1] != end:
                    frames.append(end)
                for frame in frames:
                    scene.frame_set(frame)
                    render(animation_dir/f'{name}_{frame:03}.png')
    finally:
        if door_light:
            light_data = door_light.data
            bpy.data.objects.remove(door_light, do_unlink=True)
            bpy.data.lights.remove(light_data)
        grid_mesh = grid.data
        bpy.data.objects.remove(grid, do_unlink=True)
        bpy.data.meshes.remove(grid_mesh)
        for obj, hidden in room_visibility.items():
            obj.hide_render = hidden
        for obj, hidden in collision_visibility.items():
            obj.hide_render = hidden
        for obj, hidden in character_visibility.items():
            obj.hide_render = hidden
        arm.animation_data.action = None
        reset_pose(arm)
        scene.frame_set(old_frame)
        scene.camera = old_camera
        camera.data.type = old_camera_type
        camera.data.ortho_scale = old_ortho_scale
        scene.render.resolution_x, scene.render.resolution_y, scene.render.resolution_percentage = old_size
        scene.render.filepath = old_filepath
    return previews


def set_pose_bone_segment(arm, bone_name, head, tail):
    bone = arm.data.bones[bone_name]
    start = Vector(head)
    end = Vector(tail)
    rest_direction = (bone.tail_local-bone.head_local).normalized()
    target_direction = (end-start).normalized()
    swing = rest_direction.rotation_difference(target_direction)
    rest_rotation = bone.matrix_local.to_3x3().to_quaternion()
    rotation = swing @ rest_rotation
    matrix = Matrix.Translation(start) @ rotation.to_matrix().to_4x4()
    arm.pose.bones[bone_name].matrix = matrix


def crouch_knee_target(hip, ankle, upper_length, lower_length):
    delta_y = ankle.y-hip.y
    delta_z = ankle.z-hip.z
    distance = math.hypot(delta_y, delta_z)
    distance = min(distance, upper_length+lower_length-1e-5)
    distance = max(distance, abs(upper_length-lower_length)+1e-5)
    along = (upper_length**2-lower_length**2+distance**2)/(2*distance)
    bend = math.sqrt(max(0.0, upper_length**2-along**2))
    direction_y = delta_y/distance
    direction_z = delta_z/distance
    knee_y = hip.y+along*direction_y+bend*direction_z
    knee_z = hip.z+along*direction_z-bend*direction_y
    return Vector((hip.x, knee_y, knee_z))


def author_crouch_pose(arm, pelvis_height, lean=.12):
    pelvis_drop = max(0.0, .82-pelvis_height)
    pelvis = (0, 0, pelvis_height)
    pelvis_tail = (0, 0, pelvis_height+.20)
    torso_angle = lean
    spine_one_tail = (0, -.25*math.sin(torso_angle),
                      pelvis_height+.20+.25*math.cos(torso_angle))
    spine_two_tail = (0, spine_one_tail[1]-.20*math.sin(torso_angle),
                      spine_one_tail[2]+.20*math.cos(torso_angle))
    set_pose_bone_segment(arm, 'pelvis', pelvis, pelvis_tail)
    bpy.context.view_layer.update()
    set_pose_bone_segment(arm, 'spine_01', pelvis_tail, spine_one_tail)
    bpy.context.view_layer.update()
    set_pose_bone_segment(arm, 'spine_02', spine_one_tail, spine_two_tail)
    bpy.context.view_layer.update()

    for side, sign in (('L', -1), ('R', 1)):
        hip = Vector((sign*(.12+pelvis_drop*.125),
                      -pelvis_drop*.104, pelvis_height))
        ankle = Vector((arm.data.bones['foot.'+side].head_local.x,
                        arm.data.bones['foot.'+side].head_local.y,
                        arm.data.bones['foot.'+side].head_local.z))
        upper_length = arm.data.bones['thigh.'+side].length
        lower_length = arm.data.bones['shin.'+side].length
        knee = crouch_knee_target(
            hip, ankle, upper_length, lower_length)
        set_pose_bone_segment(arm, 'thigh.'+side, hip, knee)
        bpy.context.view_layer.update()
        set_pose_bone_segment(arm, 'shin.'+side, knee, ankle)
        bpy.context.view_layer.update()
        foot_direction = (arm.data.bones['foot.'+side].tail_local -
                          arm.data.bones['foot.'+side].head_local)
        set_pose_bone_segment(
            arm, 'foot.'+side, ankle, ankle+foot_direction)
    bpy.context.view_layer.update()


def author_crouch_action(arm, name, frame_end, key_poses, loop=False):
    arm.animation_data_create()
    arm.animation_data.action = None
    reset_pose(arm)
    clip = bpy.data.actions.new(name)
    clip.use_fake_user = True
    clip['loop'] = loop
    clip['frame_start'] = 1
    clip['frame_end'] = frame_end
    arm.animation_data.action = clip
    for frame in range(1, frame_end+1):
        segment = next((index for index in range(len(key_poses)-1)
                        if key_poses[index][0] <= frame <=
                        key_poses[index+1][0]), len(key_poses)-2)
        first = key_poses[segment]
        second = key_poses[segment+1]
        amount = (frame-first[0])/(second[0]-first[0])
        amount = amount*amount*(3-2*amount)
        pelvis_height = first[1]+(second[1]-first[1])*amount
        lean = first[2]+(second[2]-first[2])*amount
        reset_pose(arm)
        author_crouch_pose(arm, pelvis_height, lean)
        for pose_bone in arm.pose.bones:
            pose_bone.keyframe_insert(
                'location', frame=frame, group=pose_bone.name)
            pose_bone.keyframe_insert(
                'rotation_euler', frame=frame, group=pose_bone.name)
            pose_bone.keyframe_insert(
                'scale', frame=frame, group=pose_bone.name)
    for curve in action_fcurves(clip):
        for key in curve.keyframe_points:
            key.interpolation = 'BEZIER'
            key.handle_left_type = 'AUTO_CLAMPED'
            key.handle_right_type = 'AUTO_CLAMPED'
    return clip


def build_animations(arm):
    neutral = {}
    walk_a = {
        'thigh.L': {'rotation': (.48, 0, 0)},
        'thigh.R': {'rotation': (-.48, 0, 0)},
        'shin.L': {'rotation': (-.22, 0, 0)},
        'shin.R': {'rotation': (.08, 0, 0)},
        'foot.L': {'rotation': (-.10, 0, 0)},
        'foot.R': {'rotation': (.10, 0, 0)},
    }
    walk_b = {
        'thigh.L': {'rotation': (-.48, 0, 0)},
        'thigh.R': {'rotation': (.48, 0, 0)},
        'shin.L': {'rotation': (.08, 0, 0)},
        'shin.R': {'rotation': (-.22, 0, 0)},
        'foot.L': {'rotation': (.10, 0, 0)},
        'foot.R': {'rotation': (-.10, 0, 0)},
    }
    recoil = {
        'spine_02': {'rotation': (-.10, 0, 0)},
        'upper_arm.L': {'rotation': (.035, 0, 0)},
        'upper_arm.R': {'rotation': (.06, 0, 0)},
        'forearm.L': {'rotation': (-.025, 0, 0)},
    }

    action(arm, 'Anim_RifleReadyIdle', 40,
           [(1, neutral), (20, {'spine_02': {'rotation': (0, .015, 0)}}),
            (40, neutral)], True)
    walk_clip = action(arm, 'Anim_Walk_Forward', 25,
                       [(1, walk_a), (13, walk_b), (25, walk_a)], True)
    arm.animation_data.action = walk_clip
    scene = bpy.context.scene
    frame_start = int(walk_clip['frame_start'])
    frame_end = int(walk_clip['frame_end'])
    period = frame_end-frame_start
    contact_height = .015
    centers = {side: {} for side in ('L', 'R')}
    sole_heights = {side: {} for side in ('L', 'R')}
    for frame in range(frame_start, frame_end+1):
        scene.frame_set(frame)
        for side in ('L', 'R'):
            bounds = world_aabb(bpy.data.objects['Officer_BootSole.'+side])
            centers[side][frame] = (
                (bounds[0][0]+bounds[1][0])*.5,
                (bounds[0][1]+bounds[1][1])*.5)
            sole_heights[side][frame] = bounds[0][2]

    def cycle_frame(frame):
        return frame_start+(frame-frame_start) % period

    for side in ('L', 'R'):
        planted_intervals = []
        for frame in range(frame_start+1, frame_end+1):
            previous = frame-1
            if max(sole_heights[side][previous], sole_heights[side][frame]) > contact_height:
                continue
            previous_xy = centers[side][previous]
            current_xy = centers[side][frame]
            if current_xy[1] <= previous_xy[1]:
                continue
            planted_intervals.append((previous, frame,
                                      current_xy[0]-previous_xy[0]))
        if not planted_intervals:
            continue

        offsets = {}
        first_contact = cycle_frame(planted_intervals[0][0])
        previous_offset = 0.0
        offsets[first_contact] = previous_offset
        for previous, current, lateral_delta in planted_intervals:
            previous_frame = cycle_frame(previous)
            current_frame = cycle_frame(current)
            previous_offset = offsets.get(previous_frame, previous_offset)
            previous_offset -= lateral_delta
            offsets[current_frame] = previous_offset

        last_contact = cycle_frame(planted_intervals[-1][1])
        release_frames = []
        frame = last_contact
        while True:
            frame = frame_start+(frame-frame_start+1) % period
            if frame == first_contact:
                break
            release_frames.append(frame)
        for index, frame in enumerate(release_frames, 1):
            offsets[frame] = previous_offset*(1-index/len(release_frames))

        foot = arm.pose.bones['foot.'+side]
        for frame in range(frame_start, frame_end+1):
            scene.frame_set(frame)
            foot.location.x = offsets.get(cycle_frame(frame), 0.0)
            foot.keyframe_insert(
                data_path='location', index=0, frame=frame, group='Walk Foot Plant')

    for curve in action_fcurves(walk_clip):
        for key in curve.keyframe_points:
            key.interpolation = 'LINEAR'
    author_crouch_action(
        arm, 'Anim_StandToCrouch', 16,
        [(1, .82, 0), (8, .70, .07), (16, .58, .12)])
    author_crouch_action(
        arm, 'Anim_CrouchIdle', 30,
        [(1, .58, .12), (15, .58, .095), (30, .58, .12)], True)
    author_crouch_action(
        arm, 'Anim_CrouchToStand', 16,
        [(1, .58, .12), (8, .70, .07), (16, .82, 0)])
    action(arm, 'Anim_RifleRecoil', 12,
           [(1, neutral), (4, recoil), (12, neutral)])
    arm.animation_data.action = None
    reset_pose(arm)
