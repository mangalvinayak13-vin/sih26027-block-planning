# SIH26027 — AI-Powered Automatic Block Planning (Prototype)

A decision-support prototype for planning railway maintenance **blocks** (see the
in-app "What is a Block?" page, or the explanation below) using **Google
OR-Tools CP-SAT** — a constraint solver, not a neural network — to check
pending block demands from Engineering, S&T, TRD and Traffic against each
other, the real timetable, and gang availability, then hand a human planner
a ranked shortlist of feasible plans to approve.

**This is a decision-support tool, not an autonomous controller.** The
solver never confirms a block — only a planner action in the dashboard
(approve/reject) can change a plan's status.

## What is a block?

A block is a time-bound restriction on a section of track during which no
train movement is permitted, so maintenance work can happen safely. There
are four kinds, one per requesting department: **Traffic block** (general
operations), **Engineering block** (track/civil), **S&T block**
(signalling/telecom), **Power/TRD block** (overhead electric line). Today
each department requests blocks separately through BDMS while train
schedules live in separate systems (TMS/SMMS/TDMS/COA) — nobody
cross-checks them against each other, causing clashes. This project is
that missing cross-check layer. The in-app "What is a Block?" tab has the
full explanation, written for a non-technical evaluator.

## The pipeline (8 stages — matches the file layout below)

1. **Data Sources** — `backend/app/data_sources/`
2. **Preprocessing & Validation** — `backend/app/preprocessing/validate.py`
3. **Constraint Modelling** — `backend/app/constraints/builder.py`
4. **Optimization Engine (OR-Tools CP-SAT)** — `backend/app/optimizer/solver.py`
5. **Conflict Detection & Priority Handling** — also in `solver.py` (`_explain_rejection`)
6. **Candidate Plans → Feasibility Validation** — also in `solver.py` (`_feasibility_check`, the multi-solve loop)
7. **Ranked Recommended Plan** — the `PlanResult` list `solver.py` returns, best-first
8. **Planner Dashboard** — `backend/app/api/routes.py` (approve/reject) + `frontend/src/pages/Dashboard.jsx`

A small hand-written formula (`backend/app/priority/scoring.py`) scores how
urgent each maintenance request is (0-1) and feeds that number **into**
the solver's objective — it never decides the plan itself. The interface
is designed so a trained ML model could be swapped in later without
touching the solver.

## Data sources — what's real, what's synthetic

Every record in the app carries a `data_source` field and the in-app
**Data Sources** tab cites all of this live, so you can point at it during
a demo.

**Real:**
- **Corridor**: New Delhi → Ghaziabad → Aligarh → Tundla → Etawah → Kanpur
  Central, a real stretch of the Delhi-Howrah main line. Real station
  names/codes.
- **Timetable**: [Indian Railways Train Time Table, data.gov.in](https://www.data.gov.in/catalog/indian-railways-train-time-table)
  (~2,810 real trains). Section lengths and real train section-occupancy
  windows are *derived* from this file (see
  `backend/app/data_sources/real_timetable.py`) — IR doesn't publish
  block-section occupancy directly, only station-to-station timings, so we
  compute "real train departs station A at t1, arrives station B at t2 ⇒
  that section is occupied [t1, t2]" from real numbers.
- The raw file lives at `backend/data/real/Train_details_22122017.csv`
  (~17MB, already included — no download step needed).

**Synthetic (necessarily — IR's internal BDMS/TMS/SMMS/TDMS data isn't
public):** block demand requests (department, section, time, work
description, asset age, days since maintenance, defect severity, safety
flag), the gang/resource roster, and a short historical block log. See
`backend/app/data_sources/synthetic_blocks.py` — every number there is
grounded in the block-planning rules described above, not random noise,
and the demo scenario is curated (not randomly generated) so the conflicts
you see in a live demo are reproducible.

## Repo layout

```
backend/
  app/
    main.py              FastAPI app, DB init, seeding on startup
    data_sources/         Stage 1 — corridor, real timetable loader, synthetic generators
    preprocessing/         Stage 2 — pandas validation
    constraints/            Stage 3 — CP-SAT constraint model
    optimizer/               Stage 4-7 — solve, rank, explain, validate
    priority/                 Criticality scoring formula (feeds the solver)
    db/                        SQLAlchemy models + SQLite session
    api/                        FastAPI routes (stage 8 backend half)
  data/real/                   The real data.gov.in timetable CSV
  data/synthetic/               (generated at runtime, into SQLite — nothing static here)
frontend/
  src/
    pages/
      WhatIsABlock.jsx          Block/pipeline explainer for evaluators
      Corridor.jsx               Raw inputs: corridor map, demands, real trains, gangs
      Dashboard.jsx              Ranked plans, reasoning, approve/reject
      DataSources.jsx            Real vs synthetic citations
    api.js                       All backend fetch calls in one place
```

## Setup & running

**Backend** (Python 3.11+):
```bash
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8000
```
On first run it creates `data/block_planning.db` (SQLite) and seeds it with
the real corridor/timetable and the synthetic demo scenario automatically.

**Frontend** (Node.js, installed via Homebrew if you didn't have it):
```bash
cd frontend
npm install
npm run dev
```
Open the printed `http://localhost:5173` URL. Start on the **What is a
Block?** tab, then **Corridor & Demands** to see the raw inputs, then
**Planner Dashboard** → "Run Solver" to see the ranked plans, then
**Data Sources** for the real-vs-synthetic citations.

### Database note

This prototype uses **SQLite** (a single file, zero setup) so it runs on a
laptop with no extra services. **PostgreSQL is the intended choice for a
production deployment** — swapping it in only touches
`backend/app/db/session.py`'s connection string; nothing else in the app
depends on SQLite specifically.

### Resetting the demo

Stop the backend, delete `backend/data/block_planning.db`, restart it — the
demo scenario reseeds automatically. Useful if you've approved/rejected
plans during a practice run and want a clean slate before the real demo.

## Modelling notes / simplifications (be ready to explain these)

- **Fixed-time grant decisions, not rescheduling**: each block demand has a
  fixed requested window; the solver decides GRANT or NO-GRANT per
  request, it doesn't shift times. This keeps the model explainable to a
  non-technical evaluator ("did this request get approved, and why") while
  still exercising every required constraint type. A production version
  would also let the solver negotiate shifted windows.
- **Train-vs-block, not train-vs-train**: real trains on a multi-track
  corridor legitimately overlap each other in time (that's what extra
  tracks are for) — only a *block* is forbidden from overlapping a *train*
  on the same section. This is enforced by precomputing, per demand,
  whether it overlaps any real train window and forcing it out if so
  (`constraints/builder.py`), rather than by an OR-Tools `NoOverlap` that
  would incorrectly also forbid trains from overlapping each other.
- **One section = one shared resource**: a section is modelled as a single
  possession, matching how a block is actually granted (over the whole
  section), even on physically multi-tracked stretches. This is why one of
  our five demo sections (Etawah–Kanpur, the busiest) has almost no free
  overnight slot at all in the real timetable — a genuine finding, not a
  bug.
