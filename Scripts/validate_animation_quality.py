"""Measure officer deformation, contacts and authored clips across every frame."""
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
         'Anim_StandToCrouch', 'Anim_CrouchIdle',
         'Anim_CrouchToStand', 'Anim_RifleRecoil')


def matrix_delta(first, second):
    return max(abs(first[row][column]-second[row][column])
               for row in range(4) for column in range(4))


def connected_component_count(mesh):
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


def skin_weight_report(obj):
    sums = []
    empty_vertices = 0
    maximum_influences = 0
    for vertex in obj.data.vertices:
        weights = [group.weight for group in vertex.groups]
        if not weights:
            empty_vertices += 1
            continue
        sums.append(sum(weights))
        maximum_influences = max(maximum_influences, len(weights))
    return {
        'vertex_count': len(obj.data.vertices),
        'empty_weight_vertices': empty_vertices,
        'maximum_influences_per_vertex': maximum_influences,
        'minimum_weight_sum': round(min(sums, default=0.0), 5),
        'maximum_weight_sum': round(max(sums, default=0.0), 5),
        'all_vertices_weighted': empty_vertices == 0,
    }


def run():
    scene = bpy.context.scene
    arm = bpy.data.objects['Rig_Officer']
    display = bpy.data.objects['SHOWCASE_Carbine']
    uniform = bpy.data.objects['Officer_Uniform']
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
        for frame in range(start, end+1):
            scene.frame_set(frame)
            bpy.context.view_layer.update()
            soles = [common.world_aabb(
                bpy.data.objects['Officer_BootSole.'+side]) for side in ('L', 'R')]
            main_grip = display.matrix_world @ Vector((.075, .015, -.15))
            support_grip = display.matrix_world @ Vector((-.04, -.20, -.08))
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
    checks['Anim_CrouchIdle']['minimum_pelvis_z_m'] = min(
        frame['pelvis_z_m'] for frame in crouch_frames.values())
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
        'maximum_planted_foot_drift_speed_mps': .10,
        'maximum_crouch_foot_float_m': .02,
        'minimum_crouch_pelvis_height_m': .50,
        'minimum_crouch_body_drop_m': .20,
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
    for name in ('Anim_StandToCrouch', 'Anim_CrouchIdle', 'Anim_CrouchToStand'):
        if checks[name]['max_foot_float_m'] > limits['maximum_crouch_foot_float_m']:
            failures.append(name+':feet_not_grounded')
    if checks['Anim_Walk_Forward']['max_foot_float_m'] > limits['maximum_foot_float_m']:
        failures.append('Anim_Walk_Forward:foot_float')
    if checks['Anim_Walk_Forward']['max_planted_foot_drift_speed_mps'] > \
            limits['maximum_planted_foot_drift_speed_mps']:
        failures.append('Anim_Walk_Forward:planted_foot_sliding')
    if crouch_drop > -limits['minimum_crouch_body_drop_m']:
        failures.append('Anim_CrouchIdle:body_not_lowered')
    if checks['Anim_CrouchIdle']['max_foot_float_m'] > \
            limits['maximum_crouch_foot_float_m']:
        failures.append('Anim_CrouchIdle:feet_not_grounded')
    if checks['Anim_CrouchIdle']['minimum_pelvis_z_m'] < \
            limits['minimum_crouch_pelvis_height_m']:
        failures.append('Anim_CrouchIdle:pelvis_too_low')
    transition_contacts = {
        name: checks[name]['max_foot_float_m']
        for name in ('Anim_StandToCrouch', 'Anim_CrouchToStand')}
    boot_dimensions = {}
    for side in ('L', 'R'):
        bounds = common.world_aabb(bpy.data.objects['Officer_BootSole.'+side])
        boot_dimensions[side] = [round(bounds[1][axis]-bounds[0][axis], 4)
                                 for axis in range(3)]
    boot_sizes_ok = all(
        .28 <= dimensions[1] <= .31 and .10 <= dimensions[0] <= .12
        for dimensions in boot_dimensions.values())
    if not boot_sizes_ok:
        failures.append('boot_dimensions_out_of_target')
    skin = skin_weight_report(uniform)
    components = connected_component_count(uniform.data)
    if components != 1:
        failures.append('uniform_surface_not_connected')
    if not skin['all_vertices_weighted'] or \
            abs(skin['minimum_weight_sum']-1.0) > .01 or \
            abs(skin['maximum_weight_sum']-1.0) > .01:
        failures.append('uniform_surface_skin_weights')
    if any(delta > limits['maximum_loop_endpoint_matrix_delta']
           for delta in loop_deltas.values()):
        failures.append('loop_endpoint_transforms')
    if max(recoil_deltas.values(), default=0) > limits['maximum_recoil_endpoint_matrix_delta']:
        failures.append('recoil_does_not_return')
    report = {
        'blender': bpy.app.version_string,
        'scene_fps': round(fps, 5),
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
        'uniform_surface': {
            'mesh_object': uniform.name,
            'connected_face_components': components,
            'skin_weights': skin,
        },
        'boot_dimensions_m': boot_dimensions,
        'transition_max_foot_float_m': transition_contacts,
        'crouch_pelvis_drop_m': round(crouch_drop, 5),
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
