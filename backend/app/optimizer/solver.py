# STAGE 4 — OPTIMIZATION ENGINE
# STAGE 5 — CONFLICT DETECTION & PRIORITY HANDLING (reason-generation)
# STAGE 6 — CANDIDATE BLOCK PLANS -> FEASIBILITY VALIDATION
# STAGE 7 — RANKED RECOMMENDED PLAN
#
# These four stages live in one file because they're one continuous
# solver run: ask CP-SAT for the best plan, ask it again for the next-best
# DIFFERENT plan (repeat a few times), independently re-verify each
# returned plan really does respect every hard rule, then hand back a
# ranked list. The API layer (stage 8's backend half) just calls
# `solve_ranked_plans(...)` and stores whatever comes back — it does not
# know or care how the ranking was produced.

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from ortools.sat.python import cp_model

from app.constraints.builder import build_model
from app.data_sources.synthetic_blocks import BlockDemand, Gang
from app.data_sources.real_timetable import RealTrainWindow


@dataclass
class PlanItem:
    demand_id: str
    granted: bool
    priority_score: float
    reason: str


@dataclass
class PlanResult:
    run_id: str
    rank: int
    objective_value: float
    total_track_time_returned_min: int
    generated_at: datetime
    items: list[PlanItem] = field(default_factory=list)
    feasibility_report: dict = field(default_factory=dict)


def _overlaps(a_start, a_end, b_start, b_end) -> bool:
    return a_start < b_end and b_start < a_end


def _explain_rejection(
    demand: BlockDemand,
    granted_ids: set[str],
    demands_by_id: dict[str, BlockDemand],
    real_windows: list[RealTrainWindow],
) -> str:
    """STAGE 5 — for a demand this plan did NOT grant, work out which
    hard constraint actually blocked it, so the planner sees a reason
    instead of a bare rejection. We re-derive this independently of the
    solver's internal state (by re-checking overlaps in plain Python)
    rather than trusting solver internals, which keeps this explanation
    trustworthy even if the constraint model changes later."""
    for w in real_windows:
        if w.section_id == demand.section_id and _overlaps(demand.start_min, demand.end_min, w.start_min, w.end_min):
            return f"Clashes with real scheduled train {w.train_no} ('{w.train_name}') on this section — timetable constraint."

    for other_id in granted_ids:
        other = demands_by_id[other_id]
        if other.id == demand.id:
            continue
        same_section = other.section_id == demand.section_id and _overlaps(
            demand.start_min, demand.end_min, other.start_min, other.end_min
        )
        same_gang = other.assigned_gang_id == demand.assigned_gang_id and _overlaps(
            demand.start_min, demand.end_min, other.start_min, other.end_min
        )
        if same_section:
            return (
                f"Section already committed to {other.department}'s '{other.work_description}' "
                f"({other.id}) at an overlapping time — that request scored higher priority."
            )
        if same_gang:
            return (
                f"Assigned gang is already committed to {other.department}'s '{other.work_description}' "
                f"({other.id}) at an overlapping time — resource (gang) availability constraint."
            )

    return "Excluded by the optimizer while maximizing total prioritized track-time returned."


def _feasibility_check(
    granted_demands: list[BlockDemand], real_windows: list[RealTrainWindow]
) -> dict:
    """STAGE 6b — independently re-verify a plan the solver returned.
    CP-SAT already guarantees feasibility internally, but re-checking in
    plain Python here is a deliberate second, transparent safety net —
    the kind of check a planner or auditor could run by hand to trust the
    output without having to trust the solver's internals."""
    section_conflicts = 0
    gang_conflicts = 0
    train_conflicts = 0

    for i in range(len(granted_demands)):
        for j in range(i + 1, len(granted_demands)):
            a, b = granted_demands[i], granted_demands[j]
            if a.section_id == b.section_id and _overlaps(a.start_min, a.end_min, b.start_min, b.end_min):
                section_conflicts += 1
            if a.assigned_gang_id == b.assigned_gang_id and _overlaps(a.start_min, a.end_min, b.start_min, b.end_min):
                gang_conflicts += 1

    for d in granted_demands:
        for w in real_windows:
            if d.section_id == w.section_id and _overlaps(d.start_min, d.end_min, w.start_min, w.end_min):
                train_conflicts += 1

    return {
        "section_conflicts": section_conflicts,
        "gang_conflicts": gang_conflicts,
        "train_conflicts": train_conflicts,
        "is_feasible": section_conflicts == 0 and gang_conflicts == 0 and train_conflicts == 0,
    }


def solve_ranked_plans(
    demands: list[BlockDemand],
    real_windows: list[RealTrainWindow],
    gangs: list[Gang],
    num_plans: int = 3,
) -> list[PlanResult]:
    demands_by_id = {d.id: d for d in demands}
    run_id = str(uuid.uuid4())[:8]
    plans: list[PlanResult] = []
    forbidden_solutions: list[dict[str, bool]] = []

    for rank in range(1, num_plans + 1):
        built = build_model(demands, real_windows, gangs)
        model = built.model

        # STAGE 6 (candidate diversity): forbid every previously-found
        # exact grant/reject pattern so this solve is forced to find a
        # genuinely DIFFERENT plan, not just re-report the best one.
        for prev in forbidden_solutions:
            diff_terms = []
            for demand_id, was_granted in prev.items():
                var = built.granted_vars[demand_id]
                diff_terms.append((1 - var) if was_granted else var)
            model.Add(sum(diff_terms) >= 1)

        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        status = solver.Solve(model)

        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            break  # no more distinct feasible plans exist

        solution = {d.id: bool(solver.Value(built.granted_vars[d.id])) for d in demands}
        forbidden_solutions.append(solution)

        granted_ids = {d_id for d_id, g in solution.items() if g}
        granted_demands = [demands_by_id[d_id] for d_id in granted_ids]

        items = []
        for d in demands:
            granted = solution[d.id]
            if granted:
                reason = f"Granted — priority score {built.priorities[d.id]:.2f}, no conflicting demand or train scored higher on this section/gang."
            else:
                reason = _explain_rejection(d, granted_ids, demands_by_id, real_windows)
            items.append(PlanItem(demand_id=d.id, granted=granted, priority_score=built.priorities[d.id], reason=reason))

        plans.append(
            PlanResult(
                run_id=run_id,
                rank=rank,
                objective_value=solver.ObjectiveValue(),
                total_track_time_returned_min=sum(d.end_min - d.start_min for d in granted_demands),
                generated_at=datetime.now(timezone.utc),
                items=items,
                feasibility_report=_feasibility_check(granted_demands, real_windows),
            )
        )

    return plans
