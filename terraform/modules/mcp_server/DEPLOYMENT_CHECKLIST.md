# MCP Server API Gateway Deployment Checklist

## Pre-Deployment

### 1. Prerequisites
- [ ] AWS CLI configured with appropriate credentials
- [ ] Terraform >= 1.0 installed
- [ ] Docker installed (for building MCP server image)
- [ ] jq installed (for JSON parsing in scripts)

### 2. Infrastructure Review
- [ ] Review VPC configuration (CIDR, subnets)
- [ ] Verify NAT Gateway exists for private subnet outbound connectivity
- [ ] Check ECS cluster is running
- [ ] Verify ECR repository contains MCP server image
- [ ] Confirm Secrets Manager secret exists with API key

### 3. Configuration Review
- [ ] Review `terraform.tfvars` for correct values
- [ ] Set `mcp_cors_allowed_origins` if restricting CORS
- [ ] Adjust `mcp_cpu` and `mcp_memory` based on expected load
- [ ] Configure `throttling_burst_limit` and `throttling_rate_limit`

## Deployment Steps

### 1. Initialize Terraform
```bash
cd dataviz-bus-realtime/terraform
terraform init
```
- [ ] Terraform initialized successfully
- [ ] Provider plugins downloaded

### 2. Plan Deployment
```bash
terraform plan -out=tfplan
```
- [ ] Review planned changes
- [ ] Verify new resources to be created:
  - Service Discovery namespace and service
  - VPC Link
  - HTTP API Gateway
  - API Gateway authorizer
  - API Gateway integration
  - API Gateway routes
  - API Gateway stage
  - CloudWatch log group
  - Security group for VPC Link
  - Security group rule for MCP server

### 3. Apply Changes
```bash
terraform apply tfplan
```
- [ ] Deployment completed successfully
- [ ] Note the `mcp_api_endpoint` output value

### 4. Wait for Resources
- [ ] VPC Link status is AVAILABLE (5-10 minutes)
- [ ] ECS service has running tasks
- [ ] Service Discovery shows registered instances

## Post-Deployment Verification

### 1. Check VPC Link
```bash
aws apigatewayv2 get-vpc-links
```
- [ ] VPC Link status is AVAILABLE
- [ ] Security group attached correctly

### 2. Check Service Discovery
```bash
aws servicediscovery discover-instances \
  --namespace-name mcp.local \
  --service-name mcp-server
```
- [ ] At least one instance registered
- [ ] Instance shows healthy status

### 3. Check ECS Service
```bash
aws ecs describe-services \
  --cluster bus-simulator \
  --services mcp-server
```
- [ ] Desired count matches running count
- [ ] Service is ACTIVE
- [ ] No deployment failures

### 4. Test Health Check
```bash
MCP_ENDPOINT=$(terraform output -raw mcp_api_endpoint)
curl "${MCP_ENDPOINT}/health"
```
- [ ] Returns 200 OK
- [ ] Response indicates healthy status

### 5. Test Authentication
```bash
# Get API key
API_KEY=$(aws secretsmanager get-secret-value \
  --secret-id bus-simulator/api-key \
  --query SecretString --output text | jq -r '.api_key')

# Test with valid credentials
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-api-key: ${API_KEY}" \
  -H "x-group-name: group1" \
  -H "Content-Type: application/json"
```
- [ ] Returns 200 OK with list of tools
- [ ] No authentication errors

### 6. Test Authorization Failures
```bash
# Test missing API key
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-group-name: group1" \
  -H "Content-Type: application/json"

# Test missing group name
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-api-key: ${API_KEY}" \
  -H "Content-Type: application/json"

# Test invalid API key
curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "x-api-key: invalid-key" \
  -H "x-group-name: group1" \
  -H "Content-Type: application/json"
```
- [ ] Missing API key returns 401
- [ ] Missing group name returns 401
- [ ] Invalid API key returns 403

### 7. Test CORS
```bash
curl -X OPTIONS "${MCP_ENDPOINT}/mcp/list-tools" \
  -H "Origin: https://example.com" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: x-api-key,x-group-name" \
  -v
```
- [ ] Returns CORS headers
- [ ] Access-Control-Allow-Origin present
- [ ] Access-Control-Allow-Methods includes POST
- [ ] Access-Control-Allow-Headers includes x-api-key and x-group-name

## Monitoring Setup

### 1. CloudWatch Logs
```bash
# API Gateway logs
aws logs tail /aws/apigateway/mcp-server --follow

# MCP server logs
aws logs tail /ecs/mcp-server --follow

# Authorizer logs
aws logs tail /aws/lambda/bus-simulator-rest-authorizer --follow
```
- [ ] Logs are being generated
- [ ] No error messages in logs
- [ ] Request/response logging working

### 2. CloudWatch Metrics
- [ ] API Gateway metrics visible in CloudWatch console
- [ ] ECS service metrics visible
- [ ] No elevated error rates

### 3. Alarms (Optional)
- [ ] Create alarm for API Gateway 5xx errors
- [ ] Create alarm for ECS service unhealthy tasks
- [ ] Create alarm for high latency

## Security Verification

### 1. Network Security
```bash
# Check security groups
aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=bus-simulator-vpc-link-sg"

aws ec2 describe-security-groups \
  --filters "Name=tag:Name,Values=bus-simulator-mcp-server-sg"
```
- [ ] VPC Link SG allows egress to VPC CIDR
- [ ] MCP server SG allows ingress from VPC Link SG
- [ ] MCP server SG allows egress to internet (for AWS services)

### 2. IAM Permissions
- [ ] Authorizer Lambda has Secrets Manager read permission
- [ ] ECS task role has Timestream query permission
- [ ] ECS task role has Secrets Manager read permission
- [ ] ECS execution role has ECR pull permission

### 3. API Gateway Security
- [ ] Authorizer is attached to protected routes
- [ ] Health check route is public (no authorizer)
- [ ] Throttling limits configured
- [ ] Access logging enabled

## Performance Testing

### 1. Load Test
```bash
# Install hey (HTTP load testing tool)
# brew install hey  # macOS
# apt-get install hey  # Ubuntu

# Run load test
hey -n 1000 -c 10 \
  -H "x-api-key: ${API_KEY}" \
  -H "x-group-name: group1" \
  -m POST \
  "${MCP_ENDPOINT}/mcp/list-tools"
```
- [ ] All requests succeed
- [ ] Average latency < 500ms
- [ ] No throttling errors
- [ ] ECS service scales if needed

### 2. Concurrent Requests
```bash
# Test concurrent requests
for i in {1..10}; do
  curl -X POST "${MCP_ENDPOINT}/mcp/list-tools" \
    -H "x-api-key: ${API_KEY}" \
    -H "x-group-name: group1" \
    -H "Content-Type: application/json" &
done
wait
```
- [ ] All requests complete successfully
- [ ] No connection errors
- [ ] Consistent response times

## Documentation

- [ ] Update API documentation with new endpoint
- [ ] Document authentication requirements
- [ ] Add example requests to documentation
- [ ] Update client SDKs/libraries
- [ ] Notify users of new endpoint

## Rollback Plan

### If Issues Occur

1. **Check Logs**:
   ```bash
   aws logs tail /aws/apigateway/mcp-server --since 1h
   aws logs tail /ecs/mcp-server --since 1h
   ```

2. **Rollback Terraform**:
   ```bash
   terraform destroy -target=module.mcp_server.aws_apigatewayv2_api.mcp
   terraform destroy -target=module.mcp_server.aws_apigatewayv2_vpc_link.mcp
   ```

3. **Full Rollback**:
   ```bash
   git checkout <previous-commit>
   terraform apply
   ```

## Cost Monitoring

### 1. Check Current Costs
```bash
# Check AWS Cost Explorer
aws ce get-cost-and-usage \
  --time-period Start=2024-01-01,End=2024-01-31 \
  --granularity MONTHLY \
  --metrics BlendedCost \
  --filter file://cost-filter.json
```

### 2. Set Budget Alerts
- [ ] Budget alert configured for monthly costs
- [ ] Email notifications enabled
- [ ] Threshold set appropriately

### 3. Monitor Usage
- [ ] Track API Gateway request count
- [ ] Monitor VPC Link hours
- [ ] Track ECS Fargate usage
- [ ] Monitor CloudWatch Logs ingestion

## Maintenance

### Regular Tasks

**Daily**:
- [ ] Check CloudWatch logs for errors
- [ ] Monitor API Gateway metrics
- [ ] Verify ECS service health

**Weekly**:
- [ ] Review CloudWatch metrics trends
- [ ] Check for security updates
- [ ] Review cost reports

**Monthly**:
- [ ] Review and optimize resource allocation
- [ ] Update documentation
- [ ] Review security group rules
- [ ] Rotate API keys if needed

## Troubleshooting Reference

### Issue: VPC Link Creation Timeout
**Solution**: VPC Link can take 5-10 minutes. Wait and check status.

### Issue: 504 Gateway Timeout
**Solution**: 
1. Check ECS service has running tasks
2. Verify Service Discovery registration
3. Check security group rules
4. Review MCP server logs

### Issue: 401 Unauthorized
**Solution**:
1. Verify both x-api-key and x-group-name headers present
2. Check API key matches Secrets Manager value
3. Review authorizer Lambda logs

### Issue: CORS Errors
**Solution**:
1. Verify allowed origins include client domain
2. Check preflight OPTIONS requests succeed
3. Verify allowed headers include required headers

## Sign-off

- [ ] Deployment completed successfully
- [ ] All tests passed
- [ ] Monitoring configured
- [ ] Documentation updated
- [ ] Team notified

**Deployed by**: _______________  
**Date**: _______________  
**Environment**: Production  
**Version**: _______________
