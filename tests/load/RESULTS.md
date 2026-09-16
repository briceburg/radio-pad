# Load-test reference results

These results are a dated capacity reference, not a portable service-level guarantee. Repeat the workload after runtime, infrastructure, protocol, or client-traffic changes.

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
- One shared CPU sustained 250 rooms, 750 sockets, and the corresponding 1 Hz bidirectional traffic for the 45-second hold. At 350 rooms, connection and authentication still succeeded but message delivery accumulated roughly 13 seconds of latency and missed the drain window. This is a throughput/backpressure knee rather than an idle-socket limit.
- Both revisions OOM-killed the 256 MiB machine while ramping toward 500 rooms. The bounded application queues in the candidate protect against individual slow subscribers, but they do not remove WebSocket protocol buffers, compression state, proxy cost, or work already queued below the application.
- Until repeated soaks and runtime telemetry exist, treat roughly 150–200 rooms with two controllers each as a conservative operating envelope for this exact machine and traffic shape. This is capacity guidance, not an admission limit.

### Next experiments

1. Disable WebSocket per-message deflate and repeat 250, 350, and 500 rooms. [Uvicorn enables it by default](https://www.uvicorn.org/settings/), while RadioPad messages are small; the underlying [`websockets` memory guide](https://websockets.readthedocs.io/en/latest/topics/memory.html) identifies compression as the primary per-connection memory factor and reports a substantially smaller baseline when disabled.
2. Route state only to controllers and commands only to the player. The current all-subscriber broadcast sends six messages per room per tick for three useful deliveries, so audience-aware routing can nearly halve steady outbound work for this workload.
3. Add low-cardinality runtime metrics for active rooms and sockets by role, event-loop lag, subscriber-queue overflow, send timeout, authentication duration, and process resources. Confirm CPU saturation rather than inferring it from the latency knee.
4. Revisit controller-auth concurrency only after measurement. The 250-room candidate burst reached 28 threads while offloading blocking Git/authz access; cap or cache that path only if repeated connection storms show it drives memory or tail latency.
5. Run a separate slow-reader fault test. k6 consumes messages promptly, so this workload validates routing throughput and disconnect churn but not a peer whose TCP receive window stops advancing.

For larger deployments, scale switchboards horizontally by player-path affinity or registry-assigned shard URLs. More memory may delay the OOM, but one Python event loop will not make proportional use of additional CPUs; multiple single-worker switchboard shards are the clearer scaling unit.
