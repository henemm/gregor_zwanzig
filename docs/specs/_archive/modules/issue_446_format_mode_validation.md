---
entity_id: issue_446_format_mode_validation
type: module
created: 2026-05-29
updated: 2026-05-29
status: implemented
version: "1.0"
tags: [hardening, backend, format_mode, validation, loader]
---

<!-- Issue #446 — Hardening: format_mode-String-Validierung im Loader -->

# Issue 446 — format_mode-Validierung in loader._resolve_format_mode

## Approval

- [ ] Approved

## Purpose

`_resolve_format_mode()` in `src/app/loader.py` gibt bisher unbekannte `format_mode`-Strings (z.B. `"Symbol"` mit Großbuchstabe, `"raw_v2"`) stillschweigend zurück, ohne sie gegen die erlaubten Werte in `MetricDefinition.format_modes` zu prüfen. Dieses Hardening ergänzt eine Validierung: bei unbekanntem Wert wird eine WARNING geloggt und auf `default_format_mode` aus dem Katalog zurückgefallen, damit fehlerhafte Konfigurationen nie unbemerkt in die Render-Schicht gelangen.

## Source

**Python-Backend**

- **File:** `src/app/loader.py`
- **Identifier:** `_resolve_format_mode` (Zeilen 40–61, wird erweitert)

> **PFLICHT — Schicht-Hinweis:** Affected Files MUSS die richtige Schicht treffen:
> - **Frontend / User-UI** → `frontend/src/...` (SvelteKit, produktive Oberfläche auf gregor20.henemm.com)
> - **Go-API** → `api/`, `internal/`, `cmd/` (Production-API auf Port 8090)
> - **Python-Backend** → `src/services/`, `src/app/`, `src/providers/` (FastAPI Core über `api.main:app`)
>
> Im Zweifel vor dem Spec-Schreiben grep auf den betroffenen Symbol-Namen — Server-Code (Go vs. Python) und UI-Code (SvelteKit vs. Server-Templates) sind getrennt. Es gab in der Vergangenheit Doppelarbeit, weil Specs Helper-Funktionen in der falschen Schicht verortet haben (Issue #129).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `get_metric(metric_id)` (`src/app/metric_catalog.py`) | Python-Backend | Liefert `MetricDefinition` mit `.format_modes: tuple[str,...]` und `.default_format_mode: str` — wird für Validierung und Fallback genutzt |
| `MetricDefinition` (`src/app/metric_catalog.py`) | Python-Backend | Datenklasse; `.format_modes` ist die erlaubte Wertemenge, `.default_format_mode` ist der Rückfallwert |
| `_effective_format_mode` (`src/output/renderers/email/helpers.py`) | Python-Backend | Thin Wrapper auf `_resolve_format_mode` (seit #444) — profitiert automatisch von der Validierung ohne eigene Änderung |

## Implementation Details

### Schritt 1 — `_resolve_format_mode` um Validierungsblock erweitern

Den bestehenden Block in `src/app/loader.py` nach `raw = mc_data.get("format_mode")` und `if raw is not None:` um eine Katalog-Prüfung ergänzen. Der vollständige neue Body der Funktion:

```python
def _resolve_format_mode(mc_data: dict, metric_id: str) -> str:
    raw = mc_data.get("format_mode")
    if raw is not None:
        try:
            from app.metric_catalog import get_metric
            metric_def = get_metric(metric_id)
            if raw not in metric_def.format_modes:
                import logging
                logging.getLogger(__name__).warning(
                    "Unknown format_mode %r for metric %r; "
                    "falling back to default %r",
                    raw, metric_id, metric_def.default_format_mode,
                )
                return metric_def.default_format_mode
        except KeyError:
            pass  # unbekannte metric_id → weiter mit raw
        return raw
    if not mc_data.get("use_friendly_format", True):
        return "raw"
    try:
        from app.metric_catalog import get_metric
        return get_metric(metric_id).default_format_mode
    except KeyError:
        return "raw"
```

Logik-Fälle im neuen Block (`if raw is not None:`):
1. `get_metric(metric_id)` klappt und `raw in metric_def.format_modes` → `raw` unverändert zurückgeben (Happy Path).
2. `get_metric(metric_id)` klappt und `raw not in metric_def.format_modes` → WARNING loggen, `metric_def.default_format_mode` zurückgeben.
3. `get_metric(metric_id)` wirft `KeyError` (unbekannte `metric_id`) → `except KeyError: pass` → `raw` unverändert zurückgeben (Toleranz bei unbekannter Metrik).

### Schritt 2 — Keine Änderungen an Aufrufstellen oder anderen Modulen

`src/app/metric_catalog.py` und `src/output/renderers/email/helpers.py` bleiben unverändert. `_effective_format_mode` (Thin Wrapper) delegiert weiterhin an `_resolve_format_mode` und erhält das Validierungsverhalten automatisch.

### Schritt 3 — Neue Test-Klasse anhängen

In `tests/red/test_issue_435_format_modes.py` eine neue Klasse `TestAC446FormatModeValidation` anhängen (+35–40 LoC) mit einem Test pro AC. Keine bestehenden Tests anfassen.

### LoC-Budget

- `src/app/loader.py`: +10 LoC
- `tests/red/test_issue_435_format_modes.py`: +35–40 LoC
- Gesamt: ~50 LoC (weit unter 250er-Default, kein Override nötig)

## Expected Behavior

- **Input:** `mc_data: dict` mit optionalem Schlüssel `"format_mode"` und `"use_friendly_format"`; `metric_id: str`
- **Output:** Ein valider `format_mode`-String; bei bekanntem Wert der Original-String; bei unbekanntem Wert (und bekannter Metrik) der `default_format_mode` aus dem Katalog; bei unbekannter Metrik der Original-String
- **Side effects:** Bei unbekanntem `format_mode` und bekannter Metrik wird eine WARNING über `logging.getLogger("app.loader")` emittiert

## Acceptance Criteria

- **AC-1:** Given `format_mode="Symbol"` (unbekannt, Großbuchstabe) für Metrik `cloud_total` / When `_resolve_format_mode` aufgerufen wird / Then wird `"symbol"` zurückgegeben (catalog default) und eine WARNING wird geloggt.
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC446FormatModeValidation::test_ac446_1_unknown_capitalized_falls_back_with_warning`

- **AC-2:** Given `format_mode="RAW"` (unbekannt, Großbuchstaben) für Metrik `cloud_total` / When `_resolve_format_mode` aufgerufen wird / Then wird `"symbol"` zurückgegeben (catalog default, nicht `"RAW"`).
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC446FormatModeValidation::test_ac446_2_unknown_all_caps_falls_back_to_catalog_default`

- **AC-3:** Given `format_mode="raw"` (valider Wert) für Metrik `cloud_total` / When `_resolve_format_mode` aufgerufen wird / Then wird `"raw"` unverändert zurückgegeben (kein Fallback, kein Log).
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC446FormatModeValidation::test_ac446_3_valid_mode_returned_unchanged`

- **AC-4:** Given `format_mode="raw_v2"` (unbekannt) für eine nicht-existierende Metrik `"nonexistent_metric"` / When `_resolve_format_mode` aufgerufen wird / Then wird `"raw_v2"` unverändert zurückgegeben (`KeyError` → pass → original raw).
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC446FormatModeValidation::test_ac446_4_unknown_metric_id_returns_raw_unchanged`

- **AC-5:** Given `format_mode="raw"` für Metrik `thunder` (hat `format_modes=("symbol",)`, nur Symbol erlaubt) / When `_resolve_format_mode` aufgerufen wird / Then wird `"symbol"` zurückgegeben (Fallback auf `default_format_mode`).
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC446FormatModeValidation::test_ac446_5_mode_not_in_restricted_format_modes_falls_back`

## Known Limitations

- Der Toleranzpfad bei unbekannter `metric_id` (`KeyError → pass → raw`) gibt den Originalwert unkontrolliert zurück. Das ist bewusstes Fail-Open-Verhalten, damit Metriken, die noch nicht im Katalog registriert sind, nicht blockiert werden.
- Das Logging verwendet `import logging` als Lazy-Import innerhalb des Validierungsblocks, konsistent mit dem bestehenden Muster für `get_metric`-Importe in derselben Funktion.
- Wenn `_effective_format_mode` von `helpers.py` den Wrapper-Aufruf auf `_resolve_format_mode` delegiert, wird das WARNING über den Logger `app.loader` emittiert, nicht über `app.output.renderers.email.helpers`. Das ist korrekt, da die Validierung in der SSOT-Funktion stattfindet.

## Changelog

- 2026-05-29: Implementation complete (Phase 6+7)
  - `src/app/loader.py`: `_resolve_format_mode()` um Validierungsblock erweitert (Zeilen 54–65, +12 LoC)
  - `tests/red/test_issue_435_format_modes.py`: `TestAC446FormatModeValidation` angehängt mit 5 ACs (+38 LoC)
  - Gesamt: +50 LoC (weit unter 250er-Default)
- 2026-05-29: Initial spec created (Phase 3, Issue #446)
