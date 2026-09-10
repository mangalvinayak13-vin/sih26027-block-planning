import { useState } from "react";
import { api } from "../api";
import { latestRunPlans } from "../utils";

// STAGE 4 — OPTIMIZATION ENGINE.
// This is the only page that actually runs the solver. Google OR-Tools
// CP-SAT — a constraint solver, not a neural network — searches for the
// assignment of "granted / not granted" to every block demand that
// respects every Stage-3 constraint and maximizes total prioritized
// track-time. We show the REAL numbers from that run (not a canned
// screenshot) so "it ran a solver" is something you can point at, not
// just claim.

export default function Stage4Optimization() {
  const [solving, setSolving] = useState(false);
  const [stats, setStats] = useState(null);
  const [error, setError] = useState(null);

  async function runSolver() {
    setSolving(true);
    setError(null);
    try {
      await api.solvePlans();
      const all = await api.listPlans();
      const plans = latestRunPlans(all);
      setStats(plans[0]);
    } catch (e) {
      setError(e.message);
    } finally {
      setSolving(false);
    }
  }

  const s = stats?.solver_stats;

  return (
    <div className="page">
      <div className="stage-kicker">Stage 4 of 8</div>
      <h1>Optimization Engine</h1>
      <p className="lede">
        Objective: <code>maximize Σ duration × (1 + 4 × priority_score) × granted</code> for every
        block demand, subject to every hard constraint from Stage 3. The "×4" deliberately makes
        priority dominate — the goal is track-time returned to traffic, but a single
        safety-critical request should still usually beat two unrelated routine ones combined.
      </p>

      <button className="solve-btn" disabled={solving} onClick={runSolver}>
        {solving ? "Running CP-SAT solver..." : "▶ Run CP-SAT Solver"}
      </button>
      {error && <p className="error">Error: {error}</p>}

      {s && (
        <>
          <h2>What just happened, in numbers</h2>
          <div className="stat-grid">
            <div className="stat-tile">
              <div className="stat-number">{s.status}</div>
              <div className="stat-label">Solver status</div>
            </div>
            <div className="stat-tile">
              <div className="stat-number">{s.solve_time_ms} ms</div>
              <div className="stat-label">Wall-clock solve time</div>
            </div>
            <div className="stat-tile">
              <div className="stat-number">{s.num_variables}</div>
              <div className="stat-label">Decision variables (1 boolean per block demand)</div>
            </div>
            <div className="stat-tile">
              <div className="stat-number">{s.num_section_noverlap_groups}</div>
              <div className="stat-label">Section NoOverlap constraint groups</div>
            </div>
            <div className="stat-tile">
              <div className="stat-number">{s.num_gang_noverlap_groups}</div>
              <div className="stat-label">Gang NoOverlap constraint groups</div>
            </div>
            <div className="stat-tile">
              <div className="stat-number">{s.num_train_forced_zero}</div>
              <div className="stat-label">Demands forced off by a real train clash</div>
            </div>
          </div>

          <h2>Best plan found this run</h2>
          <div className="stat-grid">
            <div className="stat-tile">
              <div className="stat-number">{stats.objective_value.toFixed(0)}</div>
              <div className="stat-label">Objective score</div>
            </div>
            <div className="stat-tile">
              <div className="stat-number">{stats.total_track_time_returned_min} min</div>
              <div className="stat-label">Track-time returned to maintenance</div>
            </div>
          </div>
          <p className="muted">
            Continue to Stage 5 (Conflict Detection) and Stage 6 (Candidate Plans) to see WHY the
            solver granted what it granted.
          </p>
        </>
      )}

      <h2>Why a constraint solver, not a neural network?</h2>
      <p>
        "No two blocks may use the same track at the same time" is a hard logical rule, not a
        pattern to be learned from data. CP-SAT can <strong>prove</strong> a returned plan
        satisfies every constraint; a neural network could only estimate one and might be wrong —
        unacceptable when the constraint is a safety interlocking rule. A small hand-written
        formula is allowed to score maintenance urgency (see Stage 5), but it only ever feeds a
        number into this objective — it never assigns the plan itself.
      </p>
    </div>
  );
}
