# Context: fix-1633-datenwurzel-diagnose-journale

**Issue:** [#1633](https://github.com/henemm/gregor_zwanzig/issues/1633) · Labels `bug`, `priority:critical`
**Track:** Standard (Intake-Score 1/6) · **Blockiert #1628**
**Erstellt:** 2026-08-09

## Request Summary

Vier fest verdrahtete, repo-relative `Path("data/…")`-Konstanten im Python-Kern haben den
Datenwurzel-Umzug nach `/var/lib/gregor` (#1595) nicht mitgemacht. Der Python-Kern schreibt
seine Diagnose-Journale seither in den Programmordner, die Go-API liest sie an der
Produktiv-Datenwurzel — dort eingefroren. Die Ausfallüberwachung meldet falsche Werte.

## Herkunft

Aufgefallen bei der Analyse zu #1628 (`docs/context/fix-1628-nowcast-fetch-fail-visibility.md`,
Abschnitt „Nebenbefund mit Vorrang"). Vom PO am 2026-08-09 vorgezogen, weil es #1628 blockiert.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/providers/call_log.py:21` | `DIAGNOSTICS_PATH` — MODIFY |
| `src/providers/openmeteo.py:78` | `DIAGNOSTICS_PATH` (zweite Konstante derselben Zieldatei) — MODIFY |
| `src/providers/openmeteo.py:204` | `AVAILABILITY_CACHE_PATH` (Cache, nicht Diagnose) — MODIFY |
| `src/services/official_alerts/warn_egress.py:100` | `WARN_CALLS_PATH` — MODIFY |
| `src/app/loader.py:1066-1085` | `get_data_root()` — die kanonische Auflösung |
| `internal/scheduler/briefing_health.go:211,277` | Go-Leser des Open-Meteo-Journals |
| `internal/scheduler/warn_service_health.go:270` | Go-Leser des Warn-Journals |
| `tests/tdd/test_repo_path_hardcoding_ratchet.py` | Vorbild für den Wächter aus AC-5 (AST-basiert) |

## Existing Patterns

- **Vorbild `ae0553b3` (#1595):** Modul-Konstante → Funktion, Auflösung **im Rumpf**. Ein
  Default-Argument oder ein Initialisierer würde beim Import gebunden, also vor jeder
  Testfixture, und hebelte `_DATA_ROOT` (#1133) aus.
- **Zustandstransfer Python → Go** läuft ausschließlich über Dateien im geteilten `DataDir`,
  nie über HTTP. Deshalb ist ein Pfad-Fehler hier gleichbedeutend mit einem toten Signal.
- **`get_data_root()`-Priorität:** `_DATA_ROOT` (Testfixture) > `GZ_DATA_DIR` > `data`.

## Dependencies

- **Upstream:** `app.loader.get_data_root()`
- **Downstream:** `briefing_health.go`, `warn_service_health.go` → `/api/scheduler/status` →
  externer Monitor `check-gregor20.sh` (in `henemm-infra`, nicht in diesem Repo)

## Existing Specs & ADRs

- **`docs/adr/0018-provider-fallback-ohne-kaschieren.md`** — Punkt 3 fordert das wachsende
  Health-Signal, das hier wirkungslos ist.
- `docs/specs/modules/fix_1633_datenwurzel_diagnose_journale.md` — diese Spec (freigegeben).

## Risks & Considerations

1. **Datenübernahme ist der heikelste Teil.** Append-only, nach Zeitstempel sortiert, kein
   Überschreiben; Quelldateien bis zur bestätigten Übernahme liegen lassen (reversibel).
2. **Dateirechte:** `/var/lib/gregor/diagnostics/` gehört `claude-gregor`, der Dienst läuft als
   `claude-gregor`. Vor dem Anhängen Schreibrecht prüfen — nicht als `hem` schreiben und dabei
   den Besitzer kippen (genau das war die Wurzel von #1595).
3. **Der Nachweis muss am Statusendpunkt erbracht werden** (AC-6), nicht am Schreibcode. Ein
   grüner Schreibtest hätte diesen Fehler nie gefunden.
4. **Zwei Konstanten für dieselbe Zieldatei** — eine Suche, die nach dem ersten Treffer aufhört,
   übersieht `openmeteo.py:78`.
5. **Kein Frontend-, kein Go-Anteil** — reiner Python-Core.
