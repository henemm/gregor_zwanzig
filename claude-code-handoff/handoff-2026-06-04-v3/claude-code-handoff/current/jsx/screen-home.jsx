/* Screen: Home — Cockpit (prioritätsbasierter Einzel-Hero).
 *
 * Produkt-Modell (PO 2026-06-03): In der Praxis ist man entweder
 *   • mitten in einem Multiday-Trip  ODER
 *   • auf einer Hütte / im Skigebiet und nutzt einen Orts-Vergleich.
 * Die Modi sind faktisch exklusiv. Es gibt deshalb zu jedem Zeitpunkt EINEN
 * aktiven Kontext — keinen gemischten globalen Strom.
 *
 * Konsequenzen, die diese Datei umsetzt:
 *   1 · EIN HERO nach Priorität:
 *         liveTrip  → Trip ist der Hero        (mode="trip")
 *         sonst     → aktiver Vergleich ist Hero (mode="compare")
 *   2 · „Was geht raus" ist EHRLICH auf den aktiven Kontext gescopet und trägt
 *       dessen Namen im Titel — kein irreführender »globaler« Anstrich mehr.
 *   3 · ÜBERLAPPUNG: Läuft nebenher noch ein Orts-Vergleich (man beobachtet ein
 *       paar Einzelorte zusätzlich zum Trip), bekommt er KEINE volle Hero-
 *       Behandlung, sondern eine schlanke Status-Zeile „Außerdem beobachtet"
 *       direkt unter dem Cockpit — glanceable, mit nächstem Versand.
 *   4 · Das alte Streck-Artefakt (Riesen-Karte mit leerem Loch) ist behoben:
 *       die Status-Spalten richten sich an der Oberkante aus (align-items:start),
 *       die Hero-Karte wird nur so hoch wie ihr Inhalt.
 *
 * Der reine Planungs-/Leerzustand (gar nichts live) lebt separat in
 * ScreenHomePlanning.
 */

/* Synthetischer Versand-Verlauf für einen Orts-Vergleich (aus sub-Feldern). */
function homeCompareTimeline(sub) {
  const place = `${sub.locationIds.length} Orte · ${sub.region}`;
  return [
    { when: `Zuletzt · ${sub.lastSent}`, kind: "Vergleich", channels: sub.channels, status: "sent",      etappe: place },
    { when: `Nächster · ${sub.nextSend}`, kind: "Vergleich", channels: sub.channels, status: "scheduled", etappe: place },
  ];
}

/* ─────────────────── Hero: aktiver Trip ─────────────────── */
function HomeHeroTrip({ trip, dayCurrent, dayTotal }) {
  return (
    <Card padding={0} style={{ overflow: "hidden", borderLeft: "3px solid var(--g-accent)" }}>
      <div style={{ padding: "22px 26px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          <Pill tone="accent"><Dot tone="bad" size={6}/> Live · Tag {dayCurrent} von {dayTotal}</Pill>
          <Pill tone="ghost">Sommer-Trekking</Pill>
        </div>
        <div style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.05, marginBottom: 6 }}>
          {trip.shortName}
        </div>
        <div style={{ fontSize: 15, color: "var(--g-ink-2)", marginBottom: 20 }}>
          Karnischer Höhenweg · Toblach → Nötsch · {trip.totalKm.toFixed(1)} km
        </div>

        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-2)", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600 }}>Tag {dayCurrent} / {dayTotal}</span>
            <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>06. Mai → 17. Mai 2026</span>
          </div>
          <div style={{ height: 6, borderRadius: 999, background: "var(--g-paper-deep)", overflow: "hidden" }}>
            <div style={{ width: `${(dayCurrent / dayTotal) * 100}%`, height: "100%", background: "var(--g-accent)", borderRadius: 999 }}/>
          </div>
        </div>
      </div>

      <div style={{
        borderTop: "1px solid var(--g-rule-soft)", padding: "14px 26px", background: "var(--g-card-alt)",
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Eyebrow>Kanäle</Eyebrow>
          <div style={{ display: "flex", gap: 14 }}>
            {trip.channels.map(c => (
              <span key={c.kind} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--g-ink-2)" }}>
                <Dot tone="good" size={7}/>
                <span className="mono" style={{ textTransform: "capitalize" }}>{c.kind}</span>
              </span>
            ))}
          </div>
        </div>
        <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Trip öffnen →</a>
      </div>
    </Card>
  );
}

/* ─────────────────── Hero: aktiver Orts-Vergleich ─────────────────── */
function HomeHeroCompare({ sub }) {
  return (
    <Card padding={0} style={{ overflow: "hidden", borderLeft: "3px solid var(--g-accent)" }}>
      <div style={{ padding: "22px 26px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12, flexWrap: "wrap" }}>
          <Pill tone="accent"><Dot tone="good" size={6}/> Aktiv · läuft automatisch</Pill>
          <Pill tone="ghost">{sub.profileLabel}</Pill>
        </div>
        <div style={{ fontSize: 34, fontWeight: 600, letterSpacing: "-0.02em", lineHeight: 1.05, marginBottom: 6 }}>
          {sub.name}
        </div>
        <div style={{ fontSize: 15, color: "var(--g-ink-2)", marginBottom: 20 }}>
          {sub.region} · {sub.locationIds.length} Orte verglichen · Vorhersage {sub.horizon}
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14 }}>
          <div style={{ padding: "12px 14px", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", background: "var(--g-paper-deep)" }}>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 5 }}>Zeitplan</div>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{sub.schedule}</div>
          </div>
          <div style={{ padding: "12px 14px", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", background: "var(--g-paper-deep)" }}>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 5 }}>Nächster Versand</div>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{sub.nextSend}</div>
          </div>
        </div>
      </div>

      <div style={{
        borderTop: "1px solid var(--g-rule-soft)", padding: "14px 26px", background: "var(--g-card-alt)",
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 16, flexWrap: "wrap",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Eyebrow>Kanäle</Eyebrow>
          <div style={{ display: "flex", gap: 14 }}>
            {sub.channels.map(ch => (
              <span key={ch} style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 12, color: "var(--g-ink-2)" }}>
                <Dot tone="good" size={7}/>
                <span className="mono" style={{ textTransform: "capitalize" }}>{ch}</span>
              </span>
            ))}
          </div>
        </div>
        <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Vergleich öffnen →</a>
      </div>
    </Card>
  );
}

/* ─────────────────── Postausgang (auf den Kontext gescopet) ─────────────────── */
function HomeOutboxCard({ contextName, reports }) {
  return (
    <Card padding={20}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14, gap: 12 }}>
        <div style={{ minWidth: 0 }}>
          <Eyebrow style={{ marginBottom: 4 }}>Versand · heute</Eyebrow>
          <div style={{ fontSize: 17, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
            Was geht raus · <span style={{ color: "var(--g-ink-2)", fontWeight: 600 }}>{contextName}</span>
          </div>
        </div>
        <Pill tone="good">Alle Kanäle ok</Pill>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {reports.slice(0, 3).map((r, i) => (
          <BriefingTimelineRow key={i} report={r}/>
        ))}
      </div>
    </Card>
  );
}

/* ─────────────────── Schlanke „Außerdem beobachtet"-Zeile ───────────────────
 * Überlappungsfall: zusätzlich zum Hero-Kontext laufen weitere Orts-Vergleiche
 * nebenher. Bewusst KEINE Hero-Behandlung — kompakte, klickbare Status-Zeilen. */
function HomeAlsoWatchedRow({ sub, last }) {
  const [hover, setHover] = React.useState(false);
  return (
    <div
      role="button" tabIndex={0}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        display: "flex", alignItems: "center", gap: 14, cursor: "pointer",
        padding: "12px 4px", borderBottom: last ? "none" : "1px solid var(--g-rule-soft)",
      }}>
      <Dot tone="good" size={7}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.005em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {sub.name}
        </div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
          {sub.locationIds.length} Orte · {sub.region}
        </div>
      </div>
      <div style={{ display: "flex", gap: 6, flexShrink: 0 }}>
        {sub.channels.map(ch => (
          <span key={ch} className="mono" style={{
            padding: "2px 7px", fontSize: 10, letterSpacing: "0.04em", textTransform: "capitalize",
            border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)",
            background: "var(--g-card-alt)", color: "var(--g-ink-2)",
          }}>{ch}</span>
        ))}
      </div>
      <div style={{ textAlign: "right", flexShrink: 0, minWidth: 132 }}>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", textTransform: "uppercase", letterSpacing: "0.08em" }}>Nächster Versand</div>
        <div className="mono" style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)", marginTop: 1 }}>{sub.nextSend}</div>
      </div>
      <span style={{ fontFamily: "var(--g-font-mono)", fontSize: 13, color: hover ? "var(--g-ink)" : "var(--g-ink-4)", flexShrink: 0, width: 14, textAlign: "center" }}>→</span>
    </div>
  );
}

function ScreenHome({ mode = "trip" }) {
  const trip = MOCK_TRIP;
  const dayCurrent = 1;
  const dayTotal = 12;

  const activeCompares = (window.MOCK_COMPARE_SUBS || []).filter(s => s.status === "active");

  // Priorität: laufender Trip gewinnt den Hero. Sonst der erste aktive Vergleich.
  const heroIsTrip = mode === "trip";
  const heroCompare = heroIsTrip ? null : activeCompares[0];
  // Nebenher beobachtete Vergleiche (Überlappungs-Zeile).
  const sideCompares = heroIsTrip ? activeCompares : activeCompares.slice(1);

  const contextName = heroIsTrip ? trip.shortName : (heroCompare ? heroCompare.name : "—");
  const outboxReports = heroIsTrip ? MOCK_REPORT_TIMELINE : (heroCompare ? homeCompareTimeline(heroCompare) : []);

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="home"/>
      <main data-screen-label="Startseite" style={{ flex: 1, position: "relative", overflow: "hidden" }}>
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
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <Btn variant="ghost" size="sm" icon={<span style={{ fontSize: 16, lineHeight: 0 }}>+</span>}>Neuer Trip</Btn>
            <Btn variant="ghost" size="sm" icon={<span style={{ fontSize: 16, lineHeight: 0 }}>+</span>}>Neuer Vergleich</Btn>
          </div>
        </div>

        <div style={{ position: "relative", padding: "32px 40px 80px", maxWidth: 1320 }}>

          {/* ───────── 1 · STATUS — Läuft alles? (Einzel-Hero) ───────── */}
          {/* align-items:start → Hero-Karte wird nur so hoch wie ihr Inhalt
              (behebt das alte Streck-/Leerloch-Artefakt). */}
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 24, alignItems: "start", marginBottom: 36 }}>

            <div style={{ display: "flex", flexDirection: "column", gap: 20 }}>
              {heroIsTrip
                ? <HomeHeroTrip trip={trip} dayCurrent={dayCurrent} dayTotal={dayTotal}/>
                : <HomeHeroCompare sub={heroCompare}/>}

              {/* Schnellaktionen — direkt am aktiven Kontext (PO 2026-06-04):
                  füllen den Raum unter dem Hero und sind dadurch klar zugeordnet.
                  Letzte Aktion ist der kontextbezogene Test-Versand (ersetzt die
                  kontextlose Topbar-Variante). */}
              <div>
                <div style={{ marginBottom: 12 }}>
                  <Eyebrow style={{ marginBottom: 4 }}>Schnell eingreifen</Eyebrow>
                  <div style={{ fontSize: 17, fontWeight: 600 }}>Schnellaktionen</div>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                  {heroIsTrip ? (
                    <>
                      <QuickAction glyph="pause"   label="Pausentag einplanen"     sub="→ Etappen & Wegpunkte"/>
                      <QuickAction glyph="metrics" label="Wetter-Metriken ändern"  sub="→ Wetter-Metriken"/>
                      <QuickAction glyph="clock"   label="Briefing-Zeitplan"       sub="→ Briefing-Zeitplan"/>
                      <QuickAction glyph="eye"     label="Vorschau prüfen"         sub="→ Vorschau"/>
                      <QuickAction glyph="send"    label="Test-Briefing schicken"  sub="→ An deine eigenen Kanäle"/>
                    </>
                  ) : (
                    <>
                      <QuickAction glyph="route"   label="Orte bearbeiten"         sub="→ Verglichene Orte"/>
                      <QuickAction glyph="metrics" label="Ideal-Werte ändern"      sub="→ Ideal-Profil"/>
                      <QuickAction glyph="clock"   label="Briefing-Zeitplan"       sub="→ Zeitplan & Kanäle"/>
                      <QuickAction glyph="eye"     label="Vorschau prüfen"         sub="→ Vorschau"/>
                      <QuickAction glyph="send"    label="Test-Vergleich schicken" sub="→ An deine eigenen Kanäle"/>
                    </>
                  )}
                </div>
              </div>
            </div>

            <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
              <HomeOutboxCard contextName={contextName} reports={outboxReports}/>

              <Card padding={20}>
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
                  <div>
                    <Eyebrow style={{ marginBottom: 4 }}>Alerts · letzte 24 h</Eyebrow>
                    <div style={{ fontSize: 17, fontWeight: 600 }}>{heroIsTrip ? "2 ausgelöst" : "Keine"}</div>
                  </div>
                  <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Schwellen →</a>
                </div>
                {heroIsTrip
                  ? MOCK_ALERTS_RECENT.map((a, i) => (
                      <AlertRow key={i} alert={a} last={i === MOCK_ALERTS_RECENT.length - 1}/>
                    ))
                  : <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, paddingTop: 2 }}>
                      Keine Schwellen-Überschreitung in den verglichenen Orten. Du wirst sofort benachrichtigt, sobald eine Bedingung kippt.
                    </div>}
              </Card>
            </div>
          </div>

          {/* Schnellaktionen wurden in die linke Hero-Spalte verschoben (PO 2026-06-04):
               dort füllen sie den Raum unter dem Hero und stehen klar im Kontext. */}


          {/* ───────── Überlappung — Außerdem beobachtet (schlanke Zeile) ─────────
               Niedrigere Priorität als der Hero + seine Schnellaktionen: läuft
               nur nebenher, kommt deshalb NACH den Schnellaktionen. */}
          {sideCompares.length > 0 && (
            <Card padding={20} style={{ marginBottom: 36 }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 4, gap: 16 }}>
                <div>
                  <Eyebrow style={{ marginBottom: 4 }}>Außerdem beobachtet</Eyebrow>
                  <div style={{ fontSize: 15, fontWeight: 600 }}>
                    {sideCompares.length} {sideCompares.length === 1 ? "Orts-Vergleich läuft" : "Orts-Vergleiche laufen"} nebenher
                  </div>
                </div>
                <a href="#" style={{ fontSize: 12, color: "var(--g-ink-3)", textDecoration: "none", fontFamily: "var(--g-font-mono)" }}>Alle Vergleiche →</a>
              </div>
              <div>
                {sideCompares.map((s, i) => (
                  <HomeAlsoWatchedRow key={s.id} sub={s} last={i === sideCompares.length - 1}/>
                ))}
              </div>
            </Card>
          )}

          {/* ───────── 3 · EINRICHTEN — Absprung (90 %-Use) ───────── */}
          {heroIsTrip ? (
            <Card padding={20} style={{ marginBottom: 36 }}>
              <SectionH eyebrow="Einrichten" title="Frühere Trips" kicker="8 abgeschlossene Mehrtages-Trips" right={<Btn variant="quiet" size="sm">Alle anzeigen</Btn>}/>
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
          ) : (
            <div style={{ marginBottom: 36 }}>
              <SectionH
                eyebrow="Einrichten"
                title="Kein Trip geplant"
                kicker="Sobald ein Mehrtages-Trip ansteht, übernimmt er das Cockpit"
                right={<Btn variant="primary" size="sm">Neuer Trip</Btn>}
              />
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
            </div>
          )}
        </div>
      </main>
    </div>
  );
}

window.ScreenHome = ScreenHome;
