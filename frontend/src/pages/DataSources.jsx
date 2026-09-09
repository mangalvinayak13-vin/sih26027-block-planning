import { useEffect, useState } from "react";
import { api } from "../api";

// This is the "honesty panel" — it exists so that if an evaluator asks
// "is this real data or did you make it up?", there's a live, on-screen
// answer instead of us having to explain it verbally. The content comes
// straight from the backend's /api/data-sources endpoint (see
// backend/app/api/routes.py) so the UI can never drift out of sync with
// what the backend actually did.

export default function DataSources() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getDataSources().then(setData).catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="page">Failed to load: {error}</div>;
  if (!data) return <div className="page">Loading...</div>;

  return (
    <div className="page">
      <h1>Data Sources</h1>
      <p className="lede">
        This prototype uses real Indian Railways data wherever it's publicly available, and
        clearly-labelled synthetic data everywhere it isn't — because IR's internal BDMS/TMS/SMMS/
        TDMS/COA systems aren't public. Every record shown elsewhere in this app carries a{" "}
        <code>data_source</code> tag of <span className="badge real">real</span> or{" "}
        <span className="badge synthetic">synthetic</span> so this is checkable, not just claimed.
      </p>

      <h2><span className="badge real">Real</span> data</h2>
      {data.real.map((d) => (
        <div className="card" key={d.name}>
          <h3>{d.name}</h3>
          <p className="muted">
            Source:{" "}
            <a href={d.url} target="_blank" rel="noreferrer">
              {d.source}
            </a>
          </p>
          <p>{d.used_for}</p>
        </div>
      ))}

      <h2><span className="badge synthetic">Synthetic</span> data</h2>
      {data.synthetic.map((d) => (
        <div className="card" key={d.name}>
          <h3>{d.name}</h3>
          <p className="muted">Why synthetic: {d.reason_not_public}</p>
          <p>{d.used_for}</p>
        </div>
      ))}
    </div>
  );
}
