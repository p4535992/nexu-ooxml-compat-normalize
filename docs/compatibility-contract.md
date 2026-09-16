# Compatibility contract

## Verified package guarantees

For an accepted normalization:

1. output is a valid ZIP/OPC package;
2. no package part is silently dropped;
3. relationship parts are preserved unless a future registered rule explicitly owns them;
4. content types are preserved unless a future registered rule explicitly owns them;
5. modifications are limited to declared compatibility rules;
6. postflight analysis reruns after writing;
7. strict mode rejects currently-known unresolved high-risk conditions covered by policy.

## Rendering limits

OOXML does not make different office renderers identical. Rendering can still depend on exact font files/versions, shaping engines, locale, printer metrics, vendor extensions, formula engines, SmartArt/charts, OLE/ActiveX and application-specific layout heuristics.

The project therefore reports **what it verified**, not a universal pixel-identity claim.

## Profiles

### `preserve-v1`

Preserves semantic indirections and disables automatic semantic-color normalization. Explicit user-requested font mappings can still be applied.

### `interop-transitional-v1`

Conservative default. Preserves theme/default indirections while normalizing known renderer-dependent representations such as supported semantic color glyphs.

### `portable-explicit-v1`

Extends the conservative profile by materializing only currently-supported, semantically-unambiguous dependencies:

- concrete theme font names;
- theme colors without unsupported transforms;
- Word's implicit `tblLayout=autofit` default;
- SpreadsheetML DrawingML `twoCellAnchor editAs=twoCell` default.

It does **not** flatten complex theme transforms or rewrite risky style/autofit/conditional-format behavior merely to make XML look simpler.

## Guarantee levels

- `preservation-verified`: package invariants passed;
- `best-effort-with-warnings`: package is valid but unresolved concerns remain;
- `strict-preflight-and-preservation-verified`: every currently implemented strict preflight and preservation check passed.
