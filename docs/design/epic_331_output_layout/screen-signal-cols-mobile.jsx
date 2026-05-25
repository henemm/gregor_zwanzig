/* SCREEN · Signal-Spalten-Editor (Mobile)
 * ─────────────────────────────────────────────────────────────────────────
 *
 * Zweck
 *   User-Konfiguration "Welche Wetter-Metriken erscheinen wie im Signal-
 *   Briefing", unter dem 6-Spalten-Hard-Limit aus signal-layout.jsx
 *   (siehe OverflowReadme dort für die Herleitung).
 *
 * Datenmodell (Backend-State, pro Tour pro Channel)
 *
 *     type Bucket = "table" | "prose" | "off";
 *
 *     interface SignalColumnsConfig {
 *       maxTableColumns: 6;                    // konstant für Channel = signal
 *       assignments: {
 *         [metricId: string]: {
 *           bucket: Bucket;
 *           order: number;                     // 0..n-1 innerhalb des Buckets
 *         }
 *       };
 *     }
 *
 *   Die Quelle für `metricId` ist die globale Metriken-Auswahl der Tour
 *   (screen-metrics-editor-mobile.jsx). Hier wird nur entschieden, wie
 *   sie *im Signal-Kanal* gerendert werden.
 *
 * Constraints (Frontend-validiert, server-bestätigt vor Save)
 *
 *   C1   |assignments[m].bucket == "table"| ≤ 6
 *   C2   Metrik `hour` ist required: assignments["hour"].bucket == "table"
 *        und assignments["hour"].order == 0.
 *   C3   order ist eindeutig innerhalb eines Buckets, lückenlos 0..n-1.
 *
 * Auto-Verteilung (Default & Reset)
 *
 *   Eine reine Frontend-Hilfsfunktion `autoAssign(allMetrics)` mit fester
 *   Heuristik:
 *     - "hour" → table[0]    (required)
 *     - dann nach METRIC_PRIORITY (s.u.) → table[1..5]
 *     - überzählige relevante Metriken → prose, sortiert nach METRIC_PRIORITY
 *     - alles unter Priorität-Schwellwert → off
 *
 *   Wird ausgelöst durch (a) Erstanlage eines Trips, (b) "Auto-Verteilung"-
 *   Button im UI, (c) Channel-Wechsel auf Signal wenn noch keine
 *   Assignments existieren.
 *
 * Interaktionen
 *
 *   - Tap auf eine Metrik-Zeile  → öffnet Sheet mit kontextabhängigen Aktionen:
 *       (table)   ↑ ↓                            (Reihenfolge)
 *                 → in Prosa verschieben         (move to prose)
 *                 → ausblenden                   (move to off)
 *       (prose)   ↑ ↓
 *                 → in Tabelle (disabled wenn C1)
 *                 → ausblenden
 *       (off)     → in Tabelle (disabled wenn C1)
 *                 → in Prosa
 *
 *   - "Auto-Verteilung" oben rechts in der TopAppBar → autoAssign().
 *   - "Speichern" persistiert Config zum Backend; bei Verletzung C1/C2/C3
 *     Toast mit Fehlerursache (sollte FE-seitig vorher verhindert werden).
 *
 * Wiederverwendung — andere Channels
 *
 *   Gleicher Screen mit `maxTableColumns` parametrisiert:
 *     signal   → 6   (dieser Screen)
 *     telegram → 8   (geringfügig breitere Bubbles)
 *     sms      → 0   ("table" Bucket existiert nicht, alles geht in prose
 *                     bis 140 Zeichen erreicht, dann Toast)
 *     email    → ∞   (Screen nicht nötig — kein Limit)
 *
 *   Empfehlung: identische Komponente, prop `channel` & `maxTableColumns`
 *   reinreichen, Copy/Labels über kleine `STRINGS[channel]`-Map steuern.
 *
 * Live-Vorschau
 *
 *   Sticky-Card direkt unterhalb der TopAppBar, immer sichtbar.
 *   Zeigt die aktuelle Tabellen-Header-Zeile in der Mono-Schrift, die
 *   Signal beim Empfänger rendert. Tap auf die Vorschau → öffnet ein Sheet
 *   mit Voll-Bubble-Render (SignalBubble + MonoTable + Prosa). Dieser
 *   ist in dieser ersten Iteration eingeklappt.
 */

const ALL_METRICS_SC = [
  { id: "hour",       label: "Stunde",            short: "hh",  unit: "h",     required: true,  prio: 100 },
  { id: "temp",       label: "Temperatur",        short: "°C",  unit: "°C",    prio: 95 },
  { id: "wind",       label: "Wind",              short: "W",   unit: "km/h",  prio: 90 },
  { id: "gust",       label: "Böen",              short: "G",   unit: "km/h",  prio: 88 },
  { id: "rainProb",   label: "Regen-Wahrsch.",    short: "R%",  unit: "%",     prio: 85 },
  { id: "weather",    label: "Wetter-Glyph",      short: "☁",   unit: "",      prio: 82 },
  { id: "feels",      label: "Gefühlte Temp",     short: "gef", unit: "°C",    prio: 70 },
  { id: "cloud",      label: "Bewölkung",         short: "Cl",  unit: "%",     prio: 65 },
  { id: "thunder",    label: "Gewitter-Wahrsch.", short: "Gw",  unit: "%",     prio: 60 },
  { id: "visibility", label: "Sichtweite",        short: "Si",  unit: "km",    prio: 55 },
  { id: "precip",     label: "Niederschlag",      short: "R",   unit: "mm",    prio: 52 },
  { id: "windDir",    label: "Windrichtung",      short: "Dir", unit: "°",     prio: 40 },
  { id: "radiation",  label: "Globalstrahlung",   short: "Sun", unit: "W/m²",  prio: 35 },
  { id: "uv",         label: "UV-Index",          short: "UV",  unit: "",      prio: 30 },
];

const MAX_TABLE_COLS = 6;

/* Initial state — ausgehend von Auto-Verteilung */
function initialAssignments() {
  return {
    table: ["hour", "temp", "wind", "gust", "rainProb", "weather"],
    prose: ["cloud", "feels", "visibility", "radiation"],
    off:   ["thunder", "precip", "windDir", "uv"],
  };
}

function getMetric(id) {
  return ALL_METRICS_SC.find(m => m.id === id);
}

function ScreenSignalColsMobile({ initialSheetOpen = null }) {
  const [assignments, setAssignments] = React.useState(initialAssignments());
  const [sheet, setSheet] = React.useState(initialSheetOpen); // { id, bucket } | null

  const counts = {
    table: assignments.table.length,
    prose: assignments.prose.length,
    off:   assignments.off.length,
  };
  const tableFull = counts.table >= MAX_TABLE_COLS;

  /* Bucket-Move mit Constraint-Check */
  const moveTo = (id, fromBucket, toBucket) => {
    if (toBucket === "table" && fromBucket !== "table" && tableFull) return;
    const next = {
      table: [...assignments.table],
      prose: [...assignments.prose],
      off:   [...assignments.off],
    };
    next[fromBucket] = next[fromBucket].filter(x => x !== id);
    next[toBucket].push(id);
    setAssignments(next);
    setSheet(null);
  };

  const reorder = (bucket, id, direction) => {
    const list = [...assignments[bucket]];
    const idx = list.indexOf(id);
    const targetIdx = idx + direction;
    if (targetIdx < 0 || targetIdx >= list.length) return;
    // C2: "hour" bleibt auf Index 0 im table-Bucket
    if (bucket === "table" && (list[idx] === "hour" || list[targetIdx] === "hour")) return;
    [list[idx], list[targetIdx]] = [list[targetIdx], list[idx]];
    setAssignments({ ...assignments, [bucket]: list });
  };

  const resetToDefault = () => setAssignments(initialAssignments());

  return (
    <PhoneFrame height={812}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar
          title="Signal-Spalten"
          eyebrow="KHW 403 · Briefing-Layout"
          leftIcon="back"
          right={
            <button onClick={resetToDefault} style={{
              padding: "0 14px", minHeight: 44, background: "transparent", border: "none",
              fontSize: 14, color: "var(--g-accent)", fontWeight: 600, cursor: "pointer",
            }}>Auto</button>
          }
        />

        {/* Live-Vorschau · sticky direkt unter TopAppBar */}
        <SignalColsPreview assignments={assignments}/>

        <ScreenScroll padding={0}>
          <BucketCard
            kind="table"
            title="Im Mono-Block"
            countLabel={`${counts.table} / ${MAX_TABLE_COLS}`}
            hint="Spalten der Monospace-Tabelle. Reihenfolge = Spaltenreihenfolge im Briefing."
            items={assignments.table}
            onTap={(id) => setSheet({ id, bucket: "table" })}
          />

          <BucketCard
            kind="prose"
            title="Als Prosa-Zeile"
            countLabel={`${counts.prose} Werte`}
            hint="Erscheinen als kompakte Fließtext-Zeile unter der Tabelle, durch · getrennt."
            items={assignments.prose}
            onTap={(id) => setSheet({ id, bucket: "prose" })}
          />

          <BucketCard
            kind="off"
            title="Nicht im Signal-Briefing"
            countLabel={`${counts.off} ausgeblendet`}
            hint="Diese Metriken werden für Signal weggelassen. In Email/Telegram bleiben sie unberührt."
            items={assignments.off}
            onTap={(id) => setSheet({ id, bucket: "off" })}
          />

          <div style={{ height: 16 }}/>
        </ScreenScroll>

        <div style={{
          padding: "10px 16px",
          paddingBottom: "calc(10px + env(safe-area-inset-bottom))",
          background: "var(--g-paper)", borderTop: "1px solid var(--g-rule)",
          display: "flex", gap: 8, flexShrink: 0,
        }}>
          <MBtn variant="ghost" size="lg" style={{ flex: 1 }}>Abbrechen</MBtn>
          <MBtn variant="primary" size="lg" style={{ flex: 1.6 }}>Speichern</MBtn>
        </div>

        {/* Sheet für Metrik-Aktionen */}
        {sheet && (
          <MetricActionSheet
            metric={getMetric(sheet.id)}
            bucket={sheet.bucket}
            tableFull={tableFull && sheet.bucket !== "table"}
            position={assignments[sheet.bucket].indexOf(sheet.id)}
            lastPosition={assignments[sheet.bucket].length - 1}
            onMove={(target) => moveTo(sheet.id, sheet.bucket, target)}
            onReorder={(dir) => reorder(sheet.bucket, sheet.id, dir)}
            onClose={() => setSheet(null)}
          />
        )}
      </div>
    </PhoneFrame>
  );
}

/* ─── Live-Vorschau ─────────────────────────────────────────────────── */

function SignalColsPreview({ assignments }) {
  const headerLine = assignments.table.map(id => getMetric(id).short).join("  ");
  const proseLine  = assignments.prose.map(id => getMetric(id).label).join(" · ");

  return (
    <div style={{
      flexShrink: 0,
      padding: "10px 16px 12px",
      background: "var(--g-paper-deep)",
      borderBottom: "1px solid var(--g-rule)",
    }}>
      <div className="mono" style={{
        fontSize: 9.5, letterSpacing: "0.14em", textTransform: "uppercase",
        color: "var(--g-ink-4)", marginBottom: 5,
        display: "flex", justifyContent: "space-between", alignItems: "center",
      }}>
        <span>Vorschau · so sieht der Empfänger es</span>
        <span style={{ color: "var(--g-accent)" }}>Voll-Vorschau →</span>
      </div>
      <div style={{
        background: "#eaeaea", color: "#1a1a1a",
        padding: "8px 12px",
        borderRadius: 12,
        borderBottomLeftRadius: 4,
        fontFamily: "ui-monospace, Menlo, monospace",
        fontSize: 12, lineHeight: 1.45,
        whiteSpace: "pre",
        overflowX: "auto",
      }}>
        {headerLine || "(keine Spalten in Tabelle)"}
      </div>
      {proseLine && (
        <div style={{
          marginTop: 4, fontSize: 11, lineHeight: 1.45,
          color: "var(--g-ink-3)",
          paddingLeft: 12, paddingRight: 12,
          fontStyle: "italic",
        }}>
          + Prosa: {proseLine}
        </div>
      )}
    </div>
  );
}

/* ─── Bucket-Card ──────────────────────────────────────────────────── */

function BucketCard({ kind, title, countLabel, hint, items, onTap }) {
  const overLimit = kind === "table" && items.length > MAX_TABLE_COLS;
  return (
    <div style={{ padding: "12px 16px 0" }}>
      <div style={{
        background: "var(--g-card)", border: "1px solid var(--g-rule)",
        borderRadius: "var(--g-r-3)", overflow: "hidden",
      }}>
        <div style={{
          padding: "12px 14px 8px",
          display: "flex", alignItems: "baseline", justifyContent: "space-between",
          gap: 8,
        }}>
          <div>
            <Eyebrow color={overLimit ? "var(--g-bad)" : kind === "table" ? "var(--g-accent)" : "var(--g-ink-3)"}>
              {title}
            </Eyebrow>
            <div style={{ fontSize: 13.5, color: "var(--g-ink-3)", marginTop: 4, lineHeight: 1.4 }}>
              {hint}
            </div>
          </div>
          <div className="mono" style={{
            fontSize: 12, fontWeight: 600,
            color: overLimit ? "var(--g-bad)" : "var(--g-ink-2)",
            whiteSpace: "nowrap",
          }}>{countLabel}</div>
        </div>

        {items.length === 0 ? (
          <div style={{
            padding: "16px 14px",
            borderTop: "1px solid var(--g-rule-soft)",
            fontSize: 13, color: "var(--g-ink-4)", textAlign: "center", fontStyle: "italic",
          }}>—</div>
        ) : (
          items.map((id, i) => {
            const m = getMetric(id);
            return (
              <BucketRow
                key={id} metric={m} kind={kind} index={i}
                showNumber={kind === "table"}
                onTap={() => onTap(id)}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

function BucketRow({ metric, kind, index, showNumber, onTap }) {
  return (
    <button
      onClick={onTap}
      style={{
        width: "100%", display: "flex", alignItems: "center", gap: 12,
        padding: "12px 14px", minHeight: 56,
        background: "transparent",
        border: "none", borderTop: "1px solid var(--g-rule-soft)",
        cursor: "pointer", textAlign: "left",
      }}
    >
      {showNumber && (
        <span className="mono" style={{
          width: 22, fontSize: 12, fontWeight: 600,
          color: "var(--g-ink-3)", textAlign: "right",
        }}>{index + 1}</span>
      )}
      {!showNumber && kind === "prose" && (
        <span style={{
          width: 22, color: "var(--g-ink-4)", fontSize: 14, textAlign: "center",
        }}>·</span>
      )}
      {!showNumber && kind === "off" && (
        <span style={{
          width: 22, color: "var(--g-ink-4)", fontSize: 14, textAlign: "center",
        }}>○</span>
      )}

      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 14.5, fontWeight: 500, color: "var(--g-ink)",
          display: "flex", alignItems: "baseline", gap: 8,
        }}>
          {metric.label}
          {metric.required && (
            <span className="mono" style={{
              fontSize: 9.5, letterSpacing: "0.08em", textTransform: "uppercase",
              color: "var(--g-ink-4)", fontWeight: 500,
            }}>pflicht</span>
          )}
        </div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 2 }}>
          {metric.unit || "—"} · Kürzel <span style={{ color: "var(--g-ink-3)" }}>{metric.short}</span>
        </div>
      </div>

      <MIcon kind="chevron" size={14} color="var(--g-ink-4)"/>
    </button>
  );
}

/* ─── Aktion-Sheet ─────────────────────────────────────────────────── */

function MetricActionSheet({ metric, bucket, tableFull, position, lastPosition, onMove, onReorder, onClose }) {
  const canMoveUp = position > 0 && (bucket !== "table" || (position > 0 && metric.id !== "hour"));
  const canMoveDown = position < lastPosition && (bucket !== "table" || metric.id !== "hour");
  const showReorder = bucket !== "off";

  return (
    <Sheet open snap="peek" title={metric.label}
      eyebrow={
        bucket === "table" ? "Im Mono-Block" :
        bucket === "prose" ? "Als Prosa-Zeile" :
                             "Nicht im Signal-Briefing"
      }
      onClose={onClose}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {showReorder && (
          <React.Fragment>
            <SheetAction
              icon="chevron-up" label="Eine Position nach oben"
              disabled={!canMoveUp || metric.required}
              onClick={() => onReorder(-1)}
            />
            <SheetAction
              icon="chevron-down" label="Eine Position nach unten"
              disabled={!canMoveDown || metric.required}
              onClick={() => onReorder(+1)}
            />
            <SheetDivider/>
          </React.Fragment>
        )}

        {bucket !== "table" && (
          <SheetAction
            icon="plus" label="In Tabelle verschieben"
            sub={tableFull ? "Tabelle voll (max 6)" : null}
            disabled={tableFull}
            onClick={() => onMove("table")}
          />
        )}
        {bucket !== "prose" && (
          <SheetAction
            icon="list" label={bucket === "table" ? "In Prosa-Zeile verschieben" : "In Prosa-Zeile aufnehmen"}
            disabled={metric.required}
            sub={metric.required ? "Pflicht-Spalte — muss in Tabelle bleiben" : null}
            onClick={() => onMove("prose")}
          />
        )}
        {bucket !== "off" && (
          <SheetAction
            icon="close" label="Aus Signal-Briefing entfernen"
            disabled={metric.required}
            sub={metric.required ? "Pflicht-Spalte" : null}
            onClick={() => onMove("off")}
          />
        )}
      </div>
    </Sheet>
  );
}

function SheetAction({ icon, label, sub, disabled, onClick }) {
  return (
    <button
      onClick={disabled ? undefined : onClick}
      disabled={disabled}
      style={{
        width: "100%", display: "flex", alignItems: "center", gap: 14,
        padding: "14px 6px", minHeight: 52,
        background: "transparent", border: "none",
        cursor: disabled ? "not-allowed" : "pointer", textAlign: "left",
        opacity: disabled ? 0.4 : 1,
      }}
    >
      <span style={{
        width: 36, height: 36, borderRadius: 8,
        background: "var(--g-paper-deep)", border: "1px solid var(--g-rule-soft)",
        display: "inline-flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        <MIcon kind={icon} size={18} color="var(--g-ink-2)"/>
      </span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 15, color: "var(--g-ink)", fontWeight: 500 }}>{label}</div>
        {sub && (
          <div style={{ fontSize: 12, color: "var(--g-ink-4)", marginTop: 2 }}>{sub}</div>
        )}
      </div>
    </button>
  );
}

function SheetDivider() {
  return <div style={{ height: 1, background: "var(--g-rule-soft)", margin: "6px 0" }}/>;
}

window.ScreenSignalColsMobile = ScreenSignalColsMobile;
