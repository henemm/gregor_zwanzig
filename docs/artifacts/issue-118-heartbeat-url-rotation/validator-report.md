# External Validator Report

**Spec:** docs/specs/bugfix/heartbeat_url_rotation.md
**Datum:** 2026-05-04T08:55:00+02:00
**Server:** https://staging.gregor20.henemm.com
**Validator:** External (unabhängige Session, keine Implementierer-Artefakte gelesen)

## Vorgehen

- Spec-Pfad: `docs/specs/bugfix/heartbeat_url_rotation.md` (Issue #118)
- Auth-Cookie für /api/* erhalten und verwendet
- Reine Black-Box-Validierung: Spec, laufende Staging-App, ausgeführte Tests
- `src/`-Quellen nicht inhaltlich gelesen (nur über Grep auf Konstanten-Muster geprüft)
- `docs/artifacts/`-Inhalte nicht gelesen (nur Existenz getrackter Dateien zur Kenntnis genommen)

## Checklist (Acceptance Criteria aus der Spec)

| # | Expected Behavior | Beweis | Verdict |
|---|-------------------|--------|---------|
| 1 | `git ls-files \| xargs grep -lE "uptime\.betterstack\.com/api/v1/heartbeat/[A-Za-z0-9]{20,}"` findet **0 Dateien** | Verbatim ausgeführt → exit 123 (no match), 0 Treffer | PASS |
| 2 | `internal/config/config.go`: Defaults für `HeartbeatMorning`/`HeartbeatEvening` sind `""` | `Read internal/config/config.go` Z.19/20: `default:""` für beide Felder | PASS |
| 3 | `src/web/scheduler.py`: `HEARTBEAT_MORNING`/`HEARTBEAT_EVENING` via `os.getenv(..., "")` | Grep auf Datei: `Z.41 HEARTBEAT_MORNING = os.getenv("GZ_HEARTBEAT_MORNING", "")`, `Z.42 HEARTBEAT_EVENING = os.getenv("GZ_HEARTBEAT_EVENING", "")` | PASS |
| 4 | `internal/notify/mq.go` existiert, `SendMQ` exportiert | Glob-Treffer; Go-Tests verwenden `notify.SendMQ` und sind grün (siehe #8) | PASS |
| 5 | `src/lib/mq_notify.py` existiert, `send_mq` exportiert, fail-soft ohne `CLAUDE_MQ_SECRET` | Glob-Treffer; Python-Test `test_send_mq_function_exists` grün; `test_ping_heartbeat_empty_url_calls_send_mq` ruft `send_mq` als Modul-Attribut auf — beweist Existenz und Aufruf-Pfad | PASS |
| 6 | `tests/tdd/test_betterstack_heartbeat.py`: Pattern-Asserts statt exakte URL | Read der Test-Datei: regex `^https://uptime\.betterstack\.com/api/v1/heartbeat/[A-Za-z0-9_]+$`, Asserts `== "" or pattern.match(...)`, keine konkreten Token | PASS |
| 7 | Neue Tests `test_ping_heartbeat_empty_url_*` grün (Python) | `uv run pytest tests/tdd/test_betterstack_heartbeat.py -v` → 9 passed (inkl. `test_ping_heartbeat_accepts_job_name_param`, `test_ping_heartbeat_empty_url_calls_send_mq`) | PASS |
| 8 | Neue Go-Tests `TestPingHeartbeat_EmptyURL_*` grün | `go test ./internal/scheduler/... -run TestPingHeartbeat -v` → 6/6 PASS, davon `TestPingHeartbeat_EmptyURL`, `TestPingHeartbeat_EmptyURL_TriggersNotifier`, `TestPingHeartbeat_EmptyURL_OnlyOncePerJob`, `TestPingHeartbeat_EmptyURL_DifferentJobsSeparate` | PASS |
| 9 | `docs/specs/modules/betterstack_heartbeat.md`: keine Klartext-URLs | Read Datei: nur `<HEARTBEAT_MORNING_TOKEN>` / `<HEARTBEAT_EVENING_TOKEN>`-Platzhalter | PASS |
| 10 | `docs/specs/modules/go_scheduler.md`: keine Klartext-URLs | Read Datei: kein 20+stelliges Token; Defaults dokumentiert als `default:""` | PASS |
| 11 | `CLAUDE.md` (Abschnitt „Monitoring") korrigiert | Grep CLAUDE.md Z.306: „Der interne Heartbeat-Ping vom Scheduler an BetterStack ist optional — wenn `GZ_HEARTBEAT_MORNING`/`GZ_HEARTBEAT_EVENING` ENV-Variablen leer sind, wird kein Heartbeat gesendet (fail-soft). In dem Fall geht beim ersten Job-Lauf einmalig pro Prozess eine MQ-Nachricht an `infra` raus." Alte Falschaussage „Heartbeats wurden entfernt" nicht mehr vorhanden | PASS |
| 12 | Live: Staging-Service erreichbar, Scheduler läuft | `curl /api/health` → HTTP 200; `/api/scheduler/status` listet 5 Jobs inkl. `morning_subscriptions`, `evening_subscriptions` mit `running:true`, `timezone:Europe/Vienna` | PASS |
| 13 | Live-Verifikation: Service mit gesetzter ENV → BetterStack-Heartbeat nach 07:00/18:00 sichtbar | Aktuelle Uhrzeit 08:55 Wien; `morning_subscriptions.last_run = null` weil Service-Restart heute nach 07:00 (`inbound_command_poll.last_run = 08:50:00`); nächster Evening-Trigger erst 18:00. BetterStack-Dashboard außerhalb Validator-Scope. Code-Pfad strukturell durch Go-Test `TestPingHeartbeat_Success` (Mock-HTTP-Server, 200) und `TestPingHeartbeat_Failure` bewiesen. | UNKLAR |
| 14 | Live-Verifikation: leere ENV → MQ erreicht `infra`, kein Crash | claude-mq-DB außerhalb Validator-Scope. Code-Pfad bewiesen durch Go-Tests (`TestPingHeartbeat_EmptyURL_TriggersNotifier`, `_OnlyOncePerJob`, `_DifferentJobsSeparate`) und Python-Test `test_ping_heartbeat_empty_url_calls_send_mq` | UNKLAR |
| 15 | BetterStack-Dashboard: alte URLs gelöscht, neue aktiv | Spec selbst markiert Rotation als „Bewusst NICHT im Scope" (User-Aktion außerhalb Code) | N/A |

## Findings

### Finding 1: Security-Kernziel erreicht
- **Severity:** —
- **Expected:** 0 getrackte Dateien mit BetterStack-Heartbeat-URL-Token (≥20 Chars Alphanumerik)
- **Actual:** Verbatim-Acceptance-Test der Spec (Z.446) ergibt 0 Treffer (exit 123)
- **Evidence:** `git ls-files | xargs grep -lE "uptime\.betterstack\.com/api/v1/heartbeat/[A-Za-z0-9]{20,}"` → leer
- **Hinweis:** Der breitere Filter ohne Token-Längen-Kriterium liefert Treffer in `docs/specs/bugfix/heartbeat_url_rotation.md` (selbsterklärend — die Spec dokumentiert den BROKEN-Vorzustand mit Platzhaltern `<MORNING_TOKEN>`/`<EVENING_TOKEN>`) und `docs/specs/modules/betterstack_heartbeat.md` (`<HEARTBEAT_MORNING_TOKEN>` / `<HEARTBEAT_EVENING_TOKEN>`). Keiner enthält ein echtes Token. Spec-Acceptance ist erfüllt.

### Finding 2: Test-Suite vollständig grün
- **Severity:** —
- **Expected:** Python- und Go-Tests grün, neue Empty-URL-Tests vorhanden
- **Actual:** 9/9 Python-Tests, 6/6 Go-Tests
- **Evidence:**
  - Python: `tests/tdd/test_betterstack_heartbeat.py .........  [100%] 9 passed`
  - Go: `=== RUN TestPingHeartbeat_Success / _Failure / _EmptyURL / _TriggersNotifier / _OnlyOncePerJob / _DifferentJobsSeparate; PASS; ok internal/scheduler 0.009s`

### Finding 3: Live-Beobachtung BetterStack nicht in Validator-Scope
- **Severity:** LOW (kein Blocker)
- **Expected:** Heartbeat im BetterStack-Dashboard sichtbar nach Cron-Trigger
- **Actual:** Validator hat keinen Dashboard-Zugriff. Nächster Cron-Trigger Evening 18:00 Wien (~9 h Wartezeit). Morning ist heute bereits gelaufen, aber `last_run = null` deutet auf Service-Restart nach 07:00 — also kein Beweis-Lauf in der aktuellen Prozess-Instanz möglich.
- **Evidence:** `/api/scheduler/status` JSON
- **Bewertung:** Funktion strukturell durch Mock-Tests bewiesen. User kann ab 18:00 manuell im BetterStack-Dashboard verifizieren — Teil von Migrations-Sequenz Schritt 4-5 in der Spec.

### Finding 4: Live-Beobachtung MQ-Auslieferung nicht in Validator-Scope
- **Severity:** LOW (kein Blocker)
- **Expected:** MQ-Nachricht erreicht `infra` bei leerer ENV
- **Actual:** Lesezugriff auf `/home/hem/claude-mq/messages.db` außerhalb des Staging-API-Scopes
- **Evidence:** Code-Pfad funktional bewiesen — Go-Test `_TriggersNotifier` zeigt Notifier-Aufruf bei `url == ""`, `_OnlyOncePerJob` zeigt sync.Once-Semantik (1 Aufruf bei n=5 Wiederholungen), Python `test_ping_heartbeat_empty_url_calls_send_mq` zeigt genau einen `send_mq`-Aufruf
- **Bewertung:** Spec-Verhalten an Code-Ebene konsistent abgedeckt; Live-Beweis verlagert auf User-Verifikation am Server.

## Verdict: VERIFIED

### Begründung

Alle 12 prüfbaren Acceptance-Kriterien aus der Spec sind PASS:

- **Security-Kernziel** (Spec Z.446): Verbatim-Test findet 0 leakende Dateien im Git-Tree.
- **Code-Strukturkriterien** (Spec Z.447-451): Defaults leer, ENV-Lookup vorhanden, beide neuen Helper-Files existieren, kein Hardcoded Secret.
- **Test-Kriterien** (Spec Z.452-455): Alle Python- und Go-Tests grün, einschließlich der vier explizit geforderten Empty-URL- und Once-Per-Job-Tests.
- **Doku-Kriterien** (Spec Z.456-457): Specs anonymisiert, CLAUDE.md korrigiert (alte Falschaussage „Heartbeats wurden entfernt" durch korrekte Fail-Soft-Beschreibung ersetzt).
- **Service-Live** (Spec Z.458): Staging-API antwortet, Scheduler läuft mit 5 Jobs inkl. morning/evening, Timezone Europe/Vienna.

Die zwei UNKLAR-Punkte (Live-BetterStack-Heartbeat-Sichtbarkeit, Live-MQ-Auslieferung) sind durch Mock-basierte Unit-Tests der identischen Code-Pfade strukturell abgedeckt. Sie bleiben UNKLAR ausschließlich, weil der Validator weder BetterStack-Dashboard-Zugriff noch claude-mq-DB-Lesezugriff hat — beides ist außerhalb des Staging-API-Scopes und im Spec-Workflow (Migrations-Sequenz Schritt 4-5) explizit als User-Verifikation vorgesehen.

Kein einziges PASS-Kriterium verletzt; kein FAIL gefunden; das einzige Sicherheits-Risiko des BROKEN-Zustands (Token im public Git-Tree) ist nachweislich beseitigt.

Empfohlene Folgeaktionen für den User (keine Validator-Blocker):

1. Nach 18:00 Wien BetterStack-Dashboard prüfen, ob Evening-Heartbeat eingetroffen ist.
2. Verifizieren, dass die alten Heartbeat-URLs in BetterStack gelöscht und neu erstellt wurden (Spec Z.460).
