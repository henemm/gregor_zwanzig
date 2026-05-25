/* ════════════════════════════════════════════════════════════════════════
 *  ORGANISMS — Page-Sektionen, App-spezifische Komposition
 * ════════════════════════════════════════════════════════════════════════
 *
 *  Eine Organism ist eine Komposition aus 2+ Molecules (oder Atomen mit
 *  eigener Domain-Semantik). Sie ist groß genug, dass sie an einem Ort als
 *  ganze Sektion erscheint — nicht aber so groß, dass sie eine Page IST.
 *
 *  Lade-Reihenfolge:
 *      brand-kit.jsx → atoms.jsx → molecules.jsx → organisms.jsx → screen-*.jsx
 *
 *  Inhalt dieser Datei (Stand: Konsolidierung Wetter-Editor, Issue 345):
 *      WETTER_METRICS_CATALOG      — Daten-Konstante: alle verfügbaren Metriken
 *      WETTER_PRESETS              — Daten-Konstante: Wetter-Profile (Vorlagen)
 *      WETTER_CHANNELS             — Daten-Konstante: Kanal-Limits
 *      wetterAutoAssign            — Helper: Default-Verteilung Spalte/Detail
 *      wetterDefaultHorizons       — Helper: Default-Horizonte pro Metrik
 *      wetterDefaultScore          — Helper: Default Score-Beitrag pro Metrik
 *      sampleWetterValue           — Helper: Demo-Werte für die Vorschau
 *
 *      PresetRail                  — Preset-Liste mit „Eigenes Profil"-Block
 *      MetricBucket                — Eine Spalten-/Detail-Sektion mit Rows
 *      MetricOffShelf              — Aufklappbarer „Nicht im Briefing"-Block
 *      ChannelPreviewStrip         — 4-Karten-Vorschau pro Kanal
 *      MetricsEditorContextBar     — Header oben (Kontext, Counts)
 *      MetricsEditor               — DIE konsolidierte Editor-Organism
 *
 *  Diese Organismen ersetzen die historisch in screen-metrics-editor.jsx
 *  inline definierten Sub-Komponenten (PresetRow, ActiveMetricRow,
 *  BucketSection, BucketSectionOff, ChannelPreviewBlock). Der bestehende
 *  Screen bleibt vorerst unverändert; bei nächster Berührung wird er auf
 *  diese Organism-API umgestellt.
 */


/* ════════════════════ Daten-Konstanten ════════════════════ */

const WETTER_METRICS_CATALOG = [
  { id: "temp",       group: "Temperatur",   label: "Temperatur",       short: "Temp",      unit: "°C",   prio: 95, hasIndicator: false },
  { id: "feels",      group: "Temperatur",   label: "Gefühlte Temp",    short: "Feels",     unit: "°C",   prio: 70, hasIndicator: true  },
  { id: "humidity",   group: "Temperatur",   label: "Luftfeuchtigkeit", short: "Luftf",     unit: "%",    prio: 25, hasIndicator: true  },
  { id: "wind",       group: "Wind",         label: "Wind",             short: "Wind",      unit: "km/h", prio: 90, hasIndicator: true  },
  { id: "gust",       group: "Wind",         label: "Böen",             short: "Böen",      unit: "km/h", prio: 88, hasIndicator: true  },
  { id: "windDir",    group: "Wind",         label: "Windrichtung",     short: "Windri",    unit: "°",    prio: 40, hasIndicator: false },
  { id: "precip",     group: "Niederschlag", label: "Niederschlag",     short: "Niedersch", unit: "mm",   prio: 78, hasIndicator: true  },
  { id: "rainProb",   group: "Niederschlag", label: "Regen-Wahrsch.",   short: "Regen%",    unit: "%",    prio: 85, hasIndicator: true  },
  { id: "thunder",    group: "Niederschlag", label: "Gewitter (CAPE)",  short: "Gewitter",  unit: "%",    prio: 60, hasIndicator: true  },
  { id: "cloud",      group: "Wolken",       label: "Bewölkung",        short: "Bewölk",    unit: "%",    prio: 65, hasIndicator: true  },
  { id: "visibility", group: "Wolken",       label: "Sicht",            short: "Sicht",     unit: "km",   prio: 55, hasIndicator: true  },
  { id: "uv",         group: "Wolken",       label: "UV-Index",         short: "UV",        unit: "",     prio: 45, hasIndicator: true  },
  { id: "freezeLine", group: "Sonstiges",    label: "Nullgrad-Grenze",  short: "0°-Linie",  unit: "m",    prio: 50, hasIndicator: false },
  { id: "newSnow",    group: "Sonstiges",    label: "Neuschnee 24h",    short: "Neuschnee", unit: "cm",   prio: 30, hasIndicator: false },
  { id: "pressure",   group: "Sonstiges",    label: "Luftdruck",        short: "Druck",     unit: "hPa",  prio: 18, hasIndicator: false },
];
const WETTER_METRIC_BY_ID = Object.fromEntries(WETTER_METRICS_CATALOG.map(m => [m.id, m]));

const WETTER_PRESETS = [
  { id: "alpine", builtin: true, name: "Alpen-Trekking", desc: "Standard für Höhenwanderer",
    metrics: ["temp","feels","wind","gust","precip","rainProb","thunder","cloud","visibility","uv","freezeLine"] },
  { id: "kueste",  builtin: true, name: "Küsten-Wandern", desc: "Wind, Welle, Niederschlag",
    metrics: ["temp","wind","gust","precip","rainProb","cloud","visibility","uv"] },
  { id: "skitour", builtin: true, name: "Skitouren", desc: "Lawinen-Indikatoren betont",
    metrics: ["temp","feels","wind","gust","precip","cloud","visibility","freezeLine","newSnow"] },
  { id: "khw403", builtin: false, name: "★ KHW 403 (eigen)", desc: "Karnischer Höhenweg",
    metrics: ["temp","feels","wind","gust","precip","rainProb","thunder","cloud","visibility","uv","freezeLine"] },
];

const WETTER_CHANNELS = [
  { id: "email",    label: "Email",    max: 99,  hint: "alle Werte als Spalten" },
  { id: "telegram", label: "Telegram", max: 8,   hint: "max 8 Spalten" },
  { id: "signal",   label: "Signal",   max: 6,   hint: "max 6 Spalten" },
  { id: "sms",      label: "SMS",      max: 0,   hint: "flach · 140 Zeichen" },
];


/* ════════════════════ Helpers ════════════════════ */

function wetterAutoAssign(metricIds) {
  const list = metricIds.map(id => WETTER_METRIC_BY_ID[id]).filter(Boolean).sort((a, b) => b.prio - a.prio);
  return {
    primary:   list.slice(0, 6).map(m => m.id),
    secondary: list.slice(6).map(m => m.id),
  };
}

function wetterDefaultHorizons(metricIds) {
  const map = {};
  metricIds.forEach(id => {
    const m = WETTER_METRIC_BY_ID[id];
    if (!m) return;
    map[id] = { today: true, tomorrow: m.prio >= 50, day_after: m.prio >= 75 };
  });
  return map;
}

function wetterDefaultScore(metricIds) {
  const map = {};
  metricIds.forEach(id => {
    const m = WETTER_METRIC_BY_ID[id];
    map[id] = !!m && m.prio >= 60;
  });
  return map;
}

const WETTER_SAMPLE_VALUES = ["12", "8.5", "22", "44", "0.2", "62", "hoch", "klar", "5"];
function sampleWetterValue(i) { return WETTER_SAMPLE_VALUES[i] || "—"; }


/* ════════════════════ PresetRail ════════════════════
 * Linke Spalte des Metrics-Editors. Listet alle Wetter-Profile (Builtin +
 * User-Eigene), markiert das aktive, bietet einen „Eigenes Profil speichern"-
 * Block am Ende. Verwendet kein Brand-Element selbst — die ganze Sidebar-
 * Frage ist eine Schicht höher (BrandSidebar).
 */
function PresetRail({ presets = WETTER_PRESETS, value, onChange, totalActive = 0, onSave, compact = false }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div>
        <Eyebrow>Wetter-Profil</Eyebrow>
        <div style={{ fontSize: 13, color: "var(--g-ink-3)", marginTop: 4, lineHeight: 1.5 }}>
          Vorlage wählen oder eigenes Profil anlegen.
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
        {presets.map(p => (
          <button
            key={p.id}
            onClick={() => onChange && onChange(p.id)}
            style={{
              textAlign: "left", padding: compact ? "8px 11px" : "9px 12px",
              background: p.id === value ? "var(--g-accent-tint)" : "transparent",
              borderLeft: p.id === value
                ? "3px solid var(--g-accent)"
                : "3px solid transparent",
              border: "none",
              borderRadius: "var(--g-r-2)",
              cursor: "pointer", fontFamily: "inherit",
            }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 6 }}>
              <span style={{
                fontSize: 13,
                fontWeight: p.id === value ? 600 : 500,
                color: p.id === value ? "var(--g-accent-deep)" : "var(--g-ink)",
              }}>
                {p.name}
                {!p.builtin && (
                  <span className="mono" style={{
                    marginLeft: 6, fontSize: 9, color: "var(--g-accent)",
                    letterSpacing: "0.08em",
                  }}>EIGEN</span>
                )}
              </span>
              <span className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-3)", fontWeight: 600 }}>
                {p.metrics.length}
              </span>
            </div>
            <div style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>{p.desc}</div>
          </button>
        ))}
      </div>

      <div style={{
        padding: 12, background: "var(--g-card-alt)",
        borderRadius: "var(--g-r-3)", border: "1px dashed var(--g-rule)",
      }}>
        <div className="mono" style={{
          fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase",
          color: "var(--g-ink-4)", marginBottom: 6,
        }}>Eigenes Profil</div>
        <div style={{ fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.45, marginBottom: 8 }}>
          Aktuelle Auswahl ({totalActive} Metriken) als Profil sichern.
        </div>
        <Btn variant="ghost" size="sm" style={{ width: "100%" }} onClick={onSave}>
          + Als Profil speichern
        </Btn>
      </div>
    </div>
  );
}


/* ════════════════════ MetricBucket ════════════════════
 * Eine Block-Sektion mit Header + Liste von MetricEditorRow.
 *   bucket="primary"    → „Spalten" mit ChannelLimitChip-Markers im Header
 *   bucket="secondary"  → „Detail-Werte"
 */
function MetricBucket({
  eyebrow, title, hint, items = [], bucket, context,
  horizons, score, mode,
  onHorizon, onScore, onMode, onMove, onReorder,
  showLimitMarkers, compact, channels = WETTER_CHANNELS,
  catalogById = WETTER_METRIC_BY_ID,
}) {
  return (
    <Card padding={0}>
      <div style={{
        padding: compact ? "12px 16px 10px" : "14px 18px 12px",
        borderBottom: "1px solid var(--g-rule-soft)",
      }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12 }}>
          <div>
            <Eyebrow>{eyebrow}</Eyebrow>
            <div style={{
              fontSize: compact ? 15 : 16, fontWeight: 600, marginTop: 2,
              letterSpacing: "-0.01em",
            }}>
              {title}
              <span style={{ color: "var(--g-ink-4)", fontWeight: 400, fontSize: 13 }}>
                {" · "}{items.length}
              </span>
            </div>
          </div>
          {showLimitMarkers && (
            <div style={{ display: "flex", gap: 4 }}>
              {channels.filter(c => c.max > 0 && c.max < 99).map(c => (
                <ChannelLimitChip key={c.id} channel={c.label} current={items.length} max={c.max}/>
              ))}
            </div>
          )}
        </div>
        {hint && (
          <div style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 6, lineHeight: 1.5, maxWidth: 640 }}>
            {hint}
          </div>
        )}
      </div>

      {items.length === 0 ? (
        <div style={{
          padding: 18, fontSize: 12.5, color: "var(--g-ink-4)",
          fontStyle: "italic", textAlign: "center",
        }}>
          Keine Einträge. Aus „Nicht im Briefing" hinzufügen.
        </div>
      ) : (
        <div>
          {items.map((id, i) => (
            <MetricEditorRow
              key={id}
              metric={catalogById[id]}
              index={i}
              bucket={bucket}
              context={context}
              isFirst={i === 0}
              isLast={i === items.length - 1}
              isSignalLimit={bucket === "primary" && i === 5}
              isOverLimit={bucket === "primary" && i >= 6}
              horizon={horizons && horizons[id]}
              inScore={score && score[id]}
              mode={(mode && mode[id]) || "raw"}
              onHorizon={(k) => onHorizon && onHorizon(id, k)}
              onScore={() => onScore && onScore(id)}
              onMode={(m) => onMode && onMode(id, m)}
              onMove={(to) => onMove && onMove(id, bucket, to)}
              onReorder={(dir) => onReorder && onReorder(bucket, id, dir)}
              compact={compact}
            />
          ))}
        </div>
      )}
    </Card>
  );
}


/* ════════════════════ MetricOffShelf ════════════════════
 * Aufklappbarer „Nicht im Briefing"-Block. Gruppiert nach Metric-Group.
 */
function MetricOffShelf({ items = [], onAdd, compact = false, catalog = WETTER_METRICS_CATALOG, defaultOpen = false }) {
  const [open, setOpen] = React.useState(defaultOpen);
  const grouped = catalog
    .filter(m => items.includes(m.id))
    .reduce((acc, m) => {
      (acc[m.group] = acc[m.group] || []).push(m);
      return acc;
    }, {});

  return (
    <Card padding={0}>
      <button
        onClick={() => setOpen(!open)}
        style={{
          width: "100%", padding: compact ? "12px 16px" : "14px 18px",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          background: "transparent", border: "none", cursor: "pointer", textAlign: "left",
        }}>
        <div>
          <Eyebrow>Nicht im Briefing</Eyebrow>
          <div style={{ fontSize: compact ? 14 : 15, fontWeight: 600, marginTop: 2 }}>
            {items.length} weitere Metriken
            <span style={{ color: "var(--g-ink-4)", fontSize: 12, fontWeight: 400 }}> · aktuell aus</span>
          </div>
        </div>
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
          {open ? "▴ einklappen" : "▾ ausklappen"}
        </span>
      </button>
      {open && (
        <div style={{ padding: "0 18px 16px", borderTop: "1px solid var(--g-rule-soft)" }}>
          {Object.entries(grouped).map(([g, ms]) => (
            <div key={g} style={{ marginTop: 14 }}>
              <div className="mono" style={{
                fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase",
                color: "var(--g-ink-3)", fontWeight: 600, marginBottom: 6,
              }}>{g}</div>
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 6,
              }}>
                {ms.map(m => (
                  <div key={m.id} style={{
                    display: "flex", alignItems: "center", gap: 6,
                    padding: "6px 9px", border: "1px solid var(--g-rule-soft)",
                    borderRadius: "var(--g-r-2)", background: "var(--g-card-alt)",
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 12, fontWeight: 500, color: "var(--g-ink-2)" }}>{m.label}</div>
                      <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)" }}>
                        {m.unit || "—"} · {m.short}
                      </div>
                    </div>
                    <Btn variant="ghost" size="xs" onClick={() => onAdd && onAdd(m.id, "primary")}>+ Spalte</Btn>
                    <Btn variant="quiet" size="xs" onClick={() => onAdd && onAdd(m.id, "secondary")}>+ Detail</Btn>
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


/* ════════════════════ ChannelPreviewStrip ════════════════════
 * 4-Karten-Strip: Email · Telegram · Signal · SMS.
 */
function ChannelPreviewStrip({ primary = [], secondary = [], compact = false,
                               catalogById = WETTER_METRIC_BY_ID, channels = WETTER_CHANNELS }) {
  return (
    <Card padding={0}>
      <div style={{
        padding: compact ? "12px 16px 10px" : "14px 18px 10px",
        borderBottom: "1px solid var(--g-rule-soft)",
        display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 12,
      }}>
        <div>
          <Eyebrow>Vorschau · so kommt es beim Empfänger an</Eyebrow>
          <div style={{ fontSize: compact ? 14 : 15, fontWeight: 600, marginTop: 2 }}>Pro Kanal</div>
        </div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", letterSpacing: "0.04em" }}>
          identische Konfiguration · Renderer wendet Kanal-Limits an
        </div>
      </div>
      <div style={{
        display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10,
        padding: 14, background: "var(--g-card-alt)",
      }}>
        {channels.map(ch => (
          <ChannelPreviewCard
            key={ch.id}
            channel={ch}
            primary={primary}
            secondary={secondary}
            metricLookup={catalogById}
            sampleVal={sampleWetterValue}
            compact={compact}
          />
        ))}
      </div>
    </Card>
  );
}


/* ════════════════════ MetricsEditorContextBar ════════════════════
 * Header oben im Editor. Zeigt Profil-Name + Kontext-Beschreibung + Counts.
 */
function MetricsEditorContextBar({ context = "tour", preset, buckets, horizons, score, compact = false }) {
  const ctxLabel = {
    tour: "Tour-Kontext",
    ort:  "Ort-Kontext (im Orts-Vergleich)",
    abo:  "Abo-Kontext (regelmäßiger Vergleich)",
  }[context];

  const ctxDesc = {
    tour: "Briefing-Spalten pro Etappe · Horizonte HEUTE / MORGEN / ÜBERMORGEN pro Metrik wählbar.",
    ort:  "Briefing-Spalten pro Ort · keine Horizonte (Orte haben kein Etappen-Datum) · Metrik kann in den Score einfließen.",
    abo:  "Spalten pro Eintrag im Abo-Vergleich · keine Horizonte · Score-Beitrag pro Metrik konfigurierbar.",
  }[context];

  const horiCount = context === "tour" && horizons
    ? Object.values(horizons).reduce((acc, h) =>
        acc + (h?.today ? 1 : 0) + (h?.tomorrow ? 1 : 0) + (h?.day_after ? 1 : 0), 0)
    : 0;
  const scoreCount = context !== "tour" && score
    ? Object.values(score).filter(Boolean).length
    : 0;

  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "flex-end",
      gap: 16, paddingBottom: 12,
      borderBottom: "1px solid var(--g-rule-soft)",
    }}>
      <div>
        <Eyebrow>{ctxLabel}</Eyebrow>
        <h2 style={{
          fontSize: compact ? 18 : 22, fontWeight: 600,
          letterSpacing: "-0.01em", margin: "2px 0 4px",
        }}>{preset.name}</h2>
        <div style={{
          fontSize: compact ? 11.5 : 12.5, color: "var(--g-ink-3)",
          maxWidth: 620, lineHeight: 1.5,
        }}>{ctxDesc}</div>
      </div>
      <div style={{ display: "flex", gap: 18, whiteSpace: "nowrap" }}>
        <Stat label="Spalten" value={buckets.primary.length} size="md" mono/>
        <Stat label="Detail"  value={buckets.secondary.length} size="md" mono/>
        {context === "tour"
          ? <Stat label="Horizont-Slots" value={horiCount} size="md" mono tone="accent"/>
          : <Stat label="Im Score"        value={scoreCount} size="md" mono tone="accent"/>}
      </div>
    </div>
  );
}


/* ════════════════════ MetricsEditor ════════════════════
 * DIE konsolidierte Editor-Organism. Eine Komponente, drei Kontexte:
 *   context="tour"  → mit HEUTE / MORGEN / ÜBERMORGEN pro Metrik
 *   context="ort"   → ohne Horizonte, dafür „Im Score" pro Metrik
 *   context="abo"   → wie „ort" (Abo-Frequenz lebt eine Ebene höher)
 *
 * Props:
 *   context              ← Pflicht.
 *   initialPresetId      ← Default-aktives Profil.
 *   compact              ← kleinere Schriften / Spaltenmaße (Slide-Panels)
 *   showPresetRail       ← false in Quick-/Slide-Panels
 *   showChannelPreview   ← false in Quick-/Slide-Panels
 *   onSavePreset         ← Klick auf „+ Als Profil speichern"
 */
function MetricsEditor({
  context = "tour",
  initialPresetId = "alpine",
  compact = false,
  showPresetRail = true,
  showChannelPreview = true,
  onSavePreset,
}) {
  const [presetId, setPresetId] = React.useState(initialPresetId);
  const preset = WETTER_PRESETS.find(p => p.id === presetId) || WETTER_PRESETS[0];

  const [buckets, setBuckets] = React.useState(() => wetterAutoAssign(preset.metrics));
  const [horizons, setHorizons] = React.useState(() => wetterDefaultHorizons(preset.metrics));
  const [score, setScore] = React.useState(() => wetterDefaultScore(preset.metrics));
  const [mode, setMode] = React.useState({ wind: "indicator", gust: "indicator", thunder: "indicator" });

  React.useEffect(() => {
    setBuckets(wetterAutoAssign(preset.metrics));
    setHorizons(wetterDefaultHorizons(preset.metrics));
    setScore(wetterDefaultScore(preset.metrics));
  }, [presetId]);

  const all = [...buckets.primary, ...buckets.secondary];
  const off = WETTER_METRICS_CATALOG.filter(m => !all.includes(m.id)).map(m => m.id);

  const toggleHorizon = (id, key) =>
    setHorizons(h => ({ ...h, [id]: { ...(h[id] || {}), [key]: !h[id]?.[key] } }));
  const toggleScore = (id) => setScore(s => ({ ...s, [id]: !s[id] }));
  const setModeFor  = (id, m) => setMode(x => ({ ...x, [id]: m }));

  const move = (id, from, to) => {
    setBuckets(b => {
      const next = { primary: [...b.primary], secondary: [...b.secondary] };
      if (from === "primary")   next.primary   = next.primary.filter(x => x !== id);
      if (from === "secondary") next.secondary = next.secondary.filter(x => x !== id);
      if (to === "primary")     next.primary   = [...next.primary, id];
      if (to === "secondary")   next.secondary = [...next.secondary, id];
      return next;
    });
  };
  const reorder = (bucket, id, dir) => {
    setBuckets(b => {
      const list = [...b[bucket]];
      const i = list.indexOf(id);
      const j = i + dir;
      if (j < 0 || j >= list.length) return b;
      [list[i], list[j]] = [list[j], list[i]];
      return { ...b, [bucket]: list };
    });
  };
  const addFromShelf = (id, target) => {
    setBuckets(b => ({ ...b, [target]: [...b[target], id] }));
  };

  return (
    <div style={{
      background: "var(--g-paper)",
      fontFamily: "var(--g-font-sans)",
      color: "var(--g-ink)",
      display: "grid",
      gridTemplateColumns: showPresetRail ? "240px 1fr" : "1fr",
      gap: compact ? 20 : 28,
      padding: compact ? "20px 22px" : "26px 32px",
    }}>
      {showPresetRail && (
        <PresetRail
          presets={WETTER_PRESETS}
          value={presetId}
          onChange={setPresetId}
          totalActive={all.length}
          onSave={onSavePreset}
          compact={compact}
        />
      )}

      <div style={{
        display: "flex", flexDirection: "column",
        gap: compact ? 16 : 20, minWidth: 0,
      }}>
        <MetricsEditorContextBar
          context={context}
          preset={preset}
          buckets={buckets}
          horizons={horizons}
          score={score}
          compact={compact}
        />

        <MetricBucket
          eyebrow="Im Briefing als Spalte"
          title="Spalten"
          hint={context === "tour"
            ? "Eigene Tabellen-Spalte. Reihenfolge = links → rechts. Signal max 6, Telegram max 8."
            : "Eigene Tabellen-Spalte im Vergleich. Reihenfolge entspricht Anzeige- und Score-Reihenfolge."}
          items={buckets.primary}
          bucket="primary"
          context={context}
          horizons={horizons} score={score} mode={mode}
          onHorizon={toggleHorizon} onScore={toggleScore} onMode={setModeFor}
          onMove={move} onReorder={reorder}
          showLimitMarkers
          compact={compact}
        />

        <MetricBucket
          eyebrow="Im Briefing als Detail"
          title="Detail-Werte"
          hint="Erscheinen als kompakte Zeile unter der Tabelle: Bewölkung 80 % · Sicht 5 km · …"
          items={buckets.secondary}
          bucket="secondary"
          context={context}
          horizons={horizons} score={score} mode={mode}
          onHorizon={toggleHorizon} onScore={toggleScore} onMode={setModeFor}
          onMove={move} onReorder={reorder}
          compact={compact}
        />

        {showChannelPreview && (
          <ChannelPreviewStrip
            primary={buckets.primary}
            secondary={buckets.secondary}
            compact={compact}
          />
        )}

        <MetricOffShelf items={off} onAdd={addFromShelf} compact={compact}/>
      </div>
    </div>
  );
}


/* ════════════════════ Sub-Komponenten für MetricBucket / ChannelPreviewStrip ════════════════════
 *
 *  Diese Komponenten waren als Referenz in MetricBucket / ChannelPreviewStrip
 *  schon vorhanden, fehlten aber als eigentliche Definitionen. Mit dem
 *  Reparatur-Patch (Session 7) jetzt geschlossen.
 *
 *  Lokale Helpers tragen ME*-Prefix, damit sie nicht mit gleichnamigen
 *  Inline-Helpern in screen-metrics-editor.jsx kollidieren (Babel-Scope-Falle).
 */

/* applyChannel — identisch zur Backend-Renderer-Logik aus
 * body-14-output-layout-system.md. Wendet das Spalten-Limit eines Kanals
 * auf eine primary/secondary-Konfiguration an. */
function applyChannel(primary, secondary, maxCols) {
  const inTable = primary.slice(0, maxCols);
  const overflow = primary.slice(maxCols);
  const detail = [...overflow, ...secondary];
  return { inTable, detail, demoted: overflow.length };
}

/* MEModeToggle — Segmented Control zwischen Rohwert und Skala. */
function MEModeToggle({ mode, onMode, compact }) {
  const btn = (active) => ({
    padding: compact ? "3px 9px" : "4px 12px",
    fontSize: compact ? 10.5 : 11, fontWeight: 600,
    border: "none", cursor: "pointer", borderRadius: 2,
    background: active ? "var(--g-paper)" : "transparent",
    color: active ? "var(--g-accent-deep)" : "var(--g-ink-3)",
    boxShadow: active ? "0 0 0 1px var(--g-rule)" : "none",
    fontFamily: "var(--g-font-mono)", letterSpacing: "0.04em",
  });
  return (
    <div style={{
      display: "inline-flex", padding: 2,
      background: "var(--g-card-alt)", borderRadius: 3,
      border: "1px solid var(--g-rule-soft)",
    }}>
      <button onClick={() => onMode && onMode("raw")}       style={btn(mode === "raw")}>Roh</button>
      <button onClick={() => onMode && onMode("indicator")} style={btn(mode === "indicator")}>Skala</button>
    </div>
  );
}

/* METextBtn — Inline-Text-Button für Move-Aktionen. */
function METextBtn({ children, onClick, disabled }) {
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

/* MEIconArrow — Up/Down-Pfeil für Reorder. */
function MEIconArrow({ direction, disabled, onClick }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      width: 26, height: 26, border: "1px solid var(--g-rule)", borderRadius: 3,
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center", padding: 0,
    }}>
      <svg width="11" height="11" viewBox="0 0 12 12" fill="none">
        {direction === "up"
          ? <path d="M6 2.5L10 8H2L6 2.5Z" fill="currentColor"/>
          : <path d="M6 9.5L2 4H10L6 9.5Z" fill="currentColor"/>}
      </svg>
    </button>
  );
}

/* MEHorizonChip — Slot-Toggle für HEUTE/MORGEN/ÜBERMORGEN. Nur im Tour-Kontext sichtbar. */
function MEHorizonChip({ label, active, onClick }) {
  return (
    <button onClick={onClick} style={{
      padding: "3px 7px", fontSize: 10, fontWeight: 600,
      fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em",
      borderRadius: 999, cursor: "pointer",
      background: active ? "var(--g-accent-tint)" : "transparent",
      color: active ? "var(--g-accent-deep)" : "var(--g-ink-4)",
      border: active ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
    }}>{label}</button>
  );
}

/* ════════════════════ MetricEditorRow ════════════════════
 * Eine Zeile pro Metrik im Spalten- oder Detail-Bucket.
 *
 * Layout (links → rechts):
 *   [Index]  Metrik-Label + Unit/Kürzel   Roh|Skala-Toggle   Move-Buttons   Reorder
 *   (Index nur in primary; HEUTE/MORGEN/ÜBM nur in context="tour")
 *
 * Die SignalLimit-Trennlinie (ab Index 6 in primary) wird über der
 * Zeile gerendert, nicht innerhalb — sonst landet sie zwischen Border und
 * Zeile und bricht das Raster.
 */
function MetricEditorRow({
  metric, index, bucket, context = "tour",
  isFirst, isLast, isSignalLimit, isOverLimit,
  horizon, inScore, mode, onHorizon, onScore, onMode, onMove, onReorder,
  compact,
}) {
  if (!metric) return null;
  const showIndex = bucket === "primary";
  const isTour = context === "tour";
  const hasIndicator = metric.hasIndicator;

  const cols = (() => {
    if (showIndex) {
      return isTour
        ? "28px 1fr 220px 130px 110px 70px"   // idx · meta · horizon-chips · mode · move · reorder
        : "28px 1fr 86px 130px 110px 70px";   // idx · meta · score · mode · move · reorder
    }
    return isTour
      ? "1fr 220px 130px 130px 70px"
      : "1fr 86px 130px 130px 70px";
  })();

  return (
    <React.Fragment>
      {isSignalLimit && (
        <div style={{
          padding: compact ? "3px 16px" : "4px 18px",
          fontSize: 10.5, fontFamily: "var(--g-font-mono)",
          letterSpacing: "0.1em", textTransform: "uppercase",
          color: "var(--g-warn)", background: "rgba(192,138,26,0.06)",
          borderTop: "1px dashed var(--g-warn)",
          borderBottom: "1px dashed var(--g-warn)",
        }}>
          ↓ ab hier bei <strong>Signal</strong> automatisch als Detail-Zeile (max 6 Spalten)
        </div>
      )}
      <div style={{
        display: "grid", gridTemplateColumns: cols, gap: 10,
        padding: compact ? "10px 16px" : "12px 18px",
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
          <div style={{ fontSize: compact ? 13 : 14, fontWeight: 500, color: "var(--g-ink)" }}>
            {metric.label}
          </div>
          <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 2 }}>
            {metric.unit || "—"} · Kürzel <span style={{ color: "var(--g-ink-3)" }}>{metric.short}</span>
          </div>
        </div>

        {isTour ? (
          <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
            <MEHorizonChip label="HEUTE"  active={!!horizon?.today}     onClick={() => onHorizon && onHorizon("today")}/>
            <MEHorizonChip label="MORGEN" active={!!horizon?.tomorrow}  onClick={() => onHorizon && onHorizon("tomorrow")}/>
            <MEHorizonChip label="ÜBM"    active={!!horizon?.day_after} onClick={() => onHorizon && onHorizon("day_after")}/>
          </div>
        ) : (
          <button onClick={onScore} style={{
            padding: "5px 9px", fontSize: 10.5, fontWeight: 600,
            fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em",
            borderRadius: 999, cursor: "pointer",
            background: inScore ? "var(--g-accent-tint)" : "transparent",
            color: inScore ? "var(--g-accent-deep)" : "var(--g-ink-4)",
            border: inScore ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
            whiteSpace: "nowrap",
          }}>
            {inScore ? "IM SCORE" : "+ SCORE"}
          </button>
        )}

        <div>
          {hasIndicator ? (
            <MEModeToggle mode={mode} onMode={onMode} compact={compact}/>
          ) : (
            <span className="mono" style={{
              fontSize: 10, color: "var(--g-ink-4)",
              letterSpacing: "0.06em", textTransform: "uppercase",
            }}>nur Rohwert</span>
          )}
        </div>

        <div style={{ display: "flex", gap: 4 }}>
          {bucket === "primary" && (
            <React.Fragment>
              <METextBtn onClick={() => onMove && onMove("secondary")}>→ Detail</METextBtn>
              <METextBtn onClick={() => onMove && onMove("off")}>✕</METextBtn>
            </React.Fragment>
          )}
          {bucket === "secondary" && (
            <React.Fragment>
              <METextBtn onClick={() => onMove && onMove("primary")}>↑ Spalte</METextBtn>
              <METextBtn onClick={() => onMove && onMove("off")}>✕</METextBtn>
            </React.Fragment>
          )}
        </div>

        <div style={{ display: "flex", gap: 2, justifyContent: "flex-end" }}>
          <MEIconArrow direction="up"   disabled={isFirst} onClick={() => onReorder && onReorder(-1)}/>
          <MEIconArrow direction="down" disabled={isLast}  onClick={() => onReorder && onReorder(+1)}/>
        </div>
      </div>
    </React.Fragment>
  );
}

/* ════════════════════ ChannelLimitChip ════════════════════
 * Ein Pill, das zeigt „Signal 7/6" oder „Telegram 5/8". Warnt
 * orange-warn wenn current > max. Genutzt im MetricBucket-Header.
 */
function ChannelLimitChip({ channel, current, max }) {
  const exceeded = current > max;
  return (
    <span style={{
      padding: "3px 8px", fontSize: 10.5,
      fontFamily: "var(--g-font-mono)", letterSpacing: "0.04em",
      borderRadius: 999, fontWeight: 600,
      background: exceeded ? "rgba(192,138,26,0.15)" : "rgba(26,26,24,0.05)",
      color: exceeded ? "var(--g-warn)" : "var(--g-ink-3)",
      border: exceeded ? "1px solid var(--g-warn)" : "1px solid transparent",
      whiteSpace: "nowrap",
    }}>
      {channel} {current}/{max}
    </span>
  );
}

/* ════════════════════ ChannelPreviewCard ════════════════════
 * Eine Karte im 4-er-Strip: zeigt für genau einen Kanal, wie die aktuelle
 * Konfiguration nach Anwendung der Constraints aussieht (Mini-Tabelle +
 * Detail-Zeile, oder bei SMS: flache Zeile).
 */
function ChannelPreviewCard({
  channel, primary, secondary,
  metricLookup = WETTER_METRIC_BY_ID,
  sampleVal = sampleWetterValue,
  compact = false,
}) {
  const isSMS = channel.max === 0;
  const { inTable, detail, demoted } = applyChannel(primary, secondary, channel.max);

  return (
    <div style={{
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", overflow: "hidden",
      display: "flex", flexDirection: "column",
    }}>
      <div style={{ padding: compact ? "8px 10px" : "10px 12px", borderBottom: "1px solid var(--g-rule-soft)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6 }}>
          <div style={{ fontSize: compact ? 12 : 13, fontWeight: 600 }}>{channel.label}</div>
          <span className="mono" style={{
            padding: "2px 8px", fontSize: 10, borderRadius: 999,
            background: demoted > 0 ? "rgba(192,138,26,0.15)" : "rgba(26,26,24,0.05)",
            color: demoted > 0 ? "var(--g-warn)" : "var(--g-ink-3)",
            fontWeight: 600, whiteSpace: "nowrap",
          }}>
            {isSMS ? "flach" : `${inTable.length}/${channel.max < 99 ? channel.max : "∞"} Sp`}
          </span>
        </div>
        <div className="mono" style={{
          fontSize: 9.5, color: "var(--g-ink-4)",
          marginTop: 4, letterSpacing: "0.03em",
        }}>{channel.hint}</div>
      </div>

      <div style={{ padding: compact ? 10 : 12, flex: 1, fontSize: 11 }}>
        {!isSMS && inTable.length > 0 && (
          <div style={{
            background: "var(--g-paper-deep)", borderRadius: "var(--g-r-2)",
            padding: "6px 8px", fontFamily: "var(--g-font-mono)",
            fontSize: 10, lineHeight: 1.5,
            overflowX: "auto", whiteSpace: "pre", color: "var(--g-ink)",
          }}>
            {inTable.map(id =>
              (metricLookup[id]?.short || id).slice(0, 5).padEnd(6, " ")
            ).join("")}
            {"\n"}
            {inTable.map((_, i) => String(sampleVal(i)).padEnd(6, " ")).join("")}
          </div>
        )}

        {detail.length > 0 && !isSMS && (
          <div style={{
            marginTop: 8, fontSize: 11, color: "var(--g-ink-2)",
            lineHeight: 1.5, fontStyle: "italic",
          }}>
            <span className="mono" style={{
              fontSize: 9, color: "var(--g-ink-4)",
              letterSpacing: "0.08em", textTransform: "uppercase",
              marginRight: 4, fontStyle: "normal",
            }}>Detail:</span>
            {detail.map((id, i) =>
              `${metricLookup[id]?.label || id} ${sampleVal(i)}`
            ).join(" · ")}
          </div>
        )}

        {isSMS && (
          <div style={{ fontSize: 11, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
            {[...primary, ...secondary].slice(0, 8).map((id, i) =>
              `${metricLookup[id]?.short || id} ${sampleVal(i)}`
            ).join(" · ")}
            {primary.length + secondary.length > 8 && (
              <span style={{ color: "var(--g-ink-4)" }}> …</span>
            )}
          </div>
        )}

        {demoted > 0 && (
          <div style={{
            marginTop: 10, padding: "5px 8px",
            background: "rgba(192,138,26,0.08)",
            borderLeft: "2px solid var(--g-warn)",
            fontSize: 10.5, color: "var(--g-warn)", fontWeight: 600,
          }}>
            ⚠ {demoted} {demoted === 1 ? "Spalte" : "Spalten"} in Detail verschoben
          </div>
        )}
      </div>
    </div>
  );
}


/* ════════════════════ Export ════════════════════ */
Object.assign(window, {
  /* Daten */
  WETTER_METRICS_CATALOG, WETTER_METRIC_BY_ID, WETTER_PRESETS, WETTER_CHANNELS,
  wetterAutoAssign, wetterDefaultHorizons, wetterDefaultScore, sampleWetterValue,
  applyChannel,
  /* Sub-Komponenten */
  MetricEditorRow, ChannelLimitChip, ChannelPreviewCard,
  /* Organisms */
  PresetRail, MetricBucket, MetricOffShelf, ChannelPreviewStrip,
  MetricsEditorContextBar, MetricsEditor,
});
