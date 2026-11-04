# Load-test reference results

These preliminary observations describe short runs in one environment. They do not establish a production capacity limit. Repeat the workload after runtime, infrastructure, protocol, or client-traffic changes.

## 2026-11-04 UTC local slow-reader fault probe

Tested the combined #106–#110 review at `174eeaa`, using production image `radiopad-slow-reader-review:current` (`sha256:04bbb4d44b563e494a36c3a21189a2540bdf7a19104632aaed292c8e705826ba`), one worker, one CPU, 256 MiB, and a 128-process limit. The isolated container used its local ephemeral backend and built-in seeds; OIDC was disabled and no API writes or persistent mounts were used. Health, auth mode, player lookup, and controller authentication were checked before traffic.

Python 3.13.14 with websockets 17.4 connected one synthetic player and two controllers over loopback. All peers disabled compression. The player and healthy controller drained messages concurrently; the slow controller stopped receiving after authentication with `max_queue=1` and an 8 KiB effective TCP receive buffer. Its transport stopped reading after 0.012 seconds through the library's built-in queue backpressure. The player sent 2,000 distinct 32,178-byte state messages at 100 Hz for 20.001 seconds, under a 45-second client deadline.

| Observation | Result |
| --- | --- |
| Healthy delivery | Exact sequence of all 2,000 messages; no gaps or duplicates |
| Healthy latency | Median 0.581 ms; p95 0.891 ms; maximum 1.249 ms |
| Server RSS | 90,792 KiB before connections; 91,256 KiB at every traffic sample; 90,936 KiB after client cleanup |
| Process high-water RSS | 95,816 KiB throughout |
| Sampled server CPU | Maximum 5.25% of one CPU |
| Health | Every response was 204; sampled latency 1.267–1.614 ms |
| File descriptors | 14 before connections, 18–19 during the probe, 15 after client cleanup |

The server logged `Disconnecting slow subscriber`; the healthy controller and player remained connected. After reads resumed, the slow peer drained 123 buffered messages and closed without a WebSocket Close frame after 5.780 seconds. The probe verified isolation and bounded observed resource use; it did not require an orderly closing handshake. The server had no restart or OOM, and the container and network were removed afterward.

This was one short, compression-disabled, auth-disabled local fault probe. Docker CPU/RSS/FD samples were approximately 2.2 seconds apart; generator CPU and event-loop lag were not measured. It does not establish production capacity, authenticated/S3 behavior, or a strict socket-reclamation deadline.

The local reproduction command was `bash /tmp/radiopad-slow-reader-run.sh`, using temporary script `/tmp/radiopad-slow-reader-probe.py` and the image above. Raw results, client/server logs, and container metadata remain in `/tmp/radiopad-slow-reader-results.json`, `/tmp/radiopad-slow-reader-client.log`, `/tmp/radiopad-slow-reader-server.log`, and `/tmp/radiopad-slow-reader-container.json`. These are session artifacts, not checked-in or portable test tooling.

## 2026-11-03 local Registry runtime comparison

Compared merged #104 (`4f610c1`) with #105 (`7b079aa`) using production images, one worker, one CPU, and 256 MiB per server. Both used the same disposable Git fixture (`2c11a71`), with remote synchronization and OIDC disabled. The workload offered deflate compression, opened 250 rooms with two controllers each (750 sockets), and sent state and commands at 1 Hz per room. Each run had a 10-second ramp, 60-second hold, and 2-second drain. Runs were sequential in baseline/candidate/candidate/baseline order.

| Build | Repeat | Median server CPU | Peak process RSS | p95 connect | p95 auth | p95 command | p95 fan-out | Delivery |
| --- | --: | --: | --: | --: | --: | --: | --: | --- |
| #104 | 1 | 25.0% | 129.1 MiB | 5 ms | 4 ms | 3 ms | 3 ms | 100% |
| #105 | 1 | 16.1% | 123.0 MiB | 4 ms | 3 ms | 2 ms | 2 ms | 100% |
| #105 | 2 | 16.1% | 123.1 MiB | 4 ms | 3 ms | 2 ms | 2 ms | 100% |
| #104 | 2 | 24.6% | 129.2 MiB | 5 ms | 4 ms | 3 ms | 3 ms | 100% |

All connection, authentication, delivery, and planned-disconnect thresholds passed, with no socket errors. CPU is Docker's reported percentage of one CPU, sampled after the ramp and before drain; RSS is `/proc/1/status`'s `VmHWM`. The fixture remained unchanged, and all generators and test servers stopped. An initial staging attempt exited before generating traffic because the entrypoint rejected an unset inline SSH key; the measured runs used the same placeholder key on both builds. The entrypoint now permits an absent key.

The candidate used roughly 35% less CPU and 5% less peak process memory in this workload. This compares the complete runtime update, not individual dependency changes. Both builds used the same 64 KiB ceiling, so these results do not measure its benefit. The workload is busier than normal interactive control; local transport, disabled OIDC, no S3 or remote Git I/O, unmeasured generator CPU/event-loop lag, and short holds prevent production-capacity conclusions. Authenticated correctness is covered separately by Compose integration tests.

To repeat traffic against independently staged baseline and candidate servers with identical pre-registered fixtures:

```sh
RADIOPAD_LOAD_PLAYERS=250 RADIOPAD_LOAD_CONTROLLERS_PER_PLAYER=2 \
RADIOPAD_LOAD_REGISTER_PLAYERS=0 RADIOPAD_LOAD_RAMP_SECONDS=10 \
RADIOPAD_LOAD_HOLD_SECONDS=60 RADIOPAD_LOAD_DRAIN_SECONDS=2 \
tests/load/bin/run switchboard http://localhost:28751
```

## 2026-09-16 Fly baseline

The test targeted the unified Registry and switchboard directly at its Fly hostname. The app ran in `ord` on one shared CPU with 256 MiB RAM and one Uvicorn worker, using the Git data backend with 5,000 temporary deterministic players. Authentication was temporarily disabled, but controller handshakes still performed local player lookup. The remote generator observed a roughly 50 ms network floor.

Each room contained one player and two controllers. Once per second, the player published one state event and one controller published one command. Because the current broadcast sends every event to all three room subscribers, this produces six outbound WebSocket messages per room per second even though the harness measures only the two controller state deliveries and one player command delivery.

The exact application revisions were `a6416e2` before the performance PR and `3f6a5a7` after it. The same machine, data fixture, ramp shape, and client host were used for paired points.

| Build | Rooms | Sockets | Delivery | p95 connect | p95 auth | p95 command | p95 fan-out | App RSS/HWM | Result |
| --- | --: | --: | --: | --: | --: | --: | --: | --: | --- |
| Before | 50 | 150 | 100% | 488 ms | 71 ms | 64 ms | 67 ms | — | Passed |
| After | 50 | 150 | 100% | 197 ms | 68 ms | 63 ms | 66 ms | — | Passed |
| Before | 250 | 750 | 100% | 301 ms | 82 ms | 69 ms | 71 ms | 116/116 MiB | Passed |
| After | 250 | 750 | 100% | 217 ms | 123 ms | 68 ms | 70 ms | 118/122 MiB | Passed |
| After | 350 | 1,050 | about 72% | 223 ms | 105 ms | 13.0 s | 13.0 s | 135/137 MiB | Throughput knee |
| Before | 500 | 1,500 | — | — | — | — | — | — | OOM during ramp |
| After | 500 | 1,500 | — | — | — | — | — | — | OOM during ramp |

The successful runs recorded 100% connection, authentication, command, fan-out, and planned-disconnect outcomes. Their initial nonzero socket-error counters came from k6 error callbacks during intentional closing handshakes; the harness now ignores planned-close errors and was revalidated against clean and abruptly killed local switchboards. A later 300-room run was discarded because an orphaned generator overlapped it.

### Interpretation

- The candidate showed lower connection p95 at both paired points, while steady command and fan-out latency at 250 rooms was effectively unchanged. These are single samples, so repeat runs are required before treating the connection difference as a stable regression result.
- The 250-room run sustained 750 sockets and 1 Hz bidirectional traffic for a 45-second hold. At 350 rooms, connection and authentication still succeeded but message delivery accumulated roughly 13 seconds of latency and missed the drain window. CPU utilization and event-loop lag were not captured, so the bottleneck remains unconfirmed.
- Both revisions OOM-killed the 256 MiB machine while ramping toward 500 rooms. The bounded application queues in the candidate protect against individual slow subscribers, but they do not remove WebSocket protocol buffers, compression state, proxy cost, or work already queued below the application.
- No safe operating limit is established: these were single short samples with authentication disabled, so they also exclude the production OIDC/session and S3 authorization path. Repeated authenticated runs, runtime telemetry, and longer soaks are needed before recommending capacity.

### Next experiments

1. Compare server compression enabled and disabled with clients explicitly offering deflate. The older workload omitted k6's compression option, so the Fly results do not establish compression's cost for real clients. [Uvicorn enables it by default](https://uvicorn.dev/settings/), and the [`websockets` memory guide](https://websockets.readthedocs.io/en/latest/topics/memory.html) identifies compression as a major per-connection memory factor.
2. Route state only to controllers and commands only to the player. The current all-subscriber broadcast sends six messages per room per tick for three useful deliveries, so audience-aware routing can nearly halve steady outbound work for this workload.
3. Add low-cardinality runtime metrics for active rooms and sockets by role, event-loop lag, subscriber-queue overflow, send timeout, authentication duration, and process resources. Confirm CPU saturation rather than inferring it from the latency knee.
4. Revisit controller-auth concurrency only after measurement. The 250-room candidate burst reached 28 threads while offloading blocking Git/authz access; cap or cache that path only if repeated connection storms show it drives memory or tail latency. Include authenticated S3 connection bursts and cold OIDC discovery/JWKS loads: account-owner documents are read on every authentication, and fastapi-oidc 0.1.0 does not synchronize its discovery/JWKS caches. Define ownership freshness before adding a cache; preserve the existing revocation cache's load/invalidation ordering rather than replacing its lock with a decorator that loads outside the lock.
5. Run a separate slow-reader fault test. k6 consumes messages promptly, so this workload validates routing throughput and disconnect churn but not a peer whose TCP receive window stops advancing.

For larger deployments, scale switchboards horizontally by player-path affinity or registry-assigned shard URLs. More memory may delay the OOM, but one Python event loop will not make proportional use of additional CPUs; multiple single-worker switchboard shards are the clearer scaling unit.
