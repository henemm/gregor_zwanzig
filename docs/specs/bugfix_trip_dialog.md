---
entity_id: bugfix_trip_dialog
type: bugfix
created: 2025-12-28
updated: 2025-12-28
status: deprecated
version: "1.0"
tags: [bugfix, web-ui, trips]
---

# Bugfix: Trip Dialog Event Handler

> Abgelöst/entfernt durch ADR-0001 / #129 — die NiceGUI-UI unter `src/web/` wurde am 2026-05-15 ersatzlos entfernt; diese Spec ist nur noch historisch.

## Approval

- [x] Approved

## Problem

Trip-Dialog in der Web-UI wirft Fehler und resettet sich beim Editieren:
```
AttributeError: 'GenericEventArguments' object has no attribute 'value'
```

## Root Cause

NiceGUI's `on("change", callback)` übergibt `GenericEventArguments`, nicht den Wert direkt.
Die Lambda-Funktionen erwarten fälschlicherweise `e.value`.

## Betroffene Datei

- `src/web/pages/trips.py`

## Fix

Ersetze `on("change", lambda e: ...)` durch `bind_value()` oder direkten Zugriff:

**Vorher:**
```python
stage_name.on("change", lambda e, s=stage: s.update({"name": e.value}))
```

**Nachher:**
```python
stage_name.on("update:model-value", lambda e, s=stage: s.update({"name": e.args}))
```

Oder besser: Verwende `bind_value_to()` für reaktive Bindung.

## Changelog

- 2025-12-28: Bugfix spec created
