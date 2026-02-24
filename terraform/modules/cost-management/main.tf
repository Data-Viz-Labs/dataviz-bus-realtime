# Cost Management Module - AWS Budgets and SNS notifications
# Implements Requirements 12.1, 12.2

# SNS Topic for budget alerts
resource "aws_sns_topic" "budget_alerts" {
  name = "bus-simulator-budget-alerts"

  tags = merge(
    var.tags,
    {
      Name = "bus-simulator-budget-alerts"
    }
  )
}

# SNS Topic subscriptions for email notifications
resource "aws_sns_topic_subscription" "budget_email" {
  count     = length(var.budget_alert_emails)
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = var.budget_alert_emails[count.index]
}

# AWS Budget for monthly cost monitoring
resource "aws_budgets_budget" "monthly_cost" {
  name              = "bus-simulator-monthly-budget"
  budget_type       = "COST"
  limit_amount      = var.monthly_budget_limit
  limit_unit        = "USD"
  time_unit         = "MONTHLY"
  time_period_start = formatdate("YYYY-MM-01_00:00", timestamp())

  cost_filter {
    name = "TagKeyValue"
    values = [
      "user:Project$Madrid-Bus-Simulator"
    ]
  }

  # Alert at 80% of budget (warning)
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 80
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # Alert at 100% of budget (critical)
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 100
    threshold_type            = "PERCENTAGE"
    notification_type         = "ACTUAL"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  # Alert at 120% forecasted (proactive)
  notification {
    comparison_operator       = "GREATER_THAN"
    threshold                 = 120
    threshold_type            = "PERCENTAGE"
    notification_type         = "FORECASTED"
    subscriber_sns_topic_arns = [aws_sns_topic.budget_alerts.arn]
  }

  tags = merge(
    var.tags,
    {
      Name = "bus-simulator-monthly-budget"
    }
  )
}
