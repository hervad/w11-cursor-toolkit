<#
  Shared by Run-SizeProbe.ps1 and Measure-CursorSize.ps1 (dot-source it):  . "$PSScriptRoot\CursorState.ps1"
  Saves the pointer settings these scripts touch and restores them EXACTLY, then proves it by comparing the
  registry with the snapshot taken at the start.

  Windows APIs used:
  * SystemParametersInfo(SPI_SETCURSORS = 0x57): "reload all system cursors from the registry". Analogy: the
    registry is the menu on the wall; the cursors on screen are what the kitchen already cooked. Editing the
    menu changes nothing until you tell the kitchen to cook again - that is SPI_SETCURSORS.
  * SystemParametersInfo(0x2029): UNDOCUMENTED action the Settings app uses for the pointer-size slider; pvParam
    = size in px (32..256). With SPIF_UPDATEINIFILE it also writes HKCU\Control Panel\Cursors\CursorBaseSize.
#>
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class W11CursorState {
  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool SystemParametersInfoW(uint action, uint uiParam, IntPtr pvParam, uint winIni);
}
"@ -ErrorAction SilentlyContinue   # already loaded when both scripts run in one session

$script:CursorsKey = 'HKCU:\Control Panel\Cursors'
$script:AccessKey  = 'HKCU:\Software\Microsoft\Accessibility'
$script:SPI_SETCURSORS = 0x57
$script:SPI_SETCURSORSIZE = 0x2029                # undocumented (Settings > Mouse pointer size)
$script:SPIF_UPDATE_AND_SEND = 0x03               # SPIF_UPDATEINIFILE | SPIF_SENDCHANGE

function Get-RegValues([string]$Key) {
  # name -> raw value (REG_EXPAND_SZ NOT expanded, e.g. %SYSTEMROOT%\Cursors\...)
  $out = [ordered]@{}
  if (Test-Path $Key) {
    $item = Get-Item $Key
    foreach ($n in $item.GetValueNames()) { $out[$n] = $item.GetValue($n, $null, 'DoNotExpandEnvironmentNames') }
  }
  $out
}

function Get-RegKinds([string]$Key) {
  # name -> RegistryValueKind (String, ExpandString, DWord ...). Cursor paths are usually ExpandString:
  # rewriting one as String would leave %SYSTEMROOT% unexpanded and break the cursor.
  $out = [ordered]@{}
  if (Test-Path $Key) { $item = Get-Item $Key; foreach ($n in $item.GetValueNames()) { $out[$n] = $item.GetValueKind($n) } }
  $out
}

function Set-RegValueExact([string]$Key, [string]$Name, $Value, [Microsoft.Win32.RegistryValueKind]$Kind) {
  $sub = $Key -replace '^HKCU:\\', ''
  $rk = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey($sub, $true)
  try { $rk.SetValue($Name, $Value, $Kind) } finally { $rk.Close() }
}

function Save-CursorState {
  $c = Get-RegValues $script:CursorsKey
  $a = Get-RegValues $script:AccessKey
  [pscustomobject]@{
    Cursors = $c; Access = $a
    CursorKinds = Get-RegKinds $script:CursorsKey; AccessKinds = Get-RegKinds $script:AccessKey
    ArrowExisted = $c.Contains('Arrow'); Arrow = $c['Arrow']
    BaseSizeExisted = $c.Contains('CursorBaseSize'); BaseSize = $c['CursorBaseSize']
  }
}

function Set-PointerSize([int]$Pixels) {
  if (-not [W11CursorState]::SystemParametersInfoW($script:SPI_SETCURSORSIZE, 0, [IntPtr]$Pixels, $script:SPIF_UPDATE_AND_SEND)) {
    throw "SystemParametersInfo(0x2029, $Pixels) failed, error $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
  }
}

function Update-SystemCursors {
  [void][W11CursorState]::SystemParametersInfoW($script:SPI_SETCURSORS, 0, [IntPtr]::Zero, $script:SPIF_UPDATE_AND_SEND)
}

function Write-CursorBanner($State, [string[]]$Changes) {
  $size = if ($State.BaseSizeExisted) { "$($State.BaseSize) px" } else { '(value absent - Windows default 32 px)' }
  $arrow = if ($State.ArrowExisted) { "'$($State.Arrow)'" } else { '(value absent)' }
  $acc = if ($State.Access.Contains('CursorSize')) { $State.Access['CursorSize'] } else { '(absent)' }
  Write-Host '=================================================================='
  Write-Host ' This script TEMPORARILY changes your pointer settings:'
  foreach ($c in $Changes) { Write-Host "   - $c" }
  Write-Host ' Current values (restored at the end, also on error or Ctrl+C):'
  Write-Host "   HKCU\Control Panel\Cursors\Arrow          = $arrow"
  Write-Host "   HKCU\Control Panel\Cursors\CursorBaseSize = $size"
  Write-Host "   HKCU\...\Accessibility\CursorSize         = $acc  (Settings slider index; checked, not set)"
  Write-Host '=================================================================='
}

function Restore-CursorState($State) {
  Write-Host '--- restoring pointer settings ---'
  if ($State.ArrowExisted) {
    Set-RegValueExact $script:CursorsKey 'Arrow' $State.Arrow $State.CursorKinds['Arrow']
    Write-Host "  restored Arrow = '$($State.Arrow)' ($($State.CursorKinds['Arrow']))"
  } else {
    Remove-ItemProperty $script:CursorsKey -Name Arrow -ErrorAction SilentlyContinue
    Write-Host '  Arrow did not exist at start -> removed'
  }
  if ($State.BaseSizeExisted) {
    Set-PointerSize ([int]$State.BaseSize)
    Write-Host "  restored CursorBaseSize = $($State.BaseSize) via SystemParametersInfo(0x2029)"
  } else {
    Set-PointerSize 32   # live size back to the default first (this call writes the value) ...
    Remove-ItemProperty $script:CursorsKey -Name CursorBaseSize -ErrorAction SilentlyContinue   # ... then remove it
    Write-Host '  CursorBaseSize did not exist at start -> live size reset to 32 px via SPI, value removed'
  }
  # Accessibility\CursorSize is only checked; if the size call changed it, put it back too.
  $nowAcc = Get-RegValues $script:AccessKey
  if ($State.Access.Contains('CursorSize') -and "$($nowAcc['CursorSize'])" -ne "$($State.Access['CursorSize'])") {
    Set-RegValueExact $script:AccessKey 'CursorSize' $State.Access['CursorSize'] $State.AccessKinds['CursorSize']
    Write-Host "  restored Accessibility\CursorSize = $($State.Access['CursorSize'])"
  } elseif (-not $State.Access.Contains('CursorSize') -and $nowAcc.Contains('CursorSize')) {
    Remove-ItemProperty $script:AccessKey -Name CursorSize -ErrorAction SilentlyContinue
    Write-Host '  Accessibility\CursorSize did not exist at start -> removed'
  }
  Update-SystemCursors
  Write-Host '  reloaded system cursors (SPI_SETCURSORS)'
  # Proof: compare every value AND its registry type in both keys with the snapshot.
  $diffs = @()
  foreach ($pair in @(@($script:CursorsKey, $State.Cursors, $State.CursorKinds), @($script:AccessKey, $State.Access, $State.AccessKinds))) {
    $now = Get-RegValues $pair[0]; $nowK = Get-RegKinds $pair[0]; $was = $pair[1]; $wasK = $pair[2]
    foreach ($n in @($was.Keys) + @($now.Keys) | Sort-Object -Unique) {
      $w = if ($was.Contains($n)) { "$($wasK[$n]):$($was[$n])" } else { '<absent>' }
      $c = if ($now.Contains($n)) { "$($nowK[$n]):$($now[$n])" } else { '<absent>' }
      if ($w -ne $c) { $diffs += "  DIFF $($pair[0])\$n : start=$w now=$c" }
    }
  }
  if ($diffs) { $diffs | ForEach-Object { Write-Host $_ }; Write-Host '  WARNING: registry differs from the start (see DIFF lines)' }
  else { Write-Host '  verified: both registry keys are identical to the start (values and types)' }
}

function ConvertTo-ScalePercent([string]$Text) {
  # "150", " 150 ", "150%" -> 150; anything else (or outside 100..500) -> $null
  $t = "$Text".Trim().TrimEnd('%').Trim(); $n = 0
  if ([int]::TryParse($t, [ref]$n) -and $n -ge 100 -and $n -le 500) { return $n }
  return $null
}
