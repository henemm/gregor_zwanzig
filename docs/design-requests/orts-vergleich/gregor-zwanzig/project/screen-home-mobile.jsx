/* Mobile · Übersicht / Heute
 * Hero: aktiver Trip, heutige Etappe, Sparkline, Briefings-Heute, Alerts.
 * Pattern: vertikale Card-Stacks. Bottom-Nav: home aktiv. Top-App-Bar mit Hamburger + Glocke.
 */

function ScreenHomeMobile() {
  const trip = MOCK_TRIP;
  const today = MOCK_TODAY_STAGE;
  const tomorrow = trip.stages[1];

  const right = (
    <div style={{ display: "flex" }}>
      <IconBtn kind="bell" badge={2} label="Alerts"/>
      <IconBtn kind="plus" label="Neuer Trip"/>
    </div>
  );

  return (
    <MobileShell active="home" title="Guten Morgen, Gregor" eyebrow="Mi · 06. Mai" right={right} phoneHeight={812}>
      <ScreenScroll padding={0}>
        <div style={{ padding: "12px 16px 20px" }}>

          {/* Aktiver Trip Hero */}
          <div style={{
            background: "var(--g-card)", borderRadius: "var(--g-r-3)",
            border: "1px solid var(--g-rule)", borderLeft: "3px solid var(--g-accent)",
            boxShadow: "var(--g-shadow-1)", overflow: "hidden", marginBottom: 16,
          }}>
            <div style={{ padding: "16px 16px 0" }}>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
                <Pill tone="accent"><Dot tone="bad" size={6}/> Live · Tag 1/12</Pill>
                <Pill tone="ghost">Sommer-Trekking</Pill>
              </div>
              <div style={{ fontSize: 28, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.05 }}>KHW 403</div>
              <div style={{ fontSize: 14, color: "var(--g-ink-2)", marginTop: 4, lineHeight: 1.4 }}>
                Karnischer Höhenweg<br/>
                <span className="mono" style={{ fontSize: 12, color: "var(--g-ink-3)" }}>
                  {trip.totalKm.toFixed(1)} km · ↑{trip.totalAscent} ↓{trip.totalDescent}
                </span>
              </div>
            </div>

            {/* Heutige Etappe */}
            <div style={{ padding: "14px 16px 16px", marginTop: 14, background: "var(--g-card-alt)", borderTop: "1px solid var(--g-rule-soft)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 10 }}>
                <div style={{ minWidth: 0 }}>
                  <Eyebrow style={{ marginBottom: 3 }}>Heute · {today.code}</Eyebrow>
                  <div style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.25 }}>{today.title.replace(/^.*: /, "")}</div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 4 }}>
                    08:00–12:45 · {today.km} km · ↑{today.ascent} ↓{today.descent}
                  </div>
                </div>
                <Pill tone="good">low</Pill>
              </div>
              <ElevSparkline data={today.profile} width={310} height={48}/>
              <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginTop: 10, paddingTop: 10, borderTop: "1px dashed var(--g-rule-soft)", lineHeight: 1.5 }}>
                {today.summary}
              </div>
            </div>

            {/* Etappen-Strip */}
            <div style={{ padding: "12px 16px 14px", borderTop: "1px solid var(--g-rule-soft)", display: "flex", gap: 4, overflowX: "auto", WebkitOverflowScrolling: "touch" }}>
              {trip.stages.map((s, i) => (
                <div key={s.id} style={{
                  flex: "0 0 36px", padding: "6px 4px", borderRadius: "var(--g-r-2)",
                  background: i === 0 ? "var(--g-accent-tint)" : "var(--g-paper)",
                  border: i === 0 ? "1px solid var(--g-accent)" : "1px solid var(--g-rule-soft)",
                  textAlign: "center",
                }}>
                  <div className="mono" style={{ fontSize: 9, color: i === 0 ? "var(--g-accent-deep)" : "var(--g-ink-3)", letterSpacing: "0.04em", fontWeight: 600 }}>
                    {s.code.slice(-3)}
                  </div>
                  <div style={{ marginTop: 4, height: 3, background: s.risk === "high" ? "var(--g-bad)" : s.risk === "med" ? "var(--g-warn)" : "var(--g-good)", borderRadius: 2 }}/>
                </div>
              ))}
              {Array.from({ length: 6 }).map((_, i) => (
                <div key={"f"+i} style={{ flex: "0 0 36px", padding: "6px 4px", background: "var(--g-paper-deep)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", opacity: 0.5, textAlign: "center" }}>
                  <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>{String(i+4).padStart(2,"0")}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Briefings heute */}
          <Card padding={16} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <Eyebrow style={{ marginBottom: 3 }}>Heute</Eyebrow>
                <div style={{ fontSize: 16, fontWeight: 600 }}>Was geht raus</div>
              </div>
              <Pill tone="good">3 ok</Pill>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
              {MOCK_REPORT_TIMELINE.map((r, i) => (
                <BriefingTimelineRow dense key={i} report={r}/>
              ))}
            </div>
          </Card>

          {/* Alerts */}
          <Card padding={16} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
              <div>
                <Eyebrow style={{ marginBottom: 3 }}>Alerts · 24 h</Eyebrow>
                <div style={{ fontSize: 16, fontWeight: 600 }}>2 ausgelöst</div>
              </div>
              <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Schwellen →</a>
            </div>
            {MOCK_ALERTS_RECENT.map((a, i) => (
              <AlertRow key={i} alert={a} last={i === MOCK_ALERTS_RECENT.length - 1}/>
            ))}
          </Card>

          {/* Morgen Card */}
          <Card padding={16} style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 8 }}>
              <div>
                <Eyebrow style={{ marginBottom: 3 }}>Morgen · Do 07. Mai</Eyebrow>
                <div style={{ fontSize: 16, fontWeight: 600, lineHeight: 1.25 }}>{tomorrow.title.replace(/^.*: /, "")}</div>
              </div>
              <Pill tone="warn">med</Pill>
            </div>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginBottom: 10 }}>
              {tomorrow.code} · {tomorrow.km} km · ↑{tomorrow.ascent} ↓{tomorrow.descent}
            </div>
            <ElevSparkline data={tomorrow.profile} width={310} height={44}/>
            <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginTop: 10, paddingTop: 10, borderTop: "1px dashed var(--g-rule-soft)", lineHeight: 1.5 }}>
              {tomorrow.summary}
            </div>
          </Card>

          {/* Aktive Orts-Vergleiche */}
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8, padding: "0 2px" }}>
              <Eyebrow>Aktive Orts-Vergleiche</Eyebrow>
              <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Alle →</a>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {(window.MOCK_COMPARE_SUBS || []).filter(s => s.status === "active").map(s => (
                <CompareTile
                  key={s.id}
                  sub={s}
                  dense compact
                  trailing={<MIcon kind="chevron" size={16} color="var(--g-ink-4)"/>}
                />
              ))}
            </div>
          </div>

          {/* Quick-Action: Test-Briefing */}
          <MBtn variant="ghost" block size="lg">Test-Briefing jetzt senden</MBtn>
        </div>
      </ScreenScroll>
    </MobileShell>
  );
}

window.ScreenHomeMobile = ScreenHomeMobile;
