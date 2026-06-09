# Context: Issue #670 — Antwort-Kommandos als echte Inbound-Keywords (PAUSE/SKIP/STOP/STATUS/CONFIG/HELP)

## Request Summary
E-Mail-Antworten sollen Aktionen per **bloßem Schlüsselwort** am Zeilenanfang auslösen
(`PAUSE 2d`, `SKIP`, `STOP`, `STATUS`, `CONFIG`, `HELP`) — zusätzlich zum bestehenden
`### key: value`-Pfad. Dazu muss in der Briefing-E-Mail ein Block „Antwort-Kommandos"
erscheinen. Mandantengetrennt, idempotent, mit Bestätigungs-Antwort.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | `_parse_command` (nur `###`), `_VALID_COMMANDS`, Dispatch. Hier: Bare-Keyword-Parser + neue Handler PAUSE/SKIP/STOP/CONFIG. STATUS→`status`, HELP→`hilfe` (Bestand). |
| `src/app/models.py:679` (`TripReportConfig`) | Hat `enabled` (für STOP). **Fehlt:** `paused_until` (PAUSE), `skip_next` (SKIP). Schema-relevant → Backup-Hook + Roundtrip-Test. |
| `src/app/loader.py:347-379` / `:1057-1080` | De-/Serialisierung von `report_config`. Neue Felder additiv (Defaults rückwärtskompatibel). |
| `src/services/trip_report_scheduler.py:242-264` (`_get_active_trips`) | **Gating-Punkt.** Filtert HEUTE nur nach `get_stage_for_date`. Prüft `enabled` NICHT → STOP/`abbruch` wirkt latent gar nicht. Hier müssen `enabled`/`paused_until`/`skip_next` greifen. |
| `src/services/inbound_email_reader.py:85-161` | Befüllt `InboundMessage` (trip_name aus `[Betreff]`, user_id aus `lookup_user_by_email`), ruft `process()`, sendet `confirmation_body` zurück per `_send_email_reply`. Bare-Body kommt unverändert an. |
| `src/output/renderers/email/html.py:800` + `render_html` (Block vor Footer) | Footer-Zeile listet veraltet `report·status·hilfe`. Neuer dedizierter Block „Antwort-Kommandos" in Design-Optik (Info-Box-Muster Z. 629/710), Desktop+Mobile. |
| `src/services/inbound_telegram_reader.py:174-188` | Zweiter `process()`-Aufrufer — Bare-Keywords dürfen Telegram-Pfad nicht brechen (additiv). |

## Existing Patterns
- **Mandantentrennung:** Scheduler ist pro Nutzer instanziiert (`self._user_id` → `load_all_trips(user_id)`); Processor erhält `msg.user_id` aus `lookup_user_by_email` (kein `default`-Fallback im authentifizierten Treffer). Lehre #663.
- **Idempotenz:** `command_log.json` pro Nutzer (`_is_already_applied`/`_append_command_log`) — für SKIP/PAUSE/STOP nutzbar bzw. Flag-Konsum ist selbst-idempotent.
- **Bestätigung:** Jede `CommandResult` trägt `confirmation_subject`/`confirmation_body`; E-Mail-Reader sendet automatisch zurück.
- **Optionale Mail-Blöcke:** `report_config.show_*`-Flags steuern Blöcke (vgl. #664 `show_metrics_summary`).
- **Info-Box-Optik:** `<div class="section" style="background:{G_BOX_INFO_BG};border-left:4px solid {G_ACCENT};padding:12px;margin:8px 0;">`.

## Dependencies
- **Upstream:** `TripReportConfig` (Persistenz), `load_all_trips`/`save_trip`, `EmailOutput.send`.
- **Downstream:** Scheduler-Sende-Entscheidung (morning/evening), Telegram-Inbound (gemeinsamer Processor), E-Mail-Rendering.

## Risks & Considerations
- **Latenter Bug:** `report_config.enabled` wird im Sende-Pfad nie geprüft. STOP muss erst durch ein echtes Gating wirksam werden — gehört zum Scope (AC „STOP deaktiviert dauerhaft").
- **Schema-Change:** Neue Persistenz-Felder → Backup-Hook feuert, Roundtrip-Test Pflicht (alte JSON ohne Felder → Defaults).
- **SKIP-Semantik:** „nächstes Briefing" = chronologisch nächster geplanter Versand (morning ODER evening); Flag wird beim Versand-Versuch konsumiert (one-shot) und gespeichert.
- **PAUSE-Dauer-Parsing:** `Nd`/`Nh` (und bare `N`=Tage); ungültige Dauer → Fehler-Bestätigung.
- **On-Demand vs. geplant:** Explizites `report morning` (send_test_report) bleibt trotz Pause/Stop möglich — Gating nur im geplanten Pfad.
- **Bare-Keyword-Kollision:** Nur kleine Whitelist am Zeilenanfang, case-insensitiv → geringes False-Positive-Risiko; `###`-Pfad bleibt unberührt.
- **CONFIG:** Issue-Empfehlung „zunächst Link/Status, kein Inline-Edit" → Bestätigung mit Settings-Link.
- **Kein Mock:** E2E gegen Staging via echter Inbound-Verarbeitung + IMAP; zwei Nutzer für Cross-User-Test.
