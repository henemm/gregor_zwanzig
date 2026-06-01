/* Mock-Daten für die V2-Designs.
 * Echte Datenstruktur basiert auf Repo (Trip → Stages → Waypoints).
 */

const MOCK_TRIP = {
  id: "khw-403",
  name: "KHW 403 — Karnischer Höhenweg",
  shortName: "KHW 403",
  status: "active",
  startDate: "2026-05-06",
  endDate: "2026-05-17",
  totalKm: 142.6,
  totalAscent: 7820,
  totalDescent: 7340,
  maxElev: 2772,
  region: "Karnische Alpen, AT/IT",
  activityProfile: "summer-trekking",
  participants: [
    { name: "Gregor Henemm", initials: "GH", color: "#c45a2a" },
    { name: "Steffi Klein",  initials: "SK", color: "#3d6b3a" },
    { name: "Max Reber",     initials: "MR", color: "#2c5a8c" },
  ],
  channels: [
    { kind: "email",    target: "gregor_zwanzig@henemm.com", primary: true },
    { kind: "signal",   target: "+49 170 …",                  primary: false },
    { kind: "telegram", target: "@gregorh",                   primary: false },
  ],
  reports: {
    morning: { time: "06:00", enabled: true,  channels: ["email", "signal"] },
    evening: { time: "18:00", enabled: true,  channels: ["email"] },
    alert:   { enabled: true, channels: ["signal", "email"] },
  },
  alertThresholds: {
    windGust: 50,        // km/h
    rain: 10,            // mm/h
    thunderProb: 40,     // %
    snowLineDelta: -200, // m unter Trip-Höhe
  },
  stages: [
    {
      id: "khw-00a", code: "KHW_00a", title: "Von Toblach Bhf nach Helmhotel",
      date: "2026-05-06", km: 9.3, ascent: 203, descent: 270, maxElev: 1413,
      profile: [1211, 1240, 1280, 1290, 1210, 1300, 1413, 1350, 1280, 1200, 1144],
      waypoints: [
        { name: "Start", type: "start",   lat: 46.724754, lon: 12.225424, elev: 1211, ai: false, time: "08:00" },
        { name: "Gipfel", type: "summit", lat: 46.727633, lon: 12.286008, elev: 1210, ai: true,  time: "10:00" },
        { name: "Seg 3 Start", type: "pass", lat: 46.717835, lon: 12.326463, elev: 1413, ai: true, time: "11:40" },
        { name: "Ziel",  type: "end",     lat: 46.730420, lon: 12.321643, elev: 1144, ai: false, time: "12:45" },
      ],
      summary: "8–12°C, ☁, trocken, Regen ab 11:00, schwacher Wind NE 12 km/h, Böen bis 25 km/h ab 17:00",
      risk: "low",
    },
    {
      id: "khw-00b", code: "KHW_00b", title: "Von Helmhotel nach Sillianer Hütte",
      date: "2026-05-07", km: 12.4, ascent: 1235, descent: 0, maxElev: 2377,
      profile: [1142, 1300, 1500, 1700, 1866, 2050, 2236, 2200, 2280, 2350, 2377],
      waypoints: [
        { name: "Start",  type: "start", lat: 46.730420, lon: 12.321643, elev: 1142, ai: false, time: "07:30" },
        { name: "Seg 2 Start", type: "pass",   lat: 46.715522, lon: 12.336089, elev: 1500, ai: true, time: "09:15" },
        { name: "Seg 3 Start", type: "summit", lat: 46.714237, lon: 12.356389, elev: 1866, ai: true, time: "11:00" },
        { name: "Seg 4 Start", type: "summit", lat: 46.712507, lon: 12.383926, elev: 2236, ai: true, time: "13:30" },
        { name: "Ziel (Sillianer Hütte)", type: "hut", lat: 46.706056, lon: 12.406271, elev: 2377, ai: false, time: "15:00" },
      ],
      summary: "-1–13°C, ☁, mäßiger Regen max 19:00, schwacher Wind W 11 km/h, Böen bis 35 km/h ab 15:00, ⚡ möglich 15:00–16:00",
      risk: "med",
    },
    {
      id: "khw-01", code: "KHW_01", title: "Sillianer Hütte nach Obstanserse",
      date: "2026-05-08", km: 13.2, ascent: 540, descent: 480, maxElev: 2640,
      profile: [2377, 2450, 2540, 2640, 2580, 2480, 2400, 2350, 2280, 2200, 2150],
      waypoints: [
        { name: "Start (Sillianer)", type: "hut", lat: 46.706, lon: 12.406, elev: 2377, ai: false, time: "07:00" },
        { name: "Demut-Sattel", type: "pass", lat: 46.694, lon: 12.470, elev: 2640, ai: true,  time: "10:30" },
        { name: "Ziel (Obstansersee Hütte)", type: "hut", lat: 46.681, lon: 12.510, elev: 2150, ai: false, time: "14:00" },
      ],
      summary: "3–9°C, ☁, trocken, schwacher Wind E 4 km/h, Böen bis 15 km/h ab 17:00",
      risk: "low",
    },
    {
      id: "khw-02", code: "KHW_02", title: "Obstansersee-Hütte nach Porzehütte",
      date: "2026-05-09", km: 11.8, ascent: 720, descent: 540, maxElev: 2660,
      profile: [2150, 2280, 2400, 2540, 2660, 2580, 2480, 2400, 2300, 2200, 2150],
      waypoints: [
        { name: "Start", type: "hut", lat: 46.681, lon: 12.510, elev: 2150, ai: false, time: "07:00" },
        { name: "Pfannspitze", type: "summit", lat: 46.674, lon: 12.560, elev: 2660, ai: true, time: "10:00" },
        { name: "Ziel (Porzehütte)", type: "hut", lat: 46.668, lon: 12.620, elev: 1942, ai: false, time: "13:30" },
      ],
      summary: "5–11°C, ☁, Regen ab 15:00, schwacher Wind S 10 km/h, Böen bis 30 km/h ab 16:00",
      risk: "med",
    },
    {
      id: "khw-03", code: "KHW_03", title: "Porzehütte nach Hochweißsteinhaus",
      date: "2026-05-10", km: 14.5, ascent: 980, descent: 760, maxElev: 2772,
      profile: [1942, 2100, 2300, 2500, 2700, 2772, 2680, 2540, 2400, 2280, 2160],
      waypoints: [
        { name: "Start (Porzehütte)", type: "hut", lat: 46.668, lon: 12.620, elev: 1942, ai: false, time: "07:00" },
        { name: "Hochweißstein", type: "summit", lat: 46.658, lon: 12.700, elev: 2772, ai: true, time: "11:00" },
        { name: "Ziel", type: "hut", lat: 46.652, lon: 12.760, elev: 2160, ai: false, time: "15:30" },
      ],
      summary: "3–8°C, ☁, mäßiger Regen max 12:00, schwacher Wind S 10 km/h, Böen bis 47 km/h ab 17:00",
      risk: "high",
    },
  ],
};

const MOCK_TODAY_STAGE = MOCK_TRIP.stages[0];

const MOCK_REPORT_TIMELINE = [
  { when: "Heute 06:00", kind: "morning", channels: ["email","signal"], status: "sent",     etappe: "KHW_00a" },
  { when: "Heute 18:00", kind: "evening", channels: ["email"],          status: "scheduled", etappe: "KHW_00a" },
  { when: "Morgen 06:00", kind: "morning", channels: ["email","signal"], status: "scheduled", etappe: "KHW_00b" },
  { when: "Morgen 18:00", kind: "evening", channels: ["email"],          status: "scheduled", etappe: "KHW_00b" },
];

const MOCK_ALERTS_RECENT = [
  { when: "Heute 14:32", kind: "wind",    msg: "Böen 52 km/h erwartet ab 15:00 (Schwelle 50 km/h)", channel: "signal" },
  { when: "Gestern",     kind: "thunder", msg: "Gewitter-Wahrscheinlichkeit 45% in Etappe KHW_00b", channel: "signal" },
];

const MOCK_ARCHIVED = [
  { id: "gr20-2024", name: "GR20 — Korsika Süd→Nord",     dates: "Sep 2024", stages: 16, status: "completed" },
  { id: "tmb-2023",  name: "TMB — Tour du Mont Blanc",    dates: "Jul 2023", stages: 11, status: "completed" },
  { id: "rmh-2023",  name: "Rosengarten Höhenwanderung",  dates: "Aug 2023", stages: 5,  status: "completed" },
  { id: "haute-23",  name: "Haute Route Chamonix–Zermatt",dates: "Jul 2023", stages: 12, status: "completed" },
  { id: "ahw-22",    name: "Adlerweg Tirol",              dates: "Jul 2022", stages: 9,  status: "completed" },
  { id: "doc-22",    name: "Dolomiten-Höhenweg 1",        dates: "Aug 2022", stages: 8,  status: "completed" },
  { id: "e5-21",     name: "E5 Oberstdorf–Meran",         dates: "Aug 2021", stages: 7,  status: "completed" },
  { id: "wht-20",    name: "West Highland Way",           dates: "Jun 2020", stages: 7,  status: "completed" },
];

const MOCK_SUBSCRIPTION = {
  id: "skitour-vergleich",
  name: "Skitouren — Vergleich Wochenende",
  schedule: "Freitag 18:00",
  forecastHours: 48,
  activityProfile: "wintersport",
  channels: ["email"],
  locations: [
    { name: "Stubai — Wilder Pfaff",     lat: 46.96, lon: 11.21, elev: 3458, score: 0.86, summary: "klar, -8°C, Wind 15 km/h" },
    { name: "Zillertal — Olperer",        lat: 47.02, lon: 11.65, elev: 3476, score: 0.74, summary: "leicht bewölkt, -6°C, Wind 25 km/h" },
    { name: "Ortler-Gruppe — Cevedale",   lat: 46.45, lon: 10.63, elev: 3769, score: 0.71, summary: "klar, -11°C, Wind 35 km/h" },
    { name: "Glockner — Glocknerhaus",    lat: 47.08, lon: 12.83, elev: 2150, score: 0.62, summary: "Schneefall, -5°C, Wind 18 km/h" },
    { name: "Silvretta — Piz Buin",       lat: 46.84, lon: 10.11, elev: 3312, score: 0.58, summary: "bedeckt, -4°C, Wind 28 km/h" },
    { name: "Engelberg — Titlis",         lat: 46.77, lon: 8.43,  elev: 3238, score: 0.51, summary: "Föhn, -3°C, Wind 45 km/h" },
    { name: "Pitztal — Wildspitze",       lat: 46.89, lon: 10.87, elev: 3768, score: 0.48, summary: "Niederschlag, -7°C, Wind 32 km/h" },
    { name: "Verwall — Patteriol",        lat: 47.10, lon: 10.20, elev: 3056, score: 0.42, summary: "Schneefall, -5°C, Wind 22 km/h" },
  ],
};

window.MOCK_TRIP = MOCK_TRIP;
window.MOCK_TODAY_STAGE = MOCK_TODAY_STAGE;
window.MOCK_REPORT_TIMELINE = MOCK_REPORT_TIMELINE;
window.MOCK_ALERTS_RECENT = MOCK_ALERTS_RECENT;
window.MOCK_ARCHIVED = MOCK_ARCHIVED;
window.MOCK_SUBSCRIPTION = MOCK_SUBSCRIPTION;
