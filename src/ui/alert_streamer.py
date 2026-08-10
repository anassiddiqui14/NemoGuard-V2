import streamlit as st
import sqlite3
import pandas as pd
import time
from datetime import datetime

DB_PATH = "data/generated/pipeline.db"

st.set_page_config(page_title="Alert Streamer Simulator", page_icon="📡", layout="wide")

st.title("📡 Alert Streamer Control Panel")
st.markdown("Use this panel to simulate incoming alert traffic and manage raw data injection.")

# --- SIDEBAR CONTROLS ---
st.sidebar.header("Stream Controls")
auto_refresh = st.sidebar.toggle("Enable Live Auto-Refresh", value=False)
intensity = st.sidebar.select_slider(
    "Injection Rate",
    options=["Paused", "1 / min", "5 / min", "Surge"]
)

# --- DB HELPERS ---
def fetch_alerts():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            return pd.read_sql_query("SELECT alert_id, severity, alert_type, opened_ts, status, run_id FROM alert ORDER BY opened_ts DESC", conn)
    except Exception as e:
        st.error(f"Failed to fetch alerts: {e}")
        return pd.DataFrame()

def reset_all_alerts():
    try:
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("UPDATE alert SET status = 'open'")
            conn.commit()
        st.success("All alerts reset to OPEN.")
    except Exception as e:
        st.error(f"Failed to reset: {e}")

st.markdown("### Raw Alert Feed")
alerts_df = fetch_alerts()

if alerts_df.empty:
    st.info("No alerts found in the database.")
else:
    st.dataframe(alerts_df, use_container_width=True)

st.markdown("### Manual Override")
c1, c2 = st.columns(2)
with c1:
    if st.button("🔄 Reset All Alerts to 'OPEN'"):
        reset_all_alerts()
        time.sleep(1)
        st.rerun()

with c2:
    st.info("Use the streamer controls to simulate pipeline degradation and monitor how the Incident Commander reacts in real-time.")

if auto_refresh:
    time.sleep(5)
    st.rerun()
