---
entity_id: fix_1895_s2_alarmkarte_rueckbau
type: module
created: 2026-09-21
updated: 2026-09-21
status: draft
version: "1.0"
workflow: fix-1895-s2-alarmkarte-rueckbau
tags: [alarm-regeln, delta-schwelle, zeitfenster, rueckbau, frontend, trip-new]
---

# #1895 Schritt 2 — Δ-Schwelle, Zeitfenster und Wert-Anzeige von der Alarmregel-Karte zurückbauen

## Approval

- [ ] Approved

## Purpose

Die Alarmregel-Karte im Trip-Editor zeigt zwei Eingaben, die keinen Alarm auslösen: die
Δ-Schwelle und das Zeitfenster. Auf der Ansichtskarte steht zusätzlich der dazugehörige
Wert („> 20 km/h") samt einer Pille mit dem Zeichen „Δ". Der Alarm-Auslöser
(`deviation_alert_engine._select_detector()`) speist sich ausschließlich aus den
Empfindlichkeitsstufen (`metric_alert_levels`, ADR-0043); `trip.alert_rules` wird dort nie
gelesen, und `_trip_channel_inputs()` liest von der Regel nur `enabled` und `channels`.
Die Karte verspricht also einen Regler, den es nicht gibt — derselbe Befund wie beim
Absolut-Modus aus Schritt 1 (live seit `a928dbce`, PR #2393).

Dieser Schritt nimmt Δ-Schwelle, Zeitfenster, Wert-Text **und** die „Δ"-Pille aus **beiden**
Ansichten der Karte (Bearbeiten und Ansicht). Übrig bleibt: **Metrik · Kanäle · aktiv**.
Die Datenfelder `threshold` und `delta_window` bleiben im Modell und in der Persistenz
unberührt (Präzedenzfall #1371: Bedienelement weg, Datenfeld bleibt) und werden beim
Speichern **unverändert durchgereicht**. PO-Entscheid vom 2026-09-21 (Variante A).

**Frontend-only.** Kein Go, kein Python, kein Schema, keine Migration.

## Source

- **File:** `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte`
- **Identifier:** Komponente `AlertRuleRow` (Bearbeiten- und Ansichtskarte) und
  `expandRules()` in `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts`

> Schicht: **Frontend / User-UI** (`frontend/src/lib/components/alert-rules-editor/`,
> SvelteKit). Keine Datei unter `internal/`, `cmd/`, `src/`, `api/` wird angefasst.

### Welche Fläche gemeint ist (präzise, nachgemessen 2026-09-21)

`AlertRulesEditor` (und damit `AlertRuleRow`) hat genau zwei Mounts, beide Trip:
`TripNewEditor.svelte` (Zeilen 862 und 1102, Reiter „Alerts" auf `/trips/new`) und
`TripEditView.svelte:205`. Letzterer hängt hinter `/trips/<id>/edit`, das seit 2026-06-07 auf
`redirect(307)` steht (#616) — der **einzige im Browser erreichbare Mount ist `/trips/new`**.
**Nicht gemeint** ist der Reiter „Alarme" (`AlarmeScheduleTab`, Empfindlichkeitsstufen).

**Ortsvergleich: null Mounts.** `AlertRulesEditor`/`AlertRuleRow` haben unter `shared/`,
`compare/` und `routes/` keinen Treffer; der Ortsvergleich nutzt `shared/AlarmeTab.svelte`
und kennt serverseitig keine Alarmregeln. Es gibt kein Compare-Pendant, das nachzuziehen
wäre — das ist **geprüft** (AC-8), keine Lücke.

## Entscheidungen (in der Analyse getroffen — hier zur Freigabe sichtbar)

- **E-1 — Die „Δ"-Pille fällt mit.** Seit Schritt 1 zeigt sie auf jeder Zeile konstant „Δ"
  (der „Abs"-Zweig ist unerreichbar, der Go-Store normalisiert jede Regel auf `delta`) und
  unterscheidet nichts. Ihr einziger Sinn war, den danebenstehenden Schwellenwert zu
  beschriften; fällt der Wert, beschriftet sie nichts. Nutzersichtbar, daher eigenes AC (AC-2).
- **E-2 — `expandRules(rule)` reicht `threshold` und `delta_window` durch.** Heute steht in
  der Signatur `deltaWindow: string = '6h'` — eine harte Konstante, die nie erreicht wird,
  weil `saveEdit()` immer explizit übergibt. Fällt die Eingabe weg, wird aus diesem toten
  Default der einzige Pfad, und der erste Speichervorgang schreibt jede Bestandsregel mit
  z. B. `delta_window: '12h'` still auf `'6h'` um (Klasse BUG-DATALOSS-GR221, Verstoß gegen
  „Read-Modify-Write, kein Replace" aus AC-2 von Schritt 1). Darum: `rule.threshold` und
  `rule.delta_window ?? '6h'`; der Rückfall `'6h'` gilt nur für Regeln **ohne** Zeitfenster.
  `expandRules()` hat genau eine produktive Aufrufstelle (`AlertRuleRow.svelte:92`), die
  Signatur lässt sich gefahrlos kürzen.
- **E-3 — Die `kind !== 'delta'`-Vorbelegung in `startEdit()` (`AlertRuleRow.svelte:67-81`)
  fällt ersatzlos.** `threshold` wird unverändert durchgereicht. Begründung und Restfolge:
  siehe Known Limitations („E-3 mit Messung").
- **`newDefaultRule()` bleibt unverändert** und schreibt weiter `threshold: 20`,
  `delta_window: '6h'` (Bestand aus Schritt 1, AC-7 dort). Zwei verschiedene Dinge, die
  nicht verschmelzen dürfen: neue Regel = Vorgabewerte, Bestandsregel beim Speichern =
  Durchreichen.

## Estimated Scope

- **LoC:** produktiv ca. −50 / +10 (2 Dateien), Tests zusätzlich; deutlich unter 250 — kein
  `loc_limit_override` nötig
- **Files:** 6 geändert (2 produktiv, 3 Test/E2E, 1 Doku) + 2 unverändert mit Nachweis
  (`alertChannels.test.ts` als Wächter, `.github/ci_e2e_specs.txt`)
- **Effort:** low
- **Risk Level:** MEDIUM — nicht wegen des Umfangs, sondern wegen E-2: die Änderung berührt
  den **Schreibweg auf Bestandsdaten**, und das Feld ist nach dem Rückbau nirgends mehr
  sichtbar, ein Fehler wäre unsichtbar.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | MODIFY | Bearbeiten-Karte: `alert-rule-threshold` (`:122-128`) und `alert-rule-delta-window` (`:129-140`) raus; `draftDeltaThreshold`/`draftDeltaWindow` (`:45-46`) und die `kind`-Vorbelegung in `startEdit()` (`:69-79`) fallen (E-3); `saveEdit()` ruft `expandRules(synced)` mit einem Argument. Ansichtskarte: `valueText` (`:52`), `<span class="threshold">` (`:183`) und die `<Pill>` (`:184-186`) raus (E-1); zugehörige CSS-Regeln `.threshold`, `.number-input`, `.window-select` und der nicht mehr genutzte `Pill`-Import fallen mit. Grid `.alert-rule-view`: `grid-template-columns` von 6 auf 4 Tracks (siehe „Layout"). **Metrik-Select, Kanal-Chip-Block (`:142-149`), Aktiv-Checkbox, Speichern/Abbrechen bleiben unberührt.** |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | MODIFY | `expandRules(rule)` — Parameter `deltaThreshold`/`deltaWindow` entfallen, `threshold: rule.threshold`, `delta_window: rule.delta_window ?? '6h'` (E-2); Kopfkommentar nachziehen. `newDefaultRule()` und `DELTA_ONLY_METRICS` **unverändert**. |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | MODIFY | Fünf Fälle drehen sich um oder werden gegenstandslos, drei Aufrufe verlieren mechanisch ihre Zusatzargumente (Tabelle unten). |
| `frontend/src/lib/components/alert-rules-editor/__tests__/alertRegelNurAenderung.test.ts` | MODIFY | Alle `expandRules(x, 20, '6h')`-Aufrufe verlieren ihre Argumente; Fall `:133-140` auf das Durchreichen umgestellt; neuer Fall „Bestandszeitfenster überlebt" (AC-3, AC-7). `newDefaultRule()`-Fall `:49-58` bleibt unverändert. |
| `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` | MODIFY | **CI-Ampel-relevant** (`.github/ci_e2e_specs.txt:246`, `e2e`-Check). Wird **in place umgeschrieben, nicht umbenannt** (AC-1, AC-2, AC-5, AC-6, AC-7). |
| `docs/reference/frontend_components.md` | MODIFY | Abschnitt „Alert-Rules-Editor" (`:665-681`) nachziehen: Karte zeigt nur Metrik · Kanäle · aktiv; `expandRules()` reicht `threshold`/`delta_window` durch (AC-9). `tests/tdd/test_issue_316_docs_cleanup.py` (Zeile 44 erwartet `AlertRuleRow` im Dokument) hängt daran. |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.test.ts` | UNCHANGED | **Muss grün bleiben, nicht anfassen.** Wächter dafür, dass die Kanalzuordnung (einzige verbliebene Wirkung der Regel) den Umbau überlebt — als **Zusatz**nachweis, nicht als alleiniger (siehe AC-5). |
| `.github/ci_e2e_specs.txt` | UNCHANGED | Zeile 246 bleibt stehen; **kein Ratschen-Edit** (AC-6). |

**Nicht angefasst:** Go-Store, Python-Loader, `frontend/src/lib/types.ts` (`delta_window`
bleibt im Datenmodell); `shared/`, `compare/` (AC-8); `AlertRulesEditor.svelte`;
`pairFollower`/`pair-indicator` (seit Schritt 1 unerreichbar) und
`frontend/e2e/helpers.ts:343-355` (`fillStep4`, toter Helfer des abgeschafften Wizards, #622)
— beides Sammel-Einträge für **#1199** (Nebenbefund-Triage).

**Weitere E2E-Specs mit Bezug zu den entfallenden Elementen — bewusst nicht angefasst:**
`alert-rules-editor.spec.ts` (`:172`, `:201`, `:176`, `:204`), `issue-284-alert-rules-restyle.spec.ts`
(`:282-287`, `.threshold`-Schriftart) und `issue-687-alert-editor-soll-ist.spec.ts`
(`:92-107`, Pille „Abs"). Alle drei stehen **nicht** in `.github/ci_e2e_specs.txt`
(nachgemessen) und fahren `/trips/<id>/edit`, das auf `redirect(307)` steht — sie messen
heute schon nichts. Die Lieferung ändert daran nichts; Sammel-Eintrag für **#1199**.

### Estimated Changes

- Files: 6 (2 produktiv, 3 Test/E2E, 1 Doku) plus 2 unverändert mit Nachweis
- LoC: produktiv ca. −50 / +10; Tests ca. −40 / +70

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `alertChannels.ts` (`effectiveAlertChannels`, `toggleAlertChannel`) | Modul | Einzige Schreibstelle von `rule.channels`; wird von `AlertRuleRow.svelte` aufgerufen und muss den Umbau überleben |
| `alertMetricLabels.ts` (`ALERT_METRIC_LABELS`) | Modul | Metrik-Beschriftung; `info.comparison`/`info.unit` werden auf dieser Fläche nicht mehr gelesen |
| `$lib/types` (`AlertRule`) | Typ | `threshold`/`delta_window` bleiben im Typ (Datenmodell unberührt) |
| `AlertRulesEditor.svelte` | Komponente | Rahmen mit `bind:rules`, unverändert; kein eigener API-Call, Persistenz läuft über den Trip-Save |
| `TripNewEditor.svelte` | Komponente | Der einzige im Browser erreichbare Mount (Downstream), unverändert |
| `src/services/deviation_alert_engine.py` (`_select_detector`), `src/services/alert_channels.py` (`_trip_channel_inputs`) | Python-Module | Belegen, dass `threshold`/`delta_window` nichts auslösen — Zusicherung, keine Änderung |
| `internal/model/trip.go` (`SyncAlertRules`), `internal/store/trip.go` | Go-Module | Normalisieren `Kind` bei Load und Save — Begründung für E-3, keine Änderung |
| `.github/workflows/ci.yml` (`svelte-check`, `BASELINE_ERRORS: 36`) | CI-Check | Wächter für die Signaturkürzung (AC-4) |
| ADR-0043 | Architektur-Entscheidung | Empfindlichkeitsstufe ist der einzige Alarm-Regler |
| Präzedenzfall #1371 und Schritt 1 (`fix_1895_alarm_modus_rueckbau.md`) | Entscheid / Spec | Gleiche Linie: Bedienelement entfernen, Datenfeld erhalten, Read-Modify-Write |

## Implementation Details

Reihenfolge ist Teil der Zusicherung (keine Codeblöcke, Details in den Dateien):

1. **`expandRules()` zuerst (E-2).** Das Durchreichen muss stehen, bevor die Eingabe fällt —
   sonst gibt es einen Zwischenstand, in dem `saveEdit()` schon ohne Argumente ruft und die
   Konstante `'6h'` greift. Die Signatur verliert beide Parameter; `pair_id` wird weiter
   entfernt, alle übrigen Felder bleiben unverändert.
2. **`AlertRuleRow.svelte`:** erst die Bearbeiten-Karte räumen, dann die Ansichtskarte (E-1),
   zuletzt CSS und Grid. `saveEdit()` ruft `expandRules(synced)`.
3. **Bestandstests umdrehen, E2E-Spec umschreiben.**
4. **Doku nachziehen** (Lieferpflicht, Nachweis siehe AC-9).

### Layout (CSS-Satz, kein AC)

`.alert-rule-view` definiert heute 6 Grid-Tracks; Kinder heute: Label · Schwelle · Pille ·
N Kanal-Chips · Checkbox · Kebab = 5 + N. Nach dem Rückbau: 3 + N. Die Tracks werden
**exakt um die zwei entfallenen reduziert (6 → 4)**. Der bekannte Überlauf ab zwei Kanälen
(Kinder > Tracks) bleibt unverändert Bestand und bleibt in **#1199** gebucht; ihn hier zu
heilen (5 Tracks oder `flex-wrap`) wäre Scope-Creep.

### Bestandstests, die sich umdrehen (benannt, damit sie nicht als Regression gelesen werden)

Diese Tests waren korrekt, solange `expandRules()` Parameter hatte. Sie zu ändern ist Teil
der Lieferung:

| Test | Sichert heute zu | Nach Schritt 2 |
|---|---|---|
| `alertRuleDefaults.test.ts:119-124` | `expandRules(rule mit '12h')` **ohne** Argumente → `'6h'` („Signatur-Vorgabewert ist die Konstante 6h") | umgekehrt: → `'12h'` (`threshold` 17 unverändert) |
| `alertRegelNurAenderung.test.ts:133-140` | `expandRules(rule)` ohne Argumente → `delta_window === '6h'` | Eingangsregel bekommt ein eigenes Fenster; Erwartung: das Fenster der Regel; `'6h'` nur für eine Regel ohne Fenster |
| `alertRuleDefaults.test.ts:104-115` (F005) | ein Regel-Zeitfenster „überstimmt den Parameter nicht" | **gegenstandslos** — es gibt keinen Parameter mehr; ersetzt durch „das Fenster der Regel wird durchgereicht" |
| `alertRuleDefaults.test.ts:88-94` | „der übergebene Δ-Wert gewinnt gegen `rule.threshold`" (Schwelle 30 aus dem Argument, Regel trägt 50) | umgekehrt: `rule.threshold` (50) wird unverändert durchgereicht — das ist E-3 als Test |
| `alertRuleDefaults.test.ts:96-102` | „das übergebene Zeitfenster wird durchgereicht" (`'3h'` aus dem Argument) | das Fenster **der Regel** (`delta_window: '3h'`) wird durchgereicht |

Zusätzlich verlieren die Aufrufe `alertRuleDefaults.test.ts:77`, `:141`, `:175` und alle
Aufrufe in `alertRegelNurAenderung.test.ts` ihre Zusatzargumente. Das ist nicht nur
Kosmetik: bliebe ein Aufruf mit drei Argumenten stehen, wäre das **TS2554** (siehe AC-4).
Die letzten beiden Fälle (`:88-94`, `:96-102`) stehen **nicht** in der Analyse-Tabelle; sie
wurden beim Schreiben dieser Spec gefunden und gehören zur selben Klasse.

### Nachweisebene — warum Bausteinebene plus Signatur die **einzig mögliche** ist

Die Analyse verlangte eine Staging-Browser-Strecke „Bestandsregel mit Zeitfenster ≠ 6h
bearbeiten, speichern, neu laden". **Diese Strecke ist strukturell unmöglich** und steht
deshalb bewusst **nicht** als AC:

1. Einziger erreichbarer Mount ist `/trips/new`; `/trips/<id>/edit` steht seit 2026-06-07 auf
   `redirect(307)` (#616). Eine **Bestandsregel** ist im Browser gar nicht erreichbar.
2. Auf `/trips/new` entstehen Regeln aus `newDefaultRule()` mit `'6h'` — ein Wert ≠ 6h ist
   dort nicht seedbar.
3. Nach dem Rückbau zeigt die Oberfläche `delta_window` **nirgends** mehr an — nicht
   sichtbar, also nicht messbar.

Die Bausteinebene (`expandRules`) plus die Signatur als Wächter in der CI-Ampel ist hier
deshalb die **einzige mögliche** Nachweisebene, nicht die bequeme. Dasselbe gilt für die
20/6h-Zusicherung aus Schritt 1 (AC-7 dort): `gewitter-absolutregel-gesperrt.spec.ts:199-200`
(`toHaveValue('20')`/`toHaveValue('6h')`) verliert sein Subjekt, weil das Feld verschwindet.
Der Nachweis wandert auf die Bausteinebene (`alertRegelNurAenderung.test.ts:53-54`,
`newDefaultRule()` → `threshold` 20, `delta_window` `'6h'`). Das ist **keine Gate-Erosion**,
sondern die unvermeidliche Folge des Rückbaus; die entfallenen E2E-Zeilen sind Absicht, keine
stillschweigend fallengelassene Zusicherung (AC-6).

## Expected Behavior

- **Input:** Nutzer öffnet im Reiter „Alerts" (`/trips/new`) die Alarmregeln, legt eine Regel
  an, bearbeitet sie und speichert.
- **Output:** Ansichtskarte: Metrik-Name · Kanal-Chips · „Aktiv"-Haken · Aktionsmenü — kein
  Zahlenwert, keine Pille. Bearbeiten-Karte: Metrik-Auswahl · Kanal-Chips (je aktiver Kanal)
  · „Aktiv" · Speichern/Abbrechen — keine Δ-Schwelle, kein Zeitfenster. Beim Speichern
  entsteht genau eine Regel mit `kind:'delta'`; `threshold` und `delta_window` sind
  unverändert (nur eine Regel **ohne** Fenster bekommt `'6h'`).
- **Side effects:** keine. Kein API-Aufruf, keine Migration, keine Änderung an gespeicherten
  Regeln. Der Server normalisiert bei Load/Save wie bisher.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer öffnet im Reiter „Alerts" auf `/trips/new` eine Regel im
  Bearbeiten-Modus, When er die Bearbeiten-Karte ansieht, Then gibt es weder eine
  Δ-Schwelle noch ein Zeitfenster, und die Karte zeigt nur Metrik-Auswahl, Kanal-Chips,
  „Aktiv" sowie Speichern und Abbrechen — für jede wählbare Metrik.
  - Test (E2E, `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`, echter Browser,
    `/trips/new` → „Alerts"): `alert-rule-threshold` und `alert-rule-delta-window` sind je
    0-mal vorhanden — **und zusätzlich unabhängig von der testid**: in der Karte gibt es kein
    Eingabefeld vom Typ Zahl (`role=spinbutton`) und kein Element mit Beschriftung
    „Zeitfenster" bzw. „Δ-Schwelle" (sonst würde eine bloße Umbenennung der testid das
    Feld unbemerkt am Leben halten). Schleife über alle Optionen des Metrik-Selects
    `alert-rule-metric` (Werte aus dem DOM gelesen, nicht abgeschrieben; mindestens 9
    Optionen). **Anti-Vakuum:** je Durchlauf `alert-rule-metric` hat den gewählten Wert
    (Karte steht), `alert-rule-channel-email` und `alert-rule-save` sind sichtbar, und
    `openFirstRuleEditor()` prüft weiter `expect(edit).toBeVisible()` — ohne das hieße
    „kein Feld" bloß „kein DOM". Die Zusicherungen aus Schritt 1 (keine `mode-card-*`, keine
    Gruppe „Alarm-Modus", kein `alert-rule-threshold-abs`) bleiben in derselben Spec bestehen.
  - **Mutations-Gegenprobe (Pflicht, per String-Ersetzung mit externer Sicherungskopie, nie
    `git checkout/stash/reset`):** (a) in `AlertRuleRow.svelte` das `<input … data-testid="alert-rule-threshold">`
    wieder einbauen → die Spec wird rot; (b) dasselbe Feld mit **anderer** testid, aber
    weiterhin als Zahlenfeld (`type="number"`) bzw. mit der Beschriftung „Δ-Schwelle"
    wieder einbauen → die Spec wird rot über `spinbutton`/Beschriftung, nicht über die
    testid; (c) das Zeitfenster-`<Select>` wieder einbauen → rot.

- **AC-2:** Given eine Alarmregel steht als Ansichtszeile im Reiter „Alerts", When der Nutzer
  die Zeile ansieht, Then zeigt sie Metrik-Namen, Kanal-Chips, „Aktiv"-Haken und
  Aktionsmenü, aber keinen Schwellen-Wert („> 20 km/h") und keine Pille mit „Δ".
  - Test (E2E, dieselbe Spec): nach „+ Regel hinzufügen" ist `alert-rule-row` sichtbar und
    enthält den Text „Böen"; die Zeile hat kein Kind mit Klasse `threshold`, kein Element
    `[data-slot="pill"]`, ihr Text enthält weder „Δ" noch „Abs" noch eine Ziffer noch ein
    Vergleichszeichen (`>`, `<`, `≥`) noch „km/h". Dasselbe für „Niederschlag" nach
    Bearbeiten und Speichern (`alert-rule-row` enthält „Niederschlag", statt wie bisher
    `toContainText('Δ')` in `:237` und `:195` — diese beiden Zusicherungen drehen sich
    um). **Anti-Vakuum:** „Böen"/„Niederschlag" und die Kanal-Chips müssen in der Zeile
    stehen, sonst wäre „keine Ziffer" auch von einer leeren Zeile erfüllt.
  - **Mutations-Gegenprobe:** (a) `<span class="threshold">…</span>` wieder einbauen → rot;
    (b) `<Pill>` mit `'Δ'` wieder einbauen → rot; (c) nur `valueText` wieder in die Zeile
    schreiben → rot (Ziffer/„km/h").

- **AC-3:** Given eine Bestandsregel trägt `threshold` und `delta_window` (z. B. `'12h'`),
  When der Editor sie speichert (`expandRules(rule)` mit einem Argument), Then trägt das
  Ergebnis dasselbe `threshold` und dasselbe `delta_window` — die beiden Felder werden
  durchgereicht, nicht auf 20/`'6h'` zurückgesetzt.
  - Test (Bausteinschicht, `alertRuleDefaults.test.ts` und
    `__tests__/alertRegelNurAenderung.test.ts`): `expandRules({...rule, threshold: 17,
    delta_window: '12h'})` → genau eine Regel mit `threshold` 17 und `delta_window` `'12h'`.
    Wiederholt für jedes Element der Fenster-Liste (`1h`, `3h`, `6h`, `12h`, `24h`) und für
    **jede** Metrik der produktiven Metrikliste (importiert, keine Kopie). Ein Fall mit
    `'6h'` allein wäre wertlos: er wird auch von der alten Konstante erfüllt, deshalb muss
    mindestens ein Wert ≠ `'6h'` und mindestens eine Schwelle ≠ 20 im Fixture stehen.
    Rückfall: eine Regel **ohne** `delta_window` bekommt `'6h'` (eine Δ-Regel ohne Fenster
    wäre unvollständig) und behält ihr `threshold`.
  - **Mutations-Gegenprobe:** in `alertRuleDefaults.ts` `delta_window: rule.delta_window ?? '6h'`
    per String-Ersetzung durch `delta_window: '6h'` → die Fälle mit `'12h'`/`'3h'`/`'1h'`/`'24h'`
    werden rot (**welcher** Fall rot wird, ist im Prüfbericht zu benennen, damit kein
    Zufallstreffer zählt); `threshold: rule.threshold` durch `threshold: 20` → die Fälle mit
    Schwelle ≠ 20 werden rot.
  - **Nachweisebene:** Baustein und Signatur (AC-4) sind die einzig mögliche Ebene, s.
    „Nachweisebene". Eine Browser-Strecke ist ausdrücklich **nicht** vorgesehen.

- **AC-4:** Given `saveEdit()` in `AlertRuleRow.svelte` ruft `expandRules(synced)` mit
  genau einem Argument, When irgendein Aufrufer im Frontend noch `deltaThreshold`/
  `deltaWindow` übergibt (Produktivcode oder Test), Then schlägt die Typprüfung mit
  **TS2554** („Expected 1 arguments, but got 3") fehl und der CI-Check `svelte-check` wird rot.
  - Nachweis (CI-Ampel, **kein** Testcode): `AlertRuleRow.svelte` ist `<script lang="ts">`,
    `frontend/tsconfig.json` hat `strict: true`, und `svelte-check` läuft in
    `.github/workflows/ci.yml:121-163` als Baseline-Gate mit `BASELINE_ERRORS: 36` (am
    2026-09-21 nachgemessen). Der Lauf `npx svelte-check --tsconfig ./tsconfig.json` auf dem
    Lieferstand meldet höchstens 36 Fehler. Damit ist „`saveEdit()` übergibt noch ein
    Argument" kein Testloch, sondern ein Übersetzungsfehler.
  - **Mutations-Gegenprobe:** in einer Kopie `saveEdit()` wieder auf
    `expandRules(synced, 20, '6h')` setzen → `svelte-check` meldet einen Fehler mehr als
    vorher (37 statt 36) und der Baseline-Vergleich schlägt an. Restrisiko siehe Known Limitations.

- **AC-5:** Given ein Nutzer bearbeitet eine Regel bei aktiven Kanälen E-Mail und Telegram,
  When er einen Kanal-Chip umschaltet, den „Aktiv"-Haken bedient und speichert, Then bleiben
  Kanal-Chips und „Aktiv" voll funktionsfähig: der geänderte Kanalbestand steht danach in
  der Ansichtszeile und in der erneut geöffneten Bearbeiten-Karte, `enabled` wird
  unverändert durchgereicht, und es bleibt genau eine Regel mit unveränderter `id`.
  - Test (E2E, dieselbe Spec, **Hauptnachweis** — misst die Zusicherung an der
    `.svelte`-Komponente): die zwei bestehenden Fälle aus Schritt 1 bleiben inhaltlich
    erhalten. Kanal-Fall: E-Mail und Telegram `aria-pressed="true"`, SMS fehlt; Klick auf
    Telegram → `"false"`, E-Mail bleibt `"true"`; nach „Speichern" zeigt die Ansichtszeile
    nur den Chip „E-Mail" (`.channel-chip` hat den Text `['E-Mail']`); erneut geöffnet steht
    Telegram auf `"false"`. Speichern-Fall: `enabled` abwählen → speichern → Zeile hat genau
    einen `alert-rule-row`, Haken nicht gesetzt; `<li>`-Handle bleibt `isConnected` (die `id`
    überlebt). Beide Fälle sind schon vor dem Umbau grün und müssen es danach bleiben; ihr
    Biss wird in der Mutations-Gegenprobe gemessen.
  - **Zusatznachweis (nicht alleiniger):** `alertChannels.test.ts` läuft unverändert grün.
    Er prüft nur die reinen Funktionen in `alertChannels.ts` und bliebe grün, selbst wenn der
    Chip-Block komplett aus der Komponente fiele — er ist Wächter, kein Beweis.
  - **Mutations-Gegenprobe:** den `{#each activeChannels as ch}`-Block aus der Bearbeiten-Karte
    entfernen → der Kanal-Fall wird rot (und `alertChannels.test.ts` bleibt grün — genau
    das ist zu bestätigen und im Prüfbericht festzuhalten); den Kanal-Chip-Block der
    Ansichtszeile entfernen → der Kanal-Fall wird rot (Zeile zeigt kein „E-Mail").

- **AC-6:** Given die geratschte Spec `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts`
  (`.github/ci_e2e_specs.txt:246`, läuft im `e2e`-Check der CI-Ampel), When der Umbau
  ausgeliefert wird, Then ist sie im selben PR **in place umgeschrieben und nicht
  umbenannt**, der Ratschen-Eintrag Zeile 246 bleibt unverändert bestehen, und die
  entfallenen Zusicherungen sind bewusst gestrichen statt stillschweigend gelöscht.
  - Test (CI-Ampel + Rückdreh-Gegenprobe): der `e2e`-Check ist auf dem letzten Stand grün,
    und die Zeile `e2e/gewitter-absolutregel-gesperrt.spec.ts` steht weiterhin in
    `.github/ci_e2e_specs.txt`. Die Mutations-Gegenproben aus AC-1, AC-2 und AC-5 werden
    gegen **diese** Datei gefahren — sie ist der Ort, an dem die Zusicherung wirkt. Ratsche
    leeren oder Datei umbenennen wäre das Muster „Ratsche leeren macht den abhängigen Test
    vakuum-grün", deshalb bleibt der Name.
  - **Umgeschrieben werden** (Zeilen der heutigen Fassung): Titel `:101` (nennt „aber
    Δ-Schwelle und Zeitfenster"), `:122-126`, `:141`, `:147`, `:174` (`toHaveCount(1)`/`toBeVisible()`
    auf die beiden entfallenen testids → `toHaveCount(0)`), `:195`/`:237` (`toContainText('Δ')`
    → Abwesenheit), Kopfkommentar `:1-20` und die Beschriftung der `describe`.
  - **Bewusst gestrichen, Nachweis wandert:** `:199-200` (`toHaveValue('20')`/`toHaveValue('6h')`)
    verlieren ihr Subjekt. Die Zusicherung „neue Regel startet mit 20/6h" gilt weiter und
    wird auf Bausteinebene bewacht (AC-7) — die einzig mögliche Ebene, keine Gate-Erosion.

- **AC-7:** Given der Nutzer klickt „+ Regel hinzufügen", When die neue Regel entsteht, Then
  trägt sie weiter die Vorgabewerte Δ-Schwelle 20 und Zeitfenster `'6h'` in den Daten (auch
  wenn beides nirgends mehr angezeigt wird), und die Zeile erscheint ohne Wert und ohne Pille.
  - Test (Bausteinschicht, `__tests__/alertRegelNurAenderung.test.ts:49-58`, **unverändert**):
    `newDefaultRule()` liefert `kind:'delta'`, `threshold` 20, `delta_window` `'6h'`,
    `metric` `'wind_gust'`, `enabled:true`, kein `pair_id`. Ergänzend (AC-3-Fall): eine
    **neue** Regel, die `expandRules()` durchläuft, behält 20/`'6h'`.
  - Test (E2E, dieselbe Spec): nach „+ Regel hinzufügen" ist genau eine `alert-rule-row`
    sichtbar (Anti-Vakuum) und erfüllt AC-2. Der Wert 20/`'6h'` selbst ist im Browser
    **nicht messbar** (Feld existiert nicht mehr) — das ist die Grundlage der Nachweisebene
    oben.
  - **Mutations-Gegenprobe:** `newDefaultRule()` mit `threshold: 50` → Bausteintest rot.

- **AC-8:** Given der Ortsvergleich (Alarm-Konfiguration eines Vergleichs,
  `shared/AlarmeTab.svelte`) und die Backend-Schichten, When dieser Umbau ausgeliefert
  wird, Then sind sie unverändert: `AlertRulesEditor` hat **null** Importeure im
  Ortsvergleich (nachgemessen am 2026-09-21), es gibt kein Compare-Pendant, das geklont
  würde — das ist **kein Verstoß** gegen die Trip/Ortsvergleich-Teilungs-Konvention.
  - **Nachweis = strukturelle Invariante, kein Verhaltenstest** (Adversary/Validator, kein
    Testcode): der Diff dieser Lieferung enthält **keine** Datei unter
    `frontend/src/lib/components/shared/`, `frontend/src/lib/components/compare/`,
    `internal/`, `src/` oder `api/` (Prüfung per `git diff --name-only` gegen `origin/main`).
    Es gibt keinen Berührungspunkt zwischen Umbau und Ortsvergleich, deshalb kann kein Test
    hier rot werden; ein Verhaltenstest wäre ein Vakuum-Test und wird nicht als Nachweis
    ausgegeben.

- **AC-9:** Given die Komponenten-Referenz `docs/reference/frontend_components.md`, When der
  Umbau ausgeliefert wird, Then beschreibt der Abschnitt „Alert-Rules-Editor" die Karte als
  „Metrik · Kanäle · aktiv" (ohne Δ-Schwelle und Zeitfenster) und `expandRules()` als
  durchreichend, und `AlertRuleRow` steht weiter darin.
  - **Nachweis = strukturelle Invariante, kein Testcode** (Adversary/Validator liest
    `docs/reference/frontend_components.md`, Abschnitt „Alert-Rules-Editor"): der Abschnitt
    nennt weder „Δ-Schwelle" noch „Zeitfenster" als Inhalt der Karte und beschreibt
    `expandRules()` als durchreichend.
  - **Zusatznachweis, nicht der Nachweis:** `tests/tdd/test_issue_316_docs_cleanup.py` läuft
    grün. Er verlangt nur, dass `AlertRuleRow` im Dokument steht (Zeile 44), und bliebe auch
    bei unverändertem Abschnitt grün — er ist Drift-Wächter, kein Beweis für den Inhalt.

## Nicht-Ziele

- **Kein Datenmodell-Umbau, keine Migration, kein Backend:** `threshold` und `delta_window`
  bleiben in `types.ts`, im Go-Modell und in der Persistenz.
- **`newDefaultRule()` bleibt unverändert** — es schreibt weiter 20/`'6h'`.
- **Keine Heilung des Grid-Überlaufs** ab zwei Kanälen (#1199).
- **Keine Kanalzuordnung je Metrik.** `resolve_alert_channels()` bildet über alle aktiven
  Regeln die Union der Kanäle, und `_send_alert()` fragt ohne die auslösende Metrik — die
  Kanalwahl an der Regel ist heute keine Zuordnung je Metrik. Das ist Stoff für die
  Varianten B/C im Datenmodell-Zug #1230 (`status:deferred`) und hier ausdrücklich nicht
  angefasst.
- **Kein Aufräumen von `pairFollower`/`pair-indicator` und `helpers.ts:343-355`** (#1199).
- **Die drei ungeratschten Alt-Specs** (`alert-rules-editor.spec.ts`,
  `issue-284-alert-rules-restyle.spec.ts`, `issue-687-alert-editor-soll-ist.spec.ts`) bleiben
  unberührt (s. Affected Files).

## Known Limitations

- **E-3 mit Messung — eine Alt-Regel mit Absolut-Schwelle stünde fortan als Δ-Schwelle in den
  Daten, für immer unsichtbar.** Der Zweig ist nicht erreichbar, weil `SyncAlertRules`
  (`internal/model/trip.go:365`) bei **Load und Save** ausgeführt wird
  (`internal/store/trip.go:212` und `:253`) und jede Regel auf `Kind = delta` normalisiert;
  eine Absolut-Regel bekommt dabei sogar den Standard-Δ-Wert aus `DefaultDeltaThreshold`
  zurück (`:390-394`). Der Editor sieht also nie ein `kind:'absolute'` vom Server, und auf
  Platte gibt es keine (0 Treffer für `"kind": "absolute"` unter `data/`, nachgemessen
  2026-09-21). Trotzdem festgehalten, damit es später nicht als stille Datenänderung gelesen
  wird: mit dem Wegfall der Vorbelegung in `startEdit()` reicht `expandRules()` eine
  Absolut-Zahl (z. B. 50), sollte sie je im Speicher auftauchen, als Δ-Schwelle 50 durch.
  Das ist die **einzige** mit „Read-Modify-Write, kein Replace" vereinbare Behandlung; ein
  Überschreiben auf 20 wäre aktive Datenänderung ohne Nutzerhandlung. (Die Zeilenangaben
  `:206,238` und `:383` aus der Analyse sind veraltet; die genannten stammen aus der
  Nachmessung beim Schreiben dieser Spec.)
- **Restrisiko des Signatur-Wächters (AC-4):** das Baseline-Gate prüft `≤ 36`, nicht `== 36`.
  Würde dieselbe Lieferung anderswo einen Fehler beseitigen, könnte ein neuer maskiert
  werden. Der Adversary misst deshalb den Ist-Stand vor und nach der Lieferung und
  vergleicht die Fehlerlisten, nicht nur die Zahl.
- **Restrisiko Verdrahtung in der Komponente — ZWEI Glieder, nicht eines:** die
  Bausteintests bewachen `expandRules()`, die Signatur bewacht die Argumentliste. Der Weg
  von der Bestandsregel zum gespeicherten Ergebnis läuft aber über zwei Zeilen in
  `AlertRuleRow.svelte`, die beide in `.svelte` liegen und damit weder vom Bausteintest
  noch von der Typprüfung noch im Browser erreichbar sind (Begründung 1–3 oben):
  1. `startEdit()`: `draft = { ...rule }` **muss ein voller Spread bleiben**. Ein
     `draft = { ...rule, delta_window: '6h' }` wäre typkorrekt und unsichtbar.
  2. `saveEdit()`: `synced` darf nur aus `draft` und `unit` zusammengebaut werden. Ein
     zusätzliches `delta_window: '6h'` beim Zusammenbau wäre ebenso typkorrekt und unsichtbar.

  Eine Auslagerung des Zusammenbaus in eine testbare Funktion schließt die Lücke **nicht**,
  sie verschiebt sie nur auf das jeweils andere Glied — deshalb bewusst nicht vorgesehen.
  Der einzige Wächter ist die Sichtprüfung **beider** Zeilen im Adversary-Lauf; sie ist als
  Pflichtpunkt zu behandeln, nicht als Nebenbemerkung.
- **Grid-Überlauf ab zwei Kanälen** bleibt Bestand (3 + N Kinder bei 4 Tracks), gebucht in #1199.
- **`TripEditView.svelte` (Reiter „Alarmregeln") hat keine erreichbare Route** (#616); der
  Umbau wirkt dort mit, ist aber nur am Mount `TripNewEditor` im Browser messbar.
- **`frontend/e2e/helpers.ts:352`** nutzt weiter `alert-rule-threshold` (toter Helfer des
  abgeschafften Wizards, von keiner Spec mit `alertRules:` aufgerufen) — Sammel-Eintrag #1199.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue (einschlägig: ADR-0043)
- **Rationale:** ADR-0043 („Empfindlichkeitsstufe ist der einzige Alarm-Regler") hat
  Δ-Schwelle und Zeitfenster funktional entwertet, sie aber nicht aus der Bedienfläche
  genommen. Dieser Schritt vollzieht das nach und ändert weder ADR-0043 noch ein Datenmodell
  noch die Persistenz. Die PO-Entscheidung vom 2026-09-21 (Variante A) und der
  Präzedenzfall #1371 decken das ab.

## Changelog

- 2026-09-21: Initial spec created (spec-writer, Workflow `fix-1895-s2-alarmkarte-rueckbau`)
- 2026-09-21: Known Limitation „Restrisiko Verdrahtung" auf **beide** ungeschützten Glieder
  erweitert (`startEdit()` neben `saveEdit()`); Begründung ergänzt, warum eine Auslagerung
  des Zusammenbaus die Lücke nur verschiebt statt sie zu schließen.
