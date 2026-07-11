/* ═══════════════════════════════════════════════════════════════════
 *  metric-codes.jsx — SINGLE SOURCE OF TRUTH für Metrik-Kürzel + Token-Logik
 *
 *  Warum: im Projekt existierten DREI divergente Kürzel-Sätze —
 *    · ME_ALL.short          (deutsch:  Temp, Gefühlt, Böen, Regen%, …)
 *    · CP_SMS_TOK            (SMS-Codes: N/D, R, PR, W, G, TH — nur 6 Metriken)
 *    · EmailDataTable-Header (englisch: Time, Temp, Feels, Wind, Gust, …)
 *  Jede neue Ansicht hat bisher wieder neue Kürzel erfunden. Schluss damit.
 *

 *
 *  Zwei Anzeige-Kontexte, ein Katalog (PO-Entscheid 2026-07):
 *    · codeEmail  — E-Mail hat unbegrenzte Breite → lesbarer Kopf
 *                   (Wind, Gust, Rain%, Thndr% …).
 *    · codeShort  — Telegram/SMS/Kurzübersicht sind schmal → terser
 *                   SMS-Code (W, G, PR, TH …). Für Metriken OHNE eigenen
 *                   SMS-Code sind codeEmail === codeShort.
 *  `code` bleibt als Alias auf codeShort erhalten (buildQuickTokens
 *  /-Legend + Alt-Konsumenten). NICHTS ist neu erfunden — jeder Code
 *  stammt aus SMS oder E-Mail.
 *
 *  buildQuickTokens(): die GETEILTE Token-Logik für die SMS-Stil-
 *  Kurzübersicht (ganzer Tag, alle gewählten Metriken). Aggregiert
 *  stündliche Rows je Metrik nach fester Regel. Gedacht als gemeinsame
 *  Quelle für Telegram-Kurzübersicht, SMS-Zeile und Editor-Vorschau.
 *
 *  mcGet(id): tolerant auflösender Resolver — akzeptiert sowohl das
 *  metric-codes-Id-Schema (temp, feels, windDir …) als auch das
 *  Production-Schema aus organisms.jsx (temperature, wind_chill,
 *  wind_direction …) via MC_ALIAS. Unbekannte Ids → Fallback-Objekt
 *  {codeEmail:id, codeShort:id, label:id, unit:""}, damit Tabellenköpfe
 *  nie leer bleiben.
 * ═══════════════════════════════════════════════════════════════════ */

const METRIC_CODES = {
  time:       { label: "Zeit",             unit: "",    codeEmail: "Time",   codeShort: "Time"                  },
  temp:       { label: "Temperatur",       unit: "°",   codeEmail: "Temp",   codeShort: "Temp",  agg: "range" },
  feels:      { label: "Gefühlte Temp.",   unit: "°",   codeEmail: "Feels",  codeShort: "Feels", agg: "range" },
  wind:       { label: "Wind",             unit: "",    codeEmail: "Wind",   codeShort: "W",     agg: "max"   },
  gust:       { label: "Böen",             unit: "",    codeEmail: "Gust",   codeShort: "G",     agg: "maxAt" },
  windDir:    { label: "Windrichtung",     unit: "",    codeEmail: "WindDir",codeShort: "WDir",  agg: "trend" },
  precip:     { label: "Niederschlag",     unit: "mm",  codeEmail: "Rain",   codeShort: "R",     agg: "sum"   },
  rainProb:   { label: "Regenwahrsch.",    unit: "%",   codeEmail: "Rain%",  codeShort: "PR",    agg: "maxAt" },
  thunder:    { label: "Gewitterwahrsch.", unit: "%",   codeEmail: "Thndr%", codeShort: "TH",    agg: "maxAt" },
  visibility: { label: "Sichtweite",       unit: "km",  codeEmail: "Visib",  codeShort: "Visib", agg: "min"   },
  uv:         { label: "UV-Index",         unit: "",    codeEmail: "UV",     codeShort: "UV",    agg: "max"   },
  freezeLine: { label: "Nullgradgrenze",   unit: "m",   codeEmail: "0°Line", codeShort: "0°Line",agg: "range" },
  /* — nicht in der E-Mail-Detailtabelle; im gleichen Stil ergänzt — */
  cloud:      { label: "Bewölkung",        unit: "%",   codeEmail: "Cloud",  codeShort: "Cloud", agg: "range" },
  cloudLow:   { label: "Tiefe Wolken",     unit: "%",   codeEmail: "LowCl",  codeShort: "LowCl", agg: "max"   },
  humidity:   { label: "Luftfeuchtigkeit", unit: "%",   codeEmail: "Humid",  codeShort: "Humid", agg: "range" },
  dewpoint:   { label: "Taupunkt",         unit: "°",   codeEmail: "Dew",    codeShort: "Dew",   agg: "range" },
  sunshine:   { label: "Sonnenschein",     unit: "min", codeEmail: "Sun",    codeShort: "Sun",   agg: "sum"   },
};

/* `code` = Alias auf codeShort — hält buildQuickTokens/-Legend und
 * ältere Konsumenten (m.code) am Leben, ohne zweite Quelle. */
Object.values(METRIC_CODES).forEach(m => { m.code = m.codeShort; });

/* Alt-Id-Schema (organisms.jsx Production-IDs) → metric-codes-Id.
 * Metriken ohne metric-codes-Eintrag (cape, pressure, snow_depth …)
 * fehlen hier bewusst → mcGet fällt tolerant auf den Fallback zurück. */
const MC_ALIAS = {
  temperature: "temp",       wind_chill: "feels",     humidity: "humidity",
  dewpoint: "dewpoint",      wind: "wind",            gust: "gust",
  wind_direction: "windDir", precipitation: "precip", rain_probability: "rainProb",
  thunder: "thunder",        cloud_total: "cloud",    cloud_low: "cloudLow",
  visibility: "visibility",  sunshine: "sunshine",    uv_index: "uv",
  freezing_level: "freezeLine",
};

/* Tolerant auflösender Resolver: metric-codes-Id ODER Production-Id.
 * Unbekannte Ids → Fallback {codeEmail:id, codeShort:id, label:id, unit:""}. */
function mcGet(id) {
  const mcId = METRIC_CODES[id] ? id : MC_ALIAS[id];
  const m = mcId && METRIC_CODES[mcId];
  if (m) return m;
  return { codeEmail: id, codeShort: id, code: id, label: id, unit: "" };
}

function mcFmt(n) {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

/* Baut die SMS-Stil-Kurzübersicht: pro Metrik EIN Token {id, code, value}.
 * rows = stündliche Werte, je Objekt mit den Metrik-Ids als Keys + `time`.
 * Aggregat-Regel steckt in METRIC_CODES[id].agg:
 *   range → min–max · max → Höchst · min → Tiefst · maxAt → Höchst@Std
 *   sum → Summe · trend → erster→letzter Wert. */
function buildQuickTokens(metricIds, rows) {
  return metricIds.map(id => {
    const m = METRIC_CODES[id];
    if (!m || !m.agg) return null;
    const vals  = rows.map(r => r[id]);
    const times = rows.map(r => r.time);
    let value;
    switch (m.agg) {
      case "range": {
        const lo = Math.min(...vals), hi = Math.max(...vals);
        value = lo === hi ? `${mcFmt(lo)}${m.unit}` : `${mcFmt(lo)}–${mcFmt(hi)}${m.unit}`;
        break;
      }
      case "max": value = `${mcFmt(Math.max(...vals))}${m.unit}`; break;
      case "min": value = `${mcFmt(Math.min(...vals))}${m.unit}`; break;
      case "maxAt": {
        let bi = 0; vals.forEach((v, i) => { if (v > vals[bi]) bi = i; });
        value = `${mcFmt(vals[bi])}${m.unit}@${times[bi]}`;
        break;
      }
      case "sum": value = `${mcFmt(vals.reduce((a, b) => a + b, 0))}${m.unit}`; break;
      case "trend": value = `${vals[0]}→${vals[vals.length - 1]}`; break;
      default: value = String(vals[0]);
    }
    return { id, code: m.code, value };
  }).filter(Boolean);
}

/* Kompakte Code→Bedeutung-Legende (für die gewählten Metriken, in Reihenfolge). */
function buildQuickLegend(metricIds) {
  return metricIds
    .map(id => METRIC_CODES[id] && `${METRIC_CODES[id].code} ${METRIC_CODES[id].label}`)
    .filter(Boolean)
    .join(" · ");
}

Object.assign(window, { METRIC_CODES, MC_ALIAS, mcGet, buildQuickTokens, buildQuickLegend, mcFmt });
