# Context: fix-3217-flaky-thunder-ac3

## Request Summary
Kern-Test `test_ac3_haengender_download_kostet_hoechstens_den_timeout_und_wird_nicht_wiederholt`
(`tests/tdd/test_dwd_thunder_parallel_fetch.py:329`) fällt auf ausgelasteten CI-Runnern gelegentlich
mit `AssertionError: Zelle grau_gsp+5 leer` aus (PR #3213, Lauf 44764472923). Ziel: deterministisch machen,
ohne die Zusicherung (Hänger kostet höchstens den Timeout, kein Retry, Zelle None, alle anderen Zellen gefüllt)
abzuschwächen.

## Ursache (nachgestellt)
- Der Test setzt `dwd.THUNDER_REQUEST_TIMEOUT = 0.5` per monkeypatch. Die Konstante gilt für **jeden**
  Gewitter-Einzelabruf (`DwdDirectProvider._thunder_request`, `src/providers/dwd.py:629`), nicht nur für den Hänger.
- Der lokale Testserver erzeugt pro Anfrage ein frisches GeoTIFF + bz2 (`_raster`, Test Z. 91ff.; jeder
  (param, lauf, ttt) hat einen eigenen Wert, der Cache greift also nie), der Client entpackt und dekodiert es.
  Auf einem ausgelasteten Runner (GIL, 5 parallele Downloads, CPU-Konkurrenz) kann eine **normale** Antwort
  länger als 0,5 s brauchen → `httpx.ReadTimeout` → kein Retry (#2554, gewollt) → Zelle `None`
  (`_thunder_point`, `src/providers/dwd.py:719ff.`) → Assertion „Zelle … leer“.
- Nachgestellt (Wegwerf-Kopie des Tests): wird nur die Datei `grau_gsp`+5 serverseitig um 0,6 s verzögert,
  scheitert der Test exakt mit `AssertionError: Zelle grau_gsp+5 leer` — identisch zur CI-Meldung.
  CPU-Last auf dem Server zu erzeugen wurde bewusst unterlassen (Produktionshost).
- Der erste Ausfall (PR #3211, „Abbruch ohne roten Test“) ist nicht derselbe Mechanismus und hier nicht belegt.

## Related Files
| File | Relevance |
|------|-----------|
| `tests/tdd/test_dwd_thunder_parallel_fetch.py` | betroffener Test (Z. 329–364), Server-Helfer `_raster`, `_Handler`, `_dwd_server` |
| `src/providers/dwd.py` | `THUNDER_REQUEST_TIMEOUT` (Z. 162), `_einzelflug` (Z. 534, Wartezeit = derselbe Timeout), `_thunder_request`, `_thunder_point` |
| `docs/specs/modules/fix_2554_dwd_gewitterabruf_budget.md` | Spec AC-3 des Originals |
| `tests/test_befehl_antwortzeit.py` | patcht `THUNDER_REQUEST_TIMEOUT` ebenfalls (nicht im Scope, nur Hinweis) |

## Existing Patterns
- Schwester-Test `test_ac3_haenger_mit_unveraendertem_default_timeout_endet_nach_etwa_10s` (Z. 585) nutzt den
  echten 10-s-Timeout mit 15-s-Hänger — dort ist der Abstand zu normaler Antwortzeit groß, daher stabil.
- Server-Regeln (`regel`) steuern Hänger/Status je (param, lauf, ttt); `verzoegerung_s` gilt global.

## Lösungsrichtung (Analyse, Summe 1 → in einem Durchgang)
1. **Abstand Timeout ↔ normale Antwortzeit vergrößern:** Timeout auf z. B. 2,0 s, Hänger auf 8 s; Dauer-Grenze
   `<= Timeout + Rand` bleibt deutlich unter der Hängerdauer, fängt also weiterhin „Timeout nicht angewandt“
   (8 s) und „Retry“ (Zählung == 1 plus 2× Timeout). 
2. **Serverseitige Rechenarbeit vor dem Abruf erledigen:** alle Raster der im Test angefragten Werte vorab
   erzeugen (Cache `_RASTER_CACHE_BYTES` füllen), damit eine normale Antwort keine CPU-Arbeit im Server mehr kostet.
3. Beide Maßnahmen zusammen; keine Abschwächung der Zusicherungen. Eine injizierbare Uhr ist für einen echten
   Socket-Timeout von httpx nicht anwendbar (Timeout wirkt im Socket, nicht über `time.monotonic`).

## Dependencies
- Upstream: httpx-Timeout, ThreadPool-Fan-out (`dwd.py:841`), tenacity-Retry.
- Downstream: nur dieser Test; kein Produktivcode betroffen.

## Risks & Considerations
- Laufzeit des Tests steigt um wenige Sekunden (Timeout 2 s statt 0,5 s).
- Mutationen müssen weiter rot werden: Retry bei ReadTimeout zulassen; Timeout auf 30 s zurücksetzen;
  Zelle 0 statt None.
- Hänger-Freigabe beim Abbau (`freigabe.set()`) bleibt nötig, sonst hängt der Teardown 8 s.

## Analysis

### Type
Bug (flaky Kern-Test, Testinfrastruktur; kein Produktivcode-Fehler)

### Ursache (bestätigt)
Der monkeypatchte `THUNDER_REQUEST_TIMEOUT = 0.5` gilt für jeden Einzelabruf. Der httpx-ReadTimeout läuft,
bis der Server Kopfzeilen und Bytes schickt — die Raster-Erzeugung im Test-Server (`_raster`: GeoTIFF + bz2,
Cache greift nie, da jeder (param, lauf, ttt) einen eigenen Wert hat) liegt also INNERHALB des Timeouts.
Auf einem ausgelasteten CI-Runner (GIL, 5 parallele Downloads, Client-Dekodierung in Nachbar-Threads)
überschreitet eine normale Antwort 0,5 s → ReadTimeout → kein Retry (gewollt, #2554) → Zelle None →
`AssertionError: Zelle grau_gsp+5 leer`. Nachgestellt durch Verzögerung genau dieser einen Datei um 0,6 s
(identische Meldung). Die Client-Dekodierung NACH dem Lesen zählt nicht zum Socket-Timeout.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `tests/tdd/test_dwd_thunder_parallel_fetch.py` | MODIFY | AC-3-Test: Timeout 0,5 → 2,0 s, Hänger 4 → 8 s, Dauer-Grenze `<= Timeout + Rand` (Rand bleibt < Hängerdauer − Timeout); Raster aller angefragten (param, lauf, ttt) VOR dem Abruf erzeugen (neuer Helfer, z. B. `_raster_vorwaermen(zeit)` über `zeit.laeufe` × `THUNDER_PARAMS` × benötigte ttt) |
| `docs/specs/modules/fix_3217_flaky_thunder_ac3.md` | CREATE | Bugfix-Spec mit ACs |

### Scope Assessment
- Files: 1 Test-Datei + 1 Spec
- Estimated LoC: +25/−8
- Risk Level: LOW (nur Testcode; Produktivcode und Zusicherungen unverändert)

### Technical Approach
1. Abstand vergrößern: Timeout 2,0 s, Hänger 8,0 s; `assert dauer <= 2.0 + 3.0` (5 s < 8 s → fängt
   „Timeout nicht angewandt“ und „Retry“ (2× Timeout + Overhead > Grenze bzw. Zählung == 1)).
   `@pytest.mark.timeout(30)` reicht weiterhin.
2. Server-CPU-Arbeit vorziehen: vor `_abruf` alle Raster-Bytes in `_RASTER_CACHE_BYTES` erzeugen, damit eine
   normale Antwort nur noch Bytes schreibt.
3. Zusicherungen unverändert: genau 1 Anfrage der Hänger-URL, Zelle None (nie 0), alle anderen Zellen gefüllt,
   keine Pool-Threads danach.
Eine injizierbare Uhr ist nicht anwendbar: der Timeout wirkt im Socket (httpx), nicht über `time.monotonic`.

### Mutations-Gegenprobe (muss rot werden)
- ReadTimeout wird wiederholt (Retry zulassen) → Zählung 2 / Dauer > Grenze
- Gewitterweg nutzt Grund-Timeout 30 s statt `THUNDER_REQUEST_TIMEOUT` → Dauer ≈ 8 s > 5 s
- Zelle 0 statt None bei Timeout → Zellen-Assertion

### Dependencies
Nur dieser Test; `_einzelflug` nutzt denselben Timeout als Wartezeit (unkritisch, kein Doppel-Abruf im Test).
`tests/test_befehl_antwortzeit.py` patcht den Timeout ebenfalls — außerhalb des Scopes.

### Abgrenzung
Der Ausfall bei PR #3211 („Abbruch ohne roten Test“) ist ein anderer Mechanismus und nicht Teil dieses Fixes;
taucht er wieder auf, eigenes Issue.

### Open Questions
- keine (rein technisch, keine Produktentscheidung)
