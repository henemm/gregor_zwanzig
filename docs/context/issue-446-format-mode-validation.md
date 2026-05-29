# Context: Issue #446 — format_mode-String-Validierung im Loader/Renderer (IMPLEMENTED 2026-05-29)

## Request Summary

`_resolve_format_mode()` in `src/app/loader.py` lässt unbekannte `format_mode`-Strings (z.B. `"Symbol"` mit Großbuchstaben, `"raw_v2"`) ungeprüft durch. Das Feature fügt strikte Validierung gegen `MetricDefinition.format_modes` hinzu: unbekannter Modus → `default_format_mode` + Warn-Log.

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/loader.py:40–61` | `_resolve_format_mode()` — hier muss die Validierung rein (Zeile 53–54) |
| `src/app/metric_catalog.py:25–50` | `MetricDefinition` mit `format_modes: tuple[str, ...]` + `default_format_mode: str` |
| `src/output/renderers/email/helpers.py:41–54` | `_effective_format_mode()` — Thin Wrapper auf `_resolve_format_mode` (seit #444) |
| `tests/red/test_issue_435_format_modes.py` | Existierende Tests für format_mode — neue Tests für #446 hier anhängen |

## Existing Patterns

- **Logging-Muster in loader.py:** Inline `import logging` + `logging.getLogger(__name__).warning(...)` (Zeile 778–780)
- **Katalog-Lookup:** `from app.metric_catalog import get_metric` wird bereits in `_resolve_format_mode` für den Default-Fallback (Stufe 3) genutzt (Zeile 58–59); dasselbe Pattern kann für die Validierung benutzt werden
- **Fehler-Fallback:** Unbekannte `metric_id` → `except KeyError: return "raw"` (Zeile 60–61) — analoge Strategie für unbekannten Modus: silent fallback + Warn

## Dependencies

- **Upstream:** `metric_catalog.get_metric(metric_id)` liefert `MetricDefinition` mit `.format_modes` und `.default_format_mode`
- **Downstream:** Alle Aufrufer von `_resolve_format_mode`: `loader.py` Zeilen 59, 417, 449 (direkte Aufrufe) + `_effective_format_mode` in `helpers.py` (Thin Wrapper)

## Existing Specs

- `docs/specs/modules/issue_435_metric_format_modes.md` — Ursprungs-Spec für format_mode-System
- `docs/specs/modules/issue_444_format_mode_consolidation.md` — Thin-Wrapper-Refactoring; notiert explizit: "Unbekannte `format_mode`-Strings werden weiterhin ungeprüft durchgereicht — Strikte Validierung bleibt Out-of-Scope (Adversary F004, #435)" → das ist genau das, was #446 schließt

## Current Behavior (Problem)

```python
# loader.py:52–54 (aktuell)
raw = mc_data.get("format_mode")
if raw is not None:
    return raw  # ← kein Check ob raw in metric.format_modes
```

Beispiel: `format_mode="Symbol"` (Tippfehler, Großbuchstabe) → `fmt_val()` in `helpers.py:368` berechnet `use_friendly = (mode is not None and mode != "raw")` → `True` → landet auf Friendly-Pfad, obwohl der Nutzer möglicherweise ein Symbol-Rendering erwartet hat. Kein Hinweis im Log.

## Target Behavior

```python
raw = mc_data.get("format_mode")
if raw is not None:
    # Validierung: Modus muss in der Metrik-Definition erlaubt sein
    try:
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
        pass  # unbekannte metric_id → weiter mit raw (bestehender Fallback)
    return raw
```

## Implementierungsstrategie (Phase 2 Ergebnis)

**Approach:** Validierung direkt in `_resolve_format_mode` (kein separater Helper), weil:
- `metric_id`-Parameter, `try/except KeyError` und `get_metric`-Import sind bereits da
- Ein zusätzlicher Helper wäre eine Einheit ohne direkten Aufrufer von außen

**Änderungsumfang:**
- `src/app/loader.py`: +10 LoC
- `tests/red/test_issue_435_format_modes.py`: +35–40 LoC (neue Klasse `TestAC446FormatModeValidation`)
- Gesamt: ~50 LoC — weit unter 250er-Limit

**Test-Cases:**
- TC-1: Unbekannter String (`"Symbol"` für cloud_total) → Fallback auf catalog default (`"symbol"`)
- TC-2: Case-Variante (`"RAW"` für cloud_total) → Fallback auf `"symbol"`
- TC-3: Valider String (`"raw"` für cloud_total) → passiert unverändert durch
- TC-4: Unbekannte metric_id (`"raw_v2"` für `"nonexistent"`) → `KeyError` → unverändert zurück
- TC-5: `thunder` hat nur `("symbol",)` — gespeichertes `"raw"` → Fallback auf `"symbol"` (**kritischer Edge Case!**)

## Risks & Considerations

- **Scope klein:** Nur `_resolve_format_mode` geändert (~8 LoC), keine anderen Dateien
- **Backward-Compat:** Valide Strings (raw/symbol/scale/simplified) passieren unverändert — kein Regressionsrisiko
- **Unbekannte metric_id:** Weiterhin wie bisher behandelt (Zeile 60–61: `except KeyError: return "raw"`); die neue Validierung greift nur wenn die metric_id bekannt ist
- **Kein User-Impact heute** (Frontend sendet nur valide Strings) → Low-Priority, aber saubere Diagnose-Grundlage für die Zukunft
- **Tests:** Neue Klasse in `tests/red/test_issue_435_format_modes.py` (analoge Struktur zu bestehenden AC-Klassen, keine Mocks)
