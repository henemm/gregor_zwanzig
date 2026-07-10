/* Atoms v2 — kleine wiederverwendbare Bausteine.
 * Werden global an window angehängt, damit andere .jsx sie nutzen können.
 */

const { useState, useEffect, useRef, useMemo } = React;

/* ─────────────────── Topo Background ─────────────────── */
function TopoBg({ opacity = 0.5, color = "#1a1a18", lines = 22, density = 1, style }) {
  // Pseudo-Höhenlinien als gestapelte SVG-Pfade
  const paths = useMemo(() => {
    const out = [];
    const rng = mulberry32(42);
    for (let i = 0; i < lines; i++) {
      const y = 50 + i * (700 / lines);
      const points = [];
      const segs = 12;
      for (let s = 0; s <= segs; s++) {
        const x = (s / segs) * 1600;
        const wave = Math.sin(s * 0.7 + i * 0.4) * 30 + Math.sin(s * 0.3 + i * 0.9) * 50;
        const yJit = y + wave + (rng() - 0.5) * 20;
        points.push(`${x},${yJit}`);
      }
      out.push(points.join(" "));
    }
    return out;
  }, [lines]);
  return (
    <svg
      viewBox="0 0 1600 800" preserveAspectRatio="xMidYMid slice"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity, pointerEvents: "none", ...style }}>
      {paths.map((p, i) => (
        <polyline key={i} points={p} fill="none" stroke={color} strokeWidth={i % 5 === 0 ? 0.6 : 0.3} />
      ))}
    </svg>
  );
}

function mulberry32(seed) {
  let a = seed;
  return function() {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/* ─────────────────── Eyebrow / Caps ─────────────────── */
function Eyebrow({ children, color = "var(--g-ink-3)", style }) {
  return (
    <div className="mono" style={{
      fontSize: 11, letterSpacing: "var(--g-track-caps)", textTransform: "uppercase",
      color, fontWeight: 500, ...style
    }}>{children}</div>
  );
}

/* ─────────────────── Pill / Badge ─────────────────── */
function Pill({ children, tone = "neutral", style }) {
  const tones = {
    neutral: { bg: "rgba(26,26,24,0.06)", fg: "var(--g-ink-2)" },
    accent:  { bg: "var(--g-accent-tint)", fg: "var(--g-accent-deep)" },
    good:    { bg: "rgba(61,107,58,0.10)", fg: "var(--g-good)" },
    warn:    { bg: "rgba(192,138,26,0.12)", fg: "#8a6210" },
    bad:     { bg: "rgba(168,50,50,0.10)", fg: "var(--g-bad)" },
    ghost:   { bg: "transparent", fg: "var(--g-ink-3)", border: "1px solid var(--g-rule)" },
  };
  const t = tones[tone] || tones.neutral;
  return (
    <span style={{
      display: "inline-flex", alignItems: "center", gap: 6, padding: "3px 9px",
      borderRadius: "var(--g-r-pill)", background: t.bg, color: t.fg,
      fontSize: 11, fontWeight: 500, fontFamily: "var(--g-font-mono)",
      letterSpacing: "0.04em", textTransform: "uppercase",
      border: t.border || "none", lineHeight: 1.4, ...style
    }}>{children}</span>
  );
}

/* ─────────────────── Card ─────────────────── */
function Card({ children, padding = 20, style, accent = false }) {
  return (
    <div style={{
      background: "var(--g-card)",
      border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)",
      padding,
      boxShadow: "var(--g-shadow-1)",
      borderLeft: accent ? "3px solid var(--g-accent)" : "1px solid var(--g-rule)",
      ...style,
    }}>{children}</div>
  );
}

/* ─────────────────── Sparkline (Höhenprofil mini) ─────────────────── */
function ElevSparkline({ data, width = 280, height = 60, stroke = "var(--g-accent)", fill = "rgba(196,90,42,0.10)", showArea = true }) {
  const min = Math.min(...data), max = Math.max(...data);
  const range = max - min || 1;
  const w = width, h = height;
  const pts = data.map((v, i) => {
    const x = (i / (data.length - 1)) * w;
    const y = h - ((v - min) / range) * h * 0.85 - h * 0.075;
    return [x, y];
  });
  const linePath = pts.map((p, i) => `${i === 0 ? "M" : "L"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const areaPath = `${linePath} L${w},${h} L0,${h} Z`;
  return (
    <svg width={w} height={h} style={{ display: "block" }}>
      {showArea && <path d={areaPath} fill={fill} />}
      <path d={linePath} fill="none" stroke={stroke} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}

/* ─────────────────── KV Row ─────────────────── */
function KV({ label, value, mono = true, style }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 16, padding: "6px 0", borderBottom: "1px dashed var(--g-rule-soft)", fontSize: 13, ...style }}>
      <span style={{ color: "var(--g-ink-3)", fontFamily: "var(--g-font-mono)", fontSize: 12, letterSpacing: 0.02 }}>{label}</span>
      <span style={{ color: "var(--g-ink)", fontFamily: mono ? "var(--g-font-mono)" : "var(--g-font-sans)", fontWeight: mono ? 500 : 600 }}>{value}</span>
    </div>
  );
}

/* ─────────────────── Button ─────────────────── */
function Btn({ children, variant = "primary", size = "md", icon, onClick, style }) {
  const sizes = {
    xs: { padX: 8,  padY: 4, fs: 11 },
    sm: { padX: 10, padY: 6, fs: 12 },
    md: { padX: 14, padY: 9, fs: 13 },
    lg: { padX: 20, padY: 12, fs: 14 },
  };
  const s = sizes[size] || sizes.md;
  const variants = {
    primary: { bg: "var(--g-ink)", fg: "var(--g-paper)", border: "1px solid var(--g-ink)" },
    accent:  { bg: "var(--g-accent)", fg: "#fff", border: "1px solid var(--g-accent)" },
    ghost:   { bg: "transparent", fg: "var(--g-ink)", border: "1px solid var(--g-rule)" },
    quiet:   { bg: "transparent", fg: "var(--g-ink-2)", border: "1px solid transparent" },
  };
  const v = variants[variant] || variants.primary;
  return (
    <button onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      padding: `${s.padY}px ${s.padX}px`, fontSize: s.fs, fontWeight: 500,
      fontFamily: "var(--g-font-sans)", letterSpacing: "-0.005em",
      background: v.bg, color: v.fg, border: v.border,
      borderRadius: "var(--g-r-2)", cursor: "pointer", lineHeight: 1.2,
      transition: "all 120ms", ...style,
    }}>{icon && <span style={{ display: "inline-flex" }}>{icon}</span>}{children}</button>
  );
}

/* ─────────────────── Logo ─────────────────── */
/* Delegiert an das Grundgesetz (brand-kit.jsx::BrandWordmark).
 * Diese Funktion existiert nur, damit Bestandscode wie <Logo size={20}/>
 * weiter funktioniert. Bei neuen Screens BITTE direkt <BrandWordmark/>
 * verwenden. Der `size`-Prop wird auf die diskreten Brand-Sizes gemappt. */
function Logo({ size = 22 }) {
  const variant = size <= 16 ? "sm" : size >= 28 ? "lg" : "md";
  return <window.BrandWordmark size={variant} />;
}

/* ─────────────────── Wetter-Icon (line, kein Emoji) ─────────────────── */
function WIcon({ kind = "cloud", size = 18, color = "var(--g-ink-2)" }) {
  const s = size, c = color;
  switch (kind) {
    case "sun":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round">
          <circle cx="12" cy="12" r="3.5"/>
          <path d="M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M5.6 18.4l1.4-1.4M17 7l1.4-1.4"/>
        </svg>);
    case "cloud":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinejoin="round">
          <path d="M7 17h10a4 4 0 0 0 0.5-7.97A6 6 0 0 0 6.1 11 4 4 0 0 0 7 17z"/>
        </svg>);
    case "rain":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M7 14h10a4 4 0 0 0 0.5-7.97A6 6 0 0 0 6.1 8 4 4 0 0 0 7 14z"/>
          <path d="M9 17l-1 3M13 17l-1 3M17 17l-1 3"/>
        </svg>);
    case "thunder":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M7 14h10a4 4 0 0 0 0.5-7.97A6 6 0 0 0 6.1 8 4 4 0 0 0 7 14z"/>
          <path d="M12 14l-2 4h3l-2 4"/>
        </svg>);
    case "snow":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round">
          <path d="M12 3v18M5 7l14 10M5 17l14-10"/>
        </svg>);
    case "wind":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinecap="round">
          <path d="M3 8h11a3 3 0 1 0-3-3M3 12h16a3 3 0 1 1-3 3M3 16h9"/>
        </svg>);
    case "moon":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinejoin="round">
          <path d="M20 14a8 8 0 1 1-10-10 6 6 0 0 0 10 10z"/>
        </svg>);
    case "headlamp":
      return (
        <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.5" strokeLinejoin="round" strokeLinecap="round">
          <rect x="7" y="9" width="10" height="6" rx="1.5"/>
          <path d="M17 12l4-1.5v3L17 12zM9 9V7a3 3 0 0 1 6 0v2"/>
        </svg>);
    default:
      return null;
  }
}

/* ─────────────────── Status Dot ─────────────────── */
function Dot({ tone = "good", size = 8 }) {
  const colors = {
    good: "var(--g-good)", warn: "var(--g-warn)", bad: "var(--g-bad)",
    info: "var(--g-info)", neutral: "var(--g-ink-3)",
  };
  return <span style={{
    display: "inline-block", width: size, height: size, borderRadius: "50%",
    background: colors[tone] || colors.neutral,
  }}/>;
}

/* ─────────────────── Section Header ─────────────────── */
function SectionH({ eyebrow, title, kicker, right, style }) {
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 24, marginBottom: 16, ...style }}>
      <div>
        {eyebrow && <Eyebrow style={{ marginBottom: 6 }}>{eyebrow}</Eyebrow>}
        <div style={{ fontSize: 22, fontWeight: 600, letterSpacing: "-0.01em" }}>{title}</div>
        {kicker && <div style={{ color: "var(--g-ink-3)", fontSize: 13, marginTop: 2 }}>{kicker}</div>}
      </div>
      {right && <div>{right}</div>}
    </div>
  );
}

/* ─────────────────── Avatar Stack ─────────────────── */
function AvatarStack({ users = [], size = 26 }) {
  return (
    <div style={{ display: "inline-flex" }}>
      {users.map((u, i) => (
        <div key={i} title={u.name} style={{
          width: size, height: size, borderRadius: "50%",
          background: u.color || `hsl(${(i*70)%360} 30% 65%)`, color: "#fff",
          fontSize: size * 0.42, fontWeight: 600, fontFamily: "var(--g-font-sans)",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
          border: "2px solid var(--g-card)", marginLeft: i === 0 ? 0 : -size * 0.3,
        }}>{u.initials || u.name.slice(0,2).toUpperCase()}</div>
      ))}
    </div>
  );
}

/* ─────────────────── Export ─────────────────── */
Object.assign(window, {
  TopoBg, Eyebrow, Pill, Card, ElevSparkline, KV, Btn, Logo, WIcon, Dot, SectionH, AvatarStack,
});
