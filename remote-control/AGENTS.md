# AGENTS.md

Guidance for coding agents working in `radio-pad/remote-control`.

## Project shape

- Ionic + Capacitor + Lit web-component UI.
- Lit templates provide declarative, XSS-safe DOM bindings (do not use raw `.innerHTML` or `.innerText` assignments).
- Services directly inherit native `EventTarget` (no custom emitters needed).
- Web and native builds intentionally share most code.

## Runtime and tooling

- Run local web dev with `npm start`.
- Validate production bundling with `npm run build`.
- Regenerate web and native application assets with `npm run assets` after changing their canonical SVGs in `../shared/assets`; do not hand-edit the generated PNGs.
- `src/manifest.webmanifest` owns PWA identity and behavior. Keep its root-relative icon URLs aligned with `vite.config.mjs` and the production-build assertions.
- Repository formatting is owned by the root tooling package. Run `npm run format` from the repository root to write changes; root `bin/ci` verifies them.
- Run headless logic tests via `npm test` or `npm run test:watch`.

## Auth conventions

- Google sign-in uses `@capawesome/capacitor-google-sign-in` across web, Android, and iOS.
- `VITE_GOOGLE_CLIENT_ID` should be the Google web client ID.
- Android OAuth clients register package/signing-certificate pairs in Google Auth Platform; their IDs are not application configuration.
- `VITE_GOOGLE_REDIRECT_URL` is optional on web. By default, the app uses the current page URL.
- The Settings tab's `Copy API test token` action is intentionally web-only.
- iOS also needs native Google SDK metadata in `ios/App/App/Info.plist`.
  - `GIDClientID` is wired through `$(GOOGLE_IOS_CLIENT_ID)`.
  - The URL scheme is wired through `$(GOOGLE_IOS_REVERSED_CLIENT_ID)`.
  - Set those values in the local-only `ios/App/App/GoogleSignIn.local.xcconfig`.

## Environment conventions

- `vite.config.mjs` uses `root: './src'`, so keep `envDir: '..'` so `.env` resolves from `remote-control/`.
- `remote-control/.env` is local-only and should stay gitignored.
- `remote-control/.env.example` is the checked-in template.
- `VITE_SWITCHBOARD_URL` is a web-only override for switchboard testing.
  - Web preserves the player-specific path from the registry `switchboard_url`.
  - Native must not apply the web override; it uses the explicit or inferred URL from player discovery.
- Player discovery preserves an explicit `switchboard_url` and otherwise infers the same-origin switchboard path from the registry URL.

## Testing and debugging

- `vitest` is used for isolated logical tests. Prefer `npm test` over UI checks for domain logic correctness.
- Place structural logic / service unit tests inside the `tests/` directory at the project root.

## Change preferences

- Keep platform-specific behavior explicit only where the plugin or native project metadata requires it.
- Keep `dev.radiopad.remote` aligned across Capacitor, the Android namespace/application ID and Java package, and the iOS bundle identifier.
- Never sign release builds with the debug key or commit keystores.
- Use `bin/android-bundle` for signed release bundles. It prompts locally and accepts `RADIOPAD_RELEASE_*` environment variables for non-interactive CI; publishing remains a separate step.
- Prefer small helpers over broad auth rewrites; the shared Google sign-in path should stay easy to reason about.
- Keep Settings edits as component-local drafts until explicit Save; account-dependent discovery and active Control changes occur only after Save.
- Preserve the grouped Settings UI. Standard groups use `ion-item-group` + `ion-item-divider`; Advanced uses Ionic's `ion-accordion` within an item group.
- Persist qualified RadioDial identities in preferences and derive resource URLs from the current registry URL. Do not persist URLs as RadioDial identity.
- Treat `radio_dial_url` as the source URL reported by a running player. `configured_radio_dial_url` is the remote's initial URL derived from registry configuration. Retain the configured URL when both URLs identify the same RadioDial resource; a different running-player report may supersede it.
