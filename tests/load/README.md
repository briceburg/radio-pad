# Load tests

The load tests are manual capacity tools, not correctness tests or part of `bin/ci`. They use a pinned [Grafana k6](https://grafana.com/docs/k6/latest/) container, so they add no application or repository-tooling dependencies. See [RESULTS.md](RESULTS.md) for the dated reference run and current capacity guidance.

## Switchboard

`switchboard.js` models independent rooms containing one player and one or more controllers. Several rooms share each event-driven k6 virtual user so the load generator can sustain many sockets without one JavaScript runtime per player. Connections are spread across the ramp, held concurrently, then drained and closed. During the hold, the player publishes playback state to every controller and one controller sends commands back to the player.

The setup phase registers deterministic players through the Registry API. Repeated runs update the same records, but the records remain afterward because the Registry has no delete API. Use a disposable local or staging data store.

Start a split local stack:

```sh
RADIOPAD_AUDIO=off RADIOPAD_MACROPAD=off bin/dev -f compose.split.yaml up -d --build registry switchboard
```

The runner discovers its published ports and runs the conservative default workload of 10 players and 10 controllers:

```sh
tests/load/bin/run switchboard
```

Increase capacity in steps rather than jumping directly to a large target:

```sh
RADIOPAD_LOAD_PLAYERS=500 \
RADIOPAD_LOAD_CONTROLLERS_PER_PLAYER=3 \
RADIOPAD_LOAD_RAMP_SECONDS=60 \
RADIOPAD_LOAD_HOLD_SECONDS=300 \
tests/load/bin/run switchboard
```

The runner rejects non-local endpoints unless the invocation includes `RADIOPAD_LOAD_ALLOW_REMOTE=1`. Authenticated environments also require an access token authorized to register and control players in `RADIOPAD_LOAD_ACCOUNT`:

```sh
RADIOPAD_LOAD_ALLOW_REMOTE=1 \
RADIOPAD_LOAD_ACCOUNT=briceburg \
RADIOPAD_LOAD_ACCESS_TOKEN=... \
tests/load/bin/run switchboard https://registry.example
```

The base URL form derives `https://registry.example/api` and `wss://registry.example/switchboard`. For deployments with separate hosts, set `REGISTRY_URL` and `SWITCHBOARD_URL` instead. Either variable can also be set alone when the other endpoint shares its origin. If the Compose project uses `COMPOSE_PROJECT_NAME`, supply the same value during discovery.

### Remote before/after runs

The runner only generates traffic. Keep deployment, fixture creation, backup, and restoration explicit and separate so a load command cannot mutate or reset a data source unexpectedly.

Prefer a dedicated staging app and disposable data repository. If a sole-user deployment must use its normal Git data source, use this sequence:

1. Record the application revision, image, machine size, worker count, auth mode, backend revision, and test parameters. Freeze unrelated writes for the test window.
2. Record the exact data-source `main` SHA and push that SHA to a dated backup branch.
3. Add deterministic load players in one fixture commit and push it to `main`. Record the fixture SHA and verify the first and last players through the deployed API.
4. Deploy the baseline application revision. Change only settings required by the test, then verify health, auth mode, and fixture visibility.
5. Run the same staged workload against the baseline and candidate revisions on the same machine and data. Start small, stop at the first latency, delivery, CPU, or memory knee, and repeat stable points before drawing regression conclusions.
6. Stop every load generator. Restore data `main` with `--force-with-lease` pinned to the recorded fixture SHA, deploy the intended application revision with its normal configuration, and verify the original SHA, auth mode, known resources, fixture absence, and service health.
7. Delete the backup branch only after all restoration checks pass.

Capture server CPU, RSS/high-water memory, file descriptors, thread count, active sockets, restarts, and logs alongside k6 output. A short ramp locates a knee; it is not a soak test. Repeat candidate capacity points for at least five minutes, then run a longer soak before setting production limits.

### Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `REGISTRY_URL` | discovered or derived | Registry API base, including `/api`. |
| `SWITCHBOARD_URL` | discovered or derived | Switchboard base, including `/switchboard`. |
| `RADIOPAD_LOAD_PLAYERS` | `10` | Concurrent player rooms. |
| `RADIOPAD_LOAD_ROOMS_PER_VU` | `10` | Rooms multiplexed by each k6 virtual user. |
| `RADIOPAD_LOAD_CONTROLLERS_PER_PLAYER` | `1` | Controllers connected to each player. |
| `RADIOPAD_LOAD_RAMP_SECONDS` | `10` | Time over which room connections are opened. |
| `RADIOPAD_LOAD_HOLD_SECONDS` | `30` | Time at peak concurrency. |
| `RADIOPAD_LOAD_DRAIN_SECONDS` | `1` | Delivery grace period before sockets close. |
| `RADIOPAD_LOAD_EVENT_INTERVAL_MS` | `1000` | Per-room playback-state and command interval. |
| `RADIOPAD_LOAD_ACCOUNT` | `load-test` | Account containing generated players. |
| `RADIOPAD_LOAD_PLAYER_PREFIX` | `load-player` | Prefix for deterministic generated player IDs. |
| `RADIOPAD_LOAD_PLAYER_ID_WIDTH` | `6` | Minimum numeric suffix width, keeping IDs stable across staged runs. |
| `RADIOPAD_LOAD_REGISTER_PLAYERS` | `1` | Register players during setup; set to `0` when they already exist. |
| `RADIOPAD_LOAD_ACCESS_TOKEN` | unset | Registry access token sent by controllers and registration requests. |
| `RADIOPAD_LOAD_RADIO_DIAL_URL` | community dial on `REGISTRY_URL` | RadioDial source reported by generated players. |
| `RADIOPAD_LOAD_RADIO_DIAL_REVISION` | `"load-test"` | RadioDial revision reported by generated players. |
| `RADIOPAD_LOAD_ALLOW_REMOTE` | unset | Set to `1` to acknowledge a non-local target. |

Additional arguments after `switchboard` are passed to `k6 run`.

### Reading a run

The tagged `outcomes` thresholds require more than 99% successful connections, authentications, clean shutdowns, fan-out deliveries, and command deliveries, with no unexpected socket errors. Separate connection, authentication, fan-out, and command latency trends report percentiles without imposing an arbitrary service-level objective.

Watch switchboard CPU, memory, file descriptors, and event-loop responsiveness alongside k6. Also watch the load generator: a saturated generator can look like a server limit. Repeat each step long enough to reach steady state and record the first resource or latency knee.

k6 consumes WebSocket messages promptly, so this workload does not simulate a TCP peer that stops reading. It exercises high fan-out and disconnect churn; true slow-reader validation requires a small purpose-built client or network shaping and should remain a separate destructive robustness test.

For a non-persistent production baseline, disable registration and controllers. This opens unregistered player sockets and publishes state without writing Registry data; it does not measure authentication or controller fan-out:

```sh
RADIOPAD_LOAD_ALLOW_REMOTE=1 \
RADIOPAD_LOAD_REGISTER_PLAYERS=0 \
RADIOPAD_LOAD_CONTROLLERS_PER_PLAYER=0 \
tests/load/bin/run switchboard https://registry.example
```
