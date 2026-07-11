/* Screen: Trip-Wizard (Desktop) — 5 Schritte gem. Spec issue_407_422 + PO-Korrektur 2026-05-27:
 *   1. Route   — Trip-Name + Region + GPX-Upload
 *   2. Etappen — Liste erkannter Etappen + Vorlagen-Panel
 *   3. Wetter  — Aktivitätsprofil + Metriken-Tabelle (Format-Variante pro Metrik, scrollbar)
 *   4. Layout  — Reihenfolge & Spalten-Auswahl pro Kanal (Email/Telegram/Signal/SMS)
 *   5. Reports — 3 Cards: Abend (mit 3–7-Tage-Toggle) · Morgen · Warnungen
 *
 * Konzept-Wechsel ggü. body-407_422 v1:
 * - „Horizonte HEUTE/MORGEN/ÜBERMORGEN" sind kein Trip-Setting → raus aus Step 3.
 * - Format ist pro Metrik wählbar (Roh / Vereinfacht / Skala / Symbol).
 * - Output-Layout wird Wizard-Step 4, nicht erst im Trip-Detail.
 *   Abend + Morgen nutzen dasselbe Layout pro Kanal.
 * - Step 5: Mehrtages-Trend wandert als Toggle in Abend-Briefing-Card.
 *   AUTARK ist der Default, nicht ein Feature → kein Pill mehr.
 */

const WIZARD_STEPS = [
  { n: 1, label: "Route",   sub: "Name & GPX hochladen" },
  { n: 2, label: "Etappen", sub: "Etappen prüfen" },
  { n: 3, label: "Wetter",  sub: "Metriken auswählen" },
  { n: 4, label: "Layout",  sub: "Reihenfolge pro Kanal" },
  { n: 5, label: "Reports", sub: "Zeitplan & Versand" },
];

const WIZ_TITLES = {
  1: "Route — wie kennt das System deinen Weg?",
  2: "Etappen — stimmt die Tagesaufteilung?",
  3: "Wetter — welche Daten sollen ins Briefing?",
  4: "Layout — wie sieht das Briefing pro Kanal aus?",
  5: "Reports — wann und wohin?",
};

const ACTIVITY_PROFILES_WIZ = [
  { id: "standard",   label: "Standard (kein Profil)" },
  { id: "trekking",   label: "Alpen-Trekking · Sommer" },
  { id: "skitour",    label: "Skitour · Winter" },
  { id: "alpine",     label: "Hochtour · Eis & Fels" },
  { id: "ferrata",    label: "Klettersteig" },
  { id: "coast",      label: "Küsten- & Inseltour" },
  { id: "mtb",        label: "Mountainbike" },
];

/* Format-Optionen (Skizze — Claude Code bestimmt finalen Satz pro Metrik) */
const FORMAT_OPTIONS = [
  { id: "raw",      label: "Roh" },
  { id: "scale",    label: "Skala" },
  { id: "simple",   label: "Vereinfacht" },
  { id: "symbol",   label: "Symbol" },
];

/* Längere Mock-Liste, damit Scroll erkennbar ist */
const WIZ_METRICS_FULL = [
  { id: "temp",      group: "Temperatur",   label: "Temperatur",          defaultFormat: "raw" },
  { id: "feels",     group: "Temperatur",   label: "Gefühlte Temperatur", defaultFormat: "raw" },
  { id: "humid",     group: "Temperatur",   label: "Luftfeuchte",         defaultFormat: "raw" },
  { id: "wind",      group: "Wind",         label: "Wind",                defaultFormat: "scale" },
  { id: "gust",      group: "Wind",         label: "Böen",                defaultFormat: "raw" },
  { id: "windDir",   group: "Wind",         label: "Windrichtung",        defaultFormat: "symbol" },
  { id: "rain",      group: "Niederschlag", label: "Niederschlag",        defaultFormat: "raw" },
  { id: "rainProb",  group: "Niederschlag", label: "Regen-Wahrscheinl.",  defaultFormat: "raw" },
  { id: "thunder",   group: "Niederschlag", label: "Gewitter",            defaultFormat: "scale" },
  { id: "snow",      group: "Niederschlag", label: "Schneefallgrenze",    defaultFormat: "raw" },
  { id: "snowfall",  group: "Niederschlag", label: "Neuschnee",           defaultFormat: "raw" },
  { id: "cloud",     group: "Sicht & Sonne", label: "Bewölkung",           defaultFormat: "simple" },
  { id: "vis",       group: "Sicht & Sonne", label: "Sichtweite",          defaultFormat: "raw" },
  { id: "uv",        group: "Sicht & Sonne", label: "UV-Index",            defaultFormat: "scale" },
  { id: "sun",       group: "Sicht & Sonne", label: "Sonnenstunden",       defaultFormat: "raw" },
  { id: "pressure",  group: "Atmosphäre",   label: "Luftdruck",           defaultFormat: "raw" },
  { id: "dew",       group: "Atmosphäre",   label: "Taupunkt",            defaultFormat: "raw" },
];

const WIZ_TEMPLATES = [
  { id: "gr20", name: "GR20",                region: "Korsika",         stages: 14, kind: "Trekking" },
  { id: "khw",  name: "Karnischer Höhenweg", region: "Karnische Alpen", stages: 13, kind: "Trekking" },
  { id: "stub", name: "Stubaier Höhenweg",   region: "Tirol",           stages: 7,  kind: "Trekking" },
];

const CHANNEL_DEFS = [
  { id: "email",    label: "Email",    icon: "✉", maxCols: Infinity, constraint: "Keine Begrenzung — zeigt alles" },
  { id: "telegram", label: "Telegram", icon: "→", maxCols: 8,        constraint: "max 8 Spalten" },
  { id: "signal",   label: "Signal",   icon: "▲", maxCols: 6,        constraint: "max 6 Spalten" },
  { id: "sms",      label: "SMS",      icon: "*", maxCols: 0,        constraint: "Keine Tabelle · ≤140 Zeichen · Priorität entscheidet" },
];

function ScreenTripWizard({ initialStep = 1 }) {
  const [step, setStep] = React.useState(initialStep);
  const [profile, setProfile] = React.useState("standard");
  const [tripName, setTripName] = React.useState("");
  const [region, setRegion] = React.useState("");
  const [gpxLoaded, setGpxLoaded] = React.useState(initialStep > 1);

  /* Trip-weite Metriken-Auswahl + Format. Shared state für Step 3 + Step 4. */
  const [selectedMetrics, setSelectedMetrics] = React.useState(() => {
    const o = {};
    WIZ_METRICS_FULL.forEach(m => {
      o[m.id] = { enabled: ["temp", "wind", "gust", "rain", "thunder", "snow", "vis", "sun"].includes(m.id), format: m.defaultFormat };
    });
    return o;
  });

  const goto = (n) => { if (n <= step || n === step + 1) setStep(n); };
  const next = () => setStep(Math.min(5, step + 1));
  const prev = () => setStep(Math.max(1, step - 1));

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative" }}>
        <TopoBg opacity={0.16}/>

        <div style={{ position: "relative", padding: "32px 80px 60px", maxWidth: 1180, margin: "0 auto" }}>
          <Eyebrow style={{ marginBottom: 8 }}>Schritt {step} von 5 · Neue Tour</Eyebrow>
          <div style={{ fontSize: 30, fontWeight: 600, letterSpacing: "-0.02em", marginBottom: 28, color: "var(--g-ink)" }}>
            {WIZ_TITLES[step]}
          </div>

          <WizStepper step={step} onStep={goto}/>

          <div style={{ marginTop: 40 }}>
            {step === 1 && (
              <StepRoute
                tripName={tripName} onTripName={setTripName}
                region={region} onRegion={setRegion}
                gpxLoaded={gpxLoaded} onGpxLoad={() => setGpxLoaded(true)}
              />
            )}
            {step === 2 && <StepEtappen/>}
            {step === 3 && (
              <StepWetter
                profile={profile} onProfile={setProfile}
                metrics={selectedMetrics} onChange={setSelectedMetrics}
              />
            )}
            {step === 4 && <StepLayout metrics={selectedMetrics}/>}
            {step === 5 && <StepReports/>}
          </div>

          {step === 5 && (
            <div style={{
              marginTop: 36, textAlign: "center",
              fontSize: 13, color: "var(--g-ink-3)", fontStyle: "italic",
            }}>
              Unterwegs läuft alles autark. Kein Eingreifen nötig.
            </div>
          )}

          <WizFooter
            step={step}
            totalSteps={5}
            onPrev={prev}
            onNext={next}
            onSave={() => {}}
            extra={step === 2 && <Btn variant="ghost" size="md">+ Pausentag einfügen</Btn>}
            canAdvance={step === 1 ? (tripName.trim() && gpxLoaded) : true}
          />
        </div>
      </main>
    </div>
  );
}

/* ─────────────────── Stepper ─────────────────── */

function WizStepper({ step, onStep }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-start", gap: 0, padding: "8px 0" }}>
      {WIZARD_STEPS.map((s, i) => {
        const state = s.n < step ? "done" : s.n === step ? "current" : "upcoming";
        return (
          <React.Fragment key={s.n}>
            <WizStep step={s} state={state} onClick={() => onStep(s.n)}/>
            {i < WIZARD_STEPS.length - 1 && (
              <div style={{
                flex: 1, height: 1, marginTop: 21,
                background: s.n < step ? "var(--g-ink-3)" : "var(--g-rule)",
                opacity: s.n < step ? 0.5 : 1,
                minWidth: 24,
              }}/>
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
}

function WizStep({ step, state, onClick }) {
  const clickable = state !== "upcoming";
  const cfg = {
    done:     { bg: "var(--g-paper)",  border: "1.5px solid var(--g-ink-3)",   color: "var(--g-ink-2)" },
    current:  { bg: "var(--g-paper)",  border: "2px solid var(--g-accent)",    color: "var(--g-accent)" },
    upcoming: { bg: "var(--g-paper)",  border: "1.5px solid var(--g-rule)",    color: "var(--g-ink-4)" },
  }[state];

  return (
    <div
      onClick={clickable ? onClick : undefined}
      style={{
        display: "flex", flexDirection: "column", alignItems: "center", gap: 6,
        cursor: clickable ? "pointer" : "default", flexShrink: 0, width: 112, textAlign: "center",
      }}
    >
      <div style={{
        width: 40, height: 40, borderRadius: "50%",
        display: "flex", alignItems: "center", justifyContent: "center",
        background: cfg.bg, border: cfg.border, color: cfg.color,
        fontSize: state === "done" ? 15 : 14, fontWeight: 600,
        fontFamily: state === "done" ? "var(--g-font-sans)" : "var(--g-font-mono)",
      }}>
        {state === "done" ? "✓" : step.n}
      </div>
      <div style={{
        fontSize: 13, fontWeight: 600, marginTop: 2,
        color: state === "current" ? "var(--g-ink)" : state === "done" ? "var(--g-ink-2)" : "var(--g-ink-4)",
      }}>{step.label}</div>
      <div className="mono" style={{
        fontSize: 10, letterSpacing: "0.04em",
        color: state === "current" ? "var(--g-ink-3)" : "var(--g-ink-4)",
      }}>{step.sub}</div>
    </div>
  );
}

/* ─────────────────── Footer ─────────────────── */

function WizFooter({ step, totalSteps, onPrev, onNext, onSave, extra, canAdvance }) {
  const isFirst = step === 1;
  const isLast = step === totalSteps;
  return (
    <div style={{
      marginTop: 36, paddingTop: 20, borderTop: "1px solid var(--g-rule)",
      display: "grid", gridTemplateColumns: "1fr auto 1fr", alignItems: "center", gap: 12,
    }}>
      <div>{!isFirst && <Btn variant="ghost" size="md" onClick={onPrev}>← Zurück</Btn>}</div>
      <div>{extra}</div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10 }}>
        <Btn variant="quiet" size="md">Abbrechen</Btn>
        {isLast ? (
          <Btn variant="accent" size="md" onClick={onSave}>Tour speichern</Btn>
        ) : (
          <Btn variant="accent" size="md" onClick={onNext}
            style={canAdvance ? null : { opacity: 0.4, cursor: "not-allowed" }}>
            Weiter →
          </Btn>
        )}
      </div>
    </div>
  );
}

/* ─────────────────── Schritt 1 — Route ─────────────────── */

function StepRoute({ tripName, onTripName, region, onRegion, gpxLoaded, onGpxLoad }) {
  return (
    <div style={{ maxWidth: 720, margin: "0 auto" }}>
      <Eyebrow style={{ marginBottom: 14 }}>Eckdaten</Eyebrow>

      <Field label="Trip-Name" required>
        <Input value={tripName} onChange={(e) => onTripName(e.target.value)}
          placeholder="z.B. Karnischer Höhenweg 2026" size="lg"/>
      </Field>

      <Field label="Region" hint="Optional — wird im Briefing-Header angezeigt"
        right={<span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>(optional · max 50)</span>}>
        <Input value={region} onChange={(e) => onRegion(e.target.value.slice(0, 50))}
          placeholder="z.B. Korsika, Mallorca, Karnische Alpen" size="lg"/>
      </Field>

      <div style={{ marginTop: 28 }}>
        <Eyebrow style={{ marginBottom: 10 }}>GPX-Upload</Eyebrow>

        {gpxLoaded ? (
          <div style={{
            padding: "18px 22px", borderRadius: "var(--g-r-3)",
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            display: "flex", alignItems: "center", gap: 14,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8, background: "var(--g-accent-tint)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "var(--g-accent-deep)", fontFamily: "var(--g-font-mono)", fontSize: 11, fontWeight: 700,
            }}>GPX</div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 14, fontWeight: 600 }}>karnischer-hoehenweg.gpx</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
                142.6 km · 13 erkannte Etappen · ↑7820 ↓7340
              </div>
            </div>
            <Btn variant="ghost" size="sm">Andere Datei wählen</Btn>
          </div>
        ) : (
          <div onClick={onGpxLoad}
            style={{
              padding: "44px 24px", borderRadius: "var(--g-r-3)",
              border: "1.5px dashed var(--g-accent)", background: "var(--g-accent-tint)",
              textAlign: "center", cursor: "pointer", transition: "background 120ms",
            }}>
            <WizUploadGlyph/>
            <div style={{ fontSize: 15, fontWeight: 600, color: "var(--g-ink)", marginTop: 12 }}>
              GPX-Datei hierher ziehen
            </div>
            <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginTop: 4 }}>
              oder <span style={{ color: "var(--g-accent-deep)", textDecoration: "underline" }}>aus Dateisystem wählen</span>
            </div>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 10, letterSpacing: "0.04em" }}>
              .GPX · Komoot · Outdooractive · Garmin · FootPath
            </div>
          </div>
        )}

        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 12, textAlign: "center", fontStyle: "italic" }}>
          GPX-Upload empfohlen — manuelle Eingabe geht auch (über »+ Etappe einschieben« in Schritt 2).
        </div>
      </div>
    </div>
  );
}

function WizUploadGlyph() {
  return (
    <svg width={36} height={36} viewBox="0 0 24 24" fill="none" stroke="var(--g-accent-deep)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 16V4M7 9l5-5 5 5"/>
      <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
    </svg>
  );
}

/* ─────────────────── Schritt 2 — Etappen ─────────────────── */

const MOCK_DETECTED_STAGES = [
  { n: 1,  date: "06.05.2026", name: "Toblach → Helmhotel",          km: 9.3,  asc: 203,  wp: 4, suggestions: 2 },
  { n: 2,  date: "07.05.2026", name: "Helmhotel → Sillianer Hütte",  km: 12.4, asc: 1235, wp: 5, suggestions: 3 },
  { n: 3,  date: "08.05.2026", name: "Sillianer → Obstanserseehütte", km: 13.2, asc: 540,  wp: 3, suggestions: 1 },
  { n: 4,  date: "09.05.2026", name: "Obstanserse → Porzehütte",      km: 11.8, asc: 720,  wp: 4, suggestions: 2 },
  { n: 5,  date: "10.05.2026", name: "Porze → Hochweißsteinhaus",     km: 14.5, asc: 980,  wp: 5, suggestions: 0 },
  { n: 6,  date: "11.05.2026", name: "Hochweißstein → Wolayersee",    km: 13.1, asc: 860,  wp: 4, suggestions: 2 },
];

function StepEtappen() {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: 28 }}>
      <div>
        <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
          <div>
            <Eyebrow>{MOCK_DETECTED_STAGES.length} Etappen erkannt aus 1 GPX</Eyebrow>
          </div>
          <div style={{ display: "flex", gap: 14 }}>
            <button className="mono" style={linkBtn}>Zusammenführen</button>
            <button className="mono" style={linkBtn}>+ Etappe einschieben</button>
          </div>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
          {MOCK_DETECTED_STAGES.map(s => <WizStageRow key={s.n} stage={s}/>)}
        </div>
      </div>

      <div>
        <Eyebrow style={{ marginBottom: 10 }}>Vorlagen</Eyebrow>
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {WIZ_TEMPLATES.map(t => (
            <Card key={t.id} padding={14} style={{ borderLeft: "3px solid var(--g-accent)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 8 }}>
                <div style={{ fontSize: 14, fontWeight: 600, lineHeight: 1.25 }}>{t.name}</div>
                <Pill tone="neutral">{t.kind}</Pill>
              </div>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 4 }}>
                {t.region} · {t.stages} Etappen
              </div>
              <Btn variant="ghost" size="sm" style={{ marginTop: 10, width: "100%", justifyContent: "center" }}>
                Vorlage laden
              </Btn>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

const linkBtn = {
  background: "transparent", border: "none", padding: 0, cursor: "pointer",
  fontSize: 11, color: "var(--g-accent-deep)",
  letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600,
};

function WizStageRow({ stage }) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "20px 32px 92px 1fr 60px 70px 50px 28px",
      alignItems: "center", gap: 12, padding: "12px 16px",
      background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
    }}>
      <span className="mono" style={{ fontSize: 12, color: "var(--g-ink-4)", cursor: "grab" }}>⋮⋮</span>
      <span className="mono" style={stageNumberPill}>T{String(stage.n).padStart(2,"0")}</span>
      <span className="mono" style={{ fontSize: 12, color: "var(--g-ink-3)" }}>{stage.date}</span>
      <span style={{ fontSize: 14, fontWeight: 500, color: "var(--g-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
        {stage.name}
      </span>
      <span className="mono" style={{ fontSize: 12, color: "var(--g-ink-2)", textAlign: "right" }}>{stage.km} km</span>
      <span className="mono" style={{ fontSize: 12, color: "var(--g-ink-2)", textAlign: "right" }}>↑ {stage.asc} m</span>
      <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", textAlign: "right" }}>{stage.wp} WP</span>
      <button aria-label="Entfernen" style={{
        background: "transparent", border: "none", cursor: "pointer", padding: 4,
        color: "var(--g-ink-4)", fontSize: 14, lineHeight: 1,
      }}>×</button>
    </div>
  );
}

const stageNumberPill = {
  fontSize: 11, fontWeight: 700, color: "var(--g-accent-deep)",
  background: "var(--g-accent-tint)", padding: "3px 7px", borderRadius: 999,
  textAlign: "center", letterSpacing: "0.04em",
};

function WizSuggestionPill({ count }) {
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      padding: "3px 9px", borderRadius: 999,
      border: "1px dashed var(--g-accent)",
      color: "var(--g-accent-deep)",
      fontSize: 10, fontWeight: 600, letterSpacing: "0.04em", background: "transparent",
    }}>+{count} {count === 1 ? "Vorschlag" : "Vorschläge"}</span>
  );
}

/* ─────────────────── Schritt 3 — Wetter (Auswahl + Format) ─────────────────── */

function StepWetter({ profile, onProfile, metrics, onChange }) {
  const toggleMetric = (id) =>
    onChange({ ...metrics, [id]: { ...metrics[id], enabled: !metrics[id].enabled } });

  const setFormat = (id, format) =>
    onChange({ ...metrics, [id]: { ...metrics[id], format } });

  const profileObj = ACTIVITY_PROFILES_WIZ.find(p => p.id === profile);
  const enabledCount = Object.values(metrics).filter(m => m.enabled).length;

  /* nach Gruppe gruppieren */
  const groups = WIZ_METRICS_FULL.reduce((acc, m) => {
    (acc[m.group] ||= []).push(m);
    return acc;
  }, {});

  return (
    <div style={{ maxWidth: 920, margin: "0 auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 32, alignItems: "start", marginBottom: 24 }}>
        <div>
          <Eyebrow style={{ marginBottom: 8 }}>Aktivitätsprofil</Eyebrow>
          <WizSelect value={profile} onChange={onProfile} options={ACTIVITY_PROFILES_WIZ}/>
        </div>
        <div style={{ paddingTop: 22 }}>
          <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
            {profile === "standard"
              ? "Standard-Metriken werden verwendet. Wähle ein Profil für eine kuratierte Auswahl — du kannst sie unten frei anpassen."
              : <>Profil <strong style={{ color: "var(--g-ink)" }}>{profileObj.label}</strong> geladen. Anpassbar.</>}
          </div>
        </div>
      </div>

      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 10 }}>
        <Eyebrow>Metriken · {enabledCount} aktiv von {WIZ_METRICS_FULL.length}</Eyebrow>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
          Reihenfolge & Kanal-Zuordnung kommen in Schritt 4
        </div>
      </div>

      <WizMetricListHeader/>

      {/* Scrollbarer Bereich mit Fade — macht klar dass mehr existiert */}
      <div style={{ position: "relative" }}>
        <div style={{
          maxHeight: 540, overflowY: "auto",
          border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
          background: "var(--g-paper)",
        }}>
          {Object.entries(groups).map(([groupName, items]) => (
            <div key={groupName}>
              <div className="mono" style={{
                padding: "10px 16px 6px", fontSize: 10, fontWeight: 600,
                color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase",
                background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule-soft)",
                position: "sticky", top: 0, zIndex: 1,
              }}>{groupName}</div>
              {items.map(m => (
                <WizMetricRow
                  key={m.id} metric={m}
                  state={metrics[m.id]}
                  onToggle={() => toggleMetric(m.id)}
                  onFormat={(f) => setFormat(m.id, f)}
                />
              ))}
            </div>
          ))}
        </div>
        {/* Fade-Indikator bottom */}
        <div style={{
          position: "absolute", left: 1, right: 1, bottom: 1, height: 28,
          background: "linear-gradient(to top, var(--g-paper) 0%, rgba(246,244,238,0) 100%)",
          pointerEvents: "none", borderRadius: "0 0 var(--g-r-2) var(--g-r-2)",
        }}/>
      </div>

      <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", marginTop: 12, lineHeight: 1.5, textAlign: "center", letterSpacing: "0.03em" }}>
        Format-Variante pro Metrik wählbar. SMS verwendet automatisch die kompakteste Variante (Symbol oder Skala).
      </div>
    </div>
  );
}

function WizMetricListHeader() {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "28px 1fr 220px",
      gap: 16, padding: "0 16px 8px", alignItems: "center",
    }}>
      <span/>
      <span className="mono" style={tableHeader}>Metrik</span>
      <span className="mono" style={tableHeader}>Format</span>
    </div>
  );
}

const tableHeader = {
  fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase",
};

function WizMetricRow({ metric, state, onToggle, onFormat }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "28px 1fr 220px",
      gap: 16, padding: "10px 16px", alignItems: "center",
      background: state.enabled ? "var(--g-card)" : "transparent",
      borderBottom: "1px solid var(--g-rule-soft)",
      opacity: state.enabled ? 1 : 0.55,
      transition: "opacity 120ms, background 120ms",
    }}>
      <WizCheckbox checked={state.enabled} onChange={onToggle}/>
      <span style={{ fontSize: 14, fontWeight: 500 }}>{metric.label}</span>
      <WizFormatSelect value={state.format} onChange={onFormat} disabled={!state.enabled}/>
    </div>
  );
}

function WizFormatSelect({ value, onChange, disabled }) {
  const current = FORMAT_OPTIONS.find(o => o.id === value) || FORMAT_OPTIONS[0];
  return (
    <div style={{
      position: "relative", opacity: disabled ? 0.5 : 1,
    }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        style={{
          width: "100%", appearance: "none", WebkitAppearance: "none",
          background: "var(--g-paper)", border: "1px solid var(--g-rule)",
          borderRadius: "var(--g-r-2)", padding: "6px 28px 6px 10px",
          fontSize: 12.5, fontFamily: "var(--g-font-sans)",
          color: "var(--g-ink-2)", cursor: disabled ? "not-allowed" : "pointer",
        }}>
        {FORMAT_OPTIONS.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      <span className="mono" style={{
        position: "absolute", right: 28, top: "50%", transform: "translateY(-50%)",
        pointerEvents: "none", color: "var(--g-ink-4)", fontSize: 9.5,
      }}>·</span>
      <span style={{
        position: "absolute", right: 10, top: "50%", transform: "translateY(-50%)",
        pointerEvents: "none", color: "var(--g-ink-3)", fontSize: 9,
      }}>▼</span>
    </div>
  );
}

function WizCheckbox({ checked, onChange }) {
  return (
    <span onClick={onChange} role="checkbox" aria-checked={checked} style={{
      width: 18, height: 18, borderRadius: 3,
      border: checked ? "1.5px solid var(--g-accent)" : "1.5px solid var(--g-ink-3)",
      background: checked ? "var(--g-accent)" : "transparent",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      cursor: "pointer", flexShrink: 0,
      color: "#fff", fontSize: 12, lineHeight: 1, fontWeight: 700,
    }}>{checked && "✓"}</span>
  );
}

function WizSelect({ value, onChange, options }) {
  return (
    <div style={{
      position: "relative", background: "var(--g-card)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
    }}>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{
        width: "100%", appearance: "none", WebkitAppearance: "none",
        background: "transparent", border: "none", outline: "none",
        padding: "10px 32px 10px 12px",
        fontSize: 14, fontFamily: "var(--g-font-sans)",
        color: "var(--g-ink)", cursor: "pointer",
      }}>
        {options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      <span style={{
        position: "absolute", right: 12, top: "50%", transform: "translateY(-50%)",
        pointerEvents: "none", color: "var(--g-ink-3)", fontSize: 10,
      }}>▼</span>
    </div>
  );
}

/* ─────────────────── Schritt 4 — Layout (Reihenfolge pro Kanal) ─────────────────── */

function StepLayout({ metrics }) {
  const [activeChannel, setActiveChannel] = React.useState("email");
  const channel = CHANNEL_DEFS.find(c => c.id === activeChannel);

  /* Reihenfolge ist pro Kanal lokal mockbar — startet mit allen aktiven Metriken in default-order */
  const enabledIds = WIZ_METRICS_FULL.filter(m => metrics[m.id]?.enabled).map(m => m.id);

  const [orderByChannel, setOrderByChannel] = React.useState(() => {
    const o = {};
    CHANNEL_DEFS.forEach(c => { o[c.id] = enabledIds.slice(); });
    return o;
  });

  /* Wenn Kanal-Constraint kleiner als Auswahl: erste N sind „in Tabelle", Rest „Detail" */
  const order = orderByChannel[activeChannel] || enabledIds;
  const maxCols = channel.maxCols;
  const inTable = maxCols === Infinity ? order : order.slice(0, maxCols);
  const overflow = maxCols === Infinity ? [] : order.slice(maxCols);

  const move = (fromIdx, toIdx) => {
    if (fromIdx === toIdx) return;
    const next = order.slice();
    const [m] = next.splice(fromIdx, 1);
    next.splice(toIdx, 0, m);
    setOrderByChannel({ ...orderByChannel, [activeChannel]: next });
  };

  return (
    <div style={{ maxWidth: 1100, margin: "0 auto" }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 14 }}>
        <Eyebrow>Layout pro Kanal · Abend &amp; Morgen nutzen denselben Aufbau</Eyebrow>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>
          Drag zum Sortieren · überzählige Metriken wandern in „Detail" oder fallen weg
        </div>
      </div>

      {/* Channel Tabs */}
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 0,
        border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
        background: "var(--g-paper)", marginBottom: 20, overflow: "hidden",
      }}>
        {CHANNEL_DEFS.map(c => (
          <WizChannelTab
            key={c.id} channel={c}
            active={c.id === activeChannel}
            onClick={() => setActiveChannel(c.id)}
          />
        ))}
      </div>

      {/* Body: two-col */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 380px", gap: 28, alignItems: "start" }}>
        {/* Left: Drag-Liste */}
        <div>
          {channel.id === "sms" ? (
            <WizSMSPrioList order={order} metrics={metrics}/>
          ) : (
            <>
              <Eyebrow style={{ marginBottom: 8 }}>
                Spalten · {inTable.length}{maxCols !== Infinity && ` von max ${maxCols}`}
              </Eyebrow>
              <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: overflow.length ? 14 : 0 }}>
                {inTable.map((id, i) => (
                  <WizLayoutRow
                    key={id} metric={WIZ_METRICS_FULL.find(m => m.id === id)}
                    format={metrics[id].format}
                    position={i + 1} columnHint="Spalte"
                    onMoveUp={i > 0 ? () => move(i, i - 1) : null}
                    onMoveDown={i < inTable.length - 1 ? () => move(i, i + 1) : null}
                  />
                ))}
              </div>
              {overflow.length > 0 && (
                <>
                  <Eyebrow style={{ marginBottom: 8, color: "var(--g-warn)" }}>
                    Passt nicht in Tabelle — wandert in „Detail"-Zeile · {overflow.length}
                  </Eyebrow>
                  <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
                    {overflow.map((id, i) => (
                      <WizLayoutRow
                        key={id} metric={WIZ_METRICS_FULL.find(m => m.id === id)}
                        format={metrics[id].format}
                        position={inTable.length + i + 1} columnHint="Detail"
                        onMoveUp={() => move(inTable.length + i, inTable.length + i - 1)}
                        onMoveDown={i < overflow.length - 1 ? () => move(inTable.length + i, inTable.length + i + 1) : null}
                      />
                    ))}
                  </div>
                </>
              )}
            </>
          )}
        </div>

        {/* Right: Preview */}
        <div style={{ position: "sticky", top: 24 }}>
          <Eyebrow style={{ marginBottom: 8 }}>Vorschau · {channel.label}</Eyebrow>
          <WizChannelPreview channel={channel} order={order} metrics={metrics}/>
        </div>
      </div>
    </div>
  );
}

function WizChannelTab({ channel, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: "12px 14px", textAlign: "left", cursor: "pointer",
      background: active ? "var(--g-card)" : "transparent",
      border: "none", borderRight: "1px solid var(--g-rule-soft)",
      borderBottom: active ? "2px solid var(--g-accent)" : "2px solid transparent",
      transition: "all 120ms",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <span className="mono" style={{ fontSize: 12, color: active ? "var(--g-accent)" : "var(--g-ink-4)" }}>{channel.icon}</span>
        <span style={{ fontSize: 13, fontWeight: 600, color: active ? "var(--g-ink)" : "var(--g-ink-2)" }}>{channel.label}</span>
      </div>
      <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", marginTop: 4, letterSpacing: "0.04em" }}>
        {channel.constraint}
      </div>
    </button>
  );
}

function WizLayoutRow({ metric, format, position, columnHint, onMoveUp, onMoveDown }) {
  const fmt = FORMAT_OPTIONS.find(f => f.id === format) || FORMAT_OPTIONS[0];
  const isDetail = columnHint === "Detail";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "20px 28px 1fr auto 60px",
      gap: 10, alignItems: "center", padding: "10px 12px",
      background: isDetail ? "var(--g-card-alt)" : "var(--g-card)",
      border: `1px solid ${isDetail ? "var(--g-rule-soft)" : "var(--g-rule)"}`,
      borderRadius: "var(--g-r-2)",
    }}>
      <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)", cursor: "grab" }}>⋮⋮</span>
      <span className="mono" style={{
        fontSize: 10, fontWeight: 700,
        color: isDetail ? "var(--g-ink-3)" : "var(--g-accent-deep)",
        background: isDetail ? "rgba(0,0,0,0.04)" : "var(--g-accent-tint)",
        padding: "2px 6px", borderRadius: 3, textAlign: "center",
      }}>{String(position).padStart(2,"0")}</span>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{metric.label}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>
          {fmt.label} · {metric.group}
        </div>
      </div>
      <span className="mono" style={{
        fontSize: 9.5, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase",
        padding: "3px 8px", borderRadius: 999,
        color: isDetail ? "var(--g-warn)" : "var(--g-ink-3)",
        background: isDetail ? "rgba(192,138,26,0.10)" : "transparent",
        border: isDetail ? "1px solid rgba(192,138,26,0.30)" : "1px solid var(--g-rule)",
      }}>{columnHint}</span>
      <div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>
        <WizArrowBtn dir="up" disabled={!onMoveUp} onClick={onMoveUp}/>
        <WizArrowBtn dir="down" disabled={!onMoveDown} onClick={onMoveDown}/>
      </div>
    </div>
  );
}

function WizArrowBtn({ dir, onClick, disabled }) {
  return (
    <button onClick={onClick} disabled={disabled} style={{
      width: 22, height: 22, padding: 0, cursor: disabled ? "not-allowed" : "pointer",
      background: "transparent", border: "1px solid var(--g-rule)", borderRadius: 3,
      color: disabled ? "var(--g-ink-4)" : "var(--g-ink-2)",
      fontSize: 10, lineHeight: 1, opacity: disabled ? 0.4 : 1,
    }}>{dir === "up" ? "▲" : "▼"}</button>
  );
}

function WizSMSPrioList({ order, metrics }) {
  return (
    <>
      <Eyebrow style={{ marginBottom: 8 }}>Priorisierung · was rein passt, kommt in den Text</Eyebrow>
      <div style={{
        padding: 14, background: "var(--g-card-alt)",
        border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)",
        fontSize: 12.5, color: "var(--g-ink-2)", lineHeight: 1.6, marginBottom: 14,
      }}>
        SMS hat keine Tabelle und nur 140 Zeichen pro Nachricht. Der Renderer geht die Reihenfolge
        von oben durch und nimmt mit, was noch passt — Rest fällt weg. Drag-Reihenfolge anpassen,
        um zu steuern was zuerst greift.
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {order.map((id, i) => (
          <WizLayoutRow
            key={id} metric={WIZ_METRICS_FULL.find(m => m.id === id)}
            format={metrics[id].format}
            position={i + 1} columnHint="Priorität"
            onMoveUp={i > 0 ? () => {} : null}
            onMoveDown={i < order.length - 1 ? () => {} : null}
          />
        ))}
      </div>
    </>
  );
}

function WizChannelPreview({ channel, order, metrics }) {
  const enabled = order.map(id => ({ id, ...WIZ_METRICS_FULL.find(m => m.id === id), state: metrics[id] })).filter(m => m.state.enabled);

  if (channel.id === "email") {
    return <WizEmailPreview metrics={enabled.slice(0, 10)}/>;
  }
  if (channel.id === "telegram" || channel.id === "signal") {
    const cols = enabled.slice(0, channel.maxCols);
    return <WizBubblePreview channel={channel} cols={cols} detail={enabled.slice(channel.maxCols, channel.maxCols + 3)}/>;
  }
  return <WizSMSPreview metrics={enabled}/>;
}

const SAMPLE_VALUES = {
  temp: "11°C", feels: "9°C", humid: "78%", wind: "5 Bft", gust: "55", windDir: "NW",
  rain: "2.3 mm", rainProb: "60%", thunder: "L3", snow: "1800m", snowfall: "—",
  cloud: "bewölkt", vis: "12 km", uv: "5", sun: "3.2 h", pressure: "1014", dew: "8°C",
};

function WizEmailPreview({ metrics }) {
  return (
    <div style={previewFrame}>
      <div style={previewHead}>Email · KHW · Etappe 02</div>
      <div style={{ padding: 12, background: "#fff" }}>
        <div style={{ fontSize: 10, color: "var(--g-ink-3)", marginBottom: 6 }}>Vorschau Spalten-Tabelle</div>
        <div style={{
          display: "grid", gridTemplateColumns: `repeat(${Math.min(metrics.length, 6)}, 1fr)`,
          gap: 0, fontSize: 9.5, fontFamily: "var(--g-font-mono)",
        }}>
          {metrics.slice(0, 6).map(m => (
            <div key={m.id} style={{ padding: "4px 6px", background: "var(--g-card-alt)", borderRight: "1px solid var(--g-rule-soft)", color: "var(--g-ink-3)" }}>
              {m.label.slice(0, 8)}
            </div>
          ))}
          {[0,1,2].map(row => metrics.slice(0,6).map(m => (
            <div key={`${row}-${m.id}`} style={{
              padding: "4px 6px", borderRight: "1px solid var(--g-rule-soft)",
              borderTop: "1px solid var(--g-rule-soft)", color: "var(--g-ink)",
            }}>{SAMPLE_VALUES[m.id] || "—"}</div>
          )))}
        </div>
        {metrics.length > 6 && (
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", marginTop: 6 }}>
            … + {metrics.length - 6} weitere Spalten (in Email sichtbar)
          </div>
        )}
      </div>
    </div>
  );
}

function WizBubblePreview({ channel, cols, detail }) {
  return (
    <div style={previewFrame}>
      <div style={previewHead}>{channel.label} · Bubble</div>
      <div style={{ padding: 14, background: channel.id === "signal" ? "#f3eee2" : "#e7e2d3" }}>
        <div style={{
          background: "#fff", padding: 10, borderRadius: 6, maxWidth: 272,
          fontFamily: "var(--g-font-mono)", fontSize: 10, lineHeight: 1.55,
        }}>
          <div style={{ fontWeight: 700, color: "var(--g-ink)", marginBottom: 6 }}>KHW · Etappe 02 · Morgen</div>
          {/* Mono-Tabelle */}
          <div style={{
            display: "grid",
            gridTemplateColumns: `repeat(${cols.length}, 1fr)`,
            gap: 0, color: "var(--g-ink-2)",
          }}>
            {cols.map(m => (
              <div key={m.id} style={{ paddingRight: 4, fontSize: 9, color: "var(--g-ink-3)" }}>
                {m.label.slice(0, 5)}
              </div>
            ))}
            {cols.map(m => (
              <div key={`v-${m.id}`} style={{ paddingRight: 4, color: "var(--g-ink)", fontWeight: 600 }}>
                {SAMPLE_VALUES[m.id] || "—"}
              </div>
            ))}
          </div>
          {detail.length > 0 && (
            <div style={{ marginTop: 8, paddingTop: 6, borderTop: "1px dashed var(--g-rule)", color: "var(--g-ink-3)" }}>
              <span style={{ color: "var(--g-ink-4)" }}>Detail: </span>
              {detail.map(m => `${m.label.slice(0,5)} ${SAMPLE_VALUES[m.id]||"—"}`).join(" · ")}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function WizSMSPreview({ metrics }) {
  const text = metrics.slice(0, 6).map(m => `${m.label.slice(0,4)} ${SAMPLE_VALUES[m.id]||"—"}`).join(" ");
  const truncated = text.slice(0, 140);
  return (
    <div style={previewFrame}>
      <div style={previewHead}>SMS · ≤140 Zeichen</div>
      <div style={{ padding: 14, background: "#e7e2d3" }}>
        <div style={{
          background: "#fff", padding: 10, borderRadius: 6,
          fontFamily: "var(--g-font-mono)", fontSize: 10.5, lineHeight: 1.5, color: "var(--g-ink)",
        }}>
          {truncated}
        </div>
        <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", marginTop: 6, letterSpacing: "0.04em" }}>
          {truncated.length} / 140 Zeichen · {metrics.length - 6 > 0 ? `${metrics.length - 6} Metriken fielen raus` : "alle drin"}
        </div>
      </div>
    </div>
  );
}

const previewFrame = {
  border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
  overflow: "hidden", background: "var(--g-card)",
};

const previewHead = {
  padding: "8px 12px", borderBottom: "1px solid var(--g-rule-soft)",
  fontSize: 10, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-3)",
  letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600,
  background: "var(--g-card-alt)",
};

/* ─────────────────── Schritt 5 — Reports (3 Cards) ─────────────────── */

function StepReports() {
  const [evening, setEvening] = React.useState(true);
  const [morning, setMorning] = React.useState(true);
  const [trend, setTrend] = React.useState(true);

  return (
    <div style={{ maxWidth: 1080, margin: "0 auto" }}>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 16 }}>
        <WizReportCard
          eyebrow="Abend-Briefing"
          title="Vor dem Schlafen"
          sub="Plan & Vorhersage für morgen."
          active={evening}
          onToggle={() => setEvening(!evening)}
          time="18:00"
          activeChannels={["email", "signal"]}
          trendToggle={{ checked: trend, onChange: () => setTrend(!trend) }}
        />
        <WizReportCard
          eyebrow="Morgen-Update"
          title="Vor Etappenstart"
          sub="Aktuelle Bedingungen für heute."
          active={morning}
          onToggle={() => setMorning(!morning)}
          time="06:00"
          activeChannels={["email"]}
        />
        <WizReportCard
          eyebrow="Warnungen"
          title="Sofort, wenn nötig"
          sub="Alert, sobald eine Alarmregel überschritten wird."
          activeChannels={["signal", "sms"]}
          showTime={false}
          rulesLink
        />
      </div>
    </div>
  );
}

function WizReportCard({ eyebrow, title, sub, active, onToggle, time, activeChannels = [], trendToggle, rulesLink, showTime = true }) {
  return (
    <Card padding={18} style={{ minHeight: 280, display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, marginBottom: 8 }}>
        <div>
          <Eyebrow>{eyebrow}</Eyebrow>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 4, letterSpacing: "-0.01em" }}>{title}</div>
        </div>
        {showTime && <Switch checked={active} onChange={onToggle} tone="accent"/>}
      </div>

      {sub && (
        <div style={{ fontSize: 13, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 14 }}>
          {sub}
        </div>
      )}

      {showTime && (
        <>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12, marginBottom: 12 }}>
            <div style={{ flex: 1 }}>
              <div className="mono" style={miniLabel}>Uhrzeit</div>
              <div className="mono" style={{
                fontSize: 22, fontWeight: 600,
                color: active ? "var(--g-ink)" : "var(--g-ink-4)",
                marginTop: 4, letterSpacing: "0.02em",
              }}>
                {time}<span style={{ fontSize: 11, color: "var(--g-ink-4)", marginLeft: 6, fontWeight: 400 }}>24h</span>
              </div>
            </div>
            <Btn variant="ghost" size="sm">Ändern</Btn>
          </div>
        </>
      )}

      {trendToggle && (
        <div style={{
          padding: "10px 12px", marginBottom: 12,
          background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)",
          borderRadius: "var(--g-r-2)",
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <Switch checked={trendToggle.checked} onChange={trendToggle.onChange} tone="accent" size="sm"/>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 12.5, fontWeight: 500, color: "var(--g-ink)" }}>
              3–7-Tage-Ausblick enthalten
            </div>
            <div style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 1 }}>
              Mehrtages-Trend wird mitgeschickt
            </div>
          </div>
        </div>
      )}

      <div style={{ marginTop: "auto" }}>
        <div className="mono" style={{ ...miniLabel, marginBottom: 6 }}>Versand-Kanäle</div>
        <WizChannelChipRow active={activeChannels}/>
        {rulesLink && (
          <button className="mono" style={{ ...linkBtn, marginTop: 12 }}>
            Alarmregeln verwalten →
          </button>
        )}
        {!rulesLink && (
          <button className="mono" style={{ ...linkBtn, marginTop: 12 }}>
            Inhalt im Output-Editor anpassen →
          </button>
        )}
      </div>
    </Card>
  );
}

const miniLabel = {
  fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.06em", textTransform: "uppercase",
};

function WizChannelChipRow({ active = [], style }) {
  const channels = [
    { id: "email",    label: "✉ Email" },
    { id: "signal",   label: "▲ Signal" },
    { id: "telegram", label: "→ Telegram" },
    { id: "sms",      label: "* SMS" },
  ];
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap", ...style }}>
      {channels.map(c => {
        const on = active.includes(c.id);
        return (
          <span key={c.id} className="mono" style={{
            padding: "4px 10px", borderRadius: 999,
            fontSize: 10, fontWeight: 600, letterSpacing: "0.04em",
            border: on ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
            background: on ? "var(--g-accent-tint)" : "transparent",
            color: on ? "var(--g-accent-deep)" : "var(--g-ink-4)",
          }}>{c.label}</span>
        );
      })}
    </div>
  );
}

window.ScreenTripWizard = ScreenTripWizard;
