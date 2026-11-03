# Context: staging-mailweg-2774

## Request Summary
Issue #2774: `/e2e-verify` Schritt 3b (Trip-/Compare-Mail auf Staging zustellen und per Validator prüfen) ist nicht mehr durchführbar. Soll: dokumentierter, vollständiger Weg (Wegwerf-Nutzer mit Plus-Adresse, Bestätigung über Helfer-Konto, Einzelversand mit Core-Auth), `/e2e-verify` und Rezepte aktualisieren, dazu ein Ausblick-Szenario ohne Winddaten (AC-5 aus #1670 beobachtbar).

## Befunde aus dem Issue (gegen Code geprüft)
- Rezept Schritt 3b (`.claude/commands/e2e-verify.md` Z. 83-106) schreibt vor: Test-Trip mit Empfänger `gregor-test@henemm.com`. Go lehnt diese Adresse als `email_taken` ab (`internal/handler/auth.go:189,1278,1290`), weil sie mehrdeutig ist.
- Python-Core (Port 8001) verlangt `X-GZ-Core-Auth` (`api/main.py` ~144, #2142); das Rezept nennt das nicht.
- Einzelversand existiert: `POST /api/scheduler/trips/{trip_id}/send?user_id=..&report_type=..` und `/compare-presets/{id}/send` (`api/routers/scheduler.py:310,321`), beide delegieren an `send_briefing`.
- Ein Wegwerf-Konto ohne Helfer-Bestätigung scheitert an `email_not_verified`.

## Related Files
| File | Relevanz |
|------|----------|
| `.claude/tools/staging_befehl_pruefen.py` | Vorbild: `StagingApi` (registriere → Helfer holt staging-token → verify → login; `lege_trip_an`, `loesche_nutzer`, `loese_poll_aus` mit Core-Auth), Plus-Adresse `gregor-test+<tag>@henemm.com`, IMAP nur `BODY.PEEK`, Aufräumen im `finally` |
| `.claude/tools/staging_messlauf.py` | Zweiter Staging-Treiber (#2439), nutzt das Werkzeug per importlib |
| `.claude/commands/e2e-verify.md` | Schritt 3b + Rezept „Befehl per echtem Mail-Eingang" – zu aktualisieren |
| `api/routers/scheduler.py` | Einzelversand-Endpunkte Trip/Compare |
| `api/main.py` | Core-Auth-Header |
| `scripts/send_gate_test_mails.py` | Lokale Ersatz-Mails (Notbehelf bei #1670), nur Renderer, kein Staging-Zustellweg |
| `.claude/hooks/briefing_mail_validator.py`, `email_spec_validator.py` | Lesen Postfach `gregor-test@henemm.com`; müssen Mails des Wegwerf-Nutzers (Plus-Adresse) finden können (zu prüfen) |
| `docs/specs/modules/fix_2542_staging_befehl_pruefweg.md` | Spec des Vorbild-Werkzeugs |
| `docs/specs/modules/fix_1670_mail_formatdetails.md` | AC-5: Wind-Zelle „–" statt „0" ohne Winddaten, braucht Szenario ohne Winddaten |
| `docs/reference/mail_validators.md` | Validator-Zuordnung |

## Existing Patterns
- Wegwerf-Nutzer + Helfer-Konto (`GZ_AUTH_USER/PASS` in Staging-`.env`) statt Änderung am Konto `default`.
- Aufräumen im `finally`; Exit-0/1/2-Konvention; reine Funktionen getrennt vom HTTP-Rand (testbar ohne Mock-Theater).
- Staging-Treiber lesen `/home/hem/gregor_zwanzig_staging/.env`.

## Dependencies
- Upstream: Staging-API (Go: Registrierung/Login/Trips), Core Port 8001 mit Core-Secret, Stalwart-IMAP (`GZ_TEST_IMAP_*`), Resend-Umleitung auf Testpostfach in Staging.
- Downstream: `/e2e-verify` (Hard Gate für Prod-Deploy, `staging_gate.py`), Renderer-Commit-Gate, alle Mail-Änderungen (Trip-/Compare-Briefing).

## Existing Specs
- `fix_2542_staging_befehl_pruefweg.md`, `feat_2439_staging_messtreiber.md`, `fix_1595_s1_staging_messverfahren.md`, `fix_1670_mail_formatdetails.md`, `staging_seed_endpoint.md`

## Risks & Considerations
- Staging-Versand langsam (DWD-Gewittersignal-Timeouts, Compare >3 Min): großzügige Timeouts.
- Validatoren filtern evtl. auf die exakte Adresse `gregor-test@henemm.com`; Plus-Adresse muss unterstützt oder der Validator parametrisierbar sein (in /20-analyse klären).
- Szenario „ohne Winddaten" auf Staging braucht kontrollierbare Wetterdaten (Staging-Seed-Endpoint prüfen); echte Provider liefern Wind praktisch immer.
- Kein Produktcode ändern, Absenderschutz/Auth nicht umgehen. Mehr-Nutzer-Isolation: Wegwerf-Nutzer nur mit eigener `user_id`, nie „default".
- Trip-Kontingent (Tarif free: 3) einhalten; Wegwerf-Nutzer immer löschen.
- `e2e-verify.md` ist Workflow-Doku, kein Mail-Renderer: Renderer-Commit-Gate nicht betroffen.

## Analysis

### Type
Bug (Werkzeug-/Doku-Lücke, kein Produktcode)

### Befunde der Analyse
- Beide Validatoren lesen das GANZE Postfach `gregor-test` (IMAP-Login `GZ_TEST_IMAP_*`), filtern NICHT nach Empfänger-Adresse, sondern nach `X-GZ-Mail-Type` und `--subject-contains` (`briefing_mail_validator.py` fetch_latest_message ~723; `email_spec_validator.py` `_fetch_latest_message` ~376, mit Altersgrenze). Plus-Adresse `gregor-test+<tag>@` landet (Vorbild #2542) im selben Postfach ⇒ **Validatoren brauchen keine Änderung**, nur den eindeutigen Betreff (Trip-Name mit Tag) als `--subject-contains`.
- Vorbild `.claude/tools/staging_befehl_pruefen.py` (599 Z.) liefert bereits `StagingApi` (registriere, Helfer-Bestätigung, lege_trip_an, loesche_nutzer, Core-Auth), Plus-Adresse, `_etappe`/`baue_trip`, IMAP-Helfer, Aufräumen im `finally`. Es fehlen: Compare-Preset anlegen, Einzelversand (`POST :8001/api/scheduler/trips/{id}/send`, `/compare-presets/{id}/send` mit `X-GZ-Core-Auth`), Mail-Abruf+Validator-Aufruf.
- Szenario „ohne Winddaten" (AC-5 #1670): echte Provider liefern Wind praktisch immer; `staging_seed_endpoint` setzt nur Tarif/SMS-Zähler, keine Wetterdaten. Auf Staging nicht kontrollierbar ⇒ ehrlich benennen statt erfinden.

### Affected Files
| File | Change | Description |
|------|--------|-------------|
| `.claude/tools/staging_mail_pruefen.py` | CREATE | Treiber: Wegwerf-Nutzer + Trip (+ Compare-Preset), Einzelversand mit Core-Auth, Validator-Aufruf mit `--subject-contains`, Aufräumen; importiert `StagingApi` etc. per importlib wie `staging_messlauf.py` |
| `tests/tools/test_staging_mail_pruefen.py` (o. ä. nach Konvention) | CREATE | reine Funktionen (Betreff-/Tag-Bau, Exit-Code, Validator-Argumente) ohne Mock-Theater |
| `.claude/commands/e2e-verify.md` | MODIFY | Schritt 3b ersetzt (kein `gregor-test@` als Empfänger, Core-Auth, Rezept-Verweis) |
| `docs/reference/mail_validators.md` | MODIFY | Zustellweg + Subject-Filter dokumentieren |
| `docs/reference/operations_playbook.md` o. Staging-Rezepte | MODIFY | Rezept Staging-Mailweg |

### Scope
- Dateien: 4–5 · ca. +250 LoC (Werkzeug ~170, Tests ~60, Doku) · Risiko NIEDRIG (nur Test-Infrastruktur, kein Produktcode, Aufräumen im finally)

### Technical Approach
Neues Werkzeug nach dem Muster #2542 wiederverwenden (nicht kopieren): Wegwerf-Nutzer → Trip mit Plus-Adresse → `POST /send` mit Core-Auth (großzügiges Timeout ≥ 300 s wegen Compare >3 Min) → Validator (pfadrichtig) mit `--subject-contains <Tag>` → Nutzer löschen. Mehrnutzer-Isolation: eigene `user_id`, nie `default`; Trip-Kontingent 3 beachten.

### Dependencies
Staging-API (Go), Core :8001 + Secret aus Staging-`.env`, Stalwart-IMAP, Resend-Umleitung in Staging; Downstream: `/e2e-verify`-Gate.

### Open Questions
- [ ] AC-5-Szenario auf Staging: Empfehlung = Teil dieses Tickets NUR als dokumentierte Grenze (Wind-Ausfall nur per lokalem Render-Test beobachtbar, bereits in #1670 abgedeckt); kein Staging-Eingriff in Wetterdaten. Alternativ Ort/Zeitraum suchen, für den der Provider keinen Wind liefert (unsicher) – in der Spec entscheiden.
- [ ] Compare-Preset-Anlage per API: Pfad/Feldschema in /30-write-spec aus `api_contract.md` bestätigen.
