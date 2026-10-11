# Tech context

## Stack

- **Python 3.12**: `pyyaml` (core); extras `aws` (boto3), `history` (pyarrow, numpy), `dev`
  (pytest, hypothesis, ruff, pyarrow, numpy). Package `sim` via `pyproject.toml`.
- **AWS** (eu-west-1 by default): ECS Fargate ARM64, ECR, S3, CloudFront (OAC), IoT Core
  (custom authorizer), Lambda (function URLs), Athena + Glue, Amazon Location (Maps v2 API key via
  `aws_cloudcontrolapi_resource` `AWS::Location::APIKey`, Routes v2, tracker, geofences),
  EventBridge, CloudWatch Logs, Budgets + SNS.
- **Terraform >= 1.10** (S3 backend with `use_lockfile`), providers aws ~> 6.33, archive, random.
  `terraform/bootstrap/` is a separate root with local state (state bucket + GitHub OIDC roles).
- **Web**: single-file MapLibre GL 4.7.1 map (`web/index.html`), Swagger UI 5.17.14 + AsyncAPI
  react component 1.4.10 (`web/docs.html`), all from unpkg.
- **CI/CD**: GitHub Actions `test`, `deploy-app` (native arm64 runner), `deploy-web`, `infra`.

## Local setup

```bash
make venv && make test            # ~20 s, 149 tests at last count
```

- asdf pins `.tool-versions` (python 3.12, terraform 1.11.4). The machine where this was built
  had terraform 1.5.5 globally; newer binaries were downloaded to a scratch dir for validation.
- No Docker on the original dev machine: the image has never been built locally.
- RAM ~14 GB: a 3-year backfill with 4 workers peaks at ~420 MB and takes ~12 min locally.
  Loading `stop_hourly` (34 M rows for 3 years) into Python objects OOM-killed the session.

## Data sources

- EMT GTFS `https://servicios.emtmadrid.es:8443/gtfs/transitemt.zip` (feed 2026-10-09 used),
  converted by `tools/import_gtfs.py` (formulas in its docstring). 40 lines, 1,723 stops,
  712 buses, `demand_scale` 1.3.
- Venues for events are public landmarks hard-coded in `sim/scenario.py` `VENUES`.

## Prices used for design decisions (eu-west-1, AWS Price List API, Oct 2026)

- Location: position writes $0.05/1k (first 500k) down to $0.0125/1k; geofence evaluations
  $0.16/1k down to $0.06/1k; map tiles $0.04/1k; routes $0.50/1k.
- IoT Core: $1.00 per million messages (5 KB units), rules/actions $0.15 per million each,
  connectivity $0.08 per million minutes.
- Full fleet on the tracker ≈ $440/month; with geofences ≈ $3,200/month → default tracks line 27 only.
