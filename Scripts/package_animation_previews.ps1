$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path -Parent $PSScriptRoot
$animationDir = Join-Path $repoRoot 'Previews/animations'
$statusPath = Join-Path $repoRoot 'Documentation/quality_sample_status.json'
$animationReportPath = Join-Path $repoRoot 'Documentation/animation_validation.json'
$qualityReportPath = Join-Path $repoRoot 'Documentation/quality_validation.json'
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase
Add-Type -AssemblyName System.Drawing

$specs = @(
    @{ Pattern = 'Anim_RifleReadyIdle_*.png'; Output = 'idle_review.gif' },
    @{ Pattern = 'Anim_Walk_Forward_*.png'; Output = 'walk_review.gif' },
    @{ Pattern = 'Anim_StandToCrouch_*.png'; Output = 'stand_to_crouch_review.gif' },
    @{ Pattern = 'Anim_CrouchIdle_*.png'; Output = 'crouch_review.gif' },
    @{ Pattern = 'Anim_CrouchToStand_*.png'; Output = 'crouch_to_stand_review.gif' },
    @{ Pattern = 'Anim_RifleRecoil_*.png'; Output = 'recoil_review.gif' }
)

function Set-GifFrameDelays {
    param(
        [string]$Path,
        [byte[]]$DelaysCentiseconds,
        [switch]$Loop
    )

    $bytes = [System.IO.File]::ReadAllBytes($Path)
    if ($bytes.Length -lt 13 -or
        [System.Text.Encoding]::ASCII.GetString($bytes, 0, 3) -ne 'GIF') {
        throw "Invalid GIF output: $Path"
    }
    $position = 13
    $screenFlags = $bytes[10]
    if (($screenFlags -band 0x80) -ne 0) {
        $position += 3 * [int][Math]::Pow(2, ($screenFlags -band 0x07) + 1)
    }
    if ($Loop) {
        $loopExtension = [byte[]]::new(19)
        $loopExtension[0] = 0x21
        $loopExtension[1] = 0xFF
        $loopExtension[2] = 0x0B
        [System.Buffer]::BlockCopy(
            [System.Text.Encoding]::ASCII.GetBytes('NETSCAPE2.0'),
            0, $loopExtension, 3, 11)
        $loopExtension[14] = 0x03
        $loopExtension[15] = 0x01
        $loopExtension[16] = 0
        $loopExtension[17] = 0
        $loopExtension[18] = 0
        $expanded = [byte[]]::new($bytes.Length + $loopExtension.Length)
        [System.Buffer]::BlockCopy($bytes, 0, $expanded, 0, $position)
        [System.Buffer]::BlockCopy(
            $loopExtension, 0, $expanded, $position, $loopExtension.Length)
        [System.Buffer]::BlockCopy(
            $bytes, $position, $expanded, $position + $loopExtension.Length,
            $bytes.Length - $position)
        $bytes = $expanded
    }

    $delayOffsets = [System.Collections.Generic.List[int]]::new()
    $pendingDelayOffset = -1
    while ($position -lt $bytes.Length) {
        $marker = $bytes[$position]
        if ($marker -eq 0x3B) { break }
        if ($marker -eq 0x21) {
            if ($position + 1 -ge $bytes.Length) { throw 'Truncated GIF extension.' }
            $label = $bytes[$position + 1]
            if ($label -eq 0xF9) {
                if ($position + 7 -ge $bytes.Length -or $bytes[$position + 2] -ne 4) {
                    throw 'Invalid GIF Graphics Control Extension.'
                }
                $pendingDelayOffset = $position + 4
                $position += 8
            }
            else {
                $position += 2
                while ($position -lt $bytes.Length) {
                    $blockLength = $bytes[$position]
                    $position++
                    if ($blockLength -eq 0) { break }
                    $position += $blockLength
                }
            }
            continue
        }
        if ($marker -eq 0x2C) {
            if ($pendingDelayOffset -lt 0) {
                throw 'GIF image frame has no Graphics Control Extension.'
            }
            $delayOffsets.Add($pendingDelayOffset)
            $pendingDelayOffset = -1
            if ($position + 9 -ge $bytes.Length) { throw 'Truncated GIF image descriptor.' }
            $imageFlags = $bytes[$position + 9]
            $position += 10
            if (($imageFlags -band 0x80) -ne 0) {
                $position += 3 * [int][Math]::Pow(2, ($imageFlags -band 0x07) + 1)
            }
            if ($position -ge $bytes.Length) { throw 'Missing GIF LZW code size.' }
            $position++
            while ($position -lt $bytes.Length) {
                $blockLength = $bytes[$position]
                $position++
                if ($blockLength -eq 0) { break }
                $position += $blockLength
            }
            continue
        }
        throw "Unexpected GIF block marker 0x$($marker.ToString('X2'))."
    }

    if ($delayOffsets.Count -ne $DelaysCentiseconds.Count) {
        throw "GIF has $($delayOffsets.Count) control blocks for $($DelaysCentiseconds.Count) frames."
    }
    for ($index = 0; $index -lt $delayOffsets.Count; $index++) {
        $delay = [int]$DelaysCentiseconds[$index]
        $bytes[$delayOffsets[$index]] = [byte]($delay -band 0xFF)
        $bytes[$delayOffsets[$index] + 1] = [byte](($delay -shr 8) -band 0xFF)
    }
    [System.IO.File]::WriteAllBytes($Path, $bytes)

    $writtenBytes = [System.IO.File]::ReadAllBytes($Path)
    $verifiedDelays = [System.Collections.Generic.List[int]]::new()
    for ($index = 0; $index -lt $delayOffsets.Count; $index++) {
        $offset = $delayOffsets[$index]
        $actualDelay = [int]$writtenBytes[$offset] +
        256 * [int]$writtenBytes[$offset + 1]
        if ($actualDelay -le 0 -or $actualDelay -ne $DelaysCentiseconds[$index]) {
            throw "Saved GIF frame $index delay is $actualDelay cs; expected $($DelaysCentiseconds[$index]) cs."
        }
        $verifiedDelays.Add($actualDelay)
    }
    $hasLoopExtension = [System.Text.Encoding]::ASCII.GetString(
        $writtenBytes).Contains('NETSCAPE2.0')
    if ($Loop -and -not $hasLoopExtension) {
        throw 'Saved looping GIF is missing its NETSCAPE2.0 loop extension.'
    }
    return [pscustomobject]@{
        frame_count         = $delayOffsets.Count
        delays_centiseconds = $verifiedDelays.ToArray()
        has_loop_extension  = $hasLoopExtension
    }
}

function New-StanceTransitionReview {
    param(
        [string]$AnimationDirectory,
        [object]$QualityReport,
        [double]$SceneFps
    )

    $entries = [System.Collections.Generic.List[object]]::new()
    foreach ($clipName in @('Anim_StandToCrouch', 'Anim_CrouchToStand')) {
        $clipData = $QualityReport.actions.$clipName
        $clipStart = [int]$clipData.metadata_range[0]
        $clipEnd = [int]$clipData.metadata_range[1]
        $frames = @(Get-ChildItem -LiteralPath $AnimationDirectory `
                -Filter ($clipName + '_*.png') -File |
            Sort-Object { [int]($_.BaseName -replace '^.*_(\d+)$', '$1') })
        $sourceNumbers = @($frames | ForEach-Object {
                [int]($_.BaseName -replace '^.*_(\d+)$', '$1')
            })
        if ($frames.Count -lt 2 -or $sourceNumbers[0] -ne $clipStart -or
            $sourceNumbers[-1] -ne $clipEnd) {
            throw "$clipName samples do not span the authored clip range."
        }
        $firstSample = 0
        if ($clipName -eq 'Anim_CrouchToStand') {
            $firstSample = 1
        }
        for ($index = $firstSample; $index -lt $frames.Count; $index++) {
            if ($index -lt $frames.Count-1) {
                $duration = $sourceNumbers[$index+1]-$sourceNumbers[$index]
            }
            else {
                $duration = [Math]::Max(
                    1, $clipEnd-$sourceNumbers[$index]+1)
            }
            $entries.Add([pscustomobject]@{
                    path     = $frames[$index].FullName
                    duration = $duration
                })
        }
    }

    $delays = @()
    $exactCentiseconds = 0.0
    $roundedCentiseconds = 0
    foreach ($entry in $entries) {
        $exactCentiseconds += $entry.duration*100.0/$SceneFps
        $target = [int][Math]::Round(
            $exactCentiseconds, 0, [MidpointRounding]::AwayFromZero)
        $delays += $target-$roundedCentiseconds
        $roundedCentiseconds = $target
    }

    $outputPath = Join-Path $AnimationDirectory 'stance_transition_review.gif'
    $encoder = [System.Windows.Media.Imaging.GifBitmapEncoder]::new()
    for ($index = 0; $index -lt $entries.Count; $index++) {
        $bitmap = [System.Windows.Media.Imaging.BitmapImage]::new()
        $bitmap.BeginInit()
        $bitmap.CacheOption = [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
        $bitmap.CreateOptions = [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat
        $bitmap.UriSource = [Uri]::new($entries[$index].path)
        $bitmap.EndInit()
        $metadata = [System.Windows.Media.Imaging.BitmapMetadata]::new('gif')
        $metadata.SetQuery('/grctlext/Delay', [UInt16]$delays[$index])
        $metadata.SetQuery('/grctlext/Disposal', [Byte]2)
        $encoder.Frames.Add(
            [System.Windows.Media.Imaging.BitmapFrame]::Create(
                $bitmap, $null, $metadata, $null))
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
    $timing = Set-GifFrameDelays -Path $outputPath `
        -DelaysCentiseconds $delays
    $check = [System.Drawing.Image]::FromFile($outputPath)
    try {
        $frameCount = $check.GetFrameCount(
            [System.Drawing.Imaging.FrameDimension]::Time)
        $property = $check.GetPropertyItem(0x5100)
        if ($frameCount -ne $entries.Count -or
            $property.Value.Length -ne $frameCount*4 -or
            $timing.has_loop_extension) {
            throw 'Combined stance review GIF failed frame/timing verification.'
        }
        for ($index = 0; $index -lt $frameCount; $index++) {
            $actual = [int][BitConverter]::ToUInt32(
                $property.Value, $index*4)
            if ($actual -le 0 -or $actual -ne $delays[$index]) {
                throw "Combined stance GIF frame $index has invalid timing."
            }
        }
        return [pscustomobject]@{
            path               = 'Previews/animations/stance_transition_review.gif'
            frame_count        = $frameCount
            width              = $check.Width
            height             = $check.Height
            size_bytes         = (Get-Item -LiteralPath $outputPath).Length
            source_clips       = @('Anim_StandToCrouch', 'Anim_CrouchToStand')
            source_frame_numbers = @($entries | ForEach-Object {
                    [IO.Path]::GetFileNameWithoutExtension($_.path)
                })
            loops              = $false
            fps                = $SceneFps
            frame_delays_ms    = @($delays | ForEach-Object { $_*10 })
            duration_ms        = $roundedCentiseconds*10
        }
    }
    finally {
        $check.Dispose()
    }
}

$animationReport = Get-Content -LiteralPath $animationReportPath -Raw | ConvertFrom-Json
$qualityReport = Get-Content -LiteralPath $qualityReportPath -Raw | ConvertFrom-Json
$sceneFps = [double]$animationReport.scene_fps
if ($sceneFps -le 0) { throw 'Animation report has no valid authored scene FPS.' }
$reviews = @()
foreach ($spec in $specs) {
    $frames = @(Get-ChildItem -LiteralPath $animationDir -Filter $spec.Pattern -File |
        Sort-Object { [int]($_.BaseName -replace '^.*_(\d+)$', '$1') })
    if ($frames.Count -lt 2) {
        throw "At least two sampled PNG frames are required for $($spec.Output)."
    }
    $clipName = ($frames[0].BaseName -replace '_\d+$', '')
    $clipData = $qualityReport.actions.$clipName
    if (-not $clipData -or -not $clipData.metadata_range) {
        throw "No validated frame metadata exists for $clipName."
    }
    $clipStart = [int]$clipData.metadata_range[0]
    $clipEnd = [int]$clipData.metadata_range[1]
    $loop = [bool]$clipData.loop
    $sourceFrameNumbers = @($frames | ForEach-Object {
            if ($_.BaseName -notmatch '_(\d+)$') {
                throw "Could not parse source frame number: $($_.Name)"
            }
            [int]$Matches[1]
        })
    if ($sourceFrameNumbers[0] -ne $clipStart -or
        $sourceFrameNumbers[-1] -ne $clipEnd) {
        throw "$clipName preview samples do not span the authored frame range."
    }

    $droppedLoopEndpoint = $null
    if ($loop) {
        if ($clipData.loop -ne $true) {
            throw "$clipName loop endpoint channels did not validate."
        }
        $droppedLoopEndpoint = $sourceFrameNumbers[-1]
        $frames = @($frames | Select-Object -First ($frames.Count - 1))
        $sourceFrameNumbers = @($sourceFrameNumbers | Select-Object -First ($sourceFrameNumbers.Count - 1))
    }

    $frameDurations = @()
    for ($index = 0; $index -lt $frames.Count; $index++) {
        if ($index -lt $frames.Count - 1) {
            $duration = $sourceFrameNumbers[$index + 1] - $sourceFrameNumbers[$index]
        }
        elseif ($loop) {
            $duration = $clipEnd - $sourceFrameNumbers[$index]
        }
        else {
            $duration = [Math]::Max(1, $clipEnd - $sourceFrameNumbers[$index] + 1)
        }
        if ($duration -lt 1) { throw "$clipName has a nonpositive sample interval." }
        $frameDurations += $duration
    }

    $expectedDelays = @()
    $exactCentiseconds = 0.0
    $roundedCentiseconds = 0
    foreach ($duration in $frameDurations) {
        $exactCentiseconds += $duration * 100.0 / $sceneFps
        $roundedTarget = [int][Math]::Round(
            $exactCentiseconds, 0, [MidpointRounding]::AwayFromZero)
        $delay = $roundedTarget - $roundedCentiseconds
        if ($delay -lt 1) { throw "$clipName produced a zero-length GIF frame." }
        $expectedDelays += $delay
        $roundedCentiseconds = $roundedTarget
    }

    $outputPath = Join-Path $animationDir $spec.Output
    $encoder = [System.Windows.Media.Imaging.GifBitmapEncoder]::new()
    for ($index = 0; $index -lt $frames.Count; $index++) {
        $framePath = $frames[$index]
        $bitmap = [System.Windows.Media.Imaging.BitmapImage]::new()
        $bitmap.BeginInit()
        $bitmap.CacheOption = [System.Windows.Media.Imaging.BitmapCacheOption]::OnLoad
        $bitmap.CreateOptions = [System.Windows.Media.Imaging.BitmapCreateOptions]::PreservePixelFormat
        $bitmap.UriSource = [Uri]::new($framePath.FullName)
        $bitmap.EndInit()
        $metadata = [System.Windows.Media.Imaging.BitmapMetadata]::new('gif')
        $metadata.SetQuery('/grctlext/Delay', [UInt16]$expectedDelays[$index])
        $metadata.SetQuery('/grctlext/Disposal', [Byte]2)
        $encoder.Frames.Add(
            [System.Windows.Media.Imaging.BitmapFrame]::Create(
                $bitmap, $null, $metadata, $null))
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
    $encodedTiming = Set-GifFrameDelays `
        -Path $outputPath -DelaysCentiseconds $expectedDelays -Loop:$loop

    $check = [System.Drawing.Image]::FromFile($outputPath)
    $timeDimension = [System.Drawing.Imaging.FrameDimension]::Time
    $frameCount = $check.GetFrameCount($timeDimension)
    if ($frameCount -ne $frames.Count) {
        throw "$($spec.Output) has $frameCount frames; expected $($frames.Count)."
    }
    if ($encodedTiming.frame_count -ne $frameCount) {
        throw "$($spec.Output) has $frameCount image frames but $($encodedTiming.frame_count) timed control blocks."
    }
    $delayProperty = $check.GetPropertyItem(0x5100)
    if ($delayProperty.Value.Length -ne $frameCount * 4) {
        throw "$($spec.Output) does not expose one four-byte delay per frame."
    }
    $actualDelays = @()
    for ($index = 0; $index -lt $frameCount; $index++) {
        $actualDelay = [int][BitConverter]::ToUInt32(
            $delayProperty.Value, $index * 4)
        if ($actualDelay -le 0 -or
            $actualDelay -ne $encodedTiming.delays_centiseconds[$index]) {
            throw "$($spec.Output) frame $index decoder delay is $actualDelay cs; expected $($encodedTiming.delays_centiseconds[$index]) cs."
        }
        $actualDelays += $actualDelay
    }
    if ($frameCount -gt 0) {
        $durationFrameCount = ($frameDurations | Measure-Object -Sum).Sum
        $reviews += [pscustomobject]@{
            path                        = "Previews/animations/$($spec.Output)"
            frame_count                 = $frameCount
            width                       = $check.Width
            height                      = $check.Height
            size_bytes                  = (Get-Item -LiteralPath $outputPath).Length
            source_frame_numbers        = $sourceFrameNumbers
            dropped_loop_endpoint_frame = $droppedLoopEndpoint
            loops                       = $loop
            loop_extension              = $encodedTiming.has_loop_extension
            fps                         = $sceneFps
            frame_delays_ms             = @($actualDelays | ForEach-Object { $_ * 10 })
            duration_ms                 = $roundedCentiseconds * 10
            target_duration_ms          = [Math]::Round($durationFrameCount * 1000.0 / $sceneFps, 2)
        }
    }
    $check.Dispose()
}

$reviews += New-StanceTransitionReview `
    -AnimationDirectory $animationDir `
    -QualityReport $qualityReport `
    -SceneFps $sceneFps

if (-not (Test-Path -LiteralPath $statusPath -PathType Leaf)) {
    throw 'Generate the quality sample before packaging animation previews.'
}
$status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
$status | Add-Member -NotePropertyName animation_reviews -NotePropertyValue $reviews -Force
$status | Add-Member -NotePropertyName preview_status -NotePropertyValue 'passed' -Force
$status | ConvertTo-Json -Depth 100 | Set-Content -LiteralPath $statusPath -Encoding utf8
$reviews | Format-Table -AutoSize
