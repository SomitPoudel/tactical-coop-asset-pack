"""Measure the four authored officer clips across every frame."""
import importlib
import json
import math
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
    (f'Officer_{upper}.{side}', f'Officer_{lower}.{side}',
     f'{joint}.{side}', f'Officer_{connector}.{side}')
    for side in ('L', 'R')
    for upper, lower, joint, connector in (
        ('UpperArm', 'Forearm', 'forearm', 'Elbow'),
        ('Thigh', 'Shin', 'shin', 'Knee')))


def matrix_delta(first, second):
    return max(abs(first[row][column]-second[row][column])
               for row in range(4) for column in range(4))


def joint_connector_coverage(segment, connector, seam_center, depsgraph,
                             radius=.12):
    def world_mesh(obj):
        evaluated = obj.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh()
        try:
            vertices = [evaluated.matrix_world @ vertex.co
                        for vertex in mesh.vertices]
            polygons = [tuple(polygon.vertices) for polygon in mesh.polygons]
            return vertices, BVHTree.FromPolygons(
                vertices, polygons, epsilon=1e-5)
        finally:
            evaluated.to_mesh_clear()

    segment_vertices, _ = world_mesh(segment)
    _, connector_tree = world_mesh(connector)
    nearby = [vertex for vertex in segment_vertices
              if (vertex-seam_center).length <= radius]
    sampled = sorted(nearby, key=lambda vertex: (
        vertex-seam_center).length)[:10]
    outside_gaps = []
    for vertex in sampled:
        location, normal, _, distance = connector_tree.find_nearest(vertex)
        if location is None:
            outside_gaps.append(None)
        elif (vertex-location).dot(normal) > 1e-6:
            outside_gaps.append(distance)
        else:
            outside_gaps.append(0.0)
    measured = [gap for gap in outside_gaps if gap is not None]
    return {
        'sample_radius_m': radius,
        'sampled_terminal_vertices': len(sampled),
        'connector_covered_vertex_count': sum(
            gap == 0.0 for gap in measured),
        'max_connector_separation_m': max(measured, default=None),
    }


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
    fps = scene.render.fps / scene.render.fps_base
    intended_speed = 1.25
    contact_height_limit = .015
    for name in CLIPS:
        clip = bpy.data.actions[name]
        arm.animation_data.action = clip
        frames = {}
        start = int(clip['frame_start'])
        end = int(clip['frame_end'])
        joint_seam_summary = {}
        for frame in range(start, end+1):
            scene.frame_set(frame)
            soles = [common.world_aabb(
                bpy.data.objects['Officer_BootSole.'+side]) for side in ('L', 'R')]
            main_grip = display.matrix_world @ Vector((.075, .015, -.15))
            support_grip = display.matrix_world @ Vector((-.04, -.20, -.08))
            joint_gaps = {}
            for first, second, joint_bone, connector_name in JOINT_PAIRS:
                seam_center = arm.matrix_world @ arm.pose.bones[joint_bone].head
                connector = bpy.data.objects[connector_name]
                joint_gaps[first+'__'+connector_name] = joint_connector_coverage(
                    bpy.data.objects[first], connector, seam_center, depsgraph)
                joint_gaps[second+'__'+connector_name] = joint_connector_coverage(
                    bpy.data.objects[second], connector, seam_center, depsgraph)
            for seam_name, seam_result in joint_gaps.items():
                gap = seam_result['max_connector_separation_m'] or 0.0
                summary = joint_seam_summary.get(seam_name)
                if summary is None or gap > summary['max_connector_separation_m']:
                    joint_seam_summary[seam_name] = {
                        **seam_result,
                        'max_connector_separation_m': round(gap, 5),
                        'worst_frame': frame,
                        'minimum_connector_covered_vertex_count':
                            seam_result['connector_covered_vertex_count'],
                    }
                else:
                    summary['minimum_connector_covered_vertex_count'] = min(
                        summary['minimum_connector_covered_vertex_count'],
                        seam_result['connector_covered_vertex_count'])
            frames[str(frame)] = {
                'sole_min_z_m': [round(bounds[0][2], 5) for bounds in soles],
                'sole_max_z_m': [round(bounds[1][2], 5) for bounds in soles],
                'sole_center_xy_m': [
                    [round((bounds[0][axis]+bounds[1][axis])*.5, 5)
                     for axis in range(2)] for bounds in soles],
                'main_hand_error_m': round(
                    (main_hand.matrix_world.translation-main_grip).length, 5),
                'support_hand_error_m': round(
                    (support_hand.matrix_world.translation-support_grip).length, 5),
                'pelvis_z_m': round(
                    (arm.matrix_world @ arm.pose.bones['pelvis'].matrix).translation.z, 5),
                'max_joint_seam_gap_m': round(max(
                    (gap['max_connector_separation_m'] or 0.0
                     for gap in joint_gaps.values())), 5),
            }
        all_frames = list(frames.values())
        planted_slides = {'L': [], 'R': []}
        if name == 'Anim_Walk_Forward':
            for previous_frame, current_frame in zip(all_frames, all_frames[1:]):
                for foot_index, side in enumerate(('L', 'R')):
                    if max(previous_frame['sole_min_z_m'][foot_index],
                           current_frame['sole_min_z_m'][foot_index]) > contact_height_limit:
                        continue
                    previous_xy = previous_frame['sole_center_xy_m'][foot_index]
                    current_xy = current_frame['sole_center_xy_m'][foot_index]
                    if current_xy[1] <= previous_xy[1]:
                        continue
                    dx = current_xy[0]-previous_xy[0]
                    dy = current_xy[1]-previous_xy[1]-intended_speed/fps
                    planted_slides[side].append(math.hypot(dx, dy)*fps)
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
            'max_joint_seam_gap_m': max(
                frame['max_joint_seam_gap_m']
                for frame in all_frames),
            'joint_seam_summary': joint_seam_summary,
        }
        if name == 'Anim_Walk_Forward':
            checks[name]['planted_foot_slide'] = {
                'contact_height_limit_m': contact_height_limit,
                'controller_speed_mps': intended_speed,
                'fps': round(fps, 5),
                'max_drift_speed_mps': {
                    side: round(max(values, default=0.0), 5)
                    for side, values in planted_slides.items()},
                'sampled_interval_count': {
                    side: len(values) for side, values in planted_slides.items()},
            }
            checks[name]['max_planted_foot_drift_speed_mps'] = max(
                max(values, default=0.0) for values in planted_slides.values())

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
        'maximum_joint_seam_gap_m': .035,
        'maximum_planted_foot_drift_speed_mps': .10,
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
        if result['max_joint_seam_gap_m'] > limits['maximum_joint_seam_gap_m']:
            failures.append(name+':joint_separation')
    if checks['Anim_Walk_Forward']['max_foot_float_m'] > limits['maximum_foot_float_m']:
        failures.append('Anim_Walk_Forward:foot_float')
    if checks['Anim_Walk_Forward']['max_planted_foot_drift_speed_mps'] > \
            limits['maximum_planted_foot_drift_speed_mps']:
        failures.append('Anim_Walk_Forward:planted_foot_sliding')
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
        'human_visual_review': 'pending; numerical checks do not establish visual quality',
        'locomotion': {
            'in_place': True,
            'intended_movement_speed_mps': intended_speed,
            'planted_contact_height_limit_m': contact_height_limit,
            'planted_phase_definition': (
                'both interval endpoint soles stay below the contact-height limit '
                'and sole-center motion is backward along +Y'),
            'planted_foot_drift_tolerance_mps': limits[
                'maximum_planted_foot_drift_speed_mps'],
        },
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
