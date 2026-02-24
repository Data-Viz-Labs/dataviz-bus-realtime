# Cost Management and Monitoring

This document describes the cost management and monitoring features implemented for the Madrid Bus Real-Time Simulator.

## Overview

The system includes comprehensive cost management features to monitor and control infrastructure spending:

1. **AWS Budgets** - Monthly cost monitoring with automated alerts
2. **SNS Notifications** - Email alerts when budget thresholds are exceeded
3. **Infracost Integration** - Cost estimation for infrastructure changes
4. **Pre-commit Hooks** - Automated cost checks before committing Terraform changes
5. **Cost Monitoring Scripts** - Tools to check current AWS costs and budget status

## AWS Budget Configuration

### Budget Details

- **Budget Name**: `bus-simulator-monthly-budget`
- **Budget Type**: COST (monthly)
- **Default Limit**: $200 USD (configurable via Terraform variable)
- **Cost Filtering**: Filtered by Project tag (`Madrid-Bus-Simulator`)

### Alert Thresholds

The budget is configured with three notification thresholds:

1. **80% Warning** (ACTUAL)
   - Triggers when actual spending reaches 80% of budget
   - Provides early warning to take action

2. **100% Critical** (ACTUAL)
   - Triggers when actual spending reaches 100% of budget
   - Indicates budget limit has been reached

3. **120% Forecasted** (FORECASTED)
   - Triggers when forecasted spending exceeds 120% of budget
   - Proactive alert based on spending trends

### SNS Topic

- **Topic Name**: `bus-simulator-budget-alerts`
- **Protocol**: Email
- **Subscribers**: Configured via `budget_alert_emails` Terraform variable

## Configuration

### Terraform Variables

Add the following to your `terraform.tfvars` file:

```hcl
# Monthly budget limit in USD
monthly_budget_limit = 200

# Email addresses to receive budget alerts
budget_alert_emails = [
  "admin@example.com",
  "team@example.com"
]
```

### Infracost Configuration

Infracost is configured via `.infracost/infracost.yml`:

```yaml
version: 0.1

projects:
  - path: terraform
    name: bus-simulator
    terraform_workspace: default
    usage_file: .infracost/infracost-usage.yml
```

Usage estimates are defined in `.infracost/infracost-usage.yml` with expected monthly usage for:
- API Gateway requests
- Lambda invocations
- Timestream storage and queries
- Fargate task hours

## Usage

### Check Current Costs

Use the cost monitoring script to check current AWS costs and budget status:

```bash
# Check costs with default settings
make check-costs

# Check costs with custom region
make check-costs AWS_REGION=us-east-1

# Get JSON output
python scripts/check_costs.py --region eu-west-1 --format json
```

The script displays:
- Current month's costs
- Budget limit and actual spend percentage
- Forecasted spend
- Alert threshold status

### Run Infracost Cost Estimation

Generate cost estimates for Terraform changes:

```bash
# Run Infracost breakdown
make infracost-check

# Or run directly
cd terraform
infracost breakdown --path=. --format=table
```

### Set Up Pre-commit Hooks

Install pre-commit hooks to automatically check costs before committing:

```bash
# Install hooks
make setup-hooks

# Or manually
pip install pre-commit
pre-commit install

# Generate baseline for cost diffs
cd terraform
infracost breakdown --path=. --format=json --out-file=../infracost-base.json
```

Once installed, pre-commit hooks will automatically:
1. Format Terraform files with `terraform fmt`
2. Validate Terraform configuration
3. Show cost estimates for changes
4. Show cost diff from baseline

## Pre-commit Hooks

The `.pre-commit-config.yaml` file configures the following hooks:

### Terraform Hooks

- **terraform_fmt**: Automatically formats Terraform files
- **terraform_validate**: Validates Terraform configuration
- **terraform_docs**: Updates documentation
- **terraform_tflint**: Lints Terraform files

### Infracost Hooks

- **infracost**: Shows cost estimate for current configuration
- **infracost-diff**: Shows cost difference from baseline

### General Hooks

- **trailing-whitespace**: Removes trailing whitespace
- **end-of-file-fixer**: Ensures files end with newline
- **check-yaml**: Validates YAML syntax
- **check-json**: Validates JSON syntax
- **check-added-large-files**: Prevents committing large files

## Testing

Property-based and integration tests verify cost management functionality:

### Property 35: Budget Alarm Configuration

Verifies that AWS Budget is properly configured with:
- Correct budget name and type
- Monthly time unit
- Positive budget limit
- Project tag filtering
- Three notification thresholds (80%, 100%, 120%)

### Property 36: Budget Threshold Notification

Verifies that budget notifications are properly configured:
- SNS topic exists
- Email subscriptions are configured
- Budget notifications use the SNS topic

### Property 37: Infracost Integration

Verifies that Infracost is properly configured:
- Configuration file exists
- Infracost can generate cost estimates
- Cost data includes project breakdown

### Property 38: Pre-commit Hook Execution

Verifies that pre-commit hooks are properly configured:
- Configuration file exists
- Terraform hooks are configured
- Infracost hooks are configured

### Property 39: Terraform Formatting Enforcement

Verifies that Terraform formatting is enforced:
- terraform_fmt hook is configured
- Terraform files are properly formatted

### Running Tests

```bash
# Run all cost management tests
pytest tests/test_cost_management.py -v

# Run specific property test
pytest tests/test_cost_management.py::test_property_35_budget_alarm_configuration -v
```

## Cost Estimation

### Expected Monthly Costs

Based on the Infracost usage file, expected monthly costs are approximately:

- **API Gateway**: $10-20 (1M requests)
- **Lambda Functions**: $5-10 (900K invocations)
- **Timestream**: $50-100 (storage + queries)
- **Fargate**: $30-50 (3 tasks running 24/7)
- **EventBridge**: $5-10 (events)
- **Amazon Location**: $5 (route calculations)
- **AWS Budgets**: $0.50 (budget monitoring)
- **SNS**: $0.10 (notifications)

**Total Estimated Cost**: $106-196 for 7-day operation

### Cost Optimization Tips

1. **Adjust Fargate Task Sizes**: Use smaller CPU/memory if possible
2. **Implement Timestream Lifecycle Policies**: Archive old data to reduce storage costs
3. **Use Lambda Reserved Concurrency**: For predictable costs
4. **Enable API Gateway Caching**: Reduce Lambda invocations
5. **Monitor Actual Usage**: Adjust Infracost usage estimates based on real data

## Troubleshooting

### Budget Alerts Not Received

1. Check SNS topic subscriptions are confirmed
2. Verify email addresses in `budget_alert_emails` variable
3. Check CloudWatch Logs for budget service errors
4. Ensure costs are tagged with `Project=Madrid-Bus-Simulator`

### Infracost Not Working

1. Install Infracost: `curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh`
2. Authenticate: `infracost auth login`
3. Verify configuration: `infracost breakdown --path=terraform --format=table`

### Pre-commit Hooks Not Running

1. Install pre-commit: `pip install pre-commit`
2. Install hooks: `pre-commit install`
3. Test hooks: `pre-commit run --all-files`

## References

- [AWS Budgets Documentation](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)
- [Infracost Documentation](https://www.infracost.io/docs/)
- [Pre-commit Documentation](https://pre-commit.com/)
- [Terraform fmt Documentation](https://www.terraform.io/cli/commands/fmt)
