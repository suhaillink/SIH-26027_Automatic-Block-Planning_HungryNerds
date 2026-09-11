"""
Streamlit dashboard for the Railway Block Planning prototype.
Talks to the FastAPI backend running at API_BASE.

Run with: streamlit run app.py
(Make sure the backend is running first: uvicorn main:app --reload, from /backend)
"""
import streamlit as st
import requests

API_BASE = "http://127.0.0.1:8000"

st.set_page_config(page_title="Railway Block Planning", layout="wide", initial_sidebar_state="collapsed")

# ---------------------------------------------------------------------------
# Styling - restrained, light, card-based. No default Streamlit chrome look.
# ---------------------------------------------------------------------------
st.markdown("""
<style>
    #MainMenu, footer, header {visibility: hidden;}
    .block-container {padding-top: 2rem; padding-bottom: 3rem; max-width: 1150px;}

    html, body, [class*="css"] { font-family: 'Segoe UI', Helvetica, Arial, sans-serif; }

    .app-title {
        font-size: 1.65rem; font-weight: 700; color: #1F3864; margin-bottom: 0.15rem;
    }
    .app-subtitle {
        font-size: 0.92rem; color: #6B7280; margin-bottom: 1.6rem;
    }

    .section-label {
        font-size: 0.78rem; font-weight: 600; letter-spacing: 0.04em;
        color: #6B7280; text-transform: uppercase; margin: 1.6rem 0 0.6rem 0;
    }

    .card {
        background: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 8px;
        padding: 1rem 1.2rem; margin-bottom: 0.6rem;
    }
    .metric-card {
        background: #F5F6F8; border: 1px solid #E5E7EB; border-radius: 8px;
        padding: 0.9rem 1.1rem; text-align: center;
    }
    .metric-value { font-size: 1.5rem; font-weight: 700; color: #1F3864; }
    .metric-label { font-size: 0.78rem; color: #6B7280; margin-top: 0.15rem; }

    .status-pill {
        display: inline-block; padding: 0.15rem 0.6rem; border-radius: 999px;
        font-size: 0.75rem; font-weight: 600;
    }
    .pill-high { background: #FDE8E8; color: #B42318; }
    .pill-medium { background: #FEF3C7; color: #92660A; }
    .pill-low { background: #E6F4EA; color: #1E7B34; }

    .alert-row {
        border-left: 3px solid #B42318; background: #FDF7F7; border-radius: 4px;
        padding: 0.55rem 0.9rem; margin-bottom: 0.5rem; font-size: 0.88rem;
    }
    .alert-row.hold {
        border-left-color: #92660A; background: #FFFBEB;
    }
    .alert-tag {
        font-weight: 700; font-size: 0.72rem; text-transform: uppercase;
        letter-spacing: 0.03em; margin-right: 0.4rem;
    }

    div.stButton > button {
        border-radius: 6px; border: 1px solid #D1D5DB; font-weight: 500;
        padding: 0.45rem 1rem;
    }
    div.stButton > button:hover { border-color: #1F3864; color: #1F3864; }

    div[data-testid="stDataFrame"] { border: 1px solid #E5E7EB; border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


def api_get(path):
    try:
        r = requests.get(f"{API_BASE}{path}", timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Could not reach backend at {API_BASE}{path} - is uvicorn running? ({e})")
        return None


def api_post(path):
    try:
        r = requests.post(f"{API_BASE}{path}", timeout=10)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Could not reach backend at {API_BASE}{path} - is uvicorn running? ({e})")
        return None


# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown('<div class="app-title">Railway Maintenance Block Planning</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Section SEC-14 &nbsp;&bull;&nbsp; Combines Track / Signal / OHE '
    'maintenance requests and reacts to live train movement</div>',
    unsafe_allow_html=True,
)

col1, col2, col3 = st.columns(3)
with col1:
    reset_clicked = st.button("Reset scenario", use_container_width=True)
with col2:
    optimize_clicked = st.button("Run optimizer", use_container_width=True, type="primary")
with col3:
    check_clicked = st.button("Check live conflicts", use_container_width=True)

if reset_clicked:
    api_post("/api/reset")
    st.session_state.pop("last_optimize", None)
    st.rerun()
if optimize_clicked:
    result = api_post("/api/optimize")
    if result:
        st.session_state["last_optimize"] = result
    st.rerun()
if check_clicked:
    result = api_post("/api/check-conflicts")
    if result is not None:
        st.session_state["last_alerts"] = result
    st.rerun()

# ---------------------------------------------------------------------------
# Headline metrics
# ---------------------------------------------------------------------------
if "last_optimize" in st.session_state:
    r = st.session_state["last_optimize"]
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{r["task_count_before"]}</div>'
                    f'<div class="metric-label">Separate requests</div></div>', unsafe_allow_html=True)
    with m2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{r["block_count_after"]}</div>'
                    f'<div class="metric-label">Combined block</div></div>', unsafe_allow_html=True)
    with m3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{r["reduction_pct"]}%</div>'
                    f'<div class="metric-label">Fewer blocks</div></div>', unsafe_allow_html=True)
    with m4:
        window = f'{r["start_time"][11:16]}-{r["end_time"][11:16]}'
        st.markdown(f'<div class="metric-card"><div class="metric-value">{window}</div>'
                    f'<div class="metric-label">Block window</div></div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Maintenance Tasks</div>', unsafe_allow_html=True)
tasks = api_get("/api/tasks")
if tasks:
    rows = sorted(tasks, key=lambda x: -x["priority_score"])
    st.dataframe(
        [
            {
                "Department": t["department"].capitalize(),
                "Defect": t["defect_desc"],
                "Severity": t["severity"].capitalize(),
                "Overdue (days)": t["overdue_days"],
                "Duration (min)": t["est_duration_min"],
                "Priority score": t["priority_score"],
                "In block": "Yes" if t["block_id"] else "-",
            }
            for t in rows
        ],
        use_container_width=True, hide_index=True,
    )
else:
    st.caption("No tasks loaded. Click Reset scenario to begin.")

# ---------------------------------------------------------------------------
# Block + Trains side by side
# ---------------------------------------------------------------------------
left, right = st.columns([1, 1.3])

with left:
    st.markdown('<div class="section-label">Optimized Block</div>', unsafe_allow_html=True)
    blocks = api_get("/api/blocks")
    if blocks:
        for b in blocks:
            st.markdown(
                f'<div class="card"><b>{b["section"]}</b> &nbsp;-&nbsp; {b["status"].capitalize()}<br>'
                f'{b["start_time"][11:16]} - {b["end_time"][11:16]} &nbsp;'
                f'<span style="color:#6B7280;">({len(b["task_ids"])} tasks merged)</span></div>',
                unsafe_allow_html=True,
            )
    else:
        st.caption("No block yet. Click Run optimizer.")

with right:
    st.markdown('<div class="section-label">Trains in Section (simulated)</div>', unsafe_allow_html=True)
    trains = api_get("/api/trains")
    if trains:
        st.dataframe(
            [
                {
                    "Train": t["number"],
                    "Priority": t["priority"].capitalize(),
                    "Scheduled": t["scheduled_pass_time"][11:16],
                    "Actual": t["actual_pass_time"][11:16] if t["actual_pass_time"] else "-",
                    "Slack (min)": t["slack_minutes"],
                    "Status": "Late" if t["is_late"] else "On time",
                }
                for t in trains
            ],
            use_container_width=True, hide_index=True,
        )

# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------
st.markdown('<div class="section-label">Live Conflict Feed</div>', unsafe_allow_html=True)
alerts = api_get("/api/alerts")
if alerts:
    for a in alerts:
        is_pause = "paused" in a["action_taken"]
        row_cls = "alert-row" if is_pause else "alert-row hold"
        tag = "Block paused" if is_pause else "Held / rescheduled"
        st.markdown(
            f'<div class="{row_cls}"><span class="alert-tag">{tag}</span>{a["message"]}</div>',
            unsafe_allow_html=True,
        )
else:
    st.caption("No conflicts detected yet. Run the optimizer, then click Check live conflicts.")
