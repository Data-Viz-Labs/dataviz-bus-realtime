# Timestream module for Madrid Bus Real-Time Simulator
# Creates database and tables for time series data storage

# Timestream database
resource "aws_timestreamwrite_database" "bus_simulator" {
  database_name = var.database_name

  tags = var.tags
}

# Table 1: People count at bus stops
resource "aws_timestreamwrite_table" "people_count" {
  database_name = aws_timestreamwrite_database.bus_simulator.database_name
  table_name    = "people_count"

  retention_properties {
    memory_store_retention_period_in_hours  = 24
    magnetic_store_retention_period_in_days = 30
  }

  tags = var.tags
}

# Table 2: Sensor data from buses and stops
resource "aws_timestreamwrite_table" "sensor_data" {
  database_name = aws_timestreamwrite_database.bus_simulator.database_name
  table_name    = "sensor_data"

  retention_properties {
    memory_store_retention_period_in_hours  = 24
    magnetic_store_retention_period_in_days = 30
  }

  tags = var.tags
}

# Table 3: Bus position data
resource "aws_timestreamwrite_table" "bus_position" {
  database_name = aws_timestreamwrite_database.bus_simulator.database_name
  table_name    = "bus_position"

  retention_properties {
    memory_store_retention_period_in_hours  = 24
    magnetic_store_retention_period_in_days = 30
  }

  tags = var.tags
}
