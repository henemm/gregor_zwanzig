# Context: fix-1147-resend-test-harness

Issue: #1147 — Strukturell: Fix-Verifikation versendet selbst Test-Mails über Resend (Prod-Service als Test-Harness, 11. Vorfall). Baustein C (Bash-Gate) abgespalten → #1148 (eigener Gate-Workflow).

## Analysis

### Type
Bug (strukturell) — Empfänger-Invariante (Baustein A) + Prüfrezept-Ersatz (Baustein B).

### Root Cause (Kurzform, Details in #1147)
Alle bestehenden Guards klassifizieren „Test" absender-/prozessseitig (pytest, GZ_ENV, is_test_mode, user_id-Substring). Das E2E-Prüfrezept umging alle Marker absichtlich (Kunst-User `resendverify1122`, interner Prod-Port 8001) → Verifikations-Mail über Resend am 2026-07-08 13:52. Zusätzliche Lücken (Plan-Agent):
- `EmailOutput.send(to=...)`-Override kommt erst NACH den Init-Guards an (`email.py:180-181`) — Preset-/Subscription-Empfänger (`scheduler_dispatch_service.py:88-92, 219-224, 282-286`) erreichen den Dial ungeprüft.
- Go `internal/handler/auth.go:222-246` routet nach `IsTestUser(username)`, schaut den Empfänger (`user.MailTo`) nie an.
- `src/app/core.py:20` — toter smtplib-Pfad ganz ohne Guards (kein Produktions-Aufrufer; Cleanup-Kandidat).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/channels/email.py` | MODIFY | Empfänger-Invariante in `send()` nach Z.180 (Host+finale Empfängerliste bekannt); `TEST_MAILBOXES`-Konstante |
| `internal/mail/sender.go` | MODIFY | Empfänger-Check am Eintritt von `Send()` (Z.72-75), analog `resendBlocked`; greift automatisch für `SendWithFallback` + auth.go |
| `tests/tdd/test_issue_1147_resend_recipient_invariant.py` | CREATE | AC-Tests Python (Vorbild test_issue_1122_*) |
| `internal/mail/recipient_guard_test.go` | CREATE | AC-Tests Go (Vorbild resend_guard_test.go) |
| `docs/specs/modules/issue_1147_resend_recipient_invariant.md` | CREATE | Spec |
| `docs/reference/operations_playbook.md` o.ä. | MODIFY | Baustein B: passives Prüfrezept dokumentieren |

### Scope Assessment
- Files: 5-6
- Estimated LoC: Produktivcode ~35-55, Tests ~160-240 (Tests zählen; LoC-Limit 250 im Blick behalten)
- Risk Level: MEDIUM (Sendepfad-Änderung Python+Go; Mixed-Empfängerlisten)

### Technical Approach (Empfehlung Plan/Sonnet, übernommen)
**Hart failen (raise/error), NICHT still umlenken:**
- Guard sitzt auf Send-Ebene (nicht Settings-Konstrukt wie #1122) → Raise crasht keinen Prozess, nur den einen Sendeversuch; Aufrufer (Scheduler-Dispatch) fangen Exceptions bereits ab.
- Stille Umlenkung bei Mixed-Listen (Test- + echte Empfänger) würde reale Empfänger unbemerkt über Stalwart schicken — lauter Fehler ist sicherer.
- Go: Error aus `Send()` reicht — `SendWithFallback` lenkt Nicht-535-Fehler ohnehin auf die Fallback-Config (Stalwart) um.
- Invariante: Empfängerliste enthält `gregor-test@henemm.com` oder `gregor-staging@henemm.com` UND Host enthält `resend` (case-insensitive) → Fehler mit Verweis auf #1147.

### Baustein B (Prozess/Doku)
Prod-Mail-Pfad-Nachweis nur noch passiv: Header-Forensik an echter, ohnehin versendeter User-Mail (DKIM s=resend, amazonses-Received) + Unit-Env-Attestation (`GZ_RESEND_ALLOWED=1`, Settings-Auflösung) + Guard-Log-Grep. Kein synthetischer Send, keine Kunst-User auf Prod. Memory-Rezept bereits umgeschrieben (2026-07-08); Doku-Verankerung im Repo fehlt noch.

### Dependencies
- Bestehende Guards bleiben unberührt (erste/zweite Linie); neue Invariante ist dritte, empfängerseitige Linie.
- #1148 (Bash-Gate) unabhängig, eigener Workflow.
- Cleanup Prod-Daten: `data/users/prodverify1082-1783519172` entfernen (Deploy-Schritt, als claude-gregor, chirurgisch).

### Open Questions
- (an PO, in Spec-Freigabe integriert) Mixed-Liste: harter Komplett-Fehler der einen Mail ist akzeptiert? (Empfehlung: ja — laut, statt still falsch zu routen)
