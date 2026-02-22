# Outputs for EventBridge module

output "event_bus_name" {
  description = "Name of the EventBridge event bus"
  value       = aws_cloudwatch_event_bus.bus_simulator.name
}

output "event_bus_arn" {
  description = "ARN of the EventBridge event bus"
  value       = aws_cloudwatch_event_bus.bus_simulator.arn
}

output "event_rule_arn" {
  description = "ARN of the bus position updates event rule"
  value       = aws_cloudwatch_event_rule.bus_position_updates.arn
}
