# Outputs for Amazon Location module

output "route_calculator_name" {
  description = "Name of the route calculator"
  value       = aws_location_route_calculator.bus_routes.calculator_name
}

output "route_calculator_arn" {
  description = "ARN of the route calculator"
  value       = aws_location_route_calculator.bus_routes.calculator_arn
}

output "map_name" {
  description = "Name of the map"
  value       = aws_location_map.madrid_centro.map_name
}

output "map_arn" {
  description = "ARN of the map"
  value       = aws_location_map.madrid_centro.map_arn
}
