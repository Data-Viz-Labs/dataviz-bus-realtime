# Active context

_Last updated: 2026-10-11._

## Current focus

Closing the "hackathon platform" evolution: scenario-driven history, MQTT, HTTP API + MCP,
CI/CD, budgets and documentation. Everything is implemented and tested locally; **nothing has
been deployed** and the image has never been built.

## Recent changes (this evolution)

- `sim/scenario.py`: secret scenario (line targets by centrality, overloaded peripheral line,
  calendar, events). Overloaded-line candidates widened to the 40 % farthest lines by rank after
  noticing only 4 candidates with a distance threshold.
- `sim/history.py`, `sim/backfill.py`: table schemas, recorder, streaming Parquet, calibration,
  hourly model, per-day microsimulation workers (memory fix after an OOM).
- `sim/service.py`: live service now loads the scenario, records history after
  `private/history_until.json`, publishes MQTT; state moved to the data bucket.
- `sim/mqtt.py`, `lambdas/iot_authorizer`, `lambdas/api` (REST + MCP), Terraform `iot.tf`,
  `api.tf`, `history.tf`, `access.tf`, budgets module rewrite, `terraform/bootstrap`.
- Workflows `deploy-app`, `deploy-web`, `infra`; Makefile runbook targets.
- Docs: `docs/api/{openapi.yaml,asyncapi.yaml,mcp.md,datasets.md}`, `docs/deploy.md`,
  `docs/participantes.md`, README rewrite, `AGENTS.md`.

## Next steps

1. `asdf install terraform 1.11.4` (or equivalent) on the operator machine.
2. Admin: `make bootstrap`, create GitHub environment `production`, `make gh-vars`
   (`docs/deploy.md`).
3. Optional: `make network` (Amazon Location Routes, ~140 requests) and commit `data/network.json`.
4. Day before the event: `make deploy`, `make backfill YEARS=3`, `make keys`, `make smoke`;
   verify `docs.html`, MQTT (`make mqtt-sub KEY=...`), API and MCP with a real key.
5. After the event: `make stop` or `make destroy`.
6. Nice to have: weekend frequency reduction (fleet is constant all week), night service hours in
   the microsimulation (currently filtered at write time), a check that Athena query costs stay
   small with participants' free SQL.

## Active decisions and preferences

- User: keep docs/commits neutral (no "v2"/"new phase" wording); ask before deploy/push/paid
  calls; Spanish for participants, English for code and technical docs.
- Default cost posture: tracker on line 27 only, geofences off, budgets $25/day and $60/month.
- The answer key must never be logged or served.
