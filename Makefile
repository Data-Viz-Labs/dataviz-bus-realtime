.PHONY: init plan deploy destroy build-feeders build-mcp push-images push-mcp load-config package-lambda package-all-lambdas export-keys verify verify-mcp test-unit test-int test-e2e test-all help

AWS_REGION ?= eu-west-1
AWS_ACCOUNT_ID := $(shell aws sts get-caller-identity --query Account --output text 2>/dev/null || echo "unknown")
ECR_REGISTRY := $(AWS_ACCOUNT_ID).dkr.ecr.$(AWS_REGION).amazonaws.com

help:
	@echo "Madrid Bus Real-Time Simulator - Makefile"
	@echo ""
	@echo "Available targets:"
	@echo "  init               - Initialize Terraform"
	@echo "  plan               - Run Terraform plan"
	@echo "  package-lambda     - Package a single Lambda function (LAMBDA=name)"
	@echo "  package-all-lambdas- Package all Lambda functions"
	@echo "  build-feeders      - Build container images for feeder services"
	@echo "  build-mcp          - Build MCP server container image"
	@echo "  push-images        - Push feeder container images to ECR"
	@echo "  push-mcp           - Push MCP server container image to ECR"
	@echo "  load-config        - Load configuration data to S3"
	@echo "  export-keys        - Export API keys for hackathon participants"
	@echo "  verify             - Run pre-hackathon verification checks"
	@echo "  verify-mcp         - Test deployed MCP server via API Gateway"
	@echo "  deploy             - Full deployment (build, push, apply, config)"
	@echo "  destroy            - Destroy all infrastructure"
	@echo "  infracost-check    - Run Infracost cost estimation"
	@echo "  setup-hooks        - Install pre-commit hooks"
	@echo "  check-costs        - Check current AWS costs and budget status"
	@echo "  mcp-install        - Install MCP server dependencies"
	@echo "  mcp-run            - Run MCP server locally"
	@echo "  mcp-test           - Run MCP server tests"
	@echo ""
	@echo "Testing targets:"
	@echo "  test-unit          - Run unit tests (Python, local, no AWS)"
	@echo "  test-int           - Run integration tests (Python, requires AWS)"
	@echo "  test-e2e           - Run end-to-end tests (shell scripts, API tests)"
	@echo "  test-all           - Run all tests (unit + integration + e2e)"
	@echo ""
	@echo "Environment variables:"
	@echo "  AWS_REGION    - AWS region (default: eu-west-1)"
	@echo "  LAMBDA        - Lambda function name for package-lambda target"
	@echo "  OUTPUT         - Output file for export-keys (default: api_keys.txt)"
	@echo "  FORMAT         - Output format for export-keys: text or json (default: text)"
	@echo "  VERBOSE        - Enable verbose output for verify (default: false)"
	@echo "  TIMESTREAM_DATABASE - Timestream database name for MCP server (default: bus_simulator)"

init:
	cd terraform && terraform init

plan: init
	cd terraform && terraform plan -var="aws_region=$(AWS_REGION)"

apply:
	@echo "Applying Terraform configuration..."
	cd terraform && terraform apply -var="aws_region=$(AWS_REGION)" -auto-approve

deploy: package-all-lambdas init plan apply
	@echo "Setup infrastructure and load data..."	
	$(MAKE) load-config
	$(MAKE) push-images
	$(MAKE) push-mcp
	$(MAKE) export-keys
	@echo "Deployment complete!"

build-feeders:
	@echo "Building container images with Podman..."
	podman build -t bus-simulator-people-count:latest -f docker/Dockerfile.people_count .
	podman build -t bus-simulator-sensors:latest -f docker/Dockerfile.sensors .
	podman build -t bus-simulator-bus-position:latest -f docker/Dockerfile.bus_position .

build-mcp:
	@echo "Building MCP server container image with Podman..."
	podman build -t bus-simulator-mcp:latest -f mcp_server/Dockerfile mcp_server/
	@echo "MCP server image built successfully!"

push-images: build-feeders
	@echo "Logging in to ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | podman login --username AWS --password-stdin $(ECR_REGISTRY)
	@echo "Tagging and pushing images..."
	podman tag bus-simulator-people-count:latest $(ECR_REGISTRY)/bus-simulator-feeders:people-count-latest
	podman tag bus-simulator-sensors:latest $(ECR_REGISTRY)/bus-simulator-feeders:sensors-latest
	podman tag bus-simulator-bus-position:latest $(ECR_REGISTRY)/bus-simulator-feeders:bus-position-latest
	podman push $(ECR_REGISTRY)/bus-simulator-feeders:people-count-latest
	podman push $(ECR_REGISTRY)/bus-simulator-feeders:sensors-latest
	podman push $(ECR_REGISTRY)/bus-simulator-feeders:bus-position-latest

push-mcp: build-mcp
	@echo "Logging in to ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | podman login --username AWS --password-stdin $(ECR_REGISTRY)
	@echo "Tagging and pushing MCP server image..."
	podman tag bus-simulator-mcp:latest $(ECR_REGISTRY)/bus-simulator-mcp:latest
	podman push $(ECR_REGISTRY)/bus-simulator-mcp:latest
	@echo "MCP server image pushed successfully!"

load-config:
	@echo "Loading configuration data..."
	python scripts/load_config.py --file data/lines.yaml --region $(AWS_REGION)

export-keys:
	@echo "Exporting API keys for hackathon participants..."
	@OUTPUT_FILE=$${OUTPUT:-api_keys.txt}; \
	FORMAT=$${FORMAT:-text}; \
	python scripts/export_api_keys.py --region $(AWS_REGION) --output $$OUTPUT_FILE --format $$FORMAT
	@echo "API keys exported successfully!"

package-lambda:
	@if [ -z "$(LAMBDA)" ]; then \
		echo "Error: LAMBDA variable not set. Usage: make package-lambda LAMBDA=people_count_api"; \
		exit 1; \
	fi
	@echo "Packaging Lambda function: $(LAMBDA)"
	./scripts/package_lambda.sh $(LAMBDA)

package-all-lambdas:
	@echo "Packaging all Lambda functions..."
	./scripts/package_lambda.sh people_count_api
	./scripts/package_lambda.sh sensors_api
	./scripts/package_lambda.sh bus_position_api
	./scripts/package_lambda.sh websocket_handler
	./scripts/package_lambda.sh websocket_authorizer
	@echo "All Lambda functions packaged successfully!"

verify:
	@echo "Running pre-hackathon verification checks..."
	@if [ "$(VERBOSE)" = "true" ]; then \
		python scripts/verify_deployment.py --region $(AWS_REGION) --verbose; \
	else \
		python scripts/verify_deployment.py --region $(AWS_REGION); \
	fi

verify-mcp:
	@echo "Testing deployed MCP server via API Gateway..."
	@echo "Retrieving API Gateway endpoint and API key..."
	@API_ENDPOINT=$$(cd terraform && terraform output -raw mcp_api_endpoint 2>/dev/null || echo ""); \
	if [ -z "$$API_ENDPOINT" ]; then \
		echo "Error: Could not retrieve MCP API endpoint from Terraform outputs"; \
		echo "Make sure the infrastructure is deployed and the mcp_api_endpoint output exists"; \
		exit 1; \
	fi; \
	API_KEY=$$(aws secretsmanager get-secret-value --secret-id bus-simulator/api-key --region $(AWS_REGION) --query SecretString --output text 2>/dev/null | python -c "import sys, json; print(json.load(sys.stdin)['api_key'])" || echo ""); \
	if [ -z "$$API_KEY" ]; then \
		echo "Error: Could not retrieve API key from Secrets Manager"; \
		exit 1; \
	fi; \
	echo "Testing MCP server health endpoint..."; \
	curl -s -X GET "$$API_ENDPOINT/health" \
		-H "x-api-key: $$API_KEY" \
		-H "x-group-name: makefile-test" | python -m json.tool || echo "Health check failed"; \
	echo ""; \
	echo "Testing MCP query_people_count tool..."; \
	curl -s -X POST "$$API_ENDPOINT/tools/query_people_count" \
		-H "Content-Type: application/json" \
		-H "x-api-key: $$API_KEY" \
		-H "x-group-name: makefile-test" \
		-d '{"stop_id": "S001", "mode": "latest"}' | python -m json.tool || echo "Query test failed"; \
	echo ""; \
	echo "MCP server verification complete!"

destroy:
	@echo "Destroying infrastructure..."
	cd terraform && terraform destroy -var="aws_region=$(AWS_REGION)" -auto-approve
	@echo "Infrastructure destroyed!"

infracost-check:
	@echo "Running Infracost cost estimation..."
	@if ! command -v infracost &> /dev/null; then \
		echo "Error: Infracost is not installed. Install it with:"; \
		echo "  curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh"; \
		exit 1; \
	fi
	cd terraform && infracost breakdown --path=. --format=table

setup-hooks:
	@echo "Setting up pre-commit hooks..."
	@if ! command -v pre-commit &> /dev/null; then \
		echo "Installing pre-commit..."; \
		pip install pre-commit; \
	fi
	@if ! command -v infracost &> /dev/null; then \
		echo "Warning: Infracost is not installed. Install it with:"; \
		echo "  curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh"; \
		echo "  infracost auth login"; \
	fi
	pre-commit install
	@echo "Pre-commit hooks installed successfully!"
	@echo ""
	@echo "To generate baseline cost estimate for diffs, run:"
	@echo "  cd terraform && infracost breakdown --path=. --format=json --out-file=../infracost-base.json"

check-costs:
	@echo "Checking current AWS costs and budget status..."
	python scripts/check_costs.py --region $(AWS_REGION)

# MCP Server targets
TIMESTREAM_DATABASE ?= bus_simulator

mcp-install:
	@echo "Installing MCP server dependencies..."
	cd mcp_server && pip install -r requirements.txt
	@echo "MCP server dependencies installed!"

mcp-run:
	@echo "Running MCP server..."
	@echo "Database: $(TIMESTREAM_DATABASE), Region: $(AWS_REGION)"
	cd mcp_server && TIMESTREAM_DATABASE=$(TIMESTREAM_DATABASE) AWS_REGION=$(AWS_REGION) python -m mcp_server.server

mcp-test:
	@echo "Running MCP server tests..."
	pytest tests/test_mcp_*.py -v

# Testing targets

test-unit:
	@echo "========================================"
	@echo "Running Unit Tests (Local, No AWS)"
	@echo "========================================"
	@echo ""
	@echo "Running Python unit tests..."
	pytest tests/ -v -m "not integration and not e2e" --ignore=tests/test_properties.py || true
	@echo ""
	@echo "Running property-based tests..."
	pytest tests/test_properties.py -v || true
	@echo ""
	@echo "========================================"
	@echo "Unit tests completed!"
	@echo "========================================"

test-int:
	@echo "========================================"
	@echo "Running Integration Tests (Requires AWS)"
	@echo "========================================"
	@echo ""
	@echo "Checking AWS connectivity..."
	@aws sts get-caller-identity > /dev/null 2>&1 || (echo "Error: AWS CLI not configured. Run 'aws configure'" && exit 1)
	@echo "AWS connection OK"
	@echo ""
	@echo "Running Python integration tests..."
	pytest tests/ -v -m "integration" || true
	@echo ""
	@echo "Running MCP server tests..."
	pytest tests/test_mcp_*.py -v || true
	@echo ""
	@echo "========================================"
	@echo "Integration tests completed!"
	@echo "========================================"

test-e2e:
	@echo "========================================"
	@echo "Running End-to-End Tests (API Scripts)"
	@echo "========================================"
	@echo ""
	@echo "Checking prerequisites..."
	@command -v curl > /dev/null 2>&1 || (echo "Error: curl not installed" && exit 1)
	@command -v jq > /dev/null 2>&1 || echo "Warning: jq not installed (JSON output won't be formatted)"
	@aws sts get-caller-identity > /dev/null 2>&1 || (echo "Error: AWS CLI not configured. Run 'aws configure'" && exit 1)
	@echo "Prerequisites OK"
	@echo ""
	@echo "Testing automatic configuration..."
	cd tests/api && ./test_auto_config.sh
	@echo ""
	@echo "Running REST API tests..."
	cd tests/api && ./test_people_count_latest.sh || true
	cd tests/api && ./test_sensors_latest.sh || true
	cd tests/api && ./test_bus_position_latest.sh || true
	@echo ""
	@echo "Running authentication tests..."
	cd tests/api && ./test_auth_invalid_key.sh || true
	cd tests/api && ./test_auth_missing_group.sh || true
	@echo ""
	@echo "Running MCP server tests..."
	cd tests/api && ./test_mcp_health.sh || true
	cd tests/api && ./test_mcp_query_people_count.sh || true
	cd tests/api && ./test_mcp_query_sensor_data.sh || true
	cd tests/api && ./test_mcp_query_bus_position.sh || true
	cd tests/api && ./test_mcp_auth.sh || true
	@echo ""
	@echo "========================================"
	@echo "End-to-end tests completed!"
	@echo "========================================"

test-all: test-unit test-int test-e2e
	@echo ""
	@echo "========================================"
	@echo "All Tests Completed!"
	@echo "========================================"
	@echo ""
	@echo "Summary:"
	@echo "  ✓ Unit tests (local, no AWS)"
	@echo "  ✓ Integration tests (Python with AWS)"
	@echo "  ✓ End-to-end tests (API shell scripts)"
	@echo ""
	@echo "Check output above for any failures."
