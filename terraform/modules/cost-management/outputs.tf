output "sns_topic_arn" {
  description = "SNS topic that receives every budget alert"
  value       = aws_sns_topic.budget_alerts.arn
}

output "daily_budget_name" {
  value = aws_budgets_budget.daily.name
}

output "monthly_budget_name" {
  value = aws_budgets_budget.monthly.name
}
