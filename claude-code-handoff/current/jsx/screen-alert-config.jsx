/* Screen: Alert-Konfigurator (standalone, Design-Canvas)
 * Preset-Modell pro Metrik (issue_846, approved):
 * Kein Zahlen-Input — der User wählt je Metrik eine Empfindlichkeit
 * (Aus / Entspannt / Standard / Sensibel). Die Schwellwerte sind vorgegeben.
 * Kein Modus-Karten, kein Signal, kein Severity.
 */

const AC_PRESET_TABLE = [
  { label: "Böen",                   unit: "km/h", cmp: "über",  relaxed: 85,   standard: 70,   sensitive: 55 },
  { label: "Niederschlag",           unit: "mm/h", cmp: "über",  relaxed: 8,    standard: 5,    sensitive: 3 },
  { label: "Gewitter",               unit: "%",    cmp: "über",  relaxed: 60,   standard: 40,   sensitive: 25 },
  { label: "Schneefallgrenze",       unit: "m",    cmp: "unter", relaxed: 1200, standard: 1500, sensitive: 1800 },
  { label: "Temp. Min",              unit: "°C",   cmp: "unter", relaxed: -10,  standard: -5,   sensitive: 0 },
  { label: "Temp. Max",              unit: "°C",   cmp: "über",  relaxed: 32,   standard: 28,   sensitive: 24 },
  { label: "Temp.-Änderung",         unit: "°C",   cmp: "delta", relaxed: 8,    standard: 5,    sensitive: 3 },
  { label: "Wind-Änderung",          unit: "km/h", cmp: "delta", relaxed: 30,   standard: 20,   sensitive: 12 },
  { label: "Niederschlags-Änderung", unit: "mm",   cmp: "delta", relaxed: 15,   standard: 10,   sensitive: 5 },
  { label: "Neuschnee",              unit: "cm",   cmp: "über",  relaxed: 20,   standard: 10,   sensitive: 5 },
  { label: "CAPE",                   unit: "J/kg", cmp: "über",  relaxed: 800,  standard: 500,  sensitive: 300 },
  { label: "Sichtweite",             unit: "km",   cmp: "unter", relaxed: 0.5,  standard: 1,    sensitive: 2 },
  { label: "Luftfeuchtigkeit",       unit: "%",    cmp: "über",  relaxed: 98,   standard: 95,   sensitive: 90 },
];

const AC_SENS_LEVELS = [
  { id: "off",       label: "Aus" },
  { id: "relaxed",   label: "Entspannt" },
  { id: "standard",  label: "Standard" },
  { id: "sensitive", label: "Sensibel" },
];

const AC_SAMPLE = [
  { metric: "Gewitter",   from: "15 %",    to: "60 %",    stage: "Etappe 3 · 14–18 Uhr" },
  { metric: "Böen",       from: "45 km/h", to: "72 km/h", stage: "Etappe 3 · 14–16 Uhr" },
  { metric: "Sichtweite", from: "15 km",   to: "6 km",    stage: "Etappe 3 · 14–18 Uhr" },
];

function AC_cell(r, col) {
  const v = r[col];
  if (r.cmp === "delta") return "Δ ≥ " + v;
  return (r.cmp === "über" ? "> " : "< ") + v;
}

function AC_SensSeg({ value, onChange }) {
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)", overflow: "hidden", background: "var(--g-card)" }}>
      {AC_SENS_LEVELS.map((lv, i) => {
        const on = value === lv.id;
        const isOff = lv.id === "off";
        return (
          <button key={lv.id} onClick={() => onChange(lv.id)} style={{
            padding: "6px 14px", border: "none", cursor: "pointer",
            borderLeft: i === 0 ? "none" : "1px solid var(--g-rule-soft)",
            background: on ? (isOff ? "var(--g-ink-3)" : "var(--g-accent)") : "transparent",
            color: on ? "#fff" : "var(--g-ink-3)",
            fontSize: 12, fontWeight: on ? 600 : 500, fontFamily: "var(--g-font-sans)",
            whiteSpace: "nowrap", transition: "all 120ms",
          }}>{lv.label}</button>
        );
      })}
    </div>
  );
}

function AC_MetricRow({ r, level, onLevel, isLast }) {
  const off = level === "off";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "190px 1fr 116px", alignItems: "center", padding: "10px 20px", borderBottom: isLast ? "none" : "1px solid var(--g-rule-soft)", background: off ? "transparent" : "rgba(196,90,42,0.025)", opacity: off ? 0.6 : 1, transition: "opacity 120ms, background 120ms" }}>
      <div style={{ fontSize: 13.5, fontWeight: off ? 400 : 600, color: "var(--g-ink)" }}>
        {r.label} <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{r.unit}</span>
      </div>
      <div><AC_SensSeg value={level} onChange={onLevel}/></div>
      <div className="mono" style={{ fontSize: 12.5, textAlign: "right", color: off ? "var(--g-ink-4)" : "var(--g-accent-deep)", fontWeight: off ? 400 : 600 }}>
        {off ? "kein Alert" : AC_cell(r, level)}
      </div>
    </div>
  );
}

function AC_SamplePreview() {
  return (
    <div style={{ background: "#fff", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", maxWidth: 560, overflow: "hidden", fontFamily: "Helvetica, Arial, sans-serif" }}>
      <div style={{ background: "var(--g-accent)", color: "#fff", padding: "12px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", opacity: 0.9 }}>ALERT · KHW 403</div>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>Wetter-Änderung erkannt</div>
        </div>
        <div className="mono" style={{ fontSize: 10, opacity: 0.9, textAlign: "right", lineHeight: 1.5 }}>Mi 14.05.<br/>14:23</div>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontVariantNumeric: "tabular-nums" }}>
        <thead>
          <tr style={{ background: "rgba(196,90,42,0.05)" }}>
            <th style={{ textAlign: "left", padding: "8px 18px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.04em" }}>Metrik</th>
            <th style={{ textAlign: "right", padding: "8px 8px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600 }}>Vorher</th>
            <th style={{ textAlign: "right", padding: "8px 8px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600 }}>Nachher</th>
            <th style={{ textAlign: "left", padding: "8px 18px", fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600 }}>Etappe · Zeitraum</th>
          </tr>
        </thead>
        <tbody>
          {AC_SAMPLE.map(r => (
            <tr key={r.metric} style={{ borderTop: "1px solid var(--g-rule-soft)" }}>
              <td style={{ padding: "9px 18px", fontSize: 13, fontWeight: 600, color: "var(--g-ink)" }}>{r.metric}</td>
              <td className="mono" style={{ padding: "9px 8px", fontSize: 12, textAlign: "right", color: "var(--g-ink-3)" }}>{r.from}</td>
              <td className="mono" style={{ padding: "9px 8px", fontSize: 12, textAlign: "right", color: "var(--g-accent-deep)", fontWeight: 600 }}>{r.to}</td>
              <td className="mono" style={{ padding: "9px 18px", fontSize: 11, color: "var(--g-ink-3)" }}>{r.stage}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mono" style={{ padding: "10px 18px", borderTop: "1px solid var(--g-rule-soft)", background: "var(--g-paper-deep)", fontSize: 10.5, color: "var(--g-ink-3)" }}>
        Andere Etappen: keine relevanten Änderungen seit Morgen-Briefing.
      </div>
    </div>
  );
}

function ScreenAlertConfig({ embedded = false } = {}) {
  const [levels, setLevels] = React.useState(() => Object.fromEntries(AC_PRESET_TABLE.map(r => [r.label, "standard"])));
  const setAll = (lv) => setLevels(Object.fromEntries(AC_PRESET_TABLE.map(r => [r.label, lv])));
  const setOne = (label, lv) => setLevels(s => ({ ...s, [label]: lv }));
  const vals = Object.values(levels);
  const onCount = vals.filter(v => v !== "off").length;
  const allOff = onCount === 0;
  const uniform = vals.every(v => v === vals[0]) ? vals[0] : null;

  const [cooldown, setCooldown] = React.useState(60);
  const [quietFrom, setQuietFrom] = React.useState("22:00");
  const [quietTo, setQuietTo] = React.useState("06:00");

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }} data-screen-label="Alert-Konfigurator (Desktop)">
      {!embedded && <Sidebar active="trips"/>}
      <main style={{ flex: 1, position: "relative" }}>
        {!embedded && <TopoBg opacity={0.12}/>}

        {!embedded && (
        <div style={{ position: "relative", padding: "16px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
            <span style={{ opacity: 0.6 }}>Trips</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ opacity: 0.6 }}>KHW 403</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>Alerts</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost" size="sm">Verwerfen</Btn>
            <Btn variant="primary" size="sm">Speichern</Btn>
          </div>
        </div>
        )}

        <div style={{ position: "relative", padding: "32px 40px 60px", maxWidth: 820 }}>
          <Eyebrow>Alert-Briefings · Sofort-Benachrichtigung</Eyebrow>
          <h1 style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 6px" }}>
            Sofort-Meldung zwischen den Briefings
          </h1>
          <div style={{ fontSize: 14, color: "var(--g-ink-3)", maxWidth: 660, marginBottom: 26, lineHeight: 1.55 }}>
            Gregor Zwanzig meldet zwischen Morgen- und Abend-Briefing, wenn sich das Wetter stärker entwickelt als zuletzt vorhergesagt (<strong style={{ color: "var(--g-ink)" }}>Abweichungs-Alert</strong>) oder in den nächsten 20 Minuten unerwartet Regen oder Gewitter aufzieht (<strong style={{ color: "var(--g-ink)" }}>Radar-Alert</strong>). Die Empfindlichkeit legst du je Metrik fest — die Schwellwerte sind vorgegeben.
          </div>

          {/* Global-Quickset */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, flexWrap: "wrap", marginBottom: 16 }}>
            <span style={{ fontSize: 13, color: "var(--g-ink-2)", flexShrink: 0 }}>Alle Metriken auf:</span>
            <AC_SensSeg value={uniform} onChange={setAll}/>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
              {onCount} von {AC_PRESET_TABLE.length} aktiv{uniform === null ? " · gemischt" : ""}
            </span>
          </div>

          {/* Pro-Metrik-Tabelle */}
          <Card padding={0}>
            <div style={{ display: "grid", gridTemplateColumns: "190px 1fr 116px", padding: "10px 20px", background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule)", alignItems: "center" }}>
              <Eyebrow>Metrik</Eyebrow>
              <Eyebrow>Empfindlichkeit</Eyebrow>
              <div style={{ textAlign: "right" }}><Eyebrow>Schwellwert</Eyebrow></div>
            </div>
            {AC_PRESET_TABLE.map((r, i) => (
              <AC_MetricRow key={r.label} r={r} level={levels[r.label]} onLevel={lv => setOne(r.label, lv)} isLast={i === AC_PRESET_TABLE.length - 1}/>
            ))}
          </Card>

          {/* Cooldown / Stille Stunden */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 28, maxWidth: 600, opacity: allOff ? 0.4 : 1, pointerEvents: allOff ? "none" : "auto", transition: "opacity 150ms" }}>
            <Card padding={20}>
              <Eyebrow>Cooldown</Eyebrow>
              <div style={{ fontSize: 13, color: "var(--g-ink-3)", margin: "6px 0 14px", lineHeight: 1.5 }}>
                Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei schwankenden Werten.
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <input type="number" value={cooldown} onChange={e => setCooldown(e.target.value)} style={{ width: 80, padding: "8px 10px", border: "1px solid var(--g-rule)", borderRadius: 3, fontSize: 14, fontFamily: "var(--g-font-mono)", textAlign: "right" }}/>
                <span style={{ fontSize: 13, color: "var(--g-ink-2)" }}>Minuten</span>
              </div>
            </Card>
            <Card padding={20}>
              <Eyebrow>Stille Stunden</Eyebrow>
              <div style={{ fontSize: 13, color: "var(--g-ink-3)", margin: "6px 0 14px", lineHeight: 1.5 }}>
                In diesem Zeitraum keine Alerts senden — gestaute Alerts gehen mit dem nächsten Morgen-Briefing mit.
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <input type="text" value={quietFrom} onChange={e => setQuietFrom(e.target.value)} style={{ width: 80, padding: "8px 10px", border: "1px solid var(--g-rule)", borderRadius: 3, fontSize: 14, fontFamily: "var(--g-font-mono)" }}/>
                <span style={{ fontSize: 13, color: "var(--g-ink-3)" }}>bis</span>
                <input type="text" value={quietTo} onChange={e => setQuietTo(e.target.value)} style={{ width: 80, padding: "8px 10px", border: "1px solid var(--g-rule)", borderRadius: 3, fontSize: 14, fontFamily: "var(--g-font-mono)" }}/>
              </div>
            </Card>
          </div>

          {/* Vorschau */}
          <div style={{ marginTop: 40, opacity: allOff ? 0.4 : 1, transition: "opacity 150ms" }}>
            <Eyebrow style={{ marginBottom: 4 }}>Beispiel-Alert</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginBottom: 14 }}>So sieht eine ausgelöste Alert-Mail aus.</div>
            <AC_SamplePreview/>
          </div>
        </div>
      </main>
    </div>
  );
}

window.ScreenAlertConfig = ScreenAlertConfig;
