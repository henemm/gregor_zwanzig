/* Mobile · Ortsvergleich (Compare)
 * Pattern: Preset-Header → Empfehlung Hero → Matrix als H-Scroll mit sticky 1. Spalte
 *          → Stunden-Verlauf Top-3 (H-Scroll) → Auto-Briefings.
 * Locations-Auswahl in Bottom-Sheet.
 */

function ScreenCompareMobile() {
  const locs = MOCK_LOCATIONS;
  const rows = MOCK_COMPARE_ROWS;
  const top3 = rows.slice(0, 3);
  const winner = locs.find(l => l.id === rows[0].id);

  const [locSheet, setLocSheet] = React.useState(false);
  const [presetSheet, setPresetSheet] = React.useState(false);

  const right = <IconBtn kind="plus" label="Als Auto-Briefing"/>;

  return (
    <MobileShell active="compare" title="Ortsvergleich" eyebrow="Ad-hoc · Sa 09. Mai" right={right} phoneHeight={812}
                 sheet={
                   (locSheet && <LocSheetM locs={locs} onClose={() => setLocSheet(false)}/>) ||
                   (presetSheet && <PresetSheetM onClose={() => setPresetSheet(false)}/>)
                 }>
      <ScreenScroll padding={0}>
        <div style={{ padding: "12px 16px 6px" }}>
          <div style={{ fontSize: 18, fontWeight: 600, lineHeight: 1.3, letterSpacing: "-0.01em", marginBottom: 12 }}>
            Wo finde ich am Wochenende den besten Schnee?
          </div>

          {/* Preset-Header als 2x2-Grid */}
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6,
            background: "var(--g-card)", border: "1px solid var(--g-rule)",
            borderRadius: "var(--g-r-3)", padding: 10, marginBottom: 12,
          }}>
            <PresetCell label="Datum"        value="Sa, 09.05.26"/>
            <PresetCell label="Forecast"     value="48h"/>
            <PresetCell label="Zeitfenster"  value="09:00 – 16:00"/>
            <PresetCell label="Profil"       value="Wintersport · Piste"/>
          </div>

          {/* Locations-Chip-Row */}
          <button onClick={() => setLocSheet(true)} style={{
            display: "flex", alignItems: "center", gap: 10, width: "100%", minHeight: 48,
            padding: "10px 14px", background: "var(--g-card-alt)",
            border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
            cursor: "pointer", marginBottom: 12,
          }}>
            <MIcon kind="map" size={18} color="var(--g-ink-2)"/>
            <div style={{ flex: 1, textAlign: "left", minWidth: 0 }}>
              <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.1em", textTransform: "uppercase" }}>Verglichene Orte</div>
              <div style={{ fontSize: 13, fontWeight: 500, color: "var(--g-ink)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                5 von {locs.length}: Hintertux, Zillertal Arena, Hochkönig, …
              </div>
            </div>
            <MIcon kind="chevron" size={16} color="var(--g-ink-3)"/>
          </button>

          {/* Empfehlungs-Banner */}
          <RecommendationCardM winner={winner} row={rows[0]}/>
        </div>

        {/* Vergleichs-Matrix */}
        <div style={{ padding: "12px 16px 0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <Eyebrow>Matrix · sortiert nach Score</Eyebrow>
            <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>→ scrollen</span>
          </div>
        </div>
        <CompareMatrixM rows={rows} locs={locs}/>

        {/* Stunden-Verlauf Top-3 */}
        <div style={{ padding: "16px 16px 0" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <Eyebrow>Stunden · Top-3</Eyebrow>
            <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>09:00 – 16:00</span>
          </div>
        </div>
        <HourlyMatrixM top={top3} locs={locs}/>

        {/* Auto-Briefings */}
        <div style={{ padding: "20px 16px 24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 8 }}>
            <Eyebrow>Auto-Briefings · {MOCK_COMPARE_PRESETS.length}</Eyebrow>
            <button onClick={() => setPresetSheet(true)} style={{ fontSize: 12, color: "var(--g-accent)", background: "transparent", border: "none", fontWeight: 600, cursor: "pointer" }}>
              + Aktuellen speichern
            </button>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {MOCK_COMPARE_PRESETS.map(p => <SubRowM key={p.id} sub={p}/>)}
          </div>
        </div>
      </ScreenScroll>
    </MobileShell>
  );
}

function PresetCell({ label, value }) {
  return (
    <div>
      <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.1em", textTransform: "uppercase", marginBottom: 2 }}>{label}</div>
      <div style={{ fontSize: 13, fontWeight: 600, fontFamily: "var(--g-font-mono)", color: "var(--g-ink)", lineHeight: 1.3 }}>{value}</div>
    </div>
  );
}

function RecommendationCardM({ winner, row }) {
  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(61,107,58,0.10), rgba(61,107,58,0.02))",
      border: "1px solid rgba(61,107,58,0.25)",
      borderLeft: "3px solid var(--g-good)",
      borderRadius: "var(--g-r-3)", padding: 14,
      display: "flex", gap: 12,
    }}>
      <div style={{
        width: 44, height: 44, borderRadius: "50%", flexShrink: 0,
        background: "var(--g-good)", color: "#fff",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 16, fontWeight: 700, fontFamily: "var(--g-font-mono)",
      }}>#1</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <Eyebrow style={{ color: "var(--g-good)", marginBottom: 2 }}>Empfehlung</Eyebrow>
        <div style={{ fontSize: 16, fontWeight: 600, letterSpacing: "-0.005em", lineHeight: 1.25 }}>{winner.name}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 4, lineHeight: 1.5 }}>
          Score <strong style={{ color: "var(--g-good)" }}>{row.score}</strong> · {row.snow} cm · ~{row.sun}h Sonne<br/>
          Wind {row.wind}/{row.gust} {row.dir} · gef. {row.feels >= 0 ? "+" : ""}{row.feels}°C
        </div>
      </div>
    </div>
  );
}

/* ─────────────────── Matrix · H-Scroll mit sticky 1. Spalte ─────────────────── */
function CompareMatrixM({ rows, locs }) {
  const cols = [
    { key: "score",     label: "Score",     unit: "",   highlight: "max" },
    { key: "snow",      label: "Schneeh.",  unit: "cm", highlight: "max" },
    { key: "newSnow",   label: "Neuschnee", unit: "cm", highlight: "max", prefix: "+" },
    { key: "wg",        label: "Wind/Böen", custom: r => `${r.wind}/${r.gust}${r.dir}`, highlight: "min" },
    { key: "feels",     label: "Gef.",      unit: "°", highlight: "max", prefix: r => r >= 0 ? "+" : "" },
    { key: "sun",       label: "Sonne",     unit: "h", highlight: "max", prefix: "~" },
    { key: "cloud",     label: "Bewölk.",   unit: "%", highlight: "min" },
    { key: "cloudTag",  label: "Wolken",    custom: r => r.cloudTag === "über" ? "über" : r.cloudTag === "klar" ? "klar" : "in", highlight: "tag" },
  ];
  const bestByKey = {};
  cols.forEach(c => {
    if (c.highlight === "tag" || c.custom) return;
    const vals = rows.map(r => r[c.key]).filter(v => v != null);
    if (!vals.length) return;
    bestByKey[c.key] = c.highlight === "max" ? Math.max(...vals) : Math.min(...vals);
  });

  const colW = 96;
  const firstW = 120;

  return (
    <div style={{
      overflowX: "auto", WebkitOverflowScrolling: "touch",
      borderTop: "1px solid var(--g-rule-soft)",
      borderBottom: "1px solid var(--g-rule-soft)",
      background: "var(--g-card)",
    }}>
      <div style={{ display: "inline-flex", minWidth: "100%" }}>
        {/* Sticky first col */}
        <div style={{
          position: "sticky", left: 0, zIndex: 2, flexShrink: 0, width: firstW,
          background: "var(--g-card-alt)",
          borderRight: "1px solid var(--g-rule)",
        }}>
          <div style={{ ...thMStyle(), borderBottom: "1px solid var(--g-rule-soft)" }}>Metrik</div>
          {cols.map(c => (
            <div key={c.key} style={{
              ...tdMStyle(), borderBottom: "1px solid var(--g-rule-soft)",
              fontFamily: "var(--g-font-sans)", fontWeight: 500, color: "var(--g-ink-2)",
              textAlign: "left", padding: "12px 12px",
            }}>{c.label}</div>
          ))}
        </div>

        {/* Scrollable columns */}
        <div style={{ display: "flex" }}>
          {rows.map(r => {
            const l = locs.find(x => x.id === r.id);
            const isTop = r.rank === 1;
            return (
              <div key={r.id} style={{
                width: colW, flexShrink: 0,
                background: isTop ? "rgba(61,107,58,0.05)" : "transparent",
                borderRight: "1px solid var(--g-rule-soft)",
              }}>
                {/* Header */}
                <div style={{
                  padding: "10px 8px", borderBottom: "1px solid var(--g-rule-soft)",
                  display: "flex", flexDirection: "column", alignItems: "center", gap: 4,
                }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    width: 22, height: 16, background: isTop ? "var(--g-good)" : "var(--g-ink)",
                    color: "#fff", fontSize: 9, fontWeight: 600, borderRadius: 3,
                    fontFamily: "var(--g-font-mono)",
                  }}>#{r.rank}</span>
                  <span style={{ fontSize: 11, fontWeight: 600, color: "var(--g-ink)", textAlign: "center", lineHeight: 1.2, height: 26, overflow: "hidden" }}>{l.name}</span>
                </div>
                {/* Cells */}
                {cols.map(c => {
                  const raw = c.custom ? c.custom(r) : r[c.key];
                  const display = raw == null ? "—" : (typeof raw === "number" ?
                    `${typeof c.prefix === "function" ? c.prefix(raw) : (c.prefix || "")}${raw}${c.unit || ""}` : raw);
                  const isBest = !c.custom && c.highlight !== "tag" && raw === bestByKey[c.key];
                  const isBestTag = c.key === "cloudTag" && r.cloudBest;
                  const best = isBest || isBestTag;
                  return (
                    <div key={c.key} style={{
                      ...tdMStyle(),
                      borderBottom: "1px solid var(--g-rule-soft)",
                      color: best ? "var(--g-good)" : "var(--g-ink)",
                      fontWeight: best ? 700 : 500,
                      background: best ? "rgba(61,107,58,0.08)" : "transparent",
                    }}>{display}</div>
                  );
                })}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

const thMStyle = () => ({
  fontFamily: "var(--g-font-mono)", fontSize: 10, letterSpacing: "0.1em",
  textTransform: "uppercase", color: "var(--g-ink-4)", fontWeight: 600,
  padding: "12px 12px", textAlign: "left",
});
const tdMStyle = () => ({
  fontSize: 13, padding: "12px 8px", textAlign: "center",
  fontFamily: "var(--g-font-mono)", fontVariantNumeric: "tabular-nums",
});

/* ─────────────────── Stunden-Matrix · Top-3 ─────────────────── */
function HourlyMatrixM({ top, locs }) {
  const hours = MOCK_COMPARE_HOURS[top[0].id];
  const colW = 110;
  return (
    <div style={{
      overflowX: "auto", WebkitOverflowScrolling: "touch",
      borderTop: "1px solid var(--g-rule-soft)",
      borderBottom: "1px solid var(--g-rule-soft)",
      background: "var(--g-card)",
    }}>
      <div style={{ display: "inline-flex", minWidth: "100%" }}>
        {/* Sticky time col */}
        <div style={{
          position: "sticky", left: 0, zIndex: 2, flexShrink: 0, width: 60,
          background: "var(--g-card-alt)", borderRight: "1px solid var(--g-rule)",
        }}>
          <div style={{ ...thMStyle(), borderBottom: "1px solid var(--g-rule-soft)", padding: "10px 10px", height: 50, boxSizing: "border-box" }}>Zeit</div>
          {hours.map((h, i) => (
            <div key={i} style={{
              ...tdMStyle(), borderBottom: "1px solid var(--g-rule-soft)",
              textAlign: "left", padding: "10px 10px", color: "var(--g-ink-3)",
            }}>{h.h}:00</div>
          ))}
        </div>
        <div style={{ display: "flex" }}>
          {top.map(r => {
            const l = locs.find(x => x.id === r.id);
            const isTop = r.rank === 1;
            const data = MOCK_COMPARE_HOURS[r.id];
            return (
              <div key={r.id} style={{
                width: colW, flexShrink: 0,
                background: isTop ? "rgba(61,107,58,0.05)" : "transparent",
                borderRight: "1px solid var(--g-rule-soft)",
              }}>
                <div style={{
                  padding: "8px 6px", height: 50, boxSizing: "border-box",
                  borderBottom: "1px solid var(--g-rule-soft)",
                  display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 2,
                }}>
                  <span style={{
                    display: "inline-flex", alignItems: "center", justifyContent: "center",
                    width: 22, height: 14, background: isTop ? "var(--g-good)" : "var(--g-ink)",
                    color: "#fff", fontSize: 9, fontWeight: 600, borderRadius: 3,
                    fontFamily: "var(--g-font-mono)",
                  }}>#{r.rank}</span>
                  <span style={{ fontSize: 10, fontWeight: 600, color: "var(--g-ink)", textAlign: "center", lineHeight: 1.1, overflow: "hidden" }}>{l.name.split(" ")[0]}</span>
                </div>
                {data.map((h, i) => <HourCellM key={i} h={h}/>)}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function HourCellM({ h }) {
  const cloudColor = { few: "var(--g-weather-sun)", some: "#c4a05a", many: "var(--g-weather-cloud)", snow: "var(--g-weather-snow)" }[h.cloud] || "var(--g-ink-4)";
  const cloudGlyph = { few: "☼", some: "☼", many: "☁", snow: "❄" }[h.cloud] || "·";
  return (
    <div style={{
      padding: "10px 6px", borderBottom: "1px solid var(--g-rule-soft)",
      display: "flex", alignItems: "center", gap: 4,
      fontFamily: "var(--g-font-mono)", fontSize: 11, fontVariantNumeric: "tabular-nums",
    }}>
      <span style={{ color: cloudColor, width: 10, fontWeight: 700 }}>{cloudGlyph}</span>
      <span style={{ fontWeight: 600, minWidth: 20 }}>{h.t >= 0 ? "+" : ""}{h.t}°</span>
      <span style={{ color: "var(--g-ink-3)", marginLeft: "auto" }}>{h.w}{h.d}</span>
    </div>
  );
}

/* ─────────────────── Subscription Row ─────────────────── */
function SubRowM({ sub }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "12px 14px", background: "var(--g-card)",
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)",
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, marginBottom: 2 }}>{sub.name}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>
          {sub.locations} Orte · {sub.schedule} · {sub.profile}
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6, flexShrink: 0 }}>
        <Dot tone={sub.active ? "good" : "neutral"}/>
        <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {sub.active ? "live" : "off"}
        </span>
      </div>
    </div>
  );
}

/* ─────────────────── Locations-Sheet ─────────────────── */
function LocSheetM({ locs, onClose }) {
  const groups = locs.reduce((acc, l) => {
    (acc[l.group] = acc[l.group] || []).push(l);
    return acc;
  }, {});
  return (
    <Sheet open onClose={onClose} title="Orte auswählen" eyebrow={`Meine Orte · ${locs.length}`} snap="full"
           footer={
             <div style={{ display: "flex", gap: 8 }}>
               <MBtn variant="ghost" size="lg" block onClick={onClose}>Abbrechen</MBtn>
               <MBtn variant="primary" size="lg" block onClick={onClose}>5 übernehmen</MBtn>
             </div>
           }>
      <div style={{ position: "sticky", top: 0, background: "var(--g-card)", paddingBottom: 8, marginBottom: 4, zIndex: 1 }}>
        <MInput leftIcon="search" placeholder="Orte suchen…"/>
      </div>
      {Object.entries(groups).map(([group, items]) => (
        <div key={group} style={{ marginBottom: 12 }}>
          <div className="mono" style={{
            padding: "8px 0 6px", fontSize: 10, letterSpacing: "0.14em",
            color: "var(--g-ink-4)", textTransform: "uppercase",
          }}>{group} · {items.length}</div>
          {items.map(l => <LocRowM key={l.id} loc={l} checked={items.indexOf(l) < 2}/>)}
        </div>
      ))}
    </Sheet>
  );
}

function LocRowM({ loc, checked }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12, minHeight: 48,
      padding: "10px 0", borderBottom: "1px solid var(--g-rule-soft)",
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: 5,
        border: `2px solid ${checked ? "var(--g-accent)" : "var(--g-rule)"}`,
        background: checked ? "var(--g-accent)" : "transparent",
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        {checked && <MIcon kind="check" size={14} color="#fff"/>}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, color: "var(--g-ink)", fontWeight: checked ? 600 : 500 }}>{loc.name}</div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>{loc.elev} m · {loc.focus}</div>
      </div>
    </div>
  );
}

function PresetSheetM({ onClose }) {
  return (
    <Sheet open onClose={onClose} title="Vergleich speichern" eyebrow="Neues Auto-Briefing" snap="half"
           footer={
             <div style={{ display: "flex", gap: 8 }}>
               <MBtn variant="ghost" size="lg" block onClick={onClose}>Abbrechen</MBtn>
               <MBtn variant="primary" size="lg" block onClick={onClose}>Speichern</MBtn>
             </div>
           }>
      <MField label="Name">
        <MInput placeholder="Skitouren Wochenende"/>
      </MField>
      <MField label="Zeitplan">
        <MInput defaultValue="Fr 18:00"/>
      </MField>
      <MField label="Kanäle">
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
          {["Email","Signal","Telegram","SMS"].map((k, i) => (
            <span key={k} style={{
              padding: "8px 12px", minHeight: 36, borderRadius: "var(--g-r-pill)",
              background: i === 0 ? "var(--g-ink)" : "var(--g-card-alt)",
              color: i === 0 ? "var(--g-paper)" : "var(--g-ink-2)",
              border: `1px solid ${i === 0 ? "var(--g-ink)" : "var(--g-rule)"}`,
              fontSize: 12, fontFamily: "var(--g-font-mono)", fontWeight: 500,
            }}>{k}</span>
          ))}
        </div>
      </MField>
    </Sheet>
  );
}

window.ScreenCompareMobile = ScreenCompareMobile;
window.LocSheetM = LocSheetM;
