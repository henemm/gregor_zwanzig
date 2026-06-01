/* Screen: Compare-Detail (Desktop) — Klick-Ziel einer Orts-Vergleich-Kachel.
 * ─────────────────────────────────────────────────────────────────────
 * Pattern: Detail-Seite (Charter §3 v1.1).
 *
 * Grundverständnis (CLAUDE.md): Die Web-App richtet ein und überwacht —
 * sie ist KEIN Lese-Medium. Diese Seite zeigt Setup + Monitoring + Aktionen,
 * NICHT das Tages-Briefing. Die Briefing-Vorschau ist ein Verifikations-Tool.
 *
 * Atomic Design: nutzt die Compare-Domain-Molecules (CompareStatusPill,
 * CompareKebab, CompareLocationRow, CompareIdealRow, CompareLayoutRow,
 * compareActions) + DetailRow + Card/Btn/Pill/Eyebrow/Dot aus der Library.
 * Lokale Reste tragen CD_-Prefix (Babel-Scope-Disziplin).
 */

const CD_CHANNEL_LABEL = { email: "Email", signal: "Signal", telegram: "Telegram", sms: "SMS" };

function ScreenCompareDetail({ subId = "skitour-hochkoenig", menuOpen = false }) {
  const sub = (window.MOCK_COMPARE_SUBS || []).find(s => s.id === subId)
            || (window.MOCK_COMPARE_SUBS || [])[0];
  if (!sub) return null;

  const active = sub.status === "active";
  const locs = sub.locationIds
    .map(id => (window.MOCK_LOCATIONS || []).find(l => l.id === id))
    .filter(Boolean);
  /* Header-Kebab: „Bearbeiten" ist Primäraktion → aus dem Menü filtern. */
  const headerActions = compareActions(sub.status).filter(a => a.key !== "edit");

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="compare"/>
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.12}/>

        {/* ── Topbar: Breadcrumb + Header + Aktionen ───────────────── */}
        <div style={{
          position: "relative", padding: "22px 40px 20px",
          borderBottom: "1px solid var(--g-rule-soft)",
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <a href="#" style={{
              fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.1em",
              textTransform: "uppercase", color: "var(--g-ink-3)", textDecoration: "none",
            }}>Orts-Vergleiche</a>
            <span style={{ color: "var(--g-ink-4)", fontSize: 11 }}>/</span>
            <span style={{
              fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.1em",
              textTransform: "uppercase", color: "var(--g-ink-4)",
            }}>Detail</span>
          </div>

          <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 24 }}>
            <div style={{ minWidth: 0, flex: 1 }}>
              <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
                <h1 style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", lineHeight: 1.1, margin: 0,
                  minWidth: 0, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {sub.name}
                </h1>
                <span style={{ flexShrink: 0 }}><CompareStatusPill status={sub.status}/></span>
              </div>
              <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 8 }}>
                {sub.region} · {sub.profileLabel} · {locs.length} Orte
              </div>
            </div>

            {/* Primäraktion (Charter §6: genau eine) + Sekundär im Kebab */}
            <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
              <Btn variant="primary" size="md" icon={
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4l6 6L9 21H3v-6z"/></svg>
              }>Bearbeiten</Btn>
              <CompareKebab items={headerActions} defaultOpen={menuOpen}/>
            </div>
          </div>
        </div>

        {/* ── Monitoring-Streifen (Cockpit-Logik, kein Briefing-Reader) ── */}
        <div style={{ position: "relative", padding: "16px 40px", borderBottom: "1px solid var(--g-rule-soft)", background: "var(--g-card)" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 36, flexWrap: "wrap" }}>
            <CD_StatRow label="Status">
              {active
                ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Dot tone="good" size={7}/> Läuft automatisch</span>
                : <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Dot tone="neutral" size={7}/> Pausiert</span>}
            </CD_StatRow>
            <CD_StatRow label="Nächster Versand">{sub.nextSend}</CD_StatRow>
            <CD_StatRow label="Zuletzt raus">{sub.lastSent}</CD_StatRow>
            <CD_StatRow label="Kanäle">
              {sub.health === "ok"
                ? <span style={{ display: "inline-flex", alignItems: "center", gap: 7 }}><Dot tone="good" size={7}/> {sub.channels.map(c => CD_CHANNEL_LABEL[c]).join(" · ")}</span>
                : sub.channels.map(c => CD_CHANNEL_LABEL[c]).join(" · ") || "—"}
            </CD_StatRow>
          </div>
        </div>

        {/* ── Body: Setup (links) + Versand/Vorschau (rechts) ──────── */}
        <div style={{ position: "relative", padding: "28px 40px 80px", display: "grid", gridTemplateColumns: "1.7fr 1fr", gap: 24, alignItems: "start", maxWidth: 1320 }}>

          {/* LINKS — was konfiguriert ist */}
          <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>

            {/* Orte */}
            <Card padding={0} style={{ overflow: "hidden" }}>
              <div style={{ padding: "16px 20px 12px", display: "flex", alignItems: "baseline", justifyContent: "space-between" }}>
                <div>
                  <Eyebrow style={{ marginBottom: 4 }}>Verglichene Orte</Eyebrow>
                  <div style={{ fontSize: 16, fontWeight: 600 }}>{locs.length} Kandidaten</div>
                </div>
                <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.04em" }}>
                  Ranking im Briefing
                </span>
              </div>
              <div style={{ borderTop: "1px solid var(--g-rule-soft)" }}>
                {locs.map((l, i) => (
                  <CompareLocationRow key={l.id} loc={l} index={i} alt={i % 2 === 1}/>
                ))}
              </div>
            </Card>

            {/* Idealwerte */}
            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 4 }}>Idealwerte</Eyebrow>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Was „gut“ bedeutet</div>
              <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginBottom: 16, maxWidth: 460 }}>
                Bestimmt das tägliche Ranking — je höher gewichtet, desto stärker zählt die Metrik.
              </div>
              <div>
                {sub.ideals.map((it, i) => (
                  <CompareIdealRow key={i} item={it} last={i === sub.ideals.length - 1}/>
                ))}
              </div>
            </Card>

            {/* Layout pro Kanal */}
            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 4 }}>Layout pro Kanal</Eyebrow>
              <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 4 }}>Was im Briefing steht</div>
              <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginBottom: 18, maxWidth: 480 }}>
                Spalten pro Kanal. Engere Kanäle zeigen automatisch weniger — Reihenfolge nach Priorität.
              </div>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                {sub.channels.map(ch => (
                  <CompareLayoutRow key={ch} channel={ch} cols={sub.layout[ch] || []}/>
                ))}
              </div>
            </Card>
          </div>

          {/* RECHTS — Versand + Vorschau-Verifikation */}
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>

            {/* Versand (DetailRow-Molecule) */}
            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 12 }}>Versand</Eyebrow>
              <DetailRow label="Rhythmus"    value={sub.schedule}/>
              <DetailRow label="Vorausschau" value={sub.horizon}/>
              <DetailRow label="Nächster"    value={sub.nextSend} divider="none"/>
              <div style={{ marginTop: 14 }}>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", letterSpacing: "0.14em", textTransform: "uppercase", marginBottom: 8 }}>Kanäle</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {sub.channels.length === 0
                    ? <span style={{ fontSize: 12, color: "var(--g-ink-4)" }}>Keine Kanäle</span>
                    : sub.channels.map(c => <Pill key={c} tone="neutral">{CD_CHANNEL_LABEL[c]}</Pill>)}
                </div>
              </div>
            </Card>

            {/* Vorschau — Verifikations-Tool, KEIN Konsum-Surface */}
            <Card padding={20} style={{ borderLeft: "3px solid var(--g-accent)" }}>
              <Eyebrow style={{ marginBottom: 10 }}>Vorschau · Prüfung</Eyebrow>
              <CD_MailThumb/>
              <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.5, margin: "12px 0 14px" }}>
                So sieht dein Briefing in der Mail aus. Zum <strong>Prüfen</strong> der Konfiguration —
                gelesen wird es unterwegs im Postfach, nicht hier.
              </div>
              <Btn variant="ghost" size="sm" style={{ width: "100%", justifyContent: "center" }} icon={
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-7 11-7 11 7 11 7-4 7-11 7-11-7-11-7z"/><circle cx="12" cy="12" r="3"/></svg>
              }>Vorschau öffnen</Btn>
            </Card>

            <Btn variant="quiet" size="sm" style={{ justifyContent: "center" }} icon={
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M21 3L3 10l7 3 3 7z"/><path d="M21 3l-11 11"/></svg>
            }>Test-Briefing jetzt senden</Btn>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ── Monitoring-Stat (kompakt, Text-Werte statt großer Zahl → eigenes
 *    Local-Helper, kein Stat-Molecule-Fall) ───────────────────────── */
function CD_StatRow({ label, children }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.16em", textTransform: "uppercase", marginBottom: 4 }}>{label}</div>
      <div style={{ fontSize: 13.5, color: "var(--g-ink)", fontWeight: 500 }}>{children}</div>
    </div>
  );
}

/* ── Mail-Thumbnail (rein dekorativ, Verifikations-Hinweis) ─────────── */
function CD_MailThumb() {
  const Bar = ({ w, c = "var(--g-rule)" }) => (
    <div style={{ height: 6, borderRadius: 3, background: c, width: w }}/>
  );
  return (
    <div style={{
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
      background: "var(--g-paper)", padding: 14, display: "flex", flexDirection: "column", gap: 8,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 2 }}>
        <Dot tone="good" size={8}/>
        <Bar w={120} c="var(--g-ink-3)"/>
      </div>
      <Bar w="80%"/>
      <div style={{ height: 1, background: "var(--g-rule-soft)", margin: "2px 0" }}/>
      <Bar w="100%" c="var(--g-accent-tint)"/>
      <Bar w="92%" c="var(--g-accent-tint)"/>
      <Bar w="96%" c="var(--g-accent-tint)"/>
      <Bar w="60%"/>
    </div>
  );
}

window.ScreenCompareDetail = ScreenCompareDetail;
