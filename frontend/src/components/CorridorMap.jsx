// Renders the physical corridor as a horizontal line of stations
// connected by sections — a map, not a table — because "which section is
// which" is spatial information a table forces the reader to translate
// back into a mental picture anyway. Optionally interactive: pass
// `onSelectSection` + `selectedSectionId` to let a page use this as a
// section picker (Stage 3 does this).
export default function CorridorMap({ corridor, onSelectSection, selectedSectionId, sectionBadge }) {
  if (!corridor) return null;
  return (
    <div className="corridor-map">
      {corridor.stations.map((s, i) => (
        <div className="corridor-map-item" key={s.code}>
          <div className="corridor-station">{s.name}</div>
          {i < corridor.stations.length - 1 && (
            <button
              className={`corridor-section ${corridor.sections[i].id === selectedSectionId ? "selected" : ""}`}
              onClick={() => onSelectSection?.(corridor.sections[i].id)}
              disabled={!onSelectSection}
            >
              <span className="corridor-section-id">{corridor.sections[i].id}</span>
              <span className="corridor-section-km">{corridor.sections[i].length_km} km</span>
              {sectionBadge && <span className="corridor-section-badge">{sectionBadge(corridor.sections[i].id)}</span>}
            </button>
          )}
        </div>
      ))}
    </div>
  );
}
