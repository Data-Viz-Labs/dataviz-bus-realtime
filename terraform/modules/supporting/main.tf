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

# Security group for MCP server
resource "aws_security_group" "mcp_server" {
  count = var.create_vpc ? 1 : 0

  name        = "bus-simulator-mcp-server-sg"
  description = "Security group for MCP server ECS service"
  vpc_id      = aws_vpc.main[0].id

  # Allow inbound on MCP server port from within VPC
  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Allow MCP server traffic from within VPC"
  }

  # Allow all outbound traffic for AWS service access
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = merge(var.tags, {
    Name = "bus-simulator-mcp-server-sg"
  })
}

# Security group for VPC Link (API Gateway to MCP server)
resource "aws_security_group" "vpc_link" {
  count = var.create_vpc ? 1 : 0

  name        = "bus-simulator-vpc-link-sg"
  description = "Security group for VPC Link to MCP server"
  vpc_id      = aws_vpc.main[0].id

  # Allow all outbound traffic to MCP server
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = [var.vpc_cidr]
    description = "Allow traffic to MCP server in VPC"
  }

  tags = merge(var.tags, {
    Name = "bus-simulator-vpc-link-sg"
  })
}

# Update MCP server security group to allow traffic from VPC Link
resource "aws_security_group_rule" "mcp_from_vpc_link" {
  count = var.create_vpc ? 1 : 0

  type                     = "ingress"
  from_port                = 8080
  to_port                  = 8080
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.vpc_link[0].id
  security_group_id        = aws_security_group.mcp_server[0].id
  description              = "Allow traffic from VPC Link"
}

# CloudWatch log group for MCP server
resource "aws_cloudwatch_log_group" "mcp_server" {
  name              = "/ecs/mcp-server"
  retention_in_days = 30

  tags = var.tags
}

# VPC Endpoints for private communication with AWS services
# These endpoints allow the MCP server to communicate with AWS services
# without traffic leaving the AWS network, improving security and performance

# VPC Endpoint for Secrets Manager
resource "aws_vpc_endpoint" "secrets_manager" {
  count = var.create_vpc && var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main[0].id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "bus-simulator-secrets-manager-endpoint"
  })
}

# VPC Endpoint for CloudWatch Logs
resource "aws_vpc_endpoint" "logs" {
  count = var.create_vpc && var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main[0].id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "bus-simulator-logs-endpoint"
  })
}

# VPC Endpoint for Timestream (Ingest)
resource "aws_vpc_endpoint" "timestream_ingest" {
  count = var.create_vpc && var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main[0].id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.timestream.ingest-cell1"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "bus-simulator-timestream-ingest-endpoint"
  })
}

# VPC Endpoint for Timestream (Query)
resource "aws_vpc_endpoint" "timestream_query" {
  count = var.create_vpc && var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main[0].id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.timestream.query-cell1"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = merge(var.tags, {
    Name = "bus-simulator-timestream-query-endpoint"
  })
}

# Security group for VPC endpoints
resource "aws_security_group" "vpc_endpoints" {
  count = var.create_vpc && var.enable_vpc_endpoints ? 1 : 0

  name        = "bus-simulator-vpc-endpoints-sg"
  description = "Security group for VPC endpoints (Secrets Manager, Timestream, CloudWatch Logs)"
  vpc_id      = aws_vpc.main[0].id

  # Allow inbound HTTPS traffic from VPC CIDR
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.vpc_cidr]
    description = "Allow HTTPS from VPC for AWS service access"
  }

  tags = merge(var.tags, {
    Name = "bus-simulator-vpc-endpoints-sg"
  })
}

# Data source for current region
data "aws_region" "current" {}
