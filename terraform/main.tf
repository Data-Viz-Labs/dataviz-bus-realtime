terraform {
  required_version = ">= 1.10"

  # Partial configuration: `make init` passes backend.hcl (written by terraform/bootstrap).
  backend "s3" {}

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.33"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
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

  name                 = local.name
  daily_budget_limit   = var.daily_budget_limit
  monthly_budget_limit = var.monthly_budget_limit
  budget_alert_emails  = var.budget_alert_emails
}
