/* Mobile Shell — Primitives für Gregor 20 Mobile.
 * Bottom-Nav + Top-App-Bar + Drawer + Bottom-Sheet + Toast + Inputs.
 * Alles aus tokens.css — keine neuen Farben, keine neuen Radien.
 * Touch ≥ 44px, Input-Body ≥ 16px, Safe-Area unten.
 */

const MOBILE_W = 375;
const SAFE_TOP = 44;          // Statusbar
const SAFE_BOTTOM = 34;       // Home-Indicator
const TOPBAR_H = 56;
const BOTTOMNAV_H = 64;

/* ─────────────────── PhoneFrame ───────────────────
 * Statisches Bezel für den Design-Canvas. Bringt Statusbar + Home-Indikator.
 */
function PhoneFrame({ width = MOBILE_W, height, children, theme = "light", time = "08:14" }) {
  const bg = theme === "dark" ? "#1a1a18" : "var(--g-paper)";
  return (
    <div style={{
      width: width + 12, margin: "0 auto",
      background: "#0e0e0c", padding: 6,
      borderRadius: 38, boxShadow: "0 24px 60px rgba(26,26,24,0.18), 0 4px 12px rgba(26,26,24,0.08)",
    }}>
      <div style={{
        position: "relative", width, height,
        background: bg, borderRadius: 32, overflow: "hidden",
        display: "flex", flexDirection: "column",
      }}>
        <MobileStatusBar time={time} dark={theme === "dark"}/>
        <div style={{ flex: 1, position: "relative", overflow: "hidden" }}>
          {children}
        </div>
        <HomeIndicator dark={theme === "dark"}/>
      </div>
    </div>
  );
}

function MobileStatusBar({ time = "08:14", dark = false }) {
  const c = dark ? "#fff" : "var(--g-ink)";
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "14px 26px 8px", height: SAFE_TOP, flexShrink: 0,
      fontFamily: "-apple-system, var(--g-font-sans)",
    }}>
      <span style={{ fontSize: 15, fontWeight: 600, color: c, letterSpacing: "-0.01em" }}>{time}</span>
      <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
        {/* Signal */}
        <svg width="17" height="11" viewBox="0 0 17 11">
          <rect x="0" y="7" width="3" height="4" rx="0.7" fill={c}/>
          <rect x="4.5" y="5" width="3" height="6" rx="0.7" fill={c}/>
          <rect x="9" y="2.5" width="3" height="8.5" rx="0.7" fill={c}/>
          <rect x="13.5" y="0" width="3" height="11" rx="0.7" fill={c}/>
        </svg>
        {/* WiFi */}
        <svg width="15" height="11" viewBox="0 0 15 11">
          <path d="M7.5 3C9.5 3 11.4 3.8 12.7 5L13.7 4C12.1 2.4 9.9 1.3 7.5 1.3C5.1 1.3 2.9 2.4 1.3 4L2.3 5C3.6 3.8 5.5 3 7.5 3Z" fill={c}/>
          <path d="M7.5 6C8.7 6 9.8 6.4 10.6 7.2L11.6 6.2C10.5 5.1 9 4.4 7.5 4.4C6 4.4 4.5 5.1 3.4 6.2L4.4 7.2C5.2 6.4 6.3 6 7.5 6Z" fill={c}/>
          <circle cx="7.5" cy="9.4" r="1.3" fill={c}/>
        </svg>
        {/* Battery */}
        <svg width="25" height="12" viewBox="0 0 25 12">
          <rect x="0.5" y="0.5" width="22" height="11" rx="3" stroke={c} strokeOpacity="0.4" fill="none"/>
          <rect x="2" y="2" width="18" height="8" rx="1.5" fill={c}/>
          <rect x="23.5" y="3.5" width="1.5" height="5" rx="0.5" fill={c} fillOpacity="0.5"/>
        </svg>
      </div>
    </div>
  );
}

function HomeIndicator({ dark }) {
  return (
    <div style={{
      height: SAFE_BOTTOM, flexShrink: 0,
      display: "flex", alignItems: "flex-end", justifyContent: "center",
      paddingBottom: 8,
      background: dark ? "#1a1a18" : "transparent",
    }}>
      <div style={{ width: 134, height: 5, borderRadius: 3, background: dark ? "rgba(255,255,255,0.6)" : "var(--g-ink)" }}/>
    </div>
  );
}

/* ─────────────────── TopAppBar ─────────────────── */
function TopAppBar({ title, eyebrow, onMenu, leftIcon = "menu", right, dense = false, scrolled = false }) {
  return (
    <div style={{
      height: TOPBAR_H, flexShrink: 0,
      display: "flex", alignItems: "center", gap: 4,
      padding: "0 8px 0 4px",
      borderBottom: scrolled ? "1px solid var(--g-rule-soft)" : "1px solid transparent",
      background: "var(--g-paper)",
      position: "relative", zIndex: 10,
    }}>
      <IconBtn onClick={onMenu} kind={leftIcon}/>
      <div style={{ flex: 1, minWidth: 0, paddingLeft: 4 }}>
        {eyebrow && (
          <div className="mono" style={{
            fontSize: 9, color: "var(--g-ink-4)", letterSpacing: "0.12em",
            textTransform: "uppercase", lineHeight: 1, marginBottom: 2,
          }}>{eyebrow}</div>
        )}
        <div style={{
          fontSize: dense ? 15 : 17, fontWeight: 600, letterSpacing: "-0.01em",
          color: "var(--g-ink)", lineHeight: 1.2, whiteSpace: "nowrap",
          overflow: "hidden", textOverflow: "ellipsis",
        }}>{title}</div>
      </div>
      {right}
    </div>
  );
}

function IconBtn({ kind = "menu", onClick, label, badge }) {
  return (
    <button onClick={onClick} aria-label={label} style={{
      width: 44, height: 44, display: "inline-flex",
      alignItems: "center", justifyContent: "center",
      background: "transparent", border: "none", cursor: "pointer",
      position: "relative", padding: 0,
    }}>
      <MIcon kind={kind}/>
      {badge != null && (
        <span style={{
          position: "absolute", top: 8, right: 8,
          minWidth: 16, height: 16, padding: "0 4px",
          background: "var(--g-accent)", color: "#fff",
          borderRadius: 8, fontSize: 10, fontWeight: 600,
          fontFamily: "var(--g-font-mono)",
          display: "inline-flex", alignItems: "center", justifyContent: "center",
        }}>{badge}</span>
      )}
    </button>
  );
}

function MIcon({ kind, size = 22, color = "var(--g-ink)" }) {
  const s = size, c = color;
  const stroke = { fill: "none", stroke: c, strokeWidth: 1.7, strokeLinecap: "round", strokeLinejoin: "round" };
  switch (kind) {
    case "menu":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M4 7h16M4 12h16M4 17h16"/></svg>;
    case "back":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M15 5l-7 7 7 7"/></svg>;
    case "close":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M6 6l12 12M18 6l-12 12"/></svg>;
    case "plus":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M12 5v14M5 12h14"/></svg>;
    case "search":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/></svg>;
    case "bell":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/><path d="M10 21a2 2 0 0 0 4 0"/></svg>;
    case "more":
      return <svg width={s} height={s} viewBox="0 0 24 24" fill={c}><circle cx="5" cy="12" r="1.7"/><circle cx="12" cy="12" r="1.7"/><circle cx="19" cy="12" r="1.7"/></svg>;
    case "filter":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M4 6h16M7 12h10M10 18h4"/></svg>;
    case "edit":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M14 4l6 6L9 21H3v-6z"/></svg>;
    case "share":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M12 3v13M8 7l4-4 4 4M5 14v5a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-5"/></svg>;
    case "settings":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.6 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1A1.7 1.7 0 0 0 4.7 9a1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1"/></svg>;
    case "check":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M5 12l5 5 9-11"/></svg>;
    case "chevron":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M9 6l6 6-6 6"/></svg>;
    case "chevron-down":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M6 9l6 6 6-6"/></svg>;
    case "chevron-up":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M6 15l6-6 6 6"/></svg>;
    case "drag":
      return <svg width={s} height={s} viewBox="0 0 24 24" fill={c}><circle cx="9" cy="6" r="1.6"/><circle cx="15" cy="6" r="1.6"/><circle cx="9" cy="12" r="1.6"/><circle cx="15" cy="12" r="1.6"/><circle cx="9" cy="18" r="1.6"/><circle cx="15" cy="18" r="1.6"/></svg>;
    case "trash":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M4 7h16M9 7V4h6v3M6 7l1 13a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-13"/></svg>;
    case "map":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M9 4l-6 2v14l6-2 6 2 6-2V4l-6 2-6-2zM9 4v14M15 6v14"/></svg>;
    case "list":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M4 7h16M4 12h16M4 17h16"/></svg>;
    case "external":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M14 4h6v6M20 4l-9 9M10 6H5a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5"/></svg>;
    case "send":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><path d="M3 11l18-8-7 18-3-7-8-3z"/></svg>;
    case "archive":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...stroke}><rect x="3" y="5" width="18" height="4" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/></svg>;
    default:
      return <span style={{ width: s, height: s, display: "inline-block" }}/>;
  }
}

/* ─────────────────── BottomNav ─────────────────── */
function BottomNav({ active = "home", onChange }) {
  const items = [
    { id: "home",    label: "Übersicht", icon: "home" },
    { id: "trips",   label: "Trips",     icon: "trip", badge: 1 },
    { id: "compare", label: "Vergleich", icon: "compare" },
    { id: "archive", label: "Archiv",    icon: "archive" },
  ];
  return (
    <nav style={{
      flexShrink: 0, height: BOTTOMNAV_H,
      borderTop: "1px solid var(--g-rule-soft)",
      background: "var(--g-paper-deep)",
      display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
      position: "relative", zIndex: 10,
    }}>
      {items.map(it => {
        const isActive = active === it.id;
        return (
          <button key={it.id} onClick={() => onChange && onChange(it.id)} style={{
            display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
            gap: 3, background: "transparent", border: "none", cursor: "pointer",
            position: "relative", padding: "8px 4px",
            minHeight: 44,
          }}>
            {isActive && (
              <span style={{
                position: "absolute", top: 0, left: "50%", transform: "translateX(-50%)",
                width: 28, height: 2, background: "var(--g-accent)", borderRadius: 1,
              }}/>
            )}
            <span style={{ position: "relative" }}>
              <NavIcon kind={it.icon} active={isActive}/>
              {it.badge != null && (
                <span style={{
                  position: "absolute", top: -3, right: -6,
                  minWidth: 14, height: 14, padding: "0 3px",
                  background: "var(--g-accent)", color: "#fff",
                  borderRadius: 7, fontSize: 9, fontWeight: 600,
                  fontFamily: "var(--g-font-mono)",
                  display: "inline-flex", alignItems: "center", justifyContent: "center",
                  border: "1.5px solid var(--g-paper-deep)",
                }}>{it.badge}</span>
              )}
            </span>
            <span style={{
              fontSize: 10, fontWeight: isActive ? 600 : 500,
              color: isActive ? "var(--g-ink)" : "var(--g-ink-3)",
              letterSpacing: "-0.005em",
            }}>{it.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

function NavIcon({ kind, active }) {
  const c = active ? "var(--g-ink)" : "var(--g-ink-3)";
  const s = 22;
  const sp = { fill: "none", stroke: c, strokeWidth: 1.7, strokeLinejoin: "round", strokeLinecap: "round" };
  switch (kind) {
    case "home":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/></svg>;
    case "trip":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><path d="M3 19l5-9 4 6 4-3 5 6"/><circle cx="8" cy="10" r="1.2" fill={c}/><circle cx="16" cy="13" r="1.2" fill={c}/></svg>;
    case "compare":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><path d="M5 8h7M5 12h5M5 16h7M14 8l4-3v14l-4-3"/></svg>;
    case "archive":
      return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><rect x="3" y="5" width="18" height="4" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/></svg>;
    default: return null;
  }
}

/* ─────────────────── Drawer (Hamburger-Panel) ─────────────────── */
function Drawer({ open, onClose }) {
  if (!open) return null;
  return (
    <>
      <div onClick={onClose} style={{
        position: "absolute", inset: 0, background: "rgba(26,26,24,0.42)",
        zIndex: 50,
      }}/>
      <aside style={{
        position: "absolute", top: 0, left: 0, bottom: 0, width: 296, zIndex: 51,
        background: "var(--g-paper-deep)", boxShadow: "var(--g-shadow-3)",
        display: "flex", flexDirection: "column",
      }}>
        <div style={{ height: SAFE_TOP, flexShrink: 0 }}/>
        <div style={{ padding: "12px 20px 18px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <Logo size={20}/>
          <IconBtn kind="close" onClick={onClose}/>
        </div>

        <div style={{ padding: "0 12px", flex: 1, overflow: "auto" }}>
          <DrawerGroup label="Workspace">
            <DrawerItem icon="home"    label="Übersicht"/>
            <DrawerItem icon="trip"    label="Trips"        badge="1"/>
            <DrawerItem icon="compare" label="Ortsvergleich"/>
            <DrawerItem icon="archive" label="Archiv"        badge="8"/>
          </DrawerGroup>
          <DrawerGroup label="Konfiguration">
            <DrawerItem icon="channels" label="Kanäle"/>
            <DrawerItem icon="settings" label="Einstellungen"/>
          </DrawerGroup>
        </div>

        <div style={{ padding: "16px 20px", borderTop: "1px solid var(--g-rule)", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: "50%", background: "var(--g-accent)",
            color: "#fff", fontSize: 13, fontWeight: 600,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>GH</div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div style={{ fontSize: 14, fontWeight: 600 }}>Gregor Henemm</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>henemm.com</div>
          </div>
          <IconBtn kind="external" label="Logout"/>
        </div>
        <div style={{ height: SAFE_BOTTOM, flexShrink: 0 }}/>
      </aside>
    </>
  );
}

function DrawerGroup({ label, children }) {
  return (
    <div style={{ padding: "8px 0 16px" }}>
      <div className="mono" style={{
        padding: "0 10px 6px", fontSize: 10, letterSpacing: "0.14em",
        textTransform: "uppercase", color: "var(--g-ink-4)", fontWeight: 500,
      }}>{label}</div>
      {children}
    </div>
  );
}

function DrawerItem({ icon, label, badge, active }) {
  const c = active ? "var(--g-accent)" : "var(--g-ink-3)";
  return (
    <a href="#" style={{
      display: "flex", alignItems: "center", gap: 14,
      padding: "12px 12px", minHeight: 44, textDecoration: "none",
      color: active ? "var(--g-ink)" : "var(--g-ink-2)",
      fontSize: 15, fontWeight: active ? 600 : 500,
      background: active ? "rgba(255,255,255,0.7)" : "transparent",
      borderRadius: "var(--g-r-3)",
    }}>
      <DrawerIcon kind={icon} color={c}/>
      <span style={{ flex: 1 }}>{label}</span>
      {badge && (
        <span className="mono" style={{
          fontSize: 11, padding: "2px 8px", borderRadius: "var(--g-r-pill)",
          background: "rgba(26,26,24,0.06)", color: "var(--g-ink-3)",
        }}>{badge}</span>
      )}
    </a>
  );
}

function DrawerIcon({ kind, color }) {
  const s = 20, c = color;
  const sp = { fill: "none", stroke: c, strokeWidth: 1.7, strokeLinejoin: "round", strokeLinecap: "round" };
  switch (kind) {
    case "home":     return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/></svg>;
    case "trip":     return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><path d="M3 19l5-9 4 6 4-3 5 6"/></svg>;
    case "compare":  return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><path d="M5 8h7M5 12h5M5 16h7M14 8l4-3v14l-4-3"/></svg>;
    case "archive":  return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><rect x="3" y="5" width="18" height="4" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9"/></svg>;
    case "channels": return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><path d="M4 6l8 6 8-6M4 6h16v12H4z"/></svg>;
    case "settings": return <svg width={s} height={s} viewBox="0 0 24 24" {...sp}><circle cx="12" cy="12" r="3"/><path d="M5 12l-2 0M21 12l-2 0M12 3v2M12 19v2M5 5l1.4 1.4M17.6 17.6L19 19M5 19l1.4-1.4M17.6 6.4L19 5"/></svg>;
    default: return null;
  }
}

/* ─────────────────── Bottom-Sheet ─────────────────── */
function Sheet({ open = true, onClose, title, eyebrow, snap = "full", children, footer }) {
  if (!open) return null;
  const heights = { full: "84%", half: "55%", peek: "32%" };
  return (
    <>
      <div onClick={onClose} style={{
        position: "absolute", inset: 0, background: "rgba(26,26,24,0.42)",
        zIndex: 60,
      }}/>
      <div style={{
        position: "absolute", left: 0, right: 0, bottom: 0,
        height: heights[snap] || heights.full,
        background: "var(--g-card)", zIndex: 61,
        borderTopLeftRadius: 18, borderTopRightRadius: 18,
        boxShadow: "0 -8px 32px rgba(26,26,24,0.18)",
        display: "flex", flexDirection: "column", overflow: "hidden",
      }}>
        <div style={{ display: "flex", justifyContent: "center", paddingTop: 8, paddingBottom: 4, flexShrink: 0 }}>
          <span style={{ width: 36, height: 4, borderRadius: 2, background: "var(--g-rule)" }}/>
        </div>
        {(title || eyebrow) && (
          <div style={{ padding: "8px 20px 12px", flexShrink: 0, display: "flex", alignItems: "flex-start", gap: 8 }}>
            <div style={{ flex: 1, minWidth: 0 }}>
              {eyebrow && <Eyebrow style={{ marginBottom: 4 }}>{eyebrow}</Eyebrow>}
              {title && <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.01em" }}>{title}</div>}
            </div>
            {onClose && <IconBtn kind="close" onClick={onClose}/>}
          </div>
        )}
        <div style={{ flex: 1, overflow: "auto", padding: "0 20px 20px" }}>
          {children}
        </div>
        {footer && (
          <div style={{
            padding: "12px 20px calc(12px + env(safe-area-inset-bottom))",
            borderTop: "1px solid var(--g-rule-soft)", background: "var(--g-card)",
            flexShrink: 0,
          }}>{footer}</div>
        )}
      </div>
    </>
  );
}

/* ─────────────────── Toast / Snackbar ─────────────────── */
function Toast({ kind = "info", msg, action, hint }) {
  const map = {
    info:    { bg: "var(--g-ink)",   fg: "var(--g-paper)" },
    success: { bg: "var(--g-good)",  fg: "#fff" },
    warn:    { bg: "var(--g-warn)",  fg: "#fff" },
    error:   { bg: "var(--g-bad)",   fg: "#fff" },
  };
  const t = map[kind] || map.info;
  return (
    <div style={{
      position: "absolute", left: 16, right: 16, bottom: BOTTOMNAV_H + 12,
      background: t.bg, color: t.fg,
      borderRadius: "var(--g-r-3)", padding: "12px 16px",
      display: "flex", alignItems: "center", gap: 12,
      boxShadow: "var(--g-shadow-3)", zIndex: 30,
      fontSize: 14, lineHeight: 1.4,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        {hint && (
          <div className="mono" style={{ fontSize: 10, letterSpacing: "0.1em", textTransform: "uppercase", opacity: 0.7, marginBottom: 2 }}>{hint}</div>
        )}
        <div>{msg}</div>
      </div>
      {action && (
        <button style={{
          background: "transparent", border: "none",
          color: t.fg, fontSize: 13, fontWeight: 600,
          textTransform: "uppercase", letterSpacing: "0.06em",
          fontFamily: "var(--g-font-mono)", cursor: "pointer",
          minHeight: 44, padding: "0 4px",
        }}>{action}</button>
      )}
    </div>
  );
}

/* ─────────────────── Mobile Inputs ─────────────────── */
function MInput({ value, defaultValue, placeholder, type = "text", onChange, leftIcon }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      background: "var(--g-card)", border: "1px solid var(--g-rule)",
      borderRadius: "var(--g-r-3)", padding: "0 14px",
      minHeight: 48,
    }}>
      {leftIcon && <MIcon kind={leftIcon} size={18} color="var(--g-ink-4)"/>}
      <input
        type={type} value={value} defaultValue={defaultValue}
        placeholder={placeholder} onChange={onChange}
        style={{
          flex: 1, border: "none", outline: "none", background: "transparent",
          fontSize: 16, fontFamily: "var(--g-font-sans)", color: "var(--g-ink)",
          minHeight: 44, padding: 0,
        }}/>
    </div>
  );
}

function MField({ label, sub, children }) {
  return (
    <div style={{ marginBottom: 14 }}>
      {label && (
        <div className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)", letterSpacing: "0.08em", textTransform: "uppercase", marginBottom: 6 }}>{label}</div>
      )}
      {children}
      {sub && <div style={{ fontSize: 12, color: "var(--g-ink-4)", marginTop: 6, lineHeight: 1.4 }}>{sub}</div>}
    </div>
  );
}

function MBtn({ children, variant = "primary", size = "lg", block, icon, onClick, style }) {
  const sizes = {
    md: { padX: 14, padY: 10, fs: 14, h: 40 },
    lg: { padX: 18, padY: 14, fs: 15, h: 48 },
    xl: { padX: 22, padY: 16, fs: 16, h: 56 },
  };
  const s = sizes[size] || sizes.lg;
  const variants = {
    primary: { bg: "var(--g-ink)", fg: "var(--g-paper)", border: "1px solid var(--g-ink)" },
    accent:  { bg: "var(--g-accent)", fg: "#fff", border: "1px solid var(--g-accent)" },
    ghost:   { bg: "transparent", fg: "var(--g-ink)", border: "1px solid var(--g-rule)" },
    quiet:   { bg: "transparent", fg: "var(--g-ink-2)", border: "1px solid transparent" },
    danger:  { bg: "transparent", fg: "var(--g-bad)", border: "1px solid var(--g-rule)" },
  };
  const v = variants[variant] || variants.primary;
  return (
    <button onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      gap: 8, padding: `${s.padY}px ${s.padX}px`, minHeight: s.h,
      width: block ? "100%" : "auto",
      fontSize: s.fs, fontWeight: 600, letterSpacing: "-0.005em",
      fontFamily: "var(--g-font-sans)",
      background: v.bg, color: v.fg, border: v.border,
      borderRadius: "var(--g-r-3)", cursor: "pointer", ...style,
    }}>
      {icon && <span style={{ display: "inline-flex" }}>{icon}</span>}
      {children}
    </button>
  );
}

function MSwitch({ checked, onChange, label }) {
  return (
    <div onClick={() => onChange && onChange(!checked)} style={{
      display: "flex", alignItems: "center", gap: 12, cursor: "pointer",
      minHeight: 44, padding: "10px 0",
    }}>
      {label && <span style={{ flex: 1, fontSize: 15, color: "var(--g-ink)" }}>{label}</span>}
      <span style={{
        width: 44, height: 26, borderRadius: 13,
        background: checked ? "var(--g-good)" : "var(--g-rule)",
        position: "relative", flexShrink: 0, transition: "background 120ms",
      }}>
        <span style={{
          position: "absolute", top: 3, left: checked ? 21 : 3,
          width: 20, height: 20, background: "#fff", borderRadius: "50%",
          boxShadow: "0 1px 2px rgba(0,0,0,0.2)", transition: "left 120ms",
        }}/>
      </span>
    </div>
  );
}

function MTab({ items, active, onChange, scrollable = true }) {
  return (
    <div style={{
      display: "flex", gap: 0, overflowX: scrollable ? "auto" : "hidden",
      borderBottom: "1px solid var(--g-rule-soft)",
      WebkitOverflowScrolling: "touch", scrollbarWidth: "none",
    }}>
      {items.map(it => {
        const isActive = active === it.id;
        return (
          <button key={it.id} onClick={() => onChange && onChange(it.id)} style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            padding: "14px 14px", minHeight: 44, flexShrink: 0,
            background: "transparent", border: "none", cursor: "pointer",
            fontSize: 14, fontWeight: isActive ? 600 : 500,
            color: isActive ? "var(--g-ink)" : "var(--g-ink-3)",
            borderBottom: isActive ? "2px solid var(--g-accent)" : "2px solid transparent",
            marginBottom: -1, whiteSpace: "nowrap",
            fontFamily: "var(--g-font-sans)",
          }}>
            {it.label}
            {it.badge != null && (
              <span className="mono" style={{
                fontSize: 10, padding: "1px 6px", borderRadius: 3,
                background: it.accent ? "var(--g-accent)" : "var(--g-paper-deep)",
                color: it.accent ? "#fff" : "var(--g-ink-3)",
              }}>{it.badge}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/* ─────────────────── ScreenScroll
 * Vertikal scrollender Main-Bereich zwischen TopBar und BottomNav.
 */
function ScreenScroll({ children, padding = 16, bg }) {
  return (
    <div style={{
      flex: 1, overflow: "auto", padding,
      background: bg || "transparent",
      WebkitOverflowScrolling: "touch",
    }}>
      {children}
    </div>
  );
}

/* ─────────────────── Mobile Shell Wrapper ─────────────────── */
function MobileShell({
  active = "home", title, eyebrow, leftIcon = "menu", right,
  children, footer, drawerOpen = false, sheet, toast,
  background = "var(--g-paper)", phoneHeight = 812,
  showBottomNav = true, showTopBar = true, onMenu,
}) {
  return (
    <PhoneFrame height={phoneHeight}>
      <div style={{
        position: "absolute", inset: 0, display: "flex", flexDirection: "column",
        background, overflow: "hidden",
      }}>
        {showTopBar && (
          <TopAppBar title={title} eyebrow={eyebrow} leftIcon={leftIcon} right={right} onMenu={onMenu}/>
        )}
        <div style={{ flex: 1, position: "relative", overflow: "hidden", display: "flex", flexDirection: "column" }}>
          {children}
        </div>
        {footer}
        {showBottomNav && <BottomNav active={active}/>}
      </div>
      {sheet}
      {toast}
      <Drawer open={drawerOpen} onClose={() => {}}/>
    </PhoneFrame>
  );
}

/* ─────────────────── Export ─────────────────── */
Object.assign(window, {
  MOBILE_W, SAFE_TOP, SAFE_BOTTOM, TOPBAR_H, BOTTOMNAV_H,
  PhoneFrame, MobileStatusBar, HomeIndicator,
  TopAppBar, IconBtn, MIcon, BottomNav, NavIcon,
  Drawer, DrawerGroup, DrawerItem,
  Sheet, Toast,
  MInput, MField, MBtn, MSwitch, MTab, ScreenScroll,
  MobileShell,
});
