<#
.SYNOPSIS
  NON-interactive size measurement: for each pointer-size slider step, which bitmap size does Windows CREATE
  the system arrow at? Writes probe-auto.csv (scale_pct, slider, base_px, bitmap_px).
.DESCRIPTION
  This measures the size of the cursor bitmap Windows built - NOT whether it came from the matching layer or
  was resampled from another one. That needs eyes (Run-SizeProbe.ps1). Unverified until it matches visual readings.

  Per slider: set the size with SystemParametersInfo(0x2029), point Arrow at the probe cursor, reload with
  SPI_SETCURSORS, then read the system arrow: LoadCursor(NULL, IDC_ARROW) -> GetIconInfo -> GetObject(hbmColor).
  Cross-checks printed (not in the CSV): GetCursorInfo (the cursor currently on screen) and SM_CXCURSOR.
  Everything is restored in a finally block and verified against the starting registry (CursorState.ps1).
.EXAMPLE
  .\Measure-CursorSize.ps1 -ProbeCur ..\probe\size-probe.cur -Csv ..\probe\probe-auto.csv
#>
param(
  [string]$ProbeCur = (Join-Path $PSScriptRoot '..\probe\size-probe.cur'),
  [int[]]$Sliders = @(1, 2, 3, 4, 5, 7, 9, 15),
  [string]$Csv = 'probe-auto.csv',
  [int]$SettleMs = 150
)
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\CursorState.ps1"
$probe = (Resolve-Path $ProbeCur).Path

Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class W11Measure {
  [StructLayout(LayoutKind.Sequential)] public struct ICONINFO { public bool fIcon; public int xHotspot; public int yHotspot; public IntPtr hbmMask; public IntPtr hbmColor; }
  [StructLayout(LayoutKind.Sequential)] public struct BITMAP { public int bmType; public int bmWidth; public int bmHeight; public int bmWidthBytes; public ushort bmPlanes; public ushort bmBitsPixel; public IntPtr bmBits; }
  [StructLayout(LayoutKind.Sequential)] public struct POINT { public int x; public int y; }
  [StructLayout(LayoutKind.Sequential)] public struct CURSORINFO { public int cbSize; public int flags; public IntPtr hCursor; public POINT ptScreenPos; }
  [DllImport("user32.dll", SetLastError = true)] public static extern bool SetProcessDpiAwarenessContext(IntPtr ctx);
  [DllImport("user32.dll")] public static extern IntPtr SetThreadDpiAwarenessContext(IntPtr ctx);
  [DllImport("user32.dll")] public static extern IntPtr GetThreadDpiAwarenessContext();
  [DllImport("user32.dll")] public static extern int GetAwarenessFromDpiAwarenessContext(IntPtr ctx);
  [DllImport("user32.dll")] public static extern uint GetDpiForSystem();
  [DllImport("user32.dll")] public static extern int GetSystemMetrics(int index);
  [DllImport("user32.dll")] public static extern IntPtr LoadCursorW(IntPtr hInst, IntPtr name);
  [DllImport("user32.dll", SetLastError = true)] public static extern bool GetIconInfo(IntPtr hIcon, out ICONINFO info);
  [DllImport("user32.dll", SetLastError = true)] public static extern bool GetCursorInfo(ref CURSORINFO info);
  [DllImport("gdi32.dll")] public static extern int GetObjectW(IntPtr h, int size, out BITMAP bmp);
  [DllImport("gdi32.dll")] public static extern bool DeleteObject(IntPtr h);
}
"@

function Get-CursorBitmapSize([IntPtr]$h) {
  # GetIconInfo returns COPIES of the cursor's bitmaps -> read the header, then delete them (no GDI leak).
  if ($h -eq [IntPtr]::Zero) { return $null }
  $ii = New-Object W11Measure+ICONINFO
  if (-not [W11Measure]::GetIconInfo($h, [ref]$ii)) { return $null }
  try {
    $bm = New-Object W11Measure+BITMAP
    $src = if ($ii.hbmColor -ne [IntPtr]::Zero) { $ii.hbmColor } else { $ii.hbmMask }   # monochrome: mask is 2x high
    [void][W11Measure]::GetObjectW($src, [Runtime.InteropServices.Marshal]::SizeOf($bm), [ref]$bm)
    [pscustomobject]@{ W = $bm.bmWidth; H = $bm.bmHeight; Bpp = $bm.bmBitsPixel; Hot = "($($ii.xHotspot),$($ii.yHotspot))" }
  } finally {
    if ($ii.hbmColor -ne [IntPtr]::Zero) { [void][W11Measure]::DeleteObject($ii.hbmColor) }
    if ($ii.hbmMask -ne [IntPtr]::Zero) { [void][W11Measure]::DeleteObject($ii.hbmMask) }
  }
}

# 1) Per-monitor DPI awareness V2 (-4). The PowerShell host may already have set process awareness; then the
#    process call fails and we fall back to the THREAD context (enough for the calls this script makes).
$PMv2 = [IntPtr](-4)
$procOk = [W11Measure]::SetProcessDpiAwarenessContext($PMv2)
$procErr = [Runtime.InteropServices.Marshal]::GetLastWin32Error()
if (-not $procOk) { [void][W11Measure]::SetThreadDpiAwarenessContext($PMv2) }
$awareness = [W11Measure]::GetAwarenessFromDpiAwarenessContext([W11Measure]::GetThreadDpiAwarenessContext())
$dpi = [W11Measure]::GetDpiForSystem()
$scalePct = [math]::Round($dpi * 100 / 96)
$awName = @{ 0 = 'unaware'; 1 = 'system aware'; 2 = 'per-monitor aware' }[$awareness]
Write-Host ("DPI awareness: SetProcessDpiAwarenessContext(-4) {0}; effective thread awareness = {1} ({2})" -f `
  ($(if ($procOk) { 'OK' } else { "failed (error $procErr) -> used SetThreadDpiAwarenessContext" })), $awareness, $awName)
Write-Host "GetDpiForSystem = $dpi -> scale $scalePct %"

$IDC_ARROW = [IntPtr]32512; $SM_CXCURSOR = 13
$state = Save-CursorState
Write-CursorBanner $state @(
  "Arrow (Normal Select) -> $probe",
  "pointer size (CursorBaseSize) -> $(($Sliders | ForEach-Object { 16 * ($_ + 1) }) -join ', ') px (sliders $($Sliders -join ', '))",
  "duration: about $([math]::Ceiling($Sliders.Count * ($SettleMs + 150) / 1000)) s; the pointer will visibly change size"
)
$rows = @(); $diag = @()
try {
  foreach ($s in $Sliders) {
    $px = 16 * ($s + 1)
    Set-PointerSize $px
    Set-ItemProperty $script:CursorsKey -Name Arrow -Value $probe
    Update-SystemCursors
    Start-Sleep -Milliseconds $SettleMs
    $sys = Get-CursorBitmapSize ([W11Measure]::LoadCursorW([IntPtr]::Zero, $IDC_ARROW))
    $ci = New-Object W11Measure+CURSORINFO; $ci.cbSize = [Runtime.InteropServices.Marshal]::SizeOf($ci)
    $cur = if ([W11Measure]::GetCursorInfo([ref]$ci)) { Get-CursorBitmapSize $ci.hCursor } else { $null }
    $rows += [pscustomobject]@{ scale_pct = $scalePct; slider = $s; base_px = $px; bitmap_px = $(if ($sys) { $sys.W } else { '' }) }
    $diag += [pscustomobject]@{ slider = $s; base_px = $px
      'LoadCursor WxH' = $(if ($sys) { "$($sys.W)x$($sys.H) $($sys.Bpp)bpp hs$($sys.Hot)" } else { 'n/a' })
      'GetCursorInfo (on screen)' = $(if ($cur) { "$($cur.W)x$($cur.H) hs$($cur.Hot) same=$($ci.hCursor -eq [W11Measure]::LoadCursorW([IntPtr]::Zero, $IDC_ARROW))" } else { 'n/a' })
      'SM_CXCURSOR' = [W11Measure]::GetSystemMetrics($SM_CXCURSOR)
      'expected base*scale' = [math]::Min(256, [math]::Round($px * $scalePct / 100)) }
  }
} catch {
  Write-Host "ERROR: $($_.Exception.Message)"
  throw
} finally {
  Restore-CursorState $state
}
Write-Host "`nCSV rows:"; $rows | Format-Table -AutoSize | Out-String | Write-Host
Write-Host 'Diagnostics (not in CSV):'; $diag | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
$rows | Export-Csv -NoTypeInformation -Append $Csv
Write-Host "Appended $($rows.Count) row(s) to $((Resolve-Path $Csv).Path)"
Write-Host 'NOTE: bitmap_px = size Windows CREATED the cursor at; it does not show which probe layer was used or'
Write-Host '      whether it was resampled. UNVERIFIED until it matches the visual readings (Run-SizeProbe.ps1).'
