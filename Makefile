# Madrid bus simulator. `make help` lists the targets.

AWS_REGION ?= eu-west-1
VENV       ?= venv
PY         := $(VENV)/bin/python
TF         := terraform -chdir=iac/stack
TFB        := terraform -chdir=iac/bootstrap
IMAGE_TAG  ?= latest
GTFS_URL   := https://servicios.emtmadrid.es:8443/gtfs/transitemt.zip
LINE_IDS   := $(shell grep -E '^  - line_id:' data/lines.yaml | sed -E 's/.*"(.*)"/\1/' | paste -sd, -)
YEARS      ?= 3
CLUSTER     = $$($(TF) output -raw ecs_cluster)
SERVICE     = $$($(TF) output -raw ecs_service)

.PHONY: help venv test lint run preview web schemas network import-gtfs backfill-local \
        bootstrap init plan deploy image backfill keys start stop smoke logs mqtt-sub gh-vars destroy

help:
	@echo "Local (no AWS):"
	@echo "  venv            create $(VENV) with dev dependencies"
	@echo "  test            lint + tests"
	@echo "  run             simulate HOURS (2) from START (07:30) and print a health summary"
	@echo "  preview         serve the map at http://localhost:8000 with an in-process simulation"
	@echo "  backfill-local  generate YEARS of history into .cache/history"
	@echo "Data:"
	@echo "  import-gtfs     rebuild data/lines.yaml from the EMT Madrid GTFS feed"
	@echo "  network         snap lines to streets with Amazon Location Routes -> data/network.json"
	@echo "  web / schemas   export web/network.json / history schema + MCP tool docs"
	@echo "AWS (see docs/ops/deploy.md):"
	@echo "  bootstrap       once per account: state bucket + GitHub OIDC roles"
	@echo "  plan / deploy   terraform plan / build + push the image and apply"
	@echo "  backfill        generate YEARS (3) of history on Fargate"
	@echo "  keys            print the access key of every group"
	@echo "  stop / start    scale the simulator to 0 / 1"
	@echo "  smoke / logs    check the live snapshot / tail simulator logs"
	@echo "  mqtt-sub        subscribe to LINE (27) over MQTT (needs paho-mqtt and KEY=...)"
	@echo "  gh-vars         set the GitHub variables the workflows use"
	@echo "  destroy         remove every AWS resource"

venv:
	python3 -m venv $(VENV) && $(VENV)/bin/pip install -q -e ".[aws,dev]"

lint:
	$(VENV)/bin/ruff check src bin tests examples

test: lint
	$(PY) -m pytest

run:
	$(PY) -m sim --hours $(or $(HOURS),2) --start $(or $(START),07:30) $(if $(JSONL),--jsonl $(JSONL))

preview: web
	$(PY) -m sim.preview --speedup $(or $(SPEEDUP),1)

web:
	$(PY) bin/export_web.py

schemas:
	$(PY) bin/export_schemas.py
	$(PY) bin/export_mcp_docs.py

network:
	AWS_REGION=$(AWS_REGION) $(PY) bin/build_network.py $(if $(ONLY),--only $(ONLY))

import-gtfs:
	mkdir -p .cache && curl -sfL -o .cache/gtfs.zip $(GTFS_URL)
	$(PY) -I bin/import_gtfs.py --gtfs .cache/gtfs.zip --out data/lines.yaml --lines $(or $(LINES),$(LINE_IDS))

backfill-local:
	$(PY) -m sim.backfill --years $(YEARS) --out .cache/history

bootstrap:
	$(TFB) init -input=false && $(TFB) apply -var aws_region=$(AWS_REGION)

init:
	@test -f iac/stack/backend.hcl || { echo "iac/stack/backend.hcl missing: run 'make bootstrap' first"; exit 1; }
	$(TF) init -input=false -backend-config=backend.hcl

plan: init web
	$(TF) plan -var aws_region=$(AWS_REGION) -var image_tag=$(IMAGE_TAG)

image:
	$(eval REPO := $(shell $(TF) output -raw ecr_repository_url))
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(firstword $(subst /, ,$(REPO)))
	docker buildx build --platform linux/arm64 -f src/container/Dockerfile -t $(REPO):$(IMAGE_TAG) --push .

deploy: init web
	$(TF) apply -input=false -auto-approve -var aws_region=$(AWS_REGION) -var image_tag=$(IMAGE_TAG) -target aws_ecr_repository.simulator
	$(MAKE) image
	$(TF) apply -input=false -var aws_region=$(AWS_REGION) -var image_tag=$(IMAGE_TAG)
	@echo "Map:      $$($(TF) output -raw site_url)"
	@echo "API docs: $$($(TF) output -raw site_url)docs.html"
	@echo "API:      $$($(TF) output -raw api_url)"
	@echo "MCP:      $$($(TF) output -raw mcp_url)"
	@echo "MQTT:     $$($(TF) output -raw mqtt_websocket_url)"

# One-off Fargate task with the simulator image: 4 vCPU / 8 GB, about 15 min for 3 years.
backfill:
	net=$$(aws ecs describe-services --region $(AWS_REGION) --cluster $(CLUSTER) --services $(SERVICE) \
	  --query 'services[0].networkConfiguration' --output json); \
	td=$$(aws ecs describe-services --region $(AWS_REGION) --cluster $(CLUSTER) --services $(SERVICE) \
	  --query 'services[0].taskDefinition' --output text); \
	aws ecs run-task --region $(AWS_REGION) --cluster $(CLUSTER) --launch-type FARGATE --task-definition $$td \
	  --network-configuration "$$net" \
	  --overrides '{"cpu":"4096","memory":"8192","containerOverrides":[{"name":"simulator","cpu":4096,"memory":8192,"command":["python","-m","sim.backfill","--years","$(YEARS)"]}]}' \
	  --query 'tasks[0].taskArn' --output text

keys:
	@$(TF) output -json group_keys

stop:
	aws ecs update-service --region $(AWS_REGION) --cluster $(CLUSTER) --service $(SERVICE) --desired-count 0 --query 'service.desiredCount'

start:
	aws ecs update-service --region $(AWS_REGION) --cluster $(CLUSTER) --service $(SERVICE) --desired-count 1 --query 'service.desiredCount'

smoke:
	$(PY) bin/smoke.py "$$($(TF) output -raw site_url)"

logs:
	aws logs tail /ecs/madrid-bus-simulator --follow --region $(AWS_REGION)

mqtt-sub:
	MQTT_ENDPOINT=$$($(TF) output -raw mqtt_endpoint) MQTT_AUTHORIZER=$$($(TF) output -raw mqtt_authorizer_name) \
	  API_KEY=$(KEY) LINE=$(or $(LINE),27) $(PY) examples/mqtt_subscribe.py

gh-vars:
	gh variable set AWS_REGION                 --body "$(AWS_REGION)"
	gh variable set TF_STATE_BUCKET            --body "$$($(TFB) output -raw state_bucket)"
	gh variable set AWS_PLAN_ROLE_ARN          --body "$$($(TFB) output -raw plan_role_arn)"
	gh variable set AWS_DEPLOY_ROLE_ARN        --body "$$($(TFB) output -raw deploy_role_arn)"
	gh variable set ECR_REPOSITORY_URL         --body "$$($(TF) output -raw ecr_repository_url)"
	gh variable set ECS_CLUSTER                --body "$$($(TF) output -raw ecs_cluster)"
	gh variable set ECS_SERVICE                --body "$$($(TF) output -raw ecs_service)"
	gh variable set SITE_BUCKET                --body "$$($(TF) output -raw site_bucket)"
	gh variable set CLOUDFRONT_DISTRIBUTION_ID --body "$$($(TF) output -raw cloudfront_distribution_id)"
	gh variable set SITE_URL                   --body "$$($(TF) output -raw site_url)"

destroy: init
	$(TF) destroy -var aws_region=$(AWS_REGION)
