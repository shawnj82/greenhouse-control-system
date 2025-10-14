#!/bin/bash
# Greenhouse Web Server Startup Script

# Change to the project directory
cd /home/shawn/greenhouse-control-system

# Activate virtual environment and run the web server
source /home/shawn/greenhouse-control-system/greenhouse-env/bin/activate
exec python web_app.py