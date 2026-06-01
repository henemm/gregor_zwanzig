/* Mobile · Trips-Liste
 * Pattern: Card-Stack statt Tabelle. Aktionen kollabieren in "more"-Menü (öffnet Bottom-Sheet).
 * Sticky Filter-Chip-Reihe unter dem Header.
 */

const TRIPS_LIST_M = [
  { id: "khw-403",   name: "KHW 403",                   stages: 13, from: "2026-05-04", to: "2026-05-17", status: "active",    subtitle: "Karnischer Höhenweg" },
  { id: "gr221",     name: "GR221 Mallorca",            stages:  4, from: "2026-02-23", to: "2026-02-26", status: "scheduled", subtitle: "Trockenmauer-Weg" },
  { id: "zillertal", name: "Zillertal mit Steffi",      stages:  1, from: "2025-12-28", to: null,         status: "completed", subtitle: "Wochenende Skitour" },
  { id: "e2e-2",     name: "E2E Test Trip",             stages:  1, from: "2026-04-13", to: null,         status: "draft",     subtitle: "Test-Konfiguration" },
  { id: "e2e-1",     name: "E2E Test Trip",             stages:  1, from: "2026-04-13", to: null,         status: "draft",     subtitle: "Test-Konfiguration" },
];

function ScreenTripsMobile() {
  const [query, setQuery] = React.useState("");
  const [filter, setFilter] = React.useState("all");
  const [sheetOpen, setSheetOpen] = React.useState(false);
  const filtered = TRIPS_LIST_M.filter(t =>
    (filter === "all" || t.status === filter) &&
    t.name.toLowerCase().includes(query.toLowerCase())
  );

  const right = <IconBtn kind="plus" label="Neuer Trip"/>;

  const chips = [
    { id: "all",       label: "Alle",       n: TRIPS_LIST_M.length },
    { id: "active",    label: "Aktiv",      n: 1 },
    { id: "scheduled", label: "Geplant",    n: 1 },
    { id: "completed", label: "Fertig",     n: 1 },
    { id: "draft",     label: "Drafts",     n: 2 },
  ];

  return (
    <MobileShell active="trips" title="Trips" eyebrow="Workspace" right={right} phoneHeight={812}
                 sheet={sheetOpen && <TripActionsSheet onClose={() => setSheetOpen(false)}/>}>
      <ScreenScroll padding={0}>
        {/* Search */}
        <div style={{ padding: "8px 16px 6px" }}>
          <MInput leftIcon="search" placeholder="Trips suchen…" value={query} onChange={e => setQuery(e.target.value)}/>
        </div>

        {/* Filter Chips */}
        <div style={{
          display: "flex", gap: 6, padding: "4px 16px 12px",
          overflowX: "auto", WebkitOverflowScrolling: "touch", scrollbarWidth: "none",
        }}>
          {chips.map(c => {
            const isActive = filter === c.id;
            return (
              <button key={c.id} onClick={() => setFilter(c.id)} style={{
                flexShrink: 0, padding: "8px 12px", minHeight: 36,
                background: isActive ? "var(--g-ink)" : "var(--g-card)",
                color: isActive ? "var(--g-paper)" : "var(--g-ink-2)",
                border: `1px solid ${isActive ? "var(--g-ink)" : "var(--g-rule)"}`,
                borderRadius: "var(--g-r-pill)", cursor: "pointer",
                fontFamily: "var(--g-font-mono)", fontSize: 12, fontWeight: 500,
                letterSpacing: "0.02em", whiteSpace: "nowrap",
                display: "inline-flex", alignItems: "center", gap: 6,
              }}>
                {c.label}
                <span style={{
                  fontSize: 10, padding: "1px 5px", borderRadius: 8,
                  background: isActive ? "rgba(255,255,255,0.18)" : "var(--g-paper-deep)",
                  color: isActive ? "var(--g-paper)" : "var(--g-ink-3)",
                }}>{c.n}</span>
              </button>
            );
          })}
        </div>

        {/* Trip Cards */}
        <div style={{ padding: "0 16px 20px", display: "flex", flexDirection: "column", gap: 10 }}>
          {filtered.map(t => (
            <TripCardM key={t.id} trip={t} onMore={() => setSheetOpen(true)}/>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: "60px 20px", textAlign: "center", color: "var(--g-ink-3)" }}>
              <div style={{ fontSize: 14, marginBottom: 4 }}>Keine Trips gefunden</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>Filter zurücksetzen oder neuen Trip anlegen</div>
            </div>
          )}
        </div>
      </ScreenScroll>
    </MobileShell>
  );
}

function TripCardM({ trip, onMore }) {
  const statusMap = {
    active:    { label: "aktiv",    dot: "var(--g-accent)" },
    scheduled: { label: "geplant",  dot: "var(--g-good)" },
    completed: { label: "fertig",   dot: "var(--g-ink-3)" },
    draft:     { label: "draft",    dot: "var(--g-ink-4)" },
  };
  const st = statusMap[trip.status] || statusMap.draft;
  const range = trip.to ? `${trip.from} → ${trip.to}` : trip.from;
  const isActive = trip.status === "active";

  return (
    <div style={{
      background: "var(--g-card)",
      border: "1px solid var(--g-rule)",
      borderLeft: isActive ? "3px solid var(--g-accent)" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)",
      boxShadow: "var(--g-shadow-1)",
      overflow: "hidden",
    }}>
      <div style={{ padding: "14px 14px 12px", display: "flex", alignItems: "flex-start", gap: 12 }}>
        <span style={{ width: 9, height: 9, borderRadius: "50%", background: st.dot, marginTop: 6, flexShrink: 0 }}/>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 2 }}>
            <span style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.01em", color: "var(--g-ink)" }}>{trip.name}</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.12em" }}>· {st.label}</span>
          </div>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginBottom: 6 }}>{trip.subtitle}</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.02em" }}>
            {range} · {trip.stages} {trip.stages === 1 ? "Etappe" : "Etappen"}
          </div>
        </div>
        <IconBtn kind="more" onClick={onMore} label="Aktionen"/>
      </div>
      {isActive && (
        <div style={{
          display: "flex", gap: 0, borderTop: "1px solid var(--g-rule-soft)",
          background: "var(--g-card-alt)",
        }}>
          <ActionLink label="Briefing senden" icon="send"/>
          <ActionLink label="Vorschau" icon="external"/>
          <ActionLink label="Alerts" icon="bell"/>
        </div>
      )}
    </div>
  );
}

function ActionLink({ label, icon }) {
  return (
    <button style={{
      flex: 1, display: "inline-flex", alignItems: "center", justifyContent: "center",
      gap: 6, padding: "12px 6px", minHeight: 44,
      background: "transparent", border: "none", borderRight: "1px solid var(--g-rule-soft)",
      fontSize: 12, fontWeight: 500, color: "var(--g-ink-2)",
      fontFamily: "var(--g-font-sans)", cursor: "pointer",
    }}>
      <MIcon kind={icon} size={14} color="var(--g-ink-2)"/>
      {label}
    </button>
  );
}

function TripActionsSheet({ onClose }) {
  const items = [
    { icon: "send",   label: "Briefing jetzt senden", sub: "Manueller Trigger" },
    { icon: "external", label: "Email-Vorschau", sub: "So sieht das nächste Briefing aus" },
    { icon: "bell",   label: "Alert-Konfiguration", sub: "Schwellen & Δ-Regeln" },
    { icon: "filter", label: "Wetter-Metriken", sub: "14 Spalten · Preset Alpen" },
    { icon: "edit",   label: "Bearbeiten", sub: "Wegpunkte, Profil, Kanäle" },
    { icon: "trash",  label: "Löschen", danger: true },
  ];
  return (
    <Sheet open onClose={onClose} title="KHW 403" eyebrow="Aktionen · aktiver Trip" snap="half">
      <div style={{ display: "flex", flexDirection: "column" }}>
        {items.map((it, i) => (
          <button key={i} style={{
            display: "flex", alignItems: "center", gap: 14,
            padding: "14px 4px", minHeight: 56,
            background: "transparent", border: "none",
            borderBottom: i < items.length - 1 ? "1px solid var(--g-rule-soft)" : "none",
            cursor: "pointer", textAlign: "left",
          }}>
            <span style={{
              width: 40, height: 40, borderRadius: "var(--g-r-3)",
              background: it.danger ? "rgba(168,50,50,0.08)" : "var(--g-paper-deep)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <MIcon kind={it.icon} size={20} color={it.danger ? "var(--g-bad)" : "var(--g-ink)"}/>
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 500, color: it.danger ? "var(--g-bad)" : "var(--g-ink)" }}>{it.label}</div>
              {it.sub && <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2 }}>{it.sub}</div>}
            </div>
            <MIcon kind="chevron" size={16} color="var(--g-ink-4)"/>
          </button>
        ))}
      </div>
    </Sheet>
  );
}

window.ScreenTripsMobile = ScreenTripsMobile;
window.TripActionsSheet = TripActionsSheet;
