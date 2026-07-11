/* Mock-Daten für Ortsvergleich-Modul. */

const MOCK_LOCATIONS = [
  { id: "loc-01", name: "Hintertuxer Gletscher",      group: "Zillertal",   tags: ["Zillertal", "Gletscher", "Wochenende"], lat: 47.0789, lon: 11.6856, elev: 3250, focus: "wintersport-glacier", source: "komoot" },
  { id: "loc-02", name: "Übergangsjoch (Zillertal Arena)", group: "Zillertal",  tags: ["Zillertal", "Wochenende", "Powder"],  lat: 47.2345, lon: 12.0567, elev: 2500, focus: "wintersport",      source: "manual" },
  { id: "loc-03", name: "Geisbergalm (Zillertal Arena)",   group: "Zillertal",  tags: ["Zillertal", "Familie"],               lat: 47.2401, lon: 12.0712, elev: 1850, focus: "wintersport",      source: "komoot" },
  { id: "loc-04", name: "Hochfügen",                  group: "Zillertal",   tags: ["Zillertal", "Wochenende"],            lat: 47.2643, lon: 11.8521, elev: 1500, focus: "wintersport",       source: "google-maps" },
  { id: "loc-05", name: "Bergstation Hochfügen",      group: "Zillertal",   tags: ["Zillertal", "Powder"],                lat: 47.2618, lon: 11.8489, elev: 2100, focus: "wintersport",       source: "manual-coords" },
  { id: "loc-06", name: "Profil Test",                group: "Test",        tags: ["Test"],                                lat: 47.0000, lon: 11.0000, elev: 1200, focus: "alpine-touring",    source: "manual" },
  { id: "loc-07", name: "Hochkönig / Aberg",          group: "Hochkönig",   lat: 47.4200, lon: 13.0700, elev: 1900, focus: "wintersport",       source: "komoot" },
  { id: "loc-08", name: "Hochkönig / Maria Alm",      group: "Hochkönig",   lat: 47.3961, lon: 12.9061, elev: 800,  focus: "wintersport",       source: "komoot" },
  { id: "loc-09", name: "Hochkönig / Mühlbach",       group: "Hochkönig",   lat: 47.3614, lon: 13.0339, elev: 855,  focus: "wintersport",       source: "komoot" },
  { id: "loc-10", name: "Hochkönig / Sonnberg",       group: "Hochkönig",   lat: 47.3850, lon: 12.9890, elev: 1300, focus: "wintersport",       source: "komoot" },
  { id: "loc-11", name: "Serfaus Schöngamp Berg",     group: "Tirol West",  lat: 47.0289, lon: 10.6028, elev: 2000, focus: "wintersport",       source: "komoot" },
  { id: "loc-12", name: "Serfaus Stadt",              group: "Tirol West",  lat: 47.0400, lon: 10.5900, elev: 1430, focus: "wintersport",       source: "komoot" },
  { id: "loc-13", name: "Pollença",                   group: "Mallorca",    lat: 39.8767, lon: 3.0167,  elev: 50,   focus: "trail-running",     source: "komoot" },
  { id: "loc-14", name: "Valdemossa",                 group: "Mallorca",    lat: 39.7117, lon: 2.6228,  elev: 437,  focus: "hiking",            source: "komoot" },
  { id: "loc-15", name: "GR20 Corsica Test",          group: "Test",        lat: 42.1500, lon: 9.1500,  elev: 1800, focus: "alpine-touring",    source: "manual" },
  { id: "loc-16", name: "GR20 Test Corsica",          group: "Test",        lat: 42.2000, lon: 9.2000,  elev: 2100, focus: "alpine-touring",    source: "google-maps" },
  { id: "loc-17", name: "Drei-Zinnen-Hütte",          group: "Dolomiten",   lat: 46.6181, lon: 12.3050, elev: 2405, focus: "hiking",            source: "komoot" },
  { id: "loc-18", name: "Seceda",                     group: "Dolomiten",   lat: 46.6056, lon: 11.7167, elev: 2519, focus: "hiking",            source: "komoot" },
  { id: "loc-19", name: "Tre Cime di Lavaredo",       group: "Dolomiten",   lat: 46.6186, lon: 12.3047, elev: 2999, focus: "hiking",            source: "komoot" },
];

// Score-Modell für Compare-Ranking (6 Standorte, Score 0–100)
const MOCK_COMPARE_ROWS = [
  { id: "loc-01", rank: 1, score: 82, snow: 305, newSnow: 12, wind: 7,  gust: 14, dir: "S",  feels: -2, sun: 2.0, cloud: 40, cloudTag: "über",   cloudBest: true,  tempMax: 1 },
  { id: "loc-02", rank: 2, score: 76, snow: 138, newSnow: 8,  wind: 10, gust: 26, dir: "SW", feels:  4, sun: 4.0, cloud: 23, cloudTag: "über",   cloudBest: true,  tempMax: 8 },
  { id: "loc-05", rank: 3, score: 64, snow: 95,  newSnow: 4,  wind: 9,  gust: 22, dir: "SW", feels:  1, sun: 1.5, cloud: 60, cloudTag: "in",     cloudBest: false, tempMax: 5 },
  { id: "loc-04", rank: 4, score: 51, snow: 70,  newSnow: 0,  wind: 7,  gust: 14, dir: "S",  feels: -2, sun: 0.5, cloud: 82, cloudTag: "in",     cloudBest: false, tempMax: 3 },
  { id: "loc-06", rank: 5, score: 40, snow: null, newSnow: null, wind: 11, gust: 29, dir: "W",  feels:  7, sun: 0,   cloud: 52, cloudTag: "klar",   cloudBest: false, tempMax: 11 },
  { id: "loc-03", rank: 6, score: 32, snow: null, newSnow: null, wind: 12, gust: 30, dir: "W",  feels:  8, sun: 0,   cloud: 66, cloudTag: "in",     cloudBest: false, tempMax: 9 },
  /* Hochkönig-Orte (Vergleich „Skitouren Hochkönig") — neutrale Werte, kein Ranking */
  { id: "loc-07", rank: null, score: null, snow: 145, newSnow: 18, wind: 12, gust: 24, dir: "NW", feels: -4, sun: 3.5, cloud: 35, cloudTag: "über", cloudBest: true,  tempMax: 0 },
  { id: "loc-08", rank: null, score: null, snow: 35,  newSnow: 2,  wind: 8,  gust: 15, dir: "W",  feels:  3, sun: 2.0, cloud: 70, cloudTag: "in",   cloudBest: false, tempMax: 6 },
  { id: "loc-09", rank: null, score: null, snow: 55,  newSnow: 6,  wind: 22, gust: 41, dir: "SW", feels: -1, sun: 1.0, cloud: 85, cloudTag: "in",   cloudBest: false, tempMax: 4 },
  { id: "loc-10", rank: null, score: null, snow: 90,  newSnow: 11, wind: 15, gust: 28, dir: "NW", feels: -3, sun: 3.0, cloud: 45, cloudTag: "über", cloudBest: true,  tempMax: 1 },
];

// Stundenverlauf für Top-N Locations
const MOCK_COMPARE_HOURS = {
  "loc-01": [
    { h: "09", t:  0, prec: null, w: 4,  g: 6,  d: "S",  cloud: "few"  },
    { h: "10", t:  0, prec: null, w: 5,  g: 9,  d: "SW", cloud: "few"  },
    { h: "11", t:  1, prec: null, w: 7,  g: 12, d: "SW", cloud: "few"  },
    { h: "12", t:  1, prec: null, w: 7,  g: 14, d: "S",  cloud: "many" },
    { h: "13", t:  0, prec: 0.1,  w: 7,  g: 12, d: "S",  cloud: "snow" },
    { h: "14", t:  0, prec: 0.1,  w: 6,  g: 14, d: "SE", cloud: "snow" },
    { h: "15", t:  1, prec: 0.1,  w: 3,  g: 14, d: "SW", cloud: "snow" },
    { h: "16", t:  0, prec: 0.1,  w: 2,  g: 5,  d: "S",  cloud: "few"  },
  ],
  "loc-02": [
    { h: "09", t:  6, prec: null, w: 5,  g: 14, d: "SW", cloud: "few"  },
    { h: "10", t:  7, prec: null, w: 6,  g: 17, d: "SW", cloud: "few"  },
    { h: "11", t:  8, prec: null, w: 5,  g: 21, d: "W",  cloud: "few"  },
    { h: "12", t:  7, prec: 0.1,  w: 10, g: 26, d: "NW", cloud: "some" },
    { h: "13", t:  8, prec: null, w: 6,  g: 20, d: "SW", cloud: "few"  },
    { h: "14", t:  6, prec: 0.2,  w: 7,  g: 25, d: "SW", cloud: "some" },
    { h: "15", t:  6, prec: null, w: 5,  g: 15, d: "SE", cloud: "many" },
    { h: "16", t:  7, prec: null, w: 4,  g: 12, d: "SW", cloud: "many" },
  ],
  "loc-05": [
    { h: "09", t:  4, prec: null, w: 6,  g: 14, d: "SW", cloud: "some" },
    { h: "10", t:  4, prec: null, w: 7,  g: 17, d: "SW", cloud: "some" },
    { h: "11", t:  5, prec: 0.2,  w: 8,  g: 20, d: "W",  cloud: "many" },
    { h: "12", t:  5, prec: 0.4,  w: 9,  g: 22, d: "NW", cloud: "snow" },
    { h: "13", t:  4, prec: 0.5,  w: 7,  g: 18, d: "SW", cloud: "snow" },
    { h: "14", t:  4, prec: 0.2,  w: 6,  g: 16, d: "SW", cloud: "many" },
    { h: "15", t:  3, prec: null, w: 5,  g: 12, d: "SE", cloud: "many" },
    { h: "16", t:  3, prec: null, w: 4,  g: 10, d: "SW", cloud: "many" },
  ],
  "loc-04": [
    { h: "09", t:  0, prec: null, w: 4,  g: 6,  d: "S",  cloud: "many" },
    { h: "10", t:  0, prec: null, w: 5,  g: 9,  d: "SW", cloud: "many" },
    { h: "11", t:  1, prec: null, w: 7,  g: 12, d: "SW", cloud: "many" },
    { h: "12", t:  1, prec: null, w: 7,  g: 14, d: "S",  cloud: "many" },
    { h: "13", t:  0, prec: 0.1,  w: 7,  g: 12, d: "S",  cloud: "snow" },
    { h: "14", t:  0, prec: 0.1,  w: 6,  g: 14, d: "SE", cloud: "snow" },
    { h: "15", t:  1, prec: 0.1,  w: 3,  g: 14, d: "SW", cloud: "snow" },
    { h: "16", t:  0, prec: 0.1,  w: 2,  g: 5,  d: "S",  cloud: "many" },
  ],
};

const MOCK_COMPARE_PRESETS = [
  { id: "p1", name: "Skitouren Wochenende",    locations: 5, profile: "Wintersport", schedule: "07:00 · 18:00",  active: true,  channels: ["email"] },
  { id: "p2", name: "Zillertal-Lift täglich",  locations: 4, profile: "Wintersport", schedule: "07:00 · 18:00", active: true,  channels: ["email", "telegram"] },
  { id: "p3", name: "Mallorca Trail",          locations: 3, profile: "Trail-Running", schedule: "06:00 · 18:00", active: false, channels: ["email"] },
];

const LOCATION_ACTIVITY_PROFILES = [
  { id: "wintersport",        label: "Wintersport (Piste)",  metrics: ["Schnee", "Neuschnee", "Wind", "Sicht"] },
  { id: "wintersport-glacier",label: "Wintersport · Gletscher", metrics: ["Schnee", "Wind", "Temp", "0°-Linie"] },
  { id: "alpine-touring",     label: "Skitour / Alpin",       metrics: ["Wind", "Lawine", "Sicht", "Sonne"] },
  { id: "hiking",             label: "Hochtour / Wandern",    metrics: ["Niederschlag", "Wind", "Gewitter", "Temp"] },
  { id: "trail-running",      label: "Trail-Running",         metrics: ["Temp", "UV", "Niederschlag"] },
];

/* ─────────────────────────────────────────────────────────────────────
 * Orts-Vergleich-Abos — Single-Source für Home-Kacheln + Detail-Seite.
 * Bezieht sich auf MOCK_LOCATIONS via locationIds. Spiegelt CL_COMPARE_LIST
 * (screen-compare-list.jsx), reichert es aber um Setup-Detail an:
 * Idealwerte, Layout pro Kanal, Monitoring-Status.
 *
 * Modell (PO 2026-07-11): ein Vergleich ist ein STEHENDER MONITOR — kein
 * Proto-Trip. Kein Enddatum-Zwang, läuft bis pausiert/gelöscht. Versand wie
 * beim Trip: nur Briefing-Uhrzeiten (Morgen-Briefing = heutiger Tag,
 * Abend-Briefing = morgen). KEIN rollierendes Zeitfenster, kein Rhythmus
 * (PO 2026-07-11 verworfen). Kein Score, kein Ranking (PO 2026-07-08):
 * layout[channel] sind die METRIK-ZEILEN der Übersicht (Orte = Spalten,
 * CompareEmailV2). ideals.weight = Priorität (was zuerst in die Übersicht
 * kommt), NICHT Ranking-Gewicht.
 * ───────────────────────────────────────────────────────────────────── */
const MOCK_COMPARE_SUBS = [
  {
    id: "skitour-hochkoenig",
    name: "Skitouren Hochkönig",
    region: "Hochkönig · Salzburger Land",
    profileId: "wintersport",
    profileLabel: "Wintersport (Piste)",
    status: "active",
    locationIds: ["loc-07", "loc-08", "loc-09", "loc-10", "loc-01"],
    channels: ["email", "telegram"],
    schedule: "Morgen 06:30 · Abend 18:00",
    nextSend: "morgen · 06:30",
    lastSent: "heute · 06:30",
    health: "ok",
    ideals: [
      { metric: "Neuschnee",    ideal: "≥ 10 cm",     weight: "hoch" },
      { metric: "Wind / Böen",  ideal: "≤ 15 km/h",   weight: "hoch" },
      { metric: "Sicht",        ideal: "klar / über Wolken", weight: "mittel" },
      { metric: "Temperatur",   ideal: "−8 … 0 °C",   weight: "niedrig" },
    ],
    layout: {
      email:    ["Neuschnee", "Schnee ges.", "Wind / Böen", "Sicht", "Temp"],
      telegram: ["Neuschnee", "Wind", "Sicht"],
      sms:      [],
    },
  },
  {
    id: "skigebiete-vergleich",
    name: "Skigebiete-Vergleich",
    region: "Alpen-Hauptkamm",
    profileId: "wintersport-glacier",
    profileLabel: "Wintersport · Gletscher",
    status: "active",
    locationIds: ["loc-01", "loc-02", "loc-11", "loc-12"],
    channels: ["email"],
    schedule: "Morgen 07:00 · Abend 18:00",
    nextSend: "morgen · 07:00",
    lastSent: "heute · 07:00",
    health: "ok",
    ideals: [
      { metric: "Schnee gesamt", ideal: "≥ 80 cm",   weight: "hoch" },
      { metric: "Wind",          ideal: "≤ 20 km/h", weight: "mittel" },
      { metric: "Temperatur",    ideal: "≤ 0 °C",    weight: "mittel" },
      { metric: "0°-Grenze",     ideal: "≤ 1500 m",  weight: "niedrig" },
    ],
    layout: {
      email:    ["Schnee ges.", "Neuschnee", "Wind", "Temp", "0°-Grenze"],
      telegram: ["Schnee ges.", "Wind"],
      sms:      [],
    },
  },
  {
    id: "mallorca-trail",
    name: "Mallorca Trail",
    region: "Tramuntana",
    profileId: "trail-running",
    profileLabel: "Trail-Running",
    status: "paused",
    locationIds: ["loc-13", "loc-14"],
    channels: ["email", "telegram"],
    schedule: "Morgen 07:00 · Abend 18:00",
    nextSend: "—",
    lastSent: "vor 3 Wochen",
    health: "paused",
    ideals: [
      { metric: "Temperatur",   ideal: "10 … 20 °C", weight: "hoch" },
      { metric: "Niederschlag", ideal: "0 mm",       weight: "hoch" },
      { metric: "UV-Index",     ideal: "≤ 6",        weight: "niedrig" },
    ],
    layout: {
      email:    ["Temp", "Niederschlag", "UV", "Wind"],
      telegram: ["Temp", "Niederschlag"],
      sms:      [],
    },
  },
  {
    id: "wanderung-dolomiten",
    name: "Wanderungen Dolomiten",
    region: "Dolomiten",
    profileId: "hiking",
    profileLabel: "Hochtour / Wandern",
    status: "draft",
    locationIds: ["loc-17", "loc-18", "loc-19"],
    channels: [],
    schedule: "—",
    nextSend: "—",
    lastSent: "—",
    health: "draft",
    ideals: [
      { metric: "Niederschlag", ideal: "0 mm",       weight: "hoch" },
      { metric: "Gewitter",     ideal: "kein Risiko", weight: "hoch" },
      { metric: "Wind",         ideal: "≤ 25 km/h",  weight: "mittel" },
      { metric: "Temperatur",   ideal: "8 … 18 °C",  weight: "niedrig" },
    ],
    layout: {
      email:    ["Niederschlag", "Gewitter", "Wind", "Temp"],
      telegram: ["Niederschlag", "Gewitter"],
      sms:      [],
    },
  },
];

window.MOCK_COMPARE_SUBS = MOCK_COMPARE_SUBS;
window.MOCK_LOCATIONS = MOCK_LOCATIONS;
window.MOCK_COMPARE_ROWS = MOCK_COMPARE_ROWS;
window.MOCK_COMPARE_HOURS = MOCK_COMPARE_HOURS;
window.MOCK_COMPARE_PRESETS = MOCK_COMPARE_PRESETS;
window.LOCATION_ACTIVITY_PROFILES = LOCATION_ACTIVITY_PROFILES;
