# API Gateway module for Madrid Bus Real-Time Simulator
# Creates REST API with API key authentication (no rate limiting) and WebSocket API with Lambda integrations


/*

# API Keys for hackathon participants
resource "aws_api_gateway_api_key" "participant_keys" {
  count       = var.participant_count
  name        = "participant-${count.index + 1}"
  description = "API Key for participant ${count.index + 1} to access the bus simulator API"
  enabled     = true

  tags = var.tags
}

# Usage Plan without rate limiting
resource "aws_api_gateway_usage_plan" "hackathon" {
  name        = "hackathon-usage-plan"
  description = "Usage plan for hackathon participants (no rate limiting)"

  api_stages {
    api_id = aws_api_gateway_rest_api.main.id
    stage  = aws_api_gateway_stage.prod.stage_name
  }

  tags = var.tags
}

# Associate API keys with usage plan
resource "aws_api_gateway_usage_plan_key" "participant_keys" {
  count         = var.participant_count
  key_id        = aws_api_gateway_api_key.participant_keys[count.index].id
  key_type      = "API_KEY"
  usage_plan_id = aws_api_gateway_usage_plan.hackathon.id
}

*/