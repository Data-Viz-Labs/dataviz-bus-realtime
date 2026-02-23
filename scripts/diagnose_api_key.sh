#!/bin/bash
# Script to diagnose API Gateway API Key issues

set -e

REGION="eu-west-1"
API_ID="0w08yrrx1a"
STAGE_NAME="prod"

echo "=== API Gateway API Key Diagnostic ==="
echo ""

# Get API key from terraform
echo "1. Getting API key from Terraform..."
API_KEY=$(cd terraform && terraform output -json api_key_values | jq -r '.[0]')
echo "   API Key: ${API_KEY:0:8}..."
echo ""

# Check if API key exists and is enabled
echo "2. Checking API key status..."
aws apigateway get-api-key \
  --region $REGION \
  --api-key $API_KEY \
  --include-value \
  --query '{id: id, name: name, enabled: enabled}' \
  --output json
echo ""

# Get usage plan ID
echo "3. Getting usage plan..."
USAGE_PLAN_ID=$(cd terraform && terraform output -raw usage_plan_id)
echo "   Usage Plan ID: $USAGE_PLAN_ID"
echo ""

# Check usage plan configuration
echo "4. Checking usage plan configuration..."
aws apigateway get-usage-plan \
  --region $REGION \
  --usage-plan-id $USAGE_PLAN_ID \
  --query '{id: id, name: name, apiStages: apiStages}' \
  --output json
echo ""

# Check if API key is associated with usage plan
echo "5. Checking API key association with usage plan..."
aws apigateway get-usage-plan-keys \
  --region $REGION \
  --usage-plan-id $USAGE_PLAN_ID \
  --query "items[?id=='$API_KEY']" \
  --output json
echo ""

# Check method configuration
echo "6. Checking method configuration..."
RESOURCE_ID=$(aws apigateway get-resources \
  --region $REGION \
  --rest-api-id $API_ID \
  --query "items[?path=='/people-count/{stop_id}'].id" \
  --output text)

aws apigateway get-method \
  --region $REGION \
  --rest-api-id $API_ID \
  --resource-id $RESOURCE_ID \
  --http-method GET \
  --query '{httpMethod: httpMethod, authorizationType: authorizationType, apiKeyRequired: apiKeyRequired}' \
  --output json
echo ""

# Check stage configuration
echo "7. Checking stage configuration..."
aws apigateway get-stage \
  --region $REGION \
  --rest-api-id $API_ID \
  --stage-name $STAGE_NAME \
  --query '{stageName: stageName, deploymentId: deploymentId}' \
  --output json
echo ""

# Test API call without API key
echo "8. Testing API call WITHOUT API key (should fail)..."
curl -s -w "\nHTTP Status: %{http_code}\n" \
  "https://${API_ID}.execute-api.${REGION}.amazonaws.com/${STAGE_NAME}/people-count/S001?mode=latest" \
  | head -5
echo ""

# Test API call with API key
echo "9. Testing API call WITH API key..."
curl -s -w "\nHTTP Status: %{http_code}\n" \
  -H "x-api-key: $API_KEY" \
  "https://${API_ID}.execute-api.${REGION}.amazonaws.com/${STAGE_NAME}/people-count/S001?mode=latest" \
  | head -5
echo ""

# Check recent logs
echo "10. Checking recent execution logs..."
aws logs tail "API-Gateway-Execution-Logs_${API_ID}/${STAGE_NAME}" \
  --region $REGION \
  --since 2m \
  --format short \
  2>/dev/null | grep -i "forbidden\|api key" | tail -3 || echo "   No recent logs found"
echo ""

echo "=== Diagnostic Complete ==="
