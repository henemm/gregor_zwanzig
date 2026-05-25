/* Screen: Design-System Showcase */

function ScreenDesignSystem() {
  return (
    <div style={{ padding: 56, background: "var(--g-paper)", minHeight: "100%", position: "relative", overflow: "hidden" }}>
      <TopoBg opacity={0.18}/>
      <div style={{ position: "relative", maxWidth: 1320 }}>

        <div style={{ marginBottom: 40 }}>
          <Eyebrow>System · v2 · Alpine-modern</Eyebrow>
          <div style={{ fontSize: 44, fontWeight: 600, letterSpacing: "-0.02em", marginTop: 6, lineHeight: 1.05 }}>
            Gregor 20 Design-System
          </div>
          <div style={{ fontSize: 16, color: "var(--g-ink-3)", maxWidth: 640, marginTop: 10 }}>
            Alpin, präzise, datenehrlich. Inter Tight für UI · JetBrains Mono für alle Zahlen, Koordinaten, Zeiten · Topo-Linien als ruhige Hintergrund-Stimmung. Alles als CSS-Variablen — direkt in <span className="mono">app.css</span> übernehmbar.
          </div>
        </div>

        {/* Brand Lockup */}
        <Section title="Brand" eyebrow="01" kicker="Berg+Blitz-Glyph + Mono-Lockup. EINE Quelle (brand-kit.jsx::BrandWordmark) — keine zweite Geometrie irgendwo im Projekt.">
          <Card padding={28} style={{ marginBottom: 16 }}>
            <Eyebrow style={{ marginBottom: 18 }}>Lockup · drei Größen</Eyebrow>
            <div style={{ display: "flex", flexDirection: "column", gap: 28, alignItems: "flex-start" }}>
              <BrandWordmark size="sm"/>
              <BrandWordmark size="md"/>
              <BrandWordmark size="lg"/>
            </div>
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <Card padding={24} style={{ background: "var(--g-ink)" }}>
              <Eyebrow style={{ marginBottom: 18, color: "rgba(246,244,238,0.55)" }}>Auf dunkel</Eyebrow>
              <BrandWordmark size="md" dark/>
            </Card>
            <Card padding={24}>
              <Eyebrow style={{ marginBottom: 18 }}>Icon-only · square Kontexte</Eyebrow>
              <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
                <BrandIconSquare size={64}/>
                <BrandIconSquare size={48}/>
                <BrandIconSquare size={32}/>
                <BrandIconSquare size={16}/>
                <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.12em", textTransform: "uppercase", marginLeft: 8 }}>
                  Favicon · Avatar · App-Icon
                </span>
              </div>
            </Card>
          </div>

          <Card padding={24}>
            <Eyebrow style={{ marginBottom: 14 }}>Icon-Varianten via `icon`-Prop</Eyebrow>
            <div style={{ display: "grid", gridTemplateColumns: "160px 1fr", gap: "14px 20px", alignItems: "center" }}>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.08em" }}>icon="left" (default)</div>
              <BrandWordmark size="md" icon="left"/>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.08em" }}>icon="only"</div>
              <BrandWordmark size="md" icon="only"/>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.08em" }}>icon="none"</div>
              <BrandWordmark size="md" icon="none"/>
            </div>
          </Card>
        </Section>

        {/* Type Scale */}
        <Section title="Typografie" eyebrow="02">
          <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 12, alignItems: "baseline" }}>
            {[
              { l: "Display 5xl · 60", s: 60, w: 600, t: "Karnischer Höhenweg" },
              { l: "Display 4xl · 44", s: 44, w: 600, t: "Heute geht ein Report raus." },
              { l: "Title 3xl · 32",   s: 32, w: 600, t: "KHW_00a · Toblach → Helmhotel" },
              { l: "Title 2xl · 24",   s: 24, w: 600, t: "Etappen-Übersicht" },
              { l: "Heading xl · 20",  s: 20, w: 600, t: "Wegpunkt-Editor" },
              { l: "Body lg · 17",     s: 17, w: 400, t: "Vor der Tour aktualisierst du am Desktop, unterwegs liest du SMS." },
              { l: "Body md · 15",     s: 15, w: 400, t: "8–12°C, ☁, trocken, Regen ab 11:00, schwacher Wind NE 12 km/h." },
              { l: "Caption sm · 13",  s: 13, w: 500, t: "Letzter Sync: 06:01 UTC · openmeteo (icon_d2)", c: "var(--g-ink-3)" },
              { l: "Eyebrow xs · 11",  s: 11, w: 500, t: "MORNING REPORT · 06.05.2026", c: "var(--g-ink-3)", caps: true, mono: true },
            ].map((r, i) => (
              <React.Fragment key={i}>
                <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "var(--g-track-caps)" }}>{r.l}</div>
                <div style={{
                  fontSize: r.s, fontWeight: r.w,
                  letterSpacing: r.s >= 32 ? "var(--g-track-tight)" : (r.caps ? "var(--g-track-caps)" : 0),
                  textTransform: r.caps ? "uppercase" : "none",
                  fontFamily: r.mono ? "var(--g-font-mono)" : "var(--g-font-sans)",
                  color: r.c || "var(--g-ink)", lineHeight: 1.15,
                }}>{r.t}</div>
              </React.Fragment>
            ))}
          </div>
        </Section>

        {/* Farben */}
        <Section title="Farben" eyebrow="03" kicker="Paper-Off-White als Bühne, Burnt-Orange als einziger Markenakzent. Wetter-Farben aus dem echten Email-Briefing abgeleitet.">
          <ColorRow label="Surfaces" colors={[
            { v: "var(--g-paper)",      n: "paper",      hex: "#f6f4ee" },
            { v: "var(--g-paper-deep)", n: "paper-deep", hex: "#ecead9" },
            { v: "var(--g-card)",       n: "card",       hex: "#ffffff" },
            { v: "var(--g-card-alt)",   n: "card-alt",   hex: "#faf8f1" },
            { v: "var(--g-rule)",       n: "rule",       hex: "#d8d3c2" },
          ]}/>
          <ColorRow label="Ink" colors={[
            { v: "var(--g-ink)",   n: "ink",   hex: "#1a1a18" },
            { v: "var(--g-ink-2)", n: "ink-2", hex: "#45433d" },
            { v: "var(--g-ink-3)", n: "ink-3", hex: "#6b675c" },
            { v: "var(--g-ink-4)", n: "ink-4", hex: "#9a958a" },
          ]}/>
          <ColorRow label="Accent" colors={[
            { v: "var(--g-accent-deep)", n: "accent-deep", hex: "#8c3e1a" },
            { v: "var(--g-accent)",      n: "accent",      hex: "#c45a2a" },
            { v: "var(--g-accent-soft)", n: "accent-soft", hex: "#f3d9c8" },
          ]}/>
          <ColorRow label="Semantic" colors={[
            { v: "var(--g-good)", n: "good", hex: "#3d6b3a" },
            { v: "var(--g-warn)", n: "warn", hex: "#c08a1a" },
            { v: "var(--g-bad)",  n: "bad",  hex: "#a83232" },
            { v: "var(--g-info)", n: "info", hex: "#2c5a8c" },
          ]}/>
          <ColorRow label="Wetter" colors={[
            { v: "var(--g-weather-rain)",    n: "rain",    hex: "#4a7ab8" },
            { v: "var(--g-weather-snow)",    n: "snow",    hex: "#8aa4c0" },
            { v: "var(--g-weather-thunder)", n: "thunder", hex: "#c43a2a" },
            { v: "var(--g-weather-sun)",     n: "sun",     hex: "#d99a2a" },
            { v: "var(--g-weather-cloud)",   n: "cloud",   hex: "#9a958a" },
          ]}/>
        </Section>

        {/* Bausteine */}
        <Section title="Bausteine" eyebrow="04">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
            <Card padding={24}>
              <Eyebrow style={{ marginBottom: 12 }}>Pills</Eyebrow>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                <Pill tone="neutral">Neutral</Pill>
                <Pill tone="accent">Accent</Pill>
                <Pill tone="good">Trocken</Pill>
                <Pill tone="warn">Böen 35 km/h</Pill>
                <Pill tone="bad">Gewitter 78%</Pill>
                <Pill tone="ghost">Archiviert</Pill>
              </div>
            </Card>
            <Card padding={24}>
              <Eyebrow style={{ marginBottom: 12 }}>Buttons</Eyebrow>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
                <Btn variant="primary">Trip starten</Btn>
                <Btn variant="accent">Report jetzt senden</Btn>
                <Btn variant="ghost">Archivieren</Btn>
                <Btn variant="quiet">Abbrechen</Btn>
                <Btn size="sm" variant="ghost">+ Wegpunkt</Btn>
              </div>
            </Card>
            <Card padding={24}>
              <Eyebrow style={{ marginBottom: 12 }}>Input · drei Größen</Eyebrow>
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                <Input size="sm" placeholder="Suche…"/>
                <Input size="md" placeholder="Trip-Name" defaultValue="Karnischer Höhenweg"/>
                <Input size="lg" placeholder="Email" type="email"/>
                <Input size="md" placeholder="überzogen" error/>
              </div>
            </Card>
            <Card padding={24}>
              <Eyebrow style={{ marginBottom: 12 }}>Switch</Eyebrow>
              <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
                <SwitchRow label="good (default)" tone="good"/>
                <SwitchRow label="accent" tone="accent"/>
                <SwitchRow label="info" tone="info"/>
                <div style={{ display: "flex", gap: 18, alignItems: "center", paddingTop: 6, borderTop: "1px dashed var(--g-rule-soft)" }}>
                  <Switch size="sm" checked/>
                  <Switch size="md" checked/>
                  <Switch size="lg" checked/>
                  <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.08em" }}>sm · md · lg</span>
                </div>
              </div>
            </Card>
            <Card padding={24}>
              <Eyebrow style={{ marginBottom: 12 }}>Wetter-Icons</Eyebrow>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 18, alignItems: "center" }}>
                {["sun","cloud","rain","thunder","snow","wind","moon","headlamp"].map(k => (
                  <div key={k} style={{ textAlign: "center" }}>
                    <WIcon kind={k} size={28}/>
                    <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 4, textTransform: "uppercase", letterSpacing: "0.08em" }}>{k}</div>
                  </div>
                ))}
              </div>
            </Card>
            <Card padding={24}>
              <Eyebrow style={{ marginBottom: 12 }}>Mini Höhenprofil</Eyebrow>
              <ElevSparkline data={MOCK_TODAY_STAGE.profile} width={320} height={70}/>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 6, display: "flex", justifyContent: "space-between" }}>
                <span>1211 m</span><span>↑203 ↓270</span><span>1144 m</span>
              </div>
            </Card>
          </div>
        </Section>

        {/* Molecules */}
        <Section title="Molecules" eyebrow="05" kicker="Kompositionen aus Atomen mit eigener Semantik. EINE Quelle: molecules.jsx — Drop-in für Inline-Defs aus screen-home / screen-trip-wizard.">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 12 }}>Field · unified form-field wrapper</Eyebrow>
              <Field label="Trip-Name">
                <Input placeholder="z.B. KHW 403" defaultValue="Karnischer Höhenweg 403"/>
              </Field>
              <Field label="Email" hint="Wird für Login + Versand verwendet.">
                <Input placeholder="gregor@..." type="email"/>
              </Field>
              <Field label="Passwort" side={<a href="#" style={{ color: "var(--g-accent)", textDecoration: "none" }}>Vergessen?</a>} error="Mindestens 8 Zeichen">
                <Input type="password" defaultValue="x" error/>
              </Field>
            </Card>

            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 12 }}>DetailRow · KV-Verallgemeinerung</Eyebrow>
              <DetailRow label="Strecke" value="14.2 km"/>
              <DetailRow label="Auf-/Abstieg" value="↑ 980 ↓ 720"/>
              <DetailRow label="Max-Höhe" value="2 412 m" sub="Birnlücke"/>
              <DetailRow label="Risiko" value={<Pill tone="good">low</Pill>} mono={false} divider="none"/>
            </Card>
          </div>

          <Card padding={20} style={{ marginBottom: 16 }}>
            <Eyebrow style={{ marginBottom: 12 }}>StagePill · Etappen-Streifen</Eyebrow>
            <div style={{ display: "flex", gap: 4 }}>
              <StagePill stage={{ code: "KHW_00", risk: "low" }}  state="done"/>
              <StagePill stage={{ code: "KHW_00a", risk: "med" }} state="active"/>
              <StagePill stage={{ code: "KHW_01", risk: "low" }}  state="future"/>
              <StagePill stage={{ code: "KHW_02", risk: "high" }} state="future"/>
              <StagePill stage={{ code: "KHW_03", risk: "low" }}  state="future"/>
              <StagePill stage={{ code: "KHW_04" }}                state="muted"/>
              <StagePill stage={{ code: "KHW_05" }}                state="muted"/>
              <StagePill stage={{ code: "KHW_06" }}                state="muted"/>
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.1em", textTransform: "uppercase", marginTop: 10 }}>
              done · active · future · future-high-risk · future · muted · muted · muted
            </div>
          </Card>

          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 12 }}>ChannelRow · Konfigurations-Zeile</Eyebrow>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <ChannelRow kind="Email"    target="gregor_zwanzig@henemm.com" active/>
                <ChannelRow kind="Signal"   target="+49 151 ••• 8847" active/>
                <ChannelRow kind="Telegram" target="@gregor_henemm"/>
                <ChannelRow kind="SMS"      target="+49 151 ••• 8847" sub="Fallback wenn andere Kanäle ausfallen"/>
              </div>
            </Card>

            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 12 }}>ChannelChip · kompakte Tag-Anzeige</Eyebrow>
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginBottom: 18 }}>
                <ChannelChip kind="email"/>
                <ChannelChip kind="signal"/>
                <ChannelChip kind="telegram"/>
                <ChannelChip kind="sms" active={false}/>
              </div>
              <Eyebrow style={{ marginBottom: 12 }}>ThresholdRow</Eyebrow>
              <ThresholdRow label="Windböen" value="≥ 50 km/h"/>
              <ThresholdRow label="Niederschlag" value="≥ 10 mm/h"/>
              <ThresholdRow label="Gewitter-Wahrscheinlichkeit" value="≥ 40 %"/>
              <ThresholdRow label="Schneefallgrenze" value="200 m unter Tour-Höhe"/>
            </Card>
          </div>

          <Card padding={20} style={{ marginBottom: 16 }}>
            <Eyebrow style={{ marginBottom: 12 }}>Stat · zwei Layouts</Eyebrow>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>
                  layout="stack" (default)
                </div>
                <div style={{ display: "flex", gap: 32 }}>
                  <Stat tone="accent" label="Aktive Etappe"     value="3/9"/>
                  <Stat tone="accent" label="Nächstes Briefing" value="06:00"/>
                  <Stat                label="Tage bis Start"    value="3"/>
                </div>
              </div>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 12 }}>
                  layout="inline" (Archiv-Style)
                </div>
                <div style={{ display: "flex", gap: 32 }}>
                  <Stat layout="inline" label="Touren"             value="12"/>
                  <Stat layout="inline" label="Briefings"          value="486"/>
                  <Stat layout="inline" label="Treffer Ø" tone="accent" value="87%"/>
                </div>
              </div>
            </div>
          </Card>

          <Card padding={20} style={{ marginBottom: 16 }}>
            <Eyebrow style={{ marginBottom: 12 }}>AlertRow · drei Varianten</Eyebrow>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 24 }}>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>variant="icon"</div>
                <AlertRow alert={{ kind: "thunder", when: "Heute 14:00", channel: "signal", msg: "Gewitter-Wahrscheinlichkeit 78% — Briefing-Sonderlauf um 13:00." }}/>
                <AlertRow alert={{ kind: "wind", when: "Morgen 17:00", channel: "email", msg: "Böen 50 km/h NW — Helmhotel exponiert." }} last/>
              </div>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>variant="dot"</div>
                <AlertRow variant="dot" alert={{ when: "06:42 UTC · 13. Mai", msg: "Wind-Update: Böen 50 km/h erwartet" }} divider="solid"/>
                <AlertRow variant="dot" alert={{ when: "21:11 UTC · 12. Mai", msg: "Schauer ab Mitternacht angekündigt" }} divider="solid" last/>
              </div>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>variant="plain"</div>
                <AlertRow variant="plain" alert={{ when: "Heute 14:00", msg: "Gewitterwarnung Salzkammergut" }}/>
                <AlertRow variant="plain" alert={{ when: "Morgen 17:00", msg: "Sturmböen Norddeutschland" }} last/>
              </div>
            </div>
          </Card>

          <Card padding={20} style={{ marginBottom: 16 }}>
            <Eyebrow style={{ marginBottom: 12 }}>Mobile · `dense` / `compact` / `last` Props</Eyebrow>
            <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginBottom: 18, lineHeight: 1.5 }}>
              Dieselben Molecules — auf Mobile mit Reihen-Layout statt Card-Style. Eine Bibliothek, zwei Geometrien.
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 24 }}>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>ChannelRow dense</div>
                <ChannelRow dense kind="Email"    target="gregor_zwanzig@henemm.com" active/>
                <ChannelRow dense kind="Signal"   target="+49 151 ••• 8847" active/>
                <ChannelRow dense kind="Telegram" target="@gregor_henemm"/>
                <ChannelRow dense kind="SMS"      target="+49 151 ••• 8847" sub="Fallback" last/>
              </div>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 10 }}>ThresholdRow divider="solid"</div>
                <ThresholdRow divider="solid" label="Wind / Böen"        value="≥ 50 km/h"/>
                <ThresholdRow divider="solid" label="Niederschlag"        value="≥ 10 mm/h"/>
                <ThresholdRow divider="solid" label="Gewitter-Wahrsch."   value="≥ 40 %"/>
                <ThresholdRow divider="solid" label="Nullgrad-Grenze"     value="−200 m unter Tour" last/>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", margin: "18px 0 10px" }}>BriefingTimelineRow dense</div>
                {MOCK_REPORT_TIMELINE.slice(0, 2).map((r, i) => (
                  <div key={i} style={{ marginBottom: 6 }}>
                    <BriefingTimelineRow report={r} dense/>
                  </div>
                ))}
              </div>
            </div>
          </Card>

          <Card padding={20}>
            <Eyebrow style={{ marginBottom: 12 }}>Briefing-Zeilen · zwei unterschiedliche Semantiken</Eyebrow>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
                  BriefingTimelineRow · Status-getrieben (Home)
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {MOCK_REPORT_TIMELINE.map((r, i) => (
                    <BriefingTimelineRow key={i} report={r}/>
                  ))}
                </div>
              </div>
              <div>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8 }}>
                  BriefingScheduleRow · Toggle-getrieben (Wizard)
                </div>
                <BriefingScheduleRow label="Morgen-Briefing" sub="Vor Etappenstart" time="06:00" enabled/>
                <BriefingScheduleRow label="Abend-Briefing"  sub="Ausblick auf morgen" time="18:00" enabled/>
                <BriefingScheduleRow label="Mittags-Update"   sub="Nur bei Risiko-Wechsel" time="12:30"/>
              </div>
            </div>
          </Card>
        </Section>

        {/* Organisms */}
        <Section title="Organisms" eyebrow="06" kicker="Domain-spezifische Kompositionen aus mehreren Molecules. Quelle: organisms.jsx. Wenn ein Organism in einer Page erscheint, ist sie fertig — sonst gehört die Komposition zurück hierher.">

          {/* PresetRail */}
          <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 16, marginBottom: 16 }}>
            <Card padding={16}>
              <Eyebrow style={{ marginBottom: 12 }}>PresetRail</Eyebrow>
              <PresetRail
                presets={WETTER_PRESETS}
                value="alpine"
                totalActive={11}
                compact
              />
            </Card>
            <Card padding={20}>
              <Eyebrow style={{ marginBottom: 12 }}>ChannelLimitChip · Bucket-Header-Markers</Eyebrow>
              <div style={{ display: "flex", gap: 6, marginBottom: 16 }}>
                <ChannelLimitChip channel="Telegram" current={5} max={8}/>
                <ChannelLimitChip channel="Signal"   current={5} max={6}/>
                <ChannelLimitChip channel="Signal"   current={7} max={6}/>
                <ChannelLimitChip channel="Telegram" current={9} max={8}/>
              </div>
              <div style={{ fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.5 }}>
                Pillen unter dem „Spalten"-Header im Metrics-Editor. Warnt orange wenn die User-Konfiguration das Kanal-Limit überschreitet.
              </div>

              <div style={{ marginTop: 22, paddingTop: 18, borderTop: "1px solid var(--g-rule-soft)" }}>
                <Eyebrow style={{ marginBottom: 10 }}>MetricsEditorContextBar</Eyebrow>
                <MetricsEditorContextBar
                  context="tour"
                  preset={WETTER_PRESETS[0]}
                  buckets={{ primary: ["temp","feels","wind","gust","precip","rainProb"], secondary: ["cloud","visibility","uv","freezeLine"] }}
                  horizons={{ temp: { today: true, tomorrow: true, day_after: true }, wind: { today: true, tomorrow: true }, precip: { today: true } }}
                  score={{}}
                  compact
                />
              </div>
            </Card>
          </div>

          {/* MetricEditorRow */}
          <Card padding={0} style={{ marginBottom: 16 }}>
            <div style={{ padding: "14px 18px 10px", borderBottom: "1px solid var(--g-rule-soft)" }}>
              <Eyebrow>MetricEditorRow · Eine Zeile im Spalten-/Detail-Bucket</Eyebrow>
              <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5 }}>
                Index · Metrik-Label · Horizont-Chips (HEUTE / MORGEN / ÜBM, nur Tour-Kontext) · Roh|Skala-Toggle · Move-Buttons · Reorder.
                Über-Limit-Zeilen (ab Index 6 für Signal) sind dezent orange gerastert, mit gestrichelter Trennlinie davor.
              </div>
            </div>
            <MetricEditorRow
              metric={WETTER_METRIC_BY_ID.temp} index={0} bucket="primary" context="tour"
              isFirst horizon={{ today: true, tomorrow: true, day_after: true }} mode="raw"
            />
            <MetricEditorRow
              metric={WETTER_METRIC_BY_ID.wind} index={1} bucket="primary" context="tour"
              horizon={{ today: true, tomorrow: true }} mode="indicator"
            />
            <MetricEditorRow
              metric={WETTER_METRIC_BY_ID.gust} index={5} bucket="primary" context="tour"
              isSignalLimit horizon={{ today: true }} mode="indicator"
            />
            <MetricEditorRow
              metric={WETTER_METRIC_BY_ID.cloud} index={6} bucket="primary" context="tour"
              isOverLimit horizon={{ today: true }} mode="indicator"
            />
            <MetricEditorRow
              metric={WETTER_METRIC_BY_ID.visibility} index={7} bucket="primary" context="tour"
              isLast isOverLimit horizon={{ today: true }} mode="indicator"
            />
          </Card>

          {/* ChannelPreviewStrip */}
          <Card padding={0} style={{ marginBottom: 16 }}>
            <div style={{ padding: "14px 18px 10px", borderBottom: "1px solid var(--g-rule-soft)" }}>
              <Eyebrow>ChannelPreviewStrip · Pixelnahe Multi-Channel-Vorschau</Eyebrow>
              <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5 }}>
                Vier Karten Email · Telegram · Signal · SMS. Identische Konfiguration; der Renderer wendet die Kanal-Limits (∞ / 8 / 6 / 0) an. Demoted-Spalten landen automatisch in der Detail-Zeile.
              </div>
            </div>
            <div style={{ padding: 16 }}>
              <ChannelPreviewStrip
                primary={["temp","wind","gust","precip","rainProb","cloud","visibility","uv"]}
                secondary={["feels","freezeLine"]}
                compact
              />
            </div>
          </Card>

          {/* MetricBucket + MetricOffShelf · zwei kleine Live-Renders */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <div>
              <Eyebrow style={{ marginBottom: 8 }}>MetricBucket (compact)</Eyebrow>
              <MetricBucket
                eyebrow="Im Briefing als Detail"
                title="Detail-Werte"
                hint="Zusatz-Werte unter der Spalten-Tabelle."
                items={["cloud","visibility","uv","freezeLine"]}
                bucket="secondary"
                context="tour"
                horizons={{ cloud: { today: true }, visibility: { today: true } }}
                mode={{}}
                compact
              />
            </div>
            <div>
              <Eyebrow style={{ marginBottom: 8 }}>MetricOffShelf</Eyebrow>
              <MetricOffShelf
                items={["humidity","windDir","thunder","pressure","newSnow"]}
                defaultOpen
                compact
              />
            </div>
          </div>
        </Section>

        {/* Templates */}
        <Section title="Templates" eyebrow="07" kicker="Layout-Skelette: BrandShell für Desktop, PhoneFrame + MobileShell für Mobile. Templates definieren WO etwas liegt, nicht WAS.">
          <div style={{ display: "grid", gridTemplateColumns: "1.4fr 1fr", gap: 16 }}>

            {/* BrandShell Schematic */}
            <Card padding={0}>
              <div style={{ padding: "14px 18px 10px", borderBottom: "1px solid var(--g-rule-soft)" }}>
                <Eyebrow>BrandShell · Desktop-Template</Eyebrow>
                <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5 }}>
                  Sidebar (220 px) links · Main-Bereich rechts. Sidebar enthält BrandWordmark + Nav + BrandUserBadge.
                </div>
              </div>
              <div style={{
                padding: 14, background: "var(--g-paper-deep)",
                display: "grid", gridTemplateColumns: "120px 1fr", gap: 10, minHeight: 220,
              }}>
                <div style={{
                  background: "var(--g-card)", border: "1px solid var(--g-rule)",
                  borderRadius: "var(--g-r-3)", padding: 12,
                  display: "flex", flexDirection: "column",
                }}>
                  <div className="mono" style={{ fontSize: 9, color: "var(--g-accent)", letterSpacing: "0.1em", marginBottom: 12 }}>
                    BRAND-SIDEBAR
                  </div>
                  <div style={{ display: "flex", flexDirection: "column", gap: 6, fontSize: 11, color: "var(--g-ink-3)" }}>
                    <div>· Wordmark</div>
                    <div>· Heute</div>
                    <div>· Touren</div>
                    <div>· Vergleich</div>
                    <div>· Archiv</div>
                  </div>
                  <div style={{ marginTop: "auto", paddingTop: 10, borderTop: "1px dashed var(--g-rule-soft)", fontSize: 10, color: "var(--g-ink-4)" }}>
                    UserBadge
                  </div>
                </div>
                <div style={{
                  background: "var(--g-card)", border: "1px dashed var(--g-rule)",
                  borderRadius: "var(--g-r-3)", padding: 12,
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.1em", textAlign: "center" }}>
                    MAIN-BEREICH<br/>(Page-Komposition)
                  </div>
                </div>
              </div>
            </Card>

            {/* Mobile Templates Schematic */}
            <Card padding={0}>
              <div style={{ padding: "14px 18px 10px", borderBottom: "1px solid var(--g-rule-soft)" }}>
                <Eyebrow>MobileShell · Mobile-Template</Eyebrow>
                <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5 }}>
                  TopAppBar (Sticky 56 px) · Scroll-Bereich · Sticky-Bottom-Action oder BottomNav. Plus übergreifende Patterns Drawer, Sheet, Toast.
                </div>
              </div>
              <div style={{ padding: 14, background: "var(--g-paper-deep)", display: "flex", justifyContent: "center" }}>
                <div style={{
                  width: 180, height: 320,
                  border: "2px solid var(--g-ink)", borderRadius: 24, padding: 6,
                  background: "var(--g-paper)",
                  display: "flex", flexDirection: "column",
                }}>
                  <div style={{
                    height: 32, borderBottom: "1px solid var(--g-rule)",
                    display: "flex", alignItems: "center", padding: "0 8px",
                    fontSize: 9, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-3)",
                    letterSpacing: "0.08em",
                  }}>TOPAPPBAR</div>
                  <div style={{
                    flex: 1, padding: 6, background: "var(--g-card-alt)",
                    display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: 10, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-4)",
                    letterSpacing: "0.06em", margin: "4px 0",
                    borderRadius: 4,
                  }}>SCROLL</div>
                  <div style={{
                    height: 36, borderTop: "1px solid var(--g-rule)",
                    display: "flex", alignItems: "center", justifyContent: "space-around",
                    fontSize: 8, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-3)",
                    letterSpacing: "0.06em",
                  }}>
                    <span>HOME</span><span>TRIPS</span><span>VGL</span><span>ARCH</span>
                  </div>
                </div>
              </div>
              <div style={{ padding: "12px 18px", borderTop: "1px solid var(--g-rule-soft)" }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 8 }}>
                  Begleit-Patterns
                </div>
                <div style={{ display: "flex", flexWrap: "wrap", gap: 6, fontSize: 11, color: "var(--g-ink-2)" }}>
                  <Pill tone="neutral">Drawer</Pill>
                  <Pill tone="neutral">Bottom-Sheet</Pill>
                  <Pill tone="neutral">Toast</Pill>
                  <Pill tone="neutral">Modal</Pill>
                  <Pill tone="neutral">Wizard-Cancel</Pill>
                  <Pill tone="neutral">Push-Permission</Pill>
                </div>
              </div>
            </Card>
          </div>
        </Section>

        {/* Voice */}
        <Section title="Voice & Tonalität" eyebrow="08" kicker="Dieselbe Sprache wie der Email-Briefing: knapp, datenehrlich, ohne Werbe-Floskeln.">
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
            <Card padding={20} accent>
              <Eyebrow style={{ color: "var(--g-good)", marginBottom: 8 }}>Tun</Eyebrow>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.6, color: "var(--g-ink-2)" }}>
                <li>"Heute 18:00 geht ein Abend-Briefing an Email + Signal."</li>
                <li>"Böen bis 47 km/h ab 17:00."</li>
                <li>"Ohne Stirnlampe: 05:43 – 21:10."</li>
              </ul>
            </Card>
            <Card padding={20} style={{ borderLeft: "3px solid var(--g-bad)" }}>
              <Eyebrow style={{ color: "var(--g-bad)", marginBottom: 8 }}>Lassen</Eyebrow>
              <ul style={{ margin: 0, paddingLeft: 18, fontSize: 14, lineHeight: 1.6, color: "var(--g-ink-2)" }}>
                <li><span style={{ textDecoration: "line-through" }}>"Wir kümmern uns um dein Wetter!"</span></li>
                <li><span style={{ textDecoration: "line-through" }}>"Aktiviere jetzt deinen Premium-Schutz"</span></li>
                <li><span style={{ textDecoration: "line-through" }}>"Trip-Erlebnis revolutioniert"</span></li>
              </ul>
            </Card>
          </div>
        </Section>

      </div>
    </div>
  );
}

function Section({ title, eyebrow, kicker, children }) {
  return (
    <section style={{ marginBottom: 56 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 16, marginBottom: 18, paddingBottom: 12, borderBottom: "1px solid var(--g-rule)" }}>
        <span className="mono" style={{ fontSize: 12, color: "var(--g-accent)", fontWeight: 500 }}>{eyebrow}</span>
        <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>{title}</div>
      </div>
      {kicker && <div style={{ color: "var(--g-ink-3)", fontSize: 14, maxWidth: 700, marginBottom: 18 }}>{kicker}</div>}
      {children}
    </section>
  );
}

function ColorRow({ label, colors }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "var(--g-track-caps)", marginBottom: 6 }}>{label}</div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(5, 1fr)", gap: 12 }}>
        {colors.map(c => (
          <div key={c.n} style={{ border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", overflow: "hidden", background: "var(--g-card)" }}>
            <div style={{ height: 60, background: c.v, borderBottom: "1px solid var(--g-rule-soft)" }}/>
            <div style={{ padding: "8px 10px" }}>
              <div className="mono" style={{ fontSize: 11, fontWeight: 500, color: "var(--g-ink)" }}>{c.n}</div>
              <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)" }}>{c.hex}</div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

window.ScreenDesignSystem = ScreenDesignSystem;

/* Local helper: Switch + Label row for the showcase. */
function SwitchRow({ label, tone }) {
  const [on, setOn] = React.useState(true);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <Switch checked={on} onChange={setOn} tone={tone}/>
      <span style={{ fontSize: 13, color: "var(--g-ink-2)" }}>{label}</span>
    </div>
  );
}
