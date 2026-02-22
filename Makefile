.PHONY: init plan deploy destroy build-feeders push-images load-config package-lambda package-all-lambdas help

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
	@echo "  build-feeders      - Build Docker images for feeder services"
	@echo "  push-images        - Push Docker images to ECR"
	@echo "  load-config        - Load configuration data to S3"
	@echo "  deploy             - Full deployment (build, push, apply, config)"
	@echo "  destroy            - Destroy all infrastructure"
	@echo ""
	@echo "Environment variables:"
	@echo "  AWS_REGION    - AWS region (default: eu-west-1)"
	@echo "  LAMBDA        - Lambda function name for package-lambda target"

init:
	cd terraform && terraform init

plan: init
	cd terraform && terraform plan -var="aws_region=$(AWS_REGION)"

build-feeders:
	@echo "Building Docker images..."
	docker build -t bus-simulator-people-count:latest -f docker/Dockerfile.people_count .
	docker build -t bus-simulator-sensors:latest -f docker/Dockerfile.sensors .
	docker build -t bus-simulator-bus-position:latest -f docker/Dockerfile.bus_position .

push-images: build-feeders
	@echo "Logging in to ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)
	@echo "Tagging and pushing images..."
	docker tag bus-simulator-people-count:latest $(ECR_REGISTRY)/bus-simulator-feeders:people-count-latest
	docker tag bus-simulator-sensors:latest $(ECR_REGISTRY)/bus-simulator-feeders:sensors-latest
	docker tag bus-simulator-bus-position:latest $(ECR_REGISTRY)/bus-simulator-feeders:bus-position-latest
	docker push $(ECR_REGISTRY)/bus-simulator-feeders:people-count-latest
	docker push $(ECR_REGISTRY)/bus-simulator-feeders:sensors-latest
	docker push $(ECR_REGISTRY)/bus-simulator-feeders:bus-position-latest

load-config:
	@echo "Loading configuration data..."
	python scripts/load_config.py --file data/lines.yaml --region $(AWS_REGION)

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
	@echo "All Lambda functions packaged successfully!"

deploy: push-images init
	@echo "Deploying infrastructure..."
	cd terraform && terraform apply -var="aws_region=$(AWS_REGION)" -auto-approve
	$(MAKE) load-config
	@echo "Deployment complete!"

destroy:
	@echo "Destroying infrastructure..."
	cd terraform && terraform destroy -var="aws_region=$(AWS_REGION)" -auto-approve
	@echo "Infrastructure destroyed!"
