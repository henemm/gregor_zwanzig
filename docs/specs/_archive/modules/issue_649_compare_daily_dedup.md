---
entity_id: issue_649_compare_daily_dedup
type: module
created: 2026-06-07
updated: 2026-06-07
status: draft
version: "1.0"
tags: [rework, compare, scheduler, dry]
---

# Issue #649 — Compare-Daily-Loop Versand-Dedup

## Approval

- [x] Approved

## Purpose

Die tägliche Compare-Briefing-Schleife (`_run_compare_presets_daily`) trägt eine Kopie der Versand-Logik, die seit #627 bereits als gemeinsamer Helper `_send_one_compare_preset()` existiert. Diese Spec stellt die Daily-Loop auf den Helper um, sodass beide Versand-Pfade (Daily + On-Demand) identische Logik teilen — ohne das Versand-Verhalten zu ändern.

## Source

- **File:** `api/routers/scheduler.py`
- **Identifier:** `_run_compare_presets_daily()` (Loop), `_send_one_compare_preset()` (gemeinsamer Helper)

Schicht: **Python-Backend** (FastAPI-Router, `api/routers/scheduler.py`).

## Estimated Scope

- **LoC:** ~ −35 netto (Duplikat + ungenutzte Imports entfernen, kleine try/except-Wrapper-Logik hinzu)
- **Files:** 1 Produktiv (`api/routers/scheduler.py`) + 1 Test
- **Effort:** low

## Dependencies

- `_send_one_compare_preset()` — bestehender Helper, akzeptiert `all_locations_cache`-Parameter und wirft `ValueError` bei fehlendem Empfänger / nicht auflösbaren Orten.
- `_save_preset_status()` — wird vom Helper aufgerufen (Status-Persistenz, RMW).
- `load_all_locations()`, `Settings().with_user_profile()` — bleiben in der Loop.

## Acceptance Criteria

**AC-1:** Given die Daily-Loop `_run_compare_presets_daily()` verarbeitet ein fälliges Preset, When der Versand ausgeführt wird, Then ruft sie dafür `_send_one_compare_preset()` auf und enthält **keine** eigene Inline-Versand-Logik mehr (kein direkter `EmailOutput().send()`-, `render_compare_html()`- oder `ComparisonEngine.run()`-Aufruf im Loop-Körper).

**AC-2:** Given ein gültiges daily-Preset mit Empfänger und auflösbaren Orten, When die Daily-Loop läuft, Then ist das versendete Briefing bit-identisch zum bisherigen Verhalten (gleiches Subject `Wetter-Vergleich: <name> (<datum>)`, gleicher HTML-Body, gleicher Text-Body, gleiche Empfänger) und `_save_preset_status()` wird mit demselben `top_ort` aufgerufen — nachgewiesen über einen Pipeline-Test, der den `EmailOutput.send`-Aufruf abfängt und Argumente prüft.

**AC-3:** Given mehrere daily-Presets, von denen eines fehlschlägt (z. B. nicht auflösbare Orte), When die Daily-Loop läuft, Then stoppt der Fehler die übrigen Presets nicht und der zurückgegebene `success_count` zählt nur die erfolgreich versendeten Presets (heutiges fail-soft-Verhalten erhalten).

**AC-4:** Given die Schedule-Filterung (`daily` verarbeiten, `weekly` nur am passenden Wochentag, `manual`/unbekannt still überspringen), When die Daily-Loop läuft, Then bleibt diese Filterung unverändert in der Loop erhalten und ein `manual`-Preset erzeugt weiterhin keinen Log-Eintrag.

**AC-5:** Given ein daily-Preset ohne Empfänger und ohne `mail_to`-Fallback, When die Daily-Loop läuft, Then wird das Preset übersprungen (`continue`, nicht abgebrochen) und der `success_count` nicht erhöht — das heutige Skip-Verhalten bleibt erhalten (die vom Helper geworfene `ValueError` wird gefangen).

**AC-6:** Given ein authentifizierter Mehrtenant-Kontext, When die Daily-Loop ein Preset versendet, Then wird die echte `user_id` an `_send_one_compare_preset()` durchgereicht (kein `"default"`-Fallback im aktiven Versand-Pfad).

## Out of Scope

- Änderungen am On-Demand-Pfad (`_send_compare_preset`) oder am Helper selbst (außer er bräuchte einen Parameter — aktuell nicht nötig).
- Änderungen am Versand-Format, an Subject/Render/Empfänger-Auflösung.
- Änderungen an der Schedule-/Weekly-Logik.

## Test Strategy

- **Bit-Identität (AC-2):** Pipeline-Test, der `EmailOutput.send` abfängt (in-process, kein Netzwerk) und Subject/HTML/Text/Empfänger gegen den erwarteten Wert prüft — reale `ComparisonEngine`-Ausführung mit Test-Locations, keine Mocks der Geschäftslogik.
- **Fail-soft (AC-3) + Skip (AC-5):** reale `_run_compare_presets_daily()`-Aufrufe mit tmp_path-Presets, Assertion auf `success_count` + caplog.
- **Schedule-Filter (AC-4):** bestehende Tests in `test_issue_461_compare_preset_dispatch.py` + `test_issue_511_weekly_scheduler.py` müssen grün bleiben.
- **Regression:** vollständige bestehende Compare-Dispatch-Test-Suite grün.
