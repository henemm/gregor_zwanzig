/* SCREEN · Wetter-Metriken & Spalten-Layout (Desktop)
 * ──────────────────────────────────────────────────────────────────────────
 *
 * Das ist der zentrale Ort, an dem der User pro Tour entscheidet:
 *   (a) WELCHE Metriken überhaupt im Briefing erscheinen (on/off)
 *   (b) WO sie erscheinen — als eigene Spalte oder als Detail-Wert
 *       in einer kompakten Zeile darunter
 *   (c) IN WELCHER REIHENFOLGE die Spalten stehen
 *   (d) Roh-Wert oder Skala/Kategorie
 *
 * Pro Kanal (Email/Telegram/Signal/SMS) wendet der Renderer dann automatisch
 * die jeweiligen Constraints an (max Spalten, max Bytes). Was nicht in die
 * Spalten passt, wandert in die Detail-Zeile. Was auch da nicht passt,
 * fällt für diesen Kanal weg.
 *
 *   Email     · keine Beschränkung — zeigt alles als Spalten
 *   Telegram  · max 8 Spalten
 *   Signal    · max 6 Spalten
 *   SMS       · keine Tabelle, alles in einer Textzeile bis 140 Zeichen
 *
 * Vollständige Backend-Spec (Datenmodell, Renderer-Algorithmus, Endpoints):
 *   claude-code-handoff/issue-bodies/body-14-output-layout-system.md
 *
 * UI-Sprache (kein Fach-Slang — was der User liest)
 *   "Spalte"      — eigene Tabellen-Spalte
 *   "Detail"      — Zusatz-Wert in einer Zeile unter der Tabelle
 *   "Aus"         — diese Metrik nicht ausgeben
 *   "Reihenfolge" — von links nach rechts in der Tabelle
 *   "Roh / Skala" — Zahl ("11,6 °C") oder Kategorie ("mild")
 */

const ALL_METRICS = [
  // Temperatur
  { id: "temp",       group: "Temperatur",   label: "Temperatur",          unit: "°C",   short: "Temp",      prio: 95 },
  { id: "feels",      group: "Temperatur",   label: "Gefühlte Temp",       unit: "°C",   short: "Feels",     prio: 70 },
  { id: "humidity",   group: "Temperatur",   label: "Luftfeuchtigkeit",    unit: "%",    short: "Luftf",     prio: 25 },
  { id: "dewpoint",   group: "Temperatur",   label: "Taupunkt",            unit: "°C",   short: "Taup",      prio: 20 },
  { id: "soilTemp",   group: "Temperatur",   label: "Bodentemperatur",     unit: "°C",   short: "Boden T",   prio: 10 },

  // Wind
  { id: "wind",       group: "Wind",         label: "Wind",                unit: "km/h", short: "Wind",      prio: 90 },
  { id: "gust",       group: "Wind",         label: "Böen",                unit: "km/h", short: "Böen",      prio: 88 },
  { id: "windDir",    group: "Wind",         label: "Windrichtung",        unit: "°",    short: "Windri",    prio: 40 },

  // Niederschlag
  { id: "precip",     group: "Niederschlag", label: "Niederschlag",        unit: "mm",   short: "Niedersch", prio: 78 },
  { id: "rainProb",   group: "Niederschlag", label: "Regen-Wahrsch.",      unit: "%",    short: "Regen%",    prio: 85 },
  { id: "thunder",    group: "Niederschlag", label: "Gewitter-Wahrsch.",   unit: "%",    short: "Gewitter",  prio: 60 },
  { id: "cape",       group: "Niederschlag", label: "CAPE (Energie)",      unit: "J/kg", short: "CAPE",      prio: 15 },
  { id: "snowfall",   group: "Niederschlag", label: "Schneefall",          unit: "cm",   short: "Schnee",    prio: 55 },
  { id: "precipType", group: "Niederschlag", label: "Niederschl.-Art",     unit: "",     short: "Nieder.art", prio: 35 },

  // Wolken & Sicht
  { id: "cloud",      group: "Wolken",       label: "Bewölkung gesamt",    unit: "%",    short: "Bewölk",    prio: 65 },
  { id: "cloudLow",   group: "Wolken",       label: "Tiefe Wolken",        unit: "%",    short: "tiefe W",   prio: 30 },
  { id: "cloudMid",   group: "Wolken",       label: "Mittlere Wolken",     unit: "%",    short: "mittl W",   prio: 12 },
  { id: "cloudHigh",  group: "Wolken",       label: "Hohe Wolken",         unit: "%",    short: "hohe W",    prio: 10 },
  { id: "visibility", group: "Wolken",       label: "Sichtweite",          unit: "km",   short: "Sicht",     prio: 55 },
  { id: "sunshine",   group: "Wolken",       label: "Sonnenschein-Dauer",  unit: "min",  short: "Sonne",     prio: 25 },

  // Sonstiges
  { id: "uv",         group: "Sonstiges",    label: "UV-Index",            unit: "",     short: "UV",        prio: 45 },
  { id: "pressure",   group: "Sonstiges",    label: "Luftdruck",           unit: "hPa",  short: "Druck",     prio: 18 },
  { id: "freezeLine", group: "Sonstiges",    label: "Nullgrad-Grenze",     unit: "m",    short: "0°-Linie",  prio: 50 },
  { id: "snowDepth",  group: "Sonstiges",    label: "Schneehöhe",          unit: "cm",   short: "Schnee H",  prio: 35 },
  { id: "newSnow",    group: "Sonstiges",    label: "Neuschnee 24h",       unit: "cm",   short: "Neuschnee", prio: 30 },
  { id: "radiation",  group: "Sonstiges",    label: "Globalstrahlung",     unit: "W/m²", short: "Strahlung", prio: 22 },
];

const METRIC_BY_ID = ALL_METRICS.reduce((m, x) => { m[x.id] = x; return m; }, {});

const PRESETS = [
  { id: "alpine",  name: "Alpen-Trekking",  builtin: true,  desc: "Standard für Hütten- und Höhenwanderer",
    metrics: ["temp","feels","wind","gust","windDir","precip","rainProb","thunder","cloud","visibility","uv","freezeLine","snowfall","snowDepth"] },
  { id: "hiking",  name: "Wandern",         builtin: true,  desc: "Einfach, fokus auf Tagesentscheidung",
    metrics: ["temp","feels","wind","gust","precip","rainProb","thunder","cloud","uv"] },
  { id: "skitour", name: "Skitouren",       builtin: true,  desc: "Lawinen-Indikatoren betont",
    metrics: ["temp","feels","wind","gust","windDir","newSnow","snowDepth","visibility","cloud","precip","precipType","freezeLine"] },
  { id: "winter",  name: "Wintersport",     builtin: true,  desc: "Pisten- und Loipen-Bedingungen",
    metrics: ["temp","feels","wind","newSnow","snowDepth","visibility","cloud","sunshine","uv","precipType"] },
  { id: "bike",    name: "Radtour",         builtin: true,  desc: "Wind und Niederschlag im Vordergrund",
    metrics: ["temp","feels","wind","gust","windDir","precip","rainProb","thunder","cloud","uv","visibility"] },
  { id: "water",   name: "Wassersport",     builtin: true,  desc: "Wind und Welle",
    metrics: ["temp","wind","gust","windDir","precip","rainProb","thunder","cloud","uv","pressure"] },
  { id: "general", name: "Allgemein",       builtin: true,  desc: "Minimal, für jeden Trip",
    metrics: ["temp","wind","gust","precip","rainProb","cloud","uv"] },
  { id: "khw403",  name: "★ KHW 403 (eigen)", builtin: false, desc: "Mein Karnischer-Höhenweg-Preset",
    metrics: ["temp","feels","wind","gust","windDir","precip","rainProb","thunder","cloud","cloudLow","visibility","uv","freezeLine","snowfall"] },
];

/* Roh→Skala-Mapping. Pro Metrik kann der User wählen, ob im Output der
 * präzise Wert oder eine sprechende Kategorie steht. */
const INDICATOR_MAP = {
  wind:       (v) => v >= 60 ? "sturm" : v >= 35 ? "stark" : v >= 15 ? "mäßig" : "ruhig",
  gust:       (v) => v >= 70 ? "sturm" : v >= 50 ? "stark" : v >= 30 ? "mäßig" : "ruhig",
  cape:       (v) => v >= 2500 ? "extrem" : v >= 1500 ? "hoch" : v >= 500 ? "mittel" : "niedrig",
  thunder:    (v) => v >= 70 ? "sehr hoch" : v >= 40 ? "hoch" : v >= 15 ? "mittel" : "gering",
  rainProb:   (v) => v >= 70 ? "sehr wahrsch." : v >= 40 ? "wahrsch." : v >= 15 ? "möglich" : "unwahrsch.",
  visibility: (v) => v >= 20 ? "gut" : v >= 10 ? "mäßig" : v >= 5 ? "reduziert" : "schlecht",
  cloud:      (v) => v >= 80 ? "bedeckt" : v >= 50 ? "bewölkt" : v >= 20 ? "heiter" : "klar",
  uv:         (v) => v >= 8 ? "sehr hoch" : v >= 6 ? "hoch" : v >= 3 ? "mittel" : "niedrig",
  precip:     (v) => v >= 5 ? "stark" : v >= 1 ? "mäßig" : v > 0 ? "leicht" : "trocken",
  humidity:   (v) => v >= 90 ? "feucht" : v >= 70 ? "hoch" : v >= 40 ? "mittel" : "trocken",
  feels:      (v) => v >= 25 ? "warm" : v >= 10 ? "mild" : v >= 0 ? "kühl" : v >= -10 ? "kalt" : "sehr kalt",
};
const HAS_INDICATOR = (id) => !!INDICATOR_MAP[id];

/* Kanal-Constraints — identisch im Backend-Renderer. */
const CHANNEL_LIMITS = [
  { id: "email",    label: "Email",    maxCols: 99,  hint: "alle Werte als Spalten" },
  { id: "telegram", label: "Telegram", maxCols: 8,   hint: "max 8 Spalten" },
  { id: "signal",   label: "Signal",   maxCols: 6,   hint: "max 6 Spalten" },
  { id: "sms",      label: "SMS",      maxCols: 0,   hint: "keine Tabelle, max 140 Zeichen" },
];

/* Wendet die Kanal-Constraints auf eine User-Konfiguration an. Dieselbe
 * Funktion läuft im Backend-Renderer. */
function applyChannel(primary, secondary, maxCols) {
  const inTable = primary.slice(0, maxCols);
  const overflow = primary.slice(maxCols);
  const detail = [...overflow, ...secondary];
  return { inTable, detail, demoted: overflow.length };
}

/* Default-Auto-Verteilung wenn neuer Trip / Preset-Wechsel.
 * "hour" ist immer primary[0] (fix). Danach nach prio absteigend bis 6
 * (Signal-Grenze als Daumenregel) — Rest in secondary. */
function autoAssign(activeSet) {
  const list = Array.from(activeSet)
    .map(id => METRIC_BY_ID[id])
    .filter(Boolean)
    .sort((a, b) => b.prio - a.prio);
  return {
    primary: list.slice(0, 6).map(m => m.id),
    secondary: list.slice(6).map(m => m.id),
    off: ALL_METRICS.filter(m => !activeSet.has(m.id)).map(m => m.id),
  };
}

function ScreenMetricsEditor() {
  const [presetId, setPresetId] = React.useState("khw403");
  const preset = PRESETS.find(p => p.id === presetId);
  const [buckets, setBuckets] = React.useState(() => autoAssign(new Set(preset.metrics)));
  const [mode, setMode] = React.useState({ wind: "indicator", gust: "indicator", rainProb: "indicator", cloud: "indicator", visibility: "indicator", thunder: "indicator" });
  const [dirty, setDirty] = React.useState(false);
  const [saveOpen, setSaveOpen] = React.useState(false);
  const [aboutOpen, setAboutOpen] = React.useState(false);

  React.useEffect(() => {
    setBuckets(autoAssign(new Set(preset.metrics)));
    setDirty(false);
  }, [presetId]);

  const move = (id, fromBucket, toBucket) => {
    setBuckets(b => {
      const next = {
        primary: [...b.primary], secondary: [...b.secondary], off: [...b.off],
      };
      next[fromBucket] = next[fromBucket].filter(x => x !== id);
      next[toBucket] = [...next[toBucket], id];
      return next;
    });
    setDirty(true);
  };

  const reorder = (bucket, id, direction) => {
    setBuckets(b => {
      const list = [...b[bucket]];
      const idx = list.indexOf(id);
      const next = idx + direction;
      if (next < 0 || next >= list.length) return b;
      [list[idx], list[next]] = [list[next], list[idx]];
      return { ...b, [bucket]: list };
    });
    setDirty(true);
  };

  const setModeFor = (id, m) => { setMode(x => ({ ...x, [id]: m })); setDirty(true); };

  const activeCount = buckets.primary.length + buckets.secondary.length;

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="trips"/>
      <main style={{ flex: 1, position: "relative" }}>
        <TopoBg opacity={0.12}/>
        {saveOpen && <SavePresetDialog activeCount={activeCount} mode={mode} buckets={buckets} onClose={() => setSaveOpen(false)}/>}
        {aboutOpen && <AboutOutputLayout onClose={() => setAboutOpen(false)}/>}

        <div style={{ position: "relative", padding: "16px 40px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
            <span style={{ opacity: 0.6 }}>Trips</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ opacity: 0.6 }}>KHW 403</span>
            <span style={{ margin: "0 8px" }}>/</span>
            <span style={{ color: "var(--g-ink)" }}>Wetter-Metriken</span>
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            {dirty && <Pill tone="warn">Ungespeicherte Änderungen</Pill>}
            <Btn variant="ghost" size="sm">Verwerfen</Btn>
            <Btn variant="primary" size="sm">Speichern</Btn>
          </div>
        </div>

        <div style={{ position: "relative", padding: "32px 40px 60px", maxWidth: 1480 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 24, marginBottom: 24 }}>
            <div style={{ maxWidth: 760 }}>
              <Eyebrow>Wetter-Metriken</Eyebrow>
              <h1 style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.02em", margin: "6px 0 8px" }}>
                Welche Werte gehen in das Briefing — und wie?
              </h1>
              <div style={{ fontSize: 14, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
                Jede Metrik landet entweder als <strong>eigene Spalte</strong> in der Tabelle oder als <strong>Detail-Wert</strong> in einer kompakten Zeile darunter.
                Email zeigt beides vollständig; Signal/Telegram haben Spalten-Limits — was nicht passt, wandert automatisch in die Detail-Zeile.
                <button onClick={() => setAboutOpen(true)} style={{ marginLeft: 6, color: "var(--g-accent)", background: "none", border: "none", cursor: "pointer", padding: 0, fontSize: 14, textDecoration: "underline", textUnderlineOffset: 2 }}>
                  Wie funktioniert das genau?
                </button>
              </div>
            </div>
          </div>

          <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: 32 }}>

            {/* ── Preset-Spalte ── */}
            <div>
              <SectionH eyebrow="Preset-Auswahl" title="Profile"/>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {PRESETS.map(p => (
                  <PresetRow key={p.id} preset={p} active={p.id === presetId} onClick={() => setPresetId(p.id)}/>
                ))}
              </div>
              <div style={{ marginTop: 24, padding: 16, background: "var(--g-card-alt)", borderRadius: 4, border: "1px dashed var(--g-rule)" }}>
                <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 6 }}>
                  Eigenes Preset
                </div>
                <div style={{ fontSize: 13, color: "var(--g-ink-2)", marginBottom: 10, lineHeight: 1.4 }}>
                  Aktuelle Auswahl ({activeCount} Metriken) speichern und auf andere Trips anwenden.
                </div>
                <Btn variant="ghost" size="sm" style={{ width: "100%" }} onClick={() => setSaveOpen(true)}>
                  + Als Preset speichern
                </Btn>
              </div>
            </div>

            {/* ── Editor + Vorschau ── */}
            <div style={{ display: "flex", flexDirection: "column", gap: 24 }}>

              <BucketSection
                eyebrow="Im Briefing als Spalte"
                title="Spalten"
                hint="Eine eigene Tabellen-Spalte je Metrik. Reihenfolge = von links nach rechts. Email zeigt alle; Signal max 6, Telegram max 8."
                bucket="primary"
                items={buckets.primary}
                mode={mode}
                onMode={setModeFor}
                onReorder={(id, dir) => reorder("primary", id, dir)}
                onMove={(id, target) => move(id, "primary", target)}
                showLimitMarkers
              />

              <BucketSection
                eyebrow="Im Briefing als Detail"
                title="Detail-Werte"
                hint="Erscheinen als kompakte Zeile direkt unter der Tabelle: Bewölkung 80 % · Sicht 5 km · …"
                bucket="secondary"
                items={buckets.secondary}
                mode={mode}
                onMode={setModeFor}
                onReorder={(id, dir) => reorder("secondary", id, dir)}
                onMove={(id, target) => move(id, "secondary", target)}
              />

              <ChannelPreviewBlock primary={buckets.primary} secondary={buckets.secondary}/>

              <BucketSectionOff
                items={buckets.off}
                onAdd={(id, target) => move(id, "off", target)}
              />
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}

/* ───────────────────── Preset Row (unverändert) ───────────────────── */

function PresetRow({ preset, active, onClick }) {
  return (
    <div onClick={onClick} style={{
      padding: "10px 14px", cursor: "pointer", borderRadius: 4,
      background: active ? "rgba(196, 90, 42, 0.08)" : "transparent",
      borderLeft: active ? "3px solid var(--g-accent)" : "3px solid transparent",
      transition: "all 120ms",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8 }}>
        <div style={{ fontSize: 13, fontWeight: active ? 600 : 500, color: active ? "var(--g-accent-deep)" : "var(--g-ink)" }}>
          {preset.name}
          {!preset.builtin && <span className="mono" style={{ marginLeft: 6, fontSize: 9, color: "var(--g-accent)", letterSpacing: "0.08em" }}>EIGEN</span>}
        </div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", fontWeight: 600 }}>{preset.metrics.length}</div>
      </div>
      <div style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>{preset.desc}</div>
    </div>
  );
}

/* ─────────── Bucket-Sektion: "Spalten" oder "Detail-Werte" ─────────── */

function BucketSection({ eyebrow, title, hint, bucket, items, mode, onMode, onReorder, onMove, showLimitMarkers }) {
  return (
    <Card padding={0}>
      <div style={{ padding: "16px 20px 14px", borderBottom: "1px solid var(--g-rule-soft)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
          <div>
            <Eyebrow>{eyebrow}</Eyebrow>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, letterSpacing: "-0.01em" }}>
              {title} <span style={{ color: "var(--g-ink-4)", fontWeight: 400, fontSize: 14 }}>· {items.length}</span>
            </div>
          </div>
          {showLimitMarkers && <ChannelLimitMarkers count={items.length}/>}
        </div>
        <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 8, lineHeight: 1.5, maxWidth: 760 }}>
          {hint}
        </div>
      </div>

      {items.length === 0 ? (
        <div style={{ padding: "20px 20px", fontSize: 13, color: "var(--g-ink-4)", fontStyle: "italic", textAlign: "center" }}>
          Keine Einträge — Metriken aus „Nicht im Briefing" hinzufügen.
        </div>
      ) : (
        <div>
          {items.map((id, i) => {
            const m = METRIC_BY_ID[id];
            return (
              <ActiveMetricRow
                key={id} metric={m} bucket={bucket} index={i}
                isFirst={i === 0} isLast={i === items.length - 1}
                isOverLimit={bucket === "primary" && i >= 6}
                isSignalLimit={bucket === "primary" && i === 5}
                mode={mode[id] || "raw"}
                onMode={(v) => onMode(id, v)}
                onReorder={(dir) => onReorder(id, dir)}
                onMove={(target) => onMove(id, target)}
              />
            );
          })}
        </div>
      )}
    </Card>
  );
}

function ActiveMetricRow({ metric, bucket, index, isFirst, isLast, isOverLimit, isSignalLimit, mode, onMode, onReorder, onMove }) {
  const hasIndicator = HAS_INDICATOR(metric.id);
  const showIndex = bucket === "primary";
  const isHour = metric.id === "hour";

  return (
    <React.Fragment>
      {isSignalLimit && (
        <div style={{
          padding: "4px 20px", fontSize: 10.5, fontFamily: "var(--g-font-mono)",
          letterSpacing: "0.1em", textTransform: "uppercase",
          color: "var(--g-warn)", background: "rgba(192,138,26,0.06)",
          borderTop: "1px dashed var(--g-warn)", borderBottom: "1px dashed var(--g-warn)",
        }}>
          ↓ ab hier bei <strong>Signal</strong> automatisch als Detail-Zeile (max 6 Spalten)
        </div>
      )}
      <div style={{
        display: "grid",
        gridTemplateColumns: showIndex ? "30px 1fr 280px 140px 110px" : "1fr 280px 140px 110px",
        gap: 12,
        padding: "12px 20px",
        borderBottom: "1px solid var(--g-rule-soft)",
        alignItems: "center",
        background: isOverLimit ? "rgba(192,138,26,0.04)" : "transparent",
      }}>
        {showIndex && (
          <div className="mono" style={{
            fontSize: 11, fontWeight: 600,
            color: isOverLimit ? "var(--g-warn)" : "var(--g-ink-3)",
            textAlign: "right",
          }}>
            {index + 1}
          </div>
        )}

        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 14, fontWeight: 500, color: "var(--g-ink)" }}>{metric.label}</div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 2 }}>
            {metric.unit || "—"} · Kürzel <span style={{ color: "var(--g-ink-3)" }}>{metric.short}</span>
          </div>
        </div>

        <div>
          {hasIndicator ? (
            <ModeToggle mode={mode} onMode={onMode}/>
          ) : (
            <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", letterSpacing: "0.06em", textTransform: "uppercase" }}>nur Rohwert</span>
          )}
        </div>

        <div style={{ display: "flex", gap: 4 }}>
          {bucket === "primary" && (
            <React.Fragment>
              <TextBtn onClick={() => onMove("secondary")} disabled={isHour}>→ Detail</TextBtn>
              <TextBtn onClick={() => onMove("off")} disabled={isHour}>✕</TextBtn>
            </React.Fragment>
          )}
          {bucket === "secondary" && (
            <React.Fragment>
              <TextBtn onClick={() => onMove("primary")}>↑ Spalte</TextBtn>
              <TextBtn onClick={() => onMove("off")}>✕</TextBtn>
            </React.Fragment>
          )}
        </div>

        <div style={{ display: "flex", gap: 2, justifyContent: "flex-end" }}>
          <IconArrow direction="up"   disabled={isFirst || isHour} onClick={() => onReorder(-1)}/>
          <IconArrow direction="down" disabled={isLast  || isHour} onClick={() => onReorder(+1)}/>
        </div>
      </div>
    </React.Fragment>
  );
}

function ModeToggle({ mode, onMode }) {
  return (
    <div style={{ display: "inline-flex", padding: 2, background: "var(--g-card-alt)", borderRadius: 3, border: "1px solid var(--g-rule-soft)" }}>
      <button onClick={() => onMode("raw")} style={modeBtnStyle(mode === "raw")}>Roh</button>
      <button onClick={() => onMode("indicator")} style={modeBtnStyle(mode === "indicator")}>Skala</button>
    </div>
  );
}
function modeBtnStyle(active) {
  return {
    padding: "4px 12px", fontSize: 11, fontWeight: 600,
    border: "none", cursor: "pointer", borderRadius: 2,
    background: active ? "var(--g-paper)" : "transparent",
    color: active ? "var(--g-accent-deep)" : "var(--g-ink-3)",
    boxShadow: active ? "0 0 0 1px var(--g-rule)" : "none",
    fontFamily: "var(--g-font-mono)", letterSpacing: "0.04em",
  };
}

function TextBtn({ children, onClick, disabled }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      padding: "5px 9px", fontSize: 11.5, fontWeight: 500,
      border: "1px solid var(--g-rule)", borderRadius: 3,
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1,
      whiteSpace: "nowrap", fontFamily: "var(--g-font-sans)",
    }}>{children}</button>
  );
}

function IconArrow({ direction, disabled, onClick }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      width: 26, height: 26, border: "1px solid var(--g-rule)", borderRadius: 3,
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      padding: 0,
    }}>
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
        {direction === "up"
          ? <path d="M6 2.5L10 8H2L6 2.5Z" fill="currentColor"/>
          : <path d="M6 9.5L2 4H10L6 9.5Z" fill="currentColor"/>}
      </svg>
    </button>
  );
}

function ChannelLimitMarkers({ count }) {
  return (
    <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
      {CHANNEL_LIMITS.filter(c => c.maxCols > 0 && c.maxCols < 99).map(c => {
        const exceeded = count > c.maxCols;
        return (
          <span key={c.id} title={c.hint} style={{
            padding: "3px 8px", fontSize: 10.5, fontFamily: "var(--g-font-mono)",
            letterSpacing: "0.04em", borderRadius: 999,
            background: exceeded ? "rgba(192,138,26,0.15)" : "rgba(26,26,24,0.05)",
            color: exceeded ? "var(--g-warn)" : "var(--g-ink-3)",
            fontWeight: 600, border: exceeded ? "1px solid var(--g-warn)" : "1px solid transparent",
          }}>
            {c.label} {count}/{c.maxCols}
          </span>
        );
      })}
    </div>
  );
}

/* ───────────────── Bucket-Sektion: "Nicht im Briefing" ───────────────── */

function BucketSectionOff({ items, onAdd }) {
  const [open, setOpen] = React.useState(false);
  const grouped = ALL_METRICS.filter(m => items.includes(m.id))
    .reduce((acc, m) => { (acc[m.group] = acc[m.group] || []).push(m); return acc; }, {});

  return (
    <Card padding={0}>
      <button onClick={() => setOpen(!open)} style={{
        width: "100%", padding: "14px 20px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        background: "transparent", border: "none", cursor: "pointer", textAlign: "left",
      }}>
        <div>
          <Eyebrow>Nicht im Briefing</Eyebrow>
          <div style={{ fontSize: 16, fontWeight: 600, marginTop: 2 }}>
            {items.length} weitere Metriken <span style={{ color: "var(--g-ink-4)", fontSize: 13, fontWeight: 400 }}>· nicht ausgegeben</span>
          </div>
        </div>
        <span style={{ fontSize: 14, color: "var(--g-ink-3)" }}>{open ? "▴ Einklappen" : "▾ Aufklappen"}</span>
      </button>

      {open && (
        <div style={{ padding: "0 20px 20px", borderTop: "1px solid var(--g-rule-soft)" }}>
          {Object.entries(grouped).map(([group, metrics]) => (
            <div key={group} style={{ marginTop: 16 }}>
              <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 8, fontWeight: 600 }}>
                {group}
              </div>
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 6 }}>
                {metrics.map(m => (
                  <div key={m.id} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "8px 10px", border: "1px solid var(--g-rule-soft)", borderRadius: 4,
                    background: "var(--g-card-alt)",
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12.5, fontWeight: 500, color: "var(--g-ink-2)" }}>{m.label}</div>
                      <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>{m.unit || "—"} · {m.short}</div>
                    </div>
                    <TextBtn onClick={() => onAdd(m.id, "primary")}>+ Spalte</TextBtn>
                    <TextBtn onClick={() => onAdd(m.id, "secondary")}>+ Detail</TextBtn>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

/* ───────────────── Multi-Channel-Vorschau ───────────────── */

function ChannelPreviewBlock({ primary, secondary }) {
  return (
    <Card padding={0}>
      <div style={{ padding: "16px 20px 12px", borderBottom: "1px solid var(--g-rule-soft)" }}>
        <Eyebrow>Vorschau · so kommt es beim Empfänger an</Eyebrow>
        <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2, letterSpacing: "-0.01em" }}>
          Pro Kanal
        </div>
        <div style={{ fontSize: 12.5, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 760, lineHeight: 1.5 }}>
          Identische Spalten-Konfiguration, vier Kanäle. Wenn die Spalten-Anzahl das Kanal-Limit übersteigt, wandern die hinteren automatisch in die Detail-Zeile.
        </div>
      </div>

      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 12,
        padding: 16, background: "var(--g-card-alt)",
      }}>
        {CHANNEL_LIMITS.map(c => (
          <ChannelPreviewCard key={c.id} channel={c} primary={primary} secondary={secondary}/>
        ))}
      </div>
    </Card>
  );
}

function ChannelPreviewCard({ channel, primary, secondary }) {
  const { inTable, detail, demoted } = applyChannel(primary, secondary, channel.maxCols);
  const isSMS = channel.id === "sms";

  return (
    <div style={{
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: 4, overflow: "hidden",
      display: "flex", flexDirection: "column",
    }}>
      <div style={{ padding: "10px 12px", borderBottom: "1px solid var(--g-rule-soft)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
          <div style={{ fontSize: 13, fontWeight: 600 }}>{channel.label}</div>
          <span className="mono" style={{
            padding: "2px 8px", fontSize: 10, borderRadius: 999,
            background: demoted > 0 ? "rgba(192,138,26,0.15)" : "rgba(26,26,24,0.05)",
            color: demoted > 0 ? "var(--g-warn)" : "var(--g-ink-3)",
            fontWeight: 600,
          }}>
            {isSMS ? "flach" : `${inTable.length}/${channel.maxCols < 99 ? channel.maxCols : "∞"} Spalten`}
          </span>
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 4, letterSpacing: "0.03em" }}>
          {channel.hint}
        </div>
      </div>

      <div style={{ padding: 12, flex: 1, fontSize: 11 }}>
        {!isSMS && inTable.length > 0 && (
          <div style={{
            background: "var(--g-paper-deep)", borderRadius: 3,
            padding: "6px 8px", fontFamily: "var(--g-font-mono)",
            fontSize: 10, lineHeight: 1.5, overflowX: "auto",
            whiteSpace: "pre",
            color: "var(--g-ink)",
          }}>
            {inTable.map(id => METRIC_BY_ID[id].short.slice(0, 5).padEnd(6, " ")).join("")}
            {"\n"}
            {inTable.map((_, i) => sampleRow(i).padEnd(6, " ")).join("")}
          </div>
        )}
        {detail.length > 0 && !isSMS && (
          <div style={{ marginTop: 8, fontSize: 11, color: "var(--g-ink-2)", lineHeight: 1.5, fontStyle: "italic" }}>
            <span className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.08em", textTransform: "uppercase", marginRight: 4 }}>
              Detail:
            </span>
            {detail.map(id => `${METRIC_BY_ID[id].label} ${sampleValue(id)}`).join(" · ")}
          </div>
        )}
        {isSMS && (
          <div style={{ fontSize: 11, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
            {[...primary, ...secondary].slice(0, 8).map(id => `${METRIC_BY_ID[id].short} ${sampleValue(id)}`).join(" · ")}
            {primary.length + secondary.length > 8 && <span style={{ color: "var(--g-ink-4)" }}> …</span>}
          </div>
        )}
        {demoted > 0 && (
          <div style={{
            marginTop: 10, padding: "5px 8px",
            background: "rgba(192,138,26,0.08)",
            borderLeft: "2px solid var(--g-warn)",
            fontSize: 10.5, color: "var(--g-warn)", fontWeight: 600,
          }}>
            ⚠ {demoted} {demoted === 1 ? "Spalte" : "Spalten"} verschoben in Detail
          </div>
        )}
      </div>
    </div>
  );
}

function sampleRow(i) {
  const samples = ["10", "11.6", "11", "30", "0", "80", "412", "hoch", "5"];
  return samples[i] || "—";
}
function sampleValue(id) {
  const map = {
    temp: "11.6 °C", feels: "8 °C", wind: "11", gust: "30", rainProb: "0 %",
    cloud: "80 %", visibility: "hoch", radiation: "412 W/m²", uv: "3",
    humidity: "78 %", windDir: "NE", precip: "0 mm", thunder: "0 %",
    freezeLine: "2400 m", pressure: "1018 hPa", dewpoint: "4 °C",
    snowfall: "0 cm", snowDepth: "0 cm", newSnow: "0 cm",
    soilTemp: "5 °C", sunshine: "35 min", cape: "0 J/kg",
    cloudLow: "30 %", cloudMid: "45 %", cloudHigh: "70 %", precipType: "—",
  };
  return map[id] || "—";
}

/* ───────────────── About-Dialog (Erklärung System) ───────────────── */

function AboutOutputLayout({ onClose }) {
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(26,26,24,0.45)", backdropFilter: "blur(2px)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 700, maxWidth: "90vw", maxHeight: "85vh", overflow: "auto",
        background: "var(--g-paper)", border: "1px solid var(--g-rule)", borderRadius: 6,
        boxShadow: "0 24px 80px rgba(26,26,24,0.25)",
      }}>
        <div style={{ padding: "20px 28px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
          <div>
            <Eyebrow>Output-Layout-System</Eyebrow>
            <div style={{ fontSize: 22, fontWeight: 600, marginTop: 2, letterSpacing: "-0.01em" }}>Wie kommt was wohin</div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 22, color: "var(--g-ink-3)", cursor: "pointer", lineHeight: 1 }}>×</button>
        </div>

        <div style={{ padding: "20px 28px 24px", fontSize: 14, lineHeight: 1.6, color: "var(--g-ink-2)" }}>
          <p>Du verwaltest die Metriken eines Trips an <strong>einer Stelle</strong>. Pro Metrik entscheidest du:</p>
          <ul style={{ paddingLeft: 18, margin: "12px 0" }}>
            <li><strong>Spalte</strong> — eigene Tabellen-Spalte im Briefing</li>
            <li><strong>Detail</strong> — als kompakter Zusatz-Wert in einer Zeile unter der Tabelle</li>
            <li><strong>Aus</strong> — wird für diesen Trip nicht ausgegeben</li>
          </ul>
          <p>Jeder Kanal hat seine eigenen Constraints. Der Renderer wendet sie automatisch an:</p>
          <table style={{ width: "100%", borderCollapse: "collapse", margin: "12px 0", fontSize: 13 }}>
            <thead>
              <tr style={{ background: "var(--g-card-alt)", borderBottom: "1px solid var(--g-rule)" }}>
                <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600 }}>Kanal</th>
                <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600 }}>Max Spalten</th>
                <th style={{ textAlign: "left", padding: "8px 10px", fontWeight: 600 }}>Verhalten</th>
              </tr>
            </thead>
            <tbody>
              <tr style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
                <td style={{ padding: "8px 10px", fontWeight: 600 }}>Email</td>
                <td className="mono" style={{ padding: "8px 10px" }}>∞</td>
                <td style={{ padding: "8px 10px" }}>Alles als Spalten + Detail-Zeile darunter</td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
                <td style={{ padding: "8px 10px", fontWeight: 600 }}>Telegram</td>
                <td className="mono" style={{ padding: "8px 10px" }}>8</td>
                <td style={{ padding: "8px 10px" }}>Erste 8 als Spalten, Rest wandert in Detail</td>
              </tr>
              <tr style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
                <td style={{ padding: "8px 10px", fontWeight: 600 }}>Signal</td>
                <td className="mono" style={{ padding: "8px 10px" }}>6</td>
                <td style={{ padding: "8px 10px" }}>Erste 6 als Spalten, Rest in Detail</td>
              </tr>
              <tr>
                <td style={{ padding: "8px 10px", fontWeight: 600 }}>SMS</td>
                <td className="mono" style={{ padding: "8px 10px" }}>0</td>
                <td style={{ padding: "8px 10px" }}>Keine Tabelle, alles in flacher Zeile bis 140 Zeichen</td>
              </tr>
            </tbody>
          </table>
          <p>Pro-Kanal-Overrides (z.B. „bei SMS nur die wichtigsten 3") sind in Version 2 möglich — Default ist eine Konfiguration für alle Kanäle, die der Renderer kanalspezifisch anpasst.</p>
          <div style={{ marginTop: 16, padding: 14, background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)", borderRadius: 4 }}>
            <div className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", color: "var(--g-accent)", fontWeight: 600, marginBottom: 4 }}>
              Backend-Spec
            </div>
            <div style={{ fontSize: 13 }}>
              Datenmodell, Renderer-Algorithmus und Endpoints sind als Story für Claude Code dokumentiert:
              {" "}<code style={{ fontFamily: "var(--g-font-mono)", fontSize: 12, background: "var(--g-paper-deep)", padding: "1px 6px", borderRadius: 2 }}>claude-code-handoff/issue-bodies/body-14-output-layout-system.md</code>
            </div>
          </div>
        </div>

        <div style={{ padding: "14px 28px", borderTop: "1px solid var(--g-rule-soft)", background: "var(--g-card-alt)", display: "flex", justifyContent: "flex-end" }}>
          <Btn variant="primary" size="sm" onClick={onClose}>Verstanden</Btn>
        </div>
      </div>
    </div>
  );
}

/* ───────────────── Save-Preset-Dialog (vereinfacht) ───────────────── */

function SavePresetDialog({ activeCount, mode, buckets, onClose }) {
  const indicatorCount = [...buckets.primary, ...buckets.secondary].filter(id => mode[id] === "indicator").length;
  return (
    <div onClick={onClose} style={{
      position: "fixed", inset: 0, background: "rgba(26,26,24,0.45)", backdropFilter: "blur(2px)",
      display: "flex", alignItems: "center", justifyContent: "center", zIndex: 100,
    }}>
      <div onClick={(e) => e.stopPropagation()} style={{
        width: 520, background: "var(--g-paper)", border: "1px solid var(--g-rule)", borderRadius: 6,
        boxShadow: "0 24px 80px rgba(26,26,24,0.25)", overflow: "hidden",
      }}>
        <div style={{ padding: "18px 24px", borderBottom: "1px solid var(--g-rule-soft)", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <Eyebrow>Eigenes Preset</Eyebrow>
            <div style={{ fontSize: 18, fontWeight: 600, marginTop: 2 }}>Auswahl als Preset speichern</div>
          </div>
          <button onClick={onClose} style={{ background: "none", border: "none", fontSize: 18, color: "var(--g-ink-3)", cursor: "pointer" }}>×</button>
        </div>

        <div style={{ padding: "18px 24px" }}>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>Name</div>
          <input autoFocus defaultValue="Mein Skitouren-Set"
            style={{ width: "100%", padding: "10px 12px", fontSize: 15, background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: 4 }}/>

          <div style={{ marginTop: 16, padding: "12px 14px", background: "var(--g-card-alt)", borderRadius: 4, border: "1px solid var(--g-rule-soft)" }}>
            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>Wird gespeichert</div>
            <div style={{ display: "flex", gap: 16, flexWrap: "wrap", fontSize: 12, color: "var(--g-ink-2)" }}>
              <span><strong style={{ color: "var(--g-ink)" }}>{buckets.primary.length}</strong> Spalten</span>
              <span>·</span>
              <span><strong style={{ color: "var(--g-ink)" }}>{buckets.secondary.length}</strong> Detail</span>
              <span>·</span>
              <span><strong style={{ color: "var(--g-accent-deep)" }}>{indicatorCount}</strong> als Skala</span>
            </div>
          </div>
        </div>

        <div style={{ padding: "14px 24px", borderTop: "1px solid var(--g-rule-soft)", background: "var(--g-card-alt)", display: "flex", justifyContent: "flex-end", gap: 8 }}>
          <Btn variant="ghost" size="sm" onClick={onClose}>Abbrechen</Btn>
          <Btn variant="primary" size="sm" onClick={onClose}>Preset speichern</Btn>
        </div>
      </div>
    </div>
  );
}

window.ScreenMetricsEditor = ScreenMetricsEditor;
