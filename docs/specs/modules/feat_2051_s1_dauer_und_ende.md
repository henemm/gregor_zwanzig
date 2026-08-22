---
entity_id: feat_2051_s1_dauer_und_ende
type: feature
created: 2026-08-21
updated: 2026-08-22
status: approved
version: "1.1"
tags: [alarm, briefing, nowcast, radar, dauer, ende]
---

# Ereignis-Ende und -Dauer im Nowcast mitliefern — #2051 Scheibe S1

## Approval

- [x] Approved — PO-Freigabe der Acceptance Criteria am 2026-08-21 (v1.0)
- [x] Approved — PO-Freigabe der geänderten Kriterien AC-5, AC-16 und des
  neuen AC-20 am 2026-08-22 (v1.1, Umkehr auf die Untergrenzen-Form)

## Purpose

Der Radar-/Nowcast-Pfad liest aus der abgerufenen Frame-Zeitreihe heute nur den
**ersten** nassen Zeitpunkt (`onset_minutes`) und bricht danach ab — der Rest der
bereits vorliegenden Zeitreihe wird verworfen. Der Nutzer erfährt, *wann* es
anfängt, aber nicht, **wie lange es dauert und wann es endet**. Diese Spec
leitet Ende und Dauer des zusammenhängenden nassen Blocks aus **denselben,
bereits abgerufenen Frames** ab (kein zusätzlicher Quellenabruf) und liefert
sie additiv in allen sieben Textstellen mit, die den Ereignisbeginn heute schon
ausformulieren. S2 (räumliche Ausdehnung), S3 (Reichweite der Quelle) und S4
(`/strecke`-Kommando) aus Issue #2051 bleiben ausdrücklich außerhalb dieses
Zuschnitts; das Ticket bleibt als Scheiben-Ticket offen.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `_derive_result()` (Z. 700-…), neuer Helfer
  `_derive_wet_block_end()`, `NowcastResult` (Z. 137-190)

Begleitend: `src/output/renderers/alert/model.py` (`OnsetEvent`),
`src/services/notification_service.py` (`RadarAlertRequest`, Z. 165),
`src/services/trip_alert.py` (`check_radar_alerts`, Z. 1330-1499),
`src/services/compare_radar_alert.py` (Z. 352, Ortsvergleich-Pendant),
`src/output/renderers/alert/project.py` (Z. 368-405, Mehr-Orte-Bündel),
`src/output/renderers/alert/render.py` (Textstellen 1-5),
`src/output/renderers/email/starkregen_hint.py` (Textstelle 6),
`src/services/trip_report_scheduler.py` (Z. 366, 1870, Datenform des
Briefing-Tupels), `api/routers/validator.py` (`OnsetPayload`),
`src/services/validator_render_service.py` (Vorschau-/Replay-Weg).

> **Schicht-Hinweis:** Alle Änderungen liegen ausschließlich im Python-Core
> (`src/services/`, `src/output/`, `api/routers/`) — kein Go-API-, kein
> Frontend-Anteil.

## Estimated Scope

- **LoC:** ~200-240 produktiv, ~150-220 Tests bei voller Reichweite —
  **über dem 250-LoC-Workflow-Limit**, `workflow.py set-field
  loc_limit_override 500` ist vor `/40-tdd-red` einzuplanen.
- **Files:** 11 Produktivdateien + ~10-12 Testdateien (Neuanlagen + Bestand
  fortgeschrieben).
- **Effort:** high.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_accumulate_precip_mm` | function (`radar_service.py:200-242`) | Bestehender, aus #2046 extrahierter Rechenkern: Frame-Dedup je Zeitstempel (höherer Wert gewinnt), Dauer je Frame aus dem eigenen nächsten Nachbarn (`bisect_right` über `all_ts_sorted`), Deckel `_MAX_FRAME_COVERAGE` (15 Min), hartes Fensterende. Wird für Summenbildung weiterverwendet, nicht für die neue Grenzfindung. |
| `NowcastResult.onset_minutes` / `.frames` | fields (`radar_service.py:139,142`) | Bestehende Felder — `frames` trägt bereits die vollständige Zeitreihe, aus der auch das Ende abgeleitet wird. |
| `_NOWCAST_HORIZON_MIN` | constant (`radar_service.py:69`, Wert 180) | Bleibt unverändert (E3) — Herleitung von #1945, dort bewusst von 60 auf 180 angehoben. |
| `RADAR_ONSET_THRESHOLD_MIN` | constant (`radar_service.py:121`, Wert 55) | Auslöse-Schwelle des Alarms — von dieser Spec unberührt, nur die Anzeige ändert sich. |
| `RadarAlertRequest` | DTO (`notification_service.py:165-194`) | Trip-Pfad-Transport; bekommt additiv-optionale Ende-Felder, Muster `onset_precip_mm` (#2046). |
| `OnsetEvent` | dataclass (`model.py:38-62`) | Renderer-Modell; bekommt dieselben additiven Felder. |
| `OnsetPayload` | Pydantic-Model (`api/routers/validator.py:~240`) | Vorschau-Payload-Schema — muss das neue Feld kennen, sonst Adversary-Fund wie #2046 F002. |
| `starkregen_nowcast: tuple[str, int] \| None` | field (`notification_service.py:110`) | Bestehende, zu **enge** Datenform des Briefing-Pfads — muss um Ende/Dauer/Wächter erweitert werden (vier Stellen). |
| `_onset_time_label()` / Δ-Teil `_render_sms_body` | functions (`render.py`) | Von dieser Spec **nicht** angefasst — Zusage an die Parallelsitzung `fix-2020-zeitangaben-wortlaut` (#2020 S2). |

## Getroffene Entscheidungen (E1-E3, aus Phase 2 — nicht erneut vorlegen)

**E1 — Reichweite: alle sieben Textstellen.** E-Mail-Betreff,
E-Mail Mehr-Orte-Bündel (Ortsvergleich), E-Mail Trip, Telegram (rich),
SMS/Premium-SMS/Telegram-Kurzstil, Briefing-Kurzfristhinweis und
Inbound-Kommando-Antwort bekommen alle die Ende-Angabe. Begründung: Ein
Zuschnitt ohne die Alarmtexte adressiert die eigene Problemstellung des
Tickets nicht — dieses rahmt das Problem als „das Alarmsystem meldet heute
einen Punkt". Ein Zuschnitt auf Briefing-Hinweis + Kommando-Antwort (die
beiden ungedeckelten Pfade) ließe **SMS und Premium-SMS ohne die Angabe** —
und auf der Hütte (nur Satellit) ist Premium-SMS der einzige ankommende Kanal.

**E2 — Tagesfenster: nicht kappen.** Das echte, aus den Frames abgeleitete
Ende wird genannt, auch wenn es über das konfigurierte Tagesfenster
hinausreicht. Drei Gründe: (a) Der Nowcast-Pfad spricht heute schon außerhalb
des Tagesfensters — `onset_time` wird nirgends gekappt; nur das Ende zu kappen
wäre in sich unstimmig. (b) Die Tagesfenster-Konsistenzbegründung aus
`segment_weather.py:292-308` gilt dem prognosebasierten Δ-Alarm, der gegen
Briefing-Zahlen vergleicht — für das Nowcast-Ende gibt es keine
Briefing-Entsprechung, mit der es sich widersprechen könnte. (c) Ein still
gekapptes „Ende gegen 20:00" bei Regen bis 22:00 wäre eine falsche Aussage —
dieselbe Fehlerklasse wie R4, nur selbst verursacht.

**E3 — Horizont: `_NOWCAST_HORIZON_MIN` bleibt bei 180.** Keine Kappung auf
60 — das nähme die #1945-Entscheidung (dort bewusst 60 → 180 angehoben, weil
der 60-Min-Deckel den Alarm praktisch immer erst ~8 Min vorher auslösen ließ)
still zurück. Der Alarmzweig wäre von einer Kappung ohnehin kaum betroffen
(deckelt bereits hart bei 55 Min); getroffen würden `window_precip_mm`,
`onset_precip_mm`, der Briefing-Hinweis und die Kommando-Antwort — genau die
Pfade, aus denen der im Ticket geschilderte Realfall stammt. Die vom PO
erwogene Güte-Kennzeichnung **ist** der `event_ongoing_beyond_horizon`-Wächter
(s. Implementation Details) — keine zusätzliche Kappung nötig.

## Implementation Details

Die Onset-Schleife (`radar_service.py:724-729`) läuft bereits über das
sortierte Fenster und bricht beim ersten nassen Frame ab. Die Blockende-
Bestimmung ist dieselbe Schleife **ohne** den Abbruch, ab dem Beginn-Frame
weitergeführt. Zwei Fälle, **beide ohne neue Toleranzzahl**:

| Fall | Bedeutung | Behandlung |
|---|---|---|
| Frame vorhanden, `precip_mm_h < 0.1` | Quellenaussage „hier hat es aufgehört" | beendet den Block **real** — nicht überbrücken, sonst verschmelzen zwei getrennte Ereignisse und die Dauer wird überschätzt. |
| Frame **fehlt** (Rasterlücke, Drosselung, Ausfall) | keine Beobachtung | Der letzte nasse Frame deckt ohnehin nur bis `min(nächster Frame, +_MAX_FRAME_COVERAGE, Horizontende)` — dieselbe Nachbar-Deckungslogik wie in `_accumulate_precip_mm`. Lücken bis 15 Min sind damit **implizit** toleriert; größere Lücken setzen das Ende an der Deckungsgrenze, nicht am nächsten wieder nassen Frame danach. |

**Neuer Helfer als Geschwister von `_accumulate_precip_mm`** (nicht dessen
Erweiterung — dessen Aufgabe ist Summieren in einem bekannten Fenster, nicht
Grenzen finden):

```
_derive_wet_block_end(
    frames: list, all_ts_sorted: list, onset_ts: datetime, horizon: datetime,
) -> tuple[datetime, bool]
```

Rückgabe: `(end_ts, ongoing_beyond_horizon)`. Läuft ab `onset_ts` über die
sortierten Frames im Fenster, endet beim ersten Trockenframe oder an der
Deckungsgrenze einer Lücke; erreicht die Schleife den Horizont, während der
letzte bekannte Frame noch nass war, ist `ongoing_beyond_horizon = True` und
`end_ts` der Horizont selbst (nicht behauptbar als echtes Ende).

**Zwei neue Felder auf `NowcastResult`** (`radar_service.py`, additiv,
optional, Muster `onset_precip_mm` aus #2046):

```python
event_end_minutes: Optional[int] = None
# Issue #2051 S1: Minuten ab jetzt bis zum Ende des zusammenhaengenden nassen
# Blocks, analog onset_minutes. None wenn onset_minutes None ist.
event_ongoing_beyond_horizon: bool = False
# R4-Waechter: die Frames bzw. der 180-Min-Horizont sind ausgegangen, waehrend
# der letzte bekannte Frame noch nass war. False heisst "das echte Ende ist
# bekannt" -- konsistent mit throttled/data_unavailable als
# Beobachtbarkeits-Signal.
```

**Keine** gespeicherte `event_duration_minutes` — sie ist stets
`event_end_minutes - onset_minutes`; ein drittes Feld könnte auseinanderlaufen
und würde bei jedem Konsumenten eine zweite Quelle der Wahrheit schaffen.

**Downstream `event_end_time` / `event_end_day_offset`** als Pendants zu
`onset_time`/`onset_day_offset`, über **dieselbe** Zeitversatz-Logik
(#2009-Muster: `_end_dt = now_utc + timedelta(minutes=event_end_minutes)`,
`local_fmt(_end_dt, tz)` für die Uhrzeit, `day_offset(now_utc, _end_dt, tz)`
für den Tagesversatz) — nicht neu implementiert. Das ist bewusst
**asymmetrisch** zum Beginn: Beginn und Ende können unterschiedliche
Tagesversätze tragen (Beginn 23:50 ohne Versatz, Ende 00:40 mit
`day_offset=1`).

**Zwei Pydantic-Modelle** brauchen das neue Feld: `RadarAlertRequest`
(`notification_service.py:165`) und `OnsetPayload`
(`api/routers/validator.py:~240`). Bei #2046 war genau das der
Adversary-Fund F002 — hier vorab bekannt, beide Stellen sind im Test-Plan
gelistet.

**Briefing-Pfad (Textstelle 6) — Datenform muss aufgemacht werden.** Heute
transportiert `notification_service.py:110`
`starkregen_nowcast: tuple[str, int] | None` (nur `intensity_label`,
`onset_minutes`), gebaut in `trip_report_scheduler.py:1870` als
`return (result.intensity_label, result.onset_minutes)`, ausgepackt `:366`,
verbraucht von
`format_starkregen_hint(intensity_label, onset_minutes, *, tz)`. Für Ende und
Wächter reicht das Tupel nicht mehr — Erweiterung auf ein Tupel mit den
zusätzlichen Feldern (oder ein kleines Objekt) an allen vier Stellen:
`notification_service.py:110`, `trip_report_scheduler.py:1870` und `:366`,
`starkregen_hint.py` (Signatur von `format_starkregen_hint`).

**Wortlaut — von der Parallelsitzung #2020 S2 übernommen, nicht neu
erfunden:**

- **Langform** (E-Mail-Betreff, E-Mail Trip, E-Mail Mehr-Orte, Telegram rich,
  Briefing-Hinweis, Kommando-Antwort): `letzter Regen gegen HH:MM`
- **Kurzform** (SMS/Premium-SMS/Telegram-Kurzstil): `@HH` direkt hinter dem
  Mengen-Token aus #2046, z. B. `R2.5@18:00@20`.
- **Langform Untergrenze** (bei gesetztem `event_ongoing_beyond_horizon`,
  alle sieben Textstellen): `Regen mindestens bis HH:MM`.
- **Kurzform Untergrenze** (SMS/Premium-SMS/Telegram-Kurzstil, bei gesetztem
  Wächter): ` >@HH:MM` — ein Leerzeichen, dann `>`, dann das Zeit-Token,
  z. B. `km 8-8: R2.5@18:00 >@20:00`. Schreibweise vom PO vorgegeben
  (2026-08-22).

Die Kurzform-Untergrenze trägt eine **absolute Uhrzeit**, keine relative
Dauer (»+60min«): Die Premium-SMS kommt auf der Hütte über Satellit an, teils
verzögert — eine relative Angabe würde durch die Zustellverzögerung still
falsch, eine absolute Uhrzeit bleibt richtig. Dieselbe Begründung trägt schon
`onset_day_offset` aus #2009.

Das Zeit-Token ist bei der Untergrenze bewusst **minutengenau** (`HH:MM`) und
nicht nur die Stunde: Die Quellen liefern ein 15-Minuten-Raster (INCA/AROME
am Karnischen Höhenweg) bzw. 5 Minuten (RADOLAN) — `20:45` auf `20` zu kürzen
wäre bis zu 45 Minuten daneben. Der PO hat dazu die Briefing-Konvention `%Hh`
(nur Stunde, `sms_trip.py:753`) angeführt; die gilt dort für die **geplante**
Etappen-Startzeit, die naturgemäß auf vollen Stunden liegt, nicht für einen
Messzeitpunkt.

`_onset_time_label()` und der Δ-Teil von `_render_sms_body` bleiben
**unangetastet** (Zusage an `fix-2020-zeitangaben-wortlaut`).

**Bei gesetztem `event_ongoing_beyond_horizon` rendert jeder der sieben
Textkonsumenten die Untergrenzen-Form statt der Normalform** — nicht mehr
die Ausweichform ohne Ende (PO-Entscheid 2026-08-22, kehrt die ursprüngliche
Entscheidung um). Begründung: `event_end_minutes` ist in beiden
Wächter-Fällen bereits eine belegte, keine geratene Zahl — im Code verifiziert
in `_derive_wet_block_end` (`radar_service.py:260-320`): Erreicht die
Schleife den Horizont, während der letzte bekannte Frame noch nass war
(`coverage_end >= horizon`), regnet es nachweislich durchgehend bis dorthin;
bricht die Zeitreihe ab (`next_ts is None`), ist die Untergrenze der letzte
bekannte nasse Frame plus seine `_MAX_FRAME_COVERAGE`-Deckung. Beides ist eine
Beobachtung, keine Extrapolation über den Horizont hinaus. Das Weglassen
(Ursprungsentscheidung) verwarf damit eine wahre, beobachtungsgestützte
Aussage — die Untergrenzen-Form nennt sie, ohne ein unbekanntes echtes Ende zu
behaupten (AC-20 grenzt beide Formen textlich voneinander ab). Es ist keine
neue Rechnung nötig, `event_end_minutes` trägt bereits die richtige Zahl —
nur die Textform ändert sich.

**Horizont-Drift-Korrektur (gehört in S1, s. u.):** `format_now_text()`
(`radar_service.py:431`) sagt im Trockenzweig „In den nächsten 2 Stunden kein
Regen erwartet." — geprüft werden seit #1945 tatsächlich 3 Stunden
(`_NOWCAST_HORIZON_MIN = 180`). Der Docstring von `starkregen_hint.py:4`
nennt „60-Minuten-Nowcast-Fenster (`NOWCAST_HORIZON_MIN`)" — der Wert ist
180. Beide werden in dieser Spec korrigiert (eigenes AC, eigener Commit),
nicht als separates Ticket oder stille Nebenreparatur.

## Expected Behavior

- **Input:** `NowcastResult` mit gesetztem `onset_minutes` und Frames, die den
  zusammenhängenden nassen Block ganz oder teilweise abdecken (bis zum
  Horizont oder bis zum tatsächlichen Ende).
- **Output:** alle sieben Textstellen tragen zusätzlich eine Ende-Angabe. Bei
  `event_ongoing_beyond_horizon=False` in der Normalform
  (`letzter Regen gegen HH:MM` / `@HH:MM`), bei
  `event_ongoing_beyond_horizon=True` in der Untergrenzen-Form
  (`Regen mindestens bis HH:MM` / ` >@HH:MM`, PO-Entscheid 2026-08-22).
  Nur wenn `onset_minutes is None` ist, bleibt der Text unverändert wie heute.
- **Side effects:** keine — reine additive Feld-Durchreichung plus
  Renderer-/Formatierungserweiterung. Kein Datenmodell-Bruch (alle neuen
  Felder optional mit Default), keine Persistenz betroffen, keine Änderung an
  der Auslöseregel (`radar_alert_due`) oder der #2020-Überholungsprüfung.

## Acceptance Criteria

- **AC-1:** Given eine Frame-Zeitreihe mit einem zusammenhängenden nassen
  Block (durchgängig `precip_mm_h >= 0.1` von Minute 20 bis Minute 80, danach
  trocken) / When `_derive_result` daraus `event_end_minutes` ableitet / Then
  entspricht `event_end_minutes` dem Zeitpunkt des letzten nassen Frames vor
  dem Trockenübergang (Minute 80), nicht dem Horizontende und nicht dem
  Beginn.
  - Test: Unit-Test gegen `_derive_wet_block_end` bzw. `_derive_result` mit
    konstruierten Frames im 5-Minuten-Raster, `event_end_minutes` gegen den
    erwarteten Wert geprüft.

- **AC-2:** Given zwei getrennte nasse Blöcke in derselben Frame-Zeitreihe
  (nass Minute 10-30, trocken Minute 35-50, wieder nass Minute 55-70) / When
  `_derive_result` Beginn und Ende ableitet / Then endet der Block beim ersten
  Trockenframe nach Minute 30 — das zweite, spätere Ereignis wird NICHT in
  `event_end_minutes` eingerechnet, die beiden Ereignisse verschmelzen nicht
  zu einer überlangen Dauer.
  - Test: Unit-Test mit den zwei getrennten Blöcken, `event_end_minutes`
    liegt nahe bei Minute 30, nicht bei Minute 70.

- **AC-3:** Given einen nassen Block, in dem ein einzelner Frame mitten drin
  fehlt (Raster sonst 10-Minuten-Kadenz, eine Lücke von 10 Minuten — innerhalb
  der `_MAX_FRAME_COVERAGE`-Deckung von 15 Minuten) / When das Ende abgeleitet
  wird / Then wird der Block durch die Lücke NICHT fälschlich beendet — das
  Ende liegt beim letzten tatsächlich nassen Frame nach der Lücke, nicht bei
  der Lücke selbst.
  - Test: Unit-Test mit einer 10-Minuten-Datenlücke mitten im nassen Block,
    `event_end_minutes` zeigt auf den späteren, nach der Lücke liegenden
    nassen Frame.

- **AC-4:** Given einen nassen Block mit einer Datenlücke von 25 Minuten
  (größer als `_MAX_FRAME_COVERAGE` = 15 Minuten) mitten drin, gefolgt von
  einem erneut nassen Frame / When das Ende abgeleitet wird / Then wird das
  Ende an der Deckungsgrenze des letzten Frames vor der Lücke gesetzt
  (`Frame-Zeitstempel + 15 Minuten`), NICHT am nach der Lücke wieder nassen
  Frame — dieselbe Deckungsmechanik wie `_accumulate_precip_mm`, keine neue
  Toleranzzahl.
  - Test: Unit-Test mit 25-Minuten-Lücke, `event_end_minutes` exakt
    `Beginn-Frame-Zeit-des-letzten-Frames-vor-der-Luecke + 15 Min` geprüft.

- **AC-5:** Given eine Frame-Zeitreihe, deren letzter verfügbarer bzw. bis zum
  180-Minuten-Horizont reichender Frame noch nass ist (kein Trockenframe im
  gesamten Fenster) / When `_derive_result` das Ergebnis baut und die sieben
  Textstellen gerendert werden / Then ist `event_ongoing_beyond_horizon=True`,
  und JEDE der sieben Textstellen nennt das Ende als belegte UNTERGRENZE statt
  es wegzulassen: Langform `Regen mindestens bis HH:MM`, Kurzform ` >@HH:MM`.
  Der genannte Zeitpunkt ist der aus `event_end_minutes` abgeleitete — in
  beiden Wächter-Fällen (Horizont erreicht bzw. Zeitreihe abgebrochen) eine
  beobachtungsgestützte Untergrenze, keine Schätzung.
  - Test: Ein Unit-Test gegen `_derive_result` prüft das Flag selbst; je ein
    Renderer-Test für die Langform (E-Mail Trip), die Kurzform (SMS) und den
    Briefing-Hinweis prüft die Anwesenheit der Untergrenzen-Form.

- **AC-20:** Given denselben Aufbau wie AC-5 (`event_ongoing_beyond_horizon=True`) /
  When die sieben Textstellen gerendert werden / Then erscheint in KEINEM der
  Texte die Normalfall-Formulierung `letzter Regen gegen` bzw. das schmucklose
  Kurzform-Token `@HH:MM` an der Ende-Position — die Untergrenze darf nicht als
  bekanntes Ende missverstanden werden. Umgekehrt trägt der Normalfall
  (`event_ongoing_beyond_horizon=False`) NIE `mindestens` oder `>`.
  - Test: Unit-Test über beide Zustände, Negativ-Prüfung je Richtung —
    Wächterfall ohne `letzter Regen gegen`, Normalfall ohne `mindestens`/`>`.

- **AC-6:** Given einen Onset-Alarm mit Beginn um 23:50 Ortszeit (kein
  Tagesversatz) und einem daraus abgeleiteten Ende um 00:40 des Folgetags /
  When Beginn und Ende gerendert werden / Then trägt `onset_day_offset=0`
  während `event_end_day_offset=1` — Beginn und Ende können unterschiedliche
  Tagesversätze tragen, die Ableitung ist asymmetrisch, nicht vom Beginn
  kopiert.
  - Test: Unit-Test mit Frames, die den Übergang über Mitternacht abbilden,
    beide `day_offset`-Werte einzeln geprüft.

- **AC-7:** Given eine Frame-Zeitreihe mit nassem Block, der über das
  konfigurierte Tagesfenster der Etappe hinausreicht (z. B. Ende um 22:15 bei
  einem Tagesfenster-Ende von 20:00) / When das Ende gerendert wird / Then
  nennt der Text das ECHTE Ende (22:15), OHNE es auf das Tagesfenster zu
  kappen oder zu unterdrücken.
  - Test: Unit-Test/Renderer-Test mit einem über 20:00 Ortszeit hinaus nassen
    Block, gerenderter Text enthält die ungekappte Uhrzeit.

- **AC-8:** Given ein Onset-Alarm mit gesetztem `event_end_minutes` /
  When der E-Mail-Betreff (`_render_subject_onset`) gerendert wird / Then
  enthält der Betreff zusätzlich zur Beginn-Angabe die Ende-Angabe im Wortlaut
  `letzter Regen gegen HH:MM`.
  - Test: Unit-Test gegen `_render_subject_onset` mit konstruiertem
    `OnsetEvent`, Substring-Prüfung auf `letzter Regen gegen`.

- **AC-9:** Given denselben Aufbau wie AC-8 / When die E-Mail-Trip-Onset-Zeile
  (`_render_email_onset`) gerendert wird / Then enthält der Text
  `letzter Regen gegen HH:MM` zusätzlich zur bestehenden Beginn-Zeile.
  - Test: Unit-Test gegen `_render_email_onset`, Substring-Prüfung.

- **AC-10:** Given ein Mehr-Orte-Onset-Bündel (Ortsvergleich) mit einem
  führenden Ort, dessen `NowcastResult` ein gesetztes `event_end_minutes`
  trägt / When `to_multi_location_onset_alert_message` das Ergebnis baut und
  `_render_email_onset_multi` rendert / Then enthält der Text
  `letzter Regen gegen HH:MM` — dieselbe Angabe wie im Trip-Pfad (AC-9), nicht
  nur eine leere Beginn-Zeile.
  - Test: Unit-Test über `to_multi_location_onset_alert_message` mit zwei
    Orts-`NowcastResult`s (führender Ort mit gesetztem Ende), gerenderter
    E-Mail-Text auf die Ende-Angabe geprüft.

- **AC-11:** Given denselben Aufbau wie AC-8 / When
  `_render_telegram_onset` (rich) gerendert wird / Then enthält der
  Telegram-Text `letzter Regen gegen HH:MM` zusätzlich zur Beginn-Angabe.
  - Test: Unit-Test gegen `_render_telegram_onset`, Substring-Prüfung.

- **AC-12:** Given denselben Aufbau wie AC-8 / When `_render_sms_onset`
  (SMS, Premium-SMS und Telegram-Kurzstil) gerendert wird / Then enthält der
  Text zusätzlich zum bestehenden Mengen-Token (#2046) das Kurzform-Token
  `@HH` für das Ende, unmittelbar hinter dem Mengen-Token — alle drei Kanäle
  zeigen denselben Text, weil sie denselben gerenderten `sms_body` erhalten.
  - Test: Unit-Test gegen `_render_sms_onset` mit konstruiertem `OnsetEvent`,
    Regex-Prüfung auf zwei `@HH:MM`-artige Token in der erwarteten
    Reihenfolge; ergänzend ein Kanalvergleichstest wie #2046-AC-7.

- **AC-13:** Given ein `starkregen_nowcast`-Tupel mit gesetztem Ende und
  `event_ongoing_beyond_horizon=False` / When
  `format_starkregen_hint(...)` den Briefing-Kurzfristhinweis rendert / Then
  enthält der Text zusätzlich zur Beginn-Angabe `letzter Regen gegen HH:MM`.
  - Test: Unit-Test gegen `format_starkregen_hint` mit erweiterter
    Signatur/Datenform, Substring-Prüfung.

- **AC-14:** Given ein `NowcastResult` mit gesetztem `event_end_minutes` /
  When `format_now_text(result, ...)` als Antwort auf ein Inbound-Kommando
  gerendert wird / Then enthält der Text zusätzlich zur bestehenden
  Beginn-Zeile `letzter Regen gegen HH:MM`.
  - Test: Unit-Test gegen `format_now_text`, Substring-Prüfung.

- **AC-15:** Given denselben Onset-Alarm einmal über den Trip-Pfad
  (`trip_alert.check_radar_alerts`) und einmal über den Ortsvergleich-Pfad
  (`compare_radar_alert`) gerendert (ADR-0021, geteilter Code) / When beide
  Pfade dieselben Frames erhalten / Then trägt die Ende-Angabe in beiden
  Flächen denselben Wortlaut und denselben Wert — keine Fläche zeigt das Ende,
  ohne dass es die andere auch täte.
  - Test: Paritätstest, gespiegelt zu
    `tests/tdd/test_onset_menge_kanalparitaet.py`, prüft Trip- und
    Ortsvergleich-Ausgabe auf identische Ende-Angabe.

- **AC-16:** Given ein Onset-Alarm mit langem Ortsnamen (30 Zeichen), einer
  Extremmenge (`onset_precip_mm=99.9`) UND dem Ende-Untergrenzen-Token
  (` >@23:59`, `event_ongoing_beyond_horizon=True`) — der Extremfall aus
  kombiniertem Mengen- und Untergrenzen-Token, ein Zeichen länger als die
  Normalform und NICHT die alte Marge aus #2046-AC-9 fortgeschrieben / When
  `render_sms(msg, limit=140)` gerendert wird / Then bleibt der resultierende
  Text unter 140 GSM-7-Zeichen, ohne dass der harte Schnitt `body[:limit]` im
  Normalfall greift.
  - Test: Unit-Test mit 30-Zeichen-Ortsnamen, `onset_precip_mm=99.9` und
    gesetztem Wächter (Untergrenzen-Token), `len(sms) <= 140` geprüft — reine
    Längenprüfung, kein Goldstring-Vergleich.

- **AC-17:** Given einen beliebigen der sieben gerenderten Texte mit
  gesetztem Ende / When der Text auf Formulierungen geprüft wird, die eine
  Handlungsempfehlung oder eine Position/Uhrzeit-Rechnung über den Nutzer
  enthalten (z. B. „bei Planzeit bist du um … bei km …") / Then enthält KEINER
  der sieben Texte eine solche Formulierung — ausschließlich Wetterdaten
  (Beginn, Ende, Menge, Ort).
  - Test: Unit-Test über alle sieben Renderer-Ausgaben, Negativ-Prüfung auf
    eine Liste verbotener Muster (kein Personalpronomen der zweiten Person in
    Verbindung mit einer Zeit-/Ortsangabe).

- **AC-18:** Given der Trockenzweig von `format_now_text` (kein Regen im
  gesamten Nowcast-Fenster) / When der Text gerendert wird / Then lautet die
  Zeitangabe „In den nächsten 3 Stunden kein Regen erwartet." — konsistent mit
  `_NOWCAST_HORIZON_MIN = 180` seit #1945, nicht mehr „2 Stunden".
  - Test: Unit-Test gegen `format_now_text` mit einem durchgängig trockenen
    `NowcastResult`, Substring-Prüfung auf „3 Stunden" und Abwesenheit von
    „2 Stunden".

- **AC-19:** Given ein `NowcastResult` ohne ableitbares Ende — drei Varianten:
  (a) `onset_minutes=None` (kein Beginn erkannt), (b) `throttled=True`
  (Budget-Drosselung), (c) `data_unavailable=True` (echter Fetch-Fehler) /
  When alle sieben Textstellen wie vor dieser Spec gerendert werden / Then
  bleiben `event_end_minutes=None` und `event_ongoing_beyond_horizon=False`,
  und JEDER der sieben Texte rendert exakt wie vor dieser Änderung — additives
  Feld mit Default, kein Bruch für Alt-Aufrufer.
  - Test: Regressionslauf der Bestandstests aus dem Test-Plan ohne
    inhaltliche Anpassung an ihren Fixtures — kein Bestandstest darf allein
    wegen der neuen Felder rot werden.

## Known Limitations

- **R4 bleibt strukturell:** „Ende" bei abgeschnittener Zeitreihe ist nicht
  dasselbe wie „Ende des Ereignisses". `event_ongoing_beyond_horizon` macht
  den Unterschied zwischen „Ende" und „Ende der Beobachtung" jetzt im Text
  sichtbar — als belegte Untergrenze (`Regen mindestens bis HH:MM` /
  ` >@HH:MM`) statt als Schweigen —, löst ihn aber weiterhin nicht auf:
  jenseits von 180 Minuten bleibt das tatsächliche Ende grundsätzlich
  unbekannt (das wäre S3, „Reichweite der Quelle", explizit außerhalb dieses
  Zuschnitts).
- **Abhängigkeit vom Quellenraster.** Wie bei `onset_precip_mm` (#2046)
  bestimmt die Kadenz der jeweiligen Quelle (5-15 Min) die Präzision der
  Ende-Angabe; bei gröberem Raster kann das abgeleitete Ende um bis zu
  `_MAX_FRAME_COVERAGE` (15 Min) von der Wirklichkeit abweichen.
- **S2 (räumliche Ausdehnung), S3 (Reichweite der Quelle), S4
  (`/strecke`-Kommando)** aus Issue #2051 bleiben offen — diese Spec deckt
  ausschließlich S1 (Dauer/Ende).

## Nicht-Ziele

- **Keine Änderung an der Auslöseschwelle** (`RADAR_ONSET_THRESHOLD_MIN = 55`)
  oder an der #2020-Überholungsprüfung.
- **Keine Kappung von `_NOWCAST_HORIZON_MIN`** auf 60 (E3) — nähme #1945
  zurück.
- **Keine Kappung der Ende-Angabe am Tagesfenster** (E2).
- **Keine neue Toleranzzahl** für Datenlücken — dieselbe
  `_MAX_FRAME_COVERAGE`-Deckung wie `_accumulate_precip_mm`.
- **Keine Änderung an `_onset_time_label()` oder dem Δ-Teil von
  `_render_sms_body`** — Zusage an `fix-2020-zeitangaben-wortlaut`.
- **Kein neuer Quellenabruf** — die Ende-Bestimmung nutzt ausschließlich die
  bereits abgerufenen `frames`.
- **Keine Handlungsempfehlung im Text** — ausschließlich Wetterdaten (AC-17).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Additive Feld-Durchreichung entlang einer bestehenden
  Wirkkette (Muster bereits über `onset_precip_mm`/`onset_day_offset`/
  `segment_id` etabliert) plus eine reine Renderer-Formaterweiterung. Berührt
  keine der vier Entscheidungsflächen, die ein neues ADR verlangen würden:
  ADR-0011 (ein Backend-Renderer) bleibt gültig — alle fünf renderer-seitigen
  Textstellen liegen weiter in `render.py`; ADR-0021 (geteilter Code
  Trip/Compare) wird angewendet, nicht verändert (AC-15); ADR-0052
  (Mail-Bauform, Label-Wert-Tupel) bleibt unangetastet, die Ende-Angabe fügt
  sich in dieselbe Datenzeilen-Form ein. Kein neuer Kanal, kein neuer
  Provider, keine Persistenz-Änderung, keine Änderung an der Auslöseregel.

## Reihenfolge

`render.py` wird von drei Vorhaben gleichzeitig angefasst (#2036, #2020 S2,
diese Spec). Empfohlene Reihenfolge:

1. **Datenschicht zuerst** (`radar_service.py`, `model.py`,
   `notification_service.py`, `trip_alert.py`/`compare_radar_alert.py`,
   Vorschauweg) — keine Abhängigkeit von `render.py`, kann sofort entstehen.
2. #2036 (Phase 6) und #2020 S2 (Phase 5) mergen lassen.
3. Auf beide nachziehen, **dann** die Textstellen 1-5 in `render.py`
   schreiben.

## Test-Plan

**Bestehende Tests, die den heutigen ende-losen Text festnageln — laufen
unverändert grün oder werden am Goldstring fortgeschrieben (AC-19):**

- `tests/tdd/test_alert_sms_onset_zeitpunkt.py`
- `tests/tdd/test_alert_onset_day_rollover.py`
- `tests/tdd/test_alert_preview_nowcast_replay.py`
- `tests/tdd/test_952_onset_alert_fidelity.py`
- `tests/tdd/test_alert_sms_location_positions.py`
- `tests/tdd/test_alert_addendum_sms.py`
- `tests/tdd/test_issue_919_radar_alert_canonical.py`
- `tests/tdd/test_multi_location_onset_alert.py`
- `tests/tdd/test_onset_kurzform_menge.py` (#2046)
- `tests/tdd/test_onset_menge_kanalparitaet.py` (#2046, Muster für AC-15/AC-16)

**Neue Testdateien, benannt nach Verhalten (nicht nach Issue-Nummer):**

- `tests/tdd/test_nowcast_blockende_ableitung.py` — AC-1/AC-2 (Normalfall,
  getrennte Blöcke).
- `tests/tdd/test_nowcast_blockende_datenluecke.py` — AC-3/AC-4 (Lücke
  innerhalb/außerhalb der Deckung).
- `tests/tdd/test_nowcast_blockende_horizont_waechter.py` — AC-5
  (`event_ongoing_beyond_horizon`, alle drei geprüften Kanäle; seit v1.1 in
  umgekehrter Zusicherung: Anwesenheit der Untergrenzen-Form statt
  Abwesenheit einer Ende-Angabe).
- `tests/tdd/test_nowcast_blockende_tagesversatz.py` — AC-6 (asymmetrischer
  Mitternachtsüberlauf).
- `tests/tdd/test_nowcast_blockende_tagesfenster.py` — AC-7 (ungekapptes
  Ende).
- `tests/tdd/test_onset_ende_textstellen.py` — AC-8/AC-9/AC-10/AC-11/AC-12
  (alle sieben Textstellen, je ein Fall).
- `tests/tdd/test_onset_ende_briefing_hinweis.py` — AC-13 (Datenform-
  Erweiterung des Briefing-Tupels).
- `tests/tdd/test_onset_ende_kommando_antwort.py` — AC-14
  (`format_now_text`).
- `tests/tdd/test_onset_ende_kanalparitaet.py` — AC-15 (Trip ↔ Ortsvergleich).
- `tests/tdd/test_onset_ende_sms_budget.py` — AC-16 (kombinierter
  Zeichen-Grenzfall).
- `tests/tdd/test_onset_texte_keine_bevormundung.py` — AC-17.
- `tests/tdd/test_nowcast_horizont_drift_text.py` — AC-18 (Trockenzweig
  „3 Stunden").
- `tests/tdd/test_onset_ende_untergrenze_abgrenzung.py` — AC-20 (Abgrenzung
  Untergrenze ↔ bekanntes Ende, beide Richtungen).

## Changelog

- 2026-08-21: Initial spec created (#2051 Scheibe S1, Ereignis-Ende und
  -Dauer im Nowcast).
- 2026-08-22: v1.1 — AC-5 umgekehrt (PO-Entscheid): bei gesetztem
  Horizont-Wächter wird das Ende als belegte Untergrenze genannt
  (`Regen mindestens bis HH:MM` / ` >@HH:MM`) statt weggelassen. Neu AC-20
  (Abgrenzung Untergrenze ↔ bekanntes Ende). AC-16 auf den längeren
  Extremfall nachgezogen. Nebenbefund #2063 (Onset-Uhrzeit eine Minute zu
  früh) bewusst außerhalb dieses Zuschnitts.
