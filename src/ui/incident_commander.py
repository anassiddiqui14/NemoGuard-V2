import streamlit as st
import requests
import pandas as pd
import json
import time
from datetime import datetime

API_URL = "http://127.0.0.1:8001/api/v1"

st.set_page_config(
    page_title="NemoGuard — Agentic Pipeline Incident Commander",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Premium Enterprise CSS ──────────────────────────────────────────────
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
<style>
    /* ─── Global Reset ─── */
    *, *::before, *::after { box-sizing: border-box; }
    .stApp {
        background: linear-gradient(135deg, #F0F4F8 0%, #E8EDF5 50%, #F0F4F8 100%);
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #1A202C;
    }
    .main .block-container { 
        padding-top: 1rem; 
        max-width: 100%; 
        padding-left: 2rem;
        padding-right: 2rem;
    }
    
    /* Ensure all markdown containers break words properly */
    div.stMarkdown p {
        word-wrap: break-word;
        overflow-wrap: break-word;
    }
    
    /* ─── Header Bar ─── */
    .nemo-header {
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%);
        padding: 12px 24px;
        margin: -1rem -1rem 1.5rem -1rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        border-bottom: 2px solid #3B82F6;
        box-shadow: 0 4px 20px rgba(15, 23, 42, 0.3);
    }
    .nemo-header-left {
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .nemo-logo {
        font-size: 1.3rem;
        font-weight: 800;
        background: linear-gradient(135deg, #60A5FA, #A78BFA);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
    }
    .nemo-subtitle {
        font-size: 0.8rem;
        color: #94A3B8;
        font-weight: 400;
        border-left: 1px solid #475569;
        padding-left: 12px;
    }
    .nemo-header-right {
        display: flex;
        align-items: center;
        gap: 16px;
        font-size: 0.78rem;
        color: #94A3B8;
    }
    .nemo-status-dot {
        display: inline-block;
        width: 7px; height: 7px;
        border-radius: 50%;
        background-color: #10B981;
        margin-right: 4px;
        animation: pulse-dot 2s infinite;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4); }
        50% { opacity: 0.8; box-shadow: 0 0 0 4px rgba(16, 185, 129, 0); }
    }
    
    /* ─── Situation Strip ─── */
    .situation-strip {
        display: flex;
        gap: 12px;
        margin-bottom: 1.2rem;
        padding: 0 4px;
    }
    .sit-card {
        flex: 1;
        background: white;
        border-radius: 10px;
        padding: 14px 18px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.04);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .sit-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    }
    .sit-card.critical { border-left: 4px solid #EF4444; }
    .sit-card.warning { border-left: 4px solid #F59E0B; }
    .sit-card.info { border-left: 4px solid #3B82F6; }
    .sit-card.success { border-left: 4px solid #10B981; }
    .sit-value {
        font-size: 1.8rem;
        font-weight: 800;
        line-height: 1;
        margin-bottom: 2px;
    }
    .sit-value.critical-text { color: #DC2626; }
    .sit-value.warning-text { color: #D97706; }
    .sit-value.info-text { color: #2563EB; }
    .sit-value.success-text { color: #059669; }
    .sit-label {
        font-size: 0.7rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ─── Sidebar ─── */
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
        border-right: 1px solid #E2E8F0;
    }
    div[data-testid="stSidebar"] .stMarkdown h3 {
        font-size: 0.85rem;
        font-weight: 700;
        color: #475569;
        text-transform: uppercase;
        letter-spacing: 0.8px;
        margin-bottom: 8px;
    }

    /* ─── Incident Queue Cards ─── */
    .inc-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 14px 16px;
        margin-bottom: 10px;
        cursor: pointer;
        transition: all 0.2s ease;
    }
    .inc-card:hover {
        border-color: #93C5FD;
        box-shadow: 0 2px 8px rgba(59, 130, 246, 0.12);
    }
    .inc-card.selected {
        border: 2px solid #3B82F6;
        background: linear-gradient(135deg, #EFF6FF, #F0F9FF);
        box-shadow: 0 2px 12px rgba(59, 130, 246, 0.15);
    }
    .inc-card-header {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 6px;
    }
    .inc-card-id {
        font-size: 0.75rem;
        font-weight: 700;
        color: #475569;
        font-family: 'SF Mono', 'Fira Code', monospace;
    }
    .inc-card-title {
        font-size: 0.88rem;
        font-weight: 600;
        color: #1E293B;
        line-height: 1.3;
        margin-bottom: 6px;
    }
    .inc-card-meta {
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .inc-card-status {
        font-size: 0.7rem;
        font-weight: 600;
        color: #64748B;
        background: #F1F5F9;
        padding: 2px 8px;
        border-radius: 4px;
    }
    
    /* ─── Severity Pills ─── */
    .sev-pill {
        display: inline-block;
        padding: 2px 10px;
        border-radius: 6px;
        font-weight: 700;
        font-size: 0.7rem;
        letter-spacing: 0.3px;
    }
    .sev-1 { background: linear-gradient(135deg, #FEE2E2, #FECACA); color: #991B1B; }
    .sev-2 { background: linear-gradient(135deg, #FEF3C7, #FDE68A); color: #92400E; }
    .sev-3 { background: linear-gradient(135deg, #DBEAFE, #BFDBFE); color: #1E40AF; }
    .sev-4 { background: linear-gradient(135deg, #D1FAE5, #A7F3D0); color: #065F46; }

    /* ─── Hero Card ─── */
    .hero-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 24px;
        margin-bottom: 1.2rem;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .hero-title {
        font-size: 1.35rem;
        font-weight: 700;
        color: #0F172A;
        margin: 8px 0 10px 0;
        line-height: 1.3;
    }
    .hero-summary {
        color: #475569;
        font-size: 0.92rem;
        line-height: 1.5;
        margin-bottom: 16px;
    }
    .hero-metrics {
        display: flex;
        gap: 14px;
    }
    .hero-metric {
        flex: 1;
        text-align: center;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 8px;
    }
    .hero-metric-val {
        font-size: 1.4rem;
        font-weight: 800;
        color: #1E293B;
    }
    .hero-metric-label {
        font-size: 0.68rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }

    /* ─── Lifecycle Stepper ─── */
    .stepper-container {
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0;
        margin-bottom: 20px;
        padding: 12px 20px;
        background: white;
        border-radius: 10px;
        border: 1px solid #E2E8F0;
    }
    .step-node {
        display: flex;
        flex-direction: column;
        align-items: center;
        gap: 4px;
        min-width: 70px;
    }
    .step-dot {
        width: 24px; height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.65rem;
        font-weight: 700;
        color: white;
        transition: all 0.3s;
    }
    .step-dot.done { background: linear-gradient(135deg, #10B981, #059669); }
    .step-dot.active { background: linear-gradient(135deg, #3B82F6, #2563EB); animation: pulse-step 2s infinite; }
    .step-dot.pending { background: #CBD5E1; }
    @keyframes pulse-step {
        0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
        50% { box-shadow: 0 0 0 6px rgba(59, 130, 246, 0); }
    }
    .step-label {
        font-size: 0.58rem;
        font-weight: 600;
        color: #94A3B8;
        text-transform: uppercase;
        text-align: center;
        max-width: 80px;
        line-height: 1.2;
    }
    .step-label.active { color: #2563EB; }
    .step-label.done { color: #059669; }
    .step-connector {
        width: 28px;
        height: 2px;
        margin: 0 2px;
        margin-bottom: 16px;
    }
    .step-connector.done { background: #10B981; }
    .step-connector.pending { background: #E2E8F0; }
    
    /* ─── Tabs ─── */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
        background: #F1F5F9;
        border-radius: 8px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 6px;
        font-size: 0.82rem;
        font-weight: 600;
        color: #64748B;
        background: transparent;
        padding: 0 16px;
    }
    .stTabs [aria-selected="true"] {
        background: white;
        color: #1E293B;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
    }

    /* ─── Evidence Cards ─── */
    .evidence-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
        border-left: 3px solid #3B82F6;
    }
    .evidence-card.log { border-left-color: #8B5CF6; }
    .evidence-card.alert { border-left-color: #EF4444; }
    .evidence-card.metric { border-left-color: #10B981; }
    .evidence-card.deployment { border-left-color: #F59E0B; }
    .ev-title {
        font-size: 0.85rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 4px;
    }
    .ev-source {
        font-size: 0.72rem;
        font-weight: 500;
        color: #94A3B8;
        margin-bottom: 6px;
    }
    .ev-excerpt {
        font-size: 0.82rem;
        color: #334155;
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 6px;
        padding: 8px 12px;
        font-family: 'SF Mono', 'Fira Code', monospace;
        line-height: 1.4;
    }

    /* ─── Impact Cards ─── */
    .impact-card {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .impact-card.blocked { border-left: 3px solid #EF4444; }
    .impact-card.at-risk { border-left: 3px solid #F59E0B; }
    .impact-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
    }
    .impact-badge.blocked { background: #FEE2E2; color: #991B1B; }
    .impact-badge.at-risk { background: #FEF3C7; color: #92400E; }

    /* ─── Action Panel ─── */
    .action-panel {
        background: white;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 1px 4px rgba(0,0,0,0.05);
    }
    .action-panel-title {
        font-size: 0.95rem;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 10px;
    }
    .action-step {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        padding: 10px 0;
        border-bottom: 1px solid #F1F5F9;
    }
    .action-step:last-child { border-bottom: none; }
    .action-step-icon {
        width: 24px; height: 24px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.7rem;
        flex-shrink: 0;
        margin-top: 2px;
    }
    .action-step-icon.pending { background: #F1F5F9; color: #94A3B8; }
    .action-step-icon.done { background: #D1FAE5; color: #059669; }
    .action-step-text {
        font-size: 0.83rem;
        color: #334155;
        font-weight: 500;
    }
    .risk-badge {
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.7rem;
        font-weight: 700;
    }
    .risk-low { background: #D1FAE5; color: #065F46; }
    .risk-medium { background: #FEF3C7; color: #92400E; }
    .risk-high { background: #FEE2E2; color: #991B1B; }

    /* ─── Hypothesis Card ─── */
    .hypothesis-card {
        background: linear-gradient(135deg, #F0FDF4, #ECFDF5);
        border: 1px solid #BBF7D0;
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 12px;
    }
    .hyp-confidence {
        font-size: 1.8rem;
        font-weight: 800;
        color: #059669;
        line-height: 1;
    }
    .hyp-statement {
        font-size: 0.92rem;
        color: #1E293B;
        font-weight: 500;
        line-height: 1.5;
    }
    .hyp-cause-type {
        display: inline-block;
        background: #D1FAE5;
        color: #065F46;
        padding: 2px 10px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 700;
    }

    /* ─── Agent Timeline ─── */
    .agent-event {
        display: flex;
        gap: 12px;
        padding: 10px 0;
        border-bottom: 1px solid #F1F5F9;
    }
    .agent-event:last-child { border-bottom: none; }
    .agent-avatar {
        width: 32px; height: 32px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 0.8rem;
        flex-shrink: 0;
    }
    .agent-avatar.commander { background: linear-gradient(135deg, #3B82F6, #2563EB); color: white; }
    .agent-avatar.rca { background: linear-gradient(135deg, #8B5CF6, #7C3AED); color: white; }
    .agent-avatar.impact { background: linear-gradient(135deg, #F59E0B, #D97706); color: white; }
    .agent-avatar.policy { background: linear-gradient(135deg, #10B981, #059669); color: white; }
    .agent-avatar.executor { background: linear-gradient(135deg, #EC4899, #DB2777); color: white; }
    .agent-avatar.verifier { background: linear-gradient(135deg, #06B6D4, #0891B2); color: white; }
    .agent-avatar.correlator { background: linear-gradient(135deg, #F97316, #EA580C); color: white; }
    .agent-event-actor {
        font-size: 0.78rem;
        font-weight: 700;
        color: #1E293B;
    }
    .agent-event-summary {
        font-size: 0.82rem;
        color: #475569;
        line-height: 1.4;
    }
    .agent-event-time {
        font-size: 0.68rem;
        color: #94A3B8;
        margin-top: 2px;
    }
    
    /* ─── Button Overrides ─── */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #3B82F6, #2563EB) !important;
        border: none !important;
        border-radius: 8px !important;
        font-weight: 600 !important;
        letter-spacing: 0.3px !important;
        transition: all 0.2s !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(37, 99, 235, 0.3) !important;
    }
    
    /* ─── Triage Animation ─── */
    .triage-animation {
        text-align: center;
        padding: 40px;
        background: linear-gradient(135deg, #EFF6FF, #F0F9FF);
        border-radius: 12px;
        border: 1px dashed #93C5FD;
    }
    .triage-animation h3 {
        color: #1E293B;
        margin-bottom: 8px;
    }
    .triage-animation p {
        color: #64748B;
        font-size: 0.9rem;
    }
    
    /* ─── Scrollbar ─── */
    ::-webkit-scrollbar { width: 6px; }
    ::-webkit-scrollbar-track { background: #F1F5F9; }
    ::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #94A3B8; }
</style>
""", unsafe_allow_html=True)

# ── State Management ────────────────────────────────────────────────────
if 'selected_incident_id' not in st.session_state:
    st.session_state.selected_incident_id = None
if 'triage_running' not in st.session_state:
    st.session_state.triage_running = False

def safe_api_get(path, default=None):
    try:
        r = requests.get(f"{API_URL}{path}", timeout=5)
        data = r.json()
        if isinstance(data, dict) and "detail" in data:
            return default if default is not None else []
        return data
    except Exception:
        return default if default is not None else []

def safe_api_post(path, json_data=None):
    try:
        r = requests.post(f"{API_URL}{path}", json=json_data, timeout=300)
        return r.json()
    except Exception as e:
        return {"error": str(e)}

def get_sev_class(sev):
    sev_map = {"SEV_1": "sev-1", "SEV-1": "sev-1", "SEV_2": "sev-2", "SEV-2": "sev-2", 
               "SEV_3": "sev-3", "SEV-3": "sev-3", "SEV_4": "sev-4", "SEV-4": "sev-4"}
    return sev_map.get(str(sev), "sev-3")

def get_agent_class(actor_id):
    actor_id = str(actor_id).lower()
    if "commander" in actor_id: return "commander"
    if "rca" in actor_id: return "rca"
    if "impact" in actor_id: return "impact"
    if "policy" in actor_id: return "policy"
    if "execut" in actor_id: return "executor"
    if "verif" in actor_id: return "verifier"
    if "correlat" in actor_id: return "correlator"
    return "commander"

def get_agent_icon(actor_id):
    actor_id = str(actor_id).lower()
    if "commander" in actor_id: return "🎖️"
    if "rca" in actor_id: return "🔍"
    if "impact" in actor_id: return "💥"
    if "policy" in actor_id: return "🛡️"
    if "execut" in actor_id: return "⚡"
    if "verif" in actor_id: return "✅"
    if "correlat" in actor_id: return "🔗"
    return "🤖"

# ── Header ──────────────────────────────────────────────────────────────
try:
    status = safe_api_get("/status", {})
    st.markdown(f"""
    <div class="nemo-header">
        <div class="nemo-header-left">
            <div class="nemo-logo">🛡️ NemoGuard</div>
            <div class="nemo-subtitle">Agentic Pipeline Incident Commander</div>
        </div>
        <div class="nemo-header-right">
            <span>{str(status.get('environment', 'dev')).upper()}</span>
            <span>NVIDIA NIM</span>
            <span>Nemotron-4-340B</span>
            <span><span class="nemo-status-dot"></span> All Systems Operational</span>
        </div>
    </div>
    """, unsafe_allow_html=True)
except Exception:
    st.error("⚠️ Backend not reachable. Make sure FastAPI is running on port 8001.")
    st.stop()

# ── Situation Strip ─────────────────────────────────────────────────────
ov = safe_api_get("/overview", {})
st.markdown(f"""
<div class="situation-strip">
    <div class="sit-card critical">
        <div class="sit-value critical-text">{ov.get('open_incidents', 0)}</div>
        <div class="sit-label">Open Incidents</div>
    </div>
    <div class="sit-card warning">
        <div class="sit-value warning-text">{ov.get('critical_incidents', 0)}</div>
        <div class="sit-label">Critical (SEV-1)</div>
    </div>
    <div class="sit-card info">
        <div class="sit-value info-text">{ov.get('alerts_correlated_today', 0)}</div>
        <div class="sit-label">Alerts Correlated</div>
    </div>
    <div class="sit-card warning">
        <div class="sit-value warning-text">{ov.get('jobs_currently_affected', 0)}</div>
        <div class="sit-label">Jobs Affected</div>
    </div>
    <div class="sit-card success">
        <div class="sit-value success-text">{ov.get('data_products_at_risk', 0)}</div>
        <div class="sit-label">Products at Risk</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Sidebar: Scenario Lab ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🧪 Scenario Lab")
    st.caption("Simulate real pipeline incidents to demonstrate NemoGuard's autonomous AI capabilities.")
    
    st.markdown("---")
    
    if st.button("🚀 Run Full Demo", type="primary", use_container_width=True, help="Injects alerts, correlates them, and creates an incident"):
        with st.spinner("Injecting scenario and correlating alerts..."):
            result = safe_api_post("/demo/run-scenario")
            if result and "incident_id" in result:
                st.session_state.selected_incident_id = result["incident_id"]
                st.success(f"✅ Created **{result['incident_id']}**")
                time.sleep(0.5)
                st.rerun()
            else:
                st.error(f"Failed: {result}")
    
    if st.button("🔄 Reset Environment", use_container_width=True, help="Regenerates the entire demo database from scratch"):
        with st.spinner("Resetting..."):
            safe_api_post("/demo/reset")
            st.session_state.selected_incident_id = None
            st.rerun()
    
    st.markdown("---")
    st.markdown("### 📊 System Overview")
    c1, c2 = st.columns(2)
    c1.metric("Incidents", ov.get("open_incidents", 0))
    c2.metric("Critical", ov.get("critical_incidents", 0))
    c3, c4 = st.columns(2)
    c3.metric("Jobs Hit", ov.get("jobs_currently_affected", 0))
    c4.metric("At Risk", ov.get("data_products_at_risk", 0))

# ── Main 2-Pane Layout ─────────────────────────────────────────────────
col_queue, col_workspace = st.columns([2.5, 9.5])

# ── Pane 1: Incident Queue ─────────────────────────────────────────────
with col_queue:
    st.markdown("#### 📥 Incident Queue")
    incidents = safe_api_get("/incidents?state=all", [])
    
    if not isinstance(incidents, list):
        incidents = []
    
    if not incidents:
        st.markdown("""
        <div style="text-align: center; padding: 30px 10px; color: #94A3B8;">
            <div style="font-size: 2rem; margin-bottom: 8px;">📭</div>
            <div style="font-size: 0.85rem; font-weight: 500;">No incidents</div>
            <div style="font-size: 0.78rem;">Click <b>Run Full Demo</b> in the sidebar to get started</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        if st.session_state.selected_incident_id is None:
            st.session_state.selected_incident_id = incidents[0].get('incident_id')
        
        for inc in incidents:
            inc_id = inc.get('incident_id', '')
            is_sel = st.session_state.selected_incident_id == inc_id
            sel_cls = "selected" if is_sel else ""
            sev_cls = get_sev_class(inc.get('severity', ''))
            
            st.markdown(f"""
            <div class="inc-card {sel_cls}">
                <div class="inc-card-header">
                    <span class="inc-card-id">{inc_id}</span>
                    <span class="sev-pill {sev_cls}">{inc.get('severity', 'N/A')}</span>
                </div>
                <div class="inc-card-title">{inc.get('title', 'Unknown Incident')}</div>
                <div class="inc-card-meta">
                    <span class="inc-card-status">{inc.get('status', 'UNKNOWN')}</span>
                </div>
            </div>
            """, unsafe_allow_html=True)
            if st.button("Select", key=f"sel_{inc_id}", use_container_width=True):
                st.session_state.selected_incident_id = inc_id
                st.rerun()

# ── Pane 2 & 3: Workspace & Action Panel ───────────────────────────────
if st.session_state.selected_incident_id and incidents:
    inc_id = st.session_state.selected_incident_id
    incident = safe_api_get(f"/incidents/{inc_id}", {})
    
    if not incident or "detail" in incident:
        with col_workspace:
            st.warning("Incident not found. Select another from the queue.")
    else:
        # ── Pane 2: Workspace ───────────────────────────────────────────
        with col_workspace:
            # Hero Card
            sev_cls = get_sev_class(incident.get('severity', ''))
            corr_conf = incident.get('correlation_confidence')
            corr_display = f"{corr_conf:.0%}" if isinstance(corr_conf, (int, float)) else "—"
            rca_conf = incident.get('rca_confidence')
            rca_display = f"{rca_conf:.0%}" if isinstance(rca_conf, (int, float)) else "—"
            
            st.markdown(f"""
            <div class="hero-card">
                <div>
                    <span class="sev-pill {sev_cls}">{incident.get('severity', 'N/A')}</span>
                    <span style="color: #94A3B8; font-size: 0.8rem; margin-left: 8px; font-family: monospace;">{inc_id}</span>
                </div>
                <div class="hero-title">{incident.get('title', 'Unknown')}</div>
                <div class="hero-summary">{incident.get('summary') or incident.get('actual_root_cause') or 'Awaiting AI triage analysis...'}</div>
                <div class="hero-metrics">
                    <div class="hero-metric">
                        <div class="hero-metric-val">{corr_display}</div>
                        <div class="hero-metric-label">Correlation</div>
                    </div>
                    <div class="hero-metric">
                        <div class="hero-metric-val">{rca_display}</div>
                        <div class="hero-metric-label">RCA Confidence</div>
                    </div>
                    <div class="hero-metric">
                        <div class="hero-metric-val">{incident.get('status', '—')}</div>
                        <div class="hero-metric-label">State</div>
                    </div>
                </div>
            </div>
            """, unsafe_allow_html=True)
            
            # Lifecycle Stepper
            states = ["DETECTED", "CORRELATING", "INVESTIGATING", "PLAN_READY", "EXECUTING", "VERIFYING", "RESOLVED"]
            state_labels = ["Detected", "Correlating", "Investigating", "Plan Ready", "Executing", "Verifying", "Resolved"]
            try:
                curr_idx = states.index(incident.get('status', 'DETECTED'))
            except ValueError:
                curr_idx = 0
            
            stepper_html = '<div class="stepper-container">'
            for i, (s, label) in enumerate(zip(states, state_labels)):
                if i < curr_idx:
                    dot_cls, label_cls = "done", "done"
                    dot_content = "✓"
                elif i == curr_idx:
                    dot_cls, label_cls = "active", "active"
                    dot_content = str(i + 1)
                else:
                    dot_cls, label_cls = "pending", ""
                    dot_content = str(i + 1)
                
                stepper_html += f'<div class="step-node"><div class="step-dot {dot_cls}">{dot_content}</div><div class="step-label {label_cls}">{label}</div></div>'
                if i < len(states) - 1:
                    conn_cls = "done" if i < curr_idx else "pending"
                    stepper_html += f'<div class="step-connector {conn_cls}"></div>'
            stepper_html += '</div>'
            st.markdown(stepper_html, unsafe_allow_html=True)
            
            # Tabs
            tab_overview, tab_evidence, tab_impact, tab_activity, tab_alerts = st.tabs([
                "📋 Overview", "🔬 Evidence", "💥 Impact", "🤖 Agent Activity", "📥 Raw Alerts"
            ])
            
            with tab_overview:
                hypotheses = safe_api_get(f"/incidents/{inc_id}/hypotheses", [])
                if hypotheses:
                    st.markdown("#### 🎯 Root Cause Analysis")
                    for h in hypotheses:
                        conf = h.get('confidence', 0)
                        statement = h.get('statement', '')
                        cause_type = h.get('cause_type', 'UNKNOWN')
                        st.markdown(f"""
                        <div class="hypothesis-card">
                            <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 8px;">
                                <div class="hyp-confidence">{conf*100:.0f}%</div>
                                <div>
                                    <div class="hyp-statement">{statement}</div>
                                    <div style="margin-top: 4px;"><span class="hyp-cause-type">{cause_type}</span></div>
                                </div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    # Show triage button
                    current_status = incident.get('status', '')
                    if current_status in ['DETECTED', 'CORRELATING']:
                        st.markdown("""
                        <div class="triage-animation">
                            <h3>🧠 AI Triage Available</h3>
                            <p>NemoGuard's autonomous agents will analyze alerts, logs, and deployment history to identify the root cause and generate a recovery plan.</p>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button("🧠 Initiate Autonomous AI Triage", type="primary", use_container_width=True):
                            swarm_placeholder = st.empty()
                            
                            # Enterprise-Grade SVG/CSS Swarm Visualization
                            swarm_html = """
                            <style>
                                .enterprise-swarm {{
                                    background: #0f172a;
                                    border-radius: 12px;
                                    padding: 40px 20px;
                                    color: white;
                                    font-family: 'Inter', sans-serif;
                                    text-align: center;
                                    box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
                                    margin-bottom: 20px;
                                    position: relative;
                                    overflow: hidden;
                                }}
                                .swarm-title {{
                                    font-size: 1.2rem;
                                    font-weight: 600;
                                    margin-bottom: 30px;
                                    color: #38bdf8;
                                }}
                                .svg-container {{
                                    position: relative;
                                    width: 100%;
                                    height: 150px;
                                    margin: 0 auto;
                                    max-width: 600px;
                                }}
                                .agent-node {{
                                    position: absolute;
                                    width: 60px;
                                    height: 60px;
                                    background: #1e293b;
                                    border: 2px solid #334155;
                                    border-radius: 50%;
                                    display: flex;
                                    align-items: center;
                                    justify-content: center;
                                    font-size: 1.5rem;
                                    z-index: 10;
                                    box-shadow: 0 0 15px rgba(0,0,0,0.5);
                                    transition: all 0.3s ease;
                                }}
                                .node-context {{ top: 45px; left: 0%; }}
                                .node-rca {{ top: 0px; left: 33%; }}
                                .node-impact {{ top: 90px; left: 66%; }}
                                .node-commander {{ top: 45px; left: 100%; transform: translateX(-100%); }}

                                .agent-label {{
                                    position: absolute;
                                    top: 70px;
                                    left: 50%;
                                    transform: translateX(-50%);
                                    font-size: 0.7rem;
                                    color: #94a3b8;
                                    white-space: nowrap;
                                }}
                                .node-commander .agent-label {{ top: -20px; }}

                                .active-node {{
                                    border-color: #38bdf8;
                                    box-shadow: 0 0 20px rgba(56, 189, 248, 0.6);
                                }}
                                .done-node {{
                                    border-color: #10b981;
                                    box-shadow: 0 0 15px rgba(16, 185, 129, 0.3);
                                }}
                                .connection-paths {{
                                    position: absolute;
                                    top: 0;
                                    left: 0;
                                    width: 100%;
                                    height: 100%;
                                    z-index: 1;
                                }}
                                .path-line {{
                                    fill: none;
                                    stroke: #334155;
                                    stroke-width: 2;
                                }}
                                .packet {{
                                    fill: #38bdf8;
                                    filter: drop-shadow(0 0 4px #38bdf8);
                                    opacity: 0;
                                }}

                                {packet_animations}
                            </style>
                            <div class="enterprise-swarm">
                                <div class="swarm-title">{status_text}</div>
                                <div class="svg-container">
                                    <svg class="connection-paths" viewBox="0 0 600 150">
                                        <!-- Paths -->
                                        <path id="path1" class="path-line" d="M 30,75 L 200,30" />
                                        <path id="path2" class="path-line" d="M 200,30 L 400,120" />
                                        <path id="path3" class="path-line" d="M 400,120 L 570,75" />
                                        <!-- Packets -->
                                        {packet_elements}
                                    </svg>
                                    <div class="agent-node node-context {n1_cls}"><div class="agent-icon">📡</div><div class="agent-label">Context Agent</div></div>
                                    <div class="agent-node node-rca {n2_cls}"><div class="agent-icon">🕵️</div><div class="agent-label">RCA Agent</div></div>
                                    <div class="agent-node node-impact {n3_cls}"><div class="agent-label">Impact Agent</div><div class="agent-icon">🌐</div></div>
                                    <div class="agent-node node-commander {n4_cls}"><div class="agent-label">Commander</div><div class="agent-icon">👨‍✈️</div></div>
                                </div>
                            </div>
                            """

                            def render_swarm(phase):
                                p_anim = ""
                                p_elem = ""
                                n1 = "done-node" if phase > 1 else ("active-node" if phase == 1 else "")
                                n2 = "done-node" if phase > 2 else ("active-node" if phase == 2 else "")
                                n3 = "done-node" if phase > 3 else ("active-node" if phase == 3 else "")
                                n4 = "done-node" if phase > 4 else ("active-node" if phase == 4 else "")
                                
                                if phase == 1:
                                    status = "Gathering context from Data Plane..."
                                    p_anim = """
                                        @keyframes fly1 { 0% {offset-distance: 0%; opacity: 1;} 100% {offset-distance: 100%; opacity: 1;} }
                                        .pkt1 { offset-path: path('M 30,75 L 200,30'); animation: fly1 1s infinite linear; }
                                    """
                                    p_elem = '<circle class="packet pkt1" r="4" cx="0" cy="0" />'
                                elif phase == 2:
                                    status = "Analyzing root cause across services..."
                                    p_anim = """
                                        @keyframes fly2 { 0% {offset-distance: 0%; opacity: 1;} 100% {offset-distance: 100%; opacity: 1;} }
                                        .pkt2 { offset-path: path('M 200,30 L 400,120'); animation: fly2 1.2s infinite linear; }
                                    """
                                    p_elem = '<circle class="packet pkt2" r="4" cx="0" cy="0" />'
                                elif phase == 3:
                                    status = "Evaluating downstream business impact..."
                                    p_anim = """
                                        @keyframes fly3 { 0% {offset-distance: 0%; opacity: 1;} 100% {offset-distance: 100%; opacity: 1;} }
                                        .pkt3 { offset-path: path('M 400,120 L 570,75'); animation: fly3 1s infinite linear; }
                                    """
                                    p_elem = '<circle class="packet pkt3" r="4" cx="0" cy="0" />'
                                else:
                                    status = "Commander finalizing JSON recovery plan..."
                                    p_anim = ""
                                    p_elem = ""
                                    
                                final_html = swarm_html.format(
                                    status_text=status, packet_animations=p_anim, packet_elements=p_elem,
                                    n1_cls=n1, n2_cls=n2, n3_cls=n3, n4_cls=n4
                                ).replace('\n', '')
                                swarm_placeholder.markdown(final_html, unsafe_allow_html=True)
                            
                            render_swarm(1)
                            time.sleep(1.0)
                            render_swarm(2)
                            time.sleep(2.0)
                            render_swarm(3)
                            time.sleep(1.5)
                            render_swarm(4)
                            
                            result = safe_api_post(f"/incidents/{inc_id}/triage")
                            if result and result.get("status") == "EXECUTING_CLI":
                                st.success("NemoClaw CLI Agent spawned in background! Connecting to terminal...")
                                terminal_placeholder = st.empty()
                                
                                # Poll for completion
                                while True:
                                    # Fetch live logs
                                    log_res = safe_api_get(f"/incidents/{inc_id}/agent-logs")
                                    if log_res and "logs" in log_res:
                                        terminal_placeholder.code(log_res["logs"], language="bash")
                                    
                                    # Check if status has moved to PLAN_READY
                                    status_res = safe_api_get(f"/incidents/{inc_id}")
                                    if status_res and status_res.get("status") in ["PLAN_READY", "EXECUTING"]:
                                        break
                                    time.sleep(1)
                                
                                st.success("✅ AI triage complete! Evidence gathered, hypothesis formed, recovery plan generated.")
                                time.sleep(0.5)
                                st.rerun()
                            else:
                                err = result.get("error", str(result)) if result else "Unknown Error"
                                st.error(f"Triage failed: {err}")
                    elif current_status == 'INVESTIGATING':
                        st.info("🔄 AI investigation in progress...")
                    else:
                        st.info("No hypotheses generated for this incident yet.")

                # Show root cause if available
                if incident.get('actual_root_cause'):
                    st.markdown("#### 📝 Root Cause Statement")
                    st.markdown(f"> {incident['actual_root_cause']}")
            
            with tab_evidence:
                evidence = safe_api_get(f"/incidents/{inc_id}/evidence", [])
                if evidence:
                    st.markdown(f"#### 🔬 Evidence Collected ({len(evidence)} items)")
                    for ev in evidence:
                        ev_type = str(ev.get('evidence_type', 'Log')).lower()
                        ev_cls = ev_type if ev_type in ['log', 'alert', 'metric', 'deployment'] else 'log'
                        type_icon = {"log": "📝", "alert": "🚨", "metric": "📊", "deployment": "🚀"}.get(ev_cls, "📄")
                        st.markdown(f"""
                        <div class="evidence-card {ev_cls}">
                            <div class="ev-title">{type_icon} {ev.get('title', 'Evidence')}</div>
                            <div class="ev-source">{ev.get('evidence_type', 'Unknown')} · {ev.get('source_system', 'Unknown')}</div>
                            <div class="ev-excerpt">{ev.get('excerpt', '')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No evidence collected yet. Run AI Triage to begin evidence gathering.")
            
            with tab_impact:
                impact = safe_api_get(f"/incidents/{inc_id}/impact", [])
                if impact:
                    st.markdown(f"#### 💥 Business Impact Analysis ({len(impact)} affected assets)")
                    for imp in impact:
                        status_val = str(imp.get('impact_status', 'AT_RISK'))
                        badge_cls = "blocked" if "BLOCK" in status_val.upper() else "at-risk"
                        score = imp.get('impact_score', 0)
                        st.markdown(f"""
                        <div class="impact-card {badge_cls}">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                                <span style="font-weight: 700; font-size: 0.88rem; color: #1E293B;">{imp.get('asset_id', 'Unknown')}</span>
                                <span class="impact-badge {badge_cls}">{status_val}</span>
                            </div>
                            <div style="font-size: 0.82rem; color: #475569; margin-bottom: 6px;">{imp.get('reason', '')}</div>
                            <div style="font-size: 0.72rem; color: #94A3B8;">Impact Type: {imp.get('impact_type', 'Unknown')} · Score: {score}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("Impact analysis pending. Run AI Triage to assess downstream effects.")
            
            with tab_activity:
                events = safe_api_get(f"/incidents/{inc_id}/events", [])
                if events:
                    st.markdown(f"#### 🤖 Agent Activity Timeline ({len(events)} events)")
                    for ev in events:
                        actor = ev.get('actor_id', 'System')
                        agent_cls = get_agent_class(actor)
                        agent_icon = get_agent_icon(actor)
                        ts = str(ev.get('created_at', ''))[:19]
                        st.markdown(f"""
                        <div class="agent-event">
                            <div class="agent-avatar {agent_cls}">{agent_icon}</div>
                            <div style="flex: 1;">
                                <div class="agent-event-actor">{actor}</div>
                                <div class="agent-event-summary">{ev.get('event_summary', '')}</div>
                                <div class="agent-event-time">{ts}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No agent activity recorded yet.")
            
            with tab_alerts:
                alerts = safe_api_get(f"/incidents/{inc_id}/alerts", [])
                if alerts:
                    st.markdown(f"#### 📥 Correlated Alerts ({len(alerts)})")
                    for a in alerts:
                        sev = str(a.get('severity', 'info')).lower()
                        sev_color = {"critical": "#EF4444", "high": "#F59E0B", "warning": "#3B82F6", "info": "#94A3B8"}.get(sev, "#94A3B8")
                        st.markdown(f"""
                        <div style="background: white; border: 1px solid #E2E8F0; border-left: 3px solid {sev_color}; border-radius: 8px; padding: 12px 14px; margin-bottom: 8px;">
                            <div style="display: flex; justify-content: space-between; margin-bottom: 4px;">
                                <span style="font-family: monospace; font-size: 0.78rem; font-weight: 600; color: #475569;">{a.get('alert_id', '')}</span>
                                <span style="font-size: 0.72rem; font-weight: 700; color: {sev_color}; text-transform: uppercase;">{sev}</span>
                            </div>
                            <div style="font-size: 0.85rem; color: #1E293B; font-weight: 500;">{a.get('message', '')}</div>
                            <div style="font-size: 0.72rem; color: #94A3B8; margin-top: 4px;">{a.get('source_system', '')} · {a.get('alert_type', '')}</div>
                        </div>
                        """, unsafe_allow_html=True)
                else:
                    st.info("No alerts linked to this incident.")
        
        # ── Recovery Plan (Integrated into Workspace) ────────────────────
        plans = safe_api_get(f"/incidents/{inc_id}/plans", [])
        if plans:
            plan = plans[0]
            risk = str(plan.get('overall_risk', 'MEDIUM'))
            risk_cls = f"risk-{risk.lower()}"
            
            st.markdown("---")
            st.markdown("### ⚙️ Recovery Plan & Execution")
            
            p_col1, p_col2 = st.columns([1, 1])
            with p_col1:
                st.markdown(f"""
                <div class="action-panel" style="margin-bottom:0; height: 100%;">
                    <div style="font-size: 0.95rem; color: #475569; margin-bottom: 12px; line-height: 1.6;">{plan.get('rationale', '')}</div>
                    <div style="margin-bottom: 12px;">
                        <span class="risk-badge {risk_cls}">Risk: {risk}</span>
                    </div>
                    <div style="font-size: 0.9rem; color: #1E293B; font-weight: 600; margin-bottom: 8px;">Expected Outcome</div>
                    <div style="font-size: 0.9rem; color: #475569; padding: 12px; background: #F8FAFC; border-radius: 6px;">{plan.get('expected_outcome', '')}</div>
                </div>
                """, unsafe_allow_html=True)
                
            with p_col2:
                st.markdown("""<div class="action-panel" style="margin-bottom:0; height: 100%;">
                    <div style="font-size: 0.9rem; color: #1E293B; font-weight: 600; margin-bottom: 12px;">Execution Steps</div>
                """, unsafe_allow_html=True)
                for step in plan.get('steps', []):
                    is_done = step.get('status', '') == 'SUCCEEDED'
                    icon_cls = "done" if is_done else "pending"
                    icon = "✓" if is_done else "→"
                    step_risk = str(step.get('risk_level', 'LOW'))
                    step_risk_cls = f"risk-{step_risk.lower()}"
                    
                    # If step action contains markdown code blocks, render it cleanly
                    step_action = step.get('action_type', '')
                    
                    st.markdown(f"""
                    <div class="action-step" style="background: #F8FAFC; padding: 12px; border-radius: 8px; margin-bottom: 10px; border: 1px solid #E2E8F0;">
                        <div style="display: flex; gap: 12px;">
                            <div class="action-step-icon {icon_cls}" style="margin-top: 2px;">{icon}</div>
                            <div style="flex: 1;">
                                <div style="font-family: monospace; font-size: 0.85rem; color: #334155; white-space: pre-wrap; word-break: break-all;">{step_action}</div>
                                <div style="margin-top: 8px;"><span class="risk-badge {step_risk_cls}">{step_risk}</span></div>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)
                st.markdown("</div>", unsafe_allow_html=True)
            
            st.markdown("<br>", unsafe_allow_html=True)
            
            current_status = incident.get('status', '')
            if current_status in ["PLAN_READY", "AWAITING_APPROVAL"]:
                st.warning("⚠️ **Human Approval Required** — The Policy Engine classified this plan as medium/high risk.")
                
                c_btn1, c_btn2, _ = st.columns([2, 2, 6])
                with c_btn1:
                    if st.button("✅ Approve & Execute", type="primary", use_container_width=True):
                        with st.spinner("Recording approval and executing..."):
                            safe_api_post(f"/incidents/{inc_id}/plans/{plan['action_plan_id']}/approve",
                                         {"decision": "APPROVED", "plan_hash": "sha256_demo"})
                            safe_api_post(f"/incidents/{inc_id}/plans/{plan['action_plan_id']}/execute")
                        st.rerun()
                with c_btn2:
                    if st.button("❌ Reject & Re-plan", use_container_width=True):
                        st.session_state[f'feedback_mode_{inc_id}'] = True
                        st.rerun()
                        
                if st.session_state.get(f'feedback_mode_{inc_id}', False):
                    st.markdown("### 💬 Feedback Agent")
                    feedback_text = st.text_area("Why was this plan rejected? Provide guidance for the LLM:", 
                                                 placeholder="E.g., Don't use bash scripts, use the official REST API. Ensure data is backed up first.")
                    if st.button("Send to Feedback Agent 🧠", type="primary"):
                        with st.spinner("Feedback Agent is regenerating the recovery plan..."):
                            res = safe_api_post(f"/incidents/{inc_id}/feedback", {"feedback": feedback_text})
                            if res and res.get("status") == "success":
                                st.session_state[f'feedback_mode_{inc_id}'] = False
                                st.success("Plan updated successfully!")
                                time.sleep(1)
                                st.rerun()
                            else:
                                st.error(f"Failed to update plan: {res.get('error')}")

            elif current_status == "EXECUTING":
                st.info("⚙️ Plan is currently executing...")
                if st.button("⚡ Force Run Executor", type="primary"):
                    safe_api_post(f"/incidents/{inc_id}/plans/{plan['action_plan_id']}/execute")
                    st.rerun()
            elif current_status in ["VERIFYING", "RESOLVED"]:
                st.success("🎉 **Incident Resolved** — All recovery steps executed successfully.")
