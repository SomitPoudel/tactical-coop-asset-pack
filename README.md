# Tactical Co-op Asset Pack

This repository contains a procedural Blender-based asset pack for a stylized-realistic top-down tactical action game in a warehouse infiltration mission.

## Scope

The goal is to produce a reusable first-mission pack with:
- three humanoid character archetypes
- modular architecture for warehouse/office spaces
- original equipment and props
- basic rigged animations for a shared humanoid skeleton
- procedural generation scripts for Blender

## Important status

This environment does not expose a Blender runtime or Unity import pipeline for direct validation. As a result:
- no .blend, .fbx, .glb, .png, or Unity-imported files were generated in this session
- all Blender export steps remain runnable via the scripts below on a local machine with Blender installed
- no asset, animation or Unity import is claimed as tested here

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
- `Scripts/generate_full_pack.py` — generates the full reusable pack and writes an asset manifest.
- `Scripts/blender_asset_pack_common.py` — shared helpers for scene setup, materials, and export.
- `Documentation/asset_manifest.md` — dimension, material, rig, and budget notes.
- `Documentation/limitations.md` — warnings, rough passes, and validation gaps.

## Local generation workflow

1. Install Blender 3.6+ or 4.x.
2. Open a terminal in this repo.
3. Run:

```bash
blender --background --python Scripts/generate_quality_sample.py
blender --background --python Scripts/generate_full_pack.py
```

Or, from the Blender scripting workspace:

```python
import os
exec(open("Scripts/generate_full_pack.py").read())
```

## Output directories

The generation scripts write to:

- `Sources/`
- `Characters/`
- `Equipment/`
- `Environment/`
- `Animations/`
- `Previews/`
- `Materials/`
- `Textures/`

## Asset conventions

- 1-meter grid basis
- upright world orientation, +Z up in Blender, facing +Y for front-aim direction
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

## Files intentionally not generated here

Because the Blender runtime is unavailable in this environment, the following remain to be generated locally:
- all .blend source files
- all .fbx/.glb exports
- animation clip files
- preview renders
- Unity-imported validation results

## License

All content in this repository is original procedural work authored for the project. No paid assets, external generation APIs, or copied game content are included.
