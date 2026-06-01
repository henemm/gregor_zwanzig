/* Mobile · Wegpunkt-Editor
 * Pattern: Karte als Vollbild, Bottom-Sheet mit Höhenprofil + Wegpunkten.
 * Etappen-Switcher als Pill-Row über der Karte. Floating Action Buttons rechts.
 */

function ScreenWaypointEditorMobile({ initialActive = 1, demoCascade = false, embedded = false } = {}) {
  const trip = MOCK_TRIP;
  // Editier-State: Kopie der Etappen + ein Demo-Pausentag (Parität zum Desktop-Editor),
  // damit Datum nachträglich korrigierbar ist und der Pausentag-Fall mockbar bleibt.
  const initialStages = React.useMemo(() => {
    const list = trip.stages.map(s => ({ ...s, kind: s.kind || "gpx" }));
    list.splice(3, 0, {
      id: "pause-1", code: "PAUSE", title: "Pausentag · Obstanserseehütte",
      date: "2026-05-09", kind: "pause", location: "Obstanserseehütte",
    });
    return list;
  }, []);
  const [stages, setStages] = React.useState(initialStages);
  const [active, setActive] = React.useState(initialActive);
  const [snap, setSnap] = React.useState("half"); // "peek" | "half" | "full"
  const [stageSheet, setStageSheet] = React.useState(false);
  const [cascade, setCascade] = React.useState(
    demoCascade ? { days: 2, count: initialStages.length - 1, done: false } : null
  );
  const stage = stages[active];
  const isPause = stage.kind === "pause";

  // Datum der aktiven Etappe setzen; bei erster Etappe Kaskaden-Vorschlag (wie Desktop).
  const setStageDate = (newDate) => {
    setStages(prev => {
      const old = prev[active].date;
      if (active === 0 && old && newDate && old !== newDate) {
        const days = Math.round((new Date(newDate) - new Date(old)) / 86400000);
        if (days !== 0) setCascade({ days, count: prev.length - 1, done: false });
      }
      return prev.map((s, i) => i === active ? { ...s, date: newDate } : s);
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

  const right = <IconBtn kind="more" label="Aktionen"/>;

  /* Editor-Inhalt ohne Page-Chrome (Etappen-Switcher + Datum + Karte/Sheet).
   * Im eingebetteten Modus liefert der Tab-Host (TripEditView) PhoneFrame,
   * TopAppBar und die Tab-Leiste; hier kommt nur der Tab-Inhalt. */
  const stageBlock = (
    <>
        {/* Etappen-Dropdown-Trigger (skaliert bei 13+ Etappen) */}
        <div style={{
          display: "flex", alignItems: "stretch", gap: 6,
          padding: "10px 14px", background: "var(--g-card)",
          borderBottom: "1px solid var(--g-rule-soft)", flexShrink: 0,
        }}>
          <button onClick={() => setStageSheet(true)} style={{
            flex: 1, minWidth: 0,
            display: "flex", alignItems: "center", gap: 10,
            padding: "4px 10px 4px 4px", minHeight: 44,
            background: "transparent", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-2)", cursor: "pointer", textAlign: "left",
          }}>
            <span style={{
              display: "inline-flex", alignItems: "center", justifyContent: "center",
              width: 28, height: 28, background: "var(--g-accent)", color: "#fff",
              fontSize: 10, fontFamily: "var(--g-font-mono)", fontWeight: 600,
              borderRadius: 3, flexShrink: 0,
            }}>{String(active + 1).padStart(2, "0")}</span>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.06em", marginBottom: 1 }}>{stage.code}</div>
              <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                {stage.title.replace(/^[^:]+: /,"")}
              </div>
            </div>
            <MIcon kind="chevron-down" size={16} color="var(--g-ink-3)"/>
          </button>
          <IconBtnInline kind="back" disabled={active === 0} onClick={() => active > 0 && setActive(active - 1)} flipped/>
          <IconBtnInline kind="chevron" disabled={active === stages.length - 1} onClick={() => active < stages.length - 1 && setActive(active + 1)}/>
        </div>

        {/* Etappen-Datum · editierbar (touch-lg). Kaskaden-Vorschlag bei erster Etappe. */}
        <div style={{
          padding: "10px 14px", background: "var(--g-card)",
          borderBottom: "1px solid var(--g-rule-soft)", flexShrink: 0,
        }}>
          <StageDateField value={stage.date} isFirst={active === 0} size="lg" align="left"
            onChange={setStageDate} style={{ width: "100%", minWidth: 0 }}/>
          {active === 0 && cascade && (
            <StageCascadeNotice days={cascade.days} count={cascade.count} done={cascade.done}
              onApply={applyCascade} onDismiss={() => setCascade(null)}/>
          )}
        </div>

        {/* Body: Karte+Profil-Sheet (Etappe) ODER Pausentag-Karte */}
        {isPause ? (
          <MPauseStageBody stage={stage}/>
        ) : (
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          <MapMock stage={stage}/>

          {/* Floating Controls rechts */}
          <div style={{
            position: "absolute", top: 12, right: 12,
            display: "flex", flexDirection: "column", gap: 8,
          }}>
            <FAB icon="plus"/>
            <FAB icon="map"/>
            <FAB icon="search"/>
          </div>

          {/* Profil-Strip oben */}
          <div style={{
            position: "absolute", top: 12, left: 12, right: 72,
            background: "rgba(246,244,238,0.95)", backdropFilter: "blur(8px)",
            border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
            padding: "8px 12px", boxShadow: "var(--g-shadow-1)",
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 2 }}>
              <span style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.2 }}>{stage.title.replace(/^[^:]+: /,"")}</span>
              <Pill tone={stage.risk === "high" ? "bad" : stage.risk === "med" ? "warn" : "good"}>{stage.risk}</Pill>
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)" }}>
              {stage.km} km · ↑{stage.ascent} ↓{stage.descent} · {stage.waypoints.length} WP
            </div>
          </div>

          {/* Bottom-Sheet · Höhenprofil + Wegpunkte (eingebettet, nicht modal) */}
          <ProfileSheetEmbedded stage={stage} snap={snap} onSnapChange={setSnap}/>
        </div>
        )}
    </>
  );

  const sheet = stageSheet ? (
    <StageSelectSheet
      trip={trip}
      stages={stages}
      active={active}
      onPick={(i) => { setActive(i); setStageSheet(false); }}
      onClose={() => setStageSheet(false)}
    />
  ) : null;

  if (embedded) {
    return (
      <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        {stageBlock}
        {sheet}
      </div>
    );
  }

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Wegpunkt-Editor"
          eyebrow={`KHW 403 · ${stages.length} Etappen`}
          leftIcon="back"
          right={right}
        />
        {stageBlock}
      </div>
      {sheet}
    </PhoneFrame>
  );
}

function IconBtnInline({ kind, onClick, disabled, flipped }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      width: 44, height: 44, border: "1px solid var(--g-rule)",
      background: "var(--g-paper)", borderRadius: "var(--g-r-2)",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1, padding: 0,
      transform: flipped ? "scaleX(-1)" : "none", flexShrink: 0,
    }}>
      <MIcon kind={kind} size={16} color="var(--g-ink)"/>
    </button>
  );
}

function StageSelectSheet({ trip, stages, active, onPick, onClose }) {
  const list = stages || trip.stages;
  return (
    <Sheet open onClose={onClose} title="Etappe wählen" eyebrow={`KHW 403 · ${list.length} Etappen`} snap="full">
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {list.map((s, i) => {
          const isActive = i === active;
          const sPause = s.kind === "pause";
          const tone = s.risk === "high" ? "bad" : s.risk === "med" ? "warn" : "good";
          return (
            <button key={s.id} onClick={() => onPick(i)} style={{
              display: "flex", alignItems: "center", gap: 12, minHeight: 64,
              padding: "10px 12px", textAlign: "left", cursor: "pointer",
              background: isActive ? "var(--g-accent-tint)" : "var(--g-card)",
              border: isActive ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
              borderLeft: isActive ? "3px solid var(--g-accent)" : "1px solid var(--g-rule)",
              borderRadius: "var(--g-r-3)",
            }}>
              <span style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                width: 30, height: 30, borderRadius: "var(--g-r-2)",
                background: isActive ? "var(--g-accent)" : "var(--g-paper-deep)",
                color: isActive ? "#fff" : "var(--g-ink-3)",
                fontSize: 11, fontFamily: "var(--g-font-mono)", fontWeight: 700, flexShrink: 0,
              }}>{String(i + 1).padStart(2, "0")}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.04em", marginBottom: 1 }}>{s.code} · {s.date || "—"}</div>
                <div style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.25, fontStyle: sPause ? "italic" : "normal", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {sPause ? s.title : s.title.replace(/^[^:]+: /,"")}
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 3 }}>
                  {sPause ? `⌂ Pause · ${s.location || "—"}` : `${s.km} km · ↑${s.ascent} ↓${s.descent} · ${s.waypoints.length} WP`}
                </div>
              </div>
              {sPause ? <Pill tone="ghost">Pause</Pill> : <Pill tone={tone}>{s.risk}</Pill>}
            </button>
          );
        })}
      </div>
    </Sheet>
  );
}

function FAB({ icon, subLabel }) {
  return (
    <button style={{
      width: 44, height: 44, borderRadius: "var(--g-r-3)",
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      boxShadow: "var(--g-shadow-2)", cursor: "pointer", padding: 0,
      display: "flex", alignItems: "center", justifyContent: "center",
      position: "relative",
    }}>
      <MIcon kind={icon} size={20} color="var(--g-ink)"/>
      {subLabel && (
        <span style={{
          position: "absolute", top: 2, right: 4, fontSize: 8,
          color: "var(--g-ink-3)", fontFamily: "var(--g-font-mono)",
        }}>{subLabel}</span>
      )}
    </button>
  );
}

function MapMock({ stage }) {
  return (
    <div style={{
      position: "absolute", inset: 0,
      background: "linear-gradient(180deg, #d9dec9 0%, #cfd1bb 45%, #c8c6ad 100%)",
    }}>
      <svg viewBox="0 0 375 600" width="100%" height="100%" style={{ position: "absolute", inset: 0 }} preserveAspectRatio="xMidYMid slice">
        {/* Höhenlinien */}
        {Array.from({ length: 14 }).map((_, i) => (
          <path key={i}
                d={`M${-20 + i*8} ${100 + i*30} Q${100 + i*5} ${60 + i*25} ${200 + i*4} ${110 + i*32} T${400} ${80 + i*30}`}
                stroke={`rgba(26,26,24,${0.05 + (i%3)*0.03})`} strokeWidth={i%5===0?1:0.6} fill="none"/>
        ))}
        {/* Gewässer */}
        <path d="M0 420 Q90 380 170 410 T370 405 L370 480 Q280 510 200 480 T0 500 Z" fill="rgba(74,122,184,0.15)"/>
        {/* Route */}
        <path d="M35 480 L75 410 L130 360 L190 290 L240 240 L280 200 L330 150"
              stroke="var(--g-accent)" strokeWidth="3.5" fill="none"
              strokeLinejoin="round" strokeLinecap="round"
              strokeDasharray="0" filter="drop-shadow(0 1px 2px rgba(196,90,42,0.3))"/>

        {/* Wegpunkte */}
        {[
          { x: 35, y: 480, n: 1, ai: false },
          { x: 130, y: 360, n: 2, ai: true, selected: true },
          { x: 240, y: 240, n: 3, ai: true },
          { x: 330, y: 150, n: 4, ai: false },
        ].map(wp => (
          <g key={wp.n}>
            <circle cx={wp.x} cy={wp.y} r={wp.selected ? 16 : 12}
                    fill="#fff"
                    stroke="var(--g-accent)"
                    strokeWidth={wp.selected ? 3 : 2}
                    strokeDasharray="0"/>
            <text x={wp.x} y={wp.y + 4} textAnchor="middle"
                  fontFamily="var(--g-font-mono)" fontSize={wp.selected ? 12 : 11}
                  fontWeight="700" fill="var(--g-accent-deep)">{wp.n}</text>
          </g>
        ))}
      </svg>
      {/* Attribution */}
      <div className="mono" style={{
        position: "absolute", bottom: 8, right: 8, fontSize: 9, color: "var(--g-ink-3)",
        background: "rgba(255,255,255,0.7)", padding: "1px 5px", borderRadius: 2,
      }}>© OpenStreetMap</div>
    </div>
  );
}

function ProfileSheetEmbedded({ stage, snap, onSnapChange }) {
  const heights = { peek: 92, half: 320, full: 540 };
  const h = heights[snap] || heights.half;
  return (
    <div style={{
      position: "absolute", left: 0, right: 0, bottom: 0, height: h,
      background: "var(--g-card)", borderTopLeftRadius: 18, borderTopRightRadius: 18,
      boxShadow: "0 -8px 24px rgba(26,26,24,0.15)", display: "flex", flexDirection: "column",
      transition: "height 200ms ease-out",
    }}>
      <div onClick={() => onSnapChange(snap === "full" ? "half" : snap === "half" ? "full" : "half")}
           style={{
             display: "flex", justifyContent: "center", paddingTop: 8, paddingBottom: 4,
             cursor: "pointer", flexShrink: 0,
           }}>
        <span style={{ width: 36, height: 4, borderRadius: 2, background: "var(--g-rule)" }}/>
      </div>

      <div style={{
        padding: "4px 16px 8px", display: "flex", alignItems: "center", justifyContent: "space-between", flexShrink: 0,
      }}>
        <div>
          <Eyebrow style={{ marginBottom: 2 }}>Höhenprofil & Wegpunkte</Eyebrow>
          <div style={{ fontSize: 13, fontWeight: 600 }}>WP #2 · Birnlücke</div>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)" }}>2667 m · ETA 10:42</div>
        </div>
        {snap !== "peek" && (
          <button onClick={() => onSnapChange("peek")} style={{
            width: 32, height: 32, borderRadius: "var(--g-r-2)",
            background: "transparent", border: "1px solid var(--g-rule)",
            cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <MIcon kind="chevron-down" size={14} color="var(--g-ink-3)"/>
          </button>
        )}
      </div>

      <div style={{ padding: "0 16px 8px", flexShrink: 0 }}>
        <EditorProfileSVG stage={stage}/>
      </div>

      {snap !== "peek" && (
        <div style={{ flex: 1, overflow: "auto", padding: "8px 16px 16px" }}>
          <div style={{ display: "flex", gap: 6, marginBottom: 12 }}>
            <MBtn variant="ghost" size="md" style={{ flex: 1 }}>Umbenennen</MBtn>
            <MBtn variant="ghost" size="md" style={{ flex: 1 }}>Verschieben</MBtn>
            <MBtn variant="ghost" size="md" style={{ flex: 1 }}>Löschen</MBtn>
          </div>
          <Eyebrow style={{ marginBottom: 6 }}>Alle Wegpunkte · {stage.waypoints.length}</Eyebrow>
          {stage.waypoints.map((wp, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: 10, minHeight: 48,
              padding: "8px 8px", borderBottom: "1px solid var(--g-rule-soft)",
              background: i === 1 ? "var(--g-accent-tint)" : "transparent",
              borderRadius: "var(--g-r-2)",
            }}>
              <span style={{
                width: 24, height: 24, borderRadius: "50%", flexShrink: 0,
                background: "var(--g-card)",
                border: "2px solid var(--g-accent)",
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: "var(--g-font-mono)", fontSize: 10, fontWeight: 700,
                color: "var(--g-accent-deep)",
              }}>{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{wp.name}</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 1 }}>
                  {wp.elev} m · ETA {wp.time}
                </div>
              </div>
              <MIcon kind="chevron" size={14} color="var(--g-ink-3)"/>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function EditorProfileSVG({ stage }) {
  const W = 343, H = 70;
  const min = Math.min(...stage.profile), max = Math.max(...stage.profile);
  const range = max - min || 1;
  const pts = stage.profile.map((v, i) => {
    const x = (i / (stage.profile.length - 1)) * W;
    const y = H - ((v - min) / range) * (H - 10) - 4;
    return [x, y];
  });
  const path = "M" + pts.map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
  const fill = path + ` L${W},${H} L0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} style={{ display: "block" }}>
      <path d={fill} fill="rgba(196, 90, 42, 0.1)"/>
      <path d={path} fill="none" stroke="var(--g-accent)" strokeWidth="1.5"/>
      {stage.waypoints.map((wp, i) => {
        const t = i / (stage.waypoints.length - 1);
        const idx = Math.round(t * (stage.profile.length - 1));
        const [x, y] = pts[idx];
        return <circle key={i} cx={x} cy={y} r={i === 1 ? "5" : "3.5"}
                       fill={i === 1 ? "var(--g-accent)" : "#fff"}
                       stroke="var(--g-accent)" strokeWidth="1.5"/>;
      })}
    </svg>
  );
}

/* Mobile · Pausentag-Body — kein Profil/keine Wegpunkte, nur Standort + Hinweis.
 * Parität zur Desktop-PauseStageView; das editierbare Datum sitzt bereits im
 * Datum-Strip darüber (gemeinsame StageDateField). M-Prefix = Mobile-only. */
function MPauseStageBody({ stage }) {
  return (
    <div style={{ flex: 1, overflow: "auto", background: "var(--g-paper)", padding: 14 }}>
      <div style={{
        background: "var(--g-card)", border: "1px solid var(--g-rule)",
        borderRadius: "var(--g-r-3)", padding: 16,
      }}>
        <Eyebrow style={{ marginBottom: 8 }}>Pausentag</Eyebrow>
        <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.5, marginBottom: 14 }}>
          Pausentage haben keine Wegpunkte und keine ETAs — nur einen festen Standort.
          Das Briefing enthält Wetter &amp; Tagesempfehlung an genau diesem Punkt.
        </div>

        <Eyebrow style={{ marginBottom: 6 }}>Standort</Eyebrow>
        <div style={{
          display: "flex", alignItems: "center", gap: 12, minHeight: 56,
          padding: "10px 12px", background: "var(--g-card-alt)",
          border: "1px dashed var(--g-rule)", borderRadius: "var(--g-r-2)",
        }}>
          <span style={{
            width: 34, height: 34, borderRadius: "50%", flexShrink: 0,
            background: "var(--g-paper)", border: "2px dashed var(--g-accent)",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            fontSize: 15, color: "var(--g-accent-deep)",
          }}>⌂</span>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>{stage.location || "Bitte Standort wählen"}</div>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 2 }}>
              Übernahme aus Vor-/Folge-Etappe oder per Karte
            </div>
          </div>
        </div>

        <div style={{ marginTop: 12 }}>
          <MBtn variant="ghost" size="md" style={{ width: "100%" }}>Standort wählen</MBtn>
        </div>

        <div style={{
          marginTop: 14, padding: 12, background: "var(--g-accent-tint)",
          borderLeft: "3px solid var(--g-accent)", borderRadius: "var(--g-r-2)",
          fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.5,
        }}>
          <strong>Tipp:</strong> Wird am Vortag eine Hütte erreicht und am Folgetag dieselbe
          Hütte verlassen, übernimmt das System den Standort automatisch.
        </div>
      </div>
    </div>
  );
}

window.ScreenWaypointEditorMobile = ScreenWaypointEditorMobile;
