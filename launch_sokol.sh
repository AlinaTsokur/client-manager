#!/bin/bash

APP_DIR="/Users/angrycat/.gemini/antigravity/scratch/client-manager"
PYTHON="/Library/Frameworks/Python.framework/Versions/3.11/bin/python3.11"
STREAMLIT="/Library/Frameworks/Python.framework/Versions/3.11/bin/streamlit"
LOG="/tmp/sokol.log"

cd "$APP_DIR"

# Kill any existing streamlit process on port 8502
lsof -ti :8502 | xargs kill -9 2>/dev/null

# Wait for port to free
sleep 1

# Start streamlit
nohup "$PYTHON" "$STREAMLIT" run app_new.py --server.port 8502 --server.address localhost --server.headless true > "$LOG" 2>&1 &

# Wait for server to start
sleep 4

# Open browser
open "http://localhost:8502"
