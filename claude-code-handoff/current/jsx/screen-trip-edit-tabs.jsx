/* Design-Request #503 — Wegpunkt-Editor im Tab „Etappen & Wegpunkte"
 *
 * Zeigt die EMPFEHLUNG (Option B): Der vorhandene Wegpunkt-Editor (Karte +
 * Höhenprofil + Wegpunkt-Sidebar) läuft als Inhalt des Tabs „Etappen & Wegpunkte"
 * innerhalb von TripEditView — nicht als eigene Seite, nicht als 6. Tab.
 *
 * Bewusst KEINE Neubauten: der Editor-Kern kommt 1:1 aus
 * screen-waypoint-editor.jsx / screen-waypoint-editor-mobile.jsx via `embedded`.
 * Diese Datei liefert nur die Tab-Host-Chrome (Breadcrumb + Hero + Tab-Leiste).
 *
 * Naming: alle Helfer mit Page-Prefix (TripEdit*) — Babel-Scope-Disziplin, CLAUDE.md.
 */

/* ─────────────────── Desktop Tab-Leiste ─────────────────── */
function TripEditTabBar({ active = "etappen", stageCount = 13 }) {
  const tabs = [
    { id: "route",   label: "Route" },
    { id: "etappen", label: "Etappen & Wegpunkte", badge: String(stageCount) },
    { id: "wetter",  label: "Wetter" },
    { id: "reports", label: "Reports" },
    { id: "alarme",  label: "Alarmregeln", badge: "2", accent: true },
  ];
  return (
    <div style={{ position: "relative", borderBottom: "1px solid var(--g-rule)", padding: "0 40px", display: "flex", gap: 0 }}>
      {tabs.map(t => {
        const on = t.id === active;
        return (
          <div key={t.id} style={{
            padding: "12px 16px", cursor: "pointer", fontSize: 13, fontWeight: on ? 600 : 500,
            color: on ? "var(--g-ink)" : "var(--g-ink-3)",
            borderBottom: on ? "2px solid var(--g-accent)" : "2px solid transparent",
            marginBottom: -1, display: "flex", alignItems: "center", gap: 6,
          }}>
            {t.label}
            {t.badge && (
              <span className="mono" style={{
                fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 3,
                background: t.accent ? "var(--g-accent)" : "var(--g-paper-deep)",
                color: t.accent ? "#fff" : "var(--g-ink-3)",
              }}>{t.badge}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─────────────────── Desktop: Tab-Host + eingebetteter Editor ─────────────────── */
function ScreenTripEditWaypoints({ initialActiveIdx = 1 } = {}) {
  const trip = MOCK_TRIP;
  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }} data-screen-label="Trip bearbeiten · Etappen & Wegpunkte (Desktop)">
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.14}/>

        {/* Breadcrumb + globale Trip-Aktionen — gehören dem Tab-Host, nicht dem Editor */}
        <div style={{ position: "relative", padding: "16px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.06em" }}>
            <span style={{ opacity: 0.6 }}>Trips</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ opacity: 0.6 }}>{trip.shortName}</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>Bearbeiten</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost" size="sm">Vorschläge neu berechnen</Btn>
            <Btn variant="primary" size="sm">Speichern</Btn>
          </div>
        </div>

        {/* Kompakter Hero */}
        <div style={{ position: "relative", padding: "22px 40px 16px" }}>
          <Eyebrow>Trip bearbeiten · {trip.region}</Eyebrow>
          <h1 style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em", margin: "4px 0 0", lineHeight: 1.1 }}>{trip.name}</h1>
        </div>

        {/* Tab-Leiste — „Etappen & Wegpunkte" aktiv */}
        <TripEditTabBar active="etappen" stageCount={trip.stages.length}/>

        {/* Tab-Inhalt = eingebetteter Wegpunkt-Editor MIT Karte (Option B) */}
        <ScreenWaypointEditor embedded initialActiveIdx={initialActiveIdx}/>
      </main>
    </div>
  );
}

/* ─────────────────── Mobile: Tab-Host + eingebetteter Editor ─────────────────── */
function ScreenTripEditWaypointsMobile({ initialActive = 1 } = {}) {
  const trip = MOCK_TRIP;
  const tabs = [
    { id: "route",   label: "Route" },
    { id: "etappen", label: "Etappen & Wegpunkte", badge: String(trip.stages.length) },
    { id: "wetter",  label: "Wetter" },
    { id: "reports", label: "Reports" },
    { id: "alarme",  label: "Alarme", badge: "2", accent: true },
  ];
  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }} data-screen-label="Trip bearbeiten · Etappen & Wegpunkte (Mobile)">
        <TopAppBar
          title="Bearbeiten"
          eyebrow={`${trip.shortName} · ${trip.stages.length} Etappen`}
          leftIcon="back"
          right={<IconBtn kind="more" label="Aktionen"/>}
        />
        {/* Trip-Edit-Tabs als scrollbare Leiste — „Etappen & Wegpunkte" aktiv */}
        <MTab items={tabs} active="etappen"/>
        {/* Tab-Inhalt = eingebetteter Wegpunkt-Editor (Karte + Bottom-Sheet) */}
        <ScreenWaypointEditorMobile embedded initialActive={initialActive}/>
      </div>
    </PhoneFrame>
  );
}

/* ─────────────────── Begründung A / B / C ─────────────────── */
function TripEditRationale() {
  const Row = ({ tag, title, verdict, kill, children }) => (
    <div style={{
      padding: "16px 18px", borderRadius: "var(--g-r-3)",
      background: verdict ? "rgba(196,90,42,0.06)" : "var(--g-card)",
      border: verdict ? "1.5px solid var(--g-accent)" : "1px solid var(--g-rule)",
    }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 6 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span className="mono" style={{
            fontSize: 11, fontWeight: 700, letterSpacing: "0.06em",
            color: verdict ? "var(--g-accent-deep)" : "var(--g-ink-3)",
          }}>{tag}</span>
          <span style={{ fontSize: 15, fontWeight: 600 }}>{title}</span>
        </div>
        {verdict
          ? <Pill tone="accent">Empfehlung</Pill>
          : <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>{kill}</span>}
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.55 }}>{children}</div>
    </div>
  );
  return (
    <div style={{ padding: 28, background: "var(--g-paper)", minHeight: "100%" }}>
      <Eyebrow>Design-Request #503 · Architektur-Entscheid</Eyebrow>
      <h2 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 4px" }}>Wo gehört die Karte hin?</h2>
      <div style={{ fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55, maxWidth: 620, marginBottom: 20 }}>
        Der Editor existiert fertig (Desktop + Mobile, spec-konform). Offen ist nur:
        in welchen Tab gehört er. Antwort: <strong>er ersetzt den heutigen „Etappen"-Tab</strong> —
        eine Karte, eine Stelle, kein Duplikat.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        <Row tag="A" title="Karte ganz weglassen" kill="verworfen">
          Wirft das stärkste Setup-Werkzeug weg: Wegpunkte sind <em>Wetterscheiden</em> —
          inhärent räumlich. Das Höhenprofil zeigt <em>wann</em>, nicht <em>wo</em>. Außerdem
          landet eine fertige, spec-treue Komponente im Müll.
        </Row>
        <Row tag="B" title={`Karte in den Tab „Etappen & Wegpunkte“`} verdict>
          Editor wird Inhalt des umbenannten Etappen-Tabs. EtappenStrip + Karte + Höhenprofil +
          Wegpunkt-Sidebar an <strong>einer</strong> Stelle. Eliminiert das ~90 %-Duplikat
          zwischen <span className="mono" style={{ fontSize: 12 }}>EditStagesPanelNew</span> und
          <span className="mono" style={{ fontSize: 12 }}> WaypointEditorPage</span>. Deckt sich mit
          dem bestehenden Detail-Mockup, das bereits „Etappen &amp; Wegpunkte" als einen Tab führt.
        </Row>
        <Row tag="C" title={`Eigener 6. Tab „Wegpunkte“`} kill="abgelehnt">
          Zwei Tabs zeigen denselben EtappenStrip + dasselbe Höhenprofil → doppelte Navigation,
          doppelter Pflegeaufwand, „in welchem Tab verschiebe ich einen Wegpunkt?". Genau die Drift,
          gegen die das Projekt arbeitet.
        </Row>
      </div>
      <div style={{ marginTop: 18, padding: 14, background: "var(--g-card)", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-2)" }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 }}>Zu #296</div>
        <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
          #296 bleibt im Kern gültig: <strong>keine Lat/Lon-Inputs</strong>, Bearbeiten passiert visuell.
          Der gebaute Editor hält das ein (Karten-Pins + Profil-Klick). Revidiert wird nur der eine Satz
          „Karte ganz entfernen" — die Karte kehrt als Klickfläche zurück, nicht als Koordinaten-Formular.
        </div>
      </div>
    </div>
  );
}

window.ScreenTripEditWaypoints = ScreenTripEditWaypoints;
window.ScreenTripEditWaypointsMobile = ScreenTripEditWaypointsMobile;
window.TripEditRationale = TripEditRationale;
