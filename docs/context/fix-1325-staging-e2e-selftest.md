# Kontext & Analyse: Staging-E2E-Selbsttest für Trip-Briefings kaputt (#1325)

**Workflow:** `fix-1325-staging-e2e-selftest` · **Typ:** Bug · **Erstellt:** 2026-07-20

## Problem (Nutzer-/Deploy-Sicht)

Der Staging-E2E-Selbsttest, der vor jedem Backend-/Full-Stack-Prod-Deploy eine echt
zugestellte Test-Briefing-Mail gegen Staging erzeugt, scheitert an ~5 von 7 Wochentagen
mit `422 {"detail":"Kein Briefing für … — keine Etappendaten für das aktuelle Datum"}`.
Da `briefing_mail_validator.py` diesen Lauf braucht, schreibt `staging_gate.py` kein
`VERIFIED` → Prod-Hard-Gate (#521) blockiert **jeden** Backend-Deploy.

`POST http://localhost:8001/api/scheduler/trips/staging-validator-rolling/send?user_id=validator-issue110&report_type={morning|evening}`

## Bewiesene Root Causes (bug-investigator, live gegen Port 8001 verifiziert)

Beide Defekte haben **dieselbe Wurzel**: der Test-Trip `staging-validator-rolling` rutscht
regelmäßig mit allen Etappen in die Vergangenheit.

### Defekt 1 — Refresh-Cron seit ~2026-07-13 kaputt (Rechte-Konflikt) — INFRA

- `crontab -l` (User `hem`): wöchentlich (Mo 05:00) `setup_staging_validator_trip.py`.
- Seit `.../users/validator-issue110/briefings/` am 2026-07-15 als `claude-gregor:claude-gregor`,
  Modus `2770` neu angelegt wurde, kann `hem` (nicht in Gruppe `claude-gregor`) nicht mehr
  hineinschreiben → `PermissionError` in `src/app/loader.py:1602` (`save_trip`).
  Beleg: `/home/hem/backups/setup-staging-validator-trip.log` (Traceback seit 07-13).
- Selbst bei funktionierendem Cron: wöchentlicher Lauf setzt nur Etappen `today+1`/`today+2`
  (`setup_staging_validator_trip.py:66-74`) → ab Do–So liegen beide in der Vergangenheit.
- **Roter Hering:** Die vom Issue-Autor editierte `data/.../trips/staging-validator-rolling.json`
  ist ein toter Legacy-Pfad (seit #1250 Scheibe 7a lesen weder `loader.py:1554-1557,373-378`
  noch `internal/store/trip.go:216` diesen Pfad — nur noch `briefings/`).
- **Zuständigkeit:** Server-Crontab + Rechte → Infra-Instanz (MQ). NICHT Teil dieses Code-Fixes.

### Defekt 2 — Test-Sendepfad akzeptiert stillschweigend vergangene Etappen — DIESES REPO

- `src/services/trip_report_scheduler.py:568-599` `select_test_stage`: fällt, wenn **alle**
  Etappen in der Vergangenheit liegen, auf die chronologisch **früheste** (älteste) zurück.
- Deren vergangenes Datum geht ungeklammert als `start_date` an Open-Meteo
  (`src/providers/openmeteo.py:860-870`, kein Clamp auf heute) → Forecast-Endpoint liefert
  für Vergangenheit nichts → alle Segmente `has_error=True` (#1113-Contract) → `error_ratio`
  ≥ `OUTAGE_WITHHOLD_RATIO` (0.75, Zeile 50) → `_send_trip_report_outcome` gibt `"no_weather"`
  zurück (`:781-802`) → `send_test_report`-Bool-Wrapper `False` (`:670`) →
  `api/routers/scheduler.py:202-206` mappt auf 422 mit **irreführender** „keine
  Etappendaten"-Meldung (tatsächlich: keine Wetterdaten für ein veraltetes Datum).
- **Live bewiesen:** Mit einer heutigen Etappe (2026-07-20) liefern beide report_types sofort
  `200 {"sent":true}` — der Sendepfad selbst ist gesund, nur die Datumswahl ist es nicht.

## Fix-Scope (dieses Repo)

Der Selbsttest muss **unabhängig von der Cron-Frische** funktionieren:

1. Im Test-Fallback-Pfad (`allow_test_fallback=True` / `send_test_report`) darf ein Etappen-
   Datum in der Vergangenheit den Wetter-Abruf nicht auf ein totes Vergangenheitsdatum
   schicken — es wird auf „heute" geklemmt, damit ein echter Forecast entsteht und eine echte
   Test-Mail versendet wird.
2. Sollte trotzdem kein Briefing möglich sein, muss der Fehler mit einer **ehrlichen,
   unterscheidbaren** Meldung/Outcome erscheinen (nicht das falsche „keine Etappendaten für
   das aktuelle Datum").

**Nicht im Scope (Infra, separat via MQ an `infra`):** Cron unter `claude-gregor` laufen
lassen, Kadenz täglich statt wöchentlich, Fehler-Alert auf den Cron-Log.

## Betroffene Dateien (Code)

- `src/services/trip_report_scheduler.py` — Test-Sendepfad (`select_test_stage`,
  `_send_trip_report_outcome`, Wetter-Abruf im Test-Fallback): Vergangenheits-Datum auf heute
  klemmen; genuines No-Weather als eigener, klar benannter Outcome.
- `api/routers/scheduler.py:202-206` — 422-Meldung differenzieren (No-Weather ≠ No-Stage).

## Test (Kern, deterministisch, netzfrei)

- Repro: Trip mit ausschließlich vergangenen Etappen → Test-Sendepfad. Vor Fix: `no_weather`/422.
  Nach Fix: Briefing wird erzeugt (`sent`), Wetter-Abruf gegen aufgezeichnetes Open-Meteo-Fixture
  für „heute" (Innsbruck). Kein Mock-Theater — echtes aufgezeichnetes Fixture.
- Zweiter Test: genuines No-Weather-Szenario → ehrliche, unterscheidbare Fehlermeldung/Outcome
  statt „keine Etappendaten für das aktuelle Datum".
