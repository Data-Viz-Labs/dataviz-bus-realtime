output "state_bucket" {
  description = "TF_STATE_BUCKET repository variable"
  value       = aws_s3_bucket.state.id
}

output "plan_role_arn" {
  description = "AWS_PLAN_ROLE_ARN repository variable"
  value       = aws_iam_role.gh_plan.arn
}

output "deploy_role_arn" {
  description = "AWS_DEPLOY_ROLE_ARN repository variable"
  value       = aws_iam_role.gh_deploy.arn
}

output "aws_region" {
  value = var.aws_region
}

output "account_id" {
  value = data.aws_caller_identity.current.account_id
}
