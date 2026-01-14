#!/bin/bash

# Check if .env file exists
if [ -f .env ]; then
    echo "Starting containers with environment variables from .env file..."
    docker run --rm -d --network host --env-file .env --name gc green_agent --host 127.0.0.1 --port 9009
    docker run --rm -d --network host --env-file .env --name pc purple_agent --host 127.0.0.1 --port 9019
else
    echo "Warning: .env file not found. Starting containers without environment file..."
    docker run --rm -d --network host --name gc green_agent --host 127.0.0.1 --port 9009
    docker run --rm -d --network host --name pc purple_agent --host 127.0.0.1 --port 9019
fi

# wait for agents to start
echo "Waiting for agents to start... 40 seconds"
sleep 40

# Run scenario using fwa-run command from green agent container
docker exec gc uv run fwa-run scenarios/fwa/scenario.toml
docker exec gc cat logs/FWA_green_agent.log
docker stop gc
docker stop pc
