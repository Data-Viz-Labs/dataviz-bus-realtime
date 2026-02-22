# Outputs for Fargate module

output "cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.bus_simulator.name
}

output "cluster_arn" {
  description = "ARN of the ECS cluster"
  value       = aws_ecs_cluster.bus_simulator.arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository"
  value       = aws_ecr_repository.feeders.repository_url
}

output "ecr_repository_arn" {
  description = "ARN of the ECR repository"
  value       = aws_ecr_repository.feeders.arn
}

output "service_names" {
  description = "Names of the ECS services"
  value = {
    people_count = aws_ecs_service.people_count_feeder.name
    sensors      = aws_ecs_service.sensors_feeder.name
    bus_position = aws_ecs_service.bus_position_feeder.name
  }
}
