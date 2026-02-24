# Security Groups Configuration for MCP Server

## Overview

This document describes the security group configuration for the MCP server ECS service, ensuring secure communication with AWS services and external clients.

## Security Groups

### 1. MCP Server Security Group (`aws_security_group.mcp_server`)

**Purpose**: Controls inbound and outbound traffic for the MCP server ECS tasks running in private subnets.

**Inbound Rules**:
- **Port 8080/TCP from VPC CIDR**: Allows MCP protocol traffic from within the VPC
  - Source: VPC CIDR block (default: 10.0.0.0/16)
  - Description: "Allow MCP server traffic from within VPC"

- **Port 8080/TCP from VPC Link Security Group**: Allows traffic from API Gateway VPC Link
  - Source: VPC Link security group
  - Description: "Allow traffic from VPC Link"
  - Configured via `aws_security_group_rule.mcp_from_vpc_link`

**Outbound Rules**:
- **All traffic to 0.0.0.0/0**: Allows outbound connections to AWS services
  - Enables access to:
    - Timestream (query and ingest endpoints)
    - Secrets Manager (for API key retrieval)
    - CloudWatch Logs (for logging)
    - ECR (for container image pulls during deployment)

### 2. VPC Link Security Group (`aws_security_group.vpc_link`)

**Purpose**: Controls traffic from API Gateway VPC Link to the MCP server.

**Outbound Rules**:
- **All traffic to VPC CIDR**: Allows VPC Link to reach MCP server in private subnets
  - Destination: VPC CIDR block
  - Description: "Allow traffic to MCP server in VPC"

### 3. VPC Endpoints Security Group (`aws_security_group.vpc_endpoints`)

**Purpose**: Controls access to VPC endpoints for private communication with AWS services.

**Inbound Rules**:
- **Port 443/TCP from VPC CIDR**: Allows HTTPS traffic from VPC resources to AWS service endpoints
  - Source: VPC CIDR block
  - Description: "Allow HTTPS from VPC for AWS service access"

**Note**: This security group is only created when `enable_vpc_endpoints = true`.

## VPC Endpoints (Optional)

VPC endpoints provide private connectivity to AWS services without requiring internet gateway, NAT device, VPN connection, or AWS Direct Connect. They improve security and can reduce data transfer costs.

### Configured VPC Endpoints

When `enable_vpc_endpoints = true`, the following interface endpoints are created:

1. **Secrets Manager Endpoint** (`aws_vpc_endpoint.secrets_manager`)
   - Service: `com.amazonaws.{region}.secretsmanager`
   - Purpose: Private access for API key retrieval
   - Private DNS: Enabled

2. **CloudWatch Logs Endpoint** (`aws_vpc_endpoint.logs`)
   - Service: `com.amazonaws.{region}.logs`
   - Purpose: Private access for log streaming
   - Private DNS: Enabled

3. **Timestream Ingest Endpoint** (`aws_vpc_endpoint.timestream_ingest`)
   - Service: `com.amazonaws.{region}.timestream.ingest-cell1`
   - Purpose: Private access for writing time series data
   - Private DNS: Enabled

4. **Timestream Query Endpoint** (`aws_vpc_endpoint.timestream_query`)
   - Service: `com.amazonaws.{region}.timestream.query-cell1`
   - Purpose: Private access for querying time series data
   - Private DNS: Enabled

### Benefits of VPC Endpoints

- **Enhanced Security**: Traffic between VPC and AWS services doesn't traverse the internet
- **Reduced Costs**: No NAT gateway data processing charges for AWS service traffic
- **Better Performance**: Lower latency for AWS service API calls
- **Compliance**: Meets requirements for private network communication

### Disabling VPC Endpoints

If you prefer to use public endpoints via NAT Gateway, set `enable_vpc_endpoints = false` in the module configuration. The MCP server will still function correctly, routing traffic through the NAT Gateway.

## Traffic Flow

### External Client → MCP Server

1. Client sends HTTPS request to API Gateway HTTP API
2. API Gateway Custom Authorizer validates API key (via Secrets Manager)
3. API Gateway forwards request through VPC Link
4. VPC Link routes to MCP server ECS task in private subnet
5. MCP server processes request and returns response

### MCP Server → AWS Services

#### With VPC Endpoints (Recommended)

1. MCP server makes API call to AWS service (e.g., Timestream)
2. Request routes to VPC endpoint in private subnet
3. VPC endpoint forwards to AWS service via AWS private network
4. Response returns via same path

#### Without VPC Endpoints

1. MCP server makes API call to AWS service
2. Request routes through NAT Gateway to internet
3. Request reaches AWS service public endpoint
4. Response returns via same path

## Security Best Practices

1. **Least Privilege**: MCP server security group only allows necessary inbound traffic (port 8080 from VPC Link)
2. **Private Subnets**: MCP server runs in private subnets with no direct internet access
3. **VPC Endpoints**: Optional VPC endpoints keep AWS service traffic within AWS network
4. **Egress Control**: Outbound traffic is allowed to all destinations, but can be restricted to specific AWS service CIDR ranges if needed
5. **API Gateway Integration**: External access is only via API Gateway with authentication

## Configuration Variables

- `create_vpc`: Whether to create VPC and security groups (default: `true`)
- `vpc_cidr`: CIDR block for VPC (default: `10.0.0.0/16`)
- `enable_vpc_endpoints`: Whether to create VPC endpoints for private AWS service access (default: `true`)

## Compliance with Requirements

This configuration satisfies **Requirement 14.15**:
> "THE System SHALL configure ECS service networking to allow secure communication with Timestream_DB and Secrets_Manager"

- ✅ MCP server security group allows outbound traffic to AWS services
- ✅ VPC endpoints (optional) provide private communication paths
- ✅ Security groups follow least privilege principle
- ✅ All traffic is encrypted (HTTPS/TLS)
