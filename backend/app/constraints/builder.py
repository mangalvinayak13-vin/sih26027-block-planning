# STAGE 3 — CONSTRAINT MODELLING
#
# This is where the plain-English rules from the problem statement become
# actual CP-SAT variables and constraints. Nothing here decides anything —
# it only DESCRIBES what a valid plan is allowed to look like. The solver
# (optimizer/solver.py) is the part that searches for the best plan that
# obeys everything built here.
#
# We use Google OR-Tools' CP-SAT constraint solver, not a machine-learning
# model, because block planning is fundamentally a CONSTRAINT SATISFACTION
# problem: "no two things may use the same track at the same time" is a
# hard logical rule, not a pattern to be learned from data. A solver can
# PROVE a plan is safe; a neural network can only estimate one and might
# be wrong. That guarantee is the whole reason this project exists — the
# real-world problem is that nobody currently checks these hard rules
# against each other at all.

from __future__ import annotations

from dataclasses import dataclass

from ortools.sat.python import cp_model

from app.data_sources.synthetic_blocks import BlockDemand, Gang
from app.data_sources.real_timetable import RealTrainWindow
from app.priority.scoring import priority_score


@dataclass
class BuiltModel:
    model: cp_model.CpModel
    granted_vars: dict[str, cp_model.IntVar]   # demand_id -> BoolVar
    priorities: dict[str, float]                 # demand_id -> priority score [0,1]
    weights: dict[str, int]                       # demand_id -> integer objective weight


def build_model(
    demands: list[BlockDemand],
    real_windows: list[RealTrainWindow],
    gangs: list[Gang],
) -> BuiltModel:
    model = cp_model.CpModel()

    granted_vars: dict[str, cp_model.IntVar] = {}
    priorities: dict[str, float] = {}
    weights: dict[str, int] = {}

    demand_intervals: dict[str, cp_model.IntervalVar] = {}

    for d in demands:
        granted = model.NewBoolVar(f"granted_{d.id}")
        granted_vars[d.id] = granted

        duration = d.end_min - d.start_min
        # This is an OPTIONAL interval: it only "occupies" the timeline
        # if `granted` is true. That single mechanism is what lets the
        # solver treat "should we grant this block at all?" and "does it
        # clash with something?" as one combined decision.
        interval = model.NewOptionalIntervalVar(
            d.start_min, duration, d.end_min, granted, f"interval_{d.id}"
        )
        demand_intervals[d.id] = interval

        score = priority_score(d.department, d.days_since_last_maintenance, d.defect_severity, d.safety_risk)
        priorities[d.id] = score
        # Objective weight = (track-time returned) x (1 + PRIORITY_WEIGHT
        # * priority bonus). The base "duration" term is literally the
        # asset-availability objective from the problem statement (track-
        # time handed back to maintenance). The priority term is scaled
        # up (x4, not x1) deliberately: the problem statement asks for
        # priority to RESOLVE conflicts, not just nudge them — with a x1
        # multiplier a single safety-critical short block could lose to
        # two unrelated routine blocks purely because their durations add
        # up to more, which is the wrong trade-off for a safety rule.
        # Scaled to integers x1000 because CP-SAT's objective must be
        # integer/linear, not floating point.
        PRIORITY_WEIGHT = 4
        weights[d.id] = round(duration * (1 + PRIORITY_WEIGHT * score) * 1000)

    # --- HARD CONSTRAINT: timetable / train-path protection -----------
    # A block can never be granted over a section a real train is
    # scheduled to run through in that window. Real trains on a multi-
    # track corridor legitimately overlap EACH OTHER in time on the "same"
    # section (that's what the extra tracks are for) — so we must not
    # forbid train-vs-train overlap, only block-vs-train overlap. Since a
    # demand's requested window is a fixed constant (this prototype
    # decides GRANT/NO-GRANT, not "shift the time"), whether it clashes
    # with a real train is knowable right now in plain Python — so instead
    # of a solver constraint we simply force granted=0 for any demand that
    # overlaps a real train on its section. This is still a hard
    # constraint (never relaxed), just resolved before the solver runs
    # rather than inside it.
    def _overlaps(a_start, a_end, b_start, b_end) -> bool:
        return a_start < b_end and b_start < a_end

    for d in demands:
        clash = any(
            w.section_id == d.section_id and _overlaps(d.start_min, d.end_min, w.start_min, w.end_min)
            for w in real_windows
        )
        if clash:
            model.Add(granted_vars[d.id] == 0)

    # --- HARD CONSTRAINT: safety / interlocking rule -----------------
    # A track section cannot be occupied by two conflicting BLOCKS at the
    # same time (this is on top of the train check above). This is THE
    # non-negotiable rule of railway operations — two work gangs, or a
    # gang and a train, cannot both be told the same stretch of track is
    # theirs, since that is exactly the fatal-accident scenario blocks
    # exist to prevent. Never relaxed or traded off against the
    # objective, unlike everything else in this model.
    #
    # AddNoOverlap over each section's optional block intervals means
    # CP-SAT guarantees at most one of them is ever "present" (granted) at
    # a given instant. Cross-department clashes fall out automatically,
    # because Engineering/S&T/TRD/Traffic requests on the same section all
    # land in the SAME group — nobody is checked in a departmental silo.
    sections: dict[str, list[cp_model.IntervalVar]] = {}
    for d in demands:
        sections.setdefault(d.section_id, []).append(demand_intervals[d.id])

    for section_id, intervals in sections.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)

    # --- HARD CONSTRAINT: resource (gang) availability ----------------
    # A maintenance gang/machine can only be in one place at a time. A
    # block granted to a gang that's already committed elsewhere during
    # that window is a block nobody can actually carry out — so it must
    # never be granted, regardless of how urgent it is on paper.
    by_gang: dict[str, list[cp_model.IntervalVar]] = {}
    for d in demands:
        by_gang.setdefault(d.assigned_gang_id, []).append(demand_intervals[d.id])
    for gang_id, intervals in by_gang.items():
        if len(intervals) > 1:
            model.AddNoOverlap(intervals)

    # Timetable & train-path constraint and cross-department coordination
    # are both already satisfied structurally above: real train intervals
    # share the same per-section NoOverlap group as block intervals, and
    # all departments' requests for a section share that same group.

    model.Maximize(sum(weights[d.id] * granted_vars[d.id] for d in demands))

    return BuiltModel(model=model, granted_vars=granted_vars, priorities=priorities, weights=weights)
