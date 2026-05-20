/* Mobile · POI anlegen (Location New) — Smart-Import-Flow
 * Pattern: Vollbild-Modal-Flow (kein Bottom-Nav). Step-Indikator wie Wizard.
 * Steps: 1) Quelle wählen   2) URL / Suche eingeben   3) Vorschlag prüfen  4) speichern
 */

function ScreenLocationNewMobile() {
  const [step, setStep] = React.useState(2);

  const title = {
    1: "Quelle wählen",
    2: "Ort importieren",
    3: "Vorschlag prüfen",
  }[step];

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title={title}
          eyebrow={`Neuer Ort · ${step}/3`}
          leftIcon={step === 1 ? "close" : "back"}
          right={<button style={{ padding: "0 12px", minHeight: 44, background: "transparent", border: "none", fontSize: 14, color: "var(--g-ink-3)" }}>Abbrechen</button>}
          onMenu={() => step > 1 && setStep(step - 1)}
        />

        <div style={{ display: "flex", gap: 4, padding: "8px 16px 12px", borderBottom: "1px solid var(--g-rule-soft)", flexShrink: 0 }}>
          {[1,2,3].map(n => (
            <div key={n} style={{ flex: 1, height: 3, borderRadius: 2, background: n <= step ? "var(--g-accent)" : "var(--g-rule)" }}/>
          ))}
        </div>

        <ScreenScroll padding={16}>
          {step === 1 && <LocSource onPick={() => setStep(2)}/>}
          {step === 2 && <LocImport onParsed={() => setStep(3)}/>}
          {step === 3 && <LocPreview/>}
        </ScreenScroll>

        <div style={{
          flexShrink: 0, padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8,
        }}>
          {step > 1 && <MBtn variant="ghost" size="lg" onClick={() => setStep(step - 1)} style={{ flex: 1 }}>← Zurück</MBtn>}
          {step < 3 ? (
            <MBtn variant="primary" size="lg" onClick={() => setStep(step + 1)} style={{ flex: 1.6 }}>Weiter →</MBtn>
          ) : (
            <MBtn variant="accent" size="lg" style={{ flex: 1.6 }}>Ort speichern</MBtn>
          )}
        </div>
      </div>
    </PhoneFrame>
  );
}

function LocSource({ onPick }) {
  const sources = [
    { id: "url", icon: "external", label: "URL einfügen", sub: "Komoot, Outdooractive, Google-Maps, Bergfex" },
    { id: "search", icon: "search", label: "Ort suchen", sub: "Volltextsuche nach Berg, Hütte, Skigebiet" },
    { id: "map", icon: "map", label: "Auf Karte tippen", sub: "Beliebigen Punkt setzen" },
    { id: "gpx", icon: "plus", label: "Aus GPX", sub: "Start- oder Endpunkt aus Tracks" },
  ];
  return (
    <>
      <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 4 }}>
        Woher kommt der Ort?
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 18 }}>
        Smart-Import erkennt Name, Höhe und Koordinaten automatisch — du musst keine Lat/Lon eintippen.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {sources.map(s => (
          <button key={s.id} onClick={onPick} style={{
            display: "flex", alignItems: "center", gap: 14, padding: "16px 14px",
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", cursor: "pointer", minHeight: 64,
            textAlign: "left",
          }}>
            <span style={{
              width: 40, height: 40, borderRadius: "var(--g-r-3)",
              background: "var(--g-paper-deep)",
              display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
            }}>
              <MIcon kind={s.icon} size={20} color="var(--g-ink)"/>
            </span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 15, fontWeight: 600 }}>{s.label}</div>
              <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2 }}>{s.sub}</div>
            </div>
            <MIcon kind="chevron" size={18} color="var(--g-ink-3)"/>
          </button>
        ))}
      </div>
    </>
  );
}

function LocImport({ onParsed }) {
  return (
    <>
      <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 4 }}>
        URL einfügen
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 18 }}>
        Komoot, Outdooractive, Google-Maps, Bergfex, Skigebiete.de — wir erkennen den Ort.
      </div>

      <MField label="URL oder Adresse">
        <MInput defaultValue="komoot.com/smarttour/15...…" leftIcon="external"/>
      </MField>

      {/* Parsed Preview */}
      <Card padding={14} style={{ background: "var(--g-card-alt)", marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
          <Dot tone="good"/>
          <span className="mono" style={{ fontSize: 11, color: "var(--g-good)", textTransform: "uppercase", letterSpacing: "0.1em", fontWeight: 600 }}>erkannt · komoot</span>
        </div>
        <div style={{ fontSize: 16, fontWeight: 600, marginBottom: 2 }}>Hintertuxer Gletscher</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", lineHeight: 1.5 }}>
          47.0789°N · 11.6856°E<br/>
          3250 m · Skigebiet · Zillertal, AT
        </div>
      </Card>

      <button onClick={onParsed} style={{
        marginTop: 14, padding: "10px 14px", minHeight: 44, width: "100%",
        background: "transparent", border: "1px dashed var(--g-rule)",
        borderRadius: "var(--g-r-3)", cursor: "pointer",
        fontSize: 13, color: "var(--g-ink-3)",
      }}>Andere Quelle versuchen</button>
    </>
  );
}

function LocPreview() {
  return (
    <>
      <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em", marginBottom: 4 }}>
        Vorschlag prüfen
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 18 }}>
        Pass den Namen an oder weise Gruppe und Aktivitäts-Fokus zu, damit der Vergleich passt.
      </div>

      {/* Karten-Placeholder */}
      <div style={{
        position: "relative", height: 160, borderRadius: "var(--g-r-3)",
        background: "linear-gradient(180deg, #d4dcc5 0%, #e8e6d0 100%)",
        marginBottom: 14, overflow: "hidden", border: "1px solid var(--g-rule)",
      }}>
        <svg viewBox="0 0 343 160" width="100%" height="100%" style={{ position: "absolute", inset: 0 }}>
          <path d="M0 110 Q50 80 100 95 T200 75 T343 90" stroke="rgba(26,26,24,0.15)" strokeWidth="1" fill="none"/>
          <path d="M0 130 Q60 100 120 115 T250 95 T343 110" stroke="rgba(26,26,24,0.1)" strokeWidth="1" fill="none"/>
        </svg>
        <div style={{
          position: "absolute", top: "50%", left: "50%", transform: "translate(-50%, -50%)",
          width: 16, height: 16, borderRadius: "50%", background: "var(--g-accent)",
          border: "3px solid #fff", boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
        }}/>
        <div className="mono" style={{
          position: "absolute", bottom: 8, left: 8, fontSize: 9, color: "var(--g-ink-3)",
          background: "rgba(255,255,255,0.85)", padding: "2px 6px", borderRadius: 3,
        }}>47.0789°N · 11.6856°E</div>
      </div>

      <MField label="Name">
        <MInput defaultValue="Hintertuxer Gletscher"/>
      </MField>
      <MField label="Höhe (m)">
        <MInput defaultValue="3250"/>
      </MField>
      <MField label="Gruppe">
        <MInput defaultValue="Zillertal"/>
      </MField>
      <MField label="Aktivitäts-Fokus">
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {[
            { id: "wintersport-glacier", label: "Gletscher", active: true },
            { id: "wintersport", label: "Wintersport" },
            { id: "alpine-touring", label: "Skitour" },
            { id: "hiking", label: "Wandern" },
            { id: "trail-running", label: "Trail" },
          ].map(c => (
            <span key={c.id} style={{
              padding: "8px 12px", minHeight: 36, borderRadius: "var(--g-r-pill)",
              background: c.active ? "var(--g-ink)" : "var(--g-card)",
              color: c.active ? "var(--g-paper)" : "var(--g-ink-2)",
              border: `1px solid ${c.active ? "var(--g-ink)" : "var(--g-rule)"}`,
              fontSize: 12, fontFamily: "var(--g-font-mono)", fontWeight: 500,
            }}>{c.label}</span>
          ))}
        </div>
      </MField>
    </>
  );
}

window.ScreenLocationNewMobile = ScreenLocationNewMobile;
