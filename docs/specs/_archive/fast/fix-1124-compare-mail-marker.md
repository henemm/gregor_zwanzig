# Mini-Spec: #1124 — Compare-Versandpfad setzt `X-GZ-Mail-Type: compare`

**Issue:** #1124 (Teil A — Produktivcode). Teil B (Validator `email_spec_validator.py`) ist ein **separater** Workflow (Validator-Regel).
**Track:** Fast Track (Intake-Score 0)

## Problem (verifiziert)

`send_one_compare_preset()` in `src/services/scheduler_dispatch_service.py:223` ruft
`EmailOutput(settings).send(subject, html_body, plain_text_body=…, to=…, compare_hourly_enabled=…)`
**ohne** `mail_type`. Ergebnis: der Produktiv-/Scheduler-Compare-Versand trägt **keinen**
`X-GZ-Mail-Type: compare`-Header.

Gegenprobe: `grep -rn 'mail_type=' src/` zeigt, dass **kein einziger Pfad** in `src/`
derzeit `mail_type="compare"` setzt (der im Issue genannte Legacy-`cli.py`-Pfad existiert
nicht mehr). Alle anderen Mail-Typen setzen ihren Marker
(`trip-briefing`, `radar-alert`, `deviation-alert`, `official-alert` in
`notification_service.py`) — Compare ist der einzige ohne.

`EmailOutput.send()` (`src/output/channels/email.py:372`) akzeptiert `mail_type` bereits
und reicht ihn an `build_mime_message()` durch, das den Header setzt.

## Was ändert sich

- In `send_one_compare_preset()` (`scheduler_dispatch_service.py`) wird der `send()`-Aufruf
  um `mail_type="compare"` ergänzt.

## Was darf sich NICHT ändern

- Betreff, HTML-/Text-Body, Empfängerliste, `compare_hourly_enabled` — unverändert.
- Kein `mail_format="full"`: `X-GZ-Format` ist laut CLAUDE.md **trip-briefing-spezifisch**
  (`full|compact`); für Compare ist es bedeutungslos. Bewusste Abweichung von der
  „Fix-Idee"-Skizze im Issue (Skizze ist keine Spec). Dispatch-Kriterium für den
  Compare-Validator ist laut CLAUDE.md **ausschließlich** `X-GZ-Mail-Type: compare`.
- Kein anderer Versandpfad wird angefasst.

## Manuelle Test-Schritte (Staging-E2E)

1. Compare-Preset auf Staging über den Scheduler-/Einzelversand-Pfad auslösen
   (nicht CLI), Zustellung an `gregor-test@henemm.com`.
2. Mail per IMAP holen (`BODY.PEEK`) und Header prüfen:
   `X-GZ-Mail-Type: compare` ist vorhanden.
3. `uv run python3 .claude/hooks/email_spec_validator.py` → Exit 0 (Compare-Mail-Plausibilität).

## Inline-Test (während Implementierung)

- [ ] Test treibt `send_one_compare_preset()` über einen echten Render-/Transport-Seam
      (analog bestehender Dispatch-Tests, z. B. `test_issue_461_compare_preset_dispatch.py`
      / `test_compare_preset_slot_dispatch.py`) und weist nach, dass die erzeugte
      MIME-Message `X-GZ-Mail-Type == "compare"` trägt. Kein Mock der eigenen Annahme —
      der Header muss aus dem realen `build_mime_message()`-Pfad stammen (Muster wie
      `test_issue_733_briefing_mail_validator.py`). Rot vor Fix, grün nach Fix.
