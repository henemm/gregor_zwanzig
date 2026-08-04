---
entity_id: feat_1461_s3a_alarm_dringlichkeit
type: feature
created: 2026-08-04
updated: 2026-08-04
status: implemented
version: "1.4"
tags: [alerts, urgency, trip, compare, epic-1458, issue-1461, s3a]
---

# Alarm-Dringlichkeit wird wahr (Issue #1461 Scheibe S3a, Epic #1458 Teil 3a)

## Approval

- [x] Approved — PO „go" 2026-08-04

## Purpose

Vier von sechs Protokoll-Schreibstellen setzen heute eine **Konstante** statt eines
gemessenen Werts: Radar/Nowcast schreibt immer `"HIGH"`, amtliche Warnungen schreiben
immer `"MODERATE"` — unabhängig davon, was tatsächlich passiert ist. Folge: leichter
Nieselregen in 19 Minuten steht im Protokoll als `HIGH`, eine amtliche Unwetterwarnung
der höchsten Stufe (rot) als `MODERATE`. Diese Scheibe ersetzt beide Konstanten durch
**eine geteilte Ableitung** (`src/services/alert_urgency.py`), sodass alle drei
Meldungsarten (Vorhersage-Änderung, Radar, amtliche Warnung) die Dringlichkeit tragen,
die sie tatsächlich haben. Sie ist die Voraussetzung für die einstellbare Kanal-Schwelle
(S3b) — ohne eine korrekte Einstufung würde eine Schwelle "nur das Dringendste auf die
teure SMS" das Gegenteil ihres Versprechens tun (Wiederholung von #638, s. Analyse in
`docs/context/feat-1461-s3a-kanal-dringlichkeit.md`).

## Source

- **File:** `src/services/alert_urgency.py` (neu)
- **Identifier:** `urgency_from_official_level()`, `urgency_from_radar()`,
  `urgency_from_changes()`, `highest_urgency()`

Betroffene Schicht — **ausschließlich Python-Core** (`src/services/`), kein Go, kein
Frontend. Die einzige nutzersichtbare Wirkung (Farbe des Alarm-Punkts im Cockpit,
`frontend/src/routes/+page.svelte:400-404`) liest bereits das bestehende Feld
`alert.severity` aus dem Protokoll — sie ändert sich automatisch mit dem Dateninhalt,
ohne Code-Änderung im Frontend.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `feat_1459_alert_protokoll` | module | Definiert `alert_log.append_entry()` mit dem Parameter `severity` und das Vokabular `LOW`/`MODERATE`/`HIGH` — wird hier ausschließlich mit einem abgeleiteten statt einem konstanten Wert befüllt |
| `rework_1467_s2_aenderungsalarm` | module | Vorbild für Modul-Zuschnitt (eine reine Funktion, mehrere Aufrufer) — `compare_alert_guard.py` (AG6) |
| `output.tokens.hazard_symbols.LEVEL_LETTERS` | konstante | Bestehende Abbildung amtliche Stufe → `L`/`M`/`H` (`hazard_symbols.py:34`, in Gebrauch `official_alerts.py:395`) — EINE Quelle für die Stufengrenzen, hier **referenziert**, nicht dupliziert (E2, Nachbesserung Team-Lead-Review). `MIN_SMS_LEVEL` (`hazard_symbols.py:37`) bleibt unberührt — es ist der Render-**Filter**, `LEVEL_LETTERS` ist die **Abbildung**; wir brauchen die Abbildung (s. Nicht-Ziele) |
| `services.radar_service.INTENSITY_*` (neu) | konstante | Vier benannte Label-Konstanten in `radar_service.py`, Rückgabewerte von `intensity_to_text()` — `alert_urgency.py` vergleicht gegen dieselben Konstanten statt gegen Zeichenketten-Duplikate (E3, Nachbesserung Team-Lead-Review) |
| `services.deviation_alert_engine.DeviationAlertEngine._highest_severity` | nutzt | Bestehender Baustein für die Δ-Wetter-Einstufung (E4) — bleibt inhaltlich unverändert, läuft aber durch das neue Modul |
| `services.official_alerts.models.OfficialAlert.level` | nutzt | Ganzzahlige amtliche Warnstufe 1–4, Quelle für `urgency_from_official_level()` (E2) |
| `output.renderers.alert.model.OnsetEvent`/`services.radar_service.NowcastResult` | nutzt | Trägt `is_convective` und `intensity_label`, Quelle für `urgency_from_radar()` (E3) |
| `services.trip_alert.TripAlertService` | erweitert | Zwei Konstanten (`:872`, `:1141`) ersetzt, eine bestehende Aufrufstelle (`:282`) auf das Modul umgestellt und um das Bündelungsverhalten aus E5 ergänzt |
| `services.compare_radar_alert.CompareRadarAlertService` | erweitert | Konstante `:137` ersetzt, Mehr-Orte-Bündelung über `highest_urgency()` |
| `services.compare_official_alert.CompareOfficialAlertService` | erweitert | Konstante `:151` ersetzt, Mehr-Warnungen-Bündelung über `highest_urgency()` |
| `services.compare_alert.CompareAlertService` | erweitert | `:194` auf das Modul umgestellt (inhaltlich unverändert, E4) |

## Estimated Scope

- **LoC:** ~110 neu / ~20 geändert (Team-Lead-Budget) zzgl. ~10 Zeilen in
  `radar_service.py` (Nachbesserung: benannte Label-Konstanten statt Inline-Strings) —
  insgesamt weiterhin deutlich unter der 250er-Grenze.
- **Files:** 7 (2 neu, 5 geändert, 1 Testdatei)
- **Effort:** low — kein Zustand, keine Persistenz-Änderung, kein Versandverhalten
  berührt (E6).

## Betroffene Dateien

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/alert_urgency.py` | CREATE | Vier reine Funktionen: Ableitung je Quelle + Kombinator (E1–E5) |
| `src/services/radar_service.py` | MODIFY | Vier Intensitäts-Label als benannte Konstanten (`INTENSITY_*`); `intensity_to_text()` gibt sie zurück statt Inline-Strings (wortgleicher Output) |
| `src/services/trip_alert.py` | MODIFY | Konstanten `:872` (Radar), `:1141` (amtlich) ersetzt; `:282` auf das Modul geführt, inkl. Bündelung mit `official_notices` (E5) |
| `src/services/compare_radar_alert.py` | MODIFY | Konstante `:137` ersetzt, Mehr-Orte-Bündelung über `highest_urgency()` |
| `src/services/compare_official_alert.py` | MODIFY | Konstante `:151` ersetzt, Mehr-Warnungen-Bündelung über `highest_urgency()` |
| `src/services/compare_alert.py` | MODIFY | `:194` auf das Modul geführt (inhaltlich unverändert, E4) |
| `tests/tdd/test_alert_urgency.py` | CREATE | Ableitung je Quelle inkl. Grenzfälle, Live-Referenz-Nachweise (AC-4, AC-10) |

## Ist-Stand — zwei von drei Quellen sind falsch eingestuft (gemessen)

| Quelle | Schreibstelle | heutiger Wert |
|---|---|---|
| Vorhersage-Änderung (Trip) | `trip_alert.py:282` | abgeleitet über `eval_result.severity` (korrekt) |
| Vorhersage-Änderung (Vergleich) | `compare_alert.py:194` | abgeleitet über `DeviationAlertEngine._highest_severity()` (korrekt) |
| Nowcast/Radar (Trip) | `trip_alert.py:872` | fest `"HIGH"` |
| Nowcast/Radar (Vergleich) | `compare_radar_alert.py:137` | fest `"HIGH"` |
| Amtliche Warnung (Trip) | `trip_alert.py:1141` | fest `"MODERATE"` |
| Amtliche Warnung (Vergleich) | `compare_official_alert.py:151` | fest `"MODERATE"` |

Konkrete Folge (gemessen anhand der Modelle): Ein Radar-Alarm mit `intensity_label`
`"Leichter Regen"` (leichter Nieselregen, `is_convective=False`) steht heute als `HIGH`
im Protokoll; eine amtliche Warnung `level=4` (rot, höchste Stufe) steht als `MODERATE`.
Das Cockpit zeigt beide Fälle mit vertauschter Farbe.

## Implementation Details

### E1 — Ein neues Modul, vier reine Funktionen, kein Zustand

`src/services/alert_urgency.py` bekommt eine Funktion je Quelle plus eine
Kombinationsfunktion für den Mehrquellen-Fall (E5). Rückgabewert ausschließlich das
bestehende Vokabular `"LOW"`/`"MODERATE"`/`"HIGH"`. `hazard_symbols` und `radar_service`
werden als **Module** importiert (`import output.tokens.hazard_symbols as
hazard_symbols`, `import services.radar_service as radar_service`), nicht als kopierte
Namen — nur so lesen die Funktionen bei jedem Aufruf den aktuellen Zustand der
referenzierten Konstanten, und ein Test kann eine Grenze durch Patchen tatsächlich
verschieben sehen (AC-4, AC-10).

```python
_LETTER_TO_URGENCY = {"L": "LOW", "M": "MODERATE", "H": "HIGH"}

def urgency_from_official_level(level: int) -> str:
    letter = hazard_symbols.LEVEL_LETTERS.get(level, "H")
    return _LETTER_TO_URGENCY[letter]
```

**Nachbesserung (Team-Lead-Review 2026-08-04):** Die ursprüngliche Fassung zog die
MODERATE/HIGH-Grenze aus `MIN_SMS_LEVEL` plus einer eigenen Zahl `4`. Das duplizierte
eine Grenzziehung, die in `hazard_symbols.py:34` bereits vollständig existiert
(`LEVEL_LETTERS = {2: "L", 3: "M", 4: "H"}`, in Gebrauch `official_alerts.py:395`) —
dieselbe Zuordnung 2→gelb→L, 3→orange→M, 4→rot→H, nur mit anderen Wörtern. Die
Ableitung liest jetzt ausschließlich `LEVEL_LETTERS`; `MIN_SMS_LEVEL` bleibt als
Render-Filter unberührt (Nicht-Ziel).

Fallback-Richtung bei einer Stufe außerhalb des Katalogs
(`LEVEL_LETTERS.get(level, "H")`): **konservativ, nie leiser als die Wirklichkeit** —
dieselbe Richtung wie im bestehenden Vorbild `official_alerts.py:395`. Fehlerhafte
Provider-Daten (z.B. `level=5`) werden als `HIGH` eingestuft statt als `LOW`: ein
falsch-hoher Alarm ist unbequem, ein falsch-niedriger verschluckt eine echte Warnung
(AC-3).

```python
def urgency_from_radar(*, is_convective: bool, intensity_label: str) -> str:
    if is_convective:
        return "HIGH"
    label = (intensity_label or "").strip().lower()
    if label == radar_service.INTENSITY_HEAVY.lower():
        return "HIGH"
    if label == radar_service.INTENSITY_MODERATE.lower():
        return "MODERATE"
    return "LOW"  # leicht, kein Niederschlag, unbekannt
```

`onset_minutes` geht **nicht** ein — es ist bereits die Auslöse-Bedingung
(`trip_alert.py:75-78`: Alarm nur bei ≤20 Minuten Vorlauf); eine zweite Verwendung als
Dringlichkeits-Achse wäre Doppelzählung derselben Information.

**Case-Insensitivität ist Pflicht, nicht Kosmetik:** `trip_alert.py:826-827` senkt den
ersten Buchstaben des Labels vor der Weitergabe (`_label[:1].lower() + _label[1:]`,
Grund: Fließtext-Einbettung „ab {onset_time}"), `compare_radar_alert.py` reicht das
`NowcastResult` dagegen unverändert in Title-Case durch. Ein case-sensitiver Vergleich
würde für den Trip-Pfad strukturell nie treffen — die Ableitung fiele still auf `LOW`
zurück, obwohl die Meldung `MODERATE` oder `HIGH` verdient. `urgency_from_radar()`
normalisiert deshalb selbst (`.strip().lower()`), unabhängig von der Schreibweise des
Aufrufers (AC-9).

**Nachbesserung (Team-Lead-Review 2026-08-04):** Die ursprüngliche Fassung verglich
zusätzlich gegen hartkodierte Zeichenketten (`"starker regen"`, `"mäßiger regen"`) — eine
Umbenennung der Labels an ihrer Quelle (`RadarNowcastService.intensity_to_text()`,
`radar_service.py:123-140`) hätte die Ableitung still auf `LOW` zurückfallen lassen,
ohne dass ein Test es merkt (Muster „Wächter trifft nichts und ist für immer grün"). Die
vier Labels sind jetzt benannte Modulkonstanten in `radar_service.py`
(`INTENSITY_CONVECTIVE`, `INTENSITY_HEAVY`, `INTENSITY_MODERATE`, `INTENSITY_LIGHT`,
`INTENSITY_DRY`); `intensity_to_text()` gibt sie zurück (wortgleicher Output, nur benannt
statt inline), `urgency_from_radar()` vergleicht gegen dieselben Konstanten statt gegen
Zeichenketten-Duplikate. `.strip().lower()` bleibt zusätzlich als Sicherheitsnetz für die
bekannte Kleinschreibung (AC-10).

```python
def urgency_from_changes(changes) -> str:
    return DeviationAlertEngine._highest_severity(changes)

def highest_urgency(*urgencies: str) -> str:
    if not urgencies:
        return "LOW"
    return max(urgencies, key=lambda u: _RANK.get(u, 0))
```

`urgency_from_changes()` ändert am Ergebnis nichts (E4) — sie existiert, damit alle drei
Quellen dieselbe Modul-Herkunft haben, statt dass zwei Aufrufer (`trip_alert.py:282`,
`compare_alert.py:194`) weiterhin direkt `DeviationAlertEngine._highest_severity()`
importieren. `highest_urgency()` folgt dem Muster `max_thunder()` (#1474, „das schärfste
vorhandene Signal gewinnt") und wird an jeder Stelle verwendet, an der mehrere
Einzelwerte in **einem** Protokoll-Eintrag zusammenlaufen (E5).

### E2 — Amtliche Warnung

`OfficialAlert.level: int` (1–4) → `urgency_from_official_level()`, s.o.

🔴 **Korrektur v1.4 (Validierungs-Befund):** Die vorige Fassung behauptete, Stufe 1 werde
„über `LEVEL_LETTERS` definiert behandelt (liefert `LOW`)". **Das war falsch, und kein Test
hielt die Behauptung.** `LEVEL_LETTERS` (`hazard_symbols.py:34`) hat **keinen** Schlüssel `1`
— Stufe 1 läuft in denselben konservativen Rückfall wie eine unbekannte Stufe und liefert
`HIGH`.

**Entscheidung: Verhalten bleibt, Text wird korrigiert.** Begründung:
- Stufe 1 („grün") kommt in ausgelösten Alarmen strukturell nicht vor — alle sechs Quellen
  filtern `<2` weg (`vigilance.py:126`, `meteoalarm.py`, `massif_closure.py:59`; die einzige
  Ausnahme `meteo_forets.py:113` liefert `1` zwar aus, erzeugt daraus aber keinen Alarm auf
  diesem Pfad).
- Ein Sonderfall nur für Stufe 1 wäre Code, den kein produktiver Ablauf je erreicht — und der
  gegen die Wirklichkeit nicht prüfbar wäre.
- Die Richtung des Rückfalls ist bewusst und in AC-3 abgesichert: im Zweifel dringender, nie
  stiller. Eine fälschlich als dringend eingestufte Grün-Warnung, die es nicht gibt, ist
  harmlos; eine verschluckte echte Warnung nicht.

**Lehre (Muster aus #1467 S2 AG6):** Eine Spec-Aussage über die Wirkung von Code ist eine
Vermutung, bis ein Test sie hält. Diese hier hielt niemand — sie stand vier Fassungen lang
falsch in der Spec, während der Code die ganze Zeit korrekt und absichtsvoll etwas anderes tat.

### E3 — Radar/Nowcast

`is_convective`/`intensity_label` aus `NowcastResult` (Trip-Pfad: `RadarAlertRequest`,
Compare-Pfad: `NowcastResult` direkt) → `urgency_from_radar()`, s.o.

### E4 — Vorhersage-Änderung bleibt inhaltlich unverändert

`trip_alert.py:282` und `compare_alert.py:194` rufen künftig
`alert_urgency.urgency_from_changes(...)` statt `eval_result.severity` bzw.
`DeviationAlertEngine._highest_severity(alle_changes)` direkt — der zurückgegebene Wert
ist identisch (AC-8), nur die Herkunft ist jetzt eine einzige Stelle für alle drei
Quellen.

### E5 — Mehrere Quellen im selben Lauf: die höchste gewinnt

Zwei unterschiedliche Bündelungs-Situationen sind betroffen, beide über
`highest_urgency()`:

1. **Trip: Vorhersage-Änderung + amtliche Warnung in einer Nachricht.**
   `check_and_send_alerts()` bündelt bei gleichzeitigem Δ-Treffer und offener amtlicher
   Warnung beides in **eine** Nachricht (`_send_alert(..., official_notices=...)`,
   Muster #1088, `notification_service.py:1106`). Der Log-Eintrag an `trip_alert.py:282`
   trug bisher **nur** `eval_result.severity` — die amtliche Warnung ging in der
   Einstufung unter, obwohl sie im selben Versand steckte. Neu:
   `highest_urgency(urgency_from_changes(to_report), *[urgency_from_official_level(a.level) for a, _ in official_notices])`.
2. **Ortsvergleich: mehrere Orte/mehrere Warnungen in einem Lauf.**
   `compare_radar_alert.py:137` und `compare_official_alert.py:151` bündeln bereits
   heute mehrere getriggerte Orte bzw. mehrere getaggte Warnungen in **einem**
   Log-Eintrag (`changes_count=len(triggered)` bzw. `len(tagged_alerts)`). Die
   Einstufung wird je Element berechnet und über `highest_urgency()` zusammengeführt,
   statt weiterhin eine Konstante für den ganzen Eintrag zu setzen.

### E6 — Verhaltensneutralität im Versand

Kein Alarm ändert sich — nicht ob er gesendet wird, nicht über welche Kanäle, nicht
wann. `MIN_SMS_LEVEL` bleibt als Render-Filter in `hazard_symbols.py:37` unverändert in
Kraft (Ablösung erst S3b); diese Scheibe fasst weder `effective_channels` noch
`NotificationResult` noch die Versandreihenfolge an. Einzige nutzersichtbare Änderung:
die Farbe des Punkts im Cockpit wechselt von falsch auf richtig.

### E7 — D4 aus #1459 bleibt gewahrt

Die Cockpit-Kachel „Alarme · letzte 24h" und die Archiv-Statistik „Alarme je Tour"
zählen ausschließlich `entries` (`internal/store/log.go:100 AlertCountByTrip()`,
`internal/handler/cockpit.go:36-42`). Diese Scheibe ändert an keiner der sechs
Aufrufstellen, **ob** oder **wohin** (`entries` vs. `not_delivered`) ein Eintrag
geschrieben wird — ausschließlich der Inhalt des Feldes `severity` innerhalb eines
ohnehin entstehenden Eintrags ändert sich.

## Expected Behavior

- **Input:** ein Alarm-Versandversuch (Tour oder Ortsvergleich) einer der drei
  Meldungsarten, inklusive der zugrundeliegenden Rohdaten (amtliche Stufe,
  Radar-Kennzahlen, Δ-Änderungsliste).
- **Output:** derselbe Protokoll-Eintrag wie vor dieser Scheibe (Ziel-Liste, Anzahl,
  Kanäle unverändert, E6/E7), aber mit einem `severity`-Wert, der die tatsächliche
  Dringlichkeit der Meldung widerspiegelt statt einer Konstante.
- **Side effects:** keine — reine Ableitungsfunktionen, kein Datei-/Netzzugriff, keine
  Zustandsänderung.

## Test Plan

### Automated Tests (TDD RED)

- [ ] `tests/tdd/test_alert_urgency.py::test_official_level_4_is_high` — GIVEN
      `level=4` WHEN `urgency_from_official_level()` aufgerufen wird THEN liefert sie
      `"HIGH"`.
- [ ] `tests/tdd/test_alert_urgency.py::test_official_unknown_level_falls_back_to_high`
      — GIVEN `level=5` (außerhalb des Katalogs) WHEN `urgency_from_official_level()`
      aufgerufen wird THEN liefert sie `"HIGH"` (konservative Fallback-Richtung), nicht
      `"LOW"`.
- [ ] `tests/tdd/test_alert_urgency.py::test_official_boundary_follows_level_letters`
      — GIVEN `hazard_symbols.LEVEL_LETTERS[3]` wird per Monkeypatch von `"M"` auf
      `"L"` gesetzt WHEN `urgency_from_official_level(3)` aufgerufen wird THEN liefert
      sie `"LOW"` statt `"MODERATE"` — die Grenze zieht mit der Konstante mit.
- [ ] `tests/tdd/test_trip_alert_radar_urgency.py::test_moderate_rain_radar_alert_logs_moderate`
      — GIVEN ein Radar-Alarm mit `is_convective=False`, Label „mäßiger Regen" (Trip-
      Kleinschreibung) WHEN `check_radar_alerts()` protokolliert THEN steht `"MODERATE"`
      im neuesten `entries`-Eintrag (vorher fest `"HIGH"`).
- [ ] `tests/tdd/test_alert_urgency.py::test_radar_label_rename_at_source_still_classifies_correctly`
      — GIVEN `radar_service.INTENSITY_HEAVY` wird per Monkeypatch umbenannt WHEN das
      umbenannte Label (erzeugt über `intensity_to_text()`) durch `urgency_from_radar()`
      läuft THEN liefert sie weiterhin `"HIGH"` — die Ableitung folgt der Konstante, nicht
      einem Zeichenketten-Duplikat.
- [ ] `tests/tdd/test_trip_alert_bundled_official_urgency.py::test_bundled_high_official_wins_over_minor_change`
      — GIVEN eine MINOR-Δ-Änderung und eine rote amtliche Warnung (`level=4`) werden im
      selben Lauf gebündelt WHEN protokolliert wird THEN trägt der EINE entstehende
      Eintrag `severity="HIGH"`.

## Acceptance Criteria

- **AC-1:** Given eine rote amtliche Warnung (`level=4`) löst für eine Tour einen
  Standalone-Alarm aus / When der Eintrag geschrieben wird / Then steht `"HIGH"` im
  neuesten `entries`-Eintrag — vorher stand dort fest `"MODERATE"`.
  - Test: `_send_official_alert_only(trip, [(OfficialAlert(level=4, ...), segment_ids)])`
    durchlaufen lassen, `alert_log.json["entries"][-1]["severity"] == "HIGH"` prüfen.

- **AC-2:** Given eine gelbe amtliche Warnung (`level=2`) löst denselben Standalone-Alarm
  aus / When protokolliert wird / Then steht `"LOW"` im Eintrag.
  - Test: gleiches Muster mit `level=2`.

- **AC-3 (konservative Fallback-Richtung, Nachbesserung Team-Lead-Review):** Given eine
  amtliche Warnung mit einer Stufe außerhalb des bekannten Katalogs (`level=5`,
  fehlerhafte Provider-Daten) löst einen Standalone-Alarm aus / When protokolliert wird
  / Then steht `"HIGH"` im Eintrag, nicht `"LOW"` — dieselbe konservative
  Fallback-Richtung wie im bestehenden Vorbild `official_alerts.py:395`
  (`LEVEL_LETTERS.get(alert.level, "H")`): ein falsch-hoher Alarm ist unbequem, ein
  falsch-niedriger verschluckt eine echte Warnung.
  - Test: `_send_official_alert_only()` mit `OfficialAlert(level=5, ...)`, Eintrag prüfen.

- **AC-4 (LEVEL_LETTERS-Ableitung ist live, ersetzt frühere MIN_SMS_LEVEL-Fassung):**
  Given `hazard_symbols.LEVEL_LETTERS[3]` wird testweise per Monkeypatch von `"M"` auf
  `"L"` gesetzt, eine amtliche Warnung der Stufe 3 (orange) liegt vor / When
  protokolliert wird / Then steht `"LOW"` statt `"MODERATE"` im Eintrag — der Beweis,
  dass die Grenze aus der bestehenden Abbildung `LEVEL_LETTERS` gelesen wird, nicht aus
  einer zweiten, eigenen Zahlenreihe im neuen Modul.
  - Test: `monkeypatch.setattr(hazard_symbols.LEVEL_LETTERS, ...)` bzw. Ersatz-Dict,
    denselben Standalone-Alarm mit `level=3` durchlaufen lassen, Eintrag vor/nach dem
    Patch vergleichen (`"MODERATE"` → `"LOW"`).

- **AC-5:** Given ein Radar-Alarm mit `is_convective=True` für eine Tour / When
  protokolliert wird / Then steht `"HIGH"` im Eintrag (weiterhin — aber jetzt aus
  `is_convective` abgeleitet statt aus einer Konstante).
  - Test: `check_radar_alerts()` mit einem konstruierten `NowcastResult`
    (`is_convective=True`) als Eingangsdatum, Eintrag prüfen.

- **AC-6:** Given ein Radar-Alarm mit `is_convective=False` und Label „mäßiger Regen"
  (Trip-Kleinschreibung, `trip_alert.py:826-827`) für eine Tour / When protokolliert
  wird / Then steht `"MODERATE"` im Eintrag — vorher stand dort fest `"HIGH"`.
  - Test: ein konstruiertes `NowcastResult` mit `intensity_label="Mäßiger Regen"`,
    `is_convective=False` als Eingangsdatum, Eintrag prüfen.

- **AC-7:** Given ein Radar-Alarm mit Label „leichter Regen" (leichter Nieselregen,
  `is_convective=False`) für eine Tour / When protokolliert wird / Then steht `"LOW"`
  im Eintrag — exakt der in der Analyse benannte Fall (Nieselregen in 19 Minuten, bisher
  fälschlich `HIGH`).
  - Test: ein konstruiertes `NowcastResult` mit `intensity_label="Leichter Regen"` als
    Eingangsdatum, Eintrag prüfen.

- **AC-8 (E4, Δ-Wetter unverändert, Nachbesserung Team-Lead-Review):** Given eine
  Δ-Konstellation mit mindestens einer `ChangeSeverity.MAJOR`-Änderung / When der Alarm
  über `check_and_send_alerts()` protokolliert wird / Then steht `severity="HIGH"` im
  Eintrag; bei ausschließlich `MINOR`-Änderungen steht `"LOW"`, bei höchstens
  `MODERATE` steht `"MODERATE"`.
  - Test: drei Fixtures (nur MINOR / bis MODERATE / mit MAJOR), je ein Lauf, fixe
    Erwartungswerte `"LOW"` / `"MODERATE"` / `"HIGH"` prüfen.
  - Zweck (nicht Prüfbedingung): Die Umleitung durch
    `alert_urgency.urgency_from_changes()` darf das Ergebnis von `_highest_severity()`
    nicht verändern. Ein Vergleich gegen „den Zustand vor dem Umbau" wäre als AC
    untauglich — dieser Zustand existiert danach nicht mehr, ein solcher Test kann nie
    rot werden.

- **AC-9 (Case-Robustheit, Known-Bug der Ableitungsquelle):** Given zwei
  `NowcastResult`-Datensätze mit identischem fachlichem Inhalt, einer mit dem
  Original-Label aus `intensity_to_text()` („Mäßiger Regen"), einer mit der im
  Trip-Pfad üblichen Kleinschreibung des ersten Buchstabens („mäßiger Regen") / When
  beide durch `urgency_from_radar()` laufen / Then liefern beide `"MODERATE"` —
  identisch, unabhängig von der Schreibweise des Aufrufers.
  - Test: direkter Unit-Test auf `urgency_from_radar()` mit beiden Schreibweisen,
    Ergebnisse auf Gleichheit prüfen.

- **AC-10 (Label-Umbenennung an der Quelle bleibt korrekt eingestuft, Nachbesserung
  Team-Lead-Review):** Given `radar_service.INTENSITY_HEAVY` wird testweise per
  Monkeypatch auf einen anderen Text gesetzt (simuliert eine künftige Umbenennung des
  Labels an seiner Quelle) / When `intensity_to_text()` das umbenannte Label liefert und
  dieses durch `urgency_from_radar()` läuft / Then liefert die Funktion weiterhin
  `"HIGH"` — die Ableitung folgt der lebenden Konstante, nicht einem im neuen Modul
  hartkodierten Zeichenketten-Duplikat. Ohne diesen Mechanismus würde eine Umbenennung
  an der Quelle die Einstufung still auf `"LOW"` zurückfallen lassen, ohne dass ein Test
  es merkt.
  - Test: `monkeypatch.setattr(radar_service, "INTENSITY_HEAVY", "Kräftiger Regen")`,
    `radar_service.intensity_to_text(5.0)` aufrufen (liefert jetzt „Kräftiger Regen"),
    das Ergebnis durch `urgency_from_radar()` schleusen, `"HIGH"` erwarten.

- **AC-11 (E5, Trip-Bündelung Δ + amtlich):** Given ein Alarm-Lauf, in dem eine
  MINOR-Δ-Änderung UND eine rote amtliche Warnung (`level=4`) im selben Durchlauf in
  EINE Nachricht gebündelt werden (`check_and_send_alerts(..., official_notices=...)`,
  Muster #1088) / When protokolliert wird / Then trägt der EINE entstehende Eintrag
  `severity="HIGH"` — die höchste beteiligte Dringlichkeit gewinnt, nicht die der
  Δ-Änderung allein.
  - Test: `to_report` mit einer MINOR-Änderung UND `official_notices` mit `level=4`
    durch `check_and_send_alerts()` schleusen; genau ein neuer Eintrag entsteht, dessen
    `severity` `"HIGH"` ist.

- **AC-12 (E5, Ortsvergleich-Radar, mehrere Orte):** Given ein Ortsvergleich-Radar-Alarm
  mit zwei getriggerten Orten, **beide nicht konvektiv**, einer mit leichtem und einer mit
  mäßigem Regen / When protokolliert wird / Then steht im EINEN Log-Eintrag
  `severity="MODERATE"` — die schärfste beteiligte Einstufung.
  - Test: zwei konstruierte `NowcastResult`-Objekte (`INTENSITY_LIGHT`, `INTENSITY_MODERATE`),
    je einem getriggerten Ort zugeordnet, den einen entstehenden Eintrag prüfen.
  - 🔴 **Korrektur v1.3 (RED-Phase-Befund):** Die ursprüngliche Fassung („einer konvektiv,
    einer mäßig → `HIGH`") war **strukturell wertlos** — `HIGH` ist exakt der heutige feste
    Wert, der Test war ohne jede Implementierung grün und konnte die Bündelungs-Mechanik
    nie beweisen. Der Fall mit zwei nicht-konvektiven Orten ist der einzige, bei dem sich
    „höchste gewinnt" von der Altkonstante unterscheidet. Der konvektive Fall bleibt als
    **zusätzlicher** Regressionswächter erhalten, zählt aber nicht als Nachweis.
    (Muster: „prüft der Test, was er behauptet?" — vgl. #1457, #1435 E3a.)

- **AC-13 (E5, Ortsvergleich amtlich, mehrere Warnungen):** Given ein
  Ortsvergleich-amtlich-Alarm mit zwei getaggten Warnungen unterschiedlicher Orte,
  `level=2` (gelb) und `level=4` (rot) / When protokolliert wird / Then steht
  `severity="HIGH"` im EINEN Eintrag.
  - Test: zwei getaggte `OfficialAlert`-Objekte unterschiedlicher Stufe, Eintrag prüfen.

- **AC-14 (E6, Verhaltensneutralität des Versands, Nachbesserung Team-Lead-Review):**
  Given eine Tour mit aktivem E-Mail- und Telegram-Kanal und einer Δ-Änderung, die einen
  Alarm auslöst / When der Alarm läuft / Then wird die E-Mail-Senke **genau einmal** und
  die Telegram-Senke **genau einmal** aufgerufen, die SMS-Senke **kein Mal**, und
  `NotificationResult.sent_channels` ist exakt `{"email", "telegram"}`.
  - Test: Aufrufzähler der drei Senken auf `1` / `1` / `0` prüfen, `sent_channels` als
    Menge vergleichen.
  - Zusatz-Prüfung im selben Test: derselbe Lauf mit einer roten amtlichen Warnung
    (`level=4`) statt der Δ-Änderung liefert dieselben Zähler — die geänderte
    Einstufung verschiebt nichts am Versand.
  - Zweck (nicht Prüfbedingung): S3a darf den Versand nicht anfassen. Feste Zahlen statt
    eines Vergleichs mit „dem Stand vor dieser Scheibe" — Letzterer ist nach dem Umbau
    nicht mehr herstellbar und könnte deshalb nie rot werden.

- **AC-15 (E7, D4 — Eintragszahl und Ziel-Liste unverändert):** Given eine Tour hat vor
  dieser Scheibe N Einträge in `entries` / When zusätzlich ein amtlicher Alarm
  (`level=4`) protokolliert wird, der vor dieser Scheibe als `"MODERATE"` in `entries`
  gelandet wäre / Then liegt der neue Eintrag weiterhin in `entries` (nicht
  `not_delivered`), die Anzahl steigt um genau 1 auf N+1, und `not_delivered` bleibt
  unverändert — nur der `severity`-Wert im neuen Eintrag ändert sich (`"MODERATE"` →
  `"HIGH"`), nicht die Ziel-Liste.
  - Test: Eintragszähler beider Listen vor/nach dem Lauf, Prüfung dass der neue Eintrag
    in `entries` liegt.

- **AC-16 (Mandantentrennung, zwei Nutzer):** Given zwei Nutzer A und B, jeweils mit
  einer eigenen Tour und je einer roten amtlichen Warnung (`level=4`) im selben
  Testlauf, isoliert über `app.loader.get_data_dir` (kein gemeinsamer `data_dir`) / When
  beide Alarme protokolliert werden / Then trägt Nutzer As `alert_log.json` einen Eintrag
  mit `severity="HIGH"` für seine eigene Tour, Nutzer Bs eigene, getrennt gescopte Datei
  trägt ebenfalls `"HIGH"` für seine eigene Tour — keine Vermischung von Werten oder
  Dateien zwischen den beiden `data/users/<user_id>/`-Verzeichnissen, kein Rückfall auf
  `"default"`.
  - Test: zwei `TripAlertService(user_id=...)`-Instanzen mit unterschiedlichem
    `user_id` und eigenem Testdatenordner, beide Protokolldateien getrennt prüfen.

## Known Limitations

### 🔴 Die dritte Quelle ist ebenfalls konstant — nur auf einem Umweg (RED-Phase-Befund v1.3)

Diese Spec ging davon aus, die Vorhersage-Änderung sei „abgeleitet und korrekt" und nur Radar
und amtliche Warnung seien konstant. **Gemessen in der RED-Phase: das stimmt nicht.**

- `alert_preset.py:129` und `:210` setzen `severity=AlertSeverity.WARNING` **hart** für jede
  erzeugte Regel — für alle Empfindlichkeitsstufen (entspannt/standard/sensibel) und alle
  Metriken. Die Stufe steuert den **Schwellenwert**, nie die Dringlichkeit.
- `weather_change_detection.py:629-632`: liegt für eine Metrik ein `_severity_overrides`-Eintrag
  vor, gewinnt er; die ratio-basierte `_classify_severity()` (MINOR/MODERATE/MAJOR) wird dann
  **nie** aufgerufen. Für jede aus `expand_per_metric_levels()` erzeugte Regel existiert dieser
  Override — und das ist seit #946 die **einzige** Alarm-Quelle.

⇒ **Δ-Alarme tragen faktisch immer `MODERATE`**, unabhängig davon, wie stark die Vorhersage sich
geändert hat. Alle drei Quellen sind damit konstant eingestuft, nicht zwei von drei.

**Folge für diese Scheibe:** AC-8 lässt sich über die echte Pipeline nicht mit drei
unterschiedlichen Ergebnissen belegen (MINOR/MAJOR sind dort nicht erzeugbar). AC-8 prüft
deshalb die Gleichwertigkeit der Umleitung direkt an der Funktion
(`urgency_from_changes(changes) == _highest_severity(changes)` über handgebaute
`WeatherChange`-Listen) — das entspricht dem in der AC benannten Zweck. S3a lässt den Δ-Pfad
bewusst unverändert.

**Folge für S3b — blockierend:** Eine Kanal-Schwelle „nur das Dringendste" würde **sämtliche**
Vorhersage-Änderungsalarme unterdrücken, weil sie ausnahmslos `MODERATE` tragen. Die Schwelle
darf nicht scharf gestellt werden, bevor dieser Punkt entschieden ist. Eigenes Ticket, weil
nutzersichtbar (Cockpit-Farbe) **und** blockierend für die nächste Scheibe.

- **Numerische Regenrate verlässt `intensity_to_text()` nicht als Zahl.** Die Ableitung
  vergleicht weiterhin gegen ein deutsches Label, nicht gegen `max_rate` (mm/h,
  `radar_service.py:538`) selbst — jetzt aber gegen benannte Konstanten statt
  Zeichenketten-Duplikate (E3-Nachbesserung, AC-10 beweist die Live-Referenz). Eine
  Änderung der *numerischen Schwellen* in `intensity_to_text()` (z.B. `mm_per_h < 1.0`
  → `< 0.8`) bleibt außerhalb dieser Absicherung — sie verschiebt, WANN ein Label
  vergeben wird, nicht WELCHES Label welche Dringlichkeit bedeutet, und ist deshalb kein
  Regressionsrisiko dieser Scheibe.
- **Case-Robustheit ist auf `.lower()` begrenzt.** `urgency_from_radar()` normalisiert
  über `.strip().lower()`, was Trip- und Compare-Pfad abdeckt (AC-9). Ein dritter
  Aufrufer mit einer weiteren Normalform wäre ebenfalls abgedeckt, da `.lower()`
  generisch ist — kein expliziter Test dafür, da kein dritter Aufrufer existiert.
- **Level 1 wird wie eine unbekannte Stufe behandelt und ist im Betrieb unerreichbar.**
  `LEVEL_LETTERS` hat keinen Schlüssel `1`; Stufe 1 läuft daher in den konservativen
  Rückfall und liefert `HIGH`, nicht `LOW` (Korrektur v1.4, s. E2 — die frühere
  Behauptung „liefert `LOW`" war falsch und von keinem Test gedeckt). Kein Absturz, aber
  auch keine eigene AC: Eine AC muss Wirkung am Protokoll zeigen (CLAUDE.md), und diese
  Eingabe erreicht das Protokoll strukturell nicht — alle Quellen filtern `<2` weg. Stufen
  außerhalb 1–4 (fehlerhafte Provider-Daten) SIND dagegen praktisch erreichbar und
  daher mit AC-3 abgesichert.

## Nicht-Ziele

- **Kanal-Schwelle (S3b).** Diese Scheibe entscheidet nicht, ob eine Meldung einen Kanal
  erreicht — nur, welchen Wert `severity` im Protokoll trägt. `AlertChannelPicker.svelte`
  und jede Bedienoberfläche dafür bleiben unangetastet.
- **Ablösung von `MIN_SMS_LEVEL`.** Der bestehende Render-Filter
  (`hazard_symbols.py:37`) bleibt als Sicherheits-Filter für SMS/Telegram-Warntexte
  unverändert in Kraft — diese Scheibe berührt ihn nicht (die Ableitung nutzt
  stattdessen `LEVEL_LETTERS`, s. E2-Nachbesserung).
- **Änderung der Auslöse-Bedingungen.** Der Radar-Alarm feuert weiterhin nur bei
  `onset_minutes <= 20` (`trip_alert.py:75-78`); Ruhezeiten, Cooldown und Tages-
  Obergrenze bleiben unverändert.
- **Persistenz, Go, Frontend.** Kein neues Datenfeld, keine Migration, kein
  Go-Code, kein Frontend-Code — die Cockpit-Farbe ändert sich allein durch den neuen
  Dateninhalt.

## Regressionsgefahr

- Bestehende Tests, die `severity == "HIGH"` für einen Radar-Alarm bzw.
  `severity == "MODERATE"` für einen amtlichen Alarm als **feste** Erwartung
  hartkodieren, werden durch diesen Umbau potenziell rot, sobald ihre Fixture nicht
  zufällig den Wert erzeugt, der jetzt tatsächlich abgeleitet wird. Betroffene Kandidaten
  (gemessen, nicht abschließend geprüft): `tests/tdd/test_feature_656_radar_nowcast.py`,
  `tests/tdd/test_feature_660_convective_stage.py`,
  `tests/tdd/test_issue_1168_alert_engine_extract.py`, `tests/tdd/test_alert_log.py`.
  Jeder rote Fall ist einzeln zu prüfen: entweder war die Fixture zufällig
  `is_convective=True`/`level=4` (dann bleibt der Test grün) oder sie muss auf einen
  Wert korrigiert werden, der die jetzt korrekt abgeleitete Einstufung widerspiegelt —
  **nicht** die Schwelle aufweichen, um den alten (falschen) Wert künstlich zu erhalten.
- `DeviationAlertEngine._highest_severity()` wird weiterhin direkt UND indirekt (über
  `alert_urgency.urgency_from_changes()`) aufgerufen — ein versehentliches Duplizieren
  der Rangfolge-Logik (`LOW`/`MODERATE`/`HIGH` vs. `MINOR`/`MODERATE`/`MAJOR`) an zwei
  Stellen wäre ein Rückfall in die Wiederholungs-Klasse aus #1481; `urgency_from_changes()`
  delegiert deshalb, statt die Logik zu kopieren.
- **Named Constants sind additiv, kein Rename-Risiko für Dritte.** Kein anderer Ort im
  Repo vergleicht gegen die vier Intensitäts-Label-Strings (gemessen: nur
  `radar_service.py` selbst und ein Docstring-Beispiel in `radar_alert_service.py:47`)
  — die Einführung der Konstanten ändert keinen bestehenden String-Wert, nur seine
  Herkunft.
- `highest_urgency()` mit leerer Eingabe liefert `"LOW"` (kein beteiligtes Signal) — ein
  Aufrufer, der versehentlich eine leere Liste übergibt, obwohl mindestens eine Quelle
  vorliegt, würde eine Meldung stumm unterschätzen. Die sechs Aufrufstellen sind so
  gebaut, dass mindestens ein Element garantiert vorliegt (der Alarm wurde ja bereits
  ausgelöst); ein Test dafür wäre reine Kapazitätsprüfung ohne erreichbaren Effekt,
  daher keine eigene AC (s. Known Limitations).

## Prüfung mit zwei Nutzern

AC-16 verifiziert die Mandantentrennung explizit: zwei `TripAlertService`-Instanzen mit
unterschiedlichem `user_id`, je eigenem Testdatenordner (isoliert über
`app.loader.get_data_dir`, kein gemeinsamer `data_dir`, Muster #1265). Beide erhalten
im selben Testlauf eine rote amtliche Warnung; geprüft wird, dass jede Nutzer-Datei
ausschließlich den eigenen Eintrag trägt und `user_id` an keiner der sechs
Aufrufstellen auf `"default"` zurückfällt (CLAUDE.md-Pflicht für jeden
nutzerbezogenen Endpunkt/Dienst).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe führt keinen neuen Kanal, keinen neuen Provider, kein
  neues Datenmodell und keine neue Auth-/Deploy-Strategie ein — sie korrigiert die
  Berechnung eines bereits bestehenden Feldes (`severity`, eingeführt mit #1459). Kein
  ADR-relevanter Entscheidungsraum betroffen.

## Nebenbefund (nicht Teil dieser Scheibe, zur Kenntnis)

`notification_service.py:732` zählt den SMS-Kanal bereits als „gesendet"
(`sent_channels.append("sms")`), **bevor** der SMS-Text gerendert wird
(`render_official_alert_sms()` folgt erst danach). Bei einer amtlichen Warnung, die nach
Anwendung von `MIN_SMS_LEVEL` leergefiltert wird, protokolliert das Protokoll trotzdem
einen erfolgreichen SMS-Versand mit leerem Inhalt. Gehört nicht in diese Scheibe (S3a
ändert nur `severity`, nicht die Kanal-Logik) — Eintrag für das Sammel-Issue #1199.

## Changelog

- 2026-08-04: Initial spec created
- 2026-08-04 (v1.1): Team-Lead-Review — E2 nutzt `LEVEL_LETTERS` statt eigener
  Grenzziehung mit `MIN_SMS_LEVEL`+`4` (Duplikat einer bereits bestehenden Abbildung,
  AC-4 ersetzt die frühere MIN_SMS_LEVEL-AC, AC-3 neu für die Fallback-Richtung); E3
  vergleicht gegen benannte Konstanten in `radar_service.py` statt gegen
  Zeichenketten-Duplikate (AC-10 neu, `radar_service.py` kommt als MODIFY in die
  Dateiliste). Gesamtzahl ACs: 14 → 16.
- 2026-08-04 (v1.2): Team-Lead-Review — AC-8 (Δ-Wetter) und AC-14
  (Verhaltensneutralität des Versands) von „Vergleich mit dem Zustand vor dem Umbau"
  (strukturell nicht prüfbar) auf feste, absolute Erwartungswerte umformuliert (Bezug
  zum Altverhalten bleibt als Begründung im Fließtext, nicht in der Prüfbedingung).
  Wortwahl in den Radar-ACs (5, 6, 7, 12) von „gemocktes RadarNowcastService-Ergebnis"
  auf „ein konstruiertes NowcastResult als Eingangsdatum" geändert — vermeidet den
  Eindruck von Mock-Theater (CLAUDE.md Test-Politik), Inhalt unverändert. AC-Anzahl
  bleibt bei 16.
