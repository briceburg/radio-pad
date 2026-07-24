# RadioPad

An internet radio player with physical, web, and mobile controllers that stay in sync.

![radio-pad-logo](./shared/assets/logo-dark.svg)

## How it works

- The [player](./player/) streams internet radio through a host's audio output and owns playback and volume.
- A USB [Macropad](./macropad-control/) or the web/mobile [remote control](./remote-control/) tells the player what to play.
- The [registry](./registry/) assigns players curated, shareable [RadioDials](./registry/seed-data/store/accounts/community/radio-dials/) of account-owned Stations and relays remote commands over WebSockets.

Macropad keys select Stations, the encoder adjusts volume or changes pages, and pressing the encoder stops playback. Remote controls discover players and RadioDials through the registry, then stay synchronized with the player's authoritative playback state.

![ai-enhanced-macropad-image](./shared/assets/radio-macropad-ai-image.webp)

## Components

| Component | Description |
| --- | --- |
| [player](./player/) | Audio runtime that loads its assigned RadioDial, streams the selected Station, and reports playback status. |
| [macropad-control](./macropad-control/) | Physical USB controller for Station selection, stop, and volume. |
| [registry](./registry/) | Stores accounts, Stations, RadioDials, and player assignments; serves the API and switchboard. |
| [remote-control](./remote-control/) | Web/mobile controller for discovering players and RadioDials, selecting Stations, and viewing status. |

<p align="center" width="100%">
  <img src="./shared/assets/icon-fancy-bg.svg" />
</p>

## Development

### Toolchain and dependency policy

Tool versions live at the smallest project boundary that consumes them. Python projects (`player`, `registry`, `macropad-control`, and `tests/integration`) own their `pyproject.toml` and `uv.lock`; `remote-control` owns its application `package.json` and `package-lock.json`; the root package owns repository-wide development tools.

Dependency updates should stay within that boundary: edit its manifest, regenerate only its lockfile, and run its `bin/ci` or the cheapest relevant check. Change Dockerfile or GitHub Actions runtime/tool pins only when the runtime or package-manager version intentionally changes. The root npm package is tooling-only, not a workspace; `remote-control` remains independently installable for Cloudflare and Capacitor builds.

Prettier discovers Markdown and supported first-party files across the repository; generated native projects, build output, tool caches, and lockfiles are ignored. Run `npm run format` to write canonical formatting; `bin/ci` verifies it.

Docker Compose provides the local development environment. All services mount source for live reloading.

```sh
# Start all services (unified: registry serves API + switchboard)
bin/dev up

# Or split mode (registry and switchboard as separate services)
docker compose -f compose.split.yaml up
```

`bin/dev` wraps `docker compose` and passes through compose arguments. By default it routes player audio through the host Pulse-compatible or native PipeWire socket and uses the physical macropad overlay when exactly one CDC2 data port is attached. If no macropad is found it starts without one; multiple ports require `RADIOPAD_MACROPAD_DEVICE`:

```sh
bin/dev up -d
RADIOPAD_AUDIO=off bin/dev up
RADIOPAD_MACROPAD=required bin/dev up -d --force-recreate player
RADIOPAD_MACROPAD=off bin/dev up
```

Set `RADIOPAD_AUDIO=off` to start without container audio. Set `RADIOPAD_PULSE_SOCKET=/run/user/.../pulse/native` or `RADIOPAD_PIPEWIRE_SOCKET=/run/user/.../pipewire-0` to choose a specific audio socket. Set `RADIOPAD_MACROPAD_DEVICE=/dev/ttyACM...` to choose a specific macropad data port. `bin/dev` does not mount or sync firmware; those steps stay explicit because they can prompt for privileges and write to the device.

Use `compose.audio.yaml` or `compose.macropad.yaml` directly only when you need explicit compose overlays outside `bin/dev`; in that case set the required variables from those overlay files yourself.

Registry and switchboard ports default to ephemeral; the web app defaults to port 5173 for stable OAuth redirect URIs. Copy `.env.example` to `.env` to configure overrides.

```sh
cp .env.example .env
```

View assigned ports with:

```sh
docker compose ps --format 'table {{.Service}}\t{{.Ports}}'
```

### Google sign-in

RadioPad uses one Google **Web application** OAuth client ID as the ID-token audience on every platform. In [Google Auth Platform](https://console.developers.google.com/auth/clients), create:

- Name: `RadioPad Web` (a private label shown only in Google Cloud)
- Authorized JavaScript origins: `http://localhost:5173` and `https://remote.radiopad.dev`
- Authorized redirect URIs: `http://localhost:5173/` and `https://remote.radiopad.dev/`

Do not add `https://registry.radiopad.dev`: the registry validates tokens but does not host the browser sign-in flow.

Use that same Web client ID in each environment:

| Environment | Configuration |
| --- | --- |
| Local Compose | `GOOGLE_CLIENT_ID` in the root `.env` |
| Standalone and native builds | `VITE_GOOGLE_CLIENT_ID` in `remote-control/.env` |
| Cloudflare Pages | `VITE_GOOGLE_CLIENT_ID` in `remote-control/wrangler.toml` |
| Fly registry | `REGISTRY_AUTH_OIDC_CLIENT_IDS` in `registry/fly.toml` |

Vite embeds the ID at build time. Client IDs, the issuer, and CORS origins are public configuration; the downloaded OAuth JSON and client secret are not used.

Android also requires an OAuth client for each package/signing-certificate pair; that client ID stays in Google Auth Platform. Follow the [Android debug setup](./remote-control/README.md#android-development) and [Google Play setup](./remote-control/README.md#google-play-release) for the required SHA-1 fingerprints and ownership step.

See [registry authentication and account-owner seeding](./registry/README.md#authentication-and-account-owner-seeding) for server authorization setup.

### Validation

Install the root tooling and remote-control dependencies once:

```sh
npm ci
(cd remote-control && npm ci)
```

Use `bin/ci` for routine repository validation: it verifies formatting and runs every component's CI concurrently without starting Docker. Run static integration validation and cross-service tests explicitly with `bin/ci integration`; without a file it runs the unified, split, and production-smoke Compose configurations. Passing a Compose file targets one configuration. Integration runs are isolated from local `.env` settings with ephemeral host ports, headless audio, and disabled Google auth unless a test explicitly enables it.

```sh
bin/ci
bin/ci integration
```

### Testing with a Macropad

Follow the [Macropad programming guide](./macropad-control/README.md#programming-the-macropad) for detailed setup and recovery. The normal hardware-backed development loop is:

```sh
macropad-control/bin/mount
macropad-control/bin/sync
macropad-control/bin/doctor

RADIOPAD_MACROPAD=required bin/dev up -d --force-recreate player
```

The discovery command intentionally fails when it finds zero or multiple data ports. Set `RADIOPAD_MACROPAD_DEVICE=/dev/ttyACM...` when more than one Macropad is attached. Sync before creating the player container because CircuitPython may reboot and renumber its USB interfaces. Use `macropad-control/bin/console` for the CircuitPython REPL; it selects a different USB CDC interface than `macropad-control/bin/data-port`.

## Architecture

### Deployment modes

The registry is controlled by the `REGISTRY_PROFILES` environment variable:

| Mode | `REGISTRY_PROFILES` | Description |
| --- | --- | --- |
| **Unified** | `api,switchboard` (default) | Single process serves the REST API and WebSocket switchboard. Simplest to deploy and operate. |
| **Split** | `api` / `switchboard` separately | API and switchboard run as independent services. The switchboard validates controller access via an HTTP call back to the API. Allows independent scaling of stateless API replicas vs. long-lived WebSocket connections. |

`compose.yaml` runs unified mode. `compose.split.yaml` demonstrates the split configuration and is also tested in CI.

### Core control flow

```mermaid
flowchart TD
    Macropad["Macropad controller"]
    Player["Player device<br/>🎵🎵🎵"]
    Registry["Registry<br/>(API + Switchboard)"]
    Remote["Remote control<br/>(mobile / web)"]

    Macropad <-- USB --> Player
    Player -- ws:playback_state --> Registry
    Registry -- ws:playback_start/stop --> Player
    Registry -- ws:playback_state --> Remote
    Remote -- ws:playback_start/stop --> Registry

    style Player stroke:#f9f,stroke-width:3px
    style Registry stroke:#bbf,stroke-width:3px
```

This is the baseline runtime view: controllers talk to players directly over USB or indirectly through the registry's switchboard.

### Registry and player access

```mermaid
flowchart TD
    User["User"]
    Remote["Remote control"]
    Registry["Registry API"]
    Switchboard["Registry Switchboard"]
    Player["Player device"]

    Remote -- "Read auth status + registered players" --> Registry
    Registry -- "Auth mode + public player data" --> Remote
    User -. "Google OIDC when auth enabled" .-> Remote
    Remote -- "Connect + authenticate event" --> Switchboard
    Switchboard -- "Validate account-owner control access" --> Registry
    Player -- "Connect as Player" --> Switchboard
    Switchboard -- "Route controls to Player" --> Player
```

Player control follows the registry's advertised auth mode:

- Player registry reads remain public.
- Every controller connection starts with an `authenticate` event; its token is null when registry auth is disabled.
- When registry auth is enabled, the remote signs in and supplies its OIDC token only in that first WebSocket message, never in the URL.
- The switchboard validates account-owner control access locally (unified mode) or through the registry API (split mode).
- The switchboard sends `authenticated` before replaying state or accepting commands. Unauthorized or expired sessions close with policy code `1008`.

## Contributing and support

Pull requests and bug reports are welcome. For questions, help, or feature requests, [open an issue](https://github.com/briceburg/radio-pad/issues).
