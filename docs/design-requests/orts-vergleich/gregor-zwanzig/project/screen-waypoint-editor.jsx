/* Screen: Wegpunkt-Editor — Karte + Hoehenprofil synchron, ohne Lat/Lon-Inputs */

function ScreenWaypointEditor({ initialActiveIdx = 1, demoCascade = false, embedded = false } = {}) {
  const trip = MOCK_TRIP;
  // Lokale Etappen-Liste: GPX-Etappen aus mock + ein Demo-Pausentag dazwischen.
  // Editier-Mocks: User kann diese Liste umsortieren und Pausen einfügen.
  const initialStages = React.useMemo(() => {
    const list = trip.stages.map(s => ({ ...s, kind: "gpx" }));
    // Pause nach Etappe 2 für Demo
    list.splice(3, 0, {
      id: "pause-1", code: "PAUSE", title: "Pausentag · Obstanserseehütte",
      date: "2026-05-09", kind: "pause", location: "Obstanserseehütte",
    });
    return list;
  }, []);
  const [stages, setStages] = React.useState(initialStages);
  const [activeIdx, setActiveIdx] = React.useState(initialActiveIdx);
  const [selected, setSelected] = React.useState(2);
  const [drag, setDrag] = React.useState(null);
  // Kaskade: nur relevant beim Verschieben der ERSTEN Etappe (Tourstart).
  const [cascade, setCascade] = React.useState(
    demoCascade ? { days: 2, count: initialStages.length - 1, done: false } : null
  );

  const stage = stages[activeIdx];

  // Datum einer Etappe setzen. Wird die erste Etappe verschoben, schlagen wir
  // die Mitverschiebung der Folge-Etappen vor (nicht-blockierend, inline).
  const setStageDate = (id, newDate) => {
    setStages(prev => {
      const i = prev.findIndex(s => s.id === id);
      if (i === -1) return prev;
      const old = prev[i].date;
      if (i === 0 && old && newDate && old !== newDate) {
        const days = Math.round((new Date(newDate) - new Date(old)) / 86400000);
        if (days !== 0) setCascade({ days, count: prev.length - 1, done: false });
      }
      return prev.map(s => s.id === id ? { ...s, date: newDate } : s);
    });
  };
  const applyCascade = () => {
    setStages(prev => prev.map((s, i) => {
      if (i === 0 || !s.date) return s;
      const d = new Date(s.date + "T00:00:00");
      d.setDate(d.getDate() + cascade.days);
      return { ...s, date: d.toISOString().slice(0, 10) };
    }));
    setCascade(c => ({ ...c, done: true }));
  };
  const dismissCascade = () => setCascade(null);

  const reorder = (fromId, toId) => {
    if (fromId === toId) return;
    const next = [...stages];
    const fromI = next.findIndex(s => s.id === fromId);
    const toI = next.findIndex(s => s.id === toId);
    const [moved] = next.splice(fromI, 1);
    next.splice(toI, 0, moved);
    // Aktiven Index neu ermitteln (der bewegte Eintrag bleibt visuell ausgewählt, falls aktiv)
    const wasActive = stages[activeIdx];
    setActiveIdx(next.findIndex(s => s.id === wasActive.id));
    setStages(next);
  };
  const insertPauseAfter = (idx) => {
    const next = [...stages];
    next.splice(idx + 1, 0, {
      id: "p" + Date.now(), code: "PAUSE", kind: "pause",
      title: "Pausentag", location: "neu — bitte Standort wählen",
    });
    setStages(next);
  };
  const removeStage = (id) => {
    const i = stages.findIndex(s => s.id === id);
    if (i === -1) return;
    const next = stages.filter(s => s.id !== id);
    setStages(next);
    if (i === activeIdx) setActiveIdx(Math.max(0, i - 1));
    else if (i < activeIdx) setActiveIdx(activeIdx - 1);
  };

  /* Editor-Kern (EtappenStrip + Karte/Profil/Sidebar-Grid). Wird im
   * eingebetteten Modus (Tab „Etappen & Wegpunkte" in TripEditView) ohne
   * Sidebar + Breadcrumb verwendet — die Page-Chrome liefert dann der Tab-Host. */
  const core = (
    <>
        {/* Etappen-Strip — drag-sortierbar, Pause-Insert dazwischen */}
        <EtappenStrip
          stages={stages}
          activeIdx={activeIdx}
          drag={drag}
          onSelect={(i) => { setActiveIdx(i); setSelected(2); }}
          onReorder={reorder}
          onDragStart={setDrag}
          onDragEnd={() => setDrag(null)}
          onInsertPause={insertPauseAfter}
          onRemove={removeStage}
        />

        <div style={{ position: "relative", padding: "20px 40px 60px", maxWidth: 1480 }}>

          {stage.kind === "pause" ? (
            <PauseStageView stage={stage} onDateChange={(d) => setStageDate(stage.id, d)}/>
          ) : <>
          <div style={{ marginBottom: 24 }}>
            <Eyebrow>Etappe · {stage.code}</Eyebrow>
            <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 32, marginTop: 4 }}>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em" }}>{stage.title.replace(/^[^:]+: /,"")}</div>
                <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 4, maxWidth: 680 }}>
                  Wegpunkte sind <strong style={{ color: "var(--g-ink)" }}>Wetterscheiden</strong> — Punkte, an denen sich Höhe, Exposition oder Geländekammer ändert. Aus der GPX sind {stage.waypoints.length} Wegpunkte entstanden — du kannst sie umbenennen, verschieben, löschen oder eigene ergänzen.
                </div>
              </div>
              <StageDateField value={stage.date} isFirst={activeIdx === 0} onChange={(d) => setStageDate(stage.id, d)}/>
            </div>
            {activeIdx === 0 && cascade && (
              <StageCascadeNotice days={cascade.days} count={cascade.count} done={cascade.done} onApply={applyCascade} onDismiss={dismissCascade}/>
            )}
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 360px", gap: 24 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <Card padding={0} style={{ overflow: "hidden" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 18px", borderBottom: "1px solid var(--g-rule-soft)" }}>
                  <Eyebrow>Karte · OpenTopoMap (OSM + SRTM)</Eyebrow>
                  <Pill tone="ghost">Topo</Pill>
                </div>
                <MapCanvas stage={stage} selected={selected} onSelect={setSelected}/>
              </Card>

              <Card padding={20}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <Eyebrow>Höhenprofil · synchron mit Karte</Eyebrow>
                  <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
                    {stage.km} km · ↑{stage.ascent} ↓{stage.descent} · max {stage.maxElev} m
                  </div>
                </div>
                <ProfileEditor stage={stage} selected={selected} onSelect={setSelected}/>
              </Card>
            </div>

            <div>
              <Card padding={0}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "14px 18px", borderBottom: "1px solid var(--g-rule-soft)" }}>
                  <div>
                    <Eyebrow>Wegpunkte</Eyebrow>
                    <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{stage.waypoints.length} insgesamt</div>
                  </div>
                  <Btn variant="ghost" size="sm">+ auf Route</Btn>
                </div>
                <div>
                  {stage.waypoints.map((wp, i) => (
                    <WaypointCard key={i} wp={wp} index={i} active={i === selected} onClick={() => setSelected(i)}/>
                  ))}
                </div>
              </Card>
            </div>
          </div>
          </>}
        </div>
    </>
  );

  if (embedded) return core;

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.16}/>

        <div style={{ position: "relative", padding: "16px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.06em" }}>
            <span style={{ opacity: 0.6 }}>KHW 403</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ opacity: 0.6 }}>{stage.code}</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>Wegpunkte</span>
          </div>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost" size="sm">Vorschläge neu berechnen</Btn>
            <Btn variant="primary" size="sm">Speichern</Btn>
          </div>
        </div>
        {core}
      </main>
    </div>
  );
}

/* ─────────────────── Etappen-Strip ─────────────────── */

function EtappenStrip({ stages, activeIdx, drag, onSelect, onReorder, onDragStart, onDragEnd, onInsertPause, onRemove }) {
  const [hoverGap, setHoverGap] = React.useState(null);
  return (
    <div style={{
      position: "relative",
      padding: "14px 40px 16px",
      borderBottom: "1px solid var(--g-rule-soft)",
      background: "rgba(255,255,255,0.4)",
      backdropFilter: "blur(2px)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
        <Eyebrow>Etappen · drag zum Sortieren · + Pause zwischen Etappen</Eyebrow>
        <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.06em" }}>
          {stages.filter(s => s.kind !== "pause").length} GPX · {stages.filter(s => s.kind === "pause").length} Pause
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "stretch", gap: 0, overflowX: "auto", paddingBottom: 4 }}>
        {stages.map((s, i) => (
          <React.Fragment key={s.id}>
            <StageCard
              stage={s}
              index={i}
              active={i === activeIdx}
              dragging={drag === s.id}
              onClick={() => onSelect(i)}
              onDragStart={() => onDragStart(s.id)}
              onDragOver={(e) => { e.preventDefault(); if (drag && drag !== s.id) onReorder(drag, s.id); }}
              onDragEnd={onDragEnd}
              onRemove={() => onRemove(s.id)}
            />
            <PauseInsertGap
              hovered={hoverGap === i}
              onHover={() => setHoverGap(i)}
              onLeave={() => setHoverGap(null)}
              onClick={() => { onInsertPause(i); setHoverGap(null); }}
            />
          </React.Fragment>
        ))}
        <button
          onClick={() => onInsertPause(stages.length - 1)}
          style={{
            flexShrink: 0, padding: "0 16px", border: "1px dashed var(--g-rule)", background: "transparent",
            color: "var(--g-ink-3)", fontSize: 11, fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em",
            textTransform: "uppercase", cursor: "pointer", borderRadius: 4, minHeight: 88,
          }}
          onMouseEnter={e => { e.currentTarget.style.borderColor = "var(--g-accent)"; e.currentTarget.style.color = "var(--g-accent)"; }}
          onMouseLeave={e => { e.currentTarget.style.borderColor = "var(--g-rule)"; e.currentTarget.style.color = "var(--g-ink-3)"; }}
        >
          + Etappe
        </button>
      </div>
    </div>
  );
}

function StageCard({ stage, index, active, dragging, onClick, onDragStart, onDragOver, onDragEnd, onRemove }) {
  const isPause = stage.kind === "pause";
  return (
    <div
      draggable
      onClick={onClick}
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
      style={{
        flexShrink: 0, width: 200, minHeight: 88,
        padding: "10px 12px", marginRight: 0,
        background: active ? "var(--g-card)" : (isPause ? "var(--g-card-alt)" : "var(--g-card)"),
        border: active ? "2px solid var(--g-accent)" : `1px ${isPause ? "dashed" : "solid"} var(--g-rule)`,
        borderRadius: 4, cursor: "grab",
        opacity: dragging ? 0.4 : 1,
        position: "relative",
        transition: "border-color 120ms",
        display: "flex", flexDirection: "column", justifyContent: "space-between",
      }}
    >
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 6 }}>
          <span className="mono" style={{ fontSize: 9, color: active ? "var(--g-accent-deep)" : "var(--g-ink-4)", letterSpacing: "0.08em", fontWeight: 600 }}>
            ⋮⋮ T{String(index + 1).padStart(2, "0")} · {stage.code}
          </span>
          <button onClick={(e) => { e.stopPropagation(); onRemove(); }} style={{
            background: "none", border: "none", padding: 0, fontSize: 12, color: "var(--g-ink-4)",
            cursor: "pointer", lineHeight: 1,
          }}>×</button>
        </div>
        <div style={{ fontSize: 12, fontWeight: 600, marginTop: 4, lineHeight: 1.3, fontStyle: isPause ? "italic" : "normal", color: isPause ? "var(--g-ink-2)" : "var(--g-ink)" }}>
          {isPause ? stage.title : stage.title.replace(/^[^:]+: /, "")}
        </div>
      </div>
      {isPause ? (
        <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-3)", marginTop: 6, letterSpacing: "0.04em" }}>
          ⌂ Pause · {stage.location || "—"}
        </div>
      ) : (
        <div style={{ marginTop: 6 }}>
          <MiniSpark profile={stage.profile} active={active}/>
          <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-3)", marginTop: 3, letterSpacing: "0.04em" }}>
            {stage.km} km · ↑{stage.ascent}
          </div>
        </div>
      )}
    </div>
  );
}

function MiniSpark({ profile, active }) {
  const W = 174, H = 18;
  const min = Math.min(...profile), max = Math.max(...profile);
  const range = max - min || 1;
  const pts = profile.map((v, i) => {
    const x = (i / (profile.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 2) - 1;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} preserveAspectRatio="none" style={{ display: "block" }}>
      <polyline points={pts.join(" ")} fill="none" stroke={active ? "var(--g-accent)" : "var(--g-ink-4)"} strokeWidth="1.2"/>
    </svg>
  );
}

function PauseInsertGap({ hovered, onHover, onLeave, onClick }) {
  return (
    <div
      onMouseEnter={onHover}
      onMouseLeave={onLeave}
      onClick={onClick}
      style={{
        flexShrink: 0, width: hovered ? 56 : 8, minHeight: 88,
        display: "flex", alignItems: "center", justifyContent: "center",
        cursor: "pointer", transition: "width 140ms ease",
        position: "relative",
      }}
    >
      {hovered ? (
        <span className="mono" style={{
          padding: "3px 8px", fontSize: 9, fontWeight: 600,
          background: "var(--g-accent)", color: "#fff",
          borderRadius: 10, letterSpacing: "0.06em", textTransform: "uppercase",
        }}>+ Pause</span>
      ) : (
        <span style={{ width: 1, height: 24, background: "var(--g-rule)" }}/>
      )}
    </div>
  );
}

/* Pausentag-Detail-Ansicht — keine Wegpunkte, nur Standort + Wetter dort */
function PauseStageView({ stage, onDateChange }) {
  return (
    <div style={{ marginTop: 8 }}>
      <Eyebrow>Pausentag</Eyebrow>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 32, marginTop: 4, marginBottom: 24 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em" }}>{stage.title}</div>
          <div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 4, maxWidth: 680 }}>
            Pausentage haben keine Wegpunkte und keine ETAs — nur einen festen Standort. Das Briefing für diesen Tag enthält Wetter & Tagesempfehlung an genau diesem Punkt (z.B. „Lawinen-Lage am Hütten-Hang", „Schaubadtour zur nahen Aussicht möglich?").
          </div>
        </div>
        <StageDateField value={stage.date} onChange={onDateChange}/>
      </div>

      <Card padding={24} style={{ maxWidth: 760 }}>
        <Eyebrow>Standort des Pausentags</Eyebrow>
        <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 14, padding: "14px 16px", background: "var(--g-card-alt)", borderRadius: 4, border: "1px dashed var(--g-rule)" }}>
          <span style={{
            width: 36, height: 36, borderRadius: "50%",
            background: "var(--g-paper)", border: "2px dashed var(--g-accent)",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            fontSize: 16, color: "var(--g-accent-deep)",
          }}>⌂</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{stage.location || "Bitte Standort wählen"}</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
              Übernahme aus Vor-/Folge-Etappe oder per Karte / Suche
            </div>
          </div>
          <Btn variant="ghost" size="sm">Standort wählen</Btn>
        </div>

        <div style={{ marginTop: 18, padding: 14, background: "rgba(196,90,42,0.06)", borderLeft: "3px solid var(--g-accent)", fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
          <strong>Tipp:</strong> Wenn am Vortag eine Hütte erreicht wurde und am Folgetag dieselbe Hütte verlassen wird, übernimmt das System den Standort automatisch.
        </div>
      </Card>
    </div>
  );
}

function MapCanvas({ stage, selected, onSelect }) {
  const W = 880, H = 440;
  const lats = stage.waypoints.map(w => w.lat);
  const lons = stage.waypoints.map(w => w.lon);
  const minLat = Math.min(...lats), maxLat = Math.max(...lats);
  const minLon = Math.min(...lons), maxLon = Math.max(...lons);
  const padLat = (maxLat - minLat) * 0.4 || 0.01;
  const padLon = (maxLon - minLon) * 0.4 || 0.01;
  const project = (lat, lon) => [
    ((lon - (minLon - padLon)) / ((maxLon + padLon) - (minLon - padLon))) * W,
    H - ((lat - (minLat - padLat)) / ((maxLat + padLat) - (minLat - padLat))) * H,
  ];
  const wpPx = stage.waypoints.map(w => project(w.lat, w.lon));
  const route = wpPx.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");

  return (
    <div style={{ position: "relative", height: H, background: "linear-gradient(180deg, #ecf2e8 0%, #e0ddc8 100%)", overflow: "hidden" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="100%" preserveAspectRatio="xMidYMid slice" style={{ position: "absolute", inset: 0 }}>
        {Array.from({ length: 18 }).map((_, i) => {
          const r = 60 + i * 30;
          const cx = W * 0.4 + Math.sin(i * 0.5) * 80;
          const cy = H * 0.55 + Math.cos(i * 0.7) * 40;
          return <ellipse key={i} cx={cx} cy={cy} rx={r * 1.2} ry={r * 0.8} fill="none" stroke="rgba(70, 80, 50, 0.18)" strokeWidth={i % 5 === 0 ? 0.7 : 0.35}/>;
        })}
        {Array.from({ length: 12 }).map((_, i) => {
          const r = 40 + i * 22;
          return <ellipse key={"b"+i} cx={W * 0.78} cy={H * 0.3} rx={r} ry={r * 0.65} fill="none" stroke="rgba(70, 80, 50, 0.18)" strokeWidth={i % 5 === 0 ? 0.7 : 0.35}/>;
        })}
        <path d={`M0,${H*0.7} C${W*0.2},${H*0.65} ${W*0.4},${H*0.78} ${W*0.55},${H*0.72} S${W*0.85},${H*0.6} ${W},${H*0.65}`}
          fill="none" stroke="rgba(70, 120, 184, 0.5)" strokeWidth="2"/>
        <polyline points={route} fill="none" stroke="rgba(196, 90, 42, 0.35)" strokeWidth="6" strokeLinejoin="round" strokeLinecap="round"/>
        <polyline points={route} fill="none" stroke="var(--g-accent)" strokeWidth="2.2" strokeLinejoin="round" strokeLinecap="round"/>
        {stage.waypoints.map((w, i) => {
          const [x, y] = wpPx[i];
          return <WaypointPin key={i} x={x} y={y} wp={w} index={i} active={i === selected} total={stage.waypoints.length} onClick={() => onSelect(i)}/>;
        })}
      </svg>
      <div style={{ position: "absolute", top: 14, right: 14, display: "flex", flexDirection: "column", gap: 4 }}>
        <MapBtn>+</MapBtn>
        <MapBtn>−</MapBtn>
      </div>
      <div style={{ position: "absolute", bottom: 12, left: 14, fontSize: 10, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-3)", background: "rgba(255,255,255,0.7)", padding: "3px 8px", borderRadius: 3 }}>
        500 m ━━━━━━━━━━━━━━
      </div>
      <div style={{ position: "absolute", bottom: 12, right: 14, fontSize: 10, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-3)", background: "rgba(255,255,255,0.7)", padding: "3px 8px", borderRadius: 3 }}>
        © OSM · SRTM
      </div>
    </div>
  );
}

function WaypointPin({ x, y, wp, index, active, total, onClick }) {
  const fill = active ? "var(--g-accent)" : "#fff";
  const stroke = active ? "var(--g-accent-deep)" : "var(--g-accent)";
  const r = active ? 11 : 8;
  const showLabel = active || index === 0 || index === total - 1;
  return (
    <g style={{ cursor: "pointer" }} onClick={onClick}>
      {active && <circle cx={x} cy={y} r={r + 6} fill="rgba(196, 90, 42, 0.18)"/>}
      <circle cx={x} cy={y} r={r} fill={fill} stroke={stroke} strokeWidth="2"/>
      <text x={x} y={y+4} textAnchor="middle" style={{ fontSize: 10, fontWeight: 700, fill: active ? "#fff" : "var(--g-accent-deep)", fontFamily: "var(--g-font-mono)", pointerEvents: "none" }}>{index + 1}</text>
      {showLabel && (
        <g pointerEvents="none">
          <rect x={x + 14} y={y - 22} width={Math.max(80, wp.name.length * 6.5)} height={20} rx={3} fill="rgba(26, 26, 24, 0.9)"/>
          <text x={x + 22} y={y - 8} style={{ fontSize: 11, fill: "#fff", fontFamily: "var(--g-font-sans)", fontWeight: 500 }}>{wp.name}</text>
        </g>
      )}
    </g>
  );
}

function MapBtn({ children }) {
  return <button style={{
    width: 30, height: 30, background: "rgba(255,255,255,0.92)", border: "1px solid var(--g-rule)",
    borderRadius: 4, fontSize: 14, fontWeight: 600, cursor: "pointer",
  }}>{children}</button>;
}

function ProfileEditor({ stage, selected, onSelect }) {
  const W = 820, H = 180;
  const min = Math.min(...stage.profile), max = Math.max(...stage.profile);
  const range = max - min || 1;
  const profilePts = stage.profile.map((v, i) => {
    const x = (i / (stage.profile.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 30) - 8;
    return [x, y];
  });
  const profilePath = "M" + profilePts.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
  const fillPath = profilePath + ` L${W},${H} L0,${H} Z`;
  // Verteile Wegpunkte gleichmäßig auf dem Profil
  const wpPositions = stage.waypoints.map((wp, i) => {
    const t = i / (stage.waypoints.length - 1);
    const idx = Math.round(t * (stage.profile.length - 1));
    return profilePts[idx];
  });

  return (
    <div style={{ position: "relative" }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: "block" }}>
        {[0, 0.25, 0.5, 0.75, 1].map((t, i) => (
          <line key={i} x1="0" x2={W} y1={H - 8 - t*(H-30)} y2={H - 8 - t*(H-30)} stroke="var(--g-rule-soft)" strokeWidth="1"/>
        ))}
        <path d={fillPath} fill="rgba(196, 90, 42, 0.08)"/>
        <path d={profilePath} fill="none" stroke="var(--g-accent)" strokeWidth="2"/>
        {stage.waypoints.map((wp, i) => {
          const [x, y] = wpPositions[i];
          const active = i === selected;
          return (
            <g key={i} style={{ cursor: "pointer" }} onClick={() => onSelect(i)}>
              <line x1={x} x2={x} y1={y} y2={H - 4} stroke={active ? "var(--g-accent)" : "var(--g-rule)"} strokeWidth="1"/>
              <circle cx={x} cy={y} r={active ? 7 : 5} fill={active ? "var(--g-accent)" : "#fff"} stroke="var(--g-accent)" strokeWidth="2"/>
              <text x={x} y={y+3} textAnchor="middle" style={{ fontSize: 9, fontWeight: 700, fill: active ? "#fff" : "var(--g-accent-deep)", fontFamily: "var(--g-font-mono)", pointerEvents: "none" }}>{i+1}</text>
              <text x={x} y={H+12} textAnchor="middle" style={{ fontSize: 9, fill: "var(--g-ink-3)", fontFamily: "var(--g-font-mono)" }}>{wp.elev}m</text>
            </g>
          );
        })}
      </svg>
      <div style={{ display: "flex", justifyContent: "space-between", marginTop: 14, fontFamily: "var(--g-font-mono)", fontSize: 10, color: "var(--g-ink-4)" }}>
        <span>Start · {stage.waypoints[0].time}</span>
        <span>Ziel · {stage.waypoints[stage.waypoints.length-1].time}</span>
      </div>
    </div>
  );
}

function WaypointCard({ wp, index, active, onClick }) {
  const typeLabel = { start: "Start", end: "Ziel", summit: "Gipfel", pass: "Pass", valley: "Tal", hut: "Hütte" }[wp.type] || "Wegpunkt";
  return (
    <div onClick={onClick} style={{
      padding: "12px 18px", borderBottom: "1px solid var(--g-rule-soft)", cursor: "pointer",
      background: active ? "rgba(196, 90, 42, 0.05)" : "transparent",
      borderLeft: active ? "3px solid var(--g-accent)" : "3px solid transparent",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 4 }}>
        <span style={{
          width: 22, height: 22, borderRadius: "50%", display: "inline-flex", alignItems: "center", justifyContent: "center",
          background: active ? "var(--g-accent)" : "#fff",
          border: "2px solid var(--g-accent)",
          color: active ? "#fff" : "var(--g-accent-deep)",
          fontFamily: "var(--g-font-mono)", fontSize: 10, fontWeight: 700,
        }}>{index + 1}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{wp.name}</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)" }}>
            {typeLabel} · {wp.elev} m · {wp.time}
          </div>
        </div>
      </div>
      {active && (
        <div style={{ display: "flex", gap: 6, marginTop: 8, marginLeft: 32 }}>
          <Btn variant="ghost" size="xs">Umbenennen</Btn>
          <Btn variant="ghost" size="xs">Verschieben</Btn>
          <Btn variant="ghost" size="xs">Löschen</Btn>
        </div>
      )}
    </div>
  );
}

/* ─────────────────── Etappen-Datum ───────────────────
 * Kanonisch in molecules.jsx: StageDateField + StageCascadeNotice (+ stageWeekdayDE).
 * Hier bewusst KEINE lokale Variante (Atomic-Disziplin, CLAUDE.md). */

window.ScreenWaypointEditor = ScreenWaypointEditor;
