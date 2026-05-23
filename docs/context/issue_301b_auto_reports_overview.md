# Context: issue_301b_auto_reports_overview (Lieferung B von #301)

## Request Summary
Letzter offener AC von Issue #301: Default-Content im Compare-Bereich (rechts, wenn keine
Selektion/kein Ergebnis) als **Auto-Reports-Kachelraster** (Eyebrow + H1 + Karten-Grid mit
`AutoReportCard` + `AddReportCard`) statt der heutigen schlichten Karten-**Liste**
(`CompareSubscriptionsPanel`).

## Ist-Zustand (relevant)
- `frontend/src/lib/components/compare/CompareSubscriptionsPanel.svelte` — aktuelles Default-Panel.
  Props: `subscriptions: Subscription[]`, `onsavebriefing: () => void`. Rendert: h3 „Auto-Reports" +
  Btn „Aktuellen Vergleich speichern" (= onsavebriefing); pro Sub eine `Card.Root` (Liste, `space-y-2`)
  mit `Dot` (enabled→success/default), Name, `scheduleLabel(sub) · locationsLabel(sub)`,
  „Zuletzt: …" + `Pill` (ok/Fehler), Edit-Btn (PencilIcon, **ohne Handler** — Sub-Edit heute nicht verdrahtet).
  Helper `scheduleLabel`/`locationsLabel`/`formatLastRun` bereits vorhanden.
- `frontend/src/routes/compare/+page.svelte` rendert `CompareSubscriptionsPanel` an ZWEI Stellen
  (Z. ~326 mobil, ~473 Desktop, Bedingung `{#if !result && !loading && !weatherLocationId}`), beide mit
  `onsavebriefing={() => (showSaveAsSubDialog = true)}` → öffnet `SubscriptionForm` im Dialog
  (= „neuer Auto-Report"). Import Z. 31.
- **Keine `/compare/new`-Route** (geprüft: `src/routes/compare/` hat nur `+page.*`). → `AddReportCard`
  navigiert NICHT, sondern ruft `onsavebriefing` (öffnet den Speichern-Dialog).
- `Subscription` (types.ts): `id, name, enabled, locations[], schedule, weekday, last_run?, last_status?`.
  KEIN Gruppen-Bezug → der „Group-Label"-Platzhalter aus dem Issue-Mockup = `locationsLabel`
  („Alle Orte" / „N Orte"). Kein neues Datenfeld.
- Design-System: `Eyebrow` (`$lib/components/ui/eyebrow`, Vorbild `trip-detail/BriefingPreviewCard.svelte:23`),
  `Card`, `Dot`, `Pill`, `Btn`. AP-007 (keine Hex), AP-008 (`--g-s-*` Spacing), AP-009 (keine Emojis).

## Soll (Delta)
3 neue Komponenten + 1 Import-Swap:
1. `AutoReportsOverview.svelte` (NEU) — `Eyebrow` „Orts-Vergleich · Auto-Reports" + `<h1>` „Deine Auto-Reports"
   + responsives Karten-**Grid** aus `AutoReportCard` (je Subscription) + `AddReportCard` als letzte Kachel.
   Props: `subscriptions`, `onsavebriefing` (drop-in für CompareSubscriptionsPanel).
2. `AutoReportCard.svelte` (NEU) — Status-`Dot` (enabled=success/sonst neutral), Name, Schedule (Mono) ·
   `locationsLabel`, Footer „Letzter Lauf: …" + Status-`Pill`. Reine Anzeige (Sub-Edit out-of-scope, wie heute).
3. `AddReportCard.svelte` (NEU) — gestrichelte „+"-Kachel „Neuer Auto-Report", `onclick` → `onsavebriefing`.
4. `+page.svelte` — Import + beide Render-Stellen `CompareSubscriptionsPanel` → `AutoReportsOverview`
   (gleiche Props). `CompareSubscriptionsPanel.svelte` kann danach entfernt werden (oder bleibt ungenutzt).

## Scope-Grenze (OUT)
- Subscription-Bearbeiten/Löschen-UI (heute nicht verdrahtet, kein #301-AC).
- Keine Backend-Änderungen, keine neue Route.
- Gruppen-Bezug auf Subscriptions (existiert nicht).

## Tests (KEINE Mocks)
- Reine Logik (falls Helper extrahiert): node:test. Sonst E2E (Playwright) gegen Staging:
  Default-Content zeigt Eyebrow „Auto-Reports", H1 „Deine Auto-Reports", AddReportCard,
  AddReportCard-Klick öffnet Speichern-Dialog.

## Scope-Schätzung
~140 LoC, 3 neue Dateien + 1 Swap. Innerhalb 250-LoC-Limit.
