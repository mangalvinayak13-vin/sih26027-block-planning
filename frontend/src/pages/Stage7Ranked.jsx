import { useEffect, useState } from "react";
import { api } from "../api";
import BarChart from "../components/BarChart";
import { latestRunPlans } from "../utils";

// STAGE 7 — RANKED RECOMMENDED PLAN.
// This is the actual deliverable of the pipeline: not one answer handed
// down as fact, but several ranked options with the reasoning attached,
// because the planner (Stage 8) — not the algorithm — makes the final
// call. This page's job is to make rank #1's advantage over #2 and #3
// legible: what specifically does it grant that the others don't?

export default function Stage7Ranked() {
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

  const objectiveChart = plans.map((p) => ({
    id: p.id,
    label: `#${p.rank}${p.rank === 1 ? " (recommended)" : ""}`,
    value: p.objective_value,
    color: p.rank === 1 ? "#047857" : "#9ca3af",
  }));

  const best = plans[0];

  return (
    <div className="page">
      <div className="stage-kicker">Stage 7 of 8</div>
      <h1>Ranked Recommended Plan</h1>
      <p className="lede">
        Best plan first, by objective score (track-time returned, weighted by priority) — but
        every plan shown is independently feasible (Stage 6), so a planner is free to pick #2 or
        #3 instead if there's a real-world reason #1 doesn't work for them.
      </p>

      <h2>Objective score by rank</h2>
      <BarChart items={objectiveChart} valueFormat={(v) => v.toFixed(0)} />

      {plans.slice(1).map((plan) => {
        const diffs = best.items.filter((bi) => {
          const other = plan.items.find((pi) => pi.demand_id === bi.demand_id);
          return other && other.granted !== bi.granted;
        });
        return (
          <div className="card" key={plan.id}>
            <h3>Why #1 beats #{plan.rank}</h3>
            <p className="muted">
              #1 scores {(best.objective_value - plan.objective_value).toFixed(0)} points higher.
              The difference comes down to {diffs.length} request{diffs.length !== 1 ? "s" : ""}:
            </p>
            <ul>
              {diffs.map((bi) => (
                <li key={bi.demand_id}>
                  <strong>{bi.demand_id}</strong> ({bi.department}, priority {bi.priority_score.toFixed(2)}):{" "}
                  {bi.granted ? "granted in #1, not in this plan" : "granted in this plan, not in #1"}
                </li>
              ))}
            </ul>
          </div>
        );
      })}

      <h2>Recommended plan (#1) — full reasoning</h2>
      <table className="demand-table">
        <thead><tr><th>Outcome</th><th>ID</th><th>Dept</th><th>Priority</th><th>Why</th></tr></thead>
        <tbody>
          {best.items
            .sort((a, b) => Number(b.granted) - Number(a.granted) || b.priority_score - a.priority_score)
            .map((i) => (
              <tr key={i.demand_id} className={i.granted ? "granted" : "rejected"}>
                <td>{i.granted ? "✅" : "❌"}</td>
                <td>{i.demand_id}</td>
                <td>{i.department}</td>
                <td>{i.priority_score.toFixed(2)}</td>
                <td className="reason">{i.reason}</td>
              </tr>
            ))}
        </tbody>
      </table>
    </div>
  );
}
