terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.33"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = var.tags
  }
}

data "aws_caller_identity" "current" {}

locals {
  name       = var.name
  repo_root  = "${path.module}/.."
  account_id = data.aws_caller_identity.current.account_id
}

module "cost_management" {
  source = "./modules/cost-management"

  monthly_budget_limit = var.monthly_budget_limit
  budget_alert_emails  = var.budget_alert_emails
  tags                 = var.tags
}
