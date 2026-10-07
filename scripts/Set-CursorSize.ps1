<#
.SYNOPSIS
  Change the pointer size LIVE, exactly like the Settings slider does.
.DESCRIPTION
  Uses the undocumented SystemParametersInfo action 0x2029 (found by reverse-engineering
  SystemSettings.exe). pvParam is the PIXEL size (32..256), not the slider index 1..15.
  Slider index -> pixels:  px = 16 * (index + 1)   (1=32, 2=48, 3=64 ... 15=256)
.EXAMPLE
  .\Set-CursorSize.ps1 -Pixels 64        # same as slider position 3
  .\Set-CursorSize.ps1 -Slider 5         # 96 px
#>
param(
  [ValidateRange(32, 256)][int]$Pixels,
  [ValidateRange(1, 15)][int]$Slider
)
if ($Slider) { $Pixels = 16 * ($Slider + 1) }
if (-not $Pixels) { throw "Give -Pixels or -Slider" }
Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class W11Spi {
  [DllImport("user32.dll", SetLastError = true)]
  public static extern bool SystemParametersInfoW(uint action, uint uiParam, IntPtr pvParam, uint winIni);
}
"@
$SPI_SETCURSORSIZE = 0x2029; $SPIF_UPDATEINIFILE = 0x01; $SPIF_SENDCHANGE = 0x02
$ok = [W11Spi]::SystemParametersInfoW($SPI_SETCURSORSIZE, 0, [IntPtr]$Pixels, $SPIF_UPDATEINIFILE -bor $SPIF_SENDCHANGE)
if (-not $ok) { throw "SystemParametersInfo failed" }
Write-Host "CursorBaseSize -> $Pixels px. Note: Settings may reset the scheme to Windows Default after a size change - re-select it in Mouse Properties if so."
