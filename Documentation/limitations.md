# Limitations and validation gaps

## Unvalidated in this session

This task environment did not provide access to Blender or Unity. The following are therefore not validated here:

- mesh creation and export
- armature skinning and weights
- animation playback and loop correctness
- import into Unity
- triangle count verification
- UV check for overlaps
- material slot correctness
- scale comparison against a 1 m reference cube
- door pivot alignment in a final export

## Rough or placeholder areas

The procedural script intentionally prioritizes structure and conventions over final art polish. Some asset areas may need refinement after first local export:

- humanoid silhouette shaping may need further proportion tuning
- weapon silhouettes may need silhouette cleanup for readability
- door swing and hinge placement should be tested in a real scene
- light emissive materials should be validated for brightness and falloff
- civilian and suspect outfit silhouettes should be reviewed against the target readability requirements

## Safety and quality reminders

- Never overwrite unrelated project content
- Use relative paths from the repository root
- Keep material names consistent across files
- Keep all collision objects separate from visible meshes
- Use the 1 m grid as the design baseline
- Check armature naming with Unity import rules
- Prefer reusable materials and atlas-style texture use
