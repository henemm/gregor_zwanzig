# Adversary Dialog — rework-3265-fallback-dubletten
Spec: docs/specs/modules/rework_3265_fallback_dubletten.md
Datum: 2026-11-23 10:20

## Checkliste
- [x] **Input:** Testbestand mit einer Teilmengen-Dopplung (Fall a gegen ac3 in 1142).
- [x] **Output:** gleiche geprueften Zusicherungen, je an einer wirksamen Stelle; ein Fall weniger; Kern-Schicht der vier Dateien weiter 100 % gruen.
- [x] **Side effects:** keine Auswirkung auf Produktverhalten oder Deploy-Inhalt.
- [x] **AC-1:** Given Fall (a) in `test_seam_catches_provider_request_and_not_found_error` (1142) ist identisch mit einem Teil von `test_geosphere_5xx_preserves_original_error_and_retry` (ac3) / When der Umbau fertig ist / Then ist Fall (a) samt `exc_a`-Assert entfernt, Fall (b) (`ProviderNotFoundError`, `at_direct` nicht registriert) mit beiden Asserts und der Testname unveraendert vorhanden, und der Docstring verweist fuer den frueheren Fall (a) auf ac3.
- [x] **AC-2:** Given die Mutation M1 (Fang von `ProviderRequestError` im Cross-Provider-Seam von `src/providers/openmeteo.py` entfernt) per String-Ersetzung mit externer Sicherungskopie / When sie vor und nach dem Umbau in der Kern-Schicht (`-m "not live"`) auf 1142 angewendet wird / Then wird sie vorher von ac3 und ac4 gefangen, nachher weiterhin von ac3 (Teilmenge verliert keinen Schutz), und nach Wiederherstellung aus der Sicherung ist 1142 wieder gruen.
- [x] **AC-3:** Given die Mutation M2 (Fang von `ProviderNotFoundError` im Cross-Provider-Seam entfernt) per String-Ersetzung mit externer Sicherungskopie / When sie nach dem Umbau auf 1142 angewendet wird / Then faengt weiterhin Fall (b) in `test_seam_catches_provider_request_and_not_found_error` die Mutation, und nach Wiederherstellung aus der Sicherung ist die Datei wieder gruen.
- [x] **AC-4:** Given es gibt aehnliche, aber nicht doppelte Paare (1115 ac2 gegen 1155 ac3, 1115 ac3 gegen 1155 ac4/ac2, 1155 ac7-Setup-Assert, 1141 ac2 gegen 1155 ac1, 1141 ac5 gegen 1142 ac3, 1141 ac1 gegen ac3) / When der Umbau fertig ist / Then sind 1115, 1141 und 1155 unveraendert, es gibt keine weiteren Loeschungen in 1142, und das Protokoll nennt je Paar die Begruendung (anderer Wert, andere Ebene, anderer Ort, anderer Provider, andere Erwartung), warum es bleibt.
- [x] **AC-5:** Given die vier Testdateien 1115, 1141, 1142 und 1155 / When sie namentlich mit `-m "not live"` ausgefuehrt werden (nie `uv run pytest` ohne Dateien) / Then sind alle gruen, die Kern-Schicht ist zu 100 % gruen und alle 6 CI-Checks des PR sind gruen.
- [x] **AC-6:** Given der Umbau betrifft nur Testsammlung und Dokumentation / When der Diff gegen `origin/main` geprueft wird / Then liegen alle geaenderten Dateien unter `tests/` oder `docs/`, `src/providers/openmeteo.py` ist byte-identisch zur externen Sicherung wiederhergestellt (kein Diff gegen `origin/main`), und es gibt keine Aenderung an Gate-Konfiguration.

## Dialog

### Runde 1
**Adversary:** Runde 1, Beweisführung je AC.
- AC-1 CONFIRMED. Der entfernte Block (git diff) baut `_geosphere_fault_server` + `_registered_test_direct_provider("at_direct", _FutureAtDirectAdapter)` + `_total_outage_seam` auf, ruft `provider.fetch_forecast(_INNSBRUCK, enrich_ensemble=False)` unter `pytest.raises(ProviderRequestError)` und prüft `provider == "openmeteo"`. ac3 macht exakt dasselbe und prüft zusätzlich `len(geo_server.contacted) == RETRY_ATTEMPTS`. Echte Teilmenge. Code reference: tests/tdd/test_issue_1142_geosphere_direct_fallback.py:410-443 (ac3). Fall (b) mit beiden Asserts (`exc_b.provider`, `not isinstance(... ProviderNotFoundError)`) und Testname intakt, `exc_a` kommt 0-mal vor, Docstring verweist auf AC-3. Code reference: tests/tdd/test_issue_1142_geosphere_direct_fallback.py:450-485.
Code reference: tests/tdd/test_issue_1142_geosphere_direct_fallback.py:410 (ac3, Wächter für früheren Fall a)
Code reference: tests/tdd/test_issue_1142_geosphere_direct_fallback.py:450 (Fall b, Testname und beide Asserts intakt)
- AC-2 CONFIRMED. Lauf `mutation_lauf.sh adversary` (Ausgabe: adversary-test-output.txt). Vorher (test-red-output.txt): M1 rot in ac3 UND ac4. Nachher: M1 -> `1 failed, 1 passed`, rot ist `test_geosphere_5xx_preserves_original_error_and_retry`. Wiederhergestellt: byte-identisch (cmp), 4 Dateien `7 passed, 12 deselected`.
- AC-3 CONFIRMED. M2 nachher: rot ist `test_seam_catches_provider_request_and_not_found_error` (Fall b). Wiederherstellung byte-identisch.
- AC-4 CONFIRMED. `git diff origin/main --stat` für 1115/1141/1155 leer; in 1142 nur der Fall-(a)-Block und der Docstring geändert. Paar-Begründungen stehen im Kopf von mutation_lauf.sh (sieben Paare mit Begründung).
- AC-5 CONFIRMED (lokal). Vier Dateien namentlich mit `-m "not live"`: `7 passed, 12 deselected`. CI-Teil (6 Checks) erst nach PR prüfbar: OFFEN, kein Finding.
- AC-6 CONFIRMED. `git diff origin/main --name-only`: nur docs/ und tests/tdd/test_issue_1142_geosphere_direct_fallback.py; `git diff origin/main --stat -- src/providers/openmeteo.py` leer; keine Gate-Konfiguration geändert.
**Implementierer:** (nicht beteiligt, keine Rückfrage)

### Runde 2
**Adversary:** Runde 2, eigene Gegenproben. Eigene Mutation M3 (selbst gebaut, nicht im Skript): im Seam `pass` durch `raise` ersetzt (Direktprovider-Fehler wird nicht mehr verschluckt). Ergebnis: beide verbliebenen 1142-Tests rot (ac3 und Fall b); Datei per Sicherungskopie wiederhergestellt (cmp ok, kein Diff gegen origin/main). Suche nach einer Mutation, die NUR der entfernte Fall (a) gefangen hätte: Fall (a) und ac3 teilen Fixture, Aufruf und Exception-Erwartung; ac3 ist strikt stärker (zusätzlich Retry-Zahl). Jede Mutation, die (a) rot macht (Seam fängt ProviderRequestError nicht / gibt falsche Exception zurück), macht ac3 ebenfalls rot (M1, M3 belegt). Keine Mutation gefunden, die nur (a) fängt. Rest-Hinweis (kein Finding): Der Docstring von ac3 nennt noch "RED heute"-Historie; kosmetisch.
Fall (b) schützt weiterhin einzeln den ProviderNotFoundError-Fang (M2).
**Implementierer:** (nicht beteiligt)

## Herkunft der Vorbedingungen

- kein Sprachprofil konfiguriert (`precondition_origins.default_lang`)
- Es ist kein Produktionscode geändert (reine Testbereinigung; `src/providers/openmeteo.py` ohne Diff gegen origin/main).

## Verdict

═══════════════════════════════════════
VERDICT: VERIFIED
═══════════════════════════════════════
Tests: 7 passed, 0 failed (vier Dateien, -m "not live"); Mutationen M1/M2/M3 jeweils vom verbleibenden Test gefangen.
Findings: keine. Offen: CI-Checks nach PR (AC-5-Teil).

## Geprüfte Dateien

- sha256:a6883cd4665535fe85861d439e96b010de426380210e13bf48055e3f9c50f74b  tests/tdd/test_issue_1142_geosphere_direct_fallback.py

## Prüfbasis

- base: ece30443ac09eb138070f0899d3498c55ef19141
- blob:50a8ea040e46664f55b052667ac51b2fbef9065d  tests/tdd/test_issue_1142_geosphere_direct_fallback.py
