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

function EmailPreview({ stage, trip, scale = 1, mobile = false }) {
  const seg1 = {
    title: "Segment 1 · Tal-Aufstieg",
    when: "08:00 – 10:00",
    km: 4.6, asc: 1211, dsc: 0, fromAlt: 1144, toAlt: 1210,
    rows: [
      { time: "08", temp: 8.2, feels: 7.1, wind: 5,  gust: 12, dir: "NE", precip: 0,   rainP: 8,  thnd: 0,  cloud: 70, vis: 1.2, uv: 0.4, fl: 2310, risk: "ok" },
      { time: "09", temp: 9.4, feels: 8.0, wind: 6,  gust: 14, dir: "NE", precip: 0,   rainP: 12, thnd: 0,  cloud: 65, vis: 1.4, uv: 1.2, fl: 2335, risk: "ok" },
      { time: "10", temp: 10.3, feels: 8.2, wind: 7, gust: 16, dir: "NE", precip: 0,   rainP: 13, thnd: 0,  cloud: 60, vis: 1.6, uv: 1.6, fl: 2360, risk: "ok" },
    ]
  };
  const seg2 = {
    title: "Segment 2 · Hütten-Anstieg",
    when: "10:00 – 11:40",
    km: 3.3, asc: 203, dsc: 0, fromAlt: 1210, toAlt: 1413,
    rows: [
      { time: "11", temp: 11.0, feels: 8.1, wind: 12, gust: 24, dir: "E",  precip: 0.1, rainP: 25, thnd: 0,  cloud: 80, vis: 2.15, uv: 2.0, fl: 2420, risk: "watch" },
      { time: "12", temp: 9.2,  feels: 7.4, wind: 6,  gust: 25, dir: "SE", precip: 3.2, rainP: 53, thnd: 5,  cloud: 95, vis: 3.5,  uv: 1.8, fl: 2530, risk: "watch" },
    ]
  };

  const dest = {
    title: "Wetter am Ziel · Sillianer Hütte",
    when: `12:45 – 14:45 · ${fmt(2447)} m`,
    rows: [
      { time: "13", temp: 8.7, feels: 6.6, wind: 8,  gust: 21, dir: "NE", precip: 3.8, rainP: 68, thnd: 5,  cloud: 95, vis: 2.05, uv: 1.6, fl: 2400, risk: "watch" },
      { time: "14", temp: 9.9, feels: 8.4, wind: 4,  gust: 11, dir: "NE", precip: 0.2, rainP: 63, thnd: 0,  cloud: 85, vis: 2.4,  uv: 2.4, fl: 2450, risk: "ok" },
      { time: "15", temp: 11.1,feels: 8.9, wind: 10, gust: 20, dir: "E",  precip: 0,   rainP: 48, thnd: 0,  cloud: 70, vis: 1.7,  uv: 1.7, fl: 2550, risk: "ok" },
    ]
  };

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

      {/* ─── Quick-Take ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "18px 16px 14px" : "20px 28px 16px" }}>
        <EmailEyebrow>Quick-Take</EmailEyebrow>
        <div style={{ fontSize: mobile ? 13 : 15, lineHeight: 1.55, color: "#3a3835", marginTop: 8 }}>
          {stage.summary}
        </div>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
          <EmailTag tone="warn">Regen ab 11:00</EmailTag>
          <EmailTag tone="warn">Böen bis 25 km/h</EmailTag>
          <EmailTag tone="ok">Kein Gewitter</EmailTag>
          <EmailTag tone="info">UV mäßig (3.5)</EmailTag>
          <EmailTag tone="info">0°-Linie {fmt(2530)} m</EmailTag>
        </div>
      </div>

      {/* ─── Stirnlampe ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "0 16px 14px" : "0 28px 16px" }}>
        <div style={{ background: "#fbfaf6", border: "1px solid #e6e1d3", padding: mobile ? "12px 14px" : "14px 16px", display: "flex", alignItems: "center", gap: mobile ? 10 : 16 }}>
          <div style={{ flex: 1, minWidth: 0 }}>
            <EmailEyebrow>Tageslicht ohne Stirnlampe</EmailEyebrow>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 4, fontFamily: EMAIL_MONO_STACK, fontVariantNumeric: "tabular-nums" }}>
              05:43 <span style={{ color: "#c8c4b8" }}>—</span> 21:10
            </div>
            <div style={{ fontSize: 11, color: "#6b6962", marginTop: 2, fontFamily: EMAIL_MONO_STACK }}>
              15h 26min · Dämmerung 05:06 + 37min Wolken
            </div>
          </div>
          <DaylightBar/>
        </div>
      </div>

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
        {mobile ? <EmailHourList rows={dest.rows}/> : <EmailDataTable rows={dest.rows}/>}
      </div>

      {/* ─── Folge-Etappen ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "20px 16px 12px" : "24px 28px 16px", background: "#fbfaf6" }}>
        <EmailEyebrow>Ausblick · nächste 4 Tage</EmailEyebrow>
        <div style={{ marginTop: 12, display: "flex", flexDirection: "column" }}>
          <UpcomingRow day="Do" code="KHW_00b" title="Helmhotel → Sillianer Hütte" temp="−1 / 13°C" risk="watch" note="Mäßiger Regen max 19:00 · Böen 35" mobile={mobile}/>
          <UpcomingRow day="Fr" code="KHW_01"  title="Sillianer Hütte → Hochalmkreuz" temp="3 / 9°C" risk="ok"    note="Trocken · schwacher E-Wind 4" mobile={mobile}/>
          <UpcomingRow day="Sa" code="KHW_02"  title="Obstanser → Filmoor-Standschützen" temp="5 / 11°C" risk="watch" note="Regen ab 15:00 · Böen 30" mobile={mobile}/>
          <UpcomingRow day="So" code="KHW_03"  title="Porzehütte → Wolayersee" temp="3 / 8°C" risk="risk"  note="Mäßiger Regen max 12:00 · Böen 47" mobile={mobile}/>
        </div>
      </div>

      {/* ─── Tages-Summary ────────────────────────────────────────────── */}
      <div style={{ padding: mobile ? "12px 16px 18px" : "16px 28px 20px", background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
        <EmailEyebrow>Tages-Summe</EmailEyebrow>
        <div style={{ display: "grid", gridTemplateColumns: mobile ? "repeat(2, 1fr)" : "repeat(4, 1fr)", gap: mobile ? "12px 12px" : 16, marginTop: 10 }}>
          <SumStat label="Regen gesamt" value="13.9" unit="mm"/>
          <SumStat label="Max Wind" value="25" unit="km/h"/>
          <SumStat label="Min Sicht" value="1.2" unit="km"/>
          <SumStat label="Gewitter" value="5" unit="% max"/>
        </div>
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
          <span style={{ fontSize: mobile ? 13 : 14, fontWeight: 600 }}>{seg.title.split(" · ")[1]}</span>
        </div>
        <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, color: "#6b6962" }}>
          {seg.when} · {seg.km} km · ↑{fmt(seg.asc)} · {fmt(seg.fromAlt)}→{fmt(seg.toAlt)} m
        </div>
      </div>
      {mobile ? <EmailHourList rows={seg.rows}/> : <EmailDataTable rows={seg.rows}/>}
    </div>
  );
}

function EmailDataTable({ rows }) {
  // Spalten gruppiert: Zeit | Temp-Block | Wind-Block | Niedersch-Block | Sicht/UV | Höhe
  const groupBg = "#fbfaf6";
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontSize: 12, fontFamily: EMAIL_MONO_STACK, fontVariantNumeric: "tabular-nums" }}>
      <thead>
        <tr style={{ background: groupBg }}>
          <th colSpan="1" style={hGroupStyle()}></th>
          <th colSpan="2" style={hGroupStyle("#c45a2a")}>Temp</th>
          <th colSpan="3" style={hGroupStyle()}>Wind</th>
          <th colSpan="3" style={hGroupStyle("#2a6a8c")}>Niederschlag</th>
          <th colSpan="2" style={hGroupStyle()}>Sicht / UV</th>
          <th colSpan="1" style={hGroupStyle()}>Höhe</th>
          <th colSpan="1" style={hGroupStyle()}></th>
        </tr>
        <tr style={{ background: "#fff", borderBottom: "1px solid #e6e1d3" }}>
          <th style={hCellStyle("left")}>h</th>
          <th style={hCellStyle()}>°C</th>
          <th style={hCellStyle()}>gef.</th>
          <th style={hCellStyle()}>km/h</th>
          <th style={hCellStyle()}>böe</th>
          <th style={hCellStyle()}>dir</th>
          <th style={hCellStyle()}>mm</th>
          <th style={hCellStyle()}>R%</th>
          <th style={hCellStyle()}>Gw%</th>
          <th style={hCellStyle()}>km</th>
          <th style={hCellStyle()}>UV</th>
          <th style={hCellStyle()}>0°m</th>
          <th style={hCellStyle("center")}>·</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #f0ece1" }}>
            <td style={dCellStyle("left", true)}>{r.time}</td>
            <td style={dCellStyle()}>{r.temp.toFixed(1)}</td>
            <td style={dCellStyle()}>{r.feels.toFixed(1)}</td>
            <td style={dCellStyle("center", r.wind > 20, r.wind > 20 ? "#c2410c" : null)}>{r.wind}</td>
            <td style={dCellStyle("center", r.gust > 30, r.gust > 30 ? "#c2410c" : null)}>{r.gust}</td>
            <td style={dCellStyle()}>{r.dir}</td>
            <td style={dCellStyle("center", r.precip > 1, r.precip > 1 ? "#0e6fb8" : null)}>{r.precip > 0 ? r.precip.toFixed(1) : "·"}</td>
            <td style={dCellStyle("center", r.rainP > 50, r.rainP > 50 ? "#0e6fb8" : null)}>{r.rainP}</td>
            <td style={dCellStyle("center", r.thnd > 0, r.thnd > 0 ? "#b91c1c" : null)}>{r.thnd > 0 ? r.thnd : "·"}</td>
            <td style={dCellStyle("center", r.vis < 2, r.vis < 2 ? "#c2410c" : null)}>{r.vis.toFixed(1)}</td>
            <td style={dCellStyle()}>{r.uv.toFixed(1)}</td>
            <td style={dCellStyle()}>{fmt(r.fl)}</td>
            <td style={{ ...dCellStyle("center"), padding: "8px 4px" }}><RiskDot r={r.risk}/></td>
          </tr>
        ))}
      </tbody>
    </table>
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

function RiskDot({ r }) {
  const map = {
    ok:    { bg: "#15803d", ring: "rgba(21,128,61,0.18)" },
    watch: { bg: "#c2410c", ring: "rgba(194,65,12,0.20)" },
    risk:  { bg: "#b91c1c", ring: "rgba(185,28,28,0.22)" },
  };
  const t = map[r] || { bg: "#c8c4b8", ring: "transparent" };
  return <span style={{ display: "inline-block", width: 10, height: 10, borderRadius: "50%", background: t.bg, boxShadow: `0 0 0 3px ${t.ring}` }}/>;
}

function UpcomingRow({ day, code, title, temp, risk, note, mobile }) {
  if (mobile) {
    return (
      <div style={{
        display: "grid", gridTemplateColumns: "28px 1fr auto", gap: 10,
        alignItems: "center", padding: "10px 0", borderBottom: "1px solid #e6e1d3",
      }}>
        <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, fontWeight: 700, color: "#1d1c1a", letterSpacing: "0.04em" }}>{day}</div>
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#1d1c1a", lineHeight: 1.2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{title}</span>
          </div>
          <div style={{ fontSize: 10, color: "#9a978d", fontFamily: EMAIL_MONO_STACK, marginTop: 2 }}>{code}</div>
          <div style={{ fontSize: 11, color: "#6b6962", marginTop: 3 }}>{note}</div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 4 }}>
          <span style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, color: "#3a3835" }}>{temp}</span>
          <RiskDot r={risk}/>
        </div>
      </div>
    );
  }
  return (
    <div style={{ display: "grid", gridTemplateColumns: "32px 70px 1fr 80px 14px", gap: 12, alignItems: "center", padding: "10px 0", borderBottom: "1px solid #e6e1d3" }}>
      <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, fontWeight: 700, color: "#1d1c1a", letterSpacing: "0.04em" }}>{day}</div>
      <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, color: "#9a978d" }}>{code}</div>
      <div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#1d1c1a" }}>{title}</div>
        <div style={{ fontSize: 11, color: "#6b6962", marginTop: 2 }}>{note}</div>
      </div>
      <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, color: "#3a3835", textAlign: "right" }}>{temp}</div>
      <RiskDot r={risk}/>
    </div>
  );
}

function SumStat({ label, value, unit }) {
  return (
    <div>
      <div style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 9, letterSpacing: "0.1em", color: "#9a978d", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 20, fontWeight: 600, marginTop: 4, fontFamily: EMAIL_MONO_STACK, fontVariantNumeric: "tabular-nums" }}>
        {value}<span style={{ fontSize: 11, color: "#9a978d", fontWeight: 400, marginLeft: 4 }}>{unit}</span>
      </div>
    </div>
  );
}

/* ─────────────────── SMS-Vorschau ───────────────────
 * Echtes zeichen-optimiertes SMS-Format gemäß Spec:
 *   N = Nacht-Tiefsttemp, D = Tag-Höchsttemp
 *   R = Regen (mm), PR = Regen-Wahrsch %@Stunde
 *   W = Wind km/h@Stunde (richtung optional)
 *   G = Gust/Böen km/h@Stunde
 *   TH = Gewitter %@Stunde, TH+:L/M/H = Level Low/Med/High @Stunde
 *   HR:L/M/H = starker Regen-Level @Stunde
 *   Z:HIGH/MED/LOW = Ziel-Risiko, Zahl = max. Höhe
 *   "-" = nicht relevant / kein Wert
 */
function SMSPreview({ stage, trip }) {
  // Beispiel im Spec-Format (KHW_00b)
  const smsLine = `${stage.code.toUpperCase()}: N3 D11 R3.8 PR68%@13 W12@11 G25@12 TH5%@12 HR:L@12 Z:WATCH:2447`;
  const smsLine2 = `${stage.code.toUpperCase()}+1: N-1 D13 R- PR- W- G35@17 TH+:L@16 HR:L@17 Z:HIGH:2680`;
  return (
    <div style={{
      width: 320, background: "#1c1c1e", borderRadius: 28, padding: 12,
      boxShadow: "0 8px 24px rgba(0,0,0,0.18)",
    }}>
      <div style={{ background: "#000", borderRadius: 22, overflow: "hidden", padding: "32px 0 12px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", padding: "0 24px", color: "#fff", fontSize: 12, fontFamily: "system-ui", marginBottom: 8 }}>
          <span style={{ fontWeight: 600 }}>06:01</span>
          <span>●●● </span>
        </div>
        <div style={{ borderBottom: "0.5px solid #333", padding: "8px 18px 12px", color: "#fff" }}>
          <div style={{ fontSize: 11, color: "#888", textAlign: "center" }}>Gregor Zwanzig · SMS</div>
          <div style={{ fontSize: 13, color: "#888", textAlign: "center", marginTop: 2 }}>+49 170 …</div>
        </div>
        <div style={{ padding: "16px 16px 24px" }}>
          <div style={{
            background: "#2c2c2e", color: "#fff", borderRadius: 16,
            padding: "10px 13px", maxWidth: 260, fontSize: 12, lineHeight: 1.45,
            fontFamily: EMAIL_MONO_STACK, letterSpacing: "0.01em", whiteSpace: "pre-wrap", wordBreak: "break-all",
          }}>
            {smsLine}
          </div>
          <div style={{ fontSize: 10, color: "#666", marginTop: 4, paddingLeft: 6 }}>{smsLine.length}/160 · gesendet 06:01</div>

          <div style={{
            background: "#2c2c2e", color: "#fff", borderRadius: 16,
            padding: "10px 13px", maxWidth: 260, fontSize: 12, lineHeight: 1.45, marginTop: 12,
            fontFamily: EMAIL_MONO_STACK, letterSpacing: "0.01em", whiteSpace: "pre-wrap", wordBreak: "break-all",
          }}>
            {smsLine2}
          </div>
          <div style={{ fontSize: 10, color: "#666", marginTop: 4, paddingLeft: 6 }}>{smsLine2.length}/160 · gesendet 06:01</div>
        </div>

        {/* Legende — kein echter Phone-Inhalt, nur Preview-Hilfe */}
        <div style={{ padding: "10px 16px 0", borderTop: "0.5px solid #333", marginTop: 4 }}>
          <div style={{ fontSize: 9, letterSpacing: "0.1em", color: "#666", fontFamily: EMAIL_MONO_STACK, marginBottom: 6 }}>LEGENDE (nicht teil der SMS)</div>
          <div style={{ fontSize: 10, color: "#888", fontFamily: EMAIL_MONO_STACK, lineHeight: 1.5 }}>
            N/D Nacht/Tag °C · R Regen mm · PR Regen%@h<br/>
            W Wind · G Böen · TH Gewitter%@h<br/>
            TH+/HR:L/M/H Level Low/Med/High@h · Z Ziel-Risiko
          </div>
        </div>
      </div>
    </div>
  );
}

window.EmailPreview = EmailPreview;
window.SMSPreview = SMSPreview;

/* ───────────── Mobile-Stunden-Liste ───────────── */
// Ersetzt die 14-spaltige EmailDataTable auf iPhone.
// Pro Stunde: zwei Zeilen — Hauptzeile (Zeit + Glyph + Temp + Risk-Dot) und
// Detailzeile (Wind, Niederschlag, UV, 0°-Linie). Kritische Werte fett.
function EmailHourList({ rows }) {
  return (
    <div style={{ marginTop: 12, display: "flex", flexDirection: "column", border: "1px solid #e6e1d3", background: "#fff" }}>
      {rows.map((r, i) => {
        const glyph = r.precip > 0.3 ? "☂" : (r.cloud > 75 ? "☁" : r.cloud > 35 ? "⛅" : "☼");
        const glyphColor = glyph === "☼" ? "#d99a2a" : glyph === "⛅" ? "#c4a05a" : glyph === "☁" ? "#9a958a" : "#4a7ab8";
        const tempStr = `${r.temp.toFixed(1)}°`;
        const feelsStr = `(gef. ${r.feels.toFixed(1)}°)`;
        const windHigh = r.wind > 20 || r.gust > 30;
        const precipHigh = r.precip > 1 || r.rainP > 50;
        const visLow = r.vis < 2;
        const thnd = r.thnd > 0;
        return (
          <div key={i} style={{
            display: "flex", flexDirection: "column", gap: 4,
            padding: "10px 12px",
            borderBottom: i < rows.length - 1 ? "1px solid #f0ece1" : "none",
            background: r.risk === "watch" ? "rgba(194,65,12,0.04)" : r.risk === "risk" ? "rgba(185,28,28,0.05)" : "transparent",
          }}>
            {/* Hauptzeile */}
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <span style={{
                fontFamily: EMAIL_MONO_STACK, fontSize: 13, fontWeight: 700,
                color: "#1d1c1a", width: 26,
              }}>{r.time}</span>
              <span style={{ color: glyphColor, fontSize: 14, fontWeight: 700, width: 14, textAlign: "center" }}>{glyph}</span>
              <span style={{
                fontFamily: EMAIL_MONO_STACK, fontSize: 14, fontWeight: 600,
                color: "#1d1c1a", fontVariantNumeric: "tabular-nums",
              }}>{tempStr}</span>
              <span style={{ fontFamily: EMAIL_MONO_STACK, fontSize: 11, color: "#9a978d" }}>{feelsStr}</span>
              <span style={{ flex: 1 }}/>
              <RiskDot r={r.risk}/>
            </div>
            {/* Detailzeile — Pipe-getrennte Mikro-Datenliste */}
            <div style={{
              display: "flex", flexWrap: "wrap", gap: "2px 10px",
              paddingLeft: 36, fontFamily: EMAIL_MONO_STACK, fontSize: 11,
              color: "#6b6962", fontVariantNumeric: "tabular-nums",
            }}>
              <span>
                <span style={{ color: "#9a978d" }}>Wind </span>
                <span style={{ color: windHigh ? "#c2410c" : "#1d1c1a", fontWeight: windHigh ? 700 : 500 }}>{r.wind}/{r.gust}</span>
                <span style={{ color: "#9a978d" }}> {r.dir}</span>
              </span>
              <span>
                <span style={{ color: "#9a978d" }}>Regen </span>
                <span style={{ color: precipHigh ? "#0e6fb8" : "#1d1c1a", fontWeight: precipHigh ? 700 : 500 }}>
                  {r.precip > 0 ? `${r.precip.toFixed(1)} mm` : "–"}
                </span>
                <span style={{ color: "#9a978d" }}> ({r.rainP}%)</span>
              </span>
              {thnd && (
                <span>
                  <span style={{ color: "#9a978d" }}>Gw </span>
                  <span style={{ color: "#b91c1c", fontWeight: 700 }}>{r.thnd}%</span>
                </span>
              )}
              <span>
                <span style={{ color: "#9a978d" }}>Sicht </span>
                <span style={{ color: visLow ? "#c2410c" : "#1d1c1a", fontWeight: visLow ? 700 : 500 }}>{r.vis.toFixed(1)} km</span>
              </span>
              <span>
                <span style={{ color: "#9a978d" }}>UV </span>
                <span style={{ color: "#1d1c1a" }}>{r.uv.toFixed(1)}</span>
              </span>
              <span>
                <span style={{ color: "#9a978d" }}>0° </span>
                <span style={{ color: "#1d1c1a" }}>{fmt(r.fl)} m</span>
              </span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

window.EmailHourList = EmailHourList;
