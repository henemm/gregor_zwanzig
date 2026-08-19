---
entity_id: issue_1971_legacy_preset_alarm_fallback
type: module
created: 2026-08-19
updated: 2026-08-19
status: draft
version: "1.0"
tags: [alarm, ortsvergleich, bug]
---

<!-- Issue #1971 ("Alt-Ortsvergleiche ohne migrierte active_metrics bekommen
     nie eine Alarm-Regel"). Grundlage: PFLICHTLEKTUERE
     docs/context/fix-1971-legacy-preset-alarm.md — die dortigen Messungen
     M1-M5 sind BELEGT und werden hier nicht neu recherchiert. Die
     Kernbehauptung des Issues ist in ihrer ursprünglichen Form WIDERLEGT
     (M2); die tatsächliche Lücke ist enger (M3) und entsteht neu, nicht nur
     historisch (M5).

     WICHTIG: Ein erster Lösungsentwurf (display_config im None-Fall
     voll-aktivieren) wurde durch Messung VERWORFEN — er entfernt die
     CAPE-Regel (14 → 13 Regeln, siehe „Verworfener Lösungsweg" unten). Der
     hier festgeschriebene Weg wirkt stattdessen auf der Level-Ebene, nicht
     auf der display_config-Ebene. -->

# Alarm-Pfad: fehlendes `active_metrics` bei gesetztem `metric_alert_levels` lässt neue Metriken still (#1971)

## Approval

- [x] Approved — PO-Freigabe („go") am 2026-08-19, alle 7 ACs

## Purpose

`CompareAlertService._build_eval_config()` verwendet `metric_alert_levels`
heute entweder komplett aus dem Preset (falls gesetzt) oder komplett aus
`_STANDARD_METRIC_LEVELS` (falls nicht gesetzt) — ein reines Entweder-Oder
(`compare_alert.py:530-533`). Ist `metric_alert_levels` gesetzt, aber listet
eine neu eingeführte Metrik (z. B. die Beginn-Alarme aus #1468) noch nicht
auf, UND fehlt zugleich `display_config.active_metrics`, bleibt genau diese
Metrik still, weil der `None`-Fallback in
`_display_config_from_active_metrics()` den #961-Backfill blockiert (M3).
Dieser Zustand ist nicht auf Alt-Bestand beschränkt — der Compare-Editor
kann `active_metrics` bis heute weglassen (M5), die Lücke kann also
jederzeit neu entstehen. Diese Spec schließt sie **auf der Level-Ebene**:
Fehlt `active_metrics`, werden die gesetzten `metric_alert_levels` mit
`_STANDARD_METRIC_LEVELS` ergänzt statt allein verwendet — analog zur
bereits so funktionierenden Grundidee des Render-Pfads („fehlende
Konfiguration heißt: alles gilt"), aber ohne den `display_config`-Filter zu
berühren, der CAPE (seit #1585 `selectable=False`) sonst aus jeder Regel
entfernen würde.

## Source

> **Schicht-Hinweis:** Ausschließlich **Python-Core**
> (`src/services/`). Kein Go-, kein Frontend-Anteil — der Fix wirkt beim
> Auswerten der Alarm-Kette, nicht beim Speichern/Laden des Presets.

- **File:** `src/services/alert_preset.py`
  - **Identifier:** `expand_per_metric_levels()`, neuer Supplement-Zweig im
    `display_config is None`-Fall hinter dem Parameter
    `supplement_missing_levels`.
- **File:** `src/services/compare_alert.py`
  - **Identifier:** `CompareAlertService._build_eval_config()` — setzt den
    Schalter (Zeile 541). Die Konstruktion von `metric_alert_levels`
    (Zeile 530-533) und die Nachbar-Methode
    `_display_config_from_active_metrics()` (Zeile 544-570) bleiben
    UNVERÄNDERT — sie sind bewusst NICHT der Ansatzpunkt dieser Spec (siehe
    „Verworfener Lösungsweg" und M9).
- **Files (Durchreichung):** `src/services/point_weather.py`
  (`AlertEvaluationConfig.supplement_missing_levels`, Default `False`) und
  `src/services/deviation_alert_engine.py` (`_select_detector`).

## Estimated Scope

- **LoC:** ~10-15 produktiv (`compare_alert.py`, eine Stelle) + ~150-180
  Testcode (zwei neue Testdateien) — deutlich unter dem Workflow-Limit von
  250
- **Files:** 1 Produktivdatei geändert, 2 Testdateien neu
- **Effort:** low — lokale Änderung an einer bereits bestehenden
  Fallback-Verzweigung, kein neues Datenmodell, kein neuer Kanal

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_STANDARD_METRIC_LEVELS` (`src/services/compare_alert.py:51`) | Register | Bisheriger Alles-oder-nichts-Fallback; wird künftig als ERGÄNZUNG statt als Ersatz genutzt |
| `_PRESET_TABLE` (`src/services/alert_preset.py:53-77`) | Register | Quelle von `_STANDARD_METRIC_LEVELS`; 14 Einträge |
| `expand_per_metric_levels()` (`src/services/alert_preset.py:178-387`) | Funktion | Der `display_config is not None`-Zweig (Filter Zeile 315-321, Backfill Zeile 346-385) bleibt für diesen Fix ÜBERSPRUNGEN — `display_config` bleibt im `None`-Fall weiterhin `None`, nur `levels` ändert sich |
| `is_alert_metric_active()` / CAPE-Sonderfall (`src/services/weather_change_detection.py:229-233`) | Funktion | Dokumentiert, dass CAPE (Katalog-ID `cape`, `selectable=False` seit #1585, `src/app/metric_catalog.py:480`) NIE als aktiv gilt, sobald ein `display_config` ausgewertet wird — der Grund, warum der verworfene Lösungsweg CAPE stumm geschaltet hätte |
| `_ALERT_METRIC_TO_CATALOG_ID` (`src/services/weather_change_detection.py:96-118`) | Register | Speist den Backfill; 15 Einträge — Grundlage für den AC-5-Wächter-Test (unverändert) |
| `tests/tdd/test_compare_alert_metric_gating.py::test_f001a_empty_active_metrics_wind_delta_does_not_fire` | Test | MUSS nach dem Fix unverändert grün bleiben (Regressionsschutz #1191) |

## Implementation Details

### Verworfener Lösungsweg (nicht umsetzen — Messbeleg)

Ein erster Entwurf ließ `_display_config_from_active_metrics()` im
`None`-Fall ein voll-aktiviertes `UnifiedWeatherDisplayConfig` liefern statt
`None`. Gemessen (echte Kette, keine Simulation):

```
AC-4-Fall (kein metric_alert_levels, kein active_metrics):
  VORHER 14 Regeln, NACHHER 13 — verloren: ['cape']
```

Ursache: Sobald `display_config` nicht mehr `None` ist, greift der
#961-Filter (`alert_preset.py:315-321`), der vorher übersprungen wurde.
`is_alert_metric_active()` behandelt CAPE seit #1585 als **nie aktiv**,
weil seine einzige gemappte Katalog-Größe `cape` `selectable=False` trägt
(`weather_change_detection.py:229-233`). Ein Fix gegen stille Alarm-Ausfälle,
der selbst einen neuen stillen Ausfall erzeugt, ist nicht lieferbar — dieser
Weg wird verworfen.

### Umgesetzter Lösungsweg

> **Wegwechsel in Phase 5 (M9):** Ein Dict-Merge in `_build_eval_config()`
> (`effektiv = {**_STANDARD_METRIC_LEVELS, **(levels or {})}`) war der
> ursprünglich hier festgeschriebene Weg. Der RED-Lauf hat ihn **widerlegt**:
> nach dem Merge sind ergänzte und ausdrücklich gesetzte Einträge nicht mehr
> unterscheidbar, und genau diese Unterscheidung braucht der
> `claimed_fields`-Schutz. Folge: `wind_gust: "off"` verschwindet zwar aus der
> Regelmenge, das Summary-Feld `gust_max_kmh` wird aber über `wind_change`
> **neu** bewacht (gemessen: `None` → `25.0`) — der Fix führte einen eigenen
> stillen Fehler ein und verletzte AC-7 auf Alarm-Ebene. Messbeleg:
> `docs/context/fix-1971-legacy-preset-alarm.md`, Abschnitt M9.

Ansatzpunkt ist stattdessen `expand_per_metric_levels()`
(`alert_preset.py:178-425`) im `display_config is None`-Zweig — dort bleiben
`levels` (explizit) und Nachfüllung (ergänzt) getrennt, sodass der
bestehende `claimed_fields`-Schutz greifen kann.
`_build_eval_config()` bleibt an der Level-Konstruktion (Zeile 530-533)
**unverändert**, ebenso `_display_config_from_active_metrics()` (Zeile 535):
fehlt `active_metrics`, liefert diese Methode weiterhin `None`, der
#961-Filter/-Backfill bleibt übersprungen, CAPE bleibt erhalten.

Neu ist ein ausdrücklicher Parameter, mit dem der Aufrufer erklärt, dass
`levels` nur eine TEIL-Angabe ist:

```
def expand_per_metric_levels(levels, display_config=None,
                             supplement_missing_levels=False):
    ...
    if display_config is None and supplement_missing_levels:
        claimed_fields = Vereinigung der Felder ALLER explizit gesetzten Metriken
        for row in _PRESET_TABLE:
            if row.metric in levels:
                continue                      # explizit gesetzt (inkl. "off")
            if Felder(row.metric) vollstaendig in claimed_fields:
                continue                      # Feld bereits belegt
            Regel auf "standard" ergaenzen, kollidierende Felder unterdruecken
```

Gesetzt wird der Schalter **allein** vom Vergleichs-Pfad
(`CompareAlertService._build_eval_config`, `compare_alert.py:541`); der
Trip-Pfad lässt den Default `False` stehen und bleibt damit nachweislich
unverändert (`trip_alert.py:311`, `:446` übergeben ihn nicht). Durchgereicht
wird er über das neue Feld `AlertEvaluationConfig.supplement_missing_levels`
(`point_weather.py:77`) und `DeviationAlertEngine._select_detector`
(`deviation_alert_engine.py:196-200`).

**Wirkung entlang der Kette (nachvollzogen, gemessen, nicht nur behauptet):**

| Fall | Ergebnis |
|---|---|
| AC-1: `metric_alert_levels` gesetzt ohne Onset, kein `active_metrics` | **13 Regeln, Onset ✓, CAPE ✓** (vorher: 3 Regeln, kein Onset — M3) |
| AC-4: kein `metric_alert_levels`, kein `active_metrics` | **14 Regeln, CAPE ✓** — unverändert gegenüber M2 |
| Abwahl-Probe: `{wind_gust: "off", precipitation_sum: "standard"}`, kein `active_metrics` | **12 Regeln, `wind_gust` NICHT dabei**, `gust_max_kmh` bleibt unbewacht — explizites `off` bleibt wirksam (AC-7) |
| AC-2/AC-3: `active_metrics` vorhanden (leer `[]` oder Teil-Auswahl) | von dieser Änderung **nicht berührt** — der Schalter wirkt nur bei `display_config is None` |

Die Zahlen sind gemessen, nicht geschätzt (Artefakte
`docs/artifacts/fix-1971-legacy-preset-alarm/messung-varianz-und-ac-faelle.txt`
und `messung-m9-wirkort.txt`). Zwei Zahlen liegen **niedriger** als der reine
Standard-Satz erwarten ließe, beide aus demselben Grund: der
`claimed_fields`-Feldschutz unterdrückt eine Ergänzung, deren Felder bereits
von einem ausdrücklichen Eintrag belegt sind. Bei AC-1 entfällt so
`precipitation_change` (Feld `precip_sum_mm` gehört dem gesetzten
`precipitation_sum`), bei der Abwahl-Probe zusätzlich `wind_gust` selbst.
Andernfalls überschriebe eine ergänzte `standard`-Schwelle eine bewusst
gesetzte `entspannt`-Schwelle auf demselben Feld — was
`test_issue_1170_compare_alert_config.py::test_ac5_stored_entspannt_level_makes_alert_less_sensitive`
ausdrücklich verbietet.

Der `off`-Schutz ergibt sich strukturell daraus, dass explizit gesetzte
Metriken im Supplement-Zweig übersprungen werden UND ihre Felder für
ergänzte Regeln gesperrt bleiben — kein Sonderfall-Code nötig. AC-7 macht
das als eigenen Test verbindlich, und zwar **auf Feld-Ebene** (Schwellen des
Detektors), nicht nur an der Regelmenge: nur dort zeigt sich, ob eine
abgewählte Größe über eine zweite Regel wieder unter Überwachung gerät (M9).

### Wächter-Test: Register-Deckung (unverändert gegenüber dem ursprünglichen Entwurf)

Zwei getrennt gepflegte Register speisen die zwei Wege, auf denen eine
Metrik scharf werden kann (M4): `_ALERT_METRIC_TO_CATALOG_ID`
(`weather_change_detection.py:96-118`, Backfill) und `_PRESET_TABLE`
(`alert_preset.py:53-77`, Preset-Fallback). Ein neuer Test vergleicht die
Metrik-Mengen beider Register direkt (keine Dateiinhalt-Prüfung, sondern
Import und Iteration der echten Register) und lässt nur die dokumentierte
Ausnahme `AlertMetric.SNOW_LINE` (per #959 bewusst nach `FREEZING_LEVEL`
konsolidiert) unbeanstandet. Jede künftige Metrik, die nur in einem der
beiden Register landet, macht den Test rot — schließt die Fehlerklasse
hinter #1971, nicht nur den heutigen Symptomfall.

## Expected Behavior

- **Input:** Ein Ortsvergleichs-Preset, dessen `display_config` entweder
  `active_metrics` fehlt (Key absent oder `None`) oder eine bewusst leere
  Liste `[]` trägt, kombiniert mit gesetztem oder fehlendem
  `metric_alert_levels`.
- **Output:** Fehlt `active_metrics` (Key absent/`None`), werden fehlende
  `metric_alert_levels`-Einträge auf `standard` ergänzt — unabhängig davon,
  ob `metric_alert_levels` überhaupt gesetzt ist; explizit gesetzte
  Einträge (inklusive `off`) bleiben unverändert wirksam. Ist
  `active_metrics` eine leere Liste `[]` oder eine Teil-Auswahl, bleibt das
  Verhalten exakt wie heute (unverändert, #1191).
- **Side effects:** Keine Persistenz-Änderung — die Auswertung wirkt nur
  zur Laufzeit der Alarm-Kette, das Preset auf Platte bleibt unangetastet.

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleichs-Preset ohne `display_config.active_metrics`
  (Schlüssel fehlt) und mit gesetztem `metric_alert_levels`, das die
  Onset-Metriken `thunder_onset`/`precipitation_heavy_onset` NICHT auflistet
  / When die Alarm-Kette (`_build_eval_config` → `expand_per_metric_levels`
  → `WeatherChangeDetectionService.from_alert_rules` → `detect_changes`) für
  einen deutlichen Vorverschiebungs-Sprung im Gewitterbeginn ausgewertet
  wird / Then entsteht eine `thunder_onset`-Alarmregel und der Sprung löst
  einen Alarm aus, obwohl `metric_alert_levels` die Metrik nie genannt hat.
  - Test: `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py::test_onset_alarm_fires_without_active_metrics_key` — echte Kette, kein Mock, Fixture nach Vorbild `test_onset_alert_armed_from_weather_tab.py`.

- **AC-2:** Given ein Ortsvergleichs-Preset mit `active_metrics: []` (der
  Nutzer hat im Editor bewusst alles abgewählt) / When derselbe Wind-Δ-Sprung
  ausgewertet wird, der ohne Abwahl feuern würde / Then bleibt es still
  (kein Alarm) — der Fix darf die bewusste Leer-Auswahl nicht mit dem
  fehlenden Schlüssel verwechseln.
  - Test: bestehender `tests/tdd/test_compare_alert_metric_gating.py::test_f001a_empty_active_metrics_wind_delta_does_not_fire` — MUSS nach dieser Änderung unverändert grün laufen (Regressionsschutz #1191 F001a, kein neuer Testcode nötig, nur Nachweis im Validierungslauf).

- **AC-3:** Given ein Ortsvergleichs-Preset mit einer Teil-Auswahl in
  `active_metrics` (z. B. nur `wind_gust` gewählt, Niederschlag abgewählt)
  / When ein Δ-Sprung in der NICHT gewählten Niederschlags-Metrik ausgewertet
  wird, während zeitgleich ein Δ-Sprung in der gewählten Wind-Metrik vorliegt
  / Then feuert für Niederschlag kein Alarm, während der Wind-Alarm
  unverändert feuert — die Teil-Auswahl bleibt vom Fix unberührt.
  - Test: `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py::test_partial_active_metrics_only_selected_metric_fires`.
  - Test (Adversary-Finding F003): `…::test_partial_active_metrics_with_partial_levels_keeps_single_watched_field` — Teil-`active_metrics` UND partielles `metric_alert_levels` **gleichzeitig**. Der erste Test ist gegen ein Durchschlagen der Ergänzung blind, weil sein Preset über den vollen `_STANDARD_METRIC_LEVELS`-Fallback läuft und der Supplement-Zweig dann nichts mehr zu ergänzen findet. Der zweite prüft am Wirkort (`detektor._thresholds`) auf genau ein bewachtes Feld; bei einem Leck wären es elf (Rot-Nachweis per Doppel-Mutation, `docs/artifacts/fix-1971-legacy-preset-alarm/test-red-f003-mutation.txt`).

- **AC-4:** Given ein Ortsvergleichs-Preset OHNE `active_metrics` UND OHNE
  `metric_alert_levels` (der bereits vor dem Fix funktionierende Fall, M2) /
  When die Alarm-Kette ausgewertet wird / Then entstehen exakt dieselben 14
  Regeln wie vor dem Fix, weiterhin inklusive beider Onset-Metriken UND der
  CAPE-Metrik — der bereits korrekte Level-Fallback-Pfad darf durch die
  Änderung nicht verschoben werden.
  - Test: `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py::test_legacy_preset_without_levels_unchanged_rule_count` — zählt die entstandenen `AlertRule`-Objekte und prüft Onset- UND CAPE-Metriken namentlich.

- **AC-5:** Given die beiden Register `_ALERT_METRIC_TO_CATALOG_ID`
  (`weather_change_detection.py:96-118`, speist den Backfill) und
  `_PRESET_TABLE` (`alert_preset.py:53-77`, speist den Level-Fallback) / When
  eine Metrik nur in einem der beiden Register vorkommt und nicht auf der
  dokumentierten Ausnahmeliste (`AlertMetric.SNOW_LINE`) steht / Then schlägt
  der Wächter-Test rot — die strukturelle Ursache hinter #1971 (zwei
  getrennt gepflegte Register) bleibt dauerhaft überwacht, nicht nur der
  heutige Symptomfall.
  - Test: `tests/tdd/test_alert_metric_register_coverage.py::test_registers_agree_outside_documented_exceptions` — vergleicht die Metrik-Mengen beider Register direkt aus dem importierten Code, kein Dateiinhalt-Grep.

- **AC-6:** Given ein Ortsvergleichs-Preset ohne `active_metrics` (Key
  absent oder `None`) / When die Alarm-Kette ausgewertet wird / Then enthält
  die entstandene Regelmenge weiterhin eine `cape`-Regel — CAPE ist seit
  #1585 `selectable=False` und würde durch jede Lösung, die im `None`-Fall
  ein `display_config` mit dem #961-Filter aktiviert, still verschwinden
  (siehe „Verworfener Lösungsweg").
  - Test: `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py::test_cape_rule_survives_missing_active_metrics` — prüft explizit auf `metric == "cape"` in der Regelmenge, sowohl mit als auch ohne gesetztes `metric_alert_levels`.

- **AC-7:** Given ein Ortsvergleichs-Preset ohne `active_metrics`, dessen
  `metric_alert_levels` eine Metrik ausdrücklich auf `"off"` setzt (z. B.
  `wind_gust: "off"`) / When die Alarm-Kette ausgewertet wird / Then entsteht
  für diese Metrik keine Regel, während die durch den Fix ergänzten
  Standard-Metriken (z. B. Niederschlag) weiterhin feuern — die Ergänzung
  darf eine bewusste Abwahl des Nutzers nie überschreiben (Schutz gegen
  Bevormundung, CLAUDE.md).
  - Test: `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py::test_explicit_off_survives_standard_levels_merge` — Regelmengen-Ebene (12 Regeln, `wind_gust` fehlt).
  - Test (Alarm-Ebene, M9): `…::test_explicit_off_wind_gust_stays_silent_while_supplemented_metric_fires` — Δ-Sprung in der abgewählten UND in einer ergänzten Metrik, nur letztere löst einen Alarm aus. **Dieser Test ist der eigentliche AC-7-Nachweis:** Nur auf Feld-Ebene zeigt sich, ob eine abgewählte Größe über eine zweite Regel (`wind_change` ⊃ `gust_max_kmh`) wieder unter Überwachung gerät — genau daran scheiterte der verworfene Lösungsweg.
  - Test (Gegenbeleg): `…::test_explicit_off_collision_free_metric_stays_silent` — dieselbe Zusage für eine Metrik ohne Feld-Überschneidung; trennt die beiden Ursachen.

## Known Limitations

- **Frontend-Anlege-Pfad bleibt unverändert:** `compareEditorSave.ts:407-409`
  lässt `active_metrics` weiterhin weg, solange `activeMetricKeys === null`
  (Init-Wert, M5). Diese Spec behebt das NICHT an der Quelle — der Auffang
  im Alarm-Pfad deckt die Konsequenz ab, unabhängig davon, ob der Frontend-
  Defekt später separat geschlossen wird.
- **Produktionsbestand aktuell 0 betroffene Presets** (M1): Der Fix wirkt
  vorbeugend gegen künftig neu entstehende Presets, nicht gegen einen
  bestehenden Datenschaden — es ist keine Migration nötig.
- **Register bleiben strukturell getrennt:** Der neue Wächter-Test (AC-5)
  schließt die Fehlerklasse „Metrik nur in einem Register" durch
  Beobachtung, vereinheitlicht aber nicht die beiden Register selbst — das
  wäre ein größerer Refactor außerhalb dieses Scopes.
- **`snow_line` bleibt die einzige dokumentierte Ausnahme** im Wächter-Test;
  jede neue Ausnahme braucht eine explizite Begründung in derselben Liste,
  sonst schlägt AC-5 fehl.
- **Vokabular-Mischung in bestehenden Presets ist ein separater, bekannter
  Defekt und NICHT Teil dieser Lieferung.** Gemessen am echten
  Produktions-Preset `cp-eb6ba0b239d90e37` („Le Var"): dessen
  `metric_alert_levels` mischt zwei Vokabulare — Summary-Keys
  (`gust_max_kmh`, `cape_max_jkg`, `temp_max_c`, …) und Metrik-Namen
  (`wind_gust`, `precipitation_sum`, `thunder_level`). Ausgewertet werden
  ausschließlich die Metrik-Namen; ein Summary-Key-Eintrag wie
  `gust_max_kmh: "off"` ist bereits heute wirkungslos.

  **Die hier eingeführte Ergänzung verstärkt diesen Defekt messbar** — das ist
  ein bewusst in Kauf genommener Trade-off, keine Nebensache. Gemessen an
  einem Preset OHNE `active_metrics` mit `{temp_max_c: "off", wind_gust:
  "standard"}` (Temperatur im ignorierten Vokabular abgewählt):

  ```
  VORHER   1 Regel  [wind_gust]                  → temperature_max feuert NICHT
  NACHHER 14 Regeln [.., temperature_max, ..]    → temperature_max feuert
  ```

  Der `off`-Schutz aus AC-7 greift nur für Einträge im **Metrik-Vokabular**
  (`wind_gust: "off"`); eine Abwahl im Summary-Key-Vokabular wird vom
  Standard-Satz überschrieben. Die Richtung ist die konservative
  (mehr Alarm statt Stille, Leitsatz #1467 „Der gefährlichste Fehler ist der
  ausbleibende Alarm"), aber sie kann für einen betroffenen Nutzer wie
  ungewollte Zusatz-Alarmierung wirken. Betroffen wären ausschließlich
  Presets ohne `active_metrics` — davon existiert in Produktion derzeit
  **keines** (M1), weshalb der Trade-off heute niemanden trifft.

  `Le Var` selbst hat `active_metrics` gesetzt und wird von dieser Änderung
  nicht berührt. Der Vokabular-Defekt wird separat als **Issue #1981**
  geführt; wird er dort behoben, entfällt diese Limitation von selbst.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Fix ändert weder die Detektor-Architektur (ADR-0021,
  gemeinsame `DeviationAlertEngine` für Trip und Vergleich — bleibt
  unberührt, beide Flächen laufen weiterhin durch denselben Code) noch die
  Bedeutung der Empfindlichkeitsstufe (ADR-0043 — die Stufen-Semantik ändert
  sich nicht, nur welche Metriken überhaupt eine Regel bekommen). Er
  korrigiert eine bereits im Code dokumentierte Absicht
  (`compare_alert.py:548-559`, Bug #1191 Adversary F001: „fehlendes
  `active_metrics` = konservativ, alles feuert") dahin, dass sie auch bei
  gesetztem `metric_alert_levels` greift — auf der Level-Ebene statt der
  display_config-Ebene, um die #1585-Sonderregel für CAPE nicht zu berühren.
  Keine neue Entscheidungsfläche im Sinne von CLAUDE.md (kein neuer Kanal,
  Provider, Datenmodell, Auth- oder Editor-Paradigma).

## Changelog

- 2026-08-19: Initial spec created
- 2026-08-19: **Lösungsweg erneut korrigiert (Phase 5, Befund M9)** — der
  Dict-Merge in `_build_eval_config()` ist widerlegt (er löscht die
  Unterscheidung explizit/ergänzt, die der `claimed_fields`-Schutz braucht,
  und bewacht `gust_max_kmh` bei `wind_gust: "off"` neu). Umgesetzt wird
  stattdessen ein Supplement-Zweig in `expand_per_metric_levels()` hinter dem
  neuen Parameter `supplement_missing_levels`, den allein der Vergleichs-Pfad
  setzt. Wirkungstabelle auf die gemessenen Zahlen korrigiert (AC-1 14→13,
  Abwahl-Probe 13→12; Ursache: Feldschutz). Die 7 ACs sind unverändert —
  keine erneute PO-Freigabe nötig. Adversary-Finding F002.
- 2026-08-19: Lösungsweg korrigiert — display_config-Ansatz verworfen
  (CAPE-Regression, 14→13 Regeln, Messbeleg Team-Lead), umgestellt auf
  Level-Merge in `_build_eval_config()`; AC-6 (CAPE-Regressionsschutz) und
  AC-7 (explizites `off` bleibt wirksam) ergänzt; Known Limitations um
  Vokabular-Mischungs-Befund (`cp-eb6ba0b239d90e37`) ergänzt
