# radio-pad remote-control

A web and mobile remote for [radio-pad](https://github.com/briceburg/radio-pad).

## Overview

* connects to [switchboard](../switchboard/) for real-time syncing with [players](https://github.com/briceburg/radio-pad/tree/main/player)
  * remote controls publish station requests and listen for channel changes
  * players listen for station requests and publish channel changes and other state
* loads available players and station data from [`radio-pad-registry`](https://github.com/briceburg/radio-pad-registry)
  * sign in when you need to control managed players

## Usage

### Local configuration

```bash
npm install
cp .env.example .env
```

The registry URL defaults to `https://registry.radiopad.dev`. Override it only if you are targeting a different registry or local registry instance.

Set `VITE_GOOGLE_CLIENT_ID` in `.env` to enable sign-in on the web app.

Set `VITE_GOOGLE_REDIRECT_URL` only if the browser should return to a specific URL instead of the current page URL.

For local switchboard testing, set `VITE_SWITCHBOARD_URL=ws://localhost:1980/`. See [switchboard](../switchboard/).

### Web development

Create a Google `Web application` OAuth client:

- `Authorized JavaScript origins`: `http://localhost:5173`
- `Authorized redirect URIs`: `http://localhost:5173/`

Then run:

```bash
npm start
```

Open `http://localhost:5173`. Sign in from `Settings` when you want to load managed players or test registry writes.

For registry write testing on web, copy the API test token from `Settings` and use it with the [`radio-pad-registry`](https://github.com/briceburg/radio-pad-registry) API.

When you deploy the web app, add the deployed origin and redirect URI to the same Google web client, or create a separate production client.

### Testing

The `remote-control` component uses Vitest + jsdom for headless domain logic testing.

To run the test suite for client logic:

```bash
npm test
```

To run tests in watch mode during development:

```bash
npm run test:watch
```

### Android development

Create a Google `Android` OAuth client:

- package: `net.iceburg.radio`
- signing certificate fingerprint: use your local debug or release fingerprint

Then run:

```bash
npx cap add android
npm run build
npx cap sync
npx cap run android
```

### iOS development

Create a Google `iOS` OAuth client:

- bundle identifier: `net.iceburg.radio`
- save the iOS client ID
- save the reversed URL scheme

Then create a local iOS config file:

```bash
cp ios/App/App/GoogleSignIn.local.xcconfig.example \
  ios/App/App/GoogleSignIn.local.xcconfig
```

Set these values in `ios/App/App/GoogleSignIn.local.xcconfig`:

- `GOOGLE_IOS_CLIENT_ID`
- `GOOGLE_IOS_REVERSED_CLIENT_ID`

Then run:

```bash
npx cap add ios
npx cap sync ios
```

Open the iOS project in Xcode and run it there.

## Development

### Contributing

Pull requests and bug reports are welcome! Please [open an issue](https://github.com/briceburg/radio-pad/issues) or submit a PR.

## Support

For questions or help, please open an issue on the [GitHub repository](https://github.com/briceburg/radio-pad/issues).

## License

[GNU Affero General Public License v3.0](./LICENSE)
