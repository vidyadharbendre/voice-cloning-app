# ================================
# FILE: scripts/setup.sh
# ================================

#!/bin/bash

# Setup script for Voice Cloning Application

echo "Setting up Voice Cloning Application..."

# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p uploads outputs logs

# Copy environment file
cp .env.example .env

echo "Setup complete!"
echo "Please edit .env file with your configuration"
echo "Run 'python run.py' to start the application"