/* SCREEN · Wetter-Metriken — Trip-Editor Tab (Desktop)
 * ──────────────────────────────────────────────────────────────────────────
 *  4 klare Bereiche in einem Tab, von oben nach unten:
 *  1 · Grundauswahl   — welche Metriken soll das Briefing enthalten?
 *  2 · Reihenfolge    — in welcher Reihenfolge, als Spalte oder Detail?
 *  3 · Kanäle         — an welche Kanäle geht das Briefing?
 *  4 · Vorschau       — so sieht das beim Empfänger aus
 *
 *  Kanäle (Bereich 3) werden im Tab „Briefing-Zeitplan" übernommen:
 *  nur aktivierte Kanäle erscheinen dort als Zeitplan-Karten.
 *
 *  Kein Signal-Kanal (entfernt 2026-06-05 per PO Henning).
 *  Engster Tabellen-Kanal: Telegram (max 8 Spalten).
 *  Page-Helpers: Prefix ME_  → verhindert Babel-Scope-Kollisionen.
 *
 *  Datenmodell-Ref: claude-code-handoff/issue-bodies/body-14-output-layout-system.md
 *  bucket="spalte" → aktiv (erscheint in Tabelle), aus → nicht in metrics-Array
 */

/* ── Metrik-Katalog ── */
const ME_ALL = [
  { id: "temp",       group: "Temperatur",   label: "Temperatur",          unit: "°C",   short: "Temp",     prio: 95 },
  { id: "feels",      group: "Temperatur",   label: "Gefühlte Temperatur", unit: "°C",   short: "Gefühlt",  prio: 70 },
  { id: "humidity",   group: "Temperatur",   label: "Luftfeuchtigkeit",    unit: "%",    short: "Luftf.",   prio: 25 },
  { id: "dewpoint",   group: "Temperatur",   label: "Taupunkt",            unit: "°C",   short: "Taup.",    prio: 20 },
  { id: "wind",       group: "Wind",         label: "Wind",                unit: "km/h", short: "Wind",     prio: 90 },
  { id: "gust",       group: "Wind",         label: "Böen",                unit: "km/h", short: "Böen",     prio: 88 },
  { id: "windDir",    group: "Wind",         label: "Windrichtung",        unit: "",     short: "Windr.",   prio: 40 },
  { id: "precip",     group: "Niederschlag", label: "Niederschlag",        unit: "mm",   short: "Regen",    prio: 78 },
  { id: "rainProb",   group: "Niederschlag", label: "Regenwahrsch.",       unit: "%",    short: "Regen%",   prio: 85 },
  { id: "thunder",    group: "Niederschlag", label: "Gewitterwahrsch.",    unit: "%",    short: "Gewitter", prio: 60 },
  { id: "cape",       group: "Niederschlag", label: "Gewitter-Energie",    unit: "J/kg", short: "CAPE",     prio: 15 },
  { id: "snowfall",   group: "Niederschlag", label: "Schneefall",          unit: "cm",   short: "Schnee",   prio: 55 },
  { id: "cloud",      group: "Wolken",       label: "Bewölkung",           unit: "%",    short: "Wolken",   prio: 65 },
  { id: "cloudLow",   group: "Wolken",       label: "Tiefe Wolken",        unit: "%",    short: "tiefe W.", prio: 30 },
  { id: "visibility", group: "Wolken",       label: "Sichtweite",          unit: "km",   short: "Sicht",    prio: 55 },
  { id: "sunshine",   group: "Wolken",       label: "Sonnenschein",        unit: "min",  short: "Sonne",    prio: 25 },
  { id: "uv",         group: "Sonstiges",    label: "UV-Index",            unit: "",     short: "UV",       prio: 45 },
  { id: "freezeLine", group: "Sonstiges",    label: "Nullgradgrenze",      unit: "m",    short: "0°-Linie", prio: 50 },
  { id: "snowDepth",  group: "Sonstiges",    label: "Schneehöhe",          unit: "cm",   short: "Schneeh.", prio: 35 },
  { id: "newSnow",    group: "Sonstiges",    label: "Neuschnee 24h",       unit: "cm",   short: "Neuschn.", prio: 30 },
  { id: "pressure",   group: "Sonstiges",    label: "Luftdruck",           unit: "hPa",  short: "Druck",    prio: 18 },
].map(m => {
  /* Kürzel aus Single Source metric-codes.jsx (codeShort). Nur wo
   * metric-codes die Id kennt — cape/snowDepth/newSnow/pressure/snowfall
   * behalten ihren lokalen short (mcGet-Fallback würde die id liefern). */
  const known = typeof window.METRIC_CODES !== "undefined" && window.METRIC_CODES[m.id];
  return { ...m, short: known ? window.mcGet(m.id).codeShort : m.short };
});
const ME_BY_ID = ME_ALL.reduce((m, x) => (m[x.id] = x, m), {});
const ME_GROUPS = ["Temperatur", "Wind", "Niederschlag", "Wolken", "Sonstiges"];
const ME_HAS_IND = new Set(["wind","gust","cape","thunder","rainProb","visibility","cloud","uv","precip","humidity","feels"]);
const ME_SMS_CAPABLE = new Set(["temp","precip","rainProb","wind","gust","thunder"]);

/* Kanal-Constraints (kein Signal). */
const ME_CHANNELS = [
  { id: "email",    label: "Email",    glyph: "✉", maxCols: 99 },
  { id: "telegram", label: "Telegram", glyph: "✈", maxCols: 8  },
  { id: "sms",      label: "SMS",      glyph: "✱", maxCols: 0  },
];

/* Presets. primary = Metriken im Briefing (links → rechts), rest = aus. */
const ME_PRESETS = [
  { id: "alpen",     name: "Alpen-Trekking", desc: "Standard für Hütten- und Höhenwanderer",
    primary: ["temp","feels","wind","gust","rainProb","thunder","windDir","precip","cloud","visibility","uv","freezeLine","snowfall"] },
  { id: "wandern",   name: "Wandern",        desc: "Einfach, Fokus auf Tagesentscheidung",
    primary: ["temp","feels","wind","gust","rainProb","precip","thunder","cloud","uv"] },
  { id: "skitour",   name: "Skitouren",      desc: "Lawinenkritische Metriken betont",
    primary: ["temp","feels","wind","gust","newSnow","snowDepth","windDir","visibility","cloud","precip","freezeLine"] },
  { id: "allgemein", name: "Allgemein",      desc: "Minimal, für jeden Trip",
    primary: ["temp","wind","rainProb","gust","precip","cloud","uv"] },
  { id: "khw403",    name: "★ KHW 403 (eigen)", desc: "Mein Preset für den Karnischen Höhenweg",
    primary: ["temp","feels","wind","gust","precip","rainProb","thunder","cape","cloudLow","visibility","uv","freezeLine","snowfall"] },
];
const ME_PRESET_BY_ID = ME_PRESETS.reduce((m, x) => (m[x.id] = x, m), {});

/* Initial-State aus Preset laden. */
function ME_loadPreset(presetId) {
  const p = ME_PRESET_BY_ID[presetId];
  const enabled = p.primary.map((id, i) => ({ id, bucket: "spalte", mode: ME_HAS_IND.has(id) ? "indicator" : "raw", order: i }));
  return { presetId, metrics: enabled, dirty: false };
}

/* ════════════════════ Haupt-Komponente ════════════════════ */
function ScreenMetricsEditor({ embedded = false } = {}) {
  const [cfg, setCfg] = React.useState(() => ME_loadPreset("khw403"));
  const [channels, setChannels] = React.useState({ email: true, telegram: true, sms: false });
  const [grExpanded, setGrExpanded] = React.useState(false);
  const [saveOpen, setSaveOpen] = React.useState(false);

  const enabled  = new Set(cfg.metrics.map(m => m.id));
  const primary  = cfg.metrics.map(m => m.id);

  const mutate = (fn) => setCfg(s => ({ ...s, metrics: fn(s.metrics), dirty: true }));

  const toggleMetric = (id) => {
    if (enabled.has(id)) {
      mutate(ms => ms.filter(m => m.id !== id));
    } else {
      mutate(ms => [...ms, { id, bucket: "spalte", mode: "raw" }]);
    }
    setCfg(s => ({ ...s, presetId: "khw403", dirty: true }));
  };

  const setMode = (id, mode) => mutate(ms => ms.map(m => m.id === id ? { ...m, mode } : m));

  const reorder = (id, dir) => mutate(ms => {
    const arr = [...ms]; const i = arr.findIndex(m => m.id === id);
    const j = i + dir; if (j < 0 || j >= arr.length) return ms;
    [arr[i], arr[j]] = [arr[j], arr[i]]; return arr;
  });

  const loadPreset = (id) => { setCfg(ME_loadPreset(id)); };

  const toggleChannel = (id) => setChannels(c => ({ ...c, [id]: !c[id] }));
  const [telegramSuffix, setTelegramSuffix] = React.useState(false);

  return (
    <div style={{ position: "relative", background: "var(--g-paper)" }}>
      {!embedded && <Sidebar active="trips"/>}
      <div style={{ ...(embedded ? {} : { marginLeft: 260 }) }}>
        {!embedded && <TopoBg opacity={0.12}/>}

        {!embedded && (
          <div style={{ position: "relative", padding: "14px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
              <span style={{ opacity: 0.6 }}>Trips</span><span style={{ margin: "0 8px" }}>/</span>
              <span style={{ opacity: 0.6 }}>KHW 403</span><span style={{ margin: "0 8px" }}>/</span>
              <span style={{ color: "var(--g-ink)" }}>Wetter-Metriken</span>
            </div>
            <div style={{ display: "flex", gap: 8 }}>
              {cfg.dirty && <Pill tone="warn">Ungespeichert</Pill>}
              <Btn variant="ghost" size="sm" onClick={() => setCfg(ME_loadPreset(cfg.presetId))}>Verwerfen</Btn>
              <Btn variant="primary" size="sm">Speichern</Btn>
            </div>
          </div>
        )}

        <div style={{ position: "relative", padding: embedded ? "28px 40px 60px" : "32px 40px 60px", maxWidth: 1400, display: "flex", flexDirection: "column", gap: 28 }}>

          {/* ── 1 · Grundauswahl ── */}
          <ME_Section num="1" eyebrow="Grundauswahl" title="Welche Metriken soll das Briefing enthalten?">
            <div style={{ display: "grid", gridTemplateColumns: "1fr", gap: 16 }}>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 10 }}>Profil wählen</div>
                <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                  {ME_PRESETS.map(p => (
                    <button key={p.id} onClick={() => loadPreset(p.id)} style={{
                      padding: "8px 14px", borderRadius: "var(--g-r-pill)", cursor: "pointer",
                      border: `1px solid ${cfg.presetId === p.id ? "var(--g-accent)" : "var(--g-rule)"}`,
                      background: cfg.presetId === p.id ? "var(--g-accent-tint)" : "var(--g-card)",
                      color: cfg.presetId === p.id ? "var(--g-accent-deep)" : "var(--g-ink-2)",
                      fontSize: 13, fontWeight: cfg.presetId === p.id ? 600 : 500,
                    }}>
                      {p.name}
                      <span className="mono" style={{ marginLeft: 6, fontSize: 10, opacity: 0.6 }}>{p.primary.length}</span>
                    </button>
                  ))}
                </div>
                {cfg.presetId !== "khw403" && (
                  <div style={{ marginTop: 8, fontSize: 12.5, color: "var(--g-ink-3)" }}>
                    {ME_PRESET_BY_ID[cfg.presetId]?.desc} · {cfg.metrics.length} Metriken aktiv
                  </div>
                )}
              </div>

              <div>
                <button onClick={() => setGrExpanded(!grExpanded)} style={{
                  background: "none", border: "none", cursor: "pointer", padding: 0,
                  display: "flex", alignItems: "center", gap: 8, color: "var(--g-ink-2)", fontSize: 13,
                }}>
                  <span className="mono" style={{ fontSize: 11, letterSpacing: "0.06em", color: "var(--g-ink-4)" }}>{grExpanded ? "▴" : "▾"}</span>
                  Einzelne Metriken anpassen
                  <Pill tone="neutral">{cfg.metrics.length} von {ME_ALL.length} aktiv</Pill>
                </button>

                {grExpanded && (
                  <div style={{ marginTop: 14, display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))", gap: "12px 24px" }}>
                    {ME_GROUPS.map(group => (
                      <div key={group}>
                        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8, fontWeight: 600 }}>{group}</div>
                        {ME_ALL.filter(m => m.group === group).map(m => (
                          <label key={m.id} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 0", cursor: "pointer", fontSize: 13, color: "var(--g-ink-2)" }}>
                            <input type="checkbox" checked={enabled.has(m.id)} onChange={() => toggleMetric(m.id)}
                              style={{ width: 14, height: 14, cursor: "pointer", accentColor: "var(--g-accent)", flexShrink: 0 }}/>
                            {m.label}
                            {m.unit && <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginLeft: 2 }}>{m.unit}</span>}
                          </label>
                        ))}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>
          </ME_Section>

          {/* ── 2 · Reihenfolge & Darstellung ── */}
          <ME_Section num="2" eyebrow="Reihenfolge & Darstellung"
            title="In welcher Reihenfolge?"
            hint="Von oben nach unten = von links nach rechts in der Tabelle. Reihenfolge entscheidet, was bei Telegram in die Tabelle kommt (max 8).">
            {cfg.metrics.length === 0 ? (
              <div style={{ padding: "20px 0", fontSize: 13, color: "var(--g-ink-4)", fontStyle: "italic" }}>Noch keine Metriken ausgewählt — im Bereich oben eine Grundauswahl treffen.</div>
            ) : (
              <div style={{ border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden" }}>
                <div style={{ display: "grid", gridTemplateColumns: "32px 1fr auto auto auto", gap: 0 }}>
                  {/* Header */}
                  <div style={{ gridColumn: "1/-1", display: "grid", gridTemplateColumns: "32px 1fr 220px 72px", background: "var(--g-card-alt)", padding: "8px 16px", borderBottom: "1px solid var(--g-rule)" }}>
                    <div/>
                    <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Metrik</div>
                    <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Darstellung</div>
                    <div/>
                  </div>
                </div>

                {cfg.metrics.map((m, i) => {
                  const isTelegramCut = channels.telegram && i === ME_CHANNELS.find(c => c.id === "telegram").maxCols;
                  return (
                    <React.Fragment key={m.id}>
                      {isTelegramCut && (
                        <div style={{ padding: "5px 16px", fontSize: 10.5, fontFamily: "var(--g-font-mono)", color: "#8a6210", background: "rgba(192,138,26,0.07)", borderTop: "1px dashed var(--g-warn)", borderBottom: "1px dashed var(--g-warn)", letterSpacing: "0.04em", display: "flex", alignItems: "center", gap: 8 }}>
                          <span>✂</span> ab hier Telegram-Limit (max 8 Spalten) — weiter oben = sicher in der Tabelle
                        </div>
                      )}
                      <div style={{ display: "grid", gridTemplateColumns: "32px 1fr 180px 180px 72px", padding: "10px 16px", alignItems: "center", borderBottom: "1px solid var(--g-rule-soft)", background: "var(--g-card)" }}>
                        <div className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--g-ink-3)", textAlign: "right", paddingRight: 10 }}>{i + 1}</div>
                        <div>
                          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--g-ink)" }}>{ME_BY_ID[m.id].label}</div>
                          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 1 }}>{ME_BY_ID[m.id].unit || "—"} · {ME_BY_ID[m.id].short}</div>
                        </div>
                        <div>
                          {ME_HAS_IND.has(m.id)
                            ? <Segmented size="sm" value={m.mode} onChange={(v) => setMode(m.id, v)}
                                items={[{ id: "raw", label: "Roh" }, { id: "indicator", label: "Einfach" }]}/>
                            : <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.05em" }}>nur Roh</span>}
                        </div>
                        <div style={{ display: "flex", gap: 3, justifyContent: "flex-end" }}>
                          <ME_Arrow dir="up"   disabled={i === 0} onClick={() => reorder(m.id, -1)}/>
                          <ME_Arrow dir="down" disabled={i === cfg.metrics.length - 1} onClick={() => reorder(m.id, +1)}/>
                        </div>
                      </div>
                    </React.Fragment>
                  );
                })}

                {/* Zusammenfassung */}
                <div style={{ padding: "10px 16px", background: "var(--g-card-alt)", borderTop: "1px solid var(--g-rule-soft)", display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12.5, color: "var(--g-ink-3)" }}>
                  <span><strong style={{ color: "var(--g-ink)" }}>{primary.length}</strong> Metriken aktiv</span>
                  <span>·</span>
                  <span style={{ color: channels.telegram && primary.length > 8 ? "#8a6210" : "inherit" }}>
                    Telegram: {channels.telegram ? (primary.length > 8 ? `${8} als Tabelle · ${primary.length - 8} als Zusatz` : `alle ${primary.length} passen`) : "deaktiviert"}
                  </span>
                </div>
              </div>
            )}
          </ME_Section>

          {/* ── 3 · Kanäle ── */}
          <ME_Section num="3" eyebrow="Kanäle"
            title="An welche Kanäle geht das Briefing?"
            hint={`Nur aktivierte Kanäle erscheinen im Tab „Briefing-Zeitplan". Telegram ist der engste Kanal — dort bestimmt die Reihenfolge oben, was als Tabelle ankommt.`}>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {ME_CHANNELS.map(ch => (
                <ME_ChannelCard key={ch.id} ch={ch} active={channels[ch.id]} spaltenCount={primary.length}
                  onToggle={() => toggleChannel(ch.id)}
                  telegramSuffix={ch.id === "telegram" ? telegramSuffix : undefined}
                  onSuffix={ch.id === "telegram" ? setTelegramSuffix : undefined}/>
              ))}
            </div>
            <div style={{ marginTop: 12, fontSize: 12.5, color: "var(--g-ink-3)", display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ width: 7, height: 7, borderRadius: "50%", background: "var(--g-info)", display: "inline-block" }}/>
              Aktivierte Kanäle werden im Tab <strong style={{ color: "var(--g-ink-2)" }}>Briefing-Zeitplan</strong> automatisch als Zeitplan-Optionen angeboten.
            </div>
          </ME_Section>

          {/* ── 4 · Vorschau ── */}
          <ME_Section num="4" eyebrow="Vorschau"
            title="So sieht das Briefing beim Empfänger aus"
            hint="Beispielwerte — kein Live-Wetter. Zeigt, wie deine aktuelle Auswahl und Reihenfolge pro Kanal ankommt.">
            <ChannelPreviewRedesign primary={primary} viewport="desktop" metricById={ME_BY_ID}/>
          </ME_Section>

          <Btn variant="ghost" size="sm" style={{ alignSelf: "flex-start" }} onClick={() => setSaveOpen(true)}>
            + Als eigenes Preset speichern
          </Btn>
        </div>
      </div>

      {saveOpen && <ME_SaveDialog metrics={cfg.metrics} onClose={() => setSaveOpen(false)}/>}
    </div>
  );
}

/* ── Sektion-Rahmen ── */
function ME_Section({ num, eyebrow, title, hint, children }) {
  return (
    <Card padding={0}>
      <div style={{ padding: "18px 22px 14px", borderBottom: "1px solid var(--g-rule-soft)" }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 4 }}>
          <span className="mono" style={{ fontSize: 11, fontWeight: 700, color: "var(--g-accent)", letterSpacing: "0.04em" }}>{num}</span>
          <Eyebrow>{eyebrow}</Eyebrow>
        </div>
        <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em" }}>{title}</div>
        {hint && <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5, maxWidth: 780 }}>{hint}</div>}
      </div>
      <div style={{ padding: "18px 22px 20px" }}>{children}</div>
    </Card>
  );
}

/* ── Pfeil-Button ── */
function ME_Arrow({ dir, disabled, onClick }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} aria-label={dir === "up" ? "nach oben" : "nach unten"} style={{
      width: 28, height: 28, border: "1px solid var(--g-rule)", borderRadius: 3,
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.35 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0,
    }}>
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
        {dir === "up" ? <path d="M6 2.5L10 8H2L6 2.5Z" fill="currentColor"/> : <path d="M6 9.5L2 4H10L6 9.5Z" fill="currentColor"/>}
      </svg>
    </button>
  );
}

/* ── Kanal-Karte ── */
function ME_ChannelCard({ ch, active, spaltenCount, onToggle, telegramSuffix, onSuffix }) {
  let cap, warn = false;
  if (ch.id === "email")    { cap = `Alle ${spaltenCount} Metriken · kein Limit`; }
  else if (ch.id === "telegram") {
    if (spaltenCount > 8) { cap = `8 Spalten in Tabelle · ${spaltenCount - 8} passen nicht rein`; warn = true; }
    else { cap = `Alle ${spaltenCount} Metriken passen`; }
  } else {
    cap = `Kein Raster · Kurz-Code max 140 Zeichen`;
  }

  return (
    <div style={{ border: `1px solid ${active ? "var(--g-rule)" : "var(--g-rule-soft)"}`, borderRadius: "var(--g-r-3)", padding: 18, background: active ? "var(--g-card)" : "var(--g-card-alt)", opacity: active ? 1 : 0.65, transition: "all 120ms" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12, marginBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <span className="mono" style={{ fontSize: 16, color: active ? "var(--g-accent-deep)" : "var(--g-ink-4)" }}>{ch.glyph}</span>
          <span style={{ fontSize: 15, fontWeight: 600, color: "var(--g-ink)" }}>{ch.label}</span>
        </div>
        <Switch checked={active} onChange={onToggle} tone="good" size="md"/>
      </div>
      <div style={{ fontSize: 12.5, color: warn ? "#8a6210" : "var(--g-ink-3)", lineHeight: 1.45 }}>{cap}</div>
      {ch.id === "telegram" && warn && active && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--g-rule-soft)", display: "flex", flexDirection: "column", gap: 8 }}>
          <div className="mono" style={{ fontSize: 10.5, color: "#8a6210", letterSpacing: "0.03em" }}>
            Reihenfolge (oben) entscheidet, welche 8 Spalten in die Tabelle kommen
          </div>
          <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
            <Switch checked={telegramSuffix || false} onChange={onSuffix} tone="good"/>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)" }}>Tages-Max für übrige Metriken</div>
              <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2, lineHeight: 1.4 }}>
                {spaltenCount - 8} Metriken nicht in Tabelle — als Tageszusammenfassung anhängen
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Save-Preset-Dialog ── */
function ME_SaveDialog({ metrics, onClose }) {
  const count = metrics.length;
  return (
    <div onClick={onClose} style={{ position: "fixed", inset: 0, background: "rgba(26,26,24,0.45)", backdropFilter: "blur(2px)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100 }}>
      <div onClick={e => e.stopPropagation()} style={{ width: 480, background: "var(--g-paper)", border: "1px solid var(--g-rule)", borderRadius: 6, boxShadow: "0 24px 80px rgba(26,26,24,0.22)", overflow: "hidden" }}>
        <div style={{ padding: "16px 22px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div><Eyebrow>Eigenes Preset</Eyebrow><div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>Auswahl als Preset speichern</div></div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, color: "var(--g-ink-3)", cursor: "pointer" }}>×</button>
        </div>
        <div style={{ padding: "16px 22px" }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>Name</div>
          <input autoFocus defaultValue="Mein Preset" style={{ width: "100%", padding: "9px 12px", fontSize: 15, background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: 4 }}/>
          <div style={{ marginTop: 14, padding: "12px 14px", background: "var(--g-card-alt)", borderRadius: 4, border: "1px solid var(--g-rule-soft)", display: "flex", gap: 16, fontSize: 12.5, color: "var(--g-ink-2)" }}>
            <span><strong style={{ color: "var(--g-ink)" }}>{count}</strong> Metriken aktiv</span>
          </div>
        </div>
        <div style={{ padding: "12px 22px", borderTop: "1px solid var(--g-rule-soft)", background: "var(--g-card-alt)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Btn variant="ghost" size="sm" onClick={onClose}>Abbrechen</Btn>
          <Btn variant="primary" size="sm" onClick={onClose}>Preset speichern</Btn>
        </div>
      </div>
    </div>
  );
}

window.ScreenMetricsEditor = ScreenMetricsEditor;
