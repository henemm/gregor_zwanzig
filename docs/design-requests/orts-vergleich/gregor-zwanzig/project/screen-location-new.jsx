/* Screen: Location anlegen — Smart Import (Komoot/Google Maps URL/DMS-Coords)
 * Modal-Style auf abgedunkeltem Compare-Hintergrund.
 */

function ScreenLocationNew() {
  return (
    <div style={{ position: "relative", minHeight: "100%", background: "var(--g-paper)" }}>
      {/* Hintergrund (Compare-Übersicht) als Kontext */}
      <div style={{ position: "absolute", inset: 0, opacity: 0.35, pointerEvents: "none", filter: "blur(2px)" }}>
        <ScreenCompareList/>
      </div>
      <div style={{ position: "absolute", inset: 0, background: "rgba(26,26,24,0.45)" }}/>

      {/* Modal */}
      <div style={{
        position: "absolute", top: 60, left: "50%", transform: "translateX(-50%)",
        width: 720, background: "var(--g-card)",
        border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-4)",
        boxShadow: "var(--g-shadow-3)", overflow: "hidden",
      }}>
        {/* Header */}
        <div style={{ padding: "20px 28px 16px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
          <div>
            <Eyebrow>Modul 1 · Location anlegen</Eyebrow>
            <div style={{ fontSize: 22, fontWeight: 600, marginTop: 4, letterSpacing: "-0.01em" }}>Neuer Ort</div>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginTop: 4 }}>
              Importiere aus Komoot, Google Maps, oder gib Koordinaten direkt ein.
            </div>
          </div>
          <button style={{ background: "transparent", border: "none", fontSize: 20, color: "var(--g-ink-4)", cursor: "pointer", padding: 4 }}>×</button>
        </div>

        {/* Step 1: Smart Input */}
        <div style={{ padding: "20px 28px 8px" }}>
          <LocSectionTag n="1" label="Verortung · Smart-Import"/>
          <div style={{ marginTop: 12 }}>
            <div style={{
              display: "flex", alignItems: "center", gap: 10, padding: "12px 14px",
              background: "var(--g-card-alt)", border: "1.5px solid var(--g-accent)",
              borderRadius: "var(--g-r-3)",
            }}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--g-accent)" strokeWidth="2"><path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.5 1.5"/><path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.5-1.5"/></svg>
              <span className="mono" style={{ fontSize: 13, color: "var(--g-ink)", flex: 1 }}>
                https://www.komoot.com/de-de/highlight/2049832
              </span>
              <Pill tone="good">erkannt · Komoot</Pill>
            </div>

            <div style={{ display: "flex", gap: 8, marginTop: 10, flexWrap: "wrap" }}>
              <LocFormatChip kind="komoot"     label="Komoot-URL"          example="komoot.com/highlight/…"/>
              <LocFormatChip kind="gmaps"      label="Google Maps"         example="goo.gl/maps/… · maps.app.goo.gl/…"/>
              <LocFormatChip kind="dms"        label="DMS-Koordinaten"     example="47°04'44.0&quot;N 11°41'08.2&quot;E"/>
              <LocFormatChip kind="dec"        label="Dezimal"             example="47.0789, 11.6856"/>
              <LocFormatChip kind="utm"        label="UTM"                 example="33T 296000 5215000"/>
              <LocFormatChip kind="paste-gpx"  label="GPX-Wegpunkt"        example=".gpx · einzelner Trkpt"/>
            </div>
          </div>
        </div>

        {/* Auflösung Preview */}
        <div style={{ padding: "8px 28px 16px", display: "grid", gridTemplateColumns: "1fr 280px", gap: 16, alignItems: "stretch" }}>
          <Card padding={0} style={{ background: "var(--g-card-alt)" }}>
            <div style={{ padding: "12px 16px 8px", borderBottom: "1px solid var(--g-rule-soft)" }}>
              <Eyebrow>Erkannt · Vorschau</Eyebrow>
            </div>
            <div style={{ padding: "10px 16px 14px" }}>
              <KV label="Quelle"      value="Komoot · Highlight #2049832" mono={false}/>
              <KV label="Koordinaten" value="47.07890°N · 11.68560°E"/>
              <KV label="Höhe (DEM)"  value="3.250 m ü.M."/>
              <KV label="Zeitzone"    value="Europe/Vienna · UTC+2"/>
              <KV label="Daten-Quelle" value="ICON-D2 · 2km Grid"/>
              <KV label="Land/Region" value="Tirol · Tuxer Alpen" mono={false}/>
            </div>
          </Card>

          {/* Mini-Map */}
          <div style={{
            position: "relative", borderRadius: "var(--g-r-3)", overflow: "hidden",
            border: "1px solid var(--g-rule)", background: "linear-gradient(135deg, #d8e0d3, #c8d6cd)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <TopoBg opacity={0.5} color="#3a4a3a" lines={28}/>
            <div style={{ position: "absolute", inset: 0, background: "linear-gradient(180deg, transparent 60%, rgba(20,30,20,0.15))" }}/>
            <div style={{
              position: "relative", width: 28, height: 28, borderRadius: "50%",
              background: "var(--g-accent)", border: "3px solid #fff",
              boxShadow: "0 4px 10px rgba(0,0,0,0.25)",
            }}/>
            <div style={{
              position: "absolute", bottom: 8, left: 10,
              fontFamily: "var(--g-font-mono)", fontSize: 9, color: "rgba(20,30,20,0.6)",
              letterSpacing: "0.06em",
            }}>HINTERTUX · 47.078, 11.685</div>
          </div>
        </div>

        {/* Step 2: Naming */}
        <div style={{ padding: "12px 28px" }}>
          <LocSectionTag n="2" label="Benennung"/>
          <div style={{ marginTop: 10, display: "grid", gridTemplateColumns: "2fr 1fr", gap: 12 }}>
            <LocPseudoInput label="Eindeutiger Name (für deine Übersicht)" value="Hintertuxer Gletscher" focus/>
            <LocPseudoInput label="Gruppe (optional)" value="Zillertal" hint="Tippen für neue Gruppe"/>
          </div>
        </div>

        {/* Step 3: Focus */}
        <div style={{ padding: "12px 28px" }}>
          <LocSectionTag n="3" label="Meteorologische Brille (Aktivitätsprofil)"/>
          <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 4, marginBottom: 10 }}>
            Welche Metriken sind für genau diese Koordinaten standardmäßig relevant?
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            {LOCATION_ACTIVITY_PROFILES.map((p, i) => (
              <LocProfileCard key={p.id} profile={p} active={i === 1}/>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div style={{
          padding: "16px 28px 18px", marginTop: 8,
          background: "var(--g-card-alt)", borderTop: "1px solid var(--g-rule-soft)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>
            ☐ Nach Speichern als Compare-Kandidat vormerken
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost" size="sm">Abbrechen</Btn>
            <Btn variant="primary" size="md">Ort speichern · 16 → 17</Btn>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ───────────── Helpers ───────────── */
function LocSectionTag({ n, label }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <span style={{
        width: 22, height: 22, background: "var(--g-ink)", color: "var(--g-paper)",
        borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontFamily: "var(--g-font-mono)", fontSize: 11, fontWeight: 600,
      }}>{n}</span>
      <span style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)", letterSpacing: "-0.005em" }}>{label}</span>
    </div>
  );
}

function LocFormatChip({ kind, label, example }) {
  return (
    <div title={example} style={{
      padding: "6px 10px", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
      fontSize: 11, color: "var(--g-ink-3)", background: "var(--g-card-alt)",
      display: "inline-flex", alignItems: "center", gap: 6,
    }}>
      <span style={{ fontFamily: "var(--g-font-mono)", fontWeight: 600, color: "var(--g-ink-2)" }}>{label}</span>
      <span style={{ color: "var(--g-ink-4)" }}>·</span>
      <span style={{ fontFamily: "var(--g-font-mono)", color: "var(--g-ink-4)" }}>{example}</span>
    </div>
  );
}

function LocPseudoInput({ label, value, hint, focus }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 10, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.08em", textTransform: "uppercase" }}>{label}</span>
      <div style={{
        padding: "10px 12px", border: `1.5px solid ${focus ? "var(--g-accent)" : "var(--g-rule)"}`,
        background: "var(--g-card)", borderRadius: "var(--g-r-2)",
        fontSize: 14, color: "var(--g-ink)", fontWeight: 500,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span>{value}{focus && <span style={{ display: "inline-block", width: 1.5, height: 14, background: "var(--g-accent)", marginLeft: 2, verticalAlign: "middle" }}/>}</span>
        {hint && <span style={{ fontSize: 10, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)" }}>{hint}</span>}
      </div>
    </div>
  );
}

function LocProfileCard({ profile, active }) {
  return (
    <div style={{
      padding: "12px 14px",
      border: `1.5px solid ${active ? "var(--g-accent)" : "var(--g-rule-soft)"}`,
      background: active ? "var(--g-accent-tint)" : "var(--g-card-alt)",
      borderRadius: "var(--g-r-3)", cursor: "pointer",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Pill tone="accent">{profile.label.split(" ")[0]}</Pill>
        <span style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)" }}>{profile.label}</span>
      </div>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", lineHeight: 1.5 }}>
        {profile.metrics.join(" · ")}
      </div>
    </div>
  );
}

window.ScreenLocationNew = ScreenLocationNew;
