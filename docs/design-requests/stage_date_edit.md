# Design-Request: Etappen-Datum bearbeiten

**Status:** new  
**Priorität:** Mittel — Pflichtfeld ohne nachträgliche Edit-Möglichkeit

## Problem

Jede Etappe hat ein Datum (`stage.date`, ISO-String z.B. `"2025-07-15"`). Dieses Datum
wird beim GPX-Bulk-Upload einmalig gesetzt und ist danach eingefroren — es gibt keine
Möglichkeit, das Datum einer einzelnen Etappe nachträglich zu korrigieren.

Aktuelle Anzeige (read-only):
- `StageDetailRow.svelte` zeigt `"DD.MM."` in der linken Etappen-Liste
- `PauseStageView.svelte` zeigt das Datum als grauen Text unter dem Etappen-Namen

## Kontext: Wo wird editiert?

Der Etappen-Editor ist `EditStagesPanelNew.svelte`:
- Links: `EtappenStrip` (horizontale Tabs, eine Tab pro Etappe)
- Rechts: bei normaler Etappe → `WaypointCard`-Liste + `ProfileEditor`
             bei Pausentag → `PauseStageView`

Der User wählt eine Etappe im Strip, die Details erscheinen rechts.

## Was benötigt wird

### 1 — Datum-Feld in der Etappen-Detail-Ansicht

**Für normale Etappen (mit Wegpunkten):**
Ein Datum-Input im oberen Bereich der rechten Spalte (über der Wegpunkt-Liste).
Platzierung: neben oder unter dem Etappen-Namen, kompakt (kein großer Formular-Block).

**Für Pausentage (`PauseStageView`):**
Das bestehende read-only-Datum (`stage.date` in grauem Text) durch ein editierbares
Datum-Input ersetzen. Das Pausentag-View ist bereits minimal — das Feld passt direkt rein.

### 2 — Kaskadier-Option (optional, als UX-Überlegung)

Wenn der User das Datum der **ersten** Etappe ändert: sollen alle Folge-Etappen um
dieselbe Anzahl Tage verschoben werden? Das wäre nützlich wenn sich ein Tourstart
um 2 Tage verschiebt.

Bitte eine Meinung dazu, ob diese Option hier sinnvoll ist und wie sie aussehen könnte
(z.B. Checkbox "Alle Folge-Etappen mitverschieben?" nach dem Speichern des ersten Datums).

## Referenz-Screenshots (IST)

Aktuelle Edit-Ansicht Etappen-Tab (Desktop):
`claude-code-handoff/screenshots/` — falls vorhanden, sonst gegen Live-URL prüfen:
`https://gregor20.henemm.com/trips/gr221-mallorca` → Tab „Route bearbeiten" → Etappen

## Design-System

Token-Referenz: `docs/design-system/TOKENS.md`  
Atom-Referenz: `docs/design-system/COMPONENTS.md`  
Anti-Patterns: `docs/design-system/ANTI-PATTERNS.md`

Datum-Inputs: Native `<input type="date">` ist akzeptabel (bereits in `EditRouteSection.svelte`
im Einsatz). Falls eine eigene Komponente empfohlen wird, bitte begründen.

## Erwarteter Output

- Mockup der rechten Spalte im Etappen-Editor mit Datum-Input für **normale Etappe**
- Mockup von `PauseStageView` mit editierbarem Datum
- Empfehlung zur Kaskadier-Option (ja/nein + Begründung, ggf. Mockup)
- Alle Screens: Desktop (1440px)
