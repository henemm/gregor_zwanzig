# Mobile: Etappen-Datum & -Startzeit bearbeitbar (Soll-Entwurf)

Issue: #2496 · Stand: 2026-10-04 · Status: PO-Entscheide vollständig, bereit für Spec

## Ausgangslage

Seit PR #2495 (PO-Entscheid F5: Mobile listen-only) ist die Etappen-
Datumsbearbeitung auf Mobile nicht mehr erreichbar — sie existierte nur im
Desktop-Inhalts-Zweig. Die komplette Kaskaden-Maschinerie
(`handleDateChange`, `applyCascade`, `dismissCascade`, `cascadeBanner`) ist
viewport-unabhängig im Panel und kann unverändert wiederverwendet werden.
Zusatzfund: `isPauseStage()` erkennt den Desktop-Namen `Pausentag` nicht
(#559-Ausnahme deckt nur `''`/`'Pause'`), der mobile Pfad legt Pausen
deshalb namenlos an.

## PO-Entscheide (2026-10-04)

| Frage | Entscheid |
|---|---|
| **F1** Datumsfeld-Platzierung | **Inline in Kartenkopf** — das statische Datum in der `.top`-Zeile jeder `StageCardM` wird direkt zum Eingabefeld (iOS öffnet nativen Rad-Picker). Kein Sheet, kein Zusatz-Tap. |
| **F2** Kaskaden-Rückfrage | **Inline-Banner bleibt** — der Banner rendert auf Mobile bereits als normale Zeile über der Liste (F2-Entscheid der letzten Runde). Kein Bottom-Sheet. |
| **F3** Pausentag-Harmonisierung | **Synonym erkennen** — `isPauseStage()` erkennt `'Pausentag'` zusätzlich als Pause; beide Anlage-Pfade (Desktop `handlePauseInsert` + Mobile `handleMobileAddPause`) setzen einheitlich `name: 'Pausentag'`. Kein eigener Typ. Risiko geprüft: kein Template nutzt diesen Namen. |
| **F4** Startzeit | **Ja, mit** — Startzeit wie auf dem Desktop neben dem Datum editierbar (`handleStartTimeChange` existiert bereits). |

## Design

### Kartenkopf-Zeile (StageCardM)

```
┌────────────────────────────────────────────────────┐
│ ⠿ T01 · ABC        [Mo| 23.09.2026]  [08:00]   ▾  │   ← 44px
│ Alpenüberquerung Etappe 1                          │
│ 12.4 km · ↑860 · 3 WP                              │
└────────────────────────────────────────────────────┘
```

- Links unverändert: Drag-Griff + `T01 · Code`.
- Rechts statt des statischen `.date`-Spans: **kompaktes Datumsfeld**
  (Wochentag-Chip + natives `input[type=date]`) und dahinter das **kompakte
  Zeitfeld** (`input[type=time]`, Anzeige-Default 08:00).
- `StageDateField`/`StageTimeField` erhalten einen `variant`-Prop
  (`'default' | 'inline'`): `inline` = ohne Label, horizontal einbettbar,
  gleiche Logik (Wochentag-Chip, 08:00-Default) geteilt — keine Kopie.
- **Tap-Konflikt:** Die Karten-Zeile toggelt beim Tap die Wegpunkt-Zeilen
  (F7). Datum/Zeit-Felder stoppen `click`/`keydown` (Enter/Space), damit
  das Öffnen des Pickers die Karte nicht auf/zuklappt.
- Erste Etappe: kleiner `· Trip-Start`-Marker am Datum (Desktop-Parität).
- Ohne `onDateChange`-Prop rendert die Karte weiterhin das statische Datum
  (Abwärtskompatibilität für andere Aufrufer/Tests).

### Kaskaden-Rückfrage

Kein neues UI. Der existierende `cascadeBanner` (inline über der Liste,
`data-testid="cascade-strip"`) wird durch das mobile Datumsfeld triggert:
`handleDateChange` deckt Defer-Save, Mehrfach-Klicks (#1389), Umsortieren
bei offener Rückfrage (#1390) und lückenlose Durchdatierung (#1393) bereits
ab — viewport-unabhängig.

### Pausentag (F3)

- `wizardHelpers.ts` `isPauseStage()`: `name !== 'Pause' && name !==
  'Pausentag'` → benannte Etappe (#559-Regel bleibt für alle anderen Namen).
- `handleMobileAddPause`: `name: 'Pausentag'` statt `''`.
- Drift-Beseitigung: die lokale Kopie `const isPause = (s) =>
  s.waypoints.length === 0` in `EditStagesPanelNew.svelte` (ohne #559-Regel)
  wird durch `isPauseStage` ersetzt — ein Heuristik-Verhalten im Panel.
- Nebeneffekt (Korrektur): Desktop-Pausen (`name: 'Pausentag'`, keine
  Wegpunkte) werden jetzt überall konsistent als Pause erkannt
  (bisher: `isPauseStage` = false, Panel-lokale Heuristik = true).

## Nicht-Ziele

- Kein Bottom-Sheet, kein Calendar-Baustein (iOS-nativer Picker reicht).
- Keine serverseitige Kaskaden-Logik (Backend speichert `stages` wortgleich,
  Kaskade bleibt Frontend-Logik — Status quo).
- Keine Änderung am Desktop-Zweig (≥900 px zeichen-identisch).
- GPX-Upload/Route-Bearbeitung mobil — außerhalb dieses Issues.

## Validierung

- Unit: `wizardHelpers.test.ts` (`Pausentag`-Fälle), `StageDateField`-/
  `StageTimeField`-Varianten.
- E2E (neu, Verhaltensname): `mobile-stage-date-time-edit.spec.ts` —
  Datum ändern → Kaskaden-Banner → beide Optionen; Zeit ändern; Tap auf
  Feld klapppt Karte nicht; Pausentag-Anlage benannt + als Pause erkannt;
  Desktop-Smoke unverändert.
- Bestand: `issue-498-stage-date-autosave.spec.ts` (38 Tests) und
  `issue-675-stage-start-time.spec.ts` müssen grün bleiben.
