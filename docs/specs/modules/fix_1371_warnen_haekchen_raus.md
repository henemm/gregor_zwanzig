---
entity_id: fix_1371_warnen_haekchen_raus
type: bugfix
created: 2026-07-30
updated: 2026-07-30
status: draft
version: "1.0"
tags: [frontend, corridor-editor, alarme, compare, trip]
---

<!-- Issue #1371 -->

# Fix #1371 — "Warnen"-Häkchen raus aus Wertebereiche

## Approval

- [ ] Approved

## Purpose

Das "Warnen"-Häkchen im Reiter *Wertebereiche* (Korridor-Editor) irritiert:
es sitzt neben einem Wertebereich, wirkt aber nicht auf dessen Über-/
Unterschreitung, sondern schreibt beim Speichern in `metric_alert_levels` —
dieselbe Einstellung, die der Reiter *Alarme* bereits vollwertig anbietet
(`off | entspannt | standard | sensibel`). Der Knopf entfällt; die
Alarm-Ein/Aus-Wahl liegt danach ausschließlich im Reiter *Alarme*. Der
Reiter *Wertebereiche* markiert danach nur noch (grüne Markierung im
Briefing bei Werten im Bereich) — keine zweite, redundante Alarmquelle mehr.

**Ausdrückliche Nicht-Prämisse (Richtigstellung ggü. Issue-Text):**
`Corridor.notify` ist NICHT wirkungslos — es steuert über
`deriveMetricAlertLevel()` / `buildCorridorSavePayload()` /
`buildCompareCorridorSavePayload()` beim Speichern `metric_alert_levels`,
und das ist die tatsächliche Alarmquelle (gelesen von
`src/services/compare_alert.py:225-226`, `src/services/trip_alert.py:145,
199-200,267-268,307`, `src/services/deviation_alert_engine.py:151-160`,
`src/services/alert_preset.py:100`). Der Fix behebt die **doppelte
Bedienung derselben Einstellung an zwei Stellen**, nicht ein wirkungsloses
Feature.

## Source

- **File:** `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`
- **File:** `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte`
- **File:** `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.ts`
- **File:** `frontend/src/lib/components/shared/AlarmeTab.svelte`
- **File:** `frontend/src/lib/components/shared/alarme-tab/alarmeTabSections.ts`
- **Identifier:** `buildCorridorSavePayload`, `buildCompareCorridorSavePayload`, `deriveMetricAlertLevel`

> **Schicht-Hinweis:** Reine Frontend-Änderung (SvelteKit, `frontend/src/lib/...`).
> Python (`src/app/models.py`, `src/app/loader.py`, `src/services/*`) und Go
> (`internal/model/trip.go`) werden **nicht verändert** — genau das ist Teil
> des Nachweises (A3, Datenerhalt).

## Estimated Scope

- **LoC:** ~250-350 (Code + Tests, siehe Abschnitt „Budget" unten — Grenzfall/vermutlich Überschreitung)
- **Files:** ~11 Code-/Test-Dateien (5 Produktionsdateien + mindestens 6 Bestandstests, s. Abschnitt „Betroffene Bestandstests")
- **Effort:** medium (kleiner fachlicher Schnitt, aber viele Berührungspunkte durch die geteilte Trip/Compare-Bauart)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `corridorEditorState.ts::deriveMetricAlertLevel` | function | wird für Route/Vergleich in den Save-Payload-Buildern aufgerufen — Kernstelle des Fixes |
| `AlertMetricLevelTable.svelte` (`frontend/src/lib/components/alerts-tab/`) | component | bestehender, vollwertiger Ersatzweg im Reiter *Alarme* — bleibt unverändert, wird nicht neu gebaut |
| `AlarmeTab.svelte` / `alarmeTabSections.ts` | shared component | zeigt den "Korridor-Auslöser"-Block, dessen Text nach diesem Fix nicht mehr stimmt |
| `Corridor` (Python `src/app/models.py`, `src/app/loader.py`, Go `internal/model/trip.go`) | Datenmodell | `notify`-Feld bleibt bestehen — nur nicht mehr bedienbar |

## Implementation Details

### A1 — Bedienelement entfernen (geteilter Baustein, EINMAL gebaut)

"Warnen"-Button entfällt aus beiden Kontexten (`route` UND `vergleich`) an
genau zwei Stellen — der Korridor-Editor ist geteilter Code
(Trip/Compare-Teilungs-Invariante, CLAUDE.md):

- `CorridorEditor.svelte` — `.ce-effects`-Block (Zeilen ~344-350): sowohl
  die gesperrte Variante (`alarmCapable === false`) als auch die aktive
  Variante entfallen. Nur `Markieren`-Button und `✕ entfernen` bleiben.
- `CorridorEditorMobile.svelte` — analoger `.cem-effects`-Block (Zeilen
  ~329-335).

Keine kontext-spezifische Zweitlösung — beide Komponenten sind bereits
context-parametrisiert (`context="route"|"vergleich"`), der Wegfall gilt
für beide gleichermaßen mit derselben Code-Änderung je Datei.

### A2 — Speichern im Reiter Wertebereiche lässt `metric_alert_levels` unberührt

Kernstück des Fixes. `buildCorridorSavePayload()` und
`buildCompareCorridorSavePayload()` (`corridorEditorState.ts`) dürfen ab
sofort **keine** Ableitung mehr aus `notify` in Richtung
`metric_alert_levels`/`metricAlertLevels` vornehmen — auch nicht das
`'off'`-Setzen für per "✕ entfernen" entfernte Zeilen (aktuell
`buildCorridorSavePayload` Zeilen 208-214 und
`buildCompareCorridorSavePayload` Zeilen 547-552, 567-575). Beide Funktionen
geben `corridors[]` weiterhin mit dem (nicht mehr editierbaren, aber
gespeicherten) `r.notify`-Wert zurück — nur die Alarm-Level-Ausgabe entfällt
bzw. bleibt ein reiner Pass-Through des unveränderten Eingabewerts.

Konkret: der PUT-Aufruf in `CorridorEditor.svelte::buildSaveFn()` (Zeilen
128-137) darf `display_config.metric_alert_levels` nicht mehr explizit
überschreiben — `trip!.display_config` wird unverändert durchgereicht.
Analog schreibt `syncToWizard()` (Zeilen 143-154, Compare-Kontext) die
Wizard-Rune `ws.metricAlertLevels` nicht mehr aus den Wertebereiche-Zeilen
heraus um.

Das ist der wichtigste Verhaltensunterschied ggü. dem Bestand: **ohne diese
Änderung würde ein Speichern im falschen Reiter weiterhin still die im
Reiter Alarme gesetzte Empfindlichkeit verstellen** — genau der Fehler, den
der Umbau beheben soll.

### A3 — Datenerhalt

`Corridor.notify` bleibt unverändert in Modell und Persistenz:
`src/app/models.py:887`, `src/app/loader.py:231` (Lesen) und `:1513`
(Schreiben), `internal/model/trip.go:74`. **Kein Python-/Go-Code wird in
diesem Fix verändert.** Ein Laden-Speichern-Durchlauf über den Reiter
Wertebereiche darf den gespeicherten `notify`-Wert eines Korridors nicht
verändern oder verlieren (Read-Modify-Write mit Merge, BUG-DATALOSS-GR221 /
#102) — er wird zwar nicht mehr über die UI gesetzt, aber weiterhin exakt
so re-serialisiert, wie er geladen wurde.

### A4 — Zusammenfassungen anpassen

- **Korridor-Editor-Zusammenfassung** ("N × Warnen"): entfällt ersatzlos an
  allen vier Stellen — `CorridorEditor.svelte` Zeilen 125 (`notifyN`-Deklaration)
  und 367 (Anzeige), `CorridorEditorMobile.svelte` Zeilen 110 und 356.
  `markN`/"N × Markieren" bleibt unverändert bestehen.
- **"Korridor-Auslöser"-Block im Reiter Alarme** (`AlarmeTab.svelte`
  Zeilen ~232-244, Text "Keine Warn-Schwellen aktiv" / "N × Warnen aktiv"
  aus `notifySummaryLabel()`, `alarmeTabSections.ts:38-40`, Sprunglink
  "Wertebereiche öffnen →"): Da der Reiter Wertebereiche nach diesem Fix
  keine Warn-Schwellen mehr setzt, ist eine Aussage über "Warn-Schwellen"
  an dieser Stelle sachlich falsch.

  **PO-ENTSCHIEDEN (2026-07-30, Henning): Variante 1 — Block ersatzlos
  entfernen.** Begründung des PO-Entscheids: die darunterliegende
  `metric-levels`-Sektion (`AlertMetricLevelTable`) zeigt die tatsächliche,
  aktuelle Alarm-Konfiguration je Wettergröße bereits vollständig; der
  "Korridor-Auslöser"-Block wäre nach dem Fix eine reine Dopplung ohne
  neue Information. Die verworfene Alternative (Umwidmung auf einen
  `mark`-Zähler mit Sprunglink) ist damit **nicht** umzusetzen — nicht
  erneut vorlegen.

  Damit sind folgende Durchreichungen vollständig zu entfernen:
  `CompareTabs.svelte:855`→`:1425`,
  `CompareNewEditor.svelte:110`→`:391,:476`,
  `AlarmeScheduleTab.svelte:44`→`:58`, `AlarmeTab.svelte:59,73,80`
  (`notifyCount`-Prop und `summaryLabel`).

- **PO-Vorgabe 2026-07-30, gilt für A1 UND A4: Trip und Ortsvergleich werden
  gleich behandelt.** Sowohl das "Warnen"-Bedienelement als auch der
  "Korridor-Auslöser"-Block verschwinden in **beiden** Kontexten, und zwar
  durch **eine** Änderung am geteilten Baustein — nicht durch zwei
  gleichlautende Eingriffe und ausdrücklich **nicht** über einen
  `context`-Zweig, der es nur auf einer Seite entfernt. Eine Lösung, die den
  Knopf oder den Block auf einer der beiden Seiten stehen lässt, ist ein
  Verstoß gegen diese Vorgabe und gegen die Trip/Compare-Teilungs-Invariante
  (CLAUDE.md). Betroffen sind daher beide Aufrufwege von `AlarmeTab`:
  `CompareTabs.svelte`/`CompareNewEditor.svelte` (Ortsvergleich) und
  `AlarmeScheduleTab.svelte` (Trip). Prüfbar: siehe AC-1 und AC-6.

### A5 — Was NICHT angefasst wird

- **`mark`-Pfad bleibt unverändert.** `mark` wirkt weiterhin real:
  `src/output/renderers/email/compare_html.py:355` (`_mark_lookup`),
  Aufrufer `:587` und `:763`, CSS `:1351`. Der Reiter Wertebereiche macht
  nach diesem Fix genau eine Sache: markieren.
- **`ROUTE_METRIC_DEFS`/`ROUTE_CORRIDOR_CATALOG_IDS`** (fest verdrahtete
  Listen, `corridorEditorState.ts:28-35`, `:90`) bleiben unverändert — das
  ist Issue #1384, ein eigenes Ticket, hier bewusst kein Vorgriff.
- **`alarmCapable`** bleibt backendseitig im Katalog erhalten
  (`src/output/renderers/compare_metric_catalog.py:267`). Im Frontend
  hängen seine bisherigen Verwendungen (`corridorEditorState.ts:452`,
  `:498`, `:573`) allesamt an `notify` und werden durch A1/A2
  unerreichbar — nur das im Korridor-Editor unerreichbar Gewordene wird
  zurückgebaut (z.B. die `alarmCapable === false`-Sperr-Variante des
  Warnen-Buttons, die mit A1 ohnehin komplett entfällt); die
  `alarmCapable`-Definition selbst und ihre Nutzung außerhalb des
  Korridor-Editors bleiben unangetastet, ausdrücklich ohne Vorgriff auf
  #1384.

## Betroffene Bestandstests

Diese Tests verlangen heute explizit das ALTE Verhalten (notify steuert
`metric_alert_levels` beim Wertebereiche-Speichern) und müssen auf die NEUE
Regel aus A2 umgeschrieben werden — **nicht ersatzlos löschen**:

- `frontend/src/lib/components/shared/__tests__/weatherMetricsTabCorridorCoupling.test.ts:78-106`
  — der Regressions-Anker "notify steuert weiterhin metricAlertLevels" ist
  der direkte Gegenanker zu A2. Neue Erwartung: `buildCorridorSavePayload`/
  `buildCompareCorridorSavePayload` liefern `metric_alert_levels` unverändert
  gegenüber `originalLevels`, unabhängig von `row.notify` und unabhängig
  davon, ob eine Zeile per `removedMetrics` entfernt wurde.
- `frontend/src/lib/components/shared/corridor-editor/corridorEditorMobile.test.ts:93-94,140-142`
  — Erwartungen an den "Warnen"-Button/`notifyN`-Zähler in der mobilen
  Ansicht; neue Erwartung: Button und Zähler existieren nicht mehr,
  `markN`-Zähler bleibt unverändert testbar.
- `frontend/src/lib/components/shared/corridor-editor/corridorEditorState.test.ts:397-404,447`
  — direkte Tests der Save-Payload-Funktionen auf `notify`-Ableitung;
  neue Erwartung analog Punkt 1.
- `frontend/src/lib/components/shared/__tests__/alarme_tab_sections.test.ts:83-92`
  — Test des "Korridor-Auslöser"-Textes/`notifySummaryLabel`; neue
  Erwartung richtet sich nach der PO-Entscheidung aus A4 (Variante 1 oder 2).
- `frontend/src/lib/components/compare/compareEditorSave.test.ts:266,285`
  — Compare-Save-Pfad prüft heute `notify`-getriebene `metricAlertLevels`;
  neue Erwartung: unverändert gegenüber `original.metricAlertLevels`.
- `frontend/src/lib/components/compare/__tests__/kebab_toggle_delegation.test.ts:49,80,138`
  — prüft Delegation des Warnen-Toggles im Kebab-Menü/Editor; neue
  Erwartung: Delegation existiert nicht mehr für "Warnen" im
  Wertebereiche-Kontext (Alarme-Tab bleibt einziger Schreibpfad).
- `frontend/src/lib/components/compare/__tests__/compare_hub_wizard_bridge.test.ts:89,159,193`
  — Wizard-Bridge-Erwartungen an `notify`→`metricAlertLevels`-Synchronisation
  über den Wertebereiche-Pfad; neue Erwartung analog Punkt 1.
- `frontend/src/lib/components/compare/__tests__/hub_versand_inline.test.ts:66`
  — Randberührung derselben Kopplung; ggf. nur Fixture-Anpassung nötig.

## Expected Behavior

- **Input:** Nutzer öffnet den Reiter *Wertebereiche* (Trip oder
  Ortsvergleich), ändert Von/Bis-Grenzen und/oder das Markieren-Häkchen
  einer Zeile, speichert (Trip: automatisches PUT je Änderung; Vergleich:
  Speichern-Button im Editor-Rahmen).
- **Output:** Der gespeicherte Wertebereich (`corridors[].range`) und das
  Markieren-Flag (`corridors[].mark` bzw. `display_config.ideal_ranges`)
  ändern sich wie gewünscht. Die im Reiter *Alarme* eingestellte
  Alarm-Empfindlichkeit (`metric_alert_levels`) bleibt exakt so, wie sie vor
  dem Speichern im Wertebereiche-Reiter war.
- **Side effects:** Keine — insbesondere kein stilles Verstellen der
  Alarm-Konfiguration durch eine Aktion im falschen Reiter.

## Acceptance Criteria

- **AC-1:** Given der Reiter *Wertebereiche* eines Trips oder Vergleichs / When er geöffnet wird / Then ist neben jeder Zeile kein "Warnen"-Bedienelement mehr sichtbar — nur "Markieren" und "✕ entfernen" bleiben, unverändert für beide Kontexte (route und vergleich).
  - Test: Playwright/Component-Test öffnet den Korridor-Editor (Desktop und Mobile, beide Kontexte) und prüft die Abwesenheit des "Warnen"-Buttons per Testid/Text.

- **AC-2:** Given ein Trip hat für eine Wettergröße eine im Reiter *Alarme* gesetzte Empfindlichkeit ungleich "off" / When der Nutzer im Reiter *Wertebereiche* nur die Von/Bis-Grenze derselben Größe ändert und speichert / Then bleibt die im Reiter *Alarme* angezeigte Empfindlichkeit für diese Größe exakt unverändert.
  - Test: `buildCorridorSavePayload()`/`buildCompareCorridorSavePayload()` mit vorbelegten `originalLevels` aufrufen, Range einer Zeile ändern, prüfen dass die zurückgegebenen Alarm-Levels bit-identisch zu `originalLevels` sind — echte Funktion, kein Mock.

- **AC-3:** Given ein Trip hat für eine Wettergröße eine im Reiter *Alarme* gesetzte Empfindlichkeit ungleich "off" / When der Nutzer im Reiter *Wertebereiche* die Zeile dieser Größe per "✕ entfernen" entfernt und speichert / Then bleibt die im Reiter *Alarme* angezeigte Empfindlichkeit für diese Größe exakt unverändert (kein stilles Umschalten auf "off").
  - Test: dieselben Funktionen mit `removedMetrics` aufrufen, prüfen dass die betroffene Metrik in der Ausgabe weiterhin den ursprünglichen Level trägt statt `'off'`.

- **AC-4:** Given ein gespeicherter Korridor mit `notify: true` in der Persistenz / When ein Laden-Ändern-Speichern-Durchlauf über den Reiter Wertebereiche stattfindet (z.B. nur die Grenze geändert) / Then bleibt `Corridor.notify` im gespeicherten Datensatz unverändert `true` (weder verloren noch überschrieben) — Nachweis über echtes Python-Modell/Loader-Roundtrip, kein Frontend-Mock.
  - Test: bestehende bzw. neue Roundtrip-Prüfung in `src/app/loader.py`-Testsuite: Corridor mit `notify=true` speichern, über den Wertebereiche-Payload-Pfad erneut mit geänderter Range speichern, laden, `notify` weiterhin `true`.

- **AC-5:** Given der Reiter *Alarme* zeigt für eine Wettergröße die Empfindlichkeitsstufe an / When der Nutzer sie dort ändert und speichert / Then wirkt sich die Änderung wie bisher auf den nächsten ausgelösten Alarm aus (Ersatzweg bleibt vollwertig, unverändert durch diesen Fix).
  - Test: bestehender `AlertMetricLevelTable`-Test (unverändert grün) plus ein Test, der zeigt, dass eine über den Alarme-Reiter gesetzte Stufe nach einer nachfolgenden Wertebereiche-Aktion (Grenze ändern, speichern) weiterhin die zuletzt im Alarme-Reiter gesetzte Stufe ist — nicht die alte, vom Wertebereiche-Reiter abgeleitete.

- **AC-6:** Given der Reiter *Alarme* — geöffnet einmal an einem Trip und einmal an einem Ortsvergleich / When der Nutzer ihn ansieht / Then erscheint an beiden Stellen gleichermaßen kein Kästchen mehr, das aktive Warn-Schwellen oder "Korridor-Auslöser" behauptet, und es bleibt auf beiden Seiten bei derselben Darstellung — die Wettergrößen mit ihrer Alarm-Empfindlichkeit darunter sind unverändert vorhanden.
  - Test: Component-Test für `AlarmeTab` in BEIDEN Kontexten (`context="route"` und `context="vergleich"`) — Abwesenheit des Blocks (Testid `alarme-korridor-jump` bzw. Abschnitt `korridor-summary`) und Anwesenheit der Metrik-Stufen-Tabelle. Zusätzlich ein Test, der belegt, dass die Entfernung NICHT über einen `context`-Zweig gelöst ist (kein Kontext zeigt den Block).

## Known Limitations

- `ROUTE_METRIC_DEFS`/`ROUTE_CORRIDOR_CATALOG_IDS` (feste 6er-Metrikliste im
  route-Kontext) bleiben unverändert — Folgearbeit #1384.
- Der "Korridor-Auslöser"-Block im Reiter Alarme ist **PO-entschieden
  (2026-07-30): ersatzlos entfernen** — kein offener Punkt mehr, siehe A4.
  Da damit ein sichtbares Element wegfällt, gehört es zum prüfbaren Umfang:
  nach dem Fix darf im Reiter *Alarme* keine Aussage über "Warn-Schwellen"
  oder "Korridor-Auslöser" mehr erscheinen.
- `alarmCapable` bleibt als Katalog-Feld bestehen, verliert aber im
  Korridor-Editor jede sichtbare Wirkung, da sein einziger Verwendungszweck
  dort (die Warnen-Sperre) mit A1 komplett entfällt — bewusst kein Vorgriff
  auf #1384.

## Budget

**PO-Freigabe 2026-07-30 (Henning): Limit einmalig auf 400 Zeilen angehoben**
(`workflow.py set-field loc_limit_override 400`). Begründung des Entscheids:
der Mehraufwand ist fast ausschließlich Pflege bestehender Prüfungen, nicht
neuer Code; ein Schnitt in zwei Lieferungen hätte einen Zwischenzustand
erzeugt, in dem das Häkchen weg, die Nebenwirkung auf die Alarm-Einstellungen
aber noch da wäre — genau der Zustand, der vermieden werden soll.

Angefordertes Limit: 250 Zeilen (Code + Tests) je Arbeitsgang. Geschätzt:

- Produktionscode (5 Dateien: `CorridorEditor.svelte`,
  `CorridorEditorMobile.svelte`, `corridorEditorState.ts`, `AlarmeTab.svelte`,
  `alarmeTabSections.ts` + 3 Durchreichungs-Callsites): ~90-120 Zeilen (add+delete).
- Bestandstests (mindestens 6 Dateien, s. Abschnitt „Betroffene Bestandstests"):
  ~120-180 Zeilen, da mehrere Tests nicht nur eine Assertion, sondern ganze
  Testfälle auf die neue Regel umschreiben.

**Geschätzte Summe: ~250-350 Zeilen — Grenzfall, voraussichtlich leichte
Überschreitung.** Grund: der Korridor-Editor ist geteilter Code mit sechs
unabhängigen Bestandstest-Dateien, die die alte Kopplung explizit
verifizieren (s.o.) — deren Umschreiben ist kein Nebenaufwand, sondern
Teil des Nachweises (AC-2/AC-3), kann aber nicht sinnvoll weiter verkleinert
werden, ohne Testabdeckung zu verlieren. Empfehlung: `workflow.py set-field
loc_limit_override 400` nach PO-Freigabe, falls die tatsächliche
Implementierung das ursprüngliche Limit überschreitet.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine UI-Vereinfachung/Bugfix innerhalb eines bestehenden,
  bereits entschiedenen Datenmodells (`Corridor.notify` bleibt bestehen,
  `metric_alert_levels` bleibt die Alarmquelle) — keine neue
  Architektur-Entscheidungsfläche berührt (kein neuer Kanal, kein neuer
  Provider, kein neues Datenmodell, keine Auth-/Editor-Paradigma-Änderung).

## Changelog

- 2026-07-30: Initial spec created — Issue #1371
