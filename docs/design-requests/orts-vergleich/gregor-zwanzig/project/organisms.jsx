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
 *  ═══ DRIFT-RESOLUTION (Issue #364, Session 2026-05-27) ═══
 *
 *  Die hier definierten Daten + Helpers wurden auf den Production-Stand
 *  aus `frontend/src/lib/components/trip-detail/metricsEditor.ts`
 *  (Backend-Spec Issue #360 / #364 / #365) gezogen:
 *
 *    Metrik-Namen        : temperature, wind_chill, wind_direction,
 *                          rain_probability, …  (Backend-IDs; alte Sandbox-
 *                          IDs `temp`/`feels`/`windDir`/`rainProb`
 *                          entfernt — kein Kompat-Layer, weil Sandbox-
 *                          Konsumenten gleichzeitig migriert werden).
 *    Metrik-Anzahl       : 25  (vorher 15)
 *    Kategorie-IDs       : temperature / wind / precipitation /
 *                          atmosphere / winter
 *                          (UI-Display-Labels via CATEGORY_LABELS auf
 *                          deutsch — siehe unten).
 *    Primary-Slots       : 5  (Signal-Budget, vorher 6)
 *    Channel-Budget      : email ∞ · telegram 7 · signal 5 · sms 0
 *                          (Uhrzeit-Spalte NICHT mitgezaehlt — deckt sich
 *                          mit Backend `channel_layout.py`).
 *
 *  Komponenten-API (kanonische Namen jetzt produktions-näher):
 *      WeatherMetricsTab           — DIE konsolidierte Editor-Organism
 *                                    (Alias: MetricsEditor — Legacy-Name)
 *      MetricGroup                 — Spalten- bzw. Detail-Sektion mit Rows
 *                                    (Alias: MetricBucket — Legacy)
 *      MetricCheckbox              — Tap-Row im MetricOffShelf
 *                                    (NEU — Production-Decomposition)
 *      ChannelPreviewBlock         — 4-Karten-Vorschau pro Kanal
 *                                    (Alias: ChannelPreviewStrip — Legacy)
 *      PresetRail                  — Preset-Liste mit „Eigenes Profil"-Block
 *      MetricOffShelf              — Aufklappbarer „Nicht im Briefing"-Block
 *      MetricsEditorContextBar     — Header oben (Kontext, Counts)
 *
 *  Daten + Helpers (kanonische Namen):
 *      METRIC_CATALOG, METRIC_BY_ID, METRIC_PRIORITY, METRICS_BY_CATEGORY
 *      CATEGORY_ORDER, CATEGORY_LABELS, INDICATOR_MAP, PRIMARY_SLOTS
 *      CHANNEL_BUDGET, CHANNEL_LIMITS, PRESETS
 *      applyChannel, metricsAutoAssign, metricsMove, metricsReorder
 *      channelOverflow, indicatorCapable, buildBucketSummary,
 *      buildPresetSummary, selectTableColumns, countActiveInCategory,
 *      metricsDefaultHorizons, metricsDefaultScore, sampleMetricValue
 *
 *  Legacy-Aliase (für screen-design-system.jsx & Komponenten-Showcase):
 *      WETTER_METRICS_CATALOG = METRIC_CATALOG
 *      WETTER_METRIC_BY_ID    = METRIC_BY_ID
 *      WETTER_PRESETS         = PRESETS
 *      WETTER_CHANNELS        = CHANNEL_LIMITS
 *      wetterAutoAssign       = metricsAutoAssign
 *      wetterDefaultHorizons  = metricsDefaultHorizons
 *      wetterDefaultScore     = metricsDefaultScore
 *      sampleWetterValue      = sampleMetricValue
 *      MetricsEditor          = WeatherMetricsTab
 *      MetricBucket           = MetricGroup
 *      ChannelPreviewStrip    = ChannelPreviewBlock
 *
 *  Diese Organismen ersetzen die historisch in screen-metrics-editor.jsx
 *  inline definierten Sub-Komponenten. Der bestehende Sandbox-Screen
 *  bleibt unverändert (alte IDs); bei nächster Berührung wird er auf
 *  diese Organism-API umgestellt.
 */


/* ════════════════════ Daten-Konstanten ════════════════════
 *
 *  IDs, Prioritäten und Kategorien spiegeln 1:1 die Production-Quelle
 *  `frontend/src/lib/components/trip-detail/metricsEditor.ts`
 *  (Issue #360 METRIC_PRIORITY + Issue #364 Bucket-Editor).
 *
 *  Display-Labels bleiben deutsch (User-Sprache); IDs bleiben englisch
 *  (Backend-Schema).
 */

/* Kategorie-IDs in Anzeige-Reihenfolge — deckt sich mit
 * CATEGORY_ORDER in metricsEditor.ts. */
const CATEGORY_ORDER = [
  "temperature",
  "wind",
  "precipitation",
  "atmosphere",
  "winter",
];

/* User-facing Kategorie-Labels (deutsch). */
const CATEGORY_LABELS = {
  temperature:   "Temperatur",
  wind:          "Wind",
  precipitation: "Niederschlag",
  atmosphere:    "Atmosphäre",
  winter:        "Winter",
};

/* INDICATOR_MAP — 12 Metriken mit Roh/Skala-Toggle.
 * 1:1 aus metricsEditor.ts (§4). Die Strings hier sind nur Tooltips/
 * Display-Hinweise für die UI — die Backend-Mapping-Tabellen
 * (`wind` -> "ruhig"/"mäßig"/"stark"/"sturm" etc.) leben im Renderer. */
const INDICATOR_MAP = {
  wind_direction:   "N / O / S / W",
  thunder:          "keins / mittel / hoch / extrem",
  cape:             "niedrig / mittel / hoch / extrem",
  cloud_total:      "klar / teilw. / bewölkt / bedeckt",
  cloud_low:        "klar / teilw. / bewölkt / bedeckt",
  cloud_mid:        "klar / teilw. / bewölkt / bedeckt",
  cloud_high:       "klar / teilw. / bewölkt / bedeckt",
  visibility:       "gut / eingeschränkt / schlecht / sehr schlecht",
  sunshine:         "hell / wechselhaft / bedeckt",
  wind:             "ruhig / mäßig / stark / sturm",
  gust:             "harmlos / mäßig / stark / orkan",
  rain_probability: "niedrig / mittel / hoch / sehr hoch",
};
function indicatorCapable(id) { return Object.prototype.hasOwnProperty.call(INDICATOR_MAP, id); }

/* METRIC_PRIORITY — identisch zu metricsEditor.ts (#360).
 * Höher = wichtiger. Die Top-5 landen via metricsAutoAssign in primary
 * (Signal-safe). */
const METRIC_PRIORITY = {
  temperature: 95, wind: 90, gust: 88, rain_probability: 85,
  precipitation: 78, wind_chill: 70, cloud_total: 65, thunder: 60,
  fresh_snow: 55, visibility: 55, freezing_level: 50, uv_index: 45,
  wind_direction: 40, snow_depth: 35, precip_type: 35, snowfall_limit: 35,
  cloud_low: 30, humidity: 25, sunshine: 25, dewpoint: 20,
  pressure: 18, cape: 15, cloud_mid: 12, cloud_high: 10, confidence: 8,
};

/* Vollständiger Metrik-Katalog (25 Einträge).
 *
 *  category   ← English-IDs aus CATEGORY_ORDER
 *  label      ← deutscher User-facing Name
 *  short      ← Kürzel für die Mini-Tabellen-Vorschau (≤5 Zeichen wirken
 *               in der 6-Spalten-Vorschau am besten)
 *  unit       ← Einheit für Display
 *  prio       ← Spiegel-Attribut zu METRIC_PRIORITY (für ad-hoc
 *               Sortierung; Source-of-Truth bleibt METRIC_PRIORITY)
 *  hasIndicator ← abgeleitet aus INDICATOR_MAP (Cache)
 */
const METRIC_CATALOG = [
  // Temperature
  { id: "temperature",      category: "temperature",   label: "Temperatur",          short: "Temp",  unit: "°C"   },
  { id: "wind_chill",       category: "temperature",   label: "Gefühlte Temp",       short: "Feels", unit: "°C"   },
  { id: "humidity",         category: "temperature",   label: "Luftfeuchtigkeit",    short: "Luftf", unit: "%"    },
  { id: "dewpoint",         category: "temperature",   label: "Taupunkt",            short: "Taup",  unit: "°C"   },

  // Wind
  { id: "wind",             category: "wind",          label: "Wind",                short: "Wind",  unit: "km/h" },
  { id: "gust",             category: "wind",          label: "Böen",                short: "Böen",  unit: "km/h" },
  { id: "wind_direction",   category: "wind",          label: "Windrichtung",        short: "Richt", unit: "°"    },

  // Precipitation
  { id: "precipitation",    category: "precipitation", label: "Niederschlag",        short: "Regen", unit: "mm"   },
  { id: "rain_probability", category: "precipitation", label: "Regen-Wahrsch.",      short: "Reg%",  unit: "%"    },
  { id: "thunder",          category: "precipitation", label: "Gewitter-Wahrsch.",   short: "Gewit", unit: "%"    },
  { id: "cape",             category: "precipitation", label: "CAPE (Energie)",      short: "CAPE",  unit: "J/kg" },
  { id: "precip_type",      category: "precipitation", label: "Niederschl.-Art",     short: "Art",   unit: ""     },

  // Atmosphere
  { id: "cloud_total",      category: "atmosphere",    label: "Bewölkung gesamt",    short: "Bew",   unit: "%"    },
  { id: "cloud_low",        category: "atmosphere",    label: "Tiefe Wolken",        short: "tWolk", unit: "%"    },
  { id: "cloud_mid",        category: "atmosphere",    label: "Mittlere Wolken",     short: "mWolk", unit: "%"    },
  { id: "cloud_high",       category: "atmosphere",    label: "Hohe Wolken",         short: "hWolk", unit: "%"    },
  { id: "visibility",       category: "atmosphere",    label: "Sichtweite",          short: "Sicht", unit: "km"   },
  { id: "sunshine",         category: "atmosphere",    label: "Sonnenschein-Dauer",  short: "Sonne", unit: "min"  },
  { id: "uv_index",         category: "atmosphere",    label: "UV-Index",            short: "UV",    unit: ""     },
  { id: "pressure",         category: "atmosphere",    label: "Luftdruck",           short: "Druck", unit: "hPa"  },
  { id: "confidence",       category: "atmosphere",    label: "Konfidenz",           short: "Konf",  unit: "%"    },

  // Winter
  { id: "freezing_level",   category: "winter",        label: "Nullgrad-Grenze",     short: "0°",    unit: "m"    },
  { id: "fresh_snow",       category: "winter",        label: "Neuschnee 24 h",      short: "Neusc", unit: "cm"   },
  { id: "snow_depth",       category: "winter",        label: "Schneehöhe",          short: "Schne", unit: "cm"   },
  { id: "snowfall_limit",   category: "winter",        label: "Schneefallgrenze",    short: "Sgrz",  unit: "m"    },
].map(m => ({
  ...m,
  prio: METRIC_PRIORITY[m.id] ?? 0,
  hasIndicator: indicatorCapable(m.id),
}));

const METRIC_BY_ID = Object.fromEntries(METRIC_CATALOG.map(m => [m.id, m]));

/* Metriken pro Kategorie — gruppierte Sicht für MetricOffShelf etc. */
const METRICS_BY_CATEGORY = METRIC_CATALOG.reduce((acc, m) => {
  (acc[m.category] = acc[m.category] || []).push(m);
  return acc;
}, {});

/* Built-in + ein User-Preset. Production hält Presets zwar separat
 * (DB-getrieben), aber für UI-Demos und das KHW-403-Eigen-Preset
 * brauchen wir hier eine Default-Liste. IDs stammen aus
 * METRIC_CATALOG. */
const PRESETS = [
  { id: "alpine",  builtin: true,  name: "Alpen-Trekking", desc: "Standard für Höhenwanderer",
    metrics: ["temperature","wind_chill","wind","gust","precipitation","rain_probability","thunder","cloud_total","visibility","uv_index","freezing_level"] },
  { id: "hiking",  builtin: true,  name: "Wandern", desc: "Fokus auf Tagesentscheidung",
    metrics: ["temperature","wind_chill","wind","gust","precipitation","rain_probability","thunder","cloud_total","uv_index"] },
  { id: "kueste",  builtin: true,  name: "Küsten-Wandern", desc: "Wind, Welle, Niederschlag",
    metrics: ["temperature","wind","gust","wind_direction","precipitation","rain_probability","cloud_total","visibility","uv_index"] },
  { id: "skitour", builtin: true,  name: "Skitouren", desc: "Lawinen-Indikatoren betont",
    metrics: ["temperature","wind_chill","wind","gust","wind_direction","precipitation","cloud_total","visibility","freezing_level","fresh_snow","snow_depth"] },
  { id: "khw403",  builtin: false, name: "★ KHW 403 (eigen)", desc: "Karnischer Höhenweg",
    metrics: ["temperature","wind_chill","wind","gust","precipitation","rain_probability","thunder","cloud_total","visibility","uv_index","freezing_level"] },
];

/* Kanal-Constraints — identisch zu CHANNEL_COL_BUDGET in metricsEditor.ts.
 * Email ∞, Telegram 7, Signal 5, SMS 0  (Uhrzeit-Spalte NICHT mitgezählt). */
const CHANNEL_BUDGET = {
  email:    Infinity,
  telegram: 7,
  signal:   5,
  sms:      0,
};

/* Anzeige-Modell für die Channel-Strip-Vorschau. `max=Infinity` wird im
 * UI als "∞" gerendert; numerische Limits bleiben numerisch. */
const CHANNEL_LIMITS = [
  { id: "email",    label: "Email",    max: CHANNEL_BUDGET.email,    hint: "alle Werte als Spalten" },
  { id: "telegram", label: "Telegram", max: CHANNEL_BUDGET.telegram, hint: "max 7 Spalten (+ Zeit)" },
  { id: "signal",   label: "Signal",   max: CHANNEL_BUDGET.signal,   hint: "max 5 Spalten (+ Zeit)" },
  { id: "sms",      label: "SMS",      max: CHANNEL_BUDGET.sms,      hint: "flach · 140 Zeichen" },
];

/* PRIMARY_SLOTS = 5 (Signal-Budget, Uhrzeit nicht mitgezählt).
 * Spiegelt _PRIMARY_SLOTS in Backend channel_layout.py + PRIMARY_SLOTS
 * in metricsEditor.ts. */
const PRIMARY_SLOTS = 5;


/* ════════════════════ Helpers ════════════════════
 *
 *  Identische Semantik zu den exportierten Funktionen in
 *  metricsEditor.ts (Issue #364 / #365). Wo möglich denselben
 *  Namen verwendet; UI-only-Helpers (Default-Horizonte/-Score,
 *  Sample-Werte) tragen `metrics`-Prefix.
 */

/* AC-1 / AC-8 metricsEditor.ts: Top-5 nach METRIC_PRIORITY → primary,
 * Rest aktiv → secondary, im Katalog nicht aktiv → off.
 * Stabil: bei Prio-Gleichstand entscheidet Eingabe-Reihenfolge.
 * Returnt {primary, secondary} — `off` wird vom MetricsEditor selbst
 * aus dem Katalog-Delta abgeleitet (Aufrufer-API blieb so). */
function metricsAutoAssign(metricIds) {
  const seen = new Set();
  const unique = metricIds.filter(id => {
    if (seen.has(id)) return false;
    seen.add(id);
    return true;
  });
  const ranked = unique
    .map((id, idx) => ({ id, idx, prio: METRIC_PRIORITY[id] ?? 0 }))
    .filter(x => METRIC_BY_ID[x.id])
    .sort((a, b) => (b.prio - a.prio) || (a.idx - b.idx))
    .map(x => x.id);
  return {
    primary:   ranked.slice(0, PRIMARY_SLOTS),
    secondary: ranked.slice(PRIMARY_SLOTS),
  };
}

/* AC-2 / AC-6: Move-Helper (immutabel). F001-Härtung: No-Op wenn id
 * nicht in b[from]. */
function metricsMove(b, id, from, to) {
  if (!b[from] || !b[from].includes(id)) {
    return { ...b };
  }
  const next = {
    primary:   [...(b.primary || [])],
    secondary: [...(b.secondary || [])],
    off:       [...(b.off || [])],
  };
  next[from] = next[from].filter(x => x !== id);
  if (!next[to].includes(id)) next[to] = [...next[to], id];
  return next;
}

/* AC-3: Nachbar-Swap. No-Op an den Rändern. */
function metricsReorder(b, bucket, id, dir) {
  const list = [...(b[bucket] || [])];
  const idx = list.indexOf(id);
  if (idx === -1) return b;
  const target = idx + dir;
  if (target < 0 || target >= list.length) return b;
  [list[idx], list[target]] = [list[target], list[idx]];
  return { ...b, [bucket]: list };
}

/* AC-1..AC-3 metricsEditor.ts: Kanal-Budget anwenden.
 * - budget === Infinity (Email): alles als Spalte, kein Demote.
 * - budget === 0 (SMS): keine Tabelle, alles flach in detail.
 * - sonst (Signal 5 / Telegram 7): inTable gekappt; overflow vorne
 *   in detail (vor secondary). */
function applyChannel(primary, secondary, budget) {
  if (budget === 0) {
    return { inTable: [], detail: [...primary, ...secondary], demoted: primary.length };
  }
  if (budget === Infinity) {
    return { inTable: [...primary], detail: [...secondary], demoted: 0 };
  }
  const inTable  = primary.slice(0, budget);
  const overflow = primary.slice(budget);
  return { inTable, detail: [...overflow, ...secondary], demoted: overflow.length };
}

/* AC-5: Per-Kanal Overflow-Flag (primary-Count > Budget). */
function channelOverflow(primaryCount) {
  return {
    email:    primaryCount > CHANNEL_BUDGET.email,
    telegram: primaryCount > CHANNEL_BUDGET.telegram,
    signal:   primaryCount > CHANNEL_BUDGET.signal,
    sms:      primaryCount > CHANNEL_BUDGET.sms,
  };
}

/* AC-3 metricsEditor.ts §2 (#174): aktive Metriken in einer Kategorie. */
function countActiveInCategory(metricIds, enabledMap) {
  let n = 0;
  for (const id of metricIds) if (enabledMap[id] === true) n++;
  return n;
}

/* AC-4 metricsEditor.ts (#365): Bucket-Summary für SavePresetDialog. */
function buildBucketSummary(buckets, friendlyMap) {
  const active = [...(buckets.primary || []), ...(buckets.secondary || [])];
  const skala = active.filter(id => friendlyMap[id] === true).length;
  return {
    spalten: (buckets.primary || []).length,
    detail:  (buckets.secondary || []).length,
    skala,
  };
}

/* AC-6 metricsEditor.ts (#177): Preset-Summary (enabled/raw/indicator).
 * Für Aufrufer, die noch im enabled/friendly-Map-Schema arbeiten. */
function buildPresetSummary(enabledMap, friendlyMap) {
  let activeCount = 0, rawCount = 0, indicatorCount = 0;
  for (const [id, enabled] of Object.entries(enabledMap)) {
    if (!enabled) continue;
    activeCount++;
    if (!indicatorCapable(id)) continue;
    if (friendlyMap[id] === true) indicatorCount++;
    else if (friendlyMap[id] === false) rawCount++;
  }
  return { activeCount, rawCount, indicatorCount };
}

/* AC-5 metricsEditor.ts (#176): Aktivierte Metriken in CATEGORY_ORDER-
 * Reihenfolge. Kategorien außerhalb der Order werden hinten angehängt
 * (Object.keys-Insertion-Order). */
function selectTableColumns(catalogByCategory, enabledMap) {
  const known = Object.keys(catalogByCategory);
  const ordered = CATEGORY_ORDER.filter(c => known.includes(c))
    .concat(known.filter(c => !CATEGORY_ORDER.includes(c)));
  const cols = [];
  for (const cat of ordered) {
    for (const m of (catalogByCategory[cat] || [])) {
      if (enabledMap[m.id] === true) cols.push(m);
    }
  }
  return cols;
}

/* UI-only: Default-Horizonte. Heute immer an; Morgen ab Prio 50;
 * Übermorgen ab Prio 75. Spiegelt die Heuristik der Sandbox-Variante,
 * nicht das Backend (das hat HORIZONS_ALL als Default). */
function metricsDefaultHorizons(metricIds) {
  const map = {};
  for (const id of metricIds) {
    const prio = METRIC_PRIORITY[id] ?? 0;
    map[id] = { today: true, tomorrow: prio >= 50, day_after: prio >= 75 };
  }
  return map;
}

/* UI-only: Default Score-Beitrag (Ort/Abo-Kontext). True ab Prio 60. */
function metricsDefaultScore(metricIds) {
  const map = {};
  for (const id of metricIds) {
    map[id] = (METRIC_PRIORITY[id] ?? 0) >= 60;
  }
  return map;
}

/* UI-only: Demo-Werte für die Channel-Strip-Vorschau. */
const METRICS_SAMPLE_VALUES = ["12", "8.5", "22", "44", "0.2", "62", "hoch", "klar", "5"];
function sampleMetricValue(i) { return METRICS_SAMPLE_VALUES[i] || "—"; }


/* ════════════════════ PresetRail ════════════════════
 * Linke Spalte des Metrics-Editors. Listet alle Wetter-Profile (Builtin +
 * User-Eigene), markiert das aktive, bietet einen „Eigenes Profil speichern"-
 * Block am Ende. Verwendet kein Brand-Element selbst — die ganze Sidebar-
 * Frage ist eine Schicht höher (BrandSidebar).
 */
function PresetRail({ presets = PRESETS, value, onChange, totalActive = 0, onSave, compact = false }) {
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
  showLimitMarkers, compact, channels = CHANNEL_LIMITS,
  catalogById = METRIC_BY_ID,
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
              {channels.filter(c => c.max > 0 && Number.isFinite(c.max)).map(c => (
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
              isSignalLimit={bucket === "primary" && i === PRIMARY_SLOTS - 1}
              isOverLimit={bucket === "primary" && i >= PRIMARY_SLOTS}
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
function MetricOffShelf({ items = [], onAdd, compact = false, catalog = METRIC_CATALOG, defaultOpen = false, categoryLabels = CATEGORY_LABELS, categoryOrder = CATEGORY_ORDER }) {
  const [open, setOpen] = React.useState(defaultOpen);
  /* Nach Kategorie (Production-IDs) bucketsorten — Reihenfolge folgt
   * CATEGORY_ORDER, unbekannte Kategorien hinten. */
  const grouped = catalog
    .filter(m => items.includes(m.id))
    .reduce((acc, m) => {
      const cat = m.category || m.group || "sonstige";
      (acc[cat] = acc[cat] || []).push(m);
      return acc;
    }, {});
  const orderedCats = [
    ...categoryOrder.filter(c => grouped[c]),
    ...Object.keys(grouped).filter(c => !categoryOrder.includes(c)),
  ];

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
          {orderedCats.map(cat => (
            <div key={cat} style={{ marginTop: 14 }}>
              <div className="mono" style={{
                fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase",
                color: "var(--g-ink-3)", fontWeight: 600, marginBottom: 6,
              }}>{categoryLabels[cat] || cat}</div>
              <div style={{
                display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 6,
              }}>
                {grouped[cat].map(m => (
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
                               catalogById = METRIC_BY_ID, channels = CHANNEL_LIMITS }) {
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
            sampleVal={sampleMetricValue}
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
function MetricsEditorContextBar({ context = "trip", preset, buckets, horizons, score, compact = false }) {
  const ctxLabel = {
    trip: "Trip-Kontext",
    ort:  "Ort-Kontext (im Orts-Vergleich)",
    abo:  "Abo-Kontext (regelmäßiger Vergleich)",
  }[context];

  const ctxDesc = {
    trip: "Briefing-Spalten pro Etappe · Horizonte HEUTE / MORGEN / ÜBERMORGEN pro Metrik wählbar.",
    ort:  "Briefing-Spalten pro Ort · keine Horizonte (Orte haben kein Etappen-Datum) · Metrik kann in den Score einfließen.",
    abo:  "Spalten pro Eintrag im Abo-Vergleich · keine Horizonte · Score-Beitrag pro Metrik konfigurierbar.",
  }[context];

  const horiCount = context === "trip" && horizons
    ? Object.values(horizons).reduce((acc, h) =>
        acc + (h?.today ? 1 : 0) + (h?.tomorrow ? 1 : 0) + (h?.day_after ? 1 : 0), 0)
    : 0;
  const scoreCount = context !== "trip" && score
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
        {context === "trip"
          ? <Stat label="Horizont-Slots" value={horiCount} size="md" mono tone="accent"/>
          : <Stat label="Im Score"        value={scoreCount} size="md" mono tone="accent"/>}
      </div>
    </div>
  );
}


/* ════════════════════ MetricsEditor ════════════════════
 * DIE konsolidierte Editor-Organism. Eine Komponente, drei Kontexte:
 *   context="trip"  → mit HEUTE / MORGEN / ÜBERMORGEN pro Metrik
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
  context = "trip",
  initialPresetId = "alpine",
  compact = false,
  showPresetRail = true,
  showChannelPreview = true,
  onSavePreset,
}) {
  const [presetId, setPresetId] = React.useState(initialPresetId);
  const preset = PRESETS.find(p => p.id === presetId) || PRESETS[0];

  const [buckets, setBuckets] = React.useState(() => metricsAutoAssign(preset.metrics));
  const [horizons, setHorizons] = React.useState(() => metricsDefaultHorizons(preset.metrics));
  const [score, setScore] = React.useState(() => metricsDefaultScore(preset.metrics));
  const [mode, setMode] = React.useState({
    wind: "indicator", gust: "indicator", thunder: "indicator",
    rain_probability: "indicator", visibility: "indicator", cloud_total: "indicator",
  });

  React.useEffect(() => {
    setBuckets(metricsAutoAssign(preset.metrics));
    setHorizons(metricsDefaultHorizons(preset.metrics));
    setScore(metricsDefaultScore(preset.metrics));
  }, [presetId]);

  const all = [...buckets.primary, ...buckets.secondary];
  const off = METRIC_CATALOG.filter(m => !all.includes(m.id)).map(m => m.id);

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
          presets={PRESETS}
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
          hint={context === "trip"
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
      <button onClick={() => onMode && onMode("indicator")} style={btn(mode === "indicator")}>Einfach</button>
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

/* MEHorizonChip — Slot-Toggle für HEUTE/MORGEN/ÜBERMORGEN. Nur im Trip-Kontext sichtbar. */
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
 *   (Index nur in primary; HEUTE/MORGEN/ÜBM nur in context="trip")
 *
 * Die SignalLimit-Trennlinie (ab Index 6 in primary) wird über der
 * Zeile gerendert, nicht innerhalb — sonst landet sie zwischen Border und
 * Zeile und bricht das Raster.
 */
function MetricEditorRow({
  metric, index, bucket, context = "trip",
  isFirst, isLast, isSignalLimit, isOverLimit,
  horizon, inScore, mode, onHorizon, onScore, onMode, onMove, onReorder,
  compact,
}) {
  if (!metric) return null;
  const showIndex = bucket === "primary";
  const isTrip = context === "trip";
  const hasIndicator = metric.hasIndicator;

  const cols = (() => {
    if (showIndex) {
      return isTrip
        ? "28px 1fr 220px 130px 110px 70px"   // idx · meta · horizon-chips · mode · move · reorder
        : "28px 1fr 86px 130px 110px 70px";   // idx · meta · score · mode · move · reorder
    }
    return isTrip
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
          ↓ ab hier bei <strong>Signal</strong> automatisch als Detail-Zeile (max {CHANNEL_BUDGET.signal} Spalten)
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

        {isTrip ? (
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
  metricLookup = METRIC_BY_ID,
  sampleVal = sampleMetricValue,
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
            {isSMS ? "flach" : `${inTable.length}/${Number.isFinite(channel.max) ? channel.max : "∞"} Sp`}
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


/* ════════════════════ MetricCheckbox ════════════════════
 *
 *  Tap-Row für eine einzelne Metrik. Production-Decomposition (Phase 2,
 *  Issues #174–178): das Enable/Disable einer Metrik passiert via
 *  klassischer Checkbox + optional einem Indicator-Toggle. Wir nutzen
 *  diese Komponente hier in MetricOffShelf-Alternativen und in
 *  Quick-Selector-Templates (kategorie-flat).
 *
 *  Props:
 *    metric        Pflicht — Eintrag aus METRIC_CATALOG
 *    checked       boolean
 *    onToggle      Klick auf Checkbox/Row → toggle enable
 *    friendly      boolean — true = Indikator, false = Rohwert
 *                  (nur sichtbar wenn metric.hasIndicator)
 *    onFriendly    Klick auf Roh|Skala-Pille
 *    compact       kleinere Schrift
 *    showCategory  Default false; wenn true wird die Category-Label
 *                  als sehr kleine Mono-Caption rechts neben dem Namen
 *                  angezeigt (Quick-Selector).
 */
function MetricCheckbox({
  metric,
  checked = false,
  onToggle,
  friendly = false,
  onFriendly,
  compact = false,
  showCategory = false,
}) {
  if (!metric) return null;
  const canIndicate = metric.hasIndicator;
  return (
    <label style={{
      display: "grid",
      gridTemplateColumns: canIndicate ? "20px 1fr auto" : "20px 1fr",
      gap: 10, alignItems: "center",
      padding: compact ? "7px 10px" : "9px 12px",
      borderRadius: "var(--g-r-2)",
      cursor: "pointer",
      background: checked ? "var(--g-card-alt)" : "transparent",
      border: "1px solid",
      borderColor: checked ? "var(--g-rule)" : "var(--g-rule-soft)",
      transition: "background 120ms, border-color 120ms",
    }}>
      <input
        type="checkbox"
        checked={checked}
        onChange={(e) => onToggle && onToggle(e.target.checked)}
        style={{ accentColor: "var(--g-accent)", margin: 0, cursor: "pointer" }}
      />
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontSize: compact ? 12.5 : 13.5,
          fontWeight: checked ? 600 : 500,
          color: checked ? "var(--g-ink)" : "var(--g-ink-2)",
          display: "flex", gap: 8, alignItems: "baseline",
        }}>
          <span>{metric.label}</span>
          {showCategory && (
            <span className="mono" style={{
              fontSize: 9.5, color: "var(--g-ink-4)",
              letterSpacing: "0.06em", textTransform: "uppercase",
            }}>{(CATEGORY_LABELS[metric.category] || metric.category)}</span>
          )}
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 1 }}>
          {metric.unit || "—"} · {metric.short}
        </div>
      </div>
      {canIndicate && (
        <button
          type="button"
          onClick={(e) => {
            e.preventDefault();
            e.stopPropagation();
            onFriendly && onFriendly(!friendly);
          }}
          disabled={!checked}
          style={{
            padding: "3px 9px", fontSize: 10, fontWeight: 600,
            fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em",
            borderRadius: 999, cursor: checked ? "pointer" : "not-allowed",
            opacity: checked ? 1 : 0.35,
            background: friendly ? "var(--g-accent-tint)" : "transparent",
            color: friendly ? "var(--g-accent-deep)" : "var(--g-ink-3)",
            border: friendly ? "1px solid var(--g-accent)" : "1px solid var(--g-rule)",
            whiteSpace: "nowrap",
          }}
          title={INDICATOR_MAP[metric.id] || ""}
        >
          {friendly ? "EINFACH" : "ROH"}
        </button>
      )}
    </label>
  );
}


/* ════════════════════ Kanonische ↔ Legacy-Aliase ════════════════════
 *
 *  Production-Decomposition (drift-table item 7) verwendet die
 *  englischen Namen WeatherMetricsTab / MetricGroup / ChannelPreviewBlock.
 *  Die alten Namen MetricsEditor / MetricBucket / ChannelPreviewStrip
 *  bleiben als Aliase, damit Konsumenten ohne harten Schnitt migrieren
 *  können (`screen-design-system.jsx`, Komponenten-Showcase).
 */
const WeatherMetricsTab    = MetricsEditor;
const MetricGroup          = MetricBucket;
const ChannelPreviewBlock  = ChannelPreviewStrip;

/* WETTER_*-Daten-Aliase. Werden zugleich exportiert (siehe unten),
 * damit alte Imports aus screen-* weiterhin funktionieren. */
const WETTER_METRICS_CATALOG = METRIC_CATALOG;
const WETTER_METRIC_BY_ID    = METRIC_BY_ID;
const WETTER_PRESETS         = PRESETS;
const WETTER_CHANNELS        = CHANNEL_LIMITS;
const wetterAutoAssign       = metricsAutoAssign;
const wetterDefaultHorizons  = metricsDefaultHorizons;
const wetterDefaultScore     = metricsDefaultScore;
const sampleWetterValue      = sampleMetricValue;


/* ════════════════════ Export ════════════════════ */
Object.assign(window, {
  /* Daten — kanonisch (Production-Schema) */
  METRIC_CATALOG, METRIC_BY_ID, METRIC_PRIORITY, METRICS_BY_CATEGORY,
  CATEGORY_ORDER, CATEGORY_LABELS, INDICATOR_MAP,
  PRIMARY_SLOTS, CHANNEL_BUDGET, CHANNEL_LIMITS, PRESETS,
  /* Helpers — kanonisch */
  applyChannel,
  metricsAutoAssign, metricsMove, metricsReorder,
  channelOverflow, indicatorCapable,
  buildBucketSummary, buildPresetSummary, selectTableColumns,
  countActiveInCategory,
  metricsDefaultHorizons, metricsDefaultScore, sampleMetricValue,
  /* Sub-Komponenten */
  MetricEditorRow, MetricCheckbox, ChannelLimitChip, ChannelPreviewCard,
  /* Organisms — kanonische Namen */
  PresetRail, MetricGroup, MetricOffShelf, ChannelPreviewBlock,
  MetricsEditorContextBar, WeatherMetricsTab,
  /* Legacy-Aliase (alte Sandbox-Konsumenten — bei nächstem Touch migrieren) */
  WETTER_METRICS_CATALOG, WETTER_METRIC_BY_ID, WETTER_PRESETS, WETTER_CHANNELS,
  wetterAutoAssign, wetterDefaultHorizons, wetterDefaultScore, sampleWetterValue,
  MetricBucket, ChannelPreviewStrip, MetricsEditor,
});
