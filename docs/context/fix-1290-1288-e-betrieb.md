# Context: fix-1290-1288-e-betrieb

## Request Summary

Scheibe E aus Epic #1301, gebündelt: **E1** (#1290) — der Compare-Daily-Versand meldet `status:"ok"` auch bei 100 % Fehlschlägen (belegt: 133/133 im Prod-Journal 2026-07-16), weil das `failed`-Feld fehlt; **E2** (#1288) — Telegram postet `chat_id` ungeprüft, während E-Mail einen harten Empfänger-Guard hat. Beides Backend, parallel-sicher zu D2/D3 (Frontend).

## E1 — Fundstellen (verifiziert, Stand 2e926432)

| File | Relevance |
|------|-----------|
| `api/routers/scheduler.py:40-44` | **Vorbild** Trip-Reports (#766/#1012): `sent, failed = service.send_reports_for_hour(...)`; `status = "partial" if failed > 0 else "ok"`; Rückgabe `{status, count, failed}` |
| `api/routers/scheduler.py:137-138` | **Defekt:** Compare-Daily: `count = run_compare_presets_daily(user_id, hour=hour)`; Rückgabe `{"status":"ok","count":count}` — kein `failed` |
| `src/services/scheduler_dispatch_service.py:85-117` | `_dispatch_due_preset` fängt jede Exception → `return False` (Fehler-Isolation bleibt!) |
| `src/services/dispatch_orchestrator.py:151-187` | `run_briefing_dispatch` zählt nur `self._success` — Fehlschläge werden gezählt? Prüfen: ggf. `_failed`-Zähler ergänzen bzw. vorhandenen nutzen |
| `internal/scheduler/scheduler.go:322,344-347` | Go parst `Failed` GENERISCH aus jeder Endpoint-Antwort (`parsed.Failed > 0` → Fehler-Verbuchung) — **Go braucht KEINE Änderung**, sobald Python das Feld liefert |

**Entscheidung „ab wann rot":** per Konsistenz mit dem Vorbild — `status="partial"` sobald `failed > 0` (identische Semantik wie Trip-Reports, keine neue Schwellen-Erfindung). Die Plan-Frage („1 von 20 vs. 20 von 20") ist damit beantwortet: die Statusanzeige unterscheidet ok/partial, die Zahlen (`count`, `failed`) liefern die Größenordnung.

## E2 — Fundstellen (verifiziert)

| File | Relevance |
|------|-----------|
| `src/output/channels/telegram.py:134-199` | `TelegramOutput.send` postet `chat_id` ohne Prüfung an die Bot-API |
| `src/output/channels/email.py:27-110,415-512` | **Vorbild-Guard:** `TEST_MAILBOXES`-Frozenset, Normalisierung (Plus-Adressen), bedingungslose Blocks in BEIDEN Host-Zweigen, `OutputConfigError` |
| `src/app/config.py:245-260,295-297` | `force_test = env=="staging" or is_test_user_id(user_id)`; `can_send_telegram()` prüft nur „Token+Chat-ID nicht leer" — einziger (unzureichender) Schutz |
| `src/app/config.py:30-48` | `is_test_user_id`: Name-Heuristik („test"/„tdd") + `is_test_user`-Profilflag |
| `src/services/user_tier.py:6-14` | SMS strukturell sicher (tier-Default free) — Telegram hat keine solche Schranke |
| `internal/.../test_user.go:30-34` | Go `IsTestUserID` liest das Profil-Flag bewusst NICHT (Asymmetrie — in der Spec dokumentieren, nicht „reparieren": Python ist der Versand-Enforcement-Punkt, Go fasst keine Nutzer-JSONs an) |

**Richtung (Epic-Plan: „Guard analog E-Mail"):** Harter Guard IN `TelegramOutput.send` (nicht nur in Settings-Ableitung): (a) im Test-Modus (`is_test_mode`/`for_testing`) ist ausschließlich die Test-Chat-ID (`GZ_TELEGRAM_TEST_CHAT_ID`) erlaubt — Prod-Chat-ID wird hart mit `OutputConfigError` geblockt; (b) für Test-Nutzer (`is_test_user_id`) gilt dasselbe; (c) Fail-hard mit sprechender Fehlermeldung (wie E-Mail-Guard), damit E1s neues `failed`-Feld solche Fälle sichtbar macht (E1+E2 greifen ineinander!). Genaue Allowlist-Semantik in der Spec festzurren.

## Risks & Considerations

- **E1:** Fehler-Isolation NICHT verändern (ein kaputtes Preset darf die übrigen weiter nicht abbrechen — #1207-Verhalten). Nur Zählung + Rückgabe ergänzen. `dispatch_orchestrator` wird auch vom Trip-Pfad genutzt → Änderung darf Trip-Rückgabe nicht verändern (prüfen, wie Trip seine (sent, failed) heute gewinnt).
- **E2:** Kein Live-Telegram in Kern-Tests (GZ_TELEGRAM_LIVE-Opt-in!); Guard-Tests deterministisch gegen die Guard-Funktion, Sendepfad mit Sink/Boundary. Bestehende Staging-/E2E-Flows (Staging-Bot, `tg-live-e2e`-Nutzer) dürfen nicht brechen — Staging nutzt `for_testing()`-Settings mit Test-Chat-ID → muss erlaubt bleiben.
- Beide Fixes zusammen in EINEM Workflow (PO-sanktioniertes Bündel kleiner Issues), aber getrennte ACs je Issue; beide Issues am Ende schließen.
- Scheduler-Status-Endpoint (`/api/scheduler/status`) zeigt `last_run` — nach E1 bei Fehlschlägen `status="partial"`+Fehlerverbuchung durch Go (bestehende Mechanik #1012). check-gregor20.sh-Monitoring profitiert automatisch.

## Existing Specs

- `docs/specs/modules/`-Specs zu #1012/#766 (Trip-Reports failed-Feld) als Vorbild-Referenz suchen.
- Epic-Plan Abschnitt E1/E2.
