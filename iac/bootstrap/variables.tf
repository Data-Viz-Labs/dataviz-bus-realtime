variable "aws_region" {
  description = "Region of the state bucket (same as the main stack)"
  type        = string
  default     = "eu-west-1"
}

variable "name" {
  description = "Prefix for resource names (same as the main stack)"
  type        = string
  default     = "madrid-bus"
}

variable "github_repo" {
  description = "GitHub repository (owner/name) allowed to assume the CI roles"
  type        = string
  default     = "Data-Viz-Labs/dataviz-bus-realtime"
}

variable "github_oidc_provider_arn" {
  description = "Existing token.actions.githubusercontent.com OIDC provider ARN; empty creates one (only one may exist per account)"
  type        = string
  default     = ""
}
