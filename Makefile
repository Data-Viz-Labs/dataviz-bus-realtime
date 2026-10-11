# Madrid bus simulator. `make help` lists the targets.

AWS_REGION ?= eu-west-1
VENV       ?= venv
PY         := $(VENV)/bin/python
TF         := terraform -chdir=terraform
IMAGE_TAG  ?= $(shell git rev-parse --short HEAD 2>/dev/null || echo latest)
GTFS_URL   := https://servicios.emtmadrid.es:8443/gtfs/transitemt.zip
LINE_IDS   := $(shell grep -E '^  - line_id:' data/lines.yaml | sed -E 's/.*"(.*)"/\1/' | paste -sd, -)

.PHONY: help venv test lint run preview web network import-gtfs init plan deploy image destroy logs smoke

help:
	@echo "Local (no AWS):"
	@echo "  venv          create $(VENV) with dev dependencies"
	@echo "  test          lint + tests"
	@echo "  run           simulate HOURS (2) from START (07:30) and print a health summary"
	@echo "  preview       serve the map at http://localhost:8000 with an in-process simulation"
	@echo "Data:"
	@echo "  import-gtfs   rebuild data/lines.yaml from the EMT Madrid GTFS feed"
	@echo "  network       snap lines to streets with Amazon Location Routes -> data/network.json"
	@echo "  web           export web/network.json for the map"
	@echo "AWS:"
	@echo "  plan          terraform plan"
	@echo "  deploy        build + push the image, apply terraform, restart the simulator"
	@echo "  smoke         check the deployed API returns moving, loaded buses"
	@echo "  logs          tail simulator logs"
	@echo "  destroy       remove every AWS resource"

venv:
	python3 -m venv $(VENV) && $(VENV)/bin/pip install -q -e ".[aws,dev]"

lint:
	$(VENV)/bin/ruff check sim tools tests

test: lint
	$(PY) -m pytest

run:
	$(PY) -m sim --hours $(or $(HOURS),2) --start $(or $(START),07:30) $(if $(JSONL),--jsonl $(JSONL))

preview: web
	$(PY) -m sim.preview --speedup $(or $(SPEEDUP),1)

web:
	$(PY) tools/export_web.py

network:
	AWS_REGION=$(AWS_REGION) $(PY) tools/build_network.py $(if $(ONLY),--only $(ONLY))

import-gtfs:
	mkdir -p .cache && curl -sfL -o .cache/gtfs.zip $(GTFS_URL)
	$(PY) -I tools/import_gtfs.py --gtfs .cache/gtfs.zip --out data/lines.yaml --lines $(or $(LINES),$(LINE_IDS))

init:
	$(TF) init -input=false

plan: init web
	$(TF) plan -var aws_region=$(AWS_REGION) -var image_tag=$(IMAGE_TAG)

image:
	$(eval REPO := $(shell $(TF) output -raw ecr_repository_url))
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(firstword $(subst /, ,$(REPO)))
	docker buildx build --platform linux/arm64 -t $(REPO):$(IMAGE_TAG) --push .

deploy: init web
	$(TF) apply -input=false -auto-approve -var aws_region=$(AWS_REGION) -var image_tag=$(IMAGE_TAG) -target aws_ecr_repository.simulator
	$(MAKE) image
	$(TF) apply -input=false -var aws_region=$(AWS_REGION) -var image_tag=$(IMAGE_TAG)
	@echo "Map: $$($(TF) output -raw site_url)"

smoke:
	$(PY) tools/smoke.py "$$($(TF) output -raw site_url)"

logs:
	aws logs tail /ecs/madrid-bus-simulator --follow --region $(AWS_REGION)

destroy: init
	$(TF) destroy -var aws_region=$(AWS_REGION)
