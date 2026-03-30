Guidance for coding agents working in `radio-pad/remote-control`.

## Project shape

- Ionic + Capacitor + `lit-html` remote control UI.
- `lit-html` is used declaratively for XSS-safe DOM bindings (do not use raw `.innerHTML` or `.innerText` assignments).
- Services directly inherit native `EventTarget` (no custom emitters needed).
- Web and native builds intentionally share most code.

## Runtime and tooling

- Run local web dev with `npm start`.
- Validate production bundling with `npm run build`.
- Formatting/linting uses `npm run lint` (`prettier --check src/`).
- For quick Settings/auth UI checks, use:
  - `npm run smoke:settings -- --url http://127.0.0.1:5173/`

## Auth conventions

- Google sign-in uses `@capawesome/capacitor-google-sign-in` across web, Android, and iOS.
- `VITE_GOOGLE_CLIENT_ID` should be the Google web client ID.
- `VITE_GOOGLE_REDIRECT_URL` is optional on web. By default, the app uses the current page URL.
- The Settings tab's `Copy API test token` action is intentionally web-only.
- iOS also needs native Google SDK metadata in `ios/App/App/Info.plist`.
  - `GIDClientID` is wired through `$(GOOGLE_IOS_CLIENT_ID)`.
  - The URL scheme is wired through `$(GOOGLE_IOS_REVERSED_CLIENT_ID)`.
  - Set those values in the local-only `ios/App/App/GoogleSignIn.local.xcconfig`.

## Environment conventions

- `vite.config.ts` uses `root: './src'`, so keep `envDir: '..'` so `.env` resolves from `remote-control/`.
- `remote-control/.env` is local-only and should stay gitignored.
- `remote-control/.env.example` is the checked-in template.
- `VITE_SWITCHBOARD_URL` is a web-only override for switchboard testing.
  - Web preserves the player-specific path from the registry `switchboard_url`.
  - Native must keep using the registry-provided `switchboard_url`.

## Testing/debugging preferences

- Prefer `npm run smoke:settings` over repeated ad hoc browser inspection when checking:
  - auth status text
  - visible auth buttons
  - sign-in button visibility
  - settings section rendering
- Add assertion flags to the smoke script when you want a command to fail on regression.
- Use Playwright-based local helpers for UI smoke checks before resorting to repeated agent-driven screenshots.
- `playwright-core` is intentionally used to avoid automatic browser downloads during install.
- If Chromium is missing locally, run `npx playwright install chromium` before `npm run smoke:settings`.

## Change preferences

- Keep platform-specific behavior explicit only where the plugin or native project metadata requires it.
- Prefer small helpers over broad auth rewrites; the shared Google sign-in path should stay easy to reason about.
- Preserve the grouped Settings UI structure (`ion-item-group` + `ion-item-divider`) when adjusting auth/settings presentation.
- Preserve HTML `id` attributes on key elements (like `#auth-status`, `#auth-hint`) in lit templates, as the Playwright smoke tests rely on them for assertions.
- Keep change summaries and "main changes" sections concise; avoid overly technical detail unless it is needed to act on the change.
