# TODO Name — Windows 11 HiDPI cursors

Rendered from the original vector art for every layer Windows picks at pointer sizes 1–15. Artwork by
**TODO author** ([upstream](TODO)), packaged for Windows 10 1903+ / Windows 11.

![preview](docs/preview.png)

## Install
1. Download the zip for your variant from [Releases](../../releases/latest) and extract it.
2. Right-click **`install.inf`** → **Install** (accept the UAC prompt — it copies to `C:\Windows\Cursors`).
3. Mouse Properties opens → choose **TODO scheme name** → **Apply**.

> Changing the pointer size in Settings can switch the scheme back to *Windows Default* — just re-select it.

**Uninstall:** run `uninstall.cmd`, pick another scheme, delete `C:\Windows\Cursors\<scheme>` as admin.

## What's embedded
| | Layers (px) |
|---|---|
| Static (`.cur`) | 32 48 64 72 80 96 112 120 128 144 160 168 176 192 200 208 216 224 240 256 |
| Animated (`.ani`) | 32 48 64 72 80 96 120 128 144 |

Contains every layer size Windows picks at 100–199 % display scale (measured), plus the sizes assumed for 200–300 %.
Details: [w11-cursor-toolkit docs](https://github.com/hervad/w11-cursor-toolkit).

## Why not the existing ports?
TODO: `w11cursor inspect` evidence for each existing port (layers, hotspots, roles).

## License
Artwork: TODO license (same as upstream). See [CREDITS.md](CREDITS.md) and [LICENSE](LICENSE).
