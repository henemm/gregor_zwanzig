# Context: 733 — Kanonischer Validator für Trip-Briefing-Mails (full + compact)

## Request Summary
Trip-Briefing-Mails (der meistgenutzte Mail-Typ) haben **keinen** automatisierten
Struktur-/Plausibilitäts-Validator — nur die Orts-Vergleich-Mail (via
`email_spec_validator.py`). Es soll ein kanonischer Acceptance-Validator entstehen,
der beide Briefing-Varianten (full HTML / compact Text seit #722) abdeckt und in der
Acceptance-Stage als Gate dient (Exit 0/1).

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/hooks/email_spec_validator.py` | **Vorbild** — IMAP-Fetch + Struktur/Plausi/Format/Vollständigkeit, Exit 0/1, YAML-Log. Nur Orts-Vergleich-Mail. |
| `src/outputs/email.py` | `build_mime_message()` (pure, baut MIME) + `EmailOutput.send()`. **Hier müssen die Marker-Header rein.** Genutzt von BEIDEN Mail-Typen. |
| `src/services/trip_report_scheduler.py:498-511` | Briefing-Versand: `email_html` truthy → full (html=True+plain), sonst compact (html=False, single text/plain). |
| `src/app/cli.py:347-355` | Orts-Vergleich-Versand: immer `html=True` + plain_text_body. Hier `X-GZ-Mail-Type: compare`. |
| `src/output/renderers/email/__init__.py:60,77-91` | `render_email(email_format=...)`: `compact` → `("", compact_text)`; `full` → `(html, plain)`. |
| `src/app/models.py:734` | `TripReportConfig.email_format: str = "full"` ("full"\|"compact"). |
| `src/formatters/trip_report.py:131-216` | Baut Report-DTO (`email_html`, `email_plain`, `email_subject`). |
| `tests/tdd/test_issue_722_email_compact.py` | Etablierter IMAP-MIME-Verhaltenstest (Content-Type/CTE/isascii/Bytes/Inhaltsblöcke). |

## Existing Patterns
- **Validator-Stil:** `email_spec_validator.py` — `fetch_latest_email()` via IMAP (Settings `GZ_IMAP_*`), Liste von `validate_*`-Funktionen, `run_validation()→(success, errors)`, `main()` mit Exit 0/1 + `_write_validation_log()` (YAML, fail-soft).
- **Mail-Build:** `build_mime_message()` ist eine **pure function** ohne SMTP-Seiteneffekt — ideal, um Header additiv zu setzen.
- **Format-Weiche:** existiert bereits sauber über `email_format` bzw. `email_html` truthy/leer — Validator muss nicht raten, wenn wir die Header durchreichen.
- **IMAP-MIME-Test als Beweis:** seit #722/#721/#636 ist der Briefing-Nachweis ein echter MIME-Test (multipart vs text/plain, CTE, isascii, Byte-Größe, Inhaltsblöcke) — der neue Validator kodifiziert genau dieses Muster.

## Dependencies
- **Upstream (was der Validator nutzt):** Stalwart-Test-Postfach via IMAP (`GZ_IMAP_*` aus Settings), die per Marker-Header getaggte Mail.
- **Downstream (was wir ändern, Auswirkungen):** `build_mime_message()` wird von BEIDEN Pfaden genutzt — Header sind additiv (zusätzliche MIME-Header), dürfen die bestehende Orts-Vergleich-Mail (besteht `email_spec_validator`) nicht brechen.

## Existing Specs
- CLAUDE.md-Sektion „E-MAIL SPEC VALIDATOR" (Scope auf Orts-Vergleich-Mail eingegrenzt, #732) — analoge Doku-Regel für den neuen Validator.
- Kein bestehender Spec für Briefing-Mail-Validierung (das ist die Lücke).

## Risks & Considerations
- **False-Positives:** Plausibilitäts-Schwellen müssen kalibriert sein, sonst blockieren sie Deploys fälschlich (Gate-Erosion). Kern-Anforderung des Issues.
- **Header durch zwei Pfade:** `build_mime_message` neue Params `mail_type`/`mail_format` müssen Defaults haben (Backward-Compat für Service-Error-Mail u.a.).
- **Backward-Compat alte Mails:** Validator gegen frisch zugestellte Acceptance-Mail → Header immer present. Fehlt der Header → klare Fehlermeldung statt Heuristik-Raten.
- **Kein Mock:** echte zugestellte Mail aus Test-Postfach (`GZ_IMAP_USER`), wie der bestehende Validator.
- **LoC-Budget:** Validator (~150) + Header-Plumbing (~15) könnte das 250-Limit streifen → ggf. `loc_limit_override`.
