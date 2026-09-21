# Context: fix-1895-alarm-absolut-modus

Erhoben am 2026-09-21 für Issue #1895. Zeilenangaben gegen den Worktree-Stand
`2c83b020` (Branch `worktree-epic-1419-sichtung`). Alle Angaben aus dem Issue-Text
stammen vom 2026-08-16/19 und wurden hier **gegen den heutigen Code nachgemessen** —
wo sie abweichen, steht es ausdrücklich dabei.

## Request Summary

Der Alarm-Regel-Editor bietet drei Modi an: „Änderung" (Delta), „Absolut", „Beides".
Der Modus „Absolut" verspricht eine Schwelle, die seit dem Umbau #946 keinen Alarm
mehr auslöst — der Server wandelt eine Absolut-Regel beim Speichern sogar sofort in
eine Änderungsregel um, ohne dass die Oberfläche das sagt. **Schritt 1 (dieses
Ticket):** Modus-Auswahl und Absolut-Schwellenfeld verschwinden aus der Bedienfläche;
sichtbar bleibt allein die Empfindlichkeitsstufe. Das Regel-Objekt bleibt als
unsichtbarer Träger der Kanalzuordnung bestehen. Kein Datenmodell-Umbau, keine
Migration.

## 🔴 Der PO-Entscheid liegt bereits vor — die drei „Zu entscheiden"-Fragen sind beantwortet

Der Issue-Text endet mit drei offenen Fragen. Sie sind im **Kommentar vom 2026-08-19**
([#1895, PO-Entscheid](https://github.com/henemm/gregor_zwanzig/issues/1895#issuecomment-5345547672))
entschieden — wer nur den Issue-Text liest, hält das Ticket fälschlich für offen im
Entwurf:

| Frage aus dem Issue-Text | PO-Entscheid 19.08. |
|---|---|
| Fällt der Modus „Absolut" ganz weg oder wird er umbenannt? | **Weg** — Modus-Auswahl und Absolut-Feld verschwinden aus der Bedienfläche |
| Wohin wandert die Kanalzuordnung? | **Nirgendwo — in Schritt 1 nicht.** Die Regel bleibt als unsichtbarer Träger bestehen. Ein eigenes Kanal-Feld je Metrik ist **Schritt 2**, zusammen mit #1230 (zurückgestellt) |
| Was passiert mit bestehenden Absolut-Regeln? | **Nichts** — keine Migration, kein Schema-Rework. Der Server normalisiert ohnehin seit je auf `kind='delta'` |

**Nicht-Ziel von Schritt 1** (wörtlich aus dem Entscheid): die Regel-Entität
abschaffen, `has_active_rules` ersetzen, oder an der serverseitigen Normalisierung
schrauben.

Vier Entwurfs-ACs stehen im selben Kommentar (AC-1 bis AC-4) — Feinschliff in der Spec.
**AC-4 trägt eine falsche Voraussetzung**, siehe Risiko 3.

## Der Befund ist härter als der Issue-Text sagt: doppelt abgeschnitten

Der Absolut-Modus ist nicht nur wirkungslos, er ist an **zwei unabhängigen Stellen**
abgeschnitten:

1. **Auslösepfad tot.** Es existiert echter Vergleichscode
   (`src/services/weather_change_detection.py:1005-1055`, `_detect_absolute_changes`),
   der `rule.threshold` real gegen Messwerte vergleicht. Er wird an **beiden**
   Aufrufstellen mit `include_absolute=False` aufgerufen
   (`src/services/trip_alert.py:1434-1436`, `src/services/deviation_alert_engine.py:221-223`)
   — das sind die einzigen zwei Aufrufer von `detect_changes(` im Produktivcode.
2. **Persistenz normalisiert weg.** `internal/model/trip.go:365-406` (`SyncAlertRules`,
   Herkunft #809/#817/#1257) läuft bei **jedem Load UND Save**
   (`internal/store/trip.go:206,238`) und setzt hart `rule.Kind = AlertRuleKindDelta`.
   Eine `kind='absolute'`-Regel überlebt das Speichern nicht; ist die Metrik nicht
   aktiv, wird die Regel ganz entfernt. Gemessen am laufenden Stack, Artefakt
   `docs/artifacts/fix-1488-gewitterstufen/red_ac4_go_store_normalizes_alert_rules.txt`.
   Bestätigt im Testkommentar `internal/model/alert_sync_test.go:40`:
   *„absolute Threshold war nie alert-wirksam"*.

**Folge:** Es gibt strukturell keinen Trip mit `kind='absolute'` auf Platte. Im Repo
bestätigt: 0 Treffer für `"kind": "absolute"` in `data/users/` und in den Fixtures;
`kind=absolute` existiert nur als Python-Objektkonstruktion in zwei Testdateien
(`tests/tdd/test_alert_rules_model.py`, `tests/tdd/test_issue_638_alerts_redesign.py:479-528`
— letztere prüft ausdrücklich nur die Kanal-Union, nicht die Auslösung).

## Was eine Alarmregel HEUTE noch wirksam tut

Zwei Dinge — beide unabhängig von `kind` und `threshold`:

| Funktion | Fundstelle | Wirkung |
|---|---|---|
| **Kanal-Routing** | `src/services/alert_channels.py:28-65` (`resolve_alert_channels`, Union-Logik `:53-59`), Eingabe aus `:86-93` (`_trip_channel_inputs`: Filter **nur** `r.enabled`, nie `r.kind`; Regel-Kanäle `:92`), Delegat `src/services/trip_alert.py:2873-2886` | Kette: expliziter `override` (`trip.alert_channels`) ersetzt komplett → sonst Union der `rule.channels` aktiver Regeln → leer ⇒ Rückfall auf Briefing-Kanäle (`inherited`, Default `{"email"}`) → Tier-Gates SMS/Premium-SMS |
| **Prüf-Gate** | `src/services/trip_alert.py:459-465`, zweite Stelle `:895-899` | `has_active_rules` = `has_preset OR has_metric_levels OR any(alert_rules enabled)`. Ist es `False` **und** `report_config.alert_on_changes` ebenfalls `False`, wird der Trip **komplett übersprungen** — kein Fetch, kein Check |

**Zeilenangaben im Issue sind veraltet:** Das Issue nennt `trip_alert.py:1547-1595` für
`_effective_alert_channels` und `:444-447` für `has_active_rules`. Beides ist seit dem
Kanal-Rework #2279 (geschlossen 17.09.2026) verschoben; die Kanal-Auflösung ist heute
ein **geteilter Kern** in `src/services/alert_channels.py`, `trip_alert.py` hält nur
noch einen Delegaten.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte:140-159` | Die drei Modus-Karten in `role="radiogroup"` — **das, was weg soll** |
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte:167-259` | Die Edit-Card als Ganzes: Metrik-Select → Schwellenfelder (`alert-rule-threshold-abs` :182, `-delta` :189, `alert-rule-threshold` :210/:230) → **Kanal-Chips** (`alert-rule-channel-{ch}` :237) → Aktiv-Checkbox → Speichern/Abbrechen. Alles in EINER durchgehenden Formularzeile |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte:33-55` | COPY-Map der Modus-Labels („Absolut"/„Änderung"/„Kombiniert") |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts:56-108` | `expandRules()` — die Modus-Zweige, die auf einen (`kind:'delta'`) kollabieren sollen; `DELTA_ONLY_METRICS` :47-52 |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte:23-30` | Rahmen; `updateRules()` ersetzt die bindable `rules`-Liste. **Kein eigener API-Call** — rein `bind:rules`, Persistenz läuft über den umschließenden Trip-Save |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:18,862,1102` · `frontend/src/lib/components/edit/TripEditView.svelte:10,205` | Die **einzigen zwei** Mounts des Editors — beide Trip |
| `src/services/alert_channels.py:28-65,86-93` | Kanal-Auflösung (geteilter Kern seit #2279) — muss den Umbau unbeschadet überleben (AC-3) |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.ts:24-33` | `toggleAlertChannel` — die **einzige** Schreibstelle für `rule.channels`, Vererbung bei leerem Feld `:12-17` |
| `frontend/src/lib/components/shared/AlertChannelPicker.svelte:1-13,29` · `shared/alarme-tab/alarmeDeliveryPayload.ts:102-120` | Die **andere**, trip-/vergleichsweite Kanalebene (`trip.alert_channels`) im separaten „Alarme"-Reiter — ohne Bezug zu einzelnen Regeln, von diesem Ticket nicht berührt |
| `src/services/trip_alert.py:459-465,895-899` | `has_active_rules` — Prüf-Gate, Risiko 1 |
| `internal/model/trip.go:365-406` · `internal/store/trip.go:206,238` | `SyncAlertRules` — **nicht anfassen** (Nicht-Ziel laut PO-Entscheid) |

**Tests, die den Bereich abdecken — Bausteinschicht** (alle `node --test`, kein
Vitest). 🔴 **Die E2E-Schicht deckt den Editor ebenfalls ab** und eine ihrer Specs
läuft in der CI-Ampel — siehe die Korrektur weiter oben und `## Analysis`:

| Testdatei | Rolle beim Umbau |
|---|---|
| `frontend/src/lib/components/alert-rules-editor/__tests__/deltaOnlyMetricsAbsolutGesperrt.test.ts` | Der Sperr-Test aus #1488 Scheibe A — **wird gegenstandslos**, wenn es keinen Absolut-Modus mehr gibt |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` (270 Z.) | Unit-Tests für `expandRules()`/`newDefaultRule()` — muss auf den einen verbleibenden Zweig umgeschrieben werden |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.test.ts` (88 Z.) | `effectiveAlertChannels`/`toggleAlertChannel` — **muss unverändert grün bleiben**; das ist der Nachweis, dass die Kanalzuordnung den Umbau überlebt |
| `frontend/src/lib/components/shared/__tests__/legacy_wizard_removed.test.ts:100-104` | Struktur-Test: `AlertRulesEditor` muss aktiver Export bleiben |

**🔴 KORREKTUR 21.09. (in `/20-analyse` nachgemessen): Es gibt sehr wohl
E2E-Specs für den Editor — die ursprüngliche Suche lief gegen den falschen Pfad**
(`frontend/e2e/playwright/`; die Specs liegen direkt unter `frontend/e2e/`). Gemessen:

| Spec | Treffer `mode-card`/`alert-rule-threshold` | In `.github/ci_e2e_specs.txt`? |
|---|---|---|
| `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` | 4 | **JA, Zeile 213 — läuft im `e2e`-Check der Ampel** |
| `frontend/e2e/alert-rules-editor.spec.ts` | 14 (u.a. `describe` „Issue #297 — mode=both") | nein |
| `frontend/e2e/issue-284-alert-rules-restyle.spec.ts` | 1 | nein |
| `frontend/e2e/helpers.ts` | 1 (`alert-rule-threshold`, :352) | mittelbar |

Folge: Der Umbau **bricht die CI-Ampel**, wenn die geratschte Gewitter-Spec nicht im
selben PR mit umgebaut wird. Das ist kein Risiko, sondern ein Pflicht-Arbeitspaket —
siehe `## Analysis`.

## Existing Patterns

- **Doppelte Sperre statt Kosmetik** (#1488 Scheibe A): Die `DELTA_ONLY_METRICS`-Sperre
  wirkt an zwei unabhängigen Orten — im Markup (`AlertRuleRow.svelte:141-148`, die
  Absolut-Karte wird gar nicht gerendert) **und** in der reinen Funktion
  (`alertRuleDefaults.ts:64-69,85-89`, erzwingt `kind:'delta'`). Dazu ein
  `$effect`-Guard (`:66-70`), der den Modus zurückspringen lässt. Vorlage dafür, wie
  eine UI-Zusicherung hier bewacht wird: nicht nur im Template.
- **Test importiert die produktive Konstante**, nie eine Kopie
  (`deltaOnlyMetricsAbsolutGesperrt.test.ts:11-15` benennt die Drift-Gefahr
  ausdrücklich).
- **🔴 Präzedenzfall #1371 — exakt dieselbe Entscheidung, schon einmal getroffen**
  (PO-Entscheid 24.07.2026, geschlossen): Das „Warnen"-Häkchen der Wertebereiche
  (`Corridor.notify`) löste seit der Umstellung auf den Abweichungs-Wächter (Epic #813)
  ebenfalls nie einen Alarm aus. Entschieden wurde damals: **Bedienelement entfernen,
  Datenfeld in Modell und Persistenz erhalten** (Read-Modify-Write, kein Replace). Das
  ist wörtlich die Linie, die der PO für #1895 Schritt 1 wiederholt — und damit die
  beste Umsetzungs- und Testvorlage im Haus.
- **Auffang statt Migration** (#1971, PR #1989): Bei fehlendem `active_metrics` wurde
  **kein** Bestandsdaten-Eingriff gemacht, sondern der Alarm-Pfad fängt den Fall auf
  (Parameter `supplement_missing_levels` in `src/services/alert_preset.py`), plus ein
  Wächter-Test auf Register-Deckung. Begründung: betroffene Produktionszahl lag bei 0 —
  ausdrücklich als Momentaufnahme markiert, nicht als Systemeigenschaft.
- **Empfindlichkeitsstufe als einziger Regler** (ADR-0043): `display_config.metric_alert_levels`
  → `alert_preset.expand_per_metric_levels()` (`src/services/alert_preset.py:178-330`)
  schlägt in `_PRESET_TABLE` (`:53-76`) nach und baut `AlertRule`-Objekte mit `kind` aus
  der Tabelle (fast immer `DELTA`) → `WeatherChangeDetectionService.from_alert_rules()`.
  Der vom Nutzer im Absolut-Modus eingetippte Wert fließt hier nirgends ein.

## Dependencies

- **Upstream:** `alertRuleDefaults.ts` (`expandRules`, `DELTA_ONLY_METRICS`),
  `ModeCard.svelte`, `$lib/components/organisms` (Re-Export)
- **Downstream:** `TripNewEditor.svelte` und `TripEditView.svelte` (die zwei Mounts),
  der Trip-Save-Pfad, und mittelbar `alert_channels.py` + `has_active_rules` im Python-Core

## Existing Specs & ADRs

| Dokument | Aussage |
|---|---|
| **ADR-0043** (03.08., Akzeptiert, PO-„go") | Die **Empfindlichkeitsstufe ist der einzige Alarm-Regler**; löst ADR-0040 ab, der den nutzerkonfigurierten Schwellen-Alarm eingeführt hatte. Das ist der ADR, der den Absolut-Modus funktional entwertet — er schafft ihn aber **nicht** als UI-Konzept ab; das tut erst dieses Ticket |
| **ADR-0009** (teilweise abgelöst durch 0056), **ADR-0013** | Alerts sind Abweichungs-Wächter gegen den Snapshot, nie gegen eine absolute Schwelle; `AlertEvent.threshold` ist immer Δ-Sensitivitätsschwelle |
| `docs/specs/_archive/modules/fix_946_alert_architecture.md` | AC-3: `_select_change_detector()` wertet **ausschließlich** `metric_alert_levels` aus — der Soll-Zustand seit #946 (01.07., Commit `8e9cff06`) |
| `docs/specs/modules/fix_1488_sa_gewitter_absolutregel.md` | Scheibe A: schließt das Guard-Loch nur für `thunder_level`, Frontend-only, PO-Entscheidung „entfernen statt umbenennen". Verweist den **generellen** Rückbau ausdrücklich an #1895 |
| **Für #1895 existiert noch keine Spec** unter `docs/specs/modules/` | Die vier ACs liegen nur als Entwurf im PO-Kommentar vom 19.08. |

Verwandte Issues: **#946** (closed, der Umbau), **#1488** (closed, Scheibe A+B),
**#638** (closed, hat `rule.channels` eingeführt), **#2279** (closed 17.09., geteilte
Kanal-Auflösung), **#2293** (offen, Kanäle S2 für den Ortsvergleich), **#1230**
(zurückgestellt, Datenmodell-Konvergenz — Träger von Schritt 2).

## Risks & Considerations

1. **Die Kanal-Chips sitzen in derselben Edit-Card — aber außerhalb der
   Modus-Verzweigung.** Nachgemessen: Die Modus-Verzweigung
   (`AlertRuleRow.svelte:177-233`, `{#if editMode==='both'} … {:else if 'delta'} …
   {:else /* absolute */}`) schließt in Zeile 233; der Kanal-Chip-Block (`:235-242`)
   steht **danach** und an keine Bedingung geknüpft — er wird für alle drei Modi
   identisch gerendert, im View-Modus ebenso (`:281-283`). Ein Entfernen der
   Modus-Zweige nimmt die Kanalauswahl also **strukturell nicht** mit. Die Vorsicht
   bleibt trotzdem berechtigt, weil beides in EINER Card (`:167-259`) liegt: Wer die
   Card großzügig zurückbaut statt gezielt die Zweige, verliert sie doch — AC-3 ist der
   Wächter dagegen. Die Kanalzuordnung ist in Schritt 1 die einzige verbleibende
   Daseinsberechtigung der Regel.
   Geschrieben wird `rule.channels` an genau einer Stelle
   (`alert-rules-editor/alertChannels.ts:24-33`, `toggleAlertChannel`), aufgerufen
   ausschließlich in `AlertRuleRow.svelte:240`.

2. **`has_active_rules` kippt NICHT — entgegen der ersten Vermutung.** Das Gate lautet
   `has_preset OR has_metric_levels OR any(r.enabled for r in trip.alert_rules)`
   (`trip_alert.py:459`, zweite Stelle `:895`) und prüft **ausschließlich `r.enabled`**,
   nie `r.kind`. Eine Umwandlung `absolute → delta` — die `SyncAlertRules` ohnehin bei
   jedem Load/Save vornimmt — ändert `enabled` nicht. Das #1971-Muster („stiller
   Alarm-Ausfall durch Migration") greift hier also **nicht**, solange Schritt 1 nur die
   Oberfläche vereinfacht und **keine Regeln aus `trip.alert_rules` löscht**. Genau das
   sagt der PO-Entscheid zu („Das Regel-Objekt im Hintergrund bleibt unverändert").
   ⇒ Die Zusicherung, die in die Spec gehört, ist damit nicht „das Gate darf nicht
   kippen", sondern **„es wird keine Regel gelöscht"**. Bleibt zu beachten: Der
   Nachweis „es wird keine Regel gelöscht" kommt aus der Bausteinschicht; die
   E2E-Schicht bewacht die Fläche (s. Korrektur oben), aber nicht diese Zusicherung.

3. **🔴 AC-4 des PO-Entwurfs trägt eine falsche Voraussetzung — nachgemessen.**
   AC-4 lautet „Given der Ortsvergleich mountet denselben Editor …". Das ist **nicht**
   der Fall: `AlertRulesEditor` wird im gesamten Frontend nur von
   `trip-new/TripNewEditor.svelte:18,862,1102` und `edit/TripEditView.svelte:10,205`
   importiert — beide Trip, **kein Compare-Importer**. Der Ortsvergleich nutzt für
   Alarme die tatsächlich geteilte, aber inhaltlich **andere** Komponente
   `shared/AlarmeTab.svelte` (Empfindlichkeitsstufen je Metrik über
   `AlertMetricLevelTable`), die kein Absolut/Delta/Beides-Konzept kennt. Der
   Ortsvergleich hat serverseitig auch gar keine eigenen Alarmregeln
   (`src/services/alert_channels.py:94-105`: *„Der Vergleich kennt keine Alarm-Regeln"*).
   ⇒ AC-4 muss in der Spec umformuliert werden: der Umbau ist trip-seitig, und zu
   belegen ist, dass der Ortsvergleich unverändert bleibt — **nicht**, dass er dasselbe
   Bild zeigt. Das ist **kein** Verstoß gegen die Teilungs-Konvention: es gibt kein
   Compare-Pendant, das geklont würde.

4. **Der PO-Entwurf nennt zwei Dateien, die toter Code sind.** Die erwarteten
   Fundstellen listen `alerts-tab/AlertMetricRow.svelte` und `alertMetricTable.ts` als
   „Anzeigeseite". `alerts-tab/AlertMetricTable.svelte` und `AlertMetricRow.svelte`
   haben jedoch **0 Importeure** außerhalb des eigenen Ordners; vom lebenden
   `AlarmeTab.svelte` werden nur `AlertMetricLevelTable.svelte` und
   `AlertPreviewCard.svelte` benutzt. Sie tragen eigenes „Absolut"-Vokabular
   (`AlertMetricRow.svelte:78-91` Spalte „Absolute threshold",
   `AlertMetricTable.svelte:16` Prop `requestedMode`) und sind bei einer Codesuche
   leicht mit dem lebenden System zu verwechseln. In der Spec zu entscheiden: mit
   zurückbauen oder unangetastet lassen (Löschen wäre Zuschnitt-Erweiterung).

5. **AC-1 spricht vom „Alarme-Reiter", der Editor hängt aber woanders.** AC-1 lautet
   „Given der Alarme-Reiter eines Trips …". `AlertRulesEditor` wird im Reiter „alerts"
   (`TripNewEditor`) bzw. „alarmregeln" (`TripEditView`) gemountet;
   `trip-detail/AlarmeScheduleTab.svelte:23,58-68` mountet dagegen `AlarmeTab`
   (Empfindlichkeitsstufen). In der Spec ist präzise zu benennen, **welche Fläche**
   gemeint ist, sonst zielt die Abnahme auf den falschen Bildschirm.

6. **Zeitbombe „Beides".** Im Modus „Beides" bleibt `alert-rule-threshold-abs` auch für
   Delta-only-Metriken sichtbar, und der eingetippte Wert wird beim Speichern verworfen
   (PO-Beobachtung 16.08. auf Staging `d519f4c5`). Der Hinweistext daneben sagt bereits
   das Richtige, das Eingabefeld widerspricht ihm. Fällt mit Schritt 1 weg — gehört
   als eigene Zusicherung in die Abnahme, sonst bleibt es übersehen.

## Offene Punkte für `/20-analyse`

- **Zuschnitt-Korrektur gegenüber dem Intake:** Die Intake-Bewertung war „Full Process"
  (Summe 5) und ging von zwei offenen Design-Fragen plus Backend-/Migrationsanteil aus.
  Beides trifft nicht zu — der PO-Entscheid liegt vor, der Umbau ist **frontend-only**
  (5 Quelldateien, 3 Testdateien, überwiegend Rückbau), kein Go-, kein Python-, kein
  Schema-Anteil. Realistische Neubewertung: Scope Medium, Blast Radius Medium
  (Kanalzuordnung + Prüf-Gate müssen überleben), Unsicherheit Low ⇒ **Standard**.
  Die Workflow-Art (`--type feature`) ist für beide identisch, es ist kein Neustart nötig.
- ~~Wie wird der Rückbau bewacht, wenn keine E2E-Spec den Editor abdeckt?~~
  **ERLEDIGT in `/20-analyse`** — die Voraussetzung war falsch (die Suche lief gegen
  `frontend/e2e/playwright/`). Es gibt E2E-Specs, und `gewitter-absolutregel-gesperrt.spec.ts`
  steht in der CI-Ratsche. Antwort: dieselbe geratschte Spec wird umgedreht, plus ein
  Bausteintest an der produktiven Komponente. Siehe `## Analysis`.
- Entscheidung zu Risiko 4 (toter `alerts-tab`-Zweig: anfassen oder nicht).
- Formulierung von AC-4 und AC-1 nach Risiko 3 und 5.
- **Randfall für die Abnahme:** Eine Metrik, deren abweichende Kanalzuordnung
  ausschließlich an einer Absolut-Regel hängt, **ohne** begleitende Delta-Regel für
  dieselbe Metrik. Solange die Regel nur umgewandelt (`kind='delta'`) und nicht gelöscht
  wird, bleibt `rule.channels` erhalten — `SyncAlertRules` löscht eine Regel aber sehr
  wohl, wenn die Metrik in `display_config` **nicht aktiv** ist
  (`internal/model/trip.go:365-406`). Dieser Pfad existiert bereits heute und wird von
  Schritt 1 nicht verändert; er gehört trotzdem in die Abnahme, damit niemand ihn später
  diesem Umbau zuschreibt.

## Nebenbefund (nicht Teil dieses Tickets)

Die Zurückstellung aus der #2279-Kontextdoku — *„Schwellen/`AlertRules` für den
Vergleich sind nicht Teil des Zielbilds — außerhalb dieser Scheibe"* — ist von **keinem
Folge-Ticket übernommen** worden. #2293 (offen) betrifft ausschließlich das
preset-weite `alert_channels`-Feld des Ortsvergleichs, nicht Regeln je Metrik. Falls
#1895 **Schritt 2** (Kanalzuordnung als eigenes Feld je Metrik) später auch den
Ortsvergleich einschließen soll, fehlt dafür heute ein Ticket. Kein nutzersichtbares
Fehlverhalten, kein Datenverlust, kein blockierendes Gate ⇒ nach der
Nebenbefund-Triage ein Eintrag für das Sammel-Issue **#1199**, kein eigenes Issue.

---

## Analysis

Erstellt 2026-09-21 in `/20-analyse`. Alle Zeilenangaben gegen `2c83b020`.

### Type

**Bug** (Label `bug`, `area:alerts`) — nutzersichtbares Falschversprechen. Der Fix ist
aber überwiegend **Rückbau in der Oberfläche**, kein Backend-Eingriff.

### Zuschnitt-Entscheid: Der Δ-Zweig bleibt sichtbar (wörtliche Lesart des PO-Entscheids)

Beim Lesen des PO-Entscheids stellt sich eine Zuschnittfrage, die materiell etwas
ändert: Der Zielsatz lautet *„sichtbar bleibt allein die Empfindlichkeitsstufe"*. Da
auch die **Δ-Schwelle** und das **Zeitfenster** keinen Alarm auslösen (einzige Quelle
ist `metric_alert_levels`, ADR-0043), könnte man sie mitnehmen wollen.

**Entschieden: nein — nur die Absolut-Teile fallen.** Begründung aus dem Entscheid
selbst, nicht aus Auslegung:

- Die Fundstellen-Tabelle des PO sagt wörtlich: *„`expandRules()` — die fünf
  Modus-Zweige **kollabieren auf einen (`kind: 'delta'`)**"*. Der überlebende Zweig ist
  `{...rest, kind:'delta', threshold: deltaThreshold, delta_window: deltaWindow}`
  (`alertRuleDefaults.ts:76-83`) — er **braucht** beide Eingaben.
- Die zwei Entfernungs-Bullets („Modus-Auswahl", „Absolut-Schwellenfeld") sind exakt
  die Menge dessen, was fällt, wenn die Modus-Maschinerie fällt und der Delta-Zweig
  bleibt. `alert-rule-threshold-abs` existiert nachgemessen **nur** im `both`-Zweig
  (`AlertRuleRow.svelte:177-186`).
- Der Zielsatz trägt die weitergehende Lesart nicht: Die Empfindlichkeitsstufe liegt
  gar nicht auf dieser Fläche (Risiko 5) — er ist eine Produktaussage mit bekannter
  Ungenauigkeit, keine Feldliste.

⇒ In die Spec als **ausdrückliche Annahme** und als **Nicht-Ziel**: *„Δ-Schwelle und
Zeitfenster bleiben in Schritt 1 sichtbar; dass auch sie nicht auslösen, ist derselbe
Befund und gehört zu Schritt 2."* Die AC-Freigabe in `/30-write-spec` ist der
vorgesehene Ort für eine Korrektur, falls der PO es anders meint.

### 🔴 Neu gegenüber `/10-context`: Der Umbau bricht die CI-Ampel

`frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` steht auf
`.github/ci_e2e_specs.txt:213`, läuft also im `e2e`-Check. Er geht nach dem Umbau
**garantiert rot**, an harten Assertions:

| Stelle | Assertion | Nach dem Umbau |
|---|---|---|
| Testfall 1 (Positivkontrolle Böen) | `expect(modeCard(edit,'absolute')).toHaveCount(1)` · `.toBeEnabled()` · Klick · `mode-card-absolute-selected` | **rot** — die Karte ist weg |
| Testfall 2, vor den soften Zeilen | `expect(modeCard(edit,'delta')).toHaveCount(1)` (hart) | **rot** |
| Testfall 2, AC-1c | `mode-card-delta-selected` → `toHaveCount(1)` (soft) | rot |
| Testfall 2, AC-1a/1d | `modeCard(...,'absolute')).toHaveCount(0)` (soft) | **vakuum-grün** |

**Konsequenz:** Der Umbau dieser Spec ist Pflicht-Arbeitspaket im selben PR, kein
Nachgang. Zwei Fallen dabei:

1. **Zeile 213 NICHT aus der Ratsche nehmen.** Das ist das bekannte Muster „Ratsche
   leeren macht den abhängigen Test vakuum-grün" — danach bewacht nichts mehr diese
   Fläche. Spec **in place** umschreiben, Eintrag behalten.
2. Die vorhandenen Anti-Vakuum-Kontrollen **behalten**: `expect(editor).toBeVisible()`
   in `openNewTripAlerts()` und `expect(edit).toBeVisible()` in
   `openFirstRuleEditor()`. Sie sind der Beleg, dass „keine Modus-Karte" nicht bloß
   „kein DOM" heißt. Ohne sie wäre der neue Wächter wertlos.

Damit ist auch die offene Frage aus `/10-context` („wie wird der Rückbau bewacht, wenn
keine E2E-Spec den Editor abdeckt?") beantwortet: **durch dieselbe geratschte Spec,
umgedreht** — plus einen Bausteintest als Ersatz für den gegenstandslos werdenden
`deltaOnlyMetricsAbsolutGesperrt.test.ts`.

### Affected Files (with changes)

| File | Change | Description |
|---|---|---|
| `frontend/src/lib/components/alert-rules-editor/AlertRuleRow.svelte` | MODIFY | Modus-Radiogroup `:140-159` raus; `editMode`-State `:41`, `$effect`-Guard `:62-70`, `deltaOnlyHint` `:57-60,161-165`, `draftAbsThreshold` `:46` entfallen; die drei Modus-Zweige `:177-233` kollabieren auf den Delta-Zweig (`alert-rule-threshold` + `alert-rule-delta-window`); Speichern-Label `:251` fest. **Kanal-Chips `:235-242`, Aktiv-Checkbox, Metrik-Select bleiben unberührt** |
| `frontend/src/lib/components/alert-rules-editor/ModeCard.svelte` | DELETE | Einziger Importeur ist `AlertRuleRow.svelte:20` (gemessen) |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.ts` | MODIFY | `expandRules()` `:56-108` kollabiert auf den Delta-Zweig; `AlertRuleMode` entfällt. **🔴 `DELTA_ONLY_METRICS` bleibt exportiert** — weiterhin benutzt von `alerts-tab/alertMetricTable.ts:151,367` und `alerts-tab/AlertMetricRow.svelte:17` |
| `frontend/e2e/gewitter-absolutregel-gesperrt.spec.ts` | MODIFY | **Ampel-relevant.** Wird vom Sperr-Wächter zum Abwesenheits-Wächter, Ratschen-Eintrag bleibt |
| `frontend/e2e/alert-rules-editor.spec.ts` | MODIFY | `describe` „Issue #297 — mode=both" `:298ff` und „AC-4 ModeCard Badge" `:396-420` werden gegenstandslos — löschen, nicht liegenlassen |
| `frontend/e2e/issue-284-alert-rules-restyle.spec.ts` | MODIFY | AC-5-Testfall `:263-290` greift auf `mode-card-absolute-selected` — gegenstandslos |
| `frontend/src/lib/components/alert-rules-editor/alertRuleDefaults.test.ts` | MODIFY | ~15 Modus-Testfälle auf den einen verbleibenden Zweig **umschreiben, nicht löschen**. Wer sie nur entfernt, lässt `expandRules()` genau in dem Moment ohne Abdeckung zurück, in dem die Funktion umgebaut wird — dasselbe Vakuum-Muster wie bei der E2E-Ratsche, eine Schicht tiefer |
| `frontend/src/lib/components/alert-rules-editor/__tests__/deltaOnlyMetricsAbsolutGesperrt.test.ts` | REPLACE | Wird gegenstandslos (ruft `expandRules(..., 'absolute', ...)`). Ersatz: Wächter, der die **Abwesenheit** der Modus-Fläche an der produktiven Komponente misst — nach dem Muster der Datei, die die produktive Konstante importiert statt einer Kopie |
| `frontend/src/lib/components/alert-rules-editor/alertChannels.test.ts` | UNCHANGED | **Muss unverändert grün bleiben** — das ist der AC-3-Nachweis, dass die Kanalzuordnung den Umbau überlebt |
| `frontend/src/lib/components/alert-rules-editor/AlertRulesEditor.svelte` | UNCHANGED | Kein Modus-Bezug gemessen (`editMode`/`expandRules`/`ModeCard` → 0 Treffer) |
| `frontend/e2e/helpers.ts` | UNCHANGED | `:352` nutzt `alert-rule-threshold` — diese testid trägt der überlebende Delta-Zweig |

**Nicht angefasst** (Nicht-Ziele, ausdrücklich): `internal/model/trip.go`,
`internal/store/trip.go`, `src/services/alert_channels.py`, `src/services/trip_alert.py`,
der tote `alerts-tab/AlertMetricRow.svelte` + `AlertMetricTable.svelte`-Zweig
(Risiko 4 — Löschen wäre Zuschnitt-Erweiterung). **Präzisierung zu Risiko 4:** Das
Modul `alertMetricTable.ts` selbst ist **lebendig** (sein Export `ALERTABLE_METRICS`
speist `shared/alarme-tab/tripAlertMetricsFromCatalog.ts:11` und
`activeAlertMetricsFromCatalog.ts:6`) — tot sind nur die beiden Svelte-Komponenten.

### Scope Assessment

- Dateien: **11** (3 Quelle, 6 Test/E2E, 2 unverändert-mit-Nachweis)
- Anteil: **frontend-only** — kein Go, kein Python, kein Schema, keine Migration
- LoC: überwiegend Rückbau; Löschzeilen zählen gegen das 250er-Limit, ein
  `loc_limit_override` ist wahrscheinlich nötig. **Vor der Ankündigung
  `workflow.py status` fragen**, nicht aus der Ausschlussliste ableiten
- Risk Level: **MEDIUM** — nicht wegen der Änderung selbst (isolierte Komponente),
  sondern wegen zweier Zusicherungen, die den Umbau überleben müssen: die
  **Kanalzuordnung** (`rule.channels`, einzige Schreibstelle
  `alertChannels.ts:24-33`) und die Zusicherung **„es wird keine Regel gelöscht"**
  (sonst kippt `has_active_rules` und Trips werden still übersprungen)

### Technical Approach

1. **Bausteinschicht zuerst** (`alertRuleDefaults.ts`): `expandRules()` auf den
   Delta-Zweig reduzieren, Signatur entschlacken, `DELTA_ONLY_METRICS` unangetastet
   exportiert lassen. Tests dieser Datei mitziehen.
2. **Komponente** (`AlertRuleRow.svelte`): Radiogroup und Modus-Zweige entfernen,
   Delta-Zweig als einzigen Fall stehen lassen. **Gezielt die Zweige zurückbauen, nicht
   die Edit-Card großzügig** — die Kanal-Chips stehen zwar außerhalb der
   Modus-Verzweigung (`:235-242`, an keine Bedingung geknüpft), liegen aber in
   derselben Card `:167-259`. `ModeCard.svelte` fällt danach ersatzlos.
3. **E2E-Wächter umdrehen** (`gewitter-absolutregel-gesperrt.spec.ts`): Positivkontrolle
   Böen wird zur Abwesenheitskontrolle, Surface-Checks bleiben. Ratschen-Eintrag bleibt.
4. **Obsolete Testfälle löschen** in den zwei ungeratschten E2E-Specs.
5. **Grün-Nachweis für AC-3:** `alertChannels.test.ts` unverändert grün — und in der
   Mutations-Gegenprobe gezielt prüfen, ob ein Entfernen des Kanal-Chip-Blocks von
   irgendeinem Test gefangen wird.

**Vorlage im Haus:** #1371 (PO-Entscheid 24.07.) hat exakt dieselbe Entscheidung schon
einmal getroffen — Bedienelement entfernen, Datenfeld in Modell und Persistenz
erhalten. Beste Umsetzungs- und Testvorlage.

### Dependencies

- Upstream: keine — der Umbau ist blattseitig
- Downstream: die zwei Mounts (`TripNewEditor.svelte:862,1102`,
  `TripEditView.svelte:205`), mittelbar `src/services/alert_channels.py` (Kanal-Union)
  und `has_active_rules` (Prüf-Gate) — beide nur als **Zusicherung**, nicht als Änderung
- Kein Bezug zum Ortsvergleich: `AlertRulesEditor` hat **keinen** Compare-Importeur
  (gemessen); Compare nutzt `shared/AlarmeTab.svelte`

### Korrekturen an den Entwurfs-ACs (für `/30-write-spec`)

- **AC-1** muss die Fläche präzise benennen: Reiter **„Alarmregeln"**
  (`TripEditView.svelte:64,205`) und **„Alerts"** (`TripNewEditor.svelte:67,862,1102`)
  — ausdrücklich **nicht** der „Alarme"-Reiter (`trip-detail/AlarmeScheduleTab.svelte`,
  der `AlarmeTab` mit den Empfindlichkeitsstufen mountet). Sonst zielt die Abnahme auf
  den falschen Bildschirm.
- **AC-4** umdrehen: zu belegen ist, dass der **Ortsvergleich unverändert bleibt** —
  nicht, dass er dasselbe Bild zeigt. Die Voraussetzung „mountet denselben Editor" ist
  nachgemessen falsch. Kein Verstoß gegen die Teilungs-Konvention: es gibt kein
  Compare-Pendant, das geklont würde.
- **AC-2/AC-3** bleiben inhaltlich, präzisiert um die eigentliche Zusicherung:
  **es wird keine Regel aus `trip.alert_rules` gelöscht** (nicht „das Gate darf nicht
  kippen" — das Gate prüft nur `r.enabled`, nie `r.kind`).
- **Neu AC-5 (Zeitbombe „Beides"):** Das Feld `alert-rule-threshold-abs` existiert
  nirgends mehr im DOM — auch nicht für Metriken, für die es heute im Modus „Beides"
  sichtbar bleibt und der Wert beim Speichern verworfen wird.

### Open Questions

- [ ] Keine blockierende offene Frage. Der Zuschnitt-Entscheid oben (Δ-Zweig bleibt)
      geht als **ausdrückliche Annahme** in die Spec und wird mit der AC-Freigabe
      bestätigt oder korrigiert.

### Nebenbefund (→ Sammel-Issue #1199, kein eigenes Issue)

`frontend/e2e/helpers.ts:353` benutzt die testid `alert-rule-severity`. Die gibt es im
Editor seit #687 nicht mehr — `issue-687-alert-editor-soll-ist.spec.ts:86,207` sichert
ausdrücklich `toHaveCount(0)` zu. Der `input.alertRules`-Zweig des Helpers ist von
**keiner** Spec benutzt (0 Treffer) und würde beim ersten Gebrauch brechen. Toter
Helper-Code, kein nutzersichtbares Fehlverhalten ⇒ Sammel-Eintrag.
