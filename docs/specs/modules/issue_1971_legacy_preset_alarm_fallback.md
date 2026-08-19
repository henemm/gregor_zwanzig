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

- **File:** `src/services/compare_alert.py`
  - **Identifier:** `CompareAlertService._build_eval_config()`, konkret die
    Konstruktion von `metric_alert_levels` (Zeile 530-533). Die Nachbar-
    Methode `_display_config_from_active_metrics()` (Zeile 544-570) bleibt
    UNVERÄNDERT — sie ist bewusst NICHT der Ansatzpunkt dieser Spec (siehe
    „Verworfener Lösungsweg").

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

Ansatzpunkt ist `_build_eval_config()` (`compare_alert.py:508-542`), genau
dort, wo der `_STANDARD_METRIC_LEVELS`-Fallback ohnehin schon sitzt
(Zeile 530-533). `display_config` (Zeile 535,
`_display_config_from_active_metrics(preset)`) bleibt **unverändert** —
fehlt `active_metrics`, liefert diese Methode weiterhin `None`, der
#961-Filter/-Backfill in `expand_per_metric_levels()` bleibt also
übersprungen, CAPE bleibt erhalten.

Stattdessen wird `metric_alert_levels` neu zusammengesetzt:

```
active = (preset.get("display_config") or {}).get("active_metrics")
levels = (preset.get("display_config") or {}).get("metric_alert_levels")
if active is None:
    # Kein active_metrics -> Standard-Levels als Grundlage, explizite
    # Preset-Eintraege (auch "off") ueberschreiben sie gezielt.
    effektiv = {**_STANDARD_METRIC_LEVELS, **(levels or {})}
else:
    effektiv = levels or _STANDARD_METRIC_LEVELS  # unveraendert
```

`levels or {}` bzw. `levels or _STANDARD_METRIC_LEVELS` entsprechen der
bisherigen `preset.get(...) or _STANDARD_METRIC_LEVELS`-Formulierung; neu
ist ausschließlich die Fallunterscheidung nach `active is None` und das
Merge mit „explizite Einträge gewinnen" (Python-Dict-Merge-Reihenfolge:
`_STANDARD_METRIC_LEVELS` zuerst, `levels` zuletzt).

**Wirkung entlang der Kette (nachvollzogen, gemessen, nicht nur behauptet):**

| Fall | Ergebnis |
|---|---|
| AC-1: `metric_alert_levels` gesetzt ohne Onset, kein `active_metrics` | **14 Regeln, Onset ✓, CAPE ✓** (vorher: 3 Regeln, kein Onset — M3) |
| AC-4: kein `metric_alert_levels`, kein `active_metrics` | **14 Regeln, CAPE ✓** — unverändert gegenüber M2 |
| Abwahl-Probe: `{wind_gust: "off", precipitation_sum: "standard"}`, kein `active_metrics` | **13 Regeln, `wind_gust` NICHT dabei** — explizites `off` bleibt wirksam (AC-7) |
| AC-2/AC-3: `active_metrics` vorhanden (leer `[]` oder Teil-Auswahl) | von dieser Änderung **nicht berührt** — nimmt weiterhin den `else`-Zweig |

Der `off`-Schutz ergibt sich strukturell aus dem Merge (das Preset-`levels`
wird ZULETZT gemergt, sein `"off"`-Eintrag überschreibt den
`_STANDARD_METRIC_LEVELS`-Eintrag) — kein Sonderfall-Code nötig, aber
AC-7 macht das als eigenen Test verbindlich, damit eine spätere
Umformulierung (z. B. vertauschte Merge-Reihenfolge) sofort rot wird.

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
  - Test: `tests/tdd/test_compare_alert_missing_active_metrics_with_levels.py::test_explicit_off_survives_standard_levels_merge` — Δ-Sprung in der abgewählten UND in einer ergänzten Metrik, nur letztere löst einen Alarm aus.

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

  **Der hier eingeführte Merge verstärkt diesen Defekt messbar** — das ist
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
- 2026-08-19: Lösungsweg korrigiert — display_config-Ansatz verworfen
  (CAPE-Regression, 14→13 Regeln, Messbeleg Team-Lead), umgestellt auf
  Level-Merge in `_build_eval_config()`; AC-6 (CAPE-Regressionsschutz) und
  AC-7 (explizites `off` bleibt wirksam) ergänzt; Known Limitations um
  Vokabular-Mischungs-Befund (`cp-eb6ba0b239d90e37`) ergänzt
