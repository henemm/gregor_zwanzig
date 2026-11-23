# Context: rework-3265-fallback-dubletten

## Request Summary
Issue #3265 (Teil von #1196, abgespalten aus #3208, Gruppe G6 Provider-Fallback): die Testdateien
`test_issue_1115_model_fallback.py`, `test_issue_1141_cross_provider_fallback.py`,
`test_issue_1142_geosphere_direct_fallback.py`, `test_issue_1155_retry_tuning.py` (alle `tests/tdd/`)
auf doppelte Zusicherungen prüfen und Dopplungen entfernen. Kriterium wie #3208/#3264: entfernt wird nur,
was identisch ist (Funktion + Eingabe + Erwartung) oder echte Teilmenge einer bleibenden Zusicherung;
„ähnlich" (andere Ebene, andere Werte, anderer Eingangsweg) bleibt. Je Gruppe Mutationsnachweis
vorher/nachher, Kern-Schicht 100 % grün.

## Related Files
| File | Relevance |
|------|-----------|
| tests/tdd/test_issue_1115_model_fallback.py (364) | Intra-Open-Meteo-Modellfallback: ac1 (5xx→Ersatz, Berlin), ac2 (400→kein Ausweichen, Berlin), ac3 (fallback_model gesetzt/None, Berlin), ac5 (Kette nach Auflösung, Südbaden). `_provider_seam` mit `stop_after_attempt(1)` |
| tests/tdd/test_issue_1155_retry_tuning.py (420) | Retry je Kandidat (Lappland, echter Retry-Zähler): ac1 Totalausfall, ac2 Primär 503,503,200, ac3 404, ac4 fallback_reason/-model, ac7 Laufzeit; **lädt `_provider_seam` und `_BERLIN` aus 1115 per importlib** |
| tests/tdd/test_issue_1141_cross_provider_fallback.py (570) | Regions-Direktprovider nach OM-Totalausfall: ac1 (live), ac2 Lappland ohne Region, ac3 fallback_meta, ac4 Mail-Footer, ac5/ac6 de_direct 503 (Fehler-Durchreiche / Log) |
| tests/tdd/test_issue_1142_geosphere_direct_fallback.py (500) | at_direct (GeoSphere): ac1/ac2 live, ac3 GeoSphere-503 → OM-Fehler + Retry 5, ac4 Seam fängt (a) ProviderRequestError, (b) ProviderNotFoundError |
| src/providers/openmeteo.py (`fetch_forecast`, Fallback-Schleife, Cross-Provider-Seam) | geprüfte Produktionsstelle |

## Existing Patterns
- Methode und Kriterium aus #3208/#3263/#3264: Mutation per String-Ersetzung mit externer Sicherungskopie
  (nie `git checkout/stash/reset`), Protokoll vorher/nachher unter `docs/artifacts/<workflow>/`.

## Dependencies
- Upstream: nur Testcode; Produktionscode unverändert.
- Downstream: 1155 ac7 importiert `_provider_seam`/`_BERLIN` aus 1115 → beide bleiben unangetastet.
  Testnamen in `docs/specs/_archive/modules/issue_1142_*.md` (Archiv) und als „analog"-Verweis in
  `docs/specs/modules/provider_dwd.md:109`, `provider_meteofrance.md:106` — der Testname
  `test_seam_catches_provider_request_and_not_found_error` bleibt bestehen, keine Doku-Änderung nötig.

## Analysis (Summe 1: Kontext und Analyse in einem Durchgang, gegen Quelltext geprüft 2026-11-23)

### Type
Rework (Testsuite-Bereinigung, kein Produktionscode). Befund G6a am 2026-11-23 in Phase 2 erneut gegen den Quelltext bestätigt (1142 Z. 429–435 vs. 474–484: identischer Aufbau, Aufruf und Erwartung).

### Open Questions
- keine

### G6a — 1142 ac4 Fall (a) ist identisch mit 1142 ac3 (ENTFERNEN)
- ac3 und ac4-Fall-(a): identischer Aufbau (`_geosphere_fault_server`, `_FutureAtDirectAdapter` als
  `at_direct`, `_total_outage_seam`, `_INNSBRUCK`), identischer Aufruf `fetch_forecast(_INNSBRUCK,
  enrich_ensemble=False)`, identische Erwartung `pytest.raises(ProviderRequestError)` +
  `exc.value.provider == "openmeteo"`. ac3 prüft zusätzlich die Retry-Zahl.
- ⇒ Fall (a) ist echte Teilmenge von ac3 → **Fall (a) aus ac4 entfernen**, Fall (b) (ProviderNotFoundError)
  bleibt. Testname bleibt (Spec-Verweise), Docstring nennt ac3 als Wächter für (a).

### Geprüft, bleibt (ähnlich, nicht identisch)
- 1115 ac2 (Berlin, **400**, Retry auf 1 gekappt) ↔ 1155 ac3 (Lappland, **404**, echter Retry):
  andere Werte und andere Ebene (1155 misst zusätzlich „kein Retry") → bleibt. 400 ist der fachlich
  begründete Fall (Bug #353, Datum außerhalb Horizont).
- 1115 ac3 (Berlin: `fallback_model is not None` / `!= icon_d2`, Kontrolle None) ↔ 1155 ac4 (Lappland:
  `== Folge-Kandidat`, `fallback_reason`) und 1155 ac2 (None nach Primär-Retry-Erfolg): andere Orte,
  andere Wege zum Erfolg → bleibt.
- 1115 ac1 ↔ 1115 ac3-Fallback-Hälfte: gleiche Eingabe, verschiedene Erwartungen → bleibt.
- 1155 ac7 `isinstance(NormalizedTimeseries)`: Setup-Assert des Laufzeittests (gleiche Eingabe wie 1115 ac1),
  ohne ihn wäre die Zeitmessung bedeutungslos → bleibt.
- 1141 ac2 (Lappland Totalausfall → raise) ↔ 1155 ac1 (Lappland alle 503 → raise): 1141 ac2 trägt die
  eigene Zusicherung „keine Region" und läuft mit gekapptem Retry; 1155 ac1 misst Retry-Zahlen → bleibt.
- 1141 ac5 (de_direct/DWD 503 → OM-Fehler) ↔ 1142 ac3 (at_direct/GeoSphere 503 → OM-Fehler):
  anderer Direktprovider, andere Region → bleibt. 1141 ac5 ↔ ac6: gleiche Eingabe, andere Erwartung → bleibt.
- 1141 ac1 (live) ↔ ac3: gleiche Eingabe, andere Erwartung → bleibt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| tests/tdd/test_issue_1142_geosphere_direct_fallback.py | MODIFY | in `test_seam_catches_provider_request_and_not_found_error` Fall (a) entfernen, Docstring anpassen (Verweis auf ac3) |
| docs/artifacts/rework-3265-fallback-dubletten/ | CREATE | Mutationsprotokoll vorher/nachher |

### Scope Assessment
- Files: 1 MODIFY + 1 Artefakt; LoC ca. −15 / +3; Risk LOW (nur Testcode).

### Technical Approach
1. Mutation VORHER (Kern-Schicht, `-m "not live"`): im Cross-Provider-Seam von `openmeteo.py` den Fang von
   `ProviderRequestError` aus dem `except` nehmen (GeoSphere-Fehler schlägt durch) → muss von 1142 ac3 UND
   ac4 gefangen werden.
2. Fall (a) entfernen.
3. Mutation NACHHER: dieselbe Mutation weiterhin von 1142 ac3 gefangen; zweite Mutation (Fang von
   `ProviderNotFoundError` entfernen) weiter von ac4 (b) gefangen.
4. Kern-Schicht der vier Dateien grün (benannte Dateien).

## Risks & Considerations
- Kleiner Ertrag: die vier Dateien sind überwiegend „ähnlich", nicht doppelt — ehrlich so berichten.
- Mutationen nur per String-Ersetzung mit Sicherungskopie außerhalb des Baums.

## Nebenbefund (nicht in diesem Ticket)
- 1141 ac1 ist laut Kommentar offline rot (Ursache offen, #1196 Klasse A) und nur deshalb `live` markiert.
