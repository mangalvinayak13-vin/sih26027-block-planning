# STAGE 1 — DATA SOURCES (synthetic data)
#
# WHY this data is synthetic: block DEMANDS (which department wants which
# section closed, when, and why), gang/machine ROSTERS, and per-asset
# maintenance history live inside Indian Railways' internal BDMS/TMS/SMMS/
# TDMS systems. There is no public dataset for any of this — so we
# generate it ourselves. That is the correct approach for a prototype (the
# actual SIH problem statement expects validation on historical/synthetic
# data before this ever touches a live system) — but it must be generated
# in a way that's grounded in the real rules of block planning, not random
# noise, and it must be clearly labelled "synthetic" everywhere it's shown.
#
# This file hand-builds ONE curated demo scenario rather than drawing
# purely random numbers. Reason: for a live demo in front of evaluators we
# need GUARANTEED, explainable conflicts (two departments wanting the same
# track, a gang double-booked, a block clashing with a real train) — not a
# scenario that might happen to have zero conflicts on a given random seed.
# Every number below (durations, defect severities, maintenance ages) is
# still chosen to be realistic for the block type it belongs to.

from __future__ import annotations

from dataclasses import dataclass, field

from app.data_sources.real_timetable import RealTrainWindow


@dataclass
class Gang:
    id: str
    name: str
    department: str   # ENGINEERING | S_AND_T | TRD | TRAFFIC
    gang_type: str     # human-readable specialisation, e.g. "Track fitting team"


@dataclass
class BlockDemand:
    id: str
    department: str            # ENGINEERING | S_AND_T | TRD | TRAFFIC
    block_type: str             # "Engineering block" | "S&T block" | "Power/TRD block" | "Traffic block"
    section_id: str
    start_min: int               # minutes from midnight of the demo day
    end_min: int
    work_description: str
    asset_age_years: int
    days_since_last_maintenance: int
    defect_severity: int          # 1 (minor) .. 5 (severe/safety-critical)
    safety_risk: bool
    assigned_gang_id: str
    data_source: str = "synthetic"


# --- Synthetic resource roster -------------------------------------------
# One or two gangs per department. Kept deliberately small: part of the
# point of the "resource availability" constraint is that gangs are a
# SCARCE shared resource, so a small roster is what makes that constraint
# actually bind during the demo.
GANGS = [
    Gang("G-ENG-1", "Engineering Gang Alpha", "ENGINEERING", "Track fitting team"),
    Gang("G-ENG-2", "Engineering Gang Bravo", "ENGINEERING", "Ballast & rail team"),
    Gang("G-SNT-1", "S&T Maintenance Crew 1", "S_AND_T", "Signal & cable team"),
    Gang("G-TRD-1", "TRD Overhead Crew 1", "TRD", "OHE (overhead traction) team"),
    Gang("G-TRD-2", "TRD Overhead Crew 2", "TRD", "OHE (overhead traction) team"),
    Gang("G-TRF-1", "Traffic Block Control", "TRAFFIC", "Yard/traffic control crew"),
]

BLOCK_TYPE_BY_DEPARTMENT = {
    "ENGINEERING": "Engineering block",
    "S_AND_T": "S&T block",
    "TRD": "Power/TRD block",
    "TRAFFIC": "Traffic block",
}


def _demand(
    id_, department, section_id, start_min, end_min, work_description,
    asset_age_years, days_since_last_maintenance, defect_severity, safety_risk, gang_id,
) -> BlockDemand:
    return BlockDemand(
        id=id_,
        department=department,
        block_type=BLOCK_TYPE_BY_DEPARTMENT[department],
        section_id=section_id,
        start_min=start_min,
        end_min=end_min,
        work_description=work_description,
        asset_age_years=asset_age_years,
        days_since_last_maintenance=days_since_last_maintenance,
        defect_severity=defect_severity,
        safety_risk=safety_risk,
        assigned_gang_id=gang_id,
    )


def generate_demo_scenario(real_windows: list[RealTrainWindow]) -> list[BlockDemand]:
    """Build the curated demo set of block demands.

    Block-request windows are set late night / early morning (21:00 ->
    06:00 the next day, i.e. minutes 1260-1800 on a continuous clock),
    because that is when Indian Railways actually schedules most
    maintenance blocks — passenger traffic is at its lowest. Even so,
    this corridor is one of the busiest in the country, so real trains
    still run through most of that window.

    IMPORTANT: the demands below (other than D14) were deliberately
    placed inside the actual FREE GAPS of the real timetable for their
    section (computed from real_timetable.py's derived windows) so that
    the conflicts you see in the demo are the department/gang clashes we
    want to showcase, not incidental collisions with a real train. D14 is
    the deliberate exception: it's placed ON TOP of a real train on
    purpose, to demonstrate the timetable-protection constraint. This is
    an honest simplification for a repeatable demo — a real BDMS
    deployment would check every request against the live timetable, not
    a hand-picked one.
    """
    demands = [
        # --- Three-way clash on SEC-2 (Ghaziabad-Aligarh), inside its
        # large real overnight gap (00:10-05:32): all three technical
        # departments want overlapping time on the same section. This is
        # the textbook "nobody cross-checks BDMS across departments"
        # scenario from the problem statement.
        _demand("D1", "ENGINEERING", "SEC-2", 1500, 1650,  # 01:00-03:30
                "Rail fracture repair near Ghaziabad", 18, 400, 5, True, "G-ENG-1"),
        _demand("D2", "S_AND_T", "SEC-2", 1530, 1680,  # 01:30-04:00
                "Signal cable replacement", 9, 200, 3, False, "G-SNT-1"),
        _demand("D3", "TRD", "SEC-2", 1560, 1710,  # 02:00-04:30
                "OHE insulator replacement", 12, 260, 4, False, "G-TRD-1"),

        # --- Resource (gang) clash: G-ENG-1 is already committed to D1 on
        # SEC-2, but is also requested here on SEC-4 with an overlapping
        # window. One gang cannot physically be in two places at once —
        # this is the "resource availability" constraint, distinct from
        # the "same section" constraint above.
        _demand("D4", "ENGINEERING", "SEC-4", 1640, 1700,  # 03:20-04:20
                "Track tamping", 22, 220, 2, False, "G-ENG-1"),

        _demand("D5", "S_AND_T", "SEC-4", 1710, 1770,  # 04:30-05:30
                "Axle counter maintenance", 6, 90, 2, False, "G-SNT-1"),

        # --- Traffic vs Engineering clash on SEC-3 (Aligarh-Tundla),
        # inside its real early-morning gap (05:10-06:00).
        _demand("D6", "TRAFFIC", "SEC-3", 1750, 1785,  # 05:10-05:45
                "Yard remodeling possession", 30, 500, 3, False, "G-TRF-1"),
        _demand("D7", "ENGINEERING", "SEC-3", 1765, 1795,  # 05:25-05:55
                "Rail grinding", 15, 150, 2, False, "G-ENG-2"),

        # --- TRD vs Engineering clash on SEC-1 (New Delhi-Ghaziabad),
        # inside its (narrow) real gap (01:55-03:30). Low vs. high
        # urgency — a good example for the ranked-shortlist explanation:
        # same kind of clash as D1-D3, but the priority scores are much
        # closer, so the tie-break reasoning is more interesting to show.
        _demand("D8", "TRD", "SEC-1", 1555, 1620,  # 01:55-03:00
                "OHE mast painting (cosmetic/preventive)", 5, 130, 1, False, "G-TRD-2"),
        _demand("D9", "ENGINEERING", "SEC-1", 1590, 1645,  # 02:30-03:25
                "Ballast renewal", 20, 300, 4, False, "G-ENG-2"),

        # --- S&T vs Traffic clash on SEC-4, inside its small early-
        # evening gap (21:10-21:55).
        _demand("D10", "S_AND_T", "SEC-4", 1270, 1305,  # 21:10-21:45
                "Point machine inspection", 8, 110, 2, False, "G-SNT-1"),
        _demand("D11", "TRAFFIC", "SEC-4", 1280, 1315,  # 21:20-21:55
                "Traffic block for points renewal", 25, 400, 3, False, "G-TRF-1"),

        # --- Two clean, non-conflicting filler requests, so the ranked
        # output isn't "everything is a conflict" — most real block
        # demands DON'T clash with anything, which is worth showing too.
        _demand("D12", "ENGINEERING", "SEC-2", 1710, 1755,  # 04:30-05:15
                "Routine fastener check", 10, 140, 1, False, "G-ENG-1"),
        _demand("D13", "TRD", "SEC-4", 1775, 1795,  # 05:35-05:55
                "OHE tension check", 7, 100, 2, False, "G-TRD-2"),

        # --- SEC-5 (Etawah-Kanpur) has essentially NO free overnight gap
        # in the real timetable — it's the busiest stretch of this
        # corridor. We surface that as its own filler request so the
        # dashboard can show a section that's almost always train-
        # occupied, which is a realistic and interesting finding on its
        # own (a planner would need a much shorter or daytime window
        # here). It will very likely be rejected by the timetable
        # constraint — that's the point.
        _demand("D_SEC5", "ENGINEERING", "SEC-5", 1360, 1420,  # 22:40-23:40
                "Ballast renewal near Etawah (contested section)", 20, 300, 4, False, "G-ENG-1"),
    ]

    # --- Deliberately manufacture ONE clash against a REAL train window,
    # so the "block can't be granted where a train is scheduled" hard
    # constraint has something real to visibly reject. We look for the
    # first real overnight (22:00-06:00, i.e. >=1320 or wrapped past
    # midnight) train window on any section and place a block request
    # squarely on top of it.
    overnight = [w for w in real_windows if w.start_min >= 21 * 60 or w.end_min <= 8 * 60 + 1440]
    if overnight:
        w = overnight[0]
        demands.append(
            _demand(
                "D14", "ENGINEERING", w.section_id, w.start_min, w.start_min + 60,
                f"Emergency rail inspection (clashes with real train {w.train_no} '{w.train_name}')",
                14, 190, 3, False, "G-ENG-2",
            )
        )

    return demands


# --- Synthetic historical block record (Data Source #4: "historical block
# data") — a short, illustrative log of past granted blocks. Not used by
# the solver; shown in the UI purely as the kind of trend context a real
# BDMS would supply (e.g. "Engineering wins most overnight contention").
HISTORICAL_BLOCKS = [
    {"date": "2026-08-01", "department": "ENGINEERING", "section_id": "SEC-2", "duration_min": 180, "outcome": "COMPLETED"},
    {"date": "2026-08-03", "department": "S_AND_T", "section_id": "SEC-4", "duration_min": 90, "outcome": "COMPLETED"},
    {"date": "2026-08-05", "department": "TRD", "section_id": "SEC-5", "duration_min": 120, "outcome": "CANCELLED"},
    {"date": "2026-08-08", "department": "TRAFFIC", "section_id": "SEC-1", "duration_min": 60, "outcome": "COMPLETED"},
    {"date": "2026-08-12", "department": "ENGINEERING", "section_id": "SEC-3", "duration_min": 150, "outcome": "COMPLETED"},
    {"date": "2026-08-15", "department": "S_AND_T", "section_id": "SEC-2", "duration_min": 100, "outcome": "COMPLETED"},
    {"date": "2026-08-20", "department": "TRD", "section_id": "SEC-2", "duration_min": 140, "outcome": "DEFERRED"},
]
