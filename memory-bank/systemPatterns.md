# System patterns

Architecture diagram and module table: `README.md` ("How it works"). This file records the
decisions and why they were taken.

## Simulation core (`sim/`)

- **One world owns everything**: `engine.World` holds every bus and every stop queue; a person who
  arrives at a stop is exactly the person a bus picks up. Root fix for the empty-bus bug.
- **Circuits in metres**: `network.Line` = outbound + inbound legs concatenated into one closed
  path; stops are `Visit`s at offsets, arrivals detected by visit index (no float equality, no
  `direction` flips). Circular lines = one leg. Terminal of the last leg normalised to offset 0
  with a 0.5 m tolerance (rounded street geometry).
- **Time budget per tick**: a bus spends `dt` driving, dwelling or laying over and may call at
  several stops per tick; residual time carries over.
- **Queues per (stop, line, direction)**; a stop's arrival rate is split among its queues;
  terminals only have riders for the departing leg.
- **Conditions hook**: `World.conditions` (a `Scenario`) supplies city demand, per-line demand and
  speed, per-stop event demand, suspended lines and per-line max load (crush load 1.2 for the
  overloaded line). Without it: plain daily profile (`demand.time_multiplier`).

## History (two tiers, same story)

- `scenario.generate` draws targets, the overloaded line (random among the 40 % farthest lines by
  rank) and all events from a secret seed. Serialised only to `private/scenario.json`.
- `backfill.calibrate`: microsimulates a calm school Tuesday 06:00-09:00, 3 rounds adjusting one
  demand factor per line until its 08:00 mean load hits its target; the last run is the
  **reference** for the hourly model.
- **Hourly model** (years): reference row x (scenario factors / reference factors) x noise, soft
  cap at max load; ~10-15 s per month. Service hours 06-23 only.
- **Microsimulation** (last N days + today until `--until`): one spawned process per day
  (05:00 warm-up), rows streamed hourly with `history.ParquetStream` (~200 MB per worker).
- `private/history_until.json` marks where generated history ends; the live service records
  (`history.LiveHistory`) only after it and reloads the scenario every flush.
- Validated continuity: model and microsimulation agree at the seam (8:00 weekday load
  ~0.46-0.49 both sides).

## Publishing (live service `sim/service.py`)

| Output | Cadence | Why |
|---|---|---|
| `live/snapshot.json` (site bucket, CloudFront) | 5 s | map + quick scripts; ~$3/month vs tracker for all buses |
| MQTT `madrid/lines/{id}/state` (retained) and `/calls` | 5 s / per tick | real time for participants; per-line batching keeps messages < 5 KB |
| Amazon Location tracker (tracked lines only) | heartbeat 120 s (+ stop calls if geofences) | Location showcase + 30-day history, cost-bounded |
| history Parquet (data bucket) | every 10 min | continues the generated history |
| `private/world.json` | 60 s | resume after restart (< 15 min old) |

## Access and APIs

- One key per group (`iac/stack/access.tf`, `random_password`); Lambdas only get SHA-256 hashes.
- MQTT: IoT custom authorizer (signing disabled) accepts the key as MQTT password, WSS query
  `token` or `x-api-key` header; subscribe-only policy on `madrid/*`.
- HTTP API + MCP: one Lambda behind a function URL (auth NONE, key checked in code). Athena with
  ExecutionParameters, partition pruning, read-only SQL guard, 2 GiB scan cap per query
  (workgroup), result limits. MCP: stateless Streamable HTTP, JSON responses.
- Glue tables use partition projection (`month=YYYY-MM`, `dt=YYYY-MM-DD`): no crawlers.

## Repository layout

Grouped by what gets deployed and how (details and rules in `AGENTS.md`): `iac/` Terraform, `src/container/`
the Fargate image (built with the repo root as context, so `data/` is baked in), `src/lambda/` one folder per
Lambda, `bin/` operator scripts, `web/` static site, `data/` shared inputs, `docs/`, `tests/` mirroring the code.
The Python package stays `sim` (`pyproject` finds it under `src/container`), so imports never changed.

## Delivery

- Terraform owns infrastructure; the ECS service ignores `task_definition` and `desired_count`
  so the `deploy-app` workflow and `make stop/start` own them.
- GitHub Actions with OIDC roles from `iac/bootstrap` (plan role read-only, deploy role in
  environment `production`). See `docs/ops/deploy.md`.
- Image `CMD` (not `ENTRYPOINT`) so `make backfill` can run `python -m sim.backfill` on the same
  task definition with a 4 vCPU / 8 GB override.
