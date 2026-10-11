# Budget alerts for the event. Both budgets are account-wide on purpose: the account is meant to be
# dedicated to the hackathon, and filtering by tag would need the Project tag activated as a
# cost-allocation tag first, which takes up to 24 h to apply and misses untagged spend (data
# transfer, CloudWatch, etc.). If the account is shared, add a cost_filter on that tag.
#
# time_period_start is left unset: AWS defaults it to the start of the current period. Using
# timestamp() here produced a diff on every plan.

data "aws_caller_identity" "current" {}

resource "aws_sns_topic" "budget_alerts" {
  name = "${var.name}-budget-alerts"
}

data "aws_iam_policy_document" "budget_alerts" {
  statement {
    sid       = "AllowBudgetsPublish"
    actions   = ["SNS:Publish"]
    resources = [aws_sns_topic.budget_alerts.arn]
    principals {
      type        = "Service"
      identifiers = ["budgets.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [data.aws_caller_identity.current.account_id]
    }
  }
}

resource "aws_sns_topic_policy" "budget_alerts" {
  arn    = aws_sns_topic.budget_alerts.arn
  policy = data.aws_iam_policy_document.budget_alerts.json
}

# Each address receives a confirmation email; SNS only delivers after it is confirmed.
resource "aws_sns_topic_subscription" "budget_email" {
  for_each  = toset(var.budget_alert_emails)
  topic_arn = aws_sns_topic.budget_alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

locals {
  # Budgets also email directly, so alerts arrive even before the SNS subscription is confirmed.
  # A notification block rejects an empty subscriber_email_addresses list, hence null.
  emails = length(var.budget_alert_emails) > 0 ? var.budget_alert_emails : null

  daily_thresholds = [
    { type = "ACTUAL", percent = 50 },
    { type = "ACTUAL", percent = 80 },
    { type = "ACTUAL", percent = 100 },
  ]
  monthly_thresholds = [
    { type = "ACTUAL", percent = 80 },
    { type = "ACTUAL", percent = 100 },
    { type = "FORECASTED", percent = 100 },
  ]
}

resource "aws_budgets_budget" "daily" {
  name         = "${var.name}-daily"
  budget_type  = "COST"
  limit_amount = tostring(var.daily_budget_limit)
  limit_unit   = "USD"
  time_unit    = "DAILY"

  dynamic "notification" {
    for_each = local.daily_thresholds
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.percent
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
      subscriber_email_addresses = local.emails
    }
  }

  depends_on = [aws_sns_topic_policy.budget_alerts]
}

resource "aws_budgets_budget" "monthly" {
  name         = "${var.name}-monthly"
  budget_type  = "COST"
  limit_amount = tostring(var.monthly_budget_limit)
  limit_unit   = "USD"
  time_unit    = "MONTHLY"

  dynamic "notification" {
    for_each = local.monthly_thresholds
    content {
      comparison_operator        = "GREATER_THAN"
      threshold                  = notification.value.percent
      threshold_type             = "PERCENTAGE"
      notification_type          = notification.value.type
      subscriber_sns_topic_arns  = [aws_sns_topic.budget_alerts.arn]
      subscriber_email_addresses = local.emails
    }
  }

  depends_on = [aws_sns_topic_policy.budget_alerts]
}
