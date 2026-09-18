#!/usr/bin/env bash
# Startup script for PH Trend Hunter
set -e

PORT="${PORT:-8000}"
HOST="${HOST:-0.0.0.0}"

echo "========================================================="
echo " Starting PH Trend Hunter (Autonomous Web Service)"
echo " Host: $HOST"
echo " Port: $PORT"
echo "========================================================="

python3 server.py
