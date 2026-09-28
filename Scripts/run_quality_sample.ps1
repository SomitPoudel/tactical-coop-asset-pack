param(
    [string]$BlenderPath
)

$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$statusPath = Join-Path $repoRoot 'Documentation/quality_sample_status.json'
$exportReportPath = Join-Path $repoRoot 'Documentation/export_validation.json'

function Find-Blender {
    if ($BlenderPath -and (Test-Path -LiteralPath $BlenderPath -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $BlenderPath).Path
    }
    if ($env:BLENDER_BIN -and (Test-Path -LiteralPath $env:BLENDER_BIN -PathType Leaf)) {
        return (Resolve-Path -LiteralPath $env:BLENDER_BIN).Path
    }
    $onPath = Get-Command blender -ErrorAction SilentlyContinue
    if ($onPath) {
        return $onPath.Source
    }
    $installRoots = @(
        (Join-Path $env:ProgramFiles 'Blender Foundation'),
        (Join-Path $env:LOCALAPPDATA 'Programs/Blender Foundation')
    )
    foreach ($root in $installRoots) {
        if (Test-Path -LiteralPath $root) {
            $candidate = Get-ChildItem -LiteralPath $root -Directory -ErrorAction SilentlyContinue |
                Sort-Object Name -Descending |
                ForEach-Object { Join-Path $_.FullName 'blender.exe' } |
                Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
                Select-Object -First 1
            if ($candidate) {
                return $candidate
            }
        }
    }
    throw 'Blender was not found. Pass -BlenderPath or set BLENDER_BIN.'
}

$blender = Find-Blender
Set-Location -LiteralPath $repoRoot
New-Item -ItemType Directory -Force -Path (Join-Path $repoRoot 'Documentation') | Out-Null
Remove-Item -LiteralPath $statusPath, $exportReportPath -Force -ErrorAction SilentlyContinue
& $blender --version | Select-Object -First 1
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $blender --background --python-exit-code 1 --python Scripts/generate_quality_sample.py -- --validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path -LiteralPath $statusPath -PathType Leaf)) {
    throw 'Generation exited without writing quality_sample_status.json.'
}

& $blender --background Sources/quality_sample.blend --python-exit-code 1 --python Scripts/export_to_unity.py -- --validate
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
if (-not (Test-Path -LiteralPath $exportReportPath -PathType Leaf)) {
    throw 'Export exited without writing export_validation.json.'
}
$exportReport = Get-Content -LiteralPath $exportReportPath -Raw | ConvertFrom-Json
if ($exportReport.export_status -ne 'passed') {
    throw 'FBX export validation did not pass.'
}
Write-Output 'Quality sample generated, rendered, validated, exported, and round-trip checked where supported.'