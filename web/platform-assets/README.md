# Platform Assets

Shared native-platform assets for wrappers around the Xvaw web UI.

- `AppIcon.icon` is the Apple Icon Composer source of truth for the app icon.
  The iOS project references it directly. Electron uses generated
  `icon.icns`, `icon.png`, `icon.ico`, and `icon.svg` in `electron/icons/`.
  Its static icon does not require Xcode 26; the upstream `Assets.car` is excluded.
- `logos/` contains the setup-screen logo SVGs. Electron loads them from
  `platform-assets` at runtime; iOS symlinks them into its asset catalog so the
  SwiftUI setup screen uses the same sources.
