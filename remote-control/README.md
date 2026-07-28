# RadioPad remote control

A web and native mobile controller for [RadioPad](https://github.com/briceburg/radio-pad). It discovers players and RadioDials through the registry, sends playback commands through its switchboard, renders player state in real time, and signs in only when the registry requires authentication.

The Control tab uses a compact, state-driven title whose shared playback states align with the [Macropad title row](../macropad-control/README.md#visual-states): `Starting <call sign>`, the confirmed call sign, and `Failed <call sign>`. The selected player name is the idle fallback instead of a prefix on every state.

## Development

### Configuration

Install dependencies and copy the standalone configuration:

```sh
npm ci
cp .env.example .env
```

The registry defaults to `https://registry.radiopad.dev/api/`. An explicit player `switchboard_url` takes precedence; otherwise the remote infers a same-origin `/switchboard/{account}/{player}` URL before applying the web-only `VITE_SWITCHBOARD_URL` override.

Standalone builds read the Google Web client ID from `VITE_GOOGLE_CLIENT_ID`; Vite embeds it at build time, so set it before building or syncing Capacitor. Register `http://localhost:5173` and `https://remote.radiopad.dev` as authorized JavaScript origins, with their trailing-slash forms as redirect URIs. Compose uses `GOOGLE_CLIENT_ID` from the root `.env`; see the root [Google sign-in setup](../README.md#google-sign-in).

Authentication follows the registry's runtime status. After Google sign-in, the registry keeps a rolling 30-day session and the remote keeps only its short-lived access token in memory; opening or actively using the app refreshes both. Public discovery and tokenless control remain available when authentication is disabled, and authorization failures remain visible in the Control title.

### Web

Start the Vite development server:

```sh
npm start
```

Open `http://localhost:5173`. Use the root [Compose workflow](../README.md#development) to run the complete system. When authentication is enabled, sign in from `Settings`; its web-only API test-token action supports authenticated registry requests.

Cloudflare Pages uses `remote-control` as its Git root and `npm run build` as its build command. `wrangler.toml` owns the output directory and public Web client ID.

### PWA and application assets

`src/manifest.webmanifest` owns the installed web app's identity, scope, display mode, colors, and icons. RadioPad intentionally has no service worker: current Chrome and Safari installation flows do not require one, and its control, authentication, WebSocket, and streaming behavior requires the network.

The four canonical files in `../shared/assets` are the icon foreground, transparent icon glow, and light and dark splash SVGs. Checked-in web PNGs, Android launcher and splash resources, and iOS asset-catalog PNGs are generated outputs; regenerate all platforms after changing a source:

```sh
npm run assets
```

The app-local Sharp generator is the only asset tool. `npm run build` validates the emitted manifest and icons, Apple Home Screen metadata, and `/privacy/`.

### Validation

Run the component tests and production/PWA build:

```sh
./bin/ci
```

Use `npm run test:watch` while developing. Formatting is repository-wide: run `npm run format` from the root to write changes, and use root `bin/ci` to verify every component.

## Android

The checked-in project under `android/` uses application ID `dev.radiopad.remote`; do not run `cap add` again. After completing [configuration](#configuration), build the web app, sync Android, and open Android Studio with:

```sh
./bin/android
```

Run the `app` configuration on an emulator or connected device, or use `npx cap run android`. Android OAuth clients authorize a package and signing-certificate pair while `VITE_GOOGLE_CLIENT_ID` remains the Web client ID.

Print the debug signing certificate:

```sh
(cd android && ./gradlew signingReport)
```

In the same [Google Auth Platform project](https://console.developers.google.com/auth/clients) as the Web client, create one `Android` OAuth client for each distinct debug certificate:

- `Name`: `RadioPad Android (debug - <workstation>)`
- `Package name`: `dev.radiopad.remote`
- `SHA-1 certificate fingerprint`: the `SHA1` under `Variant: debug`
- `Verify ownership`: disabled

### Google Play release

Package names are permanent, and each update must increase `versionCode` in `android/app/build.gradle`. Keep the upload keystore outside the repository, back it up, and never use the debug key. Build and verify a signed bundle with:

```sh
./bin/android-bundle
```

The helper defaults to alias `radiopad` in `~/.android/radiopad.jks`, prompts for passwords, builds and syncs the app, and prints the AAB path and SHA-256 checksum. Non-interactive builds accept:

- `RADIOPAD_RELEASE_STORE_FILE` (optional; defaults to `~/.android/radiopad.jks`)
- `RADIOPAD_RELEASE_STORE_PASSWORD`
- `RADIOPAD_RELEASE_KEY_ALIAS` (optional; defaults to `radiopad`)
- `RADIOPAD_RELEASE_KEY_PASSWORD` (optional when it matches the store password)

Create the Play Console app, enable [Play App Signing](https://support.google.com/googleplay/android-developer/answer/9842756), and upload the AAB to Internal testing. Complete its declarations as follows:

- Use `https://remote.radiopad.dev/privacy/` as the privacy-policy URL.
- Declare the `mediaPlayback` foreground service used for user-controlled background playback.
- Complete Data safety from the privacy policy; RadioPad has no ads or analytics, but Google Sign-In and network requests process account and usage data.
- Explain that listening and discovery are available without sign-in if review requests app-access instructions.

After uploading, create one Google `Android` OAuth client for each **app-signing** SHA-1 shown by Play; do not use the upload-key fingerprint. Quantum-ready Play signing exposes the classical Android 16-and-earlier identity plus newer classical and post-quantum identities. Use package `dev.radiopad.remote`, label the clients distinctly, and verify ownership after the Play app is available.

Android app ownership verification is separate from [OAuth brand/domain verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification). Manual internal-track uploads are sufficient; automation should use a protected GitHub environment and short-lived Google credentials.

## iOS

The checked-in project under `ios/` uses bundle identifier `dev.radiopad.remote`; do not run `cap add` again. Create a Google `iOS` OAuth client for that identifier, then copy and complete the local configuration:

```sh
cp ios/App/App/GoogleSignIn.local.xcconfig.example \
  ios/App/App/GoogleSignIn.local.xcconfig
```

Set `GOOGLE_IOS_CLIENT_ID` and `GOOGLE_IOS_REVERSED_CLIENT_ID`, then build, sync, and open Xcode:

```sh
./bin/ios
```

The native project lists `registry.radiopad.dev` as an app-bound domain so its shared cookie-based registry session can work on iOS. The installed PWA remains the recommended iOS distribution.

## License

[GNU Affero General Public License v3.0](./LICENSE)
