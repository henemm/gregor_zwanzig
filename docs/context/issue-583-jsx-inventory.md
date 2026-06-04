=== JSX Style Inventory: screen-archive.jsx ===

## Inline-Styles (17) — MÜSSEN 1:1 in Svelte erscheinen

- [ ] Line 106: `style={{ display: "flex", height: "100%", background: "var(--g-paper)" }}`
      Context: `<div style={{ display: "flex", height: "100%", background: "var(--g-paper)" }}>`
- [ ] Line 132: `style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}`
      Context: `<main style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}>`
- [ ] Line 134: `style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}`
      Context: `<div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>`
- [ ] Line 137: `style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}`
      Context: `<div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}>Archiv</div>`
- [ ] Line 138: `style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 620, lineHeight: 1.5 }}`
      Context: `<div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 620, lineHeight: 1.5 }}>`
- [ ] Line 147: `style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 20 }}`
      Context: `<div style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 20 }}>`
- [ ] Line 148: `style={{ position: "relative", flex: "0 0 380px" }}`
      Context: `<div style={{ position: "relative", flex: "0 0 380px" }}>`
- [ ] Line 150: `style={{ position: "absolute", top: 11, left: 12 }}`
      Context: `style={{ position: "absolute", top: 11, left: 12 }}>`
- [ ] Line 182: `style={{ overflow: "hidden" }}`
      Context: `<Card padding={0} style={{ overflow: "hidden" }}>`
- [ ] Line 193: `style={{ textAlign: "right" }}`
      Context: `<div style={{ textAlign: "right" }}>Aktionen</div>`
- [ ] Line 199: `style={{ padding: 40, textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}`
      Context: `<div style={{ padding: 40, textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}>`
- [ ] Line 242: `style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}`
      Context: `<div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>`
- [ ] Line 253: `style={{ fontSize: 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}`
      Context: `<div style={{ fontSize: 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}>`
- [ ] Line 265: `style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}`
      Context: `<div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>`
- [ ] Line 268: `style={{ width: 1, height: 18, background: "var(--g-rule)", margin: "0 4px" }}`
      Context: `<span style={{ width: 1, height: 18, background: "var(--g-rule)", margin: "0 4px" }}/>`
- [ ] Line 277: `style={{ display: "flex", alignItems: "center", gap: 10, paddingRight: 16 }}`
      Context: `<div style={{ display: "flex", alignItems: "center", gap: 10, paddingRight: 16 }}>`
- [ ] Line 280: `style={{ width: value + "%", height: "100%", background: color }}`
      Context: `<div style={{ width: value + "%", height: "100%", background: color }}/>`

## Sichtbarer Text (12) — Wortlaut prüfen

- Line 136: "Workspace · Vergangene Trips"
- Line 137: "Archiv"
- Line 165: "Sortieren"
- Line 166: "Neueste"
- Line 167: "Genauigkeit"
- Line 168: "Etappen"
- Line 188: "Name"
- Line 189: "Etappen"
- Line 190: "Zeitraum"
- Line 191: "Treffer"
- Line 192: "Was passiert ist"
- Line 193: "Aktionen"

## Mock-Felder (22) — Backend-Pre-Check

Diese Felder werden im JSX-Mock referenziert. Falls sie im TypeScript-Modell
FEHLEN, MUSS das Backend erweitert werden, BEVOR das UI gebaut wird.

- a.accuracy
- a.stages
- a.to
- b.accuracy
- b.stages
- b.to
- e.target
- filtered.length
- filtered.map
- query.toLowerCase
- t.accuracy
- t.alerts
- t.briefings
- t.id
- t.name
- trip.accuracy
- trip.alerts
- trip.from
- trip.headline
- trip.name
- trip.stages
- trip.to

## Übernahme-Checkliste

- [ ] Alle Inline-Styles 1:1 als `style=""` oder `style:` übernommen
- [ ] Keine Inline-Styles in Tailwind/CSS-Klassen übersetzt
- [ ] Sichtbarer Text wortgleich übernommen
- [ ] Mock-Felder gegen TypeScript-Modell gediffed
- [ ] Keine erfundenen Conditional-States (Loading, Empty, Fallback)
- [ ] Keine Re-Architektur in Sub-Komponenten während Übernahme
