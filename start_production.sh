#!/bin/bash

# Kill any process running on port 5001
echo "Killing any process running on port 5001..."
sudo kill -9 $(sudo lsof -t -i:5001) 2>/dev/null || echo "No process running on port 5001"

# Wait a moment to ensure the port is released
sleep 2

# Install required dependencies
echo "Installing required dependencies..."
pip install flask waitress watchdog pymupdf requests python-dotenv pillow

# Change to the backend directory
cd /home/chartnexus/ai_ir/backend

# Create logs directory if it doesn't exist
mkdir -p logs
chmod 777 logs

# Start the application in production mode in the background
echo "Starting application in production mode on port 5001..."
export PRODUCTION_MODE=true
export PORT=5001
nohup python app.py > logs/app.log 2>&1 &

# Get the PID of the new process
PID=$!
echo "Application started with PID: $PID"
echo "Logs are being written to /home/chartnexus/ai_ir/backend/logs/app.log"

# Save the PID to a file
echo $PID > logs/app.pid
echo "Process ID saved to logs/app.pid"

# Verify the process is running
sleep 2
if ps -p $PID > /dev/null; then
    echo "Process is running successfully in the background."
else
    echo "Warning: Process may have failed to start. Check logs/app.log for details."
fi