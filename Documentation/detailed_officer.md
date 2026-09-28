# Detailed Officer Rebuild

This is an independent asset branch. It does not replace `Sources/quality_sample.blend`, `Characters/Officer_Quality.fbx`, or the existing quality-sample generator. Run `Scripts/run_detailed_officer.ps1` on Windows, or invoke Blender with `Scripts/generate_detailed_officer.py` from the repository root. Pass `--no-render` or `--no-export` after Blender's `--` separator for faster iteration.

## Deliverables

- Editable source: `Sources/officer_detailed.blend`
- FBX: `Characters/Officer_Detailed/Officer_Detailed_LOD0.fbx`, with LOD1 and LOD2 siblings
- PBR maps: `Textures/Officer_Detailed/`
- Still and sampled animation renders: `Previews/officer_detailed/`
- Measured counts and Blender/FBX status: `Documentation/detailed_officer_report.json`

The rig starts in a neutral A-pose, targets 1.84 m overall height, and keeps the established `ATT_Officer_MainHand`, `ATT_Officer_SupportHand`, `ATT_Back`, and `ATT_Belt` names. Editable source copies are kept separate from the exported LOD0 meshes. LOD1 and LOD2 are decimated variants with their own exports and measured evaluated triangle counts.

## Acceptance Status

Successful file generation, measured checks, and FBX round-trip are technical evidence only. The current rendered result was reviewed and is **not visually accepted** against the supplied realism target: garment/body surfaces are still too segmented and procedural, and face, folds, stitching, and equipment surface detail need a further art pass. Human review remains pending. No mobile-performance claim is made.

Known limitations: this procedural rebuild is not sculpted production retopology; garment pieces remain modular rather than a continuous retopologized clothing shell; texture maps are generated from procedural patterns rather than baked from a sculpt; the requested rifle model and final two-hand weapon contact are not part of this separate officer build; walk and crouch motion are authored keyframes, not mocap. Generated previews do not establish visual acceptance.