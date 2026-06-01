/* Mobile · Trip-Detail
 * Pattern: Hero + Tab-Scroller + Card-Stack. Sticky Tabs. Status-Badge unter Hero.
 * Tabs: Übersicht · Etappen · Metriken · Briefings · Alerts · Vorschau (Pill-Scroller).
 */

function ScreenTripDetailMobile() {
  const trip = MOCK_TRIP;
  const [tab, setTab] = React.useState("uebersicht");
  const [activeStage, setActiveStage] = React.useState(1);

  const tabs = [
    { id: "uebersicht", label: "Übersicht" },
    { id: "etappen",    label: "Etappen", badge: trip.stages.length },
    { id: "metriken",   label: "Metriken", badge: 14 },
    { id: "briefings",  label: "Briefings" },
    { id: "alerts",     label: "Alerts", badge: 2, accent: true },
    { id: "vorschau",   label: "Vorschau" },
  ];

  const right = (
    <div style={{ display: "flex" }}>
      <IconBtn kind="send" label="Test-Senden"/>
      <IconBtn kind="more" label="Mehr"/>
    </div>
  );

  return (
    <MobileShell active="trips" title="KHW 403" eyebrow="Trips ›" leftIcon="back" right={right} phoneHeight={812}>
      <ScreenScroll padding={0}>
        {/* Hero */}
        <div style={{ padding: "12px 16px 16px", background: "var(--g-paper)" }}>
          <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", margin: 0, lineHeight: 1.1 }}>{trip.name}</h1>
          <div className="mono" style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 8, lineHeight: 1.5 }}>
            {trip.startDate} → {trip.endDate}<br/>
            {trip.stages.length} Etappen · {trip.totalKm} km · ↑{trip.totalAscent} m
          </div>

          {/* Status + Quick Stats */}
          <div style={{ display: "flex", gap: 6, marginTop: 12, flexWrap: "wrap" }}>
            <span className="mono" style={{
              display: "inline-flex", alignItems: "center", gap: 6,
              fontSize: 11, padding: "5px 10px", borderRadius: "var(--g-r-pill)",
              border: "1px solid var(--g-good)", color: "var(--g-good)",
              letterSpacing: "0.06em", fontWeight: 600, textTransform: "uppercase",
            }}>
              <span style={{ width: 6, height: 6, borderRadius: "50%", background: "var(--g-good)" }}/>
              Aktiv · Briefings laufen
            </span>
          </div>

          {/* Stat row */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8, marginTop: 16, padding: "12px 0", borderTop: "1px solid var(--g-rule-soft)", borderBottom: "1px solid var(--g-rule-soft)" }}>
            <Stat size="sm" mono tone="accent" label="Etappe" value={`${activeStage + 1}/${trip.stages.length}`}/>
            <Stat size="sm" mono tone="accent" label="Briefing" value="06:00"/>
            <Stat size="sm" mono label="Start in" value="3 Tg"/>
          </div>
        </div>

        {/* Tabs */}
        <div style={{ position: "sticky", top: 0, background: "var(--g-paper)", zIndex: 5, paddingLeft: 8 }}>
          <MTab items={tabs} active={tab} onChange={setTab}/>
        </div>

        {/* Tab Content */}
        <div style={{ padding: (tab === "etappen" || tab === "metriken" || tab === "alerts") ? 0 : "16px 16px 24px" }}>
          {tab === "uebersicht" && <DetailOverview trip={trip} activeStage={activeStage} onStage={setActiveStage}/>}
          {tab === "etappen"    && (
            <div style={{ height: 600, display: "flex", flexDirection: "column", borderTop: "1px solid var(--g-rule-soft)" }}>
              <ScreenWaypointEditorMobile embedded initialActive={activeStage}/>
            </div>
          )}
          {tab === "metriken"   && <ScreenMetricsEditorMobile embedded/>}
          {tab === "briefings"  && <DetailBriefings/>}
          {tab === "alerts"     && <ScreenAlertConfigMobile embedded/>}
          {tab === "vorschau"   && <DetailVorschau/>}
        </div>
      </ScreenScroll>
    </MobileShell>
  );
}

/* ─────────────────── Tab: Übersicht ─────────────────── */
function DetailOverview({ trip, activeStage, onStage }) {
  return (
    <>
      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 6 }}>Höhenprofil · Gesamt</Eyebrow>
        <MiniFullProfile stages={trip.stages} active={activeStage} onClick={onStage}/>
      </Card>

      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Briefings laufen</Eyebrow>
        <ReportLineM kind="Morgen" time="06:00" channels={["email","signal"]} active/>
        <ReportLineM kind="Abend"  time="18:00" channels={["email"]} active/>
        <ReportLineM kind="Alert"  time="bei Δ / Schwellwert" channels={["signal"]} active alert last/>
      </Card>

      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 6 }}>Alerts · letzte 7 Tage</Eyebrow>
        {MOCK_ALERTS_RECENT.slice(0, 2).map((a, i) => (
          <AlertRow variant="dot" divider="dashed" key={i} alert={a} last={i === 1}/>
        ))}
      </Card>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
        <MBtn variant="primary" block size="lg">Email-Vorschau</MBtn>
        <MBtn variant="ghost" block size="lg">SMS-Vorschau</MBtn>
      </div>
    </>
  );
}

function MiniFullProfile({ stages, active, onClick }) {
  const W = 343, H = 90;
  const all = stages.flatMap(s => s.profile);
  const min = Math.min(...all), max = Math.max(...all);
  const range = max - min || 1;
  let xOffset = 0;
  const totalKm = stages.reduce((sum, s) => sum + s.km, 0);
  const sections = stages.map((s, i) => {
    const w = (s.km / totalKm) * W;
    const pts = s.profile.map((v, j) => {
      const x = xOffset + (j / (s.profile.length - 1)) * w;
      const y = H - ((v - min) / range) * (H - 14) - 7;
      return [x, y];
    });
    const data = { idx: i, x0: xOffset, x1: xOffset + w, pts, stage: s };
    xOffset += w;
    return data;
  });
  const allPath = "M" + sections.flatMap(s => s.pts).map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
  const fillPath = allPath + ` L${W},${H} L0,${H} Z`;
  return (
    <svg viewBox={`0 0 ${W} ${H+18}`} width="100%" height={H+18} style={{ display: "block" }}>
      <path d={fillPath} fill="rgba(196, 90, 42, 0.08)"/>
      <path d={allPath} fill="none" stroke="var(--g-accent)" strokeWidth="1.5"/>
      {sections.map((s, i) => (
        <g key={i}>
          {i < sections.length - 1 && <line x1={s.x1} x2={s.x1} y1={0} y2={H} stroke="var(--g-rule-soft)" strokeWidth="1"/>}
          <rect x={s.x0} y={0} width={s.x1 - s.x0} height={H} fill={i === active ? "rgba(196,90,42,0.06)" : "transparent"} onClick={() => onClick(i)}/>
          {(i === active || i === 0 || i === sections.length - 1) && (
            <text x={s.x0 + 3} y={H + 12} className="mono" style={{ fontSize: 9, fill: i === active ? "var(--g-accent)" : "var(--g-ink-4)" }}>{s.stage.code.slice(-3)}</text>
          )}
        </g>
      ))}
    </svg>
  );
}

function ReportLineM({ kind, time, channels, active, alert, last }) {
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "10px 0", borderBottom: last ? "none" : "1px solid var(--g-rule-soft)" }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%",
        background: active ? (alert ? "var(--g-accent)" : "var(--g-good)") : "var(--g-rule)",
        marginRight: 10, flexShrink: 0,
      }}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600 }}>{kind}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{time}</div>
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {channels.map((c, i) => <ChannelChip compact key={i} kind={c}/>)}
      </div>
    </div>
  );
}

/* ─────────────────── Tab: Etappen ─────────────────── */
function DetailStages({ trip, active, onActive }) {
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
        <Eyebrow>{trip.stages.length} Etappen</Eyebrow>
        <MBtn variant="ghost" size="md" icon={<MIcon kind="plus" size={14}/>}>Etappe</MBtn>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {trip.stages.map((s, i) => (
          <StageCardM key={s.id} stage={s} active={i === active} onClick={() => onActive(i)} index={i}/>
        ))}
      </div>
    </>
  );
}

function StageCardM({ stage, active, onClick, index }) {
  const tone = stage.risk === "high" ? "bad" : stage.risk === "med" ? "warn" : "good";
  const toneColor = stage.risk === "high" ? "var(--g-bad)" : stage.risk === "med" ? "var(--g-warn)" : "var(--g-good)";
  return (
    <div onClick={onClick} style={{
      background: active ? "var(--g-accent-tint)" : "var(--g-card)",
      border: active ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
      borderLeft: active ? "3px solid var(--g-accent)" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", padding: "12px 14px",
      cursor: "pointer",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
        <div style={{ minWidth: 0, flex: 1 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 8, marginBottom: 2 }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.04em" }}>{stage.code}</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>· {stage.date}</span>
          </div>
          <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3 }}>{stage.title.replace(/^[^:]+: /,"")}</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 4 }}>
            {stage.km} km · ↑{stage.ascent} ↓{stage.descent} · {stage.waypoints.length} WP
          </div>
        </div>
        <Pill tone={tone}>{stage.risk === "high" ? "high" : stage.risk === "med" ? "med" : "low"}</Pill>
      </div>
    </div>
  );
}

/* ─────────────────── Tab: Metriken (Preview-Variante) ─────────────────── */
function DetailMetrics() {
  const metrics = [
    { name: "Temp", on: true }, { name: "Feels", on: true }, { name: "Luftf", on: false },
    { name: "Wind", on: true }, { name: "Böen", on: true }, { name: "Windri", on: true },
    { name: "Niedersch", on: true }, { name: "Regen%", on: true }, { name: "Gewitter", on: true },
    { name: "Schneefall", on: false }, { name: "Bewölkung", on: true }, { name: "Sicht", on: true },
    { name: "UV", on: true }, { name: "Nullgrad", on: true }, { name: "Taupunkt", on: false },
    { name: "CAPE", on: false }, { name: "Druck", on: false }, { name: "Strahlung", on: false },
  ];
  const onCount = metrics.filter(m => m.on).length;
  return (
    <>
      <Card padding={14} style={{ marginBottom: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 4 }}>
          <Eyebrow>Preset · Alpen-Trekking</Eyebrow>
          <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{onCount}/{metrics.length}</span>
        </div>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 5, marginTop: 10 }}>
          {metrics.map((m, i) => (
            <span key={i} className="mono" style={{
              fontSize: 11, padding: "5px 9px", borderRadius: "var(--g-r-2)",
              background: m.on ? "var(--g-ink)" : "transparent",
              color: m.on ? "var(--g-paper)" : "var(--g-ink-4)",
              border: m.on ? "1px solid var(--g-ink)" : "1px solid var(--g-rule)",
            }}>{m.name}</span>
          ))}
        </div>
      </Card>
      <MBtn variant="primary" block>Metriken bearbeiten →</MBtn>
    </>
  );
}

/* ─────────────────── Tab: Briefings ─────────────────── */
function DetailBriefings() {
  return (
    <>
      <Card padding={14} style={{ marginBottom: 10 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Zeitplan</Eyebrow>
        <BriefingScheduleRow label="Morgen-Briefing" time="06:00" sub="Vor Etappenstart, alles für den Tag" enabled/>
        <BriefingScheduleRow label="Abend-Briefing" time="18:00" sub="Nach Tagesende, Ausblick morgen" enabled/>
        <BriefingScheduleRow label="Alert-Trigger" time="Δ / Schwelle" sub="Sofort bei kritischer Änderung" enabled last/>
      </Card>
      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Aktive Kanäle</Eyebrow>
        <ChannelRow dense kind="Email"    target="gregor_zwanzig@henemm.com" active/>
        <ChannelRow dense kind="Signal"   target="+49 151 ••• 8847" active/>
        <ChannelRow dense kind="Telegram" target="@gregor_henemm"/>
        <ChannelRow dense kind="SMS"      target="+49 151 ••• 8847" sub="Fallback" last/>
      </Card>
      <MBtn variant="ghost" block>Zeitplan & Kanäle bearbeiten →</MBtn>
    </>
  );
}

/* ─────────────────── Tab: Alerts ─────────────────── */
function DetailAlerts() {
  return (
    <>
      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Schwellen · aktiv</Eyebrow>
        <ThresholdRow divider="solid" label="Wind / Böen" value="≥ 50 km/h"/>
        <ThresholdRow divider="solid" label="Niederschlag" value="≥ 10 mm/h"/>
        <ThresholdRow divider="solid" label="Gewitter-Wahrsch." value="≥ 40 %"/>
        <ThresholdRow divider="solid" label="Nullgrad-Grenze" value="−200 m unter Trip" last/>
      </Card>
      <Card padding={14} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 6 }}>Letzte Auslöser · 7 Tage</Eyebrow>
        {MOCK_ALERTS_RECENT.map((a, i) => (
          <AlertRow variant="dot" divider="dashed" key={i} alert={a} last={i === MOCK_ALERTS_RECENT.length - 1}/>
        ))}
      </Card>
      <MBtn variant="ghost" block>Schwellen bearbeiten →</MBtn>
    </>
  );
}

/* ─────────────────── Tab: Vorschau ─────────────────── */
function DetailVorschau() {
  return (
    <>
      <Card padding={14} style={{ marginBottom: 10 }}>
        <Eyebrow style={{ marginBottom: 6 }}>Nächstes Briefing</Eyebrow>
        <div style={{ fontSize: 15, fontWeight: 600 }}>Morgen, Do 07. Mai · 06:00</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 3 }}>
          KHW_00b · Birnlücke → Clarahütte
        </div>
      </Card>
      <MBtn variant="primary" block size="lg" style={{ marginBottom: 8 }}>Email-Vorschau öffnen</MBtn>
      <MBtn variant="ghost" block size="lg" style={{ marginBottom: 8 }}>SMS / Signal-Vorschau</MBtn>
      <MBtn variant="ghost" block size="lg">Test jetzt an mich senden</MBtn>
    </>
  );
}

window.ScreenTripDetailMobile = ScreenTripDetailMobile;
