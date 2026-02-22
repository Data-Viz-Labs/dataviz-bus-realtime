# Fargate module for Madrid Bus Real-Time Simulator
# Creates ECS cluster, ECR repository, task definitions, and services

# ECR repository for feeder images
resource "aws_ecr_repository" "feeders" {
  name                 = "bus-simulator-feeders"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = var.tags
}

# ECS cluster
resource "aws_ecs_cluster" "bus_simulator" {
  name = "bus-simulator-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = var.tags
}

# Task definition: People Count Feeder
resource "aws_ecs_task_definition" "people_count_feeder" {
  family                   = "people-count-feeder"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([{
    name  = "people-count-feeder"
    image = "${aws_ecr_repository.feeders.repository_url}:people-count-latest"

    environment = [
      {
        name  = "TIMESTREAM_DATABASE"
        value = var.timestream_database_name
      },
      {
        name  = "TIMESTREAM_TABLE"
        value = var.timestream_tables.people_count
      },
      {
        name  = "CONFIG_FILE"
        value = "/app/data/lines.yaml"
      },
      {
        name  = "TIME_INTERVAL"
        value = "60"
      },
      {
        name  = "AWS_REGION"
        value = data.aws_region.current.name
      },
      {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/people-count-feeder"
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = var.tags
}

# Task definition: Sensors Feeder
resource "aws_ecs_task_definition" "sensors_feeder" {
  family                   = "sensors-feeder"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([{
    name  = "sensors-feeder"
    image = "${aws_ecr_repository.feeders.repository_url}:sensors-latest"

    environment = [
      {
        name  = "TIMESTREAM_DATABASE"
        value = var.timestream_database_name
      },
      {
        name  = "TIMESTREAM_TABLE"
        value = var.timestream_tables.sensor_data
      },
      {
        name  = "CONFIG_FILE"
        value = "/app/data/lines.yaml"
      },
      {
        name  = "TIME_INTERVAL"
        value = "60"
      },
      {
        name  = "AWS_REGION"
        value = data.aws_region.current.name
      },
      {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/sensors-feeder"
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = var.tags
}

# Task definition: Bus Position Feeder
resource "aws_ecs_task_definition" "bus_position_feeder" {
  family                   = "bus-position-feeder"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = var.ecs_execution_role_arn
  task_role_arn            = var.ecs_task_role_arn

  container_definitions = jsonencode([{
    name  = "bus-position-feeder"
    image = "${aws_ecr_repository.feeders.repository_url}:bus-position-latest"

    environment = [
      {
        name  = "TIMESTREAM_DATABASE"
        value = var.timestream_database_name
      },
      {
        name  = "TIMESTREAM_TABLE"
        value = var.timestream_tables.bus_position
      },
      {
        name  = "EVENTBRIDGE_BUS_NAME"
        value = var.eventbridge_bus_name
      },
      {
        name  = "CONFIG_FILE"
        value = "/app/data/lines.yaml"
      },
      {
        name  = "TIME_INTERVAL"
        value = "60"
      },
      {
        name  = "AWS_REGION"
        value = data.aws_region.current.name
      },
      {
        name  = "LOG_LEVEL"
        value = "INFO"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/bus-position-feeder"
        "awslogs-region"        = data.aws_region.current.name
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = var.tags
}

# ECS Service: People Count Feeder
resource "aws_ecs_service" "people_count_feeder" {
  name            = "people-count-feeder"
  cluster         = aws_ecs_cluster.bus_simulator.id
  task_definition = aws_ecs_task_definition.people_count_feeder.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.fargate_security_group_id]
    assign_public_ip = false
  }

  tags = var.tags
}

# ECS Service: Sensors Feeder
resource "aws_ecs_service" "sensors_feeder" {
  name            = "sensors-feeder"
  cluster         = aws_ecs_cluster.bus_simulator.id
  task_definition = aws_ecs_task_definition.sensors_feeder.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.fargate_security_group_id]
    assign_public_ip = false
  }

  tags = var.tags
}

# ECS Service: Bus Position Feeder
resource "aws_ecs_service" "bus_position_feeder" {
  name            = "bus-position-feeder"
  cluster         = aws_ecs_cluster.bus_simulator.id
  task_definition = aws_ecs_task_definition.bus_position_feeder.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.fargate_security_group_id]
    assign_public_ip = false
  }

  tags = var.tags
}

# Data source for current region
data "aws_region" "current" {}
