# Context: fix-2813-e2e-en-mailweg

## Request Summary
Issue #2813 (Befund aus /e2e-verify für #2681): Der englische Mailweg wird im E2E-Verify nur mit synthetischen Mails belegt, nicht über Staging-Kern/Nutzer `en`; Worktree-Versand verliert `+en@`; Alarm-Validatoren haben keinen Betreff-Filter; Telegram-Live-Tests brauchen `-m live` und enden mit Wächter-Teardown-Error. Vier Teilbefunde.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/tools/staging_mail_pruefen.py` | Teil 1: kennt kein `--lang`; `_argumente` (Z.353), `MailApi`/`fuehre_lauf`, `echter_validator_runner` (pollt via `_mail_da` nur Betreff-Marker + Mail-Typ, ruft Validator ohne `--lang/--to-contains`); Nutzer kommt aus `GZ_AUTH_USER` |
| `scripts/send_gate_test_mails.py` | Teil 2: `_empfaenger(lang)` baut `+en@`; `_test_settings` setzt `mail_to` |
| `src/app/origin_guard.py` | Teil 2: Herkunftssperre #1476, `classify_origin` → Worktree = "test" → To wird auf Basisadresse umgeschrieben (Sperre selbst NICHT aufweichen) |
| `.claude/hooks/official_alert_mail_validator.py`, `radar_alert_mail_validator.py` | Teil 3: `main()` ruft `fetch_latest_message(lang, to_contains)` ohne `subject_contains`; kein `--subject-contains`-Argument |
| `.claude/hooks/briefing_mail_validator.py` | Vorbild Teil 3: hat `--subject-contains`/`--mail-type`, `_message_matches` (Z.703) |
| `.claude/hooks/_e2e_paths.py` | gemeinsame `sprach_argumente`, `mail_waehlbar` (Sprache+Empfänger) |
| `.claude/commands/e2e-verify.md` | Z.145–180: Doku der Befehle; Hinweis zu Telegram nennt `-m live` nur beiläufig |
| `tests/tdd/test_issue_686_telegram_functional_live.py`, `tests/tdd/test_telegram_live_zweisprachig.py` | Teil 4: `live` + `real_data_root` (Opt-out der Datenwurzel-Isolation) → Wächter #2226 (`tests/conftest.py`, Session-Wächter) schlägt im Teardown an wegen Spur `data/users/tg-live-e2e` |
| `pyproject.toml` Z.65 | `addopts = -q -m 'not email and not live and not staging'` → ohne `-m live` "0 selected"/Offline-Tests |

## Existing Patterns
- Validator-Auswahl nach Sprache + Empfänger (`mail_waehlbar`), Kopf `X-GZ-Lang` Pflicht (#2681).
- Staging-Werkzeug-Tests mit injizierbarem Netzrand (`main(transport=…, validator_runner=…)`).
- Briefing-Validator filtert per `--subject-contains` bereits sauber.

## Dependencies
- Upstream: Staging-Kern (127.0.0.1:8001), Staging-Nutzer `en` (`scripts/staging_e2e_user_en.py`, `GZ_E2E_EN_USER/PASS`), Stalwart-Test-Postfach.
- Downstream: `/e2e-verify` (Schritt 3b/3c), PR-Gates, Mail-Renderer-Commit-Gate.
- Bekannter Blocker des Staging-Mailwegs: #2774 (Wegwerf-Konten, Plus-Adresse, Helfer-Konto) – kann Teil 1 live einschränken.

## Existing Specs
- Zweisprachigkeit ADR-0104 (Epic #2644), Spec/Workflow zu #2681; in /20-analyse zu identifizieren. Keine Spec zu #2813.

## Risks & Considerations
- Teil 2: Herkunftssperre (#1476) nicht lockern; Lösung eher: Skript erkennt Worktree + `--lang en` und bricht laut ab statt still umzuschreiben.
- Teil 3: Validator-"OK" ohne Frische-Beweis → Betreff-/Token-Filter (`--subject-contains`) nachrüsten; Token im Betreff der Gate-Mails prüfen.
- Teil 4: Wächter-Fehler echt oder falsch-positiv? Prüfen, ob die Tests bewusst unter echter Datenwurzel schreiben (`real_data_root`) und aufräumen müssen; Wächter nicht still abschwächen.
- Teil 1 Umfang: `--lang en` braucht Anmeldung als Nutzer `en`, Empfänger `+en@`, Validator-Aufruf mit `--lang en --to-contains +en@`; ggf. in Teilaufgaben splitten (Triage in /20-analyse).
- Reine Werkzeug-/Doku-Änderung, kein Produktcode.

## Analysis

### Type
Bug (Werkzeug/Doku, kein Produktcode). Vier Teilbefunde, Ursachen im Code belegt.

### Befunde und Ursachen
1. **`--lang en` fehlt in `staging_mail_pruefen.py`:** `_argumente` kennt es nicht; `MailApi` legt einen Wegwerf-Nutzer per `registriere(baue_plus_adresse(tag))` an (Sprache de), `echter_validator_runner` ruft den Validator ohne `--lang/--to-contains`. EN wird nur synthetisch belegt. Blocker #2774 (Wegwerf-Konten/Plus-Adresse) kann den Live-Lauf einschränken.
2. **Worktree verliert `+en@`:** `src/output/channels/email.py:731` schreibt bei `running_origin == "test"` (jeder Worktree) das To auf `gregor-test@henemm.com` um. `send_gate_test_mails.py` meldet trotzdem Erfolg und druckt `An: …+en@`. Die Validatoren mit `--to-contains +en@` greifen dann ältere Mails: stilles falsches OK. Die Sperre bleibt unangetastet.
3. **Alarm-Validatoren ohne Betreff-Filter:** `official_alert_mail_validator.main()` (Z.564) und `radar_alert_mail_validator.main()` (Z.327) rufen `fetch_latest_message(lang, to_contains)` ohne `subject_contains`. Briefing/Compare-Gate-Mails tragen `[GATE1233 <token>]` im Betreff; der Alarm-Betreff kommt aus `render_alert_subject` — Token-Sichtbarkeit dort ist in der Spec zu prüfen. Vorbild: `briefing_mail_validator.py` (`--subject-contains`).
4. **Telegram-Live:** Die `real_data_root`-Tests legen/ändern `data/users/tg-live-e2e` absichtlich im echten Baum (`ensure_test_user_with_active_trip`, `set_test_user_language`); der Session-Wächter #2226 (`tests/conftest.py:269`) vergleicht den Fingerprint vor/nach der Session und schlägt zwangsläufig an. Echter Befund, kein Fehlalarm: die Spur wird nicht zurückgesetzt. `-m live` fehlt in der `e2e-verify.md`-Doku.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/send_gate_test_mails.py` | MODIFY | Teil 2: Worktree + `--lang en` ⇒ lauter Abbruch statt stillem Umschreiben |
| `.claude/hooks/official_alert_mail_validator.py` | MODIFY | Teil 3: `--subject-contains` |
| `.claude/hooks/radar_alert_mail_validator.py` | MODIFY | Teil 3: `--subject-contains` |
| `.claude/hooks/_e2e_paths.py` | MODIFY (ggf.) | gemeinsamer Filter |
| `.claude/tools/staging_mail_pruefen.py` | MODIFY | Teil 1: `--lang en`, Nutzer `en`, Validator mit `--lang/--to-contains` |
| `.claude/commands/e2e-verify.md` | MODIFY | Doku (`-m live`, Staging-Checkout, Subject-Filter) |
| `tests/tdd/_telegram_live_fixture.py` + beide Live-Tests | MODIFY | Teil 4: Spur im echten Baum zurücksetzen (Read-Modify-Write), Wächter nicht abschwächen |
| neue Tests unter `tests/tdd/` | CREATE | je Teil ein Verhaltenstest |

### Scope Assessment
- Files: ~9 · LoC ca. +180/-20 · Risk Level: MEDIUM (Teil 1 live-abhängig, Teil 4 berührt Wächter-Semantik)

### Technical Approach
- Teil 2: Abbruch statt Umschreiben (Herkunftssperre bleibt). Teil 3: `--subject-contains` analog Briefing-Validator. Teil 4: Fixture stellt `data/users/tg-live-e2e` am Ende auf den Ausgangszustand zurück; Wächter unverändert.
- Teil 1 ist der größte, live-abhängige Teil (#2774): als eigener Slice/Folge-Ticket empfohlen; Teile 2–4 zuerst.
- Hinweis: Der Plan-Subagent wurde bei dieser reinen Werkzeug-Änderung übersprungen; die Bewertung steht hier.

### Dependencies
`/e2e-verify` Schritt 3b/3c, Mail-Renderer-Commit-Gate, `_e2e_paths.mail_waehlbar`, Staging-Nutzer `en` (`scripts/staging_e2e_user_en.py`).

### Open Questions
- [ ] Teil 1 im selben Workflow oder als Folge-Ticket? (Empfehlung: Folge-Ticket wegen #2774)
- [ ] Tragen die Alarm-Betreffzeilen den Lauf-Token? Wenn nein, Token im Gate-Mail-Betreff ergänzen.
