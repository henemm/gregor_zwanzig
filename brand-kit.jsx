/* ═══════════════════════════════════════════════════════════════════════
 *  GREGOR ZWANZIG — BRAND KIT (DAS GRUNDGESETZ)
 * ═══════════════════════════════════════════════════════════════════════
 *
 *  Diese Datei ist die einzige Quelle der Wahrheit für das Branding und
 *  die geteilten App-Chrome-Bausteine (Wordmark, Sidebar-Header, User-
 *  Badge). Jede andere Datei, die diese Elemente zeigt, MUSS hier her
 *  delegieren — keine Duplikate, keine Forks.
 *
 *  Lade-Reihenfolge in HTML-Files: VOR atoms.jsx und vor jedem Screen.
 *
 *  ─────────────────── Kanonische Entscheidungen ────────────────────────
 *
 *  Wordmark (PO-bestätigt, Variante B):
 *      Mono-Schrift, lowercase, »gregor« + »·« (ink-4) + »zwanzig« (accent).
 *      Caption: »V0.20 · WETTER-BRIEFING« in mono-caps tracking 0.18em.
 *      KEIN Bergmark-Glyph mehr im Sidebar-Kontext.
 *
 *  Sizes:
 *      sm  — kompakte Toolbars, mobile Headers   (row 14 px / cap 8 px)
 *      md  — App-Sidebar (Default)               (row 18 px / cap 9 px)
 *      lg  — Landing-Hero, Login-Screen          (row 24 px / cap 10 px)
 *
 *  User-Badge:
 *      Initiale auf accent-Hintergrund, kreisrund. Name + Sekundärzeile
 *      in --g-font-sans / --g-font-mono. Default-User »Gregor Henemm«.
 *
 *  ──────────────────────────── Migration ───────────────────────────────
 *
 *  • atoms.jsx::Logo                       → BrandWordmark
 *  • soll-mockups/app-shell::WordmarkBrand → BrandWordmark
 *  • sidebar.jsx (Sidebar-Header)          → BrandWordmark size="md"
 *
 *  Alle alten Namen werden unten als Aliase auf window erneut exportiert,
 *  damit Bestandscode unverändert weiterläuft. Bei neuen Screens immer
 *  die Brand*-Namen verwenden.
 *
 *  ───────────────────────────────────────────────────────────────────── */

/* ─────────────────── BrandWordmark ─────────────────── */
/* Kanonisches Typo-Logo. Drei Größen. Variante »dark« kehrt den Text
 * auf Paper-Farbe für dunkle Hintergründe. */
function BrandWordmark({ size = "md", dark = false, caption = "V0.20 · Wetter-Briefing" }) {
  const SIZES = {
    sm: { row: 14, sub: 8,  gap: 2, dotGap: 0 },
    md: { row: 18, sub: 9,  gap: 3, dotGap: 0 },
    lg: { row: 24, sub: 10, gap: 4, dotGap: 0 },
  };
  const s = SIZES[size] || SIZES.md;
  const inkPrimary  = dark ? "var(--g-paper)"     : "var(--g-ink)";
  const inkDot      = dark ? "rgba(246,244,238,0.45)" : "var(--g-ink-4)";
  const inkCaption  = dark ? "rgba(246,244,238,0.55)" : "var(--g-ink-4)";

  return (
    <div style={{ display: "inline-block", lineHeight: 1 }}>
      <div style={{
        fontFamily: "var(--g-font-mono)",
        fontSize: s.row,
        fontWeight: 500,
        letterSpacing: "0.04em",
        color: inkPrimary,
        display: "flex",
        alignItems: "baseline",
        gap: s.dotGap,
        lineHeight: 1,
      }}>
        <span>gregor</span>
        <span style={{ color: inkDot }}>.</span>
        <span style={{ color: "var(--g-accent)" }}>zwanzig</span>
      </div>
      {caption && (
        <div style={{
          fontFamily: "var(--g-font-mono)",
          fontSize: s.sub,
          fontWeight: 500,
          letterSpacing: "0.18em",
          textTransform: "uppercase",
          color: inkCaption,
          marginTop: s.gap,
        }}>{caption}</div>
      )}
    </div>
  );
}

/* ─────────────────── BrandUserBadge ─────────────────── */
/* Sidebar-Footer / Profile-Pill. Avatar (Initialen) + Name + Sekundärzeile.
 * `sub` darf null sein, dann nur eine Zeile. */
function BrandUserBadge({
  name = "Gregor Henemm",
  sub = "henemm.com",
  initials,
  accent = false,           /* true → Avatar in --g-accent statt --g-ink */
}) {
  const ini = initials || name.split(" ").map(p => p[0]).slice(0, 2).join("").toUpperCase();
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
      <div style={{
        width: 28, height: 28, borderRadius: "50%",
        background: accent ? "var(--g-accent)" : "var(--g-ink)",
        color: "var(--g-paper)", fontSize: 11, fontWeight: 600,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontFamily: "var(--g-font-sans)", flexShrink: 0,
      }}>{ini}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontFamily: "var(--g-font-sans)",
          fontSize: 13, fontWeight: 500, lineHeight: 1.2,
          color: "var(--g-ink)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{name}</div>
        {sub && (
          <div style={{
            fontFamily: "var(--g-font-mono)",
            fontSize: 11, lineHeight: 1.2, color: "var(--g-ink-3)",
            whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
          }}>{sub}</div>
        )}
      </div>
    </div>
  );
}

/* ─────────────────── BrandSidebarHeader ─────────────────── */
/* Standard-Spacing-Block für den Wordmark im oberen Sidebar-Bereich.
 * Verwendung in jeder Sidebar-Implementierung, damit die Padding-Werte
 * niemals manuell drifteten. */
function BrandSidebarHeader({ size = "md", caption }) {
  return (
    <div style={{ padding: "0 18px 24px" }}>
      <BrandWordmark size={size} caption={caption}/>
    </div>
  );
}

/* ─────────────────── BrandSidebar — DIE Sidebar ───────────────────
 *
 * Kanonische App-Navigation. Vier Workspace-Items, fest in dieser
 * Reihenfolge (PO + UX-Diskussion):
 *
 *    Startseite         · Übersicht / Cockpit
 *    Meine Touren       · alle aktiven/geplanten Trips
 *    Orts-Vergleich     · gespeicherte Vergleichs-Setups
 *    Archiv             · vergangene Touren, retrospektiv
 *
 * Einstellungen / Kanäle erreicht man über das User-Badge unten,
 * nicht über die Haupt-Nav (Hygiene: nur Daten in der Sidebar).
 *
 * Props:
 *   active     — id des aktiven Items: 'home' | 'trips' | 'compare' | 'archive'
 *   counts     — optional, z. B. { trips: 3, archive: 12 }
 *   onNavigate — optional, (id) => {} für Klick
 */
const BRAND_NAV_ITEMS = [
  { id: "home",    label: "Startseite",     icon: "home" },
  { id: "trips",   label: "Meine Touren",   icon: "trip" },
  { id: "compare", label: "Orts-Vergleich", icon: "compare" },
  { id: "archive", label: "Archiv",         icon: "archive" },
];

function BrandSidebar({ active = "home", counts = {}, onNavigate, user }) {
  return (
    <aside style={{
      width: 220, flex: "0 0 220px",
      background: "var(--g-paper-deep)",
      borderRight: "1px solid var(--g-rule)",
      display: "flex", flexDirection: "column",
      padding: "24px 0 0",
      height: "100%",
      fontFamily: "var(--g-font-sans)",
    }}>
      <div style={{ padding: "0 18px 24px" }}>
        <BrandWordmark size="md"/>
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 2, padding: "0 12px" }}>
        {BRAND_NAV_ITEMS.map(it => (
          <BrandSidebarItem
            key={it.id}
            {...it}
            count={counts[it.id]}
            active={active === it.id}
            onClick={() => onNavigate && onNavigate(it.id)}
          />
        ))}
      </nav>

      <div style={{ flex: 1 }}/>

      <div style={{
        padding: "16px 18px",
        borderTop: "1px solid var(--g-rule-soft)",
      }}>
        <BrandUserBadge
          name={user?.name ?? "Gregor Henemm"}
          sub={user?.sub ?? "henemm.com"}
          accent={user?.accent ?? false}
        />
      </div>
    </aside>
  );
}

function BrandSidebarItem({ id, label, icon, count, active, onClick }) {
  return (
    <a onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "8px 12px",
      borderRadius: "var(--g-r-3)",
      background: active ? "rgba(196,90,42,0.10)" : "transparent",
      color: active ? "var(--g-accent-deep)" : "var(--g-ink-2)",
      fontSize: 13, fontWeight: active ? 600 : 500,
      textDecoration: "none", cursor: "pointer",
      transition: "background 120ms",
    }}>
      <BrandSidebarIcon kind={icon} active={active}/>
      <span style={{ flex: 1 }}>{label}</span>
      {count != null && (
        <span style={{
          fontFamily: "var(--g-font-mono)", fontSize: 10,
          color: active ? "var(--g-accent-deep)" : "var(--g-ink-4)",
          background: active ? "rgba(196,90,42,0.12)" : "rgba(26,26,24,0.05)",
          padding: "1px 6px", borderRadius: "var(--g-r-pill)",
          fontWeight: 600, letterSpacing: "0.02em",
        }}>{count}</span>
      )}
    </a>
  );
}

function BrandSidebarIcon({ kind, active }) {
  const c = active ? "var(--g-accent)" : "var(--g-ink-3)";
  const s = 16;
  switch (kind) {
    case "home":
      return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"><path d="M3 11l9-7 9 7v9a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z"/></svg>;
    case "trip":
      return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"><path d="M3 19l5-9 4 6 4-3 5 6"/><circle cx="8" cy="10" r="1.2" fill={c}/><circle cx="16" cy="13" r="1.2" fill={c}/></svg>;
    case "compare":
      return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7"><path d="M5 8h7M5 12h5M5 16h7M14 8l4-3v14l-4-3"/></svg>;
    case "archive":
      return <svg width={s} height={s} viewBox="0 0 24 24" fill="none" stroke={c} strokeWidth="1.7" strokeLinejoin="round"><rect x="3" y="5" width="18" height="4" rx="1"/><path d="M5 9v10a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1V9M10 13h4"/></svg>;
    default:
      return <span style={{ width: s, height: s, display: "inline-block" }}/>;
  }
}

/* ─────────────────── BrandShell — Sidebar + Main ─────────────────── */
/* Convenience-Wrapper für ganze Screens. */
function BrandShell({ active = "home", counts, user, onNavigate, children }) {
  return (
    <div style={{
      width: "100%", height: "100%",
      display: "flex", flexDirection: "row",
      background: "var(--g-paper)",
      overflow: "hidden",
    }}>
      <BrandSidebar active={active} counts={counts} user={user} onNavigate={onNavigate}/>
      <main style={{ flex: 1, minWidth: 0, height: "100%", overflow: "auto" }}>
        {children}
      </main>
    </div>
  );
}

/* ─────────────────── Exports ─────────────────── */
/* Neue Namen — bevorzugt verwenden: */
window.BrandWordmark      = BrandWordmark;
window.BrandUserBadge     = BrandUserBadge;
window.BrandSidebarHeader = BrandSidebarHeader;
window.BrandSidebar       = BrandSidebar;
window.BrandShell         = BrandShell;
window.BRAND_NAV_ITEMS    = BRAND_NAV_ITEMS;

/* Aliase auf alte Namen für Bestandscode. Atoms.jsx / app-shell.jsx
 * überschreiben diese später NICHT mehr — sie erben hieraus. */
window.WordmarkBrand = BrandWordmark;
