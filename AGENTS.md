# AGENTS.md

Guidance for AI agents and contributors working on this repository. Read
`memory-bank/activeContext.md` and `memory-bank/progress.md` before non-trivial work; they hold the
current state and the next steps. Stable documentation lives in `README.md` and `docs/`.

## What this is

A real-time simulator of 40 real EMT Madrid bus lines with years of synthetic history, run on
AWS for one-day data hackathons. See `README.md` for the architecture and `docs/deploy.md` for
operations.

## Language

- Code, identifiers, comments, docstrings, commit messages, PR text, Terraform and technical
  docs: **English**.
- Audience-facing Spanish is deliberate in two places only: the web map labels (`web/index.html`)
  and the participants' guide (`docs/participantes.md`).

## Commands

```bash
make venv        # Python 3.12 virtualenv (.[aws,dev])
make test        # ruff + pytest; must stay green and fast (~20 s)
make run         # local health summary of the simulation
make preview     # local map at http://localhost:8000
make schemas     # regenerate terraform/history_schema.json, docs/api/datasets.md, MCP tool docs
make help        # everything else (deploy, backfill, keys, stop...)
```

Terraform needs >= 1.10 (`.tool-versions`). Validate with
`terraform -chdir=terraform init -backend=false && terraform -chdir=terraform validate` and keep
`terraform fmt -recursive` clean; CI checks both.

## Code style

- Python 3.12, `ruff` rules E, F, I, B, UP; line length 120; imports sorted with
  `force-sort-within-sections`. Type hints everywhere; `dataclass` for plain data.
- Match the surrounding code: concise modules, a module docstring that explains the *why*,
  short function docstrings, comments only where the code is not obvious. No dead code, no
  commented-out code, no speculative abstractions.
- `sim/` core (`network`, `engine`, `demand`, `scenario`, `history`, `config`) must not import
  AWS libraries. AWS lives in adapters (`sim/aws.py`, `sim/mqtt.py`) and the services
  (`sim/service.py`, `sim/backfill.py`); boto3/pyarrow are imported lazily where the core uses them.
- Lambdas (`lambdas/`) use the standard library and boto3 only. Module names must be unique
  across lambdas (tests import them by path).
- Positions are metres along a circuit and stops are visit indices: never compare floats to
  detect arrivals.

## Single sources of truth (generate, don't hand-edit)

| Source | Generated artefacts | Command |
|---|---|---|
| `sim/history.py` `SCHEMAS` | `terraform/history_schema.json`, `docs/api/datasets.md` | `make schemas` |
| MCP tool definitions in `lambdas/api/api_mcp.py` | tool section of `docs/api/mcp.md` | `make schemas` |
| EMT GTFS feed | `data/lines.yaml` | `make import-gtfs` |
| Amazon Location Routes | `data/network.json` | `make network` |
| `data/lines.yaml` (+ network.json) | `web/network.json` (not committed) | `make web` |

Tests fail when generated files are stale. API contracts (`docs/api/openapi.yaml`,
`asyncapi.yaml`, `mcp.md`) are checked against the code by tests: change both together.

## Tests

- Prefer system-level invariants over mocks: whole-network runs checking conservation of
  people, capacity, every stop served, buses moving (`tests/test_invariants.py`). That class of
  test is what catches real simulation bugs.
- AWS code is tested with `botocore.stub.Stubber` or fakes; tests never touch the network or AWS.
- Hypothesis only where generated inputs add value (random networks); keep example counts small.
- Keep the suite fast. Anything slow (multi-year backfills) is a manual check, not a test.

## Commits

Conventional Commits, lowercase type, imperative summary, body explaining why:

```
feat(sim): draw a secret scenario for the generated history

<why, what changed, anything surprising>

Co-Authored-By: <agent> <noreply@...>   # when an AI agent wrote the change
```

Types used: `feat`, `fix`, `test`, `docs`, `ci`, `build`, `chore`, `refactor`. Scopes in use:
`sim`, `service`, `realtime` (MQTT), `api`, `infra`, `data`, `web`. Group commits by function
(code + its tests, or a coherent infra/docs/ci change); every commit should leave `make test` green.

## Safety and cost rules

- Do not deploy, `terraform apply`, push, or run paid AWS calls (Routes, Athena, IoT) without the
  user's explicit go-ahead. Read-only checks (pricing API, docs) are fine.
- Amazon Location tracker writes and geofence evaluations are billed per position: keep
  `tracked_lines` small and `stop_geofences` off by default. Budgets alert by email
  (`terraform/modules/cost-management`).
- The generated scenario is the organisers' answer key: it stays in `private/` of the data bucket,
  is never served, and logs print event *counts* only, never dates or venues.
- Memory: never materialise full history tables as Python objects (`stop_hourly` is tens of
  millions of rows). Stream with `history.ParquetStream`, aggregate with Arrow, keep backfill
  workers <= 4 (~400 MB each).
- Never commit secrets, `terraform/backend.hcl`, state files, `.cache/` or generated
  `web/network.json`.
