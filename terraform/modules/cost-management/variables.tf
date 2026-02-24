# Variables for Cost Management Module

variable "monthly_budget_limit" {
  description = "Monthly budget limit in USD"
  type        = number
}

variable "budget_alert_emails" {
  description = "Email addresses to receive budget alerts"
  type        = list(string)
}

variable "tags" {
  description = "Common tags to apply to all resources"
  type        = map(string)
  default     = {}
}
