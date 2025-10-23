#!/bin/bash
# Greenhouse Web Server Startup Script

# Change to the project directory
cd /home/shawn/greenhouse-control-system

# Activate virtual environment and run the web server
source /home/shawn/greenhouse-control-system/greenhouse-env/bin/activate

# Set Flask to listen on all network interfaces (0.0.0.0)
# This allows access from other devices on the local network
export FLASK_HOST="0.0.0.0"

exec python web_app.py