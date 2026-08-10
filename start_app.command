#!/bin/bash

# Navigate to the pipeline-copilot directory
cd "$(dirname "$0")"

echo "Killing any previous instances of Simulator Frontend..."
lsof -ti:5174 | xargs kill -9 2>/dev/null

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  🛡️  NemoGuard — Agentic Pipeline Incident Commander  ║"
echo "╚══════════════════════════════════════════════════════╝"
echo ""

echo "Building and starting Docker Compose stack..."
# Start the main stack in detached mode
docker-compose up -d --build

echo "Starting Simulator Frontend on port 5174..."
cd simulator-frontend
npm install > /dev/null 2>&1
npm run dev -- --host 127.0.0.1 --port 5174 > ../logs/simulator_ui.log 2>&1 &
SIM_VITE_PID=$!
cd ..

echo ""
echo "✅ All services are starting up!"
echo ""
echo "   NemoGuard API:       http://localhost:8000/docs"
echo "   NemoGuard UI:        http://localhost:80"
echo "   Simulator API:       http://localhost:8001/docs"
echo "   Chaos Simulator UI:  http://localhost:5174"
echo "   Temporal Web UI:     http://localhost:8233"
echo ""
echo "   Quick Start:"
echo "   1. Open the Chaos Simulator UI at http://localhost:5174"
echo "   2. Open the NemoGuard UI at http://localhost:80"
echo "   3. Open the Temporal UI at http://localhost:8233 to watch durable workflow state"
echo "   4. Click a Chaos button in the Simulator to trigger a live incident"
echo "   5. Watch the autonomous triage unfold in the NemoGuard Command Center"
echo ""
echo "Press Ctrl+C to stop all services."

# Trap SIGINT to kill background processes and docker containers
trap "echo ''; echo 'Stopping services...'; docker-compose down; kill $SIM_VITE_PID 2>/dev/null; exit" SIGINT SIGTERM

# Wait indefinitely
wait
