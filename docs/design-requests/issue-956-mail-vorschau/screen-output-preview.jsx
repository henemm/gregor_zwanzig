/* Email- und SMS-Vorschau v3
 * Visuell und typografisch konsistent mit der Haupt-App:
 * - Gleiche Tokens (g-accent, g-ink, g-rule, mono-Font)
 * - Eyebrow/Pill/Card-Sprache wie im UI
 * - Spalten-Gruppierung (Temp · Wind · Niederschlag · Sicht · Sonst)
 * - Risk-Tag pro Stunde statt 14 dichten Spalten
 * - Klare Hierarchie: Hero → Quick-Take → Stirnlampe → Segment-Tabellen → Folge-Etappen → Footer
 */

const EMAIL_FONT_STACK = "'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
const EMAIL_MONO_STACK = "'JetBrains Mono', 'SF Mono', Menlo, monospace";

// Tausender-Trennzeichen im deutschen Format (1.235) für bessere Lesbarkeit größerer Zahlen.
const fmt = (n) => {
  if (n === null || n === undefined || n === "") return n;
  const num = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(num)) return n;
  return num.toLocaleString("de-DE");
};

function EmailPreview({ stage, trip, scale = 1, mobile = false, showMetricsSummary = false }) {
  const seg1 = {
    title: "Segment 1",
    when: "08:00 – 10:00",
    km: 4.6, asc: 1211, dsc: 0, fromAlt: 1144, toAlt: 1210, fromKm: 0.0, toKm: 4.6,
    rows: [
      { time: "08", temp: 8.2, feels: 7.1, wind: 5,  gust: 12, dir: "NE", precip: 0,   rainP: 8,  thnd: 0,  cloud: 70, vis: 1.2, uv: 0.4, fl: 2310, hum: 82, dew: 5.8, sun: 15, cldLow: 45, risk: "ok" },
      { time: "09", temp: 9.4, feels: 8.0, wind: 6,  gust: 14, dir: "NE", precip: 0,   rainP: 12, thnd: 0,  cloud: 65, vis: 1.4, uv: 1.2, fl: 2335, hum: 78, dew: 6.9, sun: 20, cldLow: 40, risk: "ok" },
      { time: "10", temp: 10.3, feels: 8.2, wind: 7, gust: 16, dir: "NE", precip: 0,   rainP: 13, thnd: 0,  cloud: 60, vis: 1.6, uv: 1.6, fl: 2360, hum: 75, dew: 7.3, sun: 25, cldLow: 35, risk: "ok" },
    ]
  };
  const seg2 = {
    title: "Segment 2",
    when: "10:00 – 11:40",
    km: 3.3, asc: 203, dsc: 0, fromAlt: 1210, toAlt: 1413, fromKm: 4.6, toKm: 7.9,
    rows: [
      { time: "11", temp: 11.0, feels: 8.1, wind: 12, gust: 24, dir: "E",  precip: 0.1, rainP: 25, thnd: 8,  cloud: 80, vis: 2.15, uv: 2.0, fl: 2420, hum: 88, dew: 8.4, sun: 8,  cldLow: 65, risk: "caution" },
      { time: "12", temp: 9.2,  feels: 7.4, wind: 6,  gust: 48, dir: "SE", precip: 5.5, rainP: 72, thnd: 20, cloud: 95, vis: 3.5,  uv: 1.8, fl: 2530, hum: 95, dew: 7.9, sun: 0,  cldLow: 80, risk: "warn" },
    ]
  };

  const dest = {
    title: "Wetter am Ziel · Sillianer Hütte",
    when: `12:45 – 14:45 · ${fmt(2447)} m`,
    rows: [
      { time: "13", temp: 8.7, feels: 6.6, wind: 8,  gust: 55, dir: "NE", precip: 9.2, rainP: 90, thnd: 38, cloud: 95, vis: 2.05, uv: 1.6, fl: 2400, hum: 93, dew: 7.4, sun: 0,  cldLow: 78, risk: "danger" },
      { time: "14", temp: 9.9, feels: 8.4, wind: 4,  gust: 11, dir: "NE", precip: 0.2, rainP: 63, thnd: 12, cloud: 85, vis: 2.4,  uv: 2.4, fl: 2450, hum: 89, dew: 8.6, sun: 5,  cldLow: 68, risk: "caution" },
      { time: "15", temp: 11.1,feels: 8.9, wind: 10, gust: 20, dir: "E",  precip: 0,   rainP: 48, thnd: 0,  cloud: 70, vis: 1.7,  uv: 1.7, fl: 2550, hum: 82, dew: 9.1, sun: 15, cldLow: 52, risk: "ok" },
    ]
  };

  const allRows = [...seg1.rows, ...seg2.rows, ...dest.rows];

  return (
    <div style={{
      width: mobile ? 380 : 680, fontFamily: EMAIL_FONT_STACK, color: "#1d1c1a",
      background: "#fff",
      border: mobile ? "none" : "1px solid #d8d3c7",
      boxShadow: mobile ? "none" : "0 8px 32px rgba(0,0,0,0.06)",
      transform: `scale(${scale})`, transformOrigin: "top left",
      WebkitFontSmoothing: "antialiased",
    }}>

      {/* ─── Header ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "18px 16px 0" : "22px 28px 0", background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
        {mobile ? (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 9, letterSpacing: "0.12em", color: "#c45a2a", fontWeight: 600 }}>
                MORGEN-BRIEFING · {stage.code}
              </div>
              <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 9, letterSpacing: "0.12em", color: "#9a978d", fontWeight: 600 }}>
                GREGOR ZWANZIG
              </div>
            </div>
            <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 6, color: "#1d1c1a", lineHeight: 1.2 }}>
              {stage.title.replace(/^[^:]+: /,"")}
            </div>
            <div style={{ fontSize: 12, color: "#6b6962", marginTop: 6, fontFamily: EMAIL_MONO_STACK }}>
              Mi · 06.05.2026 · 06:01 · <span style={{ color: "#1d1c1a", fontWeight: 600 }}>{trip.shortName}</span> · Etappe {stage.code.split("_")[1]}/12
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
            <div>
              <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 10, letterSpacing: "0.12em", color: "#c45a2a", fontWeight: 600 }}>
                MORGEN-BRIEFING · {stage.code}
              </div>
              <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 4, color: "#1d1c1a" }}>
                {stage.title.replace(/^[^:]+: /,"")}
              </div>
              <div style={{ fontSize: 13, color: "#6b6962", marginTop: 4, fontFamily: EMAIL_MONO_STACK }}>
                Mi · 06.05.2026 · 06:01 MESZ
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 10, letterSpacing: "0.12em", color: "#9a978d", fontWeight: 600 }}>
                GREGOR ZWANZIG
              </div>
              <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4, color: "#1d1c1a" }}>
                {trip.shortName}
              </div>
              <div style={{ fontSize: 12, color: "#6b6962", marginTop: 2, fontFamily: EMAIL_MONO_STACK }}>
                Etappe {stage.code.split("_")[1]} / 12
              </div>
            </div>
          </div>
        )}

        {/* Etappen-Stats */}
        <div style={{
          display: "grid",
          gridTemplateColumns: mobile ? "repeat(3, 1fr)" : "repeat(5, 1fr)",
          rowGap: mobile ? 10 : 0,
          padding: "14px 0",
          borderTop: "1px solid #e6e1d3",
        }}>
          <EmailStat label="Distanz"  value={`${fmt(stage.km)}`}      unit="km" mobile={mobile} idx={0}/>
          <EmailStat label="Aufstieg" value={`↑${fmt(stage.ascent)}`}  unit="m"  mobile={mobile} idx={1}/>
          <EmailStat label="Abstieg"  value={`↓${fmt(stage.descent)}`} unit="m"  mobile={mobile} idx={2} last={mobile}/>
          <EmailStat label="Max Höhe" value={`${fmt(stage.maxElev)}`} unit="m"   mobile={mobile} idx={3}/>
          <EmailStat label="Segmente" value={`${stage.waypoints.length - 1}`} unit="" mobile={mobile} idx={4} last/>
        </div>
      </div>

      {/* ─── Tageslage-Lead (immer sichtbar) ──────────────────────────
       * Bündelt den Etappen-Summary-Satz + Vortag-Vergleich in EINEM
       * Akzent-Bar-Lead. Beide teilen dieselbe linke Kante (2px-Bar) —
       * kein zweiter farbiger Callout, kein Indentation-Versatz. */}
      <div style={{ padding: mobile ? "16px 16px 14px" : "18px 28px 16px" }}>
        <div style={{ borderLeft: "2px solid #c45a2a", paddingLeft: mobile ? 12 : 14 }}>
          <EmailEyebrow accent>Tageslage</EmailEyebrow>
          <div style={{ fontSize: mobile ? 14 : 16, lineHeight: 1.5, color: "#1d1c1a", fontWeight: 500, marginTop: 6 }}>
            {stage.summary}
          </div>
          <EmailVortag text="heute bessere Sicht als gestern" trend="better"/>
        </div>
      </div>

      {/* ─── Quick-Take-Tags / Metriken-Überblick (umschaltbar) ─────── */}
      {!showMetricsSummary && <div style={{ padding: mobile ? "0 16px 14px" : "0 28px 16px" }}>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          <EmailTag tone="warn">Regen ab 11:00</EmailTag>
          <EmailTag tone="warn">Böen bis 25 km/h</EmailTag>
          <EmailTag tone="ok">Kein Gewitter</EmailTag>
          <EmailTag tone="info">UV mäßig (3.5)</EmailTag>
          <EmailTag tone="info">0°-Linie {fmt(2530)} m</EmailTag>
        </div>
      </div>}

      {showMetricsSummary && <EmailMetricsSummary rows={allRows} mobile={mobile}/>}

      {/* ─── Segmente ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "0 16px" : "0 28px" }}>
        <EmailEyebrow>Etappen-Verlauf</EmailEyebrow>
      </div>
      <EmailSegmentBlock seg={seg1} idx={1} mobile={mobile}/>
      <EmailSegmentBlock seg={seg2} idx={2} mobile={mobile}/>

      {/* ─── Wetter am Ziel ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "18px 16px 16px" : "20px 28px 0", background: "#fbfaf6", borderTop: "1px solid #e6e1d3", marginTop: 16 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10, gap: 10, flexWrap: "wrap" }}>
          <div>
            <EmailEyebrow accent>Ankunft · Wetter am Ziel</EmailEyebrow>
            <div style={{ fontSize: mobile ? 14 : 16, fontWeight: 600, marginTop: 4 }}>{dest.title}</div>
          </div>
          <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: mobile ? 11 : 12, color: "#6b6962" }}>{dest.when}</div>
        </div>
        {mobile ? <EmailTableScroll rows={dest.rows} mobile/> : <EmailDataTable rows={dest.rows}/>}
      </div>

      {/* ─── Folge-Etappen ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "20px 16px 12px" : "24px 28px 16px", background: "#fbfaf6" }}>
        <EmailEyebrow>Ausblick · nächste 3 Tage</EmailEyebrow>
        <OutlookTable rows={OUTLOOK_ROWS} mobile={mobile}/>
      </div>

      {/* ─── Antwort-Kommandos ────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "14px 16px 16px" : "16px 28px 18px", background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
        <EmailEyebrow>Antwort-Kommandos</EmailEyebrow>
        <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: mobile ? "1fr 1fr" : "repeat(3, 1fr)", gap: "6px 24px" }}>
          {[
            { cmd: "PAUSE 2d", desc: "Briefings pausieren" },
            { cmd: "SKIP",     desc: "Nächstes überspringen" },
            { cmd: "STOP",     desc: "Dauerhaft deaktivieren" },
            { cmd: "STATUS",   desc: "Trip-Status abrufen" },
            { cmd: "CONFIG",   desc: "Spalten ändern" },
            { cmd: "HELP",     desc: "Alle Kommandos" },
          ].map(c => (
            <div key={c.cmd} style={{ display: "flex", alignItems: "baseline", gap: 8 }}>
              <span style={{ fontFamily: EMAIL_MONO_STACK, fontSize: mobile ? 10 : 11, fontWeight: 700, color: "#1d1c1a", minWidth: 70, flexShrink: 0 }}>{c.cmd}</span>
              <span style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 10, color: "#9a978d" }}>{c.desc}</span>
            </div>
          ))}
        </div>
        <div style={{ marginTop: 8, fontFamily: EMAIL_MONO_STACK, fontSize: 10, color: "#b8b4a8" }}>Antworte auf diese E-Mail mit einem Schlüsselwort.</div>
      </div>

      {/* ─── Risk-Legende (einmal pro Mail) ───────────────────────── */}
      <div style={{ padding: mobile ? "12px 16px" : "12px 28px", background: "#fbfaf6", borderTop: "1px solid #e6e1d3", borderBottom: "1px solid #e6e1d3" }}>
        <RiskLegend mobile={mobile}/>
      </div>

      {/* ─── Footer ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "14px 16px 18px" : "16px 28px 20px", background: "#1d1c1a", color: "#9a978d", fontSize: 11, fontFamily: EMAIL_MONO_STACK }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <div>
            <span style={{ color: "#fff", fontWeight: 600, letterSpacing: "0.06em" }}>GREGOR ZWANZIG</span>
            <span style={{ margin: "0 8px", color: "#5a5750" }}>·</span>
            Morgen-Briefing
          </div>
          {!mobile && <div>2026-05-06 05:01 UTC · openmeteo · icon_d2</div>}
        </div>
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #3a3835", display: "flex", gap: mobile ? 10 : 16, fontSize: 10, flexWrap: "wrap" }}>
          <a href="#" style={{ color: "#c45a2a", textDecoration: "none" }}>Trip-Übersicht öffnen →</a>
          <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Briefing-Zeitplan</a>
          {!mobile && <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Spalten ändern</a>}
          <a href="#" style={{ color: "#9a978d", textDecoration: "none", marginLeft: mobile ? 0 : "auto" }}>Abmelden</a>
        </div>
      </div>
    </div>
  );
}

/* ───────────── Email-Bausteine ───────────── */

function EmailEyebrow({ children, accent }) {
  return (
    <span style={{
      fontFamily: EMAIL_MONO_STACK, fontSize: 10, letterSpacing: "0.12em",
      color: accent ? "#c45a2a" : "#9a978d", fontWeight: 600, textTransform: "uppercase",
    }}>{children}</span>
  );
}

function EmailStat({ label, value, unit, last, mobile, idx }) {
  // Mobile: 3-Spalten-Grid → Border nur in den ersten zwei Spalten der Zeile.
  const showBorder = mobile
    ? (idx % 3 !== 2 && !last)
    : !last;
  return (
    <div style={{ borderRight: showBorder ? "1px solid #e6e1d3" : "none", paddingRight: 12, paddingLeft: mobile && idx % 3 !== 0 ? 10 : 0 }}>
      <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 9, letterSpacing: "0.1em", color: "#9a978d", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: mobile ? 15 : 18, fontWeight: 600, marginTop: 4, fontFamily: EMAIL_MONO_STACK, fontVariantNumeric: "tabular-nums", color: "#1d1c1a" }}>
        {value}<span style={{ fontSize: 11, color: "#9a978d", fontWeight: 400, marginLeft: 3 }}>{unit}</span>
      </div>
    </div>
  );
}

function EmailTag({ children, tone }) {
  const tones = {
    ok:   { bg: "#dcf2e1", fg: "#14532d", border: "#86c89a" },
    warn: { bg: "#fde6cc", fg: "#7c2d12", border: "#f0a060" },
    risk: { bg: "#fadcd6", fg: "#7f1d1d", border: "#e88472" },
    info: { bg: "#dde8f3", fg: "#1e3a5f", border: "#8aacd0" },
  };
  const t = tones[tone] || tones.info;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", padding: "4px 10px",
      background: t.bg, color: t.fg, border: `1px solid ${t.border}`,
      fontSize: 11, fontWeight: 600, fontFamily: EMAIL_MONO_STACK, letterSpacing: "0.02em",
    }}>{children}</span>
  );
}

/* Vortag-Vergleich — dezente Mono-Zeile, KEIN zweiter Callout.
 * trend: better (▲ grün) · worse (▼ orange) · same (▬ neutral). */
function EmailVortag({ text, trend = "same" }) {
  const map = {
    better: { sym: "▲", color: "#15803d" },
    worse:  { sym: "▼", color: "#c2410c" },
    same:   { sym: "▬", color: "#6b6962" },
  };
  const t = map[trend] || map.same;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, paddingTop: 10, borderTop: "1px solid #f0ece1" }}>
      <span style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 9, letterSpacing: "0.12em", color: "#9a978d", fontWeight: 600, textTransform: "uppercase" }}>vs. Gestern</span>
      <span style={{ color: t.color, fontSize: 9 }}>{t.sym}</span>
      <span style={{ fontSize: 12.5, color: "#3a3835" }}>{text}</span>
    </div>
  );
}

function DaylightBar() {
  return (
    <svg width="180" height="40" viewBox="0 0 180 40">
      <rect x="0" y="14" width="180" height="12" fill="#e6e1d3"/>
      <rect x="38" y="14" width="116" height="12" fill="#c45a2a" opacity="0.85"/>
      <rect x="32" y="14" width="6" height="12" fill="#c45a2a" opacity="0.4"/>
      <rect x="154" y="14" width="6" height="12" fill="#c45a2a" opacity="0.4"/>
      <text x="0"   y="38" fill="#9a978d" fontSize="9" fontFamily={EMAIL_MONO_STACK}>00</text>
      <text x="42"  y="38" fill="#1d1c1a" fontSize="9" fontFamily={EMAIL_MONO_STACK} fontWeight="600">06</text>
      <text x="86"  y="38" fill="#9a978d" fontSize="9" fontFamily={EMAIL_MONO_STACK}>12</text>
      <text x="146" y="38" fill="#1d1c1a" fontSize="9" fontFamily={EMAIL_MONO_STACK} fontWeight="600">21</text>
      <text x="170" y="38" fill="#9a978d" fontSize="9" fontFamily={EMAIL_MONO_STACK}>24</text>
    </svg>
  );
}

function EmailSegmentBlock({ seg, idx, mobile }) {
  return (
    <div style={{ padding: mobile ? "14px 16px 0" : "14px 28px 0" }}>
      <div style={{
        display: "flex", justifyContent: "space-between",
        alignItems: mobile ? "flex-start" : "baseline",
        flexDirection: mobile ? "column" : "row",
        gap: mobile ? 4 : 0,
        paddingBottom: 8, borderBottom: "2px solid #1d1c1a", marginBottom: 0,
      }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
          <span style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, fontWeight: 600, color: "#c45a2a", letterSpacing: "0.1em" }}>SEG {idx}</span>
        </div>
        <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, color: "#6b6962" }}>
          {seg.when} · {seg.fromKm.toFixed(1)} km - {seg.toKm.toFixed(1)} km · {fmt(seg.fromAlt)} - {fmt(seg.toAlt)} m
        </div>
      </div>
      {mobile ? <EmailTableScroll rows={seg.rows} mobile/> : <EmailDataTable rows={seg.rows}/>}
    </div>
  );
}

function EmailDataTable({ rows }) {
  // Spalten gruppiert: Zeit | Temp-Block | Wind-Block | Niedersch-Block | Sicht/UV | Höhe
  const groupBg = "#fbfaf6";
  return (
    <React.Fragment>
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: EMAIL_MONO_STACK, fontVariantNumeric: "tabular-nums" }}>
      <thead>
        <tr style={{ background: "#fff", borderBottom: "1px solid #e6e1d3" }}>
          <th style={hCellStyle("left")}>Time</th>
          <th style={hCellStyle()}>Temp</th>
          <th style={hCellStyle()}>Feels</th>
          <th style={hCellStyle()}>Wind</th>
          <th style={hCellStyle()}>Gust</th>
          <th style={hCellStyle()}>WDir</th>
          <th style={hCellStyle()}>Rain</th>
          <th style={hCellStyle()}>Rain%</th>
          <th style={hCellStyle()}>Thndr%</th>
          <th style={hCellStyle()}>Visib</th>
          <th style={hCellStyle()}>UV</th>
          <th style={hCellStyle()}>0°Line</th>
          <th style={hCellStyle("center")}>Risk</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #f0ece1" }}>
            <td style={dCellStyle("left", true)}>{r.time}</td>
            <td style={dCellStyle()}>{r.temp.toFixed(1)}</td>
            <td style={dCellStyle()}>{r.feels.toFixed(1)}</td>
            <td style={sevCellStyle("center", sevWind(r.wind))}>{r.wind}</td>
            <td style={sevCellStyle("center", sevGust(r.gust))}>{r.gust}</td>
            <td style={dCellStyle()}>{r.dir}</td>
            <td style={sevCellStyle("center", sevRain(r.precip))}>{r.precip > 0 ? r.precip.toFixed(1) : "·"}</td>
            <td style={sevCellStyle("center", sevRainP(r.rainP))}>{r.rainP}</td>
            <td style={sevCellStyle("center", sevThnd(r.thnd))}>{r.thnd > 0 ? r.thnd : "·"}</td>
            <td style={sevCellStyle("center", sevVis(r.vis))}>{r.vis.toFixed(1)}</td>
            <td style={dCellStyle()}>{r.uv.toFixed(1)}</td>
            <td style={dCellStyle()}>{fmt(r.fl)}</td>
            <td style={{ ...dCellStyle("center"), padding: "8px 4px" }}><RiskDot r={r.risk}/></td>
          </tr>
        ))}
      </tbody>
    </table>
    </React.Fragment>
  );
}

function RiskLegend({ mobile }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: "4px 16px", fontFamily: EMAIL_MONO_STACK, fontSize: 10, color: "#6b6962" }}>
      <span style={{ fontWeight: 600, color: "#9a978d", letterSpacing: "0.08em", textTransform: "uppercase" }}>Risk</span>
      <RiskLegendItem r="ok" label="unkritisch"/>
      <RiskLegendItem r="caution" label="Achtung"/>
      <RiskLegendItem r="warn" label="Warnung"/>
      <RiskLegendItem r="danger" label="Gefahr"/>
    </div>
  );
}

function RiskLegendItem({ r, label }) {
  return (
    <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
      <RiskDot r={r}/>{label}
    </span>
  );
}

function hGroupStyle(color) {
  return {
    fontSize: 9, letterSpacing: "0.1em", textTransform: "uppercase",
    color: color || "#9a978d", fontWeight: 600,
    padding: "5px 4px 4px", borderBottom: "1px solid #e6e1d3",
    borderRight: "1px solid #f0ece1",
  };
}
function hCellStyle(align) {
  return {
    fontSize: 11, color: "#3a3835", fontWeight: 600,
    padding: "6px 4px", textAlign: align || "center",
    borderRight: "1px solid #f0ece1",
  };
}
function dCellStyle(align, bold, color) {
  return {
    fontSize: 13, padding: "8px 4px",
    textAlign: align || "center",
    color: color || "#1d1c1a",
    fontWeight: bold ? 700 : 500,
    borderRight: "1px solid #f0ece1",
  };
}

/* ── Einheitliche 4-Stufen-Schwere (gleiche Skala wie RiskDot) ──
 * ok = unkritisch · caution = Achtung · warn = Warnung · danger = Gefahr.
 * Text-Töne sind dunklere, WCAG-AA-taugliche Varianten der Dot-Farben. */
const RISK_TEXT = {
  caution: "#7a5f00",
  warn:    "#a8480c",
  danger:  "#a81e17",
};
/* Getönte Zell-Hintergründe — Schweregrad sofort sichtbar, Text bleibt dunkel + lesbar. */
const RISK_CELL = {
  caution: { bg: "#fbeeb8", color: "#5e4a00" },
  warn:    { bg: "#fad6b8", color: "#8a3506" },
  danger:  { bg: "#f6c5bf", color: "#8a1009" },
};
function sevWind(v)  { return v > 40 ? "danger" : v > 30 ? "warn" : v > 20 ? "caution" : "ok"; }
function sevGust(v)  { return v > 60 ? "danger" : v > 45 ? "warn" : v > 30 ? "caution" : "ok"; }
function sevRain(v)  { return v > 8  ? "danger" : v > 4  ? "warn" : v > 1  ? "caution" : "ok"; }
function sevRainP(v) { return v > 85 ? "danger" : v > 70 ? "warn" : v > 50 ? "caution" : "ok"; }
function sevThnd(v)  { return v >= 30 ? "danger" : v >= 15 ? "warn" : v > 0 ? "caution" : "ok"; }
function sevVis(v)   { return v < 0.5 ? "danger" : v < 1 ? "warn" : v < 2 ? "caution" : "ok"; }
function sevCellStyle(align, level) {
  const t = RISK_CELL[level];
  return {
    fontSize: 13, padding: "8px 4px",
    textAlign: align || "center",
    color: t ? t.color : "#1d1c1a",
    background: t ? t.bg : "transparent",
    fontWeight: t ? 700 : 500,
    borderRight: "1px solid #f0ece1",
  };
}

/* Mobile: echte Tabelle, horizontal scrollbar (kein Umbau zur Liste). */
function EmailTableScroll({ rows, mobile }) {
  if (!mobile) return <EmailDataTable rows={rows}/>;
  return (
    <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch", marginTop: 12, border: "1px solid #e6e1d3" }}>
      <div style={{ minWidth: 600 }}>
        <EmailDataTable rows={rows} embedded/>
      </div>
    </div>
  );
}

function RiskDot({ r }) {
  const map = {
    ok:      { bg: "#2f8a3e", ring: "rgba(47,138,62,0.18)" },
    caution: { bg: "#e3b008", ring: "rgba(227,176,8,0.22)" },
    warn:    { bg: "#e07b1a", ring: "rgba(224,123,26,0.22)" },
    danger:  { bg: "#c52a22", ring: "rgba(197,42,34,0.22)" },
    // Backward-Compat-Aliase
    watch:   { bg: "#e07b1a", ring: "rgba(224,123,26,0.22)" },
    risk:    { bg: "#c52a22", ring: "rgba(197,42,34,0.22)" },
  };
  const t = map[r] || { bg: "#c8c4b8", ring: "transparent" };
  return <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: t.bg, boxShadow: `0 0 0 3px ${t.ring}` }}/>;
}

/* ─────────────────── Ausblick-Tabelle ───────────────────
 * Eine Zeile pro Tag, alle Werte fluchtend untereinander.
 * Tokens im SMS-Stil: N/D Temp · R Regen mm · PR Regen%@h ·
 * Wind · Böen@h (Peak@h) · Gew Gewitter%@h.
 * Letzte Spalte: Vorhersagegenauigkeit auf der bestehenden
 * 4-Stufen-RISK-Skala (unkritisch→Gefahr), je weiter im
 * Vorlauf desto geringer die Güte.
 */
const OUTLOOK_ROWS = [
  { day: "Do", date: "07.05.", n: -1, d: 13, rain: 4.2, rainP: 78, rainPh: 19,
    wind: 12, gust: 21, gustH: 9, gustPeak: 35, gustPeakH: 18, thnd: 25, thndH: 15, conf: "ok" },
  { day: "Fr", date: "08.05.", n: 3, d: 9, rain: 0, rainP: 15, rainPh: null,
    wind: 4, gust: null, gustH: null, thnd: 0, thndH: null, conf: "caution" },
  { day: "Sa", date: "09.05.", n: 5, d: 11, rain: 2.8, rainP: 65, rainPh: 15,
    wind: 10, gust: 30, gustH: 16, thnd: 0, thndH: null, conf: "warn" },
];

function OutlookCell({ value, hour, suffix, level, peak, peakHour, dash, bold }) {
  const t = RISK_CELL[level];
  return (
    <td style={{
      fontSize: 13, padding: "9px 6px", textAlign: "center",
      fontFamily: EMAIL_MONO_STACK, fontVariantNumeric: "tabular-nums",
      whiteSpace: "nowrap",
      color: "#1d1c1a",
      background: t ? t.bg : "transparent",
      fontWeight: 500,
      borderRight: "1px solid #f0ece1",
    }}>
      {dash
        ? <span style={{ color: "#c2bfb4", fontWeight: 400 }}>–</span>
        : <React.Fragment>
            {value}{suffix}
            {hour != null && <span style={{ fontWeight: 400 }}>@{hour}</span>}
            {peak != null && <span style={{ fontWeight: 400 }}> ({peak}@{peakHour})</span>}
          </React.Fragment>}
    </td>
  );
}

function OutlookTable({ rows, mobile }) {
  const confLabel = { ok: "unkritisch", caution: "Achtung", warn: "Warnung", danger: "Gefahr" };
  const oh = (align) => ({
    fontSize: 10, color: "#3a3835", fontWeight: 600, letterSpacing: "0.04em",
    fontFamily: EMAIL_MONO_STACK, textTransform: "uppercase",
    padding: "7px 6px", textAlign: align || "center", borderRight: "1px solid #f0ece1",
  });
  const table = (
    <table style={{
      width: "100%", minWidth: mobile ? 480 : undefined, borderCollapse: "collapse",
      marginTop: 12, fontFamily: EMAIL_MONO_STACK, fontVariantNumeric: "tabular-nums",
      borderTop: "2px solid #1d1c1a",
    }}>
      <thead>
        <tr style={{ borderBottom: "1px solid #e6e1d3" }}>
          <th style={oh("left")}>Tag</th>
          <th style={oh()}>N</th>
          <th style={oh()}>D</th>
          <th style={oh()}>R</th>
          <th style={oh()}>PR</th>
          <th style={oh()}>Wind</th>
          <th style={oh()}>Böen</th>
          <th style={oh()}>Gew</th>
          <th style={{ ...oh("right"), borderRight: "none" }}>ACC</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #f0ece1" }}>
            {/* Tag */}
            <td style={{ padding: "9px 6px", borderRight: "1px solid #f0ece1", whiteSpace: "nowrap" }}>
              <span style={{ fontSize: 13, fontWeight: 700, color: "#1d1c1a", letterSpacing: "0.04em" }}>{r.day}</span>
            </td>
            {/* N / D Temp — neutral */}
            <OutlookCell value={r.n}/>
            <OutlookCell value={r.d}/>
            {/* Regen mm */}
            <OutlookCell value={r.rain > 0 ? r.rain.toFixed(1) : null} dash={!(r.rain > 0)} level={sevRain(r.rain)}/>
            {/* Regen% @h */}
            <OutlookCell value={r.rainP} suffix="%" hour={r.rainPh} level={sevRainP(r.rainP)}/>
            {/* Wind */}
            <OutlookCell value={r.wind > 0 ? r.wind : null} dash={!(r.wind > 0)} level={sevWind(r.wind)}/>
            {/* Böen @h (Peak@h) */}
            <OutlookCell value={r.gust != null ? r.gust : null} dash={r.gust == null} hour={r.gustH}
              peak={r.gustPeak} peakHour={r.gustPeakH}
              level={sevGust(r.gustPeak != null ? r.gustPeak : r.gust)}/>
            {/* Gewitter% @h */}
            <OutlookCell value={r.thnd > 0 ? r.thnd : null} suffix={r.thnd > 0 ? "%" : ""} dash={!(r.thnd > 0)} hour={r.thndH} level={sevThnd(r.thnd)}/>
            {/* Prob — bestehende RISK-Skala, nur Dot */}
            <td style={{ padding: "9px 6px", textAlign: "right", whiteSpace: "nowrap" }}>
              <span style={{ display: "inline-flex", alignItems: "center", justifyContent: "flex-end" }}>
                <RiskDot r={r.conf}/>
              </span>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );

  return (
    <React.Fragment>
      {mobile ? (
        <div style={{ overflowX: "auto", WebkitOverflowScrolling: "touch" }}>{table}</div>
      ) : table}
      {/* Code-Legende */}
      <div style={{ marginTop: 10, fontFamily: EMAIL_MONO_STACK, fontSize: 10, color: "#9a978d", lineHeight: 1.5 }}>
        N Nacht-Tief · D Tag-Hoch °C · R Regen mm · PR Regen-W. %@h · Wind / Böen km/h@h · Gew Gewitter %@h · ACC Vorhersage-Genauigkeit
      </div>
    </React.Fragment>
  );
}

/* ─────────────────── SMS-Vorschau (Auszug, Referenz) ───────────────────
 * Vollständiger Code in der Original-Vorlage; hier für #911 nicht relevant.
 */

/* ─────────────────────────────────────────────────────────────────
 * EmailMetricsSummary
 * Optionaler Metriken-Überblick: gleiche Tag/Pill-Optik wie
 * Quick-Take, aber datengesteuert für alle konfigurierten Metriken.
 * SMS-Inhalt ausgeschrieben — eine Pill pro Metrik.
 * ───────────────────────────────────────────────────────────────── */
function EmailMetricsSummary({ rows, thresholds = {}, mobile }) {
  const pad = mobile ? "12px 16px 16px" : "14px 28px 18px";
  return (
    <div style={{padding:pad, background:"#fdfcf8", borderBottom:"1px solid #e6e1d3"}}>
      <EmailEyebrow>Metriken-Überblick</EmailEyebrow>
      <div style={{display:"flex", gap:6, flexWrap:"wrap", marginTop:10}}>
        {/* tags.map((t, i) => <EmailTag key={i} tone={t.tone}>{t.text}</EmailTag>) */}
      </div>
    </div>
  );
}

window.EmailMetricsSummary = EmailMetricsSummary;
window.EmailPreview = EmailPreview;
