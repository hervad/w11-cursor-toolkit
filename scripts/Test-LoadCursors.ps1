<#
.SYNOPSIS
  Loads every .cur/.ani under -Path through the REAL Windows cursor loader (user32).
  This is the check our Python validator can't do: "does Windows itself accept it?"
  Used by CI on windows-latest; run it locally on your Windows 11 box too.
.EXAMPLE
  .\Test-LoadCursors.ps1 -Path ..\dist
#>
param(
  [Parameter(Mandatory)][string]$Path,
  [int[]]$StaticSizes   = @(32, 48, 64, 96, 128, 256),
  [int[]]$AnimatedSizes = @(32, 48, 64, 128)
)
$ErrorActionPreference = 'Stop'
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class W11Cur {
  [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern IntPtr LoadImageW(IntPtr hInst, string name, uint type, int cx, int cy, uint flags);
  [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
  public static extern IntPtr LoadCursorFromFileW(string name);
  [DllImport("user32.dll")] public static extern bool DestroyCursor(IntPtr h);
}
"@
$IMAGE_CURSOR = 2; $LR_LOADFROMFILE = 0x10
$files = Get-ChildItem -Path $Path -Recurse -Include *.cur, *.ani
if (-not $files) { throw "No cursor files under $Path" }
$fail = 0
foreach ($f in $files) {
  $sizes = if ($f.Extension -eq '.ani') { $AnimatedSizes } else { $StaticSizes }
  $h = [W11Cur]::LoadCursorFromFileW($f.FullName)
  if ($h -eq [IntPtr]::Zero) { Write-Host "FAIL  $($f.FullName) LoadCursorFromFile err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"; $fail++; continue }
  [void][W11Cur]::DestroyCursor($h)
  foreach ($s in $sizes) {
    $h = [W11Cur]::LoadImageW([IntPtr]::Zero, $f.FullName, $IMAGE_CURSOR, $s, $s, $LR_LOADFROMFILE)
    if ($h -eq [IntPtr]::Zero) { Write-Host "FAIL  $($f.Name) @${s}px err=$([Runtime.InteropServices.Marshal]::GetLastWin32Error())"; $fail++ }
    else { [void][W11Cur]::DestroyCursor($h) }
  }
}
Write-Host "$($files.Count) files checked, $fail failure(s)"
if ($fail) { exit 1 }
