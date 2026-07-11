/* ════════════════════════════════════════════════════════════════════════
 *  Trip bearbeiten v2 — Shell + alle Tabs
 *  Prefix TE2_ — Babel-Scope-Disziplin.
 *  Export: ScreenTripEditV2
 *  Tabs: Übersicht · Etappen & Wegpunkte · Wetter-Metriken · Briefing-Zeitplan · Alerts
 * ════════════════════════════════════════════════════════════════════════ */

const TE2_TRIP = {
  name: "Karnischer Höhenweg 403",
  shortName: "KHW 403",
  region: "Karnische Alpen",
  dates: "03.06. – 14.06.2026",
  totalKm: 182,
  totalAscent: 9400,
  status: "active",
  stages: [
    { code: "KHW_01", label: "Sillian → Obstansersee-Hütte",           km: 14.2, ascent: 1420, descent: 540,  date: "03.06", risk: "low" },
    { code: "KHW_02", label: "Obstansersee → Filmoor-Standschützenhütte", km: 12.8, ascent: 820, descent: 980,  date: "04.06", risk: "med" },
    { code: "KHW_03", label: "Filmoor → Hochweißsteinhaus",              km: 10.9, ascent: 760, descent: 900,  date: "05.06", risk: "high" },
    { code: "KHW_04", label: "Hochweißsteinhaus → Wolayersee-Hütte",     km: 11.2, ascent: 680, descent: 820,  date: "06.06", risk: "low" },
    { code: "KHW_05", label: "Wolayersee → Plöckenhaus",                 km: 9.8,  ascent: 540, descent: 720,  date: "07.06", risk: "low" },
  ],
};

/* ─── Tab-Bar ─── */
function TE2_TabBar({ active, onChange, channels }) {
  const activeCh = Object.values(channels).filter(Boolean).length;
  const TABS = [
    { id: "uebersicht", label: "Übersicht" },
    { id: "etappen",    label: "Etappen & Wegpunkte", badge: String(TE2_TRIP.stages.length) },
    { id: "metriken",   label: "Wetter-Metriken" },
    { id: "alerts",     label: "Wertebereiche", badge: "6", accent: true },
    { id: "zeitplan",   label: "Briefing-Zeitplan", badge: activeCh > 0 ? String(activeCh) : "!" },
  ];
  return (
    <div style={{ position: "relative", borderBottom: "1px solid var(--g-rule)", padding: "0 40px", display: "flex", gap: 0, overflowX: "auto" }}>
      {TABS.map(t => {
        const on = t.id === active;
        return (
          <div key={t.id} onClick={() => onChange(t.id)} style={{
            padding: "12px 16px", cursor: "pointer", fontSize: 13, fontWeight: on ? 600 : 500,
            color: on ? "var(--g-ink)" : "var(--g-ink-3)",
            borderBottom: on ? "2px solid var(--g-accent)" : "2px solid transparent",
            marginBottom: -1, display: "flex", alignItems: "center", gap: 6, whiteSpace: "nowrap",
          }}>
            {t.label}
            {t.badge && (
              <span className="mono" style={{
                fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 3,
                background: t.accent ? "var(--g-accent)" : "var(--g-paper-deep)",
                color: t.accent ? "#fff" : activeCh === 0 && t.id === "zeitplan" ? "var(--g-warn)" : "var(--g-ink-3)",
              }}>{t.badge}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Übersicht-Tab ─── */
function TE2_UebersichtTab({ trip, channels, onTab }) {
  const activeCh = Object.entries(channels).filter(([,v]) => v).map(([k]) => k);
  const chGlyph = { email: "✉", telegram: "✈", sms: "✱" };
  return (
    <div style={{ position: "relative", padding: "28px 40px 60px", maxWidth: 1480, display: "grid", gridTemplateColumns: "1fr 340px", gap: 32 }}>
      <div>
        <SectionH eyebrow="Etappen" title={`${trip.stages.length} Etappen · ${trip.totalKm} km · ↑${trip.totalAscent} m`} right={<Btn variant="ghost" size="sm" onClick={() => onTab("etappen")}>Im Editor öffnen →</Btn>}/>
        <Card padding={0}>
          {trip.stages.map((s, i) => {
            const riskColor = s.risk === "high" ? "var(--g-bad)" : s.risk === "med" ? "var(--g-warn)" : "var(--g-good)";
            return (
              <div key={i} onClick={() => onTab("etappen")} style={{ display: "grid", gridTemplateColumns: "56px 1fr 80px", gap: 12, padding: "13px 18px", borderBottom: "1px solid var(--g-rule-soft)", cursor: "pointer", alignItems: "center" }}>
                <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{s.code}</span>
                <div>
                  <div style={{ fontSize: 13.5, fontWeight: 500 }}>{s.label}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 2 }}>{s.date} · {s.km} km · ↑{s.ascent} ↓{s.descent}</div>
                </div>
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <span style={{ display: "inline-block", width: 9, height: 9, borderRadius: "50%", background: riskColor }}/>
                </div>
              </div>
            );
          })}
        </Card>

        <div style={{ marginTop: 28 }}>
          <SectionH eyebrow="Wetter-Metriken" title={`${PRESETS.find(p => p.id === "alpine")?.metrics?.length ?? 0} Metriken aktiv`} right={<Btn variant="ghost" size="sm" onClick={() => onTab("metriken")}>Bearbeiten →</Btn>}/>
          <Card padding={16} style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {(PRESETS.find(p => p.id === "alpine")?.metrics || []).map(id => {
              const m = METRIC_BY_ID[id]; if (!m) return null;
              return <span key={id} className="mono" style={{ fontSize: 11, padding: "4px 8px", borderRadius: 3, background: "var(--g-ink)", color: "var(--g-paper)" }}>{m.short}</span>;
            })}
          </Card>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <Card padding={16}>
          <Eyebrow style={{ marginBottom: 10 }}>Briefings aktiv</Eyebrow>
          {activeCh.length === 0
            ? <div style={{ fontSize: 13, color: "var(--g-warn)" }}>Kein Kanal aktiv — <button onClick={() => onTab("metriken")} style={{ color: "var(--g-accent)", background: "none", border: "none", cursor: "pointer", fontSize: 13, padding: 0 }}>Wetter-Metriken öffnen →</button></div>
            : activeCh.map(k => (
              <div key={k} style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 0", borderBottom: "1px solid var(--g-rule-soft)" }}>
                <span className="mono" style={{ width: 20, textAlign: "center", color: "var(--g-ink-2)" }}>{chGlyph[k]}</span>
                <span style={{ fontSize: 13, fontWeight: 500, flex: 1 }}>{k.charAt(0).toUpperCase() + k.slice(1)}</span>
                <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--g-good)" }}/>
              </div>
            ))}
          <Btn variant="ghost" size="sm" style={{ marginTop: 10, width: "100%" }} onClick={() => onTab("zeitplan")}>Zeitplan bearbeiten →</Btn>
        </Card>

        <Card padding={16}>
          <Eyebrow style={{ marginBottom: 8 }}>Alerts</Eyebrow>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)" }}>2 aktive Regeln</div>
          <Btn variant="ghost" size="sm" style={{ marginTop: 10, width: "100%" }} onClick={() => onTab("alerts")}>Alle Alerts →</Btn>
        </Card>
      </div>
    </div>
  );
}

/* ─── Inline-Name-Input (analog TN_NameInput, eigener Prefix) ─── */
function TE2_NameInput({ value, onChange, placeholder }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <input type="text" value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder || "Etappenname …"}
      onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
      style={{
        width: "100%", boxSizing: "border-box",
        background: focus ? "var(--g-card)" : "transparent",
        border: focus ? "1.5px solid var(--g-accent)" : "1.5px solid transparent",
        borderRadius: "var(--g-r-1)",
        padding: focus ? "4px 8px" : "4px 2px",
        fontSize: 13.5, fontWeight: value ? 500 : 400,
        fontFamily: "var(--g-font-sans)",
        color: value ? "var(--g-ink)" : "var(--g-ink-4)",
        outline: "none",
        transition: "border-color 150ms, background 150ms, padding 100ms",
        cursor: focus ? "text" : "pointer",
      }}
    />
  );
}

/* ─── Etappen-Tab — zwei Unterbereiche: Etappen & GPX · Wegpunkte ─── */
function TE2_EtappenTab() {
  const [section, setSection] = React.useState("etappen");
  const [stages, setStages]   = React.useState(TE2_TRIP.stages.map(s => ({ ...s })));
  const setLabel = (code, label) => setStages(ss => ss.map(s => s.code === code ? { ...s, label } : s));

  return (
    <div>
      {/* Sub-Nav */}
      <div style={{ padding: "0 40px", borderBottom: "1px solid var(--g-rule)", display: "flex", gap: 0 }}>
        {[["etappen", "Etappen & GPX"], ["wegpunkte", "Wegpunkte"]].map(([id, label]) => (
          <div key={id} onClick={() => setSection(id)} style={{
            padding: "10px 16px", cursor: "pointer", fontSize: 13,
            fontWeight: section === id ? 600 : 500,
            color: section === id ? "var(--g-ink)" : "var(--g-ink-3)",
            borderBottom: section === id ? "2px solid var(--g-ink)" : "2px solid transparent",
            marginBottom: -1, whiteSpace: "nowrap",
          }}>{label}</div>
        ))}
      </div>

      {section === "etappen" && (
        <div style={{ position: "relative", padding: "28px 40px 60px", maxWidth: 900 }}>
          <TopoBg opacity={0.10}/>
          <div style={{ position: "relative" }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
              <div>
                <Eyebrow style={{ marginBottom: 2 }}>Etappen</Eyebrow>
                <h2 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", margin: 0 }}>
                  {stages.length} Etappen · {TE2_TRIP.totalKm} km · ↑{TE2_TRIP.totalAscent} m
                </h2>
              </div>
              <span className="mono" style={{ fontSize: 11, color: "var(--g-good)" }}>
                {stages.length} / {stages.length} GPX geladen
              </span>
            </div>

            {/* Spaltenheader */}
            <div style={{
              display: "grid",
              gridTemplateColumns: "72px 1fr 60px minmax(160px, 190px) 90px",
              gap: 10, padding: "0 14px 5px",
            }}>
              {["", "Etappenname", "Datum", "GPX-Datei", ""].map((h, i) => (
                <span key={i} className="mono" style={{
                  fontSize: 10, color: "var(--g-ink-4)",
                  letterSpacing: "0.06em", textTransform: "uppercase",
                }}>{h}</span>
              ))}
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 14 }}>
              {stages.map((s) => (
                <div key={s.code} style={{
                  display: "grid",
                  gridTemplateColumns: "72px 1fr 60px minmax(160px, 190px) 90px",
                  gap: 10, alignItems: "center", padding: "8px 14px",
                  background: "var(--g-card)",
                  border: "1px solid rgba(61,107,58,0.2)",
                  borderRadius: "var(--g-r-2)",
                }}>
                  <span className="mono" style={{
                    fontSize: 9.5, fontWeight: 700, textAlign: "center",
                    color: "var(--g-accent-deep)", background: "var(--g-accent-tint)",
                    padding: "2px 5px", borderRadius: 999,
                  }}>{s.code}</span>

                  <TE2_NameInput value={s.label} onChange={v => setLabel(s.code, v)}/>

                  <span className="mono" style={{
                    fontSize: 11, color: "var(--g-ink-3)", whiteSpace: "nowrap",
                  }}>{s.date}</span>

                  {/* GPX: bereits hochgeladen — zeigt Stats, Ersetzen-Option */}
                  <div style={{
                    display: "flex", alignItems: "center", gap: 7,
                    padding: "5px 10px", borderRadius: "var(--g-r-2)",
                    background: "rgba(61,107,58,0.08)",
                    border: "1px solid rgba(61,107,58,0.22)",
                  }}>
                    <span style={{
                      width: 16, height: 16, borderRadius: 3, flexShrink: 0,
                      background: "var(--g-good)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                    }}>
                      <svg width={9} height={9} viewBox="0 0 10 10" fill="none">
                        <polyline points="1.5,5.5 4,8 8.5,2" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
                      </svg>
                    </span>
                    <span className="mono" style={{
                      fontSize: 10, fontWeight: 600, color: "var(--g-ink-2)",
                      flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>{s.km} km · ↑{s.ascent} m</span>
                  </div>

                  <Btn variant="ghost" size="sm" style={{ fontSize: 11, padding: "4px 8px" }}>
                    GPX ersetzen
                  </Btn>
                </div>
              ))}
            </div>

            <div style={{ display: "flex", gap: 8 }}>
              <Btn variant="ghost" size="sm">+ Etappe hinzufügen</Btn>
              <Btn variant="ghost" size="sm">+ Pausentag</Btn>
            </div>
          </div>
        </div>
      )}

      {section === "wegpunkte" && (
        <div>
          <div style={{
            padding: "14px 40px", background: "var(--g-card)",
            borderBottom: "1px solid var(--g-rule-soft)",
            display: "flex", justifyContent: "space-between", alignItems: "center", gap: 24,
          }}>
            <div>
              <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 3 }}>Wegpunkte bearbeiten</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", lineHeight: 1.55 }}>
                Wegpunkte sind Wetterscheiden — umbenennen, verschieben oder ergänzen.
              </div>
            </div>
            <Btn variant="accent" size="sm">Änderungen übernehmen</Btn>
          </div>
          <ScreenWaypointEditor embedded={true}/>
        </div>
      )}
    </div>
  );
}

/* ─── Briefing-Zeitplan-Tab ─── */
function TE2_ZeitplanTab({ channels }) {
  const active = Object.entries(channels).filter(([,v]) => v).map(([k]) => k);
  const chLabel = { email: "Email", telegram: "Telegram", sms: "SMS" };
  const chGlyph = { email: "✉", telegram: "✈", sms: "✱" };
  const [cards, setCards] = React.useState([
    { id: "morning", title: "Morgen-Briefing", time: "06:00", sub: "Vor Etappenstart — alles für den Tag", ch: { email: true, telegram: true, sms: false }, on: true },
    { id: "evening", title: "Abend-Briefing",  time: "18:00", sub: "Ausblick auf morgen",                  ch: { email: true, telegram: false, sms: false }, on: true },
    { id: "alert",   title: "Alert-Trigger",   time: "bei Schwellwert", sub: "Sofort bei kritischer Änderung", ch: { email: false, telegram: true, sms: false }, on: true, accent: true },
    { id: "trend",   title: "Mehrtages-Trend", time: "So 18:00", sub: "3–7-Tage-Ausblick (optional)",     ch: { email: true, telegram: false, sms: false }, on: false },
  ]);
  const toggle = (id) => setCards(cs => cs.map(c => c.id === id ? { ...c, on: !c.on } : c));

  if (active.length === 0) {
    return (
      <div style={{ position: "relative", padding: "32px 40px 60px", maxWidth: 900 }}>
        <Eyebrow>Briefing-Zeitplan</Eyebrow>
        <div style={{ marginTop: 18, padding: "18px 20px", background: "rgba(192,138,26,0.07)", border: "1px solid var(--g-warn)", borderRadius: "var(--g-r-2)", fontSize: 14, color: "var(--g-ink-2)" }}>
          <strong style={{ color: "#8a6210" }}>Kein Kanal aktiv.</strong> Aktiviere zuerst mindestens einen Kanal im Tab <strong>Wetter-Metriken → Abschnitt 4</strong>, damit hier Zeitplan-Optionen erscheinen.
        </div>
      </div>
    );
  }

  return (
    <div style={{ position: "relative", padding: "28px 40px 60px", maxWidth: 1000 }}>
      <Eyebrow>Briefing-Zeitplan</Eyebrow>
      <h2 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.01em", margin: "6px 0 8px" }}>Wann geht was raus?</h2>
      <div style={{ padding: "9px 14px", background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", fontSize: 12.5, color: "var(--g-ink-2)", marginBottom: 22, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--g-info)", flexShrink: 0 }}/>
        Nur Kanäle, die du in <strong>Wetter-Metriken</strong> aktiviert hast, stehen hier zur Auswahl:
        {active.map(k => <span key={k} style={{ marginLeft: 6, fontSize: 12, fontWeight: 500, padding: "2px 8px", borderRadius: 3, background: "var(--g-ink)", color: "var(--g-paper)" }}>{chLabel[k]}</span>)}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        {cards.map(c => (
          <Card key={c.id} padding={18} style={{ borderLeft: c.accent && c.on ? "3px solid var(--g-accent)" : undefined }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
              <div>
                <div style={{ fontSize: 15, fontWeight: 600 }}>{c.title}</div>
                <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 2 }}>{c.sub}</div>
              </div>
              <Switch checked={c.on} onChange={() => toggle(c.id)} tone={c.accent ? "accent" : "good"}/>
            </div>
            <div style={{ marginTop: 14, paddingTop: 12, borderTop: "1px solid var(--g-rule-soft)", display: "flex", alignItems: "center", gap: 10 }}>
              <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: c.on ? "var(--g-ink)" : "var(--g-ink-4)" }}>{c.time}</span>
              <span style={{ flex: 1 }}/>
              <div style={{ display: "flex", gap: 5 }}>
                {active.map(k => (
                  <span key={k} style={{ fontSize: 12, fontWeight: 500, padding: "4px 10px", borderRadius: 4, cursor: "pointer", border: `1px solid ${c.ch[k] ? "var(--g-ink)" : "var(--g-rule)"}`, background: c.ch[k] ? "var(--g-ink)" : "var(--g-paper-deep)", color: c.ch[k] ? "var(--g-paper)" : "var(--g-ink-4)" }} onClick={() => setCards(cs => cs.map(x => x.id === c.id ? { ...x, ch: { ...x.ch, [k]: !x.ch[k] } } : x))}>{chLabel[k]}</span>
                ))}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

/* ─── Alerts-Tab · #687 / #846 ───
 * Preset-Modell (issue_846, approved): kein Zahlen-Input pro Metrik mehr.
 * Empfindlichkeit per Dropdown + Info-Tabelle (13 Metriken × 3 Presets).
 * Plus Cooldown, Stille Stunden, Beispiel-Alert-Vorschau. Kein Signal, kein Severity.
 */
const TE2_ALERT_PRESETS = [
  { id: "off",       name: "Deaktiviert", short: "Kein Alert-Versand" },
  { id: "relaxed",   name: "Entspannt",   short: "Lockere Schwellen — nur bei deutlichen Änderungen" },
  { id: "standard",  name: "Standard",    short: "Empfehlung für die meisten Touren", recommended: true },
  { id: "sensitive", name: "Sensibel",    short: "Enge Schwellen — früheste Warnung" },
];

const TE2_ALERT_PRESET_TABLE = [
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

function TE2_alertCell(r, col) {
  const v = r[col];
  if (r.cmp === "delta") return "Δ ≥ " + v;
  return (r.cmp === "über" ? "> " : "< ") + v;
}

/* Beispiel-Alert: Abweichungs-Alert (Forecast) — Metrik · vorher · nachher · Etappe */
const TE2_ALERT_SAMPLE = [
  { metric: "Gewitter",   from: "15 %",    to: "60 %",    stage: "Etappe 3 · 14–18 Uhr" },
  { metric: "Böen",       from: "45 km/h", to: "72 km/h", stage: "Etappe 3 · 14–16 Uhr" },
  { metric: "Sichtweite", from: "15 km",   to: "6 km",    stage: "Etappe 3 · 14–18 Uhr" },
];

const TE2_SENS_LEVELS = [
  { id: "off",       label: "Aus" },
  { id: "relaxed",   label: "Entspannt" },
  { id: "standard",  label: "Standard" },
  { id: "sensitive", label: "Sensibel" },
];

function TE2_SensSeg({ value, onChange }) {
  return (
    <div style={{ display: "inline-flex", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)", overflow: "hidden", background: "var(--g-card)" }}>
      {TE2_SENS_LEVELS.map((lv, i) => {
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

function TE2_MetricSensRow({ r, level, onLevel, isLast }) {
  const off = level === "off";
  return (
    <div style={{ display: "grid", gridTemplateColumns: "190px 1fr 116px", alignItems: "center", padding: "10px 20px", borderBottom: isLast ? "none" : "1px solid var(--g-rule-soft)", background: off ? "transparent" : "rgba(196,90,42,0.025)", opacity: off ? 0.6 : 1, transition: "opacity 120ms, background 120ms" }}>
      <div style={{ fontSize: 13.5, fontWeight: off ? 400 : 600, color: "var(--g-ink)" }}>
        {r.label} <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{r.unit}</span>
      </div>
      <div><TE2_SensSeg value={level} onChange={onLevel}/></div>
      <div className="mono" style={{ fontSize: 12.5, textAlign: "right", color: off ? "var(--g-ink-4)" : "var(--g-accent-deep)", fontWeight: off ? 400 : 600 }}>
        {off ? "kein Alert" : TE2_alertCell(r, level)}
      </div>
    </div>
  );
}

function TE2_AlertSamplePreview() {
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
          {TE2_ALERT_SAMPLE.map(r => (
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

/* ─── Wertebereiche-Tab (Phase 4: rein Korridor-Editor) ───
 * Die gesamte notify-Zustellung (Alert-Kanäle · Cooldown · Stille Stunden ·
 * Beispiel-Warnung) wanderte in den Versand-Tab (VersandTab context="route").
 * EIN Ort für alles, was rausgeht — dieser Tab ist jetzt nur der Korridor-Editor. */
function TE2_AlertsTab() {
  return <CorridorEditor context="route"/>;
}

/* ════════════════════ MAIN: ScreenTripEditV2 ════════════════════ */
function ScreenTripEditV2({ initialTab = "metriken" } = {}) {
  const [tab, setTab] = React.useState(initialTab);
  const [channels, setChannels] = React.useState({ email: true, telegram: true, sms: false });
  const [dirty, setDirty] = React.useState(false);
  const trip = TE2_TRIP;

  const handleChannels = (c) => { setChannels(c); setDirty(true); };

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }} data-screen-label="Trip bearbeiten v2 (Desktop)">
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative", overflowY: "auto", overflowX: "hidden" }}>
        <TopoBg opacity={0.12}/>

        {/* Breadcrumb + Aktionen */}
        <div style={{ position: "relative", padding: "14px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.06em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            <span style={{ opacity: 0.6 }}>Trips</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>{trip.shortName}</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {dirty && <Pill tone="warn">Ungespeichert</Pill>}
            <Btn variant="ghost" size="sm" onClick={() => setDirty(false)}>Verwerfen</Btn>
            <Btn variant="primary" size="sm" onClick={() => setDirty(false)}>Speichern</Btn>
          </div>
        </div>

        {/* Hero */}
        <div style={{ position: "relative", padding: "20px 40px 14px" }}>
          <Eyebrow>{trip.region} · {trip.dates}</Eyebrow>
          <h1 style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.02em", margin: "4px 0 0", lineHeight: 1.1 }}>{trip.name}</h1>
        </div>

        {/* Tabs */}
        <TE2_TabBar active={tab} onChange={setTab} channels={channels}/>

        {/* Tab-Inhalt */}
        {tab === "uebersicht" && <TE2_UebersichtTab trip={trip} channels={channels} onTab={setTab}/>}
        {tab === "etappen"    && <TE2_EtappenTab/>}
        {tab === "metriken"   && <WetterMetrikenTabV2/>}
        {tab === "zeitplan"   && <VersandTab context="route" channels={channels} onChannels={handleChannels} onOpenStages={() => setTab("etappen")}/>}
        {tab === "alerts"     && <TE2_AlertsTab/>}
      </main>
    </div>
  );
}

Object.assign(window, { ScreenTripEditV2, TE2_ZeitplanTab, TE2_AlertsTab });
