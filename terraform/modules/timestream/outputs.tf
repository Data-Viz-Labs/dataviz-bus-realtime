# Outputs for Timestream module

output "database_name" {
  description = "Name of the Timestream database"
  value       = aws_timestreamwrite_database.bus_simulator.database_name
}

output "database_arn" {
  description = "ARN of the Timestream database"
  value       = aws_timestreamwrite_database.bus_simulator.arn
}

output "table_names" {
  description = "Map of table names"
  value = {
    people_count = aws_timestreamwrite_table.people_count.table_name
    sensor_data  = aws_timestreamwrite_table.sensor_data.table_name
    bus_position = aws_timestreamwrite_table.bus_position.table_name
  }
}

output "table_arns" {
  description = "List of table ARNs"
  value = [
    aws_timestreamwrite_table.people_count.arn,
    aws_timestreamwrite_table.sensor_data.arn,
    aws_timestreamwrite_table.bus_position.arn
  ]
}
