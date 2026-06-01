/* Screen: Trip-Wizard (Mobile · 390px) — 5 Schritte gem. Spec issue_407_422 + PO-Korrektur 2026-05-27:
 *   1. Route   — Trip-Name + Region + GPX-Upload
 *   2. Etappen — Liste erkannter Etappen (1-spaltig, stacked) + Vorlagen-Akkordeon
 *   3. Wetter  — Aktivitätsprofil-Dropdown + Metriken (scrollbar, Format-Variante pro Metrik)
 *   4. Layout  — Reihenfolge pro Kanal (Tab-Selector + Drag-Liste + Mini-Preview)
 *   5. Reports — 3 Cards (1-spaltig): Abend (mit 3–7-Tage-Toggle) · Morgen · Warnungen
 *
 * Sticky Top: Schritt-Indikator (5-Segment-Bar). Bottom-Nav ausgeblendet.
 * Step 5: Button „Tour speichern".
 */

const WIZ_TITLES_M = {
  1: "Route — wie kennt das System deinen Weg?",
  2: "Etappen — stimmt die Tagesaufteilung?",
  3: "Wetter — welche Daten sollen ins Briefing?",
  4: "Layout — wie sieht das Briefing aus?",
  5: "Reports — wann und wohin?",
};

const WIZ_STEP_LABELS_M = ["Route", "Etappen", "Wetter", "Layout", "Reports"];

const WIZ_ACTIVITY_M = [
  { id: "standard",  label: "Standard (kein Profil)" },
  { id: "trekking",  label: "Alpen-Trekking · Sommer" },
  { id: "skitour",   label: "Skitour · Winter" },
  { id: "alpine",    label: "Hochtour · Eis & Fels" },
  { id: "ferrata",   label: "Klettersteig" },
  { id: "coast",     label: "Küsten- & Inseltour" },
  { id: "mtb",       label: "Mountainbike" },
];

const WIZ_FORMAT_M = [
  { id: "raw",      label: "Roh" },
  { id: "scale",    label: "Skala" },
  { id: "simple",   label: "Vereinfacht" },
  { id: "symbol",   label: "Symbol" },
];

const WIZ_METRICS_M_FULL = [
  { id: "temp",      group: "Temperatur",    label: "Temperatur",         defaultFormat: "raw" },
  { id: "feels",     group: "Temperatur",    label: "Gefühlte Temp",      defaultFormat: "raw" },
  { id: "humid",     group: "Temperatur",    label: "Luftfeuchte",        defaultFormat: "raw" },
  { id: "wind",      group: "Wind",          label: "Wind",               defaultFormat: "scale" },
  { id: "gust",      group: "Wind",          label: "Böen",               defaultFormat: "raw" },
  { id: "windDir",   group: "Wind",          label: "Windrichtung",       defaultFormat: "symbol" },
  { id: "rain",      group: "Niederschlag",  label: "Niederschlag",       defaultFormat: "raw" },
  { id: "rainProb",  group: "Niederschlag",  label: "Regen-Wahrsch.",     defaultFormat: "raw" },
  { id: "thunder",   group: "Niederschlag",  label: "Gewitter",           defaultFormat: "scale" },
  { id: "snow",      group: "Niederschlag",  label: "Schneefallgrenze",   defaultFormat: "raw" },
  { id: "snowfall",  group: "Niederschlag",  label: "Neuschnee",          defaultFormat: "raw" },
  { id: "cloud",     group: "Sicht & Sonne", label: "Bewölkung",          defaultFormat: "simple" },
  { id: "vis",       group: "Sicht & Sonne", label: "Sichtweite",         defaultFormat: "raw" },
  { id: "uv",        group: "Sicht & Sonne", label: "UV-Index",           defaultFormat: "scale" },
  { id: "sun",       group: "Sicht & Sonne", label: "Sonnenstunden",      defaultFormat: "raw" },
  { id: "pressure",  group: "Atmosphäre",    label: "Luftdruck",          defaultFormat: "raw" },
  { id: "dew",       group: "Atmosphäre",    label: "Taupunkt",           defaultFormat: "raw" },
];

const CHANNEL_DEFS_M = [
  { id: "email",    label: "Email",    icon: "✉", maxCols: Infinity, constraint: "∞ Spalten" },
  { id: "telegram", label: "Telegram", icon: "→", maxCols: 8,        constraint: "max 8 Spalten" },
  { id: "signal",   label: "Signal",   icon: "▲", maxCols: 6,        constraint: "max 6 Spalten" },
  { id: "sms",      label: "SMS",      icon: "*", maxCols: 0,        constraint: "≤140 Zeichen" },
];

const SAMPLE_VALUES_M = {
  temp: "11°C", feels: "9°C", humid: "78%", wind: "5 Bft", gust: "55", windDir: "NW",
  rain: "2.3 mm", rainProb: "60%", thunder: "L3", snow: "1800m", snowfall: "—",
  cloud: "bewölkt", vis: "12 km", uv: "5", sun: "3.2 h", pressure: "1014", dew: "8°C",
};

function ScreenTripWizardMobile({ initialStep = 1 }) {
  const [step, setStep] = React.useState(initialStep);
  const [profile, setProfile] = React.useState("standard");
  const [tripName, setTripName] = React.useState("");
  const [region, setRegion] = React.useState("");
  const [gpxLoaded, setGpxLoaded] = React.useState(initialStep > 1);

  const [selectedMetrics, setSelectedMetrics] = React.useState(() => {
    const o = {};
    WIZ_METRICS_M_FULL.forEach(m => {
      o[m.id] = { enabled: ["temp", "wind", "gust", "rain", "thunder", "snow", "vis", "sun"].includes(m.id), format: m.defaultFormat };
    });
    return o;
  });

  const next = step < 5 ? () => setStep(step + 1) : null;
  const prev = step > 1 ? () => setStep(step - 1) : null;
  const isLast = step === 5;

  const canAdvance = step === 1 ? (tripName.trim() && gpxLoaded) : true;

  const right = (
    <button style={{
      padding: "8px 12px", minHeight: 44, background: "transparent", border: "none",
      fontSize: 14, color: "var(--g-ink-3)", cursor: "pointer", fontWeight: 500,
    }}>Abbrechen</button>
  );

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title={WIZ_STEP_LABELS_M[step - 1]}
          eyebrow={`Schritt ${step} von 5 · Neue Tour`}
          leftIcon={prev ? "back" : "close"}
          right={right}
          onMenu={prev}
        />

        {/* 5-Segment-Fortschrittsbalken */}
        <div style={{
          display: "flex", gap: 3, padding: "10px 16px 12px",
          borderBottom: "1px solid var(--g-rule-soft)", flexShrink: 0,
          background: "var(--g-paper)",
        }}>
          {[1,2,3,4,5].map(n => (
            <div key={n} style={{
              flex: 1, height: 3, borderRadius: 2,
              background: n <= step ? "var(--g-accent)" : "var(--g-rule)",
              transition: "background 200ms",
            }}/>
          ))}
        </div>

        <ScreenScroll padding={16}>
          <Eyebrow style={{ marginBottom: 6, marginTop: 4 }}>
            {step}/5 · {WIZ_STEP_LABELS_M[step - 1]}
          </Eyebrow>
          <h2 style={{
            fontSize: 22, fontWeight: 600, letterSpacing: "-0.02em",
            margin: "0 0 20px", lineHeight: 1.2, color: "var(--g-ink)",
          }}>
            {WIZ_TITLES_M[step]}
          </h2>

          {step === 1 && (
            <MStepRoute
              tripName={tripName} onTripName={setTripName}
              region={region} onRegion={setRegion}
              gpxLoaded={gpxLoaded} onGpxLoad={() => setGpxLoaded(true)}
            />
          )}
          {step === 2 && <MStepEtappen/>}
          {step === 3 && (
            <MStepWetter
              profile={profile} onProfile={setProfile}
              metrics={selectedMetrics} onChange={setSelectedMetrics}
            />
          )}
          {step === 4 && <MStepLayout metrics={selectedMetrics}/>}
          {step === 5 && <MStepReports/>}

          {step === 5 && (
            <div style={{
              marginTop: 16, padding: "12px 4px", textAlign: "center",
              fontSize: 12, color: "var(--g-ink-3)", fontStyle: "italic", lineHeight: 1.5,
            }}>
              Unterwegs läuft alles autark. Kein Eingreifen nötig.
            </div>
          )}
        </ScreenScroll>

        <div style={{
          flexShrink: 0, padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8,
        }}>
          {prev && <MBtn variant="ghost" size="lg" onClick={prev} style={{ flex: 1 }}>← Zurück</MBtn>}
          {isLast ? (
            <MBtn variant="accent" size="lg" style={{ flex: prev ? 1.6 : 1 }}>
              Tour speichern
            </MBtn>
          ) : (
            <MBtn variant="accent" size="lg" onClick={canAdvance ? next : undefined}
              style={{ flex: prev ? 1.6 : 1, opacity: canAdvance ? 1 : 0.4 }}>
              Weiter →
            </MBtn>
          )}
        </div>
      </div>
    </PhoneFrame>
  );
}

/* ─────────────────── Schritt 1 · Route ─────────────────── */
function MStepRoute({ tripName, onTripName, region, onRegion, gpxLoaded, onGpxLoad }) {
  return (
    <>
      <Card padding={16} style={{ marginBottom: 12 }}>
        <Eyebrow style={{ marginBottom: 12 }}>Eckdaten</Eyebrow>
        <MField label="Trip-Name">
          <MInput value={tripName} onChange={(e) => onTripName(e.target.value)} placeholder="z.B. KHW 2026"/>
        </MField>
        <MField label="Region" sub="Optional · max 50 Zeichen">
          <MInput value={region} onChange={(e) => onRegion(e.target.value.slice(0, 50))} placeholder="z.B. Karnische Alpen"/>
        </MField>
      </Card>

      <Card padding={16}>
        <Eyebrow style={{ marginBottom: 10 }}>GPX-Upload</Eyebrow>
        {gpxLoaded ? (
          <div style={{
            padding: "14px 14px", borderRadius: "var(--g-r-2)",
            background: "var(--g-paper)", border: "1px solid var(--g-rule)",
            display: "flex", alignItems: "center", gap: 12,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 8, background: "var(--g-accent-tint)",
              display: "flex", alignItems: "center", justifyContent: "center",
              color: "var(--g-accent-deep)", fontFamily: "var(--g-font-mono)", fontSize: 10, fontWeight: 700, flexShrink: 0,
            }}>GPX</div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ fontSize: 13, fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                karnischer-hoehenweg.gpx
              </div>
              <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 2 }}>
                142.6 km · 13 Etappen
              </div>
            </div>
          </div>
        ) : (
          <button onClick={onGpxLoad} style={{
            width: "100%", minHeight: 180, padding: "24px 16px",
            border: "1.5px dashed var(--g-accent)", background: "var(--g-accent-tint)",
            borderRadius: "var(--g-r-3)",
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 6, cursor: "pointer",
          }}>
            <UploadGlyphM/>
            <div style={{ fontSize: 14, fontWeight: 600, color: "var(--g-ink)", marginTop: 8 }}>GPX-Datei wählen</div>
            <div style={{ fontSize: 12, color: "var(--g-ink-3)" }}>oder hierher ziehen</div>
            <div className="mono" style={{
              fontSize: 9.5, color: "var(--g-ink-4)", marginTop: 8,
              letterSpacing: "0.04em", textAlign: "center", lineHeight: 1.5,
            }}>Komoot · Outdooractive<br/>Garmin · FootPath</div>
          </button>
        )}
        <div className="mono" style={{
          fontSize: 10, color: "var(--g-ink-3)", marginTop: 10,
          fontStyle: "italic", textAlign: "center", lineHeight: 1.5,
        }}>GPX empfohlen — manuelle Eingabe in Schritt 2 möglich.</div>
      </Card>
    </>
  );
}

function UploadGlyphM() {
  return (
    <svg width={32} height={32} viewBox="0 0 24 24" fill="none" stroke="var(--g-accent-deep)" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 16V4M7 9l5-5 5 5"/>
      <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3"/>
    </svg>
  );
}

/* ─────────────────── Schritt 2 · Etappen ─────────────────── */

const MOCK_STAGES_M = [
  { n: 1, date: "06.05.", name: "Toblach → Helmhotel",          km: 9.3,  asc: 203,  wp: 4, suggestions: 2 },
  { n: 2, date: "07.05.", name: "Helmhotel → Sillianer Hütte",  km: 12.4, asc: 1235, wp: 5, suggestions: 3 },
  { n: 3, date: "08.05.", name: "Sillianer → Obstanserseehütte", km: 13.2, asc: 540,  wp: 3, suggestions: 1 },
  { n: 4, date: "09.05.", name: "Obstanserse → Porzehütte",      km: 11.8, asc: 720,  wp: 4, suggestions: 0 },
  { n: 5, date: "10.05.", name: "Porze → Hochweißsteinhaus",     km: 14.5, asc: 980,  wp: 5, suggestions: 2 },
];

function MStepEtappen() {
  return (
    <>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 10 }}>
        <Eyebrow>{MOCK_STAGES_M.length} Etappen aus 1 GPX</Eyebrow>
        <button className="mono" style={mLinkBtn}>Zusammenführen</button>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 6, marginBottom: 14 }}>
        {MOCK_STAGES_M.map(s => <MStageRow key={s.n} stage={s}/>)}
      </div>

      <button style={{
        width: "100%", minHeight: 48, padding: "12px 14px",
        background: "transparent", border: "1px dashed var(--g-rule)",
        borderRadius: "var(--g-r-3)", cursor: "pointer",
        fontSize: 13, color: "var(--g-ink-3)", fontWeight: 500, marginBottom: 14,
      }}>+ Pausentag einschieben</button>

      <Card padding={14}>
        <button style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          width: "100%", padding: 0, background: "transparent", border: "none", cursor: "pointer", minHeight: 32,
        }}>
          <div style={{ textAlign: "left" }}>
            <Eyebrow style={{ marginBottom: 2 }}>Vorlagen</Eyebrow>
            <div style={{ fontSize: 13, color: "var(--g-ink-2)" }}>GR20 · Karnischer Höhenweg · Stubaier Höhenweg …</div>
          </div>
          <MIcon kind="chevron-down" size={18} color="var(--g-ink-3)"/>
        </button>
      </Card>
    </>
  );
}

const mLinkBtn = {
  background: "transparent", border: "none", padding: 0, cursor: "pointer",
  fontSize: 10, color: "var(--g-accent-deep)",
  letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600,
};

function MStageRow({ stage }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "16px 36px 1fr auto",
      gap: 10, alignItems: "center", padding: "12px 12px",
      background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", minHeight: 64,
    }}>
      <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>⋮⋮</span>
      <span className="mono" style={{
        fontSize: 10, fontWeight: 700, color: "var(--g-accent-deep)",
        background: "var(--g-accent-tint)", padding: "3px 6px", borderRadius: 999,
        textAlign: "center", letterSpacing: "0.04em",
      }}>T{String(stage.n).padStart(2,"0")}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontSize: 13, fontWeight: 600, color: "var(--g-ink)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", lineHeight: 1.3,
        }}>{stage.name}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", marginTop: 3 }}>
          {stage.date} · {stage.km} km · ↑{stage.asc} · {stage.wp} WP
        </div>
      </div>
      {stage.suggestions > 0 ? (
        <span className="mono" style={{
          padding: "3px 8px", borderRadius: 999,
          border: "1px dashed var(--g-accent)", color: "var(--g-accent-deep)",
          fontSize: 9.5, fontWeight: 600, letterSpacing: "0.04em", whiteSpace: "nowrap",
        }}>+{stage.suggestions}</span>
      ) : (
        <span className="mono" style={{
          fontSize: 9, color: "var(--g-good)", letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600,
        }}>✓</span>
      )}
    </div>
  );
}

/* ─────────────────── Schritt 3 · Wetter ─────────────────── */
function MStepWetter({ profile, onProfile, metrics, onChange }) {
  const toggleMetric = (id) =>
    onChange({ ...metrics, [id]: { ...metrics[id], enabled: !metrics[id].enabled } });
  const setFormat = (id, format) =>
    onChange({ ...metrics, [id]: { ...metrics[id], format } });

  const groups = WIZ_METRICS_M_FULL.reduce((acc, m) => {
    (acc[m.group] ||= []).push(m);
    return acc;
  }, {});

  const enabledCount = Object.values(metrics).filter(m => m.enabled).length;

  return (
    <>
      <Card padding={14} style={{ marginBottom: 14 }}>
        <Eyebrow style={{ marginBottom: 8 }}>Aktivitätsprofil</Eyebrow>
        <MSelect value={profile} onChange={onProfile} options={WIZ_ACTIVITY_M}/>
      </Card>

      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", marginBottom: 8 }}>
        <Eyebrow>Metriken</Eyebrow>
        <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>
          {enabledCount} / {WIZ_METRICS_M_FULL.length} aktiv
        </span>
      </div>

      <div style={{
        border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
        background: "var(--g-paper)", overflow: "hidden",
      }}>
        {Object.entries(groups).map(([groupName, items]) => (
          <div key={groupName}>
            <div className="mono" style={{
              padding: "10px 14px 6px", fontSize: 10, fontWeight: 600,
              color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase",
              background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule-soft)",
            }}>{groupName}</div>
            {items.map(m => (
              <MMetricRow
                key={m.id} metric={m}
                state={metrics[m.id]}
                onToggle={() => toggleMetric(m.id)}
                onFormat={(f) => setFormat(m.id, f)}
              />
            ))}
          </div>
        ))}
      </div>

      <div className="mono" style={{
        fontSize: 10, color: "var(--g-ink-3)", marginTop: 10,
        lineHeight: 1.5, textAlign: "center",
      }}>
        Reihenfolge & Kanal-Zuordnung in Schritt 4
      </div>
    </>
  );
}

function MMetricRow({ metric, state, onToggle, onFormat }) {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "24px 1fr 110px",
      gap: 10, alignItems: "center", padding: "12px 14px",
      background: state.enabled ? "var(--g-card)" : "transparent",
      borderBottom: "1px solid var(--g-rule-soft)",
      opacity: state.enabled ? 1 : 0.55, minHeight: 52,
    }}>
      <MWizCheckbox checked={state.enabled} onChange={onToggle}/>
      <span style={{ fontSize: 14, fontWeight: 500 }}>{metric.label}</span>
      <MFormatSelect value={state.format} onChange={onFormat} disabled={!state.enabled}/>
    </div>
  );
}

function MFormatSelect({ value, onChange, disabled }) {
  return (
    <div style={{ position: "relative" }}>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        disabled={disabled}
        style={{
          width: "100%", appearance: "none", WebkitAppearance: "none",
          background: "var(--g-paper)", border: "1px solid var(--g-rule)",
          borderRadius: "var(--g-r-2)", padding: "8px 24px 8px 10px",
          fontSize: 12, fontFamily: "var(--g-font-sans)",
          color: "var(--g-ink-2)", cursor: disabled ? "not-allowed" : "pointer",
          minHeight: 36,
        }}>
        {WIZ_FORMAT_M.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      <span style={{
        position: "absolute", right: 8, top: "50%", transform: "translateY(-50%)",
        pointerEvents: "none", color: "var(--g-ink-3)", fontSize: 8,
      }}>▼</span>
    </div>
  );
}

function MWizCheckbox({ checked, onChange }) {
  return (
    <span onClick={onChange} role="checkbox" aria-checked={checked} style={{
      width: 22, height: 22, borderRadius: 4, flexShrink: 0,
      border: checked ? "1.5px solid var(--g-accent)" : "1.5px solid var(--g-ink-3)",
      background: checked ? "var(--g-accent)" : "transparent",
      display: "inline-flex", alignItems: "center", justifyContent: "center", cursor: "pointer",
      color: "#fff", fontSize: 14, lineHeight: 1, fontWeight: 700,
    }}>{checked && "✓"}</span>
  );
}

function MSelect({ value, onChange, options }) {
  return (
    <div style={{
      position: "relative", background: "var(--g-paper)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
    }}>
      <select value={value} onChange={(e) => onChange(e.target.value)} style={{
        width: "100%", appearance: "none", WebkitAppearance: "none",
        background: "transparent", border: "none", outline: "none",
        padding: "12px 32px 12px 14px", fontSize: 16,
        fontFamily: "var(--g-font-sans)", color: "var(--g-ink)", cursor: "pointer", minHeight: 48,
      }}>
        {options.map(o => <option key={o.id} value={o.id}>{o.label}</option>)}
      </select>
      <span style={{
        position: "absolute", right: 14, top: "50%", transform: "translateY(-50%)",
        pointerEvents: "none", color: "var(--g-ink-3)", fontSize: 10,
      }}>▼</span>
    </div>
  );
}

/* ─────────────────── Schritt 4 · Layout (mobile) ─────────────────── */
function MStepLayout({ metrics }) {
  const [activeChannel, setActiveChannel] = React.useState("email");
  const channel = CHANNEL_DEFS_M.find(c => c.id === activeChannel);
  const enabledIds = WIZ_METRICS_M_FULL.filter(m => metrics[m.id]?.enabled).map(m => m.id);

  const [orderByChannel, setOrderByChannel] = React.useState(() => {
    const o = {};
    CHANNEL_DEFS_M.forEach(c => { o[c.id] = enabledIds.slice(); });
    return o;
  });

  const order = orderByChannel[activeChannel] || enabledIds;
  const maxCols = channel.maxCols;
  const inTable = maxCols === Infinity ? order : order.slice(0, maxCols);
  const overflow = maxCols === Infinity ? [] : order.slice(maxCols);

  const move = (fromIdx, dir) => {
    const toIdx = fromIdx + dir;
    if (toIdx < 0 || toIdx >= order.length) return;
    const next = order.slice();
    [next[fromIdx], next[toIdx]] = [next[toIdx], next[fromIdx]];
    setOrderByChannel({ ...orderByChannel, [activeChannel]: next });
  };

  return (
    <>
      <div style={{ fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.5, marginBottom: 12 }}>
        Abend &amp; Morgen nutzen denselben Aufbau. Reihenfolge pro Kanal — überzählige Metriken wandern in „Detail".
      </div>

      {/* Channel Selector — horizontal scroll */}
      <div style={{
        display: "flex", gap: 6, overflowX: "auto", padding: "2px 0 10px",
        WebkitOverflowScrolling: "touch", scrollbarWidth: "none", marginBottom: 4,
      }}>
        {CHANNEL_DEFS_M.map(c => (
          <MChannelChip key={c.id} channel={c}
            active={c.id === activeChannel} onClick={() => setActiveChannel(c.id)}/>
        ))}
      </div>

      <div className="mono" style={{
        fontSize: 10, color: "var(--g-ink-3)", marginBottom: 12,
        letterSpacing: "0.04em",
      }}>{channel.icon} {channel.label} · {channel.constraint}</div>

      {/* Preview FIRST auf Mobile — Kontext vor Aktion */}
      <MChannelPreview channel={channel} order={order} metrics={metrics}/>

      <div style={{ marginTop: 16 }}>
        {channel.id === "sms" ? (
          <Eyebrow style={{ marginBottom: 8 }}>Priorität · oben zuerst</Eyebrow>
        ) : (
          <Eyebrow style={{ marginBottom: 8 }}>
            Spalten · {inTable.length}{maxCols !== Infinity && ` / ${maxCols}`}
          </Eyebrow>
        )}

        <div style={{ display: "flex", flexDirection: "column", gap: 4, marginBottom: overflow.length ? 14 : 0 }}>
          {inTable.map((id, i) => (
            <MLayoutRow
              key={id}
              metric={WIZ_METRICS_M_FULL.find(m => m.id === id)}
              format={metrics[id].format}
              position={i + 1}
              tag={channel.id === "sms" ? null : "Spalte"}
              onUp={i > 0 ? () => move(i, -1) : null}
              onDown={i < inTable.length - 1 ? () => move(i, +1) : null}
            />
          ))}
        </div>

        {overflow.length > 0 && (
          <>
            <Eyebrow style={{ marginBottom: 8, color: "var(--g-warn)" }}>
              Wandert in „Detail" · {overflow.length}
            </Eyebrow>
            <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
              {overflow.map((id, i) => {
                const absIdx = inTable.length + i;
                return (
                  <MLayoutRow
                    key={id}
                    metric={WIZ_METRICS_M_FULL.find(m => m.id === id)}
                    format={metrics[id].format}
                    position={absIdx + 1}
                    tag="Detail"
                    onUp={() => move(absIdx, -1)}
                    onDown={i < overflow.length - 1 ? () => move(absIdx, +1) : null}
                  />
                );
              })}
            </div>
          </>
        )}
      </div>
    </>
  );
}

function MChannelChip({ channel, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      flexShrink: 0, padding: "10px 12px", minHeight: 44,
      background: active ? "var(--g-accent)" : "var(--g-card)",
      color: active ? "#fff" : "var(--g-ink-2)",
      border: `1px solid ${active ? "var(--g-accent)" : "var(--g-rule)"}`,
      borderRadius: "var(--g-r-pill)", cursor: "pointer",
      fontSize: 12, fontFamily: "var(--g-font-mono)", fontWeight: 600,
      letterSpacing: "0.04em", whiteSpace: "nowrap",
      display: "inline-flex", alignItems: "center", gap: 6,
    }}>
      <span>{channel.icon}</span>
      <span>{channel.label}</span>
    </button>
  );
}

function MLayoutRow({ metric, format, position, tag, onUp, onDown }) {
  const fmt = WIZ_FORMAT_M.find(f => f.id === format) || WIZ_FORMAT_M[0];
  const isDetail = tag === "Detail";
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "26px 1fr auto auto",
      gap: 8, alignItems: "center", padding: "10px 10px",
      background: isDetail ? "var(--g-card-alt)" : "var(--g-card)",
      border: `1px solid ${isDetail ? "var(--g-rule-soft)" : "var(--g-rule)"}`,
      borderRadius: "var(--g-r-2)",
    }}>
      <span className="mono" style={{
        fontSize: 10, fontWeight: 700,
        color: isDetail ? "var(--g-ink-3)" : "var(--g-accent-deep)",
        background: isDetail ? "rgba(0,0,0,0.04)" : "var(--g-accent-tint)",
        padding: "2px 6px", borderRadius: 3, textAlign: "center", minWidth: 22,
      }}>{String(position).padStart(2,"0")}</span>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {metric.label}
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>
          {fmt.label} · {tag || "Priorität"}
        </div>
      </div>
      <button onClick={onUp} disabled={!onUp} style={mArrowBtn(!onUp)}>▲</button>
      <button onClick={onDown} disabled={!onDown} style={mArrowBtn(!onDown)}>▼</button>
    </div>
  );
}

const mArrowBtn = (disabled) => ({
  width: 36, height: 36, padding: 0, cursor: disabled ? "not-allowed" : "pointer",
  background: "transparent", border: "1px solid var(--g-rule)", borderRadius: 4,
  color: disabled ? "var(--g-ink-4)" : "var(--g-ink-2)",
  fontSize: 10, lineHeight: 1, opacity: disabled ? 0.4 : 1,
  display: "inline-flex", alignItems: "center", justifyContent: "center",
});

function MChannelPreview({ channel, order, metrics }) {
  const enabled = order.map(id => ({ id, ...WIZ_METRICS_M_FULL.find(m => m.id === id), state: metrics[id] })).filter(m => m.state.enabled);

  if (channel.id === "sms") {
    const text = enabled.slice(0, 6).map(m => `${m.label.slice(0,4)} ${SAMPLE_VALUES_M[m.id]||"—"}`).join(" ");
    const truncated = text.slice(0, 140);
    return (
      <div style={mPreviewFrame}>
        <div style={mPreviewHead}>SMS · Vorschau</div>
        <div style={{ padding: 12, background: "#e7e2d3" }}>
          <div style={{
            background: "#fff", padding: 10, borderRadius: 6,
            fontFamily: "var(--g-font-mono)", fontSize: 10.5, lineHeight: 1.5, color: "var(--g-ink)",
          }}>{truncated}</div>
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-3)", marginTop: 6 }}>
            {truncated.length}/140 Zeichen
          </div>
        </div>
      </div>
    );
  }

  const cols = channel.maxCols === Infinity ? enabled.slice(0, 5) : enabled.slice(0, channel.maxCols);

  return (
    <div style={mPreviewFrame}>
      <div style={mPreviewHead}>{channel.label} · Vorschau</div>
      <div style={{ padding: 12, background: channel.id === "signal" ? "#f3eee2" : channel.id === "telegram" ? "#e7e2d3" : "#faf8f1" }}>
        <div style={{
          background: "#fff", padding: 10, borderRadius: 6,
          fontFamily: "var(--g-font-mono)", fontSize: 10, lineHeight: 1.55,
        }}>
          <div style={{ fontWeight: 700, color: "var(--g-ink)", marginBottom: 6 }}>KHW · Etappe 02</div>
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
                {SAMPLE_VALUES_M[m.id] || "—"}
              </div>
            ))}
          </div>
          {channel.maxCols !== Infinity && enabled.length > channel.maxCols && (
            <div style={{ marginTop: 8, paddingTop: 6, borderTop: "1px dashed var(--g-rule)", color: "var(--g-ink-3)" }}>
              <span style={{ color: "var(--g-ink-4)" }}>+{enabled.length - channel.maxCols} in Detail-Zeile</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

const mPreviewFrame = {
  border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
  overflow: "hidden", background: "var(--g-card)",
};

const mPreviewHead = {
  padding: "8px 12px", borderBottom: "1px solid var(--g-rule-soft)",
  fontSize: 10, fontFamily: "var(--g-font-mono)", color: "var(--g-ink-3)",
  letterSpacing: "0.06em", textTransform: "uppercase", fontWeight: 600,
  background: "var(--g-card-alt)",
};

/* ─────────────────── Schritt 5 · Reports (1-spaltig) ─────────────────── */
function MStepReports() {
  const [evening, setEvening] = React.useState(true);
  const [morning, setMorning] = React.useState(true);
  const [trend, setTrend] = React.useState(true);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <MReportCard
        eyebrow="Abend-Briefing"
        title="Vor dem Schlafen"
        sub="Plan & Vorhersage für morgen."
        active={evening}
        onToggle={() => setEvening(!evening)}
        time="18:00"
        activeChannels={["email", "signal"]}
        trendToggle={{ checked: trend, onChange: () => setTrend(!trend) }}
      />
      <MReportCard
        eyebrow="Morgen-Update"
        title="Vor Etappenstart"
        sub="Aktuelle Bedingungen für heute."
        active={morning}
        onToggle={() => setMorning(!morning)}
        time="06:00"
        activeChannels={["email"]}
      />
      <MReportCard
        eyebrow="Warnungen"
        title="Sofort, wenn nötig"
        sub="Alert, sobald eine Alarmregel überschritten wird."
        activeChannels={["signal", "sms"]}
        showTime={false}
        rulesLink
      />
    </div>
  );
}

function MReportCard({ eyebrow, title, sub, active, onToggle, time, activeChannels = [], trendToggle, rulesLink, showTime = true }) {
  return (
    <div style={{
      padding: 16, background: "var(--g-card)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
    }}>
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 10, marginBottom: 6 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <Eyebrow>{eyebrow}</Eyebrow>
          <div style={{ fontSize: 15, fontWeight: 600, marginTop: 3, letterSpacing: "-0.01em", lineHeight: 1.25 }}>
            {title}
          </div>
        </div>
        {showTime && <Switch checked={active} onChange={onToggle} tone="accent" size="lg"/>}
      </div>

      {sub && (
        <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", lineHeight: 1.5, marginTop: 8, marginBottom: 12 }}>
          {sub}
        </div>
      )}

      {showTime && (
        <div style={{ marginBottom: 12 }}>
          <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
            <div style={{ flex: 1 }}>
              <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.06em", textTransform: "uppercase" }}>
                Uhrzeit
              </div>
              <div className="mono" style={{
                fontSize: 24, fontWeight: 600, letterSpacing: "0.01em",
                color: active ? "var(--g-ink)" : "var(--g-ink-4)", marginTop: 2,
              }}>
                {time}<span style={{ fontSize: 11, color: "var(--g-ink-4)", marginLeft: 6, fontWeight: 400 }}>24h</span>
              </div>
            </div>
            <button style={{
              padding: "8px 14px", minHeight: 36,
              background: "transparent", border: "1px solid var(--g-rule)",
              borderRadius: "var(--g-r-2)", cursor: "pointer",
              fontSize: 12, fontWeight: 500, color: "var(--g-ink-2)",
            }}>Ändern</button>
          </div>
        </div>
      )}

      {trendToggle && (
        <div style={{
          padding: "12px 12px", marginBottom: 12,
          background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)",
          borderRadius: "var(--g-r-2)",
          display: "flex", alignItems: "center", gap: 10,
        }}>
          <Switch checked={trendToggle.checked} onChange={trendToggle.onChange} tone="accent" size="md"/>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 13, fontWeight: 500, color: "var(--g-ink)" }}>
              3–7-Tage-Ausblick enthalten
            </div>
            <div style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 1 }}>
              Mehrtages-Trend mitschicken
            </div>
          </div>
        </div>
      )}

      <div className="mono" style={{
        fontSize: 9.5, color: "var(--g-ink-4)", letterSpacing: "0.06em",
        textTransform: "uppercase", marginBottom: 6,
      }}>Versand-Kanäle</div>
      <MChannelChipRow active={activeChannels}/>

      <button className="mono" style={{ ...mLinkBtn, marginTop: 12, padding: "8px 0", minHeight: 32 }}>
        {rulesLink ? "Alarmregeln verwalten →" : "Inhalt im Output-Editor anpassen →"}
      </button>
    </div>
  );
}

function MChannelChipRow({ active = [] }) {
  const channels = [
    { id: "email",    label: "✉ Email" },
    { id: "signal",   label: "▲ Signal" },
    { id: "telegram", label: "→ Telegram" },
    { id: "sms",      label: "* SMS" },
  ];
  return (
    <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
      {channels.map(c => {
        const on = active.includes(c.id);
        return (
          <span key={c.id} className="mono" style={{
            padding: "5px 10px", borderRadius: 999,
            fontSize: 10, fontWeight: 600, letterSpacing: "0.04em",
            border: on ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
            background: on ? "var(--g-accent-tint)" : "transparent",
            color: on ? "var(--g-accent-deep)" : "var(--g-ink-4)",
            minHeight: 26, display: "inline-flex", alignItems: "center",
          }}>{c.label}</span>
        );
      })}
    </div>
  );
}

window.ScreenTripWizardMobile = ScreenTripWizardMobile;
