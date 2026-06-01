/* Mobile · Alert-Konfigurator
 * Pattern: Modus-Auswahl als Card-Stack (3 Karten), Metriken-Liste mit Slidern (eingebaut).
 * Sticky Save-Bar unten.
 */

const ALERT_METRICS_M = [
  { id: "wind",      label: "Wind",            unit: "km/h", abs: 50,   delta: 20,  cmp: "über",  on: true },
  { id: "gust",      label: "Böen",            unit: "km/h", abs: 70,   delta: 25,  cmp: "über",  on: true },
  { id: "thunder",   label: "Gewitter-Wahrsch.", unit: "%",  abs: 40,   delta: 20,  cmp: "über",  on: true },
  { id: "precip",    label: "Niederschlag",    unit: "mm",   abs: 5,    delta: 10,  cmp: "über",  on: true },
  { id: "rainProb",  label: "Regen-Wahrsch.",  unit: "%",    abs: 70,   delta: 30,  cmp: "über",  on: false },
  { id: "temp",      label: "Temperatur",      unit: "°C",   abs: -5,   delta: 5,   cmp: "unter", on: false },
  { id: "visibility",label: "Sichtweite",      unit: "km",   abs: 1,    delta: 5,   cmp: "unter", on: true },
  { id: "freezeLine",label: "Nullgrad-Grenze", unit: "m",    abs: 2000, delta: 200, cmp: "unter", on: true },
  { id: "snowfall",  label: "Schneefall",      unit: "cm",   abs: 10,   delta: 5,   cmp: "über",  on: false },
];

function ScreenAlertConfigMobile({ embedded = false } = {}) {
  const [mode, setMode] = React.useState("both");
  const onCount = ALERT_METRICS_M.filter(m => m.on).length;

  const body = (
    <>
          {/* Intro */}
          <div style={{ marginBottom: 18 }}>
            <h2 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", margin: 0, lineHeight: 1.25 }}>
              Wann soll ein Alert ausgelöst werden?
            </h2>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5 }}>
              Alerts kommen zwischen Morgen- und Abend-Briefing. Wähle den Modus.
            </div>
          </div>

          {/* Modus-Auswahl */}
          <Eyebrow style={{ marginBottom: 8 }}>Auslöse-Modus</Eyebrow>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
            <ModeCardM
              id="delta" active={mode === "delta"} onClick={() => setMode("delta")}
              title="Δ-Änderung" eyebrow="Reaktiv"
              desc="Wert ändert sich seit letztem Report stark."
              example="z.B. Wind +20 km/h, Gewitter +30 %"
            />
            <ModeCardM
              id="absolute" active={mode === "absolute"} onClick={() => setMode("absolute")}
              title="Schwellwert" eyebrow="Absolut"
              desc="Wert über- oder unterschreitet eine Grenze."
              example="z.B. Wind > 50 km/h, Sicht < 1 km"
            />
            <ModeCardM
              id="both" active={mode === "both"} onClick={() => setMode("both")}
              title="Beides" eyebrow="Empfohlen"
              desc="Δ und absolut kombiniert. Maximale Abdeckung."
              example="Standard für aktive Trips"
            />
          </div>

          {/* Metriken-Liste */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <Eyebrow>Metriken & Schwellen</Eyebrow>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
              {onCount} von {ALERT_METRICS_M.length} aktiv
            </span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 16 }}>
            {ALERT_METRICS_M.map(m => (
              <AlertMetricCardM key={m.id} m={m} mode={mode}/>
            ))}
          </div>

          {/* Channel-Routing */}
          <Card padding={14} style={{ marginBottom: 16 }}>
            <Eyebrow style={{ marginBottom: 8 }}>Alert-Kanal</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginBottom: 10, lineHeight: 1.5 }}>
              Alerts gehen NUR auf diesen Kanal — separat von Briefings.
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {["Signal","SMS","Telegram","Email"].map((k, i) => (
                <button key={k} style={{
                  padding: "8px 14px", minHeight: 40, borderRadius: "var(--g-r-pill)",
                  background: i === 0 ? "var(--g-accent)" : "var(--g-card-alt)",
                  color: i === 0 ? "#fff" : "var(--g-ink-2)",
                  border: `1px solid ${i === 0 ? "var(--g-accent)" : "var(--g-rule)"}`,
                  fontSize: 13, fontFamily: "var(--g-font-mono)", fontWeight: 500, cursor: "pointer",
                }}>{k}</button>
              ))}
            </div>
          </Card>

          {/* Quiet hours */}
          <Card padding={14}>
            <Eyebrow style={{ marginBottom: 8 }}>Ruhezeit</Eyebrow>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>22:00 – 06:00</div>
                <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2 }}>Nur Gewitter-Alerts werden zugestellt</div>
              </div>
              <MSwitch checked/>
            </div>
          </Card>
    </>
  );

  if (embedded) return <div style={{ padding: 16 }}>{body}</div>;

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Alerts"
          eyebrow="KHW 403 · Sofort-Benachrichtigung"
          leftIcon="back"
          right={<button style={{ padding: "0 12px", minHeight: 44, background: "transparent", border: "none", fontSize: 14, color: "var(--g-ink-3)" }}>Verwerfen</button>}
        />
        <ScreenScroll padding={16}>{body}</ScreenScroll>
        <div style={{
          padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8, flexShrink: 0,
        }}>
          <MBtn variant="ghost" size="lg" style={{ flex: 1 }}>Test-Alert</MBtn>
          <MBtn variant="primary" size="lg" style={{ flex: 1.6 }}>Speichern</MBtn>
        </div>
      </div>
    </PhoneFrame>
  );
}

function ModeCardM({ id, active, onClick, title, eyebrow, desc, example }) {
  return (
    <button onClick={onClick} style={{
      padding: "14px 14px", textAlign: "left", cursor: "pointer", minHeight: 84,
      background: active ? "var(--g-accent-tint)" : "var(--g-card)",
      border: active ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)",
      display: "flex", gap: 12, alignItems: "flex-start",
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: "50%", flexShrink: 0,
        border: `2px solid ${active ? "var(--g-accent)" : "var(--g-rule)"}`,
        background: active ? "var(--g-accent)" : "transparent",
        display: "flex", alignItems: "center", justifyContent: "center",
        marginTop: 2,
      }}>
        {active && <span style={{ width: 8, height: 8, borderRadius: "50%", background: "#fff" }}/>}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 2 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: active ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{title}</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.1em" }}>· {eyebrow}</span>
        </div>
        <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.4 }}>{desc}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 4 }}>{example}</div>
      </div>
    </button>
  );
}

function AlertMetricCardM({ m, mode }) {
  return (
    <div style={{
      padding: "12px 14px", background: m.on ? "var(--g-card)" : "var(--g-card-alt)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
      opacity: m.on ? 1 : 0.7,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: m.on ? 10 : 0 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 600 }}>{m.label}</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
            {mode === "delta" ? `Δ ≥ ${m.delta} ${m.unit}` :
             mode === "absolute" ? `${m.cmp} ${m.abs}${m.unit}` :
             `${m.cmp} ${m.abs}${m.unit} · Δ ≥ ${m.delta}`}
          </div>
        </div>
        <MSwitch checked={m.on}/>
      </div>
      {m.on && (
        <div style={{ borderTop: "1px solid var(--g-rule-soft)", paddingTop: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          {(mode === "absolute" || mode === "both") && (
            <ThresholdRowM label={m.cmp === "über" ? "Über" : "Unter"} value={`${m.abs}`} unit={m.unit}/>
          )}
          {(mode === "delta" || mode === "both") && (
            <ThresholdRowM label="Δ ≥" value={`${m.delta}`} unit={m.unit} delta/>
          )}
        </div>
      )}
    </div>
  );
}

function ThresholdRowM({ label, value, unit, delta }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span className="mono" style={{
        fontSize: 11, color: delta ? "var(--g-accent)" : "var(--g-ink-3)",
        textTransform: "uppercase", letterSpacing: "0.06em", width: 60, fontWeight: 600,
      }}>{label}</span>
      <button style={{
        width: 32, height: 32, borderRadius: "var(--g-r-2)",
        background: "var(--g-card-alt)", border: "1px solid var(--g-rule)", cursor: "pointer",
        fontSize: 16, color: "var(--g-ink-2)", lineHeight: 1,
      }}>−</button>
      <div style={{
        flex: 1, minHeight: 36, padding: "8px 10px", textAlign: "center",
        background: "var(--g-paper)", border: "1px solid var(--g-rule)",
        borderRadius: "var(--g-r-2)", fontFamily: "var(--g-font-mono)", fontWeight: 600, fontSize: 14,
        display: "flex", alignItems: "center", justifyContent: "center", gap: 4,
      }}>
        <span>{value}</span>
        <span style={{ color: "var(--g-ink-4)", fontSize: 12 }}>{unit}</span>
      </div>
      <button style={{
        width: 32, height: 32, borderRadius: "var(--g-r-2)",
        background: "var(--g-card-alt)", border: "1px solid var(--g-rule)", cursor: "pointer",
        fontSize: 16, color: "var(--g-ink-2)", lineHeight: 1,
      }}>+</button>
    </div>
  );
}

window.ScreenAlertConfigMobile = ScreenAlertConfigMobile;
