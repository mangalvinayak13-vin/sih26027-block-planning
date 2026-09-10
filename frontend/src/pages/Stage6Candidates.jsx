import { useEffect, useState } from "react";
import { api } from "../api";
import Timeline from "../components/Timeline";
import { DEPT_COLORS } from "../constants";
import { latestRunPlans } from "../utils";

// STAGE 6 — CANDIDATE PLANS -> FEASIBILITY VALIDATION.
// The solver doesn't just return one plan — it's re-run with each
// previous solution forbidden, so it has to find a genuinely different
// combination each time (see optimizer/solver.py's solution-cutting
// loop). Each candidate is then INDEPENDENTLY re-checked in plain Python
// (not trusting CP-SAT's internal state) for section/gang/train
// conflicts — that's the feasibility checklist below. All three should
// always read zero; if they ever don't, that's a bug in the constraint
// model, not something the objective is allowed to trade away.

const VIEW_RANGE = [1200, 1860];

export default function Stage6Candidates() {
  const [plans, setPlans] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listPlans()
      .then(async (all) => {
        const summaries = latestRunPlans(all);
        if (summaries.length === 0) {
          setError("No solved plans yet — go to Stage 4 and run the solver first.");
          return;
        }
        const details = await Promise.all(summaries.map((s) => api.getPlan(s.id)));
        setPlans(details);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="page">{error}</div>;
  if (plans.length === 0) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <div className="stage-kicker">Stage 6 of 8</div>
      <h1>Candidate Plans & Feasibility Validation</h1>
      <p className="lede">
        {plans.length} distinct candidate plans from this solver run, side by side. Each one is a
        genuinely different combination of granted/rejected requests — not the same plan repeated.
      </p>

      <div className="candidate-grid">
        {plans.map((plan) => {
          const granted = plan.items.filter((i) => i.granted);
          const f = plan.feasibility;
          return (
            <div className={`card candidate-card ${plan.rank === 1 ? "best" : ""}`} key={plan.id}>
              <div className="candidate-header">
                <span className="plan-rank">#{plan.rank}</span>
                {plan.rank === 1 && <span className="best-tag">Recommended</span>}
              </div>
              <div className="stat-tile small">
                <div className="stat-number">{plan.objective_value.toFixed(0)}</div>
                <div className="stat-label">Objective score</div>
              </div>
              <div className="stat-tile small">
                <div className="stat-number">{granted.length} / {plan.items.length}</div>
                <div className="stat-label">Requests granted</div>
              </div>

              <h4>Granted requests, on the clock</h4>
              <Timeline
                rows={granted.map((i) => ({
                  id: i.demand_id,
                  label: i.demand_id,
                  sublabel: i.department,
                  start: i.start_min,
                  end: i.end_min,
                  color: DEPT_COLORS[i.department],
                }))}
                rangeStart={VIEW_RANGE[0]}
                rangeEnd={VIEW_RANGE[1]}
              />

              <h4>Independent feasibility re-check</h4>
              <ul className="feasibility-list">
                <li className={f.section_conflicts === 0 ? "ok" : "bad"}>
                  {f.section_conflicts === 0 ? "✅" : "❌"} Section double-bookings: {f.section_conflicts}
                </li>
                <li className={f.gang_conflicts === 0 ? "ok" : "bad"}>
                  {f.gang_conflicts === 0 ? "✅" : "❌"} Gang double-bookings: {f.gang_conflicts}
                </li>
                <li className={f.train_conflicts === 0 ? "ok" : "bad"}>
                  {f.train_conflicts === 0 ? "✅" : "❌"} Real-train clashes: {f.train_conflicts}
                </li>
              </ul>
              <div className={`feasible-tag ${f.is_feasible ? "ok" : "bad"}`}>
                {f.is_feasible ? "FEASIBLE — safe to present to a planner" : "INFEASIBLE — should never happen"}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
