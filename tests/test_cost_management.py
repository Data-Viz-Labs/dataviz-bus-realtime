"""
Property-based and integration tests for cost management functionality.

Tests cover:
- Property 35: Budget alarm configuration (Requirements 12.1)
- Property 36: Budget threshold notification (Requirements 12.2)
- Property 37: Infracost integration (Requirements 12.3)
- Property 38: Pre-commit hook execution (Requirements 13.1, 13.5)
- Property 39: Terraform formatting enforcement (Requirements 13.2, 12.5)
"""

import pytest
import boto3
import subprocess
import os
import json
from pathlib import Path
from hypothesis import given, settings, strategies as st
from typing import Dict, Any


# Test fixtures
@pytest.fixture
def aws_region():
    """Get AWS region from environment or use default."""
    return os.getenv('AWS_REGION', 'eu-west-1')


@pytest.fixture
def budget_name():
    """Get budget name."""
    return "bus-simulator-monthly-budget"


@pytest.fixture
def sns_topic_name():
    """Get SNS topic name."""
    return "bus-simulator-budget-alerts"


@pytest.fixture
def terraform_dir():
    """Get Terraform directory path."""
    return Path(__file__).parent.parent / "terraform"


@pytest.fixture
def infracost_config():
    """Get Infracost configuration path."""
    return Path(__file__).parent.parent / ".infracost" / "infracost.yml"


@pytest.fixture
def precommit_config():
    """Get pre-commit configuration path."""
    return Path(__file__).parent.parent / ".pre-commit-config.yaml"


# Property 35: Budget alarm configuration
# **Validates: Requirements 12.1**
def test_property_35_budget_alarm_configuration(aws_region, budget_name):
    """
    Feature: madrid-bus-realtime-simulator, Property 35: Budget alarm configuration
    
    When the system is deployed via Terraform, AWS Budget alarms should be created 
    and configured to monitor monthly costs against defined thresholds.
    
    This test verifies that:
    1. AWS Budget exists with the correct name
    2. Budget is configured for monthly cost monitoring
    3. Budget has correct notification thresholds (80%, 100%, 120%)
    4. Budget is filtered by Project tag
    """
    budgets_client = boto3.client('budgets', region_name=aws_region)
    sts_client = boto3.client('sts', region_name=aws_region)
    
    try:
        account_id = sts_client.get_caller_identity()['Account']
        
        # Get budget details
        response = budgets_client.describe_budget(
            AccountId=account_id,
            BudgetName=budget_name
        )
        
        budget = response['Budget']
        
        # Verify budget exists and has correct configuration
        assert budget['BudgetName'] == budget_name, "Budget name mismatch"
        assert budget['BudgetType'] == 'COST', "Budget should be COST type"
        assert budget['TimeUnit'] == 'MONTHLY', "Budget should be MONTHLY"
        assert 'BudgetLimit' in budget, "Budget should have a limit"
        assert float(budget['BudgetLimit']['Amount']) > 0, "Budget limit should be positive"
        
        # Verify cost filters (Project tag)
        cost_filters = budget.get('CostFilters', {})
        assert 'TagKeyValue' in cost_filters, "Budget should filter by tag"
        tag_values = cost_filters['TagKeyValue']
        assert any('Madrid-Bus-Simulator' in tag for tag in tag_values), \
            "Budget should filter by Project=Madrid-Bus-Simulator tag"
        
        # Get notifications
        notifications_response = budgets_client.describe_notifications_for_budget(
            AccountId=account_id,
            BudgetName=budget_name
        )
        
        notifications = notifications_response['Notifications']
        
        # Verify we have 3 notifications (80%, 100%, 120%)
        assert len(notifications) >= 3, "Budget should have at least 3 notification thresholds"
        
        # Check for specific thresholds
        thresholds = {notif['Threshold'] for notif in notifications}
        assert 80 in thresholds, "Budget should have 80% threshold"
        assert 100 in thresholds, "Budget should have 100% threshold"
        assert 120 in thresholds, "Budget should have 120% threshold"
        
        # Verify notification types
        notification_types = {notif['NotificationType'] for notif in notifications}
        assert 'ACTUAL' in notification_types, "Budget should have ACTUAL notifications"
        assert 'FORECASTED' in notification_types, "Budget should have FORECASTED notifications"
        
        print(f"✓ Budget alarm configuration verified: {budget_name}")
        print(f"  - Budget limit: ${budget['BudgetLimit']['Amount']} {budget['BudgetLimit']['Unit']}")
        print(f"  - Thresholds: {sorted(thresholds)}")
        print(f"  - Notification types: {notification_types}")
        
    except budgets_client.exceptions.NotFoundException:
        pytest.skip(f"Budget {budget_name} not found - infrastructure may not be deployed")
    except Exception as e:
        pytest.fail(f"Error verifying budget configuration: {e}")


# Property 36: Budget threshold notification
# **Validates: Requirements 12.2**
def test_property_36_budget_threshold_notification(aws_region, budget_name, sns_topic_name):
    """
    Feature: madrid-bus-realtime-simulator, Property 36: Budget threshold notification
    
    For any billing period where monthly costs exceed the configured budget threshold, 
    the system should send email notifications to all designated recipients within 24 hours 
    of threshold breach.
    
    This test verifies that:
    1. SNS topic exists for budget alerts
    2. SNS topic is configured as subscriber for budget notifications
    3. Email subscriptions are configured on the SNS topic
    
    Note: Actual notification delivery testing requires simulating cost increases,
    which is not practical in automated tests. This test verifies the configuration.
    """
    sns_client = boto3.client('sns', region_name=aws_region)
    budgets_client = boto3.client('budgets', region_name=aws_region)
    sts_client = boto3.client('sts', region_name=aws_region)
    
    try:
        # Find SNS topic by name
        topics_response = sns_client.list_topics()
        topic_arn = None
        for topic in topics_response['Topics']:
            if sns_topic_name in topic['TopicArn']:
                topic_arn = topic['TopicArn']
                break
        
        assert topic_arn is not None, f"SNS topic {sns_topic_name} not found"
        
        # Get SNS subscriptions
        subscriptions_response = sns_client.list_subscriptions_by_topic(
            TopicArn=topic_arn
        )
        
        subscriptions = subscriptions_response['Subscriptions']
        
        # Verify at least one email subscription exists
        email_subscriptions = [sub for sub in subscriptions if sub['Protocol'] == 'email']
        assert len(email_subscriptions) > 0, \
            "SNS topic should have at least one email subscription"
        
        # Verify budget notifications use this SNS topic
        account_id = sts_client.get_caller_identity()['Account']
        
        notifications_response = budgets_client.describe_notifications_for_budget(
            AccountId=account_id,
            BudgetName=budget_name
        )
        
        # Check that SNS topic is configured as subscriber
        subscribers_found = False
        for notification in notifications_response['Notifications']:
            subscribers_response = budgets_client.describe_subscribers_for_notification(
                AccountId=account_id,
                BudgetName=budget_name,
                Notification=notification
            )
            
            for subscriber in subscribers_response['Subscribers']:
                if subscriber['SubscriptionType'] == 'SNS' and topic_arn in subscriber['Address']:
                    subscribers_found = True
                    break
        
        assert subscribers_found, "Budget notifications should use the SNS topic"
        
        print(f"✓ Budget notification configuration verified")
        print(f"  - SNS topic: {topic_arn}")
        print(f"  - Email subscriptions: {len(email_subscriptions)}")
        print(f"  - Budget notifications configured: Yes")
        
    except sns_client.exceptions.NotFoundException:
        pytest.skip(f"SNS topic {sns_topic_name} not found - infrastructure may not be deployed")
    except budgets_client.exceptions.NotFoundException:
        pytest.skip(f"Budget {budget_name} not found - infrastructure may not be deployed")
    except Exception as e:
        pytest.fail(f"Error verifying budget notification configuration: {e}")


# Property 37: Infracost integration
# **Validates: Requirements 12.3**
def test_property_37_infracost_integration(terraform_dir, infracost_config):
    """
    Feature: madrid-bus-realtime-simulator, Property 37: Infracost integration
    
    When Terraform configuration files are modified, running Infracost should produce 
    a cost estimate report showing the projected monthly cost difference.
    
    This test verifies that:
    1. Infracost configuration file exists
    2. Infracost configuration is valid
    3. Infracost can generate cost estimates for the Terraform configuration
    """
    # Check Infracost configuration exists
    assert infracost_config.exists(), \
        f"Infracost configuration file not found: {infracost_config}"
    
    # Verify Infracost is installed
    try:
        result = subprocess.run(
            ['infracost', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        assert result.returncode == 0, "Infracost is not installed or not working"
    except FileNotFoundError:
        pytest.skip("Infracost is not installed - install with: curl -fsSL https://raw.githubusercontent.com/infracost/infracost/master/scripts/install.sh | sh")
    except subprocess.TimeoutExpired:
        pytest.fail("Infracost command timed out")
    
    # Run Infracost breakdown to verify it works
    try:
        result = subprocess.run(
            ['infracost', 'breakdown', '--path', str(terraform_dir), '--format', 'json'],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=terraform_dir.parent
        )
        
        # Infracost may return non-zero if not authenticated, but should still produce output
        if result.returncode != 0 and 'Please run' in result.stderr:
            pytest.skip("Infracost not authenticated - run: infracost auth login")
        
        # Parse JSON output
        if result.stdout:
            try:
                cost_data = json.loads(result.stdout)
                assert 'projects' in cost_data, "Infracost output should contain projects"
                assert len(cost_data['projects']) > 0, "Infracost should analyze at least one project"
                
                # Verify cost estimate is present
                project = cost_data['projects'][0]
                assert 'breakdown' in project or 'diff' in project, \
                    "Infracost output should contain cost breakdown or diff"
                
                print(f"✓ Infracost integration verified")
                print(f"  - Configuration file: {infracost_config}")
                print(f"  - Projects analyzed: {len(cost_data['projects'])}")
                if 'totalMonthlyCost' in cost_data:
                    print(f"  - Total monthly cost: ${cost_data['totalMonthlyCost']}")
                
            except json.JSONDecodeError:
                pytest.fail(f"Infracost output is not valid JSON: {result.stdout[:200]}")
        else:
            pytest.fail(f"Infracost produced no output. stderr: {result.stderr}")
            
    except subprocess.TimeoutExpired:
        pytest.fail("Infracost command timed out after 60 seconds")
    except Exception as e:
        pytest.fail(f"Error running Infracost: {e}")


# Property 38: Pre-commit hook execution
# **Validates: Requirements 13.1, 13.5**
def test_property_38_precommit_hook_execution(precommit_config):
    """
    Feature: madrid-bus-realtime-simulator, Property 38: Pre-commit hook execution
    
    For any git commit containing Terraform file changes, the pre-commit hooks 
    should execute automatically before the commit is finalized.
    
    This test verifies that:
    1. Pre-commit configuration file exists
    2. Pre-commit configuration is valid
    3. Pre-commit hooks are configured for Terraform files
    4. Infracost hooks are configured
    """
    # Check pre-commit configuration exists
    assert precommit_config.exists(), \
        f"Pre-commit configuration file not found: {precommit_config}"
    
    # Read and parse pre-commit configuration
    import yaml
    with open(precommit_config, 'r') as f:
        config = yaml.safe_load(f)
    
    assert 'repos' in config, "Pre-commit config should have repos"
    assert len(config['repos']) > 0, "Pre-commit config should have at least one repo"
    
    # Find Terraform hooks
    terraform_hooks = []
    infracost_hooks = []
    
    for repo in config['repos']:
        if 'hooks' in repo:
            for hook in repo['hooks']:
                hook_id = hook.get('id', '')
                if 'terraform' in hook_id:
                    terraform_hooks.append(hook_id)
                if 'infracost' in hook_id:
                    infracost_hooks.append(hook_id)
    
    # Verify Terraform hooks are configured
    assert len(terraform_hooks) > 0, "Pre-commit should have Terraform hooks configured"
    assert 'terraform_fmt' in terraform_hooks, "Pre-commit should have terraform_fmt hook"
    
    # Verify Infracost hooks are configured
    assert len(infracost_hooks) > 0, "Pre-commit should have Infracost hooks configured"
    
    print(f"✓ Pre-commit hook configuration verified")
    print(f"  - Configuration file: {precommit_config}")
    print(f"  - Terraform hooks: {terraform_hooks}")
    print(f"  - Infracost hooks: {infracost_hooks}")
    
    # Verify pre-commit is installed (optional - may not be in CI)
    try:
        result = subprocess.run(
            ['pre-commit', '--version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            print(f"  - Pre-commit installed: Yes ({result.stdout.strip()})")
        else:
            print(f"  - Pre-commit installed: No (install with: pip install pre-commit)")
    except FileNotFoundError:
        print(f"  - Pre-commit installed: No (install with: pip install pre-commit)")


# Property 39: Terraform formatting enforcement
# **Validates: Requirements 13.2, 12.5**
def test_property_39_terraform_formatting_enforcement(terraform_dir, precommit_config):
    """
    Feature: madrid-bus-realtime-simulator, Property 39: Terraform formatting enforcement
    
    For any Terraform file in the repository, running terraform fmt via pre-commit hook 
    should ensure consistent formatting according to Terraform style conventions.
    
    This test verifies that:
    1. terraform_fmt hook is configured in pre-commit
    2. Terraform files in the repository are properly formatted
    3. terraform fmt can be run successfully
    """
    # Verify terraform_fmt is in pre-commit config
    import yaml
    with open(precommit_config, 'r') as f:
        config = yaml.safe_load(f)
    
    terraform_fmt_found = False
    for repo in config['repos']:
        if 'hooks' in repo:
            for hook in repo['hooks']:
                if hook.get('id') == 'terraform_fmt':
                    terraform_fmt_found = True
                    break
    
    assert terraform_fmt_found, "terraform_fmt hook should be configured in pre-commit"
    
    # Check if Terraform is installed
    try:
        result = subprocess.run(
            ['terraform', 'version'],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode != 0:
            pytest.skip("Terraform is not installed")
    except FileNotFoundError:
        pytest.skip("Terraform is not installed")
    
    # Run terraform fmt -check to verify formatting
    try:
        result = subprocess.run(
            ['terraform', 'fmt', '-check', '-recursive'],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=terraform_dir
        )
        
        # terraform fmt -check returns 0 if files are formatted, 3 if changes needed
        if result.returncode == 3:
            print(f"⚠️  Terraform files need formatting:")
            print(result.stdout)
            pytest.fail("Terraform files are not properly formatted. Run: terraform fmt -recursive")
        elif result.returncode != 0:
            pytest.fail(f"terraform fmt failed with error: {result.stderr}")
        
        print(f"✓ Terraform formatting verified")
        print(f"  - All Terraform files are properly formatted")
        
    except subprocess.TimeoutExpired:
        pytest.fail("terraform fmt command timed out")
    except Exception as e:
        pytest.fail(f"Error running terraform fmt: {e}")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
