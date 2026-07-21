---
entity_id: issue_571_home_cockpit_hero
type: module
created: 2026-06-03
updated: 2026-06-03
status: draft
version: "1.0"
tags: [frontend, home, cockpit, compare, molecules, svelte]
---

<!-- Issue #571 — Home Cockpit Hero: Compare-Modus + CompareStatusRow + Prioritäts-Logik -->

# Issue 571 — Home Cockpit Hero: Compare-Modus + CompareStatusRow + Stretch-Fix

## Approval

- [ ] Approved

## Purpose

Die Startseite (#568) kennt bisher nur zwei Zustände: aktiver Trip (Cockpit) oder
Leerzustand (Planung). Dieses Feature ergänzt einen dritten Hero-Modus für aktive
Vergleiche, damit Nutzer auch ohne laufenden Trip sofort den relevantesten
Vergleich im Cockpit sehen und steuern können. Gleichzeitig ersetzt die neue
`CompareStatusRow`-Molecule das bisherige `CompareKachel`-Grid durch kompakte
Zusatz-Zeilen unterhalb des Heroes, und der bestehende CSS-Stretch-Fehler im
`.cockpit-hero`-Grid wird behoben.

## Source

- **File:** `frontend/src/routes/+page.svelte` (Hauptdatei, ~541 Zeilen)
- **File:** `frontend/src/lib/utils/cockpitHelpers568.ts` (neue Exports: `liveTrip`, `deriveNextSend`)
- **File:** `frontend/src/lib/components/molecules/CompareStatusRow.svelte` (NEU)
- **File:** `frontend/src/lib/components/molecules/index.ts` (neuer Export)
- **File:** `frontend/src/lib/utils/homeCockpit.test.ts` (AC-12 wird ersetzt, siehe unten)

> **Schicht:** Frontend / User-UI — ausschließlich SvelteKit (`frontend/src/`).
> Kein Go-API- oder Python-Backend-Berührpunkt.

## Estimated Scope

- **LoC:** ~180–250
- **Files:** 5
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `ComparePreset` | Typ (API-Contract) | Datenmodell für aktive Vergleiche (schedule, hour_from, weekday, location_ids, empfaenger, display_config) |
| `deriveStatusFromPreset` | Funktion (bestehend) | Liefert `'active'` für aktive Vergleiche — Bedingung für Hero-Auswahl und CompareStatusRow-Filterung |
| `cockpitHelpers568.ts` | Utility-Modul (bestehend, erweiterbar) | Wird um `liveTrip` und `deriveNextSend` ergänzt |
| `QuickAction.svelte` | Molecule (bestehend, #568) | Wird für Compare-Hero-QuickActions wiederverwendet |
| `SectionH` | Atom (bestehend) | Abschnittsüberschrift mit kontextspezifischem Titel (`Was geht raus · <name>`) |
| `Dot` | Atom (bestehend) | Aktiv-Status-Indikator in `CompareStatusRow` |
| `BriefingTimelineRow` | Molecule (bestehend) | Rechte Spalte oben — wird im Compare-Modus mit Preset-Kontext befüllt |
| `heroAlerts` | Logik (bestehend) | Rechte Spalte unten — bleibt, im Compare-Modus Preset-spezifisch |
| `homeCockpit.test.ts` | Testdatei (bestehend) | AC-12 (`CompareKachel` im Home-Screen) wird durch neuen Test für `CompareStatusRow` ersetzt |

## Implementation Details

### 1. Prioritäts-Logik (Hero-Modus-Ableitung)

Die Startseite leitet den aktiven Modus in dieser Reihenfolge ab:

```
mode = "trip"     wenn liveTrip(trips, now) !== null
                  (heute ∈ [trip.startDate, trip.endDate])

mode = "compare"  sonst, wenn activeCompares.length >= 1
                  (activeCompares = compares.filter(p => deriveStatusFromPreset(p) === 'active'))

mode = "planning" sonst
```

Die neue Funktion `liveTrip(trips: Trip[], now: Date): Trip | null` in
`cockpitHelpers568.ts` gibt den ersten Trip zurück, dessen `tripStatus === 'aktiv'`
ist. Sie ersetzt keine bestehende Logik, sondern kapselt den bisher inline in der
Seite stehenden Hero-Check.

### 2. Compare-Hero (mode="compare")

**Linke Spalte — Hero-Karte:**
- Aktiv-Pill (grün)
- Preset-Name als Titel
- `N Orte · Region` (N = `preset.location_ids.length`, Region aus `preset.display_config.region` falls vorhanden)
- Zeitplan-Mono-Zeile: z.B. `täglich · 06:00` oder `wöchentlich · Mo · 08:00`
- Nächster-Versand-Berechnung via `deriveNextSend(preset, now)` → ISO-Timestamp → formatiert
- Kanal-Footer: Kanal-Chips aus `preset.empfaenger`

**Rechte Spalte oben:**
- `SectionH title="Was geht raus · <preset.name>"`
- Briefing-Info aus `schedule` / `channels` (analog Trip-Modus)

**Rechte Spalte unten:**
- Alerts-Karte — kontextspezifisch; bei keinen Alerts: Erklärtext „Keine Alerts aktiv"

**QuickActions (4 Stück):**

| Aktion | Ziel-URL | glyph |
|--------|----------|-------|
| Orte bearbeiten | `/compare/<id>/edit` | `route` |
| Ideal-Werte ändern | `/compare/<id>/edit#idealwerte` | `metrics` |
| Briefing-Zeitplan | `/compare/<id>/edit#schedule` | `clock` |
| Vorschau prüfen | `/compare/<id>?tab=preview` | `eye` |

### 3. CSS-Fix `.cockpit-hero`

Das `.cockpit-hero`-Grid erhält `align-items: start`, um das Stretch-Artefakt
(linke und rechte Spalte dehnen sich auf identische Höhe) zu beheben. Die Änderung
ist auf den CSS-Block in `+page.svelte` beschränkt.

### 4. Neue Pure Function `deriveNextSend`

```typescript
// cockpitHelpers568.ts
export function deriveNextSend(preset: ComparePreset, now: Date): Date | null
```

- Liest `preset.schedule` ('daily' | 'weekly' | 'manual'), `preset.hour_from`, `preset.weekday`
- Bei `'manual'`: gibt `null` zurück
- Bei `'daily'`: gibt nächsten Tag mit `hour_from`-Uhrzeit zurück (heute wenn Uhrzeit noch nicht erreicht, sonst morgen)
- Bei `'weekly'`: gibt nächsten passenden Wochentag (`preset.weekday`) mit `hour_from` zurück
- Gibt `null` zurück wenn keine Berechnung möglich (fehlende Felder)

### 5. Neue Molecule `CompareStatusRow.svelte`

```
Props:
  preset: ComparePreset
  dense?: boolean   — Default false
```

Aufbau (horizontal, eine Zeile):
`Dot(active) · Name · N Orte · Region · Nächster Versand (Mono) · Kanal-Chips · →`

- Klick auf die gesamte Zeile → `/compare/<preset.id>`
- Touch-Target: `min-height: 44px`
- `dense=true` reduziert Padding für kompakte Listen

**Anzeige-Logik pro Modus:**
- Trip-Modus: ALLE aktiven Vergleiche als `CompareStatusRow` unterhalb des Cockpits
- Compare-Modus: aktive Vergleiche MINUS der Hero-Preset als `CompareStatusRow`
- Planning-Modus: keine (Leerzustand zeigt ohnehin ComparePresets anders)

Das bisherige `CompareKachel`-Grid wird vollständig durch diese Rows ersetzt.

### 6. AC-12 in `homeCockpit.test.ts` — wird ersetzt

Der bestehende Test AC-12 prüft, ob `CompareKachel` im Home-Screen erscheint.
Da `CompareKachel` durch `CompareStatusRow` ersetzt wird, muss AC-12 umgeschrieben
werden: neuer Test prüft, dass `CompareStatusRow` für aktive Vergleiche unterhalb
des Heroes gerendert wird. Der alte `CompareKachel`-Assert wird entfernt.

## Expected Behavior

- **Input:** Seitenzustand mit `trips: Trip[]`, `compares: ComparePreset[]`, aktuellem Datum
- **Output:** Einer von drei Hero-Modi wird gerendert (trip / compare / planning); unterhalb des Heroes erscheinen `CompareStatusRow`-Elemente für Zusatz-Vergleiche; `deriveNextSend` liefert den berechneten nächsten Versand-Zeitstempel
- **Side effects:** Keine — alle neuen Funktionen sind pure; CSS-Änderung betrifft nur visuelle Darstellung

## Acceptance Criteria

**AC-1:** Given es gibt einen Trip dessen Start- und Enddatum heute einschließt, When ich die Startseite lade, Then wird `mode="trip"` aktiviert und die Trip-Hero-Karte erscheint links im Cockpit (nicht die Compare-Hero-Karte).

**AC-2:** Given kein Trip ist heute aktiv, aber mindestens ein ComparePreset hat `deriveStatusFromPreset === 'active'`, When ich die Startseite lade, Then wird `mode="compare"` aktiviert und die Hero-Karte zeigt den ersten aktiven Vergleich mit Aktiv-Pill, Preset-Name, Orte-Anzahl und Zeitplan-Zeile.

**AC-3:** Given kein Trip ist aktiv und keine ComparePresets sind aktiv, When ich die Startseite lade, Then wird `mode="planning"` aktiviert und der Planungs-/Leerzustand erscheint (kein Hero-Grid).

**AC-4:** Given `mode="compare"` mit einem Hero-Preset das `schedule='daily'` und `hour_from=6` hat und es ist 04:00 Uhr, When `deriveNextSend` aufgerufen wird, Then gibt die Funktion einen Timestamp zurück, der heute um 06:00 Uhr liegt (Versand noch nicht erreicht).

**AC-5:** Given `mode="compare"` ist aktiv, When ich die Hero-QuickAction „Orte bearbeiten" anklicke, Then navigiere ich zu `/compare/<id>/edit`; bei „Vorschau prüfen" zu `/compare/<id>?tab=preview`.

**AC-6:** Given `mode="compare"` mit zwei weiteren aktiven Vergleichen zusätzlich zum Hero, When ich die Startseite lade, Then erscheinen unterhalb des Cockpits genau zwei `CompareStatusRow`-Elemente (Hero-Preset ist ausgenommen) mit je einem Klick-Link zu `/compare/<id>`.

**AC-7:** Given `mode="trip"` mit drei aktiven Vergleichen, When ich die Startseite lade, Then erscheinen unterhalb des Trip-Cockpits drei `CompareStatusRow`-Elemente — alle aktiven Vergleiche, kein `CompareKachel`-Grid.

**AC-8:** Given die Startseite rendert `CompareStatusRow`-Elemente, When ich `frontend/src/lib/components/molecules` importiere, Then ist `CompareStatusRow` dort über den Barrel-Export verfügbar.

**AC-9:** Given ein mobiles Viewport (≤ 640 px), When `CompareStatusRow` gerendert wird, Then beträgt das Touch-Target mindestens 44 px Höhe.

**AC-10:** Given das `.cockpit-hero`-Grid, When linke und rechte Spalte unterschiedliche Inhaltshöhen haben, Then streckt sich keine Spalte auf die Höhe der anderen — `align-items: start` ist gesetzt und das Stretch-Artefakt erscheint nicht.

**AC-11:** Given der Abschnittstitel „Was geht raus" im Cockpit, When `mode="compare"` aktiv ist, Then lautet der Titel `"Was geht raus · <preset.name>"` mit dem konkreten Preset-Namen (nicht der generische Trip-Titel).

**AC-12 (ersetzt bisherigen AC-12):** Given aktive ComparePresets auf der Startseite, When der Home-Screen gerendert wird, Then ist kein `CompareKachel`-Element im DOM vorhanden — stattdessen sind `CompareStatusRow`-Elemente für jeden aktiven Vergleich (abzüglich Hero) vorhanden.

## Known Limitations

- `deriveNextSend` berücksichtigt keine Zeitzonen — berechnet in lokaler Browser-Zeit
- Der Kanal-Footer der Compare-Hero-Karte zeigt Empfänger aus `preset.empfaenger`, aber keinen Live-Versand-Status (analog Trip-Modus: Dots zeigen konfigurierte Kanäle, kein Health-Check)
- `dense`-Prop von `CompareStatusRow` wird für zukünftige Listen-Ansichten vorgesehen, aber in #571 noch nicht aktiv genutzt

## Changelog

- 2026-06-03: Initial spec created
