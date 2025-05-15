#!/bin/bash

# Kill any process running on port 5001
echo "Killing any process running on port 5001..."
sudo kill -9 $(sudo lsof -t -i:5001) 2>/dev/null || echo "No process running on port 5001"

# Wait a moment to ensure the port is released
sleep 2
echo "Port 5001 has been cleared"