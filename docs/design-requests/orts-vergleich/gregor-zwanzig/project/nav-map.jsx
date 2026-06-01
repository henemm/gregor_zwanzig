/* nav-map.jsx — Kanonische Navigations-/IA-Karte
 * ─────────────────────────────────────────────────────────────────────────
 * EINE Quelle der Wahrheit dafür, WIE die App navigiert wird — für den PO
 * (Orientierung) UND für Claude Code (jeder Knoten ist an seine echte
 * screen-*.jsx gebunden, damit CC die Screens an der richtigen IA-Stelle
 * einordnet statt Blödsinn zu bauen).
 *
 * <NavMap platform="desktop" /> auf der Desktop-Seite,
 * <NavMap platform="mobile" />  auf der Mobile-Seite.
 * Gleiches Lebenszyklus-Skelett, je platform-spezifische Navigations-Chrome.
 *
 * Babel-Scope-Disziplin (CLAUDE.md): alle Helfer mit NavMap-Prefix.
 *
 * ── DAS KANONISCHE MODELL ─────────────────────────────────────────────────
 * Pro Trip GENAU drei Oberflächen-Typen:
 *   ERSTELLEN  = Wizard (einmalig, linear)
 *   ANSEHEN    = Trip-Detail · Tab „Übersicht" (read-only Cockpit)
 *   BEARBEITEN = Trip-Detail · die übrigen Tabs (je ein Editor)
 * Gelesen werden Briefings NICHT in der App, sondern in den KANÄLEN.
 *
 * Kanonisches Tab-Set (Drift aufgelöst — Trip-Detail gewinnt gegen den
 * Trip-Edit-Host „Route/Wetter/Reports/Alarmregeln"):
 *   Übersicht · Etappen & Wegpunkte · Wetter-Metriken ·
 *   Briefing-Zeitplan · Alerts · Vorschau
 */

/* ─────────────────── Rollen-Chip ─────────────────── */
const NAVMAP_ROLES = {
  erstellen:    { label: "Erstellen",    bg: "var(--g-accent)",      fg: "#fff" },
  ansehen:      { label: "Ansehen",      bg: "var(--g-ink)",         fg: "var(--g-paper)" },
  bearbeiten:   { label: "Bearbeiten",   bg: "transparent",          fg: "var(--g-ink)", border: "1px solid var(--g-ink-3)" },
  verifizieren: { label: "Verifizieren", bg: "transparent",          fg: "var(--g-ink-3)", border: "1px dashed var(--g-ink-4)" },
  konsum:       { label: "Lesen · außerhalb der App", bg: "transparent", fg: "var(--g-ink-3)", border: "1px dashed var(--g-accent)" },
};

function NavMapRoleChip({ role, size = "md" }) {
  const r = NAVMAP_ROLES[role] || NAVMAP_ROLES.ansehen;
  const pad = size === "sm" ? "2px 7px" : "3px 9px";
  const fs = size === "sm" ? 9.5 : 10.5;
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", padding: pad,
      borderRadius: 999, background: r.bg, color: r.fg, border: r.border || "none",
      fontSize: fs, fontWeight: 700, letterSpacing: "0.08em", textTransform: "uppercase",
      whiteSpace: "nowrap",
    }}>{r.label}</span>
  );
}

/* ─────────────────── Pfeil-Konnektor ─────────────────── */
function NavMapArrow({ dir = "right", label }) {
  const glyph = dir === "down" ? "↓" : "→";
  return (
    <div style={{
      display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
      gap: 4, minWidth: dir === "down" ? "auto" : 52, padding: dir === "down" ? "6px 0" : 0,
    }}>
      <span style={{ fontSize: 22, color: "var(--g-accent)", lineHeight: 1, fontWeight: 700 }}>{glyph}</span>
      {label && (
        <span className="mono" style={{ fontSize: 9, color: "var(--g-ink-3)", letterSpacing: "0.06em", textTransform: "uppercase", textAlign: "center", maxWidth: 86, lineHeight: 1.3 }}>
          {label}
        </span>
      )}
    </div>
  );
}

/* ─────────────────── Datei-Referenz (für Claude Code) ─────────────────── */
function NavMapFileRef({ children }) {
  return (
    <span className="mono" style={{
      fontSize: 10, color: "var(--g-ink-3)", background: "var(--g-paper-deep)",
      padding: "1px 6px", borderRadius: 3, border: "1px solid var(--g-rule-soft)",
      whiteSpace: "nowrap",
    }}>{children}</span>
  );
}

/* ─────────────────── Generischer Knoten ─────────────────── */
function NavMapNode({ role, title, sub, files = [], children, dashed = false, style }) {
  return (
    <div style={{
      background: dashed ? "transparent" : "var(--g-card)",
      border: dashed ? "1.5px dashed var(--g-accent)" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", padding: 16, boxShadow: dashed ? "none" : "var(--g-shadow-1)",
      display: "flex", flexDirection: "column", gap: 10, ...style,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
        {role && <NavMapRoleChip role={role} />}
        <span style={{ fontSize: 15, fontWeight: 600, letterSpacing: "-0.01em", whiteSpace: "nowrap" }}>{title}</span>
      </div>
      {sub && <div style={{ fontSize: 12.5, color: "var(--g-ink-2)", lineHeight: 1.5 }}>{sub}</div>}
      {children}
      {files.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 2 }}>
          {files.map((f, i) => <NavMapFileRef key={i}>{f}</NavMapFileRef>)}
        </div>
      )}
    </div>
  );
}

/* ─────────────────── Wizard-Schritte (numerierte Mini-Liste) ─────────────────── */
function NavMapStepList({ steps }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 0, marginTop: 2 }}>
      {steps.map((s, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "baseline", gap: 8, padding: "5px 0",
          borderTop: i === 0 ? "none" : "1px solid var(--g-rule-soft)",
        }}>
          <span className="mono" style={{ fontSize: 10, fontWeight: 700, color: "var(--g-accent-deep)", width: 18, flexShrink: 0 }}>
            {String(i + 1).padStart(2, "0")}
          </span>
          <div>
            <span style={{ fontSize: 13, fontWeight: 600 }}>{s.t}</span>
            <span style={{ fontSize: 12, color: "var(--g-ink-3)" }}> — {s.d}</span>
          </div>
        </div>
      ))}
    </div>
  );
}

/* ─────────────────── Trip-Detail Tab-Liste (kanonisch) ─────────────────── */
function NavMapTabList({ tabs }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", border: "1px solid var(--g-rule-soft)", borderRadius: 6, overflow: "hidden" }}>
      {tabs.map((t, i) => (
        <div key={i} style={{
          display: "grid", gridTemplateColumns: "minmax(0,1fr) auto", gap: 10, alignItems: "center",
          padding: "9px 12px",
          borderTop: i === 0 ? "none" : "1px solid var(--g-rule-soft)",
          background: t.role === "ansehen" ? "rgba(26,26,24,0.035)" : "transparent",
        }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{t.label}</div>
            <div style={{ fontSize: 11.5, color: "var(--g-ink-3)", marginTop: 1, lineHeight: 1.35 }}>
              {t.opens}
              {t.file && <> · <NavMapFileRef>{t.file}</NavMapFileRef></>}
            </div>
          </div>
          <NavMapRoleChip role={t.role} size="sm" />
        </div>
      ))}
    </div>
  );
}

/* ─────────────────── Legende ─────────────────── */
function NavMapLegend() {
  const items = ["erstellen", "ansehen", "bearbeiten", "verifizieren", "konsum"];
  return (
    <div style={{
      display: "flex", flexWrap: "wrap", gap: 14, alignItems: "center",
      padding: "12px 16px", background: "var(--g-card-alt)", borderRadius: 8,
      border: "1px solid var(--g-rule-soft)",
    }}>
      <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.1em", textTransform: "uppercase" }}>Rollen</span>
      {items.map(r => <NavMapRoleChip key={r} role={r} />)}
    </div>
  );
}

/* ─────────────────── Globale Navigation (Sidebar / Bottom-Nav) ─────────────────── */
function NavMapGlobalNav({ platform }) {
  const dest = [
    { t: "Heute", d: "Cockpit · was geht raus, Alerts, aktiver Trip" },
    { t: "Trips", d: "Liste aller Trips" },
    { t: "Ortsvergleich", d: "Liste aller Vergleiche" },
    { t: "Archiv", d: "vergangene Trips" },
  ];
  const chrome = platform === "mobile"
    ? "Bottom-Nav (4 Ziele, ≥44px) + Drawer für Kanäle / Einstellungen / Account"
    : "Sidebar links (persistent)";
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 10 }}>
        <Eyebrow>Globale Navigation</Eyebrow>
        <span style={{ fontSize: 12, color: "var(--g-ink-3)" }}>{chrome}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10 }}>
        {dest.map((d, i) => (
          <div key={i} style={{
            padding: "12px 14px", background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: 8, boxShadow: "var(--g-shadow-1)",
          }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{d.t}</div>
            <div style={{ fontSize: 11.5, color: "var(--g-ink-3)", marginTop: 3, lineHeight: 1.4 }}>{d.d}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─────────────────── Lebenszyklus-Spur ─────────────────── */
function NavMapLane({ tag, title, createNode, createArrowLabel, detailNode }) {
  return (
    <div style={{ marginTop: 4 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
        <span className="mono" style={{
          fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase",
          color: "var(--g-accent-deep)", background: "var(--g-accent-tint)", padding: "4px 10px", borderRadius: 4,
        }}>{tag}</span>
        <span style={{ fontSize: 16, fontWeight: 600 }}>{title}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0,0.92fr) 52px minmax(0,1.15fr)", alignItems: "stretch" }}>
        {createNode}
        <NavMapArrow label={createArrowLabel} />
        {detailNode}
      </div>
    </div>
  );
}

/* ─────────────────── Haupt-Komponente ─────────────────── */
function NavMap({ platform = "desktop" }) {
  const isMobile = platform === "mobile";

  /* ── TRIP ── */
  const tripWizard = (
    <NavMapNode
      role="erstellen"
      title="Trip-Wizard"
      sub={isMobile ? "5 Vollbild-Schritte, linear. Bottom-Nav ausgeblendet, sticky Indicator + Action-Bar." : "5 Schritte, linear, Vollbild. Einstieg: Trips → „+ Neuer Trip“."}
      files={[isMobile ? "screen-trip-wizard-mobile.jsx" : "screen-trip-wizard.jsx"]}
    >
      <NavMapStepList steps={[
        { t: "Route", d: "Name + Region + GPX" },
        { t: "Etappen", d: "Liste + Vorlagen (leichte Version)" },
        { t: "Wetter", d: "Metriken-Auswahl" },
        { t: "Layout", d: "Spalten / Detail pro Kanal" },
        { t: "Reports", d: "Briefing-Zeitplan" },
      ]} />
    </NavMapNode>
  );

  const tripTabs = [
    { label: "Übersicht", role: "ansehen", opens: "read-only Cockpit · jede Sektion hat „Bearbeiten →“" },
    { label: "Etappen & Wegpunkte", role: "bearbeiten", opens: "Wegpunkt-Editor (Karte + Höhenprofil)", file: isMobile ? "screen-waypoint-editor-mobile.jsx" : "screen-waypoint-editor.jsx" },
    { label: "Wetter-Metriken", role: "bearbeiten", opens: "Spalten / Detail / Aus + Multi-Channel-Vorschau", file: isMobile ? "screen-metrics-editor-mobile.jsx" : "screen-metrics-editor.jsx" },
    { label: "Briefing-Zeitplan", role: "bearbeiten", opens: "Morgen / Abend / Alert-Zeiten + Kanäle" },
    { label: "Alerts", role: "bearbeiten", opens: "Schwellwerte (Δ vs. absolut)", file: isMobile ? "screen-alert-config-mobile.jsx" : "screen-alert-config.jsx" },
    { label: "Vorschau", role: "verifizieren", opens: "Briefing-Check im Setup — KEIN Konsum-Surface" },
  ];

  const tripDetail = (
    <NavMapNode
      role="ansehen"
      title="Trip-Detail"
      sub={isMobile
        ? "Container. Pill-Tab-Scroller (sticky). Editoren öffnen als Bottom-Sheet / Accordion."
        : "Container. Eine kanonische Tab-Leiste. Einstieg: Trips → Trip-Kachel."}
      files={[isMobile ? "screen-trip-detail-mobile.jsx" : "screen-trip-detail.jsx"]}
    >
      <NavMapTabList tabs={tripTabs} />
    </NavMapNode>
  );

  /* ── ORTSVERGLEICH ── */
  const cmpWizard = (
    <NavMapNode
      role="erstellen"
      title="Ortsvergleich-Wizard"
      sub="5 Schritte: Benennen → Orte sammeln → Idealwerte → Layout → Versand. Auch der Edit-Modus läuft hier (Direkt-Sprung in einen Schritt)."
      files={[isMobile ? "screen-location-new-mobile.jsx" : "screen-compare-wizard.jsx"]}
    >
      <NavMapStepList steps={[
        { t: "Benennen", d: "Vergleich + Aktivitäts-Profil" },
        { t: "Orte", d: "POIs sammeln / importieren" },
        { t: "Idealwerte", d: "Score-Modell pro Profil" },
        { t: "Layout", d: "Spalten pro Kanal" },
        { t: "Versand", d: "Zeitplan + Aktivierung" },
      ]} />
    </NavMapNode>
  );

  const cmpDetail = (
    <NavMapNode
      role="ansehen"
      title="Vergleichs-Detail"
      sub="Kachel-Klick öffnet das SETUP (Status + Konfiguration + Aktionen) — NICHT das Tages-Briefing (Charter §3). „Bearbeiten“ springt zurück in den Wizard-Edit-Modus."
      files={[isMobile ? "screen-compare-detail-mobile.jsx" : "screen-compare-detail.jsx"]}
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        <NavMapRoleChip role="bearbeiten" size="sm" />
        <span style={{ fontSize: 12, color: "var(--g-ink-3)" }}>Bearbeiten → Wizard (Edit-Modus, gleiche Datei)</span>
      </div>
    </NavMapNode>
  );

  /* ── Kanäle (außerhalb der App) ── */
  const kanaele = (
    <NavMapNode
      role="konsum"
      title="Kanäle · hier liest der User"
      dashed
      sub="Die Briefings kommen automatisch ins Postfach. Die App muss im Urlaub NICHT geöffnet werden — sie ist Einrichtungs- & Monitoring-Werkzeug, kein Lese-Medium."
    >
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {[
          { c: "Email", lim: "∞ Spalten" },
          { c: "Telegram", lim: "max 8" },
          { c: "Signal", lim: "max 6" },
          { c: "SMS", lim: "flach, ≤140 Z." },
        ].map((k, i) => (
          <span key={i} className="mono" style={{
            fontSize: 11, padding: "4px 9px", borderRadius: 999,
            background: "var(--g-card)", border: "1px solid var(--g-rule)", color: "var(--g-ink-2)",
          }}>
            {k.c} <span style={{ color: "var(--g-ink-4)" }}>· {k.lim}</span>
          </span>
        ))}
      </div>
    </NavMapNode>
  );

  return (
    <div style={{ position: "relative", padding: 32, background: "var(--g-paper)", minHeight: "100%", overflow: "hidden" }}>
      <TopoBg opacity={0.1} />
      <div style={{ position: "relative", maxWidth: 1320 }}>

        {/* Kopf */}
        <Eyebrow>Informations-Architektur · Single-Source</Eyebrow>
        <h1 style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 8px" }}>
          Navigations-Karte · {isMobile ? "Mobile" : "Desktop"}
        </h1>
        <div style={{ fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.6, maxWidth: 880 }}>
          Pro Trip gibt es <strong>genau drei</strong> Oberflächen-Typen — <strong>Erstellen</strong> (Wizard),
          <strong> Ansehen</strong> (Trip-Detail, Tab „Übersicht“, read-only) und <strong>Bearbeiten</strong> (die übrigen
          Tabs, je ein Editor). Gelesen werden Briefings in den <strong>Kanälen</strong>, nicht in der App. Jeder Knoten
          unten nennt seine echte <NavMapFileRef>screen-*.jsx</NavMapFileRef> — damit jede Implementierung an der richtigen
          Stelle landet.
        </div>

        <div style={{ marginTop: 18 }}><NavMapLegend /></div>

        <div style={{ marginTop: 24 }}><NavMapGlobalNav platform={platform} /></div>

        <div style={{ height: 1, background: "var(--g-rule-soft)", margin: "26px 0" }} />

        {/* Trip-Lebenszyklus */}
        <NavMapLane
          tag="Trip"
          title="Lebenszyklus eines Trips"
          createNode={tripWizard}
          createArrowLabel="fertig →"
          detailNode={tripDetail}
        />

        {/* Auslauf zu den Kanälen */}
        <div style={{ display: "grid", gridTemplateColumns: "minmax(0,0.92fr) 52px minmax(0,1.15fr)", alignItems: "center", marginTop: 4 }}>
          <div />
          <div />
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
            <NavMapArrow dir="down" label="Briefing-Zeitplan sendet" />
            <div style={{ width: "100%" }}>{kanaele}</div>
          </div>
        </div>

        <div style={{ height: 1, background: "var(--g-rule-soft)", margin: "28px 0" }} />

        {/* Ortsvergleich-Lebenszyklus */}
        <NavMapLane
          tag="Ortsvergleich"
          title="Lebenszyklus eines Vergleichs"
          createNode={cmpWizard}
          createArrowLabel="aktiviert →"
          detailNode={cmpDetail}
        />

        {/* Entscheid: Tab-Naming-Drift */}
        <div style={{
          marginTop: 28, padding: "16px 18px", background: "var(--g-card)",
          border: "1px solid var(--g-rule)", borderLeft: "3px solid var(--g-accent)", borderRadius: "var(--g-r-2)",
        }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-accent-deep)", letterSpacing: "0.1em", textTransform: "uppercase", fontWeight: 700, marginBottom: 6 }}>
            Tech-Lead-Entscheid · Tab-Naming
          </div>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.6 }}>
            Es existierten zwei konkurrierende Tab-Sets für denselben Trip. <strong>Kanonisch ist genau eines</strong>,
            integriert ins Trip-Detail (kein separater „Edit-Modus“-Screen):
            {" "}<strong>Übersicht · Etappen &amp; Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts · Vorschau</strong>.
            Das alte Set des Trip-Edit-Hosts (<NavMapFileRef>Route · Wetter · Reports · Alarmregeln</NavMapFileRef>,
            screen-trip-edit-tabs.jsx) wird darauf gemappt und nicht mehr separat geführt.
          </div>
        </div>

      </div>
    </div>
  );
}

window.NavMap = NavMap;
