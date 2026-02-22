# Lambda Function Deployment Guide

This document describes how to package and deploy Lambda functions for the Madrid Bus Real-Time Simulator.

## Overview

The Lambda functions provide REST API endpoints for querying bus system data. Each Lambda function is packaged as a ZIP file containing:

- Lambda handler code (e.g., `people_count_api.py`)
- Common modules (`timestream_client.py`, `models.py`)
- Python dependencies (boto3, botocore, etc.)

## Dependencies

All Lambda functions share the same dependencies, defined in `src/lambdas/requirements.txt`:

```
boto3>=1.34.0
botocore>=1.34.0
pyyaml>=6.0
```

### Dependency Details

- **boto3**: AWS SDK for Python - used to interact with Timestream, EventBridge, and other AWS services
- **botocore**: Core functionality for boto3 - provides low-level AWS service access
- **pyyaml**: YAML parser - used for configuration file loading (if needed)

## Packaging Methods

### Method 1: Using the Makefile (Recommended)

Package a specific Lambda function:
```bash
make package-lambda LAMBDA=people_count_api
```

Package all Lambda functions:
```bash
make package-all-lambdas
```

The ZIP files will be created in the `build/` directory.

### Method 2: Using the Shell Script Directly

```bash
./scripts/package_lambda.sh people_count_api
```

Optional: Specify a custom output directory:
```bash
./scripts/package_lambda.sh people_count_api /path/to/output
```

### Method 3: Manual Packaging

If you need to package manually:

```bash
# Create build directory
mkdir -p build/lambda_build
cd build/lambda_build

# Install dependencies
pip install -r ../../src/lambdas/requirements.txt -t .

# Copy Lambda handler
cp ../../src/lambdas/people_count_api.py .

# Copy common modules
mkdir -p common
cp ../../src/common/__init__.py common/
cp ../../src/common/timestream_client.py common/
cp ../../src/common/models.py common/

# Create ZIP
zip -r ../people_count_api.zip .

# Cleanup
cd ../..
rm -rf build/lambda_build
```

## Package Structure

The resulting ZIP file has the following structure:

```
people_count_api.zip
├── people_count_api.py          # Lambda handler (entry point)
├── common/
│   ├── __init__.py
│   ├── timestream_client.py     # Timestream client wrapper
│   └── models.py                # Data models
├── boto3/                       # AWS SDK
├── botocore/                    # AWS SDK core
└── [other dependencies]
```

## Lambda Handler Configuration

When deploying to AWS Lambda, use the following configuration:

- **Runtime**: Python 3.11
- **Handler**: `people_count_api.lambda_handler`
- **Architecture**: x86_64 or arm64
- **Memory**: 256 MB (recommended minimum)
- **Timeout**: 30 seconds (recommended)

### Environment Variables

The Lambda function requires the following environment variables:

- `TIMESTREAM_DATABASE`: Name of the Timestream database (default: `bus_simulator`)
- `TIMESTREAM_TABLE`: Name of the Timestream table (default: `people_count`)
- `AWS_REGION`: AWS region (default: `eu-west-1`)

### IAM Permissions

The Lambda execution role needs the following permissions:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "timestream:DescribeEndpoints",
        "timestream:Select"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "logs:CreateLogGroup",
        "logs:CreateLogStream",
        "logs:PutLogEvents"
      ],
      "Resource": "arn:aws:logs:*:*:*"
    }
  ]
}
```

## Deployment with Terraform

The Terraform configuration (in `terraform/` directory) will automatically:

1. Create the Lambda function resource
2. Upload the ZIP package
3. Configure environment variables
4. Set up IAM roles and permissions
5. Create API Gateway integration

To deploy:

```bash
# Package Lambda functions first
make package-all-lambdas

# Deploy infrastructure (includes Lambda deployment)
make deploy
```

## Testing the Packaged Lambda

### Local Testing

You can test the packaged Lambda locally using the AWS SAM CLI:

```bash
# Install AWS SAM CLI first
# https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html

# Test locally
sam local invoke -t template.yaml PeopleCountApi \
  -e test/events/people_count_latest.json
```

### Testing in AWS

After deployment, test via API Gateway:

```bash
# Get the API Gateway URL from Terraform outputs
API_URL=$(cd terraform && terraform output -raw api_gateway_url)

# Test latest query
curl "${API_URL}/people-count/S001?mode=latest"

# Test historical query
curl "${API_URL}/people-count/S001?timestamp=2024-01-15T10:30:00Z"
```

## Troubleshooting

### Package Size Too Large

If the package exceeds Lambda's 50 MB limit:

1. Remove unnecessary dependencies from `requirements.txt`
2. Use Lambda Layers for common dependencies
3. Consider using the AWS SDK for Python (boto3) that's included in the Lambda runtime

### Import Errors

If you see import errors like `ModuleNotFoundError`:

1. Verify the package structure matches the expected layout
2. Check that `common/` directory has `__init__.py`
3. Ensure all dependencies are installed in the package root

### Timestream Connection Errors

If Lambda can't connect to Timestream:

1. Verify the Lambda has the correct IAM permissions
2. Check that environment variables are set correctly
3. Ensure the Lambda is in the same region as Timestream
4. Verify VPC configuration if using private networking

## Future Lambda Functions

When adding new Lambda functions (Sensors API, Bus Position API):

1. Create the handler file in `src/lambdas/`
2. Update `package-all-lambdas` target in Makefile
3. Add Terraform resources for the new Lambda
4. Update this documentation

Example for Sensors API:

```bash
# Package the new Lambda
./scripts/package_lambda.sh sensors_api

# Or add to Makefile
make package-lambda LAMBDA=sensors_api
```

## References

- [AWS Lambda Python Documentation](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
- [AWS Lambda Deployment Packages](https://docs.aws.amazon.com/lambda/latest/dg/python-package.html)
- [Boto3 Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [AWS Timestream Query Documentation](https://docs.aws.amazon.com/timestream/latest/developerguide/API_query_Query.html)
