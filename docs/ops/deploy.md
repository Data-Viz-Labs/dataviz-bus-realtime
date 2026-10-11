# Deploying

The stack lives for about a day: it is deployed the day before the hackathon, filled with
synthetic history, run live during the event and shut down afterwards. Infrastructure and
software deploy separately:

| What | How | Trigger |
| --- | --- | --- |
| AWS infrastructure (`iac/stack/`) | `.github/workflows/infra.yml` or `make deploy` | PR → plan comment; manual dispatch → apply |
| Simulator image (`sim/`, `data/`, `Dockerfile`) | `.github/workflows/deploy-app.yml` | push to `main`, manual |
| Static site (`web/`, `docs/api/`) | `.github/workflows/deploy-web.yml` | push to `main`, manual |

GitHub Actions authenticates to AWS with OIDC: no access keys are stored in GitHub.

## 1. One-time bootstrap (account admin)

Run once per AWS account, with admin credentials, from a clone of the repo:

```sh
terraform -chdir=iac/bootstrap init
terraform -chdir=iac/bootstrap apply
```

It creates, with **local state** (`iac/bootstrap/terraform.tfstate`, keep it):

- an S3 bucket for the main stack's state (versioned, encrypted, private; locking uses an
  S3 lock file, no DynamoDB table),
- the GitHub OIDC provider (pass `-var github_oidc_provider_arn=...` if the account already has
  one: only one may exist per account),
- `madrid-bus-gh-plan`: read-only on the account plus the state bucket; assumable by pull
  requests and by `main`,
- `madrid-bus-gh-deploy`: administrator; assumable only by jobs in the GitHub environment
  `production`,
- `iac/stack/backend.hcl`, which `terraform init -backend-config=backend.hcl` uses.

The deploy role has `AdministratorAccess` because the apply creates IAM roles, CloudFront,
Location, IoT, Glue/Athena and Budgets resources in an account dedicated to the event. Protect
it through the `production` environment (required reviewer, `main` only).

## 2. GitHub environment and variables

Create the `production` environment (Settings → Environments) and restrict it to `main`; add
yourself as required reviewer if applies should be approved:

```sh
gh api -X PUT repos/Data-Viz-Labs/dataviz-bus-realtime/environments/production \
  -F 'deployment_branch_policy[protected_branches]=false' \
  -F 'deployment_branch_policy[custom_branch_policies]=true'
gh api -X POST repos/Data-Viz-Labs/dataviz-bus-realtime/environments/production/deployment-branch-policies \
  -f name=main -f type=branch
```

Repository variables (Settings → Secrets and variables → Actions → Variables; none are secret):

| Variable | Source | Used by |
| --- | --- | --- |
| `AWS_REGION` | `eu-west-1` | all |
| `TF_STATE_BUCKET` | bootstrap output `state_bucket` | infra |
| `AWS_PLAN_ROLE_ARN` | bootstrap output `plan_role_arn` | infra (plan) |
| `AWS_DEPLOY_ROLE_ARN` | bootstrap output `deploy_role_arn` | infra (apply), deploy-app, deploy-web |
| `BUDGET_EMAILS` | JSON list, e.g. `["you@example.com"]` (optional) | infra |
| `ECR_REPOSITORY_URL` | output `ecr_repository_url` | deploy-app |
| `ECS_CLUSTER` | output `ecs_cluster` | deploy-app |
| `ECS_SERVICE` | output `ecs_service` | deploy-app |
| `SITE_URL` | output `site_url` | deploy-app (smoke test) |
| `SITE_BUCKET` | output `site_bucket` | deploy-web |
| `CLOUDFRONT_DISTRIBUTION_ID` | output `cloudfront_distribution_id` | deploy-web |

The stack outputs exist only after the first apply. `make gh-vars` sets all of them from the
Terraform outputs; it runs:

```sh
gh variable set AWS_REGION                 --body "eu-west-1"
gh variable set TF_STATE_BUCKET            --body "$(terraform -chdir=iac/bootstrap output -raw state_bucket)"
gh variable set AWS_PLAN_ROLE_ARN          --body "$(terraform -chdir=iac/bootstrap output -raw plan_role_arn)"
gh variable set AWS_DEPLOY_ROLE_ARN        --body "$(terraform -chdir=iac/bootstrap output -raw deploy_role_arn)"
gh variable set ECR_REPOSITORY_URL         --body "$(terraform -chdir=iac/stack output -raw ecr_repository_url)"
gh variable set ECS_CLUSTER                --body "$(terraform -chdir=iac/stack output -raw ecs_cluster)"
gh variable set ECS_SERVICE                --body "$(terraform -chdir=iac/stack output -raw ecs_service)"
gh variable set SITE_BUCKET                --body "$(terraform -chdir=iac/stack output -raw site_bucket)"
gh variable set CLOUDFRONT_DISTRIBUTION_ID --body "$(terraform -chdir=iac/stack output -raw cloudfront_distribution_id)"
gh variable set SITE_URL                   --body "$(terraform -chdir=iac/stack output -raw site_url)"
```

(`iac/bootstrap` outputs are only available on the machine that ran the bootstrap; on
another machine copy the three values from the IAM / S3 consoles.)

## 3. Event-day runbook

**T-1 day**

1. Bootstrap the account if it is new (section 1).
2. `make deploy` — creates the stack, pushes the image, starts the simulator. Then
   `make gh-vars` so the pipelines can deploy further changes.
3. Confirm the budget alert subscription email(s) from AWS Notifications.
4. `make backfill YEARS=3` — one-off Fargate task (`python -m sim.backfill --years 3`) that
   writes the synthetic history to the data bucket. Follow it with `make logs`; it stops by
   itself when done.
5. `make keys` — prints one access key per group; distribute them.
6. `make smoke` — buses reported, moving and carrying people.

**During the event**

- `make logs` for the simulator; the map at `make smoke`'s URL.
- Code changes: merge to `main`; `deploy-app` / `deploy-web` roll them out (tests and smoke
  test included). Infra changes: PR (plan comment), merge, run `infra` with `action=apply`.
- Watch the budget emails (below) and Billing → Budgets.

**After**

- `make stop` scales the simulator to 0 (keeps data and site; restart with `make start`), or
- `make destroy` removes every resource. The bootstrap (state bucket, OIDC, roles) stays; destroy
  it with `terraform -chdir=iac/bootstrap destroy` after emptying the state bucket.

## 4. Cost expectations

Prices for eu-west-1, on-demand; check the README for the per-feature switches.

| Item | Price | Event (~1 day) |
| --- | --- | --- |
| Fargate simulator, 0.5 vCPU / 1 GB arm64 | ~$0.02/h | ~$0.5/day |
| Backfill task (one-off) | same rate × runtime | cents |
| IoT Core messages | $1 per million | depends on fan-out to groups |
| Athena | $5 per TB scanned (2 GiB cap per query ≈ $0.01) | cents to a few $ |
| Amazon Location tracker | $0.05 per 1,000 position writes | the main variable cost: limit with `tracked_lines` / `heartbeat_seconds` |
| S3, CloudFront, CloudWatch Logs, Lambda | per request / GB | cents |

Expect a few dollars for the whole event with the defaults; scale to 0 or destroy right after.

## 5. Budget alerts

`iac/modules/cost-management` creates two **account-wide** budgets (the account is meant
to be dedicated to the event; tag-filtered budgets would need the cost-allocation tag activated
24 h in advance):

- `madrid-bus-daily` (`daily_budget_limit`, default $25): actual spend over 50 %, 80 %, 100 %.
- `madrid-bus-monthly` (`monthly_budget_limit`, default $60): actual over 80 %, 100 %, and
  forecasted over 100 %.

Each alert goes to the SNS topic `madrid-bus-budget-alerts` (email subscriptions, confirm them
once) and directly to the `budget_alert_emails` addresses. AWS refreshes budget data a few
times a day, so alerts can lag spend by several hours: they are a safety net, not a real-time
meter. When one fires, `make stop` first and investigate after.
