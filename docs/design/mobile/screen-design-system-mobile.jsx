/* Mobile · Design-System / Token-Übersicht
 * Mobile-spezifische Tokens: Touch-Targets, Spacing-Verdichtung, Inputs ≥ 16 px,
 *   Safe-Areas, Bottom-Nav-Höhe etc. Verwendet ausschließlich tokens.css.
 * Layout: scrollbarer Single-Column.
 */

function ScreenDesignSystemMobile() {
  return (
    <PhoneFrame height={1100}>
      <div style={{ position: "absolute", inset: 0, display: "flex", flexDirection: "column", background: "var(--g-paper)" }}>
        <TopAppBar title="Mobile-Tokens" eyebrow="Design-System · Mobile-Spezifikation" leftIcon="back"/>

        <ScreenScroll padding={16}>

          {/* Touch-Targets */}
          <DSGroup title="Touch-Targets" sub="Mindestmaße für tappbare Elemente (Apple HIG / Material).">
            <DSRow tk="--touch-min"     val="44 × 44 px"   note="Buttons, Nav-Items, Switches"/>
            <DSRow tk="--touch-pref"    val="48 × 48 px"   note="Primäre Actions (MBtn size=lg)"/>
            <DSRow tk="--touch-cta"     val="56 × 56 px"   note="Fokus-CTAs (size=xl)"/>
            <DSRow tk="--input-h"       val="48 px"        note="Inputs (MInput)"/>
            <DSRow tk="--input-fs"      val="16 px"        note="iOS verhindert Zoom bei ≥ 16 px"/>
          </DSGroup>

          {/* Spacing */}
          <DSGroup title="Spacing · mobil verdichtet" sub="Skalen aus tokens.css; mobile Innenränder kompakter.">
            <DSRow tk="--g-s-3 (12)"   val="Card-Gaps"     note="zwischen Cards"/>
            <DSRow tk="--g-s-4 (16)"   val="Screen-Padding" note="Außenrand · statt 40 px Desktop"/>
            <DSRow tk="--g-s-4 (16)"   val="Card-Padding"   note="Karten-Innenrand · statt 20 px"/>
            <DSRow tk="--g-s-2 (8)"    val="Inline-Gap"     note="zwischen Inline-Elementen"/>
            <DSRow tk="--g-s-1 (4)"    val="Hairline-Gap"   note="zwischen Pills, Chips"/>
          </DSGroup>

          {/* App-Shell-Maße */}
          <DSGroup title="App-Shell · Höhen" sub="Feste Maße der Mobile-Shell.">
            <DSRow tk="topbar-h"      val="56 px"   note="Top-App-Bar"/>
            <DSRow tk="bottomnav-h"   val="64 px"   note="Bottom-Nav"/>
            <DSRow tk="safe-top"      val="44 px"   note="Statusbar · env(safe-area-inset-top)"/>
            <DSRow tk="safe-bottom"   val="34 px"   note="Home-Indicator · env(safe-area-inset-bottom)"/>
            <DSRow tk="content-w"     val="375 / 414 / 768" note="Primär · Sekundär · Tablet"/>
          </DSGroup>

          {/* Typografie */}
          <DSGroup title="Typografie · Mobile-Scale" sub="Body 14 px Default, 16 px in Inputs. Display kleiner als Desktop.">
            <DSTypeRow size={28} weight={600} label="Hero" note="Trip-Titel, Login"/>
            <DSTypeRow size={22} weight={600} label="Section-H1" note="Trip-Detail Hero"/>
            <DSTypeRow size={17} weight={600} label="TopAppBar-Title" note="Sticky-Header"/>
            <DSTypeRow size={16} weight={600} label="Card-Title"/>
            <DSTypeRow size={15} weight={500} label="Drawer-Item · Body-CTA"/>
            <DSTypeRow size={14} weight={400} label="Body" note="Lesetext"/>
            <DSTypeRow size={13} weight={500} label="Sub · Card-Body"/>
            <DSTypeRow size={11} weight={500} mono label="Eyebrow · Meta-Daten"/>
            <DSTypeRow size={10} weight={500} mono label="Caption · Stat-Label"/>
          </DSGroup>

          {/* Farben */}
          <DSGroup title="Farben · aus tokens.css" sub="Keine Mobile-spezifischen Farben. Verwende --g-* unverändert.">
            <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 6 }}>
              <Swatch color="var(--g-paper)" name="paper"/>
              <Swatch color="var(--g-paper-deep)" name="paper-d"/>
              <Swatch color="var(--g-card)" name="card"/>
              <Swatch color="var(--g-card-alt)" name="card-alt"/>
              <Swatch color="var(--g-ink)" name="ink" dark/>
              <Swatch color="var(--g-ink-2)" name="ink-2" dark/>
              <Swatch color="var(--g-ink-3)" name="ink-3" dark/>
              <Swatch color="var(--g-ink-4)" name="ink-4" dark/>
              <Swatch color="var(--g-accent)" name="accent" dark/>
              <Swatch color="var(--g-good)" name="good" dark/>
              <Swatch color="var(--g-warn)" name="warn" dark/>
              <Swatch color="var(--g-bad)" name="bad" dark/>
            </div>
          </DSGroup>

          {/* Radii */}
          <DSGroup title="Radien" sub="Mobile bevorzugt --g-r-3 für Cards, --g-r-pill für Chips.">
            <div style={{ display: "flex", gap: 6 }}>
              <RadiusBox r="2" tk="--g-r-1"/>
              <RadiusBox r="4" tk="--g-r-2"/>
              <RadiusBox r="6" tk="--g-r-3"/>
              <RadiusBox r="10" tk="--g-r-4"/>
              <RadiusBox r="999" tk="--g-r-pill" label="∞"/>
            </div>
          </DSGroup>

          {/* Komponenten-Beispiele */}
          <DSGroup title="Komponenten · live" sub="Gleicher Code wie in Production-Screens.">
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <MBtn variant="primary" block>Primary · 48 px hoch</MBtn>
              <MBtn variant="accent" block>Accent</MBtn>
              <MBtn variant="ghost" block>Ghost</MBtn>
              <div style={{ display: "flex", gap: 6 }}>
                <Pill tone="good">low</Pill>
                <Pill tone="warn">med</Pill>
                <Pill tone="bad">high</Pill>
                <Pill tone="accent">Live</Pill>
              </div>
              <MInput placeholder="Input · fontSize 16 px" leftIcon="search"/>
              <MSwitch label="Switch · 44 px Touch" checked/>
            </div>
          </DSGroup>

          {/* Breakpoints */}
          <DSGroup title="Breakpoints" sub="@media-Query-Logik in app.css.">
            <DSRow tk="≤ 599 px"   val="Mobile"   note="Primärziel 375 · Sekundär 414"/>
            <DSRow tk="600–899 px" val="Wide-M"   note="Tablet 768 · 2-spaltige Cards wo sinnvoll"/>
            <DSRow tk="≥ 900 px"   val="Desktop"  note="Bestehendes Layout unverändert"/>
          </DSGroup>

        </ScreenScroll>
      </div>
    </PhoneFrame>
  );
}

function DSGroup({ title, sub, children }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{ marginBottom: 10 }}>
        <Eyebrow style={{ marginBottom: 4 }}>{title}</Eyebrow>
        {sub && <div style={{ fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.5 }}>{sub}</div>}
      </div>
      {children}
    </div>
  );
}

function DSRow({ tk, val, note }) {
  return (
    <div style={{ display: "flex", alignItems: "center", padding: "10px 0", borderBottom: "1px solid var(--g-rule-soft)", gap: 10 }}>
      <span className="mono" style={{ fontSize: 11, color: "var(--g-accent)", fontWeight: 600, minWidth: 110 }}>{tk}</span>
      <span className="mono" style={{ fontSize: 12, color: "var(--g-ink)", fontWeight: 600, minWidth: 80 }}>{val}</span>
      <span style={{ flex: 1, fontSize: 12, color: "var(--g-ink-3)", lineHeight: 1.4 }}>{note}</span>
    </div>
  );
}

function DSTypeRow({ size, weight, label, note, mono }) {
  return (
    <div style={{ display: "flex", alignItems: "baseline", padding: "8px 0", borderBottom: "1px solid var(--g-rule-soft)", gap: 12 }}>
      <span style={{
        fontSize: size, fontWeight: weight, letterSpacing: size > 20 ? "-0.02em" : 0,
        color: "var(--g-ink)", lineHeight: 1, fontFamily: mono ? "var(--g-font-mono)" : "var(--g-font-sans)",
        minWidth: 40, flexShrink: 0,
      }}>Aa</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500 }}>{label}</div>
        {note && <div className="mono" style={{ fontSize: 10, color: "var(--g-ink-4)", marginTop: 2 }}>{note}</div>}
      </div>
      <span className="mono" style={{ fontSize: 11, color: "var(--g-ink-3)" }}>{size}/{weight}</span>
    </div>
  );
}

function Swatch({ color, name, dark }) {
  return (
    <div>
      <div style={{ height: 48, background: color, borderRadius: "var(--g-r-2)", border: "1px solid var(--g-rule-soft)" }}/>
      <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-3)", marginTop: 4, textAlign: "center", letterSpacing: "0.04em" }}>{name}</div>
    </div>
  );
}

function RadiusBox({ r, tk, label }) {
  return (
    <div style={{ flex: 1, textAlign: "center" }}>
      <div style={{ height: 48, background: "var(--g-card)", border: "1px solid var(--g-rule)", borderRadius: r === "999" ? 24 : Number(r) }}/>
      <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-3)", marginTop: 4 }}>{tk}</div>
      <div className="mono" style={{ fontSize: 9, color: "var(--g-ink-4)" }}>{label || r + "px"}</div>
    </div>
  );
}

window.ScreenDesignSystemMobile = ScreenDesignSystemMobile;
