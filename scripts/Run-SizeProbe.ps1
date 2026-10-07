<#
.SYNOPSIS
  Size-probe sweep. Sets the probe cursor as "Normal Select", steps the pointer size,
  and asks you to type the number shown on the cursor. Writes probe-results.csv.
  Run once per display scale (Settings > Display > Scale: 100/125/150/175/200/250/300%).
.EXAMPLE
  w11cursor probe --out probe          # (or copy size-probe.cur from a CI artifact)
  .\Run-SizeProbe.ps1 -ProbeCur .\probe\size-probe.cur
#>
param([Parameter(Mandatory)][string]$ProbeCur, [int[]]$Sliders = @(1, 2, 3, 4, 5, 7, 9, 15))
$ErrorActionPreference = 'Stop'
$probe = (Resolve-Path $ProbeCur).Path
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class W11Probe {
  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool SystemParametersInfoW(uint action, uint uiParam, IntPtr pvParam, uint winIni);
}
"@
$orig = (Get-ItemProperty 'HKCU:\Control Panel\Cursors').Arrow
$origSize = (Get-ItemProperty 'HKCU:\Control Panel\Cursors' -ErrorAction SilentlyContinue).CursorBaseSize
if (-not $origSize) { $origSize = 32 }   # value is absent until the slider is first moved; 32 = size 1
$scale = Read-Host "Current display scale in % (e.g. 150)"
$rows = @()
try {
  foreach ($s in $Sliders) {
    $px = 16 * ($s + 1)
    [void][W11Probe]::SystemParametersInfoW(0x2029, 0, [IntPtr]$px, 0x03)
    Set-ItemProperty 'HKCU:\Control Panel\Cursors' -Name Arrow -Value $probe
    [void][W11Probe]::SystemParametersInfoW(0x57, 0, [IntPtr]::Zero, 0x03)   # SPI_SETCURSORS: reload
    $seen = Read-Host "Slider $s ($px px x $scale%) - number shown on cursor (add '?' if blurry)"
    $rows += [pscustomobject]@{ scale = $scale; slider = $s; base_px = $px; expected = [math]::Min(256, [math]::Round($px * $scale / 100)); shown = $seen }
  }
} finally {
  Set-ItemProperty 'HKCU:\Control Panel\Cursors' -Name Arrow -Value $orig
  [void][W11Probe]::SystemParametersInfoW(0x2029, 0, [IntPtr][int]$origSize, 0x03)
  [void][W11Probe]::SystemParametersInfoW(0x57, 0, [IntPtr]::Zero, 0x03)
}
$rows | Format-Table
$rows | Export-Csv -Append -NoTypeInformation probe-results.csv
Write-Host "Appended to probe-results.csv - commit it to w11-cursor-toolkit/docs/probe-results.csv"
