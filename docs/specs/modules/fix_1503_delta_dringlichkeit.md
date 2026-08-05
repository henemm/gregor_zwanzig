---
entity_id: fix_1503_delta_dringlichkeit
type: bugfix
created: 2026-08-04
updated: 2026-08-05
status: implemented
version: "1.1"
tags: [alerts, urgency, delta, trip, compare, issue-1503, epic-1458]
---

# Wetter-Änderungsalarme werden wieder abgestuft (Issue #1503)

## Approval

- [x] Approved — PO „go" 2026-08-04

## Purpose

Jede Vorhersage-Änderung trägt heute die Dringlichkeit `MODERATE` — ein Sprung um 2 Grad und
einer um 20 Grad sind im Alarm-Protokoll nicht unterscheidbar. Ursache ist ein Vorrang-Eintrag
je Metrik, der die vorhandene, getestete Abstufung nach dem Überschreitungsfaktor überschreibt.
Dieser Vorrang stammt aus #222, als man die Dringlichkeit je Regel noch selbst wählen durfte;
seit #946 gibt es diese Eingabe nicht mehr, der Vorrang trägt seither einen Wert, den niemand
setzt. Diese Scheibe entfernt ihn, sodass die Dringlichkeit aus dem **Ausmaß der Änderung**
folgt (PO-Entscheid 2026-08-04, Option 1 aus dem Ticket).

Sie ist die Voraussetzung für die einstellbare Kanal-Schwelle (#1461 S3b): eine Schwelle „nur
das Dringendste auf die teure SMS" würde heute **sämtliche** Änderungsalarme unterdrücken.

## Source

- **File:** `src/services/weather_change_detection.py`
- **Identifier:** `WeatherChangeDetectionService.from_alert_rules()`,
  `WeatherChangeDetectionService.detect_changes()`, `_classify_severity()`,
  `_ordinal_severity()` (neu)

Betroffene Schicht — **ausschließlich Python-Core** (`src/services/`). Kein Go, kein Frontend:
die einzige nutzersichtbare Wirkung (Farbe des Alarm-Punkts im Cockpit,
`frontend/src/routes/+page.svelte:399-405`) liest bereits das bestehende Protokollfeld
`alert.severity` und ändert sich allein mit dem Dateninhalt. Nachgemessen in
`docs/context/fix-1503-delta-dringlichkeit.md`: die Alarm-**Mail** druckt `ChangeSeverity`
nirgends (sie sortiert über die eigene numerische Schwellüberschreitung aus
`src/output/renderers/alert/model.py:111`), deshalb fällt auch der Vorschau-Pfad im Frontend
nicht an.

`src/services/alert_preset.py` wird **nicht** angefasst. Die dort hart gesetzte
`severity=AlertSeverity.WARNING` bleibt stehen (`AlertRule` verlangt das Feld) — sie wird für
die Δ-Einstufung nur nicht mehr gelesen. Das hält den Änderungssatz auf einer Datei.

## Estimated Scope

- **LoC:** ~45
- **Files:** 1 Produktivdatei (`src/services/weather_change_detection.py`) + Tests
- **Effort:** low (Umfang) / medium (Sorgfalt — Alarmpfad aller Nutzer)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.deviation_alert_engine.DeviationAlertEngine` | upstream | baut den Detektor aus `metric_alert_levels`, ruft `evaluate()` → `_highest_severity()` |
| `services.alert_preset.expand_per_metric_levels` | upstream | einzige Regelquelle des Alarmpfads (#946) |
| `services.alert_urgency.urgency_from_changes` | downstream | delegiert an `_highest_severity()` — **bleibt unverändert** (#1461 S3a) |
| `services.alert_log.append_entry` | downstream | schreibt `severity` ins Protokoll → Cockpit-Punkt |
| `output.renderers.sms_trip.format_alert_sms` | downstream | einziger Renderer, der `ChangeSeverity` liest (Sortierung) |
| `services.compare_alert` | downstream | Ortsvergleich nutzt denselben Detektor — wirkt automatisch mit |

## Implementation Details

### Ä1 — Der Vorrang entfällt

`from_alert_rules()` befüllt `severity_overrides[field_name] = rule.severity` (heute Zeile 536,
im DELTA-Zweig; der ABSOLUTE-Zweig hat den Eintrag nie geschrieben). Diese Zeile entfällt,
zusammen mit dem Konstruktor-Parameter `severity_overrides`, dem Feld `self._severity_overrides`
und der Fallunterscheidung in `detect_changes()` (Zeilen 629-635). Nachgemessen: kein Test und
kein anderer Aufrufer übergibt den Parameter.

```python
# detect_changes(), heute 628-635
if triggered:
    if metric in self._severity_overrides:            # ← entfällt
        severity = _RULE_SEVERITY_TO_CHANGE_SEVERITY[ # ← entfällt
            self._severity_overrides[metric]]         # ← entfällt
    else:
        severity = self._classify_severity(abs(delta), threshold)

# künftig
if triggered:
    if level is not None:                             # Niveau-Größe (Ä2)
        severity = self._ordinal_severity(old_value, new_value)
    else:
        severity = self._classify_severity(abs(delta), threshold)
```

`_RULE_SEVERITY_TO_CHANGE_SEVERITY` bleibt bestehen — der Absolut- und der
Threshold-Crossing-Pfad nutzen es weiter (`_detect_absolute_changes`,
`_detect_threshold_crossing_changes`).

### Ä2 — Niveau-Größen bekommen ihre eigene Ableitung

Für Gefahrenstufen-Größen (heute nur `thunder_level_max`, #1460) ist der Überschreitungsfaktor
das falsche Maß: die Schwelle ist in allen drei Empfindlichkeitsstufen `1`, und ausgelöst wird
über das erreichte **Niveau**, nicht über die Sprunggröße. Ohne eigene Ableitung ergäbe
`abs(delta)/1` — die Zahl der übersprungenen Stufen — folgendes:

| Übergang | Stufen-Delta | ratio | über den Faktor | richtig |
|---|---|---|---|---|
| kein Gewitter → höchste Stufe | 3 | 3,0 | MAJOR | MAJOR |
| mittlere → höchste Stufe | 1 | 1,0 | **MINOR** ❌ | MAJOR |

`_ordinal_severity(old, new)` leitet deshalb aus dem **gefährlicheren der beiden beteiligten
Niveaus** ab — symmetrisch für Verschärfung und Entwarnung, wie #1460 es für die Auslösung
bereits tut:

```python
_ORDINAL_TO_CHANGE_SEVERITY = {   # ThunderLevel-Ordinal → ChangeSeverity
    thunder_ordinal(ThunderLevel.HIGH): ChangeSeverity.MAJOR,
    thunder_ordinal(ThunderLevel.MED):  ChangeSeverity.MODERATE,
}   # LOW und NONE → MINOR (Default)
severity = _ORDINAL_TO_CHANGE_SEVERITY.get(max(old_value, new_value), ChangeSeverity.MINOR)
```

**Stolperstelle (aus dem RED-Lauf):** Die Ableitung muss **innerhalb** von `detect_changes()`
greifen, bevor das `WeatherChange` gebaut wird — dort sind `old_value`/`new_value` noch
Ordinal-Ganzzahlen. Wer sie nachträglich am fertigen `WeatherChange` ableitet, vergleicht
Floats gegen ein Dict mit Int-Schlüsseln; das geht in Python zufällig gut (`hash(3.0) == hash(3)`)
und ist genau die stille Kopplung, die sich später verschiebt.

Der Blick auf **beide** Werte ist Absicht: eine Entwarnung von der höchsten Stufe ist genauso
meldenswert wie ihr Erreichen und darf nicht dadurch abgewertet werden, dass der neue Wert
harmlos ist. Konservative Richtung wie in #1461 S3a: im Zweifel dringender, nie stiller.
Die Zuordnung entsteht über `output.metric_format.thunder_ordinal()` — keine rohen Ordinalzahlen
(die haben sich mit #1474 bereits einmal verschoben).

### Ä3 — Schwelle 0 stürzt nicht ab

`_classify_severity()` rechnet `abs(delta) / threshold` ohne Nullprüfung. Auf dem heutigen
Alarmpfad ist keine Schwelle 0 erreichbar (`_PRESET_TABLE` nachgesehen), aber der Vorrang hat
diese Stelle bisher zusätzlich abgeschirmt. Künftig: `threshold <= 0` → `ChangeSeverity.MAJOR`
(konservativ — eine Regel ohne sinnvollen Nenner feuert bei jeder Änderung, ihr Ergebnis darf
nicht stiller sein als der Normalfall).

### Was sich ausdrücklich NICHT ändert

- **Ob** ein Alarm ausgelöst wird (`abs(delta) > threshold` bzw. `_ordinal_change_triggers`)
- **Ob** ein ausgelöster Alarm gesendet wird — `trip_alert._filter_significant_changes()` gibt
  weiter alle Änderungen zurück; die Einstufung bleibt Etikett, nie Filterkriterium (#638)
- Die Bedienung: der Nutzer stellt weiterhin nur die Empfindlichkeit je Metrik ein
- `alert_urgency.py`, `deviation_alert_engine._highest_severity()`, das Vokabular
  `LOW`/`MODERATE`/`HIGH` (#1459)

## Expected Behavior

- **Input:** Zwei Vorhersage-Stände desselben Abschnitts plus die Empfindlichkeitsstufen des
  Nutzers je Metrik.
- **Output:** Je erkannter Änderung eine `ChangeSeverity` — `MINOR` bei Faktor < 1,5, `MODERATE`
  ab 1,5, `MAJOR` ab 2,0; für Gefahrenstufen-Größen aus dem höheren beteiligten Niveau. Ins
  Protokoll geht über `_highest_severity()` die höchste beteiligte Einstufung als
  `LOW`/`MODERATE`/`HIGH`.
- **Side effects:** keine neuen. Der Protokolleintrag trägt denselben Schlüssel wie bisher, nur
  mit einem gemessenen statt konstanten Wert. Der Cockpit-Punkt wird dadurch erstmals rot bzw.
  neutral statt ausnahmslos gelb.

## Acceptance Criteria

Alle ACs außer AC-10 laufen über die **echte Pipeline** (`DeviationAlertEngine.evaluate()` mit
`metric_alert_levels`), nicht über die Rechenfunktion allein — geprüft wird dort, wo die
Zusicherung wirkt, nicht dort, wo der Code steht.

- **AC-1:** Given ein Nutzer mit Empfindlichkeit „standard" für Windböen (Schwelle 20 km/h) /
  When die Böen-Vorhersage sich zwischen zwei Ständen um 25 km/h ändert (Faktor 1,25) /
  Then trägt das Ergebnis von `DeviationAlertEngine.evaluate()` die Dringlichkeit `LOW`.
  - Test: `evaluate()` mit zwei `PointWeatherData`-Ständen, `EvaluationResult.severity == "LOW"`.
    Vor dem Fix liefert derselbe Aufbau `MODERATE`.

- **AC-2:** Given derselbe Aufbau / When die Änderung 35 km/h beträgt (Faktor 1,75) /
  Then ist die Dringlichkeit `MODERATE`.
  - Test: wie AC-1 mit anderem Zweitstand. **Invarianten-AC:** dieser Wert ist schon heute
    richtig, weil Faktor 1,75 zufällig mit dem Konstantwert zusammenfällt. Er belegt für sich
    genommen **nichts** über den Fehler — er sichert nur, dass die Mitte beim Umbau nicht
    verrutscht. Ist im RED-Lauf grün und muss grün bleiben.

- **AC-3:** Given derselbe Aufbau / When die Änderung 45 km/h beträgt (Faktor 2,25) /
  Then ist die Dringlichkeit `HIGH`.
  - Test: wie AC-1.

- **AC-3b:** Given derselbe Aufbau / When dieselbe Metrik nacheinander um 25, 35 und 45 km/h
  abweicht / Then ergeben die drei Läufe **drei verschiedene** Dringlichkeiten.
  - Test: die drei Werte aus AC-1/2/3 in einer Liste gesammelt und auf Verschiedenheit geprüft.
    Das ist der eigentliche Nachweis des Fehlers aus Nutzersicht („2 Grad und 20 Grad sind
    nicht unterscheidbar") — vor dem Fix liefert er `['MODERATE', 'MODERATE', 'MODERATE']`.

- **AC-4:** Given zwei Metriken ändern sich im selben Lauf, eine knapp über Schwelle
  (Faktor 1,2) und eine mit Faktor 2,5 / When der Lauf ausgewertet wird / Then trägt der
  **Protokolleintrag** `HIGH` — die stärkste Änderung bestimmt die Dringlichkeit des Alarms.
  - Test: voller `TripAlertService`-Lauf, `alert_log`-Datei des Nutzers gelesen,
    `entries[-1]["severity"] == "HIGH"`.

- **AC-5:** Given Empfindlichkeit „sensibel" für Gewitter / When die Gewitterstufe von
  „mittel" auf „hoch" steigt (Sprung um genau eine Stufe) / Then ist die Dringlichkeit `HIGH`.
  - Test: `evaluate()` mit `thunder_level_max` MED → HIGH. Ohne `_ordinal_severity()` liefert
    derselbe Aufbau `LOW` (ratio 1,0) — das ist der Fehler, den diese AC verhindert.

- **AC-6:** Given derselbe Aufbau / When die Gewitterstufe von „hoch" auf „kein Gewitter"
  fällt (Entwarnung) / Then ist die Dringlichkeit ebenfalls `HIGH`.
  - Test: `evaluate()` mit HIGH → NONE. Belegt die Symmetrie: die Entwarnung von der
    Höchststufe wird nicht dadurch abgewertet, dass der neue Wert harmlos ist.

- **AC-7:** Given eine Änderung, die nur knapp über der Schwelle liegt und damit `LOW` trägt /
  When der vollständige Alarmlauf durchläuft / Then wird der Alarm **gesendet und
  protokolliert** — die Einstufung unterdrückt nichts.
  - Test: voller `TripAlertService`-Lauf mit einer Faktor-1,2-Änderung; geprüft wird, dass
    mindestens ein Kanal beliefert wurde und ein Eintrag in `entries` steht (Invariante #638).

- **AC-8:** Given drei Änderungen unterschiedlicher Stärke im selben Alarm / When die
  Alarm-SMS gerendert wird / Then steht das Kürzel der stärksten Änderung vorn.
  - Test: `format_alert_sms()` über die vom Detektor erzeugten `WeatherChange`-Objekte
    (nicht handgebaut); Position der Kürzel im Text geprüft. **Korrektur nach dem RED-Lauf:**
    vor dem Fix ist die Reihenfolge *nicht* beliebig. `sorted()` ist in Python **stabil** —
    bei gleichem Rang bleibt die Einfüge-Reihenfolge des Detektors erhalten, also die
    Schlüssel-Reihenfolge aus `metric_alert_levels` bzw. die `_PRESET_TABLE`-Reihenfolge des
    Backfills. Faktisch steht heute die **zuerst konfigurierte** Änderung vorn, nicht die
    stärkste. Der Test nutzt genau diese Determiniertheit (schwächste Metrik zuerst
    konfiguriert), sonst wäre er wackelig.

- **AC-9:** Given ein Orts-Vergleich mit Empfindlichkeit „standard" / When sich an einem Ort
  eine Metrik um den Faktor 2,5 ändert / Then trägt der Protokolleintrag des Vergleichs `HIGH`.
  - Test: `CompareAlertService`-Lauf, `alert_log`-Eintrag mit `entity_type == "compare"`.
    Belegt, dass der geteilte Detektor beide Seiten trägt (kein zweiter Codepfad).

- **AC-10:** Given eine Δ-Regel mit Schwelle 0 / When eine Änderung erkannt wird /
  Then stürzt die Einstufung nicht ab und liefert `MAJOR`.
  - Test: `WeatherChangeDetectionService` direkt mit `thresholds={"gust_max_kmh": 0.0}`;
    einziger AC ohne Pipeline, weil dieser Zustand über `metric_alert_levels` nicht erzeugbar
    ist.

- **AC-11:** Given ein gespeicherter Trip, dessen `alert_rules` eine Regel mit
  `severity="info"` enthalten / When ein Alarmlauf mit einer Faktor-2,5-Änderung stattfindet /
  Then ist die Dringlichkeit `HIGH`.
  - Test: voller Lauf mit einem Trip, dessen persistierte Regel-Dringlichkeit vom Ergebnis
    abweicht; als Vorbedingung wird geprüft, dass die geladene Regel wirklich `info` trägt.
    Belegt an der Wirkstelle, dass die Einstufung aus der Änderung folgt — eine reine Prüfung
    „Feld existiert nicht mehr" würde das nicht zeigen.
  - **Korrektur nach dem RED-Lauf:** die ursprüngliche Formel „`HIGH` und nicht `LOW`" war
    irreführend. Gemessen liefert dieser Aufbau heute `MODERATE`, nicht `LOW` — denn
    `trip.alert_rules[].severity` wird auf dem Alarmpfad **überhaupt nicht gelesen**
    (`_select_detector()` baut ausschließlich aus `metric_alert_levels`, und
    `expand_per_metric_levels()` setzt dort die Konstante `WARNING`). Der Vorrang trägt also
    nicht einmal den gespeicherten Wert, sondern eine Konstante. Der AC bleibt gültig, seine
    Begründung ist damit richtiggestellt.

- **AC-12:** Given zwei Nutzer mit je eigenem Datenordner, deren Trips im selben Lauf
  unterschiedlich starke Änderungen erfahren (Faktor 1,2 bzw. 2,5) / When beide Läufe
  durchlaufen / Then trägt die Protokolldatei jedes Nutzers ausschließlich die eigene
  Dringlichkeit (`LOW` bzw. `HIGH`).
  - Test: zwei `TripAlertService`-Instanzen mit verschiedenen `user_id`, isoliert über
    `app.loader.get_data_dir` (Muster #1265); geprüft wird beide Dateien, kein Rückfall auf
    `"default"`.

## Known Limitations

- **Sichtweite bleibt konstant eingestuft.** `visibility` ist eine
  Threshold-Crossing-Regel (#846), kein Δ — beim erstmaligen Unterschreiten gibt es keinen
  Überschreitungsfaktor. `_detect_threshold_crossing_changes()` setzt weiter
  `_RULE_SEVERITY_TO_CHANGE_SEVERITY[rule.severity]`, also `MODERATE`. Gleiches gilt für den
  Absolut-Pfad, der auf dem Alarmweg ohnehin ausgeschlossen ist (`include_absolute=False`).
  Bewusst außerhalb dieser Scheibe; vor dem Scharfstellen der Kanal-Schwelle (S3b) ist zu
  entscheiden, ob eine Sichtweiten-Unterschreitung die teure SMS erreichen soll.
- **Die Bänder selbst werden nicht neu justiert.** 1,5 / 2,0 sind die seit jeher
  dokumentierten Grenzen aus `_classify_severity()`. Ob ein Faktor 1,4 „gering" heißen soll,
  ist eine Produktfrage — sie wird hier nicht beantwortet, sondern erstmals überhaupt sichtbar.
- **Die tote Dringlichkeits-Auswahl in der Oberfläche bleibt stehen.**
  `AlertMetricRow.svelte:98-107` bietet je Metrik „Info / Warnung / Kritisch" an. Die
  Auswahl ist doppelt wirkungslos: `AlertMetricTable.svelte` ist nirgends eingebunden (der
  einzige Treffer ist ein Bauplan-Kommentar in `ListTable.svelte:10`), und gespeichert würde
  sie seit #946 ohnehin nicht gelesen. Nebenbefund → Sammel-Issue #1199, nicht Teil dieser
  Scheibe.

## Prüfung mit zwei Nutzern

AC-12 deckt es explizit ab. Die geänderte Funktion selbst ist nutzer-neutral
(`WeatherChangeDetectionService` bekommt Schwellen übergeben und liest nichts aus
`data/users/`); die Protokoll-Schreibstellen (`alert_log.append_entry(self._user_id, …)`)
bleiben unverändert. Die AC verifiziert, dass die neue Einstufung nicht über einen geteilten
Zustand von einem Nutzer zum anderen durchschlägt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue
- **Rationale:** Die Scheibe stellt den in ADR-0009/ADR-0013 beschriebenen Δ-Charakter wieder
  her (Delta bleibt Delta, keine absoluten Grenzen) und nutzt ausschließlich vorhandene,
  dokumentierte Vokabulare (#1459) und Rangfolgen. Sie führt keine zweite Zahlenreihe und
  keine neue Entscheidungsfläche ein. Die Niveau-Sonderbehandlung folgt ADR-0043/#1460 (keine
  generische Ordinal-Registry — dieselbe eine Größe, dieselbe Stelle).

## Changelog

- 2026-08-05: Umgesetzt. Adversary-Verdict VERIFIED nach 3 Runden (Finding F001
  geschlossen), 32 Tests grün, A/B-Gegenprobe gegen den Basisstand belegt null neue
  Regressionen.
- 2026-08-04 (v1.1): Drei Korrekturen aus dem RED-Lauf — AC-2 ist ein Invarianten-AC und
  belegt den Fehler nicht (neuer AC-3b tut es); die SMS-Reihenfolge ist heute nicht beliebig,
  sondern die Konfigurationsreihenfolge (stabile Sortierung); AC-11 liefert heute `MODERATE`,
  nicht `LOW`, weil die gespeicherte Regel-Dringlichkeit gar nicht gelesen wird.
  Zusätzlich die Umsetzungs-Stolperstelle zu Ä2 aufgenommen.
- 2026-08-04 (v1.0): Initial spec — PO-Entscheid Option (1) aus #1503
