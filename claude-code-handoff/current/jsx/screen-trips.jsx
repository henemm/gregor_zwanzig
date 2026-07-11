/* Screen: Trips — Übersichtsliste aller Trips.
 * Cockpit-Prinzip: ganze Zeile ist klickbar → öffnet Trip-Detail/Setup.
 * Aktionen kollabieren in EIN Overflow-Menü (kein Icon-Geschwader pro Zeile);
 * der aktive Trip zeigt zusätzlich eine inline Quick-Action „Briefing senden".
 * Spiegelt das kanonische Mobile-Muster (TripCardM + TripActionsSheet).
 */

const TRIPS_LIST = [
  { id: "khw-403",   name: "KHW 403",                   stages: 13, from: "2026-05-04", to: "2026-05-17", status: "active" },
  { id: "gr221",     name: "GR221 Mallorca",            stages:  4, from: "2026-02-23", to: "2026-02-26", status: "scheduled" },
  { id: "zillertal", name: "Zillertal mit Steffi",      stages:  1, from: "2025-12-28", to: null,         status: "completed" },
  { id: "e2e-2",     name: "E2E Test Trip",             stages:  1, from: "2026-04-13", to: null,         status: "draft" },
  { id: "e2e-1",     name: "E2E Test Trip",             stages:  1, from: "2026-04-13", to: null,         status: "draft" },
];

function ScreenTrips() {
  const [query, setQuery] = React.useState("");
  const filtered = TRIPS_LIST.filter(t => t.name.toLowerCase().includes(query.toLowerCase()));

  return (
    <div style={{ display: "flex", height: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="trips"/>
      <main style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}>

        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>
          <div>
            <Eyebrow>Workspace · Trips</Eyebrow>
            <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}>Trips</div>
            <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 560 }}>
              Alle aktiven, geplanten und abgeschlossenen Mehrtages-Trips. Pro Trip kannst du Alerts justieren, ein Briefing direkt schicken oder die Email-Vorschau öffnen.
            </div>
          </div>
          <Btn variant="primary" size="md" icon={<span style={{ fontSize: 14, lineHeight: 0 }}>+</span>}>Neuer Trip</Btn>
        </div>

        {/* Search */}
        <div style={{ position: "relative", maxWidth: 380, marginBottom: 20 }}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" strokeWidth="2"
               style={{ position: "absolute", top: 11, left: 12 }}>
            <circle cx="11" cy="11" r="7"/><path d="M20 20l-3.5-3.5"/>
          </svg>
          <input value={query} onChange={e => setQuery(e.target.value)} placeholder="Suchen…"
                 style={{
                   width: "100%", padding: "9px 14px 9px 34px",
                   border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)",
                   background: "var(--g-card)", fontSize: 13, fontFamily: "var(--g-font-sans)",
                   color: "var(--g-ink)", outline: "none",
                 }}/>
        </div>

        {/* Stats summary */}
        <div style={{ display: "flex", gap: 24, marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid var(--g-rule-soft)" }}>
          <SummaryStat label="Aktiv"        value="1" tone="accent"/>
          <SummaryStat label="Geplant"      value="1"/>
          <SummaryStat label="Abgeschlossen" value="1"/>
          <SummaryStat label="Drafts"       value="2"/>
        </div>

        {/* Table */}
        <Card padding={0} style={{ overflow: "hidden" }}>
          <div style={{ display: "grid", gridTemplateColumns: "1.6fr 0.8fr 1.4fr auto", gap: 0,
                        padding: "12px 20px", background: "var(--g-paper-deep)",
                        fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.18em",
                        textTransform: "uppercase", color: "var(--g-ink-3)", fontWeight: 500,
                        borderBottom: "1px solid var(--g-rule)" }}>
            <div>Name</div>
            <div>Etappen</div>
            <div>Zeitraum</div>
            <div style={{ textAlign: "right" }}>Aktionen</div>
          </div>
          {filtered.map((t, i) => (
            <TripRow key={t.id} trip={t} alt={i % 2 === 1}/>
          ))}
          {filtered.length === 0 && (
            <div style={{ padding: 40, textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}>
              Keine Trips für »{query}« gefunden.
            </div>
          )}
        </Card>

        <div style={{ marginTop: 14, fontSize: 11, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em" }}>
          {filtered.length} von {TRIPS_LIST.length} Trips
        </div>
      </main>
    </div>
  );
}

function SummaryStat({ label, value, tone }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
      <span style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em",
                     color: tone === "accent" ? "var(--g-accent)" : "var(--g-ink)" }}>{value}</span>
      <span style={{ fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.16em",
                     textTransform: "uppercase", color: "var(--g-ink-3)" }}>{label}</span>
    </div>
  );
}

function TripRow({ trip, alt }) {
  const [hover, setHover] = React.useState(false);
  const [menuOpen, setMenuOpen] = React.useState(false);
  const range = trip.to ? `${trip.from} — ${trip.to}` : trip.from;
  const statusMap = {
    active:    { label: "aktiv",     dot: "var(--g-accent)" },
    scheduled: { label: "geplant",   dot: "#3d6b3a" },
    completed: { label: "fertig",    dot: "var(--g-ink-3)" },
    draft:     { label: "draft",     dot: "var(--g-ink-4)" },
  };
  const st = statusMap[trip.status] || statusMap.draft;
  const isActive = trip.status === "active";
  const stop = e => e.stopPropagation();

  return (
    <div
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      role="button" tabIndex={0} title={`${trip.name} öffnen`}
      style={{
        display: "grid", gridTemplateColumns: "1.6fr 0.8fr 1.4fr auto",
        alignItems: "center", padding: "16px 20px",
        background: hover ? "var(--g-card-alt, #f1eee6)" : (alt ? "var(--g-paper-deep)" : "transparent"),
        borderBottom: "1px solid var(--g-rule-soft)", gap: 0,
        cursor: "pointer", transition: "background 120ms",
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: st.dot, flexShrink: 0 }}/>
        <span style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em" }}>{trip.name}</span>
        <span style={{ fontSize: 10, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-4)",
                       textTransform: "uppercase", letterSpacing: "0.16em" }}>· {st.label}</span>
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}>
        {trip.stages} {trip.stages === 1 ? "Etappe" : "Etappen"}
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.02em" }}>
        {range}
      </div>
      <div onClick={stop} style={{ display: "flex", gap: 8, justifyContent: "flex-end", alignItems: "center", position: "relative" }}>
        {isActive && (
          <Btn variant="ghost" size="sm" icon={tripsIcon("play", "var(--g-ink)")}>Briefing senden</Btn>
        )}
        <button
          title="Aktionen" aria-haspopup="menu" aria-expanded={menuOpen}
          onClick={() => setMenuOpen(o => !o)}
          style={{
            width: 32, height: 32, display: "inline-flex", alignItems: "center", justifyContent: "center",
            background: menuOpen ? "var(--g-paper-deep)" : "transparent",
            border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", cursor: "pointer",
          }}>
          {tripsIcon("more", "var(--g-ink-2)")}
        </button>
        <span style={{ display: "inline-flex", color: hover ? "var(--g-ink-3)" : "var(--g-ink-4)", marginLeft: 2 }}>
          {tripsIcon("chevron", "currentColor")}
        </span>
        {menuOpen && <TripsActionsMenu trip={trip} onClose={() => setMenuOpen(false)}/>}
      </div>
    </div>
  );
}

/* Overflow-Aktionsmenü — Desktop-Pendant zum Mobile TripActionsSheet.
 * Gleiche Item-Liste, als anker-positioniertes Popover. */
function TripsActionsMenu({ trip, onClose }) {
  const items = [
    { kind: "play",    label: "Briefing jetzt senden" },
    { kind: "preview", label: "Email-Vorschau" },
    { kind: "alert",   label: "Alert-Konfiguration" },
    { kind: "weather", label: "Wetter-Metriken" },
    { kind: "edit",    label: "Bearbeiten" },
    { kind: "trash",   label: "Löschen", danger: true },
  ];
  return (
    <React.Fragment>
      <div onClick={onClose} style={{ position: "fixed", inset: 0, zIndex: 40 }}/>
      <div role="menu" style={{
        position: "absolute", top: "calc(100% + 6px)", right: 0, zIndex: 41,
        minWidth: 232, background: "var(--g-card)", border: "1px solid var(--g-rule)",
        borderRadius: "var(--g-r-3)", boxShadow: "var(--g-shadow-2, 0 8px 28px rgba(30,26,18,.16))",
        padding: 6, overflow: "hidden",
      }}>
        {items.map((it, i) => (
          <React.Fragment key={it.kind}>
            {it.danger && <div style={{ height: 1, background: "var(--g-rule-soft)", margin: "6px 8px" }}/>}
            <button role="menuitem" onClick={onClose} style={{
              display: "flex", alignItems: "center", gap: 10, width: "100%",
              padding: "9px 10px", minHeight: 40, textAlign: "left",
              background: "transparent", border: "none", borderRadius: "var(--g-r-2)",
              cursor: "pointer", fontSize: 13, fontFamily: "var(--g-font-sans)",
              color: it.danger ? "var(--g-bad, #a83232)" : "var(--g-ink)",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "var(--g-paper-deep)"}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
              <span style={{ display: "inline-flex", flexShrink: 0 }}>
                {tripsIcon(it.kind, it.danger ? "var(--g-bad, #a83232)" : "var(--g-ink-2)")}
              </span>
              {it.label}
            </button>
          </React.Fragment>
        ))}
      </div>
    </React.Fragment>
  );
}

function tripsIcon(kind, c = "var(--g-ink-2)") {
  const p = { width: 15, height: 15, viewBox: "0 0 24 24", fill: "none", stroke: c,
              strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" };
  const map = {
    alert:   <svg {...p}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></svg>,
    weather: <svg {...p}><circle cx="12" cy="12" r="3.5"/><path d="M12 4v1.5M12 18.5V20M4 12h1.5M18.5 12H20M6 6l1 1M17 17l1 1M6 18l1-1M17 7l1-1"/></svg>,
    play:    <svg {...p} strokeLinecap="round"><path d="M7 5l12 7-12 7z"/></svg>,
    preview: <svg {...p}><path d="M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7-10-7-10-7z"/><circle cx="12" cy="12" r="3"/></svg>,
    edit:    <svg {...p}><path d="M14 4l6 6L9 21H3v-6z"/></svg>,
    trash:   <svg {...p}><path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/></svg>,
    more:    <svg {...p}><circle cx="5" cy="12" r="1.4" fill={c} stroke="none"/><circle cx="12" cy="12" r="1.4" fill={c} stroke="none"/><circle cx="19" cy="12" r="1.4" fill={c} stroke="none"/></svg>,
    chevron: <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M9 6l6 6-6 6"/></svg>,
  };
  return map[kind] || null;
}

window.ScreenTrips = ScreenTrips;
