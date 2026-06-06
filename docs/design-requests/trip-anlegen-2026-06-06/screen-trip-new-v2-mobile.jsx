/* screen-trip-new-v2-mobile.jsx
 * ═══════════════════════════════════════════════════════════════════════
 *  Neue Tour anlegen — Mobile (375 px)
 *
 *  Gleiche 6-Tab-Struktur wie Desktop (screen-trip-new-v2.jsx),
 *  aber mobile Patterns: MTab (scrollbar), MInput, MField, MBtn,
 *  ScreenScroll, Sheet, TopAppBar.
 *
 *  Tabs schalten sequenziell frei — identische Lock-Logik wie Desktop.
 *  Wegpunkte-Tab: vereinfachter Karten-Placeholder (kein full
 *  ScreenWaypointEditor — zu eng für 375 px; Desktop-Editor ist
 *  Referenz-Surface für Wegpunkt-Review).
 *
 *  Prefix: TNM_ — Babel-Scope-Disziplin (CLAUDE.md)
 *  Export:  window.ScreenTripNewV2Mobile
 * ═══════════════════════════════════════════════════════════════════════
 */

/* ─── Tab-Definitionen ─── */
const TNM_TABS = [
  { id: "route",     label: "Route"      },
  { id: "etappen",   label: "Etappen"    },
  { id: "wegpunkte", label: "Wegpunkte", badge: "opt" },
  { id: "wetter",    label: "Wetter"     },
  { id: "zeitplan",  label: "Zeitplan"   },
  { id: "alerts",    label: "Alerts"     },
];

/* ─── Lock-Logik (identisch Desktop) ─── */
function TNM_unlocked(name, startDate, etDone, wtVis, ztVis) {
  const s = new Set(["route"]);
  if (name.trim() && startDate) s.add("etappen");
  if (etDone) { s.add("wegpunkte"); s.add("wetter"); }
  if (wtVis) s.add("zeitplan");
  if (ztVis) s.add("alerts");
  return s;
}

/* ─── Datum-Helper ─── */
function TNM_stageDate(startDate, offset) {
  if (!startDate) return null;
  try {
    const d = new Date(startDate + "T00:00:00");
    d.setDate(d.getDate() + offset);
    return `${String(d.getDate()).padStart(2,"0")}.${String(d.getMonth()+1).padStart(2,"0")}.`;
  } catch(e) { return null; }
}

/* ─── Locked-Tab-Tap → kurzer Shake-Toast ─── */
function TNM_LockHint({ msg }) {
  return (
    <div style={{
      position: "absolute", bottom: 72, left: 16, right: 16, zIndex: 50,
      background: "var(--g-ink)", color: "var(--g-paper)",
      borderRadius: "var(--g-r-3)", padding: "11px 16px",
      fontSize: 13, fontFamily: "var(--g-font-mono)",
      boxShadow: "0 4px 20px rgba(26,26,24,0.25)",
      display: "flex", alignItems: "center", gap: 10,
    }}>
      <span style={{ opacity: 0.6 }}>⊘</span>
      <span>{msg}</span>
    </div>
  );
}

/* ─── MTab mit Lock-Overlay ─── */
function TNM_TabBar({ active, unlocked, onChange, onLockedTap }) {
  return (
    <div style={{
      display: "flex", gap: 0, overflowX: "auto",
      borderBottom: "1px solid var(--g-rule-soft)",
      WebkitOverflowScrolling: "touch", scrollbarWidth: "none", flexShrink: 0,
    }}>
      {TNM_TABS.map(t => {
        const on   = t.id === active;
        const open = unlocked.has(t.id);
        return (
          <button key={t.id}
            onClick={() => open ? onChange(t.id) : onLockedTap(t.id)}
            style={{
              display: "inline-flex", alignItems: "center", gap: 5,
              padding: "13px 13px", minHeight: 44, flexShrink: 0,
              background: "transparent", border: "none",
              cursor: open ? "pointer" : "default",
              fontSize: 14, fontWeight: on ? 600 : 500,
              color: on ? "var(--g-ink)" : open ? "var(--g-ink-3)" : "var(--g-ink-4)",
              borderBottom: on ? "2px solid var(--g-accent)" : "2px solid transparent",
              marginBottom: -1, whiteSpace: "nowrap",
              fontFamily: "var(--g-font-sans)",
              opacity: open ? 1 : 0.35,
            }}>
            {t.label}
            {t.badge && open && (
              <span className="mono" style={{
                fontSize: 9, fontWeight: 700, padding: "1px 5px", borderRadius: 3,
                background: "rgba(196,90,42,0.12)", color: "var(--g-accent-deep)",
                letterSpacing: "0.06em", textTransform: "uppercase",
              }}>{t.badge}</span>
            )}
            {!open && (
              <span className="mono" style={{ fontSize: 10, opacity: 0.8 }}>⊘</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ─── Fortschrittsbalken (Pflicht-Schritte) ─── */
function TNM_Progress({ name, startDate, etDone, wtVis, ztVis }) {
  const steps = [
    name.trim() && startDate,
    etDone,
    wtVis,
    ztVis,
  ];
  const n = steps.filter(Boolean).length;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "8px 16px 0" }}>
      <div style={{ display: "flex", gap: 3, flex: 1 }}>
        {steps.map((done, i) => (
          <div key={i} style={{
            flex: 1, height: 3, borderRadius: 2,
            background: done ? "var(--g-accent)" : "var(--g-rule)",
            transition: "background 350ms",
          }}/>
        ))}
      </div>
      <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", flexShrink: 0 }}>
        {n}/4
      </span>
    </div>
  );
}

/* ─── Tab 1: Route ─── */
function TNM_RouteTab({ name, onName, region, onRegion, startDate, onStartDate, onContinue }) {
  const can = name.trim().length > 0 && !!startDate;
  return (
    <ScreenScroll padding={16} style={{ paddingBottom: 88 }}>

      <MField label="Tour-Name">
        <MInput value={name} onChange={e => onName(e.target.value)}
          placeholder="z.B. Karnischer Höhenweg 2026"/>
      </MField>

      <MField label="Region" sub="optional · max 50 Zeichen">
        <MInput value={region} onChange={e => onRegion(e.target.value.slice(0, 50))}
          placeholder="z.B. Karnische Alpen"/>
      </MField>

      <MField label="Startdatum"
        sub={startDate ? `Etappe 1 startet am ${TNM_stageDate(startDate, 0)?.replace(/\.$/, "")} — jede folgende +1 Tag` : null}>
        <input type="date" value={startDate} onChange={e => onStartDate(e.target.value)}
          style={{
            display: "block", width: "100%", boxSizing: "border-box",
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", padding: "12px 14px",
            fontSize: 16, fontFamily: "var(--g-font-mono)", color: "var(--g-ink)",
            outline: "none", minHeight: 48,
            appearance: "none", WebkitAppearance: "none",
          }}
        />
      </MField>

      <div style={{
        padding: "12px 14px", borderRadius: "var(--g-r-2)",
        background: "var(--g-accent-tint)", border: "1px solid var(--g-accent-rule)",
        marginBottom: 20,
      }}>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-accent-deep)", lineHeight: 1.6 }}>
          GPX-Dateien lädst du im nächsten Schritt hoch — eine Datei pro Etappe.
        </div>
      </div>

      {/* Floating CTA */}
      <div style={{ position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 10 }}>
        <MBtn block variant={can ? "primary" : "quiet"} size="xl"
          onClick={can ? onContinue : undefined}
          style={!can ? { opacity: 0.4 } : {}}>
          {can ? "Etappen anlegen →" : (!name.trim() ? "Tour-Name eingeben" : "Startdatum wählen")}
        </MBtn>
      </div>
    </ScreenScroll>
  );
}

/* ─── GPX-Slot (Mobile, volle Zeile) ─── */
const TNM_GPX_MOCK = {
  1: { file: "etappe-01.gpx", km: 9.3,  asc: 203  },
  2: { file: "etappe-02.gpx", km: 12.4, asc: 1235 },
  3: { file: "etappe-03.gpx", km: 13.2, asc: 540  },
  4: { file: "etappe-04.gpx", km: 11.8, asc: 720  },
  5: { file: "etappe-05.gpx", km: 14.5, asc: 980  },
  6: { file: "etappe-06.gpx", km: 13.1, asc: 860  },
};

function TNM_GpxRow({ stageId, value, onChange }) {
  if (value) {
    return (
      <div style={{
        display: "flex", alignItems: "center", gap: 12,
        padding: "10px 14px", minHeight: 56,
        background: "rgba(61,107,58,0.07)",
        border: "1px solid rgba(61,107,58,0.22)",
        borderRadius: "var(--g-r-2)",
      }}>
        <div style={{
          width: 32, height: 32, borderRadius: 6, flexShrink: 0,
          background: "var(--g-good)", display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <svg width={14} height={14} viewBox="0 0 10 10" fill="none">
            <polyline points="1.5,5.5 4,8 8.5,2" stroke="#fff" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="mono" style={{ fontSize: 12, fontWeight: 600, color: "var(--g-ink-2)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{value.file}</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 1 }}>{value.km} km · ↑{value.asc} m</div>
        </div>
        <button onClick={() => onChange(null)} style={{
          background: "transparent", border: "none", cursor: "pointer",
          color: "var(--g-ink-4)", fontSize: 18, padding: "4px 6px", lineHeight: 1, minHeight: 44, flexShrink: 0,
        }}>×</button>
      </div>
    );
  }
  return (
    <button
      onClick={() => onChange(TNM_GPX_MOCK[stageId] || { file: `etappe-${String(stageId).padStart(2,"0")}.gpx`, km: "–", asc: "–" })}
      style={{
        display: "flex", alignItems: "center", gap: 12,
        width: "100%", padding: "12px 14px", minHeight: 52,
        background: "var(--g-card)", border: "1.5px dashed var(--g-rule)",
        borderRadius: "var(--g-r-2)", cursor: "pointer", textAlign: "left",
      }}>
      <div style={{
        width: 32, height: 32, borderRadius: 6, flexShrink: 0,
        background: "var(--g-accent-tint)", border: "1px dashed var(--g-accent)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <svg width={14} height={14} viewBox="0 0 24 24" fill="none"
          stroke="var(--g-accent-deep)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 16V4M7 9l5-5 5 5"/>
          <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
        </svg>
      </div>
      <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: "var(--g-accent-deep)", letterSpacing: "0.02em" }}>
        GPX hochladen
      </span>
    </button>
  );
}

/* ─── Tab 2: Etappen & GPX ─── */
function TNM_EtappenTab({ startDate, initialStages, initialGpxMap, onContinue }) {
  const [stages, setStages] = React.useState(
    initialStages || [{ id: 1, name: "" }, { id: 2, name: "" }]
  );
  const [gpxMap, setGpxMap] = React.useState(initialGpxMap || {});
  const [editId, setEditId] = React.useState(null); // Sheet für Etappen-Name

  const allHaveGpx = stages.length > 0 && stages.every(s => !!gpxMap[s.id]);
  const gpxCount   = stages.filter(s => !!gpxMap[s.id]).length;

  const setGpx  = (id, v) => setGpxMap(m => { const n = {...m}; if (v) n[id] = v; else delete n[id]; return n; });
  const setName = (id, v) => setStages(ss => ss.map(s => s.id === id ? {...s, name: v} : s));
  const addStage = () => {
    const nextId = (stages.length ? Math.max(...stages.map(s => s.id)) : 0) + 1;
    setStages(ss => [...ss, { id: nextId, name: "" }]);
  };

  const editStage = stages.find(s => s.id === editId);

  return (
    <React.Fragment>
      <ScreenScroll padding={14} style={{ paddingBottom: 88 }}>

        {/* Counter */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", fontWeight: 600, letterSpacing: "0.08em", textTransform: "uppercase" }}>
            {stages.length} Etappen
          </div>
          <span className="mono" style={{
            fontSize: 11,
            color: allHaveGpx ? "var(--g-good)" : "var(--g-ink-4)",
          }}>
            {gpxCount}/{stages.length} GPX
          </span>
        </div>

        {/* Etappen-Cards */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {stages.map((s, idx) => {
            const dateStr = TNM_stageDate(startDate, idx);
            const hasName = s.name.trim().length > 0;
            return (
              <div key={s.id} style={{
                background: "var(--g-card)",
                border: `1px solid ${gpxMap[s.id] ? "rgba(61,107,58,0.2)" : "var(--g-rule)"}`,
                borderRadius: "var(--g-r-3)",
                overflow: "hidden",
                transition: "border-color 200ms",
              }}>
                {/* Header-Zeile */}
                <div style={{ display: "flex", alignItems: "center", padding: "11px 14px 7px", gap: 10 }}>
                  <span className="mono" style={{
                    fontSize: 10, fontWeight: 700, flexShrink: 0,
                    color: "var(--g-accent-deep)", background: "var(--g-accent-tint)",
                    padding: "2px 6px", borderRadius: 999,
                  }}>T{String(idx + 1).padStart(2, "0")}</span>

                  <button onClick={() => setEditId(s.id)} style={{
                    flex: 1, textAlign: "left", background: "transparent", border: "none",
                    cursor: "pointer", minHeight: 36, padding: 0,
                  }}>
                    <div style={{
                      fontSize: 14.5, fontWeight: hasName ? 500 : 400,
                      color: hasName ? "var(--g-ink)" : "var(--g-ink-4)",
                    }}>
                      {hasName ? s.name : `Etappe ${idx + 1} benennen …`}
                    </div>
                  </button>

                  {dateStr && (
                    <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", flexShrink: 0 }}>
                      {dateStr}
                    </span>
                  )}
                </div>

                {/* GPX-Slot */}
                <div style={{ padding: "0 12px 12px" }}>
                  <TNM_GpxRow stageId={s.id} value={gpxMap[s.id] || null} onChange={v => setGpx(s.id, v)}/>
                </div>
              </div>
            );
          })}
        </div>

        <button onClick={addStage} style={{
          display: "block", width: "100%", marginTop: 10,
          padding: "13px", border: "1px dashed var(--g-rule)",
          borderRadius: "var(--g-r-3)", background: "transparent",
          color: "var(--g-ink-3)", fontSize: 14, cursor: "pointer", minHeight: 48,
        }}>
          + Etappe hinzufügen
        </button>

        {!allHaveGpx && stages.length > 0 && (
          <div style={{ marginTop: 14, padding: "11px 14px", borderRadius: "var(--g-r-2)", background: "var(--g-paper-deep)", border: "1px solid var(--g-rule)" }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
              ⊘ Noch {stages.length - gpxCount} GPX fehlen — danach Wegpunkte prüfen oder direkt zu Wetter.
            </span>
          </div>
        )}
        {allHaveGpx && (
          <div style={{ marginTop: 14, padding: "11px 14px", borderRadius: "var(--g-r-2)", background: "rgba(61,107,58,0.08)", border: "1px solid rgba(61,107,58,0.2)" }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-good)" }}>✓ Alle GPX geladen — Wegpunkte werden berechnet.</span>
          </div>
        )}
      </ScreenScroll>

      {/* Floating CTAs */}
      {allHaveGpx && (
        <div style={{ position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 10, display: "flex", flexDirection: "column", gap: 8 }}>
          <MBtn block variant="primary" size="xl" onClick={() => onContinue("wegpunkte")}>
            Wegpunkte prüfen →
          </MBtn>
          <MBtn block variant="ghost" size="lg" onClick={() => onContinue("wetter")}>
            Direkt zu Wetter
          </MBtn>
        </div>
      )}

      {/* Name-Edit Sheet */}
      <Sheet open={!!editStage} onClose={() => setEditId(null)}
        title="Etappenname" snap="half"
        footer={
          <MBtn block variant="primary" size="lg" onClick={() => setEditId(null)}>
            Übernehmen
          </MBtn>
        }>
        {editStage && (
          <div style={{ paddingTop: 8 }}>
            <MInput
              value={editStage.name}
              onChange={e => setName(editStage.id, e.target.value)}
              placeholder="z.B. Toblach → Helmhotel"
            />
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 8 }}>
              Datum: {TNM_stageDate(startDate, stages.findIndex(s => s.id === editStage.id)) || "–"}
            </div>
          </div>
        )}
      </Sheet>
    </React.Fragment>
  );
}

/* ─── Tab 3: Wegpunkte (optional, vereinfacht) ─── */
function TNM_WegpunkteTab({ onContinue }) {
  const [skipSheet, setSkipSheet] = React.useState(false);

  /* Mock-Wegpunkte */
  const waypoints = [
    { id: 1, label: "Toblach",           elev: 1223, type: "start"   },
    { id: 2, label: "Helmhotel",         elev: 1580, type: "waypoint"},
    { id: 3, label: "Sillianer Hütte",   elev: 2447, type: "hut"     },
    { id: 4, label: "Obstanserseehütte", elev: 2303, type: "hut"     },
    { id: 5, label: "Porzehütte",        elev: 2589, type: "hut"     },
  ];

  /* Minimal-Höhenprofil (SVG Polyline aus Mock-Daten) */
  const elevs = [1223, 1580, 2447, 2303, 2589, 2100, 1850];
  const minE = Math.min(...elevs), maxE = Math.max(...elevs);
  const W = 327, H = 72;
  const pts = elevs.map((e, i) => {
    const x = (i / (elevs.length - 1)) * W;
    const y = H - ((e - minE) / (maxE - minE)) * (H - 8) - 4;
    return `${x},${y}`;
  }).join(" ");

  return (
    <React.Fragment>
      <ScreenScroll padding={0} style={{ paddingBottom: 100 }}>

        {/* Info-Banner */}
        <div style={{ padding: "12px 16px", background: "var(--g-accent-tint)", borderBottom: "1px solid var(--g-accent-rule)" }}>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--g-accent-deep)", lineHeight: 1.55 }}>
            Wegpunkte automatisch berechnet. Namen anpassen, Punkte hinzufügen oder überspringen.
          </div>
        </div>

        {/* Karten-Placeholder */}
        <div style={{
          margin: "14px 14px 0",
          borderRadius: "var(--g-r-3)", overflow: "hidden",
          background: "#e8eef0",
          border: "1px solid var(--g-rule)",
          height: 180,
          display: "flex", alignItems: "center", justifyContent: "center",
          position: "relative",
        }}>
          {/* Topo-Raster als SVG */}
          <svg width="100%" height="100%" viewBox="0 0 347 180" preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
            <rect width="347" height="180" fill="#dde8ea"/>
            {[30,60,90,120,150].map(y => (
              <line key={y} x1={0} y1={y} x2={347} y2={y} stroke="#c5d3d6" strokeWidth="1"/>
            ))}
            {[50,100,150,200,250,300].map(x => (
              <line key={x} x1={x} y1={0} x2={x} y2={180} stroke="#c5d3d6" strokeWidth="1"/>
            ))}
            {/* Mock-Route */}
            <polyline points="20,150 60,120 100,60 160,80 210,45 270,55 320,90" fill="none" stroke="var(--g-accent)" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"/>
            {/* Wegpunkt-Dots */}
            {[[20,150],[60,120],[100,60],[160,80],[210,45]].map(([x,y], i) => (
              <circle key={i} cx={x} cy={y} r={5} fill="var(--g-card)" stroke="var(--g-accent)" strokeWidth="2"/>
            ))}
          </svg>
          <div style={{
            position: "absolute", bottom: 8, right: 10,
            background: "rgba(255,255,255,0.85)", borderRadius: 4,
            padding: "3px 8px",
          }}>
            <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)" }}>OpenStreetMap</span>
          </div>
        </div>

        {/* Höhenprofil */}
        <div style={{ margin: "10px 14px 0", background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)", padding: "10px 14px 8px" }}>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>Höhenprofil</div>
          <svg width="100%" height={H} viewBox={`0 0 ${W} ${H}`} style={{ display: "block", overflow: "visible" }}>
            {/* Fill */}
            <polyline points={`0,${H} ${pts} ${W},${H}`} fill="var(--g-accent-tint)" stroke="none"/>
            {/* Line */}
            <polyline points={pts} fill="none" stroke="var(--g-accent)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            {/* Peak label */}
            <text x={((4 / (elevs.length - 1)) * W)} y={H - ((2589 - minE) / (maxE - minE)) * (H - 8) - 10}
              textAnchor="middle" fontSize="9" fill="var(--g-ink-3)" fontFamily="var(--g-font-mono)">
              2589 m
            </text>
          </svg>
          <div style={{ display: "flex", justifyContent: "space-between" }}>
            <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>1223 m</span>
            <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>Toblach → Wolayersee</span>
            <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>2589 m</span>
          </div>
        </div>

        {/* Wegpunkt-Liste */}
        <div style={{ margin: "12px 14px 0" }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>
            {waypoints.length} Wegpunkte
          </div>
          <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden" }}>
            {waypoints.map((w, i) => (
              <div key={w.id} style={{
                display: "flex", alignItems: "center", gap: 12, padding: "12px 14px",
                borderBottom: i < waypoints.length - 1 ? "1px solid var(--g-rule-soft)" : "none",
                minHeight: 52,
              }}>
                <div style={{
                  width: 28, height: 28, borderRadius: "50%", flexShrink: 0,
                  background: w.type === "start" ? "var(--g-good)" : w.type === "hut" ? "var(--g-accent)" : "var(--g-rule)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <svg width={12} height={12} viewBox="0 0 24 24" fill="none"
                    stroke="white" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    {w.type === "hut"
                      ? <path d="M3 9l9-7 9 7v11a1 1 0 01-1 1H4a1 1 0 01-1-1z"/>
                      : <circle cx="12" cy="12" r="4"/>}
                  </svg>
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontSize: 14.5, fontWeight: 500 }}>{w.label}</div>
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 1 }}>{w.elev} m</div>
                </div>
                <button style={{
                  background: "transparent", border: "none", cursor: "pointer",
                  color: "var(--g-ink-4)", fontSize: 12, fontFamily: "var(--g-font-mono)",
                  padding: "4px 6px", minHeight: 44,
                }}>Bearb.</button>
              </div>
            ))}
          </div>
        </div>
      </ScreenScroll>

      {/* Floating CTAs */}
      <div style={{ position: "absolute", bottom: 16, left: 16, right: 16, zIndex: 10, display: "flex", flexDirection: "column", gap: 8 }}>
        <MBtn block variant="primary" size="xl" onClick={() => onContinue("wetter")}>
          Wegpunkte übernehmen →
        </MBtn>
        <MBtn block variant="ghost" size="lg" onClick={() => setSkipSheet(true)}>
          Überspringen
        </MBtn>
      </div>

      <Sheet open={skipSheet} onClose={() => setSkipSheet(false)} title="Wegpunkte überspringen?" snap="half"
        footer={
          <div style={{ display: "flex", gap: 10 }}>
            <MBtn block variant="ghost" size="lg" onClick={() => setSkipSheet(false)}>Abbrechen</MBtn>
            <MBtn block variant="primary" size="lg" onClick={() => { setSkipSheet(false); onContinue("wetter"); }}>Trotzdem weiter</MBtn>
          </div>
        }>
        <div style={{ paddingTop: 8, fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.6 }}>
          Du kannst die Wegpunkte jederzeit im Trip-Editor nachträglich anpassen.
        </div>
      </Sheet>
    </React.Fragment>
  );
}

/* ═══════════════════ MAIN SCREEN ═══════════════════ */
function ScreenTripNewV2Mobile({ preset = "name_entered" } = {}) {

  const TNM_HALF_STAGES = [
    { id: 1, name: "Toblach → Helmhotel"            },
    { id: 2, name: "Helmhotel → Sillianer Hütte"    },
    { id: 3, name: "Sillianer → Obstanserseehütte"  },
    { id: 4, name: ""                                },
    { id: 5, name: ""                                },
  ];
  const TNM_HALF_GPX = { 1: TNM_GPX_MOCK[1], 2: TNM_GPX_MOCK[2] };

  const TNM_FULL_STAGES = [
    { id: 1, name: "Toblach → Helmhotel"            },
    { id: 2, name: "Helmhotel → Sillianer Hütte"    },
    { id: 3, name: "Sillianer → Obstanserseehütte"  },
    { id: 4, name: "Obstanserse → Porzehütte"        },
    { id: 5, name: "Porze → Hochweißsteinhaus"       },
    { id: 6, name: "Hochweißstein → Wolayersee"      },
  ];
  const TNM_FULL_GPX = Object.fromEntries(TNM_FULL_STAGES.map(s => [s.id, TNM_GPX_MOCK[s.id]]));

  const TNM_PRESET_MAP = {
    empty: {
      name: "", startDate: "", region: "",
      initialStages: null, initialGpxMap: null,
      etDone: false, wt: false, zt: false, tab: "route",
    },
    name_entered: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TNM_HALF_STAGES, initialGpxMap: TNM_HALF_GPX,
      etDone: false, wt: false, zt: false, tab: "etappen",
    },
    etappen_done: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TNM_FULL_STAGES, initialGpxMap: TNM_FULL_GPX,
      etDone: true, wt: false, zt: false, tab: "wegpunkte",
    },
    wetter_done: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TNM_FULL_STAGES, initialGpxMap: TNM_FULL_GPX,
      etDone: true, wt: true, zt: false, tab: "wetter",
    },
    all_done: {
      name: "Karnischer Höhenweg 2026", startDate: "2026-05-06", region: "Karnische Alpen",
      initialStages: TNM_FULL_STAGES, initialGpxMap: TNM_FULL_GPX,
      etDone: true, wt: true, zt: true, tab: "zeitplan",
    },
  };

  const p = TNM_PRESET_MAP[preset] || TNM_PRESET_MAP.empty;

  const [name,      setName]      = React.useState(p.name);
  const [region,    setRegion]    = React.useState(p.region || "");
  const [startDate, setStartDate] = React.useState(p.startDate);
  const [etDone,    setEtDone]    = React.useState(p.etDone);
  const [wtVis,     setWtVis]     = React.useState(p.wt);
  const [ztVis,     setZtVis]     = React.useState(p.zt);
  const [tab,       setTab]       = React.useState(p.tab);
  const [channels,  setCh]        = React.useState({ email: true, telegram: true, sms: false });
  const [lockHint,  setLockHint]  = React.useState(null);

  const ul = TNM_unlocked(name, startDate, etDone, wtVis, ztVis);
  const ready = ztVis;

  const switchTab = (id) => {
    setTab(id);
    if (id === "wetter")   setWtVis(true);
    if (id === "zeitplan") setZtVis(true);
  };

  const handleLockedTap = (id) => {
    const hints = {
      etappen:   "erst Tour-Name + Startdatum eingeben",
      wegpunkte: "erst alle GPX hochladen",
      wetter:    "erst alle GPX hochladen",
      zeitplan:  "erst Wetter-Metriken öffnen",
      alerts:    "erst Zeitplan öffnen",
    };
    setLockHint(hints[id] || "Schritt noch gesperrt");
    setTimeout(() => setLockHint(null), 2000);
  };

  const handleEtappenContinue = (target) => {
    setEtDone(true);
    switchTab(target || "wegpunkte");
  };

  /* Titel in TopAppBar */
  const tabTitle = {
    route:     "Route",
    etappen:   "Etappen & GPX",
    wegpunkte: "Wegpunkte",
    wetter:    "Wetter-Metriken",
    zeitplan:  "Briefing-Zeitplan",
    alerts:    "Alerts",
  }[tab] || "Neue Tour";

  return (
    <PhoneFrame height={780} time="09:41">
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>

        {/* TopAppBar */}
        <TopAppBar
          title={tabTitle}
          eyebrow={name.trim() || "Neue Tour"}
          leftIcon="back"
          right={
            <button style={{
              height: 44, padding: "0 14px", border: "none", background: "transparent",
              color: ready ? "var(--g-accent)" : "var(--g-ink-4)",
              fontWeight: 600, fontSize: 14, cursor: ready ? "pointer" : "default",
              fontFamily: "var(--g-font-sans)",
            }}>
              Speichern
            </button>
          }
        />

        {/* Fortschritt */}
        <TNM_Progress name={name} startDate={startDate} etDone={etDone} wtVis={wtVis} ztVis={ztVis}/>

        {/* Tab-Bar */}
        <TNM_TabBar active={tab} unlocked={ul} onChange={switchTab} onLockedTap={handleLockedTap}/>

        {/* Inhalt */}
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          {tab === "route" && (
            <TNM_RouteTab
              name={name} onName={setName}
              region={region} onRegion={setRegion}
              startDate={startDate} onStartDate={setStartDate}
              onContinue={() => switchTab("etappen")}
            />
          )}
          {tab === "etappen" && (
            <TNM_EtappenTab
              key={preset}
              startDate={startDate}
              initialStages={p.initialStages}
              initialGpxMap={p.initialGpxMap}
              onContinue={handleEtappenContinue}
            />
          )}
          {tab === "wegpunkte" && (
            <TNM_WegpunkteTab onContinue={switchTab}/>
          )}
          {tab === "wetter" && (
            <TM2_WetterTab onChannelsChange={setCh}/>
          )}
          {tab === "zeitplan" && (
            <TM2_ZeitplanTab channels={channels}/>
          )}
          {tab === "alerts" && (
            <TM2_AlertsTab defaultChannels={channels}/>
          )}
        </div>

        {/* Lock-Hint Toast */}
        {lockHint && <TNM_LockHint msg={lockHint}/>}
      </div>
    </PhoneFrame>
  );
}

window.ScreenTripNewV2Mobile = ScreenTripNewV2Mobile;
