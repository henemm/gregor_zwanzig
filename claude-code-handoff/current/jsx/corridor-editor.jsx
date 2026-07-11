/* ════════════════════════════════════════════════════════════════════════
 *  CORRIDOR EDITOR — der gemeinsame Korridor-Editor-Organism (body-29, Phase 1+4)
 * ════════════════════════════════════════════════════════════════════════
 *
 *  EIN Organism für beide Editoren. Ersetzt:
 *    - Trip-Editor  · Alerts-Tab      (alertRules  → corridors[notify])
 *    - Compare-Editor · Idealwerte-Tab (ideals     → corridors[mark])
 *
 *  Kern-Idee (E3′): der Korridor ist EINE „Gut-Zone" pro Metrik, zwei Brillen.
 *    range [min?, max?]  — die akzeptable / ideale Zone (einseitig offen erlaubt, C2)
 *    notify              — MELDEN, sobald ein Wert den Korridor VERLÄSST (Trip-Alert)
 *    mark                — MARKIEREN (grün), solange ein Wert IM Korridor liegt (Idealwert)
 *  Eine Geometrie, zwei Wirkungen — beide auf beiden kinds erlaubt.
 *  Defaults: route → notify, vergleich → mark.
 *
 *  Constraints:
 *    C1  Neutralität — kein Score, kein Rang, keine Empfehlung. Korridore erzeugen
 *        nur notify/mark, nie Aggregation oder Sortierung.
 *    C2  range einseitig offen: [null, 60] = „warne über 60".
 *    C5  identische Match-Logik Backend + Frontend → corridorInside() ist die
 *        Single-Source, die auch die Live-Vorschau speist.
 *
 *  Lade-Reihenfolge:  … → organisms.jsx → corridor-editor.jsx → screen-*.jsx
 *  Prefix-Disziplin:  lokale Helfer tragen CE-freien, sprechenden Namen mit
 *  Corridor*-Domain-Prefix (Babel-Scope-Falle, CLAUDE.md).
 * ──────────────────────────────────────────────────────────────────────── */

/* ─── C5 · Match-Logik (Single-Source für Editor + Renderer + Vorschau) ─── */
function corridorInside(value, min, max) {
  if (value == null) return null;               // kein Messwert
  if (min != null && value < min) return false; // unter dem Korridor
  if (max != null && value > max) return false; // über dem Korridor
  return true;                                  // im Korridor
}

function corridorFmt(v, unit) {
  if (v == null) return "offen";
  const s = Number.isInteger(v) ? String(v) : v.toFixed(1);
  const withSign = unit === "°C" && v > 0 ? `+${s}` : s;
  return unit ? `${withSign} ${unit}` : withSign;
}

/* ─── Kontext-Copy ─── */
const CORRIDOR_CTX = {
  route: {
    eyebrow: "Wertebereiche · Warn-Schwellen",
    title: "Sag mir, wenn das Wetter aus dem Rahmen läuft",
    lead: "Ein Wertebereich je Metrik legt fest, welche Werte du auf der Tour noch akzeptierst. Verlässt ein Wert den Bereich, bekommst du zwischen den Briefings eine Sofort-Meldung.",
    defaultNotify: true,
    defaultMark: false,
    subjectLabel: "Etappen",
    neutral: false,
  },
  vergleich: {
    eyebrow: "Wertebereiche · Idealbereiche",
    title: "Sag mir, welche Werte dir ideal sind",
    lead: "Ein Wertebereich je Metrik legt deinen Idealbereich fest. Werte im Bereich werden im Briefing pro Ort grün markiert — kein Score, kein Ranking, nur eine Lese-Hilfe.",
    defaultNotify: false,
    defaultMark: true,
    subjectLabel: "Orte",
    neutral: true,
  },
};

/* ─── Metrik-Korridore je Editor-Beispiel ───
 * scale = plausible Anzeige-Spanne der Metrik (nur für die Band-Visualisierung).
 * Die Vorschau-Subjekte kommen aus echten Mock-Daten:
 *   vergleich → field auf MOCK_COMPARE_ROWS (Hochkönig-Orte loc-07…10)
 *   route     → samples[] (Etappen des KHW 403) */
const CORRIDOR_SEED = {
  vergleich: [
    { id: "snow",    label: "Schneehöhe",     unit: "cm",   scale: [0, 300], step: 5,  min: 80,   max: null, field: "snow",    note: "Mindestauflage Piste" },
    { id: "newSnow", label: "Neuschnee 24 h", unit: "cm",   scale: [0, 40],  step: 1,  min: 10,   max: null, field: "newSnow", note: "Pulver-Bonus" },
    { id: "wind",    label: "Wind (Mittel)",  unit: "km/h", scale: [0, 80],  step: 1,  min: null, max: 30,   field: "wind",    note: "Lift kritisch ab 50" },
    { id: "feels",   label: "Gefühlte Temp",  unit: "°C",   scale: [-20, 15],step: 1,  min: -8,   max: 2,    field: "feels",   note: "pulvrig & griffig" },
    { id: "sun",     label: "Sonnenstunden",  unit: "h",    scale: [0, 8],   step: 0.5,min: 3,    max: null, field: "sun",     note: "Komfort im Aufstieg" },
  ],
  route: [
    { id: "gust",    label: "Böen",           unit: "km/h", scale: [0, 120], step: 5,  min: null, max: 70,   note: "Grat-kritisch",
      samples: [{ label: "E2 · Filmoor", value: 52 }, { label: "E3 · Porze", value: 82 }, { label: "E4 · Öfner", value: 61 }] },
    { id: "thunder", label: "Gewitter",       unit: "%",    scale: [0, 100], step: 5,  min: null, max: 40,   note: "Abbruch bei Gewitter",
      samples: [{ label: "E2 · Filmoor", value: 15 }, { label: "E3 · Porze", value: 60 }, { label: "E4 · Öfner", value: 25 }] },
    { id: "precip",  label: "Niederschlag",   unit: "mm/h", scale: [0, 20],  step: 1,  min: null, max: 5,    note: "Nässe / Rutschgefahr",
      samples: [{ label: "E2 · Filmoor", value: 1 }, { label: "E3 · Porze", value: 7 }, { label: "E4 · Öfner", value: 3 }] },
    { id: "tmin",    label: "Temperatur Min", unit: "°C",   scale: [-20, 20],step: 1,  min: -5,   max: null, note: "Frost-Grenze",
      samples: [{ label: "E2 · Filmoor", value: 2 }, { label: "E3 · Porze", value: -7 }, { label: "E4 · Öfner", value: -2 }] },
    { id: "vis",     label: "Sichtweite",     unit: "km",   scale: [0, 20],  step: 1,  min: 1,    max: null, note: "Orientierung am Grat",
      samples: [{ label: "E2 · Filmoor", value: 12 }, { label: "E3 · Porze", value: 6 }, { label: "E4 · Öfner", value: 1 }] },
  ],
};

/* Nachschub-Pool für „+ Metrik" (nicht bereits gesetzte Metriken). */
const CORRIDOR_POOL = {
  vergleich: [
    { id: "cloud", label: "Bewölkung", unit: "%", scale: [0, 100], step: 5, min: null, max: 40, field: "cloud", note: "je klarer je besser" },
    { id: "tempMax", label: "Temperatur Max", unit: "°C", scale: [-15, 20], step: 1, min: null, max: 4, field: "tempMax", note: "Sulz vermeiden" },
  ],
  route: [
    { id: "snowfall", label: "Schneefallgrenze", unit: "m", scale: [500, 3000], step: 100, min: 1500, max: null, note: "Schnee statt Regen",
      samples: [{ label: "E2 · Filmoor", value: 2100 }, { label: "E3 · Porze", value: 1300 }, { label: "E4 · Öfner", value: 1900 }] },
    { id: "cape", label: "CAPE (Energie)", unit: "J/kg", scale: [0, 2000], step: 100, min: null, max: 500, note: "Gewitter-Potenzial",
      samples: [{ label: "E2 · Filmoor", value: 200 }, { label: "E3 · Porze", value: 900 }, { label: "E4 · Öfner", value: 400 }] },
  ],
};

/* ════════════════════ CorridorBand — dual-handle Range mit offenen Enden ════════════════════ */
function CorridorBand({ scale, step, min, max, notify, mark, onChange }) {
  const trackRef = React.useRef(null);
  const [drag, setDrag] = React.useState(null); // "min" | "max" | null
  const [lo, hi] = scale;
  const span = hi - lo || 1;
  const pos = (v) => Math.max(0, Math.min(1, (v - lo) / span));
  const valAt = (clientX) => {
    const el = trackRef.current;
    if (!el) return lo;
    const r = el.getBoundingClientRect();
    const t = Math.max(0, Math.min(1, (clientX - r.left) / (r.width || 1)));
    const raw = lo + t * span;
    return Math.round(raw / step) * step;
  };

  React.useEffect(() => {
    if (!drag) return;
    const move = (e) => {
      const cx = e.touches ? e.touches[0].clientX : e.clientX;
      let v = valAt(cx);
      if (drag === "min") { if (max != null) v = Math.min(v, max); onChange({ min: v }); }
      else                { if (min != null) v = Math.max(v, min); onChange({ max: v }); }
    };
    const up = () => setDrag(null);
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, [drag, min, max]);

  const left  = min != null ? pos(min) : 0;
  const right = max != null ? pos(max) : 1;
  const fillColor = mark ? "var(--g-good)" : notify ? "var(--g-ink-3)" : "var(--g-ink-3)";
  const outsideTint = notify ? "rgba(192,138,26,0.14)" : "transparent";

  const Handle = ({ side, value }) => (
    <div
      onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); setDrag(side); }}
      style={{
        position: "absolute", top: "50%", left: `${pos(value) * 100}%`,
        width: 16, height: 16, marginLeft: -8, marginTop: -8, borderRadius: "50%",
        background: "#fff", border: `2px solid ${mark ? "var(--g-good)" : "var(--g-accent)"}`,
        boxShadow: "var(--g-shadow-1)", cursor: "ew-resize", touchAction: "none",
        zIndex: 3,
      }}
    />
  );

  return (
    <div>
      <div ref={trackRef} style={{ position: "relative", height: 10, marginTop: 8, marginBottom: 8 }}>
        {/* Grund-Track + Warn-Schraffur außerhalb */}
        <div style={{ position: "absolute", inset: 0, borderRadius: 5, background: "var(--g-rule-soft)", overflow: "hidden" }}>
          {min != null && <div style={{ position: "absolute", top: 0, bottom: 0, left: 0, width: `${left * 100}%`, background: outsideTint }}/>}
          {max != null && <div style={{ position: "absolute", top: 0, bottom: 0, right: 0, width: `${(1 - right) * 100}%`, background: outsideTint }}/>}
        </div>
        {/* Korridor-Füllung */}
        <div style={{
          position: "absolute", top: 0, bottom: 0, left: `${left * 100}%`, width: `${(right - left) * 100}%`,
          background: fillColor, opacity: mark ? 0.85 : 0.4, borderRadius: 5,
        }}/>
        {/* offene-Enden-Marker */}
        {min == null && <span className="mono" style={{ position: "absolute", left: 2, top: -18, fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>◂ offen</span>}
        {max == null && <span className="mono" style={{ position: "absolute", right: 2, top: -18, fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>offen ▸</span>}
        {min != null && <Handle side="min" value={min}/>}
        {max != null && <Handle side="max" value={max}/>}
      </div>
      <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.03em" }}>
        <span>{corridorFmt(lo, "")}</span>
        <span>{corridorFmt(hi, "")}</span>
      </div>
    </div>
  );
}

/* ─── Numerische Grenzen mit „offen"-Toggle je Ende ─── */
function CorridorBound({ side, value, unit, scale, step, onChange }) {
  const isOpen = value == null;
  const label = side === "min" ? "Von" : "Bis";
  const fallback = side === "min" ? scale[0] + (scale[1] - scale[0]) * 0.25 : scale[0] + (scale[1] - scale[0]) * 0.75;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", width: 22 }}>{label}</span>
      {isOpen ? (
        <button onClick={() => onChange(Math.round(fallback / step) * step)} style={{
          fontFamily: "var(--g-font-mono)", fontSize: 11.5, padding: "4px 8px", cursor: "pointer",
          background: "transparent", border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-2)",
          color: "var(--g-ink-4)", whiteSpace: "nowrap",
        }}>offen · + Grenze</button>
      ) : (
        <div style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
          <input type="number" value={value} step={step}
            onChange={(e) => onChange(e.target.value === "" ? null : Number(e.target.value))}
            style={{
              width: 58, padding: "4px 6px", textAlign: "right",
              fontFamily: "var(--g-font-mono)", fontVariantNumeric: "tabular-nums", fontSize: 12,
              border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", background: "var(--g-card)", color: "var(--g-ink)",
            }}/>
          <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", width: 30 }}>{unit}</span>
          <button title="Grenze öffnen" onClick={() => onChange(null)} style={{
            border: "none", background: "transparent", cursor: "pointer", color: "var(--g-ink-4)", fontSize: 13, padding: 2, lineHeight: 1,
          }}>×</button>
        </div>
      )}
    </div>
  );
}

/* ─── Wirkungs-Toggle (Warnen / Markieren) ─── */
function CorridorEffect({ kind, on, onToggle }) {
  const conf = kind === "notify"
    ? { label: "Warnen", tone: "var(--g-warn)", tint: "rgba(192,138,26,0.12)" }
    : { label: "Markieren", tone: "var(--g-good)", tint: "rgba(61,107,58,0.12)" };
  const glyph = kind === "notify"
    ? <path d="M6 9a6 6 0 0 1 12 0c0 5 2 6 2 6H4s2-1 2-6z M10 19a2 2 0 0 0 4 0"/>
    : <path d="M12 4l2.4 5.2L20 10l-4 3.8L17 20l-5-2.8L7 20l1-6.2L4 10l5.6-0.8z"/>;
  return (
    <button onClick={onToggle} aria-pressed={on} style={{
      display: "inline-flex", alignItems: "center", gap: 6, padding: "5px 10px",
      borderRadius: "var(--g-r-pill)", cursor: "pointer", whiteSpace: "nowrap",
      fontFamily: "var(--g-font-sans)", fontSize: 12, fontWeight: 600,
      background: on ? conf.tint : "transparent",
      color: on ? conf.tone : "var(--g-ink-4)",
      border: `1px solid ${on ? conf.tone : "var(--g-rule)"}`,
    }}>
      <svg width="13" height="13" viewBox="0 0 24 24" fill={kind === "mark" && on ? conf.tone : "none"}
        stroke={conf.tone} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round"
        style={{ opacity: on ? 1 : 0.55 }}>{glyph}</svg>
      {conf.label}
    </button>
  );
}

/* ─── Live-Vorschau je Zeile: reale Subjekte, grün wenn im Korridor ─── */
function CorridorPreviewChips({ subjects, unit }) {
  if (!subjects || subjects.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {subjects.map((s, i) => {
        const st = s.inside;                       // true | false | null
        const bg = st === true ? "rgba(61,107,58,0.10)" : st === false ? "rgba(192,138,26,0.10)" : "var(--g-card-alt)";
        const fg = st === true ? "var(--g-good)" : st === false ? "#8a6210" : "var(--g-ink-3)";
        const bd = st === true ? "rgba(61,107,58,0.35)" : st === false ? "rgba(192,138,26,0.35)" : "var(--g-rule-soft)";
        return (
          <span key={i} className="mono" style={{
            display: "inline-flex", alignItems: "center", gap: 5, padding: "3px 8px",
            borderRadius: "var(--g-r-pill)", background: bg, color: fg, border: `1px solid ${bd}`,
            fontSize: 10.5, letterSpacing: "0.02em", fontVariantNumeric: "tabular-nums",
          }}>
            <span style={{ color: "var(--g-ink-4)" }}>{s.label}</span>
            <strong style={{ fontWeight: 600 }}>{corridorFmt(s.value, unit)}</strong>
            {st === true && <span aria-hidden>✓</span>}
            {st === false && <span aria-hidden>▲</span>}
          </span>
        );
      })}
    </div>
  );
}

/* ─── Eine Korridor-Zeile ─── */
function CorridorRow({ metric, subjects, isLast, onChange, onRemove }) {
  const { unit, scale, step, min, max, notify, mark } = metric;
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "190px 1fr 224px", gap: 22,
      padding: "18px 20px", alignItems: "start",
      borderBottom: isLast ? "none" : "1px solid var(--g-rule-soft)",
    }}>
      {/* Metrik + Vorschau */}
      <div style={{ minWidth: 0 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 6 }}>
          <span style={{ fontSize: 14, fontWeight: 600, color: "var(--g-ink)" }}>{metric.label}</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{unit}</span>
        </div>
        {metric.note && <div style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 2, fontStyle: "italic" }}>{metric.note}</div>}
        <div style={{ marginTop: 12 }}>
          <CorridorPreviewChips subjects={subjects} unit={unit}/>
        </div>
      </div>

      {/* Band + numerische Grenzen */}
      <div>
        <CorridorBand scale={scale} step={step} min={min} max={max} notify={notify} mark={mark}
          onChange={(patch) => onChange({ ...patch })}/>
        <div style={{ display: "flex", gap: 16, marginTop: 12, flexWrap: "wrap" }}>
          <CorridorBound side="min" value={min} unit={unit} scale={scale} step={step} onChange={(v) => onChange({ min: v })}/>
          <CorridorBound side="max" value={max} unit={unit} scale={scale} step={step} onChange={(v) => onChange({ max: v })}/>
        </div>
      </div>

      {/* Wirkungen */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, alignItems: "flex-start" }}>
        <div style={{ display: "flex", gap: 6 }}>
          <CorridorEffect kind="notify" on={notify} onToggle={() => onChange({ notify: !notify })}/>
          <CorridorEffect kind="mark"   on={mark}   onToggle={() => onChange({ mark: !mark })}/>
        </div>
        <button onClick={onRemove} style={{
          background: "transparent", border: "none", padding: "2px 0", cursor: "pointer",
          color: "var(--g-ink-4)", fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.04em",
        }}>✕ entfernen</button>
      </div>
    </div>
  );
}

/* ════════════════════ CorridorEditor — DER Organism ════════════════════
 *  Props:
 *    context   "route" | "vergleich"  (setzt Copy + Wirkungs-Defaults)
 *    profileLabel  optional — Anzeige im Header
 */
function CorridorEditor({ context = "route", profileLabel }) {
  const ctx = CORRIDOR_CTX[context] || CORRIDOR_CTX.route;
  const seed = CORRIDOR_SEED[context] || [];
  const pool = CORRIDOR_POOL[context] || [];

  const [rows, setRows] = React.useState(() => seed.map(m => ({
    ...m, notify: ctx.defaultNotify, mark: ctx.defaultMark,
    // Trip-Beispiel: Böen/Gewitter/Niederschlag warnen; im Vergleich alle markieren
  })));
  const [poolLeft, setPoolLeft] = React.useState(pool);

  const patchRow = (id, patch) => setRows(rs => rs.map(r => r.id === id ? { ...r, ...patch } : r));
  const removeRow = (id) => setRows(rs => rs.filter(r => r.id !== id));
  const addRow = (m) => {
    setRows(rs => [...rs, { ...m, notify: ctx.defaultNotify, mark: ctx.defaultMark }]);
    setPoolLeft(p => p.filter(x => x.id !== m.id));
  };

  /* Subjekte je Zeile (Live-Vorschau, C5) */
  const compareRows = window.MOCK_COMPARE_ROWS || [];
  const locations = window.MOCK_LOCATIONS || [];
  const hochkoenig = ["loc-07", "loc-08", "loc-09", "loc-10"];
  const shortName = (id) => {
    const l = locations.find(x => x.id === id);
    if (!l) return id;
    const p = l.name.split("/");
    return (p.length > 1 ? p[p.length - 1] : l.name).trim();
  };
  const subjectsFor = (m) => {
    let raw = [];
    if (context === "vergleich" && m.field) {
      raw = hochkoenig.map(id => {
        const row = compareRows.find(r => r.id === id) || {};
        return { label: shortName(id), value: row[m.field] };
      });
    } else if (m.samples) {
      raw = m.samples;
    }
    return raw.map(s => ({ ...s, inside: corridorInside(s.value, m.min, m.max) }));
  };

  const notifyN = rows.filter(r => r.notify).length;
  const markN   = rows.filter(r => r.mark).length;

  return (
    <div style={{ position: "relative", padding: "28px 40px 60px", maxWidth: 1040 }}>
      <TopoBg opacity={0.06}/>
      <div style={{ position: "relative" }}>
        <Eyebrow>{ctx.eyebrow}{profileLabel ? ` · ${profileLabel}` : ""}</Eyebrow>
        <h2 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.01em", margin: "6px 0 8px" }}>{ctx.title}</h2>
        <div style={{ fontSize: 13.5, color: "var(--g-ink-2)", lineHeight: 1.55, maxWidth: 680, marginBottom: 20 }}>{ctx.lead}</div>

        {/* Legende: eine Zone, zwei Wirkungen */}
        <div style={{
          display: "flex", flexWrap: "wrap", gap: 18, alignItems: "center",
          padding: "12px 16px", marginBottom: 20,
          background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-3)",
        }}>
          <span className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--g-ink-4)" }}>So liest sich ein Wertebereich</span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--g-ink-2)" }}>
            <span style={{ width: 22, height: 8, borderRadius: 4, background: "var(--g-good)", opacity: 0.85, display: "inline-block" }}/>
            im Bereich = <strong style={{ color: "var(--g-good)" }}>markiert</strong>
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--g-ink-2)" }}>
            <span style={{ width: 22, height: 8, borderRadius: 4, background: "rgba(192,138,26,0.28)", display: "inline-block" }}/>
            außerhalb = <strong style={{ color: "#8a6210" }}>Warnung</strong>
          </span>
          <span style={{ fontSize: 12, color: "var(--g-ink-3)" }}>Beide Wirkungen je Metrik frei kombinierbar.</span>
        </div>

        {/* Tabelle */}
        <Card padding={0}>
          <div style={{
            display: "grid", gridTemplateColumns: "190px 1fr 224px", gap: 22,
            padding: "10px 20px", background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule)",
          }}>
            <Eyebrow style={{ margin: 0 }}>Metrik · {ctx.subjectLabel} live</Eyebrow>
            <Eyebrow style={{ margin: 0 }}>Wertebereich</Eyebrow>
            <Eyebrow style={{ margin: 0 }}>Wirkung</Eyebrow>
          </div>
          {rows.map((m, i) => (
            <CorridorRow key={m.id} metric={m} subjects={subjectsFor(m)} isLast={i === rows.length - 1 && poolLeft.length === 0}
              onChange={(patch) => patchRow(m.id, patch)} onRemove={() => removeRow(m.id)}/>
          ))}
          {poolLeft.length > 0 && (
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", padding: "14px 20px", borderTop: "1px dashed var(--g-rule-soft)" }}>
              <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>Metrik hinzufügen:</span>
              {poolLeft.map(m => (
                <Btn key={m.id} variant="ghost" size="sm" onClick={() => addRow(m)}>＋ {m.label}</Btn>
              ))}
            </div>
          )}
        </Card>

        {/* Zusammenfassung + Neutralitäts-Guard */}
        <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 16, flexWrap: "wrap" }}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--g-ink-2)" }}>
            <Dot tone="warn"/> {notifyN} × Warnen
          </span>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--g-ink-2)" }}>
            <Dot tone="good"/> {markN} × Markieren
          </span>
          {ctx.neutral && (
            <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", letterSpacing: "0.03em" }}>
              · kein Score · kein Rang · Wertebereiche markieren nur, sie sortieren nicht
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

/* ════════════════════ CompareEndDateControl — Laufzeit (E8/C3) ════════════════════
 *  Ersetzt den festen „kein Enddatum"-Hinweis im Compare-Versand-Tab.
 *  „bis auf Weiteres" (null) | „bis Datum" (danach Auto-Pause, kein Löschen). */
function CompareEndDateControl({ value, onChange }) {
  const [mode, setMode] = React.useState(value ? "date" : "open");
  const [date, setDate] = React.useState(value || "");
  const set = (m) => { setMode(m); onChange && onChange(m === "date" ? date : null); };
  return (
    <div>
      <Eyebrow style={{ marginBottom: 12 }}>Laufzeit</Eyebrow>
      <div style={{ display: "flex", gap: 16, alignItems: "flex-start", flexWrap: "wrap" }}>
        <Segmented
          items={[{ id: "open", label: "Bis auf Weiteres" }, { id: "date", label: "Bis Datum" }]}
          value={mode} onChange={set}
        />
        {mode === "date" && (
          <StageDateField value={date} onChange={(v) => { setDate(v); onChange && onChange(v); }}/>
        )}
      </div>
      <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 12, lineHeight: 1.5, maxWidth: 560 }}>
        {mode === "date"
          ? "Nach diesem Datum pausiert der Vergleich automatisch — er wird nicht gelöscht und nicht archiviert. Du kannst ihn jederzeit wieder aktivieren."
          : "Der Vergleich läuft als stehender Monitor weiter, bis du ihn pausierst."}
      </div>
    </div>
  );
}

/* ════════════════════ AlertChannelPicker — Alert-Kanäle (getrennt vom Briefing) ════════════════════
 *  Geteilter Selektor für den notify-Zustellstrom. EINE Definition für beide
 *  Editoren + Desktop/Mobile (dense). Baut auf dem Molecule ChannelRow.
 *
 *  Warum getrennt (PO 2026-07-11): das geplante Briefing ist eine Tabelle →
 *  faktisch E-Mail (Telegram cappt bei 8 Spalten, SMS flach). Alerts sind kurze
 *  Ein-Fakt-Meldungen → Telegram/SMS ideal (sofortiger Push). Default hier:
 *  Telegram + SMS an, E-Mail aus. Datenmodell: neues Feld `alertChannels[]`.
 *
 *  props: dense? (Mobile-Layout) · defaults? ({email,telegram,sms}) */
const ALERT_CHANNEL_TARGETS = { email: "gregor_zwanzig@henemm.com", telegram: "@henemm", sms: "+49 151 12345 678" };
function AlertChannelPicker({ dense = false, defaults }) {
  const [on, setOn] = React.useState(defaults || { email: false, telegram: true, sms: true });
  const toggle = (k) => setOn(s => ({ ...s, [k]: !s[k] }));
  const activeN = Object.values(on).filter(Boolean).length;
  return (
    <div>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 12, marginBottom: 6 }}>
        <Eyebrow style={{ margin: 0 }}>Alert-Kanäle</Eyebrow>
        <span className="mono" style={{ fontSize: 10, color: activeN ? "var(--g-ink-4)" : "var(--g-warn)", letterSpacing: "0.03em" }}>
          {activeN ? `${activeN} aktiv` : "kein Kanal — Alerts gehen nirgends hin"}
        </span>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: dense ? 8 : 10 }}>
        Alerts sind kurze Sofort-Meldungen — <strong style={{ color: "var(--g-ink-2)" }}>Telegram/SMS</strong> sind dafür ideal.
        Das geplante Briefing (die Tabelle) läuft davon getrennt weiter über seine eigenen Kanäle.
      </div>
      <Card padding={0}>
        <div style={{ padding: dense ? "2px 14px" : "4px 18px" }}>
          <ChannelRow kind="Telegram" target={ALERT_CHANNEL_TARGETS.telegram} active={on.telegram} onToggle={() => toggle("telegram")} sub="sofortiger Push" dense/>
          <ChannelRow kind="SMS"      target={ALERT_CHANNEL_TARGETS.sms}      active={on.sms}      onToggle={() => toggle("sms")}      sub="sofort · ≤ 140 Z." dense/>
          <ChannelRow kind="Email"    target={ALERT_CHANNEL_TARGETS.email}    active={on.email}    onToggle={() => toggle("email")}    sub="optional · langsamer als Push" dense last/>
        </div>
      </Card>
    </div>
  );
}

/* ─── Export ─── */
Object.assign(window, {
  corridorInside, corridorFmt,
  CorridorBand, CorridorBound, CorridorEffect, CorridorPreviewChips, CorridorRow,
  CorridorEditor, CompareEndDateControl, AlertChannelPicker,
  CORRIDOR_CTX, CORRIDOR_SEED, CORRIDOR_POOL,
});
