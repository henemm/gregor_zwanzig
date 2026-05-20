/* Mobile · Output-Vorschau
 * Pattern: Segmented Control oben (Email · SMS · Signal), darunter Vorschau-Inhalt.
 * Verwendet vorhandene EmailPreview-Komponente im Mobile-Modus.
 * Sticky Footer: Test-Senden + Konfig öffnen.
 */

function ScreenOutputPreviewMobile() {
  const [view, setView] = React.useState("email");
  const stage = MOCK_TRIP.stages[1];

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper-deep)" }}>
        <TopAppBar
          title="Briefing-Vorschau"
          eyebrow="KHW 403 · Morgen 06:00"
          leftIcon="back"
          right={<IconBtn kind="share" label="Teilen"/>}
        />

        {/* Segmented Control */}
        <div style={{ padding: "10px 16px", borderBottom: "1px solid var(--g-rule-soft)", flexShrink: 0, background: "var(--g-paper)" }}>
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 4, padding: 4,
            background: "var(--g-card-alt)", borderRadius: "var(--g-r-3)",
            border: "1px solid var(--g-rule-soft)",
          }}>
            {[
              { id: "email", label: "Email" },
              { id: "sms", label: "SMS" },
              { id: "signal", label: "Signal" },
            ].map(t => {
              const isActive = view === t.id;
              return (
                <button key={t.id} onClick={() => setView(t.id)} style={{
                  minHeight: 36, padding: "8px 4px",
                  background: isActive ? "var(--g-card)" : "transparent",
                  color: isActive ? "var(--g-ink)" : "var(--g-ink-3)",
                  border: isActive ? "1px solid var(--g-rule)" : "1px solid transparent",
                  borderRadius: "var(--g-r-2)", cursor: "pointer",
                  fontSize: 13, fontWeight: isActive ? 600 : 500,
                  boxShadow: isActive ? "var(--g-shadow-1)" : "none",
                }}>{t.label}</button>
              );
            })}
          </div>
        </div>

        {/* Preview content */}
        <div style={{ flex: 1, overflow: "auto", background: "var(--g-paper-deep)", padding: 12 }}>
          {view === "email" && <EmailMobilePreview stage={stage}/>}
          {view === "sms" && <SMSMobilePreview stage={stage}/>}
          {view === "signal" && <SignalMobilePreview stage={stage}/>}
        </div>

        {/* Footer */}
        <div style={{
          padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8, flexShrink: 0,
        }}>
          <MBtn variant="ghost" size="lg" style={{ flex: 1 }}>Metriken</MBtn>
          <MBtn variant="primary" size="lg" style={{ flex: 1.4 }} icon={<MIcon kind="send" size={16} color="var(--g-paper)"/>}>Test jetzt senden</MBtn>
        </div>
      </div>
    </PhoneFrame>
  );
}

function EmailMobilePreview({ stage }) {
  return (
    <div style={{
      background: "#fff", borderRadius: "var(--g-r-3)",
      border: "1px solid var(--g-rule)", overflow: "hidden",
      fontFamily: "Georgia, 'Times New Roman', serif",
    }}>
      {/* Mail-Header */}
      <div style={{ padding: "12px 14px", borderBottom: "1px solid var(--g-rule-soft)", background: "var(--g-card-alt)" }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>von Gregor Zwanzig</div>
        <div style={{ fontSize: 15, fontWeight: 700, color: "var(--g-ink)", lineHeight: 1.3, fontFamily: "var(--g-font-sans)" }}>
          KHW_00b · Birnlücke → Clarahütte
        </div>
        <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 4, fontFamily: "var(--g-font-sans)" }}>
          Do, 07. Mai · 06:00 · 11,8 km · ↑420 ↓1140
        </div>
      </div>

      {/* Body */}
      <div style={{ padding: "14px 14px 18px" }}>
        <div style={{ fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.6, marginBottom: 14 }}>
          Guten Morgen. Heute Birnlücke → Clarahütte. Gewitter-Wahrscheinlichkeit am Nachmittag <strong>45 %</strong> — früh starten, spätestens 13:00 an der Clarahütte. Wind moderat (15/30 SW).
        </div>

        {/* Mini-Profil */}
        <ElevSparkline data={stage.profile} width={290} height={50}/>

        <div style={{ marginTop: 14, paddingTop: 12, borderTop: "2px solid var(--g-ink)", fontFamily: "var(--g-font-sans)" }}>
          <div className="mono" style={{ fontSize: 9, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--g-ink-3)", marginBottom: 8 }}>Wegpunkte · 6:00 → 14:00</div>
          {stage.waypoints.map((wp, i) => (
            <div key={i} style={{ display: "flex", gap: 10, padding: "8px 0", borderBottom: i < stage.waypoints.length - 1 ? "1px solid var(--g-rule-soft)" : "none" }}>
              <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", width: 38, fontWeight: 600 }}>{wp.time}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 600 }}>{wp.name}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
                  {wp.elev} m · +6° · Wind 15 km/h · Gewitter 30 %
                </div>
              </div>
            </div>
          ))}
        </div>

        <div style={{ marginTop: 16, padding: 10, background: "rgba(168,50,50,0.06)", borderLeft: "3px solid var(--g-bad)", fontSize: 12, color: "var(--g-ink-2)", fontFamily: "var(--g-font-sans)" }}>
          <strong>Achtung:</strong> Gewitter-Aufzug ab 14:00. Rückzugsoption: Obstanserseehütte (1h von Clarahütte zurück).
        </div>
      </div>
    </div>
  );
}

function SMSMobilePreview({ stage }) {
  return (
    <div style={{ padding: "20px 8px" }}>
      <div style={{ textAlign: "center", marginBottom: 12 }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Heute · 06:00
        </div>
      </div>
      <div style={{
        maxWidth: 280, marginLeft: "auto",
        background: "var(--g-good)", color: "#fff",
        borderRadius: 18, borderBottomRightRadius: 4,
        padding: "10px 14px",
        fontSize: 14, lineHeight: 1.4,
        fontFamily: "-apple-system, var(--g-font-sans)",
        whiteSpace: "pre-wrap",
      }}>
{`KHW_00b · Birnlücke → Clarahütte
06:00 -1° wolkig
10:00 +4° Birnlücke (KI)
13:00 +6° Clarahütte
14:00 ⚡ Gewitter 45%
Wind 15/30 SW. Früh anschlagen.`}
      </div>
      <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", textAlign: "right", marginTop: 4, paddingRight: 6 }}>
        Zugestellt · 158 Zeichen
      </div>
    </div>
  );
}

function SignalMobilePreview({ stage }) {
  return (
    <div style={{ padding: "8px 0" }}>
      <div style={{ textAlign: "center", marginBottom: 12 }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.1em" }}>
          Gregor Zwanzig · 06:00
        </div>
      </div>
      <div style={{
        maxWidth: 290,
        background: "var(--g-card)", color: "var(--g-ink)",
        border: "1px solid var(--g-rule)",
        borderRadius: 14, borderBottomLeftRadius: 4,
        padding: "10px 14px",
        fontSize: 14, lineHeight: 1.5,
        fontFamily: "-apple-system, var(--g-font-sans)",
      }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>📍 KHW_00b</div>
        <div style={{ marginBottom: 8 }}>Birnlücke → Clarahütte · 11,8 km · ↑420 ↓1140</div>
        <div className="mono" style={{ fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.6, whiteSpace: "pre-wrap" }}>
{`06:00 ☁ -1° Birnlücke
10:00 ☁ +4° (KI)
13:00 ☀ +6° Clarahütte
14:00 ⚡ Gewitter 45%`}
        </div>
        <div style={{ marginTop: 10, padding: "6px 10px", background: "rgba(168,50,50,0.08)", borderLeft: "2px solid var(--g-bad)", fontSize: 12, color: "var(--g-bad)", fontWeight: 600 }}>
          Achtung: Gewitter ab 14:00 — vor 13:00 an der Hütte.
        </div>
      </div>
      <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", marginTop: 4, paddingLeft: 6 }}>
        Gelesen · Mit Anhang: Höhenprofil
      </div>
    </div>
  );
}

window.ScreenOutputPreviewMobile = ScreenOutputPreviewMobile;
