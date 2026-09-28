# Unity Handoff Notes

## Unity Availability

Unity import was not run. No Unity Hub executable or Unity editor was found at the paths recorded in `quality_sample_report.md`. Hub project registry entries point to three missing directories and do not constitute available projects. Nothing was installed and no project was created.

The Hub registry entries cite Unity `2022.3.41f1`; that editor was not found. To continue manually, install Unity Hub and a compatible editor, then open or create a project and identify its render pipeline. No render pipeline was available to inspect in this pass.

## Import Guidance

- Import the officer, carbine, and room FBXs into separate folders under `Assets/TacticalCoop/`.
- Begin with FBX scale factor 1.0 and compare imported dimensions with `quality_validation.json`; Unity scale has not been tested.
- Use Generic rig import pending avatar validation. Do not select or claim Humanoid unless Unity avatar mapping validates successfully.
- The carbine is a separate asset; attach it to the officer's `ATT_Officer_MainHand` socket in the Unity scene.
- The room contains `Anim_Door_L` and `Anim_Door_R`. Door playback and collision behavior were not tested in Unity.
- Objects named `Collision_*` are Blender collision proxies. Configure appropriate Unity colliders and disable their renderers after import; this has not been verified in-engine.
- Material definitions are procedural Blender materials. The pack has no generated texture maps or atlases. Assign project-compatible shaders and inspect material slots after import.
- Showcase-only lights, cameras, and the display-only rifle are excluded from the asset exports.

## Included Files

`Unity_Handoff_QualitySample.zip` contains:
- `Characters/Officer_Quality.fbx`
- `Equipment/Carbine_Quality.fbx`
- `Environment/QualityRoom.fbx`
- `Materials/README.md` and `Documentation/asset_manifest.md`
- `Documentation/pipeline.md`, `limitations.md`, and this import note
- `Documentation/quality_sample_report.md`
- `Documentation/quality_validation.json`
- `Documentation/animation_validation.json`
- `Documentation/export_validation.json`
- `Documentation/quality_sample_status.json`

Blender export and clean-scene reimport checks passed. Unity import warnings and failures were not collected because no Unity import occurred. Unity scale, materials, render-pipeline conversion, collision setup, clips, and avatars remain untested.
