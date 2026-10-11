# Session log

Chronological record of how the project reached its current state, so a new session can
resume without re-deriving decisions. Dates are 2026-10-11 unless noted.

## 1. Diagnosis of the original version (plan mode)

- Indexed with codebase-memory MCP; reproduced locally with mocked AWS: 24 buses, ~3 % load
  frozen after 20 min, 11 stops never visited.
- Root causes: stop counts siloed between two feeders (never replenished / never drained), 1-ulp
  float comparison losing the terminus on L1/L46, strict `<` skipping first stops, inbound stop
  detection ignoring direction, env var mismatch, unused Amazon Location resources, Timestream
  closed to new customers, 709 tests with no system-level invariant.
- Plan approved: clean rewrite, Amazon Location (Routes, Maps, Tracker, Geofences).

## 2. Engine rewrite and real network

- `sim/` engine with circuits in metres, invariant tests, `make run`.
- Subagent imported 40 real lines from the EMT GTFS (`tools/import_gtfs.py`); schema moved to
  shared stops + per-direction stop lists; `demand_scale` calibrated to ~30 % rush load.
- Cost check via AWS Price List: full fleet on the tracker ≈ $440-3,200/month → map reads an S3
  snapshot; tracker only for `tracked_lines`; Lambda/DynamoDB dropped.
- Local preview verified with headless Chrome; tween fix for long jumps.
- v1 removed (tag `v1-archive`), single commit `5ffd05a` on main, pushed by the user.

## 3. Hackathon platform (this evolution)

User asked why WebSockets/MCP were dropped (they were coupled to Timestream; removing them was an
over-reach) and for MQTT, 1-week+ history, an architecture diagram, a software pipeline. Then:
one-day operation, 1-3 year backfill with Madrid events and randomness, budgets, OpenAPI/AsyncAPI
docs for every surface.

- Measured: 1 simulated day ≈ 57-100 s → years need an hourly model, last days microsimulated.
- Contracts first (group keys in `access.tf`, `sim/history.py` schemas, `history.tf`), then three
  parallel subagents: MQTT/IoT, API+MCP, CI/CD+budgets. Integrated their follow-ups (Dockerfile
  `CMD`, ECS `ignore_changes`, site docs upload, `next_stop_id` in snapshot, `API_URL` in config).
- Scenario + calibration + backfill written; tests found a real bug (concert weekends spilling
  into the next quarter / duplicates) → distinct Fridays per quarter.
- **Interruption 1**: the session was killed by RAM while a 3-year backfill ran with 8 workers
  (each day held ~1.5 M position dicts). Fix: hourly streaming to Parquet in workers, workers write
  to the sink directly, default <= 4 workers. Rerun: 12 min, 420 MB peak.
- **Interruption 2**: an ad-hoc validation script loaded all `stop_hourly` rows (34 M) as Python
  objects → OOM (exit 137). Lesson recorded in AGENTS.md: aggregate with Arrow, read only needed
  columns.
- Light Arrow validation confirmed the story in the data; widened overloaded-line candidates
  (only 4 with the distance threshold → 16 by rank).
- Memory bank, AGENTS.md, `.editorconfig`, `.tool-versions` written; changes committed in
  functional groups (Conventional Commits).

## 4. Repository reorganisation (same day, after the user pushed)

- The user wanted fewer, functional top-level folders with three-letter names. Agreed layout: TLA for moving
  parts (`iac`, `src`, `bin`, `web`), conventional names where tools expect them (`docs`, `tests`,
  `examples`, `data`, `memory-bank`).
- Done with `git mv` + reference fixes in one commit. Pitfalls met: a blanket `tools/` -> `bin/` rewrite also
  hit the MCP methods `tools/list` / `tools/call` (restored; contract tests would have failed);
  `tests/lambda` cannot be a package (`lambda` is a keyword) -> `tests/lambdas`.
- Verified: 149 tests, generated files unchanged, `make run`, `make preview`, Terraform 1.11 validate + fmt
  for `iac/stack` and `iac/bootstrap`, actionlint.

## Working practices that paid off

- Reproduce before fixing; measure (time, memory, prices) before choosing an architecture.
- System-level invariants and contract tests (docs vs code) over mocks.
- Subagents only on disjoint files, with explicit contracts and "report what you need from me".
- Ask before anything outward-facing or paid.
