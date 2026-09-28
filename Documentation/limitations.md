# Quality Sample Limitations

The procedural officer, carbine, room, validation, preview, and export paths have been revised, but Blender is unavailable in the current environment. Geometry, skinning, poses, render quality, evaluated dimensions/triangle counts, FBX output, and Blender round trips remain unverified until the launcher runs successfully.

The automated visual-quality checks measure dimensions, triangle budgets, socket positions, and door proxy bounds. They cannot judge silhouette readability, surface intersections, believable foot contact, or deformation quality from rendered frames. Human visual review is still required.

## Deliberate Scope

- Only rifle-ready idle, in-place walk, crouch idle, and recoil are authored for this sample. Reload, run, and downed clips are deferred until these pass pose review.
- The walk uses authored alternating leg poses rather than IK; foot contact requires rendered playback review.
- The support hand is positioned to the handguard in the authored pose, without a runtime IK solver.
- Recoil and crouch use a compact shared skeleton and need deformation review around shoulders, elbows, hips, and knees.
- The face and helmet are low-poly procedural forms with restrained facial detail, not a finished hero-character sculpt.
- The carbine is a procedural blockout with a separate magazine; materials, small controls, and surface detailing remain sparse.
- The room has simple split-wall construction and box collision proxies. Gameplay use still needs door-clearance and collision review in-engine.

## Compatibility

FBX reimport into Blender, when the importer is available, is a format round-trip check only. Unity avatar mapping, import settings, materials, and animation playback have not been tested. UV quality, texture authoring, and material response are also outside the current sample checks.
