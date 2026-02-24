# Dockerfile for Madrid Bus Simulator MCP Server
# This container runs the Model Context Protocol server for time series data access

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    AWS_DEFAULT_REGION=eu-west-1

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy MCP server code
COPY __init__.py .
COPY server.py .
COPY auth.py .
COPY config.json .

# Expose port for MCP protocol (stdio-based, but keeping for future HTTP support)
EXPOSE 8080

# Set environment variables for AWS services
# These will be overridden by ECS task definition
ENV TIMESTREAM_DATABASE=bus_simulator \
    AWS_REGION=eu-west-1 \
    SECRET_ID=bus-simulator/api-key

# Health check (optional, for future HTTP-based MCP)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
#   CMD python -c "import sys; sys.exit(0)"

# Set entrypoint to run MCP server
ENTRYPOINT ["python", "-m", "server"]
