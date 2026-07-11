/* ════════════════════════════════════════════════════════════════════════
 *  Trip bearbeiten v2 — Mobile Screen
 *  Prefix TM2_ — Babel-Scope-Disziplin.
 *  Export: ScreenTripEditV2Mobile
 *  Nutzt: PhoneFrame, TopAppBar, MTab, ScreenScroll, Sheet, MSwitch,
 *         MBtn aus mobile-shell.jsx + WM2_* aus screen-trip-edit-v2-weather.jsx
 * ════════════════════════════════════════════════════════════════════════ */

/* ─── Hilfsfunktionen ─── */
function TM2_Arrow({ dir, disabled, onClick }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      width: 36, height: 36, border: "1px solid var(--g-rule)", borderRadius: 4,
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.3 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0, flexShrink: 0,
    }}>
      <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">
        {dir === "up" ? <path d="M6 2.5L10 8H2Z"/> : <path d="M6 9.5L2 4H10Z"/>}
      </svg>
    </button>
  );
}

/* ─── Wetter-Metriken Tab (Mobile) ───
 * Phase 4: Auswahl (Preset + Grundauswahl) bleibt hier; Reihenfolge + Kappung
 * + Live-Vorschau kommen aus <LayoutTab context="route" dense noScroll>.
 * Kanäle an/aus wanderten in den Versand-Tab (VersandTab). */
function TM2_WetterTab() {
  const [state, setState] = React.useState(() => WM2_buildState("alpine"));
  const [highlight, setHl] = React.useState(null);

  const flash = (id, kind) => { setHl({ id, kind }); setTimeout(() => setHl(null), 2500); };

  const toggle = (id, wasOn) => {
    setState(s => {
      const n = { ...s, primary: [...s.primary], off: [...s.off], dirty: true };
      if (wasOn) { n.primary = n.primary.filter(x => x !== id); n.off = [...n.off, id]; }
      else { n.off = n.off.filter(x => x !== id); n.primary = [...n.primary, id]; }
      return n;
    });
    flash(id, wasOn ? "removed" : "added");
  };



  const reorder = (bucket, id, dir) => {
    setState(s => {
      const list = [...s[bucket]]; const i = list.indexOf(id); const ni = i + dir;
      if (ni < 0 || ni >= list.length) return s;
      [list[i], list[ni]] = [list[ni], list[i]];
      return { ...s, [bucket]: list, dirty: true };
    });
    flash(id, "moved");
  };

  const loadPreset = (pid) => { setState(WM2_buildState(pid)); flash(null, null); };
  const active = new Set(state.primary);

  return (
    <React.Fragment>
      <ScreenScroll padding={14} style={{ paddingBottom: 24 }}>

        {/* 01 Profil */}
        <div style={{ marginBottom: 16 }}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>01 — Profil</div>
          <div style={{ display: "flex", gap: 8, overflowX: "auto", paddingBottom: 4 }}>
            {PRESETS.map(p => {
              const on = p.id === state.presetId && !state.dirty;
              return (
                <button key={p.id} onClick={() => loadPreset(p.id)} style={{
                  flexShrink: 0, padding: "8px 14px", borderRadius: "var(--g-r-pill)", cursor: "pointer",
                  border: `1px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`,
                  background: on ? "var(--g-accent-tint)" : "var(--g-card)",
                  color: on ? "var(--g-accent-deep)" : "var(--g-ink-2)", fontSize: 13, fontWeight: on ? 600 : 500,
                }}>{p.name}</button>
              );
            })}
          </div>
        </div>

        {/* 02 Grundauswahl */}
        <div style={{ marginBottom: 16 }}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
            02 — Grundauswahl <span style={{ color: "var(--g-ink-2)", textTransform: "none", fontFamily: "var(--g-font-sans)", letterSpacing: 0 }}>{active.size} aktiv</span>
          </div>
          <Card padding={14}>
            {CATEGORY_ORDER.map(cat => (
              <div key={cat} style={{ marginBottom: 12 }}>
                <div style={{ fontSize: 11, color: "var(--g-ink-3)", fontWeight: 600, marginBottom: 7 }}>{CATEGORY_LABELS[cat]}</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                  {(METRICS_BY_CATEGORY[cat] || []).map(m => {
                    const on = active.has(m.id);
                    const hl = highlight && highlight.id === m.id;
                    return (
                      <button key={m.id} onClick={() => toggle(m.id, on)} style={{
                        padding: "7px 12px", borderRadius: 4, cursor: "pointer", fontSize: 13, fontWeight: 500,
                        border: `1px solid ${on ? "var(--g-ink)" : "var(--g-rule)"}`,
                        background: hl ? "var(--g-accent-tint)" : on ? "var(--g-ink)" : "var(--g-card)",
                        color: on ? "var(--g-paper)" : "var(--g-ink-3)",
                        outline: hl ? "2px solid var(--g-accent)" : "none", outlineOffset: 2,
                        minHeight: 44,
                      }}>
                        {on && <span style={{ fontSize: 10, marginRight: 4, opacity: 0.7 }}>✓</span>}
                        {m.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </Card>
        </div>

        {/* 03 Reihenfolge + Kanal-Kappung + Live-Vorschau — geteilter Organism */}
        <LayoutTab context="route" dense noScroll state={state}
          onReorder={(id, dir) => reorder("primary", id, dir)} highlight={highlight}/>

      </ScreenScroll>
    </React.Fragment>
  );
}

/* ─── Zeitplan Tab (Mobile) ─── */
function TM2_ZeitplanTab({ channels }) {
  const active = Object.entries(channels).filter(([,v]) => v).map(([k]) => k);
  const chLabel = { email: "Email", telegram: "Telegram", sms: "SMS" };
  const [cards, setCards] = React.useState([
    { id: "morning", title: "Morgen-Briefing", time: "06:00",       on: true,  ch: { email: true, telegram: true, sms: false } },
    { id: "evening", title: "Abend-Briefing",  time: "18:00",       on: true,  ch: { email: true, telegram: false, sms: false } },
    { id: "alert",   title: "Alert-Trigger",   time: "bei Schwellwert", on: true, accent: true, ch: { email: false, telegram: true, sms: false } },
    { id: "trend",   title: "Mehrtages-Trend", time: "So 18:00",    on: false, ch: { email: true, telegram: false, sms: false } },
  ]);
  if (active.length === 0) {
    return (
      <ScreenScroll padding={16}>
        <div style={{ padding: "18px 16px", background: "rgba(192,138,26,0.07)", border: "1px solid var(--g-warn)", borderRadius: "var(--g-r-2)", fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
          <strong style={{ color: "#8a6210" }}>Kein Kanal aktiv.</strong> Aktiviere zuerst einen Kanal in <strong>Abschnitt 04 — Kanäle</strong>.
        </div>
      </ScreenScroll>
    );
  }
  return (
    <ScreenScroll padding={14}>
      <div style={{ padding: "10px 12px", background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", fontSize: 12.5, color: "var(--g-ink-2)", marginBottom: 14 }}>
        Aktive Kanäle aus Wetter-Metriken:{active.map(k => <strong key={k} style={{ marginLeft: 6, color: "var(--g-ink)" }}>{chLabel[k]}</strong>)}
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {cards.map(c => (
          <Card key={c.id} padding={14} style={{ borderLeft: c.accent && c.on ? "3px solid var(--g-accent)" : undefined }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{c.title}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 1 }}>{c.time}</div>
              </div>
              <MSwitch checked={c.on} onChange={() => setCards(cs => cs.map(x => x.id === c.id ? { ...x, on: !x.on } : x))}/>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              {active.map(k => (
                <button key={k} onClick={() => setCards(cs => cs.map(x => x.id === c.id ? { ...x, ch: { ...x.ch, [k]: !x.ch[k] } } : x))} style={{
                  padding: "6px 12px", fontSize: 13, fontWeight: 500, borderRadius: 4, cursor: "pointer", minHeight: 36,
                  background: c.ch[k] ? "var(--g-ink)" : "var(--g-paper-deep)",
                  color: c.ch[k] ? "var(--g-paper)" : "var(--g-ink-4)",
                  border: `1px solid ${c.ch[k] ? "var(--g-ink)" : "var(--g-rule)"}`,
                }}>{chLabel[k]}</button>
              ))}
            </div>
          </Card>
        ))}
      </div>
    </ScreenScroll>
  );
}

/* ─── Alerts Tab (Mobile) · #687 / #846 ───
 * Preset-Modell (issue_846, approved): Empfindlichkeit-Dropdown + Info-Tabelle,
 * Cooldown, Stille Stunden, Beispiel-Alert. Kein Zahlen-Input pro Metrik,
 * kein Signal, kein Severity.
 */
const TM2_ALERT_PRESETS = [
  { id: "off",       name: "Deaktiviert", short: "Kein Alert-Versand" },
  { id: "relaxed",   name: "Entspannt",   short: "Lockere Schwellen — nur bei deutlichen Änderungen" },
  { id: "standard",  name: "Standard",    short: "Empfehlung für die meisten Touren", recommended: true },
  { id: "sensitive", name: "Sensibel",    short: "Enge Schwellen — früheste Warnung" },
];

const TM2_ALERT_PRESET_TABLE = [
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

function TM2_alertCell(r, col) {
  const v = r[col];
  if (r.cmp === "delta") return "Δ≥" + v;
  return (r.cmp === "über" ? ">" : "<") + v;
}

const TM2_ALERT_SAMPLE = [
  { metric: "Gewitter",   from: "15 %",    to: "60 %",    stage: "Etappe 3 · 14–18 Uhr" },
  { metric: "Böen",       from: "45 km/h", to: "72 km/h", stage: "Etappe 3 · 14–16 Uhr" },
  { metric: "Sichtweite", from: "15 km",   to: "6 km",    stage: "Etappe 3 · 14–18 Uhr" },
];

const TM2_SENS_LEVELS = [
  { id: "off",       label: "Aus" },
  { id: "relaxed",   label: "Entsp." },
  { id: "standard",  label: "Std." },
  { id: "sensitive", label: "Sens." },
];

function TM2_SensSeg({ value, onChange }) {
  return (
    <div style={{ display: "flex", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", overflow: "hidden", background: "var(--g-card)" }}>
      {TM2_SENS_LEVELS.map((lv, i) => {
        const on = value === lv.id;
        const isOff = lv.id === "off";
        return (
          <button key={lv.id} onClick={() => onChange(lv.id)} style={{
            flex: 1, minHeight: 42, border: "none", cursor: "pointer",
            borderLeft: i === 0 ? "none" : "1px solid var(--g-rule-soft)",
            background: on ? (isOff ? "var(--g-ink-3)" : "var(--g-accent)") : "transparent",
            color: on ? "#fff" : "var(--g-ink-3)",
            fontSize: 12.5, fontWeight: on ? 600 : 500, fontFamily: "var(--g-font-sans)",
            transition: "all 120ms",
          }}>{lv.label}</button>
        );
      })}
    </div>
  );
}

function TM2_MetricSensRow({ r, level, onLevel, isLast }) {
  const off = level === "off";
  return (
    <div style={{ padding: "12px 14px", borderBottom: isLast ? "none" : "1px solid var(--g-rule-soft)", background: off ? "transparent" : "rgba(196,90,42,0.025)", opacity: off ? 0.65 : 1 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 14.5, fontWeight: off ? 400 : 600, color: "var(--g-ink)" }}>
          {r.label} <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)" }}>{r.unit}</span>
        </span>
        <span className="mono" style={{ fontSize: 12.5, color: off ? "var(--g-ink-4)" : "var(--g-accent-deep)", fontWeight: off ? 400 : 600, flexShrink: 0 }}>
          {off ? "kein Alert" : TM2_alertCell(r, level)}
        </span>
      </div>
      <TM2_SensSeg value={level} onChange={onLevel}/>
    </div>
  );
}

function TM2_AlertSamplePreview() {
  return (
    <div style={{ background: "#fff", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", overflow: "hidden", fontFamily: "Helvetica, Arial, sans-serif" }}>
      <div style={{ background: "var(--g-accent)", color: "#fff", padding: "11px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <div>
          <div className="mono" style={{ fontSize: 9.5, letterSpacing: "0.1em", opacity: 0.9 }}>ALERT · KHW 403</div>
          <div style={{ fontSize: 15, fontWeight: 600, marginTop: 2 }}>Wetter-Änderung erkannt</div>
        </div>
        <div className="mono" style={{ fontSize: 9.5, opacity: 0.9, textAlign: "right", lineHeight: 1.4 }}>Mi 14.05.<br/>14:23</div>
      </div>
      <div>
        {TM2_ALERT_SAMPLE.map((r, i) => (
          <div key={r.metric} style={{ padding: "10px 14px", borderTop: i === 0 ? "none" : "1px solid var(--g-rule-soft)" }}>
            <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
              <span style={{ fontSize: 14, fontWeight: 600, color: "var(--g-ink)" }}>{r.metric}</span>
              <span className="mono" style={{ fontSize: 12.5 }}>
                <span style={{ color: "var(--g-ink-3)" }}>{r.from}</span>
                <span style={{ color: "var(--g-ink-4)", margin: "0 5px" }}>→</span>
                <span style={{ color: "var(--g-accent-deep)", fontWeight: 600 }}>{r.to}</span>
              </span>
            </div>
            <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 2 }}>{r.stage}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ─── Korridore Tab (Mobile · ersetzt Alerts · body-29 Phase 1) ───
 * Warn-Schwellen sind jetzt Korridore (context="route"). Cooldown, Stille
 * Stunden und Beispiel-Warnung bleiben als notify-Zustell-Einstellungen im
 * footer-Slot des gemeinsamen Mobile-Organism. */
function TM2_AlertsTab() {
  return <CorridorEditorMobile context="route"/>;
}

/* ════════════════════ MAIN: ScreenTripEditV2Mobile ════════════════════ */
function ScreenTripEditV2Mobile({ initialTab = "metriken" } = {}) {
  const [tab, setTab] = React.useState(initialTab);
  const [channels, setChannels] = React.useState({ email: true, telegram: true, sms: false });

  const TABS = [
    { id: "uebersicht", label: "Übersicht" },
    { id: "etappen",    label: "Etappen", badge: "5" },
    { id: "metriken",   label: "Wetter" },
    { id: "alerts",     label: "Wertebereiche", badge: "6", accent: true },
    { id: "zeitplan",   label: "Zeitplan" },
  ];

  return (
    <PhoneFrame height={812} time="08:14">
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Wetter-Metriken"
          eyebrow="KHW 403 · bearbeiten"
          leftIcon="back"
          right={<button style={{ height: 44, padding: "0 14px", border: "none", background: "transparent", color: "var(--g-accent)", fontWeight: 600, fontSize: 14, cursor: "pointer" }}>Speichern</button>}
        />
        <MTab items={TABS} active={tab} onChange={setTab}/>
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          {tab === "uebersicht" && (
            <ScreenScroll padding={16}>
              <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 4 }}>KHW 403</div>
              <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginBottom: 16 }}>Karnischer Höhenweg · 5 Etappen · 182 km</div>
              {[["Wetter-Metriken", () => setTab("metriken")], ["Briefing-Zeitplan", () => setTab("zeitplan")], ["Alerts", () => setTab("alerts")]].map(([lbl, fn]) => (
                <div key={lbl} onClick={fn} style={{ display: "flex", justifyContent: "space-between", padding: "14px 0", borderBottom: "1px solid var(--g-rule-soft)", cursor: "pointer", minHeight: 44, alignItems: "center" }}>
                  <span style={{ fontSize: 15, fontWeight: 500 }}>{lbl}</span>
                  <span style={{ color: "var(--g-ink-4)" }}>›</span>
                </div>
              ))}
            </ScreenScroll>
          )}
          {tab === "etappen" && (
            <ScreenScroll padding={16}>
              <div style={{ padding: "20px", background: "var(--g-card-alt)", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-2)", color: "var(--g-ink-3)", fontSize: 13, textAlign: "center" }}>
                Wegpunkt-Editor: bereits als eigene Komponente gebaut (Issue #503)
              </div>
            </ScreenScroll>
          )}
          {tab === "metriken" && <TM2_WetterTab/>}
          {tab === "zeitplan" && <VersandTab context="route" dense onOpenStages={() => setTab("etappen")}/>}
          {tab === "alerts"   && <TM2_AlertsTab/>}
        </div>
      </div>
    </PhoneFrame>
  );
}

window.ScreenTripEditV2Mobile = ScreenTripEditV2Mobile;
