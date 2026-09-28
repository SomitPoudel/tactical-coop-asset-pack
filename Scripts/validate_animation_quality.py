"""Measure the four authored officer clips across every frame."""
import importlib
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

sys.path.insert(0, str(Path(__file__).resolve().parent))
common = importlib.import_module('blender_asset_pack_common')


ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT/'Documentation'/'animation_validation.json'
CLIPS = ('Anim_RifleReadyIdle', 'Anim_Walk_Forward',
         'Anim_CrouchIdle', 'Anim_RifleRecoil')
JOINT_PAIRS = tuple(
    (f'Officer_{upper}.{side}', f'Officer_{lower}.{side}')
    for side in ('L', 'R')
    for upper, lower in (('UpperArm', 'Forearm'), ('Thigh', 'Shin')))


def matrix_delta(first, second):
    return max(abs(first[row][column]-second[row][column])
               for row in range(4) for column in range(4))


def mesh_surface_gap(first, second, depsgraph):
    def world_mesh(obj):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        vertices = [evaluated.matrix_world @ vertex.co
                    for vertex in mesh.vertices]
        polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
        tree = BVHTree.FromPolygons(vertices, polygons, epsilon=1e-5)
        evaluated.to_mesh_clear()
        return vertices, tree

    first_vertices, first_tree = world_mesh(first)
    second_vertices, second_tree = world_mesh(second)
    distances = [second_tree.find_nearest(vertex)[3]
                 for vertex in first_vertices]
    distances.extend(first_tree.find_nearest(vertex)[3]
                     for vertex in second_vertices)
    return min(distance for distance in distances if distance is not None)


def run():
    scene = bpy.context.scene
    arm = bpy.data.objects['Rig_Officer']
    display = bpy.data.objects['SHOWCASE_Carbine']
    main_hand = bpy.data.objects['ATT_Officer_MainHand']
    support_hand = bpy.data.objects['ATT_Officer_SupportHand']
    checks = {}
    old_frame = scene.frame_current
    old_action = arm.animation_data.action
    old_slot = getattr(arm.animation_data, 'action_slot', None)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    for name in CLIPS:
        clip = bpy.data.actions[name]
        arm.animation_data.action = clip
        frames = {}
        start = int(clip['frame_start'])
        end = int(clip['frame_end'])
        for frame in range(start, end+1):
            scene.frame_set(frame)
            soles = [common.world_aabb(
                bpy.data.objects['Officer_BootSole.'+side]) for side in ('L', 'R')]
            main_grip = display.matrix_world @ Vector((.075, .015, -.15))
            support_grip = display.matrix_world @ Vector((-.04, -.20, -.08))
            joint_gaps = [mesh_surface_gap(
                bpy.data.objects[first], bpy.data.objects[second], depsgraph)
                for first, second in JOINT_PAIRS]
            frames[str(frame)] = {
                'sole_min_z_m': [round(bounds[0][2], 5) for bounds in soles],
                'sole_max_z_m': [round(bounds[1][2], 5) for bounds in soles],
                'main_hand_error_m': round(
                    (main_hand.matrix_world.translation-main_grip).length, 5),
                'support_hand_error_m': round(
                    (support_hand.matrix_world.translation-support_grip).length, 5),
                'pelvis_z_m': round(
                    (arm.matrix_world @ arm.pose.bones['pelvis'].matrix).translation.z, 5),
                'max_adjacent_joint_surface_gap_m': round(max(joint_gaps), 5),
            }
        all_frames = list(frames.values())
        checks[name] = {
            'frame_range': [start, end],
            'evaluated_frame_count': len(frames),
            'frames': frames,
            'max_foot_penetration_m': round(max(
                0.0, -min(min(frame['sole_min_z_m']) for frame in all_frames)), 5),
            'max_foot_float_m': round(max(
                max(frame['sole_min_z_m']) for frame in all_frames), 5),
            'max_main_hand_error_m': max(
                frame['main_hand_error_m'] for frame in all_frames),
            'max_support_hand_error_m': max(
                frame['support_hand_error_m'] for frame in all_frames),
            'max_adjacent_joint_surface_gap_m': max(
                frame['max_adjacent_joint_surface_gap_m']
                for frame in all_frames),
        }

    crouch_frames = checks['Anim_CrouchIdle']['frames']
    idle_frames = checks['Anim_RifleReadyIdle']['frames']
    crouch_drop = min(frame['pelvis_z_m'] for frame in crouch_frames.values()) - \
        idle_frames['1']['pelvis_z_m']
    checks['crouch_body_drop_m'] = round(crouch_drop, 5)
    loop_deltas = {}
    for name in ('Anim_RifleReadyIdle', 'Anim_Walk_Forward', 'Anim_CrouchIdle'):
        clip = bpy.data.actions[name]
        arm.animation_data.action = clip
        scene.frame_set(int(clip['frame_start']))
        start_matrices = {bone.name: bone.matrix_basis.copy()
                          for bone in arm.pose.bones}
        scene.frame_set(int(clip['frame_end']))
        loop_deltas[name] = round(max(
            matrix_delta(start_matrices[bone.name], bone.matrix_basis)
            for bone in arm.pose.bones), 6)
    recoil = bpy.data.actions['Anim_RifleRecoil']
    arm.animation_data.action = recoil
    scene.frame_set(int(recoil['frame_start']))
    recoil_start = {bone.name: bone.matrix_basis.copy()
                    for bone in arm.pose.bones}
    scene.frame_set(int(recoil['frame_end']))
    recoil_deltas = {bone.name: round(
        matrix_delta(recoil_start[bone.name], bone.matrix_basis), 6)
        for bone in arm.pose.bones}

    limits = {
        'maximum_main_hand_error_m': .035,
        'maximum_support_hand_error_m': .035,
        'maximum_foot_penetration_m': .01,
        'maximum_foot_float_m': .12,
        'maximum_adjacent_joint_surface_gap_m': .035,
        'minimum_crouch_body_drop_m': .10,
        'maximum_loop_endpoint_matrix_delta': .001,
        'maximum_recoil_endpoint_matrix_delta': .001,
    }
    failures = []
    for name in CLIPS:
        result = checks[name]
        if result['max_main_hand_error_m'] > limits['maximum_main_hand_error_m']:
            failures.append(name+':main_hand_alignment')
        if result['max_support_hand_error_m'] > limits['maximum_support_hand_error_m']:
            failures.append(name+':support_hand_alignment')
        if result['max_foot_penetration_m'] > limits['maximum_foot_penetration_m']:
            failures.append(name+':foot_penetration')
        if result['max_adjacent_joint_surface_gap_m'] > \
                limits['maximum_adjacent_joint_surface_gap_m']:
            failures.append(name+':joint_separation')
    if checks['Anim_Walk_Forward']['max_foot_float_m'] > limits['maximum_foot_float_m']:
        failures.append('Anim_Walk_Forward:foot_float')
    if crouch_drop > -limits['minimum_crouch_body_drop_m']:
        failures.append('Anim_CrouchIdle:body_not_lowered')
    if any(delta > limits['maximum_loop_endpoint_matrix_delta']
           for delta in loop_deltas.values()):
        failures.append('loop_endpoint_transforms')
    if max(recoil_deltas.values(), default=0) > limits['maximum_recoil_endpoint_matrix_delta']:
        failures.append('recoil_does_not_return')
    report = {
        'blender': bpy.app.version_string,
        'status': 'failed' if failures else 'passed',
        'human_visual_review': 'pending; frames were not visually inspected',
        'locomotion': {'in_place': True, 'intended_movement_speed_mps': 1.25},
        'checks': checks,
        'loop_endpoint_matrix_deltas': loop_deltas,
        'recoil_endpoint_matrix_deltas': recoil_deltas,
        'limits': limits,
        'failures': failures,
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding='utf8')
    scene.frame_set(old_frame)
    arm.animation_data.action = old_action
    if old_action and hasattr(arm.animation_data, 'action_slot'):
        arm.animation_data.action_slot = old_slot
    if failures:
        raise RuntimeError('Animation validation failed: '+', '.join(failures))
    print('ANIMATION_VALIDATION_OK', REPORT)


if __name__ == '__main__':
    run()
