// A simple horizontal bar chart, hand-rolled the same way as Timeline —
// each bar is just a div whose width is a percentage of the largest
// value in the set. Used wherever we need to compare a handful of
// numbers visually (priority scores, objective values, track-time
// returned) instead of making the evaluator read a table of numbers.
//
// items: [{ id, label, value, color, sublabel? }]
export default function BarChart({ items, maxValue, valueFormat = (v) => v }) {
  const max = maxValue ?? Math.max(...items.map((i) => i.value), 1);
  return (
    <div className="barchart">
      {items.map((item) => (
        <div className="barchart-row" key={item.id}>
          <div className="barchart-label">
            {item.label}
            {item.sublabel && <span className="barchart-sublabel">{item.sublabel}</span>}
          </div>
          <div className="barchart-track">
            <div
              className="barchart-bar"
              style={{ width: `${Math.max((item.value / max) * 100, 2)}%`, background: item.color }}
            />
          </div>
          <div className="barchart-value">{valueFormat(item.value)}</div>
        </div>
      ))}
    </div>
  );
}
