# The database tables. Using SQLite (a single file on disk) instead of a
# "real" database server like PostgreSQL — WHY: this is a prototype meant
# to run on a laptop for a demo, and SQLite needs zero setup (no server to
# install/start). PostgreSQL is what a production BDMS integration would
# use (see README), but that's a deployment concern, not a modelling one —
# swapping the DB later doesn't change any of the code below.

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class Station(Base):
    __tablename__ = "stations"
    code = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    km_from_start = Column(Float, nullable=False)


class SectionRow(Base):
    __tablename__ = "sections"
    id = Column(String, primary_key=True)
    from_station = Column(String, ForeignKey("stations.code"), nullable=False)
    to_station = Column(String, ForeignKey("stations.code"), nullable=False)
    length_km = Column(Float, nullable=False)


class RealTrainWindowRow(Base):
    """A real train's derived section-occupancy window. data_source is
    always 'real' here — kept as an explicit column (not just implied by
    the table) so the API/UI never has to guess what's real vs synthetic."""
    __tablename__ = "real_train_windows"
    id = Column(Integer, primary_key=True, autoincrement=True)
    train_no = Column(String, nullable=False)
    train_name = Column(String, nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    start_min = Column(Integer, nullable=False)
    end_min = Column(Integer, nullable=False)
    data_source = Column(String, nullable=False, default="real")


class GangRow(Base):
    __tablename__ = "gangs"
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    gang_type = Column(String, nullable=False)
    data_source = Column(String, nullable=False, default="synthetic")


class BlockDemandRow(Base):
    __tablename__ = "block_demands"
    id = Column(String, primary_key=True)
    department = Column(String, nullable=False)
    block_type = Column(String, nullable=False)
    section_id = Column(String, ForeignKey("sections.id"), nullable=False)
    start_min = Column(Integer, nullable=False)
    end_min = Column(Integer, nullable=False)
    work_description = Column(String, nullable=False)
    asset_age_years = Column(Integer, nullable=False)
    days_since_last_maintenance = Column(Integer, nullable=False)
    defect_severity = Column(Integer, nullable=False)
    safety_risk = Column(Boolean, nullable=False)
    assigned_gang_id = Column(String, ForeignKey("gangs.id"), nullable=False)
    data_source = Column(String, nullable=False, default="synthetic")
    # Preprocessing stage may flag a raw record as invalid instead of
    # dropping it silently — kept visible so evaluators can see the
    # validation stage actually did something.
    validation_flag = Column(String, nullable=True)


class HistoricalBlockRow(Base):
    __tablename__ = "historical_blocks"
    id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(String, nullable=False)
    department = Column(String, nullable=False)
    section_id = Column(String, nullable=False)
    duration_min = Column(Integer, nullable=False)
    outcome = Column(String, nullable=False)
    data_source = Column(String, nullable=False, default="synthetic")


class PlanRow(Base):
    """One candidate plan produced by a single solver run. A solver run
    that asks for 'top 3 plans' produces 3 PlanRow entries, ranked."""
    __tablename__ = "plans"
    id = Column(Integer, primary_key=True, autoincrement=True)
    run_id = Column(String, nullable=False)   # groups plans generated together
    rank = Column(Integer, nullable=False)     # 1 = best
    objective_value = Column(Float, nullable=False)
    total_track_time_returned_min = Column(Integer, nullable=False)
    generated_at = Column(DateTime, nullable=False)
    # Human-in-the-loop status. The solver NEVER sets this to APPROVED —
    # only the /approve API endpoint (a planner action) can. This is the
    # column that enforces "decision support, not autonomous control".
    status = Column(String, nullable=False, default="PENDING")
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # Stage 6 (feasibility validation) — an INDEPENDENT re-check of this
    # plan, stored so the "Candidate Plans" page can show it without
    # re-solving. See optimizer/solver.py::_feasibility_check.
    feasibility_section_conflicts = Column(Integer, nullable=True)
    feasibility_gang_conflicts = Column(Integer, nullable=True)
    feasibility_train_conflicts = Column(Integer, nullable=True)
    is_feasible = Column(Boolean, nullable=True)

    # Stage 4 (optimization engine) transparency numbers, same for every
    # rank within one run — see optimizer/solver.py's PlanResult.solver_stats.
    solver_status = Column(String, nullable=True)
    solve_time_ms = Column(Float, nullable=True)
    num_variables = Column(Integer, nullable=True)
    num_train_forced_zero = Column(Integer, nullable=True)
    num_section_noverlap_groups = Column(Integer, nullable=True)
    num_gang_noverlap_groups = Column(Integer, nullable=True)

    items = relationship("PlanDemandRow", back_populates="plan", cascade="all, delete-orphan")


class PlanDemandRow(Base):
    """Per-demand outcome within a plan: granted or not, its priority
    score, and (if rejected) WHY — this is what lets the UI show
    reasoning next to each plan instead of a bare accept/reject list."""
    __tablename__ = "plan_demands"
    id = Column(Integer, primary_key=True, autoincrement=True)
    plan_id = Column(Integer, ForeignKey("plans.id"), nullable=False)
    demand_id = Column(String, ForeignKey("block_demands.id"), nullable=False)
    granted = Column(Boolean, nullable=False)
    priority_score = Column(Float, nullable=False)
    reason = Column(Text, nullable=False)

    plan = relationship("PlanRow", back_populates="items")
