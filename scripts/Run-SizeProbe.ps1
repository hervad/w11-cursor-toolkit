<#
.SYNOPSIS
  Size-probe sweep (VISUAL, interactive). Sets the probe cursor as "Normal Select", steps the pointer size,
  and asks you to type the number shown on the cursor. Appends to probe-results.csv.
  Run once per display scale (Settings > Display > Scale: 100/125/150/175/200/250/300%).
.DESCRIPTION
  Changes HKCU\Control Panel\Cursors\Arrow and the pointer size while it runs and restores both in a finally
  block (also on error / Ctrl+C), then verifies the registry matches the start (CursorState.ps1).
  Needs a real console: it uses Read-Host. Don't run it from a non-interactive host.
.EXAMPLE
  w11cursor probe --out probe
  .\Run-SizeProbe.ps1 -ProbeCur .\probe\size-probe.cur -Scale 150
#>
param(
  [Parameter(Mandatory)][string]$ProbeCur,
  [int[]]$Sliders = @(1, 2, 3, 4, 5, 7, 9, 15),
  [ValidateRange(100, 500)][int]$Scale      # display scale in %; omit to be asked
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\CursorState.ps1"
$probe = (Resolve-Path $ProbeCur).Path

if (-not $PSBoundParameters.ContainsKey('Scale')) {
  while ($true) {
    $answer = Read-Host 'Current display scale in % (whole number 100-500, e.g. 150)'
    $Scale = ConvertTo-ScalePercent $answer
    if ($null -ne $Scale) { break }
    Write-Host "  '$answer' is not a whole number between 100 and 500 - please try again."
  }
}

$state = Save-CursorState
Write-CursorBanner $state @(
  "Arrow (Normal Select) -> $probe",
  "pointer size (CursorBaseSize) -> $(($Sliders | ForEach-Object { 16 * ($_ + 1) }) -join ', ') px (sliders $($Sliders -join ', '))"
)
$rows = @()
try {
  foreach ($s in $Sliders) {
    $px = 16 * ($s + 1)
    Set-PointerSize $px
    Set-ItemProperty $script:CursorsKey -Name Arrow -Value $probe
    Update-SystemCursors
    $seen = Read-Host "Slider $s ($px px x $Scale%) - number shown on cursor (add '?' if blurry)"
    $rows += [pscustomobject]@{ scale = $Scale; slider = $s; base_px = $px
      expected = [math]::Min(256, [math]::Round($px * $Scale / 100)); shown = $seen }
  }
} catch {
  Write-Host "ERROR: $($_.Exception.Message)"   # never exit silently
  throw
} finally {
  Restore-CursorState $state
}
$rows | Format-Table
$rows | Export-Csv -Append -NoTypeInformation probe-results.csv
Write-Host "Appended $($rows.Count) row(s) to $(Join-Path (Get-Location) 'probe-results.csv')"
