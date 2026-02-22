# EventBridge module for Madrid Bus Real-Time Simulator
# Creates event bus and rules for real-time bus position updates

# EventBridge event bus
resource "aws_cloudwatch_event_bus" "bus_simulator" {
  name = "bus-simulator-events"

  tags = var.tags
}

# Event rule for bus position updates
resource "aws_cloudwatch_event_rule" "bus_position_updates" {
  name           = "bus-position-updates"
  event_bus_name = aws_cloudwatch_event_bus.bus_simulator.name
  description    = "Route bus position update events to WebSocket broadcast Lambda"

  event_pattern = jsonencode({
    source      = ["bus-simulator.feeder"]
    detail-type = ["Bus Position Update"]
  })

  tags = var.tags
}

# Event target - WebSocket broadcast Lambda
resource "aws_cloudwatch_event_target" "websocket_broadcast" {
  rule           = aws_cloudwatch_event_rule.bus_position_updates.name
  event_bus_name = aws_cloudwatch_event_bus.bus_simulator.name
  arn            = var.lambda_websocket_arn
  target_id      = "websocket-broadcast-lambda"
}

# Permission for EventBridge to invoke Lambda
resource "aws_lambda_permission" "eventbridge_invoke" {
  statement_id  = "AllowExecutionFromEventBridge"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_websocket_arn
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.bus_position_updates.arn
}
