/* ════════════════════════════════════════════════════════════════════════
 *  REDESIGN · Issue #496 — „Pro Kanal"-Vorschau neu gedacht
 * ════════════════════════════════════════════════════════════════════════
 *
 *  Ersetzt den 4-Kachel-Strip (ChannelPreviewBlock / ChannelPreviewStrip).
 *
 *  TECH-LEAD-ENTSCHEIDUNG (Begründung im Host-Canvas):
 *    Weder A (nur Konsequenz-Zahlen) noch B (nur Ein-Kanal-Vorschau) noch
 *    C (entfernen) trägt allein. Gewählt: A + B als ZWEI Schichten.
 *
 *    Schicht 1 — Konsequenz-Leiste:  alle 4 Kanäle, je als kompakte
 *      „passt / rutscht / fällt weg"-Kachel. Klick = Kanal-Wähler.
 *    Schicht 2 — Ehrliche Ein-Kanal-Vorschau (Voll-Breite): EIN Kanal in
 *      realistischer Breite — echte Email-Tabelle (Desktop + iPhone),
 *      echte Telegram-Bubble (≈330px), echte SMS im Spec-Code.
 *
 *  WICHTIG — Fidelity-Regeln (PO 2026, Issue #496-Review):
 *    • Email: Desktop-Tabelle UND iPhone-Mail.app müssen beide gezeigt
 *      werden (Empfänger liest unterwegs am iPhone).
 *    • SMS: striktes Spec-Format aus screen-output-preview.jsx::SMSPreview —
 *      Token-Code, KEIN hübscher „ · "-Fließtext. Sonst Missverständnisse.
 *        N{lo} D{hi}  R{mm}|R-  PR{p}%@{h}  W{v}@{h}({max}@{h})
 *        G{v}@{h}({max}@{h})  TH{p}%@{h}  TH+:L/M/H@{h}  HR:L/M/H@{h}
 *        Z:HIGH/MED/LOW:{höhe}     "-" = kein Wert
 *      SMS ist KEIN Spalten-Kanal: nur entscheidungskritische Metriken
 *      haben einen Code, der Rest fällt weg.
 *
 *  Kein Live-Wetter — alle Zahlen sind markierte Beispielwerte.
 *  Atomic-Design: nutzt Card/Eyebrow aus atoms.jsx. Lokale Helfer = CP*.
 *  ──────────────────────────────────────────────────────────────────── */

/* Selbständiger Mini-Katalog (Fallback, wenn kein metricById übergeben). */
const CP_METRICS = [
  { id: "temp",       label: "Temperatur",       short: "Temp",   unit: "°C",   prio: 95 },
  { id: "feels",      label: "Gefühlte Temp",    short: "Gef",    unit: "°C",   prio: 70 },
  { id: "wind",       label: "Wind",             short: "Wind",   unit: "km/h", prio: 90 },
  { id: "gust",       label: "Böen",             short: "Böe",    unit: "km/h", prio: 88 },
  { id: "rainProb",   label: "Regen-Wahrsch.",   short: "Reg%",   unit: "%",    prio: 85 },
  { id: "precip",     label: "Niederschlag",     short: "mm",     unit: "mm",   prio: 78 },
  { id: "thunder",    label: "Gewitter",         short: "Gew%",   unit: "%",    prio: 60 },
  { id: "cloud",      label: "Bewölkung",        short: "Wolk",   unit: "%",    prio: 65 },
  { id: "visibility", label: "Sichtweite",       short: "Sicht",  unit: "km",   prio: 55 },
  { id: "uv",         label: "UV-Index",         short: "UV",     unit: "",     prio: 45 },
  { id: "humidity",   label: "Luftfeuchtigkeit", short: "Luftf",  unit: "%",    prio: 25 },
  { id: "windDir",    label: "Windrichtung",     short: "Windri", unit: "°",    prio: 40 },
  { id: "freezeLine", label: "Nullgrad-Grenze",  short: "0°-L",   unit: "m",    prio: 50 },
  { id: "dewpoint",   label: "Taupunkt",         short: "Taup",   unit: "°C",   prio: 20 },
].map(m => {
  /* Kürzel aus Single Source metric-codes.jsx (codeShort — Telegram/SMS). */
  const known = typeof window.METRIC_CODES !== "undefined" && window.METRIC_CODES[m.id];
  return { ...m, short: known ? window.mcGet(m.id).codeShort : m.short };
});
const CP_BY_ID = CP_METRICS.reduce((m, x) => (m[x.id] = x, m), {});

/* Beispielwerte für 3 Beispiel-Stunden (NICHT live). */
const CP_SAMPLE = {
  temp:       ["8,2", "11,0", "9,9"],
  feels:      ["7,1", "8,1", "8,4"],
  wind:       ["5", "12", "4"],
  gust:       ["12", "24", "11"],
  rainProb:   ["8", "53", "63"],
  precip:     ["0", "3,2", "0,2"],
  thunder:    ["0", "5", "0"],
  cloud:      ["70", "95", "85"],
  visibility: ["1,2", "3,5", "2,4"],
  uv:         ["0,4", "2,0", "2,4"],
  humidity:   ["78", "88", "83"],
  windDir:    ["NE", "SE", "NE"],
  freezeLine: ["2.310", "2.530", "2.450"],
  dewpoint:   ["4", "6", "5"],
};

const CP_CHANNELS = [
  { id: "email",    label: "Email",    glyph: "✉", maxCols: 99, note: "volle HTML-Tabelle · keine Grenze" },
  { id: "telegram", label: "Telegram", glyph: "✈", maxCols: 8,  note: "Monospace-Tabelle · max 8 Spalten — engster Tabellen-Kanal" },
  { id: "sms",      label: "SMS",      glyph: "✱", maxCols: 0,  note: "kein Raster · Token-Code · 140 Zeichen" },
];
const CP_CH_BY_ID = CP_CHANNELS.reduce((m, x) => (m[x.id] = x, m), {});

/* SMS-Token-Code je Metrik (Spec screen-output-preview.jsx::SMSPreview).
 * Nur entscheidungskritische Metriken haben einen Code — alles andere
 * existiert im SMS-Kanal NICHT. Werte = Beispiel. */
const CP_SMS_TOK = {
  temp:     "N8 D11",
  precip:   "R3.2",
  rainProb: "PR53%@12",
  wind:     "W12@11(24@13)",
  gust:     "G25@12(43@14)",
  thunder:  "TH5%@12",
};
const CP_SMS_PREFIX = "KHW03:";
const CP_SMS_TAIL = "Z:WATCH:2447";   // Ziel-Risiko — strukturell immer dabei
const CP_SMS_MAX = 140;

const CP_smsTokenMeaning = {
  temp:     "N/D = Nacht-Tief / Tag-Hoch °C",
  precip:   "R = Regen mm (R- = keiner)",
  rainProb: "PR = Regen-Wahrsch. %@Stunde",
  wind:     "W = Wind km/h@Std(Max@Std)",
  gust:     "G = Böen km/h@Std(Max@Std)",
  thunder:  "TH = Gewitter %@Stunde",
};

/* Spalten-Renderer (identisch zum Backend-Constraint-Modell). */
function CP_apply(primary, maxCols) {
  const inTable = primary.slice(0, maxCols);
  const demoted = primary.slice(maxCols);
  return { inTable, demoted, detail: demoted };
}

/* SMS-Renderer: baut die echte Token-Zeile, priorisiert nach Reihenfolge,
 * füllt bis 140 Zeichen. Liefert getragene / mangels-Code-weggefallene /
 * mangels-Platz-weggefallene Metriken zurück. */
function CP_smsRender(primary) {
  const order = [...primary];
  const carried = [], noCode = [], overflow = [];
  let tokens = [];
  const lenWith = (toks) => `${CP_SMS_PREFIX} ${[...toks, CP_SMS_TAIL].join(" ")}`.length;

  for (const id of order) {
    const tok = CP_SMS_TOK[id];
    if (!tok) { noCode.push(id); continue; }
    if (lenWith([...tokens, tok]) > CP_SMS_MAX) { overflow.push(id); continue; }
    tokens.push(tok); carried.push(id);
  }
  const line = `${CP_SMS_PREFIX} ${[...tokens, CP_SMS_TAIL].join(" ")}`;
  return { line, carried, noCode, overflow, len: line.length, dropped: noCode.length + overflow.length };
}

/* ════════════════════ Haupt-Komponente ════════════════════ */
function ChannelPreviewRedesign({
  primary = [],
  viewport = "desktop",
  initialChannel = "telegram",
  metricById = null,      /* optionaler externer Katalog (Editor) */
}) {
  const [sel, setSel] = React.useState(initialChannel);
  const mobile = viewport === "mobile";
  const MB = (id) => (metricById && metricById[id]) || CP_BY_ID[id] || { short: id, label: id, unit: "" };

  return (
    <Card padding={0}>
      {/* ── Header ── */}
      <div style={{ padding: mobile ? "14px 16px 12px" : "16px 22px 14px", borderBottom: "1px solid var(--g-rule-soft)" }}>
        <Eyebrow>Vorschau · so kommt es beim Empfänger an</Eyebrow>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginTop: 3 }}>
          <div style={{ fontSize: mobile ? 17 : 19, fontWeight: 600, letterSpacing: "-0.01em" }}>Pro Kanal</div>
          <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
            {primary.length} Spalten
          </span>
        </div>
        <div style={{ fontSize: mobile ? 12.5 : 13, color: "var(--g-ink-2)", marginTop: 8, lineHeight: 1.55, maxWidth: 720 }}>
          Eine Konfiguration, vier Kanäle mit unterschiedlicher Kapazität. Links siehst du <strong>für jeden Kanal die Konsequenz</strong> deiner Auswahl — klick einen Kanal an, um <strong>die echte Vorschau</strong> in Original-Breite zu sehen.
        </div>
      </div>

      {/* ── Body ── */}
      <div style={{ display: mobile ? "block" : "grid", gridTemplateColumns: mobile ? undefined : "340px 1fr" }}>
        {/* Schicht 1 — Konsequenz-Leiste */}
        <div style={{
          padding: mobile ? "14px 16px 4px" : "18px 18px 18px 22px",
          borderRight: mobile ? "none" : "1px solid var(--g-rule-soft)",
          background: "var(--g-card-alt)",
        }}>
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--g-ink-3)", fontWeight: 600, marginBottom: 10 }}>
            1 · Konsequenz pro Kanal
          </div>
          <div style={{
            display: mobile ? "grid" : "flex",
            gridTemplateColumns: mobile ? "1fr 1fr" : undefined,
            flexDirection: mobile ? undefined : "column",
            gap: 8,
          }}>
            {CP_CHANNELS.map(ch => (
              <CP_ConsequenceTile
                key={ch.id} channel={ch} primary={primary}
                active={sel === ch.id} onSelect={() => setSel(ch.id)} MB={MB}
              />
            ))}
          </div>
        </div>

        {/* Schicht 2 — Ehrliche Ein-Kanal-Vorschau */}
        <div style={{ padding: mobile ? "16px 16px 18px" : "18px 22px 22px" }}>
          <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 10, marginBottom: 12 }}>
            <div className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--g-ink-3)", fontWeight: 600 }}>
              2 · So sieht {CP_CH_BY_ID[sel].label} aus
            </div>
            <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.04em", textTransform: "uppercase" }}>
              Beispielwerte · kein Live-Wetter
            </span>
          </div>
          <CP_Fidelity sel={sel} primary={primary} mobile={mobile} MB={MB}/>
        </div>
      </div>
    </Card>
  );
}

/* ──────────── Schicht 1: Konsequenz-Kachel ──────────── */
function CP_ConsequenceTile({ channel, primary, active, onSelect, MB }) {
  const isSMS = channel.id === "sms";
  const total = primary.length;

  let bigNum, bigSub, statusText, tone;
  if (isSMS) {
    const sms = CP_smsRender(primary);
    bigNum = sms.carried.length;
    bigSub = `/ ${total} als Code`;
    tone = sms.dropped > 0 ? "warn" : "ok";
    statusText = sms.dropped > 0 ? `${sms.dropped} fallen weg` : "alle haben Code";
  } else {
    const { inTable, demoted } = CP_apply(primary, channel.maxCols);
    bigNum = inTable.length;
    const noLimit = channel.maxCols >= 99;
    bigSub = noLimit ? "Spalten" : `/ ${channel.maxCols} Spalten`;
    tone = demoted.length > 0 ? "warn" : "ok";
    /* Email (∞): am Desktop Tabelle, am Handy gestapelt — aber NIE Datenverlust. */
    statusText = noLimit ? "nichts f\u00e4llt weg" : (demoted.length > 0 ? `${demoted.length} rutschen` : "alle als Spalte");
  }
  const toneColor = tone === "warn" ? "var(--g-warn)" : "var(--g-good)";

  return (
    <button
      onClick={onSelect}
      style={{
        textAlign: "left", cursor: "pointer", width: "100%",
        background: active ? "var(--g-card)" : "transparent",
        border: `1px solid ${active ? "var(--g-ink)" : "var(--g-rule-soft)"}`,
        borderLeft: active ? "3px solid var(--g-accent)" : "3px solid transparent",
        borderRadius: "var(--g-r-2)",
        boxShadow: active ? "var(--g-shadow-1)" : "none",
        padding: "10px 12px",
        transition: "border-color 120ms, background 120ms",
        display: "flex", flexDirection: "column", gap: 8,
      }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
        <span className="mono" style={{ fontSize: 13, color: active ? "var(--g-accent-deep)" : "var(--g-ink-3)", width: 14, textAlign: "center" }}>{channel.glyph}</span>
        <span style={{ fontSize: 13.5, fontWeight: 600, color: "var(--g-ink)" }}>{channel.label}</span>
        <span style={{ flex: 1 }}/>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: toneColor, flexShrink: 0 }}/>
      </div>

      <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
        <span className="mono" style={{ fontSize: 20, fontWeight: 600, color: "var(--g-ink)", fontVariantNumeric: "tabular-nums", lineHeight: 1 }}>{bigNum}</span>
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{bigSub}</span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: 6, flexWrap: "wrap" }}>
        <span className="mono" style={{
          fontSize: 10, fontWeight: 600, letterSpacing: "0.02em",
          padding: "2px 7px", borderRadius: "var(--g-r-pill)",
          background: tone === "warn" ? "rgba(192,138,26,0.14)" : "rgba(61,107,58,0.12)",
          color: tone === "warn" ? "#8a6210" : "var(--g-good)",
        }}>{statusText}</span>

      </div>
    </button>
  );
}

/* ──────────── Schicht 2: Fidelity-Router ──────────── */
function CP_Fidelity({ sel, primary, mobile, MB }) {
  if (sel === "email") return <CP_EmailPreview primary={primary} mobile={mobile} MB={MB}/>;
  if (sel === "sms")   return <CP_SmsPreview primary={primary} MB={MB}/>;
  return <CP_BubblePreview channel={CP_CH_BY_ID[sel]} primary={primary} MB={MB}/>;
}

/* Wert-Helfer (Beispielwerte, „–" wenn unbekannt). */
const CP_val = (id, h = 1) => (CP_SAMPLE[id] ? CP_SAMPLE[id][h] : "–");
function CP_valUnit(id, MB, h = 1) {
  const m = MB ? MB(id) : CP_BY_ID[id];
  const u = m && m.unit ? ` ${m.unit}` : "";
  return `${CP_val(id, h)}${u}`;
}



/* ──────────── Email: Desktop-Tabelle + iPhone-Mail.app ──────────── */
function CP_EmailPreview({ primary, mobile, MB }) {
  const { inTable } = CP_apply(primary, 99);
  const [view, setView] = React.useState(mobile ? "iphone" : "desktop");

  return (
    <div>
      {/* Mail-Viewport-Umschalter — Empfänger liest am Desktop ODER iPhone */}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <div style={{ display: "inline-flex", padding: 2, gap: 2, background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: 4 }}>
          {[["desktop", "Desktop-Mail"], ["iphone", "iPhone-Mail"]].map(([id, lbl]) => (
            <button key={id} onClick={() => setView(id)} className="mono" style={{
              padding: "4px 10px", fontSize: 10.5, fontWeight: 600, letterSpacing: "0.03em",
              border: "none", borderRadius: 2, cursor: "pointer",
              background: view === id ? "var(--g-paper)" : "transparent",
              color: view === id ? "var(--g-accent-deep)" : "var(--g-ink-3)",
              boxShadow: view === id ? "0 0 0 1px var(--g-rule)" : "none",
            }}>{lbl}</button>
          ))}
        </div>
        <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>
          {view === "iphone" ? "schmal · Stunden gestapelt" : "breit · volle Tabelle"}
        </span>
      </div>

      {view === "desktop"
        ? <CP_EmailDesktop inTable={inTable} MB={MB}/>
        : <CP_EmailPhone inTable={inTable} MB={MB}/>}
    </div>
  );
}

function CP_MailChrome({ iphone }) {
  return (
    <div style={{ padding: iphone ? "8px 12px" : "9px 14px", background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", alignItems: "center", gap: 8 }}>
      <span className="mono" style={{ fontSize: 9.5, letterSpacing: "0.1em", color: "var(--g-accent)", fontWeight: 600 }}>MORGEN-BRIEFING</span>
      <span style={{ flex: 1 }}/>
      <span className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.08em" }}>GREGOR ZWANZIG · EMAIL</span>
    </div>
  );
}
const CP_th = (align) => ({ fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600, padding: "5px 9px 5px 0", textAlign: align || "right", whiteSpace: "nowrap" });
const CP_td = (align, head) => ({ fontSize: 12.5, color: head ? "var(--g-ink-3)" : "var(--g-ink)", fontWeight: head ? 600 : 500, padding: "6px 9px 6px 0", textAlign: align || "right", whiteSpace: "nowrap" });

function CP_EmailDesktop({ inTable, MB }) {
  const hours = ["08", "12", "15"];
  return (
    <div style={{ border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", overflow: "hidden", background: "var(--g-card)" }}>
      <CP_MailChrome/>
      <div style={{ padding: "12px 14px", overflowX: "auto" }}>
        <table className="mono tnum" style={{ borderCollapse: "collapse", fontSize: 12, width: "100%" }}>
          <thead>
            <tr style={{ borderBottom: "1px solid var(--g-rule)" }}>
              <th style={CP_th("left")}>h</th>
              {inTable.map(id => <th key={id} style={CP_th()}>{MB(id).short}</th>)}
            </tr>
          </thead>
          <tbody>
            {hours.map((h, hi) => (
              <tr key={h} style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
                <td style={CP_td("left", true)}>{h}</td>
                {inTable.map(id => <td key={id} style={CP_td()}>{CP_val(id, hi)}</td>)}
              </tr>
            ))}
          </tbody>
        </table>

      </div>
      <div className="mono" style={{ padding: "8px 14px", borderTop: "1px solid var(--g-rule-soft)", fontSize: 10, color: "var(--g-good)", background: "rgba(61,107,58,0.05)", letterSpacing: "0.03em" }}>
        ✓ Email zeigt alle {inTable.length} Spalten — nichts rutscht weg.
      </div>
    </div>
  );
}

/* iPhone-Mail.app: schmaler Bezel, Stunden gestapelt (wie EmailHourList). */
function CP_EmailPhone({ inTable, MB }) {
  const hours = ["08", "12", "15"];
  return (
    <div style={{ display: "flex", justifyContent: "flex-start" }}>
      <div style={{
        width: 300, background: "#1c1c1e", borderRadius: 30, padding: 9,
        boxShadow: "0 10px 30px rgba(0,0,0,0.18)",
      }}>
        <div style={{ background: "#fff", borderRadius: 23, overflow: "hidden" }}>
          {/* Status-Bar */}
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "8px 18px 4px" }}>
            <span className="mono" style={{ fontSize: 11, fontWeight: 700 }}>06:01</span>
            <span style={{ fontSize: 10, color: "#1d1c1a" }}>● ● ●</span>
          </div>
          <CP_MailChrome iphone/>
          <div style={{ padding: "8px 14px 14px" }}>
            {hours.map((h, hi) => (
              <div key={h} style={{ padding: "8px 0", borderBottom: hi < hours.length - 1 ? "1px solid var(--g-rule-soft)" : "none" }}>
                <div className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--g-ink)", marginBottom: 4 }}>{h}:00</div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "3px 12px", fontFamily: "var(--g-font-mono)", fontSize: 11, color: "var(--g-ink-2)" }}>
                  {inTable.map(id => (
                    <span key={id}><span style={{ color: "var(--g-ink-4)" }}>{MB(id).short} </span><span style={{ color: "var(--g-ink)", fontWeight: 600 }}>{CP_val(id, hi)}</span></span>
                  ))}
                </div>
              </div>
            ))}

          </div>
        </div>
      </div>
      <div style={{ marginLeft: 14, alignSelf: "center", maxWidth: 210, fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.55 }}>
        Eine {inTable.length}-Spalten-Tabelle passt am Handy nicht nebeneinander. Die Mail rendert deshalb <strong>pro Stunde gestapelt</strong> als Mikro-Liste — alle {inTable.length} Werte bleiben erhalten, <strong>nichts geht verloren</strong>, nur das Layout bricht um.
      </div>
    </div>
  );
}

/* ──────────── Telegram: echte Chat-Bubble ──────────── */
function CP_BubblePreview({ channel, primary, MB }) {
  const { inTable, demoted } = CP_apply(primary, channel.maxCols);
  const bubbleW = 330;
  const accent = "#2aabee";

  const colW = 6;
  const headLine = inTable.map(id => MB(id).short.slice(0, 5).padEnd(colW, " ")).join("");
  const rowLine = (hi) => inTable.map(id => String(CP_val(id, hi)).slice(0, 5).padEnd(colW, " ")).join("");

  return (
    <div>
      <div style={{ background: "#e9e6dc", borderRadius: "var(--g-r-3)", padding: "16px 14px", display: "flex", justifyContent: "flex-start" }}>
        <div style={{ maxWidth: bubbleW, width: "100%", background: "#fff", borderRadius: "4px 14px 14px 14px", boxShadow: "0 1px 2px rgba(0,0,0,0.12)", overflow: "hidden" }}>
          <div style={{ padding: "8px 12px 4px", display: "flex", alignItems: "center", gap: 7, borderBottom: "1px solid #eee" }}>
            <span style={{ width: 18, height: 18, borderRadius: "50%", background: accent, color: "#fff", fontSize: 10, display: "inline-flex", alignItems: "center", justifyContent: "center", fontWeight: 700 }}>{channel.glyph}</span>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#1d1c1a" }}>Gregor Zwanzig</span>
          </div>
          <div style={{ padding: "10px 12px 12px" }}>
            <div className="mono" style={{ fontSize: 11, color: "#1d1c1a", fontWeight: 600, marginBottom: 6 }}>KHW 03 · Morgen 06:00</div>
            <div className="mono tnum" style={{ fontSize: 11, lineHeight: 1.55, whiteSpace: "pre", overflowX: "auto", color: "#1d1c1a", background: "#f6f4ee", borderRadius: 4, padding: "7px 9px" }}>
              <div style={{ color: "#6b675c" }}>{headLine}</div>
              {[0, 1, 2].map(hi => <div key={hi}>{rowLine(hi)}</div>)}
            </div>

            <div className="mono" style={{ marginTop: 8, fontSize: 9.5, color: "#9a978d", textAlign: "right" }}>06:00 ✓✓</div>
          </div>
        </div>
      </div>

      <div style={{
        marginTop: 10, padding: "9px 12px", borderRadius: "var(--g-r-2)",
        background: demoted.length ? "rgba(192,138,26,0.08)" : "rgba(61,107,58,0.06)",
        borderLeft: `2px solid ${demoted.length ? "var(--g-warn)" : "var(--g-good)"}`,
        fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.5,
      }}>
        {demoted.length ? (
          <React.Fragment>
            <strong style={{ color: "#8a6210" }}>{demoted.length} {demoted.length === 1 ? "Metrik passt" : "Metriken passen"} nicht in die {channel.label}-Tabelle:</strong>{" "}
            {demoted.map(id => MB(id).label).join(", ")}. Telegram zeigt nur die ersten <strong>{channel.maxCols}</strong> Spalten.
          </React.Fragment>
        ) : (
          <React.Fragment>Alle <strong>{inTable.length}</strong> Spalten passen in das {channel.label}-Limit ({channel.maxCols}). Nichts rutscht.</React.Fragment>
        )}
      </div>
    </div>
  );
}

/* ──────────── SMS: echtes Spec-Token-Format + Mapping ──────────── */
function CP_SmsPreview({ primary, MB }) {
  const { line, carried, noCode, overflow, len } = CP_smsRender(primary);
  const over = len > CP_SMS_MAX;

  return (
    <div>
      {/* Echte SMS-Bubble im Spec-Code */}
      <div style={{ background: "#e9e6dc", borderRadius: "var(--g-r-3)", padding: "16px 14px" }}>
        <div style={{ maxWidth: 320 }}>
          <div className="mono" style={{ background: "#e5e5ea", color: "#1d1c1a", borderRadius: "4px 14px 14px 14px", padding: "10px 13px", fontSize: 12, lineHeight: 1.55, wordBreak: "break-all", letterSpacing: "0.01em" }}>
            {line}
          </div>
          <div className="mono" style={{ fontSize: 10, color: over ? "var(--g-bad)" : "#6b675c", marginTop: 5, paddingLeft: 4 }}>
            {len}/{CP_SMS_MAX} Zeichen · gesendet 06:00
          </div>
        </div>
      </div>

      {/* Token-Mapping: was hat einen Code, was fällt weg */}
      <div style={{ marginTop: 12, display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div style={{ border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", padding: "10px 12px", background: "var(--g-card)" }}>
          <div className="mono" style={{ fontSize: 9.5, letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--g-good)", fontWeight: 600, marginBottom: 7 }}>
            ✓ {carried.length} mit SMS-Code
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
            {carried.map(id => (
              <div key={id} style={{ display: "flex", justifyContent: "space-between", gap: 8, fontSize: 11.5 }}>
                <span style={{ color: "var(--g-ink-2)" }}>{MB(id).label}</span>
                <span className="mono" style={{ color: "var(--g-ink)", fontWeight: 600 }}>{CP_SMS_TOK[id]}</span>
              </div>
            ))}
          </div>
        </div>
        <div style={{ border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", padding: "10px 12px", background: "var(--g-card-alt)" }}>
          <div className="mono" style={{ fontSize: 9.5, letterSpacing: "0.08em", textTransform: "uppercase", color: "#8a6210", fontWeight: 600, marginBottom: 7 }}>
            ✕ {noCode.length + overflow.length} fallen weg
          </div>
          <div style={{ fontSize: 11.5, color: "var(--g-ink-3)", lineHeight: 1.55 }}>
            {noCode.length > 0 && (
              <div style={{ marginBottom: overflow.length ? 6 : 0 }}>
                <span style={{ color: "var(--g-ink-2)" }}>{noCode.map(id => MB(id).label).join(", ")}</span>
                <span style={{ color: "var(--g-ink-4)" }}> — kein SMS-Code</span>
              </div>
            )}
            {overflow.length > 0 && (
              <div>
                <span style={{ color: "var(--g-ink-2)" }}>{overflow.map(id => MB(id).label).join(", ")}</span>
                <span style={{ color: "var(--g-ink-4)" }}> — über 140 Zeichen</span>
              </div>
            )}
            {noCode.length + overflow.length === 0 && <span>—</span>}
          </div>
        </div>
      </div>

      {/* Spec-Hinweis + Legende der getragenen Codes */}
      <div style={{ marginTop: 10, padding: "9px 12px", borderRadius: "var(--g-r-2)", background: "rgba(192,138,26,0.06)", borderLeft: "2px solid var(--g-warn)", fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
        SMS ist <strong>kein Spalten-Kanal</strong>: der Renderer übersetzt nur entscheidungskritische Metriken in feste Kurz-Codes und nimmt sie nach Priorität bis 140 Zeichen. Reihenfolge oben steuert, was zuerst greift.
      </div>
      {carried.length > 0 && (
        <div className="mono" style={{ marginTop: 8, fontSize: 10, color: "var(--g-ink-4)", lineHeight: 1.7 }}>
          {carried.map(id => CP_smsTokenMeaning[id]).filter(Boolean).map((t, i) => (
            <div key={i}>{t}</div>
          ))}
          <div>Z = Ziel-Risiko:Höhe · „-" = kein Wert</div>
        </div>
      )}
    </div>
  );
}

/* ════════════════════ Lehr-Konfiguration + Begründung ════════════════════
 * Single-Source für die Demo-Auswahl, die das Constraint-Verhalten zeigt:
 * 10 Spalten — bewusst über dem Telegram-Limit (8), damit man sieht,
 * wie Telegram (8) und SMS (140 Zeichen) verschieben/abschneiden
 * und warum Email (∞) nur umbricht, nie verliert.
 * Wird von den Haupt-Seiten (Desktop + Mobile) UND vom Editor referenziert. */
const CP_DEMO_PRIMARY   = ["temp","feels","wind","gust","rainProb","precip","thunder","cloud","visibility","uv"];
const CP_DEMO_SECONDARY = ["humidity","windDir","freezeLine","dewpoint"];


/* Tech-Lead-Begründung (Issue #496) — warum A+B statt eines der drei Vorschläge.
 * Wandert mit auf die Haupt-Seite, damit die Entscheidung dort dokumentiert ist. */
function ChannelPreviewRationale() {
  const Opt = ({ tag, title, body, verdict, tone }) => (
    <div style={{ display: "grid", gridTemplateColumns: "26px 1fr", gap: 14, padding: "14px 0", borderBottom: "1px solid var(--g-rule-soft)" }}>
      <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: tone === "pick" ? "var(--g-accent)" : "var(--g-ink-4)" }}>{tag}</div>
      <div>
        <div style={{ fontSize: 14.5, fontWeight: 600, marginBottom: 3 }}>{title}</div>
        <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.55 }}>{body}</div>
        <div className="mono" style={{ fontSize: 11, marginTop: 6, letterSpacing: "0.03em", color: tone === "pick" ? "var(--g-good)" : "var(--g-ink-3)", fontWeight: 600 }}>{verdict}</div>
      </div>
    </div>
  );
  return (
    <div style={{ padding: "36px 44px", background: "var(--g-paper)", minHeight: "100%", position: "relative" }}>
      <TopoBg opacity={0.1}/>
      <div style={{ position: "relative", maxWidth: 860 }}>
        <Eyebrow>Issue #496 · Entscheidung</Eyebrow>
        <h1 style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.02em", margin: "8px 0 14px" }}>
          „Pro Kanal" als zwei Schichten — nicht als vier Kacheln
        </h1>
        <div style={{ fontSize: 15, color: "var(--g-ink-2)", lineHeight: 1.6, marginBottom: 8 }}>
          Das Grundproblem des 4er-Grids: eine 200px-Kachel kann eine Email-Tabelle (∞ Spalten) physisch nicht ehrlich abbilden. Der User soll hier eine einzige Frage beantworten können — <strong>„passt meine Auswahl, und welche Metriken rutschen weg?"</strong> — und das vor dem Speichern verifizieren.
        </div>

        <div style={{ marginTop: 18, border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", padding: "4px 20px 12px", background: "var(--g-card)" }}>
          <Opt tag="A" tone="" title="Nur Konsequenz-Zahlen" body={`„Telegram: 8 Spalten.“ Beantwortet PASST-ES, aber nie SIEHT-ES-RICHTIG-AUS.`} verdict="Allein zu schwach für ein Verifikations-Tool."/>
          <Opt tag="B" tone="" title="Nur Ein-Kanal-Vorschau" body={`Eine große Tabelle für den aktiven Kanal. Ehrlich, aber verliert den Quervergleich „welcher Kanal ist der Engpass?“.`} verdict="Allein verliert die Übersicht."/>
          <Opt tag="C" tone="" title="Block entfernen, inline-Hinweis" body="Nur eine Zeile im Editor. Wirft den Verifikations-Nutzen ganz weg." verdict={`Widerspricht „Vorschau = Verifikation im Setup“ (CLAUDE.md).`}/>
          <Opt tag="A+B" tone="pick" title="Gewählt · Konsequenz-Leiste + ehrliche Ein-Kanal-Vorschau" body="Schicht 1 zeigt alle 4 Kanäle kompakt nebeneinander (Engpass auf einen Blick, klickbar = Wähler). Schicht 2 rendert EINEN Kanal in echter Breite — echte Email-Tabelle, echte Telegram-Bubble (≈330px), echter SMS-Text mit 140-Zähler." verdict="✓ Beide Fragen beantwortet · keine 200px-Lüge · readability-first."/>
        </div>

        <div style={{ marginTop: 18, fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.6 }}>
          Demo-Konfiguration in den Mockups: <strong>10 Spalten</strong> — bewusst über dem Telegram-Limit (8), damit man sieht, wie Telegram und SMS (Zeichen-Budget) Metriken abschneiden. Email (∞) bricht am Handy nur um, verliert nie. Zahlen sind markierte Beispielwerte, kein Live-Wetter.
        </div>
      </div>
    </div>
  );
}

window.ChannelPreviewRedesign = ChannelPreviewRedesign;
window.ChannelPreviewRationale = ChannelPreviewRationale;
window.CP_METRICS = CP_METRICS;
window.CP_DEMO_PRIMARY = CP_DEMO_PRIMARY;
window.CP_DEMO_SECONDARY = CP_DEMO_SECONDARY;

