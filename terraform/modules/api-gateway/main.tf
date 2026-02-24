# API Gateway module for Madrid Bus Real-Time Simulator
# Creates REST API with Custom Authorizer authentication and WebSocket API with Lambda integrations
# API key management is now handled via Secrets Manager (see secrets-manager.tf and authorizers.tf)

# Note: API Gateway API keys and usage plans have been replaced with Custom Authorizers
# that validate against a single API key stored in AWS Secrets Manager.
# This provides centralized key management and better security.
