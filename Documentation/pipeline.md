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
- `Previews/officer_front.png`, `officer_side.png`, `gameplay_angle.png`, `door_closed.png`, and `door_open.png`
- Sampled PNG frames under `Previews/animations/`
- `Documentation/quality_validation.json`, `export_validation.json`, and `quality_sample_status.json`

The validator measures evaluated mesh descendants and evaluated triangle counts. Dimension targets, tolerances, and current measured values are in `Documentation/quality_validation.json`. Full-frame officer motion checks are written separately to `Documentation/animation_validation.json` by `Scripts/validate_animation_quality.py`.

## Export Policy

The character FBX allowlist is `Anim_RifleReadyIdle`, `Anim_Walk_Forward`, `Anim_CrouchIdle`, and `Anim_RifleRecoil`. The room exports only `Anim_Door_L` and `Anim_Door_R`; the standalone carbine exports no actions. Showcase lights, cameras, reference geometry, and the officer's display-only rifle instance are excluded from asset FBX files. The exporter attempts clean-scene Blender reimports and records dimensions, hierarchy, and clip presence.

The FBX round-trip checker verifies imported dimensions, hierarchy, declared clips, and representative animated frames in Blender. Blender round trips are not Unity compatibility tests. Avatar mapping, materials, scale/import settings, and playback still need to be checked in a Unity project.
