<#
.SYNOPSIS
  Checks that Windows PARSES the per-step delays each .ani declares (Test-LoadCursors.ps1 only
  checks that it loads). Read-only: loads files, changes no settings.
.DESCRIPTION
  Uses the UNDOCUMENTED user32 export GetCursorFrameInfo(hCursor, reserved, istep, out rate, out steps)
  (signature as implemented by Wine/ReactOS). Because it is undocumented, a control file with known
  timing is checked first: Microsoft's aero_busy.ani must read back as 18 steps x 3 jiffies.
  If the control fails, the method is not trustworthy on this machine -> exit 2, nothing else judged.
  Then, for every .ani under -Path: declared delays (rate chunk, else anih default for every step,
  read straight from the file bytes) must equal what user32 reports.
  Reports parsed timing, not on-screen timing.
  Exit codes: 0 all match, 1 mismatch/load failure, 2 control failed.
.EXAMPLE
  .\Get-AniFrameTiming.ps1 -Path ..\dist
#>
param(
  [Parameter(Mandatory)][string]$Path,
  [string]$ControlPath = "$env:WINDIR\Cursors\aero_busy.ani",
  [int]$ControlSteps = 18,
  [int]$ControlJiffies = 3,
  [int]$Size = 32
)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class AniTiming {
  [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern IntPtr LoadImageW(IntPtr hInst, string name, uint type, int cx, int cy, uint flags);
  [DllImport("user32.dll")]
  public static extern IntPtr GetCursorFrameInfo(IntPtr hCursor, uint reserved, uint istep, out uint rateJiffies, out uint numSteps);
  [DllImport("user32.dll")] public static extern bool DestroyCursor(IntPtr h);
}
"@

function Get-ParsedDelays([string]$File) {
  # What user32 parsed: one delay per step, or $null if the file did not load.
  $h = [AniTiming]::LoadImageW([IntPtr]::Zero, $File, 2, $Size, $Size, 0x10)  # IMAGE_CURSOR, LR_LOADFROMFILE
  if ($h -eq [IntPtr]::Zero) { return $null }
  try {
    $rate = 0; $n = 0
    [void][AniTiming]::GetCursorFrameInfo($h, 0, 0, [ref]$rate, [ref]$n)
    , @(for ($i = 0; $i -lt $n; $i++) {
      $r = 0; $m = 0
      [void][AniTiming]::GetCursorFrameInfo($h, 0, [uint32]$i, [ref]$r, [ref]$m)
      [int]$r
    })
  } finally { [void][AniTiming]::DestroyCursor($h) }
}

function Get-DeclaredDelays([string]$File) {
  # What the file declares: walk the top-level RIFF chunks (anih / rate), like pack/ani.py's parser.
  $b = [IO.File]::ReadAllBytes($File)
  $end = 8 + [BitConverter]::ToUInt32($b, 4); $pos = 12; $steps = 0; $default = 0; $rates = $null
  while ($pos + 8 -le $end) {
    $id = [Text.Encoding]::ASCII.GetString($b, $pos, 4); $size = [BitConverter]::ToUInt32($b, $pos + 4)
    if ($id -eq 'anih') { $steps = [BitConverter]::ToUInt32($b, $pos + 8 + 8); $default = [BitConverter]::ToUInt32($b, $pos + 8 + 28) }
    elseif ($id -eq 'rate') { $rates = @(for ($i = 0; $i -lt $size / 4; $i++) { [int][BitConverter]::ToUInt32($b, $pos + 8 + 4 * $i) }) }
    $pos += 8 + $size + ($size -band 1)
  }
  if ($rates) { , $rates } else { , @(for ($i = 0; $i -lt $steps; $i++) { [int]$default }) }
}

# 1) Control: is the undocumented call reporting real values on this machine?
if (-not (Test-Path $ControlPath)) { Write-Host "CONTROL MISSING  $ControlPath"; exit 2 }
$ctl = Get-ParsedDelays $ControlPath
$ctlOk = $ctl -and $ctl.Count -eq $ControlSteps -and -not ($ctl | Where-Object { $_ -ne $ControlJiffies })
Write-Host ("control {0}: steps={1} jiffies=[{2}] -> {3}" -f (Split-Path $ControlPath -Leaf), $ctl.Count, ($ctl -join ','), ($(if ($ctlOk) { 'OK' } else { 'FAIL' })))
if (-not $ctlOk) { Write-Host "GetCursorFrameInfo did not reproduce the control timing - results would be meaningless."; exit 2 }

# 2) Every .ani under -Path: declared == parsed?
$files = Get-ChildItem -Path $Path -Recurse -Include *.ani
if (-not $files) { throw "No .ani files under $Path" }
$fail = 0
foreach ($f in $files) {
  $want = Get-DeclaredDelays $f.FullName
  $got = Get-ParsedDelays $f.FullName
  if ($null -eq $got) { Write-Host "FAIL  $($f.FullName) did not load"; $fail++; continue }
  $ok = ($got -join ',') -eq ($want -join ',')
  if (-not $ok) { $fail++ }
  Write-Host ("{0}  {1}  declared=[{2}] parsed=[{3}]" -f ($(if ($ok) { 'OK  ' } else { 'FAIL' })), $f.FullName, ($want -join ','), ($got -join ','))
}
Write-Host "$($files.Count) .ani file(s) checked, $fail mismatch(es)"
if ($fail) { exit 1 }
