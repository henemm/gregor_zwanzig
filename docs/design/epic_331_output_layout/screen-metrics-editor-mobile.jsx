/* Mobile · Wetter-Metriken-Editor
 * Pattern: Preset-Picker oben (H-Scroll), 26 Metriken in 5 Accordions (Kategorien).
 * Sticky Save-Bar unten.
 */

const METRICS_GROUPS_M = [
  {
    group: "Temperatur",
    items: [
      { id: "temp",     label: "Temperatur",        unit: "°C",   on: true },
      { id: "feels",    label: "Gefühlte Temp",     unit: "°C",   on: true },
      { id: "humidity", label: "Luftfeuchtigkeit",  unit: "%",    on: false },
      { id: "dewpoint", label: "Taupunkt",          unit: "°C",   on: false },
      { id: "soilTemp", label: "Bodentemperatur",   unit: "°C",   on: false },
    ],
  },
  {
    group: "Wind",
    items: [
      { id: "wind",    label: "Wind",          unit: "km/h", on: true },
      { id: "gust",    label: "Böen",          unit: "km/h", on: true },
      { id: "windDir", label: "Windrichtung",  unit: "°",    on: true },
    ],
  },
  {
    group: "Niederschlag",
    items: [
      { id: "precip",     label: "Niederschlag",       unit: "mm",   on: true },
      { id: "rainProb",   label: "Regen-Wahrsch.",     unit: "%",    on: true },
      { id: "thunder",    label: "Gewitter-Wahrsch.",  unit: "%",    on: true },
      { id: "cape",       label: "CAPE (Energie)",     unit: "J/kg", on: false },
      { id: "snowfall",   label: "Schneefall",         unit: "cm",   on: true },
      { id: "precipType", label: "Niederschl.-Art",    unit: "",     on: false },
    ],
  },
  {
    group: "Wolken & Sicht",
    items: [
      { id: "cloud",      label: "Bewölkung gesamt",   unit: "%",   on: true },
      { id: "cloudLow",   label: "Tiefe Wolken",       unit: "%",   on: true },
      { id: "cloudMid",   label: "Mittlere Wolken",    unit: "%",   on: false },
      { id: "cloudHigh",  label: "Hohe Wolken",        unit: "%",   on: false },
      { id: "visibility", label: "Sichtweite",         unit: "km",  on: true },
      { id: "sunshine",   label: "Sonnenschein-Dauer", unit: "min", on: false },
    ],
  },
  {
    group: "Sonstiges",
    items: [
      { id: "uv",         label: "UV-Index",           unit: "",   on: true },
      { id: "pressure",   label: "Luftdruck",          unit: "hPa", on: false },
      { id: "freezeLine", label: "Nullgrad-Grenze",    unit: "m",   on: true },
      { id: "snowDepth",  label: "Schneehöhe",         unit: "cm",  on: false },
      { id: "newSnow",    label: "Neuschnee 24h",      unit: "cm",  on: false },
      { id: "radiation",  label: "Globalstrahlung",    unit: "W/m²", on: false },
    ],
  },
];

const PRESETS_M = [
  { id: "alpine",   name: "Alpen-Trekking",  count: 14, active: true },
  { id: "hiking",   name: "Wandern",         count: 9 },
  { id: "skitour",  name: "Skitouren",       count: 12 },
  { id: "winter",   name: "Wintersport",     count: 10 },
  { id: "bike",     name: "Radtour",         count: 11 },
  { id: "water",    name: "Wassersport",     count: 10 },
  { id: "general",  name: "Allgemein",       count: 7 },
  { id: "khw403",   name: "★ KHW 403",       count: 14, custom: true },
];

function ScreenMetricsEditorMobile() {
  const [openGroups, setOpenGroups] = React.useState({ Temperatur: true, Wind: true, Niederschlag: false, "Wolken & Sicht": false, Sonstiges: false });
  const totalOn = METRICS_GROUPS_M.reduce((s, g) => s + g.items.filter(i => i.on).length, 0);
  const totalAll = METRICS_GROUPS_M.reduce((s, g) => s + g.items.length, 0);

  const toggleGroup = (g) => setOpenGroups({ ...openGroups, [g]: !openGroups[g] });

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Wetter-Metriken"
          eyebrow="KHW 403 · Briefing-Spalten"
          leftIcon="back"
          right={<button style={{ padding: "0 12px", minHeight: 44, background: "transparent", border: "none", fontSize: 14, color: "var(--g-ink-3)" }}>Abbrechen</button>}
        />

        <ScreenScroll padding={0}>
          {/* Preset-Picker H-Scroll */}
          <div style={{ padding: "10px 0 12px", borderBottom: "1px solid var(--g-rule-soft)" }}>
            <Eyebrow style={{ padding: "0 16px 8px" }}>Preset wählen</Eyebrow>
            <div style={{ display: "flex", gap: 8, padding: "0 16px", overflowX: "auto", WebkitOverflowScrolling: "touch", scrollbarWidth: "none" }}>
              {PRESETS_M.map(p => (
                <button key={p.id} style={{
                  flexShrink: 0, padding: "10px 14px", minHeight: 56, minWidth: 130,
                  background: p.active ? "var(--g-accent)" : "var(--g-card)",
                  color: p.active ? "#fff" : "var(--g-ink)",
                  border: `1px solid ${p.active ? "var(--g-accent)" : "var(--g-rule)"}`,
                  borderRadius: "var(--g-r-3)", cursor: "pointer", textAlign: "left",
                }}>
                  <div style={{ fontSize: 13, fontWeight: 600, lineHeight: 1.2 }}>{p.name}</div>
                  <div className="mono" style={{ fontSize: 10, marginTop: 4, opacity: p.active ? 0.85 : 0.6 }}>
                    {p.count} {p.custom ? "Metriken · eigen" : "Metriken"}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Selected summary */}
          <div style={{ padding: "12px 16px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>Alpen-Trekking</div>
              <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
                {totalOn} von {totalAll} Metriken aktiv
              </div>
            </div>
            <MBtn variant="ghost" size="md">Als eigen sp.</MBtn>
          </div>

          {/* Accordions */}
          <div style={{ padding: "0 16px 8px" }}>
            {METRICS_GROUPS_M.map(g => {
              const isOpen = openGroups[g.group];
              const groupOn = g.items.filter(i => i.on).length;
              return (
                <div key={g.group} style={{
                  background: "var(--g-card)", border: "1px solid var(--g-rule)",
                  borderRadius: "var(--g-r-3)", marginBottom: 8, overflow: "hidden",
                }}>
                  <button onClick={() => toggleGroup(g.group)} style={{
                    width: "100%", display: "flex", alignItems: "center", gap: 10,
                    padding: "14px 14px", minHeight: 56,
                    background: "transparent", border: "none", cursor: "pointer", textAlign: "left",
                  }}>
                    <div style={{ flex: 1, minWidth: 0 }}>
                      <div style={{ fontSize: 14, fontWeight: 600 }}>{g.group}</div>
                      <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>
                        {groupOn} von {g.items.length} aktiv
                      </div>
                    </div>
                    <MIcon kind={isOpen ? "chevron-up" : "chevron-down"} size={16} color="var(--g-ink-3)"/>
                  </button>
                  {isOpen && (
                    <div style={{ padding: "0 14px 8px" }}>
                      {g.items.map((m, i) => (
                        <div key={m.id} style={{
                          display: "flex", alignItems: "center", gap: 10, padding: "12px 0",
                          borderTop: "1px solid var(--g-rule-soft)",
                          minHeight: 56,
                        }}>
                          <div style={{ flex: 1, minWidth: 0 }}>
                            <div style={{ fontSize: 14, color: "var(--g-ink)" }}>{m.label}</div>
                            <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>
                              {m.unit || "—"}
                            </div>
                          </div>
                          <MSwitch checked={m.on}/>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </ScreenScroll>

        {/* Sticky Save-Bar */}
        <div style={{
          padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8, flexShrink: 0,
        }}>
          <MBtn variant="ghost" size="lg" style={{ flex: 1 }}>Reset</MBtn>
          <MBtn variant="primary" size="lg" style={{ flex: 1.6 }}>{totalOn} übernehmen</MBtn>
        </div>
      </div>
    </PhoneFrame>
  );
}

window.ScreenMetricsEditorMobile = ScreenMetricsEditorMobile;
