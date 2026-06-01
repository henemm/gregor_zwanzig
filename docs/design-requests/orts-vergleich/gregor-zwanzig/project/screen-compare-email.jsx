/* Compare-Email — "Orts-Vergleich"
 * Aktivitäts-agnostisch: Spalten und Score-Modell kommen aus dem Profil.
 *
 * Zwei Render-Modi:
 *   - desktop (width 680)  → klassische Email-Karte
 *   - mobile  (width 380)  → iPhone-Mail.app-optimiert, Matrix kippt zu Karten,
 *                            Stunden werden zu kompakten Streifen je Ort.
 *
 * In echtem Email wäre der Wechsel via @media (max-width: 480px).
 */

const CE_FONT_SANS = "'Inter Tight', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif";
const CE_FONT_MONO = "'JetBrains Mono', 'SF Mono', Menlo, monospace";

const CE_PROFILES = {
  "wintersport-glacier": {
    label: "Wintersport · Schnee",
    code: "WINTER-PISTE",
    question: "Wo finde ich am Wochenende den besten Schnee?",
    // Spalten in der Matrix. "primary"-Spalten kriegen im Mobile-Layout auch
    // einen sichtbaren Platz; alle anderen wandern in die Detail-Liste.
    cols: [
      { key: "score",   label: "Score",      unit: "",   highlight: "max", primary: true },
      { key: "snow",    label: "Schnee",     unit: "cm", highlight: "max", primary: true },
      { key: "newSnow", label: "Neuschnee",  unit: "cm", highlight: "max", prefix: "+" },
      { key: "wg",      label: "Wind/Böen",  unit: "",   highlight: "min", custom: r => `${r.wind}/${r.gust} ${r.dir}`, primary: true },
      { key: "feels",   label: "Gef. Temp",  unit: "°C", highlight: "max", signed: true },
      { key: "sun",     label: "Sonne",      unit: "h",  highlight: "max", prefix: "~", primary: true },
      { key: "cloudPos",label: "Wolkenlage", unit: "",   highlight: "tag", custom: r => r.cloudTag === "über" ? "über Wolken" : r.cloudTag === "klar" ? "klar" : "in Wolken" },
    ],
    tags: [
      { tone: "good", label: "1 Ort über Wolken" },
      { tone: "warn", label: "Böen 26 km/h #2" },
      { tone: "info", label: "+12 cm Neuschnee #1" },
    ],
  },

  "alpine-touring": {
    label: "Skitour · Backcountry",
    code: "SKITOUR",
    question: "Welcher Trip passt morgen — Sicht, Wind, Lawine?",
    cols: [
      { key: "score",   label: "Score",        unit: "",     highlight: "max", primary: true },
      { key: "wind",    label: "Wind ⌀",       unit: "km/h", highlight: "min", primary: true },
      { key: "gust",    label: "Böen max",     unit: "km/h", highlight: "min" },
      { key: "avalanche",label: "Lawine",      unit: "",     highlight: "min", custom: r => `${r.avalanche}/5`, primary: true },
      { key: "vis",     label: "Sicht min",    unit: "km",   highlight: "max", primary: true },
      { key: "sun",     label: "Sonne",        unit: "h",    highlight: "max", prefix: "~" },
      { key: "feels",   label: "Gef. Temp",    unit: "°C",   highlight: "max", signed: true },
    ],
    tags: [
      { tone: "good", label: "Lawine 2/5 #1" },
      { tone: "warn", label: "Sicht 0.8 km #4" },
      { tone: "info", label: "Sonne 5.5 h #2" },
    ],
  },

  "trail-running": {
    label: "Trail-Running · Süden",
    code: "TRAIL-RUN",
    question: "Wo ist Sa morgens trockene Lauf-Witterung?",
    cols: [
      { key: "score",   label: "Score",        unit: "",     highlight: "max", primary: true },
      { key: "tempMax", label: "Temp max",     unit: "°C",   highlight: "ideal", ideal: 18, primary: true },
      { key: "feels",   label: "Gef. Temp",    unit: "°C",   highlight: "ideal", ideal: 16, signed: true },
      { key: "uv",      label: "UV-Index",     unit: "",     highlight: "min" },
      { key: "rain",    label: "Regen 6h",     unit: "mm",   highlight: "min", primary: true },
      { key: "rainP",   label: "Regen-Prob.",  unit: "%",    highlight: "min", primary: true },
      { key: "wind",    label: "Wind ⌀",       unit: "km/h", highlight: "min" },
    ],
    tags: [
      { tone: "good", label: "0.0 mm Regen #1" },
      { tone: "warn", label: "UV 6 #3" },
      { tone: "info", label: "+22 °C max #2" },
    ],
  },
};

const CE_DATA = {
  "wintersport-glacier": {
    locations: {
      "loc-01": { name: "Hintertuxer Gletscher",          group: "Zillertal", elev: 3250 },
      "loc-02": { name: "Übergangsjoch (Zillertal Arena)",group: "Zillertal", elev: 2500 },
      "loc-04": { name: "Hochfügen",                      group: "Zillertal", elev: 1500 },
      "loc-03": { name: "Geisbergalm (Zillertal Arena)",  group: "Zillertal", elev: 1850 },
    },
    rows: [
      { id: "loc-01", rank: 1, score: 82, snow: 305, newSnow: 12, wind: 7,  gust: 14, dir: "S",  feels: -2, sun: 4.0, cloudTag: "über", cloudBest: true },
      { id: "loc-02", rank: 2, score: 76, snow: 189, newSnow: 8,  wind: 7,  gust: 17, dir: "W",  feels:  1, sun: 4.0, cloudTag: "über", cloudBest: true },
      { id: "loc-04", rank: 3, score: 55, snow: 70,  newSnow: 0,  wind: 8,  gust: 15, dir: "W",  feels: -6, sun: 0,   cloudTag: "in",   cloudBest: false },
      { id: "loc-03", rank: 4, score: 40, snow: 24,  newSnow: 0,  wind: 7,  gust: 19, dir: "O",  feels:  4, sun: 0,   cloudTag: "in",   cloudBest: false },
    ],
    hours: {
      "loc-01": [["09","-3","-","5/9 W","☼"],["12","-3","-","6/13 W","☼"],["13","-3","-","5/9 W","☼"],["14","-3","-","6/13 W","☼"],["15","-3","-","8/15 W","☼"],["16","-3","-","6/15 NW","☼"]],
      "loc-02": [["09","1","-","3/8 W","☼"],["12","1","0.1","3/4 W","☼"],["13","1","0.1","3/4 W","☼"],["14","2","-","2/10 W","☼"],["15","2","-","6/16 W","☼"],["16","2","-","7/17 NW","☼"]],
      "loc-04": [["09","-3","-","5/9 W","☁"],["12","-3","-","5/9 W","☁"],["13","-3","-","5/9 W","☁"],["14","-3","-","6/13 W","☁"],["15","-3","-","8/15 W","☁"],["16","-3","-","6/15 NW","☁"]],
    },
  },

  "alpine-touring": {
    locations: {
      "loc-a": { name: "Pitztaler Gletscher",       group: "Tirol West",  elev: 2890 },
      "loc-b": { name: "Stubaier Wildspitze",       group: "Stubaital",   elev: 3150 },
      "loc-c": { name: "Sellrain · Lampsenspitze",  group: "Stubaital",   elev: 2876 },
      "loc-d": { name: "Rofan · Hochiss-Anstieg",   group: "Rofan",       elev: 2299 },
    },
    rows: [
      { id: "loc-a", rank: 1, score: 84, wind: 9,  gust: 19, dir: "NW", avalanche: 2, vis: 8.2, sun: 4.5, feels: -8 },
      { id: "loc-b", rank: 2, score: 71, wind: 14, gust: 27, dir: "W",  avalanche: 3, vis: 6.5, sun: 5.5, feels: -10 },
      { id: "loc-c", rank: 3, score: 58, wind: 11, gust: 22, dir: "W",  avalanche: 3, vis: 4.0, sun: 2.0, feels: -7 },
      { id: "loc-d", rank: 4, score: 32, wind: 19, gust: 38, dir: "SW", avalanche: 3, vis: 0.8, sun: 0.5, feels: -4 },
    ],
    hours: {
      "loc-a": [["07","-9","-","6/12 NW","☼"],["09","-8","-","8/16 NW","☼"],["10","-8","-","9/18 NW","☼"],["12","-7","-","10/19 W","☼"],["13","-6","-","9/16 W","☼"],["14","-6","-","7/14 W","☼"]],
      "loc-b": [["07","-11","-","12/22 W","☼"],["09","-10","-","13/25 W","☼"],["10","-10","-","14/27 W","☼"],["12","-9","-","14/27 W","☼"],["13","-8","-","13/24 W","☼"],["14","-7","-","11/20 W","☼"]],
      "loc-c": [["07","-8","-","9/18 W","☁"],["09","-7","-","10/20 W","☁"],["10","-7","0.2","11/22 W","❅"],["12","-6","0.1","11/21 W","☁"],["13","-6","-","10/19 W","☁"],["14","-5","-","8/16 W","☁"]],
    },
  },

  "trail-running": {
    locations: {
      "loc-13": { name: "Pollença",           group: "Mallorca", elev: 50 },
      "loc-x":  { name: "Cap de Formentor",   group: "Mallorca", elev: 380 },
      "loc-y":  { name: "Sóller Tramuntana",  group: "Mallorca", elev: 95 },
      "loc-14": { name: "Valdemossa",         group: "Mallorca", elev: 437 },
    },
    rows: [
      { id: "loc-13", rank: 1, score: 88, tempMax: 18, feels: 16, uv: 5, rain: 0.0, rainP: 8,  wind: 8 },
      { id: "loc-x",  rank: 2, score: 71, tempMax: 22, feels: 19, uv: 6, rain: 0.4, rainP: 22, wind: 18 },
      { id: "loc-y",  rank: 3, score: 64, tempMax: 19, feels: 18, uv: 6, rain: 1.1, rainP: 35, wind: 11 },
      { id: "loc-14", rank: 4, score: 38, tempMax: 14, feels: 12, uv: 3, rain: 4.2, rainP: 70, wind: 9  },
    ],
    hours: {
      "loc-13": [["06","12","-","4/8 NE","☼"],["07","13","-","5/9 NE","☼"],["08","15","-","6/11 NE","☼"],["09","17","-","7/13 N","☼"],["10","18","-","8/14 N","☼"],["11","18","-","9/15 N","☼"]],
      "loc-x":  [["06","16","-","12/22 NE","☼"],["07","17","-","14/24 NE","☼"],["08","19","-","15/26 NE","☼"],["09","21","-","16/28 N","☼"],["10","22","-","18/30 N","☼"],["11","22","0.1","17/29 N","☼"]],
      "loc-y":  [["06","13","-","6/10 NE","☼"],["07","15","-","7/12 NE","☁"],["08","17","0.2","8/14 NE","☁"],["09","18","0.4","9/16 N","☁"],["10","19","0.3","10/17 N","☁"],["11","19","0.2","11/18 N","☁"]],
    },
  },
};

const ceFmt = (n) => {
  if (n === null || n === undefined || n === "" || Number.isNaN(n)) return "—";
  const num = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(num)) return "—";
  return num.toLocaleString("de-DE");
};

// Rohwert aus der Zeile holen (für Highlight-Berechnung).
const ceRawVal = (col, row) => {
  if (col.key === "wg") return row.wind;
  return row[col.key];
};

// Display-String für eine Zelle.
const ceDisplay = (col, row) => {
  const raw = col.custom ? col.custom(row) : row[col.key];
  if (raw == null || raw === "") return "—";
  if (typeof raw === "number") {
    const prefix = typeof col.prefix === "function" ? col.prefix(raw) : (col.prefix || (col.signed && raw > 0 ? "+" : ""));
    return `${prefix}${ceFmt(raw)}${col.unit ? " " + col.unit : ""}`;
  }
  return raw;
};

// Best-Wert pro Spalte für Highlighting.
function ceBestByKey(profile, data) {
  const best = {};
  profile.cols.forEach(c => {
    if (c.highlight === "tag") return;
    const vals = data.rows.map(r => ceRawVal(c, r)).filter(v => v != null && !Number.isNaN(v));
    if (!vals.length) return;
    if (c.highlight === "max") best[c.key] = Math.max(...vals);
    else if (c.highlight === "min") best[c.key] = Math.min(...vals);
    else if (c.highlight === "ideal") {
      const ideal = c.ideal;
      best[c.key] = vals.reduce((b, v) => Math.abs(v - ideal) < Math.abs(b - ideal) ? v : b, vals[0]);
    }
  });
  return best;
}

const ceIsBest = (col, row, best) => {
  if (col.highlight === "tag") return col.key === "cloudPos" && !!row.cloudBest;
  const v = ceRawVal(col, row);
  return v != null && v === best[col.key];
};

/* ───────────────────────────────────────────────────────────── */
/* MAIN COMPONENT                                                */
/* ───────────────────────────────────────────────────────────── */

function CompareEmail({
  profileId = "wintersport-glacier",
  schedule = "Sa 06:00",
  subscriptionName = "Skigebiete-Vergleich",
  mobile = false,
}) {
  const profile = CE_PROFILES[profileId];
  const data = CE_DATA[profileId];
  const winner = data.rows[0];
  const winnerLoc = data.locations[winner.id];
  const best = ceBestByKey(profile, data);

  const width = mobile ? 380 : 680;
  const px = mobile ? 18 : 28;

  return (
    <div style={{
      width, fontFamily: CE_FONT_SANS, color: "#1d1c1a",
      background: "#fff",
      border: mobile ? "none" : "1px solid #d8d3c7",
      boxShadow: mobile ? "none" : "0 8px 32px rgba(0,0,0,0.06)",
      WebkitFontSmoothing: "antialiased",
    }}>

      {/* ─── Header ─────────────────────────────────────────────── */}
      <div style={{ padding: `${mobile ? 18 : 22}px ${px}px 0`, background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
        {mobile ? (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ fontFamily: CE_FONT_MONO, fontSize: 9, letterSpacing: "0.12em", color: "#c45a2a", fontWeight: 600 }}>
                ORTS-VERGLEICH · {profile.code}
              </div>
              <div style={{ fontFamily: CE_FONT_MONO, fontSize: 9, letterSpacing: "0.12em", color: "#9a978d", fontWeight: 600 }}>
                GREGOR ZWANZIG
              </div>
            </div>
            <div style={{ fontSize: 19, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 6, color: "#1d1c1a", lineHeight: 1.2 }}>
              {profile.question}
            </div>
            <div style={{ fontSize: 12, color: "#6b6962", marginTop: 6, fontFamily: CE_FONT_MONO }}>
              <span style={{ color: "#1d1c1a", fontWeight: 600 }}>So · 17.05.2026</span> · 09–16 Uhr · <span style={{ color: "#1d1c1a", fontWeight: 600 }}>{subscriptionName}</span>
            </div>
          </div>
        ) : (
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 14 }}>
            <div>
              <div style={{ fontFamily: CE_FONT_MONO, fontSize: 10, letterSpacing: "0.12em", color: "#c45a2a", fontWeight: 600 }}>
                ORTS-VERGLEICH · {profile.code}
              </div>
              <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.015em", marginTop: 4, color: "#1d1c1a", lineHeight: 1.2 }}>
                {profile.question}
              </div>
              <div style={{ fontSize: 13, color: "#6b6962", marginTop: 6, fontFamily: CE_FONT_MONO }}>
                Forecast für <span style={{ color: "#1d1c1a", fontWeight: 600 }}>So · 17.05.2026</span> · 09:00 – 16:00
              </div>
            </div>
            <div style={{ textAlign: "right" }}>
              <div style={{ fontFamily: CE_FONT_MONO, fontSize: 10, letterSpacing: "0.12em", color: "#9a978d", fontWeight: 600 }}>
                GREGOR ZWANZIG
              </div>
              <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4, color: "#1d1c1a" }}>
                {subscriptionName}
              </div>
              <div style={{ fontSize: 11, color: "#6b6962", marginTop: 2, fontFamily: CE_FONT_MONO }}>
                auto · {schedule}
              </div>
            </div>
          </div>
        )}

        {/* Setup-Stats */}
        <div style={{
          display: "grid",
          gridTemplateColumns: mobile ? "1fr 1fr" : "repeat(4, 1fr)",
          gap: mobile ? "12px 0" : 0,
          padding: `${mobile ? 12 : 14}px 0`,
          borderTop: "1px solid #e6e1d3",
        }}>
          <CEStat label="Profil"   value={profile.label.split(" · ")[0]} sub={profile.label.split(" · ")[1] || "—"} mobile={mobile} idx={0}/>
          <CEStat label="Orte"     value={data.rows.length} sub={`von ${Object.keys(data.locations).length} verglichen`} mobile={mobile} idx={1} last={mobile}/>
          <CEStat label="Horizont" value="+48h" sub="icon_d2 · openmeteo" mobile={mobile} idx={2}/>
          <CEStat label="Erstellt" value="12:32" sub="17.05.2026" mobile={mobile} idx={3} last/>
        </div>
      </div>

      {/* ─── Winner / Empfehlung ────────────────────────────────── */}
      <div style={{ padding: `${mobile ? 16 : 20}px ${px}px 0` }}>
        <CEEyebrow accent>Empfehlung · Rang 1</CEEyebrow>
        <div style={{
          marginTop: 8, border: "1px solid #cfdec8", borderLeft: "3px solid #3d6b3a",
          background: "linear-gradient(135deg, rgba(61,107,58,0.05), rgba(61,107,58,0.0))",
          padding: mobile ? "14px 14px" : "16px 18px",
          display: "flex", gap: mobile ? 14 : 18, alignItems: "center",
        }}>
          <div style={{
            width: mobile ? 50 : 56, height: mobile ? 50 : 56, background: "#3d6b3a", color: "#fff",
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            fontFamily: CE_FONT_MONO, lineHeight: 1, flexShrink: 0,
          }}>
            <span style={{ fontSize: 9, letterSpacing: "0.1em", opacity: 0.8 }}>SCORE</span>
            <span style={{ fontSize: mobile ? 20 : 22, fontWeight: 700, marginTop: 4 }}>{winner.score}</span>
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: mobile ? 16 : 18, fontWeight: 600, color: "#1d1c1a", letterSpacing: "-0.01em", lineHeight: 1.2 }}>{winnerLoc.name}</div>
            <div style={{ fontSize: 11, color: "#6b6962", marginTop: 3, fontFamily: CE_FONT_MONO }}>
              {winnerLoc.group} · {ceFmt(winnerLoc.elev)} m
            </div>
            <div style={{ marginTop: 8, fontSize: 11, color: "#3a3835", lineHeight: 1.5, fontFamily: CE_FONT_MONO, display: "flex", flexWrap: "wrap", gap: "2px 10px" }}>
              {profile.cols.filter(c => c.primary && c.key !== "score").slice(0, 3).map(c => (
                <span key={c.key}>
                  <span style={{ color: "#9a978d" }}>{c.label}:</span> <span style={{ color: "#1d1c1a", fontWeight: 600 }}>{ceDisplay(c, winner)}</span>
                </span>
              ))}
            </div>
          </div>
        </div>

        {/* Tags */}
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 12 }}>
          {profile.tags.map((t, i) => <CETag key={i} tone={t.tone}>{t.label}</CETag>)}
        </div>
      </div>

      {/* ─── Vergleichs-Matrix ──────────────────────────────────── */}
      <div style={{ padding: `${mobile ? 20 : 24}px ${px}px 0` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", paddingBottom: 8, borderBottom: "2px solid #1d1c1a", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <span style={{ fontFamily: CE_FONT_MONO, fontSize: 11, fontWeight: 600, color: "#c45a2a", letterSpacing: "0.1em" }}>VERGLEICH</span>
            <span style={{ fontSize: mobile ? 13 : 14, fontWeight: 600 }}>{mobile ? "Alle Orte" : "Alle Orte · sortiert nach Score"}</span>
          </div>
          <div style={{ fontFamily: CE_FONT_MONO, fontSize: 10, color: "#9a978d" }}>
            grün = bester Wert
          </div>
        </div>

        {mobile
          ? <CEMobileMatrix profile={profile} data={data} best={best}/>
          : <CEDesktopMatrix profile={profile} data={data} best={best}/>
        }
      </div>

      {/* ─── Stunden-Übersicht ──────────────────────────────────── */}
      <div style={{ padding: `${mobile ? 20 : 24}px ${px}px 0` }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", paddingBottom: 8, borderBottom: "2px solid #1d1c1a", gap: 12, flexWrap: "wrap" }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
            <span style={{ fontFamily: CE_FONT_MONO, fontSize: 11, fontWeight: 600, color: "#c45a2a", letterSpacing: "0.1em" }}>STUNDEN</span>
            <span style={{ fontSize: mobile ? 13 : 14, fontWeight: 600 }}>Top-3 · Sonntag</span>
          </div>
          <div style={{ fontFamily: CE_FONT_MONO, fontSize: 10, color: "#9a978d" }}>
            ° · mm · km/h
          </div>
        </div>

        {mobile
          ? <CEMobileHours data={data}/>
          : <CEDesktopHours data={data}/>
        }
      </div>

      {/* ─── Abo / Footer Info ──────────────────────────────────── */}
      <div style={{ padding: `${mobile ? 20 : 24}px ${px}px 16px`, background: "#fbfaf6", borderTop: "1px solid #e6e1d3", marginTop: mobile ? 16 : 20 }}>
        <div style={{ display: "grid", gridTemplateColumns: mobile ? "1fr" : "1fr 1fr", gap: mobile ? 16 : 20 }}>
          <div>
            <CEEyebrow>Dieses Abo</CEEyebrow>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4, color: "#1d1c1a" }}>{subscriptionName}</div>
            <div style={{ fontSize: 11, color: "#6b6962", marginTop: 4, fontFamily: CE_FONT_MONO, lineHeight: 1.6 }}>
              Profil: <span style={{ color: "#1d1c1a" }}>{profile.label}</span><br/>
              Plan: <span style={{ color: "#1d1c1a" }}>{schedule}</span> · 09–16 Uhr<br/>
              Quelle: <span style={{ color: "#1d1c1a" }}>open-meteo · icon_d2</span>
            </div>
          </div>
          <div>
            <CEEyebrow>Nächster Versand</CEEyebrow>
            <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4, color: "#1d1c1a", fontFamily: CE_FONT_MONO }}>
              Sa · 23.05.2026 · 06:00
            </div>
            <div style={{ fontSize: 11, color: "#6b6962", marginTop: 4, lineHeight: 1.6 }}>
              Du bekommst diese E-Mail wegen deines Abos<br/>
              <strong style={{ color: "#1d1c1a" }}>{subscriptionName}</strong> in Gregor 20.
            </div>
          </div>
        </div>
      </div>

      {/* ─── App-Footer ─────────────────────────────────────────── */}
      <div style={{ padding: `16px ${px}px 20px`, background: "#1d1c1a", color: "#9a978d", fontSize: 11, fontFamily: CE_FONT_MONO }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <div>
            <span style={{ color: "#fff", fontWeight: 600, letterSpacing: "0.06em" }}>GREGOR ZWANZIG</span>
            <span style={{ margin: "0 8px", color: "#5a5750" }}>·</span>
            Orts-Vergleich
          </div>
          {!mobile && <div>2026-05-17 12:32 UTC · openmeteo · icon_d2</div>}
        </div>
        <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid #3a3835", display: "flex", gap: mobile ? 10 : 16, fontSize: 10, flexWrap: "wrap" }}>
          <a href="#" style={{ color: "#c45a2a", textDecoration: "none" }}>Vergleich in App öffnen →</a>
          <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Abo bearbeiten</a>
          <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Orte ändern</a>
          {!mobile && <a href="#" style={{ color: "#9a978d", textDecoration: "none" }}>Metriken & Score</a>}
          <a href="#" style={{ color: "#9a978d", textDecoration: "none", marginLeft: mobile ? 0 : "auto" }}>Abmelden</a>
        </div>
      </div>
    </div>
  );
}

/* ───────────── Bausteine ───────────── */

function CEEyebrow({ children, accent }) {
  return (
    <span style={{
      fontFamily: CE_FONT_MONO, fontSize: 10, letterSpacing: "0.12em",
      color: accent ? "#c45a2a" : "#9a978d", fontWeight: 600, textTransform: "uppercase",
    }}>{children}</span>
  );
}

function CEStat({ label, value, sub, last, mobile, idx }) {
  // Auf Mobile: 2x2 Grid → Border-right nur in linker Spalte, kein Border-right ganz rechts.
  const showBorder = mobile ? (idx % 2 === 0) : !last;
  return (
    <div style={{ borderRight: showBorder ? "1px solid #e6e1d3" : "none", paddingRight: 10, paddingLeft: mobile && idx % 2 === 1 ? 10 : 0 }}>
      <div style={{ fontFamily: CE_FONT_MONO, fontSize: 9, letterSpacing: "0.1em", color: "#9a978d", textTransform: "uppercase" }}>{label}</div>
      <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4, color: "#1d1c1a", lineHeight: 1.2 }}>{value}</div>
      <div style={{ fontSize: 10, color: "#9a978d", marginTop: 3, fontFamily: CE_FONT_MONO }}>{sub}</div>
    </div>
  );
}

function CETag({ children, tone }) {
  const tones = {
    good: { bg: "#dcf2e1", fg: "#14532d", border: "#86c89a" },
    warn: { bg: "#fde6cc", fg: "#7c2d12", border: "#f0a060" },
    risk: { bg: "#fadcd6", fg: "#7f1d1d", border: "#e88472" },
    info: { bg: "#dde8f3", fg: "#1e3a5f", border: "#8aacd0" },
  };
  const t = tones[tone] || tones.info;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", padding: "4px 10px",
      background: t.bg, color: t.fg, border: `1px solid ${t.border}`,
      fontSize: 11, fontWeight: 600, fontFamily: CE_FONT_MONO, letterSpacing: "0.02em",
    }}>{children}</span>
  );
}

/* ───────────── Desktop · Matrix (Tabelle) ───────────── */

function CEDesktopMatrix({ profile, data, best }) {
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: CE_FONT_MONO, fontVariantNumeric: "tabular-nums" }}>
      <thead>
        <tr style={{ background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
          <th style={{ ...ceThStyle("left"), width: 100 }}>Metrik</th>
          {data.rows.map(r => {
            const l = data.locations[r.id];
            return (
              <th key={r.id} style={{
                ...ceThStyle("center"),
                background: r.rank === 1 ? "rgba(61,107,58,0.06)" : "transparent",
              }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    minWidth: 24, height: 16, padding: "0 5px",
                    background: r.rank === 1 ? "#3d6b3a" : "#1d1c1a",
                    color: "#fff", fontSize: 9, fontWeight: 600, letterSpacing: "0.04em",
                  }}>#{r.rank}</span>
                  <span style={{
                    fontFamily: CE_FONT_SANS, fontSize: 11, fontWeight: 600,
                    color: "#1d1c1a", textAlign: "center", lineHeight: 1.25,
                  }}>{l.name}</span>
                </div>
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {profile.cols.map(c => (
          <tr key={c.key} style={{ borderBottom: "1px solid #f0ece1" }}>
            <td style={{ ...ceTdStyle("left"), fontFamily: CE_FONT_SANS, color: "#3a3835", fontWeight: 500, fontSize: 12 }}>{c.label}</td>
            {data.rows.map(r => {
              const display = ceDisplay(c, r);
              const isBest = ceIsBest(c, r, best);
              const isWinnerCol = r.rank === 1;
              return (
                <td key={r.id} style={{
                  ...ceTdStyle("center"),
                  background: isBest ? "rgba(61,107,58,0.12)" : (isWinnerCol ? "rgba(61,107,58,0.03)" : "transparent"),
                  color: isBest ? "#2c4f29" : "#1d1c1a",
                  fontWeight: isBest ? 700 : (c.key === "score" ? 600 : 500),
                  fontSize: c.key === "score" ? 15 : 13,
                }}>{display}</td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ───────────── Mobile · Matrix (Karten pro Ort) ───────────── */

function CEMobileMatrix({ profile, data, best }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
      {data.rows.map(r => {
        const l = data.locations[r.id];
        const isWinner = r.rank === 1;
        const otherCols = profile.cols.filter(c => c.key !== "score");
        return (
          <div key={r.id} style={{
            border: "1px solid #e6e1d3",
            borderLeft: `3px solid ${isWinner ? "#3d6b3a" : "#d8d3c7"}`,
            background: isWinner ? "rgba(61,107,58,0.03)" : "#fff",
          }}>
            {/* Card-Header */}
            <div style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "10px 12px", borderBottom: "1px solid #f0ece1",
              background: isWinner ? "rgba(61,107,58,0.05)" : "#fbfaf6",
            }}>
              <span style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                minWidth: 26, height: 18, padding: "0 6px",
                background: isWinner ? "#3d6b3a" : "#1d1c1a",
                color: "#fff", fontSize: 10, fontWeight: 600,
                fontFamily: CE_FONT_MONO, letterSpacing: "0.04em",
              }}>#{r.rank}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600, color: "#1d1c1a", lineHeight: 1.2 }}>{l.name}</div>
                <div style={{ fontSize: 10, color: "#9a978d", fontFamily: CE_FONT_MONO, marginTop: 1 }}>
                  {l.group} · {ceFmt(l.elev)} m
                </div>
              </div>
              <div style={{
                fontFamily: CE_FONT_MONO, fontVariantNumeric: "tabular-nums",
                fontSize: 20, fontWeight: 700,
                color: isWinner ? "#3d6b3a" : "#1d1c1a", lineHeight: 1,
              }}>
                {r.score}
                <span style={{ fontSize: 9, color: "#9a978d", fontWeight: 500, marginLeft: 4, letterSpacing: "0.06em" }}>SCORE</span>
              </div>
            </div>

            {/* Card-Body: Metriken in 2-Spalten-Grid */}
            <div style={{
              padding: "8px 4px",
              display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0",
            }}>
              {otherCols.map((c, i) => {
                const isBest = ceIsBest(c, r, best);
                const display = ceDisplay(c, r);
                return (
                  <div key={c.key} style={{
                    display: "flex", justifyContent: "space-between", alignItems: "baseline",
                    padding: "6px 10px",
                    background: isBest ? "rgba(61,107,58,0.10)" : "transparent",
                  }}>
                    <span style={{ fontSize: 11, color: "#6b6962", fontFamily: CE_FONT_SANS }}>{c.label}</span>
                    <span style={{
                      fontSize: 12, fontFamily: CE_FONT_MONO, fontVariantNumeric: "tabular-nums",
                      color: isBest ? "#2c4f29" : "#1d1c1a",
                      fontWeight: isBest ? 700 : 500,
                    }}>{display}</span>
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </div>
  );
}

/* ───────────── Desktop · Stunden ───────────── */

function CEDesktopHours({ data }) {
  const top3 = data.rows.slice(0, 3);
  const hoursRef = data.hours[top3[0].id] || [];
  return (
    <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: CE_FONT_MONO, fontVariantNumeric: "tabular-nums" }}>
      <thead>
        <tr style={{ background: "#fbfaf6", borderBottom: "1px solid #e6e1d3" }}>
          <th style={{ ...ceThStyle("left"), width: 50 }}>Zeit</th>
          {top3.map(r => {
            const l = data.locations[r.id];
            return (
              <th key={r.id} style={{ ...ceThStyle("center"), background: r.rank === 1 ? "rgba(61,107,58,0.06)" : "transparent" }}>
                <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3 }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    width: 18, height: 14, background: r.rank === 1 ? "#3d6b3a" : "#1d1c1a",
                    color: "#fff", fontSize: 8, fontWeight: 600,
                  }}>#{r.rank}</span>
                  <span style={{ fontFamily: CE_FONT_SANS, fontSize: 11, fontWeight: 600, color: "#1d1c1a", textAlign: "center", lineHeight: 1.2 }}>{l.name}</span>
                </div>
              </th>
            );
          })}
        </tr>
      </thead>
      <tbody>
        {hoursRef.map((_, i) => (
          <tr key={i} style={{ borderBottom: "1px solid #f0ece1" }}>
            <td style={{ ...ceTdStyle("left"), color: "#6b6962", fontSize: 12 }}>{hoursRef[i][0]}:00</td>
            {top3.map(r => {
              const h = data.hours[r.id] && data.hours[r.id][i];
              if (!h) return <td key={r.id} style={ceTdStyle("center")}>—</td>;
              return (
                <td key={r.id} style={{
                  ...ceTdStyle("center"),
                  background: r.rank === 1 ? "rgba(61,107,58,0.03)" : "transparent",
                  fontSize: 11, padding: "8px 4px",
                }}>
                  <CEHourCell glyph={h[4]} temp={h[1]} prec={h[2]} wind={h[3]}/>
                </td>
              );
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/* ───────────── Mobile · Stunden (pro Ort ein Block) ───────────── */

function CEMobileHours({ data }) {
  const top3 = data.rows.slice(0, 3);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, marginTop: 12 }}>
      {top3.map(r => {
        const l = data.locations[r.id];
        const hours = data.hours[r.id] || [];
        const isWinner = r.rank === 1;
        return (
          <div key={r.id} style={{
            border: "1px solid #e6e1d3",
            background: isWinner ? "rgba(61,107,58,0.03)" : "#fff",
          }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              padding: "8px 12px", borderBottom: "1px solid #f0ece1",
              background: isWinner ? "rgba(61,107,58,0.05)" : "#fbfaf6",
            }}>
              <span style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                minWidth: 22, height: 14, padding: "0 5px",
                background: isWinner ? "#3d6b3a" : "#1d1c1a",
                color: "#fff", fontSize: 9, fontWeight: 600, fontFamily: CE_FONT_MONO,
              }}>#{r.rank}</span>
              <span style={{ fontSize: 12, fontWeight: 600, color: "#1d1c1a" }}>{l.name}</span>
            </div>
            <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: CE_FONT_MONO, fontVariantNumeric: "tabular-nums" }}>
              <tbody>
                {hours.map((h, i) => (
                  <tr key={i} style={{ borderBottom: i < hours.length - 1 ? "1px solid #f5f1e6" : "none" }}>
                    <td style={{ padding: "5px 12px", fontSize: 11, color: "#6b6962", width: 40 }}>{h[0]}:00</td>
                    <td style={{ padding: "5px 4px", textAlign: "center", fontSize: 11, width: 16 }}>
                      <span style={{ color: h[4] === "☼" ? "#d99a2a" : h[4] === "☁" ? "#9a958a" : "#8aa4c0", fontWeight: 700 }}>{h[4]}</span>
                    </td>
                    <td style={{ padding: "5px 4px", textAlign: "right", fontSize: 12, fontWeight: 600, width: 36 }}>
                      {Number(h[1]) > 0 ? "+" : ""}{h[1]}°
                    </td>
                    <td style={{ padding: "5px 4px", textAlign: "center", fontSize: 11, color: "#4a7ab8", width: 28 }}>
                      {h[2] !== "-" ? h[2] : ""}
                    </td>
                    <td style={{ padding: "5px 12px 5px 4px", textAlign: "right", fontSize: 11, color: "#6b6962" }}>
                      {h[3]}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        );
      })}
    </div>
  );
}

function CEHourCell({ glyph, temp, prec, wind }) {
  const glyphColor = glyph === "☼" ? "#d99a2a" : glyph === "☁" ? "#9a958a" : glyph === "❅" ? "#8aa4c0" : "#9a958a";
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11 }}>
      <span style={{ color: glyphColor, fontWeight: 700, width: 10 }}>{glyph}</span>
      <span style={{ fontWeight: 600, minWidth: 22, textAlign: "right" }}>{Number(temp) > 0 ? "+" : ""}{temp}°</span>
      {prec !== "-" && <span style={{ color: "#4a7ab8" }}>{prec}</span>}
      <span style={{ color: "#6b6962" }}>{wind}</span>
    </div>
  );
}

function ceThStyle(align) {
  return {
    fontSize: 10, color: "#9a978d", fontWeight: 600,
    padding: "10px 6px", textAlign: align || "center",
    borderRight: "1px solid #f0ece1", verticalAlign: "bottom",
  };
}
function ceTdStyle(align) {
  return {
    fontSize: 13, padding: "9px 6px",
    textAlign: align || "center",
    color: "#1d1c1a",
    borderRight: "1px solid #f0ece1",
  };
}

window.CompareEmail = CompareEmail;

/* ───────────── iPhone-Mail.app Frame ───────────── */
// Schmaler iPhone-Frame (Statusbar + Mail-Toolbar oben, Compose-Bar unten),
// damit man den Mobile-Mail-Render in echtem Kontext sieht.
function CEPhoneFrame({ children }) {
  return (
    <div style={{
      padding: 16, background: "#1a1a18", minHeight: "100%",
      display: "flex", justifyContent: "center",
    }}>
      <div style={{
        width: 400, background: "#000", borderRadius: 44, padding: 8,
        boxShadow: "0 12px 40px rgba(0,0,0,0.4), inset 0 0 0 1px #2a2a28",
      }}>
        <div style={{ background: "#f2f1ec", borderRadius: 36, overflow: "hidden", position: "relative" }}>
          {/* iOS Status Bar */}
          <div style={{
            display: "flex", justifyContent: "space-between", alignItems: "center",
            padding: "14px 28px 6px", color: "#000",
            fontFamily: "-apple-system, system-ui, sans-serif",
          }}>
            <span style={{ fontSize: 15, fontWeight: 600 }}>9:41</span>
            <div style={{
              position: "absolute", top: 8, left: "50%", transform: "translateX(-50%)",
              width: 110, height: 30, background: "#000", borderRadius: 18,
            }}/>
            <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
              <svg width="16" height="10" viewBox="0 0 17 12"><rect x="0" y="7.5" width="3" height="4.5" rx="0.7" fill="#000"/><rect x="4.5" y="5" width="3" height="7" rx="0.7" fill="#000"/><rect x="9" y="2.5" width="3" height="9.5" rx="0.7" fill="#000"/><rect x="13.5" y="0" width="3" height="12" rx="0.7" fill="#000"/></svg>
              <svg width="15" height="10" viewBox="0 0 17 12"><path d="M8.5 3.2C10.8 3.2 12.9 4.1 14.4 5.6L15.5 4.5C13.7 2.7 11.2 1.5 8.5 1.5C5.8 1.5 3.3 2.7 1.5 4.5L2.6 5.6C4.1 4.1 6.2 3.2 8.5 3.2Z" fill="#000"/><path d="M8.5 6.8C9.9 6.8 11.1 7.3 12 8.2L13.1 7.1C11.8 5.9 10.2 5.1 8.5 5.1C6.8 5.1 5.2 5.9 3.9 7.1L5 8.2C5.9 7.3 7.1 6.8 8.5 6.8Z" fill="#000"/><circle cx="8.5" cy="10.5" r="1.5" fill="#000"/></svg>
              <svg width="24" height="11" viewBox="0 0 27 13"><rect x="0.5" y="0.5" width="23" height="12" rx="3.5" stroke="#000" strokeOpacity="0.35" fill="none"/><rect x="2" y="2" width="20" height="9" rx="2" fill="#000"/><path d="M25 4.5V8.5C25.8 8.2 26.5 7.2 26.5 6.5C26.5 5.8 25.8 4.8 25 4.5Z" fill="#000" fillOpacity="0.4"/></svg>
            </div>
          </div>

          {/* Mail.app Toolbar */}
          <div style={{
            display: "flex", alignItems: "center", justifyContent: "space-between",
            padding: "10px 16px 8px", borderBottom: "0.5px solid rgba(0,0,0,0.12)",
            background: "rgba(242,241,236,0.92)",
            backdropFilter: "blur(10px)",
          }}>
            <span style={{ fontSize: 15, color: "#007aff", fontFamily: "-apple-system, system-ui, sans-serif" }}>‹ Posteingang</span>
            <div style={{ display: "flex", gap: 18, color: "#007aff" }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 9 12 15 18 9"/></svg>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="6 15 12 9 18 15"/></svg>
            </div>
          </div>

          {/* Mail-Header (From / To) */}
          <div style={{
            padding: "10px 16px 12px", borderBottom: "0.5px solid rgba(0,0,0,0.10)",
            background: "#fff",
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <div style={{
                width: 36, height: 36, borderRadius: "50%", background: "#c45a2a",
                color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 13, fontWeight: 700, fontFamily: "-apple-system, system-ui, sans-serif",
              }}>GZ</div>
              <div style={{ flex: 1, minWidth: 0, fontFamily: "-apple-system, system-ui, sans-serif" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                  <span style={{ fontSize: 14, fontWeight: 600, color: "#000" }}>Gregor Zwanzig</span>
                  <span style={{ fontSize: 12, color: "#8a8580" }}>06:00</span>
                </div>
                <div style={{ fontSize: 12, color: "#8a8580", marginTop: 1 }}>an mich</div>
              </div>
            </div>
          </div>

          {/* Email-Body */}
          <div style={{ background: "#fff" }}>
            {children}
          </div>

          {/* Home-Indicator */}
          <div style={{
            display: "flex", justifyContent: "center", padding: "6px 0 8px", background: "#fff",
          }}>
            <div style={{ width: 120, height: 4, background: "#000", borderRadius: 2 }}/>
          </div>
        </div>
      </div>
    </div>
  );
}

window.CEPhoneFrame = CEPhoneFrame;
