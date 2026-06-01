/* Mobile · Ortsvergleich · Liste (Kachel-Stack)
 * ─────────────────────────────────────────────────────────────────────
 * Mobile-Pendant zur Desktop-Compare-Übersicht (Charter §3 v1.1).
 * Vertikaler Card-Stack; Tap auf eine Karte → ScreenCompareDetailMobile.
 *
 * Atomic Design: nutzt CompareTile (dense) + Stat (inline) aus
 * molecules.jsx — KEINE eigene Mobile-Kachel mehr (Drift-Auflösung).
 * Chevron-Affordanz via MIcon wird als `trailing` injiziert.
 * Lokale Reste mit CLM_-Prefix (Babel-Scope).
 */

function ScreenCompareListMobile() {
  const subs = window.MOCK_COMPARE_SUBS || [];
  const counts = {
    active: subs.filter(c => c.status === "active").length,
    paused: subs.filter(c => c.status === "paused").length,
    draft:  subs.filter(c => c.status === "draft").length,
  };
  const right = <IconBtn kind="plus" label="Neuer Vergleich"/>;

  return (
    <MobileShell active="compare" title="Orts-Vergleiche" eyebrow={`Workspace · ${subs.length}`} right={right} phoneHeight={812}>
      <ScreenScroll padding={0}>
        <div style={{ padding: "12px 16px 24px" }}>

          {/* Intro */}
          <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 14 }}>
            Tägliche Briefings, die mehrere Orte vergleichen und eine Empfehlung mitliefern.
            Einmal eingerichtet, läuft jeder Vergleich automatisch.
          </div>

          {/* Suche */}
          <div style={{ marginBottom: 12 }}>
            <MInput leftIcon="search" placeholder="Suchen…"/>
          </div>

          {/* Stats (Stat-Molecule, inline) */}
          <div style={{
            display: "flex", gap: 20, padding: "4px 2px 16px",
            borderBottom: "1px solid var(--g-rule-soft)", marginBottom: 16,
          }}>
            <Stat label="Aktiv"    value={counts.active} layout="inline" size="sm" tone="accent" mono/>
            <Stat label="Pausiert" value={counts.paused} layout="inline" size="sm" mono/>
            <Stat label="Drafts"   value={counts.draft}  layout="inline" size="sm" mono/>
          </div>

          {/* Kachel-Stack */}
          <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
            {subs.map(s => (
              <CompareTile
                key={s.id}
                sub={s}
                dense
                trailing={<MIcon kind="chevron" size={16} color="var(--g-ink-4)"/>}
              />
            ))}
          </div>
        </div>
      </ScreenScroll>
    </MobileShell>
  );
}

window.ScreenCompareListMobile = ScreenCompareListMobile;
