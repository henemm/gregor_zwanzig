/* ════════════════════════════════════════════════════════════════════════
 *  WETTER-EDITOR KONSOLIDIERUNG · Issue 345
 * ════════════════════════════════════════════════════════════════════════
 *
 *  Heute lebt die Wetter-Konfiguration an DREI Stellen mit unterschiedlichem
 *  Funktionsumfang:
 *      (a) Tour-Detail · Tab „Wetter-Metriken"     ← Soll-Optik, vollständig
 *      (b) Tour-Bearbeiten-Maske · Sektion „Wetter" ← reduziert, kein Horizont
 *      (c) Schnell-Fenster aus den Listen          ← Aktuell-Wetter, NICHT Edit
 *
 *  Plus: Abos und Orte haben heute KEINE Metrik-Konfiguration, sollen aber
 *  bekommen — ohne Zeithorizonte, weil Orte/Abos kein Etappen-Datum kennen.
 *
 *  Diese Datei produziert das Design-Canvas mit:
 *      Sektion 1 · Empfehlungs-Übersicht (3 Karten, eine pro Entscheidung)
 *      Sektion 2 · Der konsolidierte MetrikEditor (eine Komponente, drei Kontexte)
 *      Sektion 3 · Entscheidung 1 — Schnell-Fenster aus den Listen
 *      Sektion 4 · Entscheidung 2 — Wetter-Sektion in Tour-Bearbeiten-Maske
 *      Sektion 5 · Entscheidung 3 — Abos/Orte ohne Horizonte
 *
 *  Atomic-Design-Disziplin (CLAUDE.md):
 *      Alle hier verwendeten Bausteine kommen aus brand-kit / atoms /
 *      molecules / organisms. Diese Datei enthält NUR Page-Komposition,
 *      keine Inline-Atome.
 */


/* ════════════════════ Empfehlungs-Karten (Page-Komposition) ════════════════════ */

function WEKRecommendation({ index, title, decision, reasoning, decisionTone = "good", style }) {
  return (
    <div style={{
      background: "var(--g-card)",
      border: "1px solid var(--g-rule)",
      borderTop: `3px solid var(--g-accent)`,
      borderRadius: "var(--g-r-3)",
      padding: "18px 20px",
      display: "flex", flexDirection: "column", gap: 12,
      ...style,
    }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 10 }}>
        <span className="mono" style={{
          fontSize: 11, color: "var(--g-accent-deep)",
          letterSpacing: "0.12em", fontWeight: 700,
        }}>ENTSCHEIDUNG {index}</span>
        <Pill tone={decisionTone}>{decision}</Pill>
      </div>
      <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.01em" }}>
        {title}
      </div>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
        {reasoning}
      </div>
    </div>
  );
}


function WEKContextHeader({ title, kicker }) {
  return (
    <div style={{
      maxWidth: 1080, margin: "0 auto", padding: "0 32px 8px",
      fontFamily: "var(--g-font-sans)",
    }}>
      <Eyebrow>Issue 345 · Konsolidierung</Eyebrow>
      <h2 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", margin: "4px 0 6px" }}>
        {title}
      </h2>
      {kicker && (
        <div style={{ fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55, maxWidth: 880 }}>
          {kicker}
        </div>
      )}
    </div>
  );
}


/* ════════════════════ Sektion 1: Empfehlungs-Übersicht ════════════════════ */

function WEKOverview() {
  return (
    <div style={{
      background: "var(--g-paper-deep)",
      padding: "32px 36px",
      fontFamily: "var(--g-font-sans)",
      color: "var(--g-ink)",
      height: "100%",
      display: "flex", flexDirection: "column", gap: 24,
    }}>
      <div>
        <Eyebrow>Vorschlag in einer Folie</Eyebrow>
        <h1 style={{
          fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em",
          margin: "4px 0 10px",
        }}>Eine Komponente, drei Kontexte, weniger Bedien-Wahrheiten.</h1>
        <div style={{
          fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55, maxWidth: 880,
        }}>
          Statt drei nicht synchroner Wetter-Editoren betreiben wir die kanonische
          <strong> MetricsEditor</strong>-Organism aus dem Atomic-Design-System.
          Sie kennt drei Kontexte (Tour · Ort · Abo) und passt die Mitten-Kontrolle
          jeder Metrik-Zeile entsprechend an. Schnell-Fenster und Edit-Maske halten
          wir bewusst dünn — Wetter wird dort konfiguriert, wo es zu Hause ist.
        </div>
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 18, flex: 1,
      }}>
        <WEKRecommendation
          index="1"
          title="Schnell-Fenster aus den Listen"
          decision="Streichen"
          decisionTone="bad"
          reasoning={
            <>
              Auf der Touren-Kachel zeigen wir nur einen <strong>Status-Chip</strong>
              („Wetter-Profil: Alpen-Trekking · 14 Spalten").
              Klick auf die Kachel öffnet die Tour mit aktivem Wetter-Tab —
              das ist ein Klick mehr, dafür aber dieselbe Editor-Oberfläche wie
              überall sonst. Vermeidet Icon-Soup (AP-005) und drei verschiedene
              Quick-Edit-Dialekte.
            </>
          }
        />
        <WEKRecommendation
          index="2"
          title="Wetter-Sektion in Tour-Bearbeiten"
          decision="Streichen"
          decisionTone="bad"
          reasoning={
            <>
              Die Bearbeiten-Maske zeigt eine read-only <strong>Wetter-Profil-Zusammenfassung</strong>
              mit Link „Im Wetter-Tab bearbeiten →". Damit hat Wetter nur noch
              EINE Bearbeitungs-Stelle. Der Wizard-Schritt 3 bleibt (Erst-Setup beim
              Anlegen) und nutzt dieselbe Editor-Organism in `compact`-Variante.
            </>
          }
        />
        <WEKRecommendation
          index="3"
          title="Abos / Orte ohne Horizonte"
          decision={'Selbe Komponente, Kontext = „ort" / „abo"'}
          decisionTone="good"
          reasoning={
            <>
              Die Pro-Metrik-Mitte wird vom <em>HorizonChips</em>-Trio (HEUTE / MORGEN /
              ÜBERMORGEN) auf den <em>ScoreToggle</em> umgeklappt — „im Score" / „nicht
              im Score". Alles andere (Spalte/Detail/Aus, Roh/Skala, Kanal-Limits,
              Vorschau) bleibt identisch. Eine Code-Pfad, eine Lern-Kurve.
            </>
          }
        />
      </div>
    </div>
  );
}


/* ════════════════════ Sektion 2: Der konsolidierte MetrikEditor ════════════════════ */

function WEKEditorTour() {
  return (
    <BrandShell active="trips">
      <div style={{ padding: "18px 0 0" }}>
        <div style={{ padding: "0 32px 14px" }}>
          <Eyebrow>Tour · Mallorca GR221 / Tab „Wetter-Metriken"</Eyebrow>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
            <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>
              Wetter-Metriken
            </h1>
            <div style={{ display: "flex", gap: 8 }}>
              <Btn variant="ghost" size="sm">Verwerfen</Btn>
              <Btn variant="accent" size="sm">Speichern</Btn>
            </div>
          </div>
        </div>
        <MetricsEditor context="tour" initialPresetId="alpine"/>
      </div>
    </BrandShell>
  );
}

function WEKEditorOrt() {
  return (
    <BrandShell active="compare">
      <div style={{ padding: "18px 0 0" }}>
        <div style={{ padding: "0 32px 14px" }}>
          <Eyebrow>Orts-Vergleich · Wochenend-Touren / Metrik-Konfiguration</Eyebrow>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
            <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em" }}>
              Metriken & Score
            </h1>
            <div style={{ display: "flex", gap: 8 }}>
              <Btn variant="ghost" size="sm">Verwerfen</Btn>
              <Btn variant="accent" size="sm">Speichern</Btn>
            </div>
          </div>
        </div>
        <MetricsEditor context="ort" initialPresetId="alpine"/>
      </div>
    </BrandShell>
  );
}

/* Mobile-Variante: enge Metrik-Zeile, kein Preset-Rail, keine Channel-Preview.
 * Diese läuft in einer Sheet-/Drilldown-Ansicht inside des Tour-Detail-Tabs. */
function WEKEditorMobile() {
  return (
    <PhoneFrame width={390} height={780}>
      <MobileShell
        active="trips"
        eyebrow="MALLORCA GR221"
        title="Wetter-Metriken"
        leftIcon="back"
        right={<Btn variant="accent" size="xs">Speichern</Btn>}
      >
        <div style={{ padding: "0 14px 18px" }}>
          <div style={{ padding: "10px 0 8px" }}>
            <Eyebrow>Profil</Eyebrow>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 6 }}>
              <div style={{ fontSize: 16, fontWeight: 600 }}>Alpen-Trekking</div>
              <Btn variant="ghost" size="xs">Profil wechseln →</Btn>
            </div>
          </div>
          <MetricsEditor
            context="tour"
            initialPresetId="alpine"
            compact
            showPresetRail={false}
            showChannelPreview={false}
          />
        </div>
      </MobileShell>
    </PhoneFrame>
  );
}


/* ════════════════════ Sektion 3: Entscheidung 1 — Quick-Window ════════════════════ */

/* Status-quo-Mockup. Bewusst dicht und ein bisschen nervig — die Liste
 * trägt heute 6 Icon-Buttons je Zeile (AP-005-Verstoß). */
function WEKListStatusQuo() {
  const trips = [
    { name: "Mallorca GR221",       when: "12.–19. SEP 2026", status: "Aktiv",   tone: "good"    },
    { name: "Karnischer Höhenweg",  when: "04.–11. JUL 2026", status: "Geplant", tone: "neutral" },
    { name: "Stubaier Höhenweg",    when: "21.–28. AUG 2026", status: "Geplant", tone: "neutral" },
  ];
  return (
    <BrandShell active="trips">
      <div style={{ padding: "26px 32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 16 }}>
          <div>
            <Eyebrow>Heute · Status quo</Eyebrow>
            <h1 style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 4 }}>Meine Touren</h1>
          </div>
          <Btn variant="accent">+ Neue Tour</Btn>
        </div>

        <div style={{
          padding: "10px 14px", marginBottom: 14,
          background: "rgba(168,50,50,0.06)",
          border: "1px solid rgba(168,50,50,0.30)",
          borderLeft: "3px solid var(--g-bad)",
          borderRadius: "var(--g-r-3)",
          fontSize: 12.5, color: "var(--g-bad)", lineHeight: 1.45,
        }}>
          <span className="mono" style={{
            fontSize: 10, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", marginRight: 6,
          }}>AP-005 · Icon-Soup</span>
          Sechs Icon-Buttons pro Zeile (Alert · Wetter · Briefing · Vorschau · Bearbeiten · Löschen).
          Das Quick-Wetter-Icon ist ein Quick-View, kein Editor — wir nehmen es weg.
        </div>

        {trips.map((t, i) => (
          <div key={i} style={{
            display: "grid",
            gridTemplateColumns: "220px 1fr 110px 240px",
            alignItems: "center", gap: 16,
            padding: "14px 16px",
            background: "var(--g-card)",
            border: "1px solid var(--g-rule-soft)",
            borderRadius: "var(--g-r-3)",
            marginBottom: 8,
          }}>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{t.when}</div>
            <div style={{ fontSize: 15, fontWeight: 600 }}>{t.name}</div>
            <Pill tone={t.tone}>{t.status}</Pill>
            <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
              <WEKIconStub label="Alert"/>
              <WEKIconStub label="Wetter" highlight/>
              <WEKIconStub label="Briefing"/>
              <WEKIconStub label="Vorschau"/>
              <WEKIconStub label="Bearbeiten"/>
              <WEKIconStub label="Löschen"/>
            </div>
          </div>
        ))}
      </div>
    </BrandShell>
  );
}

function WEKIconStub({ label, highlight }) {
  return (
    <div title={label} style={{
      width: 28, height: 28, borderRadius: "var(--g-r-2)",
      background: highlight ? "rgba(168,50,50,0.15)" : "var(--g-card-alt)",
      border: `1px solid ${highlight ? "var(--g-bad)" : "var(--g-rule-soft)"}`,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      fontSize: 9, color: "var(--g-ink-3)",
      fontFamily: "var(--g-font-mono)", letterSpacing: "0.02em",
    }}>
      {label.slice(0, 2).toUpperCase()}
    </div>
  );
}


/* Variante A: Quick-Window bleibt — vereinheitlicht als Slide-Panel mit
 * `compact`-Editor (kein Preset-Rail, keine Kanal-Preview). */
function WEKQuickPanelKeep() {
  return (
    <div style={{
      width: "100%", height: "100%", background: "var(--g-paper)",
      fontFamily: "var(--g-font-sans)",
      display: "grid", gridTemplateColumns: "1fr 560px",
      overflow: "hidden",
    }}>
      <div style={{ padding: "26px 32px", position: "relative", overflow: "hidden", background: "var(--g-paper-deep)" }}>
        <Eyebrow>Aus jeder Liste · Touren · Orte · Abos</Eyebrow>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4 }}>
          <h2 style={{ fontSize: 22, fontWeight: 600 }}>Meine Touren</h2>
          <Btn variant="accent" size="sm">+ Neue Tour</Btn>
        </div>
        <div style={{ marginTop: 18, display: "flex", flexDirection: "column", gap: 8 }}>
          {[
            { n: "Mallorca GR221",      d: "12.–19. SEP 2026", active: true },
            { n: "Karnischer Höhenweg", d: "04.–11. JUL 2026" },
            { n: "Stubaier Höhenweg",   d: "21.–28. AUG 2026" },
          ].map((t, i) => (
            <div key={i} style={{
              padding: "12px 14px",
              background: t.active ? "var(--g-card)" : "var(--g-paper)",
              border: t.active ? "1px solid var(--g-accent)" : "1px solid var(--g-rule-soft)",
              borderRadius: "var(--g-r-3)",
              display: "flex", alignItems: "center", justifyContent: "space-between", gap: 12,
              opacity: t.active ? 1 : 0.6,
            }}>
              <div>
                <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)" }}>{t.d}</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 2 }}>{t.n}</div>
              </div>
              {t.active && <Pill tone="accent">Quick-Wetter offen</Pill>}
            </div>
          ))}
        </div>
        <div style={{ position: "absolute", inset: 0, background: "rgba(26,26,24,0.06)", pointerEvents: "none" }}/>
      </div>

      <aside style={{
        background: "var(--g-card)", borderLeft: "1px solid var(--g-rule)",
        display: "flex", flexDirection: "column",
        boxShadow: "-12px 0 32px rgba(26,26,24,0.06)",
        overflow: "hidden",
      }}>
        <div style={{ padding: "14px 18px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <Eyebrow>Quick-Wetter · MALLORCA GR221</Eyebrow>
            <div style={{ fontSize: 15, fontWeight: 600, marginTop: 2 }}>Metrik-Konfiguration</div>
          </div>
          <Btn variant="quiet" size="sm">×</Btn>
        </div>
        <div style={{ flex: 1, overflow: "auto" }}>
          <MetricsEditor
            context="tour"
            initialPresetId="alpine"
            compact
            showPresetRail={false}
            showChannelPreview={false}
          />
        </div>
        <div style={{
          padding: "12px 18px", borderTop: "1px solid var(--g-rule-soft)",
          background: "var(--g-card-alt)",
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.04em" }}>
            speichert direkt — kein Form-Speichern-Button
          </span>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost" size="sm">Abbrechen</Btn>
            <Btn variant="accent" size="sm">Übernehmen</Btn>
          </div>
        </div>
      </aside>
    </div>
  );
}


/* Empfehlung: Quick-Window streichen. Stattdessen zeigt jede Tour-Kachel
 * eine Profil-Zusammenfassung; Klick auf die Kachel öffnet die Tour mit
 * aktivem Wetter-Tab. */
function WEKQuickPanelDrop() {
  const trips = [
    { name: "Mallorca GR221",      when: "12.–19. SEP 2026", status: "Aktiv",  tone: "good",
      profile: "Alpen-Trekking", cols: 9, detail: 3, alerts: 2 },
    { name: "Karnischer Höhenweg", when: "04.–11. JUL 2026", status: "Geplant", tone: "neutral",
      profile: "★ KHW 403 (eigen)", cols: 11, detail: 2, alerts: 0 },
    { name: "Stubaier Höhenweg",   when: "21.–28. AUG 2026", status: "Geplant", tone: "neutral",
      profile: "Alpen-Trekking", cols: 9, detail: 3, alerts: 0 },
  ];
  return (
    <BrandShell active="trips">
      <div style={{ padding: "26px 32px" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 16 }}>
          <div>
            <Eyebrow>Empfehlung · Quick-Window weg</Eyebrow>
            <h1 style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 4 }}>Meine Touren</h1>
          </div>
          <Btn variant="accent">+ Neue Tour</Btn>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {trips.map((t, i) => (
            <a key={i} href="#" style={{
              display: "grid",
              gridTemplateColumns: "220px 1fr 360px 110px 24px",
              alignItems: "center", gap: 18,
              padding: "16px 18px",
              background: "var(--g-card)",
              border: "1px solid var(--g-rule-soft)",
              borderRadius: "var(--g-r-3)",
              textDecoration: "none", color: "inherit",
              cursor: "pointer",
            }}>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{t.when}</div>
              <div>
                <div style={{ fontSize: 16, fontWeight: 600 }}>{t.name}</div>
                {t.alerts > 0 && (
                  <div className="mono" style={{ fontSize: 10.5, color: "var(--g-bad)", marginTop: 4, letterSpacing: "0.04em" }}>
                    {t.alerts} Alarme aktiv
                  </div>
                )}
              </div>

              {/* Wetter-Profil-Chip — ersetzt den Quick-Wetter-Button */}
              <div style={{
                display: "inline-flex", alignItems: "center", gap: 10,
                padding: "8px 12px",
                background: "var(--g-card-alt)",
                border: "1px solid var(--g-rule-soft)",
                borderRadius: "var(--g-r-3)",
              }}>
                <WIcon kind="cloud" size={18} color="var(--g-ink-3)"/>
                <div style={{ minWidth: 0 }}>
                  <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
                    Wetter-Profil
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 1 }}>
                    {t.profile}
                  </div>
                  <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>
                    {t.cols} Spalten · {t.detail} Detail
                  </div>
                </div>
              </div>

              <Pill tone={t.tone}>{t.status}</Pill>
              <span style={{ color: "var(--g-ink-4)", fontSize: 16 }}>›</span>
            </a>
          ))}
        </div>

        <div style={{
          marginTop: 16, padding: "10px 14px",
          background: "var(--g-accent-tint)",
          borderLeft: "3px solid var(--g-accent)",
          borderRadius: "var(--g-r-2)",
          fontSize: 12.5, color: "var(--g-accent-deep)", lineHeight: 1.5,
        }}>
          <strong>Bedienlogik:</strong> Klick auf die Kachel = Tour öffnen.
          Tour-Detail entscheidet selbst, ob Wetter-Tab oder Übersicht zuerst kommt
          (z. B. „bei aktiven Alarmen automatisch Wetter-Tab"). Damit ist „schnell
          zum Wetter" ein Klick — und es ist DERSELBE Editor wie in jedem anderen
          Kontext.
        </div>
      </div>
    </BrandShell>
  );
}


/* ════════════════════ Sektion 4: Entscheidung 2 — Wetter in Tour-Bearbeiten ════════════════════ */

/* Variante A: Tour-Bearbeiten behält die Wetter-Sektion und modernisiert sie
 * — der volle MetricsEditor im Tour-Kontext lebt mitten in der Edit-Maske.
 * Vorteil: ein Save-Button. Nachteil: jetzt zwei UI-Stellen, an denen Wetter
 * editiert wird (Edit-Maske + Tour-Detail-Tab) — Drift-Gefahr. */
function WEKEditFormKeep() {
  return (
    <BrandShell active="trips">
      <div style={{ padding: "22px 32px 60px" }}>
        <Eyebrow>Variante A · Bearbeiten</Eyebrow>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4, marginBottom: 16 }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>Mallorca GR221</h1>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost">Abbrechen</Btn>
            <Btn variant="accent">Tour speichern</Btn>
          </div>
        </div>

        <Card padding={20} style={{ marginBottom: 14 }}>
          <Eyebrow>Identität</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 10 }}>
            <Field label="Name"><Input defaultValue="Mallorca GR221"/></Field>
            <Field label="Zeitraum"><Input defaultValue="12.09. – 19.09.2026"/></Field>
            <Field label="Status"><Input defaultValue="Geplant"/></Field>
            <Field label="Region"><Input defaultValue="Tramuntana, Mallorca"/></Field>
          </div>
        </Card>

        <Card padding={0}>
          <div style={{ padding: "16px 20px", borderBottom: "1px solid var(--g-rule-soft)" }}>
            <Eyebrow>Sektion · Wetter (inline)</Eyebrow>
            <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4 }}>
              Wetter-Metriken
            </div>
            <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5, maxWidth: 720 }}>
              Speichern erfolgt mit dem Tour-Speichern-Button oben. Achtung: dieselbe
              Konfiguration ist auch im Tour-Detail · Tab „Wetter-Metriken" sichtbar
              und editierbar — beide Stellen müssen identisches Verhalten zeigen.
            </div>
          </div>
          <MetricsEditor context="tour" initialPresetId="alpine" showPresetRail={false}/>
        </Card>

        <div style={{
          marginTop: 16, padding: "10px 14px",
          background: "rgba(192,138,26,0.10)",
          borderLeft: "3px solid var(--g-warn)",
          borderRadius: "var(--g-r-2)",
          fontSize: 12.5, color: "var(--g-warn)", lineHeight: 1.5,
        }}>
          <strong>Kosten dieser Variante:</strong> Zwei Stellen mit identischem Editor
          (Bearbeiten + Detail-Tab) — Drift-Risiko und doppelte Lern-Kurve. Lohnt sich
          nur, wenn das Argument „alles in einem Speichern-Schritt" wirklich gewünscht ist.
        </div>
      </div>
    </BrandShell>
  );
}


/* Empfehlung: Bearbeiten-Maske bleibt schlank. Wetter zeigt sich als
 * read-only Profil-Zusammenfassung mit Link in den Wetter-Tab. */
function WEKEditFormDrop() {
  return (
    <BrandShell active="trips">
      <div style={{ padding: "22px 32px 40px" }}>
        <Eyebrow>Empfehlung · Bearbeiten</Eyebrow>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4, marginBottom: 16 }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>Mallorca GR221</h1>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost">Abbrechen</Btn>
            <Btn variant="accent">Tour speichern</Btn>
          </div>
        </div>

        <Card padding={20} style={{ marginBottom: 14 }}>
          <Eyebrow>Identität</Eyebrow>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 10 }}>
            <Field label="Name"><Input defaultValue="Mallorca GR221"/></Field>
            <Field label="Zeitraum"><Input defaultValue="12.09. – 19.09.2026"/></Field>
            <Field label="Status"><Input defaultValue="Geplant"/></Field>
            <Field label="Region"><Input defaultValue="Tramuntana, Mallorca"/></Field>
          </div>
        </Card>

        <Card padding={0} style={{ marginBottom: 14 }}>
          <div style={{
            padding: "16px 20px", display: "grid", gridTemplateColumns: "1fr auto", gap: 18, alignItems: "center",
          }}>
            <div>
              <Eyebrow>Wetter-Profil</Eyebrow>
              <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginTop: 4 }}>
                <div style={{ fontSize: 18, fontWeight: 600 }}>Alpen-Trekking</div>
                <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.04em" }}>
                  9 Spalten · 3 Detail · 8 nicht im Briefing
                </span>
              </div>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 4, letterSpacing: "0.02em" }}>
                Temp · Wind · Böen · Niederschlag · Regen% · Gewitter · Bewölkung · Sicht · UV
              </div>
            </div>
            <Btn variant="ghost">Im Wetter-Tab bearbeiten →</Btn>
          </div>
          <div style={{
            padding: "10px 20px", borderTop: "1px solid var(--g-rule-soft)",
            background: "var(--g-card-alt)",
            fontSize: 12, color: "var(--g-ink-3)",
          }}>
            <strong style={{ color: "var(--g-ink-2)" }}>Read-only.</strong>
            {" "}Wetter-Konfiguration lebt im Tour-Detail · Tab „Wetter-Metriken" —
            dort einziger Bearbeitungs-Ort. Das Tour-Speichern hier ändert
            ausschließlich Identitäts-Felder oben.
          </div>
        </Card>

        <div style={{
          padding: "10px 14px",
          background: "var(--g-accent-tint)",
          borderLeft: "3px solid var(--g-accent)",
          borderRadius: "var(--g-r-2)",
          fontSize: 12.5, color: "var(--g-accent-deep)", lineHeight: 1.5,
        }}>
          <strong>Konsequenz:</strong> Bearbeiten-Maske trägt nur noch Identität und
          ähnliche Stamm-Daten (Route, Zeitraum, Status). Wetter, Alarme und Briefing-
          Zeitplan haben eigene Tabs im Tour-Detail und werden dort gespeichert. Das
          spiegelt die Anti-Pattern AP-013: Wetter ist immer Drill-Down aus Kontext,
          nie eigenständige Sub-Maske.
        </div>
      </div>
    </BrandShell>
  );
}


/* ════════════════════ Sektion 5: Entscheidung 3 — Abos/Orte ohne Horizonte ════════════════════ */

function WEKOrtsVergleichEditor() {
  return (
    <BrandShell active="compare">
      <div style={{ padding: "22px 32px 40px" }}>
        <Eyebrow>Orts-Vergleich · Wochenend-Touren</Eyebrow>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4, marginBottom: 16 }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>
            Metriken & Score
          </h1>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost">Verwerfen</Btn>
            <Btn variant="accent">Speichern</Btn>
          </div>
        </div>

        <div style={{
          padding: "10px 14px", marginBottom: 14,
          background: "var(--g-accent-tint)",
          border: "1px solid var(--g-accent-soft)",
          borderRadius: "var(--g-r-2)",
          fontSize: 12.5, color: "var(--g-accent-deep)", lineHeight: 1.5,
        }}>
          <strong>Unterschied zum Tour-Editor:</strong> Statt HEUTE / MORGEN / ÜBERMORGEN
          pro Metrik (Orte haben kein Etappen-Datum) entscheidest du hier
          <em> „Im Score" / „Nicht im Score"</em>. Score-Metriken fließen in den
          0–100-Wert pro Ort ein, Detail-Metriken erscheinen in der Vergleichs-Karte
          ohne Score-Beitrag.
        </div>

        <Card padding={0}>
          <MetricsEditor context="ort" initialPresetId="alpine" showPresetRail showChannelPreview/>
        </Card>
      </div>
    </BrandShell>
  );
}


function WEKAboDetail() {
  return (
    <BrandShell active="compare">
      <div style={{ padding: "22px 32px 40px" }}>
        <Eyebrow>Abo · Skigebiete Zillertal</Eyebrow>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginTop: 4, marginBottom: 14 }}>
          <h1 style={{ fontSize: 24, fontWeight: 600, letterSpacing: "-0.02em" }}>
            Skigebiete Zillertal
          </h1>
          <div style={{ display: "flex", gap: 8 }}>
            <Btn variant="ghost">Pausieren</Btn>
            <Btn variant="accent">Speichern</Btn>
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 18, marginBottom: 14 }}>
          <Card padding={20}>
            <Eyebrow>Stammdaten</Eyebrow>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginTop: 10 }}>
              <Field label="Name"><Input defaultValue="Skigebiete Zillertal"/></Field>
              <Field label="Gruppe"><Input defaultValue="Skigebiete Tirol"/></Field>
              <Field label="Versand-Zeit"><Input defaultValue="täglich 07:00"/></Field>
              <Field label="Aktiv-Zeitraum"><Input defaultValue="01.12.2026 – 30.04.2027"/></Field>
            </div>
          </Card>
          <Card padding={20}>
            <Eyebrow>Empfänger</Eyebrow>
            <div style={{ marginTop: 10 }}>
              <ChannelRow kind="Email" target="gregor@henemm.com" active sub="zuletzt: heute 07:01"/>
              <div style={{ marginTop: 8 }}>
                <ChannelRow kind="Signal" target="+43 660 … 4711"/>
              </div>
            </div>
          </Card>
        </div>

        <Card padding={0}>
          <div style={{ padding: "14px 20px", borderBottom: "1px solid var(--g-rule-soft)" }}>
            <Eyebrow>Sektion · Wetter-Konfiguration</Eyebrow>
            <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4 }}>Metriken & Score</div>
            <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 4, lineHeight: 1.5, maxWidth: 720 }}>
              Identische Komponente wie im Tour-Editor — nur die Mitten-Spalte
              zeigt „Im Score" statt HEUTE / MORGEN / ÜBERMORGEN.
            </div>
          </div>
          <MetricsEditor context="abo" initialPresetId="alpine" showPresetRail={false}/>
        </Card>
      </div>
    </BrandShell>
  );
}


Object.assign(window, {
  WEKOverview, WEKEditorTour, WEKEditorOrt, WEKEditorMobile,
  WEKListStatusQuo, WEKQuickPanelKeep, WEKQuickPanelDrop,
  WEKEditFormKeep, WEKEditFormDrop,
  WEKOrtsVergleichEditor, WEKAboDetail,
});
