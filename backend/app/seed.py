# Populates the SQLite database with STAGE 1 (data sources) content:
# the real corridor, the real derived train windows, and the synthetic
# demo scenario (gangs + block demands + historical log). Runs once on
# startup if the tables are empty — after that, everything persists in
# the .db file so approvals survive a server restart.

from __future__ import annotations

from sqlalchemy.orm import Session

from app.data_sources.corridor import SECTIONS, STATIONS
from app.data_sources.real_timetable import load_real_train_windows
from app.data_sources.synthetic_blocks import GANGS, HISTORICAL_BLOCKS, generate_demo_scenario
from app.db.models import (
    BlockDemandRow,
    GangRow,
    HistoricalBlockRow,
    RealTrainWindowRow,
    SectionRow,
    Station,
)
from app.preprocessing.validate import validate_demands


def seed_if_empty(db: Session) -> None:
    if db.query(Station).count() > 0:
        return  # already seeded

    for s in STATIONS:
        db.add(Station(code=s.code, name=s.name, km_from_start=s.km_from_start))
    for sec in SECTIONS:
        db.add(SectionRow(id=sec.id, from_station=sec.from_station, to_station=sec.to_station, length_km=sec.length_km))
    db.flush()

    for g in GANGS:
        db.add(GangRow(id=g.id, name=g.name, department=g.department, gang_type=g.gang_type))
    db.flush()

    real_windows = load_real_train_windows()
    for w in real_windows:
        db.add(
            RealTrainWindowRow(
                train_no=w.train_no, train_name=w.train_name, section_id=w.section_id,
                start_min=w.start_min, end_min=w.end_min,
            )
        )
    db.flush()

    raw_demands = generate_demo_scenario(real_windows)
    clean_demands, report = validate_demands(raw_demands)
    flagged_ids = {}
    for entry in report:
        for demand_id in entry["failed_ids"]:
            flagged_ids.setdefault(demand_id, []).append(entry["check"])

    for d in clean_demands:
        db.add(
            BlockDemandRow(
                id=d.id, department=d.department, block_type=d.block_type, section_id=d.section_id,
                start_min=d.start_min, end_min=d.end_min, work_description=d.work_description,
                asset_age_years=d.asset_age_years, days_since_last_maintenance=d.days_since_last_maintenance,
                defect_severity=d.defect_severity, safety_risk=d.safety_risk,
                assigned_gang_id=d.assigned_gang_id,
                validation_flag=",".join(flagged_ids.get(d.id, [])) or None,
            )
        )

    for h in HISTORICAL_BLOCKS:
        db.add(HistoricalBlockRow(**h))

    db.commit()
