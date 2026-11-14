---
entity_id: fix_2219_alarm_vorschau_haerten
type: bugfix
created: 2026-11-13
updated: 2026-11-13
status: draft
version: "1.0"
workflow: fix-2219-alarm-vorschau-haerten
tags: [alert, alert-preview, validator, eingabepruefung, i18n, onset]
---

# Alarm-Vorschau als Prüfwerkzeug härten (#2219)

Issue: [#2219](https://github.com/henemm/gregor_zwanzig/issues/2219) (Bündel aus #1199: C5-18, C5-19, C5-28, C5-46, C5-52, Nachzug B2-72)
Basis: `origin/main` = `5dd49a173`. Kontext und Analyse: `docs/context/fix-2219-alarm-vorschau-haerten.md`.

## Approval

- [ ] Approved

## Purpose

Die Alarm-Vorschau (`POST /api/trips/{id}/alert-preview`, ebenso `POST /api/briefings/{id}/alert-preview?kind=route|vergleich`)
ist das Prüfwerkzeug für Black-Box-Validatoren und den Alarme-Reiter. Sie antwortet bei fehlerhaften Eingaben mit HTTP 500
oder zeigt Zustände, die der Versand nie erzeugt. Diese Spec macht daraus saubere 422-Antworten (lokalisiert, wie
`metrik_unbekannt`) und lässt den Replay-Zweig den Beginn mit Tagesbezug zeigen, wie es der Versand tut.
Der Versandpfad bleibt unberührt.

## Source

- **File:** `api/routers/validator.py`
- **Identifier:** `alert_preview`, `briefing_alert_preview`, Payload-Modelle `ChangePayload`, `OnsetPayload`, `NowcastFramePayload`

Schicht: **Python-Core / Domain-Backend** (`api/`, `src/services/`, `src/output/`, `src/i18n/`). Frontend und Go-API sind nicht
betroffen: das Frontend sendet bereits `minor/moderate/major` (`alertPreviewHelpers.ts` `SEVERITY_MAP`) und keine
`nowcast_frames`; die Go-API reicht den Body nur durch.

Querschnitts-Prüfpunkte:
- **Trip/Ortsvergleich-Teilung:** Die Severity-Prüfung gilt für beide Zweige (Trip: `validator.py`, Compare:
  `compare_alert_preview_service.py`) über **eine** gemeinsame Prüffunktion. Die übrigen Prüfungen betreffen Payload-Felder,
  die nur der Trip-Zweig kennt (`onset`, `nowcast_frames`, Onset-`changes`); ein Compare-Pendant existiert nicht.
- **Mandantentrennung:** keine neue Nutzerdatenbewegung; Laden bleibt user-scoped (`user_id` aus dem Aufruf). Die neuen
  Fehlertexte werden in der Sprache dieses Nutzers gerendert (`api_fehler(…, user_id, …)`).
- **Kanäle:** Betroffen ist die Vorschau aller vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS-Form = SMS-Text). Der Inhalt
  des Versands ändert sich nicht; nur die Replay-Vorschau zeigt den Beginn jetzt vollständig.

## Estimated Scope

- **LoC:** ca. +150 bis +250 (etwa die Hälfte Tests)
- **Files:** 8 (davon 1 bis 2 neue Testdateien)
- **Effort:** medium

## Scope

**Im Scope:**
- Eingangsprüfung der Alarm-Vorschau mit lokalisierten 422-Antworten für: unbekannte Schwere (C5-52, Trip- und
  Compare-Zweig), zonenlose oder ungültige `nowcast_frames[].timestamp` (C5-28), Tagesversatz ohne Wochentagskürzel bei
  Beginn oder Ende (C5-46), Beginn-Verschiebung 0 oder unter der Schwelle (C5-19).
- Replay-Zweig zeigt den Beginn mit Tagesbezug über die neue geteilte Anzeigefassung `onset_display` (B2-72, #2085).
- Regressionstest für die Zeitzone der Stub-Segmente (C5-18, Befund widerlegt, kein Code-Fix).
- Vier neue Fehlerschlüssel DE/EN im i18n-Katalog, Fehlerfälle in `docs/reference/api_contract.md`.

**Nicht im Scope:**
- Versandpfad (`render.py`, `trip_alert.py`, `weather_change_detection.py`) und dortige Inline-Ableitung des Beginns.
- Echte statt Stub-Segmente in der Vorschau (#2069).
- Frontend und Go-API.

## Definition of Done

- Alle AC-1 bis AC-13 durch automatische Tests belegt, Kern-Testschicht grün, bestehende Vorschau-, Onset- und
  i18n-Paritätstests unverändert grün.
- Auf Staging liefert die Vorschau für jede der vier Fehleingaben HTTP 422 mit lokalisiertem Text statt HTTP 500;
  ein gültiger Aufruf liefert weiterhin 200.
- Replay-Vorschau mit Tagesversatz zeigt Beginn und Ende jeweils mit Wochentagskürzel.
- API-Contract-Doku nennt die neuen 422-Gründe; #2085 als Duplikat mit Verweis geschlossen.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `api/fehler.py` `api_fehler` | reuse | lokalisierte 422-Antwort, Muster `metrik_unbekannt` / `segment_unbekannt` |
| `src/app/models.py` `ChangeSeverity` (`minor/moderate/major`) | reuse | Quelle der erlaubten Severity-Werte; keine zweite Liste |
| `src/services/alert_preset.py` `ONSET_SHIFT_BOUNDS` (`(früher_h, später_h)` je Stufe) | reuse | Quelle der Schwelle für die Beginn-Verschiebung; `weather_change_detection._onset_change` liest dieselbe Tabelle |
| `src/output/renderers/alert/project.py` `_is_onset_change`, `event_end_display`, `_de_weekday_short` | reuse / Muster | Erkennung Beginn-Verschiebung über den Katalog; Vorbild der neuen `onset_display` |
| `src/utils/timezone.py` `day_offset`, `local_dt`, `local_fmt` | reuse | Ortszeit und Tagesversatz im Replay |
| `src/services/validator_render_service.py` `_render_nowcast_replay` | MODIFY | `onset_ns` über `onset_display` |
| `src/services/compare_alert_preview_service.py` `_deviation` | MODIFY | gemeinsame Severity-Prüfung |
| `src/i18n/messages/{de,en}/api.json` | MODIFY | vier neue `api.fehler.*`-Schlüssel (ADR-0104) |
| `docs/specs/modules/feat_2054_onset_wochentagskuerzel.md` | Vorgänger | Kürzel-Schreibweise, AC-10 „Versatz entscheidet" |
| `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md` | Vorgänger | Replay-Zweig der Vorschau |

## Implementation Details

Technische Fragen der Analyse, durch Code-Lesen beantwortet:

1. **Welches Feld trägt die Beginn-Verschiebung?** Ein Eintrag in `body.changes[]` (`ChangePayload`), dessen `metric` über den
   Katalog eine Beginn-Größe ist (`project._is_onset_change`: Aggregation `onset`, d. h. `thunder_onset` bzw.
   `precipitation_heavy_onset`). `old_value` und `new_value` sind **Epochensekunden**, `delta = new_value - old_value`
   (Sekunden). Das Payload trägt keine Empfindlichkeitsstufe.
2. **Wo liegt die Schwelle?** `alert_preset.ONSET_SHIFT_BOUNDS` (Stunden, je Stufe `(früher, später)`: entspannt 2/4,
   standard 1/3, sensibel 1/2); `_onset_change` wählt je Richtung `later_h` bei `delta > 0`, sonst `earlier_h`. Da die Vorschau
   die Stufe nicht kennt, gilt als Eingabegrenze die **kleinste Schwelle der jeweiligen Richtung über alle Stufen**
   (`min(früher)` bzw. `min(später)` aus derselben Tabelle, in Sekunden). Unter dieser Grenze kann der Versand die Verschiebung
   bei keiner Stufe melden. Kein neuer Zahlenwert, nur eine Ableitung aus der bestehenden Tabelle.
3. **Senden bestehende Tests verbotene Eingaben?** Nein. `rg` über `tests/` (Dateien mit `preview`) findet keinen Aufruf mit
   `onset_day_offset`/`event_end_day_offset` ohne Kürzel, keine Beginn-Verschiebung mit Shift 0 oder unter Schwelle; alle
   Severity-Werte in Preview-Tests sind `minor/moderate/major`, alle Replay-Zeitstempel zoniert (`datetime.now(timezone.utc)`).
   Trotzdem läuft die Gesamtliste der Vorschau-Tests (siehe Test Plan) als Regressionsschutz.

Änderungen je Befund (Tech-Lead-Entscheidungen unverändert aus der Analyse):

| Befund | Änderung |
|---|---|
| C5-52 | `ChangePayload.severity: str` bleibt. Neue Prüffunktion `_validate_change_severity` gegen die Werte von `ChangeSeverity`; Verstoß → `api_fehler(422, "schwere_unbekannt", user_id, severity=…, erlaubt="minor, moderate, major")`. Dieselbe Funktion im Compare-Zweig vor `ChangeSeverity(c["severity"])`. „HIGH" (reines Ausgabe-Token der Engine, kein Rück-Mapping im Versand) wird abgelehnt, nicht abgebildet. |
| C5-28 | Router-Prüfung von `nowcast_frames.frames[].timestamp`: nicht als ISO parsebar oder `tzinfo is None` → `api_fehler(422, "zeitstempel_ohne_zone", user_id, timestamp=…)`. Service unverändert. |
| C5-46 | `onset_day_offset != 0` ohne `onset_weekday` bzw. `event_end_day_offset != 0` ohne `event_end_weekday` → `api_fehler(422, "onset_tagesbezug_unvollstaendig", user_id, feld=…)`. `render._sms_onset_time` bleibt **unverändert** (Versandpfad erzeugt den Fall nie). |
| C5-19 | Onset-`changes[]` mit `delta == 0` oder `abs(new_value - old_value)` unter der Grenze aus Punkt 2 → `api_fehler(422, "onset_shift_null", user_id, …)`. Kein Guard im Renderer (`_onset_shift_text` unverändert). |
| B2-72 | Neue geteilte `onset_display(now_utc, onset_minutes, tz) -> (hhmm, offset, weekday)` in `project.py` neben `event_end_display`, gleiche Slice-Behandlung (`local_fmt(...)[-5:]`). Nur der Replay (`_render_nowcast_replay`, `onset_ns`) nutzt sie und setzt zusätzlich `onset_day_offset` und `onset_weekday`. Die Versandstellen (`trip_alert.py`, `project.py` Inline-Ableitung) bleiben byte-identisch; ein Refactor auf die geteilte Funktion ist ein Folge-Ticket. |
| C5-18 | Kein Codefix. `tz_for_coords(0, 0)` ergibt UTC, `resolve_location_tz(0, 0)` ergibt `None` (UTC gilt als „nicht auflösbar"), `_tz_for_location` fällt per `or fallback_tz` auf die Trip-Zone zurück. Die Prämisse des Befunds trifft nicht zu; ein Regressionstest hält das fest. |

Fehlertexte: vier neue Schlüssel `api.fehler.schwere_unbekannt`, `api.fehler.zeitstempel_ohne_zone`,
`api.fehler.onset_tagesbezug_unvollstaendig`, `api.fehler.onset_shift_null` in `src/i18n/messages/de/api.json` und
`en/api.json` (Paritätstest `tests/test_i18n_api_katalog_paritaet.py` und `tests/tdd/test_api_fehler_nutzersprache.py`
decken beide Sprachen ab). Antwortformat identisch zu `metrik_unbekannt` (`api_fehler`-Struktur, kein pydantic-`detail[]`).
Der Replay-Zweig und der Briefing-Delegate (`kind=route`) laufen über denselben Endpunktcode; `kind=vergleich` fängt
`ValueError` bisher als `alarm_body_ungueltig` ab, die Severity-Prüfung dort liefert den spezifischen Grund
(`schwere_unbekannt`) mit Status 422.

Abgrenzung: **#2069** (Stub- statt echter Segmente, km/Distanz/Höhe blind) ist nicht Teil. **#2085** ist identisch mit B2-72
und wird hier mitgelöst, danach als Duplikat mit Verweis geschlossen. Nicht angefasst: `render.py`, `trip_alert.py`,
`weather_change_detection.py`.

## Expected Behavior

- **Input:** Vorschau-Aufruf mit fehlerhaftem Payload (unbekannte Severity, zonenloser Zeitstempel, Tagesversatz ohne Kürzel,
  Beginn-Verschiebung 0 oder unter Schwelle) oder gültiger Payload.
- **Output:** Fehlerfall: HTTP 422 mit lokalisiertem Grund und Code (bei Severity inkl. erlaubter Werte). Gültiger Fall: 200 mit
  derselben Ausgabe wie bisher; Replay zeigt zusätzlich Beginn mit Tagesbezug, wenn ein Tagesversatz besteht
  (z. B. `R0.8@Sa0:23 >@Sa0:38`).
- **Side effects:** keine. Kein Versand, keine Persistenz, keine Schwellen- oder Auslöselogik wird berührt.

## Test Plan

### Automated Tests (TDD RED)

Datei `tests/tdd/test_fix_2219_alarm_vorschau_eingaben.py` (echte Endpunktaufrufe über TestClient gegen `api.main:app`, echte
Trips im Test-Datenverzeichnis, kein `Mock`/`patch`) und `tests/tdd/test_fix_2219_onset_replay_tagesbezug.py`
(Service-Aufruf `render_alert_preview` bzw. Endpunkt, echte Renderer). Kein Mock-Theater, keine Dateiinhalt-Checks.

- [ ] Test 1: GIVEN Trip mit Segment / WHEN `changes[].severity="HIGH"` / THEN 422, Code `schwere_unbekannt`, Text nennt `minor`, `moderate`, `major` (DE und EN je nach Nutzersprache)
- [ ] Test 2: GIVEN Orts-Vergleich-Preset / WHEN `kind=vergleich` mit `severity="HIGH"` / THEN 422 `schwere_unbekannt`, nicht 500 und nicht `alarm_body_ungueltig`
- [ ] Test 3: GIVEN Replay-Frames / WHEN Zeitstempel `"2026-11-13T10:00:00"` (ohne Zone) bzw. `"gestern"` / THEN 422 `zeitstempel_ohne_zone`
- [ ] Test 4: GIVEN Onset-Payload / WHEN `onset_day_offset=1` ohne `onset_weekday` bzw. `event_end_day_offset=1` ohne `event_end_weekday` / THEN 422 `onset_tagesbezug_unvollstaendig`
- [ ] Test 5: GIVEN Onset-`changes` (`thunder_onset`) / WHEN `old_value == new_value` bzw. Verschiebung 30 Minuten / THEN 422 `onset_shift_null`
- [ ] Test 6: GIVEN Replay mit Regenbeginn nach Mitternacht Ortszeit (Beispiel #2085) / WHEN Vorschau / THEN SMS zeigt `@Sa0:23` für den Beginn und `>@Sa0:38` für das Ende
- [ ] Test 7: GIVEN Trip Europe/Berlin, Stub-Zweig ohne frische Reihen, Beginn-Verschiebung / WHEN Vorschau / THEN Beginn-Uhrzeit in Berliner Ortszeit (C5-18-Regression)
- [ ] Test 8: GIVEN gültige Eingaben (`minor`/`moderate`/`major`, zonierte Zeitstempel, Offset mit Kürzel, Verschiebung 2 h früher) / WHEN Vorschau / THEN 200 und Ausgabe identisch zu einer Referenz aus dem Bestand
- [ ] Test 9: GIVEN Replay ohne Tagesversatz / WHEN Vorschau / THEN Ausgabe byte-identisch zum Bestand (kein Kürzel am Beginn)
- [ ] Test 10: Bestehende Dateien bleiben grün (`test_i18n_api_katalog_paritaet.py` und `test_api_contract_drift.py` unter `tests/`, alle übrigen unter `tests/tdd/`): `test_i18n_api_katalog_paritaet.py`, `test_api_fehler_nutzersprache.py`, `test_api_contract_drift.py`, `test_alert_preview_input_validation.py`, `test_alert_preview_onset_payload.py`, `test_alert_preview_nowcast_replay.py`, `test_alert_preview_compare_paritaet.py`, `test_alert_preview_compare_paritaet_drossel_frei.py`, `test_onset_wochentagskuerzel.py`

## Acceptance Criteria

- **AC-1:** Given ein Trip mit gültigem Segment / When die Alarm-Vorschau mit einer Änderung der Schwere `"HIGH"` aufgerufen wird / Then antwortet der Dienst mit 422 und dem Grund `schwere_unbekannt`, der die erlaubten Werte `minor`, `moderate` und `major` nennt, und nicht mit HTTP 500. (Befund: C5-52)
  - Test: echter Endpunktaufruf mit `severity="HIGH"`; Status, Code und erlaubte Werte im Text der Nutzersprache prüfen.

- **AC-2:** Given ein Orts-Vergleich mit Alarm-Preset / When die Alarm-Vorschau (`kind=vergleich`) eine Änderung der Schwere `"HIGH"` enthält / Then antwortet der Dienst ebenfalls mit 422 und dem Grund `schwere_unbekannt` über dieselbe Prüfung wie im Trip-Zweig. (Befund: C5-52, Compare)
  - Test: echter Endpunktaufruf `briefings/{id}/alert-preview?kind=vergleich` mit ungültiger Schwere; Code `schwere_unbekannt`, kein 500.

- **AC-3:** Given ein Nowcast-Replay-Aufruf / When ein Zeitstempel der Frames keine Zeitzone trägt oder kein gültiges ISO-Datum ist / Then antwortet der Dienst mit 422 und dem Grund `zeitstempel_ohne_zone` und nicht mit HTTP 500. (Befund: C5-28)
  - Test: Aufruf mit `"2026-11-13T10:00:00"` und mit `"gestern"`; beide ergeben 422 mit Code `zeitstempel_ohne_zone`.

- **AC-4:** Given ein Onset-Payload / When `onset_day_offset` oder `event_end_day_offset` ungleich 0 ist, das zugehörige Wochentagskürzel aber fehlt / Then antwortet der Dienst mit 422 und dem Grund `onset_tagesbezug_unvollstaendig`, statt den Tagesbezug still zu verschlucken. (Befund: C5-46)
  - Test: Aufrufe mit `onset_day_offset=1` ohne Kürzel und mit `event_end_day_offset=1` ohne Kürzel; beide 422; der Kontrollfall mit Kürzel liefert 200 und `@Sa0:23`.

- **AC-5:** Given dieselbe Eingabe-Konstellation / When die Kurznachricht über den Renderer erzeugt wird / Then bleibt `_sms_onset_time` unverändert und liefert für alle bisherigen Eingaben (Versatz 0, Versatz mit Kürzel) zeichengleiche Ergebnisse wie vor der Änderung. (Befund: C5-46, Versandcode)
  - Test: bestehende `tests/tdd/test_onset_wochentagskuerzel.py` bleibt unverändert grün (Fallmatrix aus feat_2054 AC-8, AC-10).

- **AC-6:** Given Änderungen mit einer Beginn-Verschiebung (`thunder_onset` oder `precipitation_heavy_onset`) / When die Verschiebung 0 beträgt oder unter der kleinsten Schwelle ihrer Richtung aus `ONSET_SHIFT_BOUNDS` liegt / Then antwortet der Dienst mit 422 und dem Grund `onset_shift_null`, statt „0 h früher" zu rendern. (Befund: C5-19)
  - Test: Aufruf mit `old_value == new_value` und mit 30 Minuten Verschiebung; beide 422. Kontrollfall 2 h früher liefert 200 und enthält „2 h früher".

- **AC-7:** Given die Schwellen-Tabelle `ONSET_SHIFT_BOUNDS` / When ein Eintrag dieser Tabelle geändert wird / Then folgt die Grenze der Vorschau-Prüfung dieser Änderung ohne zweite Konstante, weil Vorschau und `_onset_change` dieselbe Tabelle lesen. (Befund: C5-19, eine Quelle)
  - Test: Verschiebung genau auf der kleinsten Schwelle der Richtung (z. B. 1 h früher) wird akzeptiert (200), eine Sekunde darunter abgelehnt (422); Grenzwerte aus der Tabelle gelesen, nicht fest einkodiert.

- **AC-8:** Given ein Nowcast-Replay, dessen Regenbeginn und Ende hinter Mitternacht Ortszeit liegen / When die Vorschau gerendert wird / Then trägt der Beginn wie das Ende das Wochentagskürzel (Beispiel aus #2085: statt `R0.8@0:23 >@Sa0:38` zeigt die Kurznachricht `R0.8@Sa0:23 >@Sa0:38`). (Befund: B2-72, #2085)
  - Test: Replay-Frames mit Beginn kurz nach Mitternacht Ortszeit; SMS-Text der Vorschau enthält das Kürzel am Beginn und am Ende, in allen Kanälen derselbe Tagesbezug (E-Mail/Telegram als Wort).

- **AC-9:** Given ein Replay mit Beginn am selben Tag / When die Vorschau gerendert wird / Then bleibt die Ausgabe zeichengleich zum Bestand (kein Kürzel am Beginn), und `onset_display` liefert Uhrzeit, Versatz und Kürzel nach derselben Regel wie `event_end_display` (Versatz entscheidet, Kürzel nur bei Versatz ungleich 0, Wochentag der Ortszeit). (Befund: B2-72, geteilte Ableitung)
  - Test: Replay ohne Tagesversatz gegen festgeschriebenen Bestands-String; Ortszeit-Fall (Europe/Berlin, UTC- und Ortstag fallen auseinander) liefert den Wochentag der Ortszeit.

- **AC-10:** Given ein Trip in der Zeitzone Europe/Berlin und ein Aufruf der Abweichungs-Vorschau ohne frische Stundenreihen (Stub-Segmente) / When ein Beginn gerendert wird / Then steht die Uhrzeit in Berliner Ortszeit, nicht in UTC. (Befund: C5-18, Regression)
  - Test: echter Endpunktaufruf mit Beginn-Verschiebung; Uhrzeit entspricht der Berliner Ortszeit (Sommer-/Winterzeit-Versatz zu UTC erkennbar). Es gibt keinen Codefix; der Test bewacht die heutige Zonenauflösung.

- **AC-11:** Given gültige Eingaben (Schwere `minor`, `moderate`, `major`; zonierte Zeitstempel; Tagesversatz mit Kürzel; Beginn-Verschiebung über der Schwelle) / When die Vorschau aufgerufen wird / Then antwortet sie weiterhin mit 200 und byte-identischer Ausgabe wie vor der Änderung. (Befund: Regression gültige Eingaben)
  - Test: je Eingabevariante Ausgabe gegen eine Referenz aus dem Bestand (Betreff, E-Mail, Telegram, SMS); die bestehenden Preview-Tests laufen unverändert grün.

- **AC-12:** Given die Änderung ist umgesetzt / When ein echter Alarm über den Versandpfad erzeugt wird / Then ist der Inhalt aller vier Kanäle (E-Mail, Telegram, SMS, Premium-SMS) zeichengleich zum Stand davor, da `render.py`, `trip_alert.py` und `weather_change_detection.py` nicht geändert werden. (Befund: Versandpfad unberührt)
  - Test: bestehende Kanal- und Onset-Tests (`tests/tdd/test_onset_wochentagskuerzel.py`, `tests/tdd/test_alert_onset_day_rollover.py`, `tests/tdd/test_alert_zeitangaben_tagesbezug.py`) laufen unverändert grün; Prüfung per `git diff --stat`, dass die drei Dateien nicht geändert sind, ist Teil der Validierung, nicht des Verhaltenstests.

- **AC-13:** Given Nutzer mit Sprache Deutsch bzw. Englisch / When eine der vier neuen 422-Antworten ausgelöst wird / Then erscheint der Text in der Sprache des Nutzers aus dem i18n-Katalog (ADR-0104) im selben Fehlerformat wie `metrik_unbekannt`, und für jeden Schlüssel existieren beide Sprachen. (Befund: Fehlertexte lokalisiert)
  - Test: je neuem Grund ein Aufruf mit DE-Nutzer und mit EN-Nutzer; Text weicht in der Sprache ab; `test_i18n_api_katalog_paritaet.py` bleibt grün.

## Known Limitations

- Die untere Grenze der Beginn-Verschiebung (Punkt 2) ist die kleinste Schwelle über alle Stufen; die Vorschau kennt die Stufe des Nutzers nicht. Eine Verschiebung zwischen kleinster und stufenspezifischer Schwelle wird akzeptiert, obwohl der Versand sie für eine strengere Stufe nicht melden würde.
- `_sms_onset_time` verschluckt weiter still den Tagesbezug, wenn Versatz und Kürzel inkonsistent hereinkommen; das ist über den Versandpfad nicht erreichbar und wird nur an der Vorschau-Eingabe abgefangen.
- Versandstellen bilden den Beginn weiter inline statt über `onset_display`; Vereinheitlichung als Folge-Ticket.
- Stub-Segmente statt echter Segmente (km, Distanz, Höhe blind) bleiben → #2069.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Kein neues Entscheidungsfeld. Die Spec nutzt etablierte Muster (`api_fehler`-422 wie `metrik_unbekannt`, geteilte Anzeigefassung wie `event_end_display`, i18n-Katalog nach ADR-0104) und bildet nur Versandzustände in der Vorschau ab.

## Changelog

- 2026-11-13 (Phase 5, RED): C5-18 ist doch reproduzierbar. Der RED-Test zu AC-10 (Trip bei Garmisch, Etappe morgen,
  Abweichungszweig mit Stub-Segmenten, Beginn-Verschiebung) zeigt `Gewitter-Beginn: 00:00 → 22:00` in UTC, während
  `Stand:` in Berliner Zeit steht. Die Analyse-Annahme „kein Codefix" (Rückfall auf die Trip-Zone) trifft für diesen Zweig
  nicht zu; AC-10 bleibt unverändert und verlangt jetzt einen Fix. Ursache in Phase 6 suchen: welche Zone der
  Abweichungszweig von `render_alert_preview` an die Projektion übergibt (`_alert_tz_for_trip` liefert Berlin) bzw. welchen
  Rückfall `_tz_for_location` für die 0/0-Stubs bekommt. Versandpfad bleibt unberührt. Beginn-Größen heißen im Payload
  über ihr Summary-Feld (`thunder_onset_utc`, `precip_heavy_onset_utc`); `changes` ohne heutige Etappe brauchen `segment_times`.
- 2026-11-13: Initial spec created (Bündel #2219 inkl. Nachzug B2-72, löst #2085 als Duplikat mit)
