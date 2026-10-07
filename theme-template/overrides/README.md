# overrides/

Files here win over upstream SVGs with the same name:

- `overrides/_all/<name>.svg` - applies to every variant (e.g. new `pin.svg`, `person.svg`)
- `overrides/<variant-id>/<name>.svg` - applies to one variant

Use this for: missing Windows roles (Pin, Person), hotspot-friendly tweaks, small-size
hinting fixes. Never edit files inside `upstream/` (it's a pinned submodule).
Every override must keep the upstream license - note what you changed in CREDITS.md.
