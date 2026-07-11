/* Screen: Home · Planungs-/Leerzustand.
 *
 * Der häufigste Zustand (CLAUDE.md): kein Trip läuft gerade, Gregor bereitet
 * die nächste Reise vor — ~90 % der Webnutzung. Statt des Live-Status-Cockpits
 * trägt die Seite hier den Vorbereitungs-Fall:
 *   1 · Weiter einrichten — nächster geplanter Trip + Vergleichs-Entwurf, je
 *                           mit Setup-Fortschritt und „Setup fortsetzen"
 *   2 · Schnell anlegen   — Neuer Trip / Vergleich / Orte
 *   3 · Laufende Vergleiche — Orts-Vergleiche laufen auch ohne Trip weiter
 *                           (Monitoring + Kebab-Aktionen)
 *   4 · Archiv
 *
 * Nutzt SetupResumeCard, QuickAction, CompareTile + CompareKebab/compareActions
 * (alle aus molecules.jsx) — keine Inline-Varianten.
 */

const HP_PLANNED_TRIP = {
  name: "Dolomiten-Höhenweg 2",
  subtitle: "Südtirol · Dolomiten · 9 Etappen · 118,4 km",
  steps: [
    { label: "Route", done: true },
    { label: "Etappen", done: true },
    { label: "Wetter-Metriken", done: true },
    { label: "Layout", done: false },
    { label: "Reports", done: false },
  ],
};

function ScreenHomePlanning() {
  const draft = (window.MOCK_COMPARE_SUBS || []).find(s => s.status === "draft");
  const draftSteps = [
    { label: "Vergleich", done: true },
    { label: "Orte", done: true },
    { label: "Idealwerte", done: true },
    { label: "Layout", done: true },
    { label: "Versand", done: false },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="home"/>
      <main data-screen-label="Startseite · Planung" style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.22}/>

        {/* Topbar */}
        <div style={{
          position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "20px 40px", borderBottom: "1px solid var(--g-rule-soft)",
        }}>
          <div>
            <Eyebrow>Übersicht · vor der Reise</Eyebrow>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, letterSpacing: "-0.005em" }}>Guten Morgen, Gregor.</div>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Btn variant="ghost" size="sm" icon={<span style={{ fontSize: 16, lineHeight: 0 }}>+</span>}>Neuer Trip</Btn>
            <Btn variant="ghost" size="sm" icon={<span style={{ fontSize: 16, lineHeight: 0 }}>+</span>}>Neuer Vergleich</Btn>
          </div>
        </div>

        <div style={{ position: "relative", padding: "32px 40px 80px", maxWidth: 1320 }}>

          {/* Kein aktiver Trip — ehrlicher Hinweis */}
          <div style={{
            display: "flex", alignItems: "center", gap: 12, marginBottom: 28,
            padding: "12px 18px", borderRadius: "var(--g-r-3)",
            background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)",
          }}>
            <Dot tone="neutral" size={8}/>
            <span style={{ fontSize: 14, color: "var(--g-ink-2)" }}>
              Aktuell läuft <strong>kein Trip</strong>. Sobald deine nächste Reise startet, schickt <span className="mono" style={{ fontSize: 13 }}>gregor · zwanzig</span> die Briefings automatisch in deine Kanäle.
            </span>
          </div>

          {/* ───────── 1 · WEITER EINRICHTEN ───────── */}
          <div style={{ marginBottom: 36 }}>
            <SectionH
              eyebrow="Weiter einrichten"
              title="Mach weiter, wo du aufgehört hast"
              kicker="Du nutzt die Webseite vor allem zur Vorbereitung — hier liegen deine offenen Entwürfe"
            />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20 }}>
              <SetupResumeCard
                tone="accent"
                eyebrow="Geplant · Start in 24 Tagen · 30. Juni"
                title={HP_PLANNED_TRIP.name}
                subtitle={HP_PLANNED_TRIP.subtitle}
                steps={HP_PLANNED_TRIP.steps}
                ctaLabel="Setup fortsetzen"
                secondary="Öffnen"
              />
              <SetupResumeCard
                eyebrow="Entwurf · Orts-Vergleich"
                title={draft ? draft.name : "Wanderungen Dolomiten"}
                subtitle={draft ? `${draft.locationIds.length} Orte · ${draft.profileLabel}` : "3 Orte · Hochtour / Wandern"}
                steps={draftSteps}
                ctaLabel="Setup fortsetzen"
                secondary="Öffnen"
              />
            </div>
          </div>

          {/* ───────── 2 · SCHNELL ANLEGEN ───────── */}
          <div style={{ marginBottom: 36 }}>
            <SectionH eyebrow="Schnell anlegen" title="Neu starten"/>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 14 }}>
              <QuickAction glyph="route"   tone="accent" label="Neuer Trip"            sub="Wizard · 5 Schritte"/>
              <QuickAction glyph="metrics" label="Neuer Orts-Vergleich"  sub="Wizard · 5 Schritte"/>
              <QuickAction glyph="eye"     label="Test-Briefing prüfen"   sub="Vorschau · alle Kanäle"/>
            </div>
          </div>

          {/* ───────── 3 · LAUFENDE ORTS-VERGLEICHE ───────── */}
          <div style={{ marginBottom: 36 }}>
            <SectionH
              eyebrow="Läuft automatisch"
              title="Laufende Orts-Vergleiche"
              kicker="Vergleiche laufen unabhängig von Trips weiter — Briefing kommt in die Kanäle"
              right={<Btn variant="quiet" size="sm">Alle anzeigen</Btn>}
            />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {(window.MOCK_COMPARE_SUBS || []).filter(s => s.status === "active").map(s => (
                <CompareTile
                  key={s.id}
                  sub={s}
                  compact
                  trailing={<CompareKebab items={compareActions(s.status)} btnSize={28}/>}
                />
              ))}
            </div>
          </div>

          {/* ───────── Archiv ───────── */}
          <Card padding={20}>
            <SectionH eyebrow="Archiv" title="Frühere Trips" kicker="8 abgeschlossene Mehrtages-Trips" right={<Btn variant="quiet" size="sm">Alle anzeigen</Btn>}/>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {MOCK_ARCHIVED.slice(0, 4).map(t => (
                <div key={t.id} style={{
                  padding: "14px 16px", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)",
                  background: "var(--g-card-alt)",
                }}>
                  <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>{t.dates}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3, marginBottom: 6 }}>{t.name}</div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{t.stages} Etappen</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}

window.ScreenHomePlanning = ScreenHomePlanning;
