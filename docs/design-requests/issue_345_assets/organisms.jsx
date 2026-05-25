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


/* ════════════════════ Export ════════════════════ */
Object.assign(window, {
  /* Daten */
  WETTER_METRICS_CATALOG, WETTER_METRIC_BY_ID, WETTER_PRESETS, WETTER_CHANNELS,
  wetterAutoAssign, wetterDefaultHorizons, wetterDefaultScore, sampleWetterValue,
  /* Organisms */
  PresetRail, MetricBucket, MetricOffShelf, ChannelPreviewStrip,
  MetricsEditorContextBar, MetricsEditor,
});
