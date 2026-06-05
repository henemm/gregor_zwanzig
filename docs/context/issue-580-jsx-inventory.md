=== JSX Style Inventory: screen-trips.jsx ===

## Inline-Styles (21) — MÜSSEN 1:1 in Svelte erscheinen

- [ ] Line 19: `style={{ display: "flex", height: "100%", background: "var(--g-paper)" }}`
      Context: `<div style={{ display: "flex", height: "100%", background: "var(--g-paper)" }}>`
- [ ] Line 21: `style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}`
      Context: `<main style={{ flex: 1, padding: "32px 40px", overflow: "auto" }}>`
- [ ] Line 23: `style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}`
      Context: `<div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", marginBottom: 28 }}>`
- [ ] Line 26: `style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}`
      Context: `<div style={{ fontSize: 32, fontWeight: 600, letterSpacing: "-0.025em", marginTop: 4 }}>Trips</div>`
- [ ] Line 27: `style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 560 }}`
      Context: `<div style={{ fontSize: 14, color: "var(--g-ink-3)", marginTop: 6, maxWidth: 560 }}>`
- [ ] Line 31: `style={{ fontSize: 14, lineHeight: 0 }}`
      Context: `<Btn variant="primary" size="md" icon={<span style={{ fontSize: 14, lineHeight: 0 }}>+</span>}>Neuer Trip</Btn>`
- [ ] Line 35: `style={{ position: "relative", maxWidth: 380, marginBottom: 20 }}`
      Context: `<div style={{ position: "relative", maxWidth: 380, marginBottom: 20 }}>`
- [ ] Line 37: `style={{ position: "absolute", top: 11, left: 12 }}`
      Context: `style={{ position: "absolute", top: 11, left: 12 }}>`
- [ ] Line 50: `style={{ display: "flex", gap: 24, marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid var(--g-rule-soft)" }}`
      Context: `<div style={{ display: "flex", gap: 24, marginBottom: 20, paddingBottom: 16, borderBottom: "1px solid var(--g-rule-soft)`
- [ ] Line 58: `style={{ overflow: "hidden" }}`
      Context: `<Card padding={0} style={{ overflow: "hidden" }}>`
- [ ] Line 67: `style={{ textAlign: "right" }}`
      Context: `<div style={{ textAlign: "right" }}>Aktionen</div>`
- [ ] Line 73: `style={{ padding: 40, textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}`
      Context: `<div style={{ padding: 40, textAlign: "center", color: "var(--g-ink-3)", fontSize: 13 }}>`
- [ ] Line 79: `style={{ marginTop: 14, fontSize: 11, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.06em" }}`
      Context: `<div style={{ marginTop: 14, fontSize: 11, color: "var(--g-ink-4)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.`
- [ ] Line 89: `style={{ display: "flex", alignItems: "baseline", gap: 8 }}`
      Context: `<div style={{ display: "flex", alignItems: "baseline", gap: 8 }}>`
- [ ] Line 115: `style={{ display: "flex", alignItems: "center", gap: 10 }}`
      Context: `<div style={{ display: "flex", alignItems: "center", gap: 10 }}>`
- [ ] Line 116: `style={{ width: 7, height: 7, borderRadius: "50%", background: st.dot, flexShrink: 0 }}`
      Context: `<span style={{ width: 7, height: 7, borderRadius: "50%", background: st.dot, flexShrink: 0 }}/>`
- [ ] Line 117: `style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em" }}`
      Context: `<span style={{ fontSize: 14, fontWeight: 600, letterSpacing: "-0.01em" }}>{trip.name}</span>`
- [ ] Line 121: `style={{ fontSize: 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}`
      Context: `<div style={{ fontSize: 13, color: "var(--g-ink-2)", fontVariantNumeric: "tabular-nums" }}>`
- [ ] Line 124: `style={{ fontSize: 13, color: "var(--g-ink-2)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.02em" }}`
      Context: `<div style={{ fontSize: 13, color: "var(--g-ink-2)", fontFamily: "var(--g-font-mono)", letterSpacing: "0.02em" }}>`
- [ ] Line 127: `style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}`
      Context: `<div style={{ display: "flex", gap: 4, justifyContent: "flex-end" }}>`
- [ ] Line 132: `style={{ width: 1, height: 18, background: "var(--g-rule)", margin: "0 4px" }}`
      Context: `<span style={{ width: 1, height: 18, background: "var(--g-rule)", margin: "0 4px" }}/>`

## Sichtbarer Text (7) — Wortlaut prüfen

- Line 25: "Workspace · Trips"
- Line 26: "Trips"
- Line 31: "Neuer Trip"
- Line 64: "Name"
- Line 65: "Etappen"
- Line 66: "Zeitraum"
- Line 67: "Aktionen"

## Mock-Felder (14) — Backend-Pre-Check

Diese Felder werden im JSX-Mock referenziert. Falls sie im TypeScript-Modell
FEHLEN, MUSS das Backend erweitert werden, BEVOR das UI gebaut wird.

- e.target
- filtered.length
- filtered.map
- query.toLowerCase
- st.dot
- st.label
- statusMap.draft
- t.id
- t.name
- trip.from
- trip.name
- trip.stages
- trip.status
- trip.to

## Übernahme-Checkliste

- [ ] Alle Inline-Styles 1:1 als `style=""` oder `style:` übernommen
- [ ] Keine Inline-Styles in Tailwind/CSS-Klassen übersetzt
- [ ] Sichtbarer Text wortgleich übernommen
- [ ] Mock-Felder gegen TypeScript-Modell gediffed
- [ ] Keine erfundenen Conditional-States (Loading, Empty, Fallback)
- [ ] Keine Re-Architektur in Sub-Komponenten während Übernahme
