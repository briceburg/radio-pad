# AGENTS.md

Guidance for coding agents working in `radio-pad/tests/load`.

## Scope

- Load tests are manual, opt-in capacity tools and never run in CI.
- `bin/run` owns endpoint discovery, the explicit remote-target guard, and launching the pinned k6 image. `switchboard.js` owns traffic only.
- Do not add deployment, data backup, fixture reset, or restoration behavior to the runner. Those stateful operations must remain visible, separately authorized, and independently verifiable.

## Safe remote workflow

- Prefer a dedicated app and disposable data repository. Registration persists players, so use prepared fixtures with `RADIOPAD_LOAD_REGISTER_PLAYERS=0` for repeatable remote runs.
- Before using a normal Git data source, record its exact remote SHA and create a remote backup branch. Restore with `--force-with-lease` against the exact fixture SHA; never use an unguarded force push or a broad reset.
- Compare baseline and candidate on the same app, machine size, worker count, backend fixture, auth mode, client host, and workload. Record every deviation.
- Increase load in stages and stop at the first resource, delivery, or latency knee. Treat an OOM, restart, growing backlog, or saturated generator as a failed point rather than waiting blindly for a summary.
- After a remote run, stop all load containers before restoring data. Verify the original backend SHA, normal auth configuration, fixture absence, known real resources, and service health before deleting the backup branch.
- If a runner hangs after its peer disappears, inspect the target logs and the specific container first. Terminate only the resolved load-container ID; do not use broad Docker cleanup commands.

## Evidence

- Record application and data revisions, image/version, region, CPU and memory, process count, auth/backend mode, workload variables, network location or RTT floor, and hold duration.
- Capture k6 outcome counts and latency percentiles together with server CPU, RSS/high-water memory, file descriptors, threads, active sockets, restarts, and relevant logs.
- Repeat points before claiming a performance change. Mark invalid or overlapping runs as discarded rather than averaging them into results.
- Keep dated environment-specific observations in `RESULTS.md`; keep general usage and safety guidance in `README.md`.

## Change preferences

- Preserve the dependency-free, pinned-container workflow.
- Prefer k6's standard `k6/websockets` global event loop over one VU per socket or an in-repository client framework.
- Keep thresholds focused on protocol correctness. Report latency distributions without inventing an SLO.
- Exercise slow readers separately; the standard workload intentionally consumes messages promptly.
