# Lambda functions
resource "aws_lambda_function" "people_count_api" {
  filename         = "${path.root}/../build/people_count_api.zip"
  function_name    = "bus-simulator-people-count"
  role             = var.lambda_execution_role_arn
  handler          = "people_count_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/people_count_api.zip")
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      TIMESTREAM_DATABASE = var.timestream_database_name
      TIMESTREAM_TABLE    = var.timestream_tables.people_count
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "sensors_api" {
  filename         = "${path.root}/../build/sensors_api.zip"
  function_name    = "bus-simulator-sensors"
  role             = var.lambda_execution_role_arn
  handler          = "sensors_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/sensors_api.zip")
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      TIMESTREAM_DATABASE = var.timestream_database_name
      TIMESTREAM_TABLE    = var.timestream_tables.sensor_data
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "bus_position_api" {
  filename         = "${path.root}/../build/bus_position_api.zip"
  function_name    = "bus-simulator-bus-position"
  role             = var.lambda_execution_role_arn
  handler          = "bus_position_api.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/bus_position_api.zip")
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      TIMESTREAM_DATABASE = var.timestream_database_name
      TIMESTREAM_TABLE    = var.timestream_tables.bus_position
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "websocket_handler" {
  filename         = "${path.root}/../build/websocket_handler.zip"
  function_name    = "bus-simulator-websocket"
  role             = var.lambda_execution_role_arn
  handler          = "websocket_handler.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/websocket_handler.zip")
  runtime          = "python3.11"
  timeout          = 30

  environment {
    variables = {
      DYNAMODB_TABLE = var.dynamodb_table_name
    }
  }

  tags = var.tags
}

resource "aws_lambda_function" "websocket_authorizer" {
  filename         = "${path.root}/../build/websocket_authorizer.zip"
  function_name    = "bus-simulator-websocket-authorizer"
  role             = var.lambda_execution_role_arn
  handler          = "websocket_authorizer.lambda_handler"
  source_code_hash = filebase64sha256("${path.root}/../build/websocket_authorizer.zip")
  runtime          = "python3.11"
  timeout          = 10

  environment {
    variables = {
      REST_API_ID = aws_api_gateway_rest_api.main.id
    }
  }

  tags = var.tags
}
