# Quality Sample Completion Report

## Status

Commands ran in native Windows PowerShell 5.1 on Windows NT build `10.0.26200.0`, host `SOMIT`, in `C:\Users\poude\OneDrive\Documents\GitHub\tactical-coop-asset-pack`. This was not WSL or a container; VS Code remote-session markers were empty.

Blender 5.2.2 LTS is installed as the Microsoft Store package `BlenderFoundation.Blender` at `C:\Program Files\WindowsApps\BlenderFoundation.Blender_5.2.2.0_x64__ppwjx1n5r4v9t`. Directly running its `Blender\blender.exe` returned **Access is denied**. The package `blender-launcher.exe` returned 0 without running the script or creating files. I copied the 0.88 GB `Blender` program directory to `%LOCALAPPDATA%\Temp\BlenderCLI-5.2.2`; the executable there ran successfully as Blender 5.2.2 LTS.

The first real generation attempt exposed `AttributeError: 'Action' object has no attribute 'fcurves'` in Blender 5.2. The builder now handles both legacy F-curves and layered-action channel bags. The next validation run failed muzzle orientation, grip, and carbine dimension checks; the report recorded those values. A Blender transform probe showed `parent_keep_world()` captured stale matrices before dependency-graph updates. Updating the dependency graph before capture and after parenting fixed those failures. Generation and validation then passed. Visual review also revealed the standalone source carbine appearing at the officer's feet; its render visibility is now disabled while the independent export geometry remains available, and the two stills were regenerated.

| Check | Result | Evidence |
|---|---|---|
| Python syntax and editor diagnostics | Passed | Pylance diagnostics for the builder, generators, and exporter |
| No-render Blender generation and validation | Passed | Blender 5.2.2 LTS, exit code 0; `QUALITY_SAMPLE_OK True` |
| Structural and scripted quality checks | Passed | `Documentation/quality_validation.json`; muzzle error 0.000 m, hand-socket errors 0.000 m, door proxy AABB errors 0.000 m at frames 1 and 24 |
| Evaluated dimensions | Passed within configured tolerances | Officer 0.852 x 0.920 x 1.850 m; carbine 0.1875 x 0.9325 x 0.435 m; room 6.200 x 6.200 x 3.295 m |
| Evaluated triangle counts | Passed budgets | Officer 7,800; carbine 908; room 1,512 |
| Front and gameplay still rendering | Passed | Blender exit code 0; both 900 x 900 PNGs saved and visually reviewed |
| Duplicate standalone weapon in previews | Fixed and visually rechecked | Only the hand-held display instance is visible in the regenerated views |
| Animation playback/deformation review | Not run | No animation frames were rendered in this focused pass |
| FBX export and Blender round trip | Not run | Export was intentionally deferred |
| Unity avatar mapping and playback | Not run | No Unity project/runtime used |

Visual inspection confirms the carbine is held in the showcase pose and the duplicate source mesh no longer appears at the feet. The model is still a visibly procedural low-poly blockout: the straight-on view foreshortens the rifle, body/accessory forms remain angular, and the gameplay composition crops the upper doorway near the top edge. The renders are evidence of current appearance, not a claim that the requested final art quality has been achieved.

Generated files:

- `Sources/quality_sample.blend` (214,346 bytes)
- `Documentation/quality_validation.json` (7,203 bytes)
- `Documentation/quality_sample_status.json` (379 bytes)
- `Previews/officer_front.png` (834,550 bytes, 900 x 900)
- `Previews/gameplay_angle.png` (917,260 bytes, 900 x 900)

## PowerShell Run

The successful run used `%LOCALAPPDATA%\Temp\BlenderCLI-5.2.2\blender.exe`. From the repository root, repeat generation/validation first without rendering, then render only the two requested views. These commands do not export FBX files or render animation frames:

```powershell
$Blender = Join-Path $env:LOCALAPPDATA 'Temp\BlenderCLI-5.2.2\blender.exe'
& $Blender --background --python-exit-code 1 --python Scripts\generate_quality_sample.py -- --validate --no-render
if ($LASTEXITCODE -ne 0) { throw "Generation/validation failed: $LASTEXITCODE" }

& $Blender --background Sources\quality_sample.blend --python-exit-code 1 --python Scripts\generate_quality_sample.py -- --preview-only --preview-views officer_front gameplay_angle
if ($LASTEXITCODE -ne 0) { throw "Preview rendering failed: $LASTEXITCODE" }
```

## Scripted Targets

The validator measures evaluated mesh descendants, excluding the display-only weapon instance from the character dimensions. These are explicit targets and tolerances, not measured results:

| Asset | Target dimensions (m) | Per-axis tolerance (m) |
|---|---:|---:|
| Officer | 0.92 x 0.95 x 1.82 | 0.28 x 0.35 x 0.08 |
| Carbine | 0.14 x 0.93 x 0.44 | 0.05 x 0.15 x 0.06 |
| Room | 6.20 x 6.20 x 3.30 | 0.15 x 0.15 x 0.12 |

Evaluated triangle budgets are 12,000 for the officer, 2,000 for the carbine, and 12,000 for the room. The room declares a 2.36 m wide by 2.32 m high doorway. The four character clips are rifle-ready idle, in-place walk, crouch idle, and recoil; run, reload, and downed are deliberately deferred.

## Deferred Review

Animation playback and deformation still need dedicated review; this run intentionally did not render animation frames. FBX exports and clean-scene reimports were also deferred, as were Unity checks. Do not infer Unity compatibility from the Blender validation report.
