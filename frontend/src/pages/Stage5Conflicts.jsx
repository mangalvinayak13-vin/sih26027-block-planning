import { useEffect, useState } from "react";
import { api } from "../api";
import BarChart from "../components/BarChart";
import { DEPT_COLORS } from "../constants";
import { groupBy, latestRunPlans } from "../utils";

// STAGE 5 — CONFLICT DETECTION & PRIORITY HANDLING.
// When two departments want the same section (or the same gang) at an
// overlapping time, something has to decide who wins — this page shows
// exactly that decision, section by section, as a bar chart of priority
// scores with the actual winner highlighted. The score itself comes from
// a small hand-written formula (backend/app/priority/scoring.py), not a
// trained model — see Stage 4 for why that boundary matters.

export default function Stage5Conflicts() {
  const [plan, setPlan] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .listPlans()
      .then(async (all) => {
        const plans = latestRunPlans(all);
        if (plans.length === 0) {
          setError("No solved plans yet — go to Stage 4 and run the solver first.");
          return;
        }
        const detail = await api.getPlan(plans[0].id);
        setPlan(detail);
      })
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="page">{error}</div>;
  if (!plan) return <div className="page">Loading...</div>;

  const bySection = groupBy(plan.items, (i) => i.section_id);
  const contestedSections = Object.entries(bySection).filter(([, items]) => items.length > 1);
  const cleanSections = Object.entries(bySection).filter(([, items]) => items.length === 1);

  return (
    <div className="page">
      <div className="stage-kicker">Stage 5 of 8</div>
      <h1>Conflict Detection & Priority Handling</h1>
      <p className="lede">
        The priority score blends three things: <strong>how overdue</strong> the maintenance is
        against its department's normal cycle (40%), <strong>defect severity</strong> 1-5 (35%),
        and a <strong>safety-risk flag</strong> (25%). Below, every section with more than one
        request competing for it — the winner is whichever request the solver actually granted
        (bordered), not necessarily the single highest score alone, since gang/timetable
        constraints and combined value across requests matter too.
      </p>

      <h2>Contested sections ({contestedSections.length})</h2>
      {contestedSections.map(([sectionId, items]) => (
        <div className="card conflict-card" key={sectionId}>
          <h3>{sectionId}</h3>
          <BarChart
            items={items
              .sort((a, b) => b.priority_score - a.priority_score)
              .map((i) => ({
                id: i.demand_id,
                label: `${i.demand_id} · ${i.department}`,
                sublabel: i.granted ? "GRANTED" : undefined,
                value: i.priority_score,
                color: i.granted ? DEPT_COLORS[i.department] : "#d1d5db",
              }))}
            maxValue={1}
            valueFormat={(v) => v.toFixed(2)}
          />
          <table className="demand-table small">
            <tbody>
              {items.map((i) => (
                <tr key={i.demand_id} className={i.granted ? "granted" : "rejected"}>
                  <td>{i.granted ? "✅" : "❌"}</td>
                  <td>{i.demand_id}</td>
                  <td>{i.department}</td>
                  <td className="reason">{i.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}

      <h2>Uncontested sections ({cleanSections.length})</h2>
      <p className="muted">
        Only one request touched these — no priority conflict between departments to resolve
        (though it may still have lost to a real train, see Stage 3).
      </p>
      <div className="chip-row">
        {cleanSections.map(([sectionId, items]) => (
          <div key={sectionId} className={`chip ${items[0].granted ? "chip-pass" : "chip-fail"}`}>
            {items[0].granted ? "✅" : "❌"} {sectionId}: {items[0].demand_id} ({items[0].department})
          </div>
        ))}
      </div>
    </div>
  );
}
