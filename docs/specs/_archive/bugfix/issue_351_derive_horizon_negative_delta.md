---
entity_id: issue_351_derive_horizon_negative_delta
type: bugfix
created: 2026-05-29
updated: 2026-05-29
status: draft
version: "1.0"
tags: [backend, python, horizon-filter, derive-horizon, email-renderer, issue-351]
---

# Issue #351 — derive_horizon: negativer Delta (vergangene Etappen) explizit behandeln

## Approval

- [x] Approved

## Purpose

`derive_horizon()` in `src/output/renderers/email/helpers.py` leitet aus dem Abstand zwischen
Report-Datum und Etappen-Datum einen Horizont-Bezeichner (`today`/`tomorrow`/`day_after`) ab.
Vergangene Etappen (delta < 0) werden implizit durch das catch-all `return None` am Ende der
Funktion abgedeckt, aber ohne expliziten Guard und ohne Test-Coverage — das macht die Intention
unsichtbar und lässt Reviewer im Unklaren, ob das Verhalten für delta < 0 beabsichtigt oder ein
Versehen ist.

Der Fix macht das Verhalten explizit: ein dedizierter `if delta < 0: return None`-Guard mit
erklärendem Kommentar wird vor den positiven Delta-Checks eingefügt, und ein Test
`test_derive_horizon_negative_delta` deckt den Fall ab. Zusätzlich erhält die Spec
`issue_342_pro_metrik_horizon_backend.md` einen Known-Limitation-Satz, der dokumentiert, dass
vergangene Etappen den Horizont-Filter nicht auslösen.

## Source

- **File:** `src/output/renderers/email/helpers.py`
- **Identifier:** `derive_horizon` (Zeilen 263–278)

> Schicht: **Python-Backend** — `src/output/renderers/email/helpers.py` ist Teil des
> E-Mail-Renderers. Einzige Aufrufstelle: `src/output/renderers/email/html.py:235`.

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `src/output/renderers/email/helpers.py` | Python-Modul (vorhanden) | Enthält `derive_horizon()`; hier wird der Guard eingefügt |
| `tests/tdd/test_horizon_filter.py` | Pytest-Testdatei (vorhanden) | Bestehende Tests für delta=0/1/2/≥3; neuer Test für delta<0 wird ergänzt |
| `docs/specs/modules/issue_342_pro_metrik_horizon_backend.md` | Spec (vorhanden) | Known-Limitation-Satz für vergangene Etappen wird nachgetragen |

## Implementation Details

### 1. Expliziter Guard in `derive_horizon()` (helpers.py:263–278)

Vor den positiven Delta-Checks wird ein Guard für negative Deltas eingefügt:

```python
def derive_horizon(report_date: date, etappe_date: date) -> str | None:
    delta = (etappe_date - report_date).days
    # Vergangene Etappen (delta < 0) ignorieren den Horizont-Filter —
    # sie sind bereits abgelaufen und haben keinen relevanten Horizont.
    if delta < 0:
        return None
    if delta == 0:
        return "today"
    if delta == 1:
        return "tomorrow"
    if delta == 2:
        return "day_after"
    return None
```

Die Logik ändert sich nicht — das Rückgabeverhalten für delta < 0 war bereits `None`.
Der Guard macht nur die Absicht sichtbar und gibt Reviewern Gewissheit, dass der Fall
bewusst behandelt wird.

### 2. Neuer Test in `tests/tdd/test_horizon_filter.py`

Ergänzt nach dem bestehenden delta=0/1/2/≥3-Block:

```python
def test_derive_horizon_negative_delta():
    """Vergangene Etappen (delta < 0) geben None zurück — kein Horizont-Treffer."""
    report = date(2026, 5, 10)
    assert derive_horizon(report, date(2026, 5, 9)) is None   # delta = -1
    assert derive_horizon(report, date(2026, 5, 1)) is None   # delta = -9
    assert derive_horizon(report, date(2025, 12, 31)) is None  # delta = -130
```

### 3. Known-Limitation-Satz in `docs/specs/modules/issue_342_pro_metrik_horizon_backend.md`

In der `Known Limitations`-Sektion wird folgender Satz ergänzt:

```
- Vergangene Etappen (Etappen-Datum vor Report-Datum) ignorieren den Horizont-Filter:
  `derive_horizon()` gibt `None` zurück, sodass alle Metriken sichtbar bleiben.
  Dieses Verhalten ist beabsichtigt — für bereits abgelaufene Tage existiert kein
  sinnvoller Horizont-Kontext.
```

## Expected Behavior

- **Input:** `report_date: date`, `etappe_date: date`
- **Output:**
  - delta < 0 (vergangene Etappe): `None`
  - delta == 0: `"today"`
  - delta == 1: `"tomorrow"`
  - delta == 2: `"day_after"`
  - delta >= 3: `None`
- **Side effects:** keine — reine Berechnung, kein I/O, kein State

## Acceptance Criteria

**AC-1:** Given `etappe_date` liegt 1 oder mehr Tage vor `report_date` (delta < 0) /
When `derive_horizon(report_date, etappe_date)` aufgerufen wird /
Then gibt die Funktion `None` zurück und kein anderer Wert wird emittiert.
  - Test: (populated after /tdd-red)

**AC-2:** Given `etappe_date == report_date` (delta == 0) /
When `derive_horizon()` aufgerufen wird /
Then gibt die Funktion `"today"` zurück — unverändert gegenüber vor dem Fix.
  - Test: (populated after /tdd-red)

**AC-3:** Given die Implementierung in `helpers.py` ist geändert /
When `uv run pytest tests/tdd/test_horizon_filter.py` ausgeführt wird /
Then laufen alle bestehenden Tests plus der neue `test_derive_horizon_negative_delta` grün durch.
  - Test: (populated after /tdd-red)

## Affected Files

| Datei | Änderung |
|-------|----------|
| `src/output/renderers/email/helpers.py` | Expliziter `if delta < 0: return None`-Guard mit Kommentar vor den positiven Checks (~3 LoC) |
| `tests/tdd/test_horizon_filter.py` | Neuer Test `test_derive_horizon_negative_delta` mit 3 Assertions (~6 LoC) |
| `docs/specs/modules/issue_342_pro_metrik_horizon_backend.md` | Known-Limitation-Satz für vergangene Etappen (~4 LoC) |

## Known Limitations

- Das Verhalten für delta < 0 war vor diesem Fix bereits korrekt (`None` via catch-all).
  Dieser Fix ist rein dokumentarisch und testabdeckend — kein funktionales Risiko.
- `derive_horizon()` hat keine Kenntnis darüber, ob der Aufruf aus einem historischen
  Report stammt. Für zukünftige Horizonte über Tag 2 hinaus (delta >= 3) bleibt das
  Verhalten ebenfalls `None`; das ist durch Issue #342 dokumentiert und beabsichtigt.

## Changelog

- 2026-05-29: Initial spec erstellt (Issue #351 — derive_horizon negativer Delta, Adversary-Finding F003 aus #342).
