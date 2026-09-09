"""
app.py
-------
Streamlit dashboard tying together the data pipeline, the ML urgency
scorer, and the CP-SAT block-scheduling optimizer for the AI-Powered
Automatic Block Planning prototype (SIH26027).

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import datetime as dt

import pandas as pd
import plotly.express as px
import streamlit as st

from data_generator import generate_all
from urgency_model import FEATURE_COLS, explain_urgency, predict_urgency, train_urgency_model
from scheduler import SectionSolveResult, solve_all_sections

st.set_page_config(page_title="AI Block Planning — SIH26027", layout="wide")

BASE_DATE = dt.date(2026, 9, 8)  # arbitrary anchor date used to render Gantt timelines


def to_datetime(minute: int) -> dt.datetime:
    return dt.datetime.combine(BASE_DATE, dt.time(0, 0)) + dt.timedelta(minutes=int(minute))


# --------------------------------------------------------------------------
# Cached data / model loading
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Generating synthetic railway data...")
def load_data(num_sections: int, seed: int) -> dict[str, pd.DataFrame]:
    return generate_all(num_sections=num_sections, seed=seed)


@st.cache_resource(show_spinner="Training urgency model...")
def get_trained_model(historical_df: pd.DataFrame):
    pipeline, metrics, fi = train_urgency_model(historical_df)
    return pipeline, metrics, fi


# --------------------------------------------------------------------------
# Sidebar controls
# --------------------------------------------------------------------------
st.sidebar.title("⚙️ Controls")

num_sections = st.sidebar.slider("Number of sections to simulate", 2, 8, 6)
seed = st.sidebar.number_input("Random seed (data)", value=42, step=1)

if st.sidebar.button("🔄 Regenerate data"):
    st.cache_data.clear()

data = load_data(num_sections, seed)
sections_df, trains_df, assets_df, jobs_df, historical_df = (
    data["sections"],
    data["trains"],
    data["assets"],
    data["jobs"],
    data["historical"],
)
used_real_trains = data.get("used_real_trains", False)

model, metrics, feature_importance = get_trained_model(historical_df)
jobs_scored = predict_urgency(model, jobs_df)
jobs_scored["reason_ml"] = jobs_scored.apply(explain_urgency, axis=1)

st.sidebar.markdown("---")
st.sidebar.subheader("Solver parameters")
max_train_delay = st.sidebar.slider("Max allowed train delay (min)", 0, 60, 15)
delay_penalty = st.sidebar.slider("Delay penalty (per minute)", 0.0, 10.0, 3.0, 0.5)
urgency_weight = st.sidebar.slider("Urgency weight in objective", 0.1, 3.0, 1.0, 0.1)

st.sidebar.markdown("---")
section_options = sections_df["section_id"] + " — " + sections_df["section_name"]
section_map = dict(zip(section_options, sections_df["section_id"]))
selected_labels = st.sidebar.multiselect(
    "Sections to solve (section-by-section execution)",
    options=list(section_options),
    default=list(section_options),
)
selected_sections = [section_map[l] for l in selected_labels]

run_clicked = st.sidebar.button("▶️ Run Solver on Selected Sections", type="primary")

# --------------------------------------------------------------------------
# Header
# --------------------------------------------------------------------------
st.title("🚆 AI-Powered Automatic Block Planning")
st.caption(
    "SIH26027 prototype — ML urgency scoring (XGBoost) + CP-SAT optimization (OR-Tools) "
    "for scheduling maintenance blocks against live train timetables."
)
if used_real_trains:
    st.success(
        "🟢 Using REAL Indian Railways train numbers, station names, and scheduled times "
        "(source: data.gov.in Indian Railways Train Time Table). Only asset condition/maintenance "
        "data below is synthetic — no public dataset exists for that.",
        icon="✅",
    )
else:
    st.warning(
        "⚠️ Real timetable dataset not found — falling back to fully synthetic trains/sections. "
        "Run `python real_data_loader.py` once to download it.",
        icon="⚠️",
    )

tab_overview, tab_assets, tab_schedule, tab_explain = st.tabs(
    ["📊 Overview", "🛠️ Asset Health & Urgency", "🗓️ Schedule (Gantt)", "🔍 Explainability"]
)

# --------------------------------------------------------------------------
# Run solver (persisted in session_state so tab switches don't re-solve)
# --------------------------------------------------------------------------
if run_clicked:
    with st.spinner("Solving block schedule with CP-SAT..."):
        results: list[SectionSolveResult] = solve_all_sections(
            jobs_scored,
            trains_df,
            section_ids=selected_sections,
            max_train_delay=max_train_delay,
            delay_penalty_per_min=delay_penalty,
            urgency_weight=urgency_weight,
        )
    st.session_state["results"] = results
    st.session_state["solved_sections"] = selected_sections

results: list[SectionSolveResult] | None = st.session_state.get("results")

# --------------------------------------------------------------------------
# Overview tab
# --------------------------------------------------------------------------
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Sections", len(sections_df))
    c2.metric("Trains scheduled today", len(trains_df))
    c3.metric("Pending maintenance jobs", len(jobs_scored))
    c4.metric("ML model", metrics["backend"], f"MAE {metrics['mae']} · R² {metrics['r2']}")

    st.markdown("### Solver results summary")
    if results:
        total_jobs = sum(len(r.jobs_result) for r in results)
        total_scheduled = sum(int(r.jobs_result["scheduled"].sum()) for r in results if not r.jobs_result.empty)
        total_urgency_reduced = sum(r.total_urgency_scheduled for r in results)
        total_delay = sum(r.total_train_delay_min for r in results)

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Maintenance slots filled", f"{total_scheduled}/{total_jobs}")
        m2.metric("Total asset risk reduced", f"{total_urgency_reduced:.0f} urgency pts")
        m3.metric("Estimated train delay impact", f"{total_delay} min")
        m4.metric("Sections solved", len(results))

        summary_rows = [
            {
                "Section": r.section_id,
                "Status": r.status,
                "Jobs scheduled": int(r.jobs_result["scheduled"].sum()) if not r.jobs_result.empty else 0,
                "Jobs total": len(r.jobs_result),
                "Urgency scheduled": round(r.total_urgency_scheduled, 1),
                "Train delay (min)": r.total_train_delay_min,
                "Objective": round(r.objective_value, 1),
            }
            for r in results
        ]
        st.dataframe(pd.DataFrame(summary_rows), use_container_width=True, hide_index=True)
    else:
        st.info("Configure parameters in the sidebar and click **Run Solver on Selected Sections** to see results.")

# --------------------------------------------------------------------------
# Asset health & urgency tab
# --------------------------------------------------------------------------
with tab_assets:
    st.markdown("### Pending maintenance jobs ranked by ML-predicted urgency")
    display_cols = [
        "urgency_rank",
        "job_id",
        "section_id",
        "job_type",
        "predicted_urgency_score",
        "current_condition_score",
        "last_maintained_days_ago",
        "past_failures",
        "asset_age_years",
        "traffic_load_trains_per_day",
        "estimated_duration_min",
    ]
    st.dataframe(jobs_scored[display_cols], use_container_width=True, hide_index=True)

    col_a, col_b = st.columns(2)
    with col_a:
        top_n = jobs_scored.sort_values("predicted_urgency_score", ascending=False).head(15)
        fig = px.bar(
            top_n.sort_values("predicted_urgency_score"),
            x="predicted_urgency_score",
            y="job_id",
            color="section_id",
            orientation="h",
            title="Top 15 most urgent pending jobs",
            labels={"predicted_urgency_score": "Predicted urgency (0-100)", "job_id": "Job"},
        )
        st.plotly_chart(fig, use_container_width=True)
    with col_b:
        fig2 = px.bar(
            feature_importance,
            x="importance",
            y="feature",
            orientation="h",
            title="What drives the urgency model?",
        )
        st.plotly_chart(fig2, use_container_width=True)

    st.markdown("### Asset health register")
    st.dataframe(assets_df, use_container_width=True, hide_index=True)

# --------------------------------------------------------------------------
# Schedule / Gantt tab
# --------------------------------------------------------------------------
with tab_schedule:
    if not results:
        st.info("Run the solver from the sidebar to view the schedule.")
    else:
        section_filter = st.selectbox(
            "Filter Gantt chart by section",
            options=["All solved sections"] + [r.section_id for r in results],
        )

        gantt_rows = []
        for r in results:
            if section_filter != "All solved sections" and r.section_id != section_filter:
                continue
            for _, tr in r.trains_result.iterrows():
                gantt_rows.append(
                    {
                        "Section": r.section_id,
                        "Resource": f"{r.section_id}",
                        "Task": f"Train {tr['train_no']}",
                        "Start": to_datetime(tr["new_dep_min"]),
                        "Finish": to_datetime(tr["new_arr_min"]),
                        "Type": "Train" + (" (delayed)" if tr["delay_min"] > 0 else ""),
                        "Detail": f"{tr['train_type']} — orig {tr['original_dep_time']}, new {tr['new_dep_time']} (+{tr['delay_min']}m)",
                    }
                )
            for _, job in r.jobs_result[r.jobs_result["scheduled"]].iterrows():
                gantt_rows.append(
                    {
                        "Section": r.section_id,
                        "Resource": f"{r.section_id}",
                        "Task": f"Block: {job['job_id']}",
                        "Start": to_datetime(job["start_min"]),
                        "Finish": to_datetime(job["end_min"]),
                        "Type": "Maintenance Block",
                        "Detail": job["reason"],
                    }
                )

        if gantt_rows:
            gantt_df = pd.DataFrame(gantt_rows)
            fig = px.timeline(
                gantt_df,
                x_start="Start",
                x_end="Finish",
                y="Resource" if section_filter == "All solved sections" else "Task",
                color="Type",
                hover_data=["Detail"],
                title="Train timetable vs. scheduled maintenance blocks",
                color_discrete_map={
                    "Train": "#4C78A8",
                    "Train (delayed)": "#E45756",
                    "Maintenance Block": "#F2A900",
                },
            )
            fig.update_yaxes(autorange="reversed")
            fig.update_layout(height=max(400, 20 * len(gantt_df["Task"].unique()) if section_filter != "All solved sections" else 400))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No trains/jobs to display for this selection.")

        st.markdown("#### Train delay impact")
        for r in results:
            if section_filter != "All solved sections" and r.section_id != section_filter:
                continue
            delayed = r.trains_result[r.trains_result["delay_min"] > 0]
            if not delayed.empty:
                st.write(f"**{r.section_id}**")
                st.dataframe(
                    delayed[["train_no", "train_type", "original_dep_time", "new_dep_time", "delay_min"]],
                    use_container_width=True,
                    hide_index=True,
                )

# --------------------------------------------------------------------------
# Explainability tab
# --------------------------------------------------------------------------
with tab_explain:
    if not results:
        st.info("Run the solver from the sidebar to view explanations.")
    else:
        for r in results:
            with st.expander(f"Section {r.section_id} — {r.status} — objective {r.objective_value:.1f}", expanded=False):
                if r.jobs_result.empty:
                    st.write("No pending jobs on this section.")
                    continue
                for _, row in r.jobs_result.sort_values("scheduled", ascending=False).iterrows():
                    icon = "✅" if row["scheduled"] else "❌"
                    st.markdown(f"{icon} **{row['job_id']}** ({row['job_type']}) — {row['reason']}")
