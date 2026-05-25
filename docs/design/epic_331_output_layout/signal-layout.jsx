/* Signal-Layout für Gregor-20 Briefings
 * ─────────────────────────────────────────────────────────
 * Technische Basis (recherchiert, Mai 2026):
 * - Signal unterstützt "body ranges": Bold, Italic, Strikethrough, Monospace, Spoiler.
 *   Kein Markdown-Syntax (*bold* etc.) — programmatisch via signal-cli --text-style.
 * - Kein 160-Zeichen-Limit wie SMS (lange Reports gehen problemlos), aber Display
 *   schneidet auf Desktop bei ~2000 Zeichen ab → wir bleiben darunter.
 * - Volle Unicode/Emoji-Unterstützung.
 * - Anhänge: PNG/PDF/GPX möglich → Höhenprofil als Bild-Card einsetzbar.
 * - Reply-Quote auf einzelne Bubbles → Splittung in mehrere Bubbles macht Sinn.
 *
 * Layout-Strategie:
 *   A) Eine lange Bubble — Vollformat, Monospace-Tabelle, Bold-Header. Closest to status quo.
 *   B) Splittung in 4 Bubbles — jede ist einzeln zitierbar/reactionsfähig, weniger erschlagend.
 *   C) Anhang + Quick-Read — Höhenprofil-PNG oben, kurze Lese-Bubble, separate Daten-Bubble.
 *   D) Dark Mode — gleiche Inhalts-Logik in Signals dunklem Theme.
 */

/* ───────────────────────────────────────────── Theme ───── */

const SIGNAL_THEMES = {
  light: {
    bg: "#ffffff",
    bgChrome: "#ffffff",
    bubbleIn: "#eaeaea",
    bubbleInText: "#1a1a1a",
    bubbleOut: "#1d72f3",
    bubbleOutText: "#ffffff",
    header: "#f6f6f6",
    headerText: "#1a1a1a",
    rule: "rgba(0,0,0,0.08)",
    mutedText: "#7a7a7a",
    link: "#1d72f3",
    composerBg: "#f6f6f6",
    statusBarText: "#1a1a1a",
    attachmentBg: "#dadada",
  },
  dark: {
    bg: "#1b1b1b",
    bgChrome: "#1b1b1b",
    bubbleIn: "#2c2c2c",
    bubbleInText: "#ededed",
    bubbleOut: "#2a7df3",
    bubbleOutText: "#ffffff",
    header: "#1b1b1b",
    headerText: "#ededed",
    rule: "rgba(255,255,255,0.10)",
    mutedText: "#8c8c8c",
    link: "#7ab1f8",
    composerBg: "#252525",
    statusBarText: "#ffffff",
    attachmentBg: "#3a3a3a",
  },
};

const SIGNAL_FONT = "-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif";
// Signal verwendet auf iOS Menlo, auf Android Roboto Mono. JetBrains Mono ist visuell sehr ähnlich.
const SIGNAL_MONO = "ui-monospace, Menlo, 'SF Mono', 'JetBrains Mono', 'Roboto Mono', monospace";

/* ───────────────────────────────────────────── Phone-Frame ───── */

/* Tall Phone Frame: zeigt die ganze Konversation als wäre durchgescrollt.
 * Status-Bar oben, Signal-Chat-Header darunter, dann beliebig viel Content,
 * Composer ganz unten. Bezel rundherum.
 */
function SignalPhone({ theme = "light", height, children, name = "Gregor Zwanzig", lastSeen = "online", time = "07:03" }) {
  const t = SIGNAL_THEMES[theme];
  return (
    <div style={{
      width: 387, margin: "0 auto",
      background: "#0e0e0c", padding: 6,
      borderRadius: 38,
      boxShadow: "0 24px 60px rgba(26,26,24,0.18), 0 4px 12px rgba(26,26,24,0.08)",
    }}>
      <div style={{
        position: "relative", width: 375,
        background: t.bg, borderRadius: 32, overflow: "hidden",
        display: "flex", flexDirection: "column",
        minHeight: height,
        fontFamily: SIGNAL_FONT,
      }}>
        <SignalStatusBar t={t} time={time}/>
        <SignalChatHeader t={t} name={name} lastSeen={lastSeen}/>
        <div style={{ flex: 1, background: t.bg, position: "relative" }}>
          {children}
        </div>
        <SignalComposer t={t}/>
        <SignalHomeIndicator t={t}/>
      </div>
    </div>
  );
}

function SignalStatusBar({ t, time }) {
  const c = t.statusBarText;
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "14px 26px 6px", height: 44, flexShrink: 0,
      background: t.bgChrome,
    }}>
      <span style={{ fontSize: 15, fontWeight: 600, color: c, letterSpacing: "-0.01em" }}>{time}</span>
      <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
        <svg width="17" height="11" viewBox="0 0 17 11">
          <rect x="0" y="7" width="3" height="4" rx="0.7" fill={c}/>
          <rect x="4.5" y="5" width="3" height="6" rx="0.7" fill={c}/>
          <rect x="9" y="2.5" width="3" height="8.5" rx="0.7" fill={c}/>
          <rect x="13.5" y="0" width="3" height="11" rx="0.7" fill={c}/>
        </svg>
        <svg width="15" height="11" viewBox="0 0 15 11">
          <path d="M7.5 3C9.5 3 11.4 3.8 12.7 5L13.7 4C12.1 2.4 9.9 1.3 7.5 1.3C5.1 1.3 2.9 2.4 1.3 4L2.3 5C3.6 3.8 5.5 3 7.5 3Z" fill={c}/>
          <path d="M7.5 6C8.7 6 9.8 6.4 10.6 7.2L11.6 6.2C10.5 5.1 9 4.4 7.5 4.4C6 4.4 4.5 5.1 3.4 6.2L4.4 7.2C5.2 6.4 6.3 6 7.5 6Z" fill={c}/>
          <circle cx="7.5" cy="9.4" r="1.3" fill={c}/>
        </svg>
        <svg width="25" height="12" viewBox="0 0 25 12">
          <rect x="0.5" y="0.5" width="22" height="11" rx="3" stroke={c} strokeOpacity="0.4" fill="none"/>
          <rect x="2" y="2" width="18" height="8" rx="1.5" fill={c}/>
          <rect x="23.5" y="3.5" width="1.5" height="5" rx="0.5" fill={c} fillOpacity="0.5"/>
        </svg>
      </div>
    </div>
  );
}

function SignalChatHeader({ t, name, lastSeen }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "6px 12px 10px",
      borderBottom: `1px solid ${t.rule}`,
      background: t.header,
      flexShrink: 0,
    }}>
      {/* Back chevron + unread count */}
      <button aria-label="Zurück" style={{
        display: "inline-flex", alignItems: "center", gap: 2,
        background: "transparent", border: "none", color: t.link, padding: "8px 4px 8px 0",
        cursor: "pointer",
      }}>
        <svg width="12" height="20" viewBox="0 0 12 20" fill="none">
          <path d="M10 2L2 10L10 18" stroke={t.link} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"/>
        </svg>
        <span style={{ fontSize: 17, color: t.link, fontWeight: 400, marginLeft: -2 }}>4</span>
      </button>

      {/* Avatar */}
      <div style={{
        width: 36, height: 36, borderRadius: "50%",
        background: "linear-gradient(135deg, #c45a2a 0%, #8c3e1a 100%)",
        color: "#fff", display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 14, fontWeight: 600, letterSpacing: "0.01em",
        boxShadow: "inset 0 0 0 1px rgba(255,255,255,0.1)",
      }}>GZ</div>

      {/* Name + status */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 16, fontWeight: 600, color: t.headerText, lineHeight: 1.15, letterSpacing: "-0.01em" }}>
          {name}
        </div>
        <div style={{ fontSize: 12, color: t.mutedText, marginTop: 1 }}>
          {lastSeen}
        </div>
      </div>

      {/* Call icons */}
      <button aria-label="Video" style={iconBtn(t)}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <path d="M3 7a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2zM16 10l5-3v10l-5-3z" stroke={t.link} strokeWidth="1.8" strokeLinejoin="round"/>
        </svg>
      </button>
      <button aria-label="Anruf" style={iconBtn(t)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <path d="M5 4h4l2 5-3 2a12 12 0 0 0 5 5l2-3 5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z" stroke={t.link} strokeWidth="1.8" strokeLinejoin="round" strokeLinecap="round"/>
        </svg>
      </button>
    </div>
  );
}

function iconBtn(t) {
  return {
    width: 38, height: 38, display: "inline-flex",
    alignItems: "center", justifyContent: "center",
    background: "transparent", border: "none", cursor: "pointer", padding: 0,
  };
}

function SignalComposer({ t }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 6,
      padding: "8px 10px 10px",
      background: t.bgChrome,
      borderTop: `1px solid ${t.rule}`,
      flexShrink: 0,
    }}>
      <button aria-label="Anhang" style={iconBtn(t)}>
        <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="9.5" stroke={t.mutedText} strokeWidth="1.6"/>
          <path d="M12 8v8M8 12h8" stroke={t.mutedText} strokeWidth="1.6" strokeLinecap="round"/>
        </svg>
      </button>
      <div style={{
        flex: 1, minHeight: 36, padding: "8px 14px",
        background: t.composerBg, color: t.mutedText,
        borderRadius: 18,
        fontSize: 15, display: "flex", alignItems: "center",
        border: `1px solid ${t.rule}`,
      }}>Signal-Nachricht</div>
      <button aria-label="Sprachnachricht" style={iconBtn(t)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
          <rect x="9" y="3" width="6" height="12" rx="3" stroke={t.link} strokeWidth="1.8"/>
          <path d="M5 11a7 7 0 0 0 14 0M12 18v3" stroke={t.link} strokeWidth="1.8" strokeLinecap="round"/>
        </svg>
      </button>
    </div>
  );
}

function SignalHomeIndicator({ t }) {
  return (
    <div style={{
      height: 24, flexShrink: 0,
      display: "flex", alignItems: "flex-end", justifyContent: "center",
      paddingBottom: 8,
      background: t.bgChrome,
    }}>
      <div style={{ width: 134, height: 5, borderRadius: 3, background: t.statusBarText, opacity: 0.85 }}/>
    </div>
  );
}

/* ─────────────────────────────────────── Date separator ─── */

function SignalDateSep({ t, label = "Heute" }) {
  return (
    <div style={{
      display: "flex", justifyContent: "center",
      padding: "14px 0 8px",
    }}>
      <span style={{
        fontSize: 11, fontWeight: 600,
        color: t.mutedText, letterSpacing: "0.04em",
        textTransform: "uppercase",
        padding: "4px 10px",
        background: t.bg,
      }}>{label}</span>
    </div>
  );
}

/* ───────────────────────────────────────── Bubble + parts ─── */

function SignalBubble({ t, children, side = "in", time, status, withTail = true, style }) {
  const isOut = side === "out";
  return (
    <div style={{
      padding: "0 12px 4px",
      display: "flex", justifyContent: isOut ? "flex-end" : "flex-start",
    }}>
      <div style={{ maxWidth: 296, display: "flex", flexDirection: "column", alignItems: isOut ? "flex-end" : "flex-start" }}>
        <div style={{
          background: isOut ? t.bubbleOut : t.bubbleIn,
          color: isOut ? t.bubbleOutText : t.bubbleInText,
          borderRadius: 18,
          borderBottomRightRadius: isOut && withTail ? 4 : 18,
          borderBottomLeftRadius: !isOut && withTail ? 4 : 18,
          padding: "8px 12px 9px",
          fontSize: 15, lineHeight: 1.34,
          wordBreak: "break-word",
          ...style,
        }}>
          {children}
        </div>
        {(time || status) && (
          <div style={{
            fontSize: 11, color: t.mutedText, marginTop: 3, marginBottom: 2,
            display: "flex", alignItems: "center", gap: 4,
            padding: "0 4px",
          }}>
            {time && <span>{time}</span>}
            {status === "delivered" && <DoubleCheck color={t.mutedText}/>}
            {status === "read"      && <DoubleCheck color={t.link}/>}
          </div>
        )}
      </div>
    </div>
  );
}

function DoubleCheck({ color }) {
  return (
    <svg width="14" height="10" viewBox="0 0 14 10" fill="none">
      <path d="M1 5.5l2.5 2.5L9 1.5" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
      <path d="M5 5.5l2.5 2.5L13 1.5" stroke={color} strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

/* Inline formatting helpers — entsprechen Signal body-ranges */
function Mono({ children, style }) {
  return <span style={{ fontFamily: SIGNAL_MONO, fontSize: 12.5, letterSpacing: "0", ...style }}>{children}</span>;
}
function B({ children }) {
  return <span style={{ fontWeight: 700 }}>{children}</span>;
}
function I({ children }) {
  return <span style={{ fontStyle: "italic" }}>{children}</span>;
}

/* Attachment-Card im Bubble-Stil (Bild-Vorschau) */
function SignalAttachment({ t, kind = "elevation", caption }) {
  return (
    <div style={{
      padding: "0 12px 6px",
      display: "flex", justifyContent: "flex-start",
    }}>
      <div style={{ maxWidth: 296 }}>
        <div style={{
          background: t.bubbleIn,
          borderRadius: 16,
          overflow: "hidden",
          padding: 4,
        }}>
          <div style={{
            width: 280, height: 158,
            background: t.attachmentBg,
            borderRadius: 12,
            position: "relative",
            overflow: "hidden",
          }}>
            {kind === "elevation" && <ElevationPNGPreview t={t}/>}
            {kind === "map" && <MapPNGPreview t={t}/>}
            <div style={{
              position: "absolute", bottom: 8, left: 10, right: 10,
              fontSize: 10, fontFamily: SIGNAL_MONO,
              color: t.bubbleInText, opacity: 0.7,
              display: "flex", justifyContent: "space-between",
            }}>
              <span>{kind === "elevation" ? "KHW_03_profile.png" : "KHW_03_map.png"}</span>
              <span>· 24 KB</span>
            </div>
          </div>
          {caption && (
            <div style={{ padding: "8px 10px 4px", fontSize: 14, color: t.bubbleInText, lineHeight: 1.35 }}>
              {caption}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function ElevationPNGPreview({ t }) {
  // Höhenprofil-Skizze als SVG: KHW_03 Porze → Hochweißsteinhaus
  // Startwert 1942 oben links, fällt auf 1867 bis Mitte, dann flach bis Ende.
  const dark = t.bubbleInText === "#ededed";
  return (
    <svg width="280" height="158" viewBox="0 0 280 158" style={{ display: "block" }}>
      <defs>
        <linearGradient id="elevFill" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor="#c45a2a" stopOpacity={dark ? 0.55 : 0.4}/>
          <stop offset="100%" stopColor="#c45a2a" stopOpacity="0"/>
        </linearGradient>
      </defs>
      {/* horizontal grid */}
      {[0,1,2,3].map(i => (
        <line key={i} x1="32" y1={28 + i*30} x2="270" y2={28 + i*30} stroke={dark ? "rgba(255,255,255,0.06)" : "rgba(0,0,0,0.06)"} strokeWidth="1"/>
      ))}
      {/* y-axis labels */}
      {[
        { y: 30, v: "2000" },
        { y: 60, v: "1900" },
        { y: 90, v: "1800" },
        { y: 120, v: "1700" },
      ].map(s => (
        <text key={s.v} x="6" y={s.y + 3} fontSize="8.5" fontFamily={SIGNAL_MONO} fill={dark ? "rgba(255,255,255,0.5)" : "rgba(0,0,0,0.45)"}>{s.v}</text>
      ))}
      {/* profile area */}
      <path d="M32 58 L70 50 L100 64 L130 76 L155 88 L180 96 L210 100 L240 102 L270 104 L270 130 L32 130 Z"
        fill="url(#elevFill)"/>
      <path d="M32 58 L70 50 L100 64 L130 76 L155 88 L180 96 L210 100 L240 102 L270 104"
        stroke="#c45a2a" strokeWidth="1.8" fill="none" strokeLinejoin="round"/>
      {/* x-axis labels */}
      <text x="32" y="146" fontSize="8.5" fontFamily={SIGNAL_MONO} fill={dark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.5)"}>Porze</text>
      <text x="234" y="146" fontSize="8.5" fontFamily={SIGNAL_MONO} fill={dark ? "rgba(255,255,255,0.55)" : "rgba(0,0,0,0.5)"}>1867m</text>
      <text x="115" y="146" fontSize="8.5" fontFamily={SIGNAL_MONO} fill={dark ? "rgba(255,255,255,0.4)" : "rgba(0,0,0,0.35)"}>9.8 km · ↓75</text>
      {/* min/max dots */}
      <circle cx="70"  cy="50"  r="2.4" fill="#c45a2a"/>
      <circle cx="240" cy="102" r="2.4" fill="#c45a2a"/>
    </svg>
  );
}

function MapPNGPreview({ t }) {
  const dark = t.bubbleInText === "#ededed";
  return (
    <svg width="280" height="158" viewBox="0 0 280 158" style={{ display: "block" }}>
      <rect width="280" height="158" fill={dark ? "#2a2a2a" : "#d9d4c8"}/>
      {/* contour lines */}
      {[0,1,2,3,4,5,6,7].map(i => (
        <path key={i}
          d={`M0 ${20 + i * 18} Q 70 ${5 + i*18} 140 ${30 + i*18} T 280 ${20 + i*18}`}
          stroke={dark ? "rgba(255,255,255,0.07)" : "rgba(0,0,0,0.10)"} strokeWidth="1" fill="none"/>
      ))}
      {/* track */}
      <path d="M30 120 Q 90 80 140 90 T 250 60" stroke="#c45a2a" strokeWidth="2.2" fill="none" strokeLinecap="round"/>
      <circle cx="30" cy="120" r="4" fill="#c45a2a"/>
      <circle cx="250" cy="60" r="4" fill="#3d6b3a"/>
    </svg>
  );
}

/* ───────────────────────────────────────── Report content ─── */
/* KHW Etappe: Porze – Hochweißsteinhaus (entspricht der Referenz-Screenshot)
 * Hier werden die Inhalte in mehreren Granularitäten bereitgestellt,
 * damit jede Variante sich daraus bedienen kann.
 */

const RPT = {
  subject: "[KHW] Porze → Hochweißsteinhaus · Abend · D13 W10 G29",
  preheader: "Abend-Briefing für die morgige Etappe",
  date: "Fr · 22.05.2026 · 07:03",
  tour: "Karnischer Höhenweg",
  stage: "Porze → Hochweißsteinhaus",
  dateOnly: "Sa, 23.05.2026",
  stats: { km: 9.8, asc: 280, dsc: 355, max: 1942 },
  overview: "12–23 °C, trocken, schwacher Wind 11 km/h, Böen bis 30 km/h ab 07:00.",
  daylight: {
    range: "04:38 – 21:34",
    span: "16h 55m",
    dawn: "04:38",
    sunrise: "05:19",
    sunset: "20:53",
  },
  // Mehrsegment-Tour: 3 Abschnitte. Beispiel für die typische Struktur einer Etappe.
  segments: [
    {
      label: "Aufstieg Porze",
      when: "08:00 – 10:00",
      km: 3.2,
      altFrom: 1660,
      altTo: 1942,
      rows: [
        { t: "08", tmp: 10.4, w: 12, g: 22, r: 0.0, rp: 0,  c: 70, sun: "☀" },
        { t: "09", tmp: 11.6, w: 11, g: 30, r: 0.0, rp: 0,  c: 80, sun: "☀" },
        { t: "10", tmp: 12.8, w:  9, g: 29, r: 0.0, rp: 0,  c: 80, sun: "☀" },
      ],
    },
    {
      label: "Höhenkamm",
      when: "10:00 – 11:30",
      km: 4.1,
      altFrom: 1942,
      altTo: 1880,
      rows: [
        { t: "10", tmp: 12.8, w:  9, g: 29, r: 0.0, rp: 0,  c: 80, sun: "☀" },
        { t: "11", tmp: 13.8, w:  8, g: 20, r: 0.0, rp: 0,  c: 80, sun: "☀" },
      ],
    },
    {
      label: "Abstieg Hütte",
      when: "11:30 – 12:26",
      km: 2.5,
      altFrom: 1880,
      altTo: 1867,
      rows: [
        { t: "11", tmp: 13.8, w:  8, g: 20, r: 0.0, rp: 0,  c: 80, sun: "☀" },
        { t: "12", tmp: 14.6, w:  7, g: 18, r: 0.0, rp: 0,  c: 75, sun: "☀" },
      ],
    },
  ],
  destDay: {
    when: "12:26 – 14:00",
    alt: 1867,
    rows: [
      { t: "12", tmp: 21.2, w:  8, g: 17, r: 0.0, rp: 0, c: 80, sun: "☀" },
      { t: "13", tmp: 22.0, w: 10, g: 20, r: 0.0, rp: 0, c: 80, sun: "☀" },
      { t: "14", tmp: 22.7, w: 10, g: 20, r: 0.0, rp: 0, c: 80, sun: "☀" },
    ],
  },
  night: {
    when: "14:00 → 06:00",
    alt: 1867,
    rows: [
      { t: "14", tmp: 22.7, w: 10, g: 20, r: 0.0, rp: 3,  c: 80, sun: "☀" },
      { t: "16", tmp: 22.9, w:  9, g: 19, r: 0.0, rp: 8,  c: 79, sun: "☀" },
      { t: "18", tmp: 21.1, w:  9, g: 19, r: 0.0, rp: 0,  c: 70, sun: "☀" },
      { t: "20", tmp: 16.5, w:  7, g: 13, r: 0.0, rp: 0,  c: 73, sun: "🌙" },
      { t: "22", tmp: 15.0, w:  8, g: 13, r: 0.0, rp: 0,  c: 80, sun: "🌙" },
      { t: "00", tmp: 14.2, w:  8, g: 14, r: 0.0, rp: 0,  c: 80, sun: "🌙" },
    ],
    note: "2h-Blöcke (Minimum)",
  },
  next: {
    label: "Nächste Etappe · So",
    title: "Hochweißsteinhaus → Wolayersee",
    summary: "17–21 °C, trocken, Wind 8 km/h, Böen bis 30 km/h ab 17:00.",
  },
  summary: "Tiefste Nacht 14,2 °C (00:00). Keine kritischen Schwellwerte.",
  units: "°C · km/h · mm · % · W/m²",
  source: "openmeteo · icon_d2",
  generated: "2026-05-22 07:03 UTC",
};

/* ─── Bubble-Building-Blocks ─── */

/* Monospace-Tabelle, optimiert auf ≤ 28 Zeichen Breite (passt in Signal-Bubble) */
function MonoTable({ rows, t, color }) {
  const head = "hh   °C  W  G  R%  ⛅";
  return (
    <Mono style={{ display: "block", whiteSpace: "pre", color: color || t.bubbleInText, lineHeight: 1.5 }}>
{head + "\n"}{rows.map(r => {
  const tmp = r.tmp.toFixed(1).padStart(4, " ");
  const w   = String(r.w).padStart(2, " ");
  const g   = String(r.g).padStart(2, " ");
  const rp  = String(r.rp).padStart(3, " ");
  return `${r.t}  ${tmp} ${w} ${g} ${rp}  ${r.sun}`;
}).join("\n")}
    </Mono>
  );
}

/* Sektion-Header innerhalb einer Bubble — Bold + dezenter Trenner */
function SectionHead({ children, color }) {
  return (
    <div style={{
      fontSize: 14, fontWeight: 700, letterSpacing: "-0.005em",
      marginTop: 10, marginBottom: 4,
      color: color,
    }}>{children}</div>
  );
}

/* ─────────────────────────────────────────── Variants ─── */

/* Variant B · Empfehlung
 *
 * Inhaltliche Aufteilung:
 *   Bubble 1  · Quick-Read       — Headline + Streckendaten + Prosa-Zusammenfassung + Tageslicht
 *   Bubble 2…N · Pro Segment   — jeweils Label, Eckdaten, Mono-Tabelle. Skaliert linear.
 *   Bubble N+1 · Ziel & Nacht  — zwei Tabellen, gleicher Ort
 *   Bubble N+2 · Outlook       — nächste Etappe + Footer (Quelle, Zeitstempel)
 *
 * Entscheidungen:
 *   — Jede Bubble ist einzeln zitierbar, reagierbar, Push-tauglich.
 *   — Erste Bubble enthält bereits alles für eine Go/No-Go-Entscheidung;
 *     der Rest ist Vertiefung.
 *   — Keine dekorativen Emojis. Wetter-Glyphs (☀ ☁ 🌙 ⚡) bleiben — sie tragen Info.
 *   — Bold für Sektionstitel + kritische Werte; alles andere bleibt regular.
 */
function VariantB({ theme = "light" }) {
  const t = SIGNAL_THEMES[theme];
  const segCount = RPT.segments.length;
  // Bubble-Anzahl: 1 Quick-Read + segCount + 1 Ziel + 1 Outlook
  const phoneHeight = 600 + segCount * 230 + 600;
  return (
    <SignalPhone theme={theme} height={phoneHeight} time="07:03" lastSeen="Signal-Bot · 07:03">
      <SignalDateSep t={t} label="Heute · 22. Mai"/>

      {/* ── Bubble 1 · Quick-Read ── */}
      <SignalBubble t={t} time="07:03">
        <Mono style={{ display: "block", color: t.mutedText, fontSize: 10.5, marginBottom: 6 }}>
          KHW · ABEND-BRIEFING · 22.05.
        </Mono>
        <div style={{ fontSize: 16, fontWeight: 700, letterSpacing: "-0.01em", lineHeight: 1.25 }}>
          {RPT.stage}
        </div>
        <Mono style={{ display: "block", color: t.mutedText, fontSize: 12.5, marginTop: 4 }}>
          {RPT.dateOnly} · {RPT.stats.km} km · ↑{RPT.stats.asc} ↓{RPT.stats.dsc} · max {RPT.stats.max} m
        </Mono>
        <div style={{ marginTop: 10, fontSize: 14.5, lineHeight: 1.45 }}>
          {RPT.overview}
        </div>
        <div style={{ marginTop: 8, fontSize: 14.5, lineHeight: 1.45 }}>
          Tageslicht <B>{RPT.daylight.range}</B> ({RPT.daylight.span}). {RPT.summary}
        </div>
      </SignalBubble>

      {/* ── Bubble je Segment ── */}
      {RPT.segments.map((seg, i) => (
        <SignalBubble key={i} t={t} time="07:03">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
            <div style={{ fontSize: 14, fontWeight: 700 }}>
              Segment {i + 1} · {seg.label}
            </div>
            <Mono style={{ color: t.mutedText, fontSize: 11.5, whiteSpace: "nowrap" }}>
              {seg.when}
            </Mono>
          </div>
          <Mono style={{ display: "block", color: t.mutedText, fontSize: 11.5, marginBottom: 6 }}>
            {seg.km} km · {seg.altFrom} → {seg.altTo} m
          </Mono>
          <MonoTable rows={seg.rows} t={t}/>
        </SignalBubble>
      ))}

      {/* ── Bubble · Ziel (Tag + Nacht zusammen) ── */}
      <SignalBubble t={t} time="07:03">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
          <div style={{ fontSize: 14, fontWeight: 700 }}>
            Wetter am Ziel
          </div>
          <Mono style={{ color: t.mutedText, fontSize: 11.5 }}>
            {RPT.destDay.alt} m
          </Mono>
        </div>

        <Mono style={{ display: "block", color: t.mutedText, fontSize: 11.5, marginTop: 4, marginBottom: 4 }}>
          Ankunft + Nachmittag · {RPT.destDay.when}
        </Mono>
        <MonoTable rows={RPT.destDay.rows} t={t}/>

        <Mono style={{ display: "block", color: t.mutedText, fontSize: 11.5, marginTop: 10, marginBottom: 4 }}>
          Nacht · {RPT.night.when} · {RPT.night.note}
        </Mono>
        <MonoTable rows={RPT.night.rows} t={t}/>
      </SignalBubble>

      {/* ── Bubble · Outlook + Footer ── */}
      <SignalBubble t={t} time="07:03" status="read">
        <div style={{ fontSize: 14, fontWeight: 700, marginBottom: 4 }}>
          {RPT.next.label}
        </div>
        <div style={{ fontSize: 14 }}>
          <B>{RPT.next.title}</B>
        </div>
        <div style={{ fontSize: 13.5, color: t.mutedText, marginTop: 3 }}>
          {RPT.next.summary}
        </div>
        <Mono style={{ display: "block", color: t.mutedText, marginTop: 10, fontSize: 10.5, lineHeight: 1.5 }}>
          Einheiten: {RPT.units}{"\n"}{RPT.generated} · {RPT.source}
        </Mono>
      </SignalBubble>
    </SignalPhone>
  );
}

/* ─────────────────────────────────────────── Readme Card ─── */

function SignalReadmeCard() {
  return (
    <div style={{
      padding: 28, background: "var(--g-card)", height: "100%",
      overflow: "auto", border: "1px solid var(--g-rule)", borderRadius: 6,
      fontFamily: "var(--g-font-sans)",
    }}>
      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--g-ink-3)", marginBottom: 8 }}>
        Output-Kanal · Signal Messenger Mobile
      </div>
      <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 12px" }}>
        Was Signal kann — und was die Layout-Entscheidungen daraus ableitet
      </h1>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.6, marginBottom: 18 }}>
        Recherchiert gegen Signal-Doku, Source-Code & signal-cli (Stand Mai 2026). Die Tabellen-Spalten und Bubble-Breiten sind aus diesen Constraints abgeleitet.
      </div>

      <ReadmeRowSig tag="A · Formatierung" verdict="Bold, Italic, Strike, Monospace, Spoiler"
        text={'Signal kennt „body ranges“ — Format-Spans als Metadaten neben dem Textinhalt. Kein Markdown-Syntax: Asterisks bleiben Asterisks. Programmatisch via signal-cli --text-style="BOLD:0:10" setzbar. → Wir nutzen Bold für Sektion-Header und kritische Werte, Monospace für Tabellen.'}/>

      <ReadmeRowSig tag="B · Längen-Limit" verdict="Kein 160-Limit, aber ≤ 2000 Zeichen pro Bubble"
        text="Anders als SMS keine harte Segmentierung. Signal-Desktop kürzt allerdings die Anzeige bei ~2000 Zeichen. Mehrere Bubbles in einer Sendung umgehen das sauber — jede Bubble bleibt unter 600 Zeichen."/>

      <ReadmeRowSig tag="C · Bubble-Breite" verdict="≈ 296 px (iPhone 13/14/15)"
        text="Maximale Bubble-Breite auf iPhone 6.1″ ≈ 296 px. Monospace-Tabelle bei Menlo 12.5px = ca. 28 Zeichen. → 6-Spalten-Tabelle (hh · °C · W · G · R% · Wetter-Glyph). Mehr passt nicht zuverlässig, bei Body-Schriftgröße L noch weniger."/>

      <ReadmeRowSig tag="D · Antwort-Zitate" verdict="Pro Bubble einzeln"
        text={'Reply-Quote referenziert genau eine Bubble. → Splittung erlaubt z. B. „diese Tabelle bitte mit Böen-Indikator“ gezielt auf die richtige Bubble. Bei einer Mega-Bubble referenziert das Zitat den ganzen Block — unbrauchbar für Detail-Rückfragen.'}/>

      <ReadmeRowSig tag="E · Reactions" verdict="Pro Bubble einzeln"
        text={'✅/❌ Reactions auf eine Bubble. Splittung erlaubt z. B. ❌ auf den Outlook-Block („Etappe verschieben“) oder ✅ auf Quick-Read als Empfangsbestätigung. Single-Bubble verliert diese Granularität.'}/>

      <ReadmeRowSig tag="F · Mehrsegment-Skalierung" verdict="Linear: 1 Bubble pro Segment"
        text="Echte Etappen haben meist 2–4 Segmente (Aufstieg · Höhenkamm · Abstieg). Pattern bleibt: Quick-Read + N Segment-Bubbles + Ziel/Nacht + Outlook. Eine 4-Segment-Etappe = 7 Bubbles, immer noch lesbar im Scroll."/>

      <ReadmeRowSig tag="G · Emoji-Policy" verdict="Nur wenn Info, nie als Schmuck"
        text="Wetter-Glyphs (☀ ☁ 🌙 ⛅ ⚡) ersetzen Worte und sparen Spalten — sie bleiben. Dekorations-Emojis (🌄 🏁 ❄ 🌅) werden konsequent weggelassen. Tour-Codes (KHW · ABEND) tragen die Hierarchie zuverlässiger."/>

      <ReadmeRowSig tag="H · Push-Preview" verdict="Erste ~80 Zeichen"
        text="Push-Notification zeigt typischerweise Sender + 1–3 Zeilen Text. → Erste Zeile jeder Bubble muss self-contained sein. Quick-Read-Bubble bringt Tour-Code, Etappe und Eckdaten in die erste 80 Zeichen."/>

      <ReadmeRowSig tag="I · Dark Mode" verdict="Auto · Light · Dark — vom Empfänger gesteuert"
        text="Wir designen beide; Bold/Mono/Akzentfarben müssen lesbar bleiben. Akzent #c45a2a bleibt unverändert — funktioniert auf #eaeaea und #2c2c2c."/>

      <div style={{
        marginTop: 22, padding: 16,
        background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)",
        borderRadius: 6,
      }}>
        <div className="mono" style={{ fontSize: 10, letterSpacing: "0.12em", textTransform: "uppercase", color: "var(--g-accent)", fontWeight: 600, marginBottom: 6 }}>
          Layout-Pattern
        </div>
        <div style={{ fontSize: 13.5, lineHeight: 1.55, color: "var(--g-ink)" }}>
          Bubble 1 · <B>Quick-Read</B> (Headline + Eckdaten + Prosa-Zusammenfassung + Tageslicht) — reicht für Go/No-Go.<br/>
          Bubble 2…N · <B>pro Segment</B> (Label, Eckdaten, Mono-Tabelle). Skaliert linear.<br/>
          Bubble N+1 · <B>Ziel & Nacht</B> (zwei Tabellen, gleicher Ort).<br/>
          Bubble N+2 · <B>Outlook</B> (nächste Etappe + Quelle + Zeitstempel).
        </div>
      </div>
    </div>
  );
}

function ReadmeRowSig({ tag, verdict, text }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "180px 1fr", gap: 16, padding: "12px 0", borderTop: "1px solid var(--g-rule-soft)" }}>
      <div>
        <div className="mono" style={{ fontSize: 10, color: "var(--g-accent)", textTransform: "uppercase", letterSpacing: "0.08em", fontWeight: 600 }}>{tag}</div>
        <div style={{ fontSize: 12.5, fontWeight: 600, marginTop: 4, color: "var(--g-ink)", lineHeight: 1.35 }}>{verdict}</div>
      </div>
      <div style={{ fontSize: 12.5, color: "var(--g-ink-2)", lineHeight: 1.6 }}>{text}</div>
    </div>
  );
}

/* ─────────────────────────────────────────── Export ─── */

/* Spalten-Overflow-Demo */

const OVERFLOW_ROWS = [
  { t: "10", tmp: 11.6, feels: 8.2, w: 11, g: 30, r: 0.0, rp: 0, c: 80, sun: "☀", sw: 412, sicht: "hoch" },
  { t: "11", tmp: 12.8, feels: 9.0, w:  9, g: 29, r: 0.0, rp: 0, c: 80, sun: "☀", sw: 488, sicht: "hoch" },
  { t: "12", tmp: 13.8, feels: 9.6, w:  8, g: 20, r: 0.0, rp: 0, c: 75, sun: "☀", sw: 521, sicht: "hoch" },
];

function OverflowTableOk({ t }) {
  const head = "hh   °C  W  G  R%  ☁";
  return (
    <Mono style={{ display: "block", whiteSpace: "pre", color: t.bubbleInText, lineHeight: 1.5 }}>
{head + "\n"}{OVERFLOW_ROWS.map(r => {
  const tmp = r.tmp.toFixed(1).padStart(4, " ");
  const w   = String(r.w).padStart(2, " ");
  const g   = String(r.g).padStart(2, " ");
  const rp  = String(r.rp).padStart(3, " ");
  return `${r.t}  ${tmp} ${w} ${g} ${rp}  ${r.sun}`;
}).join("\n")}
    </Mono>
  );
}

function OverflowTableBroken({ t }) {
  const head = "hh   °C  gef   W   G  R%  Cl  Sun Sich";
  return (
    <Mono style={{ display: "block", whiteSpace: "pre-wrap", color: t.bubbleInText, lineHeight: 1.5, wordBreak: "break-all" }}>
{head + "\n"}{OVERFLOW_ROWS.map(r => {
  const tmp = r.tmp.toFixed(1).padStart(4, " ");
  const feels = r.feels.toFixed(1).padStart(4, " ");
  const w   = String(r.w).padStart(2, " ");
  const g   = String(r.g).padStart(2, " ");
  const rp  = String(r.rp).padStart(3, " ");
  const c   = String(r.c).padStart(2, " ");
  const sw  = String(r.sw).padStart(3, " ");
  return `${r.t}  ${tmp} ${feels} ${w} ${g} ${rp}  ${c} ${sw} ${r.sicht}`;
}).join("\n")}
    </Mono>
  );
}

function OverflowDemo({ theme = "light", state = "ok" }) {
  const t = SIGNAL_THEMES[theme];
  const meta = {
    ok:     { tone: "#3d6b3a", label: "6 Spalten · passt",      kicker: "OK",     note: "Default-Auslegung. Tabelle bleibt aligned bei Schrift M auf iPhone 13/14/15." },
    broken: { tone: "#a83232", label: "9 Spalten · bricht",     kicker: "BROKEN", note: "Mono-Zeile überschreitet 272 px Content-Breite. Signal bricht zwangsweise um — Spalten verlieren Ausrichtung." },
    fixed:  { tone: "#c08a1a", label: "6 Spalten + Prosa-Zeile", kicker: "FIX",    note: "Überzählige Metriken laufen als kompakte Prosa-Zeile unter der Tabelle. Bleibt lesbar weil normaler Fliess-Umbruch." },
  }[state];

  return (
    <SignalPhone theme={theme} height={640} time="07:03" lastSeen="Signal-Bot · 07:03">
      <div style={{
        margin: "10px 12px 0", padding: "6px 10px",
        borderLeft: `3px solid ${meta.tone}`,
        background: theme === "dark" ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)",
        borderRadius: 4,
        fontFamily: "var(--g-font-mono)", fontSize: 10.5,
        color: t.bubbleInText, letterSpacing: "0.04em", textTransform: "uppercase",
      }}>
        <span style={{ color: meta.tone, fontWeight: 700 }}>{meta.kicker} · </span>
        {meta.label}
      </div>

      <SignalDateSep t={t} label="Heute · 22. Mai"/>

      <SignalBubble t={t} time="07:03" status="read">
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", gap: 8, marginBottom: 4 }}>
          <div style={{ fontSize: 14, fontWeight: 700 }}>Segment 1 · Aufstieg Porze</div>
          <Mono style={{ color: t.mutedText, fontSize: 11.5 }}>10–12</Mono>
        </div>
        <Mono style={{ display: "block", color: t.mutedText, fontSize: 11.5, marginBottom: 6 }}>
          3,2 km · 1660 → 1942 m
        </Mono>

        {state === "ok" && <OverflowTableOk t={t}/>}
        {state === "broken" && <OverflowTableBroken t={t}/>}
        {state === "fixed" && (
          <React.Fragment>
            <OverflowTableOk t={t}/>
            <div style={{ marginTop: 8, fontSize: 12.5, lineHeight: 1.5, color: t.bubbleInText }}>
              Cloud <B>80–75 %</B> · Sun 412–521 W/m² · Sicht hoch · gef. 8,2–9,6 °C
            </div>
          </React.Fragment>
        )}
      </SignalBubble>

      <div style={{
        margin: "8px 12px 12px", padding: "8px 10px",
        background: theme === "dark" ? "rgba(255,255,255,0.05)" : "rgba(0,0,0,0.04)",
        border: `1px dashed ${theme === "dark" ? "rgba(255,255,255,0.12)" : "rgba(0,0,0,0.12)"}`,
        borderRadius: 4,
        fontSize: 11.5, lineHeight: 1.5,
        color: theme === "dark" ? "rgba(255,255,255,0.7)" : "rgba(0,0,0,0.6)",
      }}>
        {meta.note}
      </div>
    </SignalPhone>
  );
}

function OverflowReadme() {
  const table = [
    { phone: "iPhone 13/14/15 (6.1″)",   m: "6", l: "5", xl: "4", xxl: "4" },
    { phone: "iPhone Pro Max (6.7″)",    m: "7", l: "6", xl: "5", xxl: "4" },
    { phone: "iPhone Mini / SE (5.4″)",  m: "5", l: "4", xl: "3", xxl: "3" },
  ];
  return (
    <div style={{
      padding: 28, background: "var(--g-card)", height: "100%",
      overflow: "auto", border: "1px solid var(--g-rule)", borderRadius: 6,
      fontFamily: "var(--g-font-sans)",
    }}>
      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--g-ink-3)", marginBottom: 8 }}>
        Constraint · Tabellen-Spalten in Signal-Bubble
      </div>
      <h1 style={{ fontSize: 26, fontWeight: 600, letterSpacing: "-0.02em", margin: "0 0 12px" }}>
        Wieviele Spalten passen — und was tun, wenn der User mehr auswählt?
      </h1>
      <div style={{ fontSize: 13, color: "var(--g-ink-2)", lineHeight: 1.6, marginBottom: 20 }}>
        Bubble-Content-Breite ≈ 272 px. Monospace-Glyph (Menlo / SF Mono) skaliert mit der Body-Schriftgröße des Empfängers, die wir nicht kennen. Daher: auf realistischen Worst-Case auslegen + Konfigurations-Limit hart durchsetzen.
      </div>

      <div style={{
        background: "var(--g-card-alt)", border: "1px solid var(--g-rule-soft)",
        borderRadius: 6, overflow: "hidden", marginBottom: 22,
      }}>
        <div style={{
          display: "grid", gridTemplateColumns: "1.6fr 1fr 1fr 1fr 1fr",
          fontFamily: "var(--g-font-mono)", fontSize: 11,
          letterSpacing: "0.08em", textTransform: "uppercase",
          color: "var(--g-ink-3)",
          padding: "10px 14px",
          borderBottom: "1px solid var(--g-rule-soft)",
          background: "var(--g-paper-deep)",
        }}>
          <span>Gerät</span>
          <span style={{ textAlign: "right" }}>Schrift M</span>
          <span style={{ textAlign: "right" }}>L</span>
          <span style={{ textAlign: "right" }}>XL</span>
          <span style={{ textAlign: "right" }}>XXL+</span>
        </div>
        {table.map((r, i) => (
          <div key={i} style={{
            display: "grid", gridTemplateColumns: "1.6fr 1fr 1fr 1fr 1fr",
            padding: "10px 14px",
            borderBottom: i < table.length - 1 ? "1px solid var(--g-rule-soft)" : "none",
            alignItems: "center",
            fontSize: 13.5,
          }}>
            <span>{r.phone}</span>
            <span className="mono" style={{ textAlign: "right", fontWeight: 600 }}>{r.m}</span>
            <span className="mono" style={{ textAlign: "right" }}>{r.l}</span>
            <span className="mono" style={{ textAlign: "right" }}>{r.xl}</span>
            <span className="mono" style={{ textAlign: "right", color: "var(--g-bad)" }}>{r.xxl}</span>
          </div>
        ))}
      </div>

      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--g-ink-3)", marginBottom: 10 }}>
        Entscheidung
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--g-ink)", marginBottom: 18 }}>
        Hard-Limit <B>6 Spalten</B> pro Tabelle für Signal. Deckt 95 % der Empfänger sauber ab (iPhone 13+ bei Schrift M oder L). iPhone Mini/SE bei Schrift L würde marginal umbrechen — vertretbar gegen den Gewinn an Datendichte.
      </div>

      <div className="mono" style={{ fontSize: 10, letterSpacing: "0.14em", textTransform: "uppercase", color: "var(--g-ink-3)", marginBottom: 10 }}>
        Wo das durchgesetzt wird
      </div>
      <div style={{ fontSize: 13.5, lineHeight: 1.6, color: "var(--g-ink)" }}>
        <B>Im Metriken-Editor</B>, kanal-spezifisch. Pro Kanal eine Spalten-Auswahl mit Live-Counter „X / 6 Tabelle · Y als Prosa“. Spalten oberhalb des Limits werden automatisch in eine <B>Prosa-Zeile</B> unter der Tabelle verschoben (siehe rechte Demo — „Fix“). Nicht in der Anzeige abfangen — die Empfänger-Schriftgröße ist serverseitig unbekannt.
      </div>
    </div>
  );
}

Object.assign(window, {
  VariantB,
  OverflowDemo, OverflowReadme,
  SignalReadmeCard,
  SignalPhone, SignalBubble, SignalDateSep, Mono, B, I,
  SIGNAL_THEMES, SIGNAL_FONT, SIGNAL_MONO,
});
