# Context: fix-1891-compare-user-id

## Request Summary
`GET /api/compare` lädt Orte unabhängig vom eingeloggten Nutzer immer über den
Pseudo-Nutzer `"default"` — Verstoß gegen die Mandantentrennungs-Pflicht
(CLAUDE.md). Fix: echte `user_id` aus dem Auth-Kontext (von Go injiziert)
durchreichen, analog zu allen anderen authentifizierten Endpoints.

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/compare.py:26-38` | `run_comparison()` — ruft `load_all_locations()` ohne `user_id` auf. Fehlerort. |
| `src/app/loader.py:1263` | `load_all_locations(user_id: str = "default")` — Default-Fallback, den der Router nie überschreibt. |
| `internal/handler/proxy.go:75-102,140-158` | `CompareProxyHandler` + `appendUserID()` — Go injiziert den echten Nutzer bereits korrekt in den Query-String (Anti-Spoofing, entfernt clientseitige `user_id`-Werte). Keine Änderung nötig. |
| `internal/router/router.go:156` | Route liegt im authentifizierten Block (`AuthMiddleware`, Cookie-Pflicht). |
| `api/routers/preview.py:33,89` | Referenzmuster: `user_id: str = Query(..., description="Session-User (vom Go-Proxy injiziert)")` — Pflichtparameter, kein Default. Gleiches Muster in `gpx.py:25`, `internal.py:30,58`, `notify.py:21`, `validator.py:183,247,276`. |
| `api/routers/scheduler.py:291` | Abweichendes, schwächeres Muster (`Query("default")`) — NICHT als Vorbild verwenden, da es denselben Fehler in abgeschwächter Form zeigt. |

## Existing Patterns
- 16 bestehende Endpoints reichen `user_id` bereits per `user_id: str = Query(...)` durch (Pflichtparameter ohne Default) — das ist das etablierte, sichere Muster für Go-proxied Endpoints hinter `AuthMiddleware`.
- Von 8 Python-Aufrufstellen von `load_all_locations()` ist `compare.py:38` die **einzige** ohne `user_id`-Argument (alle anderen: `compare_preview_service.py:240`, `compare_radar_alert.py:92`, `scheduler_dispatch_service.py:419`, `compare_official_alert.py:90`, `dispatch_orchestrator.py:147,183`, `compare_alert.py:124`).
- Go-Proxy-Seite ist bereits korrekt: `appendUserID()` entfernt clientseitig mitgeschickte `user_id`-Werte und setzt ausschließlich den authentifizierten Nutzer — kein Spoofing-Risiko auf Go-Seite.

## Dependencies
- **Upstream:** `internal/handler/proxy.go` (`CompareProxyHandler`) — reicht bereits `?user_id=...` an Python durch, sobald der Python-Router den Parameter akzeptiert, braucht Go **keine Änderung**.
- **Downstream:** `run_comparison_parallel()` (`src/services/comparison_parallel.py`) erhält die bereits userbezogen gefilterte `selected`-Liste — keine Änderung nötig.

## Existing Specs
- Keine dedizierte Spec zu `/api/compare` gefunden; verwandt: `docs/adr/` zu Auth/Mandantentrennung (nicht einzeln durchsucht, Pattern ist im Code eindeutig etabliert).

## Bestehende Tests, die brechen werden (Scope-relevant)
Fünf Aufrufstellen (in 5 Dateien) rufen `GET /api/compare?location_ids=...` **ohne** `user_id`-Query-Parameter auf. Wird `user_id` zum Pflichtparameter (`Query(...)`, analog `preview.py`), schlagen sie mit HTTP 422 fehl, bis sie angepasst sind:
- `tests/tdd/test_hail_flag_metrics_catalog_and_compare_api.py:103`
- `tests/tdd/test_vorschau_anzeige_folgen_ortszone.py:477,521,597`
- `tests/tdd/test_sport_aware_scoring.py:251`
- `tests/unit/test_sofortvergleich_parallel.py:102-103` (Funktion `_abfrage()`, per Plan-Agent-Bewertung + Nachlese bestätigt)

Alle stubben `load_all_locations` bereits mit `lambda *a, **kw: [...]` (nimmt beliebige Argumente an) — die Anpassung ist rein additiv (`&user_id=...` an die Aufruf-URL), keine Stub-Signatur-Änderung nötig.

## Analysis

### Type
Bug (Verstoß gegen bestehende Mandantentrennungs-Pflicht, kein neues Feature).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `api/routers/compare.py` | MODIFY | `user_id: str = Query(...)` in Signatur von `run_comparison()` ergänzen, an `load_all_locations(user_id=user_id)` durchreichen. ~2-3 Zeilen. |
| `tests/tdd/test_hail_flag_metrics_catalog_and_compare_api.py` | MODIFY | `&user_id=...` an Aufruf-URL ergänzen |
| `tests/tdd/test_vorschau_anzeige_folgen_ortszone.py` | MODIFY | `&user_id=...` an 3 Aufruf-URLs ergänzen |
| `tests/tdd/test_sport_aware_scoring.py` | MODIFY | `&user_id=...` an Aufruf-URL ergänzen |
| `tests/unit/test_sofortvergleich_parallel.py` | MODIFY | `&user_id=...` in `_abfrage()` ergänzen |
| neue Testdatei/-funktion (Name TDD-Phase) | CREATE | Zwei-Nutzer-Nachweis (Pflicht CLAUDE.md) + 422-Nachweis bei fehlendem `user_id` |

### Scope Assessment
- Files: 6 (1 Produktivcode, 5 Bestandstests) + 1 neue Testdatei
- Estimated LoC: Produktivcode ~2-3 Zeilen; Testanpassungen ~8 Zeilen additiv; neuer Test ~40-60 Zeilen
- Risk Level: LOW auf Produktivverkehr (siehe unten), MEDIUM auf Blast-Radius-Klassifikation (Mandantentrennung ist ein kritischer Pfad)

### Technical Approach
`user_id: str = Query(...)` als Pflichtparameter — konsistent mit 16 etablierten Endpoints, schließt den Fehler strukturell aus. Kein Default nötig: einziger Produktionsaufrufer ist `CompareProxyHandler` (Go), der `user_id` bereits zuverlässig injiziert. Keine CLI-, Cron- oder internen Python-Aufrufer von `run_comparison()`/`/api/compare` gefunden. Ein Default wie bei `scheduler.py:291` würde den Fehler nur abschwächen statt beheben.

### Dependencies
- Keine Sequenzabhängigkeit zu Go — `/api/compare` liegt bereits in der globalen `AuthMiddleware`-Gruppe (`router.go:37`), keine Ausnahme in der Public-Whitelist (`internal/middleware/auth.go:33-46`). Ohne gültige Session bekommt der Handler bereits 401, bevor `appendUserID` mit leerem `userID` aufgerufen würde. Dokumentiert in `test_selftest_auth_required.py:215`.
- Python-Änderung ist eigenständig sicher deploybar.

### Open Questions
Keine — Plan-Agent-Bewertung (Standard-Track, Schritt 3) hat technischen Ansatz, Risiko, Scope und Testaufbau abschließend geklärt.

## Risks & Considerations
- **Pflicht- vs. Default-Parameter:** `user_id: str = Query(...)` (Pflicht, wie bei `preview.py`) ist konsistent mit der Mehrheit der authentifizierten Endpoints und schließt den Fehler strukturell aus (kein stiller Fallback mehr möglich). Abweichendes Muster `Query("default")` (`scheduler.py:291`) wird bewusst nicht übernommen.
- **Zwei-Nutzer-Nachweis PFLICHT** (CLAUDE.md): Der Bugfix-Nachweis braucht einen Test mit zwei verschiedenen `user_id`-Werten und jeweils eigenen Orten — die 5 o.g. Bestandstests weisen nur *irgendeinen* `user_id`-Wert nach, nicht die Trennung selbst. Stub muss `user_id` tatsächlich AUSWERTEN (z.B. `lambda user_id=None, **kw: {"alice": ORTE_ALICE, "bob": ORTE_BOB}[user_id]`), nicht nur ignorieren.
- **Test-Isolation:** Der neue Zwei-Nutzer-Test darf KEINEN `@pytest.mark.live`/`@pytest.mark.real_data_root`-Marker tragen — `tests/conftest.py` installiert die Daten-Isolation dort nicht, der Test würde sonst gegen den echten `data/users/`-Baum laufen statt gegen Fixtures.
- **Nicht im Scope:** Der zweite Befund aus #1891 (kein Limit auf `location_ids`) ist laut PO-Entscheid abgetrennt und als Zeile in #1199 dokumentiert — hier nicht mitfixen.
- **Nicht im Scope:** Go-Seite ist bereits korrekt, keine Änderung an `internal/`.
