#!/usr/bin/env python3
"""
Cost monitoring script for Madrid Bus Real-Time Simulator.
Queries AWS Cost Explorer to get current month's costs and budget status.

Requirements: 12.1, 12.2
"""

import argparse
import boto3
from datetime import datetime, timedelta
from typing import Dict, Any
import json


def get_current_month_costs(region: str, project_tag: str = "Madrid-Bus-Simulator") -> Dict[str, Any]:
    """
    Query AWS Cost Explorer for current month's costs filtered by project tag.
    
    Args:
        region: AWS region
        project_tag: Project tag value to filter costs
        
    Returns:
        Dictionary with cost information
    """
    ce_client = boto3.client('ce', region_name=region)
    
    # Get first day of current month
    today = datetime.now()
    start_date = today.replace(day=1).strftime('%Y-%m-%d')
    end_date = today.strftime('%Y-%m-%d')
    
    try:
        response = ce_client.get_cost_and_usage(
            TimePeriod={
                'Start': start_date,
                'End': end_date
            },
            Granularity='MONTHLY',
            Metrics=['UnblendedCost'],
            Filter={
                'Tags': {
                    'Key': 'Project',
                    'Values': [project_tag]
                }
            }
        )
        
        if response['ResultsByTime']:
            amount = float(response['ResultsByTime'][0]['Total']['UnblendedCost']['Amount'])
            unit = response['ResultsByTime'][0]['Total']['UnblendedCost']['Unit']
            
            return {
                'success': True,
                'amount': amount,
                'unit': unit,
                'start_date': start_date,
                'end_date': end_date
            }
        else:
            return {
                'success': False,
                'error': 'No cost data available for the current month'
            }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def get_budget_status(region: str, budget_name: str = "bus-simulator-monthly-budget") -> Dict[str, Any]:
    """
    Get current budget status and alert thresholds.
    
    Args:
        region: AWS region
        budget_name: Name of the AWS Budget
        
    Returns:
        Dictionary with budget status information
    """
    budgets_client = boto3.client('budgets', region_name=region)
    
    try:
        # Get account ID
        sts_client = boto3.client('sts', region_name=region)
        account_id = sts_client.get_caller_identity()['Account']
        
        # Get budget details
        response = budgets_client.describe_budget(
            AccountId=account_id,
            BudgetName=budget_name
        )
        
        budget = response['Budget']
        limit_amount = float(budget['BudgetLimit']['Amount'])
        limit_unit = budget['BudgetLimit']['Unit']
        
        # Get calculated spend (if available)
        calculated_spend = budget.get('CalculatedSpend', {})
        actual_spend = float(calculated_spend.get('ActualSpend', {}).get('Amount', 0))
        forecasted_spend = float(calculated_spend.get('ForecastedSpend', {}).get('Amount', 0))
        
        # Calculate percentages
        actual_percentage = (actual_spend / limit_amount * 100) if limit_amount > 0 else 0
        forecasted_percentage = (forecasted_spend / limit_amount * 100) if limit_amount > 0 else 0
        
        return {
            'success': True,
            'budget_name': budget_name,
            'limit_amount': limit_amount,
            'limit_unit': limit_unit,
            'actual_spend': actual_spend,
            'forecasted_spend': forecasted_spend,
            'actual_percentage': actual_percentage,
            'forecasted_percentage': forecasted_percentage,
            'thresholds': {
                'warning': 80,
                'critical': 100,
                'forecasted': 120
            }
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }


def format_cost_report(costs: Dict[str, Any], budget: Dict[str, Any], format_type: str = 'text') -> str:
    """
    Format cost and budget information for display.
    
    Args:
        costs: Cost information from get_current_month_costs
        budget: Budget information from get_budget_status
        format_type: Output format ('text' or 'json')
        
    Returns:
        Formatted report string
    """
    if format_type == 'json':
        return json.dumps({
            'costs': costs,
            'budget': budget
        }, indent=2)
    
    # Text format
    lines = []
    lines.append("=" * 60)
    lines.append("Madrid Bus Simulator - Cost Report")
    lines.append("=" * 60)
    lines.append("")
    
    # Current costs
    if costs['success']:
        lines.append(f"Current Month Costs ({costs['start_date']} to {costs['end_date']}):")
        lines.append(f"  Amount: ${costs['amount']:.2f} {costs['unit']}")
    else:
        lines.append(f"Current Month Costs: ERROR - {costs['error']}")
    
    lines.append("")
    
    # Budget status
    if budget['success']:
        lines.append(f"Budget Status ({budget['budget_name']}):")
        lines.append(f"  Budget Limit: ${budget['limit_amount']:.2f} {budget['limit_unit']}")
        lines.append(f"  Actual Spend: ${budget['actual_spend']:.2f} ({budget['actual_percentage']:.1f}%)")
        lines.append(f"  Forecasted Spend: ${budget['forecasted_spend']:.2f} ({budget['forecasted_percentage']:.1f}%)")
        lines.append("")
        lines.append("  Alert Thresholds:")
        lines.append(f"    Warning (80%): ${budget['limit_amount'] * 0.8:.2f}")
        lines.append(f"    Critical (100%): ${budget['limit_amount']:.2f}")
        lines.append(f"    Forecasted (120%): ${budget['limit_amount'] * 1.2:.2f}")
        lines.append("")
        
        # Status indicators
        if budget['actual_percentage'] >= 100:
            lines.append("  ⚠️  CRITICAL: Budget limit exceeded!")
        elif budget['actual_percentage'] >= 80:
            lines.append("  ⚠️  WARNING: Approaching budget limit")
        elif budget['forecasted_percentage'] >= 120:
            lines.append("  ⚠️  WARNING: Forecasted to exceed budget by 20%")
        else:
            lines.append("  ✓ Budget status: OK")
    else:
        lines.append(f"Budget Status: ERROR - {budget['error']}")
    
    lines.append("")
    lines.append("=" * 60)
    
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Check current AWS costs and budget status for Madrid Bus Simulator'
    )
    parser.add_argument(
        '--region',
        default='eu-west-1',
        help='AWS region (default: eu-west-1)'
    )
    parser.add_argument(
        '--budget-name',
        default='bus-simulator-monthly-budget',
        help='Name of the AWS Budget (default: bus-simulator-monthly-budget)'
    )
    parser.add_argument(
        '--project-tag',
        default='Madrid-Bus-Simulator',
        help='Project tag value for cost filtering (default: Madrid-Bus-Simulator)'
    )
    parser.add_argument(
        '--format',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    args = parser.parse_args()
    
    # Get current costs
    costs = get_current_month_costs(args.region, args.project_tag)
    
    # Get budget status
    budget = get_budget_status(args.region, args.budget_name)
    
    # Format and print report
    report = format_cost_report(costs, budget, args.format)
    print(report)
    
    # Exit with error code if budget is exceeded
    if budget['success'] and budget['actual_percentage'] >= 100:
        return 1
    
    return 0


if __name__ == '__main__':
    exit(main())
