# Asset manifest

This document records the intended deliverables, the planned structure, and the validation status for the modular asset pack.

## Build status

The generation scripts are provided, but no Blender exports were generated in this session because a Blender executable was not available in the runtime exposed to this task.

## Mission pack goals

- Top-down, readable silhouettes from angled camera
- low-poly stylized-realistic forms
- consistent 1 m construction grid
- shared humanoid rig and modular architecture
- first-mission warehouse with office and extraction context

## Character kit

| Asset | Purpose | Rig | Materials | Budget | Notes |
|---|---|---:|---:|---:|---|
| `Char_Officer_01` | Tactical officer | Shared humanoid | 3-5 shared | 2,500-5,000 tri | Estimate only |
| `Char_Officer_02` | Co-op variant | Shared humanoid | 3-5 shared | 2,500-5,000 tri | Estimate only |
| `Char_Suspect_01` | Armed suspect | Shared humanoid | 3-5 shared | 2,500-5,000 tri | Estimate only |
| `Char_Suspect_02` | Armed suspect variant | Shared humanoid | 3-5 shared | 2,500-5,000 tri | Estimate only |
| `Char_Civilian_01` | Hostage | Shared humanoid | 3-5 shared | 2,200-4,500 tri | Estimate only |
| `Char_Civilian_02` | Hostage variant | Shared humanoid | 3-5 shared | 2,200-4,500 tri | Estimate only |

## Equipment catalog

| Asset | Dimensions | Budget | Rig compatibility | Notes |
|---|---|---:|---:|---|
| `Equip_Carbine` | ~0.9 x 0.1 x 0.2 m | 200-500 tri | Hand socket | Estimate only |
| `Equip_Pistol` | ~0.3 x 0.1 x 0.2 m | 120-240 tri | Hand socket | Estimate only |
| `Equip_Shotgun` | ~0.9 x 0.15 x 0.2 m | 220-450 tri | Hand socket | Estimate only |
| `Equip_Shield` | ~0.6 x 0.8 x 0.1 m | 300-700 tri | Arm support | Estimate only |
| `Equip_Radio` | ~0.1 x 0.05 x 0.04 m | 40-100 tri | Belt slot | Estimate only |
| `Equip_Flashlight` | ~0.12 x 0.05 x 0.05 m | 50-120 tri | Weapon mount | Estimate only |
| `Equip_Breaching_Charge` | ~0.2 x 0.15 x 0.15 m | 80-180 tri | Hand slot | Estimate only |
| `Equip_DRone` | ~0.23 x 0.23 x 0.18 m | 180-350 tri | Attachment point | Estimate only |
| `Equip_Medical_Pouch` | ~0.15 x 0.1 x 0.08 m | 50-120 tri | Belt slot | Estimate only |

## Modular architecture

| Asset | Dimensions | Budget | Collision mesh | Notes |
|---|---|---:|---:|---|
| `Arch_FloorTile_3x3` | 3 x 3 m | 200-500 tri | Yes | Reusable tile |
| `Arch_Wall_3m` | 3 x 3 m | 150-350 tri | Yes | Exterior/interior wall |
| `Arch_Wall_6m` | 6 x 3 m | 250-500 tri | Yes | Long segment |
| `Arch_Corner_3m` | 3 x 3 m | 180-400 tri | Yes | Corner |
| `Arch_Doorway_3m` | 3 x 3 m | 180-420 tri | Yes | Door opening |
| `Arch_DoorFrame_3m` | 3 x 3 m | 150-350 tri | Yes | Separate frame |
| `Arch_Door_Single` | 1.1 x 2.1 m | 150-300 tri | Yes | Hinge pivot |
| `Arch_Door_Double` | 2.2 x 2.1 m | 250-500 tri | Yes | Side-by-side |
| `Arch_WindowWall_3m` | 3 x 3 m | 180-420 tri | Yes | Glass panel |
| `Arch_Shutter` | 3 x 3 m | 180-350 tri | Yes | Warehouse shutter |
| `Arch_Pillar_3m` | 0.5 x 3 m | 120-220 tri | Yes | Structural column |
| `Arch_Step_1m` | 0.3 x 1.0 m | 50-120 tri | Yes | Loading step |
| `Arch_Roof_Section_3m` | 3 x 3 m | 150-350 tri | Yes | Ceiling section |

## Prop pack

| Asset | Dimensions | Budget | Notes |
|---|---|---:|---|
| `Prop_Crate` | 0.6 x 0.6 x 0.6 m | 80-180 tri | 2 variants |
| `Prop_ShippingCarton` | 0.5 x 0.5 x 0.4 m | 60-140 tri | 2 variants |
| `Prop_Pallet` | 1.2 x 1.0 x 0.15 m | 120-220 tri | Wooden |
| `Prop_Shelf` | 1.8 x 0.45 x 0.75 m | 200-450 tri | Metal shelving |
| `Prop_Barrel` | 0.5 x 0.5 x 0.9 m | 100-220 tri | Metal/wood |
| `Prop_Desk` | 1.2 x 0.6 x 0.75 m | 180-350 tri | Office furniture |
| `Prop_Chair` | 0.5 x 0.5 x 0.9 m | 120-220 tri | Office |
| `Prop_Locker` | 0.5 x 0.6 x 1.8 m | 180-350 tri | Storage |
| `Prop_Sofa` | 1.8 x 0.8 x 0.9 m | 220-450 tri | Low poly |
| `Prop_Monitor` | 0.5 x 0.35 x 0.05 m | 80-180 tri | Screen and stand |
| `Prop_FireExtinguisher` | 0.15 x 0.15 x 0.5 m | 70-140 tri | Red cylinder |
| `Prop_Light_Pendant` | 0.2 x 0.2 x 0.8 m | 60-150 tri | Separate bulb |
| `Prop_Light_Wall` | 0.15 x 0.15 x 0.3 m | 50-110 tri | Wall mount |
| `Prop_Light_Fluorescent` | 1.5 x 0.15 x 0.12 m | 120-220 tri | Fixture |
| `Prop_SecurityCamera` | 0.15 x 0.15 x 0.1 m | 60-120 tri | Lens detail |
| `Prop_FuseBox` | 0.3 x 0.2 x 0.15 m | 60-120 tri | Panel |
| `Prop_Briefcase` | 0.35 x 0.2 x 0.1 m | 50-120 tri | Evidence |
| `Prop_ExtractionMarker` | 0.15 x 0.15 x 0.25 m | 60-150 tri | Marker |

## Animation catalog

The shared humanoid skeleton is intended to support the following named clips:

- `Anim_Idle`
- `Anim_Idle_Rifle`
- `Anim_Walk_Forward`
- `Anim_Run_Forward`
- `Anim_Strafe_Left`
- `Anim_Strafe_Right`
- `Anim_Walk_Backward`
- `Anim_Crouch_Idle`
- `Anim_Crouch_Walk`
- `Anim_Fire_Rifle`
- `Anim_Fire_Pistol`
- `Anim_Reload_Rifle`
- `Anim_Reload_Pistol`
- `Anim_Interact_Door`
- `Anim_Place_Breaching_Charge`
- `Anim_Hit_Reaction`
- `Anim_Collapse`
- `Anim_Kneel_Surrender`
- `Anim_Hostage_Cower`
- `Anim_Revive`

Loop status:
- Idle, walk, run, strafe, crouch, and hit reactions are intended as loops where appropriate
- door interaction, reload, firing recoil, revival, and charge placement are not intended as seamless loops unless explicitly authored that way
- rough first-pass clips should be labeled as such and treated as placeholders until reviewed in a real Blender session

## Notes on invalidated data

This manifest intentionally contains estimated triangle counts and design budgets. These are project planning values, not measured export results.

The following must be validated locally when Blender is available:
- actual mesh triangle counts
- actual UV layout
- exact bone weights
- proper rigid-body collision proxies
- armature import compatibility in Unity
- clip loop correctness
- pivot placement and scale in export
