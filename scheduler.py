"""
scheduler.py
-------------
CP-SAT (Google OR-Tools) formulation of the block-planning problem for
a single railway section over one operating day (0-1440 minutes).

Decision variables
-------------------
- For each pending maintenance job: an OPTIONAL interval variable on the
  section's single shared "track possession" resource, plus a boolean
  `is_scheduled` literal.
- For each running train: an interval variable that is fixed in
  duration but may be *delayed* by up to `max_train_delay` minutes, to
  allow the solver to make small, bounded timetable adjustments if that
  is what it takes to fit a highly urgent job in (this is what turns the
  "minimize train delay" requirement into a real soft constraint rather
  than a fixed no-go zone).

Constraints
-----------
- Hard: every train interval and every *scheduled* job interval on a
  section must be mutually non-overlapping (AddNoOverlap) -- i.e. no
  maintenance block clashes with a running train, and no two
  maintenance jobs clash with each other on the same section.
- Hard: each train may only be delayed within [0, max_train_delay].
- Soft: minimize total train delay (weighted penalty in the objective).

Objective
---------
    maximize   urgency_weight * sum(urgency_i * is_scheduled_i)
             - delay_penalty  * sum(train_delay_j)

Output
------
A results DataFrame with one row per job (scheduled or not) including
the chosen start/end time and a human-readable explanation of the
decision (urgency vs. the timetable gap that was used), suitable for
direct display in the Streamlit dashboard.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from ortools.sat.python import cp_model

DAY_MINUTES = 24 * 60


@dataclass
class SectionSolveResult:
    section_id: str
    status: str
    objective_value: float
    total_urgency_scheduled: float
    total_train_delay_min: int
    jobs_result: pd.DataFrame
    trains_result: pd.DataFrame


def _fmt_time(minute: int) -> str:
    minute = int(minute) % DAY_MINUTES
    return f"{minute // 60:02d}:{minute % 60:02d}"


def solve_section(
    section_id: str,
    jobs_df: pd.DataFrame,
    trains_df: pd.DataFrame,
    horizon_minutes: int = DAY_MINUTES,
    max_train_delay: int = 15,
    delay_penalty_per_min: float = 3.0,
    urgency_weight: float = 1.0,
    time_limit_seconds: float = 10.0,
) -> SectionSolveResult:
    """Solve the block-scheduling problem for one section.

    Parameters
    ----------
    jobs_df: pending jobs for this section. Must have columns
        job_id, estimated_duration_min, predicted_urgency_score
        (falls back to a synthetic urgency if not present).
    trains_df: running trains for this section. Must have columns
        train_id, train_no, dep_min, arr_min.
    """
    jobs_df = jobs_df.reset_index(drop=True)
    trains_df = trains_df.reset_index(drop=True)

    model = cp_model.CpModel()

    # ---- Train (flexible-start, fixed-duration) intervals ----
    train_delay_vars = []
    train_start_vars = []
    train_intervals = []
    for _, tr in trains_df.iterrows():
        duration = int(tr["arr_min"] - tr["dep_min"])
        delay = model.NewIntVar(0, max_train_delay, f"delay_{tr['train_id']}")
        start = model.NewIntVar(0, horizon_minutes, f"start_{tr['train_id']}")
        model.Add(start == int(tr["dep_min"]) + delay)
        end = model.NewIntVar(0, horizon_minutes + max_train_delay, f"end_{tr['train_id']}")
        model.Add(end == start + duration)
        interval = model.NewIntervalVar(start, duration, end, f"ival_{tr['train_id']}")
        train_delay_vars.append(delay)
        train_start_vars.append(start)
        train_intervals.append(interval)

    # ---- Job (optional, fixed-duration, free-start) intervals ----
    urgency_col = "predicted_urgency_score" if "predicted_urgency_score" in jobs_df.columns else None
    job_presence = []
    job_start_vars = []
    job_intervals = []
    for _, job in jobs_df.iterrows():
        duration = int(job["estimated_duration_min"])
        presence = model.NewBoolVar(f"present_{job['job_id']}")
        start = model.NewIntVar(0, horizon_minutes, f"jstart_{job['job_id']}")
        end = model.NewIntVar(0, horizon_minutes, f"jend_{job['job_id']}")
        model.Add(end == start + duration)
        model.Add(end <= horizon_minutes).OnlyEnforceIf(presence)
        interval = model.NewOptionalIntervalVar(start, duration, end, presence, f"jival_{job['job_id']}")
        job_presence.append(presence)
        job_start_vars.append(start)
        job_intervals.append(interval)

    # ---- Hard constraint: no overlaps on the shared section resource ----
    model.AddNoOverlap(train_intervals + job_intervals)

    # ---- Objective ----
    urgencies = [
        float(jobs_df.iloc[i][urgency_col]) if urgency_col else 50.0 for i in range(len(jobs_df))
    ]
    # scale to integers for CP-SAT (x100 keeps 2 decimal precision)
    urgency_terms = [
        int(round(urgencies[i] * urgency_weight * 100)) * job_presence[i] for i in range(len(job_presence))
    ]
    delay_terms = [int(round(delay_penalty_per_min * 100)) * d for d in train_delay_vars]

    model.Maximize(cp_model.LinearExpr.Sum(urgency_terms) - cp_model.LinearExpr.Sum(delay_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_seconds
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    jobs_result_rows = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for i, job in jobs_df.iterrows():
            scheduled = bool(solver.Value(job_presence[i]))
            start = solver.Value(job_start_vars[i]) if scheduled else None
            duration = int(job["estimated_duration_min"])
            reason = _explain_job(job, trains_df, urgencies[i], scheduled, start, duration, max_train_delay)
            jobs_result_rows.append(
                {
                    "job_id": job["job_id"],
                    "section_id": section_id,
                    "asset_id": job.get("asset_id"),
                    "job_type": job.get("job_type"),
                    "urgency_score": urgencies[i],
                    "scheduled": scheduled,
                    "start_min": start,
                    "end_min": (start + duration) if scheduled else None,
                    "start_time": _fmt_time(start) if scheduled else None,
                    "end_time": _fmt_time(start + duration) if scheduled else None,
                    "duration_min": duration,
                    "reason": reason,
                }
            )
        trains_result_rows = []
        for i, tr in trains_df.iterrows():
            delay = solver.Value(train_delay_vars[i])
            new_start = solver.Value(train_start_vars[i])
            duration = int(tr["arr_min"] - tr["dep_min"])
            trains_result_rows.append(
                {
                    "train_id": tr["train_id"],
                    "train_no": tr["train_no"],
                    "section_id": section_id,
                    "train_type": tr.get("train_type"),
                    "original_dep_min": int(tr["dep_min"]),
                    "new_dep_min": int(new_start),
                    "new_arr_min": int(new_start) + duration,
                    "delay_min": int(delay),
                    "original_dep_time": _fmt_time(tr["dep_min"]),
                    "new_dep_time": _fmt_time(new_start),
                }
            )
        total_urgency_scheduled = sum(
            r["urgency_score"] for r in jobs_result_rows if r["scheduled"]
        )
        total_delay = sum(r["delay_min"] for r in trains_result_rows)
        objective_value = solver.ObjectiveValue() / 100.0
    else:
        trains_result_rows = []
        total_urgency_scheduled = 0.0
        total_delay = 0
        objective_value = 0.0

    return SectionSolveResult(
        section_id=section_id,
        status=status_name,
        objective_value=objective_value,
        total_urgency_scheduled=total_urgency_scheduled,
        total_train_delay_min=total_delay,
        jobs_result=pd.DataFrame(jobs_result_rows),
        trains_result=pd.DataFrame(trains_result_rows),
    )


def _explain_job(job, trains_df, urgency, scheduled, start, duration, max_train_delay) -> str:
    """Build a plain-English explanation of why the solver did (or did
    not) schedule this job, referencing the timetable gap it used."""
    label = job.get("job_type", "Maintenance")
    if not scheduled:
        return (
            f"{label} NOT scheduled — no timetable gap large enough for the "
            f"{duration}-min block was found within the {max_train_delay}-min max "
            f"allowed train delay, or lower-urgency vs. competing jobs on this section "
            f"(urgency {urgency:.1f}/100)."
        )
    end = start + duration
    before = trains_df[trains_df["arr_min"] <= start].sort_values("arr_min").tail(1)
    after = trains_df[trains_df["dep_min"] >= end].sort_values("dep_min").head(1)
    before_txt = f"train {before.iloc[0]['train_no']} arriving {_fmt_time(before.iloc[0]['arr_min'])}" if len(before) else "start of day"
    after_txt = f"train {after.iloc[0]['train_no']} departing {_fmt_time(after.iloc[0]['dep_min'])}" if len(after) else "end of day"
    return (
        f"{label} scheduled {_fmt_time(start)}-{_fmt_time(end)} in the gap between "
        f"{before_txt} and {after_txt} (urgency {urgency:.1f}/100 justified the block)."
    )


def solve_all_sections(
    jobs_df: pd.DataFrame,
    trains_df: pd.DataFrame,
    section_ids: list[str] | None = None,
    **solver_kwargs,
) -> list[SectionSolveResult]:
    """Run `solve_section` independently for every section (or a filtered
    subset), enabling scalable section-by-section execution."""
    if section_ids is None:
        section_ids = sorted(set(jobs_df["section_id"]) | set(trains_df["section_id"]))
    results = []
    for sid in section_ids:
        sec_jobs = jobs_df[jobs_df["section_id"] == sid]
        sec_trains = trains_df[trains_df["section_id"] == sid]
        if sec_jobs.empty and sec_trains.empty:
            continue
        results.append(solve_section(sid, sec_jobs, sec_trains, **solver_kwargs))
    return results


if __name__ == "__main__":
    import os
    from data_generator import DATA_DIR
    from urgency_model import load_model, predict_urgency, MODEL_PATH

    jobs = pd.read_csv(os.path.join(DATA_DIR, "jobs.csv"))
    trains = pd.read_csv(os.path.join(DATA_DIR, "trains.csv"))

    if os.path.exists(MODEL_PATH):
        model = load_model()
        jobs = predict_urgency(model, jobs)
    else:
        jobs["predicted_urgency_score"] = 50.0

    results = solve_all_sections(jobs, trains)
    for r in results:
        print(f"\n=== {r.section_id} [{r.status}] ===")
        print(f"Urgency scheduled: {r.total_urgency_scheduled:.1f} | Train delay: {r.total_train_delay_min} min")
        print(r.jobs_result[["job_id", "scheduled", "start_time", "end_time", "reason"]].to_string(index=False))
