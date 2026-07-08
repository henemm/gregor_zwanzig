/* Orts-Vergleich · Mail v2
 * ─────────────────────────────────────────────────────────────────────────
 * Neu-Ausrichtung (PO, 2026-07-08): der Ortsvergleich orientiert sich stärker
 * an den Trip-Briefings. Vier PO-Vorgaben:
 *   1. Score entfällt vollständig — nicht nachvollziehbar; der User beurteilt
 *      die Kriterien selbst. Kein Composite-Ranking, kein „Bester Standort".
 *   2. Eine Übersichtstabelle mit den vom User gewählten Metriken (Orte als
 *      Spalten, Metriken als Zeilen).
 *   3. Die Übersicht enthält die amtlichen Warnungen als eigene Metrik-Zeile
 *      (eine Warn-Zelle pro Ort) — statt einer langen Liste über der Tabelle.
 *   4. Darunter für ALLE Orte eine Stundentabelle mit allen Metriken.
 *
 * Visuelles Vokabular = Trip-Mail (screen-output-preview.jsx):
 *   gleicher Header, gleiche Eyebrow/Tag-Sprache, gleiche Risk-Skala + Zell-
 *   Färbung (ok · caution · warn · danger), gleiche Mono-Tabellen.
 *
 * CV2_-Prefix auf allen Top-Level-Komponenten (Babel-Scope-Falle, CLAUDE.md).
 */

const CV2_SANS = "'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
const CV2_MONO = "'JetBrains Mono', 'SF Mono', Menlo, monospace";

/* ── 4-Stufen-Risk-Skala — identisch zur Trip-Mail ───────────────────────── */
const CV2_RISK_CELL = {
  caution: { bg: "#fbeeb8", color: "#5e4a00" },
  warn:    { bg: "#fad6b8", color: "#8a3506" },
  danger:  { bg: "#f6c5bf", color: "#8a1009" },
};
const CV2_TAG = {
  ok:   { bg: "#dcf2e1", fg: "#14532d", border: "#86c89a" },
  warn: { bg: "#fde6cc", fg: "#7c2d12", border: "#f0a060" },
  risk: { bg: "#fadcd6", fg: "#7f1d1d", border: "#e88472" },
  info: { bg: "#dde8f3", fg: "#1e3a5f", border: "#8aacd0" },
};
const cv2SevTemp  = v => v >= 34 ? "danger" : v >= 31 ? "warn" : v >= 28 ? "caution" : "ok";
const cv2SevWind  = v => v > 40 ? "danger" : v > 30 ? "warn" : v > 20 ? "caution" : "ok";
const cv2SevGust  = v => v > 60 ? "danger" : v > 45 ? "warn" : v > 30 ? "caution" : "ok";
const cv2SevRain  = v => v > 8  ? "danger" : v > 4  ? "warn" : v > 1  ? "caution" : "ok";
const cv2SevUV    = v => v >= 8 ? "danger" : v >= 6 ? "warn" : v >= 3 ? "caution" : "ok";

/* ── Metrik-Katalog: was der User als Übersichts-Spalten gewählt hat ──────── */
/* highlight: "min"|"max" = welcher Wert ist der günstigste Einzelwert (rein
 * faktisch, KEIN Gesamt-Ranking). null = kein Highlight. */
const CV2_METRICS = [
  { key: "warn",    label: "Amtliche Warnungen", kind: "warn" },
  { key: "tempMax", label: "Temp max",  unit: "°C", kind: "num", sev: cv2SevTemp, highlight: null },
  { key: "wind",    label: "Wind",      unit: "km/h", kind: "num", sev: cv2SevWind, highlight: "min" },
  { key: "sun",     label: "Sonne",     unit: "h",  kind: "num", highlight: "max", decimals: 1 },
  { key: "cloud",   label: "Wolken",    unit: "%",  kind: "num", highlight: "min" },
  { key: "uvMax",   label: "UV max",    unit: "",   kind: "num", sev: cv2SevUV, highlight: null },
];

/* ── Warn-Typen → Kürzel + Schweregrad ───────────────────────────────────── */
const CV2_WARN = {
  hitze:      { short: "Hitze",       sev: "warn"    },
  brand2:     { short: "Brand · 2",   sev: "caution" },
  brand3:     { short: "Brand · 3",   sev: "warn"    },
  brand4:     { short: "Brand · 4",   sev: "danger"  },
  zugang:     { short: "Zugang",      sev: "caution" },
};
/* Langform für die Detail-Blöcke. */
const CV2_WARN_LONG = {
  hitze:  "Extreme Hitze",
  brand2: "Waldbrand-Gefahr — Stufe 2",
  brand3: "Waldbrand-Gefahr — Stufe 3",
  brand4: "Waldbrand-Gefahr — Stufe 4",
};

/* ── Daten: Var / Côte d'Azur · Hitzewelle 08.07.2026 (aus echtem Render) ── */
const CV2_META = {
  title: "Le Var · Wo ist es diese Woche am erträglichsten?",
  name: "Le Var (Sommer)",
  code: "WETTER-BRIEFING",
  dateLong: "Mi · 08.07.2026 · 09:00 – 16:00",
  horizon: "+48h",
  created: "04:01",
  createdDate: "08.07.2026",
  source: "openmeteo · icon_eu",
  next: "Do · 09.07.2026 · 04:00",
};

const CV2_LOCS = [
  {
    id: "toulon", name: "Toulon", group: "Var · Küste",
    warns: [{ t: "hitze" }, { t: "brand3" }, { t: "zugang", note: "Monts Toulonnais" }],
    ov: { tempMax: 32, wind: 13, sun: 8.0, cloud: 56, uvMax: 8 },
    hours: [
      { h: "09", t: 30, f: 33, w: 9,  g: 18, r: 0,   cl: 6,   uv: 2 },
      { h: "10", t: 31, f: 34, w: 9,  g: 20, r: 0,   cl: 9,   uv: 4 },
      { h: "11", t: 32, f: 35, w: 11, g: 22, r: 0,   cl: 12,  uv: 6 },
      { h: "12", t: 31, f: 34, w: 13, g: 26, r: 0,   cl: 21,  uv: 8 },
      { h: "13", t: 31, f: 34, w: 13, g: 26, r: 0,   cl: 100, uv: 5 },
      { h: "14", t: 30, f: 33, w: 13, g: 24, r: 0.2, cl: 100, uv: 3 },
      { h: "15", t: 30, f: 33, w: 10, g: 20, r: 0,   cl: 100, uv: 2 },
      { h: "16", t: 30, f: 33, w: 8,  g: 16, r: 0,   cl: 100, uv: 1 },
    ],
  },
  {
    id: "bormes", name: "Bormes Les Mimosas", group: "Var · Küste",
    warns: [{ t: "hitze" }, { t: "brand3" }],
    ov: { tempMax: 29, wind: 16, sun: 8.0, cloud: 15, uvMax: 7 },
    hours: [
      { h: "09", t: 27, f: 28, w: 10, g: 20, r: 0,   cl: 3,   uv: 2 },
      { h: "10", t: 28, f: 29, w: 12, g: 24, r: 0,   cl: 0,   uv: 4 },
      { h: "11", t: 28, f: 29, w: 13, g: 26, r: 0,   cl: 21,  uv: 6 },
      { h: "12", t: 29, f: 30, w: 14, g: 28, r: 0,   cl: 0,   uv: 7 },
      { h: "13", t: 29, f: 30, w: 16, g: 30, r: 0,   cl: 0,   uv: 6 },
      { h: "14", t: 28, f: 29, w: 15, g: 30, r: 0.1, cl: 100, uv: 3 },
      { h: "15", t: 28, f: 29, w: 13, g: 26, r: 0,   cl: 1,   uv: 2 },
      { h: "16", t: 27, f: 28, w: 11, g: 22, r: 0,   cl: 1,   uv: 1 },
    ],
  },
  {
    id: "giens", name: "Giens", group: "Var · Halbinsel",
    warns: [{ t: "hitze" }, { t: "brand3" }],
    ov: { tempMax: 28, wind: 14, sun: 8.0, cloud: 39, uvMax: 7 },
    hours: [
      { h: "09", t: 28, f: 29, w: 6,  g: 12, r: 0, cl: 26,  uv: 2 },
      { h: "10", t: 28, f: 29, w: 10, g: 20, r: 0, cl: 31,  uv: 4 },
      { h: "11", t: 28, f: 29, w: 12, g: 24, r: 0, cl: 7,   uv: 6 },
      { h: "12", t: 28, f: 29, w: 14, g: 28, r: 0, cl: 14,  uv: 7 },
      { h: "13", t: 28, f: 29, w: 14, g: 28, r: 0, cl: 1,   uv: 5 },
      { h: "14", t: 28, f: 29, w: 14, g: 28, r: 0, cl: 100, uv: 3 },
      { h: "15", t: 28, f: 29, w: 12, g: 24, r: 0, cl: 39,  uv: 2 },
      { h: "16", t: 28, f: 29, w: 7,  g: 14, r: 0, cl: 100, uv: 1 },
    ],
  },
  {
    id: "camp", name: "Camp du Domaine", group: "Var · Küste",
    warns: [{ t: "hitze" }, { t: "brand3" }],
    ov: { tempMax: 28, wind: 17, sun: 8.0, cloud: 20, uvMax: 7 },
    hours: [
      { h: "09", t: 26, f: 27, w: 11, g: 22, r: 0,   cl: 8,   uv: 2 },
      { h: "10", t: 27, f: 28, w: 13, g: 26, r: 0,   cl: 5,   uv: 4 },
      { h: "11", t: 28, f: 29, w: 15, g: 30, r: 0,   cl: 12,  uv: 6 },
      { h: "12", t: 28, f: 29, w: 17, g: 34, r: 0,   cl: 20,  uv: 7 },
      { h: "13", t: 28, f: 29, w: 16, g: 32, r: 0,   cl: 40,  uv: 5 },
      { h: "14", t: 27, f: 28, w: 14, g: 28, r: 0.1, cl: 100, uv: 3 },
      { h: "15", t: 27, f: 28, w: 12, g: 24, r: 0,   cl: 60,  uv: 2 },
      { h: "16", t: 26, f: 27, w: 10, g: 20, r: 0,   cl: 100, uv: 1 },
    ],
  },
  {
    id: "frejus", name: "Fréjus", group: "Var · Est",
    warns: [{ t: "brand2" }],
    ov: { tempMax: 31, wind: 23, sun: 8.0, cloud: 9, uvMax: 8 },
    hours: [
      { h: "09", t: 27, f: 28, w: 16, g: 32, r: 0, cl: 5,  uv: 3 },
      { h: "10", t: 29, f: 30, w: 18, g: 36, r: 0, cl: 4,  uv: 5 },
      { h: "11", t: 30, f: 31, w: 20, g: 40, r: 0, cl: 6,  uv: 7 },
      { h: "12", t: 31, f: 32, w: 22, g: 44, r: 0, cl: 8,  uv: 8 },
      { h: "13", t: 31, f: 32, w: 23, g: 46, r: 0, cl: 9,  uv: 6 },
      { h: "14", t: 30, f: 31, w: 21, g: 42, r: 0, cl: 12, uv: 4 },
      { h: "15", t: 29, f: 30, w: 18, g: 36, r: 0, cl: 10, uv: 2 },
      { h: "16", t: 28, f: 29, w: 15, g: 30, r: 0, cl: 8,  uv: 1 },
    ],
  },
  {
    id: "sttropez", name: "Saint-Tropez", group: "Var · Golfe",
    warns: [{ t: "hitze" }, { t: "brand3" }],
    ov: { tempMax: 29, wind: 12, sun: 8.0, cloud: 33, uvMax: 7 },
    hours: [
      { h: "09", t: 25, f: 26, w: 8,  g: 16, r: 0, cl: 33, uv: 2 },
      { h: "10", t: 27, f: 28, w: 10, g: 20, r: 0, cl: 20, uv: 4 },
      { h: "11", t: 28, f: 29, w: 11, g: 22, r: 0, cl: 10, uv: 6 },
      { h: "12", t: 29, f: 30, w: 12, g: 24, r: 0, cl: 15, uv: 7 },
      { h: "13", t: 28, f: 29, w: 12, g: 24, r: 0, cl: 25, uv: 5 },
      { h: "14", t: 27, f: 28, w: 11, g: 22, r: 0, cl: 40, uv: 3 },
      { h: "15", t: 26, f: 27, w: 10, g: 20, r: 0, cl: 60, uv: 2 },
      { h: "16", t: 25, f: 26, w: 8,  g: 16, r: 0, cl: 80, uv: 1 },
    ],
  },
  {
    id: "collobrieres", name: "Collobrières", group: "Massif des Maures",
    warns: [{ t: "hitze" }, { t: "brand3" }, { t: "zugang", note: "Maures" }],
    ov: { tempMax: 34, wind: 13, sun: 8.0, cloud: 82, uvMax: 8 },
    hours: [
      { h: "09", t: 27, f: 29, w: 8,  g: 16, r: 0,   cl: 40,  uv: 2 },
      { h: "10", t: 30, f: 32, w: 10, g: 20, r: 0,   cl: 55,  uv: 4 },
      { h: "11", t: 32, f: 34, w: 12, g: 24, r: 0,   cl: 60,  uv: 6 },
      { h: "12", t: 34, f: 36, w: 13, g: 26, r: 0,   cl: 70,  uv: 8 },
      { h: "13", t: 33, f: 35, w: 13, g: 26, r: 0,   cl: 80,  uv: 6 },
      { h: "14", t: 32, f: 34, w: 12, g: 24, r: 0.2, cl: 100, uv: 4 },
      { h: "15", t: 30, f: 32, w: 10, g: 20, r: 0,   cl: 90,  uv: 2 },
      { h: "16", t: 28, f: 30, w: 8,  g: 16, r: 0,   cl: 100, uv: 1 },
    ],
  },
  {
    id: "marseille", name: "Marseille", group: "Bouches-du-Rhône",
    warns: [{ t: "hitze" }, { t: "brand4" }],
    ov: { tempMax: 32, wind: 35, sun: 8.0, cloud: 89, uvMax: 7 },
    hours: [
      { h: "09", t: 28, f: 30, w: 28, g: 50, r: 0,   cl: 60,  uv: 2 },
      { h: "10", t: 30, f: 32, w: 32, g: 56, r: 0,   cl: 70,  uv: 4 },
      { h: "11", t: 31, f: 33, w: 35, g: 62, r: 0,   cl: 80,  uv: 6 },
      { h: "12", t: 32, f: 34, w: 35, g: 64, r: 0,   cl: 85,  uv: 7 },
      { h: "13", t: 32, f: 34, w: 33, g: 60, r: 0,   cl: 89,  uv: 5 },
      { h: "14", t: 31, f: 33, w: 30, g: 56, r: 0.1, cl: 100, uv: 3 },
      { h: "15", t: 30, f: 32, w: 28, g: 52, r: 0,   cl: 95,  uv: 2 },
      { h: "16", t: 29, f: 31, w: 24, g: 46, r: 0,   cl: 100, uv: 1 },
    ],
  },
];

/* ── Fmt-Helfer ──────────────────────────────────────────────────────────── */
const cv2Fmt = (n, dec) => {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const num = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(num)) return "—";
  return dec != null ? num.toFixed(dec) : num.toLocaleString("de-DE");
};

/* Günstigster Einzelwert je Metrik (rein faktisch). */
function cv2BestByMetric() {
  const best = {};
  CV2_METRICS.forEach(m => {
    if (m.kind !== "num" || !m.highlight) return;
    const vals = CV2_LOCS.map(l => l.ov[m.key]).filter(v => v != null && !Number.isNaN(v));
    if (!vals.length) return;
    // Kein Highlight, wenn alle Orte denselben Wert haben (z.B. Sonne 8.0h überall)
    // — dann gibt es keinen „günstigsten“ Einzelwert.
    if (new Set(vals).size <= 1) return;
    best[m.key] = m.highlight === "max" ? Math.max(...vals) : Math.min(...vals);
  });
  return best;
}

/* ══════════════════════════════════════════════════════════════════════════
 * MAIN
 * ════════════════════════════════════════════════════════════════════════ */
function CompareEmailV2({ mobile = false, subscriptionName = "Le Var · Sommer" }) {
  const M = CV2_META;
  const px = mobile ? 16 : 28;

  // Region-weite Warn-Aggregation für den Lead + Quick-Take-Tags.
  const heatCount = CV2_LOCS.filter(l => l.warns.some(w => w.t === "hitze")).length;
  const brandMax  = Math.max(...CV2_LOCS.flatMap(l => l.warns.filter(w => w.t.startsWith("brand")).map(w => Number(w.t.slice(5)))));
  const brandMaxLoc = CV2_LOCS.find(l => l.warns.some(w => w.t === `brand${brandMax}`));
  const zugangCount = CV2_LOCS.filter(l => l.warns.some(w => w.t === "zugang")).length;

  return (
    <div style={{
      width: mobile ? 380 : 680, fontFamily: CV2_SANS, color: "#1d1c1a", background: "#fff",
      border: mobile ? "none" : "1px solid #d8d3c7",
      boxShadow: mobile ? "none" : "0 8px 32px rgba(0,0,0,0.06)",
      WebkitFontSmoothing: "antialiased",
    }}>

      {/* ─── Header ─────────────────────────────────────────────── */}
      <div style={{ padding: `${mobile ? 18 : 22}px ${px}px 0`, background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
        {mobile ? (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontFamily: CV2_MONO, fontSize: 9, letterSpacing: "0.12em", color: "#c45a2a", fontWeight: 600 }}>ORTS-VERGLEICH · {M.code}</div>
              <div style={{ fontFamily: CV2_MONO, fontSize: 9, letterSpacing: "0.12em", color: "#9a978d", fontWeight: 600 }}>GREGOR ZWANZIG</div>
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 6, lineHeight: 1.2 }}>{M.title}</div>
            <div style={{ fontSize: 12, color: "#6b6962", marginTop: 6, fontFamily: CV2_MONO }}>{M.dateLong}</div>
          </div>
        ) : (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
            <div>
              <div style={{ fontFamily: CV2_MONO, fontSize: 10, letterSpacing: "0.12em", color: "#c45a2a", fontWeight: 600 }}>ORTS-VERGLEICH · {M.code}</div>
              <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 4, lineHeight: 1.2 }}>{M.title}</div>
              <div style={{ fontSize: 13, color: "#6b6962", marginTop: 6, fontFamily: CV2_MONO }}>{M.dateLong}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: CV2_MONO, fontSize: 10, letterSpacing: "0.12em", color: "#9a978d", fontWeight: 600 }}>GREGOR ZWANZIG</div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{subscriptionName}</div>
              <div style={{ fontSize: 11, color: "#6b6962", marginTop: 2, fontFamily: CV2_MONO }}>auto · {M.created}</div>
            </div>
          </div>
        )}

        {/* Setup-Stats */}
        <div style={{
          display: "grid", gridTemplateColumns: mobile ? "1fr 1fr" : "repeat(4, 1fr)",
          gap: mobile ? "12px 0" : 0, padding: `${mobile ? 12 : 14}px 0`, borderTop: "1px solid #e6e1d3",
        }}>
          <CV2Stat label="Profil"   value="Wetter-Briefing" sub="alle Metriken" mobile={mobile} idx={0}/>
          <CV2Stat label="Orte"     value={CV2_LOCS.length} sub="verglichen" mobile={mobile} idx={1} last={mobile}/>
          <CV2Stat label="Horizont" value={M.horizon} sub={M.source} mobile={mobile} idx={2}/>
          <CV2Stat label="Erstellt" value={M.created} sub={M.createdDate} mobile={mobile} idx={3} last/>
        </div>
      </div>

      {/* ─── Amtliche-Warnungen-Lead (Trip-Vokabular: Akzent-Bar) ── */}
      <div style={{ padding: mobile ? "16px 16px 14px" : "18px 28px 16px" }}>
        <div style={{ borderLeft: "2px solid #c45a2a", paddingLeft: mobile ? 12 : 14 }}>
          <CV2Eyebrow accent>Amtliche Warnungen · aktiv</CV2Eyebrow>
          <div style={{ fontSize: mobile ? 14 : 16, lineHeight: 1.5, fontWeight: 500, marginTop: 6 }}>
            Für {heatCount} von {CV2_LOCS.length} Orten liegt eine Hitze­warnung vor, für das Massif des
            Maures und die Monts Toulonnais gilt ein Zugangs­verbot. Höchste Waldbrand­stufe:{" "}
            <span style={{ fontWeight: 700, color: "#8a1009" }}>Stufe {brandMax} · {brandMaxLoc.name}</span>.
          </div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
            <CV2Tag tone="warn">Extreme Hitze · {heatCount} Orte</CV2Tag>
            <CV2Tag tone="risk">Waldbrand Stufe {brandMax} · {brandMaxLoc.name}</CV2Tag>
            <CV2Tag tone="warn">Zugang gesperrt · {zugangCount} Gebiete</CV2Tag>
            <CV2Tag tone="info">Kein Niederschlag</CV2Tag>
          </div>
        </div>
      </div>

      {/* ─── 1 · Übersichtstabelle (Metriken × Orte, inkl. Warn-Zeile) ── */}
      <div style={{ padding: `${mobile ? 4 : 6}px ${px}px 0` }}>
        <CV2SectionHead accent="ÜBERSICHT" title={mobile ? "Alle Orte" : "Alle Orte · gewählte Metriken"} hint="grün = günstigster Wert · ← scrollen"/>
        <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch", marginTop: 12, border: "1px solid #e6e1d3" }}>
          <div style={{ minWidth: 760 }}><CV2Overview/></div>
        </div>
      </div>

      {/* ─── 2 · Stundentabellen · alle Orte ──────────────────────── */}
      <div style={{ padding: `${mobile ? 22 : 26}px ${px}px 0` }}>
        <CV2SectionHead accent="STUNDEN" title={mobile ? "Alle Orte · Verlauf" : "Stundenverlauf · alle Orte"} hint="09–16 Uhr"/>
      </div>
      {CV2_LOCS.map((loc, i) => <CV2LocationHours key={loc.id} loc={loc} mobile={mobile} px={px} first={i === 0}/>)}

      {/* ─── Risk-Legende ─────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "16px 16px" : "18px 28px", background: "#fbfaf6", borderTop: "1px solid #e6e1d3", marginTop: mobile ? 18 : 22 }}>
        <CV2Legend/>
      </div>

      {/* ─── Abo / nächster Versand ───────────────────────────────── */}
      <div style={{ padding: `${mobile ? 16 : 20}px ${px}px`, background: "#fbfaf6", borderTop: "1px solid #e6e1d3" }}>
        <div style={{ display: "grid", gridTemplateColumns: mobile ? "1fr" : "1fr 1fr", gap: mobile ? 16 : 20 }}>
          <div>
            <CV2Eyebrow>Dieses Abo</CV2Eyebrow>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{subscriptionName}</div>
            <div style={{ fontSize: 11, color: "#6b6962", marginTop: 4, fontFamily: CV2_MONO, lineHeight: 1.6 }}>
              {CV2_LOCS.length} Orte · Profil Wetter-Briefing<br/>
              Quelle: {M.source}
            </div>
          </div>
          <div>
            <CV2Eyebrow>Nächster Versand</CV2Eyebrow>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4, fontFamily: CV2_MONO }}>{M.next}</div>
            <div style={{ fontSize: 11, color: "#6b6962", marginTop: 4, lineHeight: 1.6 }}>
              Du bekommst diese E-Mail wegen deines Abos<br/>
              <strong style={{ color: "#1d1c1a" }}>{subscriptionName}</strong> in Gregor Zwanzig.
            </div>
          </div>
        </div>
      </div>

      {/* ─── App-Footer ───────────────────────────────────────────── */}
      <div style={{ padding: `16px ${px}px 20px`, background: "#1d1c1a", color: "#9a978d", fontSize: 11, fontFamily: CV2_MONO }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <div>
            <span style={{ color: "#fff", fontWeight: 600, letterSpacing: "0.06em" }}>GREGOR ZWANZIG</span>
            <span style={{ margin: "0 8px", color: "#5a5750" }}>·</span>
            Orts-Vergleich
          </div>
          {!mobile && <div>{M.createdDate} {M.created} · {M.source}</div>}
        </div>
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #3a3835", display: "flex", gap: mobile ? 10 : 16, fontSize: 10, flexWrap: "wrap" }}>
          <a href="#" style={{ color: "#c45a2a", textDecoration: "none" }}>Vergleich in App öffnen →</a>
          <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Abo bearbeiten</a>
          <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Orte ändern</a>
          {!mobile && <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Metriken ändern</a>}
          <a href="#" style={{ color: "#9a978d", textDecoration: "none", marginLeft: mobile ? 0 : "auto" }}>Abmelden</a>
        </div>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
 * Übersichtstabelle
 * ════════════════════════════════════════════════════════════════════════ */
function CV2Overview() {
  const best = cv2BestByMetric();
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: CV2_MONO, fontVariantNumeric: "tabular-nums" }}>
      <thead>
        <tr style={{ background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
          <th style={{ ...cv2Th("left"), minWidth: 96 }}>Metrik</th>
          {CV2_LOCS.map(l => (
            <th key={l.id} style={cv2Th("center")}>
              <span style={{ fontFamily: CV2_SANS, fontSize: 11, fontWeight: 600, color: "#1d1c1a", lineHeight: 1.2, display: "block" }}>{l.name}</span>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {CV2_METRICS.map(m => (
          <tr key={m.key} style={{ borderBottom: "1px solid #f0ece1" }}>
            <td style={{ ...cv2Td("left"), fontFamily: CV2_SANS, color: "#3a3835", fontWeight: 500, fontSize: 12 }}>{m.label}</td>
            {CV2_LOCS.map(l => {
              if (m.kind === "warn") {
                return <td key={l.id} style={{ ...cv2Td("center"), padding: "7px 5px", verticalAlign: "middle" }}><CV2WarnStack warns={l.warns}/></td>;
              }
              const v = l.ov[m.key];
              const sev = m.sev ? m.sev(v) : "ok";
              const t = CV2_RISK_CELL[sev];
              const isBest = m.highlight && v === best[m.key];
              return (
                <td key={l.id} style={{
                  ...cv2Td("center"),
                  background: isBest ? "rgba(61,107,58,0.14)" : (t ? t.bg : "transparent"),
                  color: isBest ? "#2c4f29" : (t ? t.color : "#1d1c1a"),
                  fontWeight: isBest || t ? 700 : 500,
                }}>
                  {cv2Fmt(v, m.decimals)}{m.unit ? (m.unit === "°C" || m.unit === "%" ? m.unit : " " + m.unit) : ""}
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* Warn-Zellen-Inhalt: kompakte Chips gestapelt (max Lesbarkeit in enger Zelle). */
function CV2WarnStack({ warns }) {
  if (!warns || !warns.length) {
    return <span style={{ color: "#b8b4a8", fontSize: 12 }}>—</span>;
  }
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", gap: 3, alignItems: "center" }}>
      {warns.map((w, i) => {
        const meta = CV2_WARN[w.t];
        const t = CV2_RISK_CELL[meta.sev];
        return (
          <span key={i} style={{
            display: "inline-block", fontSize: 9.5, fontWeight: 700, letterSpacing: "0.01em",
            padding: "2px 6px", whiteSpace: "nowrap",
            background: t.bg, color: t.color, border: `1px solid ${t.color}22`,
          }}>{meta.short}</span>
        );
      })}
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
 * Stundentabelle je Ort — mit vorangestelltem Warn-Streifen
 * ════════════════════════════════════════════════════════════════════════ */
function CV2LocationHours({ loc, mobile, px, first }) {
  return (
    <div style={{ padding: `${first ? 14 : 20}px ${px}px 0` }}>
      {/* Ort-Kopf */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: mobile ? "flex-start" : "baseline", gap: 8, flexWrap: "wrap", paddingBottom: 8, borderBottom: "2px solid #1d1c1a" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, minWidth: 0 }}>
          <span style={{ fontFamily: CV2_MONO, fontSize: 11, fontWeight: 600, color: "#c45a2a", letterSpacing: "0.1em" }}>ORT</span>
          <span style={{ fontSize: mobile ? 14 : 15, fontWeight: 600 }}>{loc.name}</span>
          <span style={{ fontFamily: CV2_MONO, fontSize: 11, color: "#9a978d" }}>{loc.group}</span>
        </div>
      </div>

      {/* Warn-Streifen: amtliche Warnungen in Langform, farbcodiert */}
      {loc.warns.length > 0 && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 10 }}>
          {loc.warns.map((w, i) => {
            const meta = CV2_WARN[w.t];
            const t = CV2_RISK_CELL[meta.sev];
            const label = w.t === "zugang" ? `Zugang eingeschränkt${w.note ? " — " + w.note : ""}` : CV2_WARN_LONG[w.t];
            return (
              <span key={i} style={{
                display: "inline-flex", alignItems: "center", gap: 6,
                fontFamily: CV2_MONO, fontSize: 10.5, fontWeight: 600,
                padding: "3px 9px", background: t.bg, color: t.color, borderLeft: `3px solid ${t.color}`,
              }}>{label}</span>
            );
          })}
        </div>
      )}

      {/* Stunden-Tabelle */}
      {mobile
        ? <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch", marginTop: 12, border: "1px solid #e6e1d3" }}>
            <div style={{ minWidth: 560 }}><CV2HourTable hours={loc.hours}/></div>
          </div>
        : <CV2HourTable hours={loc.hours}/>}
    </div>
  );
}

function CV2HourTable({ hours }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", marginTop: 12, fontSize: 12, fontFamily: CV2_MONO, fontVariantNumeric: "tabular-nums" }}>
      <thead>
        <tr style={{ background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
          <th style={cv2Hh("left")}>Zeit</th>
          <th style={cv2Hh()}>Temp</th>
          <th style={cv2Hh()}>Gef.</th>
          <th style={cv2Hh()}>Wind</th>
          <th style={cv2Hh()}>Böen</th>
          <th style={cv2Hh()}>Regen</th>
          <th style={cv2Hh()}>Wolken</th>
          <th style={cv2Hh()}>UV</th>
        </tr>
      </thead>
      <tbody>
        {hours.map((r, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #f0ece1" }}>
            <td style={{ ...cv2Hd("left"), color: "#6b6962" }}>{r.h}:00</td>
            <td style={cv2SevTd(cv2SevTemp(r.t))}>{r.t}°</td>
            <td style={cv2Hd()}>{r.f}°</td>
            <td style={cv2SevTd(cv2SevWind(r.w))}>{r.w}</td>
            <td style={cv2SevTd(cv2SevGust(r.g))}>{r.g}</td>
            <td style={cv2SevTd(cv2SevRain(r.r))}>{r.r > 0 ? r.r.toFixed(1) : "·"}</td>
            <td style={{ ...cv2Hd(), color: r.cl >= 70 ? "#6b6962" : "#9a978d" }}>{r.cl}%</td>
            <td style={cv2SevTd(cv2SevUV(r.uv))}>{r.uv}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
 * Bausteine
 * ════════════════════════════════════════════════════════════════════════ */
function CV2Eyebrow({ children, accent }) {
  return <span style={{ fontFamily: CV2_MONO, fontSize: 10, letterSpacing: "0.12em", color: accent ? "#c45a2a" : "#9a978d", fontWeight: 600, textTransform: "uppercase" }}>{children}</span>;
}

function CV2SectionHead({ accent, title, hint }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", paddingBottom: 8, borderBottom: "2px solid #1d1c1a", gap: 12, flexWrap: "wrap" }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span style={{ fontFamily: CV2_MONO, fontSize: 11, fontWeight: 600, color: "#c45a2a", letterSpacing: "0.1em" }}>{accent}</span>
        <span style={{ fontSize: 14, fontWeight: 600 }}>{title}</span>
      </div>
      {hint && <div style={{ fontFamily: CV2_MONO, fontSize: 10, color: "#9a978d" }}>{hint}</div>}
    </div>
  );
}

function CV2Stat({ label, value, sub, last, mobile, idx }) {
  const showBorder = mobile ? (idx % 2 === 0) : !last;
  return (
    <div style={{ borderRight: showBorder ? "1px solid #e6e1d3" : "none", paddingRight: 10, paddingLeft: mobile && idx % 2 === 1 ? 10 : 0 }}>
      <div style={{ fontFamily: CV2_MONO, fontSize: 9, letterSpacing: "0.1em", color: "#9a978d", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4, lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 10, color: "#9a978d", marginTop: 3, fontFamily: CV2_MONO }}>{sub}</div>
    </div>
  );
}

function CV2Tag({ children, tone }) {
  const t = CV2_TAG[tone] || CV2_TAG.info;
  return <span style={{ display: "inline-flex", alignItems: "center", padding: "4px 10px", background: t.bg, color: t.fg, border: `1px solid ${t.border}`, fontSize: 11, fontWeight: 600, fontFamily: CV2_MONO, letterSpacing: "0.02em" }}>{children}</span>;
}

function CV2Dot({ r }) {
  const map = { ok: "#2f8a3e", caution: "#e3b008", warn: "#e07b1a", danger: "#c52a22" };
  const bg = map[r] || "#c8c4b8";
  return <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: bg, boxShadow: `0 0 0 3px ${bg}22` }}/>;
}

function CV2Legend() {
  const items = [["ok", "unkritisch"], ["caution", "Achtung"], ["warn", "Warnung"], ["danger", "Gefahr"]];
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "4px 16px", fontFamily: CV2_MONO, fontSize: 10, color: "#6b6962" }}>
      <span style={{ fontWeight: 600, color: "#9a978d", letterSpacing: "0.08em", textTransform: "uppercase" }}>Risk</span>
      {items.map(([r, l]) => <span key={r} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}><CV2Dot r={r}/>{l}</span>)}
      <span style={{ marginLeft: "auto", color: "#9a978d" }}>Warn-Kürzel: Hitze · Brand·Stufe · Zugang</span>
    </div>
  );
}

/* ── Zell-Styles ─────────────────────────────────────────────────────────── */
function cv2Th(align) {
  return { fontSize: 10, color: "#9a978d", fontWeight: 600, padding: "9px 5px", textAlign: align || "center", borderRight: "1px solid #f0ece1", verticalAlign: "bottom" };
}
function cv2Td(align) {
  return { fontSize: 12.5, padding: "8px 5px", textAlign: align || "center", color: "#1d1c1a", borderRight: "1px solid #f0ece1" };
}
function cv2Hh(align) {
  return { fontSize: 11, color: "#3a3835", fontWeight: 600, padding: "6px 4px", textAlign: align || "center", borderRight: "1px solid #f0ece1" };
}
function cv2Hd(align) {
  return { fontSize: 13, padding: "8px 4px", textAlign: align || "center", color: "#1d1c1a", fontWeight: 500, borderRight: "1px solid #f0ece1" };
}
function cv2SevTd(level) {
  const t = CV2_RISK_CELL[level];
  return { fontSize: 13, padding: "8px 4px", textAlign: "center", color: t ? t.color : "#1d1c1a", background: t ? t.bg : "transparent", fontWeight: t ? 700 : 500, borderRight: "1px solid #f0ece1" };
}

window.CompareEmailV2 = CompareEmailV2;
