# ================================
# FILE: scripts/deploy.sh
# ================================

#!/bin/bash

# Deployment script for Voice Cloning Application

echo "Deploying Voice Cloning Application..."

# Build Docker image
docker build -f docker/Dockerfile -t voice-cloning-api .

# Run with docker-compose
docker-compose -f docker/docker-compose.yml up -d

echo "Application deployed successfully!"
echo "Access the API at: http://localhost:8000"
echo "API documentation at: http://localhost:8000/docs"