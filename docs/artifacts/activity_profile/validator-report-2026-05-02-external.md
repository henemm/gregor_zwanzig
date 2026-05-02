---
role: external-validator
spec: docs/specs/modules/activity_profile.md
date: 2026-05-02T07:55:00+02:00
server: https://gregor20.henemm.com
verdict: AMBIGUOUS
---

# External Validator Report — ActivityProfile Harmonisierung

**Spec:** docs/specs/modules/activity_profile.md
**Datum:** 2026-05-02T07:55:00+02:00 (Europe/Vienna)
**Server:** https://gregor20.henemm.com

## Methodik

Strikte Isolation eingehalten:
- `src/` nicht gelesen
- `docs/artifacts/` nicht gelesen (nur dieser neue Report dort geschrieben — bestehende Dateien wurden NICHT angefasst, um Implementer-Spuren nicht zu kontaminieren)
- `git log`/`git diff` nicht gelesen
- `.claude/workflow_state.json` nicht gelesen
- Inputs ausschließlich: Spec-Datei + laufende App + Verifikations-Skript

## Vorbemerkung — Testbarkeitsgrenze dieser Spec

Die Spec ist ein **reiner Code-Refactor** (Enum-Konsolidierung). Die Akzeptanzkriterien §A1, §A2, §A3, §A4 sind Code-Level-Checks (`grep -rn "class ActivityProfile" src`, `uv run pytest`), die per Validator-Rolle verboten sind ("Du darfst NICHT in `src/` lesen"). Diese Punkte gehören in die Implementer-/CI-Phase, nicht in die externe Validierung.

Als externer Validator kann ich nur das prüfen, was sich am laufenden System (Endpoints, UI, Verifikations-Skript) zeigt. Ohne Test-Credentials sind alle authentifizierten Endpoints und alle UI-Pfade nicht direkt prüfbar.

## Checklist

| # | Akzeptanzkriterium | Beweis | Verdict |
|---|--------------------|--------|---------|
| §A1 | Genau ein `class ActivityProfile` in `src/` | Code-Grep verboten für Validator | UNKLAR (out of scope) |
| §A2 | Alle 4 Werte vorhanden, kein `CUSTOM` | Kein Introspect-Endpoint ohne Auth erreichbar | UNKLAR |
| §A3 | `LocationActivityProfile` aus src+tests entfernt | Code-Grep verboten für Validator | UNKLAR (out of scope) |
| §A4 | `uv run pytest` grün | Test-Run berührt src/, verboten | UNKLAR (out of scope) |
| §A5 | `verify_activity_profile_migration.py` Exit 0 | Script-Run-Output: `OK: 457 Dateien gescannt, 10 Profile-Werte alle gueltig` — Exit 0 | **PASS** |
| §A6 (1/2) | API akzeptiert `activity_profile: "summer_trekking"` | POST `/api/compare/subscriptions` ohne Auth → HTTP 401 (Auth fired before Validation) | UNKLAR |
| §A6 (2/2) | API lehnt `activity_profile: "custom"` mit 400 ab | POST `/api/compare/subscriptions` mit `{"activity_profile":"custom"}` ohne Auth → HTTP 401 (kein 400 erreichbar) | UNKLAR |
| §A7 (1/2) | GPX-Upload nutzt `SUMMER_TREKKING` und funktioniert | UI hinter `/login`, keine Test-Credentials zur Verfügung | UNKLAR |
| §A7 (2/2) | Compare-Scoring dispatcht für wintersport/wandern/allgemein | UI hinter `/login`, keine Test-Credentials | UNKLAR |
| Server-Health | App läuft post-deploy | `GET /api/health` → 200 `{"python_core":"ok","status":"ok","version":"0.1.0"}` | **PASS** |
| Scheduler | Hintergrund-Jobs laufen weiter | `GET /api/scheduler/status` → alle 5 Jobs `status:"ok"`, frische `last_run`-Timestamps | **PASS** |

## Findings

### F1 — §A5 Verifikations-Skript bestanden
- **Severity:** —
- **Expected:** Exit 0, alle persistierten Werte ∈ {wintersport, wandern, summer_trekking, allgemein, None/absent}
- **Actual:** `OK: 457 Dateien gescannt, 10 Profile-Werte alle gueltig` — Exit 0
- **Evidence-Befehl:** `uv run python3 scripts/verify_activity_profile_migration.py`

### F2 — Server läuft, Scheduler intakt
- **Severity:** —
- **Expected:** Migration bricht den Service nicht
- **Actual:** `/api/health` 200, alle 5 Scheduler-Jobs (`inbound_command_poll`, `alert_checks`, `trip_reports_hourly`, `evening_subscriptions`, `morning_subscriptions`) mit `status:"ok"` und plausiblen `last_run`-Zeiten (alle innerhalb der letzten Stunde bzw. ihres Intervalls)
- **Evidence-Befehl:** `curl https://gregor20.henemm.com/api/scheduler/status`

### F3 — §A6 nicht extern verifizierbar (BLOCKER für externe Validierung)
- **Severity:** HIGH (Methodenproblem, KEINE Implementierungsaussage — sagt nicht "kaputt", sondern "von außen nicht prüfbar")
- **Expected:** Spec verlangt API akzeptiert `summer_trekking`, lehnt `custom` mit 400 ab
- **Actual:** Alle Probes auf `/api/compare/subscriptions`, `/api/subscriptions`, `/api/profiles` etc. liefern **401 vor Validation**. Auth-Middleware feuert vor Body-Validation — der Validations-Code-Pfad ist ohne Credentials nicht erreichbar.
- **Evidence:**
  ```
  POST /api/compare/subscriptions {"activity_profile":"custom"}          → HTTP 401 {"error":"unauthorized"}
  POST /api/compare/subscriptions {"activity_profile":"summer_trekking"} → HTTP 401
  POST /api/compare/subscriptions {"activity_profile":"wandern"}         → HTTP 401
  POST /api/compare/subscriptions {"activity_profile":"allgemein"}       → HTTP 401
  POST /api/compare/subscriptions (kein Body)                            → HTTP 401
  POST /api/compare/subscriptions (malformed JSON)                       → HTTP 401
  ```
- **Konsequenz:** §A6 muss entweder durch Implementer mit Test-User-Token belegt werden, oder die Spec muss einen unauthentifizierten Validations-Endpoint definieren.

### F4 — §A7 nicht extern verifizierbar (BLOCKER)
- **Severity:** HIGH (Methodenproblem)
- **Expected:** GPX-Upload + Compare-Scoring funktionieren nach Migration
- **Actual:** `/compare`, `/locations`, `/py`, `/nicegui`, `/ui`, `/admin` → alle 302 → `/login`. Keine Möglichkeit ohne Credentials, die UI-Pfade zu betreten oder einen GPX-Upload durchzuführen.
- **Evidence:** `curl -sIL https://gregor20.henemm.com/<path>` liefert für jeden geprüften Pfad Login-Redirect.

### F5 — §A1, §A2, §A3, §A4 sind keine externen Validator-Kriterien
- **Severity:** MEDIUM (Spec-Methodik)
- **Beobachtung:** §A1/§A3 verlangen `grep -rn` auf `src/`, §A4 verlangt `uv run pytest`. Beide setzen Source-Zugriff voraus, der dem External Validator per Definition (`.claude/agents/external-validator.md` Zeilen 11, 24) verboten ist.
- **Empfehlung:** Diese Kriterien gehören in die Implementer-Phase / CI-Run, nicht in die External Validation. In diesem Report als "out of scope" markiert.

## Verdict: AMBIGUOUS

### Begründung

**Positive Befunde mit Evidenz:**
- §A5 (Verifikations-Skript) **PASS**: 457 Dateien, 10 valide Werte, Exit 0.
- Server-Health & Scheduler **PASS**: Migration hat keinen sichtbaren Service-Bruch verursacht; alle Jobs laufen mit frischen `last_run`-Timestamps und `status:"ok"`.

**Nicht verifizierbar (UNKLAR — ohne Auth-Zugang):**
- §A6 (Go-API-Validation für `summer_trekking` vs. `custom`)
- §A7 (GPX-Upload + Compare-Scoring im Frontend)

**Out of scope für External Validator (gehört in Implementer-/CI-Phase):**
- §A1, §A2, §A3, §A4 (Code-Level-Checks)

Da kein Akzeptanzkriterium nachweislich BROKEN ist, aber zentrale extern verifizierbare Punkte (§A6, §A7) mangels Auth-Zugang **nicht prüfbar** sind und der Validator-Regel "Funktioniert wahrscheinlich = FAIL / Kein Beweis = FAIL" folgt, ist das Verdict **AMBIGUOUS** (weder VERIFIED noch BROKEN).

### Empfohlene Folgeschritte

1. **Test-User bereitstellen:** Ohne Test-Credentials bleibt jede künftige External Validation am gleichen Auth-Wall stehen. Empfehlung: dedizierter `validator@henemm.com`-Account oder kurzlebiges Service-Token.
2. **Spec-Sektion „External-Validator-Kriterien" einführen:** §A1, §A3, §A4 als „Implementer/CI" markieren; §A5, §A6, §A7 als „External Validator". Saubere Trennung verhindert das aktuelle Methodenproblem.
3. **Optional: Public Read-Endpoint** `GET /api/profiles` (liefert die Go-Whitelist als JSON-Array). Damit wird Whitelist-Drift extern detektierbar (Diff Endpoint-Response ↔ Spec-§4.1) — adressiert direkt Risiko **R2** der Spec.
