#!/bin/bash

# Gemini MCP Server Docker Runner
# This script starts the Gemini MCP Server in a Docker container

echo "Starting Gemini MCP Server (Docker)..."

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if docker-compose is available
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif docker compose version &> /dev/null; then
    COMPOSE_CMD="docker compose"
else
    echo "Error: docker-compose is not available. Please install Docker Compose."
    exit 1
fi

# Check if .env file exists, if not create a template
if [ ! -f .env ]; then
    echo "Creating .env file template..."
    echo "GEMINI_API_KEY=your-gemini-api-key-here" > .env
    echo ""
    echo "Please edit .env file and add your GEMINI_API_KEY"
    echo "Then run this script again."
    exit 1
fi

# Check if GEMINI_API_KEY is set in .env
if ! grep -q "GEMINI_API_KEY=.*[^[:space:]]" .env; then
    echo "Error: GEMINI_API_KEY is not set in .env file"
    echo "Please edit .env file and add your API key"
    exit 1
fi

# Get the HOST_PORT from .env if set, otherwise use default
HOST_PORT=$(grep "^HOST_PORT=" .env 2>/dev/null | cut -d'=' -f2 | tr -d ' ')
if [ -z "$HOST_PORT" ]; then
    HOST_PORT="8000"
fi

# Build and start the container
echo "Building and starting container..."
$COMPOSE_CMD up -d --build

# Check if container started successfully
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Gemini MCP Server is running at http://localhost:$HOST_PORT"
    echo ""
    echo "To view logs: $COMPOSE_CMD logs -f"
    echo "To stop: $COMPOSE_CMD down"
    echo ""
    echo "Configure your MCP client with:"
    echo "  URL: http://localhost:$HOST_PORT"
    echo '  Transport: sse'
else
    echo ""
    echo "❌ Failed to start Gemini MCP Server"
    echo "Check the logs with: $COMPOSE_CMD logs"
fi