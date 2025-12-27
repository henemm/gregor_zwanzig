---
entity_id: debug_buffer
type: module
created: 2025-12-27
updated: 2025-12-27
status: implemented
version: "1.0"
tags: [debug, logging]
---

# DebugBuffer

## Approval

- [x] Approved

## Purpose

Sammelt Debug-Informationen waehrend der Programmausfuehrung. Stellt sicher, dass Console- und E-Mail-Debug identisch sind.

## Source

- **File:** `src/app/debug.py`
- **Identifier:** `class DebugBuffer`

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|

## Implementation Details

```python
@dataclass
class DebugBuffer:
    lines: List[str]

    def add(line: str) -> None
    def extend(items: List[str]) -> None
    def as_text() -> str          # Vollstaendige Console-Ausgabe
    def email_subset() -> str     # Subset fuer E-Mail
```

## Expected Behavior

- **Input:** Debug-Zeilen via add()/extend()
- **Output:** Formatierter Text via as_text()/email_subset()
- **Side effects:** Keine

## Known Limitations

- email_subset() gibt aktuell alles zurueck (TODO: Filterlogik)

## Changelog

- 2025-12-27: Initial spec created (migrated from existing code)
