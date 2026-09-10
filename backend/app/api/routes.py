# STAGE 8 (backend half) — everything the React planner dashboard talks to.
# This file is intentionally "dumb": it fetches rows from the DB, calls
# the pipeline modules, and returns plain dicts/lists. All the actual
# decision-making logic lives in the stage-specific modules imported here
# — keeping that separation is what makes it possible to point at one
# file per pipeline stage when an evaluator asks "where does X happen?".

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.data_sources.corridor import SECTIONS, STATIONS
from app.data_sources.synthetic_blocks import BlockDemand, GANGS
from app.data_sources.real_timetable import RealTrainWindow, load_real_train_windows
from app.db.models import BlockDemandRow, GangRow, HistoricalBlockRow, PlanDemandRow, PlanRow, RealTrainWindowRow
from app.db.session import get_db
from app.optimizer.solver import solve_ranked_plans

router = APIRouter(prefix="/api")


# ---------------------------------------------------------------- STAGE 1
@router.get("/corridor")
def get_corridor():
    """Real corridor definition — used by the 'what is a block' page and
    any corridor map in the UI."""
    return {
        "stations": [s.__dict__ for s in STATIONS],
        "sections": [s.__dict__ for s in SECTIONS],
    }


@router.get("/data-sources")
def get_data_sources():
    """Backs the in-app 'Data Sources' panel — the honesty-to-evaluators
    requirement. Every field here should be defensible if challenged live."""
    return {
        "real": [
            {
                "name": "Indian Railways Train Time Table",
                "source": "data.gov.in (Open Government Data Platform India)",
                "url": "https://www.data.gov.in/catalog/indian-railways-train-time-table",
                "used_for": "Real train numbers/names and real station arrival & departure times on the "
                            "New Delhi -> Kanpur Central corridor. Section-occupancy windows for real trains "
                            "are DERIVED from these real timetable times (a real train's departure from one "
                            "station and arrival at the next is treated as that section being occupied in "
                            "between) — Indian Railways does not publish block-section occupancy directly.",
            },
            {
                "name": "Corridor stations & section lengths",
                "source": "Derived from the same data.gov.in timetable file (median distance-column "
                           "difference between consecutive real trains stopping at both stations)",
                "url": "https://www.data.gov.in/catalog/indian-railways-train-time-table",
                "used_for": "Real station names/codes and real approximate section lengths for the demo corridor.",
            },
        ],
        "synthetic": [
            {
                "name": "Block demand requests (Engineering / S&T / TRD / Traffic)",
                "reason_not_public": "IR's internal Block Demand Management System (BDMS) data isn't public.",
                "used_for": "The 14 demo block requests shown on the dashboard, incl. asset age, days since "
                            "last maintenance, defect severity and safety-risk flag used for priority scoring.",
            },
            {
                "name": "Maintenance gang / machine roster",
                "reason_not_public": "Internal resource-planning data, not published.",
                "used_for": "Which gang is assigned to which block request, used for the resource-availability constraint.",
            },
            {
                "name": "Historical block log",
                "reason_not_public": "Internal BDMS history, not published.",
                "used_for": "Illustrative past-blocks trend context shown on the dashboard.",
            },
        ],
    }


@router.get("/trains")
def get_trains(db: Session = Depends(get_db)):
    rows = db.query(RealTrainWindowRow).all()
    return [
        {"train_no": r.train_no, "train_name": r.train_name, "section_id": r.section_id,
         "start_min": r.start_min, "end_min": r.end_min, "data_source": r.data_source}
        for r in rows
    ]


@router.get("/historical")
def get_historical(db: Session = Depends(get_db)):
    rows = db.query(HistoricalBlockRow).all()
    return [
        {"date": r.date, "department": r.department, "section_id": r.section_id,
         "duration_min": r.duration_min, "outcome": r.outcome, "data_source": r.data_source}
        for r in rows
    ]


@router.get("/demands")
def get_demands(db: Session = Depends(get_db)):
    rows = db.query(BlockDemandRow).all()
    return [
        {
            "id": r.id, "department": r.department, "block_type": r.block_type, "section_id": r.section_id,
            "start_min": r.start_min, "end_min": r.end_min, "work_description": r.work_description,
            "asset_age_years": r.asset_age_years, "days_since_last_maintenance": r.days_since_last_maintenance,
            "defect_severity": r.defect_severity, "safety_risk": r.safety_risk,
            "assigned_gang_id": r.assigned_gang_id, "data_source": r.data_source,
            "validation_flag": r.validation_flag,
        }
        for r in rows
    ]


@router.get("/gangs")
def get_gangs(db: Session = Depends(get_db)):
    rows = db.query(GangRow).all()
    return [{"id": r.id, "name": r.name, "department": r.department, "gang_type": r.gang_type} for r in rows]


# --------------------------------------------------------- STAGES 2-7
@router.post("/plans/solve")
def solve_plans(db: Session = Depends(get_db)):
    """Runs preprocessing -> constraint modelling -> optimization ->
    conflict handling -> candidate generation -> feasibility validation
    -> ranking, then PERSISTS the ranked plans. Nothing here auto-approves
    anything — plans are written with status='PENDING'."""
    demand_rows = db.query(BlockDemandRow).all()
    if not demand_rows:
        raise HTTPException(status_code=400, detail="No block demands loaded — seed the database first.")

    demands = [
        BlockDemand(
            id=r.id, department=r.department, block_type=r.block_type, section_id=r.section_id,
            start_min=r.start_min, end_min=r.end_min, work_description=r.work_description,
            asset_age_years=r.asset_age_years, days_since_last_maintenance=r.days_since_last_maintenance,
            defect_severity=r.defect_severity, safety_risk=r.safety_risk, assigned_gang_id=r.assigned_gang_id,
        )
        for r in demand_rows
    ]
    train_rows = db.query(RealTrainWindowRow).all()
    real_windows = [
        RealTrainWindow(train_no=r.train_no, train_name=r.train_name, section_id=r.section_id,
                         start_min=r.start_min, end_min=r.end_min)
        for r in train_rows
    ]

    plan_results = solve_ranked_plans(demands, real_windows, GANGS, num_plans=3)

    saved_plans = []
    for pr in plan_results:
        plan_row = PlanRow(
            run_id=pr.run_id, rank=pr.rank, objective_value=pr.objective_value,
            total_track_time_returned_min=pr.total_track_time_returned_min,
            generated_at=pr.generated_at, status="PENDING",
            feasibility_section_conflicts=pr.feasibility_report.get("section_conflicts"),
            feasibility_gang_conflicts=pr.feasibility_report.get("gang_conflicts"),
            feasibility_train_conflicts=pr.feasibility_report.get("train_conflicts"),
            is_feasible=pr.feasibility_report.get("is_feasible"),
            solver_status=pr.solver_stats.get("status"),
            solve_time_ms=pr.solver_stats.get("solve_time_ms"),
            num_variables=pr.solver_stats.get("num_variables"),
            num_train_forced_zero=pr.solver_stats.get("num_train_forced_zero"),
            num_section_noverlap_groups=pr.solver_stats.get("num_section_noverlap_groups"),
            num_gang_noverlap_groups=pr.solver_stats.get("num_gang_noverlap_groups"),
        )
        db.add(plan_row)
        db.flush()  # so plan_row.id is populated before we attach items

        for item in pr.items:
            db.add(
                PlanDemandRow(
                    plan_id=plan_row.id, demand_id=item.demand_id, granted=item.granted,
                    priority_score=item.priority_score, reason=item.reason,
                )
            )
        saved_plans.append(plan_row.id)

    db.commit()
    return {"run_id": plan_results[0].run_id if plan_results else None, "plan_ids": saved_plans}


def _plan_summary_dict(r: PlanRow) -> dict:
    return {
        "id": r.id, "run_id": r.run_id, "rank": r.rank, "objective_value": r.objective_value,
        "total_track_time_returned_min": r.total_track_time_returned_min,
        "generated_at": r.generated_at.isoformat(), "status": r.status,
        "feasibility": {
            "section_conflicts": r.feasibility_section_conflicts,
            "gang_conflicts": r.feasibility_gang_conflicts,
            "train_conflicts": r.feasibility_train_conflicts,
            "is_feasible": r.is_feasible,
        },
        "solver_stats": {
            "status": r.solver_status, "solve_time_ms": r.solve_time_ms, "num_variables": r.num_variables,
            "num_train_forced_zero": r.num_train_forced_zero,
            "num_section_noverlap_groups": r.num_section_noverlap_groups,
            "num_gang_noverlap_groups": r.num_gang_noverlap_groups,
        },
    }


@router.get("/plans")
def list_plans(db: Session = Depends(get_db)):
    rows = db.query(PlanRow).order_by(PlanRow.run_id.desc(), PlanRow.rank.asc()).all()
    return [_plan_summary_dict(r) for r in rows]


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(PlanRow).filter(PlanRow.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")

    demand_by_id = {r.id: r for r in db.query(BlockDemandRow).all()}
    items = []
    for item in plan.items:
        demand = demand_by_id.get(item.demand_id)
        items.append(
            {
                "demand_id": item.demand_id,
                "granted": item.granted,
                "priority_score": item.priority_score,
                "reason": item.reason,
                "department": demand.department if demand else None,
                "block_type": demand.block_type if demand else None,
                "section_id": demand.section_id if demand else None,
                "start_min": demand.start_min if demand else None,
                "end_min": demand.end_min if demand else None,
                "work_description": demand.work_description if demand else None,
            }
        )

    return {
        **_plan_summary_dict(plan),
        "reviewed_by": plan.reviewed_by,
        "reviewed_at": plan.reviewed_at.isoformat() if plan.reviewed_at else None,
        "items": items,
    }


@router.get("/pipeline/preprocessing")
def get_preprocessing_demo():
    """STAGE 2 demo endpoint — regenerates the raw (pre-validation) demand
    list, INCLUDING one deliberately invalid record, and runs it through
    validate_demands() so the frontend can show the checks actually
    rejecting something, not just an empty 'all good' screen. Read-only:
    doesn't touch the database seeded at startup."""
    from app.data_sources.synthetic_blocks import generate_demo_scenario
    from app.preprocessing.validate import validate_demands

    real_windows = load_real_train_windows()
    raw_demands = generate_demo_scenario(real_windows)
    # A deliberately broken record — end before start — the kind of
    # data-entry mistake Check 1 in validate.py exists to catch.
    raw_demands.append(
        BlockDemand(
            id="D_BAD", department="ENGINEERING", block_type="Engineering block", section_id="SEC-1",
            start_min=1700, end_min=1650, work_description="Bad record: end time before start time",
            asset_age_years=10, days_since_last_maintenance=100, defect_severity=2, safety_risk=False,
            assigned_gang_id="G-ENG-1",
        )
    )
    clean_demands, report = validate_demands(raw_demands)
    clean_ids = {d.id for d in clean_demands}
    return {
        "raw_count": len(raw_demands),
        "clean_count": len(clean_demands),
        "checks_run": ["positive_duration", "defect_severity_range", "known_section", "known_gang", "unusually_long_block_flagged"],
        "report": report,
        "demands": [
            {"id": d.id, "department": d.department, "section_id": d.section_id,
             "start_min": d.start_min, "end_min": d.end_min, "work_description": d.work_description,
             "passed_validation": d.id in clean_ids}
            for d in raw_demands
        ],
    }


# ------------------------------------------------------------ STAGE 8
# Human-in-the-loop decision. This is the ONLY code path in the whole
# backend that can set a plan's status to APPROVED or REJECTED — the
# solver and every pipeline stage before this only ever produce
# PENDING plans. That is the deliberate boundary that keeps this a
# decision-support tool rather than an autonomous controller.
@router.post("/plans/{plan_id}/approve")
def approve_plan(plan_id: int, reviewer: str = "Planner", db: Session = Depends(get_db)):
    plan = db.query(PlanRow).filter(PlanRow.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = "APPROVED"
    plan.reviewed_by = reviewer
    plan.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": plan.id, "status": plan.status}


@router.post("/plans/{plan_id}/reject")
def reject_plan(plan_id: int, reviewer: str = "Planner", db: Session = Depends(get_db)):
    plan = db.query(PlanRow).filter(PlanRow.id == plan_id).first()
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan.status = "REJECTED"
    plan.reviewed_by = reviewer
    plan.reviewed_at = datetime.now(timezone.utc)
    db.commit()
    return {"id": plan.id, "status": plan.status}
