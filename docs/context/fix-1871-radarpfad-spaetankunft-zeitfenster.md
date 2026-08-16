# Kontext: #1871 — test_radarpfad_spaetankunft reproduzierbar rot 01:03–04:03 UTC

## Analysis

### Type
Bug (Test-Fixture, kein Produktivcode)

### Korrektur zum Ticket
Das Issue nennt als Rot-Zone "04:00–06:00 UTC" und zitiert einen CI-Rot-Lauf um 05:29 UTC
als Bestätigung. Beides ist widerlegt:
- Nachgemessen (frischer Prozess je Datenpunkt, `freezegun`) ist die reale Rot-Zone
  **01:03–04:03 UTC**.
- Der zitierte CI-Rot-Lauf 05:29 UTC gehört laut `docs/specs/modules/fix_1851_alarm_tests_vorlaufsperre.md`
  zum #1851-Vorlaufsperre-Mechanismus (`test_ac1_…`/`test_ac2a_…`/`test_ac3_…`), nicht zu
  `test_radarpfad_spaetankunft_faellt_nicht_in_alle_segmente_vorbei`.

### Root Cause (verifiziert, nicht spekuliert)

`tests/unit/test_alarm_zeitfenster_ziel.py:398` in `_radar_mails_fuer_spaetankunft()`:

```
start_local = (arrival - timedelta(hours=4)).astimezone(dest_tz)
```

`_island_taugt()` (Zeile 323) erzwingt Ortsstunde `>= 1` für Reykjavik-Wahl, aber keine
Obergrenze. Für Ankunft-Ortsstunden 1–3 (Reykjavik = UTC+0, keine DST) fällt
`start_local = arrival - 4h` lokal auf den VORTAG zurück (z.B. Ankunft 02:27 → Start 22:27
des Vortags). Beide Wegpunkte (W1 = `start_local`, W2 = `arrival_local`) werden als reine
`HH:MM`-Strings (`arrival_calculated`, Zeilen 407/410) ohne Datumskontext auf denselben
`date.today()`-Stage-Tag gelegt.

Der Rollover-Mechanismus in `src/services/trip_segments.py:154-157` vergleicht diese reinen
Uhrzeiten (`t < prev` = "strikt fallend = Tagesgrenze") und erhöht `day`, weil W1="22:27" >
W2="02:27". Für ECHTE mehrtägige Treks ist das korrekt (#1091/#1098) — hier ist es ein
Artefakt der Fixture-Konstruktion. Das Zielsegment landet auf dem Folgetag, „jetzt" liegt
davor, kein Segment gilt aktiv, der Radar-Pfad nimmt den „alle Segmente vorbei"-Zweig — keine
Mail, Test rot.

**Kein Produktivcode-Bug** — `trip_segments.py:154-157` arbeitet wie spezifiziert.

### Bestehender Wächter ist blind für genau diesen Fall (verifiziert)

`test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster`
(`tests/unit/test_alarm_zeitfenster_ziel.py:551`) iteriert 1440+3 Minuten und prüft
ausschließlich drei Invarianten von `radar_fixture_window()`/`radar_fixture_tz()`/
`radar_fixture_ort()`: `start_hour < end_hour`, `end_hour == Ortsstunde`, `Ortsdatum ==
Etappendatum`. Er ruft `start_local` (Zeile 398) nie auf und prüft die W1-vs-W2-Wegpunktfolge
nicht — eine andere Eigenschaft als die, an der der Fachtest hängt.

**Zusätzlicher Fund:** Der KNOWN_VIOLATIONS-Kommentar in
`tests/tdd/test_fixture_wallclock_ratchet.py:180-185` behauptet für genau diese Fixture, der
1440-Minuten-Wächter sei „NICHT schwächer als die Ratsche, sondern stärker" und decke den
Schutz vollständig ab. Das ist widerlegt — der Wächter deckt die Fensterwahl ab, nicht die
W1-vs-W2-Sequenz. Der Kommentar sollte im Zuge dieses Fixes korrigiert werden, sonst bleibt
eine falsche Sicherheitszusicherung im Code stehen.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/unit/test_alarm_zeitfenster_ziel.py` | MODIFY | `start_local`-Berechnung auf lokalen Tagesbeginn klemmen statt naiv `arrival - 4h`; neue reine Funktion `radar_fixture_start_local()` (Pendant zu `radar_fixture_window/_tz/_ort`); Wächter `test_radar_fixture_ist_zu_jeder_tageszeit_kein_mitternachtsfenster` um die Invariante `start_hour_str <= arrival_hour_str` in derselben 1440er-Schleife erweitern |
| `tests/tdd/test_fixture_wallclock_ratchet.py` | MODIFY | KNOWN_VIOLATIONS-Kommentar (Zeilen ~180-185) korrigieren: falsche „stärker als die Ratsche"-Behauptung entfernen/richtigstellen |

### Scope Assessment
- Files: 2
- Estimated LoC: +30/-5 (überwiegend Kommentar-Korrektur + Klemm-Logik + Assertion-Erweiterung)
- Risk Level: LOW — `_radar_mails_fuer_spaetankunft()` hat genau einen Aufrufer (Zeile 637, verifiziert per grep), keine Kollateralwirkung auf andere Testfälle

### Technical Approach
Klemmen statt Ausweichen: Wenn `arrival_local.hour < 4`, `start_local` auf lokalen
Tagesbeginn (`00:00`) setzen statt `arrival - 4h` zu rechnen — analog zum Docstring-Titel von
`test_fixture_wallclock_ratchet.py` ("…ohne sie auf einen Tagesbereich zu klemmen"), NICHT
analog zum Auckland-Ausweichmuster (das löst eine andere Invariante: Fensterende vs.
Ankunftsstunde). Da `_island_taugt()` `hour >= 1` erzwingt, ist `arrival_local.hour` im
Bugfenster immer 1–3, `00:00 <= arrival_local` gilt garantiert, keine Grenzfälle bei Minute 0.

Reihenfolge: (a) Klemm-Fix in der Fixture → Fachtest wird grün, (b) Wächter erweitern und per
Mutations-Gegenprobe zeigen, dass ein Revert der Klemmung die erweiterte Assertion rot macht
(Projekt-Pflicht Mutations-Gegenprobe).

### Dependencies
Keine Produktivcode-Abhängigkeiten. `radar_fixture_window/_tz/_ort` bleiben unverändert
(andere Invariante, nicht wiederverwendbar für die W1-Klemmung).

### Open Questions
- [ ] Soll die Korrektur des KNOWN_VIOLATIONS-Kommentars in derselben Scheibe erfolgen oder
      als eigener kleiner Nebenbefund? Empfehlung: gleiche Scheibe, da sonst eine widerlegte
      Sicherheitszusicherung im Code stehen bleibt.
