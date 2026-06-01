/* Screen: Ortsvergleich (Compare) — Hauptbühne
 * Linker Rail: gespeicherte Locations (gruppiert, suchbar, Multi-Select)
 * Mitte: Preset-Kopf (Datum, Zeitfenster, Forecast-Horizont, Aktivitätsprofil)
 *        + Empfehlungs-Banner + Vergleichs-Matrix + Stunden-Verlauf der Top-3
 * Rechts: bestehende Auto-Briefings (Subscriptions)
 */

function ScreenCompare() {
  const locs = MOCK_LOCATIONS;
  const rows = MOCK_COMPARE_ROWS;
  const top3 = rows.slice(0, 3);
  const selected = new Set(rows.map(r => r.id));
  const winner = locs.find(l => l.id === rows[0].id);

  return (
    <div style={{ display: "flex", minHeight: "100%", background: "var(--g-paper)" }}>
      <Sidebar active="compare"/>

      {/* Locations-Rail */}
      <CompareLocationsRail locs={locs} selected={selected} />

      {/* Hauptbereich */}
      <main style={{ flex: 1, position: "relative", overflow: "hidden" }}>
        <TopoBg opacity={0.18}/>

        {/* Topbar */}
        <div style={{
          position: "relative", display: "flex", alignItems: "center", justifyContent: "space-between",
          padding: "20px 32px", borderBottom: "1px solid var(--g-rule-soft)",
        }}>
          <div>
            <Eyebrow>Ortsvergleich · Ad-hoc</Eyebrow>
            <div style={{ fontSize: 22, fontWeight: 600, marginTop: 2, letterSpacing: "-0.01em" }}>
              Wo finde ich am Wochenende den besten Schnee?
            </div>
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
            <Btn variant="ghost" size="sm">Preset laden ▾</Btn>
            <Btn variant="ghost" size="sm" icon={<span style={{ fontSize: 13 }}>＋</span>}>Als Auto-Briefing speichern</Btn>
            <Btn variant="primary" size="sm">Vergleich starten →</Btn>
          </div>
        </div>

        <div style={{ position: "relative", padding: "24px 32px 60px", display: "grid", gridTemplateColumns: "1fr 320px", gap: 24, alignItems: "flex-start" }}>

          <div style={{ display: "flex", flexDirection: "column", gap: 20, minWidth: 0 }}>

            {/* ─── Settings ─── */}
            <Card padding={0}>
              <div style={{ padding: "16px 20px 6px", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
                <Eyebrow>Compare-Preset</Eyebrow>
                <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>5 Locations · 8h-Fenster · +48h</span>
              </div>
              <div style={{ padding: "10px 20px 18px", display: "grid", gridTemplateColumns: "150px 110px 110px 130px 1fr", gap: 14 }}>
                <CompareField label="Datum"      value="Sa, 09.05.2026" mono/>
                <CompareField label="Von (Uhr)"  value="09:00"          mono/>
                <CompareField label="Bis (Uhr)"  value="16:00"          mono/>
                <CompareField label="Forecast"   value="48h"            mono select/>
                <CompareField label="Aktivitätsprofil" value="Wintersport · Piste" select/>
              </div>
            </Card>

            {/* ─── Empfehlungs-Banner ─── */}
            <RecommendationBanner winner={winner} row={rows[0]}/>

            {/* ─── Vergleichs-Matrix ─── */}
            <CompareMatrix rows={rows} locs={locs}/>

            {/* ─── Stunden-Verlauf ─── */}
            <HourlyMatrix top={top3} locs={locs}/>
          </div>

          {/* ─── Sidepanel: Auto-Briefings ─── */}
          <CompareSubscriptionsPanel/>
        </div>
      </main>
    </div>
  );
}

/* ───────────── Locations-Rail (linke Spalte 240px) ───────────── */
function CompareLocationsRail({ locs, selected }) {
  const groups = locs.reduce((acc, l) => {
    (acc[l.group] = acc[l.group] || []).push(l);
    return acc;
  }, {});
  return (
    <aside style={{
      width: 240, flex: "0 0 240px",
      background: "var(--g-card-alt)",
      borderRight: "1px solid var(--g-rule)",
      display: "flex", flexDirection: "column",
      padding: "20px 0",
    }}>
      <div style={{ padding: "0 16px 12px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <Eyebrow>Meine Orte · {locs.length}</Eyebrow>
        <button style={{
          background: "transparent", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
          padding: "3px 8px", fontFamily: "var(--g-font-mono)", fontSize: 10, color: "var(--g-ink-3)",
          cursor: "pointer", letterSpacing: "0.06em",
        }}>＋ NEU</button>
      </div>

      {/* Search */}
      <div style={{ padding: "0 16px 12px" }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 8, padding: "6px 10px",
          background: "var(--g-card)", border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)",
        }}>
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="var(--g-ink-4)" strokeWidth="2"><circle cx="11" cy="11" r="7"/><path d="M21 21l-4-4"/></svg>
          <span style={{ fontSize: 12, color: "var(--g-ink-4)" }}>Orte suchen</span>
        </div>
      </div>

      {/* Quick-Actions */}
      <div style={{ padding: "0 16px 14px", display: "flex", gap: 6, flexWrap: "wrap" }}>
        <ChipBtn active>Alle (16)</ChipBtn>
        <ChipBtn>Zillertal (5)</ChipBtn>
        <ChipBtn>Hochkönig (4)</ChipBtn>
      </div>

      {/* Gruppen */}
      <div style={{ flex: 1, overflowY: "auto" }}>
        {Object.entries(groups).map(([group, items]) => (
          <div key={group} style={{ marginBottom: 6 }}>
            <div style={{
              padding: "8px 16px 4px", fontFamily: "var(--g-font-mono)", fontSize: 10,
              letterSpacing: "0.1em", color: "var(--g-ink-4)", textTransform: "uppercase",
              display: "flex", justifyContent: "space-between",
            }}>
              <span>{group}</span><span>{items.length}</span>
            </div>
            {items.map(l => (
              <LocationRow key={l.id} loc={l} checked={selected.has(l.id)}/>
            ))}
          </div>
        ))}
      </div>
    </aside>
  );
}

function LocationRow({ loc, checked }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 8,
      padding: "6px 16px", cursor: "pointer",
      background: checked ? "var(--g-accent-tint)" : "transparent",
      borderLeft: checked ? "2px solid var(--g-accent)" : "2px solid transparent",
      paddingLeft: checked ? 14 : 16,
    }}>
      <div style={{
        width: 14, height: 14, borderRadius: 3,
        border: `1.5px solid ${checked ? "var(--g-accent)" : "var(--g-rule)"}`,
        background: checked ? "var(--g-accent)" : "transparent",
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        {checked && <svg width="9" height="9" viewBox="0 0 12 12" fill="none" stroke="#fff" strokeWidth="2.5"><path d="M2 6l3 3 5-6"/></svg>}
      </div>
      <span style={{ flex: 1, fontSize: 12, color: "var(--g-ink)", lineHeight: 1.3 }}>{loc.name}</span>
      <FocusBadge focus={loc.focus}/>
    </div>
  );
}

function FocusBadge({ focus }) {
  const map = {
    "wintersport":         { i: "❄", c: "#4a7ab8" },
    "wintersport-glacier": { i: "◇", c: "#5a8ac8" },
    "alpine-touring":      { i: "▲", c: "#c45a2a" },
    "hiking":              { i: "▴", c: "#3d6b3a" },
    "trail-running":       { i: "→", c: "#c08a1a" },
  };
  const m = map[focus] || { i: "·", c: "#9a958a" };
  return (
    <span title={focus} style={{
      width: 16, height: 16, fontSize: 10, color: m.c,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      fontFamily: "var(--g-font-mono)", fontWeight: 600,
    }}>{m.i}</span>
  );
}

function ChipBtn({ children, active }) {
  return (
    <button style={{
      padding: "4px 9px", fontSize: 11,
      background: active ? "var(--g-ink)" : "transparent",
      color: active ? "var(--g-paper)" : "var(--g-ink-3)",
      border: `1px solid ${active ? "var(--g-ink)" : "var(--g-rule)"}`,
      borderRadius: "var(--g-r-pill)", cursor: "pointer",
      fontFamily: "var(--g-font-mono)", letterSpacing: "0.02em",
    }}>{children}</button>
  );
}

/* ───────────── Field (Settings-Pseudo-Input) ───────────── */
function CompareField({ label, value, mono, select }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 4 }}>
      <span style={{ fontSize: 10, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.08em", textTransform: "uppercase" }}>{label}</span>
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 6,
        padding: "8px 10px", background: "var(--g-card-alt)",
        border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)",
        fontFamily: mono ? "var(--g-font-mono)" : "var(--g-font-sans)",
        fontSize: 13, color: "var(--g-ink)", fontWeight: 500,
      }}>
        <span>{value}</span>
        {select && <span style={{ color: "var(--g-ink-4)", fontSize: 10 }}>▾</span>}
      </div>
    </div>
  );
}

/* ───────────── Empfehlungs-Banner ───────────── */
function RecommendationBanner({ winner, row }) {
  return (
    <div style={{
      background: "linear-gradient(135deg, rgba(61,107,58,0.08), rgba(61,107,58,0.02))",
      border: "1px solid rgba(61,107,58,0.25)", borderLeft: "3px solid var(--g-good)",
      borderRadius: "var(--g-r-3)", padding: "16px 20px",
      display: "flex", alignItems: "center", justifyContent: "space-between", gap: 20,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <div style={{
          width: 44, height: 44, borderRadius: "50%",
          background: "var(--g-good)", color: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: 18, fontWeight: 700, fontFamily: "var(--g-font-mono)",
        }}>#1</div>
        <div>
          <Eyebrow style={{ color: "var(--g-good)", marginBottom: 2 }}>Empfehlung</Eyebrow>
          <div style={{ fontSize: 20, fontWeight: 600, letterSpacing: "-0.01em", color: "var(--g-ink)" }}>{winner.name}</div>
          <div className="mono" style={{ fontSize: 12, color: "var(--g-ink-3)", marginTop: 4 }}>
            Score <strong style={{ color: "var(--g-good)" }}>{row.score}</strong> · {fmtDE(row.snow)} cm Schnee · ~{row.sun}h Sonne · Wind {row.wind}/{row.gust} {row.dir} · gef. {row.feels >= 0 ? "+" : ""}{row.feels}°C
          </div>
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 4, textAlign: "right" }}>
        <Btn variant="ghost" size="sm">Details öffnen →</Btn>
        <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)" }}>basis: 5/16 verglichen</span>
      </div>
    </div>
  );
}

/* ───────────── Vergleichs-Matrix ───────────── */
function CompareMatrix({ rows, locs }) {
  const cols = [
    { key: "score",     label: "Score",        unit: "",   highlight: "max" },
    { key: "snow",      label: "Schneehöhe",   unit: "cm", highlight: "max" },
    { key: "newSnow",   label: "Neuschnee",    unit: "cm", highlight: "max", prefix: "+" },
    { key: "wg",        label: "Wind/Böen",    unit: "",   highlight: "min", custom: r => `${r.wind}/${r.gust} ${r.dir}` },
    { key: "feels",     label: "Temp (gef.)",  unit: "°C", highlight: "max", prefix: r => r >= 0 ? "+" : "" },
    { key: "sun",       label: "Sonnenstunden",unit: "h",  highlight: "max", prefix: "~" },
    { key: "cloud",     label: "Bewölkung",    unit: "%",  highlight: "min" },
    { key: "cloudTag",  label: "Wolkenlage",   unit: "",   highlight: "tag", custom: r => r.cloudTag === "über" ? "über Wolken" : r.cloudTag === "klar" ? "klar" : "in Wolken" },
  ];
  // Best value per Spalte
  const bestByKey = {};
  cols.forEach(c => {
    if (c.highlight === "tag") return;
    const vals = rows.map(r => c.custom ? null : r[c.key]).filter(v => v != null && !Number.isNaN(v));
    if (!vals.length) return;
    bestByKey[c.key] = c.highlight === "max" ? Math.max(...vals) : Math.min(...vals);
  });

  return (
    <Card padding={0}>
      <div style={{ padding: "16px 20px 8px", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <Eyebrow>Vergleichs-Matrix · sortiert nach Score</Eyebrow>
        </div>
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>
          Grün = bester Wert · gef. Temp = Wind-Chill · * über tiefen Wolken
        </span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--g-font-mono)", fontVariantNumeric: "tabular-nums" }}>
        <thead>
          <tr style={{ borderTop: "1px solid var(--g-rule-soft)", borderBottom: "1px solid var(--g-rule-soft)" }}>
            <th style={thStyle("left")}>Metrik</th>
            {rows.map(r => {
              const l = locs.find(x => x.id === r.id);
              return (
                <th key={r.id} style={{ ...thStyle("center"), background: r.rank === 1 ? "rgba(61,107,58,0.05)" : "transparent" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6 }}>
                    <span style={{
                      display: "inline-flex", alignItems: "center", justifyContent: "center",
                      width: 22, height: 18, background: r.rank === 1 ? "var(--g-good)" : "var(--g-ink)",
                      color: "#fff", fontSize: 10, fontWeight: 600, borderRadius: 3,
                    }}>#{r.rank}</span>
                    <span style={{ fontFamily: "var(--g-font-sans)", fontSize: 12, fontWeight: 600, color: "var(--g-ink)", maxWidth: 120, lineHeight: 1.2 }}>{l.name}</span>
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {cols.map(c => (
            <tr key={c.key} style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
              <td style={{ ...tdStyle("left"), fontFamily: "var(--g-font-sans)", color: "var(--g-ink-2)", fontWeight: 500 }}>{c.label}</td>
              {rows.map(r => {
                const raw = c.custom ? c.custom(r) : r[c.key];
                const display = raw == null ? "—" : (typeof raw === "number" ? `${typeof c.prefix === "function" ? c.prefix(raw) : (c.prefix || "")}${fmtDE(raw)}${c.unit}` : raw);
                const isBest = c.highlight !== "tag" && raw != null && !c.custom && raw === bestByKey[c.key];
                const isBestTag = c.key === "cloudTag" && r.cloudBest;
                const best = isBest || isBestTag;
                return (
                  <td key={r.id} style={{
                    ...tdStyle("center"),
                    background: best ? "rgba(61,107,58,0.10)" : (r.rank === 1 ? "rgba(61,107,58,0.03)" : "transparent"),
                    color: best ? "var(--g-good)" : "var(--g-ink)",
                    fontWeight: best ? 700 : 500,
                  }}>{display}</td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

/* Mini-Bar pro Zelle: zeigt den Wert + relative Position in der Spalte. */
function MiniBarCell({ display, raw, min, max, highlight, isBest }) {
  const range = max - min || 1;
  const norm = (raw - min) / range; // 0..1
  // Bei »min«-Highlight (Wind/Böen/Bewölkung): niedrig = besser → invertieren
  const score = highlight === "min" ? 1 - norm : norm;
  const barWidth = Math.max(0.05, score) * 100;
  const barColor = isBest ? "var(--g-good)" : (score > 0.66 ? "#7a9a55" : score > 0.33 ? "#c08a1a" : "#a87a55");
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
      <span style={{
        fontFamily: "var(--g-font-mono)", fontVariantNumeric: "tabular-nums",
        fontWeight: isBest ? 700 : 500, color: isBest ? "var(--g-good)" : "var(--g-ink)",
        fontSize: 13,
      }}>{display}</span>
      <div style={{ width: "80%", height: 3, background: "var(--g-rule-soft)", borderRadius: 1.5, overflow: "hidden" }}>
        <div style={{ width: `${barWidth}%`, height: "100%", background: barColor }}/>
      </div>
    </div>
  );
}

const thStyle = (align) => ({
  fontFamily: "var(--g-font-mono)", fontSize: 10, letterSpacing: "0.08em",
  textTransform: "uppercase", color: "var(--g-ink-4)", fontWeight: 600,
  padding: "10px 12px", textAlign: align || "center", verticalAlign: "bottom",
});
const tdStyle = (align) => ({
  fontSize: 13, padding: "10px 12px", textAlign: align || "center",
  color: "var(--g-ink)", borderRight: "1px solid var(--g-rule-soft)",
});

const fmtDE = (n) => {
  if (n == null || n === "") return n;
  const num = typeof n === "number" ? n : Number(n);
  if (!Number.isFinite(num)) return n;
  return num.toLocaleString("de-DE");
};

/* ───────────── Stunden-Matrix (Top-3) ───────────── */
function HourlyMatrix({ top, locs }) {
  return (
    <Card padding={0}>
      <div style={{ padding: "16px 20px 8px", display: "flex", justifyContent: "space-between", alignItems: "baseline" }}>
        <div>
          <Eyebrow>Stunden-Verlauf · Top-3</Eyebrow>
          <div style={{ fontSize: 14, fontWeight: 500, marginTop: 4 }}>Sa 09.05.2026 · 09:00–16:00</div>
        </div>
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-4)" }}>°C · mm/cm · km/h ·  Richtung</span>
      </div>
      <table style={{ width: "100%", borderCollapse: "collapse", fontFamily: "var(--g-font-mono)", fontVariantNumeric: "tabular-nums" }}>
        <thead>
          <tr style={{ borderTop: "1px solid var(--g-rule-soft)", borderBottom: "1px solid var(--g-rule-soft)" }}>
            <th style={{ ...thStyle("left"), width: 70 }}>Zeit</th>
            {top.map(r => {
              const l = locs.find(x => x.id === r.id);
              return (
                <th key={r.id} style={{ ...thStyle("center"), background: r.rank === 1 ? "rgba(61,107,58,0.05)" : "transparent" }}>
                  <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 4 }}>
                    <span style={{
                      display: "inline-flex", alignItems: "center", justifyContent: "center",
                      width: 22, height: 16, background: r.rank === 1 ? "var(--g-good)" : "var(--g-ink)",
                      color: "#fff", fontSize: 9, fontWeight: 600, borderRadius: 3,
                    }}>#{r.rank}</span>
                    <span style={{ fontFamily: "var(--g-font-sans)", fontSize: 12, fontWeight: 600, color: "var(--g-ink)" }}>{l.name}</span>
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {MOCK_COMPARE_HOURS[top[0].id].map((_, i) => (
            <tr key={i} style={{ borderBottom: "1px solid var(--g-rule-soft)" }}>
              <td style={{ ...tdStyle("left"), color: "var(--g-ink-3)" }}>{MOCK_COMPARE_HOURS[top[0].id][i].h}:00</td>
              {top.map(r => {
                const h = MOCK_COMPARE_HOURS[r.id][i];
                return (
                  <td key={r.id} style={{ ...tdStyle("center"), background: r.rank === 1 ? "rgba(61,107,58,0.03)" : "transparent" }}>
                    <HourCell h={h}/>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}

function HourCell({ h }) {
  const cloudColor = { few: "var(--g-weather-sun)", some: "#c4a05a", many: "var(--g-weather-cloud)", snow: "var(--g-weather-snow)" }[h.cloud] || "var(--g-ink-4)";
  const cloudGlyph = { few: "☼", some: "☼", many: "☁", snow: "❄" }[h.cloud] || "·";
  return (
    <div style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 12 }}>
      <span style={{ color: cloudColor, width: 12, fontWeight: 700 }}>{cloudGlyph}</span>
      <span style={{ fontWeight: 600, minWidth: 20 }}>{h.t >= 0 ? "+" : ""}{h.t}°</span>
      {h.prec != null && <span style={{ color: "var(--g-weather-rain)" }}>{h.prec}{h.cloud === "snow" ? "cm" : "mm"}</span>}
      <span style={{ color: "var(--g-ink-3)" }}>{h.w}/{h.g} {h.d}</span>
    </div>
  );
}

/* ───────────── Auto-Briefings Sidepanel ───────────── */
function CompareSubscriptionsPanel() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <Card padding={0}>
        <div style={{ padding: "14px 18px 10px", borderBottom: "1px solid var(--g-rule-soft)" }}>
          <Eyebrow>Auto-Briefings · {MOCK_COMPARE_PRESETS.length}</Eyebrow>
          <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>Wiederkehrende Vergleiche</div>
        </div>
        <div>
          {MOCK_COMPARE_PRESETS.map(p => (
            <SubRow key={p.id} sub={p}/>
          ))}
        </div>
        <div style={{ padding: "10px 18px 14px", borderTop: "1px solid var(--g-rule-soft)" }}>
          <Btn variant="ghost" size="sm" style={{ width: "100%", justifyContent: "center" }}>＋ Aktuellen Vergleich speichern</Btn>
        </div>
      </Card>

      <Card padding={0}>
        <div style={{ padding: "14px 18px 4px" }}>
          <Eyebrow>Letzter Versand</Eyebrow>
        </div>
        <div style={{ padding: "8px 18px 16px", fontSize: 12, color: "var(--g-ink-2)", lineHeight: 1.55 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
            <span className="mono">Heute 07:00</span>
            <Pill tone="good">gesendet</Pill>
          </div>
          <strong>Skitouren Wochenende</strong> · 5 Locations<br/>
          <span style={{ color: "var(--g-ink-3)" }}>Top: Hintertuxer Gletscher (Score 70)</span>
        </div>
      </Card>
    </div>
  );
}

function SubRow({ sub }) {
  return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "10px 18px", borderBottom: "1px solid var(--g-rule-soft)" }}>
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: "var(--g-ink)", marginBottom: 2 }}>{sub.name}</div>
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{sub.locations} Orte · {sub.schedule} · {sub.profile}</div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        {sub.active ? <Dot tone="good"/> : <Dot tone="neutral"/>}
        <span className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.08em" }}>
          {sub.active ? "live" : "off"}
        </span>
      </div>
    </div>
  );
}

window.ScreenCompare = ScreenCompare;
