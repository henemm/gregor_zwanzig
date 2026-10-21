---
entity_id: feat_2439_befehle_antwortzeit
type: module
created: 2026-10-18
updated: 2026-10-18
status: implemented
version: "1.0"
tags: [inbound, befehle, antwortzeit, dwd, briefing, parallel, observability, 2439]
---

# Antwortzeit der Befehle — messbare Zielgröße, schnellerer Wetterabruf, Betriebs-Rest des Push-Eingangs

## Approval

- [ ] Approved

## Purpose

Befehle ohne Wetterabruf (`HELP`, `CODES`, `STATUS`) sollen in unter 30 Sekunden beantwortet sein, Wetter-Befehle (`HEUTE`/`MORGEN`, englisch `TODAY`/`TOMORROW`) in unter 60 Sekunden — ohne dass die Antwort kürzer oder ärmer wird. Heute braucht `HEUTE` auf Staging im Mittel 57,8 Sekunden reine Rechenzeit (Gesamtlauf 69,6 s), davon den größten Teil für kalte DWD-Gewitter-Tagesfenster, die nacheinander geladen werden. Diese Spec macht die Zeit erstmals messbar (Journal-Zeile), überlappt die Wartezeiten (Vorwärmen + parallele Segmentschleife) und schließt dabei den Betriebs-Rest des Push-Eingangs (Teil a) ab. Sie schließt Issue #2439 komplett ab; Teil a ist in `feat_2439_befehle_push_eingang.md`, Teil b dort ausdrücklich Out of Scope.

## Source

- **File:** `src/services/trip_report_scheduler.py` (Hauptort), `src/providers/dwd.py`, `src/services/trip_command_processor.py`
- **Identifier:** `TripReportSchedulerService._send_trip_report_outcome`, `TripReportSchedulerService._fetch_weather`, `DwdDirectProvider.fetch_thunder_signals_named`, Befehls-Dispatch in `trip_command_processor.py`
- **Issue:** #2439 (Epic #2506). PO-Vorschlag 28.09.: ohne Wetterabruf < 30 s, mit Wetterabruf < 1 min, Zielgröße je Befehlsklasse als prüfbare AC.
- **Python-Core (ändern):** `src/services/trip_command_processor.py` (Dauer je Befehl, Dispatch ~1087-1106), `src/services/trip_report_scheduler.py` (Phasenzeiten, Vorwärmen vor dem Hauptabruf ~1211/1295, `_fetch_weather` ~2386-2434 parallel), `src/providers/dwd.py` (Vorwärm-Einstieg, Abschluss-Log, Cache-Kapazität 512 → 2048), `src/services/parallel_fetch.py` (Nutzung `fetch_ordered`, keine Verhaltensänderung des Bausteins)
- **Tests:** `tests/test_befehl_antwortzeit.py` (neu, Kern), `tests/e2e/test_push_eingang_befehle_staging.py` (ändern, Live)
- **Doku:** `docs/runbooks/inbound-webhooks.md` (Z. 55-58 und Z. 102)
- **Infra (anderes Repo, Lieferbestandteil, selbst erledigt):** `henemm-infra/scripts/check-gregor20.sh` (`missed_total`-Check). Nginx-Versionierung ist bereits erledigt (henemm-infra PR #266, Commit a1c596d) und nur erwähnt.
- **Schicht:** ausschließlich Python-Core (`src/`, `api/`) und Infra; keine Go- oder Frontend-Änderung. Analyse und Messbasis: `docs/context/feat-2439-befehle-antwortzeit.md`.

## Entscheidungen (alle getroffen, keine offene Frage)

| # | Entscheidung | Begründung |
|---|---|---|
| 1 | **Zielgröße.** Messintervall = Eingang beim Python-Core (Webhook-/Poll-Übernahme bzw. Telegram-Webhook) bis Übergabe der Antwort an den Versand-Provider; Satelliten-/Garmin-Laufzeit liegt außerhalb. Befehle ohne Wetterabruf: **jeder** Lauf < 30 s. `HEUTE`/`MORGEN` kalt auf Staging über echten Eingang, ≥ 5 Läufe: **jeder** Lauf < 60 s (harte Obergrenze) **und** Median < 45 s. Verbindlich für die DE/Alpen-Route (`de_direct` + `geosphere`) und für Korsika (`fr_direct`, Obergrenze < 60 s, AC-5). Gilt auf allen drei Befehlseingängen (E-Mail, Telegram, Premium-SMS). | PO-Vorschlag übernommen. Der DWD-Abruf schwankt 6-30 s; ein Median allein ließe Ausreißer zu, eine Obergrenze allein wäre bei Schwankung flackrig — beides zusammen ist ehrlich und prüfbar. |
| 2 | **Beobachtbarkeit zuerst (S0).** Dauer je Befehl (Befehl, Kanal, Trip-ID, ms; keine personenbezogenen Inhalte) + Phasenzeiten im On-Demand-Bau + DWD-Fensterzeit/Downloads/Cache-Treffer als Journal-Zeile. | Heute gibt es im Befehlspfad keine Laufzeitmessung. Ohne sie ist die Zielgröße nicht prüfbar; die Zielgrößen-ACs werden aus dieser Zeile gemessen. |
| 3 | **S1: DWD-Tagesfenster vorwärmen.** Alle für den Bericht nötigen Tagesfenster (Zieltag, Nacht, +1, +2) werden **vor** dem Hauptabruf mit Pool 2 gleichzeitig geladen, das Ergebnis wird verworfen, der Hauptabruf trifft den Cache. Einbau im geteilten Briefing-Bau (nützt auch dem geplanten Versand; inhaltsneutral; Pool 2 begrenzt die DWD-Last). | Messung 18.10. (Probelauf, 4 Kalendertage): seriell Median 12,0 s, 2 Tage parallel 9,3 s, 4 parallel 8,5 s. Jeder Lauf lädt dieselben 272 Dateien/170,6 MB — Parallelität spart also keine Downloads, nur Wartezeit-Überlappung (~20-30 %); mehr als 2 gleichzeitig bringt wegen Bandbreite nichts. Daher Pool 2. |
| 4 | **S2: Segmentschleife parallel — fester Umfang.** `_fetch_weather` nutzt `services/parallel_fetch.fetch_ordered` (Semaphore je Provider, Reihenfolge erhalten, Retry/Backoff je Segment erhalten). | S1 allein spart laut Messung nur ~20-30 % der DWD-Zeit; Staging steht heute bei 57,8 s, das Ziel wäre damit nicht sicher. Hinweis: Läuft der Aufruf aus einem Worker-Thread, arbeitet `fetch_ordered` inline seriell (Docstring) — das ist beim Einbau zu beachten, damit der Parallelgewinn nicht stillschweigend ausbleibt. |
| 5 | **Cache-Kapazität** des DWD-Punkt-Fenster-Caches 512 → 2048 URLs. | Ein Eintrag (41×41 float64) ≈ 13,5 KB: 512 ≈ 6,9 MB, 2048 ≈ 27,6 MB. Ein Trip braucht ~415 Dateien; parallele Alarm- und Ortsvergleichsläufe würden bei 512 den Vorwärm-Bestand mitten im Lauf verdrängen. 28 MB sind auf dem 8-GB-Server unkritisch. |
| 6 | **Poll-Lock bleibt.** Entkoppeln wird verworfen. | Entkoppeln gefährdet Zustellreihenfolge und Kanaltreue und spart 0 s Rechenzeit. Stattdessen wird die Haltung als AC messbar gemacht: ein `HELP` während eines laufenden `HEUTE` desselben Kanals wird spätestens 30 s nach Ende des `HEUTE` beantwortet (busy → Weckruf pending → Nachlauf). Im ungünstigsten Fall gilt damit < 90 s. |
| 7 | **Inhalt unverändert.** Keine Kürzung (Nacht, Ausblick, Gewitter +1/+2, Ensemble bleiben). | Kanal-Parität (Epic #2506); eine Kürzung wäre eine Produktentscheidung, keine Optimierung. |
| 8 | **Teil-a-Betriebs-Rest** ist Lieferbestandteil dieser Spec, nicht abgespalten (Epics themenweise abschließen). | Siehe AC-14 bis AC-17. |

## Estimated Scope

- **Dateien:** ~6 im Repo (3 Produktcode `trip_command_processor.py`, `trip_report_scheduler.py`, `dwd.py`; Tests; Live-Test; Runbook) + 1 in `henemm-infra`
- **LoC:** S0 ~40, S1 ~80-120, S2 ~60-90, Tests ~150 → über dem Standard-Limit; `loc_limit_override` wird auf **500** gesetzt
- **Aufteilung:** S0 Beobachtbarkeit → S1 Vorwärmen → S2 Segmentschleife → Teil-a-Rest; Staging-Messung nach S0+S1+S2 gemeinsam
- **Effort:** medium; **Risiko MEDIUM** (geteilter Pfad, siehe Abschnitt Dependencies/Risiken)

## Dependencies

Inklusive Risiken:

| Entity | Art | Zweck / Risiko |
|---|---|---|
| `_send_trip_report_outcome`, `_fetch_weather`, `_build_stage_trend` | **geteilter Pfad** | Derselbe Code bedient geplanten Briefing-Versand, Nachlieferung, Test-Versand (`api/routers/scheduler.py:309`), `REPORT`-Befehl (`trip_command_processor.py:2539`) und Vorschau (`preview_service.py:193,260`). Jede Änderung wirkt auf alle — Inhalt muss bit-identisch bleiben. |
| `fetch_segment_weather` + Segment-Cache, DWD-Raster-Cache | geteilt | Alarm-Lauf (`trip_alert.py:2993`), UI-Etappenansicht (`stage_weather.py:58`), Ortsvergleich (`compare_location_weather_source.py:181`) lesen und füllen denselben Cache. Vorwärmen darf deren Ergebnisse nicht verändern; größerer Cache (28 MB) ist der einzige Seiteneffekt. |
| `GZ_PARALLEL_FETCH_WORKERS=8` | geteilt | Alle Aufrufer von `parallel_fetch` teilen sich diese 8 Worker; ein paralleler Befehl kann gleichzeitige Läufe verlangsamen. |
| DWD (GRIB-Server) | extern | Fenster schwankt 6-30 s auch nach den Maßnahmen; Pool 2 begrenzt die Last, kein Single-flight im Raster-Abruf (daher Join, AC-8). |
| Open-Meteo, GeoSphere (SNOWGRID, CAPE/CIN), Ensemble, Warn-/Radar-Provider | extern | Rate-Limits bei Parallelität → Semaphore je Provider aus `parallel_fetch`. |
| **Renderer-Commit-Gate** | Gate | `trip_report_scheduler.py` ist Mail-Inhalts-Datei: Commit blockt, bis Modus-Matrix-Test und `uv run python3 .claude/hooks/briefing_mail_validator.py` (Trip-Briefing, nicht der Ortsvergleichs-Validator) frisch grün sind. |
| `henemm-infra/scripts/check-gregor20.sh` | anderes Repo | Arbeitsbaum ist sofort live (Cron) → nur in einer Kopie entwickeln und testen; infra-Änderung zuerst. |

## Implementation Details

```
S0 Beobachtbarkeit
  - trip_command_processor (Dispatch): Zeit messen vom Eingang beim Core bis Übergabe der Antwort
    an den Versand-Provider; eine Journal-Zeile je Befehl:
    befehl=<HEUTE> kanal=<email|telegram|sms|premium_sms> trip=<id> dauer_ms=<n>
    (keine Nachrichtentexte, keine Adressen/Nummern).
  - trip_report_scheduler (On-Demand-/Briefing-Bau): Phasenzeiten je Phase
    (Zieltag-Segmente, Nacht, Ausblick, Gewitter +1/+2, Ensemble, Warnungen, Rendern, Versandübergabe).
  - dwd.py: Abschluss-Zeile je Fenster: fenster_s, downloads, cache_treffer.

S1 Vorwärmen (im geteilten Briefing-Bau, vor dem Hauptabruf)
  - Fensterliste = Zieltag, Nacht, +1, +2 — mit DEMSELBEN Zuschnitt wie der spätere Abruf
    (Nullpunkt am ersten Open-Meteo-Datenpunkt, ganzer Kalendertag, openmeteo.py:1112-1114).
  - Pool 2 gleichzeitig (copy_context je Thread), Ergebnis verwerfen.
  - Hauptabruf wartet auf Ende des Vorwärmens (Join) — es gibt kein Single-flight im Raster-Abruf.
  - Exception/Timeout im Vorwärmen: nur Log-Zeile, Bericht läuft weiter wie heute.

S2 Segmentschleife
  - _fetch_weather: fetch_ordered statt serieller Schleife; Ergebnisreihenfolge = Segmentreihenfolge;
    Retry/Backoff je Segment wie bisher.

Cache
  - Punkt-Fenster-Cache dwd.py: Obergrenze 512 → 2048 URLs.
```

**Nachtrag Umsetzung (Validierung 2026-10-19):** Für den Startpunkt der Dauer-Messung (AC-1, „Eingang beim Core") wurden zusätzlich die drei Befehls-Eingänge `src/services/inbound_email_reader.py`, `src/services/inbound_telegram_reader.py` und `src/services/inbound_sms_reader.py` angepasst (zusammen +30/−4 Zeilen): Sie setzen den Eingangszeitpunkt bzw. markieren den erkannten Befehl. AC-16 liegt im Repo `henemm-infra` (Commit `544008e`, Abschnitt 2f in `scripts/check-gregor20.sh`, Tests `tests/test_check_gregor20_push_missed.py`).

## Expected Behavior

- **Input:** Befehl des Nutzers über E-Mail, Telegram, SMS oder Premium-SMS (unverändert).
- **Output:** Dieselbe Antwort wie heute, nur schneller; je Befehl eine Dauer-Zeile im Journal.
- **Side effects:** Kurzzeitig bis zu 2 gleichzeitige DWD-Fensterabrufe pro Bericht; Cache bis ~28 MB; zusätzliche Journal-Zeilen.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer sendet einen beliebigen Befehl (z. B. `HELP`, `HEUTE`) über einen der vier Kanäle, When der Befehl verarbeitet und die Antwort an den Versand-Provider übergeben wurde, Then steht im Journal genau eine Zeile mit Befehl, Kanal, Trip-ID und Dauer in Millisekunden, gemessen vom Eingang beim Python-Core bis zur Übergabe — ohne Nachrichtentext, Absenderadresse oder Telefonnummer.
  - Test: Kern-Test ruft den Befehlsweg mit lokalem Versand-Ersatz auf und liest die Journal-Zeile; Gegenprobe: Zeile enthält keinen Nachrichtentext und keine Adresse. Zwei Nutzer mit je eigenem Trip → jede Zeile trägt die eigene Trip-ID.

- **AC-2:** Given ein `HEUTE` oder `MORGEN` wird berechnet, When der Bericht gebaut wird, Then gibt das Journal die Zeit je Phase (Zieltag-Segmente, Nacht, Ausblick, Gewitter +1/+2, Ensemble, Warnungen, Rendern) sowie je DWD-Tagesfenster Fensterzeit, Anzahl Downloads und Cache-Treffer aus.
  - Test: Kern-Test mit lokalem, künstlich verzögertem Raster-Server liest die Zeilen; die Summe der Phasenzeiten liegt innerhalb von 10 % der Gesamtdauer-Zeile.

- **AC-3:** Given Befehle ohne Wetterabruf (`HELP`, `CODES`, `STATUS`), When sie auf Staging über jeden echten Befehlseingang gesendet werden (E-Mail, Telegram, Premium-SMS-Rückkanal über seven.io — über ihn läuft auch der SMS-Befehlseingang), Then liegt die gemessene Dauer-Zeile auf jedem dieser Eingänge bei jedem Lauf unter 30 Sekunden.
  - Test: Live-Test in `tests/e2e/test_push_eingang_befehle_staging.py`, mindestens 5 Läufe je Befehl und Eingang, alle < 30 s (aus der Journal-Zeile, nicht aus dem Gesamtlauf).

- **AC-4:** Given ein Trip auf der DE/Alpen-Route (DWD + GeoSphere) und ein kalter Zustand (neuer Prozess bzw. erster Abruf des Kalendertags: die DWD-Fenster werden vor dem Lauf durch Neustart von `gregor-python-staging` bzw. einen Trip mit noch nie abgerufenem Datum herbeigeführt), When `HEUTE` und `MORGEN` je mindestens 5-mal auf Staging über den echten Eingang gesendet werden (jeder der drei Eingänge E-Mail, Telegram, Premium-SMS mindestens einmal darunter), Then liegt **jeder einzelne** Lauf unter 60 Sekunden **und** der Median unter 45 Sekunden.
  - Test: Live-Test fährt ≥ 5 kalte Läufe je Befehl, liest die Dauer-Zeilen (AC-1), prüft max < 60 s und Median < 45 s und gibt alle Einzelwerte aus. Ausgangswert zum Vergleich: 57,8 s (Messung 18.10.).

- **AC-5:** Given ein Trip auf der Korsika-Route (`fr_direct`, Météo-France), When `HEUTE` und `MORGEN` kalt je mindestens 3-mal auf Staging über den echten Eingang gesendet werden, Then gilt dieselbe Zielgröße wie in AC-4: jeder Lauf unter 60 Sekunden.
  - Test: Live-Test mit Korsika-Trip, liest die Dauer-Zeilen (AC-1), prüft max < 60 s und gibt alle Einzelwerte aus. Verfehlt die Route das Ziel, ist das ein Befund in diesem Ticket (Abrufpfad `fr_direct` beschleunigen), keine Ausnahme.

- **AC-6:** Given ein Bericht braucht mehrere DWD-Tagesfenster (Zieltag, Nacht, +1, +2), When das Vorwärmen läuft, Then werden höchstens 2 Fenster gleichzeitig geladen und die Gesamtzeit liegt nahe der Zeit des langsamsten Fensters statt der Summe aller.
  - Test: Kern-Test mit lokalem HTTP-Server, der jede Datei künstlich verzögert und die gleichzeitigen Verbindungen zählt: Spitze der gleichzeitigen Fenster = 2; Gesamtzeit < 0,75 × Summe der Einzelzeiten. Kein `patch()`/Mock.

- **AC-7:** Given das Vorwärmen ist abgeschlossen, When der Hauptabruf desselben Berichts läuft, Then macht er 0 Netz-Downloads für diese Fenster (alle Treffer aus dem Cache), weil die vorgewärmten Fenster schlüsselgleich mit dem späteren Abruf sind — auch für ein kurzes 2-Stunden-Segment, dessen Fenster am ersten Datenpunkt des ganzen Kalendertags beginnt.
  - Test: Kern-Test liest den Download-Zähler des lokalen Raster-Servers nach dem Vorwärmen und nach dem Hauptabruf (Differenz = 0); Variante mit 2-h-Segment und Variante mit ganztägigem Segment. Gemessen wird der Zähler, nicht die Gesamtzeit.

- **AC-8:** Given das Vorwärmen läuft noch, When der Hauptabruf startet, Then wartet er auf das Ende des Vorwärmens (Join), sodass keine Datei doppelt geladen wird.
  - Test: Kern-Test mit langsamem lokalem Server: Zähler zeigt je Datei höchstens einen Download; der Hauptabruf beginnt erst nach dem Ende der Vorwärm-Fenster.

- **AC-9:** Given das Vorwärmen scheitert oder überschreitet die Zeit (Server liefert Fehler bzw. antwortet nicht), When der Bericht gebaut wird, Then wird der Bericht trotzdem erzeugt und versendet, der Hauptabruf läuft wie vor dieser Änderung, und das Journal vermerkt den Fehlschlag des Vorwärmens.
  - Test: Kern-Test mit lokalem Server, der Fehler und Hänger liefert: Bericht kommt an, Inhalt entspricht dem Stand ohne Vorwärmen, Journal-Zeile „Vorwärmen fehlgeschlagen“ vorhanden.

- **AC-10:** Given ein Trip mit mehreren Segmenten, When die Wetterdaten für alle Segmente geholt werden, Then laufen die Abrufe parallel (Semaphore je Provider), das Ergebnis behält die Reihenfolge der Segmente, und ein fehlschlagendes Segment wird wie bisher mit Wiederholung/Backoff behandelt, ohne die übrigen zu blockieren.
  - Test: Kern-Test mit lokalem verzögertem Server und gestaffelten Antwortzeiten: Ergebnisliste in Segmentreihenfolge, Gesamtzeit < 0,75 × serielle Summe; ein Segment mit zwei Fehlern und dann Erfolg liefert sein Ergebnis; Aufruf aus einem Worker-Thread wird gesondert geprüft (kein stilles Zurückfallen auf seriell, oder dokumentierte Entscheidung im Test).

- **AC-11:** Given der DWD-Punkt-Fenster-Cache ist auf 2048 URLs vergrößert, When ein Trip-Bericht (~415 Dateien) und gleichzeitig ein Alarm- bzw. Ortsvergleichslauf Fenster laden, Then wird der Vorwärm-Bestand des Trips nicht mitten im Lauf verdrängt (Hauptabruf macht weiter 0 Downloads) und der Speicherbedarf bleibt unter 40 MB.
  - Test: Kern-Test füllt den Cache mit der Trip-Dateimenge plus einer zweiten Dateimenge gleicher Größe und prüft, dass alle Trip-Einträge noch vorhanden sind; Speichermessung des gefüllten Caches < 40 MB.

- **AC-12:** Given auf demselben Kanal läuft gerade ein `HEUTE`, When währenddessen ein `HELP` eingeht, Then antwortet das System mit dem `HELP` spätestens 30 Sekunden nach Ende des `HEUTE` (Lock belegt → „busy“ → Weckruf bleibt pending → Nachlauf), und im ungünstigsten Fall liegt die Gesamtzeit des `HELP` unter 90 Sekunden.
  - Test: Live-Test auf Staging über echten Eingang (E-Mail und SMS): `HEUTE` senden, direkt danach `HELP`; Differenz zwischen Ende der `HEUTE`-Dauer-Zeile und Übergabe der `HELP`-Antwort ≤ 30 s und `HELP`-Gesamtzeit < 90 s.

- **AC-13:** Given dieselben aufgezeichneten Eingangsdaten (Wetterrohdaten eines Trips), When der Bericht einmal im Stand vor dieser Änderung (seriell, ohne Vorwärmen) und einmal im neuen Stand gebaut wird, Then sind die erzeugten Berichte (E-Mail-HTML/Text, Telegram-, SMS-Kurzform) bit-identisch; Nacht, Ausblick, Gewitter +1/+2 und Ensemble sind unverändert enthalten. Zusätzlich sind Modus-Matrix-Test und `briefing_mail_validator.py` am Commit frisch grün (Renderer-Commit-Gate).
  - Test: Golden-Vergleich mit versionierter Fixture und lokalem Raster-Server (Referenz-Ausgabe vor der Änderung eingefroren); Validator-Lauf gegen eine echt zugestellte Staging-Briefing-Mail (Exit 0).

- **AC-14:** Given der SMS-Nachversuch 0/3/8 Sekunden ist implementiert, When auf Staging eine echte SMS von der zweiten seven.io-Nummer als Befehl gesendet wird, Then ist `tests/e2e/test_push_eingang_befehle_staging.py::test_ac1_sms_last_run_sekunden_nach_webhook` grün, `last_run.status` ist `ok` und das Staging-Log enthält keinen EOF-Fehler.
  - Test: Live-Test mit echter SMS auf Staging; Log-Auszug ohne „EOF“ und `last_run.status == ok` als Beleg.

- **AC-15:** Given die Prod-Hooks sind bei seven.io (`sms_mo`) und Stalwart (Eventname `message-ingest.ham`) registriert, When ein echter Prod-Befehl gesendet wird, Then steigt `received_total` des betreffenden Kanals im Prod-Push-Status (`/api/scheduler/status` mit gültigem `X-GZ-Status-Token`) über 0, und der Befehl wird sofort ohne Warten auf den 5-Minuten-Tick beantwortet.
  - Test: Beleg über Prod-Push-Status vor und nach einem echten Prod-Befehl (Wert `received_total` je Kanal); ohne Anstieg gilt die Registrierung als nicht erfüllt.

- **AC-16:** Given das externe Monitoring läuft, When `push.missed_total` eines Kanals gegenüber dem vorigen Lauf steigt, Then meldet `henemm-infra/scripts/check-gregor20.sh` einen Fehler (ERRORS > 0, kein BetterStack-Heartbeat-Ping); bleibt der Zähler gleich, wird nicht als Fehler gewertet und der Ping erfolgt (Readiness-Prinzip: nur bei fachlichem Erfolg).
  - Test: Das Skript wird in einer Kopie gegen ein gestelltes Status-JSON geprüft (steigender Zähler → Fehler und kein Ping; gleicher Zähler → Ping; fehlender Zähler/Statusabruf-Fehler → kein Ping). Mutation nur in der Kopie (der Arbeitsbaum von henemm-infra ist sofort live); infra-Änderung wird zuerst ausgeliefert.

- **AC-17:** Given das Runbook `docs/runbooks/inbound-webhooks.md`, When ein Leser die Registrierung des Stalwart-Hooks nachschlägt, Then steht dort der Eventname `message-ingest.ham` als verifiziert (Z. 55-58 und Z. 102), ohne den Hinweis „vor Registrierung verifizieren“, und `store.ingest` ist als nicht existierend vermerkt.
  - Test: Doku-Prüfung (`# doc-compliance-test`): Runbook enthält `message-ingest.ham` an beiden Stellen und keinen „vor Registrierung verifizieren“-Satz mehr.

## Test Plan

Geplante Tests, nach Verhalten benannt, kein Mock-Theater:

- `tests/test_befehl_antwortzeit.py` (Kern): Dauer-Zeile (AC-1/2), Vorwärmen parallel ≈ Maximum statt Summe (AC-6), 0 Downloads danach (AC-7), Join (AC-8), Fehlertoleranz (AC-9), Segmente parallel und in Reihenfolge (AC-10), Cache-Kapazität (AC-11), Golden-Vergleich Inhalt identisch (AC-13). Lokaler, künstlich verzögerter Raster-/HTTP-Server bzw. aufgezeichnete Daten; Prüfling relativ zur Testdatei aufgelöst.
- `tests/e2e/test_push_eingang_befehle_staging.py` (Live, nur `/e2e-verify`): Zielgrößen je Befehlsklasse (AC-3/4/5), `HELP` während `HEUTE` (AC-12), SMS-Nachversuch (AC-14).
- Betriebsbelege: Prod-Push-Status (AC-15), `check-gregor20.sh`-Kopie (AC-16), Runbook-Prüfung (AC-17).

## Out of Scope

- **Hintergrund-Vorwärmen rund um die Uhr:** dauerhafte DWD-Last, 250+ LoC, hohes Risiko; Vorwärmen nur im Befehlslauf reicht für das Ziel.
- **Eigener CAPE-/SNOWGRID-Cache:** ändert die Cache-Semantik für Alarm und Ortsvergleich; der Gewinn wird durch die parallele Segmentschleife (S2) abgedeckt.
- **Poll-Lock entkoppeln:** gefährdet Zustellreihenfolge und Kanaltreue, spart keine Rechenzeit (Entscheidung 6).
- **Inhaltskürzung** (weniger Stunden für +1/+2, Ausblick weglassen): Produktentscheidung des PO, keine Optimierung; Inhalt bleibt unverändert (Entscheidung 7).
- Nginx-Versionierung: bereits erledigt (henemm-infra PR #266).

## Known Limitations

- **Korsika (`fr_direct`):** vor der Spec nicht gemessen (Zugangsdaten im Mess-Harness nicht verfügbar). Die Zielgröße gilt trotzdem verbindlich (AC-5); die erste Messung erfolgt auf Staging. Das Vorwärmen (S1) betrifft nur DWD; Korsika profitiert vor allem von der parallelen Segmentschleife (S2).
- **DWD-Schwankung:** ein Tagesfenster braucht 6-30 s auch nach den Maßnahmen; daher harte Obergrenze plus Median über mindestens 5 Läufe.
- **Parallelität spart keine Downloads**, nur Wartezeit (~20-30 %); mehr als 2 gleichzeitige Fenster bringt wegen Bandbreite nichts.
- **Prod evtl. schneller als Staging:** der dauerhaft laufende Prozess und der 15-Minuten-Alarmzyklus halten Fenster eventuell warm; nicht gemessen, daher gilt die Zielgröße zunächst nur für Staging kalt.
- **Poll-Lock:** ein `HELP` hinter einem laufenden `HEUTE` desselben Kanals wartet (AC-12), Telegram ist davon nicht betroffen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Keine Grundsatzentscheidung zu Kanälen, Provider-Wahl, Datenmodell oder Auth: Inhalt, Kanäle und Persistenz bleiben unverändert; geändert werden nur Abrufreihenfolge (Vorwärmen, Parallelität), Cache-Obergrenze und Beobachtbarkeit.

## Changelog

- 2026-10-18: Initial spec created (v1.0) — schließt #2439 komplett ab (Zielgröße, Beobachtbarkeit, Vorwärmen, parallele Segmentschleife, Cache 2048, Teil-a-Betriebs-Rest)
- 2026-10-18: v1.1 — Zielgrößen gelten ausdrücklich auf allen drei Befehlseingängen inkl. Premium-SMS (AC-3/AC-4) und verbindlich auch für Korsika (AC-5), statt dort nur zu berichten
- 2026-10-19: Nachtrag Implementation Details — drei Eingangs-Reader als Mess-Startpunkt, Ort der AC-16-Umsetzung in henemm-infra (keine AC-Änderung)
