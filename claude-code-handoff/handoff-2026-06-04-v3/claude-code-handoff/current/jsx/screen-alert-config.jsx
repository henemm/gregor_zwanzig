/* Screen: Alert-Konfigurator
 * Pro Trip: User waehlt Δ-Modus (Aenderung seit letztem Briefing) oder absolut (Schwellwert) oder beide.
 * Pro aktive Metrik: Schwellwert (Δ und/oder absolut) konfigurierbar.
 */

const ALERT_METRICS = [
  { id: "wind",      label: "Wind",                unit: "km/h", deltaDefault: 20,  absDefault: 50,  absLabel: "über" },
  { id: "gust",      label: "Böen",                unit: "km/h", deltaDefault: 25,  absDefault: 70,  absLabel: "über" },
  { id: "precip",    label: "Niederschlag",        unit: "mm",   deltaDefault: 10,  absDefault: 5,   absLabel: "über" },
  { id: "rainProb",  label: "Regen-Wahrsch.",      unit: "%",    deltaDefault: 30,  absDefault: 70,  absLabel: "über" },
  { id: "thunder",   label: "Gewitter-Wahrsch.",   unit: "%",    deltaDefault: 20,  absDefault: 40,  absLabel: "über" },
  { id: "temp",      label: "Temperatur",          unit: "°C",   deltaDefault: 5,   absDefault: -5,  absLabel: "unter" },
  { id: "visibility",label: "Sichtweite",          unit: "km",   deltaDefault: 5,   absDefault: 1,   absLabel: "unter" },
  { id: "freezeLine",label: "Nullgrad-Grenze",     unit: "m",    deltaDefault: 200, absDefault: 2000, absLabel: "unter" },
  { id: "snowfall",  label: "Schneefall",          unit: "cm",   deltaDefault: 5,   absDefault: 10,  absLabel: "über" },
];

function ScreenAlertConfig({ embedded = false } = {}) {
  const [mode, setMode] = React.useState("both");
  const [enabled, setEnabled] = React.useState({
    wind: true, gust: true, precip: true, rainProb: false, thunder: true,
    temp: false, visibility: true, freezeLine: true, snowfall: false,
  });

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
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

        <div style={{ position: "relative", padding: "32px 40px 60px", maxWidth: 1320 }}>
          <Eyebrow>Alert-Briefings · Sofort-Benachrichtigung</Eyebrow>
          <h1 style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 6px" }}>
            Wann soll ein Alert ausgelöst werden?
          </h1>
          <div style={{ fontSize: 14, color: "var(--g-ink-3)", maxWidth: 760, marginBottom: 28 }}>
            Alerts kommen zwischen Morning- und Abend-Briefing. Du wählst, ob sie auf <strong style={{ color: "var(--g-ink)" }}>Änderungen seit letztem Briefing</strong> (Δ) reagieren, auf <strong style={{ color: "var(--g-ink)" }}>absolute Schwellwerte</strong>, oder beides.
          </div>

          {/* Modus-Auswahl */}
          <SectionH eyebrow="Auslöse-Modus" title="Was triggert einen Alert?"/>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 12, marginBottom: 32 }}>
            <ModeCard
              id="delta"
              active={mode === "delta"}
              onClick={() => setMode("delta")}
              title="Δ-Änderung"
              eyebrow="Reaktiv"
              desc="Wenn sich ein Wert seit dem letzten Report stark ändert. Gut für sich entwickelnde Wetterlagen."
              example="z.B. Wind ändert sich um 20 km/h, Gewitter-Wahrsch. um 30%"
            />
            <ModeCard
              id="absolute"
              active={mode === "absolute"}
              onClick={() => setMode("absolute")}
              title="Schwellwert"
              eyebrow="Absolut"
              desc="Wenn ein Wert eine Grenze über- oder unterschreitet. Gut für klare Sicherheits-Limits."
              example="z.B. Wind > 50 km/h, Sicht < 1 km, Gewitter > 40%"
            />
            <ModeCard
              id="both"
              active={mode === "both"}
              onClick={() => setMode("both")}
              title="Beides"
              eyebrow="Empfohlen"
              desc="Δ-Änderungen und absolute Schwellwerte gleichzeitig prüfen. Maximale Abdeckung."
              example="Trigger sobald eines von beiden zutrifft"
            />
          </div>

          {/* Schwellwert-Editor */}
          <SectionH eyebrow="Schwellwerte" title="Pro Metrik festlegen"/>
          <Card padding={0}>
            <div style={{ display: "grid", gridTemplateColumns: "32px 200px 1fr 1fr", gap: 0, padding: "12px 20px", background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule)", alignItems: "center" }}>
              <div></div>
              <Eyebrow>Metrik</Eyebrow>
              <Eyebrow>Δ-Änderung (seit letztem Briefing)</Eyebrow>
              <Eyebrow>Absoluter Schwellwert</Eyebrow>
            </div>
            {ALERT_METRICS.map(m => (
              <AlertMetricRow
                key={m.id}
                metric={m}
                enabled={enabled[m.id]}
                onToggle={() => setEnabled({ ...enabled, [m.id]: !enabled[m.id] })}
                showDelta={mode === "delta" || mode === "both"}
                showAbs={mode === "absolute" || mode === "both"}
              />
            ))}
          </Card>

          {/* Cooldown / Stille Stunden */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, marginTop: 32 }}>
            <Card padding={20}>
              <Eyebrow>Cooldown</Eyebrow>
              <div style={{ fontSize: 13, color: "var(--g-ink-3)", margin: "6px 0 14px", lineHeight: 1.5 }}>
                Mindestabstand zwischen zwei Alerts derselben Metrik — verhindert Spam bei zappelnden Werten.
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <input type="number" defaultValue="60" style={{ width: 80, padding: "8px 10px", border: "1px solid var(--g-rule)", borderRadius: 3, fontSize: 14, fontFamily: "var(--g-font-mono)" }}/>
                <span style={{ fontSize: 13, color: "var(--g-ink-2)" }}>Minuten</span>
              </div>
            </Card>
            <Card padding={20}>
              <Eyebrow>Stille Stunden</Eyebrow>
              <div style={{ fontSize: 13, color: "var(--g-ink-3)", margin: "6px 0 14px", lineHeight: 1.5 }}>
                In diesem Zeitraum keine Alerts senden — gestaute Alerts gehen mit dem nächsten Morgen-Briefing mit.
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
                <input type="text" defaultValue="22:00" style={{ width: 80, padding: "8px 10px", border: "1px solid var(--g-rule)", borderRadius: 3, fontSize: 14, fontFamily: "var(--g-font-mono)" }}/>
                <span style={{ fontSize: 13, color: "var(--g-ink-3)" }}>bis</span>
                <input type="text" defaultValue="06:00" style={{ width: 80, padding: "8px 10px", border: "1px solid var(--g-rule)", borderRadius: 3, fontSize: 14, fontFamily: "var(--g-font-mono)" }}/>
              </div>
            </Card>
          </div>

          {/* Vorschau */}
          <div style={{ marginTop: 40 }}>
            <SectionH eyebrow="Beispiel-Alert" title="So sieht ein ausgelöster Alert aus"/>
            <AlertPreview/>
          </div>
        </div>
      </main>
    </div>
  );
}

function ModeCard({ id, active, onClick, title, eyebrow, desc, example }) {
  return (
    <div onClick={onClick} style={{
      padding: 18, borderRadius: 4, cursor: "pointer",
      background: active ? "var(--g-card)" : "transparent",
      border: active ? "2px solid var(--g-accent)" : "1px solid var(--g-rule)",
      transition: "all 120ms",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <Eyebrow>{eyebrow}</Eyebrow>
        <span style={{
          width: 18, height: 18, borderRadius: "50%",
          border: `2px solid ${active ? "var(--g-accent)" : "var(--g-rule)"}`,
          display: "inline-flex", alignItems: "center", justifyContent: "center",
        }}>
          {active && <span style={{ width: 8, height: 8, borderRadius: "50%", background: "var(--g-accent)" }}/>}
        </span>
      </div>
      <div style={{ fontSize: 18, fontWeight: 600, marginBottom: 6, color: active ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{title}</div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.5, marginBottom: 10 }}>{desc}</div>
      <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", paddingTop: 10, borderTop: "1px solid var(--g-rule-soft)", lineHeight: 1.5 }}>
        {example}
      </div>
    </div>
  );
}

function AlertMetricRow({ metric, enabled, onToggle, showDelta, showAbs }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "32px 200px 1fr 1fr", gap: 0,
      padding: "14px 20px", borderBottom: "1px solid var(--g-rule-soft)",
      alignItems: "center", opacity: enabled ? 1 : 0.45,
    }}>
      <label style={{ cursor: "pointer" }}>
        <span onClick={onToggle} style={{
          display: "inline-block", width: 30, height: 16, borderRadius: 9,
          background: enabled ? "var(--g-accent)" : "var(--g-rule)", position: "relative",
          transition: "background 120ms",
        }}>
          <span style={{
            position: "absolute", top: 2, left: enabled ? 16 : 2,
            width: 12, height: 12, borderRadius: "50%", background: "#fff",
            transition: "left 120ms",
          }}/>
        </span>
      </label>
      <div>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{metric.label}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{metric.unit}</div>
      </div>
      <div>
        {showDelta ? (
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>Δ ≥</span>
            <input type="number" defaultValue={metric.deltaDefault} disabled={!enabled} style={{
              width: 64, padding: "6px 8px", border: "1px solid var(--g-rule)",
              borderRadius: 3, fontSize: 13, fontFamily: "var(--g-font-mono)", textAlign: "right",
            }}/>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{metric.unit}</span>
          </div>
        ) : <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>— deaktiviert —</span>}
      </div>
      <div>
        {showAbs ? (
          <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{metric.absLabel}</span>
            <input type="number" defaultValue={metric.absDefault} disabled={!enabled} style={{
              width: 70, padding: "6px 8px", border: "1px solid var(--g-rule)",
              borderRadius: 3, fontSize: 13, fontFamily: "var(--g-font-mono)", textAlign: "right",
            }}/>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{metric.unit}</span>
          </div>
        ) : <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>— deaktiviert —</span>}
      </div>
    </div>
  );
}

/* Alert-Preview: NUR die Etappen/Werte, die sich geaendert haben */
function AlertPreview() {
  return (
    <div style={{ background: "#fff", border: "1px solid var(--g-rule)", maxWidth: 720, fontFamily: "Helvetica, Arial, sans-serif" }}>
      <div style={{ background: "var(--g-accent)", color: "#fff", padding: "14px 20px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div style={{ fontSize: 11, letterSpacing: "0.1em", opacity: 0.85, fontFamily: "var(--g-font-mono)" }}>ALERT · KHW 403</div>
          <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>Wetter-Änderung erkannt</div>
        </div>
        <div style={{ fontSize: 11, opacity: 0.85, fontFamily: "var(--g-font-mono)", textAlign: "right" }}>
          Mi 14.05.2026<br/>14:23 MESZ
        </div>
      </div>

      <div style={{ padding: "16px 20px", borderBottom: "2px solid var(--g-accent)", background: "rgba(196, 90, 42, 0.04)" }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.06em", marginBottom: 8, textTransform: "uppercase" }}>Was hat sich geändert</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 13, color: "var(--g-ink)", lineHeight: 1.5 }}>
          <div>↑ <strong>Gewitter-Wahrsch.</strong> auf Etappe 3 um <strong style={{ color: "var(--g-accent-deep)" }}>+45%</strong> gestiegen <span className="mono" style={{ color: "var(--g-ink-4)", fontSize: 11 }}>(15% → 60%, Schwelle Δ20%)</span></div>
          <div>↑ <strong>Böen</strong> auf Etappe 3 jetzt <strong style={{ color: "var(--g-accent-deep)" }}>72 km/h</strong> <span className="mono" style={{ color: "var(--g-ink-4)", fontSize: 11 }}>(absolut &gt; 70)</span></div>
          <div>↓ <strong>Sichtweite</strong> auf Etappe 3 um <strong style={{ color: "var(--g-accent-deep)" }}>−9 km</strong> gefallen <span className="mono" style={{ color: "var(--g-ink-4)", fontSize: 11 }}>(15 → 6, Schwelle Δ5)</span></div>
        </div>
      </div>

      <div style={{ padding: "14px 20px" }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>Etappe 3 · Plöckenpass → Hochweißsteinhaus</div>
        <table className="mono" style={{ width: "100%", borderCollapse: "collapse", fontSize: 11, fontVariantNumeric: "tabular-nums" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--g-rule)" }}>
              <th style={{ textAlign: "left", padding: "6px 8px 6px 0", color: "var(--g-ink-3)", fontWeight: 600 }}>Zeit</th>
              <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--g-ink-3)", fontWeight: 600 }}>Gewit.%</th>
              <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--g-ink-3)", fontWeight: 600 }}>Böen</th>
              <th style={{ textAlign: "right", padding: "6px 8px", color: "var(--g-ink-3)", fontWeight: 600 }}>Sicht</th>
            </tr>
          </thead>
          <tbody>
            <AlertChangeRow time="14:00" cells={[["60", "+45"], ["72", "+38"], ["6", "-9"]]}/>
            <AlertChangeRow time="16:00" cells={[["55", "+40"], ["68", "+32"], ["8", "-7"]]}/>
            <AlertChangeRow time="18:00" cells={[["35", "+20"], ["55", "+15"], ["12", "-3"]]}/>
          </tbody>
        </table>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 10, paddingTop: 10, borderTop: "1px solid var(--g-rule-soft)" }}>
          Andere Etappen: keine relevanten Änderungen seit Morgen-Briefing 06:00.
        </div>
      </div>

      <div style={{ padding: "12px 20px", background: "var(--g-paper-deep)", fontSize: 11, color: "var(--g-ink-3)", display: "flex", justifyContent: "space-between" }}>
        <span>Gregor Zwanzig · Alert-Report</span>
        <a href="#" style={{ color: "var(--g-accent-deep)", textDecoration: "none" }}>Vollständigen Report öffnen →</a>
      </div>
    </div>
  );
}

function AlertChangeRow({ time, cells }) {
  return (
    <tr style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
      <td style={{ padding: "7px 8px 7px 0", color: "var(--g-ink)", fontWeight: 600 }}>{time}</td>
      {cells.map((c, i) => (
        <td key={i} style={{ padding: "7px 8px", textAlign: "right" }}>
          <span style={{ color: "var(--g-ink)", fontWeight: 600 }}>{c[0]}</span>
          <span style={{ color: c[1].startsWith("-") ? "var(--g-info-deep)" : "var(--g-accent-deep)", marginLeft: 6, fontSize: 10 }}>
            {c[1].startsWith("-") ? c[1] : "+" + c[1]}
          </span>
        </td>
      ))}
    </tr>
  );
}

window.ScreenAlertConfig = ScreenAlertConfig;
