# Context: gate-1148-prod-send-deny

Issue: #1148 — Gate: Claude-Sessions dürfen keine Send-Trigger gegen Prod auslösen (Baustein C aus #1147)

## Request Summary

Neuer projektlokaler PreToolUse:Bash-Hook, der Send-Trigger (POST auf Scheduler-/Send-Endpoints, direkte SMTP-Verbindungen zu smtp.resend.com) gegen das Produktivsystem default-deny blockiert. Staging und GET-Requests bleiben frei. Freigabe nur per vom User getipptem Override-Token (kurze TTL).

## WICHTIGER BEFUND: Port-Korrektur gegenüber Issue-Text

Issue #1148 (und #1147) nennen „localhost:8001" als Prod-Port — **das ist falsch**.
Verifiziert am 2026-07-09 gegen systemd-Units + Prod-Journal:

| Service | Prod | Staging |
|---|---|---|
| gregor-python (uvicorn) | **127.0.0.1:8000** | 127.0.0.1:8001 |
| gregor-api (Go) | **8090** (Default, kein GZ_PORT) | 8091 (`GZ_PORT=8091`) |
| Extern (nginx) | **gregor20.henemm.com** | staging.gregor20.henemm.com |

Journal-Beweis: Der Vorfalls-POST vom 2026-07-08 13:52 (`resendverify1122`) lief im Prozess `uv[713555]`, dessen Startzeile „Uvicorn running on http://127.0.0.1:**8000**" lautet — also Prod-Python auf 8000. Ein Block auf 8001 würde Staging lahmlegen und Prod offen lassen.

**Konsequenz:** Blockliste = `localhost/127.0.0.1:8000`, `:8090`, `gregor20.henemm.com` (negativ abgegrenzt gegen `staging.gregor20.henemm.com`). Erlaubt = `:8001`, `:8091`, `staging.gregor20.henemm.com`.

## Send-Endpoint-Inventar (vollständiger als Issue-Text)

Python-API (`api/routers/scheduler.py`, Prefix `/api/scheduler`):
- POST `/trip-reports` (Z. 31), `/alert-checks` (Z. 50), `/radar-alert-checks` (Z. 60)
- POST `/subscriptions/{id}/send` (Z. 109), `/trips/{id}/send` (Z. 179), `/compare-presets/{id}/send` (Z. 219)

Go-API (`internal/router/router.go`):
- POST `/api/subscriptions/{id}/send` (Z. 149), `/api/trips/{id}/send` (Z. 166), `/api/compare/presets/{id}/send` (Z. 186)
- POST `/api/scheduler/trip-reports` (Z. 202), `/api/scheduler/alert-checks` (Z. 205) — Proxies auf Python

Das Issue nennt nur eine Teilmenge; das Gate sollte generisch matchen: Pfad endet auf `/send` ODER `/api/scheduler/(trip-reports|alert-checks|radar-alert-checks)`.

SMTP: direkte Verbindungen zu `smtp.resend.com` (python/smtplib, openssl s_client, swaks, nc, curl smtp://). Achtung False-Positive-Falle: `grep smtp.resend.com src/` (Code-Suche) ist legitim — nur in Verbindung mit Verbindungs-Indikatoren blocken.

## Related Files

| Datei | Relevanz |
|---|---|
| `.claude/hooks/renderer_mail_gate.py` | Vorbild: projektlokaler PreToolUse:Bash-Hook (stdin-JSON, Exit 0/2, hook_utils via sys.path) |
| `.claude/hooks/hook_utils.py` (Projekt) | `get_tool_input()`, `block()`, `allow()` |
| `.claude/settings.json` | Registrierung: PreToolUse-Matcher „Bash" — neuer Eintrag neben renderer_mail_gate |
| Plugin `core/hooks/bash_gate.py` | Referenz für Pattern-Matching-Stil, `sh -c`/eval-Fallback (Obfuskations-Schutz) |
| Plugin `core/hooks/override_token.py` | Token-Datei `.claude/user_override_token.json` (v2, TTL 1h), `has_valid_token(workflow)` |
| Plugin `core/hooks/phase_listener.py` | User tippt „override"/„genehmige" → `create_token(workflow_name)` |

## Existing Patterns

- **Override-Mechanik:** User tippt wörtlich „override" → phase_listener (Plugin, UserPromptSubmit) legt Token in `.claude/user_override_token.json` an, TTL 1 h. Projekt-Hook kann dieselbe Datei mit eigenem kleinen Reader prüfen (kein Plugin-Import nötig — Format ist stabil dokumentiert). „Einmalig durchgelassen" aus dem Issue ≈ Token nach Verbrauch löschen oder kurze TTL; Design-Entscheidung für die Spec.
- **Fail-closed bei Obfuskation:** bash_gate fällt bei `sh -c`/`eval`/shlex-Fehlern auf Roh-String-Scan zurück — gleiches Muster übernehmen.
- **Registrierung:** settings.json `PreToolUse` → matcher `Bash` → command mit `${CLAUDE_PROJECT_DIR}`.

## Dependencies

- Upstream: `.claude/user_override_token.json` (Erzeugung durch Plugin-phase_listener), stdin-Hook-Protokoll von Claude Code.
- Downstream: JEDER Bash-Aufruf jeder Session in diesem Repo läuft durch den Hook → False Positives blockieren legitime Arbeit (Staging-E2E, Alert-Preview-Proben auf 8001/8000-GET, Code-Suche nach „smtp.resend.com").

## Risks & Considerations

1. **Falsch-negativ = Prod-Send-Leck** (der eigentliche Zweck). Variablen-Obfuskation (`P=8000; curl :$P/...`) ist prinzipiell nicht vollständig fangbar — Roh-String-Scan als konservative Basis, dokumentierte Restlücke.
2. **Falsch-positiv = Arbeitsblockade** in allen Sessions. GET auf Status/Health gegen Prod muss durchgehen; Staging-Sends (Port 8001/8091, staging.gregor20) müssen durchgehen; `grep`/Doku-Erwähnungen von Endpoints/smtp.resend.com müssen durchgehen.
3. **Hook-Datei selbst ist edit_gate-geschützt** (`.claude/hooks/*.py` = Infrastruktur) → Implementierung braucht vom User getipptes „override" (Projektregel: Validator-/Hook-Änderungen im eigenen Workflow — dieser hier).
4. **Tests:** Hook ist als Doku-/Tooling-Artefakt testbar (stdin-JSON rein, Exit-Code raus) — `# doc-compliance-test`-Ausnahme greift, kein Mock-Verbot verletzt.
5. Issue-Testschritt 1 nennt Port 8001 als Block-Fall — muss wegen Port-Korrektur auf 8000 umformuliert werden (8001 ist der DURCHLASS-Fall).
