---
entity_id: fix_1895_alarm_modus_rueckbau
type: module
created: 2026-09-21
updated: 2026-09-21
status: draft
version: "1.0"
workflow: fix-1895-alarm-absolut-modus
tags: [alarm-regeln, absolut-modus, rueckbau, frontend, trip-new, ratsche]
---

# #1895 Schritt 1 — Modus-Auswahl „Änderung/Absolut/Beides" im Alarmregel-Editor zurückbauen

## Approval

- [ ] Approved

## Purpose

Der Alarmregel-Editor bietet beim Bearbeiten einer Regel drei Modus-Karten an
(„Änderung", „Absolut", „Beides") samt Absolut-Schwellenfeld. Der Absolut-Modus
verspricht eine Schwelle, die seit dem Umbau #946 nie mehr einen Alarm auslöst; der
Server wandelt jede Absolut-Regel bei jedem Laden und Speichern ohnehin still in eine
Änderungsregel um (`SyncAlertRules`). Die Bedienfläche sagt also etwas, das es nicht gibt.

Dieser Schritt nimmt die Modus-Auswahl und das Absolut-Schwellenfeld aus der
Bedienfläche. Die Regel selbst bleibt als unsichtbarer Träger der Kanalzuordnung
(`rule.channels`) bestehen — sie ist heute ihre einzige wirksame Aufgabe neben dem
Prüf-Gate `has_active_rules`. PO-Entscheid vom 2026-08-19 im Issue #1895:
Modus-Auswahl und Absolut-Feld verschwinden, die Kanalzuordnung wandert in Schritt 1
nirgendwohin, bestehende Regeln werden nicht migriert.

**Frontend-only.** Kein Go, kein Python, kein Schema, keine Migration.

## Source

- **File:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte`
- **Identifier:** Komponente `AlertRuleRow` (Edit-Card) und `expandRules()` in
  `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts`

> Schicht: **Frontend / User-UI** (`frontend/src/lib/components/alert-rules-editor/`,
> SvelteKit). Keine Datei unter `internal/`, `cmd/`, `src/`, `api/` wird angefasst.

### Welche Fläche gemeint ist (präzise)

`AlertRulesEditor` (und damit `AlertRuleRow`) hat genau **zwei Mounts**, beide Trip:

| Reiter | Datei | Zeilen |
|---|---|---|
| **„Alerts"** (Trip anlegen, `/trips/new`) | `frontend/src/lib/components/trip-new/TripNewEditor.svelte` | 67, 862, 1102 |
| **„Alarmregeln"** (Trip bearbeiten) | `frontend/src/lib/components/edit/TripEditView.svelte` | 64, 205 |

**Ausdrücklich NICHT gemeint** ist der Reiter **„Alarme"**
(`frontend/src/lib/components/trip-detail/AlarmeScheduleTab.svelte`). Er mountet
`AlarmeTab` mit den Empfindlichkeitsstufen und kennt kein Modus-Konzept. Der
PO-Entwurf im Issue-Kommentar sagt „Alarme-Reiter" — das zielt auf den falschen
Bildschirm und wird hier korrigiert.

Nachgemessen beim Schreiben dieser Spec: `TripEditView.svelte` hat im produktiven
Frontend **keinen Importeur** (nur Textlese-Tests und Kommentare verweisen darauf).
Der einzige live erreichbare Mount ist damit „Alerts" in `TripNewEditor`. Der Umbau
betrifft beide Mounts gleichermaßen, weil beide dieselbe Komponente einbinden; der
Browser-Nachweis läuft am live erreichbaren Mount (`/trips/new`).

## Ausdrückliche Annahmen (freigabepflichtig — hier entscheidet der PO)

### Annahme 1: Der Δ-Zweig bleibt sichtbar

> **ANNAHME:** In Schritt 1 fallen **nur die Absolut-Teile**. Der **Δ-Zweig bleibt
> sichtbar**: das Feld **Δ-Schwelle** (`alert-rule-threshold`) und das **Zeitfenster**
> (`alert-rule-delta-window`) bleiben in der Edit-Card stehen.

Der PO-Zielsatz lautet „sichtbar bleibt allein die Empfindlichkeitsstufe". Nachgemessen
lösen aber **auch Δ-Schwelle und Zeitfenster keinen Alarm aus** — einzige Alarmquelle ist
`display_config.metric_alert_levels` (ADR-0043). Diese Spec liest den Entscheid trotzdem
**wörtlich** und lässt den Δ-Zweig stehen, aus drei Gründen:

1. Die PO-Fundstellentabelle sagt wörtlich, die Modus-Zweige von `expandRules()`
   „kollabieren auf einen (`kind:'delta'`)". Der überlebende Zweig braucht beide Eingaben.
2. Die zwei Entfernungs-Punkte des Entscheids („Modus-Auswahl", „Absolut-Schwellenfeld")
   sind genau die Menge dessen, was fällt, wenn die Modus-Maschinerie fällt.
3. Die Empfindlichkeitsstufe liegt gar nicht auf dieser Fläche, sondern im Reiter
   „Alarme". Der Zielsatz ist eine Produktaussage, keine Feldliste.

**Folge:** Nach diesem Schritt zeigt die Edit-Card weiterhin zwei Eingaben, die (wie
vorher schon) nichts auslösen. Das ist derselbe Befund wie beim Absolut-Modus und gehört
zu Schritt 2.

**Falls der PO es anders meint** (Δ-Schwelle und Zeitfenster sollen ebenfalls fallen,
die Edit-Card also nur noch Metrik, Kanäle und „Aktiv" zeigen): Die Freigabe dieser Spec
ist der vorgesehene Ort für die Korrektur. AC-1, AC-5 und AC-7 ändern sich dann; der Rest
(AC-2, AC-3, AC-4, AC-6) bleibt unverändert.

### Annahme 2: Standardwerte einer neu hinzugefügten Regel

> **ZWEITE ANNAHME:** Weil es nach dem Umbau nur noch Änderungsregeln gibt, muss die
> Vorgabe einer frisch hinzugefügten Regel (`newDefaultRule()`, heute `kind:'absolute'`,
> Schwelle 50 km/h) auf `kind:'delta'` umgestellt werden — sonst zeigt jede neue Zeile
> weiter die Kennzeichnung „Abs". Das steht **nicht** im PO-Entscheid und ist eine
> Folgeentscheidung dieser Spec.

Zur Wahl stehen:

- **Variante A (angenommen):** `kind:'delta'`, Δ-Schwelle **20**, Zeitfenster `6h`. Die 20
  ist kein neuer Wert, sondern die bereits heute vorbelegte Δ-Schwelle des Editors
  (`AlertRuleRow.svelte:47`, `draftDeltaThreshold = 20`); die `6h` ebenso (`:48`). Der
  Nutzer sieht dieselben Zahlen wie bisher, wenn er im Modus „Änderung" eine Regel anlegt.
- **Variante B:** `kind:'delta'`, Schwelle unverändert **50**. Kleinste Wertänderung, aber
  50 km/h als Δ-Schwelle ist eine deutlich unempfindlichere „Änderung" als der bisherige
  Δ-Standard.

Für die Alarmwirkung ist beides folgenlos (die Δ-Schwelle löst nichts aus, ADR-0043); es
geht nur um die angezeigte Vorgabe. AC-7 ist auf Variante A geschrieben; bei Variante B
ändert sich in AC-7 nur die Zahl (50 statt 20).

## Estimated Scope

- **LoC:** überwiegend Rückbau (Löschzeilen), geschätzt −250 / +130 inklusive Tests.
  Ein `loc_limit_override` ist wahrscheinlich nötig; vor der Ankündigung
  `workflow.py status` fragen, nicht aus der Ausschlussliste ableiten.
- **Files:** 9 geändert/neu/gelöscht (3 Quelle, 6 Test/E2E) + 3 unverändert mit Nachweis
- **Effort:** medium
- **Risk Level:** MEDIUM — nicht wegen der Änderung selbst (isolierte Komponente),
  sondern wegen zweier Zusicherungen, die den Umbau überleben müssen: die
  **Kanalzuordnung** (`rule.channels`, einzige Schreibstelle `alertChannels.ts:24-33`)
  und die Zusicherung **„es wird keine Regel aus `trip.alert_rules` gelöscht"** (sonst
  kann das Prüf-Gate `has_active_rules` kippen und Trips werden still übersprungen).

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | MODIFY | Modus-Radiogroup (`:140-159`), `editMode`-State (`:41`), `$effect`-Guard (`:62-70`), `deltaOnlyHint` (`:57-60,161-165`), `draftAbsThreshold` (`:46`) und `.mode-selector`/`.delta-only-hint`-CSS entfallen; die drei Modus-Zweige (`:177-233`) kollabieren auf den Δ-Zweig; Speichern-Label fest „Speichern". **Kanal-Chip-Block (`:235-242`), Metrik-Select, Aktiv-Checkbox bleiben unberührt.** |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | DELETE | Einziger Importeur ist `AlertRuleRow.svelte:20` (nachgemessen) |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | MODIFY | `expandRules()` (`:56-108`) kollabiert auf den Δ-Zweig und liefert immer genau **eine** Regel; `AlertRuleMode` entfällt; `newDefaultRule()` liefert eine Änderungsregel (Annahme 2). **`DELTA_ONLY_METRICS` bleibt exportiert.** |
| `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` | MODIFY | **CI-Ampel-relevant** (`.github/ci_e2e_specs.txt:213`, `e2e`-Check). Wird **in place** vom Sperr-Wächter zum Abwesenheits-Wächter; enthält zusätzlich die Browser-Nachweise für AC-2, AC-3, AC-5, AC-7 |
| `frontend/e2e/alert-rules-editor.spec.ts` | MODIFY | `describe` „Issue #297 — mode=both" (`:298ff`) und „AC-4 ModeCard Badge" (`:396-420`) sind gegenstandslos — löschen |
| `frontend/e2e/issue-284-alert-rules-restyle.spec.ts` | MODIFY | Testfall AC-5 (`:263-290`) greift auf `mode-card-absolute-selected` — gegenstandslos, löschen |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | MODIFY | ~15 Modus-Testfälle auf den einen verbleibenden Zweig **umschreiben, nicht löschen** (sonst bleibt `expandRules()` genau beim Umbau ohne Abdeckung) |
| `frontend/src/lib/components/alert-rules-editor/__tests__/deltaOnlyMetricsAbsolutGesperrt.test.ts` | DELETE | Wird gegenstandslos (ruft `expandRules(..., 'absolute', ...)`) |
| `frontend/src/lib/components/alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts` | CREATE | Ersatz: Bausteinnachweis für AC-2 („keine Regel geht verloren", `channels` überlebt) und AC-7 (`newDefaultRule`) über alle Metriken; importiert die produktive Metrikliste, keine Kopie |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.test.ts` | UNCHANGED | Zusätzlicher Grün-Nachweis für die reinen Funktionen; **nie alleiniger** AC-3-Nachweis (s. AC-3) |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | UNCHANGED | Kein Modus-Bezug (`editMode`/`expandRules`/`ModeCard` → 0 Treffer, nachgemessen) |
| `frontend/e2e/helpers.ts` | UNCHANGED | `:352` nutzt `alert-rule-threshold` — diese testid trägt der überlebende Δ-Zweig |

`.github/ci_e2e_specs.txt` bleibt **unverändert** (Zeile 213 bleibt, s. AC-6). Die Löschung
gegenstandsloser Testfälle in `alert-rules-editor.spec.ts` und
`issue-284-alert-rules-restyle.spec.ts` ist unkritisch für die CI-Ratsche: beide Dateien
stehen **nicht** in `ci_e2e_specs.txt` (nachgemessen), die Zähl-Schwellen
(`E2E_MIN_SPECS`, `E2E_MIN_EXECUTED_HAUPT`) bleiben unberührt.

**Zählung gegenüber dem Kontextdokument** (dort: 11 Dateien = 3 Quelle + 6 Test/E2E + 2
unverändert): Diese Spec zählt 9 geänderte/neue/gelöschte Dateien plus 3 unverändert mit
Nachweis = 12 Zeilen. Abweichung, weil der Ersatz des Sperr-Tests hier als DELETE + CREATE
geführt wird (`deltaOnlyMetricsAbsolutGesperrt.test.ts` weg, `alertRegelNurAenderung.test.ts`
neu; im Kontextdokument eine Zeile „REPLACE") und `helpers.ts` als dritte unveränderte
Datei mit Nachweis gelistet ist. Inhaltlich derselbe Umfang.

### Estimated Changes

- Files: 9 (3 Quelle, 6 Test/E2E) plus 3 unverändert mit Nachweis
- LoC: ca. +130 / −250

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alertChannels.ts` (`effectiveAlertChannels`, `toggleAlertChannel`) | Modul | Einzige Schreibstelle von `rule.channels`; wird von `AlertRuleRow.svelte:240` aufgerufen und muss den Umbau überleben |
| `DELTA_ONLY_METRICS` (`alertRuleDefaults.ts:47-52`) | Konstante | **Bleibt exportiert** — weiter benutzt von `alerts-tab/alertMetricTable.ts:151,367` und `alerts-tab/AlertMetricRow.svelte:17` |
| `AlertRulesEditor.svelte` | Komponente | Rahmen mit `bind:rules`; kein eigener API-Call, Persistenz läuft über den umschließenden Trip-Save |
| `TripNewEditor.svelte`, `TripEditView.svelte` | Komponenten | Die zwei Mounts (Downstream), unverändert |
| `src/services/alert_channels.py` (`resolve_alert_channels`) | Python-Modul | Kanal-Union aus `rule.channels` aktiver Regeln (Filter nur `r.enabled`) — Zusicherung, keine Änderung |
| `src/services/trip_alert.py:459-465,895-899` (`has_active_rules`) | Python-Modul | Prüf-Gate, prüft nur `r.enabled`, nie `r.kind` — Zusicherung, keine Änderung |
| ADR-0043 | Architektur-Entscheidung | Empfindlichkeitsstufe ist der einzige Alarm-Regler |
| Präzedenzfall #1371 | Entscheid (PO, 24.07.2026) | Gleiche Linie schon einmal getroffen: Bedienelement entfernen, Datenfeld in Modell und Persistenz erhalten |

## Implementation Details

Technischer Ansatz (Details bewusst knapp, keine Codeblöcke):

1. **Bausteinschicht zuerst.** `expandRules()` reduziert auf einen Zweig: die Eingabe-Regel
   wird zu `kind:'delta'` mit Δ-Schwelle und Zeitfenster; `pair_id` wird entfernt; alle
   übrigen Felder (`id`, `metric`, `enabled`, `channels`, `severity`, `unit`) werden
   unverändert durchgereicht. Es entsteht **immer genau eine** Regel, nie zwei, nie null.
   Die Signatur verliert Modus- und Absolut-Parameter. `DELTA_ONLY_METRICS` bleibt
   unangetastet exportiert.
2. **`newDefaultRule()`** liefert eine Änderungsregel (`kind:'delta'`, Δ-Schwelle 20,
   Zeitfenster `6h`, Metrik `wind_gust`, `enabled:true`) — **Variante A der „Zweiten
   Annahme" oben, vom PO mit der AC-Freigabe zu bestätigen**. Grund: sonst zeigt jede frisch
   hinzugefügte Regel weiter die „Abs"-Kennzeichnung (`AlertRuleRow.svelte:279`) und die
   Edit-Card würde eine Absolut-Zahl (50) als Δ-Schwelle anzeigen. `startEdit()` liest die
   Δ-Schwelle nur aus Regeln mit `kind:'delta'`; für eine Alt-Regel mit `kind:'absolute'`
   (die es auf Platte nicht gibt, s. Known Limitations) gilt der Δ-Standardwert 20.
3. **Komponente gezielt zurückbauen.** Radiogroup und Modus-Zweige entfernen, den Δ-Zweig
   als einzigen Fall stehen lassen. **Die Kanal-Chips stehen zwar außerhalb der
   Modus-Verzweigung (`:235-242`), liegen aber in derselben Edit-Card (`:167-259`).** Wer
   die Card großzügig statt gezielt zurückbaut, verliert die Kanalauswahl — die einzige
   verbleibende Daseinsberechtigung der Regel. Genau davor schützt AC-3.
4. **`ModeCard.svelte` fällt ersatzlos**, danach den Import in `AlertRuleRow.svelte` und
   die Kopfkommentare (`#179`-Modus-Toggle) nachziehen.
5. **E2E-Ratsche in derselben Lieferung** (AC-6): dieselbe geratschte Spec wird
   umgeschrieben, nicht ersetzt.
6. **Vorlage im Haus:** #1371 (Corridor `notify` — Bedienelement weg, Datenfeld bleibt,
   Read-Modify-Write).

**Testschichten:** Bausteinschicht = `node --test` unter
`frontend/src/lib/components/alert-rules-editor/__tests__/` (**kein Vitest**, kein
Komponenten-Klick: der SSR-Harness erreicht den Bearbeiten-Zustand nicht). Alles, was
die Verdrahtung der `.svelte`-Komponente beweisen muss (Chips, Klick, Speichern), läuft
deshalb im Browser (Playwright, `frontend/e2e/`, Spec auf der CI-Ratsche).

## Expected Behavior

- **Input:** Nutzer öffnet im Reiter „Alerts" (`/trips/new`) bzw. „Alarmregeln" eine Regel
  im Bearbeiten-Modus.
- **Output:** Die Edit-Card zeigt Metrik-Auswahl, Δ-Schwelle, Zeitfenster, Kanal-Chips
  (je aktiver Kanal), „Aktiv", Speichern/Abbrechen. Es gibt keine Modus-Karten, kein
  Absolut-Schwellenfeld, keinen Hinweistext zum Δ-Rückfall. Beim Speichern entsteht genau
  eine Regel mit `kind:'delta'`, alle übrigen Felder bleiben erhalten.
- **Side effects:** keine. Kein API-Aufruf, keine Migration, keine Änderung an bestehenden
  gespeicherten Regeln. Der Server normalisiert weiterhin bei jedem Load/Save (unverändert).

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet im Reiter „Alerts" (bzw. „Alarmregeln") eines Trips
  eine Regel im Bearbeiten-Modus, When er die Edit-Card ansieht, Then gibt es keine
  Modus-Auswahl mehr: weder Modus-Karten (`mode-card-*`) noch die Gruppe „Alarm-Modus" noch
  einen Hinweistext zum Δ-Rückfall — und die Card zeigt weiterhin Metrik-Auswahl, Δ-Schwelle
  (`alert-rule-threshold`) und Zeitfenster (`alert-rule-delta-window`).
  - Test (E2E, `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`, echter Browser,
    `/trips/new` → „Alerts"): nach `alert-rule-edit-btn` ist `alert-rule-edit` sichtbar, die
    Zahl der Modus-Karten (beide testid-Varianten) ist 0, die Gruppe „Alarm-Modus" fehlt,
    `alert-rule-threshold` und `alert-rule-delta-window` sind je genau einmal sichtbar. Das
    gilt für Böen und nach Metrik-Wechsel für Gewitter (keine „MITTEL"/„HOCH"-Optionen) und
    „Temperatur (Änderung)". Die Anti-Vakuum-Prüfungen bleiben erhalten:
    `expect(editor).toBeVisible()` in `openNewTripAlerts()` und `expect(edit).toBeVisible()`
    in `openFirstRuleEditor()` — ohne sie hieße „keine Modus-Karte" bloß „kein DOM".
    **Nicht gemeint:** der Reiter „Alarme" (`AlarmeScheduleTab`).

- **AC-2:** Given ein Trip mit einer oder mehreren Alarmregeln, When der Nutzer eine Regel
  im Editor bearbeitet und speichert, Then bleibt die Regel in der Regelliste erhalten
  (es wird keine Regel aus `trip.alert_rules` gelöscht und keine zusätzliche erzeugt),
  ihre `id`, `metric`, `enabled` und `channels` sind unverändert, und `kind` ist `delta`.
  Die Zusicherung lautet ausdrücklich „keine Regel geht verloren" und **nicht** „das
  Prüf-Gate `has_active_rules` kippt nicht" — das Gate prüft nur `r.enabled`, nie `r.kind`.
  - Test (Bausteinschicht, `__tests__/alertRegelNurAenderung.test.ts`): für **jede** Metrik
    der produktiven Metrikliste liefert `expandRules()` genau eine Regel mit unveränderter
    `id`, `metric`, `enabled` (sowohl `true` als auch `false`), `channels` (explizit
    gesetzt und leer/fehlend), `kind:'delta'` und ohne `pair_id`. Positivkontrolle: eine
    Regel mit `pair_id` verliert dieses Feld, behält aber alles andere.
  - Test (E2E, dieselbe Spec): Regel hinzufügen → bearbeiten → speichern; danach ist genau
    eine `alert-rule-row` sichtbar (nicht null, nicht zwei) mit der gewählten Metrik und
    gesetztem „Aktiv"-Haken.

- **AC-3:** Given ein Nutzer bearbeitet eine Regel bei aktiven Kanälen E-Mail und Telegram,
  When er die Edit-Card öffnet, einen Kanal-Chip umschaltet und speichert, Then werden die
  Kanal-Chips weiterhin an der produktiven Komponente gerendert, das Umschalten erreicht
  `toggleAlertChannel`, und der geänderte Kanalbestand steht nach dem Speichern in
  `rule.channels` (sichtbar in Ansichtszeile und erneut geöffneter Edit-Card).
  - Test (E2E, `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`, **Hauptnachweis**,
    misst die Zusicherung an der `.svelte`-Komponente): `alert-rule-channel-email` und
    `alert-rule-channel-telegram` sind sichtbar mit `aria-pressed="true"`,
    `alert-rule-channel-sms` fehlt (Standardkanäle in `/trips/new` sind E-Mail und
    Telegram); Klick auf Telegram setzt `aria-pressed="false"`, E-Mail bleibt `"true"`;
    nach „Speichern" zeigt die Ansichtszeile nur den Chip „E-Mail"; erneutes Öffnen der
    Edit-Card zeigt Telegram weiter `"false"`. Fiele der Chip-Block aus der Komponente,
    würde dieser Test rot.
  - Test (Bausteinschicht, `alertRegelNurAenderung.test.ts`): `expandRules()` reicht
    `channels` unverändert durch (Regel mit `channels:['sms']` bleibt `['sms']`).
  - **Kein Datenbank-Roundtrip:** „nach dem Speichern" meint den Speicher-Klick im Editor
    (`onSave` → `bind:rules` im Arbeitsspeicher; `AlertRulesEditor` macht keinen eigenen
    API-Aufruf). Die Persistenz (Trip-Save, `SyncAlertRules`) ist von dieser Lieferung
    unverändert; der Nachweis ist der Roundtrip **im Editor** (Ansichtszeile und erneut
    geöffnete Edit-Card), nicht ein `GET /api/trips/{id}`.
  - `alertChannels.test.ts` darf als **zusätzlicher** Grün-Nachweis genannt werden, ist aber
    **nicht** der Nachweis: er prüft nur die reinen Funktionen in `alertChannels.ts`, der
    Umbau berührt `AlertRuleRow.svelte` und `alertRuleDefaults.ts` — der Test bliebe grün,
    selbst wenn der Chip-Block komplett aus der Komponente fiele (Vakuum-Test).

- **AC-4:** Given der Ortsvergleich (Alarm-Konfiguration eines Vergleichs, Komponente
  `shared/AlarmeTab.svelte`), When dieser Umbau ausgeliefert ist, Then ist der Ortsvergleich
  unverändert: sein Verhalten und seine Dateien bleiben gleich, denn `AlertRulesEditor` hat
  **null** Importeure im Ortsvergleich. Das ist **kein Verstoß** gegen die
  Trip/Ortsvergleich-Teilungs-Konvention: es gibt kein Compare-Pendant, das geklont würde —
  der Ortsvergleich nutzt für Alarme die inhaltlich andere, bereits geteilte
  Empfindlichkeitsstufen-Fläche und hat serverseitig keine eigenen Alarmregeln.
  - **Nachweis = strukturelle Invariante, kein Verhaltenstest** (Adversary/Validator, kein
    Testcode): der Diff dieser Lieferung enthält keine Datei unter
    `frontend/src/lib/components/compare/`, `frontend/src/lib/components/shared/`,
    `internal/`, `src/` oder `api/` (Prüfung per `git diff --name-only` gegen `origin/main`).
    Es gibt keinen Berührungspunkt zwischen Umbau und Ortsvergleich, deshalb kann kein Test
    hier rot werden — ein Verhaltenstest wäre ein Vakuum-Test und wird nicht als Nachweis
    ausgegeben.
  - **Regressionsnetz, kein Nachweis:** die bestehende, geratschte Spec
    `frontend/e2e/compare-alarme-speichert-selbst.spec.ts` (`.github/ci_e2e_specs.txt:195`)
    läuft unverändert grün.

- **AC-5:** Given eine Regel im Bearbeiten-Modus, When der Nutzer nacheinander jede
  wählbare Metrik einstellt (auch solche, für die das Absolut-Feld bisher im Modus
  „Beides" sichtbar blieb und der eingetippte Wert beim Speichern verworfen wurde), Then
  existiert die testid `alert-rule-threshold-abs` für keine Metrik im DOM.
  - Test (E2E, `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`): Schleife über alle
    Optionen des Metrik-Selects `alert-rule-metric` (Werte aus dem DOM gelesen, nicht
    abgeschrieben); je Metrik ist `alert-rule-threshold-abs` 0-mal vorhanden und
    `alert-rule-threshold` 1-mal (Anti-Vakuum: die Schleife beweist, dass die Card pro
    Metrik tatsächlich gerendert wurde, und die Schleife lief über mindestens 9 Optionen).

- **AC-6:** Given die geratschte Spec `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`
  (`.github/ci_e2e_specs.txt:213`, läuft im `e2e`-Check der CI-Ampel), When der Umbau
  ausgeliefert wird, Then ist diese Spec im selben PR **in place** vom Sperr-Wächter zum
  Abwesenheits-Wächter umgeschrieben, der Ratschen-Eintrag Zeile 213 bleibt bestehen, und
  die gegenstandslosen Testfälle in den ungeratschten Specs `alert-rules-editor.spec.ts`
  und `issue-284-alert-rules-restyle.spec.ts` sind entfernt.
  - Test (CI-Ampel + Rückdreh-Gegenprobe): der `e2e`-Check ist auf dem letzten Stand grün,
    und die Zeile `e2e/gewitter-absolutregel-gesperrt.spec.ts` steht weiterhin in
    `.github/ci_e2e_specs.txt`. Mutations-Gegenprobe (Pflicht, per String-Ersetzung mit
    externer Sicherungskopie, nie `git checkout/stash/reset`): eine wieder eingebaute
    `ModeCard` in `AlertRuleRow.svelte` und ein wieder eingebautes
    `alert-rule-threshold-abs` machen die geratschte Spec **rot**. Ratsche leeren wäre das
    Muster „Ratsche leeren macht den abhängigen Test vakuum-grün" — deshalb bleibt der
    Eintrag, und der Dateiname wird nicht geändert.

- **AC-7:** Given der Nutzer klickt im Editor „+ Regel hinzufügen", When die neue Zeile
  erscheint, Then trägt sie die Änderungs-Kennzeichnung „Δ" (nicht „Abs"), und ihr
  Bearbeiten-Formular zeigt eine Δ-Schwelle von 20 mit Zeitfenster „6 Stunden" (Variante A
  der zweiten Annahme, vom PO mit der AC-Freigabe zu bestätigen oder auf 50 zu ändern).
  - Test (Bausteinschicht, `alertRegelNurAenderung.test.ts`): `newDefaultRule()` liefert
    `kind:'delta'`, `threshold` 20, `delta_window` `'6h'`, `metric` `'wind_gust'`,
    `enabled:true`.
  - Test (E2E, dieselbe Spec wie AC-1): nach „+ Regel hinzufügen" enthält die Pille der
    `alert-rule-row` „Δ" und nicht „Abs"; nach dem Öffnen des Formulars hat
    `alert-rule-threshold` den Wert 20 und `alert-rule-delta-window` den Wert `6h`.

## Nicht-Ziele

- **`internal/model/trip.go` (`SyncAlertRules`), `internal/store/trip.go`,
  `src/services/alert_channels.py`, `src/services/trip_alert.py` werden nicht angefasst.**
- **Keine Migration, kein Schema-Rework, keine Bestandsdaten-Änderung.**
- **Die Regel-Entität wird nicht abgeschafft, `has_active_rules` nicht ersetzt.**
- **Δ-Schwelle und Zeitfenster bleiben sichtbar** (s. Annahme 1).
- **Abweichung vom Ticket (bewusst):** Die PO-Fundstellentabelle listet
  `frontend/src/lib/components/alerts-tab/AlertMetricRow.svelte` und `alertMetricTable.ts`
  als „Anzeigeseite". Nachgemessen sind die beiden **Svelte-Komponenten**
  (`AlertMetricRow.svelte`, `AlertMetricTable.svelte`) toter Code: 0 Importeure außerhalb
  des eigenen Ordners. Das Modul `alertMetricTable.ts` ist dagegen **lebendig** (sein Export
  `ALERTABLE_METRICS` speist `shared/alarme-tab/tripAlertMetricsFromCatalog.ts:11` und
  `activeAlertMetricsFromCatalog.ts:6`). **Entscheidung dieser Spec: nicht anfassen** —
  Löschen wäre eine Zuschnitt-Erweiterung. Der tote Zweig trägt weiter eigenes
  „Absolut"-Vokabular; er ist als Nebenbefund für das Sammel-Issue #1199 vorzumerken.
- **`DELTA_ONLY_METRICS` in `alertRuleDefaults.ts` bleibt exportiert** — weiter benutzt von
  `alerts-tab/alertMetricTable.ts:151,367` und `alerts-tab/AlertMetricRow.svelte:17`.
- **Schritt 2 ist nicht Teil dieser Lieferung:** Kanalzuordnung als eigenes Feld je
  Metrik, zusammen mit #1230 (zurückgestellt).

## Known Limitations

- **Randfall, der nicht von diesem Umbau stammt:** `SyncAlertRules` löscht eine Regel
  bereits heute, wenn ihre Metrik in `display_config` nicht aktiv ist
  (`internal/model/trip.go:365-406`). Hing die abweichende Kanalzuordnung einer Metrik
  ausschließlich an einer solchen Regel, geht sie serverseitig verloren. Dieser Pfad
  existiert unverändert und wird von Schritt 1 weder ausgelöst noch verschlimmert; er ist
  hier festgehalten, damit er später nicht diesem Umbau zugeschrieben wird.
- Auf Platte gibt es strukturell keine `kind='absolute'`-Regeln (`SyncAlertRules` setzt bei
  jedem Load/Save `Kind = delta`; 0 Treffer in `data/users/` und den Fixtures). Eine
  Alt-Regel mit `kind:'absolute'` kann daher nur im Speicher entstehen; die Kennzeichnungs-
  Pille in der Ansichtszeile (`rule.kind === 'delta' ? 'Δ' : 'Abs'`) bleibt deshalb
  unverändert im Code, wird aber nach AC-7 nie mehr „Abs" zeigen.
- Δ-Schwelle und Zeitfenster lösen ebenfalls keinen Alarm aus (ADR-0043) — Schritt 2.
- `frontend/e2e/helpers.ts:353` nutzt die testid `alert-rule-severity`, die seit #687 nicht
  mehr im Editor existiert; der zugehörige Helper-Zweig ist von keiner Spec benutzt.
  Nebenbefund, kein Bestandteil dieser Lieferung (Sammel-Issue #1199).
- `TripEditView.svelte` (Reiter „Alarmregeln") hat im produktiven Frontend keinen
  Importeur; der Umbau wirkt dort mit, ist aber nur am Mount `TripNewEditor` im Browser
  messbar.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (einschlägig: ADR-0043)
- **Rationale:** ADR-0043 („Empfindlichkeitsstufe ist der einzige Alarm-Regler") hat den
  Absolut-Modus funktional entwertet, ihn aber nicht als Bedienkonzept abgeschafft. Dieser
  Schritt vollzieht das in der Bedienfläche nach und ändert weder ADR-0043 noch ein
  Datenmodell noch die Persistenz. Kein neuer Entscheidungsraum: die PO-Entscheidung vom
  2026-08-19 im Issue #1895 und der Präzedenzfall #1371 (Bedienelement entfernen,
  Datenfeld erhalten) decken das ab.

## Changelog

- 2026-09-21: Initial spec created (spec-writer, Workflow `fix-1895-alarm-absolut-modus`)
