# Context: issue-1034-official-alerts-foundation

## Request Summary
Slice 1 von Epic #1033: Fundament für amtliche Warnungen im Orts-Vergleich — Datentyp `OfficialAlert`, Quellen-Registry mit Geo-Scope (`covers(lat, lon)`), fail-softe Integration in die Compare-Mail. Noch KEINE echte Quelle (kommt in #1035-#1037); Plumbing wird mit einer Test-Fake-Quelle bewiesen. PO-Go für Umsetzungsstart liegt vor (2026-07-06). Terminkontext: Epic-Ziel 2026-07-20 (Côte-d'Azur-Urlaub des PO).

## Related Files
| File | Relevance |
|------|-----------|
| `docs/specs/modules/issue_1034_official_alerts_foundation.md` | Fertige Spec (AC-N-Format) aus der Planungsphase — Grundlage für Phase 2/3 |
| `docs/adr/0016-amtliche-warnungen-additiver-typ.md` | Architektur-Entscheidung: eigener additiver Typ, NICHT Δ-Alert/WeatherProvider |
| `src/services/comparison_engine.py` | Integrationspunkt: `run()` (:38) reichert `LocationResult` an; Geo-Muster `_select_provider_for_location` (:262) mit `GEOSPHERE_BOUNDS` (:269) |
| `src/app/user.py` | `LocationResult` (:147) bekommt additives Feld `official_alerts` |
| `src/output/renderers/email/compare_html.py` | `render_compare_html()` (:552) — neuer Badge-/Warn-Block pro Ort |
| `src/providers/base.py` | Vorbild-Registry: `WeatherProvider`-Protocol (:19), `register_provider` (:92), `get_provider` (:101) |
| `src/services/radar_service.py` | Vorbild Geo-Scope: `_AROME_FR_*`-Bbox (:39-42), `_within_arome_france` (:353) |
| `src/services/scheduler_dispatch_service.py` | Produktiver Versandpfad: `run_compare_presets_daily` (:20), `send_one_compare_preset` (:198), `ComparisonEngine.run` (:237) |
| `src/services/compare_subscription.py` | Legacy-Pfad (#456), ruft ebenfalls `ComparisonEngine.run` (:90) — profitiert automatisch, kein eigener Umbau |

## Existing Patterns
- **Registry:** Protocol + `register_*`/`get_*` + Lazy-Load in `src/providers/base.py` — 1:1-Vorbild für `OfficialAlertSource`-Registry.
- **Geo-Scope:** flache Bbox-Konstanten + `_within_*`-Prädikat + geordnete Kette (`radar_service.py`) — Vorbild für `covers(lat, lon)`.
- **Beide Dispatch-Zweige beachten** (Lehre aus #952/#957): produktiv = `scheduler_dispatch_service.py` (Scheduler + manueller Senden-Button), legacy = `compare_subscription.py`. Beide laufen über `ComparisonEngine.run()` → Integration dort trifft automatisch beide.
- **Compare-Mail-Gate:** Marker `X-GZ-Mail-Type: compare`, E2E-Validierung via `email_spec_validator.py` gegen echte Staging-Mail (Stalwart-Postfach).

## Dependencies
- Upstream: keine neuen externen Abhängigkeiten in diesem Slice (Fake-Quelle rein lokal); ENV `GZ_METEOFRANCE_APIKEY` liegt schon in Prod-/Staging-.env, wird aber erst ab #1035 benutzt.
- Downstream: #1035/#1036/#1037 implementieren echte Quellen gegen das hier gebaute Interface; #1040 (Config-Checkbox) liest das hier eingeführte Verhalten (Default an).

## Existing Specs
- `docs/specs/modules/issue_1034_official_alerts_foundation.md` — dieser Slice
- `docs/features/epic-1033-compare-official-alerts.md` — Epic-Übersicht
- `docs/reference/api_contract.md` — DTO-Konventionen (bei `LocationResult`-Erweiterung beachten)

## Risks & Considerations
- **Diskrepanz in der Spec prüfen (Phase 2):** Die Planungs-Spec erwähnt `src/services/comparison_renderers.py` — diese Datei existiert NICHT (Kandidaten: `comparison_scoring.py`, Renderer unter `src/output/renderers/`). Text-Renderer-Parität war ohnehin in die Quellen-Slices verschoben; Datei-Liste der Spec in der Analyse korrigieren.
- Fail-soft ist Pflicht: leere/kaputte Quelle darf die Compare-Mail nie blockieren (try/except pro Quelle).
- Mandanten-Pflicht: Integration läuft über bestehende user_id-Pfade; Tests mit zwei Nutzern.
- Kein Mock-Missbrauch: Fake-Quelle ist ein echtes registriertes Objekt im echten Codepfad (erlaubtes Seam analog Fake-Radar), kein `Mock()`/`patch()`.
- LoC-Limit 250 (Workflow) — Spec schätzt das Fundament bewusst schlank.

## Analysis

### Type
Feature (Slice 1 von Epic #1033)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/official_alerts/__init__.py` | CREATE | Paket-Export (`OfficialAlert`, Registry) |
| `src/services/official_alerts/models.py` | CREATE | Dataclass `OfficialAlert` |
| `src/services/official_alerts/base.py` | CREATE | `OfficialAlertSource`-Protocol + Registry + `get_official_alerts_for_location()` (fail-soft, try/except pro Quelle) |
| `src/app/user.py` | MODIFY | `LocationResult` + `official_alerts: list = field(default_factory=list)` (transient, keine Persistenz betroffen) |
| `src/services/comparison_engine.py` | MODIFY | Anreicherung NUR im Erfolgszweig (:180); Fehlerzweige (:70/:201) bleiben beim Default `[]` |
| `src/output/renderers/email/compare_html.py` | MODIFY | Neue `_render_official_alerts_block()` (div/span, KEIN `<table>`), Slot bei :646 hinter `warnings_html`, vor `matrix_html` |

**Bewusst NICHT in diesem Slice:** `src/output/renderers/comparison.py` (`render_comparison_text` :331 — Text-Parität laut Known Limitations der Slice-Spec erst mit #1035); `api/routers/compare.py` JSON-Ausgabe (Epic-Scope = Mail-only; Go-nativer `/api/compare/run` ist ohnehin separate Engine → Teil-Sichtbarkeit wäre inkonsistent). Beides als Out-of-Scope in der Spec dokumentieren.

### Scope Assessment
- Files: 6 (3 neu, 3 geändert)
- Estimated LoC: ~110–140 src-LoC (Limit 250 — Puffer)
- Risk Level: LOW

### Technical Approach
Eigener Renderer-Block statt Wiederverwendung von `_render_warning_banner` (:130 — hart auf Orange, kann AC-2-Farbcodierung nicht): `_render_official_alerts_block(locations)` mit Level-Farb-Mapping auf bestehende Tokens (`design_tokens.py:25-27`: 1-2→G_SUCCESS, 3→G_WARNING, 4→G_DANGER). Leere Liste ⇒ leerer String ⇒ AC-1 (byte-identisch) strukturell gesichert. Registry-Muster nach `providers/base.py`; `official_alerts/` importiert nur `app.user`-Typen → kein Kreis-Import.

### Dependencies
- Aufrufer `ComparisonEngine.run`: `api/routers/compare.py:53` (Web-Proxy), `compare_subscription.py:90` (legacy), `scheduler_dispatch_service.py:237` (produktiv) — alle profitieren automatisch.
- `render_compare_html` zusätzlich von `validator_render_service.py:170` (Vorschau-Endpoint).
- Go-nativer `/api/compare/run` (internal/compare) = separate Engine, außerhalb des Epic-Scopes (Mail).

### Validator-/Gate-Constraints (hart)
- `email_spec_validator.py`: exakt 2 `<table>`-Tags; erste `<table>` = Vergleichstabelle → neuer Block div/span-basiert und NIE vor der Vergleichstabelle.
- **Renderer-Commit-Gate #811:** `renderer_mail_gate.py:42` matcht auch `compare_html.py` → Commit verlangt frischen Matrix-Test-Nachweis (`tests/tdd/test_issue_811_mode_matrix.py`) + `briefing_mail_validator.py`-Log, obwohl fachlich Compare. Bekanntes mechanisches Erfordernis, KEIN Bug — im Implementierungs-/Commit-Ablauf einplanen.

### TDD-Reihenfolge
1. AC-1 (byte-identisches HTML bei leerer Registry), 2. AC-3 (Fail-soft bei werfender Fake-Quelle), 3. AC-2 (farbcodierter Badge). Implementierung: models → base/Registry → Engine-Wiring → Renderer-Block.

### Open Questions
- Keine offene Produktentscheidung. Out-of-Scope-Punkte (Text-Parität → #1035, JSON-Sichtbarkeit) werden explizit in die Spec-Freigabe aufgenommen.
