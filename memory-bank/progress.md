# Progress

## What works (verified locally)

- Simulation on the real network: rush-hour mean load ~28 % with the plain profile; with a
  scenario, line targets ~20-75 % and the overloaded line ~95-100 % (max 120 %). All stops served,
  passengers conserved (invariant tests).
- `make preview`: map with 712 buses, line filter, occupancy colours (headless Chrome screenshots).
- Backfill: 3 years + 7 detailed days in ~12 min, peak ~420 MB (4 workers), 386 MB of Parquet.
  The data shows the scenario: snowstorm days with zero trips matching the answer key, July/August
  dip (Aug ~53 % of October), weekend dip (Sun ~61 % of weekdays), overloaded line on top of
  the 08:00 load ranking.
- Live service wiring with fake AWS clients: snapshot, MQTT, tracker, state, history after the
  backfill marker.
- API/MCP handler, IoT authorizer, MQTT publisher, network builder: tested with botocore stubs.
- Terraform validates with 1.11/1.13 (`init -backend=false`), fmt clean; workflows pass actionlint.
- 149 tests, ~20 s.

## Not verified / left to do

- Never deployed: CloudFront OAC, IoT custom authorizer over WSS, Lambda function URL
  permissions, `aws_cloudcontrolapi_resource` map key, Budgets, OIDC roles — all untested on AWS.
- Docker image never built (no Docker locally); `deploy-app` builds it on GitHub's arm64 runner.
- `data/network.json` (street geometry) not generated yet: buses run straight stop to stop.
- MCP server untested with a real client; Swagger "try it out" against the real API untested.
- Weekend frequency reduction and night service hours are not modelled in the microsimulation.

## Known issues / caveats

- Seven lines hit the importer's 25-bus cap; capacity 90 everywhere (GTFS has no vehicle info).
- The hourly model's stop-level waiting is an estimate (reference x factors), not simulated.
- Generated history ends at `--until` (default: now, floored to the hour); hours between the end
  of the backfill and the next history flush are recorded by the live service.

## Evolution of decisions

See `sessionLog.md` for the chronological account and the reasons behind each pivot.
