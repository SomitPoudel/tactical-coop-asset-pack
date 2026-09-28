"""Shared Blender 3.6 LTS helpers for the tactical asset pack.

Run scripts from any working directory with Blender 3.6 LTS:
  blender -b --python Scripts/generate_quality_sample.py -- --validate
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Iterable

import bpy
from mathutils import Vector

BLENDER_MIN = (3, 6, 0)
ROOT = Path(__file__).resolve().parents[1]
DIRS = {n: ROOT / n for n in ("Characters", "Equipment", "Environment", "Animations", "Materials", "Textures", "Sources", "Previews", "Documentation")}


def ensure_runtime():
    v = bpy.app.version
    if v < BLENDER_MIN:
        raise RuntimeError(f"Blender 3.6 LTS or newer is required; found {bpy.app.version_string}")
    for p in DIRS.values(): p.mkdir(parents=True, exist_ok=True)


def cli_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser()
    p.add_argument("--validate", action="store_true")
    p.add_argument("--export", action="store_true")
    p.add_argument("--no-render", action="store_true")
    return p.parse_args(argv)


def clear_scene():
    bpy.ops.object.mode_set(mode='OBJECT') if bpy.context.object and bpy.context.object.mode != 'OBJECT' else None
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    for datablocks in (bpy.data.meshes, bpy.data.armatures, bpy.data.cameras, bpy.data.lights):
        for block in list(datablocks):
            if block.users == 0: datablocks.remove(block)


def setup_scene():
    clear_scene(); s = bpy.context.scene
    s.unit_settings.system = 'METRIC'; s.unit_settings.scale_length = 1.0
    s.render.engine = 'BLENDER_EEVEE_NEXT' if 'BLENDER_EEVEE_NEXT' in {i.identifier for i in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items} else 'BLENDER_EEVEE'
    s.render.resolution_x, s.render.resolution_y, s.render.resolution_percentage = 1280, 720, 100
    w = s.world or bpy.data.worlds.new('World'); s.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get('Background'); bg.inputs['Color'].default_value = (0.025, 0.035, 0.05, 1); bg.inputs['Strength'].default_value = 0.35
    bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, .5)); ref = bpy.context.object; ref.name = 'REF_1M_DO_NOT_EXPORT'; ref.hide_render = True
    bpy.ops.object.light_add(type='AREA', location=(3, -4, 6)); bpy.context.object.name = 'SHOWCASE_Key'; bpy.context.object.data.energy = 1000; bpy.context.object.data.size = 5
    bpy.ops.object.light_add(type='AREA', location=(-4, 2, 3)); bpy.context.object.name = 'SHOWCASE_Fill'; bpy.context.object.data.energy = 500; bpy.context.object.data.size = 4
    bpy.ops.object.camera_add(location=(6, -7, 5.5)); cam = bpy.context.object; cam.name = 'SHOWCASE_Camera'; cam.data.lens = 38; s.camera = cam
    point_camera(cam, (0, 0, 1.0))


def point_camera(obj, target): obj.rotation_euler = (Vector(target) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def collection(name):
    c = bpy.data.collections.get(name) or bpy.data.collections.new(name)
    if c.name not in bpy.context.scene.collection.children: bpy.context.scene.collection.children.link(c)
    return c


def move_to(obj, col):
    for c in list(obj.users_collection): c.objects.unlink(obj)
    col.objects.link(obj); return obj


def mat(name, color, metallic=0.0, roughness=.7, emission=None):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes = True
    bs = m.node_tree.nodes.get('Principled BSDF'); bs.inputs['Base Color'].default_value = (*color[:3], color[3] if len(color)>3 else 1)
    bs.inputs['Metallic'].default_value = metallic; bs.inputs['Roughness'].default_value = roughness
    if emission:
        if 'Emission Color' in bs.inputs: bs.inputs['Emission Color'].default_value = (*emission, 1); bs.inputs['Emission Strength'].default_value = 2
        elif 'Emission' in bs.inputs: bs.inputs['Emission'].default_value = (*emission, 1)
    return m


def assign_mat(o, m):
    o.data.materials.clear(); o.data.materials.append(m); return o


def add_cube(name, location, dimensions, material=None, bevel=.02, col=None):
    bpy.ops.mesh.primitive_cube_add(size=1, location=location); o=bpy.context.object; o.name=name; o.dimensions=dimensions
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        b=o.modifiers.new('Bevel','BEVEL'); b.width=bevel; b.segments=2
    if material: assign_mat(o, material)
    if col: move_to(o,col)
    return o


def add_cylinder(name, location, radius, depth, material=None, col=None, vertices=16):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=depth, location=location); o=bpy.context.object; o.name=name
    if material: assign_mat(o,material)
    if col: move_to(o,col)
    return o


def add_uv(name, location, scale, material=None, col=None):
    bpy.ops.mesh.primitive_uv_sphere_add(segments=20, ring_count=12, location=location); o=bpy.context.object; o.name=name; o.scale=scale; bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if material: assign_mat(o,material)
    if col: move_to(o,col)
    return o


def ground_pivot(o, z=0.0):
    bpy.context.view_layer.update(); minz=min((o.matrix_world @ Vector(c)).z for c in o.bound_box)
    o.location.z += z-minz; bpy.context.view_layer.update()
    o.select_set(True); bpy.context.view_layer.objects.active=o; bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
    o.select_set(False); return o


def parent_keep_world(o, parent, bone=None):
    world=o.matrix_world.copy(); o.parent=parent
    if bone: o.parent_type='BONE'; o.parent_bone=bone
    o.matrix_world=world


def create_humanoid_rig(name='Rig_Humanoid', col=None):
    bpy.ops.object.armature_add(enter_editmode=True, location=(0,0,0)); arm=bpy.context.object; arm.name=name; arm.data.name=name+'_Data'
    eb=arm.data.edit_bones
    for b in list(eb): eb.remove(b)
    specs={
      'root':((0,0,0),(0,0,.12),None), 'pelvis':((0,0,.82),(0,0,1.02),'root'),
      'spine_01':((0,0,1.02),(0,0,1.30),'pelvis'), 'spine_02':((0,0,1.30),(0,0,1.58),'spine_01'),
      'neck':((0,0,1.58),(0,0,1.76),'spine_02'), 'head':((0,0,1.76),(0,0,2.02),'neck'),
      'clavicle.L':((-.03,0,1.53),(-.20,0,1.53),'spine_02'), 'upper_arm.L':((-.20,0,1.53),(-.48,0,1.25),'clavicle.L'), 'forearm.L':((-.48,0,1.25),(-.72,0,1.10),'upper_arm.L'), 'hand.L':((-.72,0,1.10),(-.88,0,1.08),'forearm.L'),
      'clavicle.R':((.03,0,1.53),(.20,0,1.53),'spine_02'), 'upper_arm.R':((.20,0,1.53),(.48,0,1.25),'clavicle.R'), 'forearm.R':((.48,0,1.25),(.72,0,1.10),'upper_arm.R'), 'hand.R':((.72,0,1.10),(.88,0,1.08),'forearm.R'),
      'thigh.L':((-.12,0,.82),(-.16,0,.43),'pelvis'), 'shin.L':((-.16,0,.43),(-.16,0,.08),'thigh.L'), 'foot.L':((-.16,0,.08),(-.16,.22,.04),'shin.L'),
      'thigh.R':((.12,0,.82),(.16,0,.43),'pelvis'), 'shin.R':((.16,0,.43),(.16,0,.08),'thigh.R'), 'foot.R':((.16,0,.08),(.16,.22,.04),'shin.R')}
    bones={}
    for n,(h,t,p) in specs.items(): b=eb.new(n); b.head=h; b.tail=t; bones[n]=b; b.parent=bones.get(p)
    bpy.ops.object.mode_set(mode='OBJECT'); arm.data.display_type='BBONE'; arm.show_in_front=True
    if col: move_to(arm,col)
    return arm


def piece(name, loc, dims, material, arm, bone, col, skin=True):
    o=add_cube(name,loc,dims,material,.04,col); parent_keep_world(o,arm,bone)
    if skin:
        mod=o.modifiers.new('Armature_Deform','ARMATURE'); mod.object=arm
        vg=o.vertex_groups.new(name=bone); vg.add(list(range(len(o.data.vertices))),1.0,'REPLACE')
    return o


def build_officer(arm, variant='blue', root_name='Char_Officer'):
    c=collection(root_name); colors={'blue':(.12,.25,.38,1),'orange':(.42,.20,.08,1)}; cloth=mat('MAT_Officer_'+variant,colors.get(variant,colors['blue']),0,.8); armor=mat('MAT_Armor',(.20,.25,.29,1),.25,.5); dark=mat('MAT_Rubber',(.035,.045,.05,1),.1,.65); skin=mat('MAT_Skin',(.62,.38,.27,1),0,.75); accent=mat('MAT_Accent',(.65,.72,.76,1),.1,.55)
    root=bpy.data.objects.new(root_name,None); c.objects.link(root); root['asset_type']='character'; parent_keep_world(arm,root); arm.parent=root
    piece('Officer_Torso',(0,0,1.30),(.46,.28,.55),cloth,arm,'spine_01',c); piece('Officer_Plate',(0,-.16,1.38),(.40,.08,.32),armor,arm,'spine_02',c); piece('Officer_Pelvis',(0,0,.90),(.38,.25,.25),cloth,arm,'pelvis',c)
    piece('Officer_Thigh.L',(-.14,0,.62),(.20,.20,.40),cloth,arm,'thigh.L',c); piece('Officer_Thigh.R',(.14,0,.62),(.20,.20,.40),cloth,arm,'thigh.R',c); piece('Officer_Shin.L',(-.16,0,.25),(.16,.18,.34),dark,arm,'shin.L',c); piece('Officer_Shin.R',(.16,0,.25),(.16,.18,.34),dark,arm,'shin.R',c)
    piece('Officer_Boot.L',(-.16,.09,.06),(.22,.36,.14),dark,arm,'foot.L',c); piece('Officer_Boot.R',(.16,.09,.06),(.22,.36,.14),dark,arm,'foot.R',c)
    piece('Officer_UpperArm.L',(-.34,0,1.38),(.18,.18,.38),armor,arm,'upper_arm.L',c); piece('Officer_UpperArm.R',(.34,0,1.38),(.18,.18,.38),armor,arm,'upper_arm.R',c); piece('Officer_Forearm.L',(-.60,0,1.18),(.16,.16,.34),cloth,arm,'forearm.L',c); piece('Officer_Forearm.R',(.60,0,1.18),(.16,.16,.34),cloth,arm,'forearm.R',c)
    piece('Officer_Glove.L',(-.78,0,1.08),(.16,.16,.14),dark,arm,'hand.L',c); piece('Officer_Glove.R',(.78,0,1.08),(.16,.16,.14),dark,arm,'hand.R',c)
    piece('Officer_Head',(0,0,1.86),(.28,.25,.32),skin,arm,'head',c); piece('Officer_Helmet',(0,0,2.02),(.36,.32,.20),dark,arm,'head',c); piece('Officer_Belt',(0,0,1.00),(.52,.32,.10),accent,arm,'pelvis',c); piece('Officer_Pouch.L',(-.30,-.15,1.02),(.16,.12,.16),accent,arm,'pelvis',c); piece('Officer_Pouch.R',(.30,-.15,1.02),(.16,.12,.16),accent,arm,'pelvis',c)
    for n,loc,b in [('ATT_MainHand',(.78,0,1.08),'hand.R'),('ATT_SupportHand',(-.78,0,1.08),'hand.L'),('ATT_Back', (0,.16,1.35),'spine_02'),('ATT_Belt',(.30,-.15,1.02),'pelvis')]:
        e=bpy.data.objects.new(n,None); c.objects.link(e); e.location=loc; parent_keep_world(e,arm,b); e['attachment']=True
    return root


def build_carbine():
    c=collection('Equip_Carbine'); root=bpy.data.objects.new('Equip_Carbine',None); c.objects.link(root); root['asset_type']='equipment'; metal=mat('MAT_Weapon_Metal',(.08,.10,.11,1),.5,.4); polymer=mat('MAT_Weapon_Polymer',(.025,.03,.035,1),.05,.7)
    parts=[add_cube('Carbine_Receiver',(0,0,0),(.42,.11,.16),metal,.025,c),add_cube('Carbine_Stock',(-.38,0,.01),(.36,.10,.12),polymer,.03,c),add_cube('Carbine_Handguard',(.38,0,.01),(.38,.10,.12),polymer,.03,c),add_cube('Carbine_Grip',(.10,-.06,-.13),(.12,.11,.25),polymer,.025,c),add_cube('Carbine_Magazine',(.04,-.08,-.12),(.14,.07,.20),metal,.02,c),add_cylinder('Carbine_Barrel',(.72,0,.01),.025,.62,metal,c),add_cube('Carbine_SightFront',(.62,0,.12),(.04,.04,.08),metal,.01,c),add_cube('Carbine_SightRear',(.22,0,.12),(.04,.04,.08),metal,.01,c)]
    for o in parts: parent_keep_world(o,root)
    for n,loc in [('ATT_Muzzle',(1.03,0,.01)),('ATT_MainHand',(.10,-.06,-.02)),('ATT_SupportHand',(.40,0,-.02))]: e=bpy.data.objects.new(n,None); c.objects.link(e); e.location=loc; parent_keep_world(e,root)
    return root


def build_room():
    c=collection('Env_QualityRoom'); concrete=mat('MAT_Concrete',(.32,.35,.38,1),0,.9); frame=mat('MAT_DoorFrame',(.20,.12,.07,1),.1,.7); door_mat=mat('MAT_Door',(.12,.16,.18,1),.2,.6)
    add_cube('Room_Floor',(0,0,-.06),(6,6,.12),concrete,.01,c)
    # 3 m walls with a 2.4 m clear double doorway in the north wall.
    add_cube('Room_Wall_South',(0,-3,1.5),(6,.20,3),concrete,.02,c); add_cube('Room_Wall_East',(3,0,1.5),(.20,6,3),concrete,.02,c); add_cube('Room_Wall_West',(-3,0,1.5),(.20,6,3),concrete,.02,c)
    add_cube('Room_Wall_North_L',(-2.1,3,1.5),(1.8,.20,3),concrete,.02,c); add_cube('Room_Wall_North_R',(2.1,3,1.5),(1.8,.20,3),concrete,.02,c); add_cube('Room_Wall_North_Header',(0,3,2.75),(2.4,.20,.5),concrete,.02,c)
    add_cube('DoorFrame_Left',(-1.2,2.92,1.5),(.12,.30,3),frame,.02,c); add_cube('DoorFrame_Right',(1.2,2.92,1.5),(.12,.30,3),frame,.02,c); add_cube('DoorFrame_Top',(0,2.92,2.94),(2.52,.30,.12),frame,.02,c)
    for side,x in [('L',-1.17),('R',1.17)]:
        pivot=bpy.data.objects.new(f'DoorPivot_{side}',None); c.objects.link(pivot); pivot.location=(x,2.86,0); pivot['hinge']='outside'; pivot['axis']='Z'
        leaf=add_cube(f'DoorLeaf_{side}',(x+(0.58 if side=='L' else -0.58),2.84,1.4),(1.16,.10,2.8),door_mat,.025,c); parent_keep_world(leaf,pivot); leaf.location=(0.58 if side=='L' else -0.58,0,1.4)
        col=add_cube(f'Collision_Door_{side}',leaf.location,(1.16,.12,2.8),None,0,c); parent_keep_world(col,pivot); col.hide_render=True; col.display_type='WIRE'; col['collision_proxy']=True
        pivot.rotation_euler=(0,0,0); pivot.keyframe_insert('rotation_euler',frame=1); pivot.rotation_euler.z=math.radians(78 if side=='L' else -78); pivot.keyframe_insert('rotation_euler',frame=24)
    roof=add_cube('Room_Roof_Section',(0,0,3.1),(6,6,.15),concrete,.01,collection('Env_Upper'))
    return c


def action(arm,name,frame_end,poses,loop=False):
    a=bpy.data.actions.new(name); a.use_fake_user=True; a['loop']=loop; a['frame_start']=1; a['frame_end']=frame_end; arm.animation_data_create(); arm.animation_data.action=a
    for f,rot in poses:
        for bone_name,euler in rot.items():
            pb=arm.pose.bones.get(bone_name)
            if pb: pb.rotation_mode='XYZ'; pb.rotation_euler=euler; pb.keyframe_insert('rotation_euler',frame=f,group=bone_name)
    return a


def build_animations(arm):
    z={}; action(arm,'Anim_RifleReadyIdle',40,[(1,z),(20,{'spine_02':(0,.02,0)}),(40,z)],True)
    action(arm,'Anim_Walk_Forward',24,[(1,{'thigh.L':(.35,0,0),'thigh.R':(-.35,0,0),'shin.L':(-.2,0,0),'shin.R':(.2,0,0)}),(13,{'thigh.L':(-.35,0,0),'thigh.R':(.35,0,0),'shin.L':(.2,0,0),'shin.R':(-.2,0,0)}),(24,{'thigh.L':(.35,0,0),'thigh.R':(-.35,0,0)})],True)
    action(arm,'Anim_Run_Forward',16,[(1,{'thigh.L':(.65,0,0),'thigh.R':(-.65,0,0),'shin.L':(-.35,0,0),'shin.R':(.35,0,0)}),(9,{'thigh.L':(-.65,0,0),'thigh.R':(.65,0,0),'shin.L':(.35,0,0),'shin.R':(-.35,0,0)}),(16,{'thigh.L':(.65,0,0),'thigh.R':(-.65,0,0)})],True)
    action(arm,'Anim_CrouchIdle',30,[(1,{'thigh.L':(.65,0,0),'thigh.R':(.65,0,0),'shin.L':(-.8,0,0),'shin.R':(-.8,0,0),'spine_01':(.25,0,0)}),(30,{'thigh.L':(.65,0,0),'thigh.R':(.65,0,0),'shin.L':(-.8,0,0),'shin.R':(-.8,0,0),'spine_01':(.25,0,0)})],True)
    action(arm,'Anim_RifleRecoil',12,[(1,{}),(4,{'spine_02':(-.12,0,0),'upper_arm.L':(-.08,0,0),'upper_arm.R':(-.08,0,0)}),(12,{})])
    action(arm,'Anim_RifleReload',36,[(1,{}),(10,{'forearm.L':(0,-.7,0)}),(20,{'forearm.L':(0,-1.2,0)}),(28,{'forearm.L':(0,-.4,0)}),(36,{})])
    action(arm,'Anim_Downed',24,[(1,{}),(24,{'spine_01':(1.1,0,0),'thigh.L':(.8,0,0),'thigh.R':(.8,0,0),'shin.L':(-1.0,0,0),'shin.R':(-1.0,0,0)})])
    arm.animation_data.action=None


def bounds(objects):
    bpy.context.view_layer.update(); pts=[o.matrix_world @ Vector(c) for o in objects for c in o.bound_box]; return [round(max(p[i] for p in pts)-min(p[i] for p in pts),4) for i in range(3)] if pts else [0,0,0]


def validate(path):
    checks=[]; roots=[o for o in bpy.data.objects if o.get('asset_type')]
    checks.append({'name':'metric_units','pass':bpy.context.scene.unit_settings.system=='METRIC'})
    arm=bpy.data.objects.get('Rig_Officer'); checks.append({'name':'armature_and_actions','pass':bool(arm and len(bpy.data.actions)>=7)})
    checks.append({'name':'attachments','pass':all(bpy.data.objects.get(n) for n in ('ATT_Muzzle','ATT_MainHand','ATT_SupportHand'))})
    checks.append({'name':'door_pivots','pass':all(bpy.data.objects.get(n) and abs(bpy.data.objects[n].location.x)>1 for n in ('DoorPivot_L','DoorPivot_R'))})
    checks.append({'name':'quality_sample_roots','pass':len(roots)>=3})
    data={'blender':bpy.app.version_string,'checks':checks,'passed':all(x['pass'] for x in checks),'dimensions':{o.name:bounds([x for x in bpy.data.objects if x.parent==o or x==o]) for o in roots},'actions':{a.name:[a['frame_start'],a['frame_end'],a.get('loop',False)] for a in bpy.data.actions}}
    Path(path).write_text(json.dumps(data,indent=2),encoding='utf8');
    if not data['passed']: raise RuntimeError('Quality validation failed: '+', '.join(x['name'] for x in checks if not x['pass']))
    return data
