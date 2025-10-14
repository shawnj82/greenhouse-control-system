#!/bin/bash
# Greenhouse Sensor Scheduler Service Startup Script
# Activates virtual environment and starts the sensor scheduler

set -e

# Set up PATH for systemd environment
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

# Configuration
GREENHOUSE_DIR="/home/shawn/greenhouse-control-system"
VENV_DIR="$GREENHOUSE_DIR/greenhouse-env"
PYTHON_SCRIPT="sensor_scheduler_service.py"

# Change to project directory
cd "$GREENHOUSE_DIR"

# Activate virtual environment
source "$VENV_DIR/bin/activate"

# Log startup information
echo "$(date): Starting Greenhouse Sensor Scheduler Service"
echo "$(date): Working directory: $(pwd)"
echo "$(date): Python executable: $(which python)"
echo "$(date): Virtual environment: $VENV_DIR"

# Start the sensor scheduler service
exec python "$PYTHON_SCRIPT"