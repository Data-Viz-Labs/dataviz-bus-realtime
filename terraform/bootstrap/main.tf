# One-time bootstrap, run by an account admin with local state:
#   terraform -chdir=terraform/bootstrap init && terraform -chdir=terraform/bootstrap apply
# Creates the remote state bucket, the GitHub OIDC trust and the two CI roles, and writes
# terraform/backend.hcl for the main stack. Keep terraform.tfstate of this folder safe (or
# re-import) — it is not stored remotely.

terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.33"
    }
    local = {
      source  = "hashicorp/local"
      version = "~> 2.5"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project   = "madrid-bus-simulator"
      ManagedBy = "terraform-bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

# ---------------------------------------------------------------- state bucket

resource "aws_s3_bucket" "state" {
  bucket_prefix = "${var.name}-tfstate-"
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket                  = aws_s3_bucket.state.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

locals {
  state_key = "madrid-bus/terraform.tfstate"
}

resource "local_file" "backend" {
  filename        = "${path.module}/../backend.hcl"
  file_permission = "0644"
  content         = <<-EOT
    bucket       = "${aws_s3_bucket.state.id}"
    key          = "${local.state_key}"
    region       = "${var.aws_region}"
    use_lockfile = true
    encrypt      = true
  EOT
}

# ---------------------------------------------------------------- GitHub OIDC

resource "aws_iam_openid_connect_provider" "github" {
  count          = var.github_oidc_provider_arn == "" ? 1 : 0
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  # AWS validates GitHub's certificate against its own trusted CAs; the thumbprint is ignored
  # but the API still requires a value.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

locals {
  oidc_provider_arn = var.github_oidc_provider_arn != "" ? var.github_oidc_provider_arn : aws_iam_openid_connect_provider.github[0].arn
}

data "aws_iam_policy_document" "gh_trust" {
  for_each = {
    plan   = ["repo:${var.github_repo}:pull_request", "repo:${var.github_repo}:ref:refs/heads/main"]
    deploy = ["repo:${var.github_repo}:environment:production"]
  }

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = each.value
    }
  }
}

# Plan role: pull requests and main. Read-only on the account, plus the state bucket (the S3
# backend writes a .tflock object even for plan).
resource "aws_iam_role" "gh_plan" {
  name                 = "${var.name}-gh-plan"
  assume_role_policy   = data.aws_iam_policy_document.gh_trust["plan"].json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "gh_plan_readonly" {
  role       = aws_iam_role.gh_plan.name
  policy_arn = "arn:aws:iam::aws:policy/ReadOnlyAccess"
}

data "aws_iam_policy_document" "state_access" {
  statement {
    sid       = "ListStateBucket"
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.state.arn]
  }
  statement {
    sid       = "ReadWriteStateAndLock"
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/${local.state_key}", "${aws_s3_bucket.state.arn}/${local.state_key}.tflock"]
  }
}

resource "aws_iam_role_policy" "gh_plan_state" {
  name   = "terraform-state"
  role   = aws_iam_role.gh_plan.id
  policy = data.aws_iam_policy_document.state_access.json
}

# Deploy role: only jobs running in the protected "production" environment (required reviewers
# / branch rule set on GitHub). AdministratorAccess because `terraform apply` creates IAM roles,
# CloudFront, Location, IoT, Glue/Athena, Budgets... and the account is dedicated to the event.
# To narrow it: run an apply with CloudTrail on, collect the actions used (or IAM Access
# Analyzer policy generation on this role) and replace this attachment with that policy, plus a
# permissions boundary on the roles Terraform creates.
resource "aws_iam_role" "gh_deploy" {
  name                 = "${var.name}-gh-deploy"
  assume_role_policy   = data.aws_iam_policy_document.gh_trust["deploy"].json
  max_session_duration = 3600
}

resource "aws_iam_role_policy_attachment" "gh_deploy_admin" {
  role       = aws_iam_role.gh_deploy.name
  policy_arn = "arn:aws:iam::aws:policy/AdministratorAccess"
}
