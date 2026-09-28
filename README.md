# Tactical Co-op Asset Pack

This repository contains procedural Blender assets for a stylized-realistic top-down tactical co-op game. The quality sample is focused on one rifle-equipped officer and a test room; broader inventory work remains secondary until this sample has been inspected in Blender.

## Scope

The longer-term goal is a reusable first-mission pack with:
- three humanoid character archetypes
- modular architecture for warehouse/office spaces
- original equipment and props
- basic rigged animations for a shared humanoid skeleton
- procedural generation scripts for Blender

## Important status

Blender and Unity are not available in the current editing environment. The scripts and launchers are implemented, but this revision has not produced or visually inspected binary assets. See [quality_sample_report.md](Documentation/quality_sample_report.md) for checks run and checks still pending.

## Required folder structure

- Characters/
- Equipment/
- Environment/
- Animations/
- Materials/
- Textures/
- Sources/
- Scripts/
- Previews/
- Documentation/

## Repository layout

- `Scripts/generate_quality_sample.py` — builds the quality sample: officer, carbine, and hinge-pivot doorway room.
- `Scripts/generate_full_pack.py` — an unfinished secondary prop-set generator; it is not the quality-sample acceptance path.
- `Scripts/blender_asset_pack_common.py` — shared helpers for scene setup, materials, and export.
- `Documentation/asset_manifest.md` — dimension, material, rig, and budget notes.
- `Documentation/limitations.md` — warnings, rough passes, and validation gaps.

## Local generation workflow

Install Blender 3.6 LTS or newer, then run the launcher for your shell from the repository root:

```bash
Scripts/run_quality_sample.sh
```

Windows PowerShell equivalent, with automatic detection through PATH and common install locations:

```powershell
.\Scripts\run_quality_sample.ps1
```

Set `BLENDER_BIN` or pass `-BlenderPath` for a custom install. The launcher checks Blender's process exit code and the generated validation/export reports. `generate_quality_sample.py -- --export` exports the three sample assets in the same Blender run.

## Output directories

The generation scripts write to:

- `Sources/`
- `Characters/`
- `Equipment/`
- `Environment/`
- `Animations/`
- `Previews/` — close officer views, gameplay angle, door states, and sampled animation frames after a Blender run
- `Materials/`
- `Textures/`

## Asset conventions

- 1-meter grid basis
- upright world orientation, +Z up in Blender, character forward is -Y
- consistent naming: `Char_Officer_01`, `Prop_Wall_3m`, `Anim_Idle`
- shared material palette for metal, concrete, wood, fabric, plastic, glass, emissive
- separate collision meshes labeled with `Collision_` postfix
- door pivot at hinge side with clearly defined local origin
- rigs use a shared humanoid skeleton with body, upper limbs, and lower limbs

## Notes for Unity import

The project uses Unity import conventions, so generated FBX/GLB exports should be checked in Unity for:
- correct scale
- armature import naming
- clip names
- root transforms
- material slots
- double-sided normals

This repo intentionally does not claim a tested Unity import because no Unity project or runtime is present in this session.

The `.blend`, `.fbx`, preview images, and measured validation reports are generated locally by the launcher. They are not present in this checkout because Blender is unavailable in the current environment.

## License

All content in this repository is original procedural work authored for the project. No paid assets, external generation APIs, or copied game content are included.
