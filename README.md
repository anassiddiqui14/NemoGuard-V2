# NemoGuard Pipeline Copilot

NemoGuard Pipeline Copilot is an AI-driven, real-time Incident Commander platform powered by NemoClaw agents. It monitors complex data pipelines, triages anomalies across schemas, data quality, and compute layers, and automatically generates actionable recovery plans using autonomous AI agents.

## Project Structure

- `frontend/` - React frontend built with Vite, TailwindCSS, and Lucide Icons. Features real-time SSE event streaming for agent activity and a fully responsive enterprise-grade dashboard.
- `src/` - Backend Python application (FastAPI).
  - `src/api/` - REST API endpoints and SSE endpoints.
  - `src/domain/` - Orchestrator and agent definitions using LLM APIs to drive the NemoClaw agents.
- `data/` - SQLite databases including the generated incident demo database.
- `scripts/` - Assorted helper scripts for scenario injection and configuration.

## Setup & Installation

### 1. Backend (FastAPI + Python)

Ensure you have Python 3.9+ installed.

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Or manually install core dependencies if requirements.txt is missing
pip install fastapi uvicorn pyyaml pandas pyarrow duckdb mcp pydantic openai
```

### 2. Frontend (React + Vite)

Ensure you have Node.js 18+ installed.

```bash
cd frontend
npm install
```

## Running the Application

You need to run both the backend and frontend servers simultaneously.

**Start the Backend Server (Terminal 1):**
```bash
# From the project root, with your venv activated:
python3 -m uvicorn src.api.main:app --reload --port 8000
```
*Note: The backend runs on `http://localhost:8000`.*

**Start the Frontend Server (Terminal 2):**
```bash
cd frontend
npm run dev
```
*Note: The frontend typically runs on `http://localhost:5173`. The Vite config is set up to proxy `/api` requests automatically to `http://localhost:8000`.*

## Features

- **Live Agent Operations Console**: View real-time autonomous reasoning and execution traces via SSE.
- **Dynamic Causal Chain**: Visualizes the downstream impact of an alert leading to a root cause hypothesis.
- **Scenario Lab**: Generate fully synthetic, highly realistic pipeline incidents (Schema Regressions, Compute Crashes, DQ Anomalies) to test the agent platform.
- **Business Impact Dashboards**: See real-time blast radius analysis (Data Products affected, SLAs at risk).
- **Interactive Action Plans**: Review, edit, approve, or provide textual feedback on LLM-generated incident recovery runbooks.

## License

Confidential and Proprietary. All rights reserved.
