---
entity_id: fix_1695_anker_ortsmitternacht
type: bugfix
created: 2026-11-05
updated: 2026-11-05
status: draft
workflow: fix-1695-anker-ortsmitternacht
version: "1.0"
tags: [alerts, compare, anchor, day-window, midnight, issue-1695]
---

# Ortsvergleich-Anker darf nicht auf zwei Kalendertage zerfallen (Issue #1695)

## Approval

- [ ] Approved

## Purpose

Beim Versand eines Ortsvergleich-Briefings schreibt das System für jeden Ort des Vergleichs einen Referenz-Wert (Δ-Anker), gegen den der 15-Minuten-Alarm später Änderungen misst. Heute löst jeder Ort seinen Zeitpunkt („jetzt") selbst auf. Fällt die Ortsmitternacht zwischen den Abruf von Ort 1 und Ort 2, tragen die Anker desselben Vergleichs verschiedene Kalendertage (`target_date`), und der Alarm meldet eine „Änderung", obwohl sich die Vorhersage nicht geändert hat. Diese Spec lässt den Schreibpfad **einen** Zeitpunkt je Vergleich festhalten und an alle Orte durchreichen. Herleitung: `docs/context/fix-1695-anker-ortsmitternacht.md`; Vorgänger und Ursprung des Befunds (Adversary-Finding F005): `docs/specs/modules/fix_1661_anker_vom_falschen_tag.md`.

## Source

- **File:** `src/services/scheduler_dispatch_service.py`
- **Identifier:** `_write_compare_alert_snapshots` (ab Zeile 1228; Orte-Schleife und `fetch()`-Aufruf in Zeile 1274-1290)
- Nebendateien: `src/services/compare_location_weather_source.py` (`CompareLocationWeatherSource.fetch`, `now = datetime.now(timezone.utc)` in Zeile 121), `src/services/point_weather.py` (Docstring des `LocationWeatherSource`-Protocols, Zeile 96-108).

> **Schicht-Hinweis:** ausschließlich Python-Core (`src/services/`). Kein Frontend, keine Go-API, kein Datenschema.

## Estimated Scope

- **LoC:** ca. +30 Produktivcode (inkl. Kommentare/Docstrings), ca. +20 in vier bestehenden Test-Attrappen, ca. +150 neue Tests.
- **Files:** 3 Produktivdateien, 4 bestehende Testdateien (Attrappen), 1 neue Testdatei.
- **Effort:** low. Neuer optionaler Parameter, Default = bisheriges Verhalten, keine Migration.

### Affected Files

| Datei | Änderungstyp | Beschreibung |
|---|---|---|
| `src/services/compare_location_weather_source.py` | MODIFY | `fetch()` bekommt keyword-only `now: Optional[datetime] = None` (tz-aware). Ersetzt `datetime.now(timezone.utc)` in Zeile 121 durch `now`, falls gegeben. Naives `now` → `ValueError`. `local_today` bleibt je Ort aus der Ortszeit |
| `src/services/scheduler_dispatch_service.py` | MODIFY | `_write_compare_alert_snapshots`: EIN `now = _datetime.now(_timezone_mod.utc)` vor der Orte-Schleife, bedingungslos in `zusatz` an jedes `fetch()`. Funktionssignatur bleibt unverändert |
| `src/services/point_weather.py` | MODIFY (nur Docstring) | `now` im Protocol-Docstring als optionales Schlüsselwort-Argument dokumentieren, wie `target_date`/`tage_ab_ortstag`. Protocol-Signatur bleibt ohne `now` |
| `tests/tdd/test_compare_anker_ortsmitternacht.py` | CREATE | Neue Tests AC-1 bis AC-8 |
| `tests/tdd/test_compare_briefing_anchor_and_memory_reset.py` | MODIFY | Attrappe `fetch()` Zeile 188-193: Parameter `now=None` ergänzen |
| `tests/tdd/test_compare_briefing_anchor_survives_dispatch_failure.py` | MODIFY | Attrappe `fetch()` Zeile 96-99: Parameter `now=None` ergänzen |
| `tests/tdd/test_compare_alert_dedup_briefing_reset.py` | MODIFY | Attrappe `fetch()` Zeile 101-104: Parameter `now=None` ergänzen |
| `tests/tdd/test_compare_alert_day_window.py` | MODIFY | `SpionierendeQuelle.fetch()` Zeile 415-423: `now=None` ergänzen UND an `super().fetch(...)` durchreichen (echte Unterklasse, delegiert an den Prüfling) |

### Prüfung der Test-Attrappen (Pflicht-Befund, per grep belegt)

Der Schreibpfad ruft `fetch()` künftig **bedingungslos** mit `now=` auf. Eine Attrappe ohne diesen Parameter wirft dann `TypeError`, den die fail-soft-Schleife (`except Exception` → `logger.warning`) **still verschluckt**: Es entstünde kein Anker, kein Test fiele durch Fehlermeldung auf, nur Tests, die den Anker lesen, würden unerklärlich rot (oder, schlimmer, grün, weil sie den Anker gar nicht prüfen).

**Erreichen den Schreibpfad (müssen `now` bekommen).** Alle vier werden per `monkeypatch.setattr(quelle_mod, "CompareLocationWeatherSource", ...)` in `_write_compare_alert_snapshots` eingeschleust:

- `tests/tdd/test_compare_briefing_anchor_and_memory_reset.py:188` (`_ScriptedWeatherSource.fetch`, Patch Zeile 284)
- `tests/tdd/test_compare_briefing_anchor_survives_dispatch_failure.py:96` (Patch Zeile 175)
- `tests/tdd/test_compare_alert_dedup_briefing_reset.py:101` (Patch Zeile 188)
- `tests/tdd/test_compare_alert_day_window.py:415` (`SpionierendeQuelle`, Patch Zeile 427)

**Erreichen den Schreibpfad NICHT (bleiben unverändert).** Sie werden über die Konstruktor-Naht `CompareAlertService(weather_source=...)` eingespeist, also nur auf der Leseseite (`compare_alert.py`), die `now` nicht übergibt:

- `tests/tdd/_compare_alert_parallel_fixtures.py:212` (`WetterRand`)
- `tests/test_alert_stumme_ausfaelle.py:272` (`_OrtsWetterRand`)
- `tests/test_alarm_bausteine_nutzersprache.py:99`, `tests/tdd/test_compare_alert_email_off.py:138`, `tests/tdd/test_compare_alert_metric_gating.py:97` (diese drei kennen nicht einmal `tage_ab_ortstag`, können den Schreibpfad also schon heute nicht bedienen)
- `tests/tdd/test_compare_anchor_target_date.py:68` (`SpionierendeQuelle`, nur über `weather_source=`)

**Ersetzen die ganze Schreibfunktion (unberührt, solange deren Signatur gleich bleibt):** alle Tests mit `monkeypatch.setattr(..., "_write_compare_alert_snapshots", lambda *a, **k: None)` bzw. `_zaehlen`/`_handversand_fixtures.py:243`. Deshalb ändert diese Spec die Signatur von `_write_compare_alert_snapshots` bewusst **nicht**.

**Unberührt, weil echte Quelle:** `tests/tdd/test_ortsvergleich_hoehe_und_cache.py:225` ruft `_write_compare_alert_snapshots` mit der echten `CompareLocationWeatherSource` auf.

Die Umsetzung muss mit einem Guard prüfen, dass kein weiterer Treffer übersehen wurde: Nach der Änderung muss ein grep nach `monkeypatch.setattr(.*"CompareLocationWeatherSource"` genau die vier obigen Dateien liefern (plus ggf. neue Test-Datei).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `CompareLocationWeatherSource.fetch` | function | nimmt neuen optionalen `now` entgegen |
| `tz_for_coords`, `local_dt` (`utils.timezone`) | function | bilden weiterhin je Ort den lokalen Kalendertag aus `now` |
| `day_window.window_end_utc_exclusive`, `_window_bound` | function | Fensterbildung, semantisch unverändert |
| `CompareWeatherSnapshotService` | class | speichert die Anker je (Preset, Ort) unter `data/users/<user_id>/`; unverändert |
| `compare_alert.py::_evaluate_one_location` (Leseseite, #1661) | function | liest `target_date` aus dem Anker; **bleibt unverändert** |
| `tests/tdd/test_compare_alert_day_window.py` (`Szenario`, `SkriptierterOpenMeteo`, `Wetterlage`) | test helper | Vorbild für den neuen Test: echter Sendepfad, nur Provider-Rand und Uhr gestellt |
| `docs/specs/modules/fix_1661_anker_vom_falschen_tag.md` | doc | Vorgänger; Known Limitation Punkt 2 wird hier geschlossen |

## Implementation Details

**Schreibseite (`scheduler_dispatch_service.py`).** Vor der Schleife über `locations` wird genau einmal `now = _datetime.now(_timezone_mod.utc)` bestimmt (die beiden Namen sind im Modul bereits importiert, Zeile 10). Der Wert wird in `zusatz` neben `tage_ab_ortstag`, `elevation_m` und `user_id` an **jedes** `fetch()` übergeben. Die Übergabe ist **bedingungslos** (gleiche Begründung wie bei `elevation_m`, Issue #1991): `CompareLocationWeatherSource` ist die einzige Schreib-Implementierung; eine konditionale Weitergabe ließe eine Implementierung ohne den Parameter still mit eigener Uhr weiterlaufen, also genau den Fehler, den diese Spec behebt. Der Wert wird durchgereicht, nie nachträglich berechnet (Muster #1661 F003).

**Lesende Quelle (`compare_location_weather_source.py`).** `fetch()` bekommt `now: Optional[datetime] = None` als Schlüsselwort-Argument (hinter `*`, neben `user_id`). Ablauf:

```
if now is None:
    now = datetime.now(timezone.utc)
elif now.tzinfo is None or now.utcoffset() is None:
    raise ValueError("... `now` muss zeitzonen-bewusst (tz-aware) sein ...")
else:
    now = now.astimezone(timezone.utc)
```

Die Prüfung auf naives `now` steht früh, noch vor dem Provider-Zugriff, analog zur bestehenden `ValueError`-Prüfung für `target_date`/`tage_ab_ortstag`. Es gibt keinen stillen Rückfall auf die Systemuhr. Die Normalisierung auf UTC hält die Stundenrundung im Mitternachts-Fallback (`now.replace(minute=0, ...)`, Zeile 154) unabhängig von der Zeitzone des Aufrufers.

`local_today = local_dt(now, tz).date()` bleibt **je Ort** aus der Ortszeit gebildet (Kamtschatka/UTC+12-Fall aus #1661 bleibt gültig). Fensterbildung (`window_day`, `window_start`, `window_end`) und der Mitternachts-Fallback sind unverändert; dort ist `now` weiterhin der Fensterbeginn, nur ist er jetzt für alle Orte derselbe Moment.

**Leseseite (`compare_alert.py`).** Unverändert. Der 15-Minuten-Check übergibt `now` nicht und liest den Tag aus dem Anker (`target_date`); jede Leseseiten-Änderung wäre Scope-Überschreitung.

**Protocol (`point_weather.py`).** Nur der Docstring wird ergänzt: Implementierungen dürfen zusätzlich `now` (tz-aware) annehmen, mit dem der Schreibpfad einen einzigen Zeitpunkt über alle Orte eines Vergleichs festhält. Die Protocol-Signatur bleibt ohne `now`, weil Aufrufer es nur auf der Schreibseite durchreichen (wie bei `target_date`/`tage_ab_ortstag`).

**Bewusst verboten:** ein Wächter „Anker-Tag == Mail-Tag". Er würde für jeden Ort ab UTC+6 östlich bzw. UTC-7 westlich dauerhaft feuern, weil dort absoluter Mail-Tag und ortslokaler Anker-Tag per Konstruktion abweichen, und risse damit F002 aus #1661 wieder auf.

## Expected Behavior

- **Input:** Ein Ortsvergleich-Briefing wird versendet; `_write_compare_alert_snapshots` schreibt für alle Orte des Presets den Anker.
- **Output:** Alle Anker eines Presets in einem Lauf beruhen auf demselben Zeitpunkt. Liegt zwischen Ort 1 und Ort 2 eine Ortsmitternacht (Uhr springt), tragen beide Anker dasselbe `target_date`. Der Versatz `tage_ab_ortstag` (Morgen-Slot 0, Abend-Slot +1) wirkt weiterhin ortslokal.
- **Side effects:** Keine. Dateinamen, Schema und Ablageort der Anker bleiben unverändert; keine Migration. `fetch()` ohne `now` (Leseseite, direkte Aufrufer) verhält sich wie bisher.

## Test Plan

Alle Tests laufen in der Kern-Schicht (deterministisch, kein Netz). Kein Mock-Theater: echter Aufruf von `_write_compare_alert_snapshots` mit echter `CompareLocationWeatherSource`; nur der Provider-Rand (`SkriptierterOpenMeteo` über die Provider-Registry) und die Uhr sind gestellt (Muster `Szenario` aus `test_compare_alert_day_window.py`). Die Uhr der Quelle wird wie dort über `datetime` in `compare_location_weather_source` gestellt; für den Sprung-Test liefert sie bei aufeinanderfolgenden Aufrufen 23:59 und 00:01 Ortszeit, die Uhr des Dispatch-Moduls (`_datetime` in `scheduler_dispatch_service`) einen festen Wert vor der Mitternacht.

### Automated Tests (TDD RED)

- [ ] Test 1 (AC-1, rot vor dem Fix): GIVEN Preset mit zwei Orten WHEN die Uhr zwischen dem Abruf von Ort 1 und Ort 2 über die Ortsmitternacht springt UND `_write_compare_alert_snapshots` läuft THEN tragen beide gespeicherten Anker dasselbe `target_date`.
- [ ] Test 2 (AC-2): GIVEN `fetch()` ohne `now` WHEN die Uhr gestellt ist THEN entspricht der Ortstag der gestellten Uhr wie vor dem Fix.
- [ ] Test 3 (AC-3): GIVEN `fetch()` mit `now` und eine abweichende Systemuhr WHEN Orte in UTC+12 und UTC-7 abgerufen werden THEN stammt der Ortstag je Ort aus `now`.
- [ ] Test 4 (AC-4): GIVEN naives `now` WHEN `fetch()` aufgerufen wird THEN `ValueError`.
- [ ] Test 5 (AC-5): GIVEN ein Ort wirft beim Abruf WHEN der Schreibpfad läuft THEN liegen die Anker der anderen Orte vor, der Lauf bricht nicht ab.
- [ ] Test 6 (AC-6): GIVEN zwei Nutzer mit je einem Preset WHEN beide Anker schreiben THEN liegt jeder Anker nur im Bereich seines Nutzers.
- [ ] Test 7 (AC-7): Bestehende #1661-Tests (`test_compare_anchor_target_date.py`, `test_compare_alert_day_window.py`) bleiben unverändert grün.
- [ ] Test 8 (AC-8): GIVEN die Attrappen der vier Bestandsdateien WHEN der Schreibpfad läuft THEN existiert für jeden Ort ein Anker (Schutz gegen den verschluckten `TypeError`).

## Acceptance Criteria

- **AC-1:** Given ein Ortsvergleich-Preset mit zwei Orten und eine Uhr, die zwischen dem Abruf von Ort 1 und Ort 2 über die Ortsmitternacht springt / When der Anker-Schreiber `_write_compare_alert_snapshots` beide Orte speichert / Then tragen beide gespeicherten Anker dasselbe `target_date`, und der Änderungs-Alarm vergleicht den ganzen Vergleich gegen einen einheitlichen Tag.
  - Test: Kern. Echter Aufruf von `_write_compare_alert_snapshots` mit echter `CompareLocationWeatherSource`, nur Provider-Rand und Uhr gestellt. Die Anker werden über `CompareWeatherSnapshotService.load()` gelesen; beide `target_date` müssen gleich sein. Vor dem Fix rot (Ort 1 trägt den alten, Ort 2 den neuen Tag).

- **AC-2:** Given `fetch()` wird ohne den neuen Parameter `now` aufgerufen (Leseseite, 15-Minuten-Check, direkte Aufrufer) / When die Quelle den Wetterabruf aufbaut / Then verhält sie sich exakt wie vor dieser Änderung: Der Kalendertag stammt aus der Systemuhr des Aufrufs, in der Ortszeit des Ortes.
  - Test: Kern. Uhr auf einen festen Moment stellen, `fetch()` ohne `now` aufrufen; Fenster und Ortstag stimmen mit dem Bestandsverhalten überein (Regression gegen `test_compare_alert_day_window.py`).

- **AC-3:** Given `fetch()` wird mit einem tz-aware `now` aufgerufen, das von der Systemuhr abweicht, und Orte in Kamtschatka (UTC+12) sowie in Kalifornien (UTC-7) / When die Fenster gebildet werden / Then nutzt jeder Ort dieses `now` als Zeitpunkt und bildet seinen Kalendertag weiterhin aus der eigenen Ortszeit, sodass der Ortstag je Ort richtig bleibt.
  - Test: Kern. Dasselbe `now` an Ort West und Ort Ost übergeben, Systemuhr auf einen anderen Tag stellen. Assert: Das gespeicherte `target_date` (mit `tage_ab_ortstag`) folgt dem Ortstag aus `now`, nicht der Systemuhr, und die beiden Orte können sich korrekt um einen Tag unterscheiden (Kamtschatka-Test aus #1661 bleibt gültig).

- **AC-4:** Given `fetch()` wird mit einem naiven `now` (ohne Zeitzone) aufgerufen / When die Quelle den Aufruf prüft / Then wirft sie `ValueError` mit verständlicher Meldung, statt still auf die Systemuhr zurückzufallen.
  - Test: Kern. `fetch(..., now=datetime(2026, 11, 5, 12, 0))` mit `pytest.raises(ValueError)`; zusätzlich Assert, dass der Provider nicht aufgerufen wurde (frühe Prüfung).

- **AC-5:** Given ein Ort des Vergleichs wirft beim Abruf einen Fehler / When `_write_compare_alert_snapshots` die Orte nacheinander schreibt / Then werden die Anker aller übrigen Orte trotzdem geschrieben und der bereits erfolgte Versand wird nicht beeinträchtigt (fail-soft je Ort bleibt).
  - Test: Kern. Drei Orte, mittlerer wirft am Provider-Rand. Assert: Anker für Ort 1 und 3 liegen vor, für Ort 2 nicht, Funktion kehrt ohne Ausnahme zurück.

- **AC-6:** Given zwei verschiedene Nutzer (`user_id`) mit je einem Ortsvergleich-Preset / When beide Schreibläufe nacheinander ausgeführt werden / Then landet jeder Anker im Snapshot-Bereich des eigenen Nutzers und kein Anker im Bereich des anderen.
  - Test: Kern. Zwei Nutzerverzeichnisse; nach beiden Läufen `CompareWeatherSnapshotService(user_id=A/B).load()` prüfen: jeder Nutzer sieht nur seine Anker, `user_id` kommt aus dem Aufruf, nie `"default"`.

- **AC-7:** Given die Leseseite `compare_alert.py` und die bestehenden Tests zu #1661 / When die Änderung umgesetzt ist / Then bleibt die Leseseite unverändert und alle bestehenden #1661-Tests laufen grün durch.
  - Test: Kern. `test_compare_anchor_target_date.py` und `test_compare_alert_day_window.py` laufen unverändert (bis auf die Attrappen-Signatur) grün (Verhaltensnachweis der unveränderten Leseseite, kein Diff-Check).

- **AC-8:** Given der Schreibpfad übergibt `now` bedingungslos an `fetch()` und die vier Test-Attrappen der Bestandsdateien (siehe „Prüfung der Test-Attrappen") / When der Briefing-Versand den Anker schreibt / Then liegt für jeden Ort tatsächlich ein Anker vor, es wird also kein `TypeError` durch die fail-soft-Schleife still verschluckt.
  - Test: Kern. In den vier Bestandsdateien bzw. im neuen Test: nach dem Schreiblauf `CompareWeatherSnapshotService.load()` je Ort nicht leer; ein Test ohne diese Prüfung gilt als unzureichend. Mutations-Gegenprobe: Wird `now` aus einer Attrappe wieder entfernt, muss mindestens ein Test rot werden.

## Known Limitations

- **Fenster 1 (bewusst nicht gelöst).** Überschreitet ein Ort seine Ortsmitternacht **zwischen** der Fälligkeits-Sammlung in `compare_slot_scheduler` und dem Schreiben des Ankers, wandert der Bezugspunkt der Tagesbildung weiter. Dieser Zeitpunkt wird **nicht** bis ins Schreiben durchgereicht. Der Versatz `tage_ab_ortstag` bleibt richtig, der Anker-Satz bleibt in sich einheitlich (er beruht ab dem Schreibbeginn auf einem Moment); es entsteht kein zerfallener Anker-Satz mehr. Das Restrisiko ist ein einheitlich um einen Tag verschobener Satz in einem Zeitfenster von Sekunden bis Minuten rund um die Ortsmitternacht. Die Entscheidung ist festgelegt, kein offener Punkt.
- Die Leseseite (`compare_alert.py`) übergibt weiterhin kein `now`; sie braucht keines, weil sie den Tag aus dem Anker liest.
- Das Protocol `LocationWeatherSource` kennt `now` nicht; fremde Implementierungen für den Schreibpfad müssten `now` annehmen (heute existiert nur `CompareLocationWeatherSource`).
- Die UTC-Normalisierung von `now` ändert nichts am fachlichen Ergebnis, sondern verhindert nur zeitzonenabhängige Rundungsfehler im Mitternachts-Fallback.

## Kanäle

Die Änderung betrifft ausschließlich den **Anker**, also die Vergleichsbasis des Änderungs-Alarms (Δ-Alarm). Briefing- oder Alarm-**Inhalt** wird nicht direkt verändert, weder Text noch Format noch Schwellen. Der Δ-Alarm erreicht alle vier Kanäle gleichrangig (E-Mail, Telegram, SMS, Premium-SMS; ADR-0095, Alarme erreichen alle Kanäle, #1701). Ein zerfallener Anker erzeugte einen Änderungsalarm ohne geänderte Vorhersage, und zwar auf jedem dieser Kanäle. Der Fix beseitigt die Ursache an der gemeinsamen Quelle (dem gespeicherten Anker), sodass auf allen vier Kanälen keine falschen Änderungsalarme aus dieser Ursache mehr entstehen. Kanal-spezifischer Code wird nicht angefasst, eine kanalbezogene Prüfung ist deshalb nicht nötig.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Fix setzt bestehende Entscheidungen konsequent um und trifft keine neue: Er folgt dem Muster „Werte durchreichen, nie nachträglich berechnen" aus #1661 (F003) und der Pflicht, Anker und Frisch-Abruf strukturell am selben Code zu halten (Issue #1169, ADR-0021). Er fügt der Quelle einen optionalen Parameter hinzu, ändert weder Datenmodell noch Kanäle, Provider, Auth oder Test-/Deploy-Strategie. Der verbotene Wächter „Anker-Tag == Mail-Tag" ist bereits in der Vorgänger-Spec begründet abgelehnt.

## Changelog

- 2026-11-05: Initial spec created (Issue #1695, Folge von #1661 Finding F005).
