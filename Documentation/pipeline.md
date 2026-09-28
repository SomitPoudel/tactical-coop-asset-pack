# Quality Sample Pipeline

The supported runtime is Blender 3.6 LTS or newer; Blender 5.2.2 LTS is the current verified runtime. Run from the repository root:

```bash
Scripts/run_quality_sample.sh
```

Windows PowerShell, with discovery through `BLENDER_BIN`, PATH, and common install folders:

```powershell
.\Scripts\run_quality_sample.ps1
```

The launchers stop on Python failures, require generated status reports, and run export only after generation succeeds. Set `BLENDER_BIN` or pass `-BlenderPath` for a custom install. To generate and export from one Blender process, use `blender --background --python-exit-code 1 --python Scripts/generate_quality_sample.py -- --validate --export`.

## Outputs

- `Sources/quality_sample.blend`
- `Characters/Officer_Quality.fbx`, `Equipment/Carbine_Quality.fbx`, and `Environment/QualityRoom.fbx`
- `Previews/officer_front.png`, `officer_side.png`, `officer_three_quarter.png`, `officer_boots_knees.png`, `officer_standing_crouched.png`, `gameplay_angle.png`, `door_closed.png`, and `door_open.png`
- Matching officer before/after review views under `Previews/review/`
- Sampled PNG frames under `Previews/animations/`
- Seven compact animation GIFs under `Previews/animations/` in the Windows PowerShell workflow
- `Documentation/quality_validation.json`, `export_validation.json`, and `quality_sample_status.json`

The validator measures evaluated mesh descendants and evaluated triangle counts. Dimension targets, tolerances, and current measured values are in `Documentation/quality_validation.json`. Full-frame officer motion checks are written separately to `Documentation/animation_validation.json` by `Scripts/validate_animation_quality.py`; both standard launchers run it. The animation checks measure planted-foot drift, connected uniform topology, skin weights and boot dimensions. Numerical checks do not replace visual review of the rendered stills and GIFs.

## Export Policy

The character FBX allowlist is `Anim_RifleReadyIdle`, `Anim_Walk_Forward`, `Anim_StandToCrouch`, `Anim_CrouchIdle`, `Anim_CrouchToStand`, and `Anim_RifleRecoil`. The room exports only `Anim_Door_L` and `Anim_Door_R`; the standalone carbine exports no actions. Showcase lights, cameras, reference geometry, and the officer's display-only rifle instance are excluded from asset FBX files. The exporter attempts clean-scene Blender reimports and records dimensions, hierarchy, and clip presence.

The FBX round-trip checker verifies bind-pose dimensions, hierarchy, declared clips, and representative animated frames in Blender. Blender round trips are not Unity compatibility tests. No Unity project or editor was available for this pass; avatar mapping, materials, scale/import settings, collision setup, and playback remain untested. Do not claim Humanoid compatibility unless Unity avatar validation succeeds.
