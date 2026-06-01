/* Screen: Trips — Übersichtsliste aller Trips.
 * Tabelle mit Name, Etappen, Zeitraum, Aktionen (Alert / Briefing-jetzt /
 * Test-Senden / Vorschau / Bearbeiten / Löschen).
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
              Alle aktiven, geplanten und abgeschlossenen Mehrtagestouren. Pro Trip kannst du Alerts justieren, ein Briefing direkt schicken oder die Email-Vorschau öffnen.
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
  const range = trip.to ? `${trip.from} — ${trip.to}` : trip.from;
  const statusMap = {
    active:    { label: "aktiv",     dot: "var(--g-accent)" },
    scheduled: { label: "geplant",   dot: "#3d6b3a" },
    completed: { label: "fertig",    dot: "var(--g-ink-3)" },
    draft:     { label: "draft",     dot: "var(--g-ink-4)" },
  };
  const st = statusMap[trip.status] || statusMap.draft;

  return (
    <div style={{
      display: "grid", gridTemplateColumns: "1.6fr 0.8fr 1.4fr auto",
      alignItems: "center", padding: "16px 20px",
      background: alt ? "var(--g-paper-deep)" : "transparent",
      borderBottom: "1px solid var(--g-rule-soft)", gap: 0,
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
      <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
        <ActionBtn kind="alert"   title="Alert-Konfiguration"/>
        <ActionBtn kind="weather" title="Aktuelles Wetter"/>
        <ActionBtn kind="play"    title="Briefing jetzt senden"/>
        <ActionBtn kind="preview" title="Email-Vorschau"/>
        <span style={{ width: 1, height: 18, background: "var(--g-rule)", margin: "0 4px" }}/>
        <ActionBtn kind="edit"    title="Bearbeiten"/>
        <ActionBtn kind="trash"   title="Löschen" danger/>
      </div>
    </div>
  );
}

function ActionBtn({ kind, title, danger }) {
  const c = danger ? "var(--g-ink-3)" : "var(--g-ink-2)";
  const ic = {
    alert:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></svg>,
    weather: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3.5"/><path d="M12 4v1.5M12 18.5V20M4 12h1.5M18.5 12H20M6 6l1 1M17 17l1 1M6 18l1-1M17 7l1-1"/></svg>,
    play:    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"><path d="M7 5l12 7-12 7z"/></svg>,
    preview: <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"><path d="M7 5l12 7-12 7z" fill="none"/><line x1="14" y1="12" x2="20" y2="12" opacity="0.4"/></svg>,
    edit:    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4l6 6L9 21H3v-6z"/></svg>,
    trash:   <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/></svg>,
  };
  return (
    <button title={title} style={{
      width: 30, height: 30, display: "inline-flex", alignItems: "center", justifyContent: "center",
      background: "transparent", border: "1px solid var(--g-rule-soft)",
      borderRadius: "var(--g-r-2)", cursor: "pointer",
    }}>{ic[kind]}</button>
  );
}

window.ScreenTrips = ScreenTrips;
