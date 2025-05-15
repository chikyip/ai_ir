#!/bin/bash

# First, deactivate any current virtual environment (if active)
deactivate

# Navigate to your project directory
cd ~/ai_ir

# Create a new virtual environment if needed
python -m venv venv

# Activate the virtual environment properly
source venv/bin/activate

# Install the required packages
pip install flask PyMuPDF werkzeug watchdog requests

# Run your application
python backend/app.py