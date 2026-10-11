# The simulator: one long-running Fargate task that owns every bus and every stop queue. It
# publishes the live snapshot (site bucket), MQTT (IoT Core), the tracked buses (Amazon
# Location) and history (data bucket). The same task definition runs `python -m sim.backfill`.

resource "aws_ecr_repository" "simulator" {
  name                 = "${local.name}-simulator"
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

resource "aws_ecr_lifecycle_policy" "simulator" {
  repository = aws_ecr_repository.simulator.name
  policy = jsonencode({
    rules = [{
      rulePriority = 1
      description  = "Keep the last 5 images"
      selection    = { tagStatus = "any", countType = "imageCountMoreThan", countNumber = 5 }
      action       = { type = "expire" }
    }]
  })
}

resource "aws_cloudwatch_log_group" "simulator" {
  name              = "/ecs/${local.name}-simulator"
  retention_in_days = 14
}

resource "aws_ecs_cluster" "main" {
  name = local.name
}

data "aws_iam_policy_document" "ecs_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
    condition {
      test     = "StringEquals"
      variable = "aws:SourceAccount"
      values   = [local.account_id]
    }
  }
}

resource "aws_iam_role" "execution" {
  name               = "${local.name}-execution"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role" "simulator" {
  name               = "${local.name}-simulator"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume.json
}

data "aws_iam_policy_document" "simulator" {
  statement {
    sid       = "Positions"
    actions   = ["geo:BatchUpdateDevicePosition"]
    resources = [aws_location_tracker.buses.tracker_arn]
  }
  statement {
    sid       = "MapKey"
    actions   = ["geo:DescribeKey"]
    resources = ["arn:aws:geo:${var.aws_region}:${local.account_id}:api-key/${local.name}-map"]
  }
  dynamic "statement" {
    for_each = aws_location_geofence_collection.stops
    content {
      sid       = "StopGeofences"
      actions   = ["geo:ListGeofences", "geo:BatchPutGeofence"]
      resources = [statement.value.collection_arn]
    }
  }
  statement {
    sid       = "PublishSnapshot"
    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.site.arn}/live/*"]
  }
  statement {
    sid       = "HistoryAndPrivateState"
    actions   = ["s3:PutObject", "s3:GetObject"]
    resources = ["${aws_s3_bucket.data.arn}/history/*", "${aws_s3_bucket.data.arn}/private/*"]
  }
  statement {
    sid       = "MissingKeyIsNotAnError" # without ListBucket a missing key is a 403, not a 404
    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.data.arn]
    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["private/*", "history/*"]
    }
  }
}

resource "aws_iam_role_policy" "simulator" {
  role   = aws_iam_role.simulator.id
  policy = data.aws_iam_policy_document.simulator.json
}

data "aws_vpc" "default" {
  count   = length(var.subnet_ids) == 0 ? 1 : 0
  default = true
}

data "aws_subnets" "default" {
  count = length(var.subnet_ids) == 0 ? 1 : 0
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default[0].id]
  }
}

data "aws_subnet" "first" {
  id = local.subnet_ids[0]
}

locals {
  subnet_ids = length(var.subnet_ids) > 0 ? var.subnet_ids : data.aws_subnets.default[0].ids
}

# Outbound only: the task calls AWS APIs and nothing calls it.
resource "aws_security_group" "simulator" {
  name        = "${local.name}-simulator"
  description = "Simulator task, egress only"
  vpc_id      = data.aws_subnet.first.vpc_id

  egress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "simulator" {
  family                   = "${local.name}-simulator"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.task_cpu
  memory                   = var.task_memory
  execution_role_arn       = aws_iam_role.execution.arn
  task_role_arn            = aws_iam_role.simulator.arn

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "ARM64"
  }

  container_definitions = jsonencode([{
    name      = "simulator"
    image     = "${aws_ecr_repository.simulator.repository_url}:${var.image_tag}"
    essential = true
    environment = [
      { name = "SITE_BUCKET", value = aws_s3_bucket.site.id },
      { name = "DATA_BUCKET", value = aws_s3_bucket.data.id },
      { name = "MQTT_ENDPOINT", value = local.mqtt_endpoint },
      { name = "API_URL", value = trimsuffix(aws_lambda_function_url.api.function_url, "/") },
      { name = "TRACKER_NAME", value = aws_location_tracker.buses.tracker_name },
      { name = "TRACKED_LINES", value = var.tracked_lines },
      { name = "GEOFENCE_COLLECTION", value = var.stop_geofences ? aws_location_geofence_collection.stops[0].collection_name : "" },
      { name = "HEARTBEAT_SECONDS", value = tostring(var.heartbeat_seconds) },
      { name = "MAP_KEY_NAME", value = jsondecode(aws_cloudcontrolapi_resource.map_key.desired_state).KeyName },
      { name = "LINES", value = var.lines },
      { name = "AWS_REGION", value = var.aws_region },
    ]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.simulator.name
        awslogs-region        = var.aws_region
        awslogs-stream-prefix = "simulator"
      }
    }
    stopTimeout = 30
  }])
}

resource "aws_ecs_service" "simulator" {
  name            = "simulator"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.simulator.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  # Exactly one simulator may run: two would write conflicting positions.
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  network_configuration {
    subnets          = local.subnet_ids
    security_groups  = [aws_security_group.simulator.id]
    assign_public_ip = true
  }

  deployment_circuit_breaker {
    enable   = true
    rollback = true
  }

  # The deploy-app workflow registers new task revisions; `make stop/start` changes the count.
  lifecycle {
    ignore_changes = [task_definition, desired_count]
  }
}
