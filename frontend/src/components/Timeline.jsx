import { formatMinutes } from "../api";

// A hand-rolled Gantt-style timeline using plain flexbox/CSS, not a
// charting library or SVG. WHY: every pipeline stage needs to show
// "these things happen over overlapping TIME WINDOWS on a shared
// resource" (a track section, a gang) — a fixed label column plus a
// relatively-positioned "track" div per row, with each bar placed by
// percentage-of-width, does exactly that and stays readable/responsive
// without pulling in a dependency for one custom chart shape.
//
// rows: [{ id, label, start, end, color, conflict?, dimmed?, sublabel? }]
// rangeStart/rangeEnd: the time window (minutes-from-midnight) to plot.
export default function Timeline({ rows, rangeStart, rangeEnd, onHoverRow }) {
  const totalMinutes = rangeEnd - rangeStart;

  function pct(minute) {
    return Math.max(0, Math.min(100, ((minute - rangeStart) / totalMinutes) * 100));
  }

  const startHour = Math.ceil(rangeStart / 60);
  const endHour = Math.floor(rangeEnd / 60);
  const gridMinutes = [];
  for (let h = startHour; h <= endHour; h += 2) gridMinutes.push(h * 60);

  return (
    <div className="timeline">
      {rows.length === 0 && <p className="muted">Nothing scheduled in this window.</p>}
      {rows.map((row) => (
        <div className="timeline-row" key={row.id} onMouseEnter={() => onHoverRow?.(row)}>
          <div className="timeline-label">
            {row.label}
            {row.sublabel && <span className="timeline-sublabel">{row.sublabel}</span>}
          </div>
          <div className="timeline-track">
            {gridMinutes.map((m) => (
              <div key={m} className="timeline-gridline" style={{ left: `${pct(m)}%` }} />
            ))}
            <div
              className={`timeline-bar ${row.conflict ? "conflict" : ""} ${row.dimmed ? "dimmed" : ""}`}
              style={{
                left: `${pct(row.start)}%`,
                width: `${Math.max(pct(row.end) - pct(row.start), 0.8)}%`,
                background: row.color,
              }}
              title={`${row.label}: ${formatMinutes(row.start)} – ${formatMinutes(row.end)}`}
            />
          </div>
        </div>
      ))}
      <div className="timeline-axis">
        <div className="timeline-label" />
        <div className="timeline-track">
          {gridMinutes.map((m) => (
            <span key={m} className="timeline-axis-label" style={{ left: `${pct(m)}%` }}>
              {formatMinutes(m)}
            </span>
          ))}
        </div>
      </div>
    </div>
  );
}
