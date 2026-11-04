# AGENTS.md

Guidance for coding agents working in `radio-pad/tests/load`.

- Follow the staging, comparison, and restoration procedure in [README.md](README.md). Remote load tests require explicit authorization and never run in CI.
- Keep deployment and data restoration outside the traffic runner. Stop every generator and verify restoration before finishing a remote test.
- Use the pinned k6 container and standard `k6/websockets` API; keep application dependencies unchanged.
- Keep dated measurements and raw artifacts with their PR or benchmark run; keep this directory focused on reusable workloads and instructions.
- Validate runner lifecycle changes with `node --test tests/load/switchboard.test.cjs` from the repository root. Keep slow-reader fault tests separate from the normal workload.
