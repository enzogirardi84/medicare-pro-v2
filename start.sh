#!/bin/bash
# MediCare PRO - Start script for production
# Usage: bash start.sh [port]

PORT=${1:-8501}
echo "Starting MediCare PRO on port $PORT..."
streamlit run streamlit_app.py --server.port $PORT --server.headless true --browser.gatherUsageStats false
