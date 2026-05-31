# Context: Issue #481 — Mobile Home Header-Icons falsch

## Request Summary
Der mobile Header zeigt rechts einen Mond/Sonne-Button (Dark-Mode-Toggle). Laut Design-Handoff soll er stattdessen eine Glocke (Bell) und einen Plus-Button zeigen.

## Betroffene Dateien

| Datei | Relevanz |
|-------|----------|
| `frontend/src/lib/components/ui/sidebar/TopAppBar.svelte` | Einzige Änderungsdatei: Dark-Toggle entfernen, Bell+Plus hinzufügen |
| `frontend/src/routes/+layout.svelte` | Übergibt `darkMode`/`ontoggleDark` an TopAppBar — bleibt unverändert |
| `frontend/src/lib/components/ui/sidebar/Sidebar.svelte` | Hat ebenfalls Dark-Mode-Toggle (bleibt erhalten als einziger mobiler Zugangspunkt) |
| `frontend/src/lib/components/mobile/MIcon.svelte` | Liefert `bell` und `plus` SVG-Icons |

## IST-Zustand
`TopAppBar.svelte` rendert rechts:
```svelte
<button onclick={ontoggleDark}>
    {#if darkMode}<SunIcon />{:else}<MoonIcon />{/if}
</button>
```

## SOLL-Zustand (aus Design-Handoff `soll-screenshots/mobile-m-home.png` + SOLL-IST-Analyse Finding M-09)
```
[≡]  gregor.zwanzig  [🔔]  [+]
```
- Hamburger links (bleibt)
- Wordmark Mitte (bleibt)
- Glocke (Bell) rechts — Placeholder, kein Ziel (Notifications-System noch nicht implementiert)
- Plus rechts — navigiert zu `/trips/new`

## Bestehende Muster
- `MIcon` hat `kind='bell'` und `kind='plus'` bereits als Inline-SVGs
- `<a href="/trips/new">` wird in der App mehrfach so genutzt (kein `goto` nötig)
- Dark-Mode-Toggle bleibt im Sidebar-Drawer erhalten (lines 91+143 in Sidebar.svelte) — kein Feature-Verlust

## Abhängigkeiten
- **Upstream:** `+layout.svelte` übergibt `darkMode`/`ontoggleDark` — Prop-Interface bleibt identisch, Props sind bereits optional mit Defaults
- **Downstream:** Keine anderen Komponenten importieren TopAppBar direkt

## Risiken
- Dark-Mode auf Mobile ist danach nur noch über Sidebar-Drawer erreichbar (Intentional — entspricht SOLL-Design)
- Bell-Button ohne Aktion könnte verwirrend wirken → `aria-label="Benachrichtigungen (bald verfügbar)"` setzen
