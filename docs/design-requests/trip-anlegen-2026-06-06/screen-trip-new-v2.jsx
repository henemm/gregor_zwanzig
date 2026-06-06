/* screen-trip-new-v2.jsx
 * ═══════════════════════════════════════════════════════════════════════
 *  Neue Tour anlegen — Progressive Tab Editor
 *  Prefix: TN_ — Babel-Scope-Disziplin (CLAUDE.md)
 *  Export:  window.ScreenTripNewV2
 * ═══════════════════════════════════════════════════════════════════════
 */

const TN_TAB_DEFS = [
  { id: "route",      label: "Route",              lockHint: null,                               optional: false },
  { id: "etappen",    label: "Etappen & GPX",       lockHint: "erst Tour-Name + Startdatum",      optional: false },
  { id: "wegpunkte",  label: "Wegpunkte prüfen",    lockHint: "erst alle GPX hochladen",          optional: true  },
  { id: "metriken",   label: "Wetter-Metriken",     lockHint: "erst alle GPX hochladen",          optional: false },
  { id: "zeitplan",   label: "Briefing-Zeitplan",   lockHint: "erst Wetter-Metriken öffnen",      optional: false },
  { id: "alerts",     label: "Alerts",              lockHint: "erst Zeitplan öffnen",             optional: false },
];

/* Wegpunkte + Wetter schalten gleichzeitig frei (beide nach allen GPX geladen).
 * Wegpunkte ist optional — User kann direkt zu Wetter springen. */
function TN_unlocked(name, startDate, etDone, wtVisited, ztVisited) {
  const s = new Set(["route"]);
  if (name.trim() && startDate) s.add("etappen");
  if (etDone) { s.add("wegpunkte"); s.add("metriken"); }
  if (wtVisited) s.add("zeitplan");
  if (ztVisited) s.add("alerts");
  return s;
}

function TN_doneSet(name, startDate, etDone, wtVisited, ztVisited) {
  const s = new Set();
  if (name.trim() && startDate) s.add("route");
  if (etDone) s.add("etappen");
  if (wtVisited) s.add("metriken");
  if (ztVisited) s.add("zeitplan");
  return s;
}

/* ─── Tab Bar ─── */
function TN_TabBar({ active, unlocked, done, onChange }) {
  const [flash, setFlash] = React.useState(null);
  const handleClick = (id) => {
    if (unlocked.has(id)) { onChange(id); }
    else { setFlash(id); setTimeout(() => setFlash(null), 500); }
  };
  return (
    <div style={{
      borderBottom: "1px solid var(--g-rule)",
      padding: "0 40px", display: "flex", gap: 0, overflowX: "auto",
    }}>
      {TN_TAB_DEFS.map((t) => {
        const on   = t.id === active;
        const open = unlocked.has(t.id);
        const isDone = done.has(t.id) && !on;
        return (
          <div key={t.id} onClick={() => handleClick(t.id)}
            title={!open && t.lockHint ? `Gesperrt — ${t.lockHint}` : undefined}
            style={{
              padding: "12px 16px", cursor: open ? "pointer" : "not-allowed",
              fontSize: 13, fontWeight: on ? 600 : 500,
              color: on ? "var(--g-ink)" : open ? "var(--g-ink-3)" : "var(--g-ink-4)",
              borderBottom: on ? "2px solid var(--g-accent)" : "2px solid transparent",
              marginBottom: -1, display: "flex", alignItems: "center", gap: 5,
              whiteSpace: "nowrap", opacity: open ? 1 : 0.34,
              transition: "opacity 250ms, color 200ms",
              transform: flash === t.id ? "translateX(2px)" : "none",
              userSelect: "none",
            }}>
            {t.label}
            {t.optional && open && (
              <span className="mono" style={{
                fontSize: 9, fontWeight: 600, letterSpacing: "0.06em",
                padding: "1px 5px", borderRadius: 3,
                background: "rgba(196,90,42,0.10)", color: "var(--g-accent-deep)",
                textTransform: "uppercase",
              }}>optional</span>
            )}
            {isDone && (
              <span style={{
                fontSize: 10, fontWeight: 700, padding: "2px 5px", borderRadius: 3,
                background: "rgba(61,107,58,0.12)", color: "var(--g-good)",
                fontFamily: "var(--g-font-mono)",
              }}>✓</span>
            )}
            {!open && (
              <span style={{ fontSize: 10, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", opacity: 0.7 }}>⊘</span>
            )}
          </div>
        );
      })}
    </div>
  );
}

/* ─── Fortschrittsbalken (nur Pflicht-Schritte) ─── */
function TN_Progress({ done }) {
  const steps = ["route", "etappen", "metriken", "zeitplan"];
  const n = steps.filter(s => done.has(s)).length;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 7 }}>
      <div style={{ display: "flex", gap: 3 }}>
        {steps.map(s => (
          <div key={s} style={{
            width: 24, height: 3, borderRadius: 2,
            background: done.has(s) ? "var(--g-accent)" : "var(--g-rule)",
            transition: "background 350ms",
          }}/>
        ))}
      </div>
      <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
        {n === 0 ? "Noch nichts eingerichtet" : `${n} / ${steps.length} Abschnitte eingerichtet`}
      </span>
    </div>
  );
}

/* ─── Route Tab ─── */
function TN_RouteTab({ name, onName, region, onRegion, startDate, onStartDate, onContinue }) {
  const can = name.trim().length > 0 && !!startDate;
  const missing = !name.trim() ? "Tour-Name fehlt" : !startDate ? "Startdatum fehlt" : null;

  return (
    <div style={{ position: "relative", padding: "28px 40px 60px" }}>
      <TopoBg opacity={0.10}/>
      <div style={{ position: "relative", maxWidth: 640 }}>
        <Eyebrow style={{ marginBottom: 14 }}>Tour-Grunddaten</Eyebrow>

        <Field label="Tour-Name" required>
          <Input value={name} onChange={e => onName(e.target.value)}
            placeholder="z.B. Karnischer Höhenweg 2026" size="lg" autoFocus/>
        </Field>

        <Field label="Region"
          right={<span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>optional · max 50</span>}>
          <Input value={region} onChange={e => onRegion(e.target.value.slice(0, 50))}
            placeholder="z.B. Karnische Alpen" size="lg"/>
        </Field>

        <Field label="Startdatum" required>
          <input type="date" value={startDate} onChange={e => onStartDate(e.target.value)}
            style={{
              width: "100%", boxSizing: "border-box", padding: "9px 12px", fontSize: 14,
              fontFamily: "var(--g-font-mono)", border: "1.5px solid var(--g-rule)",
              borderRadius: "var(--g-r-2)", background: "var(--g-card)", color: "var(--g-ink)",
              outline: "none", appearance: "none", WebkitAppearance: "none",
            }}/>
          {startDate && (
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 6 }}>
              Etappe 1 startet am {TN_stageDate(startDate, 0)?.replace(/\.$/, "")} — jede folgende Etappe +1 Tag.
            </div>
          )}
        </Field>

        <div style={{
          marginTop: 12, padding: "12px 16px", borderRadius: "var(--g-r-2)",
          background: "var(--g-accent-tint)", border: "1px solid var(--g-accent-rule)",
        }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-accent-deep)", lineHeight: 1.6 }}>
            GPX-Dateien lädst du im nächsten Schritt hoch — eine Datei pro Etappe.
          </div>
        </div>

        <div style={{
          marginTop: 28, paddingTop: 20, borderTop: "1px solid var(--g-rule)",
          display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12,
        }}>
          {missing && <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>⊘ {missing}</span>}
          <Btn variant={can ? "accent" : "quiet"} size="md"
            onClick={can ? onContinue : undefined}
            style={!can ? { opacity: 0.45, cursor: "not-allowed" } : {}}>
            Etappen anlegen →
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ─── GPX-Slot ─── */
const TN_GPX_MOCK = {
  1: { file: "etappe-01.gpx", km: 9.3,  asc: 203  },
  2: { file: "etappe-02.gpx", km: 12.4, asc: 1235 },
  3: { file: "etappe-03.gpx", km: 13.2, asc: 540  },
  4: { file: "etappe-04.gpx", km: 11.8, asc: 720  },
  5: { file: "etappe-05.gpx", km: 14.5, asc: 980  },
  6: { file: "etappe-06.gpx", km: 13.1, asc: 860  },
};

function TN_GpxSlot({ stageId, value, onChange }) {
  const [hover, setHover] = React.useState(false);
  if (value) {
    return (
      <div style={{
        display: "flex", alignItems: "center", gap: 7, padding: "5px 10px",
        borderRadius: "var(--g-r-2)",
        background: "rgba(61,107,58,0.08)", border: "1px solid rgba(61,107,58,0.22)",
      }}>
        <span style={{
          width: 16, height: 16, borderRadius: 3, flexShrink: 0,
          background: "var(--g-good)", display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <svg width={9} height={9} viewBox="0 0 10 10" fill="none">
            <polyline points="1.5,5.5 4,8 8.5,2" stroke="#fff" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="mono" style={{ fontSize: 10, fontWeight: 600, color: "var(--g-ink-2)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            {value.file}
          </div>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)" }}>
            {value.km} km · ↑{value.asc} m
          </div>
        </div>
        <button onClick={() => onChange(null)} title="GPX entfernen"
          style={{ background: "transparent", border: "none", cursor: "pointer", color: "var(--g-ink-4)", fontSize: 13, padding: "1px 3px", lineHeight: 1, flexShrink: 0 }}>×</button>
      </div>
    );
  }
  return (
    <div onClick={() => onChange(TN_GPX_MOCK[stageId] || { file: `etappe-${String(stageId).padStart(2,"0")}.gpx`, km: "–", asc: "–" })}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        padding: "6px 11px", borderRadius: "var(--g-r-2)",
        border: `1.5px dashed ${hover ? "var(--g-accent)" : "var(--g-rule)"}`,
        background: hover ? "var(--g-accent-tint)" : "transparent",
        cursor: "pointer", display: "flex", alignItems: "center", gap: 6,
        transition: "background 120ms, border-color 120ms",
      }}>
      <svg width={11} height={11} viewBox="0 0 24 24" fill="none"
        stroke={hover ? "var(--g-accent-deep)" : "var(--g-ink-4)"}
        strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M12 16V4M7 9l5-5 5 5"/>
        <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
      </svg>
      <span className="mono" style={{
        fontSize: 10.5, fontWeight: 600, letterSpacing: "0.02em",
        color: hover ? "var(--g-accent-deep)" : "var(--g-ink-4)", whiteSpace: "nowrap",
      }}>GPX hochladen</span>
    </div>
  );
}

/* ─── Inline-Name-Input ─── */
function TN_NameInput({ value, onChange, placeholder }) {
  const [focus, setFocus] = React.useState(false);
  return (
    <input type="text" value={value} onChange={e => onChange(e.target.value)}
      placeholder={placeholder || "Etappenname eingeben …"}
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

/* ─── Datum-Helper ─── */
function TN_stageDate(startDate, offset) {
  if (!startDate) return null;
  try {
    const d = new Date(startDate + "T00:00:00");
    d.setDate(d.getDate() + offset);
    return `${String(d.getDate()).padStart(2,"0")}.${String(d.getMonth()+1).padStart(2,"0")}.`;
  } catch(e) { return null; }
}

/* ─── Etappen Tab ─── */
const TN_DEFAULT_STAGES = [
  { id: 1, name: "Toblach → Helmhotel"            },
  { id: 2, name: "Helmhotel → Sillianer Hütte"    },
  { id: 3, name: "Sillianer → Obstanserseehütte"  },
  { id: 4, name: "Obstanserse → Porzehütte"        },
  { id: 5, name: "Porze → Hochweißsteinhaus"       },
  { id: 6, name: "Hochweißstein → Wolayersee"      },
];

function TN_EtappenTab({ startDate, initialStages, initialGpxMap, onContinue }) {
  const [stages, setStages] = React.useState(
    initialStages || [{ id: 1, name: "" }, { id: 2, name: "" }]
  );
  const [gpxMap, setGpxMap] = React.useState(initialGpxMap || {});

  const allHaveGpx = stages.length > 0 && stages.every(s => !!gpxMap[s.id]);
  const gpxCount   = stages.filter(s => !!gpxMap[s.id]).length;

  const setGpx  = (id, val) => setGpxMap(m => { const n = {...m}; if (val) n[id] = val; else delete n[id]; return n; });
  const setName = (id, val) => setStages(ss => ss.map(s => s.id === id ? {...s, name: val} : s));
  const remove  = (id) => { setStages(ss => ss.filter(s => s.id !== id)); setGpxMap(m => { const n = {...m}; delete n[id]; return n; }); };
  const addStage = () => {
    const nextId = (stages.length ? Math.max(...stages.map(s => s.id)) : 0) + 1;
    setStages(ss => [...ss, { id: nextId, name: "" }]);
  };

  return (
    <div style={{ position: "relative", padding: "28px 40px 60px" }}>
      <TopoBg opacity={0.10}/>
      <div style={{ position: "relative", maxWidth: 900 }}>

        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", marginBottom: 20 }}>
          <div>
            <Eyebrow style={{ marginBottom: 2 }}>Etappen</Eyebrow>
            <h2 style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", margin: 0 }}>
              Namen vergeben &amp; GPX-Datei je Etappe hochladen
            </h2>
          </div>
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-end", gap: 3 }}>
            <span className="mono" style={{ fontSize: 11, color: allHaveGpx && stages.length > 0 ? "var(--g-good)" : "var(--g-ink-4)" }}>
              {gpxCount} / {stages.length} GPX geladen
            </span>
            {startDate && (
              <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>
                Start: {TN_stageDate(startDate, 0)?.replace(/\.$/, "")}
              </span>
            )}
          </div>
        </div>

        {/* Spaltenheader */}
        <div style={{
          display: "grid", gridTemplateColumns: "36px 1fr 60px minmax(170px, 200px) 28px",
          gap: 10, padding: "0 14px 5px",
        }}>
          {["", "Etappenname", "Datum", "GPX-Datei", ""].map((h, i) => (
            <span key={i} className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.06em", textTransform: "uppercase" }}>{h}</span>
          ))}
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 14 }}>
          {stages.map((s, idx) => {
            const dateStr = TN_stageDate(startDate, idx);
            const hasGpx  = !!gpxMap[s.id];
            const hasName = s.name.trim().length > 0;
            return (
              <div key={s.id} style={{
                display: "grid", gridTemplateColumns: "36px 1fr 60px minmax(170px, 200px) 28px",
                gap: 10, alignItems: "center", padding: "8px 14px",
                background: "var(--g-card)",
                border: `1px solid ${hasGpx ? "rgba(61,107,58,0.2)" : "var(--g-rule)"}`,
                borderRadius: "var(--g-r-2)", transition: "border-color 200ms",
                opacity: (!hasName && idx > 1) ? 0.65 : 1,
              }}>
                <span className="mono" style={{
                  fontSize: 10, fontWeight: 700, textAlign: "center",
                  color: "var(--g-accent-deep)", background: "var(--g-accent-tint)",
                  padding: "2px 4px", borderRadius: 999,
                }}>T{String(idx + 1).padStart(2, "0")}</span>

                <TN_NameInput value={s.name} onChange={v => setName(s.id, v)} placeholder={`Etappe ${idx + 1} benennen …`}/>

                <span className="mono" style={{ fontSize: 11, color: dateStr ? "var(--g-ink-3)" : "var(--g-ink-4)", whiteSpace: "nowrap" }}>
                  {dateStr || "–"}
                </span>

                <TN_GpxSlot stageId={s.id} value={gpxMap[s.id] || null} onChange={v => setGpx(s.id, v)}/>

                <button onClick={() => remove(s.id)} style={{
                  background: "transparent", border: "none", cursor: "pointer",
                  color: "var(--g-ink-4)", fontSize: 15, padding: "2px 4px", lineHeight: 1, textAlign: "center",
                }}>×</button>
              </div>
            );
          })}
        </div>

        <div style={{ display: "flex", gap: 8, marginBottom: 24 }}>
          <Btn variant="ghost" size="sm" onClick={addStage}>+ Etappe hinzufügen</Btn>
          <Btn variant="ghost" size="sm">+ Pausentag</Btn>
        </div>

        {/* Hinweis GPX fehlen */}
        {!allHaveGpx && stages.length > 0 && (
          <div style={{
            padding: "10px 15px", borderRadius: "var(--g-r-2)",
            background: "var(--g-paper)", border: "1px solid var(--g-rule)", marginBottom: 20,
          }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
              ⊘ {stages.length - gpxCount} Etappe{stages.length - gpxCount !== 1 ? "n" : ""} ohne GPX-Datei —
              nach dem Upload werden Wegpunkte automatisch berechnet.
            </span>
          </div>
        )}

        {/* Hinweis wenn alle GPX geladen */}
        {allHaveGpx && stages.length > 0 && (
          <div style={{
            padding: "10px 15px", borderRadius: "var(--g-r-2)",
            background: "rgba(61,107,58,0.07)", border: "1px solid rgba(61,107,58,0.2)", marginBottom: 20,
          }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-good)" }}>
              ✓ Alle GPX geladen — Wegpunkte werden berechnet.
              Jetzt weiter zu „Wegpunkte prüfen" (optional) oder direkt zu „Wetter-Metriken".
            </span>
          </div>
        )}

        <div style={{
          paddingTop: 20, borderTop: "1px solid var(--g-rule)",
          display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8,
        }}>
          {allHaveGpx && (
            <Btn variant="ghost" size="md" onClick={() => onContinue("metriken")}>
              Wetter direkt →
            </Btn>
          )}
          <Btn variant={allHaveGpx ? "accent" : "quiet"} size="md"
            onClick={allHaveGpx ? () => onContinue("wegpunkte") : undefined}
            style={!allHaveGpx ? { opacity: 0.45, cursor: "not-allowed" } : {}}>
            Wegpunkte prüfen →
          </Btn>
        </div>
      </div>
    </div>
  );
}

/* ─── Wegpunkte Tab (optional) ─── */
function TN_WegpunkteTab({ onContinue }) {
  return (
    <div style={{ position: "relative" }}>

      {/* Info-Banner */}
      <div style={{
        padding: "14px 40px",
        background: "var(--g-card)", borderBottom: "1px solid var(--g-rule-soft)",
        display: "flex", justifyContent: "space-between", alignItems: "center", gap: 24,
      }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13.5, fontWeight: 600, marginBottom: 3 }}>
            Wegpunkte aus GPX berechnet — optional prüfen
          </div>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", lineHeight: 1.55 }}>
            Wegpunkte sind Wetterscheiden — Punkte, an denen sich Höhe, Exposition oder Geländekammer ändert.
            Du kannst sie umbenennen, verschieben oder ergänzen. Diesen Schritt kannst du auch überspringen.
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, flexShrink: 0 }}>
          <Btn variant="ghost" size="sm" onClick={() => onContinue("metriken")}>
            Überspringen →
          </Btn>
          <Btn variant="accent" size="sm" onClick={() => onContinue("metriken")}>
            Wegpunkte übernehmen →
          </Btn>
        </div>
      </div>

      {/* Eingebetteter Wegpunkt-Editor (embedded=true = ohne Sidebar/Breadcrumb) */}
      <ScreenWaypointEditor embedded={true}/>

      {/* Footer */}
      <div style={{
        padding: "20px 40px", borderTop: "1px solid var(--g-rule)",
        background: "var(--g-card)",
        display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8,
      }}>
        <Btn variant="ghost" size="md" onClick={() => onContinue("metriken")}>
          Überspringen
        </Btn>
        <Btn variant="accent" size="md" onClick={() => onContinue("metriken")}>
          Wegpunkte übernehmen →
        </Btn>
      </div>
    </div>
  );
}

/* ═══════════════════ MAIN SCREEN ═══════════════════ */
function ScreenTripNewV2({ preset = "name_entered" } = {}) {

  const TN_HALF_STAGES = [
    { id: 1, name: "Toblach → Helmhotel"           },
    { id: 2, name: "Helmhotel → Sillianer Hütte"   },
    { id: 3, name: "Sillianer → Obstanserseehütte" },
    { id: 4, name: ""                               },
    { id: 5, name: ""                               },
  ];
  const TN_HALF_GPX = { 1: TN_GPX_MOCK[1], 2: TN_GPX_MOCK[2] };

  const TN_FULL_STAGES = TN_DEFAULT_STAGES;
  const TN_FULL_GPX    = Object.fromEntries(TN_FULL_STAGES.map(s => [s.id, TN_GPX_MOCK[s.id]]));

  const TN_PRESET_MAP = {
    empty: {
      name: "", startDate: "", region: "",
      initialStages: null, initialGpxMap: null,
      etDone: false, wt: false, zt: false, tab: "route",
    },
    name_entered: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TN_HALF_STAGES, initialGpxMap: TN_HALF_GPX,
      etDone: false, wt: false, zt: false, tab: "etappen",
    },
    etappen_done: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TN_FULL_STAGES, initialGpxMap: TN_FULL_GPX,
      etDone: true, wt: false, zt: false, tab: "wegpunkte",
    },
    wetter_done: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TN_FULL_STAGES, initialGpxMap: TN_FULL_GPX,
      etDone: true, wt: true, zt: false, tab: "metriken",
    },
    all_done: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TN_FULL_STAGES, initialGpxMap: TN_FULL_GPX,
      etDone: true, wt: true, zt: true, tab: "zeitplan",
    },
  };

  const p = TN_PRESET_MAP[preset] || TN_PRESET_MAP.empty;

  const [name,      setName]      = React.useState(p.name);
  const [region,    setRegion]    = React.useState(p.region || "");
  const [startDate, setStartDate] = React.useState(p.startDate);
  const [etDone,    setEtDone]    = React.useState(p.etDone);
  const [wtVis,     setWtVis]     = React.useState(p.wt);
  const [ztVis,     setZtVis]     = React.useState(p.zt);
  const [tab,       setTab]       = React.useState(p.tab);
  const [channels,  setCh]        = React.useState({ email: true, telegram: true, sms: false });

  const ul   = TN_unlocked(name, startDate, etDone, wtVis, ztVis);
  const done = TN_doneSet(name, startDate, etDone, wtVis, ztVis);
  const ready = done.has("zeitplan");

  const switchTab = (id) => {
    setTab(id);
    if (id === "metriken")  setWtVis(true);
    if (id === "zeitplan") setZtVis(true);
  };

  /* Etappen-Tab: Weiter-Schaltfläche kann Ziel-Tab vorgeben */
  const handleEtappenContinue = (target) => {
    setEtDone(true);
    switchTab(target || "wegpunkte");
  };

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}
      data-screen-label="Neue Tour anlegen">
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative", overflowY: "auto", overflowX: "hidden" }}>
        <TopoBg opacity={0.12}/>

        {/* Breadcrumb */}
        <div style={{
          position: "relative", padding: "14px 40px",
          borderBottom: "1px solid var(--g-rule-soft)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.06em" }}>
            <span style={{ opacity: 0.6 }}>Trips</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>Neue Tour</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {!ready && (
              <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)" }}>
                Zeitplan einrichten zum Speichern
              </span>
            )}
            <Btn variant="ghost" size="sm">Abbrechen</Btn>
            <Btn variant={ready ? "primary" : "quiet"} size="sm"
              style={!ready ? { opacity: 0.4, cursor: "not-allowed" } : {}}>
              Tour speichern
            </Btn>
          </div>
        </div>

        {/* Hero */}
        <div style={{ position: "relative", padding: "20px 40px 14px" }}>
          <Eyebrow>Neue Tour anlegen</Eyebrow>
          <h1 style={{
            fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em",
            margin: "4px 0 0", lineHeight: 1.1,
            color: name.trim() ? "var(--g-ink)" : "var(--g-ink-4)",
          }}>
            {name.trim() || "Noch kein Name"}
          </h1>
          <TN_Progress done={done}/>
        </div>

        <TN_TabBar active={tab} unlocked={ul} done={done} onChange={switchTab}/>

        {tab === "route" && (
          <TN_RouteTab
            name={name} onName={setName}
            region={region} onRegion={setRegion}
            startDate={startDate} onStartDate={setStartDate}
            onContinue={() => switchTab("etappen")}
          />
        )}
        {tab === "etappen" && (
          <TN_EtappenTab
            key={preset}
            startDate={startDate}
            initialStages={p.initialStages}
            initialGpxMap={p.initialGpxMap}
            onContinue={handleEtappenContinue}
          />
        )}
        {tab === "wegpunkte" && (
          <TN_WegpunkteTab onContinue={switchTab}/>
        )}
        {tab === "metriken" && <WetterMetrikenTabV2 onChannelsChange={setCh}/>}
        {tab === "zeitplan" && <TE2_ZeitplanTab channels={channels}/>}
        {tab === "alerts"   && <TE2_AlertsTab defaultChannels={channels}/>}
      </main>
    </div>
  );
}

window.ScreenTripNewV2 = ScreenTripNewV2;
