# Context: fix-2152-testkonto-profilfeld

Issue: #2152 — Testkonto-Heuristik trifft echte Nutzernamen (Teil von Epic #2138). Stand `cf2782b5`, 2026-09-17.

## Analysis

### Type
Bug (Fehlklassifikation echter Nutzer als Testkonto, stiller Ausfall aller Kanäle)

### Root Cause
Testkonto-Status wird in Go UND Python allein über die Namens-Heuristik (`test`/`tdd` Substring, case-insensitive) bestimmt. Das Profilfeld `is_test_user` existiert nur in Python als Leser, im Go-Modell gar nicht — und `SaveUser` (Replace) verschluckt es.

Zwei Richtungen falsch:
- **False Positive:** „protester", „Testarossa", „mattdd" → Fan-out-Skip, kein Adress-Eigentum, Mail-Lookup blind, Mail-Routing auf Test-SMTP. Python: `config.py:68` schaltet `force_test` → Briefing ginge über das Test-Postfach, selbst wenn Go den Nutzer bedient.
- **False Negative:** die echten Testkonten heißen `admin` (Playwright, `frontend/e2e/testUser.ts`) und `validator-issue110` (`GZ_VALIDATOR_USER`) — kein Treffer. ADR-0028:64 hat das vorhergesagt.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/model/user.go` | MODIFY | Feld `IsTestUser bool \`json:"is_test_user,omitempty"\`` |
| `internal/model/test_user.go` | MODIFY | Heuristik entfernen; Prädikat = Profilfeld ODER `tg-live-e2e` (fester Fixture-Sonderfall bleibt) |
| `internal/scheduler/scheduler.go:496-500` | MODIFY | `filterOutTestUsers` bekommt Store-Zugriff (`s.store.LoadUser`), filtert über Feld |
| `internal/store/address_owner.go:53`, `internal/store/user.go:482` | MODIFY | `u.IsTestUser` statt Namensprüfung (`u` liegt schon geladen vor) |
| `internal/mail/sender.go:67` `IsTestUser` | MODIFY | Signatur auf `*model.User`/Flag; Aufrufer `handler/auth.go:371,1225`, `auth_oauth.go:352` laden das Profil |
| `internal/handler/auth.go` Register | MODIFY | optionales Request-Feld `is_test_user` wird persistiert |
| `scripts/setup-validator-user.sh:20-23`, `frontend/e2e/global.setup.ts` | MODIFY | Testkonten beim Anlegen mit `is_test_user: true` registrieren |
| `src/app/config.py:56-78` | MODIFY | Namens-Heuristik entfernen; Profilfeld über `get_data_root()` (Default `data_dir=None`), `tg-live-e2e` bleibt |
| `src/app/config.py:380` | MODIFY | Wrapper übergibt die konfigurierte Datenwurzel |
| `src/app/loader.py:1209-1211` | MODIFY | `startswith("test")`-Vorfilter entfernen |
| `internal/mail/sender_test.go` (`TestIsTestUser_Boundary`), `sender_allowlist_test.go:215-254`, `tests/tdd/test_issue_1013_telegram_test_isolation.py:180-260`, `tests/tdd/test_telegram_chat_id_ownership.py:216-217` | MODIFY | pinnen die Heuristik fest → auf Flag-Semantik umstellen |
| `docs/specs/modules/password_reset_mail.md:249` | MODIFY | „akzeptierter False Positive" revidieren |
| `docs/adr/00xx-testkonto-profilfeld.md` | CREATE | löst ADR-0028 Known Limitation ab („Abgelöst durch") |
| `docs/specs/modules/testkonto_profilfeld.md` | CREATE | Spec |

### Scope Assessment
- Files: ~16 (8 Go, 3 Python, 4 Tests, Docs)
- Estimated LoC: ~+180/-90 (Produktivcode ~90, Tests ~100); `loc_limit_override 500` bei Bedarf — KEIN Schnitt in Scheiben
- Risk Level: MEDIUM — Fan-out-/Versandpfad; Gegenrichtung „Testkonto wird echt und sendet über Resend"
- Deploy: Full-Stack (Go + Python)

### Technical Approach
1. **Feld zuerst** (`model.User.IsTestUser`) — damit Replace-Save es nicht mehr verschluckt (Daten-Schema-Rework: Roundtrip-Test Pflicht, Bestandsfelder unberührt).
2. **Heuristik ERSETZEN, nicht als Fallback behalten** — ein Fallback bei fehlendem Feld fängt „protester" weiterhin (Feld fehlt bei ihm ja). Einzige feste Ausnahme: `tg-live-e2e` (dokumentierte Fixture-Konstante, bleibt in Go und Python).
3. **Flag bei Anlage setzen:** Register-Request akzeptiert `is_test_user`; `setup-validator-user.sh` und Playwright-Setup nutzen es. Sonst reißt der Schutz bei jedem neuen Testkonto (False-Negative-Richtung, ADR-0028).
4. **Keine Migration:** Staging hält `default`, `tg-live-e2e`, `validator-issue110` — nur `tg-live-e2e` braucht Test-Status und ist Konstante. `migrate_1257/1258` sind manuelle One-Shot-CLIs, kein Startup-Muster. Prod-Bestand für diese Sitzung nicht lesbar → im Deploy-Schritt gegenprüfen (Liste der Nutzer-IDs, ob eine der Heuristik entspräche); nur dann einmaliges Setzen per Datei.
5. **Nachweis am Wirkort:** Test „protester ohne Flag" muss durch den echten Dispatch-Pfad laufen (Scheduler nicht übersprungen UND Python wählt Produktiv-Credentials, nicht `for_testing()`), nicht nur `filterOutTestUsers` isoliert. Gegenprobe: Konto mit `is_test_user: true` und neutralem Namen wird übersprungen und auf Test-SMTP geroutet.
6. **Dokumentierte Entscheidungen ablösen:** ADR-0028 Known Limitation → neues ADR; `password_reset_mail.md:249` revidieren.

### Dependencies
- `internal/store` (LoadUser) ← scheduler, handler/auth, mail
- Python `get_data_root()` (loader) ← config `is_test_user_id`
- Tests-Fixture `tests/tdd/_telegram_live_fixture.py:250` setzt das Flag bereits — bleibt kompatibel

### Assumptions (entschieden, nicht PO-Frage)
- 409-Übergangslösung aus dem Ticket entfällt (würde Projekt-Testkonten am Registrierungspfad blockieren, nutzt der falschen Quelle).
- Prod-Kopfzahl betroffener Nutzer unbekannt; Schwere gilt wegen des Mechanismus.

### Open Questions
- [ ] keine für den PO
