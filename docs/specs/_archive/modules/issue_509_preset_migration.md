---
entity_id: issue_509_preset_migration
type: module
created: 2026-06-01
updated: 2026-06-01
status: draft
version: "1.0"
tags: [compare, presets, migration, scheduler]
---

# Issue #509: Preset-Migration + Doppelversand-Guard

## Approval

- [ ] Approved

## Purpose

Commit b8e34f0 (feat #490) hat die `/compare`-UI auf `compare_presets.json` umgestellt,
ohne Bestandsdaten aus `compare_subscriptions.json` zu migrieren. Zwei Probleme folgen:

1. **UI zeigt nichts** — presets.json fehlt für bestehende Nutzer (hotfix für `henning` bereits
   manuell erledigt).
2. **Doppelversand ab morgen 06:00** — presets-System sendet via `compare_presets_daily` (06:00),
   subscriptions-System sendet dieselben Vergleiche nochmals via `morning_subscriptions` (07:00),
   weil subscriptions.json-Einträge noch `enabled: true` sind.
3. **Leere `empfaenger`** — migrierte Presets ohne explizite `recipients` in subscriptions.json
   haben `empfaenger: []` und werden vom presets-System übersprungen → keine E-Mail.

## Source

- **Primär:** `api/routers/scheduler.py` (Python-Backend, FastAPI)
- **Datenmigration:** `data/users/*/compare_presets.json` (Laufzeitdaten, nicht git-tracked)
- **Kein Go-Code-Change nötig** — Go-API schreibt presets.json bereits korrekt

## Estimated Scope

- **LoC:** ~30
- **Files:** 1 Python-Datei + Datenmigration
- **Effort:** low

## Dependencies

- `api/routers/scheduler.py` → `_run_subscriptions_by_schedule`, `_run_compare_presets_daily`
- `src/app/config.py` → `Settings.mail_to` (Fallback-Empfänger)
- Datei-Konvention: `data/users/{user_id}/compare_presets.json` (Array), `compare_subscriptions.json` (wrapped)

## Acceptance Criteria

**AC-1:** Given ein User mit `compare_presets.json` (nicht leer) / When `morning_subscriptions`
oder `evening_subscriptions` ausgelöst wird / Then werden 0 Subscriptions verarbeitet und
kein Versand findet statt (Doppelversand verhindert).

**AC-2:** Given ein Preset mit `empfaenger: []` und `Settings.mail_to = "user@example.com"` /
When `compare_presets_daily` ausgelöst wird / Then wird die Mail an `settings.mail_to` gesendet
(kein Skip wegen leerem `empfaenger`).

**AC-3:** Given ein User mit `compare_subscriptions.json` aber OHNE `compare_presets.json` /
When `morning_subscriptions` ausgelöst wird / Then werden Subscriptions wie bisher verarbeitet
(keine Regression).

**AC-4:** Given User `admin` hat `compare_subscriptions.json` mit "Ski Tirol" (enabled=true) /
When die Datenmigration läuft / Then existiert `data/users/admin/compare_presets.json` mit
"Ski Tirol" (schedule=daily, empfaenger aus settings.mail_to oder leer).

**AC-5:** Given User `henning` hat bereits `compare_presets.json` /
When `compare_presets_daily` um 06:00 läuft / Then erhalten Mallorca, Zillertal, Heimat
je eine E-Mail (nicht doppelt via subscriptions um 07:00).

**AC-6:** Test-User (`__test_*`, `__bug89_*`) werden von der Migration NICHT angefasst
(ihre subscriptions.json-Daten sind Test-Fixtures).

## Implementation Plan

### Änderung 1: Doppelversand-Guard in `_run_subscriptions_by_schedule`

```python
# Früh im Funktionskörper, vor der Subscription-Schleife:
import json as _json
from pathlib import Path as _Path
preset_path = _Path("data") / "users" / user_id / "compare_presets.json"
if preset_path.exists():
    try:
        if _json.loads(preset_path.read_text()):
            logger.info("Presets-System aktiv für %s — subscriptions übersprungen", user_id)
            return 0
    except Exception:
        pass  # Korrupte presets.json: Fallback auf subscriptions
```

Gleiches Guard-Pattern in `_run_weekly_subscriptions`.

### Änderung 2: `mail_to`-Fallback in `_run_compare_presets_daily`

```python
# Statt:
if not empfaenger:
    logger.warning("Preset %s has no empfaenger — skipping", preset_id)
    continue

# Neu:
if not empfaenger:
    default_to = getattr(settings, "mail_to", None)
    if not default_to:
        logger.warning("Preset %s: keine empfaenger und kein mail_to — skip", preset_id)
        continue
    empfaenger = [default_to]
    logger.info("Preset %s: empfaenger leer, nutze mail_to=%s", preset_id, default_to)
```

### Datenmigration (einmalig)

Für alle User, bei denen gilt: `compare_subscriptions.json` existiert, `compare_presets.json`
fehlt, User-ID beginnt NICHT mit `__`:

- Mapping: `locations` → `location_ids`, `time_window_start/end` → `hour_from/to`,
  `activity_profile` → `profil`, `recipients` → `empfaenger`,
  `enabled=false` → `schedule: "manual"`, else `schedule: "daily"`,
  `last_run` → `letzter_versand`, `top_ort_letzter_versand` → gleich

Admin-User `admin` hat keine expliziten recipients → `empfaenger: []` (Fallback via mail_to greift).

## Out of Scope

- Bidirektionale Sync zwischen presets.json und subscriptions.json
- Wöchentliche Presets (weekly) — kein eigener Go-Scheduler-Job existiert dafür noch
- Löschen alter subscriptions.json-Einträge (bleiben als Backup erhalten)
