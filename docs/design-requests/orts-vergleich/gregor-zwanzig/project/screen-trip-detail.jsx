/* Screen: Trip-Uebersicht — Hauptbuehne pro Trip
 * Von hier verzweigt alles: Etappen, Wegpunkte, Wetter-Metriken, Empfaenger, Briefings.
 * Status: Geplant / Aktiv (Briefings laufen) / Pausiert / Archiviert
 */

function ScreenTripDetail({ initialTab = "uebersicht" } = {}) {
  const trip = MOCK_TRIP;
  const [activeStage, setActiveStage] = React.useState(1);
  const [tab, setTab] = React.useState(initialTab);
  const TABS = [
    { id: "uebersicht", label: "Übersicht" },
    { id: "etappen", label: "Etappen & Wegpunkte", badge: String(trip.stages.length) },
    { id: "metriken", label: "Wetter-Metriken", badge: "14" },
    { id: "zeitplan", label: "Briefing-Zeitplan" },
    { id: "alerts", label: "Alerts", badge: "2", accent: true },
    { id: "vorschau", label: "Vorschau" },
  ];

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }} data-screen-label="Trip-Detail (Desktop)">
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.14}/>

        {/* Breadcrumb + Status + Aktionen */}
        <div style={{ position: "relative", padding: "16px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.06em" }}>
            <span style={{ opacity: 0.6 }}>Trips</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>{trip.shortName}</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Btn variant="ghost" size="sm">Pausieren</Btn>
            <Btn variant="ghost" size="sm">Archivieren</Btn>
            <Btn variant="accent" size="sm">Test-Briefing senden</Btn>
          </div>
        </div>

        {/* Hero: Trip-Identity */}
        <div style={{ position: "relative", padding: "26px 40px 18px", maxWidth: 1480 }}>
          <Eyebrow>Trip · {trip.region}</Eyebrow>
          <h1 style={{ fontSize: 38, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 0", lineHeight: 1.1 }}>{trip.name}</h1>
          <div style={{ display: "flex", alignItems: "center", gap: 12, marginTop: 12, flexWrap: "wrap" }}>
            <span style={{ fontSize: 13, color: "var(--g-ink-2)" }}>läuft seit Tag 2</span>
            <StatusBadge status="active"/>
            <span className="mono" style={{ fontSize: 13, color: "var(--g-ink-3)" }}>
              {trip.startDate} → {trip.endDate} · {trip.stages.length} Etappen · {trip.totalKm} km · ↑{trip.totalAscent} m
            </span>
          </div>
        </div>

        {/* Tab-Navigation — interaktiv */}
        <div style={{ position: "relative", borderBottom: "1px solid var(--g-rule)", padding: "0 40px", display: "flex", gap: 0, overflowX: "auto" }}>
          {TABS.map(t => (
            <Tab key={t.id} label={t.label} badge={t.badge} accent={t.accent} active={t.id === tab} onClick={() => setTab(t.id)}/>
          ))}
        </div>

        {/* Tab-Inhalt */}
        {tab === "uebersicht" && <HubOverview trip={trip} activeStage={activeStage} onStage={setActiveStage} onJump={setTab}/>}
        {tab === "etappen" && <ScreenWaypointEditor embedded initialActiveIdx={1}/>}
        {tab === "metriken" && <ScreenMetricsEditor embedded/>}
        {tab === "zeitplan" && <HubSchedule/>}
        {tab === "alerts" && <ScreenAlertConfig embedded/>}
        {tab === "vorschau" && <HubPreview trip={trip}/>}
      </main>
    </div>
  );
}

/* ─────────────────── Hub-Tab-Inhalte ─────────────────── */

/* Tab 1 · Übersicht — read-only Cockpit. Jede Sektion springt per Link in den passenden Editor-Tab. */
function HubOverview({ trip, activeStage, onStage, onJump }) {
  return (
    <div style={{ position: "relative", padding: "32px 40px 60px", display: "grid", gridTemplateColumns: "1fr 380px", gap: 32, maxWidth: 1480 }}>
      <div>
        <SectionH eyebrow="Etappen" title="Reihenfolge & Profil" right={<Btn variant="ghost" size="sm" onClick={() => onJump("etappen")}>Im Editor öffnen →</Btn>}/>
        <Card padding={20}>
          <FullProfile stages={trip.stages} active={activeStage} onClick={onStage}/>
        </Card>
        <div style={{ marginTop: 24 }}>
          {trip.stages.map((s, i) => (
            <StageRow key={i} stage={s} index={i} active={i === activeStage} onClick={() => onStage(i)}/>
          ))}
        </div>
        <div style={{ marginTop: 40 }}>
          <SectionH eyebrow="Wetter-Metriken" title="14 Spalten · Preset Alpen-Trekking" right={<Btn variant="ghost" size="sm" onClick={() => onJump("metriken")}>Bearbeiten →</Btn>}/>
          <MetricsPreview/>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
        <Card padding={18}>
          <Eyebrow>Briefings laufen</Eyebrow>
          <div style={{ marginTop: 12 }}>
            <ReportLine kind="morning" time="06:00" channels={["email","signal"]} active/>
            <ReportLine kind="evening" time="18:00" channels={["email"]} active/>
            <ReportLine kind="alert" time="bei Δ / Schwellwert" channels={["signal"]} active alert/>
          </div>
          <Btn variant="ghost" size="sm" style={{ marginTop: 12, width: "100%" }} onClick={() => onJump("zeitplan")}>Zeitplan bearbeiten →</Btn>
        </Card>

        <Card padding={18}>
          <Eyebrow>Alerts (letzte 7 Tage)</Eyebrow>
          <div style={{ marginTop: 12 }}>
            <AlertRow variant="dot" alert={MOCK_ALERTS_RECENT[0]}/>
            <AlertRow variant="dot" alert={MOCK_ALERTS_RECENT[1]}/>
          </div>
          <Btn variant="ghost" size="sm" style={{ marginTop: 12, width: "100%" }} onClick={() => onJump("alerts")}>Alle Alerts →</Btn>
        </Card>

        <Card padding={18} style={{ background: "var(--g-card-alt)" }}>
          <Eyebrow>Vorschau</Eyebrow>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginTop: 6, marginBottom: 12 }}>
            Wie sieht das nächste Briefing aus?
          </div>
          <Btn variant="primary" size="sm" style={{ width: "100%" }} onClick={() => onJump("vorschau")}>Vorschau öffnen</Btn>
        </Card>
      </div>
    </div>
  );
}

/* Tab 4 · Briefing-Zeitplan */
function HubSchedule() {
  return (
    <div style={{ position: "relative", padding: "32px 40px 60px", maxWidth: 1480 }}>
      <Eyebrow>Briefing-Zeitplan</Eyebrow>
      <h2 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 8px" }}>Wann geht was an welchen Kanal?</h2>
      <div style={{ fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55, maxWidth: 720, marginBottom: 24 }}>
        Drei Briefing-Typen, je eigener Zeitpunkt und eigene Kanäle. Gelesen werden sie im Kanal — die App schickt sie automatisch.
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 20, maxWidth: 980 }}>
        <HubScheduleCard title="Morgen-Briefing" time="06:00" sub="Vor Etappenstart — alles für den Tag" channels={["email","signal"]} on/>
        <HubScheduleCard title="Abend-Briefing" time="18:00" sub="Nach Tagesende — Ausblick auf morgen" channels={["email"]} on/>
        <HubScheduleCard title="Alert-Trigger" time="bei Δ / Schwellwert" sub="Sofort bei kritischer Änderung" channels={["signal"]} on alert/>
        <HubScheduleCard title="Mehrtages-Trend" time="So 18:00" sub="3–7-Tage-Ausblick (optional)" channels={["email"]}/>
      </div>
    </div>
  );
}

function HubScheduleCard({ title, time, sub, channels, on, alert }) {
  const [enabled, setEnabled] = React.useState(!!on);
  return (
    <Card padding={18}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12 }}>
        <div>
          <div style={{ fontSize: 15, fontWeight: 600 }}>{title}</div>
          <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 2 }}>{sub}</div>
        </div>
        <Switch checked={enabled} onChange={setEnabled} tone={alert ? "accent" : "good"}/>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--g-rule-soft)" }}>
        <span className="mono" style={{ fontSize: 13, fontWeight: 600, color: enabled ? "var(--g-ink)" : "var(--g-ink-4)" }}>{time}</span>
        <span style={{ flex: 1 }}/>
        <div style={{ display: "flex", gap: 4 }}>
          {channels.map((c, i) => <ChannelDot key={i} kind={c}/>)}
        </div>
      </div>
    </Card>
  );
}

/* Tab 6 · Vorschau — Verifikation, kein Konsum-Surface. */
function HubPreview({ trip }) {
  const [ch, setCh] = React.useState("email");
  return (
    <div style={{ position: "relative", padding: "28px 40px 60px", maxWidth: 1480 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end", gap: 24, marginBottom: 20 }}>
        <div style={{ maxWidth: 680 }}>
          <Eyebrow>Vorschau · Verifikation</Eyebrow>
          <h2 style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 6px" }}>So sieht das nächste Briefing aus</h2>
          <div style={{ fontSize: 13.5, color: "var(--g-ink-3)", lineHeight: 1.5 }}>
            Pixel-Vorschau zum Gegencheck deiner Konfiguration. Gelesen wird das echte Briefing im jeweiligen Kanal.
          </div>
        </div>
        <Segmented items={[{ id: "email", label: "Email" }, { id: "sms", label: "SMS / Signal" }]} value={ch} onChange={setCh}/>
      </div>
      <div style={{ display: "flex", justifyContent: "center", padding: 24, background: "#e9e6dc", borderRadius: "var(--g-r-3)", border: "1px solid var(--g-rule)" }}>
        {ch === "email"
          ? <div style={{ width: 680 }}><EmailPreview stage={trip.stages[1]} trip={trip}/></div>
          : <div style={{ width: 380 }}><SMSPreview stage={trip.stages[1]} trip={trip}/></div>}
      </div>
    </div>
  );
}

/* ─────────────────── Bausteine ─────────────────── */

function StatusBadge({ status }) {
  const map = {
    planned:    { label: "Geplant",    bg: "var(--g-info)",   dot: "var(--g-info)" },
    active:     { label: "Aktiv · Briefings laufen", bg: "var(--g-good)",   dot: "var(--g-good)" },
    paused:     { label: "Pausiert",   bg: "var(--g-warn)",   dot: "var(--g-warn)" },
    archived:   { label: "Archiviert", bg: "var(--g-ink-3)",  dot: "var(--g-ink-3)" },
  };
  const s = map[status] || map.active;
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      fontSize: 11, padding: "5px 10px", borderRadius: "var(--g-r-pill)",
      background: "transparent", border: `1px solid ${s.bg}`, color: s.bg,
      letterSpacing: "0.06em", fontWeight: 600,
    }}>
      <span style={{ width: 6, height: 6, borderRadius: "50%", background: s.dot }}/>
      {s.label.toUpperCase()}
    </span>
  );
}

function Tab({ label, active, badge, accent, onClick }) {
  return (
    <div onClick={onClick} style={{
      padding: "12px 16px", cursor: "pointer", fontSize: 13, fontWeight: active ? 600 : 500,
      color: active ? "var(--g-ink)" : "var(--g-ink-3)",
      borderBottom: active ? "2px solid var(--g-accent)" : "2px solid transparent",
      marginBottom: -1, display: "flex", alignItems: "center", gap: 6,
    }}>
      {label}
      {badge && (
        <span className="mono" style={{
          fontSize: 10, fontWeight: 600, padding: "2px 6px", borderRadius: 3,
          background: accent ? "var(--g-accent)" : "var(--g-paper-deep)",
          color: accent ? "#fff" : "var(--g-ink-3)",
        }}>{badge}</span>
      )}
    </div>
  );
}

function FullProfile({ stages, active, onClick }) {
  const all = stages.flatMap(s => s.profile);
  const min = Math.min(...all), max = Math.max(...all);
  const range = max - min || 1;
  const W = 1000, H = 140;

  let xOffset = 0;
  const totalKm = stages.reduce((sum, s) => sum + s.km, 0);
  const sectionsData = stages.map((s, i) => {
    const w = (s.km / totalKm) * W;
    const pts = s.profile.map((v, j) => {
      const x = xOffset + (j / (s.profile.length - 1)) * w;
      const y = H - ((v - min) / range) * (H - 16) - 8;
      return [x, y];
    });
    const data = { idx: i, x0: xOffset, x1: xOffset + w, pts, stage: s };
    xOffset += w;
    return data;
  });

  const allPath = "M" + sectionsData.flatMap(s => s.pts).map(([x,y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" L");
  const fillPath = allPath + ` L${W},${H} L0,${H} Z`;

  return (
    <svg viewBox={`0 0 ${W} ${H+22}`} width="100%" style={{ display: "block" }}>
      <path d={fillPath} fill="rgba(196, 90, 42, 0.08)"/>
      <path d={allPath} fill="none" stroke="var(--g-accent)" strokeWidth="1.6"/>
      {sectionsData.map((s, i) => (
        <g key={i}>
          {i < sectionsData.length - 1 && <line x1={s.x1} x2={s.x1} y1={0} y2={H} stroke="var(--g-rule-soft)" strokeWidth="1"/>}
          <rect x={s.x0} y={0} width={s.x1 - s.x0} height={H} fill={i === active ? "rgba(196,90,42,0.05)" : "transparent"} style={{ cursor: "pointer" }} onClick={() => onClick(i)}/>
          <text x={s.x0 + 4} y={H + 14} className="mono" style={{ fontSize: 9, fill: i === active ? "var(--g-accent)" : "var(--g-ink-4)" }}>{s.stage.code}</text>
        </g>
      ))}
    </svg>
  );
}

function StageRow({ stage, active, onClick, index }) {
  const tone = stage.risk === "high" ? "bad" : stage.risk === "med" ? "warn" : "good";
  return (
    <div onClick={onClick} style={{
      display: "grid", gridTemplateColumns: "60px 1fr 280px 100px",
      gap: 16, padding: "14px 18px", borderBottom: "1px solid var(--g-rule-soft)",
      cursor: "pointer", background: active ? "rgba(196, 90, 42, 0.05)" : "transparent",
      borderLeft: active ? "3px solid var(--g-accent)" : "3px solid transparent",
      alignItems: "center",
    }}>
      <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{stage.code}</div>
      <div>
        <div style={{ fontSize: 14, fontWeight: 500 }}>{stage.title.replace(/^[^:]+: /,"")}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
          {stage.date} · {stage.km} km · ↑{stage.ascent} ↓{stage.descent} · max {stage.maxElev} m · {stage.waypoints.length} WP
        </div>
      </div>
      <div style={{ fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.4, fontStyle: "italic" }}>
        {stage.summary}
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <Pill tone={tone}>{stage.risk === "high" ? "Risiko" : stage.risk === "med" ? "Achten" : "OK"}</Pill>
      </div>
    </div>
  );
}

function ReportLine({ kind, time, channels, active, alert }) {
  const labels = { morning: "Morning", evening: "Evening", alert: "Alert" };
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "8px 0", borderBottom: "1px solid var(--g-rule-soft)" }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%",
        background: active ? (alert ? "var(--g-accent)" : "var(--g-good)") : "var(--g-rule)",
        marginRight: 10,
      }}/>
      <div style={{ flex: 1 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{labels[kind]}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)" }}>{time}</div>
      </div>
      <div style={{ display: "flex", gap: 4 }}>
        {channels.map((c, i) => <ChannelDot key={i} kind={c}/>)}
      </div>
    </div>
  );
}

function ChannelDot({ kind }) {
  const map = { email: "✉", signal: "▲", telegram: "✈", sms: "·" };
  return <span className="mono" style={{ width: 18, height: 18, borderRadius: 3, background: "var(--g-paper-deep)", display: "inline-flex", alignItems: "center", justifyContent: "center", fontSize: 10, color: "var(--g-ink-2)" }}>{map[kind]}</span>;
}

function MetricsPreview() {
  const metrics = [
    { name: "Temp", on: true }, { name: "Feels", on: true }, { name: "Luftf", on: false },
    { name: "Taup", on: false }, { name: "Wind", on: true }, { name: "Böen", on: true },
    { name: "Windri", on: true }, { name: "Niedersch", on: true }, { name: "Regen%", on: true },
    { name: "Gewitter", on: true }, { name: "CAPE", on: false }, { name: "Schneefall", on: false },
    { name: "Niedersch.art", on: false }, { name: "Bewölkung", on: true },
    { name: "tiefe Wolken", on: false }, { name: "mittl. Wolken", on: false }, { name: "hohe Wolken", on: false },
    { name: "Sicht", on: true }, { name: "Sonnenschein", on: false }, { name: "UV", on: true },
    { name: "Druck", on: false }, { name: "Nullgrad", on: true }, { name: "Schneehöhe", on: false },
    { name: "Neuschnee", on: false }, { name: "Boden Temp", on: false }, { name: "Strahlung", on: false },
  ];
  return (
    <Card padding={20}>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {metrics.map((m, i) => (
          <span key={i} className="mono" style={{
            fontSize: 11, padding: "5px 10px", borderRadius: 3,
            background: m.on ? "var(--g-ink)" : "transparent",
            color: m.on ? "var(--g-paper)" : "var(--g-ink-4)",
            border: m.on ? "1px solid var(--g-ink)" : "1px solid var(--g-rule)",
            opacity: m.on ? 1 : 0.6,
          }}>{m.name}</span>
        ))}
      </div>
      <div style={{ marginTop: 14, paddingTop: 14, borderTop: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
          14 von 26 aktiv · Preset <span style={{ color: "var(--g-ink)", fontWeight: 600 }}>Alpen-Trekking</span>
        </span>
        <Btn variant="ghost" size="xs">Als eigenes Preset speichern</Btn>
      </div>
    </Card>
  );
}

window.ScreenTripDetail = ScreenTripDetail;
