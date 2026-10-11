variable "aws_region" {
  description = "Region for every resource (must offer Amazon Location Maps/Routes v2)"
  type        = string
  default     = "eu-west-1"
}

variable "name" {
  description = "Prefix for resource names"
  type        = string
  default     = "madrid-bus"
}

variable "image_tag" {
  description = "Simulator image tag in ECR"
  type        = string
  default     = "latest"
}

variable "lines" {
  description = "Comma-separated subset of line ids to simulate; empty simulates every line in data/lines.yaml"
  type        = string
  default     = ""
}

variable "tracked_lines" {
  description = "Lines whose buses are written to the Amazon Location tracker: comma-separated ids, \"all\" or \"\" (none). Tracker writes are billed per position; see README"
  type        = string
  default     = "27"
}

variable "stop_geofences" {
  description = "Create a geofence per stop of the tracked lines and write every stop call (ENTER/EXIT events in CloudWatch Logs). Geofence evaluations are billed per position"
  type        = bool
  default     = false
}

variable "heartbeat_seconds" {
  description = "Max seconds between two tracker writes of a bus"
  type        = number
  default     = 120
}

variable "task_cpu" {
  description = "Fargate CPU units for the simulator"
  type        = number
  default     = 512
}

variable "task_memory" {
  description = "Fargate memory (MiB) for the simulator"
  type        = number
  default     = 1024
}

variable "subnet_ids" {
  description = "Public subnets for the simulator task; empty uses the default VPC"
  type        = list(string)
  default     = []
}

variable "monthly_budget_limit" {
  description = "Monthly budget in USD for alerts"
  type        = number
  default     = 100
}

variable "budget_alert_emails" {
  description = "Emails that receive budget alerts"
  type        = list(string)
  default     = []
}

variable "tags" {
  description = "Tags applied to every resource"
  type        = map(string)
  default = {
    Project   = "madrid-bus-simulator"
    ManagedBy = "terraform"
  }
}
