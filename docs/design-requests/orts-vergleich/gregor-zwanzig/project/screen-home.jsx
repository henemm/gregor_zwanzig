/* Screen: Home — aktiver Trip als Hero */

function ScreenHome() {
  const trip = MOCK_TRIP;
  const today = MOCK_TODAY_STAGE;
  const tomorrow = trip.stages[1];

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="home"/>
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.22}/>

        {/* Topbar */}
        <div style={{
          position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "20px 40px", borderBottom: "1px solid var(--g-rule-soft)",
        }}>
          <div>
            <Eyebrow>Übersicht · Mi, 06. Mai 2026</Eyebrow>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, letterSpacing: "-0.005em" }}>Guten Morgen, Gregor.</div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <Btn variant="ghost" size="sm">Test-Briefing senden</Btn>
            <Btn variant="primary" size="sm" icon={<span style={{ fontSize: 16, lineHeight: 0 }}>+</span>}>Neuer Trip</Btn>
          </div>
        </div>

        <div style={{ position: "relative", padding: "32px 40px 80px", maxWidth: 1320 }}>

          {/* HERO: Aktiver Trip + Briefings heute */}
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24, marginBottom: 40 }}>

            {/* Aktiver Trip Card */}
            <Card padding={0} style={{ overflow: "hidden", borderLeft: "3px solid var(--g-accent)" }}>
              <div style={{ padding: "24px 28px 0" }}>
                <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 8 }}>
                  <Pill tone="accent"><Dot tone="bad" size={6}/> Live · Tag 1 von 12</Pill>
                  <Pill tone="ghost">Sommer-Trekking</Pill>
                </div>
                <div style={{ fontSize: 36, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.05, marginBottom: 6 }}>
                  KHW 403
                </div>
                <div style={{ fontSize: 17, color: "var(--g-ink-2)", marginBottom: 18 }}>
                  Karnischer Höhenweg · Toblach → Nötsch · {trip.totalKm.toFixed(1)} km · ↑{trip.totalAscent} ↓{trip.totalDescent}
                </div>

                {/* Heutige Etappe */}
                <div style={{ background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-3)", padding: "16px 18px", marginBottom: 16 }}>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 12 }}>
                    <div>
                      <Eyebrow style={{ marginBottom: 4 }}>Heutige Etappe · {today.code}</Eyebrow>
                      <div style={{ fontSize: 18, fontWeight: 600 }}>{today.title}</div>
                      <div className="mono" style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 4 }}>
                        08:00 – 12:45 · {today.km} km · ↑{today.ascent} ↓{today.descent} · max {today.maxElev} m
                      </div>
                    </div>
                    <Pill tone="good">Risk · low</Pill>
                  </div>
                  <ElevSparkline data={today.profile} width={520} height={56}/>
                  <div style={{ fontSize: 14, color: "var(--g-ink-2)", marginTop: 14, paddingTop: 14, borderTop: "1px dashed var(--g-rule-soft)", lineHeight: 1.55 }}>
                    {today.summary}
                  </div>
                </div>
              </div>

              {/* Etappen-Streifen */}
              <div style={{ borderTop: "1px solid var(--g-rule-soft)", padding: "14px 28px 18px", background: "var(--g-card)" }}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 10 }}>
                  <Eyebrow>Etappen-Verlauf</Eyebrow>
                  <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Alle anzeigen →</a>
                </div>
                <div style={{ display: "flex", gap: 4, overflow: "hidden" }}>
                  {trip.stages.map((s, i) => (
                    <StagePill key={s.id} stage={s} state={i === 0 ? "active" : "future"}/>
                  ))}
                  {Array.from({length: 7}).map((_, i) => (
                    <StagePill key={"future"+i} stage={{code: `KHW_${String(i+4).padStart(2,"0")}`, risk: "low"}} state="muted"/>
                  ))}
                </div>
              </div>
            </Card>

            {/* Briefings heute */}
            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <Card padding={20}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
                  <div>
                    <Eyebrow style={{ marginBottom: 4 }}>Heute</Eyebrow>
                    <div style={{ fontSize: 17, fontWeight: 600 }}>Was geht raus</div>
                  </div>
                  <Pill tone="good">Alle Kanäle ok</Pill>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {MOCK_REPORT_TIMELINE.map((r, i) => (
                    <BriefingTimelineRow key={i} report={r}/>
                  ))}
                </div>
              </Card>

              <Card padding={20}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <div>
                    <Eyebrow style={{ marginBottom: 4 }}>Alerts · letzte 24 h</Eyebrow>
                    <div style={{ fontSize: 17, fontWeight: 600 }}>2 ausgelöst</div>
                  </div>
                  <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Schwellen →</a>
                </div>
                {MOCK_ALERTS_RECENT.map((a, i) => (
                  <AlertRow key={i} alert={a}/>
                ))}
              </Card>
            </div>
          </div>

          {/* Naechste Etappe */}
          <div style={{ marginBottom: 40 }}>
            <Card padding={20}>
              <SectionH eyebrow="Morgen, Do · 07. Mai" title={tomorrow.title.replace(/^.*: /, "")} right={<Pill tone="warn">Risk · med</Pill>}/>
              <div className="mono" style={{ fontSize: 12, color: "var(--g-ink-3)", marginBottom: 12 }}>
                {tomorrow.code} · {tomorrow.km} km · ↑{tomorrow.ascent} ↓{tomorrow.descent} · max {tomorrow.maxElev} m
              </div>
              <ElevSparkline data={tomorrow.profile} width={480} height={50}/>
              <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginTop: 12, paddingTop: 12, borderTop: "1px dashed var(--g-rule-soft)", lineHeight: 1.55 }}>
                {tomorrow.summary}
              </div>
            </Card>
          </div>

          {/* Aktive Orts-Vergleiche — Kachel-Grid (Charter §3). Klick → Detail. */}
          <div style={{ marginBottom: 40 }}>
            <SectionH
              eyebrow="Workspace"
              title="Aktive Orts-Vergleiche"
              kicker="Laufen automatisch — Briefing kommt in die Kanäle, nicht hierher"
              right={<Btn variant="quiet" size="sm">Alle anzeigen</Btn>}
            />
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 16 }}>
              {(window.MOCK_COMPARE_SUBS || []).filter(s => s.status === "active").map(s => (
                <CompareTile
                  key={s.id}
                  sub={s}
                  compact
                  trailing={
                    <button title="Bearbeiten" onClick={(e) => e.stopPropagation()} style={{
                      width: 28, height: 28, display: "inline-flex", alignItems: "center", justifyContent: "center",
                      background: "transparent", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", cursor: "pointer",
                    }}>
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-2)" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M14 4l6 6L9 21H3v-6z"/></svg>
                    </button>
                  }
                />
              ))}
            </div>
          </div>

          {/* Archiv */}
          <Card padding={20}>
            <SectionH eyebrow="Archiv" title="Frühere Trips" kicker="8 abgeschlossene Mehrtages-Trips" right={<Btn variant="quiet" size="sm">Alle anzeigen</Btn>}/>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12 }}>
              {MOCK_ARCHIVED.slice(0, 4).map(t => (
                <div key={t.id} style={{
                  padding: "14px 16px", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)",
                  background: "var(--g-card-alt)",
                }}>
                  <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 4 }}>{t.dates}</div>
                  <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.3, marginBottom: 6 }}>{t.name}</div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{t.stages} Etappen</div>
                </div>
              ))}
            </div>
          </Card>
        </div>
      </main>
    </div>
  );
}

window.ScreenHome = ScreenHome;
