---
entity_id: feat_2261_sz8_messpunkt_position
type: feature
created: 2026-10-02
updated: 2026-10-02
status: draft
workflow: feat-2261-sz8-messpunkt-position
version: "1.0"
tags: [alarm, radar, nowcast, messpunkt, waechter, trip]
---

# Szenario 8: Der Radar-Alarm misst dort, wo der Nutzer sein wird (Issue #2261 Teil A, Herkunft #2050 B-3 / #2017)

## Approval

- [ ] Approved — Product Owner (offen; Freigabe der ACs auf Deutsch durch Henning steht aus)

## Purpose

Anforderung B-3 aus #2050 lautet: Der Radar-Alarm fragt das Wetter dort ab, wo der Nutzer zum
Ereigniszeitpunkt sein wird, nicht dort, wo er gestartet ist. #2017 hat das umgesetzt (Messpunkt =
Position zur Fenstermitte, mit Höhe), #2051 S2a hat daraus bis zu `RADAR_ZONE_MAX_POINTS = 6`
Messpunkte entlang der Reststrecke gemacht.

Bewacht ist die Zusicherung heute nur an zwei Stellen: auf Bausteinebene
(`tests/tdd/test_position_at_time.py`) und auf Auslöseebene gegen **eine feste**
Trip-Konfiguration (`tests/tdd/test_issue_822_radar_nowcast_segment.py::test_2017_ac8`). Es fehlt
der Nachweis, der B-3 wörtlich trägt: **derselbe Lauf mit verschobenem Wegpunkt muss andere
Koordinaten und eine andere Höhe an den Nowcast-Abruf liefern**, und zwar an der Stelle, an der die
Zusicherung WIRKT — den Argumenten von `get_nowcast` im echten `check_radar_alerts()`. Diese
Scheibe liefert genau diesen Wächter. Sie ist eine reine Nachweis-Scheibe: Produktivcode wird
voraussichtlich **nicht** geändert.

Zusätzlich hält sie die dokumentierte Näherung und das Restrisiko des Messpunkts in
`fix_2017_nowcast_messpunkt.md` fest (Doku-Teil, siehe AC-5).

## Source

- **File:** `tests/tdd/test_alarm_szenario_messpunkt_position.py` (neu)
- **Geprüfter Produktivcode (nur lesend):** `src/services/trip_alert.py::TripAlertService.check_radar_alerts`
  (Radar-Block `:1798-1880`: `_at = now_utc + RADAR_ONSET_THRESHOLD_MIN // 2`, `_punkte =
  points_along_remaining_route(...)`, `_pos = _punkte[0]`, `get_nowcast(lat, lon,
  elevation_m=int(round(_pos.elevation_m)))`), `src/services/trip_segments.py::position_at_time`
  (`:561`), `::points_along_remaining_route` (`:683`), `RADAR_ZONE_MAX_POINTS = 6` (`:37`),
  `RADAR_ZONE_POINT_SPACING_KM = 2.0` (`:36`).
- **Schicht:** Python-Core, nur Test + Doku. Kein Go, kein Frontend, kein neuer Endpoint.

## Estimated Scope

- **Files:** 1 neuer Test, 1 Doku-Änderung (`fix_2017_nowcast_messpunkt.md`), diese Spec; dazu die
  geteilte Hilfsfunktion (siehe Entscheidung unten): `tests/helpers/nowcast_gate_fixtures.py`
  (additiv) und eine Import-Zeile in `tests/tdd/test_issue_822_radar_nowcast_segment.py`.
- **LoC:** +120–160 Test (Doku und Spec zählen nicht), plus ca. 25 LoC Verschiebung des
  aufzeichnenden Radar-Dienstes (kein neues Verhalten).
- **Risk:** LOW — kein Produktivcode; der heiß umkämpfte Radar-Block (#2065, #2051, #2050 S4a/b)
  bleibt unangetastet.
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripAlertService.check_radar_alerts` (`src/services/trip_alert.py`) | function | Prüfling — echter Lauf, kein Nachbau der Auslöseentscheidung |
| `trip_segments.position_at_time` / `points_along_remaining_route` | function | Prüfling (indirekt); die ERWARTUNG wird NICHT daraus gerechnet |
| `RadarNowcastService.get_nowcast` | method | Wirkstelle: aufzeichnende Unterklasse liest `lat`, `lon`, `elevation_m` jedes Abrufs |
| `tests/helpers/nowcast_gate_fixtures.py` (`make_trip`, `trip_stage`, `CountingFrameSource`, `clean_uid`, `fresh_uid`, `save_trip`, `settings_email_only`, `write_user_tier`, `reset_radar_cache`) | helper | Echte Trips, gestellte Uhr, `frame_source`-Naht — Muster der Schwester-Wächter `tests/tdd/test_alarm_szenario_*.py` |
| `tests/tdd/test_issue_822_radar_nowcast_segment.py::_aufzeichnender_radar_dienst` | helper | Vorlage des aufzeichnenden Dienstes (echte Unterklasse, `super()` läuft unverändert) |
| `docs/specs/modules/fix_2017_nowcast_messpunkt.md` | spec | Doku-Ziel (AC-5); Herkunft der Näherung |
| `docs/specs/modules/alarm_pruefstrecke.md` | spec | Hinweis: die `AlarmPruefstrecke` erfasst keine `get_nowcast`-Argumente; siehe Test-Aufbau |

## Implementation Details

### Test-Aufbau (Wächter, keine Produktivänderung)

**Einstieg.** Der echte `TripAlertService.check_radar_alerts()` unter gestellter Uhr
(`freeze_time`, Reykjavik/UTC+0, mittags — Muster `_alarm_lauf_2017`), mit dem **aufzeichnenden
Nowcast-Dienst** als `radar_service=`. Begründung für diesen Einstieg statt der
`AlarmPruefstrecke(zweig="radar")`: die Prüfstrecke gibt Kanalinhalte und Auslösezähler zurück,
aber nicht die Argumente von `get_nowcast` — und genau die sind die Wirkstelle. Der Wächter
fährt dennoch denselben echten Pfad (`check_radar_alerts()`), keinen Nachbau.

**Lange Etappe.** Eine Zwei-Wegpunkt-Etappe 11:00–15:00 mit Luftlinie > 12 km (Standard-Etappe aus
`trip_stage`: +0,1° Breite und +0,1° Länge bei 64,13° N, etwa 12 km). Damit ist die Reststrecke ab
Fenstermitte (≈ 7–8 km) groß genug für mehrere Messpunkte (Abstand 2 km, rund 4 Punkte; Obergrenze 6). Der Fenstermitte-Zeitanteil
(+27 Min bei 12:00 gestellt) liegt weit weg vom Startpunkt (p ≈ 0,3625).

**Zwei Läufe, ein Unterschied.** Lauf A: Standard-Etappe. Lauf B: identischer Trip, aber der
Endwegpunkt der Etappe ist verschoben (Länge gespiegelt: `lon − 0,1` statt `lon + 0,1`; Höhe
900 m statt 600 m). Die Verschiebung geschieht am Trip-Objekt vor `save_trip`; der Prüfling liest
den Trip von der Platte (Muster `_alarm_lauf_2017`, damit Erwartung und Prüfling dieselbe Fassung
sehen). Frames: `CountingFrameSource(onset_minutes=8)`, `reset_radar_cache()` vor jedem Lauf (die
Cache-Schlüssel `lat_lon_region` würden sonst Abrufe verschlucken, TTL 300 s).

**Erwartung ist KEIN Spiegel von `position_at_time`.** Geprüft werden Ungleichheit und Richtung,
nicht ein aus dem Prüfling gerechneter Sollwert:

1. Lauf A und Lauf B unterscheiden sich in den abgefragten Koordinaten (jeder Punkt `i` von A
   gegen Punkt `i` von B, Abstand deutlich > 0,01°) und in der abgefragten Höhe.
2. Richtung: der erste Messpunkt liegt in A östlich, in B westlich des Startpunkts (Vorzeichen
   von `lon_punkt − lon_start` folgt dem Vorzeichen von `lon_end − lon_start`); die Höhe des
   ersten Punkts liegt in B über der in A und zwischen Start- und Endhöhe der jeweiligen Etappe.
3. Messpunkt ≠ Startpunkt: der erste abgefragte Punkt liegt in beiden Läufen mehr als 1 km vom
   Segment-Startpunkt entfernt (der Nutzer hat ihn zur Fenstermitte laengst verlassen).
4. Folgepunkte: es gibt mehr als einen Abruf, höchstens `RADAR_ZONE_MAX_POINTS`; jeder
   Folgepunkt wandert mit dem verschobenen Endwegpunkt (westlich in B, östlich in A), nicht nur der
   erste.

Kein Zwei-Nutzer-Test: es entsteht kein neuer und kein geänderter Endpoint, kein neuer
Datenzugriff; der Wächter liest nur die Argumente eines Abrufs für **einen** Nutzer. Die
Mandantentrennung des Radar-Alarms bewacht `tests/tdd/test_alarm_szenario_mandantentrennung.py`
(#2050) bereits.

### Entscheidung: geteilter Helfer statt Kopie

`_alarm_lauf_2017` selbst wird **nicht** geteilt: er ist an `_MITTAGS_2017`, an feste Trip-Parameter
und an die Rückgabe `(sent, mails, dienst, frames, trip, now_utc)` dieser einen Datei gebunden;
der neue Wächter braucht eine andere Trip-Bauart (verschobener Endwegpunkt). Ein Verallgemeinern
brächte Parameter, die nur ein Aufrufer nutzt.

Geteilt wird dagegen `_aufzeichnender_radar_dienst` (echte `RadarNowcastService`-Unterklasse, die
`lat`/`lon`/`elevation_m` je Abruf mitschreibt, ca. 25 LoC): er ist verhaltensneutral, wird von
zwei Dateien gebraucht und ist exakt die Art Baustein, die `tests/helpers/` für diesen Zweck führt
(Teilungsregel statt Nachbau, vgl. `trip_stage` in `nowcast_gate_fixtures.py`). Er zieht nach
`tests/helpers/nowcast_gate_fixtures.py` (additiv; Import von `RadarNowcastService` bleibt lazy
innerhalb der Funktion), die Datei `test_issue_822_radar_nowcast_segment.py` importiert ihn von
dort statt ihn lokal zu definieren. Verhalten der 822-Tests bleibt bit-identisch (belegt durch
unveränderten Lauf der Datei).

### Pflicht-Mutationsgegenproben (Adversary, Step 3b)

Alle per String-Ersetzung mit **externer Sicherungskopie** (Kopie ins Scratchpad, danach
zurückkopieren und `diff` gegen die Kopie) — nie `git checkout`/`stash`/`reset`. Zu jeder
Mutation steht der Test fest, der rot werden MUSS; wird ein anderer oder gar kein Test rot, ist
das ein Finding.

| # | Datei / Ersetzung | Muss rot werden |
|---|---|---|
| M1 | `src/services/trip_alert.py:1845` `_pos = _punkte[0]` → `_pos = active.start_point` (Messpunkt auf den Segmentstart zurückgedreht) | `test_sz8_messpunkt_ist_nicht_der_startpunkt` |
| M2 | `src/services/trip_segments.py:542` in `_interpolate_point` (von `position_at_time` genutzt) `a, b = seg.start_point, seg.end_point` → `a, b = seg.start_point, seg.start_point` (Wegpunkt-Verschiebung wird ignoriert: Interpolation kennt den Endwegpunkt nicht) | `test_sz8_messpunkt_wandert_mit_dem_wegpunkt` |
| M3 | `src/services/trip_segments.py:711` in `points_along_remaining_route` `start, active.end_point,` → `start, active.start_point,` (Folgepunkte folgen dem Endwegpunkt nicht; Zeile 739 in `points_from_km` ist NICHT der Radar-Pfad) | `test_sz8_folgepunkte_wandern_mit_dem_wegpunkt` |
| M4 | `src/services/trip_alert.py:1867` `int(round(_pos.elevation_m))` → `int(round(active.start_point.elevation_m))` (Höhe wandert nicht mit) | `test_sz8_hoehe_wandert_mit_dem_messpunkt` |
| M5 | `src/services/trip_segments.py:37` `RADAR_ZONE_MAX_POINTS = 6` → `= 60` (Obergrenze wirkungslos) | `test_sz8_obergrenze_der_messpunkte` (Etappe ~45 km, genau `RADAR_ZONE_MAX_POINTS` Abrufe) |

Hinweis: Zeilennummern per `grep` verifizieren; bei M2/M3 werden zusätzlich weitere Wächter-Tests rot (Adversary-Beleg), der benannte Test MUSS dabei sein.

Leitfrage (CLAUDE.md): Ist die Zusicherung an der Stelle geprüft, an der sie WIRKT? Hier: an den
Argumenten von `get_nowcast` im echten `check_radar_alerts()`, nicht in `position_at_time` selbst.
Wird M2 (bzw. M3) nur von `test_position_at_time.py` gefangen, aber von keinem Test dieser Datei, ist der
Wächter wertlos.

### Eventualfall: Wächter wird gegen den Ist-Stand ROT

Erwartet wird, dass der Wächter gegen `origin/main` grün ist (Nachweis-Scheibe). Wird er rot, ohne
dass ein Testfehler vorliegt (Vorbedingungen der Etappe stimmen, Lauf A rot nach Ungleichheits- oder
Richtungsprüfung), ist das eine echte Abweichung von B-3. Dann gilt: Produktivfix ausschließlich
**additiv** im Radar-Block von `src/services/trip_alert.py` (nur Messpunkt-Bestimmung, kein Umbau
der Auslöse-, Sperrzeit- oder Entdopplungslogik), im selben Workflow; die Spec wird vor dem Fix um
den Befund (Code-Referenz `file:line`) ergänzt und ihr LoC-Limit gegebenenfalls über
`loc_limit_override` angehoben. Rot wegen eines Testfehlers (z. B. Etappe zu kurz für 6 Punkte) ist
kein Eventualfall, sondern wird im Test behoben.

## Expected Behavior

- **Input:** Zwei Trips, identisch bis auf den Endwegpunkt der aktiven Etappe (Lage und Höhe),
  gestellte Uhr mitten in der Etappe, ein auslösender Frame-Satz.
- **Output:** Die Abrufliste des aufzeichnenden Nowcast-Dienstes (je Abruf `lat`, `lon`,
  `elevation_m`) unterscheidet sich zwischen Lauf A und Lauf B in jedem Punkt, in Richtung des
  jeweiligen Endwegpunkts, und der erste Punkt liegt in beiden Läufen weit vom Segmentstart.
- **Side effects:** keine. Kein Produktivcode, keine Persistenzänderung, kein neues Feld; der
  Wächter arbeitet auf der pytest-isolierten Datenwurzel.

## Acceptance Criteria

- **AC-1:** Given eine lange Etappe (Luftlinie über 12 km) mit gestellter Uhr mitten im Segment,
  When `check_radar_alerts()` einmal mit der Standard-Etappe (Lauf A) und einmal mit einem
  verschobenen Endwegpunkt (Lauf B, Länge gespiegelt) läuft, Then unterscheiden sich die an
  `get_nowcast` übergebenen Koordinaten zwischen A und B (jeder Punkt, nicht nur der erste),
  und die Koordinate wandert in Richtung des verschobenen Wegpunkts: der erste Messpunkt liegt in
  A östlich und in B westlich des Segmentstarts.
  - Test: `test_sz8_messpunkt_wandert_mit_dem_wegpunkt`; Zusicherung an den aufgezeichneten
    Argumenten des aufzeichnenden Nowcast-Dienstes (Ungleichheit + Vorzeichen), nicht als Spiegel
    von `position_at_time`.

- **AC-2:** Given dieselbe lange Etappe und dieselbe gestellte Uhr, When `check_radar_alerts()`
  den Nowcast abfragt, Then liegt der erste Messpunkt in beiden Läufen mehr als 1 km vom
  Segment-Startpunkt entfernt, nicht auf dem Startpunkt (Messpunkt = Position zum
  Ereigniszeitpunkt, nicht Segmentstart; Herkunft #2017).
  - Test: `test_sz8_messpunkt_ist_nicht_der_startpunkt`; Abstand des ersten aufgezeichneten
    Abrufs zum Segment-Startpunkt in Lauf A und Lauf B.

- **AC-3:** Given die lange Etappe mit Reststrecke ab Fenstermitte von mehreren Kilometern (mindestens 4 km), When
  `check_radar_alerts()` die Messpunkte entlang der Reststrecke abfragt, Then erfolgen mehr als
  ein und höchstens `RADAR_ZONE_MAX_POINTS` Abrufe, und jeder Folgepunkt wandert mit dem
  verschobenen Endwegpunkt (in A östlich, in B westlich des ersten Punkts), nicht nur der erste.
  - Test: `test_sz8_folgepunkte_wandern_mit_dem_wegpunkt`; alle aufgezeichneten Punkte beider
    Läufe, Anzahl gegen die Obergrenze, Richtungsvorzeichen je Folgepunkt. Die Obergrenze selbst
    bewacht `test_sz8_obergrenze_der_messpunkte` (Etappe ~45 km, genau `RADAR_ZONE_MAX_POINTS`
    Abrufe — die ~12-km-Etappe erreicht die Obergrenze nicht).

- **AC-4:** Given Endwegpunkte unterschiedlicher Höhe in Lauf A (600 m) und Lauf B (900 m), When
  `check_radar_alerts()` den Nowcast abfragt, Then wandert die an `get_nowcast` übergebene Höhe
  mit: sie liegt in beiden Läufen zwischen Start- und Endhöhe der jeweiligen Etappe, ist in B
  größer als in A und ist nicht die Höhe des Startpunkts (ganze Meter, wie an der Aufrufstelle
  gerundet).
  - Test: `test_sz8_hoehe_wandert_mit_dem_messpunkt`; `elevation_m` des ersten Abrufs je Lauf.

- **AC-5:** Given die #2017-Spec `docs/specs/modules/fix_2017_nowcast_messpunkt.md`, When diese
  Scheibe geliefert ist, Then enthält sie additiv (a) die Näherung „Position zur Fenstermitte
  statt zum Onset" mit Begründung (Onset entsteht erst aus dem Abruf; die Folgepunkte der
  #2051-S2a-Mehrpunktabfrage decken die Strecke bis zum spätesten Onset ab) und (b) das Restrisiko
  „Auslöseregel nur am ersten Punkt, Folgepunkte liefern nur Zonen — bewusste #2051-S2a-
  Entscheidung", und das Restrisiko ist als eigenes Issue #2480 geführt (nutzersichtbare Alarm-Lücke, Triage-Fall (a);
  kein befristeter Sammel-Eintrag in #1199).
  - Test: Doku-Abnahme (`# doc-compliance-test`-Ausnahme: kein Verhaltenstest); der Adversary
    liest den Abschnitt „Known Limitations" der #2017-Spec und prüft per `gh issue view <N> --json number,title,state`, dass das
    Restrisiko-Issue existiert und in der #2017-Spec verlinkt ist.
  > **Erledigt durch #2480 (2026-10-02):** das Restrisiko „Auslöseregel nur am ersten Punkt“ ist behoben; der AC bleibt als Doku-Nachweis bestehen.

- **AC-6:** Given der neue Wächter ist grün gegen den Ist-Stand, When die Mutationen M1 bis M5
  (Messpunkt auf Startpunkt zurückdrehen, Wegpunkt-Verschiebung ignorieren in der Interpolation
  und in den Folgepunkten, Höhe vom Startpunkt nehmen, Obergrenze der Messpunkte anheben) einzeln per String-Ersetzung mit externer
  Sicherungskopie eingespielt werden, Then wird bei jeder Mutation der in der Tabelle benannte
  Test rot, und nach dem Zurückspielen der Sicherungskopie ist der Wächter wieder grün
  (`diff` gegen die Kopie leer).
  - Test: Adversary-Durchlauf Step 3b; je Mutation das Rot-Muster des benannten Tests belegen
    (nicht „irgendein Test rot").

## Known Limitations

- **Mehr-Etappen-Fenster nicht Teil des Wächters.** Er prüft die Verschiebung innerhalb einer
  Etappe. Segment- und Tagesgrenzen der Positionsberechnung bewacht `test_position_at_time.py`
  (AC-5/AC-6 der #2017-Spec); sie auf Auslöseebene zu wiederholen wäre Dopplung.
- **Planposition, nicht Ist-Position:** unverändert Known Limitation 1 der #2017-Spec (PO-Entscheid).
- **Restrisiko Auslöseregel nur am ersten Punkt** wird dokumentiert (AC-5), nicht gebaut.
  Begründung: bewusste Entscheidung aus #2051 S2a; das Restrisiko wird als eigenes Issue #2480 geführt (PO-Regel: bekannte Abweichung nie befristet ablegen).

## Nicht Ziel

- Kein Umbau der Messpunktwahl, keine Position „zum echten Onset" (Zirkelschluss, siehe #2017).
- Keine Auslöseregel über Folgepunkte (bewusste #2051-S2a-Entscheidung).
- Keine Änderung am Starkregen-Hinweis-Pfad (`trip_report_scheduler.py`) und am `/jetzt`-Pfad.
- Keine neue Mutations- oder Gate-Infrastruktur; keine neue Pflichtregel, kein neues Gate (damit
  kein Prüfdatum nach dem Regel-Budget nötig).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Nachweis-Scheibe mit Test und Doku. Keine Entscheidungsfläche im Sinne von
  `docs/adr/README.md` berührt; die bewusste Mehrpunkt-/Auslöseentscheidung (#2051 S2a) wird
  festgehalten, nicht verändert.

## Changelog

- 2026-10-02: Adversary-Befund F001/F002 behoben: Mutationstabelle M2/M3 auf die tatsächlichen
  Fundstellen (`_interpolate_point:542`, `points_along_remaining_route:711`) korrigiert, M5
  (Obergrenze) und `test_sz8_obergrenze_der_messpunkte` ergänzt. Keine Änderung an Zusicherungen.

- 2026-10-02: Initial spec created (Issue #2261 Teil A Szenario 8, verdichtet aus
  `docs/context/feat-2261-sz8-messpunkt-position.md`).
