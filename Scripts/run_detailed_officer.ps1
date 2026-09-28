param(
    [string]$BlenderPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot

function Find-Blender {
    if ($BlenderPath -and (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $BlenderPath).Path
    }
    if ($env:BLENDER_BIN -and (Test-Path -LiteralPath $env:BLENDER_BIN -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $env:BLENDER_BIN).Path
    }
    $onPath = Get-Command blender -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    $roots = @(
        (Join-Path $env:ProgramFiles 'Blender Foundation'),
        (Join-Path $env:LOCALAPPDATA 'Programs/Blender Foundation'),
        (Join-Path $env:LOCALAPPDATA 'Temp')
    )
    foreach ($root in $roots) {
        if (Test-Path -LiteralPath $root) {
            $candidate = Get-ChildItem -LiteralPath $root -Filter blender.exe -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -First 1
            if ($candidate) { return $candidate.FullName }
        }
    }
    throw 'Blender was not found. Pass -BlenderPath or set BLENDER_BIN.'
}

$blender = Find-Blender
Set-Location -LiteralPath $repoRoot
& $blender --background --python-exit-code 1 --python Scripts/generate_detailed_officer.py --
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output 'Detailed officer source, previews, textures, LODs and FBX exports generated.'