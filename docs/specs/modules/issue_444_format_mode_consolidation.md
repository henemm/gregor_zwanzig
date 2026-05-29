---
entity_id: issue_444_format_mode_consolidation
type: module
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [refactoring, output, backend, format_mode, deduplication]
---

<!-- Issue #444 — _effective_format_mode als Thin Wrapper auf loader._resolve_format_mode -->

# Issue 444 — Format-Mode-Konsolidierung (Thin Wrapper)

## Approval

- [ ] Approved

## Purpose

`_effective_format_mode` in `src/output/renderers/email/helpers.py` und `_resolve_format_mode` in `src/app/loader.py` implementieren dieselbe 3-stufige Präzedenzlogik (explizites `format_mode` → `use_friendly_format=False` → Katalog-Default) identisch. Dieses Refactoring macht `_effective_format_mode` zu einem Thin Wrapper, der an `loader._resolve_format_mode` delegiert, sodass die Präzedenzregel exakt eine Implementierung hat und Bugfixes oder Erweiterungen nur an einer Stelle vorgenommen werden müssen.

## Source

**Python-Backend**

- **File (SSOT, unverändert):** `src/app/loader.py`
- **Identifier:** `_resolve_format_mode` (Zeilen 40–61)

- **File (geändert):** `src/output/renderers/email/helpers.py`
- **Identifier:** `_effective_format_mode` (Zeilen 41–57, wird zu Thin Wrapper, ca. 10 LoC)

> **PFLICHT — Schicht-Hinweis:** Affected Files MUSS die richtige Schicht treffen:
> - **Frontend / User-UI** → `frontend/src/...` (SvelteKit, produktive Oberfläche auf gregor20.henemm.com)
> - **Go-API** → `api/`, `internal/`, `cmd/` (Production-API auf Port 8090)
> - **Python-Backend** → `src/services/`, `src/app/`, `src/providers/` (FastAPI Core über `api.main:app`)
>
> Im Zweifel vor dem Spec-Schreiben grep auf den betroffenen Symbol-Namen — Server-Code (Go vs. Python) und UI-Code (SvelteKit vs. Server-Templates) sind getrennt. Es gab in der Vergangenheit Doppelarbeit, weil Specs Helper-Funktionen in der falschen Schicht verortet haben (Issue #129).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_resolve_format_mode` (`src/app/loader.py:40–61`) | Python-Backend | SSOT der Präzedenzlogik; Input: `mc_data: dict, metric_id: str`; Output: aufgelöster `format_mode`-String |
| `MetricConfig` (`src/app/models.py`) | Python-Backend | Pydantic-Modell; liefert `format_mode`, `use_friendly_format`, `metric_id` als Attribute |
| `metric_catalog.get_metric()` (`src/app/metric_catalog.py`) | Python-Backend | Wird innerhalb `_resolve_format_mode` für den Katalog-Default-Lookup genutzt (Stufe 3 der Präzedenz) |
| `_effective_format_mode` — 3 Aufrufstellen | Python-Backend | `helpers.py` Zeilen 76, 567, 591 — bleiben unverändert, rufen weiterhin `_effective_format_mode(mc)` auf |

## Implementation Details

### Schritt 1 — `_effective_format_mode` zu Thin Wrapper umbauen

Den Body der Funktion in `src/output/renderers/email/helpers.py` (Zeilen 41–57) durch folgende Implementierung ersetzen:

```python
def _effective_format_mode(mc) -> str:
    """Issue #444: thin wrapper — delegates to loader._resolve_format_mode.

    See loader._resolve_format_mode for the authoritative precedence rule
    (explicit format_mode > use_friendly_format=False > catalog default).
    """
    from app.loader import _resolve_format_mode
    return _resolve_format_mode(
        {
            "format_mode": getattr(mc, "format_mode", None),
            "use_friendly_format": getattr(mc, "use_friendly_format", True),
        },
        mc.metric_id,
    )
```

Der Import ist bewusst als Lazy-Import (inline) ausgeführt, konsistent mit dem Muster, das `loader.py` selbst für `metric_catalog` verwendet. `loader.py` importiert nichts aus `output/` — kein zirkulärer Import entsteht.

### Schritt 2 — Keine Änderungen an den 3 Aufrufstellen

Die Aufrufstellen in `helpers.py` (Zeilen 76, 567, 591) bleiben unverändert. Die Signatur `_effective_format_mode(mc)` bleibt identisch.

### Schritt 3 — Neuer Test in bestehendem Test-Modul

In `tests/red/test_issue_435_format_modes.py` wird eine neue Klasse `TestAC444DelegationToResolveFormatMode` angehängt (ca. +45 LoC) mit Tests für alle drei Präzedenzfälle (AC-444-A, AC-444-B, AC-444-C).

### LoC-Budget

- `helpers.py`: −7 LoC (17 → 10 Zeilen in `_effective_format_mode`)
- `tests/red/test_issue_435_format_modes.py`: +45 LoC
- Netto: +38 LoC (weit unter 250er-Default, kein Override nötig)

## Expected Behavior

- **Input:** Ein `MetricConfig`-Objekt mit den Attributen `format_mode` (optional), `use_friendly_format` (bool, default `True`), `metric_id` (str)
- **Output:** Ein `format_mode`-String (z.B. `"raw"`, `"symbol"`, `"scale"`, `"simplified"`), identisch zu dem, was `loader._resolve_format_mode` für dasselbe Objekt zurückgeben würde
- **Side effects:** Keine — reine Berechnung ohne Schreib-Operationen; alle 3 bestehenden Aufrufstellen in `helpers.py` erhalten dasselbe Ergebnis wie zuvor

## Acceptance Criteria

- **AC-1:** (strukturell) Given `_effective_format_mode` wurde als Thin Wrapper umgebaut / When der Source-Code von `helpers.py` per `ast`-Inspektion analysiert wird / Then enthält der Body von `_effective_format_mode` einen Aufruf von `_resolve_format_mode`.
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC444DelegationToResolveFormatMode::test_ac444_a_delegates_to_resolve_format_mode`

- **AC-2:** (Parität) Given ein `MetricConfig`-Objekt für jeden der drei Fälle: (1) explizites `format_mode` gesetzt, (2) `use_friendly_format=False` ohne `format_mode`, (3) weder `format_mode` noch `use_friendly_format=False` / When `_effective_format_mode(mc)` aufgerufen wird / Then ist das Ergebnis identisch zu `loader._resolve_format_mode({"format_mode": mc.format_mode, "use_friendly_format": mc.use_friendly_format}, mc.metric_id)`.
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC444DelegationToResolveFormatMode::test_ac444_b_parity_all_three_precedence_cases`

- **AC-3:** (kein Duplikat) Given `_effective_format_mode` wurde als Thin Wrapper umgebaut / When der Source-Code von `helpers.py` per `ast`-Inspektion analysiert wird / Then enthält der Body von `_effective_format_mode` KEINEN direkten Zugriff auf `default_format_mode` (d.h. keine Re-Implementierung des Katalog-Lookups).
  - Test: `tests/red/test_issue_435_format_modes.py::TestAC444DelegationToResolveFormatMode::test_ac444_c_no_duplicate_catalog_lookup`

## Known Limitations

- `_resolve_format_mode` in `loader.py` wird im Production-Read-Pfad heute nicht aufgerufen — nach diesem Refactoring wird es indirekt über `_effective_format_mode` zur Render-Zeit aufgerufen. Das Deployment-Verhalten ändert sich nicht, aber der Code-Pfad verschiebt sich.
- Unbekannte `format_mode`-Strings (z.B. `"raw_v2"`) werden weiterhin ungeprüft durchgereicht (Verhalten geerbt von `_resolve_format_mode`). Strikte Validierung in [Issue #446](issue_446_format_mode_validation.md) (implementiert 2026-05-29).
- Die symmetrische Richtung — `loader._resolve_format_mode` als Wrapper auf `_effective_format_mode` — ist nicht möglich, da `loader.py` zur Load-Zeit auf einem serialisierten `dict` operiert, nicht auf einem `MetricConfig`-Objekt.

## Changelog

- 2026-05-29: Initial spec created (Phase 3, Issue #444)
