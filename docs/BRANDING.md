# Xwav brand

Xwav brings your AI agents into one shared workspace. Three separated, flowing signal ribbons represent independent agents moving together. Their offset rhythm and mint, ice, and periwinkle colors give Xwav a distinctive wave emblem that stays clear at small sizes.

**Tagline:** Your agents. One workspace.

| Color | Value | Use |
| --- | --- | --- |
| Deep navy | `#101923` | App icon and dark surfaces |
| Mint | `#6EE7D2` | Logo and dark-mode brand accent |
| Teal | `#087F70` | Light-mode accent with readable contrast |
| Periwinkle | `#89A9FF` | Secondary ribbon and highlights |
| Ice | `#E8FFF9` | Central signal ribbon |

## Assets

- Master SVG icon: `web/platform-assets/logos/xwav-icon.svg`.
- Light/dark wordmarks: `web/platform-assets/logos/xwav-wordmark.svg` and `xwav-wordmark-reverse.svg`.
- React mark: `web/src/components/icons/XwavIcon.tsx`, used by the app's default `BrandLogo`. Operator-supplied branding still overrides it.
- Browser favicon, Apple touch icon, 192/512 px icons, and a relative-path web manifest: `web/public/`.
- Desktop PNG, ICO, ICNS, and SVG: `web/electron/icons/`.
- Apple Icon Composer source: `web/platform-assets/AppIcon.icon/`.
- Android launcher, monochrome, and setup vectors: `web/android/app/src/main/res/drawable/`.
- README banner: `docs/images/xwav-banner.svg`.

Regenerate raster icons with Python 3, Pillow, and CairoSVG:

```bash
python3 -m pip install pillow cairosvg
python3 scripts/generate_xwav_assets.py
```

The SVG and React mark share the same 128-unit geometry. Keep both in sync when changing the mark. Existing `omnigents-logo*.svg` filenames remain compatibility aliases for native resource catalogs; their contents are the Xwav wordmarks.

## Fork boundaries

The Python distribution and import namespace remain `omnigent`, and `xwav` is the public CLI alias. The previous `xvaw` CLI alias remains available for existing scripts. The public XWAV_* environment prefix (with earlier XVAW_* aliases still accepted) maps to the existing runtime settings. Configuration/state locations, HTTP headers, SDK APIs, and native source/target identifiers retain their compatibility names. New session links use xwav://; desktop and iOS also accept older session links. This avoids breaking integrations. Xwav's desktop app ID is `ai.neuraltech.xwav.desktop`; iOS and Android use ai.neuraltech.xwav application IDs. Their signing requires owner-specific configuration before distribution.

The Electron source installer uses the upstream installer's existing `--repo` option to install this fork. Public release downloads and auto-updates are not configured. Upstream signing identity and compiled `Assets.car` are removed from Xwav desktop packaging; macOS uses the generated Xwav ICNS instead. Recompile the Apple Icon Composer source on macOS if a native dynamic icon is needed.

The inherited installer/CLI upgrade commands, app-store metadata, release workflows, documentation, historical screenshots, and tests can reference upstream services. They are not evidence of published Xwav releases. Use the source instructions in the root README for this fork.

Omnigent's original copyright, LICENSE, NOTICE, SDK identities, and historical attribution are retained. This fork is not an official Omnigent or Databricks distribution.

## Interface audit

The main sidebar uses the wave icon and a theme-aware Xwav name. Onboarding, login, settings, reconnect commands, permissions dialogs, settings exports, installer output, CLI banners/help, native store copy, and the API-only fallback use Xwav. Original artwork paths are compatibility aliases containing the new artwork. The VS Code extension also uses Xwav titles, a new setting namespace, and the wave icon; older settings and command bindings retain compatibility. Legal upstream attribution remains in LICENSE, NOTICE, and the root README.

XWAV_* settings are aliases for the existing runtime environment variables. An explicitly supplied internal/legacy setting retains precedence so existing deployments behave consistently. Use xwav host, xwav server, and xwav --version in user-facing command examples.
