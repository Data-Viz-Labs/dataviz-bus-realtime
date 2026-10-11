variable "name" {
  description = "Prefix for resource names"
  type        = string
}

variable "daily_budget_limit" {
  description = "Daily cost budget in USD"
  type        = number
}

variable "monthly_budget_limit" {
  description = "Monthly cost budget in USD"
  type        = number
}

variable "budget_alert_emails" {
  description = "Emails that receive budget alerts (SNS subscription + direct budget notification); may be empty"
  type        = list(string)
  default     = []
}
