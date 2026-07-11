/* ════════════════════════════════════════════════════════════════════════
 *  corridor-editor-mobile.jsx  —  Mobile-Spiegel des Korridor-Editors (375 px)
 * ════════════════════════════════════════════════════════════════════════
 *
 *  Desktop-Pendant: corridor-editor.jsx (CorridorEditor). Diese Datei ist
 *  KEIN Fork — Daten + Match-Logik kommen aus dem Desktop-Organism:
 *      corridorInside · corridorFmt · CORRIDOR_CTX · CORRIDOR_SEED · CORRIDOR_POOL
 *  Nur das Layout ist mobil neu: eine Card je Metrik statt Tabellen-Grid,
 *  Touch ≥ 44 px, Stepper statt Mini-Number-Inputs, 16 px Eingaben.
 *
 *  Prefix CM_ (Babel-Scope-Disziplin, CLAUDE.md · M* wäre Mobile-Atom-Namespace,
 *  daher CM_ für Compare/Corridor-Mobile-Helfer). Nutzt mobile-shell (MBtn,
 *  ScreenScroll) + Atoms (Eyebrow, Dot).
 *  Export: window.CorridorEditorMobile · window.CompareEndDateControlMobile
 * ──────────────────────────────────────────────────────────────────────── */

/* ─── Touch-Band: dual-handle mit offenen Enden (mobile-eigene Geometrie) ─── */
function CM_Band({ scale, step, min, max, notify, mark, onChange }) {
  const trackRef = React.useRef(null);
  const [drag, setDrag] = React.useState(null);
  const [lo, hi] = scale;
  const span = hi - lo || 1;
  const pos = (v) => Math.max(0, Math.min(1, (v - lo) / span));
  const valAt = (clientX) => {
    const el = trackRef.current;
    if (!el) return lo;
    const r = el.getBoundingClientRect();
    const t = Math.max(0, Math.min(1, (clientX - r.left) / (r.width || 1)));
    return Math.round((lo + t * span) / step) * step;
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
  const fill  = mark ? "var(--g-good)" : "var(--g-ink-3)";
  const outsideTint = notify ? "rgba(192,138,26,0.16)" : "transparent";

  const Handle = ({ side, value }) => (
    <div onPointerDown={(e) => { e.currentTarget.setPointerCapture?.(e.pointerId); setDrag(side); }}
      style={{
        position: "absolute", top: "50%", left: `${pos(value) * 100}%`,
        width: 24, height: 24, marginLeft: -12, marginTop: -12, borderRadius: "50%",
        background: "#fff", border: `2px solid ${mark ? "var(--g-good)" : "var(--g-accent)"}`,
        boxShadow: "var(--g-shadow-1)", cursor: "ew-resize", touchAction: "none", zIndex: 3,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: mark ? "var(--g-good)" : "var(--g-accent)" }}/>
    </div>
  );

  return (
    <div>
      <div ref={trackRef} style={{ position: "relative", height: 14, marginTop: 22, marginBottom: 8 }}>
        <div style={{ position: "absolute", inset: 0, borderRadius: 7, background: "var(--g-rule-soft)", overflow: "hidden" }}>
          {min != null && <div style={{ position: "absolute", top: 0, bottom: 0, left: 0, width: `${left * 100}%`, background: outsideTint }}/>}
          {max != null && <div style={{ position: "absolute", top: 0, bottom: 0, right: 0, width: `${(1 - right) * 100}%`, background: outsideTint }}/>}
        </div>
        <div style={{ position: "absolute", top: 0, bottom: 0, left: `${left * 100}%`, width: `${(right - left) * 100}%`, background: fill, opacity: mark ? 0.85 : 0.4, borderRadius: 7 }}/>
        {min == null && <span className="mono" style={{ position: "absolute", left: 2, top: -18, fontSize: 10, color: "var(--g-ink-4)" }}>◂ offen</span>}
        {max == null && <span className="mono" style={{ position: "absolute", right: 2, top: -18, fontSize: 10, color: "var(--g-ink-4)" }}>offen ▸</span>}
        {min != null && <Handle side="min" value={min}/>}
        {max != null && <Handle side="max" value={max}/>}
      </div>
      <div className="mono" style={{ display: "flex", justifyContent: "space-between", fontSize: 10, color: "var(--g-ink-4)" }}>
        <span>{corridorFmt(lo, "")}</span><span>{corridorFmt(hi, "")}</span>
      </div>
    </div>
  );
}

/* ─── Touch-Grenze: Stepper (−/+) statt Tastatur-Input ─── */
function CM_Bound({ side, value, unit, scale, step, min, max, onChange }) {
  const label = side === "min" ? "Von" : "Bis";
  const open = value == null;
  const [lo, hi] = scale;
  const fallback = side === "min" ? lo + (hi - lo) * 0.25 : lo + (hi - lo) * 0.75;
  const clampV = (v) => {
    v = Math.round(v / step) * step;
    v = Math.max(lo, Math.min(hi, v));
    if (side === "min" && max != null) v = Math.min(v, max);
    if (side === "max" && min != null) v = Math.max(v, min);
    return v;
  };
  const nudge = (d) => onChange(clampV((value ?? fallback) + d * step));

  const StepBtn = ({ children, onTap }) => (
    <button onClick={onTap} style={{
      width: 40, height: 40, flexShrink: 0, border: "1px solid var(--g-rule)", background: "var(--g-card)",
      borderRadius: "var(--g-r-2)", cursor: "pointer", color: "var(--g-ink)", fontSize: 20, lineHeight: 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center", fontFamily: "var(--g-font-mono)",
    }}>{children}</button>
  );

  return (
    <div style={{ flex: 1, minWidth: 0 }}>
      <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 5 }}>{label}</div>
      {open ? (
        <button onClick={() => onChange(clampV(fallback))} style={{
          width: "100%", minHeight: 40, border: "1px dashed var(--g-rule)", background: "transparent",
          borderRadius: "var(--g-r-2)", cursor: "pointer", color: "var(--g-ink-4)",
          fontFamily: "var(--g-font-mono)", fontSize: 12, letterSpacing: "0.02em",
        }}>offen · + Grenze</button>
      ) : (
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <StepBtn onTap={() => nudge(-1)}>−</StepBtn>
          <div style={{ flex: 1, minWidth: 0, textAlign: "center", padding: "0 2px" }}>
            <div className="mono" style={{ fontSize: 16, fontWeight: 600, color: "var(--g-ink)", fontVariantNumeric: "tabular-nums", lineHeight: 1.1 }}>{value}</div>
            <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)" }}>{unit}</div>
          </div>
          <StepBtn onTap={() => nudge(1)}>+</StepBtn>
          <button title="Grenze öffnen" onClick={() => onChange(null)} style={{
            width: 30, height: 40, border: "none", background: "transparent", cursor: "pointer",
            color: "var(--g-ink-4)", fontSize: 15,
          }}>×</button>
        </div>
      )}
    </div>
  );
}

/* ─── Wirkungs-Toggle (Touch, ≥ 44 px) ─── */
function CM_Effect({ kind, on, onToggle }) {
  const conf = kind === "notify"
    ? { label: "Warnen", tone: "var(--g-warn)", tint: "rgba(192,138,26,0.12)", fg: "#8a6210" }
    : { label: "Markieren", tone: "var(--g-good)", tint: "rgba(61,107,58,0.12)", fg: "var(--g-good)" };
  return (
    <button onClick={onToggle} aria-pressed={on} style={{
      flex: 1, display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 8,
      minHeight: 44, padding: "0 12px", borderRadius: "var(--g-r-3)", cursor: "pointer",
      fontFamily: "var(--g-font-sans)", fontSize: 14, fontWeight: 600,
      background: on ? conf.tint : "transparent",
      color: on ? conf.fg : "var(--g-ink-4)",
      border: `1px solid ${on ? conf.tone : "var(--g-rule)"}`,
    }}>
      <span style={{
        width: 16, height: 16, flexShrink: 0, borderRadius: kind === "notify" ? 3 : "50%",
        background: on ? conf.tone : "transparent", border: on ? "none" : "1.5px solid var(--g-rule)",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
      }}>
        {on && <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="2.4"><path d="M2 6l3 3 5-6"/></svg>}
      </span>
      {conf.label}
    </button>
  );
}

/* ─── Live-Vorschau-Chips (Orte/Etappen · grün wenn im Korridor) ─── */
function CM_PreviewChips({ subjects, unit }) {
  if (!subjects || subjects.length === 0) return null;
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
      {subjects.map((s, i) => {
        const st = s.inside;
        const bg = st === true ? "rgba(61,107,58,0.10)" : st === false ? "rgba(192,138,26,0.10)" : "var(--g-card-alt)";
        const fg = st === true ? "var(--g-good)" : st === false ? "#8a6210" : "var(--g-ink-3)";
        const bd = st === true ? "rgba(61,107,58,0.35)" : st === false ? "rgba(192,138,26,0.35)" : "var(--g-rule-soft)";
        return (
          <span key={i} className="mono" style={{
            display: "inline-flex", alignItems: "center", gap: 5, padding: "4px 9px", borderRadius: "var(--g-r-pill)",
            background: bg, color: fg, border: `1px solid ${bd}`, fontSize: 11, fontVariantNumeric: "tabular-nums",
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

/* ─── Eine Korridor-Card ─── */
function CM_Card({ metric, subjects, onChange, onRemove }) {
  const { unit, scale, step, min, max, notify, mark } = metric;
  return (
    <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", padding: "14px 14px 12px", marginBottom: 10 }}>
      {/* Kopf: Metrik + Bereich */}
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
        <div style={{ minWidth: 0 }}>
          <span style={{ fontSize: 15, fontWeight: 600, color: "var(--g-ink)" }}>{metric.label}</span>
          <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginLeft: 6 }}>{unit}</span>
        </div>
        <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)", fontVariantNumeric: "tabular-nums", whiteSpace: "nowrap" }}>
          {KE_rangeLabelMobile(min, max, unit)}
        </span>
      </div>
      {metric.note && <div style={{ fontSize: 11.5, color: "var(--g-ink-4)", marginTop: 2, fontStyle: "italic" }}>{metric.note}</div>}

      {/* Band */}
      <div style={{ marginTop: 4 }}>
        <CM_Band scale={scale} step={step} min={min} max={max} notify={notify} mark={mark} onChange={(patch) => onChange(patch)}/>
      </div>

      {/* Grenzen-Stepper */}
      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <CM_Bound side="min" value={min} unit={unit} scale={scale} step={step} min={min} max={max} onChange={(v) => onChange({ min: v })}/>
        <CM_Bound side="max" value={max} unit={unit} scale={scale} step={step} min={min} max={max} onChange={(v) => onChange({ max: v })}/>
      </div>

      {/* Wirkungen */}
      <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
        <CM_Effect kind="notify" on={notify} onToggle={() => onChange({ notify: !notify })}/>
        <CM_Effect kind="mark"   on={mark}   onToggle={() => onChange({ mark: !mark })}/>
      </div>

      {/* Vorschau */}
      {subjects && subjects.length > 0 && (
        <div style={{ marginTop: 12, paddingTop: 12, borderTop: "1px solid var(--g-rule-soft)" }}>
          <CM_PreviewChips subjects={subjects} unit={unit}/>
        </div>
      )}

      {/* Entfernen */}
      <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 8 }}>
        <button onClick={onRemove} style={{ background: "transparent", border: "none", padding: "6px 2px", color: "var(--g-ink-4)", cursor: "pointer", fontSize: 11.5, fontFamily: "var(--g-font-mono)", letterSpacing: "0.04em" }}>✕ entfernen</button>
      </div>
    </div>
  );
}

/* Mobile-Bereichslabel (kompakt · nutzt corridorFmt für Vorzeichen). */
function KE_rangeLabelMobile(min, max, unit) {
  const f = (v) => corridorFmt(v, unit);
  if (min != null && max != null) return `${corridorFmt(min, "")} … ${f(max)}`;
  if (min != null) return `≥ ${f(min)}`;
  if (max != null) return `≤ ${f(max)}`;
  return "offen";
}

/* ════════════════════ CorridorEditorMobile — DER Mobile-Organism ════════════════════ */
function CorridorEditorMobile({ context = "route", profileLabel, footer }) {
  const ctx = (window.CORRIDOR_CTX || {})[context] || {};
  const seed = (window.CORRIDOR_SEED || {})[context] || [];
  const pool = (window.CORRIDOR_POOL || {})[context] || [];

  const [rows, setRows] = React.useState(() => seed.map(m => ({ ...m, notify: ctx.defaultNotify, mark: ctx.defaultMark })));
  const [poolLeft, setPoolLeft] = React.useState(pool);

  const patchRow = (id, patch) => setRows(rs => rs.map(r => r.id === id ? { ...r, ...patch } : r));
  const removeRow = (id) => setRows(rs => rs.filter(r => r.id !== id));
  const addRow = (m) => { setRows(rs => [...rs, { ...m, notify: ctx.defaultNotify, mark: ctx.defaultMark }]); setPoolLeft(p => p.filter(x => x.id !== m.id)); };

  /* Subjekte je Zeile (Live-Vorschau, C5 — identisch zum Desktop). */
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
      raw = hochkoenig.map(id => { const row = compareRows.find(r => r.id === id) || {}; return { label: shortName(id), value: row[m.field] }; });
    } else if (m.samples) { raw = m.samples; }
    return raw.map(s => ({ ...s, inside: corridorInside(s.value, m.min, m.max) }));
  };

  const notifyN = rows.filter(r => r.notify).length;
  const markN   = rows.filter(r => r.mark).length;

  return (
    <ScreenScroll padding={14}>
      <Eyebrow style={{ marginBottom: 4 }}>{ctx.eyebrow}{profileLabel ? ` · ${profileLabel}` : ""}</Eyebrow>
      <div style={{ fontSize: 19, fontWeight: 600, letterSpacing: "-0.01em", lineHeight: 1.2, marginBottom: 6 }}>{ctx.title}</div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.5, marginBottom: 14 }}>{ctx.lead}</div>

      {/* Legende */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, padding: "12px 14px", marginBottom: 14, background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-3)" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 9, fontSize: 12.5, color: "var(--g-ink-2)" }}>
          <span style={{ width: 24, height: 9, borderRadius: 4, background: "var(--g-good)", opacity: 0.85, flexShrink: 0 }}/>
          im Bereich = <strong style={{ color: "var(--g-good)" }}>markiert</strong>
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 9, fontSize: 12.5, color: "var(--g-ink-2)" }}>
          <span style={{ width: 24, height: 9, borderRadius: 4, background: "rgba(192,138,26,0.28)", flexShrink: 0 }}/>
          außerhalb = <strong style={{ color: "#8a6210" }}>Warnung</strong>
        </span>
      </div>

      {/* Cards */}
      {rows.map(m => (
        <CM_Card key={m.id} metric={m} subjects={subjectsFor(m)} onChange={(patch) => patchRow(m.id, patch)} onRemove={() => removeRow(m.id)}/>
      ))}

      {/* Metrik hinzufügen */}
      {poolLeft.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 4, marginBottom: 6 }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase" }}>Metrik hinzufügen</div>
          {poolLeft.map(m => (
            <MBtn key={m.id} block variant="ghost" size="lg" onClick={() => addRow(m)}>＋ {m.label}</MBtn>
          ))}
        </div>
      )}

      {/* Zusammenfassung */}
      <div style={{ display: "flex", alignItems: "center", gap: 16, marginTop: 10, flexWrap: "wrap" }}>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--g-ink-2)" }}><Dot tone="warn"/> {notifyN} × Warnen</span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, fontSize: 12.5, color: "var(--g-ink-2)" }}><Dot tone="good"/> {markN} × Markieren</span>
      </div>
      {ctx.neutral && (
        <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 8, letterSpacing: "0.02em", lineHeight: 1.5 }}>
          kein Score · kein Rang · Wertebereiche markieren nur, sie sortieren nicht
        </div>
      )}
      {footer && <div style={{ marginTop: 22, paddingTop: 18, borderTop: "1px solid var(--g-rule-soft)" }}>{footer}</div>}
    </ScreenScroll>
  );
}

/* ════════════════════ CompareEndDateControlMobile — Laufzeit (E8/C3) ════════════════════ */
function CompareEndDateControlMobile({ value, onChange }) {
  const [mode, setMode] = React.useState(value ? "date" : "open");
  const [date, setDate] = React.useState(value || "2026-04-30");
  const wd = (typeof stageWeekdayDE === "function" && date) ? stageWeekdayDE(date) : null;
  const pick = (m) => { setMode(m); onChange && onChange(m === "date" ? date : null); };

  const Opt = ({ id, title, sub }) => {
    const on = mode === id;
    return (
      <button onClick={() => pick(id)} style={{
        width: "100%", textAlign: "left", cursor: "pointer", minHeight: 56,
        padding: "14px 14px", borderRadius: "var(--g-r-3)", marginBottom: 8,
        background: on ? "var(--g-accent-tint)" : "var(--g-card)",
        border: on ? "1.5px solid var(--g-accent)" : "1px solid var(--g-rule)",
        fontFamily: "var(--g-font-sans)",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <span style={{ width: 18, height: 18, borderRadius: "50%", flexShrink: 0, border: `1.5px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`, display: "inline-flex", alignItems: "center", justifyContent: "center" }}>
            {on && <span style={{ width: 9, height: 9, borderRadius: "50%", background: "var(--g-accent)" }}/>}
          </span>
          <span style={{ fontSize: 15, fontWeight: 600, color: on ? "var(--g-accent-deep)" : "var(--g-ink)" }}>{title}</span>
        </div>
        <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", lineHeight: 1.5, marginTop: 6, paddingLeft: 28 }}>{sub}</div>
      </button>
    );
  };

  return (
    <div style={{ fontFamily: "var(--g-font-sans)" }}>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.10em", textTransform: "uppercase", marginBottom: 10 }}>Laufzeit</div>
      <Opt id="open" title="Bis auf Weiteres" sub="Läuft, bis du pausierst."/>
      <Opt id="date" title="Bis Datum" sub="Zum Saisonende automatisch pausieren — kein Löschen."/>
      {mode === "date" && (
        <label style={{ display: "flex", alignItems: "center", gap: 10, background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", padding: "0 12px", minHeight: 52, cursor: "pointer", marginTop: 2 }}>
          {wd && <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: "var(--g-accent-deep)", background: "var(--g-accent-tint)", borderRadius: 3, padding: "4px 8px" }}>{wd}</span>}
          <input type="date" value={date} onChange={e => { setDate(e.target.value); onChange && onChange(e.target.value); }} className="mono"
            style={{ flex: 1, border: "none", outline: "none", background: "transparent", fontFamily: "var(--g-font-mono)", fontSize: 16, color: "var(--g-ink)", fontVariantNumeric: "tabular-nums", minHeight: 44 }}/>
        </label>
      )}
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 12, fontSize: 12.5, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
        <span style={{ width: 7, height: 7, borderRadius: "50%", background: mode === "date" ? "var(--g-warn)" : "var(--g-good)", flexShrink: 0 }}/>
        {mode === "date" ? "Danach Auto-Pause — erscheint pausiert im Hub, kein Datenverlust." : "Stehender Monitor — kein automatisches Ende."}
      </div>
    </div>
  );
}

/* ─── Export ─── */
Object.assign(window, {
  CM_Band, CM_Bound, CM_Effect, CM_PreviewChips, CM_Card,
  CorridorEditorMobile, CompareEndDateControlMobile,
});
