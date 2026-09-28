$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$animationDir = Join-Path $repoRoot 'Previews/animations'
$statusPath = Join-Path $repoRoot 'Documentation/quality_sample_status.json'
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$specs = @(
    @{ Pattern = 'Anim_RifleReadyIdle_*.png'; Output = 'idle_review.gif' },
    @{ Pattern = 'Anim_Walk_Forward_*.png'; Output = 'walk_review.gif' },
    @{ Pattern = 'Anim_CrouchIdle_*.png'; Output = 'crouch_review.gif' },
    @{ Pattern = 'Anim_RifleRecoil_*.png'; Output = 'recoil_review.gif' }
)
$reviews = @()
foreach ($spec in $specs) {
    $frames = @(Get-ChildItem -LiteralPath $animationDir -Filter $spec.Pattern -File |
        Sort-Object { [int]($_.BaseName -replace '^.*_(\d+)$', '$1') })
    if ($frames.Count -lt 2) {
        throw "At least two sampled PNG frames are required for $($spec.Output)."
    }

    $outputPath = Join-Path $animationDir $spec.Output
    $encoder = [System.Windows.Media.Imaging.GifBitmapEncoder]::new()
    foreach ($framePath in $frames) {
        $bitmap = [System.Windows.Media.Imaging.BitmapImage]::new()
        $bitmap.BeginInit()
        $bitmap.CacheOption = [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
        $bitmap.CreateOptions = [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat
        $bitmap.UriSource = [Uri]::new($framePath.FullName)
        $bitmap.EndInit()
        $encoder.Frames.Add(
            [System.Windows.Media.Imaging.BitmapFrame]::Create($bitmap))
    }

    $stream = [System.IO.File]::Open(
        $outputPath, [System.IO.FileMode]::Create,
        [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $encoder.Save($stream)
    }
    finally {
        $stream.Dispose()
    }

    $check = [System.Windows.Media.Imaging.GifBitmapDecoder]::new(
        [Uri]::new($outputPath),
        [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat,
        [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad)
    $frameCount = $check.Frames.Count
    if ($frameCount -ne $frames.Count) {
        throw "$($spec.Output) has $frameCount frames; expected $($frames.Count)."
    }
    if ($frameCount -gt 0) {
        $reviews += [pscustomobject]@{
            path        = "Previews/animations/$($spec.Output)"
            frame_count = $frameCount
            width       = $check.Frames[0].PixelWidth
            height      = $check.Frames[0].PixelHeight
            size_bytes  = (Get-Item -LiteralPath $outputPath).Length
        }
    }
}

if (-not (Test-Path -LiteralPath $statusPath -PathType Leaf)) {
    throw 'Generate the quality sample before packaging animation previews.'
}
$status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
$status | Add-Member -NotePropertyName animation_reviews -NotePropertyValue $reviews -Force
$status | Add-Member -NotePropertyName preview_status -NotePropertyValue 'passed' -Force
$status | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $statusPath -Encoding utf8
$reviews | Format-Table -AutoSize
