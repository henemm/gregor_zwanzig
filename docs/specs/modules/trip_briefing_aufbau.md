---
entity_id: trip_briefing_aufbau
type: refactor
created: 2026-11-18
updated: 2026-11-18
status: draft
version: "1.0"
workflow: feat-3128-trip-gemeinsamer-berichtsaufbau
tags: [trip, briefing, vorschau, versand, paritaet, 3128]
---

# Trip-Briefing: gemeinsamer Berichtsaufbau fuer Vorschau und Versand

## Approval

- [ ] Approved

## Purpose

Das Trip-Briefing setzt seinen Bericht heute an zwei Stellen zusammen: im Versand
(`TripReportSchedulerService._briefing_bauen_und_senden`) und in der Vorschau
(`PreviewService._build_report`). Ein neuer Baustein `src/services/trip_briefing_aufbau.py`
wird die einzige Stelle, die Segmente, Zeitzone, Render-Optionen, Wetterabruf, Anreicherung
(Wetterlage, Etappe, Nacht, Trend, Gewitter) und den Render-Aufruf zusammensetzt. Versand =
Baustein + Seiteneffekte + Senden, Vorschau = Baustein. Das ist ein reiner Refactor: der
Versandinhalt bleibt byte-gleich, das Vorschau-Verhalten bleibt in diesem Ticket unveraendert.

## Source

- **File:** `src/services/trip_briefing_aufbau.py` (neu)
- **Identifier:** `trip_segmente_bauen`, `trip_wetter_laden`, `trip_anreicherung_bauen`, `trip_report_rendern`, `trip_briefing_bauen`

> **Schicht:** ausschliesslich Python-Core (`src/services/`). Kein Frontend, keine Go-API.
>
> **Trip/Ortsvergleich-Teilung:** Das Compare-Pendant `compare_briefing_aufbau` (#2983) existiert
> bereits; dieser Baustein folgt demselben Muster (kleine Funktionen ohne Nebenwirkungen in einem
> Modul, Aufrufer loesen zur Laufzeit auf). Die Bausteine bleiben getrennte Module, weil Trip- und
> Compare-Wetterlauf unterschiedliche Stufen haben (Etappen, Nacht, Trend gegen Orte, Profil);
> es entsteht kein zweiter Editor- oder UI-Code.
>
> **Mandantentrennung:** `user_id` kommt vom Aufrufer (Auth-Kontext bzw. Scheduler-Nutzer),
> nie `"default"`. Tests mit zwei verschiedenen Nutzern.
>
> **Kanaele:** E-Mail, SMS (160), Premium-SMS und Telegram (kurz/lang) bleiben im Inhalt
> byte-gleich. Premium-SMS nutzt weiter den SMS-Text und wird nur im Versand zugestellt.

## Estimated Scope

- **LoC:** +~350 / -~400 Produktionszeilen (Verschiebung zaehlt als hinzugefuegt), plus ~250 Testzeilen
- **Files:** 7 (4 Quelldateien: 1 neu, 3 geaendert, `notification_service.py` nur falls noetig; 3 Testdateien, davon 2 nur falls noetig)
- **Effort:** high (Risiko hoch, weil jeder Trip-Versand durch den Umbau laeuft)
- **LoC-Limit:** `loc_limit_override 500` ist noetig. Das Standardlimit von 250 hinzugefuegten
  Zeilen pro Workflow wird ueberschritten, weil die Verdrahtung nicht neu geschrieben, sondern aus
  `_briefing_bauen_und_senden` (ca. 580 Zeilen) und `_build_report` (ca. 250 Zeilen) in den
  Baustein verschoben wird; verschobene Zeilen zaehlen als hinzugefuegt. Ein Aufteilen nach
  Funktionen waere nicht allein lieferbar, weil Versand und Vorschau sonst voruebergehend zwei
  halbe Bausteine haetten. Die Drift-Angleichung der Vorschau (zusaetzliche ca. 250 Zeilen)
  ist bewusst in #3144 ausgelagert. Der Umbau erfolgt in Etappen (Golden zuerst), damit jedes Delta klein bleibt.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `services.trip_report_scheduler` (`_convert_trip_to_segments`, `_build_stage_trend`, `_build_thunder_forecast_from_trend_or_fetch`) | module | Teilschritte, vom Baustein zur Laufzeit ueber das uebergebene Scheduler-Objekt aufgeloest, NICHT auf Modulebene importiert |
| `services.preview_service` | module | Aufrufer (Fassade); darf vom Baustein NICHT importiert werden |
| `services.segment_weather` (`night_weather_needed`, `fetch_night_weather`) | module | Nachtwetter |
| `services.weather_pattern` (`WeatherPatternService`) | module | Wetterlage |
| `output.renderers.trip_report.TripReportFormatter` | module | Render-Weg E-Mail, SMS, Telegram (unveraendert) |
| `services.report_config_resolver.resolve_report_render_options` | module | Render-Optionen |
| `utils.timezone.tz_for_coords` | module | Zeitzone der Etappe |
| `services.forecast_budget` | module | Kontingent; bleibt im Versand zwischen Wetterabruf und Rendern |
| `services.notification_service.send_trip_report` | module | Zustellung, `has_gap`, `undelivered`; Inhalt unveraendert |
| `tests/helpers/trip_vorschau_bericht.py` und ca. 28 Testdateien | test | rufen `_build_report` und `render_sms_preview` direkt; Signatur und Rueckgabe-Tupel sind Vertrag |
| `tests/tdd/test_bug_397_output_localtime.py`, `tests/tdd/test_issue_1004_ssot_callers.py` | test | `inspect.getsource`-Pruefungen auf Fassaden-/Versandquelltext, vorab pruefen und minimal anpassen |
| `tests/tdd/test_einstellung_gleich_mail_trip.py` | test | bestehendes Mail-Golden des Trip-Versands |

## Implementation Details

**Aufteilung des Bausteins.** Der Versand hat fachlich festgelegte Zwischenstopps: `no_stage`,
Wetterabruf, Kontingent-Abbruch (`manuell_abgelehnt`, #2961) nach dem Wetterabruf und vor dem
Rendern, `no_weather`-Regel (#1113 Ausfallschwelle), Anker-Pfad (#1629) und Marker/Logs nach
dem Versand, dazu die Phasenuhr (`uhr.wechsel`). Ein Rundum-Aufruf wuerde diese Reihenfolge
veraendern. Deshalb besteht der Baustein aus kleinen Funktionen in EINEM Modul; der Versand
ruft sie einzeln an den heutigen Stellen, die Vorschau ruft den Gesamtaufruf:

1. `trip_segmente_bauen(scheduler, trip, target, persist)`: Segmente je Etappe und Tag.
   `persist=False` fuer die Vorschau (kein Backfill, #2036). Test-Fallback (#768), Klemmen
   (#1325, #2417) und `_last_converted_trip`-Tausch bleiben im Versand.
2. `trip_wetter_laden(...)`: Hauptabruf des Wetters. Wind-Exposition und DWD-Vorwaermen sind
   Schalter nur fuer den Versand.
3. `trip_anreicherung_bauen(..., trend_parallel=False)`: Wetterlage, Etappe/Name/Stats,
   Nachtwetter, Trend, Gewitter. Die Vorschau setzt `trend_parallel=True` (Trend im eigenen
   Thread, #1839), der Versand bleibt seriell mit Phasenuhr.
4. `trip_report_rendern(..., has_gap, lang, undelivered, vortag, starkregen)`: der eine
   Render-Weg (`TripReportFormatter`) fuer E-Mail, SMS und Telegram. Die Vorschau uebergibt
   heute `has_gap=False`, keine Sprache, keine Zusatzbloecke; der Versand seine heutigen Werte.
5. `trip_briefing_bauen(...)`: Gesamtaufruf 1 bis 4 nur fuer die Vorschau; Rueckgabe wie bisher
   `(report, segment_weather, stage_name, trip_tz)` ueber die Fassade.

Ohne Nebenwirkungen im Baustein: kein Versand, kein Kontingent, kein Anker, keine Marker, keine
Persistenz, keine Schreibzugriffe im Nutzerverzeichnis. Phasenuhr, Logs, Anker, Marker und
Kontingent liegen ausschliesslich im Scheduler.

**Zirkelimport.** Der Baustein importiert weder `trip_report_scheduler` noch `preview_service`
auf Modulebene. Der Scheduler wird als Objekt uebergeben und seine Methoden werden zur
Laufzeit aufgeloest (wie bei `compare_briefing_aufbau`). Kein Alt-Name wird entfernt.

**Versand (`_briefing_bauen_und_senden`).** Name und Signatur unveraendert. Reihenfolge der
Zwischenstopps, Phasenuhr, Anker, Marker, Logs, `_last_converted_trip`-Tausch und Test-Fallback
bleiben in heutiger Reihenfolge im Scheduler; nur der jeweilige Aufbauschritt wird durch den
Aufruf der Baustein-Funktion ersetzt.

**Vorschau (`PreviewService._build_report`).** Bleibt Fassade: Signatur, Rueckgabe-Tupel
`(report, segment_weather, stage_name, trip_tz)` und die `vorschau_*`-Fehlercodes unveraendert.
Trend laeuft weiter nebenlaeufig (#1839), `persist_backfill=False` (#2036) bleibt, der
Demo-FixtureProvider (#483) bleibt. `render_sms_preview` bleibt einziger oeffentlicher Einstieg
(API `GET /api/preview/{trip_id}/sms`, `scripts/premium_sms_preflight_check.py`).

**Bewusst NICHT in diesem Ticket (Out of Scope, #3144).** Die vier SMS-sichtbaren Abweichungen
der Vorschau gegen den Versand bleiben unveraendert bestehen: amtliche Warnungen werden in der
Vorschau nicht geladen, `has_gap` bleibt in der Vorschau `False`, das Nachtwetter-Gate der
Vorschau (nur bei `night_weather_needed`) bleibt, der Test-Fallback bleibt nur im Versand. Die
Angleichung folgt in #3144, damit dieser Umbau byte-gleich pruefbar bleibt.

**Quelltext-Tests (geprueft).** `tests/tdd/test_bug_397_output_localtime.py` und
`tests/tdd/test_issue_1004_ssot_callers.py` lesen per `inspect.getsource` Quelltext der
Fassade bzw. des Versands. Wandert ein geprueftes Symbol in den Baustein, wird nur die
Fundstelle der Pruefung verschoben, die Zusicherung (Ortszeit-Ausgabe, einzelne SSOT-Aufrufer)
bleibt inhaltlich bestehen.

## Expected Behavior

- **Input:** Scheduler-Objekt, Trip, Zieltag, `user_id`, Render- und Versandschalter (Aufrufer-seitig).
- **Output:** Segmente, Wetter, Anreicherung und der gerenderte Bericht (E-Mail, SMS, Telegram); Vorschau liefert das bisherige Tupel.
- **Side effects:** keine im Baustein. Der Wetterabruf verbraucht Abrufbudget des uebergebenen Nutzers wie bisher.

## Test Plan

### Automated Tests (TDD RED)

- [ ] Golden-Test Versand (Characterization, VOR dem Umbau gegen den Ist-Stand gruen, danach unveraendert): GIVEN ein Trip mit festen Etappen und deterministischen Wetterdaten (Fixture-Provider, Sinks statt Mocks) WHEN der Trip-Versand laeuft THEN sind Mail (Betreff, HTML, Text), SMS (160 Zeichen), Premium-SMS und Telegram (kurz und lang) byte-gleich zu den vorher festgehaltenen Werten. Datei `tests/tdd/test_trip_briefing_aufbau.py`; bestehendes Mail-Golden `tests/tdd/test_einstellung_gleich_mail_trip.py` bleibt gruen.
- [ ] Vorschau-Verhalten unveraendert: GIVEN derselbe Trip WHEN `render_sms_preview` und `_build_report` laufen THEN gleiche SMS und gleiches Rueckgabe-Tupel wie vor dem Umbau (inkl. `vorschau_*`-Fehlercodes).
- [ ] Mandantentrennung: GIVEN zwei Nutzer mit je eigenem Trip WHEN Vorschau und Versand fuer Nutzer A laufen THEN erscheint nichts von Nutzer B, die `user_id` im Wetterabruf ist echt (nie `"default"`).
- [ ] Reihenfolge Versand: GIVEN erschoepftes Kontingent im Handversand THEN Abbruch nach Wetterabruf und vor jedem Rendern; GIVEN kein Wetter THEN `no_weather` ohne Mail; GIVEN keine Etappe THEN `no_stage`.
- [ ] Struktur: Der Baustein ist in einem frischen Prozess importierbar, ohne dass `trip_report_scheduler` oder `preview_service` geladen werden.
- [ ] Seiteneffektfreiheit: Vorschau-Aufruf mit Verzeichnis-Snapshot vorher/nachher; Sinks werden nie aufgerufen.
- [ ] Ein Baustein, zwei Aufrufer: eine Aenderung am Baustein (Test-Ersatzfassung) wirkt in Vorschau UND Versand.
- [ ] Regressionswaechter: die ca. 28 Testdateien auf `_build_report`/`render_sms_preview`, `test_bug_397_output_localtime.py`, `test_issue_1004_ssot_callers.py` laufen gruen (die beiden Quelltext-Tests mit minimal verschobener Fundstelle).
- [ ] Mail-Validator `.claude/hooks/briefing_mail_validator.py` gegen echt zugestellte Staging-Mail: Exit 0 (Deploy-Nachweis, Renderer-Commit-Gate).

## Definition of Done

- [ ] Golden-Tests des Versands vor dem Umbau gegen den Ist-Stand gruen, nach dem Umbau unveraendert gruen (AC-1, AC-2)
- [ ] AC-3 bis AC-8 durch deterministische Kern-Tests ohne Mock-Theater belegt
- [ ] AC-9: `briefing_mail_validator.py` gegen echt zugestellte Staging-Mail Exit 0
- [ ] Adversary-Verdict VERIFIED inkl. Mutations-Gegenprobe, alle 6 CI-Checks gruen, Produktion ausgeliefert, Selftest gruen

## Acceptance Criteria

- **AC-1:** Given ein Trip mit festen Etappen und gleichen Wetterdaten / When der Versand vor und nach dem Umbau laeuft / Then sind Mail (Betreff, HTML, Text), SMS (160 Zeichen), Premium-SMS und Telegram (Kurz- und Langform) byte-gleich zu vorher.
  - Test: Golden-Test mit Sinks und deterministischen Fixture-Wetterdaten, Soll-Werte VOR dem Umbau gegen den Ist-Stand erfasst, ohne Mock-Theater.
- **AC-2:** Given dieselbe Eingabe fuer die SMS-Vorschau und das Rueckgabe-Tupel / When die Vorschau nach dem Umbau erzeugt wird / Then entspricht sie in SMS-Text, Tupel `(report, segment_weather, stage_name, trip_tz)` und `vorschau_*`-Fehlercodes dem Stand vor dem Umbau, auch Trend, Backfill-Verzicht und Demo-Daten.
  - Test: Vorschau-Ergebnisse vor dem Umbau festhalten und danach vergleichen; bestehende Tests auf `_build_report` und `render_sms_preview` bleiben gruen.
- **AC-3:** Given zwei verschiedene Nutzer mit je eigenem Trip / When Vorschau oder Versand fuer Nutzer A laufen / Then enthalten Bericht und Wetterabruf nur Daten von Nutzer A, und es wird nie `"default"` als Nutzer verwendet.
  - Test: Zwei-Nutzer-Test an Vorschau und Versand mit echter `user_id`.
- **AC-4:** Given der Quelltext der Dienste / When man die Stelle sucht, die Segmente, Wetterabruf, Anreicherung und Render-Aufruf des Trip-Briefings zusammensetzt / Then gibt es genau eine (`trip_briefing_aufbau`), und Versand wie Vorschau rufen sie auf, ohne eigene Kopie der Verdrahtung.
  - Test: Verhaltenstest: eine Aenderung am Baustein (Test-Ersatzfassung) ist in Vorschau UND Versand sichtbar; Mutations-Gegenprobe des Validators.
- **AC-5:** Given der neue Baustein / When er in einem frischen Prozess importiert wird / Then werden weder `trip_report_scheduler` noch `preview_service` geladen (kein Zirkelimport), und alle bisherigen Import-Namen bleiben gueltig.
  - Test: Import im frischen Prozess, Pruefung der geladenen Module.
- **AC-6:** Given der Baustein / When die Vorschau ihn ausfuehrt / Then entsteht keine Nebenwirkung: kein Versand, kein Kontingent-Abbruch, kein Anker, keine Marker, keine Persistenz im Nutzerverzeichnis.
  - Test: Vorschau-Aufruf mit Verzeichnis-Snapshot vorher/nachher und Sinks, die nie aufgerufen werden duerfen.
- **AC-7:** Given ein Trip ohne Etappe, ohne Wetterdaten oder bei erschoepftem Handversand-Kontingent / When der Versand laeuft / Then bleiben Reihenfolge und Ergebnis wie bisher: `no_stage`, `no_weather` bzw. `manuell_abgelehnt` nach dem Wetterabruf und vor dem Rendern, Anker nur nach erfolgreichem Versand, Phasenuhr misst weiter jede Phase.
  - Test: Versand-Tests fuer die Abbruchpfade; bestehende Tests fuer Anker (#1629), Kontingent (#2961) und Phasenuhr bleiben gruen.
- **AC-8:** Given die bekannten SMS-sichtbaren Abweichungen der Vorschau (amtliche Warnungen, `has_gap`, Nachtwetter-Gate, Test-Fallback) / When dieses Ticket umgesetzt ist / Then verhaelt sich die Vorschau in diesen Punkten unveraendert und wird erst in #3144 angeglichen.
  - Test: Vorschau-Test mit Nachtwetter-Gate und `has_gap=False` zeigt dieselbe SMS wie vor dem Umbau; keine neue Warnungsabfrage in der Vorschau.
- **AC-9:** Given ein echt zugestelltes Trip-Briefing im Staging-Postfach / When der Mail-Validator `briefing_mail_validator.py` laeuft / Then endet er mit Exit 0.
  - Test: Validator gegen echte Staging-Mail nach dem Deploy auf Staging.

## Out of Scope

- **Angleichung der Vorschau an den Versand** (amtliche Warnungen, `has_gap`, Nachtwetter-Gate, Test-Fallback): eigenes Issue #3144.
- Aenderung des Inhalts von Mail, SMS, Premium-SMS oder Telegram: keine; nur der Ort des Aufbaus.
- Phasenuhr, Anker, Marker, Kontingent und Logs: bleiben unveraendert im Scheduler.

## Known Limitations

- Der Baustein ist in fuenf Funktionen geteilt (nicht nur eine), weil der Versand zwischen Wetterabruf und Rendern Kontingent und `no_weather` pruft, Phasenuhr misst und Anker im try-Block setzt.
- Bis #3144 zeigt die SMS-Vorschau in vier Punkten weiterhin nicht exakt die zugestellte SMS; das ist heutiger Stand, kein neuer Fehler.
- Der Umbau liegt ueber dem Standard-LoC-Limit (`loc_limit_override 500`), siehe Estimated Scope.

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/trip_briefing_aufbau.py` | CREATE | Baustein (5 Funktionen), ohne Nebenwirkungen, kein Modul-Import von Scheduler/preview_service |
| `src/services/trip_report_scheduler.py` | MODIFY | `_briefing_bauen_und_senden` ruft Teilfunktionen an heutigen Stellen; Zwischenstopps, Phasenuhr, Anker, Marker, Test-Fallback bleiben |
| `src/services/preview_service.py` | MODIFY | `_build_report` duenne Fassade auf `trip_briefing_bauen`; Signatur, Tupel, `vorschau_*`-Codes, Trend parallel unveraendert |
| `src/services/notification_service.py` | MODIFY (minimal, evtl. keine) | Render-Aufruf ggf. ueber Baustein, Inhalt unveraendert |
| `tests/tdd/test_trip_briefing_aufbau.py` | CREATE | Golden Versand (SMS, Premium-SMS, Telegram kurz/lang, Mail), Vorschau unveraendert, Mandantentrennung, Seiteneffektfreiheit, Import ohne Zirkel |
| `tests/tdd/test_bug_397_output_localtime.py` | MODIFY (nur falls noetig) | Fundstelle des Quelltext-Tests |
| `tests/tdd/test_issue_1004_ssot_callers.py` | MODIFY (nur falls noetig) | Fundstelle des Quelltext-Tests |

### Estimated Changes

- Files: 7 (4 Quellen inkl. evtl. notification_service, 3 Tests)
- LoC: +~350 / -~400 Produktionszeilen (`loc_limit_override 500`)

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Zusammenfuehrung doppelter Verdrahtung nach dem bestehenden Muster geteilter Bausteine (`compare_briefing_aufbau`); keine neue Entscheidungsflaeche, die Vorschau-Entscheidung (SMS-Vorschau = zugestellte SMS, #1743) bleibt unveraendert und wird in #3144 umgesetzt.

## Changelog

- 2026-11-18: Initial spec created (Issue #3128, Trip-Teil aus #2983; Drift-Angleichung als #3144 ausgelagert)
