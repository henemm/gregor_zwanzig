/* ════════════════════════════════════════════════════════════════════════
 *  LAYOUT-TAB — der geteilte Layout-Organism (Epic #29, Phase 4)
 * ════════════════════════════════════════════════════════════════════════
 *
 *  EIN Organism für beide Editoren. Ersetzt:
 *    - Compare-Editor · Layout-Tab      (CE_LayoutTab/CE_LayoutPreview,
 *                                        CEM_LayoutTab)
 *    - Trip-Editor    · den Ausgabe-Teil des Wetter-Metriken-Tabs
 *                       (Reihenfolge + Kanal-Kappung + Live-Mail-Vorschau).
 *                       Die Metrik-AUSWAHL (Preset + Grundauswahl) bleibt
 *                       Trip-eigen — sie sitzt weiter im Wetter-Metriken-Tab
 *                       ÜBER diesem Organism (PO 2026-07-11).
 *
 *  Beide Editoren droppen nur <LayoutTab context="route" | "vergleich" …/>.
 *
 *  E9 · zwei Templates über gemeinsame Primitiva — die Briefing-Templates
 *  werden NICHT zusammengelegt:
 *    · route     → Stunden × Metrik-Tabelle (echtes Mail-Chrome, WM2-Primitiva)
 *    · vergleich → Orte-als-Spalten-Tabelle (neutral, kein Rang)
 *  Geteilt sind: der Kanal-Umschalter + die Kappungs-Logik
 *  (Email ∞ · Telegram 8 · SMS flach) + die Zwei-Spalten-Hülle + die Cut-Line.
 *
 *  route ist CONTROLLED (Zustand + Handler kommen vom Wetter-Metriken-Tab,
 *  identische Signatur wie bisher → migrationsarm). vergleich ist
 *  self-contained (eigene Demo-Zeilen + pickedIds für die Spaltenzahl).
 *
 *  Lade-Reihenfolge: … organisms · metric-codes · screen-trip-edit-v2-weather
 *    (liefert WM2_Reihenfolge/WM2_EmailTable/…) → layout-tab.jsx → screen-*.
 *  Prefix-Disziplin (CLAUDE.md): lokale Helfer tragen LT_-Prefix.
 * ──────────────────────────────────────────────────────────────────────── */

/* ─── Kanal-Definitionen (Kappung) ─── */
const LT_CHANNELS = [
  { id: "email",    label: "Email",    max: Infinity, note: "alle Spalten · kein Limit" },
  { id: "telegram", label: "Telegram", max: 8,        note: "max 8 Spalten" },
  { id: "sms",      label: "SMS",      max: 0,         note: "kein Raster · ≤ 140 Zeichen" },
];
const LT_CH_BY_ID = Object.fromEntries(LT_CHANNELS.map(c => [c.id, c]));

/* ─── Geteilter Kanal-Umschalter mit Kappungs-Chip ───
 * Wählt den Kanal, für den Reihenfolge/Cut-Line + Vorschau gezeigt werden.
 * (Der An/Aus-Zustand der Kanäle lebt im Versand-Tab, nicht hier.) */
function LT_ChannelPicker({ channel, onChange, overflow, dense }) {
  return (
    <div style={{ display: "flex", gap: dense ? 6 : 4 }}>
      {LT_CHANNELS.map(ch => {
        const on = ch.id === channel;
        const over = overflow && overflow[ch.id];
        return (
          <button key={ch.id} onClick={() => onChange(ch.id)} style={{
            flex: dense ? 1 : "0 0 auto",
            padding: dense ? "10px 8px" : "7px 12px", cursor: "pointer",
            fontSize: dense ? 13 : 13, fontWeight: on ? 600 : 500,
            border: `1px solid ${on ? "var(--g-ink)" : "var(--g-rule)"}`,
            borderBottom: on ? "2px solid var(--g-accent)" : `1px solid var(--g-rule)`,
            borderRadius: "var(--g-r-2)", background: on ? "var(--g-card)" : "transparent",
            color: on ? "var(--g-ink)" : "var(--g-ink-3)", fontFamily: "var(--g-font-sans)",
            display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 6,
            textAlign: "center",
          }}>
            <span>{ch.label}</span>
            <span className="mono" style={{ fontSize: dense ? 9.5 : 10.5, color: on ? "var(--g-accent-deep)" : "var(--g-ink-4)", fontWeight: 600 }}>
              {ch.max === Infinity ? "∞" : ch.max === 0 ? "—" : ch.max}
            </span>
            {over && <span className="mono" style={{ fontSize: 9.5, padding: "1px 5px", borderRadius: 999, background: "rgba(192,138,26,0.15)", color: "#8a6210", fontWeight: 600 }}>−{over}</span>}
          </button>
        );
      })}
    </div>
  );
}

/* ─── Kappungs-Hinweis unter der Reihenfolge ─── */
function LT_CapNote({ channel, colCount, subject, dense }) {
  const ch = LT_CH_BY_ID[channel];
  if (!ch) return null;
  let text, warn = false;
  if (ch.max === Infinity) text = "Email zeigt alles · keine Begrenzung";
  else if (ch.max === 0)   text = "SMS hat keine Tabelle — nur Fließtext, entscheidungskritische Werte";
  else {
    const fits = colCount <= ch.max;
    warn = !fits;
    text = `${ch.label}: ${colCount} Spalten (Label + ${subject}) · ${fits ? `passt (max ${ch.max})` : `zu breit — max ${ch.max}, weiter vorne = sicherer`}`;
  }
  return (
    <div className="mono" style={{ marginTop: dense ? 8 : 10, fontSize: dense ? 10.5 : 11, color: warn ? "var(--g-warn)" : "var(--g-ink-4)", letterSpacing: "0.03em", lineHeight: 1.5 }}>
      {text}
    </div>
  );
}

/* ════════════════════ VERGLEICH · Orte-als-Spalten (E9-Template A) ════════════════════ */

/* Demo-Metrik-Zeilen der Übersicht (Wintersport-Profil). */
const LT_COMPARE_ROWS = [
  { label: "Schneehöhe",      key: "snow",    fmt: r => `${r.snow} cm`,                          good: r => r.snow >= 80,               emailOnly: false },
  { label: "Neuschnee 24 h",  key: "newSnow", fmt: r => `+${r.newSnow}`,                         good: r => r.newSnow >= 10,            emailOnly: false },
  { label: "Wind / Böen",     key: "wind",    fmt: r => `${r.wind}/${r.gust} ${r.dir}`,          good: r => r.wind <= 30,               emailOnly: false },
  { label: "Temperatur gef.", key: "feels",   fmt: r => `${r.feels >= 0 ? "+" : ""}${r.feels}°`, good: r => r.feels >= -8 && r.feels <= 2, emailOnly: false },
  { label: "Sonnenstunden",   key: "sun",     fmt: r => `~${r.sun} h`,                           good: r => r.sun >= 3,                 emailOnly: true },
  { label: "Bewölkung",       key: "cloud",   fmt: r => `${r.cloud ?? "–"}%`,                     good: () => false,                     emailOnly: true, off: true },
];

function LT_CompareOrderList({ channel, rows, onToggle, dense }) {
  return (
    <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden" }}>
      {rows.map((row, i) => {
        const shownAsDetail = row.off || (row.emailOnly && channel !== "email");
        return (
          <div key={row.key} style={{ display: "flex", alignItems: "center", gap: 10, padding: dense ? "12px 14px" : "9px 14px", minHeight: dense ? 48 : "auto", borderBottom: i < rows.length - 1 ? "1px solid var(--g-rule-soft)" : "none" }}>
            {!dense && <span style={{ color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", fontSize: 11, cursor: "grab" }}>⋮⋮</span>}
            <span style={{ flex: 1, fontSize: dense ? 14 : 13, color: "var(--g-ink-2)" }}>{row.label}</span>
            {shownAsDetail && <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" }}>↳ Detail</span>}
            <Switch checked={!shownAsDetail} tone="good" onChange={() => onToggle && onToggle(row.key)}/>
          </div>
        );
      })}
    </div>
  );
}

/* Neutrale Vorschau (PO 2026-07-08): Orte = Spalten, Metriken = Zeilen.
 * Kein Score, kein Rang. Werte im Idealbereich (Korridor) grün markiert. */
function LT_ComparePreview({ channel, pickedIds, dense }) {
  const locations = window.MOCK_LOCATIONS || [];
  const allRows   = window.MOCK_COMPARE_ROWS || [];
  const rows      = allRows.filter(r => pickedIds.includes(r.id)).slice(0, 4);

  if (rows.length === 0) return (
    <div style={{ padding: "40px 20px", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-3)", textAlign: "center", color: "var(--g-ink-4)", fontSize: 13 }}>
      Keine Orte ausgewählt — zurück zu „Orte".
    </div>
  );

  const locName = (id) => {
    const l = locations.find(x => x.id === id);
    if (!l) return id;
    const parts = l.name.split("/");
    return parts.length > 1 ? parts[parts.length - 1].trim() : l.name.split(/[\s(·]/)[0];
  };

  const metricRows = [
    { label: "Schnee",    fmt: r => `${r.snow} cm`,                          good: r => r.snow >= 80 },
    { label: "Neuschnee", fmt: r => `+${r.newSnow}`,                         good: r => r.newSnow >= 10 },
    { label: "Wind/Böen", fmt: r => `${r.wind}/${r.gust} ${r.dir}`,          good: r => r.wind <= 30 },
    { label: "Temp gef.", fmt: r => `${r.feels >= 0 ? "+" : ""}${r.feels}°`, good: r => r.feels >= -8 && r.feels <= 2 },
    ...(channel === "email" ? [{ label: "Sonne", fmt: r => `~${r.sun} h`, good: r => r.sun >= 3 }] : []),
  ];

  if (channel === "sms") {
    const parts = rows.slice(0, 3).map(r => `${locName(r.id)} ${r.snow}cm +${r.newSnow} ${r.feels >= 0 ? "+" : ""}${r.feels}°`);
    const body = `GZ Fr–So: ${parts.join(" · ")}`;
    return (
      <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", padding: "18px" }}>
        <Eyebrow style={{ marginBottom: 10 }}>SMS · ≤ 140 Z.</Eyebrow>
        <div style={{ padding: "12px 14px", background: "var(--g-paper-deep)", borderRadius: "var(--g-r-2)", fontFamily: "var(--g-font-mono)", fontSize: 12.5, lineHeight: 1.5, color: "var(--g-ink)" }}>{body}</div>
        <div className="mono" style={{ marginTop: 8, fontSize: 10, color: "var(--g-ink-4)" }}>
          {body.length} Zeichen · keine Tabelle — alle Orte nacheinander, ohne Rangfolge.
        </div>
      </div>
    );
  }

  const orteCols = rows.length + 1;
  return (
    <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden" }}>
      <div style={{ padding: "14px 16px", borderBottom: "1px solid var(--g-rule-soft)", background: "var(--g-card-alt)" }}>
        <Eyebrow style={{ marginBottom: 4 }}>Übersicht · Fr 12. – So 14.06.</Eyebrow>
        <div style={{ fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
          Werte nebeneinander — <span style={{ color: "var(--g-good)", fontWeight: 600 }}>grün</span> = in deinem Idealbereich. Kein Ranking.
        </div>
      </div>
      <div style={{ overflowX: "auto" }}>
        <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--g-font-mono)", fontVariantNumeric: "tabular-nums" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
              <th style={{ padding: "8px 12px", textAlign: "left", fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", fontWeight: 600 }}>Metrik</th>
              {rows.map(r => (
                <th key={r.id} style={{ padding: "8px 8px", textAlign: "center", fontSize: 10, color: "var(--g-ink)", letterSpacing: "0.04em", fontWeight: 600, fontFamily: "var(--g-font-sans)" }}>{locName(r.id)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {metricRows.map((m, i) => (
              <tr key={m.label} style={{ borderBottom: i < metricRows.length - 1 ? "1px solid var(--g-rule-soft)" : "none", background: i % 2 === 1 ? "var(--g-paper-deep)" : "transparent" }}>
                <td style={{ padding: "8px 12px", fontSize: 11, color: "var(--g-ink-3)", fontFamily: "var(--g-font-sans)", fontWeight: 500 }}>{m.label}</td>
                {rows.map(r => {
                  const ok = m.good(r);
                  return <td key={r.id} style={{ padding: "8px", textAlign: "center", fontSize: 11.5, color: ok ? "var(--g-good)" : "var(--g-ink)", fontWeight: ok ? 700 : 500 }}>{m.fmt(r)}</td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div style={{ padding: "8px 14px", background: "var(--g-paper-deep)", fontFamily: "var(--g-font-mono)", fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
        {channel === "email"
          ? "Email · alle Metrik-Zeilen + Stunden je Ort"
          : `Telegram · Label + ${rows.length} Orte = ${orteCols} Spalten (max 8)`}
      </div>
    </div>
  );
}

/* ════════════════════ ROUTE · Stunden × Metrik (E9-Template B) ════════════════════
 * Reine Wiederverwendung der WM2-Primitiva (echtes Mail-Chrome). */
function LT_RoutePreview({ state, channel, highlight, telegramSuffix, dense }) {
  const { primary, mode } = state;
  return (
    <div>
      {typeof WM2_DiffBanner === "function" && <WM2_DiffBanner highlight={highlight}/>}
      {channel === "email"    && <WM2_EmailTable    primary={primary} mode={mode} highlight={highlight} compact={dense}/>}
      {channel === "telegram" && <WM2_TelegramBubble primary={primary} mode={mode} highlight={highlight} telegramSuffix={telegramSuffix}/>}
      {channel === "sms"      && <WM2_SMSLine        primary={primary}/>}
    </div>
  );
}

/* Mobile-Reihenfolge (route · dense) — kompakte Reorder-Liste + Cut-Line. */
function LT_RouteOrderDense({ state, channel, onReorder }) {
  const { primary } = state;
  const ch = LT_CH_BY_ID[channel];
  const cutAt = ch && ch.max !== Infinity && ch.max > 0 ? ch.max : null;
  const Arrow = ({ dir, disabled, onClick }) => (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      width: 36, height: 36, border: "1px solid var(--g-rule)", borderRadius: 4, background: "var(--g-card)",
      color: "var(--g-ink-2)", cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.3 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0, flexShrink: 0,
    }}>
      <svg width="12" height="12" viewBox="0 0 12 12" fill="currentColor">{dir === "up" ? <path d="M6 2.5L10 8H2Z"/> : <path d="M6 9.5L2 4H10Z"/>}</svg>
    </button>
  );
  return (
    <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden" }}>
      <div style={{ padding: "12px 14px 8px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <span style={{ fontSize: 15, fontWeight: 600 }}>Reihenfolge <span style={{ color: "var(--g-ink-4)", fontWeight: 400, fontSize: 12 }}>· {primary.length}</span></span>
        <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>links → rechts</span>
      </div>
      {primary.map((id, i) => {
        const m = METRIC_BY_ID[id]; if (!m) return null;
        return (
          <React.Fragment key={id}>
            {cutAt != null && i === cutAt && (
              <div style={{ padding: "5px 14px", fontSize: 10.5, color: "#8a6210", background: "rgba(192,138,26,0.07)", borderTop: "1.5px dashed var(--g-warn)", borderBottom: "1.5px dashed var(--g-warn)", fontFamily: "var(--g-font-mono)" }}>
                ✂ ab hier {ch.label}-Limit (max {ch.max})
              </div>
            )}
            <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "12px 14px", borderBottom: "1px solid var(--g-rule-soft)", minHeight: 56 }}>
              <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", width: 22, textAlign: "right", flexShrink: 0 }}>{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 14, fontWeight: 500 }}>{m.label}</div>
                {m.unit && <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{m.unit}</div>}
              </div>
              <div style={{ display: "flex", gap: 4 }}>
                <Arrow dir="up"   disabled={i === 0} onClick={() => onReorder(id, -1)}/>
                <Arrow dir="down" disabled={i === primary.length - 1} onClick={() => onReorder(id, +1)}/>
              </div>
            </div>
          </React.Fragment>
        );
      })}
    </div>
  );
}

/* ════════════════════ LayoutTab — DER Organism ════════════════════
 *  Props:
 *    context   "route" | "vergleich"
 *    dense     true → Mobile
 *    ── route (controlled vom Wetter-Metriken-Tab): ──
 *    state, onMove, onReorder, onMode, highlight, telegramSuffix, onSuffix
 *    ── vergleich (self-contained): ──
 *    pickedIds  Orts-IDs (für Spaltenzahl der Vorschau)
 */
function LayoutTab(props) {
  const { context = "route", dense = false } = props;
  const isRoute = context === "route";

  const [channel, setChannel] = React.useState("email");

  /* Overflow-Badges für den Kanal-Picker. */
  const primaryCount = isRoute ? (props.state ? props.state.primary.length : 0) : 0;
  const pickedIds = props.pickedIds || ["loc-07", "loc-08", "loc-09", "loc-10"];
  const overflow = {};
  LT_CHANNELS.forEach(ch => {
    if (ch.max === Infinity || ch.max === 0) return;
    const count = isRoute ? primaryCount : pickedIds.length + 1;
    if (count > ch.max) overflow[ch.id] = count - ch.max;
  });

  /* Vergleich-Zeilen (self-managed on/off als Demo). */
  const [compareRows, setCompareRows] = React.useState(LT_COMPARE_ROWS.map(r => ({ ...r })));
  const toggleCompare = (key) => setCompareRows(rs => rs.map(r => r.key === key ? { ...r, off: !(r.off || (r.emailOnly && channel !== "email")) ? true : false } : r));

  const colCount = isRoute
    ? primaryCount + 1
    : pickedIds.length + 1;
  const subjectLabel = isRoute ? "Metriken" : `${pickedIds.length} Orte`;

  /* ── LINKS: Kanal + Reihenfolge ── */
  const leftCol = (
    <div style={{ display: "flex", flexDirection: "column", gap: dense ? 14 : 20 }}>
      <div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
          Kanal · Vorschau & Kappung
        </div>
        <LT_ChannelPicker channel={channel} onChange={setChannel} overflow={overflow} dense={dense}/>
      </div>
      <div>
        {!isRoute && (
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
            Metrik-Zeilen der Übersicht
          </div>
        )}
        {isRoute
          ? (dense
              ? <LT_RouteOrderDense state={props.state} channel={channel} onReorder={props.onReorder}/>
              : <WM2_Reihenfolge state={props.state} channel={channel} onMove={props.onMove} onReorder={props.onReorder} onMode={props.onMode} highlight={props.highlight}/>)
          : <LT_CompareOrderList channel={channel} rows={compareRows} onToggle={toggleCompare} dense={dense}/>}
        <LT_CapNote channel={channel} colCount={colCount} subject={subjectLabel} dense={dense}/>
      </div>
    </div>
  );

  /* ── RECHTS: Vorschau ── */
  const previewCol = (
    <div>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>
        So kommt es an · {LT_CH_BY_ID[channel].label}
      </div>
      {isRoute
        ? <LT_RoutePreview state={props.state} channel={channel} highlight={props.highlight} telegramSuffix={props.telegramSuffix} dense={dense}/>
        : <LT_ComparePreview channel={channel} pickedIds={pickedIds} dense={dense}/>}
    </div>
  );

  if (dense) {
    const inner = (
      <React.Fragment>
        {leftCol}
        <div style={{ marginTop: 20 }}>{previewCol}</div>
      </React.Fragment>
    );
    if (props.noScroll) return inner;
    return (
      <ScreenScroll padding={14} style={{ paddingBottom: props.bottomPad || 24 }}>
        {inner}
      </ScreenScroll>
    );
  }

  return (
    <div style={{ position: "relative", padding: "28px 40px 60px" }}>
      <TopoBg opacity={0.10}/>
      <div style={{ position: "relative", maxWidth: 1100, display: "grid", gridTemplateColumns: "minmax(380px, 1fr) minmax(380px, 1.1fr)", gap: 32, alignItems: "start" }}>
        {leftCol}
        {previewCol}
      </div>
    </div>
  );
}

/* ─── Export ─── */
Object.assign(window, {
  LayoutTab,
  LT_CHANNELS, LT_CH_BY_ID,
  LT_ChannelPicker, LT_CapNote,
  LT_CompareOrderList, LT_ComparePreview,
  LT_RoutePreview, LT_RouteOrderDense,
});
