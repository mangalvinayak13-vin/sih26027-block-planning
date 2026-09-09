// This page exists purely to explain the domain to a non-technical
// evaluator, in the evaluator's own words as much as possible — separate
// from the dashboard, so a demo can open on THIS page first before
// touching any data or solver output. Every evaluator's first question
// is "wait, what even IS a block?", so this has to exist as its own,
// obvious, first stop.

const BLOCK_TYPES = [
  {
    name: "Traffic block",
    owner: "Traffic / Operating department",
    why: "General operational reasons — e.g. temporarily closing a section for yard remodeling or operational convenience.",
  },
  {
    name: "Engineering block",
    owner: "Engineering department",
    why: "Track & civil maintenance — rail repair, ballast renewal, tamping, bridge work.",
  },
  {
    name: "S&T block",
    owner: "Signalling & Telecommunications department",
    why: "Signal, interlocking, and telecom cable maintenance.",
  },
  {
    name: "Power / TRD block",
    owner: "Traction Distribution department",
    why: "Overhead electric line (OHE) maintenance — the wires that power electric trains.",
  },
];

const PIPELINE_STAGES = [
  ["1. Data Sources", "Timetable, asset status, maintenance requirements, historical block data, operational constraints."],
  ["2. Preprocessing & Validation", "Clean and sanity-check the raw data (e.g. reject a block whose end time is before its start time) before anything touches the solver."],
  ["3. Constraint Modelling", "Turn safety, maintenance-window, timetable, and resource rules into CP-SAT constraints."],
  ["4. Optimization Engine", "Google OR-Tools CP-SAT solves for the plan that maximizes total track-time returned to traffic, subject to every constraint above. Not a neural network — a constraint solver that can PROVE its answer is safe."],
  ["5. Conflict Detection & Priority Handling", "When two departments want the same section/time, a criticality/priority score (not arbitrary choice) decides who wins."],
  ["6. Candidate Plans -> Feasibility Validation", "Generate several different valid plans, and independently re-check each one really does respect every hard rule."],
  ["7. Ranked Recommended Plan", "Return the candidate plans best-first, with the reasoning behind every granted/rejected request visible."],
  ["8. Planner Dashboard", "A human planner reviews the ranked plans and approves or rejects — the system never confirms a block on its own."],
];

export default function WhatIsABlock() {
  return (
    <div className="page">
      <h1>What is a "block"?</h1>
      <p className="lede">
        A <strong>block</strong> is a time-bound restriction on a section of railway track during
        which no train movement is permitted on that section. Blocks exist so maintenance work —
        track repairs, signalling work, overhead power line work — can happen safely, without a
        train running into a work gang on the track.
      </p>

      <h2>The four kinds of block</h2>
      <div className="cards">
        {BLOCK_TYPES.map((b) => (
          <div className="card" key={b.name}>
            <h3>{b.name}</h3>
            <p className="muted">{b.owner}</p>
            <p>{b.why}</p>
          </div>
        ))}
      </div>

      <h2>The problem this project solves</h2>
      <p>
        Today, each department requests its blocks separately through a system called{" "}
        <strong>BDMS</strong> (Block Demand Management System), while train schedules and corridor
        occupancy live in separate systems (<strong>TMS, SMMS, TDMS, Control Office Application /
        COA</strong>). Nobody cross-checks these against each other in one place — so you get
        overlapping block requests on the same section, blocks granted on track that's actually
        busy with trains, and departments negotiating clashes ad hoc.
      </p>
      <p>
        This project is a <strong>decision-support layer</strong> that takes all pending block
        demands, the timetable, and corridor occupancy, checks them against each other, resolves
        conflicts by a priority score, and hands a human planner a ranked shortlist of feasible
        plans to approve.{" "}
        <strong>It does not decide anything on its own — the planner always makes the final call.</strong>
      </p>

      <h2>The pipeline, stage by stage</h2>
      <ol className="pipeline">
        {PIPELINE_STAGES.map(([title, desc]) => (
          <li key={title}>
            <strong>{title}</strong>
            <div className="muted">{desc}</div>
          </li>
        ))}
      </ol>
    </div>
  );
}
