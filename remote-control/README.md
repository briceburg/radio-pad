# RadioPad remote control

A web and native mobile controller for [RadioPad](https://github.com/briceburg/radio-pad).

## Overview

- Discover players and RadioDials from the [registry](../registry/).
- Send playback commands through the registry switchboard and render requested, confirmed, and failed playback plus player status in real time.
- Run as a web app or a Capacitor app for Android and iOS.
- Sign in only when the registry requires authentication for player control.

## Usage

### Local configuration

```sh
npm ci
cp .env.example .env
```

The registry URL defaults to `https://registry.radiopad.dev/api/`. Override it only if you are targeting a different registry or local registry instance. An explicit player `switchboard_url` takes precedence; otherwise the remote infers a same-origin `/switchboard/{account}/{player}` URL before applying the web-only `VITE_SWITCHBOARD_URL` override.

Standalone builds read the Web client ID from `VITE_GOOGLE_CLIENT_ID` in `remote-control/.env`; Vite embeds it at build time, so set it before `npm run build` or `npx cap sync`. Compose instead reads `GOOGLE_CLIENT_ID` from the root `.env`; see the root [Google sign-in setup](../README.md#google-sign-in). Register `http://localhost:5173` and `https://remote.radiopad.dev` as authorized JavaScript origins on the Web client, with their trailing-slash forms as authorized redirect URIs.

The remote reads the registry's auth status at runtime. When registry auth is disabled, public player discovery and tokenless switchboard control remain available for local development. Controllers authenticate in their first WebSocket message so OIDC tokens never appear in switchboard URLs or access logs. Authentication and authorization failures stop reconnecting and remain visible in the Control title.

Settings edits remain local drafts until you select `Save`. Changing the Account hides its Player and RadioDial choices until Save refreshes discovery; the current Control player remains active until that save completes.

Set `VITE_GOOGLE_REDIRECT_URL` only if the browser should return to a specific URL instead of the current page URL.

For local switchboard testing, set `VITE_SWITCHBOARD_URL=ws://localhost:1980/switchboard/`.

### Web development

After completing [local configuration](#local-configuration), run:

```sh
npm start
```

Open `http://localhost:5173`. When registry auth is enabled, sign in from `Settings` to control players or test registry writes.

For [Compose-based development](../README.md#development), the root `.env` pins the remote-control port to `5173` so the same Google OAuth web client works with `docker compose up`. If you change that port, update the Google web client origin and redirect URI to match.

For registry write testing on web, copy the API test token from `Settings` and use it with the [registry](../registry/) API.

Cloudflare Pages uses `remote-control` as the Git root and `npm run build` as the build command. The output directory and public Web client ID live in `wrangler.toml`; Pages does not support defining the Git root or build command there.

### Testing

The `remote-control` component uses Vitest + jsdom for headless domain and UI-structure tests.

Run the full client test suite with:

```sh
./bin/ci
```

Use `npm test` for tests only, or run tests in watch mode during development:

```sh
npm run test:watch
```

Formatting is repo-wide; run `npm run format` from the repository root to write changes. Root `bin/ci` verifies formatting and every component; for dependency changes, follow the root [toolchain policy](../README.md#toolchain-and-dependency-policy).

### Android development

The Android project is checked in under `android/`; do not run `cap add` again. Complete the [local configuration](#local-configuration) before building because Vite embeds it in the native app.

Android OAuth clients authorize a package and signing-certificate pair. Their client IDs stay in Google Auth Platform; `VITE_GOOGLE_CLIENT_ID` remains the Web client ID from the root setup.

Print the debug signing certificate with:

```sh
cd android
./gradlew signingReport
cd ..
```

Copy the `SHA1` value under `Variant: debug`. It changes when the debug keystore changes, and each workstation commonly has its own.

In the same [Google Auth Platform project](https://console.developers.google.com/auth/clients) as the Web client, create an `Android` OAuth client:

- `Name`: `RadioPad Android (debug - <workstation>)` (a private console label)
- `Package name`: `dev.radiopad.remote`
- `SHA-1 certificate fingerprint`: the `SHA1` value printed above
- `Verify ownership`: leave disabled for a local debug client

Create one debug Android client for each distinct debug signing certificate used by the team.

Build, sync Android, and open Android Studio:

```sh
./bin/android
```

Select an emulator or connected device in Android Studio and run the `app` configuration. For command-line deployment to a running emulator or device, use `npx cap run android`.

### Google Play release

The application ID is `dev.radiopad.remote`. Confirm it before creating the Play Console app because package names are permanent. Each update must increase `versionCode` in `android/app/build.gradle`.

Keep the dedicated upload keystore outside the repository, back it up, and do not use the debug key. Build a signed bundle with:

```sh
./bin/android-bundle
```

The helper offers the `radiopad` key in `~/.android/radiopad.jks` as its local default, prompts for passwords, builds the web app, syncs Capacitor, creates the release bundle, verifies its signature, and prints its path and SHA-256 checksum.

In a non-interactive environment, provide:

- `RADIOPAD_RELEASE_STORE_FILE` (optional; defaults to `~/.android/radiopad.jks`)
- `RADIOPAD_RELEASE_STORE_PASSWORD`
- `RADIOPAD_RELEASE_KEY_ALIAS` (optional; defaults to `radiopad`)
- `RADIOPAD_RELEASE_KEY_PASSWORD` (optional when it matches the keystore password)

The helper is a shared build entry point for local and non-interactive releases; publishing remains separate. CI can reconstruct the keystore under its temporary runner directory, invoke the helper, and publish its output directly without retaining the signed AAB as a workflow artifact.

Create the app in Play Console, enable [Play App Signing](https://support.google.com/googleplay/android-developer/answer/9842756), and upload the signed `.aab` to Internal testing. For the Play declarations:

- Use `https://remote.radiopad.dev/privacy/` as the privacy-policy URL.
- Declare the `mediaPlayback` foreground service: it keeps a user-selected station playing in the background and the user can stop it from RadioPad or the system media controls.
- Complete Data safety from the behavior documented in the privacy policy. RadioPad has no ads or analytics, but Google Sign-In and network requests process account and usage data.
- Explain that listening and discovery are available without sign-in if Play review asks for app-access instructions.

After uploading, copy every **app-signing** SHA-1 from Play Console's App signing page. Do not use the upload-key fingerprint: Google Play signs the APK installed by users with its app-signing keys. Quantum-ready Play signing uses three identities: the classical key for Android 16 and earlier, plus the newer classical and post-quantum keys.

Create one Google `Android` OAuth client for each SHA-1:

- `Package name`: `dev.radiopad.remote`
- `SHA-1 certificate fingerprint`: one Play app-signing SHA-1
- `Name`: a private label that distinguishes the legacy classical, hybrid classical, and hybrid post-quantum clients

Select `Verify ownership` for these production clients after the Play app is available.

Android app ownership verification is separate from [OAuth brand/domain verification](https://developers.google.com/identity/protocols/oauth2/production-readiness/brand-verification).

Manual Play uploads work well for internal testing. Automated publishing should use a protected GitHub environment and short-lived Google credentials to publish the helper's output directly to Play's internal track.

### iOS development

The iOS project is checked in under `ios/`; do not run `cap add` again.

Create a Google `iOS` OAuth client with bundle identifier `dev.radiopad.remote`, then save its client ID and reversed URL scheme.

Then create a local iOS config file:

```sh
cp ios/App/App/GoogleSignIn.local.xcconfig.example \
  ios/App/App/GoogleSignIn.local.xcconfig
```

Set these values in `ios/App/App/GoogleSignIn.local.xcconfig`:

- `GOOGLE_IOS_CLIENT_ID`
- `GOOGLE_IOS_REVERSED_CLIENT_ID`

Then run:

```sh
npm run build
npx cap sync ios
```

Open the iOS project in Xcode and run it there.

## License

[GNU Affero General Public License v3.0](./LICENSE)
