#!/bin/bash
sudo pkill -f gunicorn
cd /home/chartnexus/ai_ir/backend
gunicorn -c /home/chartnexus/ai_ir/backend/gunicorn_config.py app:app