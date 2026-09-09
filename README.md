# AI-Powered Automatic Block Planning (SIH26027) — Prototype

A prototype system that combines machine learning and constraint
optimization to schedule railway maintenance "blocks" (track
possessions) against live train timetables.

## Architecture

| File | Responsibility |
|---|---|
| `real_data_loader.py` | Loads the **real** Indian Railways train timetable dataset (data.gov.in) and derives real sections + real train schedules from it. |
| `data_generator.py` | Uses real sections/trains when available (falls back to synthetic ones otherwise); always synthesizes asset condition data and pending maintenance jobs, since no public dataset exists for those. |
| `urgency_model.py` | Trains an XGBoost (or scikit-learn fallback) regressor to score each pending job's Maintenance Urgency (0–100). |
| `scheduler.py` | CP-SAT (Google OR-Tools) model that schedules maintenance blocks into timetable gaps, maximizing urgency addressed while minimizing train delay, with explainable per-job decisions. |
| `app.py` | Streamlit dashboard tying the pipeline together with Gantt visualization. |

## Real vs. synthetic data

This prototype uses **real Indian Railways data wherever it's publicly available**:

- **REAL**: train numbers, train names, station codes/names, and scheduled arrival/departure
  times — the entire `sections` and `trains` tables come from the official "Indian Railways
  Train Time Table" dataset (data.gov.in), via `real_data_loader.py`. By default the busiest
  real corridors in the dataset are selected (e.g. Mumbai suburban Kurla–Dadar–Matunga,
  Kolkata Sealdah–Bidhannagar).
- **SYNTHETIC (necessarily)**: per-asset condition/maintenance data (asset age, failure
  history, condition score, traffic load) and the pending maintenance jobs derived from them.
  Indian Railways does not publish granular track/signal/asset condition data publicly, so this
  layer is generated from a hand-specified, noise-injected urgency formula
  (`data_generator.true_urgency_formula`) standing in for real inspection/failure records. Swap
  in real asset records here (keeping the same `FEATURE_COLS` interface in `urgency_model.py`)
  if you get access to actual maintenance logs.

The real dataset (~17MB) is downloaded automatically on first run into `real_data/` if not
already present. To fetch/inspect it standalone:
```bash
python real_data_loader.py
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

> **Note (macOS):** if XGBoost fails to load its native library (a
> known `libomp.dylib` issue on Mac), the code automatically falls back
> to scikit-learn's `GradientBoostingRegressor` — no action needed. To
> use real XGBoost on macOS, run `brew install libomp` first.

## Run steps

1. **Generate sample data** (optional — the app also does this automatically on first load):
   ```bash
   python data_generator.py
   ```
   Writes `data/sections.csv`, `data/trains.csv`, `data/assets.csv`, `data/jobs.csv`, `data/historical.csv`.

2. **Train the urgency model** (optional standalone check):
   ```bash
   python urgency_model.py
   ```
   Prints validation MAE/R² and feature importances, saves `models/urgency_model.joblib`.

3. **Test the optimizer from the CLI** (optional):
   ```bash
   python scheduler.py
   ```
   Solves every section and prints scheduled/unscheduled jobs with reasoning.

4. **Launch the dashboard:**
   ```bash
   streamlit run app.py
   ```
   Open the printed local URL. In the sidebar:
   - Adjust number of sections / regenerate data.
   - Tune solver parameters (max train delay, delay penalty, urgency weight).
   - Select which sections to solve (section-by-section execution for scalability).
   - Click **Run Solver on Selected Sections**.

   Then explore the tabs: **Overview** (summary KPIs), **Asset Health & Urgency**
   (ML rankings + feature importance), **Schedule (Gantt)** (interactive Plotly
   timeline of trains vs. maintenance blocks), and **Explainability** (per-job
   scheduling rationale).

## Modeling notes

- **Urgency label**: since real historical failure data isn't available in this
  prototype, `data_generator.py` simulates a larger "historical" dataset with a
  hidden ground-truth urgency formula (condition, failures, age, maintenance
  recency, traffic load) plus noise — standing in for real inspection/failure
  outcomes. The model is trained on that and applied to score *current* pending
  jobs from features alone, the same way it would work with real historical
  records.
- **Optimization**: each section's trains and jobs contend for one shared
  track-possession resource (`AddNoOverlap`). Jobs are optional intervals (may
  go unscheduled); trains are fixed-duration but can shift within a small,
  configurable delay bound — making "minimize disruption" a real soft
  constraint the solver trades off against total urgency addressed.
