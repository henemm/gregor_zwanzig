/* ════════════════════════════════════════════════════════════════════════
 *  MOLECULES — kleine Kompositionen aus Atomen
 * ════════════════════════════════════════════════════════════════════════
 *
 *  Eine Molecule ist eine Komposition aus 2+ Atomen mit einer eigenen
 *  semantischen Bedeutung. Sie ist nie Brand-Träger und nie eine ganze
 *  Sektion einer Seite — beides liegt eine Ebene höher (organisms.jsx).
 *
 *  Lade-Reihenfolge in HTML-Files:
 *      brand-kit.jsx → atoms.jsx → molecules.jsx → screen-*.jsx
 *
 *  Migrations-Quellen (siehe docs/atomic-design-inventory.md §3):
 *      Field                   ← screen-trip-wizard::Field + AuthField
 *      DetailRow               ← Verallgemeinerung von atoms::KV
 *      StagePill               ← screen-home::StagePill
 *      ChannelRow              ← screen-trip-wizard::ChannelLine
 *      ChannelChip             ← NEU (kompakte Variante)
 *      BriefingTimelineRow     ← screen-home::ReportRow
 *      BriefingScheduleRow     ← screen-trip-wizard::ReportRow
 *      ThresholdRow            ← screen-trip-wizard::ThresholdRow
 *
 *  Naming-Konvention (CLAUDE.md):
 *      Sprechender Name, kein Prefix. Brand-only = Brand*. Mobile-only = M*.
 *
 *  ──────────────────────────────────────────────────────────────────── */


/* ─────────────────── Field ───────────────────
 * Form-Field-Wrapper: Label oben + Children + optional Hint/Error + Side-Link.
 * Vereinheitlicht trip-wizard::Field, auth::AuthField, und ist drop-in für
 * mobile-shell::MField (mit dense={false}). */
function Field({
  label,
  hint,        /* zarter Hilfstext unter dem Feld */
  error,       /* Error-String — überschreibt hint visuell */
  side,        /* z. B. "Passwort vergessen?" rechts neben dem Label */
  dense = true,
  children,
  style,
}) {
  return (
    <div style={{ marginBottom: dense ? 14 : 18, ...style }}>
      {(label || side) && (
        <div style={{
          display: "flex", justifyContent: "space-between", alignItems: "baseline",
          marginBottom: dense ? 6 : 8,
        }}>
          {label && (
            <span className="mono" style={{
              fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase",
              color: "var(--g-ink-3)", fontWeight: 500,
            }}>{label}</span>
          )}
          {side && (
            <span style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{side}</span>
          )}
        </div>
      )}
      {children}
      {(hint || error) && (
        <div style={{
          fontSize: 11, marginTop: 5, lineHeight: 1.4,
          color: error ? "var(--g-bad)" : "var(--g-ink-4)",
        }}>{error || hint}</div>
      )}
    </div>
  );
}


/* ─────────────────── DetailRow ───────────────────
 * Label-Value-Zeile, optional mit Icon links, Sub-Text, Right-Slot,
 * gestrichelter Bottom-Border (default). KV-Verallgemeinerung. */
function DetailRow({
  label, value, sub, icon, right,
  mono = true,                /* Value-Font: mono (Default) oder sans */
  divider = "dashed",         /* "dashed" | "solid" | "none" */
  style,
}) {
  const borderStyle = divider === "none"
    ? "none"
    : `1px ${divider} var(--g-rule-soft)`;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "8px 0", borderBottom: borderStyle, fontSize: 13,
      ...style,
    }}>
      {icon && <span style={{ display: "inline-flex", flexShrink: 0 }}>{icon}</span>}
      <div style={{ flex: 1, minWidth: 0 }}>
        <span className="mono" style={{
          fontSize: 12, color: "var(--g-ink-3)", letterSpacing: "0.02em",
        }}>{label}</span>
        {sub && (
          <div style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 2 }}>{sub}</div>
        )}
      </div>
      {value != null && (
        <span style={{
          color: "var(--g-ink)",
          fontFamily: mono ? "var(--g-font-mono)" : "var(--g-font-sans)",
          fontWeight: mono ? 500 : 600,
          fontSize: 13,
          fontVariantNumeric: mono ? "tabular-nums" : "normal",
        }}>{value}</span>
      )}
      {right}
    </div>
  );
}


/* ─────────────────── StagePill ───────────────────
 * Etappen-Kachel für Etappen-Streifen / Trip-Verlauf.
 * State-getriebenes Prop-Modell (D7). Backward-compatible mit den
 * boolschen Original-Props (active/done/muted) aus screen-home. */
function StagePill({ stage, state, active, done, muted, style }) {
  /* Boolean-Props auf state mappen, falls state nicht gesetzt: */
  const s = state
    || (active ? "active" : done ? "done" : muted ? "muted" : "future");

  const isActive = s === "active";
  const isMuted  = s === "muted";

  const riskTone = stage.risk === "high"
    ? "var(--g-bad)"
    : stage.risk === "med"
      ? "var(--g-warn)"
      : "var(--g-good)";

  return (
    <div style={{
      flex: 1, minWidth: 0, padding: "8px 10px",
      background: isActive
        ? "var(--g-accent-tint)"
        : isMuted
          ? "var(--g-paper-deep)"
          : "var(--g-card-alt)",
      border: isActive
        ? "1px solid var(--g-accent)"
        : "1px solid var(--g-rule-soft)",
      borderRadius: "var(--g-r-2)",
      opacity: isMuted ? 0.55 : 1,
      ...style,
    }}>
      <div className="mono" style={{
        fontSize: 10,
        color: isActive ? "var(--g-accent-deep)" : "var(--g-ink-3)",
        textTransform: "uppercase", letterSpacing: "0.06em", fontWeight: 500,
        whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
      }}>{stage.code}</div>
      {!isMuted && stage.risk && (
        <div style={{ marginTop: 6, height: 3, background: riskTone, borderRadius: 2 }}/>
      )}
    </div>
  );
}


/* ─────────────────── ChannelGlyph ───────────────────
 * Interner Helper: einheitliches Mono-Glyph pro Kanal. */
function channelGlyph(kind) {
  const k = String(kind).toLowerCase();
  if (k.startsWith("email"))    return "✉";
  if (k.startsWith("signal"))   return "▲";
  if (k.startsWith("telegram")) return "✈";
  if (k.startsWith("sms"))      return "✱";
  return "·";
}


/* ─────────────────── ChannelRow ───────────────────
 * Kanal-Konfigurations-Zeile: Kind + Target-Adresse + Switch + optional Sub.
 * Zwei Layouts:
 *   default        — als Card-alt-Karte mit Rundung (Desktop, in Wizard-Listen)
 *   dense=true     — reihen-style, mit Bottom-Border (Mobile-Listen in Cards) */
function ChannelRow({
  kind,                  /* "Email" | "Signal" | "Telegram" | "SMS" */
  target,                /* z. B. "gregor_zwanzig@henemm.com" */
  active = false,
  sub,
  onToggle,              /* (next: boolean) => void; ohne → readonly */
  dense = false,
  last = false,
  style,
}) {
  if (dense) {
    return (
      <div style={{
        display: "flex", alignItems: "center", padding: "10px 0",
        borderBottom: last ? "none" : "1px solid var(--g-rule-soft)",
        gap: 12, ...style,
      }}>
        <span className="mono" style={{
          fontSize: 10, width: 60, textTransform: "uppercase",
          letterSpacing: "0.08em", color: "var(--g-ink-3)",
        }}>{kind}</span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="mono" style={{
            fontSize: 12, color: "var(--g-ink)",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>{target}</div>
          {sub && (
            <div style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>{sub}</div>
          )}
        </div>
        <Switch checked={active} onChange={onToggle} size="lg" tone="good"/>
      </div>
    );
  }
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "10px 14px", background: "var(--g-card-alt)",
      borderRadius: "var(--g-r-2)", ...style,
    }}>
      <span className="mono" style={{
        fontSize: 9, width: 56, textTransform: "uppercase",
        letterSpacing: "0.08em", color: "var(--g-ink-3)",
      }}>{kind}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="mono" style={{
          fontSize: 12, color: "var(--g-ink)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{target}</div>
        {sub && (
          <div style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>{sub}</div>
        )}
      </div>
      <Switch checked={active} onChange={onToggle} tone="good"/>
    </div>
  );
}


/* ─────────────────── ChannelChip ───────────────────
 * Kanal-Indikator. Zwei Layouts:
 *   default      — Pill mit Glyph + Text (Desktop, in Briefing-Listen)
 *   compact=true — 24×24 Tile mit Glyph allein (Mobile, in Listen) */
function ChannelChip({ kind, active = true, compact = false, style }) {
  const opacity = active ? 1 : 0.5;
  if (compact) {
    return (
      <span className="mono" style={{
        width: 24, height: 24, borderRadius: 4,
        background: "var(--g-paper-deep)",
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        fontSize: 12, color: "var(--g-ink-2)", opacity,
        flexShrink: 0, ...style,
      }}>{channelGlyph(kind)}</span>
    );
  }
  return (
    <span className="mono" style={{
      display: "inline-flex", alignItems: "center", gap: 4,
      fontSize: 11, padding: "2px 6px",
      border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-pill)",
      color: "var(--g-ink-3)", opacity,
      ...style,
    }}>
      <span>{channelGlyph(kind)}</span>
      <span style={{ textTransform: "lowercase" }}>{String(kind).toLowerCase()}</span>
    </span>
  );
}


/* ─────────────────── BriefingTimelineRow ───────────────────
 * Vergangenheits-/Zukunfts-Zeile aus screen-home: ein geplanter oder
 * gesendeter Briefing-Versand. Status-getrieben (sent / planned).
 *
 *   dense=true — Mobile-Layout: kompaktere Channel-Chips, kein
 *                 "gesendet/geplant"-Suffix, etwas weniger Padding. */
function BriefingTimelineRow({ report, dense = false, style }) {
  const isSent = report.status === "sent";
  return (
    <div style={{
      display: "flex", alignItems: "center",
      gap: dense ? 10 : 12, padding: "10px 12px",
      background: isSent ? "var(--g-card-alt)" : "var(--g-card)",
      border: "1px solid var(--g-rule-soft)",
      borderRadius: "var(--g-r-2)",
      ...style,
    }}>
      <Dot tone={isSent ? "good" : "neutral"}/>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ display: "flex", gap: 8, alignItems: "baseline" }}>
          <span className="mono" style={{ fontSize: 12, fontWeight: dense ? 600 : 500 }}>{report.when}</span>
          <span style={{ fontSize: 12, color: "var(--g-ink-3)", textTransform: "capitalize" }}>
            {report.kind}{!dense && "-Briefing"}
          </span>
        </div>
        {report.etappe && (
          <div className="mono" style={{
            fontSize: dense ? 10 : 11, color: "var(--g-ink-3)", marginTop: 2,
            overflow: dense ? "hidden" : undefined,
            textOverflow: dense ? "ellipsis" : undefined,
            whiteSpace: dense ? "nowrap" : undefined,
          }}>
            {report.etappe}
          </div>
        )}
      </div>
      <div style={{ display: "flex", gap: dense ? 2 : 4 }}>
        {(report.channels || []).map(c => (
          <ChannelChip key={c} kind={c} compact={dense}/>
        ))}
      </div>
      {!dense && (
        <span className="mono" style={{
          fontSize: 11,
          color: isSent ? "var(--g-good)" : "var(--g-ink-4)",
          minWidth: 60, textAlign: "right",
          textTransform: "uppercase", letterSpacing: "0.06em",
        }}>{isSent ? "gesendet" : "geplant"}</span>
      )}
    </div>
  );
}


/* ─────────────────── BriefingScheduleRow ───────────────────
 * Konfigurations-Zeile aus dem Trip-Wizard: »Morgen-Briefing · 06:00 · [on]«.
 * Toggle-getrieben. Time als Mono-Display. `last` unterdrückt Bottom-Border. */
function BriefingScheduleRow({
  label, sub, time, enabled = false, onToggle, last = false, style,
}) {
  return (
    <div style={{
      display: "flex", alignItems: "center",
      padding: "10px 0",
      borderBottom: last ? "none" : "1px solid var(--g-rule-soft)",
      gap: 12,
      ...style,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600 }}>{label}</div>
        {sub && <div style={{ fontSize: 11, color: "var(--g-ink-3)", marginTop: 2 }}>{sub}</div>}
      </div>
      {time && (
        <div className="mono" style={{
          fontSize: 13, fontWeight: 600,
          color: "var(--g-accent-deep)", whiteSpace: "nowrap",
        }}>{time}</div>
      )}
      <Switch checked={enabled} onChange={onToggle} tone="good"/>
    </div>
  );
}


/* ─────────────────── ThresholdRow ───────────────────
 * Sans-Label + Mono-Value-Paar, kompakt.
 *   divider="none"   — keine Trennlinie (Default, kompakte Listen ohne Border)
 *   divider="solid"  — durchgezogene Linie unten (Mobile-Listen)
 *   divider="dashed" — gestrichelt
 *   last=true        — unterdrückt die Linie für die letzte Zeile in der Liste
 *   editable=true    — pencil-Cursor (Inline-Edit kommt später). */
function ThresholdRow({
  label, value,
  divider = "none",
  last = false,
  editable = false, onEdit,
  style,
}) {
  const showDivider = !last && divider !== "none";
  return (
    <div
      onClick={editable ? onEdit : undefined}
      style={{
        display: "flex", justifyContent: "space-between", alignItems: "center",
        padding: divider !== "none" ? "10px 0" : "6px 0",
        borderBottom: showDivider ? `1px ${divider} var(--g-rule-soft)` : "none",
        cursor: editable ? "pointer" : "default",
        ...style,
      }}
    >
      <span style={{ fontSize: 13, color: "var(--g-ink-2)" }}>{label}</span>
      <span className="mono" style={{ fontSize: 13, color: "var(--g-ink)", fontWeight: 600 }}>
        {value}
      </span>
    </div>
  );
}


/* ─────────────────── Stat ───────────────────
 * Tile-Statistik: Label + großer Zahlenwert, optional Einheit & Sub-Text.
 * Zwei Layouts decken alle bestehenden Stat-Implementierungen:
 *   layout="stack"  — Label oben (mono caps), Value unten groß.  Default.
 *   layout="inline" — Value groß links, Label rechts (mono caps).
 * tone="accent" hebt den Value-Text in Burnt-Orange hervor.
 *
 * Migrationsquellen: trip-detail::Stat, archive::ArchiveStat.
 * NICHT zu verwenden im Email-Render-Kontext (dort eigene EmailStat/CEStat
 * mit gemockten Email-Client-Farben). */
function Stat({
  label, value, sub, unit,
  tone = "default",
  layout = "stack",
  size = "md",
  mono = false,
  style,
}) {
  const SIZES = {
    sm: { value: 18, label: 9 },
    md: { value: 22, label: 10 },
    lg: { value: 28, label: 10 },
  };
  const s = SIZES[size] || SIZES.md;
  const valueColor = tone === "accent" ? "var(--g-accent)" : "var(--g-ink)";
  const labelEl = (
    <span className="mono" style={{
      fontSize: s.label,
      color: "var(--g-ink-3)",
      letterSpacing: "0.12em",
      textTransform: "uppercase",
      fontWeight: 500,
    }}>{label}</span>
  );
  const valueEl = (
    <span style={{
      fontSize: layout === "inline" ? Math.max(s.value, 22) : s.value,
      fontWeight: 600,
      color: valueColor,
      letterSpacing: layout === "inline" ? "-0.02em" : 0,
      fontFamily: mono ? "var(--g-font-mono)" : undefined,
      fontVariantNumeric: "tabular-nums",
      lineHeight: 1,
      display: "inline-flex", alignItems: "baseline", gap: 4,
    }}>
      {value}
      {unit && (
        <span style={{
          fontSize: 12, color: "var(--g-ink-4)", fontWeight: 500,
        }}>{unit}</span>
      )}
    </span>
  );

  if (layout === "inline") {
    return (
      <div style={{ display: "flex", alignItems: "baseline", gap: 8, ...style }}>
        {valueEl}
        {labelEl}
      </div>
    );
  }
  return (
    <div style={style}>
      <div style={{ marginBottom: 4 }}>{labelEl}</div>
      {valueEl}
      {sub && (
        <div style={{ fontSize: 11, color: "var(--g-ink-4)", marginTop: 4 }}>{sub}</div>
      )}
    </div>
  );
}


/* ─────────────────── AlertRow ───────────────────
 * Eine Alert-/Warn-Meldung in einer Liste. Drei Varianten:
 *   variant="icon"  — WIcon links (Wetter-Symbol je nach alert.kind),
 *                    when + channel oben, msg unten.  Home + Mobile.
 *   variant="dot"   — kleiner Accent-Dot, when oben, msg unten.
 *                    Kompakt, ohne Wetter-Icon.  Trip-Detail-Style.
 *   variant="plain" — nur when + msg, kein Marker.
 *
 * alert: { kind, when, msg, channel? }
 * last: bei true wird der Bottom-Divider unterdrückt (Mobile-Listen).
 * divider: "dashed" (default) | "solid" | "none". */
function AlertRow({
  alert,
  variant = "icon",
  last = false,
  divider = "dashed",
  style,
}) {
  const tone = alert.kind === "thunder" ? "bad" : "warn";
  const toneColor = tone === "bad" ? "var(--g-bad)" : "var(--g-warn)";
  const borderBottom = (last || divider === "none")
    ? "none"
    : `1px ${divider} var(--g-rule-soft)`;

  return (
    <div style={{
      display: "flex", gap: 10, padding: "10px 0",
      borderBottom,
      ...style,
    }}>
      {variant === "icon" && (
        <div style={{ marginTop: 2, flexShrink: 0 }}>
          <WIcon
            kind={alert.kind === "thunder" ? "thunder" : "wind"}
            size={18}
            color={toneColor}
          />
        </div>
      )}
      {variant === "dot" && (
        <div style={{ paddingTop: 6, flexShrink: 0 }}>
          <span style={{
            display: "inline-block", width: 6, height: 6, borderRadius: "50%",
            background: "var(--g-accent)",
          }}/>
        </div>
      )}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div className="mono" style={{
          fontSize: 11, color: "var(--g-ink-3)", marginBottom: 2,
        }}>
          {alert.when}
          {alert.channel && <span> · {alert.channel}</span>}
        </div>
        <div style={{ fontSize: 13, color: "var(--g-ink)", lineHeight: 1.4 }}>{alert.msg}</div>
      </div>
    </div>
  );
}


/* ─────────────────── HorizonChips ───────────────────
 * Drei Pills HEUTE / MORGEN / ÜBERMORGEN für die pro-Metrik-Horizont-Wahl
 * (Trip-Kontext). Pill-active = ink-on-paper; inaktiv = ghost.
 *
 * value: { today, tomorrow, day_after }  → onToggle(key) flippt einen Slot.
 * Verwendung: in MetricEditorRow, Trip-Kontext. Ort/Abo-Kontext nutzt ScoreToggle.
 */
function HorizonChips({ value = {}, onToggle, compact = false, style }) {
  const items = [
    { key: "today",     label: "HEUTE" },
    { key: "tomorrow",  label: "MORGEN" },
    { key: "day_after", label: "ÜBERM." },
  ];
  return (
    <div style={{ display: "inline-flex", gap: 4, ...style }}>
      {items.map(it => {
        const on = !!value[it.key];
        return (
          <button
            key={it.key}
            onClick={() => onToggle && onToggle(it.key)}
            aria-pressed={on}
            className="mono"
            style={{
              padding: compact ? "3px 7px" : "3px 9px",
              fontSize: compact ? 9 : 9.5, fontWeight: 600,
              letterSpacing: "0.08em",
              background: on ? "var(--g-ink)" : "transparent",
              color: on ? "var(--g-paper)" : "var(--g-ink-4)",
              border: `1px solid ${on ? "var(--g-ink)" : "var(--g-rule)"}`,
              borderRadius: "var(--g-r-pill)",
              cursor: "pointer",
            }}>{it.label}</button>
        );
      })}
    </div>
  );
}


/* ─────────────────── ScoreToggle ───────────────────
 * Ein einzelner Pill-Toggle „Im Score / Nicht im Score" für Ort/Abo-Kontext.
 * Erscheint dort wo im Trip-Kontext die HorizonChips stehen. */
function ScoreToggle({ on = false, onToggle, compact = false, style }) {
  return (
    <button
      onClick={onToggle}
      aria-pressed={on}
      className="mono"
      style={{
        padding: compact ? "3px 9px" : "4px 11px",
        fontSize: compact ? 10 : 10.5, fontWeight: 600,
        letterSpacing: "0.08em",
        background: on ? "var(--g-accent-tint)" : "transparent",
        color: on ? "var(--g-accent-deep)" : "var(--g-ink-4)",
        border: `1px solid ${on ? "var(--g-accent)" : "var(--g-rule)"}`,
        borderRadius: "var(--g-r-pill)",
        cursor: "pointer",
        display: "inline-flex", gap: 6, alignItems: "center",
        ...style,
      }}>
      <span style={{
        width: 6, height: 6, borderRadius: "50%",
        background: on ? "var(--g-accent)" : "var(--g-rule)",
      }}/>
      {on ? "Im Score" : "Nicht im Score"}
    </button>
  );
}


/* ─────────────────── MetricEditorRow ───────────────────
 * Zentrale Zeile im Wetter-Metrik-Editor. EINE Komponente für alle drei
 * Kontexte — Unterschied steckt nur im `context`-Prop:
 *   "trip"  → HorizonChips als Mitten-Control
 *   "ort"   → ScoreToggle  als Mitten-Control
 *   "abo"   → ScoreToggle  (dito; Abo-Frequenz lebt eine Ebene höher)
 *
 * `bucket` ist "primary" (Spalte) oder "secondary" (Detail).
 * Index wird nur bei primary angezeigt — er ist die Tabellen-Position.
 *
 * Roh/Skala-Wahl nutzt das Segmented-Atom. Move-Buttons sind Btn quiet xs.
 */
function MetricEditorRow({
  metric,                /* { id, label, short, unit, hasIndicator } */
  index = 0,
  bucket = "primary",    /* "primary" | "secondary" */
  context = "trip",      /* "trip" | "ort" | "abo" */
  isFirst, isLast, isSignalLimit, isOverLimit,
  horizon, inScore,
  mode = "raw",          /* "raw" | "indicator" */
  onHorizon, onScore, onMode,
  onMove,                /* (target: "primary"|"secondary"|"off") => void */
  onReorder,             /* (dir: -1|+1) => void */
  compact = false,
  style,
}) {
  const showIndex = bucket === "primary";
  const cols = compact
    ? (showIndex ? "22px 1fr 168px 84px 56px" : "1fr 168px 84px 56px")
    : (showIndex ? "26px 1fr 220px 110px 100px 58px" : "1fr 220px 110px 100px 58px");

  const ctxControl = context === "trip"
    ? <HorizonChips value={horizon || {}} onToggle={onHorizon} compact={compact}/>
    : <ScoreToggle on={!!inScore} onToggle={onScore} compact={compact}/>;

  return (
    <React.Fragment>
      {isSignalLimit && (
        <div className="mono" style={{
          padding: "4px 18px", fontSize: 10,
          letterSpacing: "0.1em", textTransform: "uppercase",
          color: "var(--g-warn)",
          background: "rgba(192,138,26,0.06)",
          borderTop: "1px dashed var(--g-warn)",
          borderBottom: "1px dashed var(--g-warn)",
        }}>↓ ab hier bei Signal automatisch in Detail-Zeile · max 6 Spalten</div>
      )}

      <div style={{
        display: "grid", gridTemplateColumns: cols, gap: 10,
        padding: compact ? "9px 16px" : "11px 18px",
        borderBottom: "1px solid var(--g-rule-soft)",
        alignItems: "center",
        background: isOverLimit ? "rgba(192,138,26,0.04)" : "transparent",
        ...style,
      }}>
        {showIndex && (
          <div className="mono" style={{
            fontSize: 10.5, fontWeight: 600, textAlign: "right",
            color: isOverLimit ? "var(--g-warn)" : "var(--g-ink-3)",
          }}>{index + 1}</div>
        )}

        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: compact ? 12.5 : 13.5, fontWeight: 500, color: "var(--g-ink)" }}>
            {metric.label}
          </div>
          <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 1 }}>
            {metric.unit || "—"} · {metric.short}
          </div>
        </div>

        <div>{ctxControl}</div>

        {!compact && (
          <div>
            {metric.hasIndicator ? (
              <Segmented
                size="sm"
                items={[{ id: "raw", label: "Roh" }, { id: "indicator", label: "Einfach" }]}
                value={mode}
                onChange={onMode}
              />
            ) : (
              <span className="mono" style={{
                fontSize: 10, color: "var(--g-ink-4)",
                letterSpacing: "0.06em", textTransform: "uppercase",
              }}>nur Roh</span>
            )}
          </div>
        )}

        <div style={{ display: "flex", gap: 4 }}>
          {bucket === "primary"
            ? <Btn variant="ghost" size="xs" onClick={() => onMove && onMove("secondary")}>→ Detail</Btn>
            : <Btn variant="ghost" size="xs" onClick={() => onMove && onMove("primary")}>↑ Spalte</Btn>}
          <Btn variant="quiet" size="xs" onClick={() => onMove && onMove("off")}>✕</Btn>
        </div>

        <div style={{ display: "flex", gap: 2, justifyContent: "flex-end" }}>
          <MetricArrow direction="up"   disabled={isFirst} onClick={() => onReorder && onReorder(-1)}/>
          <MetricArrow direction="down" disabled={isLast}  onClick={() => onReorder && onReorder(+1)}/>
        </div>
      </div>
    </React.Fragment>
  );
}

/* Tiny up/down arrow used inside MetricEditorRow. Not exposed — pure internal. */
function MetricArrow({ direction, disabled, onClick }) {
  return (
    <button onClick={disabled ? undefined : onClick} disabled={disabled} style={{
      width: 22, height: 22, padding: 0,
      border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-2)",
      background: "var(--g-card)", color: "var(--g-ink-2)",
      cursor: disabled ? "not-allowed" : "pointer", opacity: disabled ? 0.4 : 1,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
    }}>
      <svg width="9" height="9" viewBox="0 0 12 12">
        {direction === "up"
          ? <path d="M6 2.5 L10 8 H2 Z" fill="currentColor"/>
          : <path d="M6 9.5 L2 4 H10 Z" fill="currentColor"/>}
      </svg>
    </button>
  );
}


/* ─────────────────── ChannelLimitChip ───────────────────
 * Mono-Pill, die zeigt: dieser Kanal hat Spalten-Limit X, aktuell sind Y belegt.
 * Bei Over-Limit Warn-Tonalität. Verwendung im Header der MetricBucket-Sektion.
 */
function ChannelLimitChip({ channel, current, max, style }) {
  const over = current > max;
  return (
    <span className="mono" style={{
      padding: "2px 7px", fontSize: 9.5, letterSpacing: "0.04em",
      borderRadius: "var(--g-r-pill)", fontWeight: 600,
      background: over ? "rgba(192,138,26,0.15)" : "rgba(26,26,24,0.05)",
      color: over ? "var(--g-warn)" : "var(--g-ink-3)",
      border: over ? "1px solid var(--g-warn)" : "1px solid transparent",
      ...style,
    }}>{channel} {current}/{max}</span>
  );
}


/* ─────────────────── ChannelPreviewCard ───────────────────
 * Eine Karte pro Kanal in der Output-Vorschau: Header (Name + Belegt/Max-Pill),
 * Mini-Tabelle mit Mono-Daten, Detail-Zeile darunter, ggf. Demote-Banner.
 *
 *  channel:  { id, label, max, hint }
 *  primary:  string[]   — Metric-IDs im Spalten-Bucket (in Order)
 *  secondary: string[]  — Metric-IDs im Detail-Bucket
 *  metricLookup: id → { short, label }
 *  sampleVal: i → string  — Demo-Wert für Spalte i
 */
function ChannelPreviewCard({
  channel, primary = [], secondary = [],
  metricLookup, sampleVal,
  compact = false, style,
}) {
  const max = channel.max ?? 99;
  const inTable = primary.slice(0, max);
  const overflow = primary.slice(max);
  const detail = [...overflow, ...secondary];
  const isSMS = channel.id === "sms";

  const shortOf = (id) => (metricLookup?.[id]?.short || id).slice(0, 5).padEnd(6, " ");
  const labelOf = (id) =>  metricLookup?.[id]?.label || id;

  return (
    <div style={{
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", overflow: "hidden",
      display: "flex", flexDirection: "column",
      ...style,
    }}>
      <div style={{ padding: "8px 10px", borderBottom: "1px solid var(--g-rule-soft)" }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div style={{ fontSize: 12, fontWeight: 600 }}>{channel.label}</div>
          <span className="mono" style={{
            padding: "1px 6px", fontSize: 9.5, borderRadius: "var(--g-r-pill)", fontWeight: 600,
            background: overflow.length ? "rgba(192,138,26,0.15)" : "rgba(26,26,24,0.05)",
            color: overflow.length ? "var(--g-warn)" : "var(--g-ink-3)",
          }}>{isSMS ? "flach" : `${inTable.length}/${max < 99 ? max : "∞"}`}</span>
        </div>
        {channel.hint && (
          <div className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", marginTop: 3, letterSpacing: "0.03em" }}>
            {channel.hint}
          </div>
        )}
      </div>

      <div style={{ padding: 9, flex: 1 }}>
        {!isSMS && inTable.length > 0 && (
          <div style={{
            background: "var(--g-paper-deep)", borderRadius: "var(--g-r-2)",
            padding: "5px 7px", fontFamily: "var(--g-font-mono)",
            fontSize: 9.5, lineHeight: 1.5, overflowX: "auto", whiteSpace: "pre",
          }}>
            {inTable.map(id => shortOf(id)).join("")}{"\n"}
            {inTable.map((_, i) => (sampleVal ? sampleVal(i) : "—").padEnd(6, " ")).join("")}
          </div>
        )}
        {detail.length > 0 && !isSMS && (
          <div style={{ marginTop: 6, fontSize: 10.5, color: "var(--g-ink-2)",
                        lineHeight: 1.45, fontStyle: "italic" }}>
            <span className="mono" style={{
              fontSize: 9, color: "var(--g-ink-4)",
              letterSpacing: "0.08em", textTransform: "uppercase", marginRight: 4,
            }}>Detail:</span>
            {detail.slice(0, 5).map(labelOf).join(" · ")}
            {detail.length > 5 && <span> · …</span>}
          </div>
        )}
        {isSMS && (
          <div style={{ fontSize: 10.5, color: "var(--g-ink-2)", lineHeight: 1.5 }}>
            {[...primary, ...secondary].slice(0, 6).map(id => metricLookup?.[id]?.short || id).join(" · ")}
            <span style={{ color: "var(--g-ink-4)" }}> · …</span>
          </div>
        )}
        {overflow.length > 0 && (
          <div className="mono" style={{
            marginTop: 7, padding: "4px 7px",
            background: "rgba(192,138,26,0.08)",
            borderLeft: "2px solid var(--g-warn)",
            fontSize: 10, color: "var(--g-warn)", fontWeight: 600,
            letterSpacing: "0.04em",
          }}>↳ {overflow.length} {overflow.length === 1 ? "Spalte" : "Spalten"} → Detail</div>
        )}
      </div>
    </div>
  );
}


/* ════════════════════ Compare-Domain-Molecules ════════════════════
 *
 * Single-Source für Orts-Vergleich-Listen + Detail (Desktop + Mobile).
 * Ersetzt die früheren Inline-Helfer CL_/CD_/CLM_/CDM_/HM_/HMM_ in den
 * screen-compare-*-Dateien (Drift-Auflösung 2026-05-31, Charter §3 v1.1).
 *
 * Konvention (inventory §1, §4): sprechender Name, kein Prefix,
 * `dense` = Mobile-Spacing, `compact` = reduzierte Home-Kachel.
 * KEINE Abhängigkeit von MIcon/Mobile-Atomen — die Trailing-Affordanz
 * (Kebab/Chevron/Stift) wird vom Screen als `trailing`-Node injiziert.
 */

const COMPARE_STATUS_LABEL = { active: "aktiv", paused: "pausiert", draft: "draft" };
const COMPARE_CHANNEL_LABEL = { email: "Email", signal: "Signal", telegram: "Telegram", sms: "SMS" };
/* Kanal-Spalten-Limits im Compare-Kontext (CLAUDE.md · Output-Layout-System). */
const COMPARE_CHANNEL_CONSTRAINT = { email: "alle Spalten", telegram: "max 8", signal: "max 6", sms: "flach" };
const COMPARE_WEIGHT_TONE = { hoch: "accent", mittel: "neutral", niedrig: "ghost" };

/* Sekundäraktionen pro Status (Charter §6). Render-agnostisch — Desktop
 * nutzt Dropdown (CompareKebab), Mobile ein Bottom-Sheet. */
function compareActions(status) {
  if (status === "draft") {
    return [
      { key: "edit",  label: "Setup fortsetzen", icon: "edit" },
      { key: "trash", label: "Löschen", icon: "trash", danger: true },
    ];
  }
  const toggle = status === "active"
    ? { key: "pause",  label: "Pausieren",  icon: "check" }
    : { key: "resume", label: "Aktivieren", icon: "check" };
  return [
    toggle,
    { key: "send",    label: "Briefing jetzt senden", icon: "send" },
    { key: "preview", label: "Vorschau öffnen", icon: "search" },
    { key: "edit",    label: "Bearbeiten", icon: "edit" },
    { key: "trash",   label: "Löschen", icon: "trash", danger: true },
  ];
}


/* ─────────────────── CompareStatusPill ───────────────────
 * Status-Badge eines Vergleichs. active = grün gefüllt, sonst Outline. */
function CompareStatusPill({ status, style }) {
  const active = status === "active";
  return (
    <span className="mono" style={{
      padding: "3px 10px", fontSize: 10.5, letterSpacing: "0.1em",
      textTransform: "uppercase", fontWeight: 600,
      background: active ? "var(--g-good)" : "var(--g-card)",
      color: active ? "#fff" : "var(--g-ink-3)",
      border: active ? "none" : "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-pill)",
      display: "inline-flex", alignItems: "center", gap: 6, ...style,
    }}>{COMPARE_STATUS_LABEL[status] || "draft"}</span>
  );
}


/* ─────────────────── CompareTile ───────────────────
 * Kachel eines Orts-Vergleichs. Klick-Ziel = Detail.
 *   dense=true    → Mobile-Spacing, kein Hover/Shadow (Touch)
 *   compact=true  → Home-Variante ohne Kanal-Pills
 *   trailing      → Affordanz oben rechts (Kebab Desktop / Chevron Mobile /
 *                   Stift Home) — vom Screen injiziert
 *   onClick       → öffnet Detail
 */
function CompareTile({ sub, dense = false, compact = false, accent = true, trailing, onClick, style }) {
  const [hover, setHover] = React.useState(false);
  const active = sub.status === "active";
  const draft  = sub.status === "draft";

  return (
    <div
      role="button" tabIndex={0}
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      style={{
        cursor: "pointer", textAlign: "left", width: "100%",
        background: "var(--g-card)",
        border: "1px solid var(--g-rule)",
        borderColor: hover && !dense ? "var(--g-ink-3)" : "var(--g-rule)",
        borderLeft: accent && active ? "3px solid var(--g-accent)" : "1px solid var(--g-rule)",
        borderRadius: "var(--g-r-3)",
        boxShadow: dense ? "none" : (hover ? "var(--g-shadow-2, 0 6px 20px rgba(0,0,0,0.10))" : "var(--g-shadow-1)"),
        transition: "box-shadow 120ms, border-color 120ms",
        padding: dense ? "14px 14px" : "16px 18px", minHeight: 44,
        display: "flex", flexDirection: "column", gap: dense ? 10 : 12,
        opacity: draft && !dense ? 0.94 : 1,
        ...style,
      }}>
      {/* Kopf */}
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <span style={{ marginTop: dense ? 5 : 6, flexShrink: 0 }}>
          <Dot tone={active ? "good" : "neutral"} size={7}/>
        </span>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{
            fontSize: dense ? 15 : 15.5, fontWeight: 600, letterSpacing: "-0.01em", lineHeight: 1.25,
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>{sub.name}</div>
          <div style={{ display: "flex", alignItems: "center", gap: 7, marginTop: 3 }}>
            <span className="mono" style={{ fontSize: 9.5, color: "var(--g-ink-4)", textTransform: "uppercase", letterSpacing: "0.14em" }}>
              {COMPARE_STATUS_LABEL[sub.status] || "draft"}
            </span>
            <span style={{ fontSize: 12, color: "var(--g-ink-3)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>· {sub.region}</span>
          </div>
        </div>
        {trailing && (
          <div style={{ flexShrink: 0, marginTop: 2 }} onClick={(e) => e.stopPropagation()}>{trailing}</div>
        )}
      </div>

      {/* Meta */}
      <div className="mono" style={{ fontSize: dense ? 11 : 11.5, color: "var(--g-ink-2)", letterSpacing: "0.02em", paddingLeft: 17 }}>
        {sub.locationIds.length} {sub.locationIds.length === 1 ? "Ort" : "Orte"} · {sub.profileLabel}
      </div>

      {/* Kanäle (nicht in der kompakten Home-Kachel) */}
      {!compact && (
        <div style={{ display: "flex", flexWrap: "wrap", gap: dense ? 4 : 5, paddingLeft: 17, minHeight: dense ? 18 : 20 }}>
          {sub.channels.length === 0
            ? <span className="mono" style={{ fontSize: dense ? 10 : 11, color: "var(--g-ink-4)" }}>noch keine Kanäle</span>
            : sub.channels.map(ch => (
                <span key={ch} className="mono" style={{
                  padding: "2px 7px", fontSize: dense ? 9.5 : 10, letterSpacing: "0.04em",
                  border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)",
                  background: "var(--g-card-alt)", color: "var(--g-ink-2)",
                }}>{COMPARE_CHANNEL_LABEL[ch] || ch}</span>
              ))}
        </div>
      )}

      {/* Status-Fuß */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8,
        paddingLeft: 17, paddingTop: 11, borderTop: "1px dashed var(--g-rule-soft)",
      }}>
        <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.02em" }}>
          {draft ? "Setup unvollständig" : sub.schedule}
        </span>
        {!draft && (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6, fontSize: 11, color: "var(--g-ink-3)" }}>
            <Dot tone={active ? "good" : "neutral"} size={6}/> zuletzt {sub.lastSent}
          </span>
        )}
      </div>
    </div>
  );
}


/* ─────────────────── CompareKebab ───────────────────
 * Desktop-Dropdown für Sekundäraktionen (Charter §6). Eigenes Icon (Punkte),
 * keine MIcon-Abhängigkeit. `defaultOpen` für statische Mockup-Varianten. */
function CompareKebab({ items = [], onSelect, align = "right", defaultOpen = false, btnSize = 38 }) {
  const [open, setOpen] = React.useState(defaultOpen);
  return (
    <div style={{ position: "relative" }}>
      <button
        title="Weitere Aktionen"
        onClick={(e) => { e.stopPropagation(); setOpen(o => !o); }}
        style={{
          width: btnSize, height: btnSize, display: "inline-flex", alignItems: "center", justifyContent: "center",
          background: open ? "var(--g-card-alt)" : "transparent",
          border: "1px solid var(--g-rule-soft)", borderRadius: "var(--g-r-2)", cursor: "pointer",
        }}>
        <svg width="16" height="16" viewBox="0 0 24 24" fill="var(--g-ink-2)"><circle cx="12" cy="5" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="12" cy="19" r="1.7"/></svg>
      </button>
      {open && (
        <div onClick={(e) => e.stopPropagation()} style={{
          position: "absolute", top: btnSize + 4, [align]: 0, zIndex: 20, minWidth: 210,
          background: "var(--g-card)", border: "1px solid var(--g-rule)",
          borderRadius: "var(--g-r-3)", boxShadow: "var(--g-shadow-2, 0 8px 28px rgba(0,0,0,0.14))",
          padding: 6,
        }}>
          {items.map(it => (
            <React.Fragment key={it.key}>
              {it.danger && <div style={{ height: 1, background: "var(--g-rule-soft)", margin: "4px 0" }}/>}
              <button
                onClick={() => { setOpen(false); onSelect && onSelect(it.key); }}
                style={{
                  display: "flex", alignItems: "center", gap: 10, width: "100%",
                  padding: "9px 10px", border: "none", background: "transparent",
                  borderRadius: "var(--g-r-2)", cursor: "pointer", textAlign: "left",
                  fontSize: 13, fontFamily: "var(--g-font-sans)",
                  color: it.danger ? "var(--g-bad)" : "var(--g-ink)",
                }}>{it.label}</button>
            </React.Fragment>
          ))}
        </div>
      )}
    </div>
  );
}


/* ─────────────────── CompareLocationRow ───────────────────
 * Gerankte Orts-Zeile in der Detail-Card „Verglichene Orte". */
function CompareLocationRow({ loc, index = 0, dense = false, alt = false, style }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: dense ? 12 : 14,
      padding: dense ? "12px 14px" : "12px 20px",
      background: alt ? "var(--g-paper-deep)" : "transparent",
      borderTop: index === 0 ? "none" : "1px solid var(--g-rule-soft)",
      ...style,
    }}>
      <span className="mono" style={{
        fontSize: 12, fontWeight: 600, color: "var(--g-ink-3)",
        width: dense ? 20 : 24, flexShrink: 0, fontVariantNumeric: "tabular-nums",
      }}>{String(index + 1).padStart(2, "0")}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{loc.name}</div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--g-ink-4)", marginTop: 2, letterSpacing: "0.02em" }}>{loc.group}</div>
      </div>
      <span className="mono" style={{ fontSize: 12, color: "var(--g-ink-2)", flexShrink: 0, fontVariantNumeric: "tabular-nums" }}>{loc.elev} m</span>
    </div>
  );
}


/* ─────────────────── CompareIdealRow ───────────────────
 * Metrik · Idealwert · Gewicht-Pill. Bestimmt das Ranking. */
function CompareIdealRow({ item, dense = false, last = false, style }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: dense ? 10 : 16,
      padding: "11px 0", borderBottom: last ? "none" : "1px dashed var(--g-rule-soft)",
      ...style,
    }}>
      <span style={{ flex: 1, fontSize: dense ? 13.5 : 13.5, fontWeight: 500, color: "var(--g-ink)" }}>{item.metric}</span>
      <span className="mono" style={{ fontSize: dense ? 12.5 : 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}>{item.ideal}</span>
      <Pill tone={COMPARE_WEIGHT_TONE[item.weight] || "neutral"}>{item.weight}</Pill>
    </div>
  );
}


/* ─────────────────── CompareLayoutRow ───────────────────
 * Spalten pro Kanal im Briefing. dense → gestapelt (Mobile-Card),
 * sonst Label links / Chips rechts (Desktop). */
function CompareLayoutRow({ channel, cols = [], dense = false, style }) {
  const head = (
    <div style={{ display: dense ? "flex" : "block", justifyContent: "space-between", alignItems: "baseline",
      width: dense ? "100%" : 110, flexShrink: 0, marginBottom: dense ? 8 : 0, paddingTop: dense ? 0 : 2 }}>
      <span style={{ fontSize: 13, fontWeight: 600 }}>{COMPARE_CHANNEL_LABEL[channel]}</span>
      <span className="mono" style={{ fontSize: dense ? 9.5 : 10, color: "var(--g-ink-4)", letterSpacing: "0.06em", textTransform: "uppercase", marginTop: dense ? 0 : 2, display: "block" }}>
        {COMPARE_CHANNEL_CONSTRAINT[channel]}
      </span>
    </div>
  );
  const chips = (
    <div style={{ display: "flex", flexWrap: "wrap", gap: dense ? 5 : 6, flex: 1 }}>
      {cols.length === 0
        ? <span className="mono" style={{ fontSize: 11.5, color: "var(--g-ink-4)" }}>flach · ohne Spalten</span>
        : cols.map((c, i) => (
            <span key={i} className="mono" style={{
              padding: dense ? "3px 8px" : "3px 9px", fontSize: dense ? 10.5 : 11, letterSpacing: "0.02em",
              border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-pill)",
              background: i === 0 ? "var(--g-accent-tint)" : "var(--g-card-alt)",
              color: i === 0 ? "var(--g-accent-deep)" : "var(--g-ink-2)",
            }}>{c}</span>
          ))}
    </div>
  );
  if (dense) {
    return (
      <div style={{ background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: "var(--g-r-3)", padding: "12px 14px", ...style }}>
        {head}{chips}
      </div>
    );
  }
  return (
    <div style={{ display: "flex", gap: 16, alignItems: "flex-start", ...style }}>
      {head}{chips}
    </div>
  );
}


/* ─────────────────── StageDateField ───────────────────
 * Kanonisches, kompaktes Datum-Control für die Etappen-Detail-Ansicht
 * (normale Etappe + Pausentag, Desktop + Mobile). Native <input type="date">
 * (Picker/Tastatur/A11y umsonst) im Token-Rahmen + abgeleiteter Wochentag-Chip.
 * size="lg" für Mobile (44px Touch-Target, 16px = kein iOS-Zoom).
 * Single-Source statt Inline-Variante je Screen (Atomic-Disziplin). */
function stageWeekdayDE(iso) {
  if (!iso) return null;
  const d = new Date(iso + "T00:00:00");
  return ["So", "Mo", "Di", "Mi", "Do", "Fr", "Sa"][d.getDay()];
}

function StageDateField({ value, onChange, isFirst = false, size = "md", align = "right", style }) {
  const wd = stageWeekdayDE(value);
  const sz = size === "lg" ? { minH: 44, fs: 16, chip: 12 } : { minH: 38, fs: 13, chip: 11 };
  return (
    <div style={{ flexShrink: 0, minWidth: 168, ...style }}>
      <div className="mono" style={{
        fontSize: 10, letterSpacing: "0.08em", textTransform: "uppercase",
        color: "var(--g-ink-3)", fontWeight: 500, marginBottom: 6, textAlign: align,
      }}>
        Datum{isFirst && <span style={{ color: "var(--g-accent-deep)" }}> · Tourstart</span>}
      </div>
      <label style={{
        display: "flex", alignItems: "center", gap: 8,
        background: "var(--g-card)", border: "1px solid var(--g-rule)",
        borderRadius: "var(--g-r-2)", padding: "0 10px 0 8px", minHeight: sz.minH,
        cursor: "pointer", boxShadow: "var(--g-shadow-1)",
      }}>
        <span className="mono" style={{
          fontSize: sz.chip, fontWeight: 700, color: "var(--g-accent-deep)",
          background: "var(--g-accent-tint)", borderRadius: 3, padding: "3px 7px",
          letterSpacing: "0.04em", flexShrink: 0,
        }}>{wd || "—"}</span>
        <input
          type="date" value={value || ""}
          onChange={(e) => onChange && onChange(e.target.value)}
          className="mono"
          style={{
            border: "none", outline: "none", background: "transparent",
            fontFamily: "var(--g-font-mono)", fontSize: sz.fs, color: "var(--g-ink)",
            fontVariantNumeric: "tabular-nums", cursor: "pointer", width: "100%", minWidth: 0,
          }}
        />
      </label>
    </div>
  );
}

/* ─────────────────── StageCascadeNotice ───────────────────
 * Inline, nicht-blockierender Vorschlag beim Verschieben der ersten Etappe:
 * „Folge-Etappen mitverschieben?" Zwei Zustände (Vorschlag / erledigt).
 * Flat-Props (days/count/done) — flex-wrap, also Desktop- und Mobile-tauglich. */
function StageCascadeNotice({ days, count, done, onApply, onDismiss, style }) {
  const sign = days > 0 ? "+" : "−";
  const abs = Math.abs(days);
  const dayWord = abs === 1 ? "Tag" : "Tage";
  if (done) {
    return (
      <div style={{
        marginTop: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap",
        padding: "12px 16px", background: "rgba(61,107,58,0.10)",
        borderLeft: "3px solid var(--g-good)", borderRadius: "var(--g-r-2)",
        fontSize: 13, color: "var(--g-ink-2)", ...style,
      }}>
        <Dot tone="good"/>
        <span><strong style={{ color: "var(--g-ink)" }}>{count} Folge-Etappen verschoben</strong> · alle Daten um {sign}{abs} {dayWord} angepasst.</span>
        <button onClick={onDismiss} style={{
          marginLeft: "auto", background: "none", border: "none", padding: 0,
          color: "var(--g-ink-3)", fontSize: 12, cursor: "pointer", textDecoration: "underline",
        }}>Schließen</button>
      </div>
    );
  }
  return (
    <div style={{
      marginTop: 16, display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap",
      padding: "12px 16px", background: "var(--g-accent-tint)",
      borderLeft: "3px solid var(--g-accent)", borderRadius: "var(--g-r-2)", ...style,
    }}>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", flex: 1, minWidth: 240, lineHeight: 1.45 }}>
        <strong style={{ color: "var(--g-ink)" }}>Tourstart um {sign}{abs} {dayWord} verschoben.</strong>{" "}
        Sollen die {count} Folge-Etappen um denselben Betrag mitverschoben werden?
      </div>
      <div style={{ display: "flex", gap: 8 }}>
        <Btn variant="accent" size="sm" onClick={onApply} style={{ whiteSpace: "nowrap" }}>Alle mitverschieben</Btn>
        <Btn variant="ghost" size="sm" onClick={onDismiss} style={{ whiteSpace: "nowrap" }}>Nur diese Etappe</Btn>
      </div>
    </div>
  );
}

/* ─────────────────── Export ─────────────────── */
Object.assign(window, {
  Field,
  DetailRow,
  StageDateField,
  stageWeekdayDE,
  StageCascadeNotice,
  StagePill,
  ChannelRow,
  ChannelChip,
  channelGlyph,
  BriefingTimelineRow,
  BriefingScheduleRow,
  ThresholdRow,
  Stat,
  AlertRow,
  HorizonChips,
  ScoreToggle,
  MetricEditorRow,
  ChannelLimitChip,
  ChannelPreviewCard,
  /* Compare-Domain */
  compareActions,
  CompareStatusPill,
  CompareTile,
  CompareKebab,
  CompareLocationRow,
  CompareIdealRow,
  CompareLayoutRow,
});
