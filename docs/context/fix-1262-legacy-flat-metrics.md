# Context: fix-1262-legacy-flat-metrics

## Request Summary
Ein Trip, dessen `display_config.metrics` als **Legacy-Flach-String-Liste**
(`["temperature", "wind_speed"]`) statt als Liste von MetricConfig-Dicts
gespeichert ist, crasht beim Laden in `_parse_display_config`. Der Scheduler
fängt den Fehler pro Trip nur mit `logger.error` ab → der Trip wird **still
übersprungen**, es gehen **keine Briefings und keine Alarme** raus. [triage:a]

## Root Cause
`src/app/loader.py:_parse_display_config` nimmt an, jeder `metrics`-Eintrag sei
ein dict:
- Zeile 707: `active_ids = [mc["metric_id"] for mc in raw_metrics if mc.get("enabled", True)]`
  → `str` hat kein `.get()` → `AttributeError`.
- Zeile 713: `mid = mc_data["metric_id"]` → `str["metric_id"]` → `TypeError`.

Der Fehler propagiert aus `load_trip` heraus. Im Scheduler
(`src/services/trip_report_scheduler.py:178`) wird pro Trip
`except Exception as e: logger.error(...)` gefangen — Zustellung bleibt aus,
ohne dass es dem Nutzer sichtbar wird.

## Related Files
| File | Relevance |
|------|-----------|
| `src/app/loader.py:693-826` (`_parse_display_config`) | Crash-Stelle; hier muss Flach-String → dict normalisiert werden |
| `src/app/loader.py:668` (`_normalize_legacy_mode`) | Präzedenz: pro-Metrik-Legacy-Normalisierung |
| `src/app/loader.py:846-885` (`_migrate_weather_config`) | Migriert `TripWeatherConfig.enabled_metrics` (Flach-String-Liste!) → MetricConfig — genau die Legacy-Form, die hier direkt in `display_config.metrics` landen kann |
| `src/app/models.py:496-521` (`MetricConfig`) | Zielstruktur; nur `metric_id` ist pflicht, alle anderen Felder haben Defaults |
| `src/services/trip_report_scheduler.py:170-181` | Swallow-Punkt (logger.error, keine Nutzer-Sichtbarkeit) |
| `src/services/trip_alert.py:204,271` | Alarm-Pfad liest `trip.display_config` — dieselbe geladene Config, also ebenfalls betroffen |
| `scripts/migrate_1244_null_lists.py` | Vorbild: Loader-Self-Heal + optionales Migrations-Skript, tar.gz-Backup, `_TRIP_LIST_FIELDS` enthält bereits `metrics` |

## Existing Patterns
- **Fail-soft im Loader (#1244):** `data.get("metrics") or []`, `data["display_config"] or {}` — Loader heilt beim Lesen, on-disk-Datei bleibt bis zum nächsten Save kaputt.
- **Legacy-Normalisierung pro Eintrag:** `_normalize_legacy_mode` normalisiert veraltete Felder innerhalb eines Metrik-dicts. Analog kann eine Vor-Schleifen-Normalisierung Strings → `{"metric_id": s}` wrappen.
- **Migrations-Skript-Muster:** Dry-Run-Default, `--execute`, `--root`, tar.gz-Backup, Read-Modify-Write (BUG-DATALOSS-GR221).

## Dependencies
- **Upstream:** `_parse_display_config` liest aus geladenem Trip-JSON (`data["display_config"]["metrics"]`).
- **Downstream:** Alles, was `trip.display_config.metrics` nutzt — Briefing-Renderer (`trip_report.py`), Scheduler (`trip_report_scheduler.py`), Alarm-Engine (`trip_alert.py`), Preview (`preview_service.py`).

## Existing Specs
- `docs/specs/modules/weather_config.md` v2.0 — UnifiedWeatherDisplayConfig
- `docs/specs/modules/fix_1244_null_list_fields.md` — Fail-soft-Loader + Migrations-Vorbild

## Risks & Considerations
- **Regressionsgefahr:** `_parse_display_config` läuft für **jeden** Trip-Load. Normalisierung muss den bestehenden dict-Pfad bit-identisch lassen (Roundtrip-Tests).
- **Stille vs. laute Fehler:** Reine Loader-Heilung macht den Trip wieder zustellbar. Zu prüfen: soll der Scheduler-Swallow (`logger.error`) zusätzlich lauter werden (z.B. MQ/Heartbeat), damit künftige Lade-Crashes nicht wieder unsichtbar bleiben? — Für die Spec-Phase.
- **Bestandsdaten:** Loader-Heal reicht für Zustellung; on-disk-Datei bleibt Flach-String bis zum nächsten Save. Optionales Migrations-Skript analog #1244 klärt die Persistenz (Spec-Entscheid).
- **Nachweis:** Repro-Test muss aus **Nutzersicht** zeigen: Trip mit Flach-String-`metrics` → vorher keine Zustellung (rot), nachher Zustellung (grün).

## Analysis

### Type
Bug (Datenintegritäts-Regression beim Laden → stille Nicht-Zustellung).

### Präziser Swallow-Punkt (bestätigt)
`load_all_trips` (`src/app/loader.py:1287-1295`) fängt **jede** Exception pro
Trip-Datei ab: `logger.error("Skipping corrupt trip %s: %s", ...)` + `continue`.
Der Trip mit Flach-String-`metrics` crasht in `load_trip → _parse_display_config`
und wird damit **komplett aus der geladenen Trip-Liste entfernt**. Diese Liste
speist **beide** betroffenen Pfade:
- Briefing-Scheduler (`trip_report_scheduler._get_active_trips` → `load_all_trips`)
- Alarm-Engine (liest denselben Trip-Bestand)

→ **Ein Fixpunkt, beide Symptome** (keine Briefings, keine Alarme).
Der Kommentar in Zeile 1290 (#1244 AC-6) erkennt bereits an: „ein unladbarer
Trip ist ein Datenintegritätsproblem" — trotzdem bleibt es bei einer stillen
Log-Zeile. Genau das ist die Kern-Ursache des „4 Tage niemand hat's gemerkt".

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/app/loader.py` (`_parse_display_config`) | MODIFY | Legacy-Flach-String-Einträge in `metrics` (und channel/per-report-Layouts) vor der Schleife zu `{"metric_id": s}` normalisieren. **Kern-Fix.** |
| `src/services/trip_report_scheduler.py` | MODIFY | Sichtbarkeit: Anzahl übersprungener/kaputter Trips im Scheduler-Lauf erfassen und über `/api/scheduler/status` + eine deduplizierte MQ-Meldung an `infra` sichtbar machen (User-Wunsch „Scheduler lauter machen"). |
| `scripts/migrate_1262_flat_metrics.py` | CREATE | Bestandsdaten in `briefings/*.json` (kind≠vergleich): Flach-String-`display_config.metrics` → dict-Liste umschreiben. Vorbild #1244: Dry-Run-Default, `--execute`, `--root`, tar.gz-Backup, Read-Modify-Write. |
| `tests/tdd/…` (Repro) | CREATE | Nutzersicht-Test: Flach-String-Trip → Zustellung (rot vor Fix). Roundtrip: dict-Config bit-identisch. |

### Scope Assessment
- Files: 3 Code + 1 Test + Migration
- Estimated LoC: Loader ~10, Scheduler-Observability ~20, Migration ~80 (zählt), Test ~40
- Risk Level: **LOW-MEDIUM** — Loader läuft für jeden Trip-Load; Normalisierung muss den dict-Pfad bit-identisch lassen.

### Technical Approach (Empfehlung)
1. **Loader-Selbstheilung** (zentral): Helper `_coerce_metric_entry(entry)` — `str` → `{"metric_id": entry, "enabled": True}`, dict unverändert. Einmal auf `raw_metrics` anwenden (vor Zeile 707), Helper in channel/per-report-Schleifen wiederverwenden. Macht den Trip wieder ladbar → beide Pfade geheilt.
2. **Observability**: Scheduler erfasst pro Lauf „N kaputte Trips übersprungen", surft es im Status-Endpoint (`last_run`-Analog) und feuert **einmalig/dedupliziert** eine MQ-`high` an `infra`. Kein Ping-Spam pro Tick.
3. **Migration** (User-Wunsch): idempotentes Skript nach #1244-Vorbild, Ziel `briefings/*.json`, Backup vor Schreiben.

### Open Questions
- [ ] Observability-Mechanismus final: MQ-Meldung **und** Status-Endpoint-Counter, oder reicht der Status-Counter? → in Spec als AC pinnen, dem PO zur Freigabe vorlegen.
- [ ] Migration: Dry-Run-Default + `--execute` bestätigt (kein Auto-Run im Deploy ohne Freigabe).
