/* Mobile · Wegpunkt-Editor
 * Pattern: Karte als Vollbild, Bottom-Sheet mit Höhenprofil + Wegpunkten.
 * Etappen-Switcher als Pill-Row über der Karte. Floating Action Buttons rechts.
 */

function ScreenWaypointEditorMobile() {
  const trip = MOCK_TRIP;
  const [active, setActive] = React.useState(1);
  const [snap, setSnap] = React.useState("half"); // "peek" | "half" | "full"
  const [stageSheet, setStageSheet] = React.useState(false);
  const stage = trip.stages[active];

  const right = <IconBtn kind="more" label="Aktionen"/>;

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Wegpunkt-Editor"
          eyebrow={`KHW 403 · ${trip.stages.length} Etappen`}
          leftIcon="back"
          right={right}
        />

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
          <IconBtnInline kind="chevron" disabled={active === trip.stages.length - 1} onClick={() => active < trip.stages.length - 1 && setActive(active + 1)}/>
        </div>

        {/* Map area */}
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          <MapMock stage={stage}/>

          {/* Floating Controls rechts */}
          <div style={{
            position: "absolute", top: 12, right: 12,
            display: "flex", flexDirection: "column", gap: 8,
          }}>
            <FAB icon="plus"/>
            <FAB icon="map" subLabel="🛰"/>
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
      </div>
      {stageSheet && (
        <StageSelectSheet
          trip={trip}
          active={active}
          onPick={(i) => { setActive(i); setStageSheet(false); }}
          onClose={() => setStageSheet(false)}
        />
      )}
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

function StageSelectSheet({ trip, active, onPick, onClose }) {
  return (
    <Sheet open onClose={onClose} title="Etappe wählen" eyebrow={`KHW 403 · ${trip.stages.length} Etappen`} snap="full">
      <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
        {trip.stages.map((s, i) => {
          const isActive = i === active;
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
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.04em", marginBottom: 1 }}>{s.code} · {s.date}</div>
                <div style={{ fontSize: 14, fontWeight: 500, lineHeight: 1.25, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                  {s.title.replace(/^[^:]+: /,"")}
                </div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 3 }}>
                  {s.km} km · ↑{s.ascent} ↓{s.descent} · {s.waypoints.length} WP
                </div>
              </div>
              <Pill tone={tone}>{s.risk}</Pill>
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
                    strokeDasharray={wp.ai ? "3,2" : "0"}/>
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
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)" }}>2667 m · KI-Vorschlag · ETA 10:42</div>
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
            <MBtn variant="accent" size="md" style={{ flex: 1 }} icon={<MIcon kind="check" size={14} color="#fff"/>}>KI-Vorschlag übernehmen</MBtn>
            <MBtn variant="ghost" size="md">Verwerfen</MBtn>
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
                background: wp.ai ? "rgba(196,90,42,0.15)" : "var(--g-card)",
                border: `2px ${wp.ai ? "dashed" : "solid"} var(--g-accent)`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontFamily: "var(--g-font-mono)", fontSize: 10, fontWeight: 700,
                color: "var(--g-accent-deep)",
              }}>{i + 1}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: 13, fontWeight: 500 }}>{wp.name}</div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 1 }}>
                  {wp.elev} m · ETA {wp.time} {wp.ai && <span style={{ color: "var(--g-accent)" }}>· KI</span>}
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
                       fill={i === 1 ? "var(--g-accent)" : (wp.ai ? "rgba(196,90,42,0.2)" : "#fff")}
                       stroke="var(--g-accent)" strokeWidth="1.5"
                       strokeDasharray={wp.ai && i !== 1 ? "2,1.5" : "0"}/>;
      })}
    </svg>
  );
}

window.ScreenWaypointEditorMobile = ScreenWaypointEditorMobile;
