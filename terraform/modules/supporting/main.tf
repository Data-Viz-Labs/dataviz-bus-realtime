# Supporting resources module for Madrid Bus Real-Time Simulator
# Creates VPC, S3, DynamoDB, and CloudWatch resources

# VPC and networking (conditional creation)
resource "aws_vpc" "main" {
  count = var.create_vpc ? 1 : 0

  cidr_block           = var.vpc_cidr
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = "bus-simulator-vpc"
  })
}

resource "aws_subnet" "private" {
  count = var.create_vpc ? 2 : 0

  vpc_id            = aws_vpc.main[0].id
  cidr_block        = cidrsubnet(var.vpc_cidr, 8, count.index)
  availability_zone = data.aws_availability_zones.available.names[count.index]

  tags = merge(var.tags, {
    Name = "bus-simulator-private-${count.index + 1}"
  })
}

resource "aws_subnet" "public" {
  count = var.create_vpc ? 2 : 0

  vpc_id                  = aws_vpc.main[0].id
  cidr_block              = cidrsubnet(var.vpc_cidr, 8, count.index + 100)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "bus-simulator-public-${count.index + 1}"
  })
}

resource "aws_internet_gateway" "main" {
  count = var.create_vpc ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  tags = merge(var.tags, {
    Name = "bus-simulator-igw"
  })
}

resource "aws_eip" "nat" {
  count = var.create_vpc ? 1 : 0

  domain = "vpc"

  tags = merge(var.tags, {
    Name = "bus-simulator-nat-eip"
  })
}

resource "aws_nat_gateway" "main" {
  count = var.create_vpc ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id

  tags = merge(var.tags, {
    Name = "bus-simulator-nat"
  })

  depends_on = [aws_internet_gateway.main]
}

resource "aws_route_table" "public" {
  count = var.create_vpc ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main[0].id
  }

  tags = merge(var.tags, {
    Name = "bus-simulator-public-rt"
  })
}

resource "aws_route_table" "private" {
  count = var.create_vpc ? 1 : 0

  vpc_id = aws_vpc.main[0].id

  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.main[0].id
  }

  tags = merge(var.tags, {
    Name = "bus-simulator-private-rt"
  })
}

resource "aws_route_table_association" "public" {
  count = var.create_vpc ? 2 : 0

  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public[0].id
}

resource "aws_route_table_association" "private" {
  count = var.create_vpc ? 2 : 0

  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private[0].id
}

# Security group for Fargate services
resource "aws_security_group" "fargate" {
  count = var.create_vpc ? 1 : 0

  name        = "bus-simulator-fargate-sg"
  description = "Security group for Fargate feeder services"
  vpc_id      = aws_vpc.main[0].id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "bus-simulator-fargate-sg"
  })
}

# Data source for availability zones
data "aws_availability_zones" "available" {
  state = "available"
}

# S3 bucket for configuration storage
resource "aws_s3_bucket" "config" {
  bucket_prefix = "bus-simulator-config-"

  tags = var.tags
}

resource "aws_s3_bucket_versioning" "config" {
  bucket = aws_s3_bucket.config.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "config" {
  bucket = aws_s3_bucket.config.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# DynamoDB table for WebSocket connections
resource "aws_dynamodb_table" "websocket_connections" {
  name         = "bus-simulator-websocket-connections"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "connection_id"

  attribute {
    name = "connection_id"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = var.tags
}

# CloudWatch log groups
resource "aws_cloudwatch_log_group" "lambda_people_count" {
  name              = "/aws/lambda/bus-simulator-people-count"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "lambda_sensors" {
  name              = "/aws/lambda/bus-simulator-sensors"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "lambda_bus_position" {
  name              = "/aws/lambda/bus-simulator-bus-position"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "lambda_websocket" {
  name              = "/aws/lambda/bus-simulator-websocket"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "ecs_people_count" {
  name              = "/ecs/people-count-feeder"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "ecs_sensors" {
  name              = "/ecs/sensors-feeder"
  retention_in_days = 30

  tags = var.tags
}

resource "aws_cloudwatch_log_group" "ecs_bus_position" {
  name              = "/ecs/bus-position-feeder"
  retention_in_days = 30

  tags = var.tags
}
