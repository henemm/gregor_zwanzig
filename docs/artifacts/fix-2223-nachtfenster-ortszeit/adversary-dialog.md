# Adversary Dialog — fix-2223-nachtfenster-ortszeit
Spec: docs/specs/bugfix/fix_2223_nachtfenster_ortszeit.md
Datum: 2026-11-06 19:54

## Checkliste
- [x] **Input:** letztes Segment mit Ziel-Koordinaten und Ankunftszeit (UTC)
- [x] **Output:** Zeitreihe von Ankunft bis 06:00 Ortszeit des Folgetags am Ortsdatum
- [x] **Side effects:** weniger angefragte Provider-Stunden bei Ankunft nach UTC-Mitternacht
- [x] **AC-1:** Given ein Trip-Ziel in UTC−5 und eine Ankunft um 20:00 Ortszeit (01:00 UTC des Folgetags) / When das Nachtwetter geholt wird / Then endet das Fenster um 06:00 Ortszeit des Folgetags (ca. 10 Stunden), nicht erst am übernächsten Tag (ca. 29 Stunden).
- [x] **AC-2:** Given ein Ziel auf Mallorca oder Korsika (Sommer UTC+2, Winter UTC+1) / When das Nachtwetter geholt wird / Then endet das Fenster um 06:00 Ortszeit (04:00 bzw. 05:00 UTC), nicht um 06:00 UTC.
- [x] **AC-3:** Given eine Ankunft in der Nacht der Sommerzeit-Umstellung / When das Nachtwetter geholt wird / Then endet das Fenster trotzdem exakt um 06:00 Ortszeit des Folgetags.
- [x] **AC-4:** Given ein Ziel, dessen Zeitzone nicht aufgelöst werden kann / When das Nachtwetter geholt wird / Then gilt der bisherige UTC-Rückfall (06:00 UTC am UTC-Datum+1) und es entsteht kein Fehler.
- [x] **AC-5:** Given Versand und Vorschau / When beide das Nachtwetter holen / Then nutzen beide dieselbe Funktion und erhalten dasselbe Fenster für dieselbe Ankunft.

## Dialog

### Runde 1
**Adversary:** Tests: tests/tdd/test_night_window_ortszeit.py 8 passed (selbst gelaufen); Nachbarn 146 passed (Artefakt). Code reference: src/services/segment_weather.py:616 (tz = location_tz(seg.end_point)), :617 local_dt, :618-622 combine(... time(6,0), tzinfo=tz).astimezone(utc).
Mutationen (String-Ersetzung, Sicherung im Scratchpad, danach identisch): tz=UTC, +1 Tag weg, +2 Tage, hour 7, hour 5, astimezone(utc) weg, local_dt weg (UTC-Datum), tzinfo=UTC, Fensterende +1h -> alle ROT. Mutation start_time=arrival-1h -> GRUEN (Fensterstart nur indirekt bewacht; AC-1 laesst 9-11 h zu; ausserhalb des Diffs, LOW).
Fund: AC-4 Test nutzt (0,0); das loest zu Etc/GMT auf (resolve_location_tz != None), ist NICHT "nicht aufloesbar". Mutation: Rueckfall durch `resolve_location_tz(...) or UTC+3` ersetzt -> alle 8 Tests GRUEN. Rueckfallzweig ungeprueft.
**Implementierer:** (offen)

### Runde 2
**Adversary:** Randfaelle per Code-Lektuere und Live-Probe: Ankunft vor 06:00 Ortszeit -> Ortsdatum+1 06:00 (~30h), wie Spec Known Limitations (bewusst). DST: ZoneInfo wirkt auf Wandzeit, 06:00 nie in Luecke/Falte; AC-3 gruen. Zone None: location_tz liefert UTC (live bestaetigt) -> altes Verhalten, kein Fehler. Versand=Vorschau: AC-5 ruft beide Wege, alle Mutationen schlagen dort durch. Keine Regression in Nachbartests.
**Implementierer:** (offen)

### Runde 3 (nach CI-Fund Zeitzonen-Wächter #1402)
**Adversary:** Änderung: rohes `.astimezone(timezone.utc)` in fetch_night_weather durch `to_utc(...)` ersetzt. Tests: test_night_window_ortszeit.py + test_output_timezone_guard.py 26 passed. Mutationen (String-Ersetzung, Sicherung im Scratchpad, danach byte-identisch zurück per cmp): to_utc entfernt -> AC-2/3/4/5 ROT; time(7,0) -> AC-2/3/4/5 ROT; tzinfo=UTC -> AC-2/3/5 ROT. Live-Probe: to_utc(x) == x.astimezone(utc) für aware Zeiten, Bogota und Madrid, 4 Daten (acht Fälle, alle True). Keine Findings. Code reference: src/services/segment_weather.py:616
**Implementierer:** (offen)

## Herkunft der Vorbedingungen

- Test-Fixtures (Koordinaten, Ankunftszeiten, _RecordingProvider): Testcode selbst gelesen in tests/tdd/test_night_window_ortszeit.py.
- Zonen-Aufloesung: selbst ausgefuehrt (resolve_location_tz fuer (0,0) und None).
- Testergebnis 8 passed: selbst gelaufen; Nachbar-Output (146 passed) aus Artefakt uebernommen, nicht neu gelaufen.
- Mutationsergebnisse: selbst ausgefuehrt.

## Verdict
Code reference: src/services/segment_weather.py:616

VERDICT: VERIFIED (mit 1 MEDIUM- und 1 LOW-Befund, kein Blocker)

F001 MEDIUM edge_case, src/services/segment_weather.py:616: AC-4-Testdaten (0,0) loesen zu Etc/GMT auf, UTC-Rueckfallzweig ungetestet; Mutation des Rueckfalls bleibt gruen. Abhilfe: Test mit Ziel ohne Koordinaten/Zone (lat=None).
F002 LOW: Fensterstart-Mutation (arrival-1h) unbemerkt; AC-1-Toleranz 9-11 h.

F001 BEHOBEN (Nachtrag): AC-4-Test nutzt jetzt einen TimezoneFinder ohne Treffer (resolve_location_tz -> None, Vorbedingung im Test geprueft). Mutation des Rueckfalls (UTC+3) ist ROT (assert 03:00 UTC == 06:00 UTC), unveraenderte Implementierung 8 passed. Code reference: src/services/segment_weather.py:616

## Geprüfte Dateien

- sha256:3b432d6601383977b22b2c5a9279b6bd1e3ac7b9dffdb5a47ba7c55e73df1b1e  src/services/segment_weather.py

## Prüfbasis

- base: 63e7519b514576ba5ec79f1ffc909b4c32fcad43
- blob:308a328d8534b625046d8a1b4d8cc5d4e993e523  src/services/segment_weather.py

## Herkunft der Vorbedingungen

kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)

## Geprüfte Dateien

- sha256:3b432d6601383977b22b2c5a9279b6bd1e3ac7b9dffdb5a47ba7c55e73df1b1e  src/services/segment_weather.py

## Prüfbasis

- base: 63e7519b514576ba5ec79f1ffc909b4c32fcad43
- blob:308a328d8534b625046d8a1b4d8cc5d4e993e523  src/services/segment_weather.py

## Geprüfte Dateien

- sha256:5709ac2c5d636ab5a0f1fe54408c24d28550fe33020a9adba0c84110e37c3ead  src/services/segment_weather.py

## Prüfbasis

- base: 63e7519b514576ba5ec79f1ffc909b4c32fcad43
- blob:d1ff5ed4739cd71b0cdaf0383e15fedb24865fbb  src/services/segment_weather.py
