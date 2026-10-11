output "site_url" {
  description = "Live map"
  value       = "https://${aws_cloudfront_distribution.site.domain_name}/"
}

output "ecr_repository_url" {
  value = aws_ecr_repository.simulator.repository_url
}

output "ecs_cluster" {
  value = aws_ecs_cluster.main.name
}

output "ecs_service" {
  value = aws_ecs_service.simulator.name
}

output "tracker_name" {
  value = aws_location_tracker.buses.tracker_name
}

output "site_bucket" {
  value = aws_s3_bucket.site.id
}

output "cloudfront_distribution_id" {
  value = aws_cloudfront_distribution.site.id
}

output "geofence_log_group" {
  value = one(aws_cloudwatch_log_group.geofence_events[*].name)
}
