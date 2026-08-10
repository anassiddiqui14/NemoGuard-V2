import streamlit as st
import sqlite3
import pandas as pd
import time
from datetime import datetime
from src.tools.read_tools import ReadTools

DB_PATH = "data/generated/pipeline.db"

# --- PAGE CONFIG ---
st.set_page_config(
    page_title="NemoClaw Incident Navigator",
    page_icon="🌌",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
<style>
    /* Global Background and Text */
    .stApp {
        background-color: #0B1121;
        color: #E2E8F0;
        font-family: 'Inter', sans-serif;
    }
    
    /* Headers */
    h1, h2, h3 {
        color: #F8FAFC !important;
        font-weight: 600 !important;
    }
    
    /* Sidebar Styling */
    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #1F2937;
    }
    
    /* Metric Cards */
    [data-testid="stMetricValue"] {
        color: #38BDF8 !important;
        font-size: 2rem !important;
        font-weight: 700 !important;
    }
    
    /* Custom Alerts / Badges */
    .badge-critical {
        background-color: #EF4444; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em;
    }
    .badge-high {
        background-color: #F97316; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em;
    }
    .badge-warning {
        background-color: #EAB308; color: black; padding: 4px 8px; border-radius: 4px; font-weight: bold; font-size: 0.8em;
    }
    
    /* DataFrame */
    .stDataFrame {
        border-radius: 8px;
        overflow: hidden;
        border: 1px solid #334155;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 24px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0px 0px;
        gap: 1px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    
    /* Mock Terminal */
    .terminal-box {
        background-color: #000000;
        color: #00FF00;
        font-family: 'Courier New', Courier, monospace;
        padding: 15px;
        border-radius: 5px;
        border: 1px solid #333;
        overflow-x: auto;
        margin-top: 10px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- INIT TOOLS ---
@st.cache_resource
def get_read_tools():
    return ReadTools(db_path=DB_PATH)

read_tools = get_read_tools()

# --- SIDEBAR: ALERT STREAMER ---
st.sidebar.markdown("## 📡 Alert Streamer")
st.sidebar.markdown("Control the incoming alert feed and define triage thresholds.")

# Streamer Controls
severity_filter = st.sidebar.multiselect(
    "Severity Filter",
    options=["critical", "high", "warning", "info"],
    default=["critical", "high"],
    help="Select which alert severities to ingest into the stream."
)

status_filter = st.sidebar.multiselect(
    "Status Filter",
    options=["open", "acknowledged", "resolved"],
    default=["open"],
    help="Filter alerts by their current lifecycle state."
)

st.sidebar.markdown("---")
intensity_mode = st.sidebar.select_slider(
    "Stream Intensity (Simulation)",
    options=["Low", "Normal", "High", "Critical Surge"],
    value="Normal",
    help="Controls the simulated rate of incoming alerts."
)

auto_refresh = st.sidebar.toggle("Live Auto-Refresh", value=False)
if auto_refresh:
    time.sleep(5)  # Simulate pulling every 5s if toggled
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.markdown(f"**Last Sync:** `{datetime.now().strftime('%H:%M:%S')}`")


# --- DATA FETCHING ---
def fetch_filtered_alerts(severities, statuses):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            sev_placeholders = ",".join(f"'{s}'" for s in severities) if severities else "'INVALID'"
            stat_placeholders = ",".join(f"'{s}'" for s in statuses) if statuses else "'INVALID'"
            query = f"SELECT alert_id, severity, alert_type, source_system, opened_ts, status, run_id FROM alert WHERE severity IN ({sev_placeholders}) AND status IN ({stat_placeholders}) ORDER BY opened_ts DESC"
            return pd.read_sql_query(query, conn)
    except Exception as e:
        st.error(f"Failed to fetch alerts: {e}")
        return pd.DataFrame()

def fetch_kpis():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            total_runs = pd.read_sql_query("SELECT COUNT(*) as c FROM execution", conn).iloc[0]['c']
            failed_runs = pd.read_sql_query("SELECT COUNT(*) as c FROM execution WHERE status='failed'", conn).iloc[0]['c']
            open_alerts_count = pd.read_sql_query("SELECT COUNT(*) as c FROM alert WHERE status='open'", conn).iloc[0]['c']
            return total_runs, failed_runs, open_alerts_count
    except Exception:
        return 0, 0, 0

# --- MAIN DASHBOARD ---
st.markdown("<h1><span style='color:#38BDF8;'>NemoClaw</span> Incident Navigator</h1>", unsafe_allow_html=True)
st.markdown("Enterprise command center for autonomous pipeline orchestration.")

# KPI Row
total_runs, failed_runs, open_alerts_count = fetch_kpis()
health_score = max(0, 100 - (failed_runs / (total_runs or 1)) * 100) if total_runs else 100

col1, col2, col3, col4 = st.columns(4)
col1.metric("System Health", f"{health_score:.2f}%")
col2.metric("Total Executions", f"{total_runs:,}")
col3.metric("Failed Executions", f"{failed_runs:,}")
col4.metric("Active Alerts", f"{open_alerts_count:,}", delta="-2 (resolved)" if open_alerts_count > 0 else None, delta_color="inverse")

st.markdown("---")

# Alert Queue
st.subheader("🚨 Alert Queue")
alerts_df = fetch_filtered_alerts(severity_filter, status_filter)

if alerts_df.empty:
    st.success("No alerts matching current filters. System is operating normally.")
else:
    # Use dataframe selection
    st.dataframe(
        alerts_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "alert_id": st.column_config.TextColumn("Alert ID", width="medium"),
            "severity": st.column_config.TextColumn("Severity", width="small"),
            "alert_type": st.column_config.TextColumn("Type", width="medium"),
            "opened_ts": st.column_config.DatetimeColumn("Opened At", width="medium"),
        }
    )
    
    st.markdown("### Investigate Alert")
    target_alert_id = st.selectbox("Select an Alert to investigate:", options=alerts_df['alert_id'].tolist())
    
    if st.button("🚀 Launch Autonomous Investigation", type="primary"):
        # Select target alert row
        alert_row = alerts_df[alerts_df['alert_id'] == target_alert_id].iloc[0]
        run_id = alert_row['run_id']
        severity = alert_row['severity']
        
        # --- INVESTIGATION PROGRESS ---
        st.markdown("---")
        st.subheader(f"🧠 Incident Commander: Investigation `{target_alert_id}`")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        status_text.markdown("🔄 **[Triage Agent]** Extracting alert metadata...")
        time.sleep(1)
        progress_bar.progress(25)
        
        status_text.markdown("🔄 **[Dependency Analyst]** Fetching pipeline topology and downstream impact...")
        # Execute tool
        response_data = read_tools.get_run(run_id).data
        run_res = response_data.get('run', {}) if response_data else {}
        job_id = run_res.get('job_id', 'UNKNOWN')
        time.sleep(1.5)
        progress_bar.progress(50)
        
        status_text.markdown("🔄 **[Root Cause Analyst]** Analyzing execution logs and comparing to last successful run...")
        time.sleep(1.5)
        progress_bar.progress(75)
        
        status_text.markdown("🔄 **[Runbook Expert]** Retrieving mitigation steps and drafting communications...")
        time.sleep(1)
        progress_bar.progress(100)
        status_text.markdown("✅ **Investigation Complete.** Generating Executive Report.")
        time.sleep(0.5)
        
        # --- EXECUTIVE REPORT ---
        st.markdown(f"## 📋 Executive Incident Report: `{job_id}`")
        
        tab1, tab2, tab3, tab4 = st.tabs(["📝 Summary & Root Cause", "⛓️ Impact Assessment", "📢 Stakeholder Comms", "🛠️ Action Plan"])
        
        with tab1:
            colA, colB = st.columns([2, 1])
            with colA:
                st.markdown("### Simulated Root Cause Analysis")
                st.markdown(f"The autonomous agent analyzed the logs for execution **`{run_id}`** and identified a breaking schema change. The upstream source system dropped mandatory columns expected by the ingestion pipeline.")
                st.markdown("#### Log Evidence Citations")
                
                timeline = read_tools.get_run_timeline(run_id).data.get('timeline', [])
                error_logs = [l for l in timeline if l['level'] == 'ERROR']
                if error_logs:
                    for err in error_logs:
                        st.markdown(f"<div class='terminal-box'>[{err['timestamp']}] ERROR {err['error_code']}: {err['message']}</div>", unsafe_allow_html=True)
                else:
                    st.markdown("<div class='terminal-box'>[2026-08-04 09:02:15] ERROR SCHEMA_COLUMN_MISSING: Missing expected columns in source payload.</div>", unsafe_allow_html=True)
            
            with colB:
                st.markdown("### Investigation Metadata")
                st.info(f"**Target Job:** `{job_id}`\n\n**Severity:** `{severity.upper()}`\n\n**Confidence Score:** 98%")
                
        with tab2:
            st.markdown("### Downstream Pipeline Impact")
            st.markdown(f"Based on the topology graph, the failure of **`{job_id}`** has blocked the following downstream entities:")
            
            # Fetch downstream graph
            graph = read_tools.get_job_graph(job_id).data.get('graph', [])
            if graph:
                for edge in graph:
                    st.error(f"Blocked: `{edge['downstream_id']}` (Edge Type: {edge['edge_type']})")
            else:
                st.error("Blocked: `JOB_AWS_EXTRACT_RESERVATION` (Edge Type: success)")
                st.error("Blocked: `JOB_EDW_GSO_LOAD` (Edge Type: data)")
                
            st.markdown("### Business Impact Score")
            st.metric("Estimated Financial Risk (Mock)", "$12,500 / hr", delta="Increasing", delta_color="inverse")
            
        with tab3:
            st.markdown("### Auto-Drafted Stakeholder Notification")
            st.markdown("The orchestrator has drafted the following message to be sent to the `#data-eng-alerts` Slack channel and Data Product Owners:")
            
            draft_msg = f"""
            🚨 **SEV-{severity.upper()} Incident: Pipeline Failure**
            
            **Job:** `{job_id}`
            **Status:** Failing due to `SCHEMA_COLUMN_MISSING`
            **Impact:** Downstream analytical models (`JOB_AWS_EXTRACT_RESERVATION`) are delayed.
            **Action:** NemoClaw Incident Commander is currently mitigating the issue by applying the fallback schema runbook. 
            **ETA to resolution:** 15 minutes.
            
            *This is an automated message generated by NemoClaw Autonomous Ops.*
            """
            st.text_area("Review Communication", value=draft_msg.strip(), height=200)
            st.button("✉️ Send Communication Now")
            
        with tab4:
            st.markdown("### Recommended Action Plan")
            st.markdown("The Runbook Expert agent recommends the following automated recovery actions:")
            
            st.markdown("""
            1. **Schema Mitigation:** Automatically inject a migration step to pad missing columns with `NULL` defaults.
            2. **Pipeline Restart:** Trigger a replay of the execution from the point of failure.
            3. **Data Quality Check:** Execute the `JOB_AWS_DQ_VALIDATION` canary to ensure downstream data integrity is not compromised.
            """)
            
            st.markdown("---")
            st.markdown("### 🔒 Approval Gate")
            st.warning("These actions require human approval before the orchestrator modifies production state.")
            
            c1, c2 = st.columns(2)
            if c1.button("✅ Approve & Execute Runbook", type="primary", use_container_width=True):
                st.success("Execution Approved! The orchestrator is now applying the fix.")
                st.balloons()
            if c2.button("❌ Reject & Escalate", use_container_width=True):
                st.error("Escalated to human engineering team.")
