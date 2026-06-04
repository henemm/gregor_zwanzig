/* Screen: Compare-List — Übersicht aller Orts-Vergleiche.
 * ─────────────────────────────────────────────────────────────────────
 * Pattern: Kachel-Grid (Charter §3 v1.1). Umstellung Tabelle → Kacheln
 * am 2026-05-31 (PO-Auftrag).
 *
 * Atomic Design: nutzt die Compare-Domain-Molecules (CompareTile,
 * CompareKebab, compareActions) + Stat (inline) aus molecules.jsx.
 * KEINE Inline-Kachel mehr (Drift-Auflösung). Lokale Reste mit CL_-Prefix.
 *
 * Jede Kachel ist ein eigenständiger Einstiegspunkt:
 *   • Klick auf die Kachel  → Detail-Seite (ScreenCompareDetail)
 *   • Kebab ⋯               → Sekundäraktionen (compareActions)
 *
 * Quelle: MOCK_COMPARE_SUBS (Single-Source, mock-locations.jsx).
 */

function ScreenCompareList() {
  const subs = window.MOCK_COMPARE_SUBS || [];
  const [query, setQuery] = React.useState("");
  const filtered = subs.filter(c => c.name.toLowerCase().includes(query.toLowerCase()));

  const counts = {
    active: subs.filter(c => c.status === "active").length,
    paused: subs.filter(c => c.status === "paused").length,
    draft:  subs.filter(c => c.status === "draft").length,
  };

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="compare"/>
      <main style={{ flex: 1, padding: "32px 40px 60px", overflow: "auto" }}>

        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>
          <div>
            <Eyebrow>Workspace · Orts-Vergleiche</Eyebrow>
            <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}>Orts-Vergleiche</div>
            <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 620 }}>
              Tägliche Briefings, die mehrere Orte gegeneinander stellen und eine
              Empfehlung mitliefern („heute ist Ort X am besten — weil …").
              Einmalig eingerichtet, läuft pro Vergleich automatisch.
            </div>
          </div>
          <Btn variant="primary" size="md" icon={<span style={{ fontSize: 14, lineHeight: 0 }}>+</span>}>
            Neuer Vergleich
          </Btn>
        </div>

        {/* Suche */}
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

        {/* Stats (Stat-Molecule, inline) */}
        <div style={{ display: "flex", gap: 24, marginBottom: 22, paddingBottom: 16, borderBottom: "1px solid var(--g-rule-soft)" }}>
          <Stat label="Aktiv"    value={counts.active} layout="inline" tone="accent" mono/>
          <Stat label="Pausiert" value={counts.paused} layout="inline" mono/>
          <Stat label="Drafts"   value={counts.draft}  layout="inline" mono/>
        </div>

        {/* Kachel-Grid */}
        {filtered.length === 0 ? (
          <Card padding={40} style={{ textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}>
            Keine Vergleiche für »{query}« gefunden.
          </Card>
        ) : (
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))", gap: 16 }}>
            {filtered.map(c => (
              <CompareTile
                key={c.id}
                sub={c}
                trailing={<CompareKebab items={compareActions(c.status)} btnSize={28}/>}
              />
            ))}
          </div>
        )}

        <div style={{ marginTop: 16, fontSize: 11, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em" }}>
          {filtered.length} von {subs.length} Vergleichen
        </div>
      </main>
    </div>
  );
}

window.ScreenCompareList = ScreenCompareList;
