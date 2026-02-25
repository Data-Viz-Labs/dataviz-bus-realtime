# Deployment Manual

This document provides comprehensive deployment procedures for the Madrid Bus Real-Time Simulator.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Initial Deployment](#initial-deployment)
3. [Configuration](#configuration)
4. [Component Deployment](#component-deployment)
5. [Post-Deployment](#post-deployment)
6. [Updates and Maintenance](#updates-and-maintenance)
7. [Rollback Procedures](#rollback-procedures)
8. [Multi-Region Deployment](#multi-region-deployment)

---

## Prerequisites

### Required Tools

1. **Terraform** >= 1.0
   ```bash
   # Install via package manager
   brew install terraform  # macOS
   sudo apt-get install terraform  # Ubuntu
   
   # Verify installation
   terraform version
   ```

2. **Podman** >= 4.0 (for container builds)
   ```bash
   # Install via package manager
   brew install podman  # macOS
   sudo apt-get install podman  # Ubuntu
   
   # Verify installation
   podman version
   ```

3. **Python** >= 3.11
   ```bash
   # Verify installation
   python --version
   
   # Install dependencies
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```

4. **AWS CLI** >= 2.0
   ```bash
   # Install
   curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"
   unzip awscliv2.zip
   sudo ./aws/install
   
   # Verify installation
   aws --version
   ```

5. **jq** (for JSON processing)
   ```bash
   brew install jq  # macOS
   sudo apt-get install jq  # Ubuntu
   ```

6. **Make** (build automation)
   ```bash
   # Usually pre-installed on Linux/macOS
   make --version
   ```

### AWS Account Setup

1. **AWS Account**: Active AWS account with appropriate permissions

2. **IAM Permissions**: User/role needs permissions for:
   - EC2 (VPC, Security Groups, NAT Gateway)
   - ECS (Cluster, Services, Tasks)
   - ECR (Repositories)
   - Lambda (Functions, Layers)
   - API Gateway (REST and WebSocket APIs)
   - Timestream (Databases, Tables)
   - DynamoDB (Tables)
   - S3 (Buckets)
   - Secrets Manager (Secrets)
   - EventBridge (Rules, Targets)
   - CloudWatch (Logs, Metrics, Alarms)
   - IAM (Roles, Policies)
   - Amazon Location Service

3. **AWS CLI Configuration**:
   ```bash
   aws configure
   # Enter:
   # - AWS Access Key ID
   # - AWS Secret Access Key
   # - Default region (e.g., eu-west-1)
   # - Default output format (json)
   
   # Verify configuration
   aws sts get-caller-identity
   ```

4. **Service Quotas**: Verify sufficient quotas for:
   - ECS tasks
   - Lambda concurrent executions
   - API Gateway requests
   - Timestream ingestion rate

### Repository Setup

1. **Clone Repository**:
   ```bash
   git clone <repository-url>
   cd dataviz-bus-realtime
   ```

2. **Verify Structure**:
   ```bash
   ls -la
   # Should see: data/, docker/, docs/, src/, terraform/, tests/, Makefile
   ```

---

## Initial Deployment

### Step 1: Configure Terraform Variables

Create `terraform/terraform.tfvars`:

```hcl
# AWS Configuration
aws_region = "eu-west-1"

# Project Configuration
project_name = "bus-simulator"
environment  = "prod"

# Budget Configuration (optional)
monthly_budget_limit = 200
budget_alert_emails  = [
  "admin@example.com",
  "team@example.com"
]

# Network Configuration (optional)
vpc_cidr = "10.0.0.0/16"

# Feeder Configuration (optional)
people_count_feeder_cpu    = "512"
people_count_feeder_memory = "1024"
sensors_feeder_cpu         = "512"
sensors_feeder_memory      = "1024"
bus_position_feeder_cpu    = "512"
bus_position_feeder_memory = "1024"

# MCP Server Configuration (optional)
mcp_server_cpu    = "512"
mcp_server_memory = "1024"

# Lambda Configuration (optional)
lambda_timeout     = 30
lambda_memory_size = 256
```

### Step 2: Initialize Terraform

```bash
make init
```

**Or manually:**
```bash
cd terraform
terraform init
```

**Expected output:**
```
Initializing modules...
Initializing the backend...
Initializing provider plugins...
Terraform has been successfully initialized!
```

### Step 3: Review Deployment Plan

```bash
make plan
```

**Or manually:**
```bash
cd terraform
terraform plan
```

**Review the plan carefully:**
- Check resource counts
- Verify configurations
- Estimate costs
- Identify potential issues

### Step 4: Build Container Images

```bash
make build-feeders
```

**This builds three container images:**
- `bus-simulator-people-count-feeder`
- `bus-simulator-sensors-feeder`
- `bus-simulator-bus-position-feeder`
- `bus-simulator-mcp-server`

**Verify images:**
```bash
podman images | grep bus-simulator
```

### Step 5: Package Lambda Functions

```bash
make package-all-lambdas
```

**This creates ZIP files in `build/`:**
- `people_count_api.zip`
- `sensors_api.zip`
- `bus_position_api.zip`
- `websocket_handler.zip`
- `rest_authorizer.zip`
- `websocket_authorizer_v2.zip`

**Verify packages:**
```bash
ls -lh build/*.zip
```

### Step 6: Deploy Infrastructure

```bash
make deploy AWS_REGION=eu-west-1
```

**This performs:**
1. Builds container images
2. Creates ECR repositories
3. Pushes images to ECR
4. Packages Lambda functions
5. Applies Terraform configuration
6. Loads bus lines configuration to S3

**Deployment time:** ~15-20 minutes

**Monitor deployment:**
```bash
# In another terminal
watch -n 5 'aws ecs describe-services \
  --cluster bus-simulator-cluster \
  --services people-count-feeder sensors-feeder bus-position-feeder mcp-server \
  --query "services[*].[serviceName,status,runningCount]" \
  --output table'
```

### Step 7: Verify Deployment

```bash
# Get API endpoints
cd terraform
terraform output

# Expected outputs:
# - http_api_endpoint
# - websocket_api_endpoint
# - mcp_api_endpoint
# - timestream_database_name
# - s3_config_bucket
```

**Test APIs:**
```bash
# Get API key
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString --output text | jq -r '.api_key')

# Test REST API
curl -H "x-api-key: $API_KEY" \
     -H "x-group-name: test" \
     "$(terraform output -raw http_api_endpoint)/people-count/S001?mode=latest"

# Test MCP Server
curl -X POST "$(terraform output -raw mcp_api_endpoint)/mcp/list-tools" \
  -H "x-api-key: $API_KEY" \
  -H "x-group-name: test" \
  -H "Content-Type: application/json"
```

---

## Configuration

### Bus Lines Configuration

The system uses `data/lines.yaml` to configure bus lines, stops, and buses.

**Configuration structure:**
```yaml
lines:
  - line_id: "L1"
    name: "Plaza de Castilla - Atocha"
    stops:
      - stop_id: "S001"
        name: "Plaza de Castilla"
        latitude: 40.4657
        longitude: -3.6886
        is_terminal: true
        base_arrival_rate: 2.5
      - stop_id: "S002"
        name: "Paseo de la Castellana"
        latitude: 40.4500
        longitude: -3.6900
        is_terminal: false
        base_arrival_rate: 1.8
    buses:
      - bus_id: "B001"
        capacity: 80
        initial_position: 0.0
      - bus_id: "B002"
        capacity: 80
        initial_position: 0.33
```

**Configuration parameters:**

- `line_id`: Unique line identifier (e.g., "L1", "L2")
- `name`: Human-readable line name
- `stop_id`: Unique stop identifier (e.g., "S001", "S002")
- `name`: Stop name
- `latitude`, `longitude`: GPS coordinates
- `is_terminal`: Whether stop is a terminal (direction changes here)
- `base_arrival_rate`: Average people arriving per minute
- `bus_id`: Unique bus identifier (e.g., "B001", "B002")
- `capacity`: Maximum passenger capacity
- `initial_position`: Starting position on route (0.0 to 1.0)

**Load configuration:**
```bash
make load-config AWS_REGION=eu-west-1
```

**Or manually:**
```bash
aws s3 cp data/lines.yaml s3://bus-simulator-config-$(aws sts get-caller-identity --query Account --output text)/lines.yaml
```

**Verify configuration:**
```bash
aws s3 ls s3://bus-simulator-config-$(aws sts get-caller-identity --query Account --output text)/
```

**After updating configuration, restart feeders:**
```bash
aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service people-count-feeder \
  --force-new-deployment \
  --region eu-west-1

aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service sensors-feeder \
  --force-new-deployment \
  --region eu-west-1

aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service bus-position-feeder \
  --force-new-deployment \
  --region eu-west-1
```

### Environment-Specific Configuration

For different environments (dev, staging, prod), use Terraform workspaces:

```bash
# Create workspace
cd terraform
terraform workspace new staging

# Switch workspace
terraform workspace select staging

# Deploy to workspace
terraform apply -var-file=staging.tfvars

# List workspaces
terraform workspace list
```

---

## Component Deployment

### Lambda Functions

**Package specific Lambda:**
```bash
make package-lambda LAMBDA=people_count_api
```

**Deploy Lambda via Terraform:**
```bash
cd terraform
terraform apply -target=module.api_gateway.aws_lambda_function.people_count_api
```

**Update Lambda code directly:**
```bash
aws lambda update-function-code \
  --function-name bus-simulator-people-count \
  --zip-file fileb://build/people_count_api.zip \
  --region eu-west-1
```

**Verify Lambda deployment:**
```bash
aws lambda get-function \
  --function-name bus-simulator-people-count \
  --region eu-west-1
```

### Fargate Services

**Build and push new image:**
```bash
# Build image
podman build -t bus-simulator-people-count-feeder -f docker/Dockerfile.people_count_feeder .

# Tag for ECR
podman tag bus-simulator-people-count-feeder \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-1.amazonaws.com/bus-simulator-people-count-feeder:latest

# Login to ECR
aws ecr get-login-password --region eu-west-1 | \
  podman login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-1.amazonaws.com

# Push image
podman push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-1.amazonaws.com/bus-simulator-people-count-feeder:latest
```

**Update ECS service:**
```bash
aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service people-count-feeder \
  --force-new-deployment \
  --region eu-west-1
```

**Monitor deployment:**
```bash
aws ecs describe-services \
  --cluster bus-simulator-cluster \
  --services people-count-feeder \
  --region eu-west-1
```

### MCP Server

**Build and deploy MCP server:**
```bash
# Build image
podman build -t bus-simulator-mcp-server -f mcp_server/Dockerfile .

# Tag for ECR
podman tag bus-simulator-mcp-server \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-1.amazonaws.com/bus-simulator-mcp-server:latest

# Push image
podman push $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-1.amazonaws.com/bus-simulator-mcp-server:latest

# Update service
aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service mcp-server \
  --force-new-deployment \
  --region eu-west-1
```

### API Gateway

**Deploy API Gateway changes:**
```bash
cd terraform
terraform apply -target=module.api_gateway
```

**Create new deployment:**
```bash
aws apigatewayv2 create-deployment \
  --api-id $(terraform output -raw http_api_id) \
  --region eu-west-1
```

### Timestream

**Timestream is managed by Terraform. To modify:**

1. Edit `terraform/modules/timestream/main.tf`
2. Apply changes:
   ```bash
   cd terraform
   terraform apply -target=module.timestream
   ```

**Modify retention policies:**
```hcl
resource "aws_timestreamwrite_table" "people_count" {
  retention_properties {
    memory_store_retention_period_in_hours  = 24
    magnetic_store_retention_period_in_days = 30
  }
}
```

---

## Post-Deployment

### Verification

**Run comprehensive verification:**
```bash
make verify AWS_REGION=eu-west-1
```

**Or manually:**
```bash
python scripts/verify_deployment.py --region eu-west-1 --verbose
```

**Verification checks:**
1. Timestream has data (at least 5 days for hackathon)
2. All Fargate services running
3. REST API endpoints responding
4. API key authentication enforced
5. WebSocket connections working
6. MCP server responding

### Export API Keys

**Export keys for distribution:**
```bash
python scripts/export_api_keys.py --region eu-west-1 --output api_keys.txt
```

**Output includes:**
- API key value
- REST API endpoint
- WebSocket API endpoint
- MCP API endpoint
- Usage examples

### Monitoring Setup

**Create CloudWatch dashboard:**
```bash
# Via Terraform (recommended)
cd terraform
terraform apply -target=module.monitoring

# Or manually via AWS Console
# Navigate to CloudWatch > Dashboards > Create dashboard
```

**Set up alarms:**
```bash
# Example: Lambda error alarm
aws cloudwatch put-metric-alarm \
  --alarm-name bus-simulator-lambda-errors \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --evaluation-periods 1 \
  --threshold 10 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=bus-simulator-people-count \
  --region eu-west-1
```

### Documentation

**Generate API documentation:**
```bash
# OpenAPI spec is in docs/openapi.yaml
# Interactive docs in docs/api.html

# Open in browser
open docs/api.html
```

**Update README with endpoints:**
```bash
cd terraform
echo "REST API: $(terraform output -raw http_api_endpoint)" >> ../DEPLOYMENT_INFO.md
echo "WebSocket API: $(terraform output -raw websocket_api_endpoint)" >> ../DEPLOYMENT_INFO.md
echo "MCP API: $(terraform output -raw mcp_api_endpoint)" >> ../DEPLOYMENT_INFO.md
```

---

## Updates and Maintenance

### Updating Lambda Functions

1. **Modify code** in `src/lambdas/`
2. **Package Lambda:**
   ```bash
   make package-lambda LAMBDA=people_count_api
   ```
3. **Deploy:**
   ```bash
   cd terraform
   terraform apply -target=module.api_gateway.aws_lambda_function.people_count_api
   ```
4. **Verify:**
   ```bash
   curl -H "x-api-key: $API_KEY" \
        -H "x-group-name: test" \
        "$API_URL/people-count/S001?mode=latest"
   ```

### Updating Feeder Services

1. **Modify code** in `src/feeders/`
2. **Build image:**
   ```bash
   make build-feeders
   ```
3. **Push to ECR:**
   ```bash
   make push-images AWS_REGION=eu-west-1
   ```
4. **Update service:**
   ```bash
   aws ecs update-service \
     --cluster bus-simulator-cluster \
     --service people-count-feeder \
     --force-new-deployment \
     --region eu-west-1
   ```
5. **Monitor deployment:**
   ```bash
   aws ecs describe-services \
     --cluster bus-simulator-cluster \
     --services people-count-feeder \
     --region eu-west-1
   ```

### Updating Infrastructure

1. **Modify Terraform** in `terraform/`
2. **Plan changes:**
   ```bash
   cd terraform
   terraform plan
   ```
3. **Review plan carefully**
4. **Apply changes:**
   ```bash
   terraform apply
   ```
5. **Verify deployment:**
   ```bash
   make verify AWS_REGION=eu-west-1
   ```

### Scaling

**Scale ECS services:**
```bash
# Via Terraform
# Edit terraform/modules/ecs/main.tf
resource "aws_ecs_service" "people_count_feeder" {
  desired_count = 2  # Increase from 1
}

# Apply
cd terraform
terraform apply

# Or via AWS CLI
aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service people-count-feeder \
  --desired-count 2 \
  --region eu-west-1
```

**Scale Lambda concurrency:**
```bash
aws lambda put-function-concurrency \
  --function-name bus-simulator-people-count \
  --reserved-concurrent-executions 10 \
  --region eu-west-1
```

---

## Rollback Procedures

### Terraform Rollback

**Rollback to previous state:**
```bash
cd terraform

# List state versions (if using remote backend)
terraform state list

# Rollback to specific version
terraform state pull > backup.tfstate
terraform state push previous.tfstate

# Or use version control
git log --oneline
git checkout <previous-commit>
terraform apply
```

### Lambda Rollback

**Rollback to previous version:**
```bash
# List versions
aws lambda list-versions-by-function \
  --function-name bus-simulator-people-count \
  --region eu-west-1

# Update alias to previous version
aws lambda update-alias \
  --function-name bus-simulator-people-count \
  --name prod \
  --function-version <previous-version> \
  --region eu-west-1
```

### ECS Rollback

**Rollback to previous task definition:**
```bash
# List task definitions
aws ecs list-task-definitions \
  --family-prefix bus-simulator-people-count-feeder \
  --region eu-west-1

# Update service to previous task definition
aws ecs update-service \
  --cluster bus-simulator-cluster \
  --service people-count-feeder \
  --task-definition bus-simulator-people-count-feeder:<previous-revision> \
  --region eu-west-1
```

### Complete Rollback

**Rollback entire deployment:**
```bash
# Checkout previous version
git checkout <previous-tag>

# Rebuild and redeploy
make deploy AWS_REGION=eu-west-1

# Verify
make verify AWS_REGION=eu-west-1
```

---

## Multi-Region Deployment

### Prerequisites

- Terraform workspaces or separate state files
- Region-specific configuration files
- Cross-region replication for S3 (optional)

### Deploy to Multiple Regions

**Method 1: Terraform Workspaces**

```bash
cd terraform

# Create workspace for each region
terraform workspace new eu-west-1
terraform workspace new eu-central-1

# Deploy to eu-west-1
terraform workspace select eu-west-1
terraform apply -var="aws_region=eu-west-1"

# Deploy to eu-central-1
terraform workspace select eu-central-1
terraform apply -var="aws_region=eu-central-1"
```

**Method 2: Separate Directories**

```bash
# Create region-specific directories
mkdir -p terraform/regions/eu-west-1
mkdir -p terraform/regions/eu-central-1

# Copy configuration
cp terraform/*.tf terraform/regions/eu-west-1/
cp terraform/*.tf terraform/regions/eu-central-1/

# Deploy to each region
cd terraform/regions/eu-west-1
terraform init
terraform apply -var="aws_region=eu-west-1"

cd ../eu-central-1
terraform init
terraform apply -var="aws_region=eu-central-1"
```

### Cross-Region Considerations

- **Data Replication**: Timestream doesn't support cross-region replication
- **API Endpoints**: Each region has separate API endpoints
- **Configuration**: Use S3 cross-region replication for `lines.yaml`
- **Monitoring**: Set up CloudWatch dashboards per region
- **Costs**: Double costs for dual-region deployment

---

## Cleanup

### Destroy Infrastructure

**Complete cleanup:**
```bash
make destroy AWS_REGION=eu-west-1
```

**Or manually:**
```bash
cd terraform
terraform destroy
```

**Verify cleanup:**
```bash
# Check ECS cluster
aws ecs describe-clusters \
  --clusters bus-simulator-cluster \
  --region eu-west-1

# Check Timestream database
aws timestream-write describe-database \
  --database-name bus_simulator \
  --region eu-west-1

# Check S3 buckets
aws s3 ls | grep bus-simulator
```

**Manual cleanup if needed:**
```bash
# Delete S3 buckets
aws s3 rb s3://bus-simulator-config-<account-id> --force

# Delete ECR repositories
aws ecr delete-repository \
  --repository-name bus-simulator-people-count-feeder \
  --force \
  --region eu-west-1

# Delete CloudWatch log groups
aws logs delete-log-group \
  --log-group-name /ecs/people-count-feeder \
  --region eu-west-1
```

---

## Troubleshooting Deployment

### Terraform Errors

**State lock errors:**
```bash
# Force unlock (use with caution)
cd terraform
terraform force-unlock <lock-id>
```

**Resource already exists:**
```bash
# Import existing resource
terraform import aws_s3_bucket.config bus-simulator-config-<account-id>
```

**Provider errors:**
```bash
# Reinitialize providers
terraform init -upgrade
```

### Container Build Errors

**Podman errors:**
```bash
# Check Podman status
podman info

# Clean up old images
podman system prune -a

# Rebuild with no cache
podman build --no-cache -t bus-simulator-people-count-feeder -f docker/Dockerfile.people_count_feeder .
```

**ECR push errors:**
```bash
# Re-authenticate
aws ecr get-login-password --region eu-west-1 | \
  podman login --username AWS --password-stdin \
  $(aws sts get-caller-identity --query Account --output text).dkr.ecr.eu-west-1.amazonaws.com

# Verify repository exists
aws ecr describe-repositories --region eu-west-1
```

### Lambda Package Errors

**Missing dependencies:**
```bash
# Reinstall dependencies
pip install -r src/lambdas/requirements.txt -t build/lambda_build/

# Verify package contents
unzip -l build/people_count_api.zip
```

**Package too large:**
```bash
# Check package size
ls -lh build/people_count_api.zip

# Use Lambda layers for large dependencies
# Or optimize dependencies
```

---

## Additional Resources

- [Operations Manual](./ops_manual.md)
- [API Documentation](./UI.md)
- [Main README](../README.md)
- [Terraform Documentation](https://www.terraform.io/docs)
- [AWS ECS Documentation](https://docs.aws.amazon.com/ecs/)
- [AWS Lambda Documentation](https://docs.aws.amazon.com/lambda/)

## Support

For deployment issues:
- Check CloudWatch logs
- Review Terraform plan output
- Consult troubleshooting section
- Open GitHub issue with deployment logs
