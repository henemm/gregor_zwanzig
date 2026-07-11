/* ════════════════════════════════════════════════════════════════════════
 *  Wetter-Metriken Tab v2 — neu, klar, Signal-frei.
 *  Prefix WM2_ — Babel-Scope-Disziplin.
 *  Exports: WetterMetrikenTabV2
 *
 *  4 Abschnitte (alle auf einer Seite, kein Unter-Tab):
 *    1 Profil / Preset
 *    2 Grundauswahl   — welche Metriken ins Briefing
 *    3 Reihenfolge & Darstellung — Reihenfolge, Roh/Einfach
 *    4 Kanäle         — Email / Telegram / SMS on/off
 *  Rechts sticky: Live-Mail-Vorschau mit Diff-Highlight + Kanal-Umschalter.
 * ════════════════════════════════════════════════════════════════════════ */

const WM2_TG_LIMIT = 8;

const WM2_CHANNELS = [
  { id: "email",    label: "Email",    glyph: "✉", max: 99, note: "alle Spalten · kein Limit" },
  { id: "telegram", label: "Telegram", glyph: "✈", max: WM2_TG_LIMIT, note: `max ${WM2_TG_LIMIT} Spalten` },
  { id: "sms",      label: "SMS",      glyph: "✱", max: 0, note: "kein Raster · 140 Zeichen" },
];
const WM2_CH_BY_ID = Object.fromEntries(WM2_CHANNELS.map(c => [c.id, c]));

/* Sample-Werte · Segment 1 · KHW 403 (08/09/10 Uhr) */
const WM2_S = {
  temperature:     { raw: ["6,5","6,8","5,5"] },
  wind_chill:      { raw: ["5,2","4,7","2,6"] },
  wind:            { raw: ["2","8","10"],        ind: ["ruhig","ruhig","ruhig"] },
  gust:            { raw: ["23","16","24"],      ind: ["ruhig","ruhig","ruhig"] },
  precipitation:   { raw: ["1,1","3,3","1,8"] },
  rain_probability:{ raw: ["100","100","98"],   ind: ["sehr w.","sehr w.","sehr w."] },
  thunder:         { raw: ["–","–","–"],         ind: ["nein","nein","nein"] },
  cloud_total:     { raw: ["90","85","80"],      ind: ["bed.","bed.","bed."] },
  visibility:      { raw: ["25","12","22"],      ind: ["gut","mäßig","gut"] },
  uv_index:        { raw: ["0,2","0,4","0,9"] },
  freezing_level:  { raw: ["2880","2890","2930"] },
  humidity:        { raw: ["78","85","80"] },
  dewpoint:        { raw: ["4","5","3"] },
  wind_direction:  { raw: ["N","N","NO"] },
  pressure:        { raw: ["1012","1010","1011"] },
  sunshine:        { raw: ["0","0","5"] },
  fresh_snow:      { raw: ["–","–","–"] },
  snow_depth:      { raw: ["–","–","–"] },
  snowfall_limit:  { raw: ["–","–","–"] },
  cloud_low:       { raw: ["60","40","30"] },
  cloud_mid:       { raw: ["20","15","10"] },
  cloud_high:      { raw: ["5","5","5"] },
  cape:            { raw: ["40","120","80"],     ind: ["nied.","nied.","nied."] },
  precip_type:     { raw: ["Regen","Regen","Regen"] },
  confidence:      { raw: ["82","78","74"] },
};
function WM2_cell(id, h, mode) {
  const s = WM2_S[id] || { raw: ["–","–","–"] };
  if (mode === "indicator" && s.ind) return s.ind[h] || "–";
  return (s.raw || ["–","–","–"])[h] || "–";
}

function WM2_buildState(presetId) {
  const p = PRESETS.find(x => x.id === presetId) || PRESETS[0];
  const active = new Set(p.metrics);
  return {
    presetId, dirty: false,
    primary:        [...p.metrics],
    off:            METRIC_CATALOG.filter(m => !active.has(m.id)).map(m => m.id),
    mode:           {},
    telegramSuffix: false,  // Tages-Max für Überlauf bei Telegram
  };
}

/* ── Highlight-Farben ── */
function WM2_hlBg(kind) {
  if (kind === "removed") return { background: "rgba(168,50,50,0.10)", outline: "1.5px solid var(--g-bad)" };
  return { background: "var(--g-accent-tint)", outline: "1.5px solid var(--g-accent)" };
}

/* ══════════════════ ABSCHNITT 1: Preset-Bar ══════════════════ */
function WM2_PresetBar({ presetId, dirty, onChange }) {
  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {PRESETS.map(p => {
          const on = p.id === presetId && !dirty;
          return (
            <button key={p.id} onClick={() => onChange(p.id)} title={p.desc} style={{
              padding: "7px 13px", borderRadius: "var(--g-r-pill)", cursor: "pointer",
              border: `1px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`,
              background: on ? "var(--g-accent-tint)" : "var(--g-card)",
              color: on ? "var(--g-accent-deep)" : "var(--g-ink-2)", fontSize: 12.5, fontWeight: on ? 600 : 500,
            }}>{p.name}</button>
          );
        })}
      </div>
      {dirty && <div style={{ marginTop: 7, fontSize: 12, color: "var(--g-ink-3)" }}>
        Geändert — <button onClick={() => {}} style={{ color: "var(--g-accent)", background: "none", border: "none", cursor: "pointer", fontSize: 12, padding: 0 }}>als eigenes Profil speichern</button>
      </div>}
    </div>
  );
}

/* ══════════════════ ABSCHNITT 2: Grundauswahl ══════════════════ */
function WM2_Grundauswahl({ primary, onToggle, highlight }) {
  const active = new Set(primary);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
      {CATEGORY_ORDER.map(cat => (
        <div key={cat}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 7 }}>{CATEGORY_LABELS[cat]}</div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
            {(METRICS_BY_CATEGORY[cat] || []).map(m => {
              const on = active.has(m.id);
              const hl = highlight && highlight.id === m.id;
              return (
                <button key={m.id} onClick={() => onToggle(m.id, on)} style={{
                  padding: "6px 11px", borderRadius: 4, cursor: "pointer", fontSize: 12.5, fontWeight: 500,
                  border: `1px solid ${on ? "var(--g-ink)" : "var(--g-rule)"}`,
                  background: hl ? "var(--g-accent-tint)" : on ? "var(--g-ink)" : "var(--g-card)",
                  color: on ? "var(--g-paper)" : "var(--g-ink-3)",
                  outline: hl ? "2px solid var(--g-accent)" : "none",
                  outlineOffset: 2, transition: "background 0.2s",
                }}>
                  {on && <span style={{ fontSize: 9, marginRight: 4, opacity: 0.7 }}>✓</span>}
                  {m.label}
                </button>
              );
            })}
          </div>
        </div>
      ))}
      <div style={{ fontSize: 11.5, color: "var(--g-ink-4)", marginTop: 2 }}>
        Aktivierte Metriken erscheinen in Abschnitt 3, wo du Reihenfolge und Darstellung festlegst.
      </div>
    </div>
  );
}

/* ══════════════════ ABSCHNITT 3: Reihenfolge & Darstellung ══════════════════ */
function WM2_ReihenfolgeRow({ id, index, isFirst, isLast, mode, onMode, onMove, onReorder, highlight }) {
  const m = METRIC_BY_ID[id]; if (!m) return null;
  const isFixed = id === "time";
  const hl = highlight && highlight.id === id;
  const hasInd = indicatorCapable(id);
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "28px 16px 1fr auto",
      gap: 10, padding: "10px 16px", borderBottom: "1px solid var(--g-rule-soft)", alignItems: "center",
      background: hl ? "var(--g-accent-tint)" : "transparent", transition: "background 0.3s",
    }}>
      <div className="mono" style={{ fontSize: 11, fontWeight: 600, color: "var(--g-ink-4)", textAlign: "right" }}>{index + 1}</div>
      <svg width="10" height="14" viewBox="0 0 10 14" fill="var(--g-ink-4)" style={{ opacity: isFixed ? 0.2 : 0.5 }}>
        <circle cx="3" cy="3" r="1.1"/><circle cx="7" cy="3" r="1.1"/><circle cx="3" cy="7" r="1.1"/><circle cx="7" cy="7" r="1.1"/><circle cx="3" cy="11" r="1.1"/><circle cx="7" cy="11" r="1.1"/>
      </svg>
      <div>
        <span style={{ fontSize: 13.5, fontWeight: 500, color: "var(--g-ink)" }}>{m.label}</span>
        {m.unit && <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginLeft: 6 }}>{m.unit}</span>}
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "flex-end", flexWrap: "wrap" }}>
        {hasInd && (
          <Segmented size="sm" value={mode || "raw"} onChange={(v) => onMode(v)}
            items={[{ id: "raw", label: "Roh" }, { id: "indicator", label: "Einfach" }]}/>
        )}
        <div style={{ display: "flex", gap: 4 }}>
          <WM2_Btn onClick={() => onMove("off")} tone="bad">Aus</WM2_Btn>
        </div>
        <div style={{ display: "flex", gap: 2 }}>
          <WM2_Arrow dir="up"   disabled={isFirst || isFixed} onClick={() => onReorder(-1)}/>
          <WM2_Arrow dir="down" disabled={isLast}             onClick={() => onReorder(+1)}/>
        </div>
      </div>
    </div>
  );
}
function WM2_Arrow({ dir, disabled, onClick }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      width: 26, height: 26, border: "1px solid var(--g-rule)", borderRadius: 3,
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.3 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0,
    }}>
      <svg width="11" height="11" viewBox="0 0 12 12" fill="currentColor">
        {dir === "up" ? <path d="M6 2.5L10 8H2Z"/> : <path d="M6 9.5L2 4H10Z"/>}
      </svg>
    </button>
  );
}
function WM2_Btn({ children, onClick, tone }) {
  return (
    <button onClick={onClick} style={{
      padding: "5px 9px", fontSize: 11.5, fontFamily: "var(--g-font-sans)", fontWeight: 500,
      border: `1px solid ${tone === "bad" ? "rgba(168,50,50,0.35)" : "var(--g-rule)"}`,
      borderRadius: 3, background: "var(--g-card)",
      color: tone === "bad" ? "var(--g-bad)" : "var(--g-ink-2)", cursor: "pointer", whiteSpace: "nowrap",
    }}>{children}</button>
  );
}
function WM2_CutLine({ channel }) {
  const ch = WM2_CH_BY_ID[channel];
  if (!ch || ch.max >= 99 || ch.max === 0) return null;
  return (
    <div style={{ padding: "6px 16px", fontSize: 10.5, color: "#8a6210", background: "rgba(192,138,26,0.07)",
      borderTop: "1.5px dashed var(--g-warn)", borderBottom: "1.5px dashed var(--g-warn)",
      display: "flex", alignItems: "center", gap: 7, fontFamily: "var(--g-font-mono)" }}>
      <span>✂</span>
      <span>ab hier Telegram-Limit — weiter vorne = sicherer in der Tabelle (max {ch.max} Spalten)</span>
    </div>
  );
}
function WM2_Reihenfolge({ state, channel, onMove, onReorder, onMode, highlight }) {
  const { primary, mode } = state;
  const ch = WM2_CH_BY_ID[channel];
  const cutAt = ch && ch.max < 99 && ch.max > 0 ? ch.max : null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
      <Card padding={0}>
        <div style={{ padding: "14px 16px 10px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div style={{ fontSize: 16, fontWeight: 600 }}>Reihenfolge <span style={{ color: "var(--g-ink-4)", fontWeight: 400, fontSize: 13 }}>· {primary.length} Metriken</span></div>
          <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>links → rechts in der Email-Tabelle</span>
        </div>
        {primary.map((id, i) => (
          <React.Fragment key={id}>
            {cutAt != null && i === cutAt && <WM2_CutLine channel={channel}/>}
            <WM2_ReihenfolgeRow id={id} index={i} isFirst={i === 0} isLast={i === primary.length - 1}
              mode={mode[id]} highlight={highlight}
              onMode={(v) => onMode(id, v)} onMove={(t) => onMove(id, "primary", t)} onReorder={(d) => onReorder(id, d)}/>
          </React.Fragment>
        ))}
      </Card>
      </div>
  );
}

/* ══════════════════ ABSCHNITT 4: Kanäle ══════════════════ */
function WM2_Kanaele({ channels, onChange, primary, telegramSuffix, onSuffix }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      {WM2_CHANNELS.map(ch => {
        const on = channels[ch.id];
        return (
          <div key={ch.id} style={{
            border: `1px solid ${on ? "var(--g-ink)" : "var(--g-rule)"}`,
            borderRadius: "var(--g-r-2)",
            background: on ? "var(--g-card)" : "var(--g-card-alt)",
          }}>
            <div onClick={() => onChange({ ...channels, [ch.id]: !on })} style={{
              display: "flex", alignItems: "center", gap: 14, padding: "14px 16px", cursor: "pointer",
            }}>
              <span className="mono" style={{ fontSize: 16, width: 22, textAlign: "center", color: on ? "var(--g-ink)" : "var(--g-ink-4)" }}>{ch.glyph}</span>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 14, fontWeight: 600, color: on ? "var(--g-ink)" : "var(--g-ink-3)" }}>{ch.label}</div>
                <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 1 }}>{ch.note}</div>
              </div>
              <Switch checked={on} onChange={(v) => { v !== on && onChange({ ...channels, [ch.id]: v }); }}/>
            </div>
            {ch.id === "telegram" && on && primary && primary.length > WM2_TG_LIMIT && (
              <div style={{ padding: "10px 16px 14px 52px", borderTop: "1px solid var(--g-rule-soft)" }}>
                <div style={{ display: "flex", alignItems: "flex-start", gap: 12 }}>
                  <Switch checked={telegramSuffix || false} onChange={onSuffix} style={{ flexShrink: 0 }}/>
                  <div style={{ cursor: "pointer" }} onClick={() => onSuffix(!telegramSuffix)}>
                    <div style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)" }}>Tages-Max für übrige Metriken</div>
                    <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 2, lineHeight: 1.45 }}>
                      {primary.length - WM2_TG_LIMIT} Metriken passen nicht in die Tabelle — als kompakte Tageszusammenfassung anhängen
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        );
      })}
      <div style={{ fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.5, paddingLeft: 2 }}>
        Aktivierte Kanäle erscheinen auch im <strong>Briefing-Zeitplan</strong> und als Standard in den <strong>Alerts</strong>.
      </div>
    </div>
  );
}

/* ══════════════════ MAIL-VORSCHAU (rechts, sticky) ══════════════════ */
function WM2_ChannelTabs({ value, onChange, primary }) {
  return (
    <div style={{ display: "flex", gap: 4 }}>
      {WM2_CHANNELS.map(ch => {
        const on = ch.id === value;
        const over = ch.max < 99 && ch.max > 0 && primary.length > ch.max;
        return (
          <button key={ch.id} onClick={() => onChange(ch.id)} style={{
            padding: "7px 12px", cursor: "pointer", fontSize: 13, fontWeight: on ? 600 : 500,
            border: `1px solid ${on ? "var(--g-ink)" : "var(--g-rule)"}`,
            borderBottom: on ? "2px solid var(--g-accent)" : "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-2)", background: on ? "var(--g-card)" : "transparent",
            color: on ? "var(--g-ink)" : "var(--g-ink-3)",
            display: "inline-flex", alignItems: "center", gap: 6,
          }}>
            {ch.label}
            {over && <span className="mono" style={{ fontSize: 9.5, padding: "1px 5px", borderRadius: 999, background: "rgba(192,138,26,0.15)", color: "#8a6210", fontWeight: 600 }}>−{primary.length - ch.max}</span>}
          </button>
        );
      })}
    </div>
  );
}
function WM2_DiffBanner({ highlight }) {
  if (!highlight || !highlight.kind) return null;
  const m = highlight.id ? (METRIC_BY_ID[highlight.id] || {}) : null;
  const labels = { moved: "verschoben", added: "neu aktiviert", removed: "deaktiviert", mode: "Darstellung geändert" };
  const bad = highlight.kind === "removed";
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "7px 12px", borderRadius: "var(--g-r-2)", marginBottom: 10,
      background: bad ? "rgba(168,50,50,0.07)" : "var(--g-accent-tint)", borderLeft: `2px solid ${bad ? "var(--g-bad)" : "var(--g-accent)"}` }}>
      <span style={{ width: 7, height: 7, borderRadius: "50%", background: bad ? "var(--g-bad)" : "var(--g-accent)", flexShrink: 0 }}/>
      <span style={{ fontSize: 12.5, color: "var(--g-ink-2)" }}>
        {m ? <React.Fragment><strong style={{ color: "var(--g-ink)" }}>{m.label}</strong> — {labels[highlight.kind]}</React.Fragment>
           : <React.Fragment>Vorschau aktualisiert</React.Fragment>}
        <span style={{ color: "var(--g-ink-4)" }}> · unten hervorgehoben</span>
      </span>
    </div>
  );
}

/* Tages-Max: nimmt den höchsten Rohwert über die 3 Sample-Stunden */
function WM2_maxVal(id, mode) {
  const s = WM2_S[id] || { raw: ['–','–','–'] };
  const vals = (mode === 'indicator' && s.ind) ? s.ind : s.raw;
  // Try numeric max, fall back to last value
  let best = vals[0];
  let bestN = parseFloat(String(best).replace(',','.'));
  for (let i = 1; i < vals.length; i++) {
    const n = parseFloat(String(vals[i]).replace(',','.'));
    if (!isNaN(n) && (isNaN(bestN) || n > bestN)) { best = vals[i]; bestN = n; }
  }
  const m = METRIC_BY_ID[id];
  return m && m.unit ? best + ' ' + m.unit : best;
}
function WM2_EmailTable({ primary, mode, highlight, compact }) {
  const fs = compact ? 11.5 : 12.5;
  return (
    <div style={{ border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden", background: "#fff" }}>
      <div style={{ padding: "8px 14px", background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", alignItems: "center", gap: 8 }}>
        <span className="mono" style={{ fontSize: 9, letterSpacing: "0.12em", color: "var(--g-accent)", fontWeight: 600 }}>✉ ABEND-BRIEFING</span>
        <span className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", marginLeft: "auto" }}>KHW 403 · Segment 1</span>
      </div>
      <div style={{ padding: compact ? "12px 14px" : "16px 18px" }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-accent)", fontWeight: 600, marginBottom: 2 }}>◷ Wetter-Briefing</div>
        <div style={{ fontSize: compact ? 18 : 22, fontWeight: 700, letterSpacing: "-0.01em" }}>KHW 403</div>
        <div style={{ fontSize: 12, color: "var(--g-ink-2)", margin: "2px 0 14px" }}>Etappe 4: Hochweißsteinhaus → Wolayersee · 08–10 h</div>
        <div style={{ overflowX: "auto" }}>
          <table className="mono tnum" style={{ borderCollapse: "collapse", fontSize: fs, minWidth: "max-content", width: "100%" }}>
            <thead>
              <tr style={{ borderBottom: "1px solid var(--g-rule)" }}>
                <th style={{ fontSize: fs - 1.5, color: "var(--g-ink-3)", fontWeight: 600, padding: "4px 10px 4px 0", textAlign: "left" }}>Zeit</th>
                {primary.map(id => {
                  const hl = highlight && highlight.id === id;
                  const m = METRIC_BY_ID[id]; if (!m) return null;
                  const head = (typeof mcGet === "function") ? mcGet(id).codeEmail : m.short;
                  return <th key={id} style={{ fontSize: fs - 1.5, color: "var(--g-ink-3)", fontWeight: 600, padding: "4px 10px 4px 0", textAlign: "right", whiteSpace: "nowrap", ...(hl ? { ...WM2_hlBg(highlight.kind), borderRadius: "3px 3px 0 0" } : {}) }}>{head}</th>;
                })}
              </tr>
            </thead>
            <tbody>
              {["08","09","10"].map((h, hi) => (
                <tr key={h} style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
                  <td style={{ fontSize: fs, color: "var(--g-ink-3)", fontWeight: 600, padding: "5px 10px 5px 0" }}>{h}</td>
                  {primary.map(id => {
                    const hl = highlight && highlight.id === id;
                    return <td key={id} style={{ fontSize: fs, color: "var(--g-ink)", fontWeight: 500, padding: "5px 10px 5px 0", textAlign: "right", whiteSpace: "nowrap", ...(hl ? WM2_hlBg(highlight.kind) : {}) }}>{WM2_cell(id, hi, mode[id])}</td>;
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
function WM2_TelegramBubble({ primary, mode, highlight, telegramSuffix }) {
  const inTable = primary.slice(0, WM2_TG_LIMIT);
  const overflow = primary.slice(WM2_TG_LIMIT);
  const colW = 7;
  const fmt = (txt) => String(txt).slice(0, 6).padEnd(colW);
  const head = inTable.map(id => fmt((typeof mcGet === "function" ? mcGet(id).codeShort : ((METRIC_BY_ID[id] || {}).short || id)))).join("");
  const row = (hi) => inTable.map(id => fmt(WM2_cell(id, hi, mode[id]))).join("");
  const cut = primary.length > WM2_TG_LIMIT;
  return (
    <div>
      <div style={{ background: "#e9e6dc", borderRadius: "var(--g-r-3)", padding: "14px 12px" }}>
        <div style={{ maxWidth: 360, background: "#fff", borderRadius: "4px 14px 14px 14px", boxShadow: "0 1px 2px rgba(0,0,0,0.12)", overflow: "hidden" }}>
          <div style={{ padding: "7px 12px 5px", display: "flex", alignItems: "center", gap: 7, borderBottom: "1px solid #eee" }}>
            <span style={{ width: 18, height: 18, borderRadius: "50%", background: "#2aabee", color: "#fff", fontSize: 11, display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>✈</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#1d1c1a" }}>Gregor Zwanzig</span>
            <span className="mono" style={{ fontSize: 9, color: "#9a978d", marginLeft: "auto" }}>Telegram</span>
          </div>
          <div style={{ padding: "10px 12px 12px" }}>
            <div className="mono" style={{ fontSize: 11, color: "#1d1c1a", fontWeight: 600, marginBottom: 6 }}>KHW 403 · Seg. 1 · 08–10 h</div>
            <div className="mono tnum" style={{ fontSize: 11, lineHeight: 1.55, whiteSpace: "pre", overflowX: "auto", color: "#1d1c1a", background: "#f6f4ee", borderRadius: 4, padding: "6px 8px" }}>
              <div style={{ color: "#6b675c" }}>{head}</div>
              {[0,1,2].map(hi => <div key={hi}>{row(hi)}</div>)}
            </div>
            {telegramSuffix && overflow.length > 0 && (
              <div style={{ marginTop: 7, fontSize: 11.5, color: "#3a3835", lineHeight: 1.6 }}>
                <span style={{ fontFamily: "var(--g-font-mono)", fontSize: 10, color: "#6b675c", marginRight: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>Tages-Max</span>
                {overflow.map((id, i) => {
                  const m = METRIC_BY_ID[id]; if (!m) return null;
                  return <span key={id}>
                    {i > 0 && <span style={{ color: "#b9b4a6" }}> · </span>}
                    <strong>{m.label}</strong> {WM2_maxVal(id, mode[id])}
                  </span>;
                })}
              </div>
            )}
          </div>
        </div>
      </div>
      <div style={{ marginTop: 9, padding: "9px 12px", borderRadius: "var(--g-r-2)", borderLeft: `2px solid ${cut ? "var(--g-warn)" : "var(--g-good)"}`, background: cut ? "rgba(192,138,26,0.07)" : "rgba(61,107,58,0.06)", fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
        {cut
          ? <React.Fragment><strong style={{ color: "#8a6210" }}>{overflow.length} {overflow.length === 1 ? "Metrik passt" : "Metriken passen"} nicht in die Tabelle:</strong>{" "}{overflow.map(id => (METRIC_BY_ID[id] || {}).label || id).join(", ")}. Telegram zeigt nur die ersten <strong>{WM2_TG_LIMIT}</strong> — <strong>deshalb zählt die Reihenfolge.</strong></React.Fragment>
          : <React.Fragment>Alle <strong>{inTable.length}</strong> Spalten passen ins Telegram-Limit ({WM2_TG_LIMIT}).</React.Fragment>}
      </div>
    </div>
  );
}
function WM2_SMSLine({ primary }) {
  const line = `KHW403: N${WM2_cell("temperature",1,null)} W${WM2_cell("wind",1,null)}(${WM2_cell("gust",1,null)}) PR${WM2_cell("rain_probability",1,null)}% Z:WATCH`;
  return (
    <div>
      <div style={{ background: "#e9e6dc", borderRadius: "var(--g-r-3)", padding: "14px 12px" }}>
        <div style={{ maxWidth: 300, background: "#e5e5ea", color: "#1d1c1a", borderRadius: "4px 14px 14px 14px", padding: "10px 13px", fontSize: 12.5, lineHeight: 1.55, fontFamily: "var(--g-font-mono)", wordBreak: "break-all" }}>{line}</div>
        <div className="mono" style={{ fontSize: 10, color: "#6b675c", marginTop: 5 }}>{line.length}/140 Zeichen</div>
      </div>
      <div style={{ marginTop: 9, padding: "9px 12px", borderRadius: "var(--g-r-2)", borderLeft: "2px solid var(--g-warn)", background: "rgba(192,138,26,0.06)", fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
        SMS kennt keine Spalten-Reihenfolge: nur entscheidungskritische Werte werden als Kurzcodes gesendet.
      </div>
    </div>
  );
}
function WM2_MailPreview({ state, highlight, telegramSuffix }) {
  const [ch, setCh] = React.useState("email");
  const { primary, mode } = state;
  return (
    <div style={{ position: "sticky", top: 16 }}>
      <Eyebrow style={{ marginBottom: 8 }}>So kommt es an</Eyebrow>
      <WM2_ChannelTabs value={ch} onChange={setCh} primary={primary}/>
      <div style={{ marginTop: 12 }}>
        <WM2_DiffBanner highlight={highlight}/>
        {ch === "email"    && <WM2_EmailTable    primary={primary} mode={mode} highlight={highlight}/>}
        {ch === "telegram" && <WM2_TelegramBubble primary={primary} mode={mode} highlight={highlight}/>}
        {ch === "sms"      && <WM2_SMSLine primary={primary}/>}
      </div>
    </div>
  );
}

/* ══════════════════ HAUPTKOMPONENTE ══════════════════
 * Phase 4: Sektion 1+2 (Auswahl) bleiben Trip-eigen; Reihenfolge + Kanal-
 * Kappung + Live-Vorschau kommen aus dem geteilten <LayoutTab context="route">.
 * Kanäle an/aus wanderten in den Versand-Tab (VersandTab). */
function WetterMetrikenTabV2() {
  const [state, setState] = React.useState(() => WM2_buildState("alpine"));
  const [highlight, setHl] = React.useState(null);

  const flash = (id, kind) => { setHl({ id, kind }); setTimeout(() => setHl(null), 2500); };

  const toggle = (id, wasOn) => {
    setState(s => {
      const n = { ...s, primary: [...s.primary], off: [...s.off], dirty: true };
      if (wasOn) {
        n.primary = n.primary.filter(x => x !== id);
        n.off = [...n.off, id];
      } else {
        n.off = n.off.filter(x => x !== id);
        n.primary = [...n.primary, id];
      }
      return n;
    });
    flash(id, wasOn ? "removed" : "added");
  };

  const move = (id, from, to) => {
    setState(s => {
      const n = { ...s, primary: [...s.primary], off: [...s.off], dirty: true };
      n.primary = n.primary.filter(x => x !== id);
      n.off = n.off.filter(x => x !== id);
      if (to !== "off") n.primary = [...n.primary, id]; else n.off = [...n.off, id];
      return n;
    });
    flash(id, to === "off" ? "removed" : "added");
  };

  const reorder = (id, dir) => {
    setState(s => {
      const list = [...s.primary]; const i = list.indexOf(id); const ni = i + dir;
      if (ni < 0 || ni >= list.length) return s;
      [list[i], list[ni]] = [list[ni], list[i]];
      return { ...s, primary: list, dirty: true };
    });
    flash(id, "moved");
  };

  const setMode = (id, m) => { setState(s => ({ ...s, mode: { ...s.mode, [id]: m }, dirty: true })); flash(id, "mode"); };

  const loadPreset = (pid) => { setState(WM2_buildState(pid)); flash(null, null); };

  const [telegramSuffix, setTelegramSuffix] = React.useState(false);

  return (
    <div style={{ position: "relative" }}>
      {/* Sektion 1+2 · Metrik-Auswahl (Trip-eigen) */}
      <div style={{ position: "relative", padding: "28px 40px 4px", maxWidth: 900 }}>
        <TopoBg opacity={0.06}/>
        <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 20 }}>
          <Card padding={18}>
            <Eyebrow style={{ marginBottom: 10 }}>01 — Profil</Eyebrow>
            <WM2_PresetBar presetId={state.presetId} dirty={state.dirty} onChange={loadPreset}/>
          </Card>
          <Card padding={18}>
            <Eyebrow style={{ marginBottom: 4 }}>02 — Grundauswahl</Eyebrow>
            <div style={{ fontSize: 15, fontWeight: 600, marginBottom: 14 }}>
              Welche Metriken ins Briefing?
              <span style={{ fontSize: 13, fontWeight: 400, color: "var(--g-ink-3)", marginLeft: 8 }}>{state.primary.length} aktiv</span>
            </div>
            <WM2_Grundauswahl primary={state.primary} onToggle={toggle} highlight={highlight}/>
          </Card>
        </div>
      </div>

      {/* Sektion 3 · Reihenfolge + Kanal-Kappung + Live-Vorschau — geteilter Organism */}
      <LayoutTab context="route" state={state} onMove={move} onReorder={reorder} onMode={setMode}
        highlight={highlight} telegramSuffix={telegramSuffix} onSuffix={setTelegramSuffix}/>
    </div>
  );
}

Object.assign(window, {
  WetterMetrikenTabV2, WM2_CHANNELS, WM2_TG_LIMIT,
  WM2_buildState, WM2_cell,
  WM2_PresetBar, WM2_Grundauswahl, WM2_Kanaele,
  WM2_EmailTable, WM2_TelegramBubble, WM2_SMSLine,
  WM2_DiffBanner, WM2_ChannelTabs, WM2_MailPreview,
});
