# Context: feat-2830-staging-mail-pruefen-lang-en

## Request Summary
`.claude/tools/staging_mail_pruefen.py` kann Trip- und Compare-Mail nur mit dem deutschen Wegwerf-Nutzer
zustellen und prüfen. `staging_gate.py --write-verdict` verlangt aber `--langs de,en` (#2681). Gewünscht:
Option `--lang en`, die den vorhandenen Staging-Nutzer `en` nutzt. Auslöser: #1563 steckt davor fest.

## Related Files
| File | Relevance |
|------|-----------|
| `.claude/tools/staging_mail_pruefen.py` (389 Z.) | Zu ändern: `_argumente`, `main`, `fuehre_lauf`, `_raeume_auf`, `baue_validator_aufruf` |
| `.claude/tools/staging_befehl_pruefen.py` | Vorbild/Basis: `StagingApi.registriere` (Wegwerf-Nutzer), `loesche_nutzer`, `baue_plus_adresse`, `baue_tag` |
| `scripts/staging_e2e_user_en.py` | Stellt den Nutzer `en` sicher; `EnApi.anmelden(nutzer, passwort)` ist die Anmeldung mit `GZ_E2E_EN_USER`/`GZ_E2E_EN_PASS` |
| `.claude/hooks/_e2e_paths.py` | `EN_SUBADRESSE = "+en@"`, `mail_waehlbar`: en-Mail nur wählbar, wenn To `+en@` enthält |
| `.claude/hooks/email_spec_validator.py`, `briefing_mail_validator.py` | Nehmen `--lang` und `--to-contains` bereits an |
| `tests/tdd/test_staging_mail_pruefweg.py` (769 Z.) | Bestehende Tests mit Ersatz-Staging (`_Staging`), müssen grün bleiben |
| `docs/runbooks/staging_e2e_nutzer_en.md` | Runbook zum Nutzer `en`, ggf. um den Aufruf ergänzen |
| `docs/specs/modules/fix_2774_staging_mailweg.md` | Spec des bestehenden Werkzeugs |

## Existing Patterns
- Netzrand und Validator-Runner sind injizierbar, Tests laufen gegen ein Ersatz-Staging ohne Mocks.
- Betreff-Marker `GZM <tag>` macht jede Mail eindeutig (`--subject-contains`).
- Aufräumen im `finally`; nur selbst angelegte Objekte werden gelöscht.

## Wichtige Erkenntnis (bestimmt das Design)
Ein Wegwerf-Nutzer reicht für Englisch **nicht**: `_empfaenger_passt` lässt eine en-Mail nur zu, wenn die
Empfängeradresse genau `+en@` enthält. Das ist die Adresse `gregor-test+en@henemm.com`, und die gehört
bereits dem festen Staging-Nutzer `en`. Also muss das Werkzeug bei `--lang en` **diesen** Nutzer anmelden,
Trip bzw. Orte und Preset darunter anlegen, senden, mit `--lang en --to-contains "+en@"` validieren und
**nur die selbst angelegten Objekte** löschen. Der Nutzer `en` selbst darf nie gelöscht werden
(`loesche_nutzer` muss bei `en` entfallen).

## Dependencies
- Upstream: Staging-`.env` mit `GZ_E2E_EN_USER`, `GZ_E2E_EN_PASS`, `GZ_E2E_EN_MAIL` (Werte nie ausgeben),
  Kern-Secret `GZ_CORE_SHARED_SECRET`, IMAP-Zugang.
- Downstream: `/e2e-verify` Schritt 3b (Skill-Text nennt das Werkzeug nur mit `--typ`), Deploy-Gate über
  `staging_gate.py --langs de,en`.

## Risks & Considerations
- Der Nutzer `en` darf durch einen Fehler beim Aufräumen nie gelöscht werden (Test mit Gegenprobe).
- Trip-Kontingent (Tarif free: 3 Trips): übrig gebliebene Trips des Nutzers `en` würden spätere Läufe blockieren.
- Reste eines abgebrochenen Laufs müssen mit Kennung gemeldet werden, wie beim Wegwerf-Nutzer.
- Ausgaben dürfen keine Zugangsdaten enthalten (bestehender Test `test_ausgaben_enthalten_keine_geheimnisse`).
- Fehlen die `GZ_E2E_EN_*`-Werte: Exit 2 vor jeder Änderung.
- Der Vertretungshinweis selbst (#1563) bleibt auch danach nur per Unit-Test belegt; diese Arbeit schließt
  nur die Sprachlücke im Nachweis.

## Analysis

### Type
Feature (Werkzeug-Erweiterung, kein Produktcode)

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `.claude/tools/staging_mail_pruefen.py` | MODIFY | `--lang de\|en` (Default `de`); `baue_validator_aufruf(..., lang)` hängt bei `en` `--lang en --to-contains "+en@"` an; neue Klasse `EnMailApi(MailApi)` mit `melde_an(user, pass)` (Login statt Registrierung) und `loesche_nutzer()` als No-op; `fuehre_lauf` verzweigt Anmeldung (de: `registriere`, en: `melde_an`) und Aufräum-Meldung; `main` liest `GZ_E2E_EN_USER/PASS`, Exit 2 vor jeder Änderung wenn sie fehlen |
| `tests/tdd/test_staging_mail_pruefweg.py` | MODIFY | Neue Tests gegen Ersatz-Staging: en-Lauf meldet an statt zu registrieren; Validator-Aufruf mit `--lang en --to-contains +en@`; Nutzer `en` wird nie gelöscht (auch bei Aufräum-Fehler); nur eigene Objekte gelöscht; fehlende `GZ_E2E_EN_*` ⇒ Exit 2 ohne Netzzugriff; Login scheitert ⇒ Exit 2; keine Geheimnisse in Ausgaben; de-Verhalten unverändert |
| `docs/runbooks/staging_e2e_nutzer_en.md` | MODIFY | Aufruf `--lang en` ergänzen |
| Skill/Befehl `e2e-verify` Schritt 3b | MODIFY (prüfen) | Hinweis auf `--lang en`, damit `staging_gate.py --langs de,en` erreichbar wird |
| `docs/specs/modules/fix_2774_staging_mailweg.md` | MODIFY | Spec um den en-Pfad erweitern (Entscheidung in /30) |

### Scope Assessment
- Files: 3–4
- Estimated LoC: +~90 Werkzeug / +~150 Tests / +~10 Doku
- Risk Level: LOW (Dev-Werkzeug, kein Laufzeitcode). Einziges echtes Risiko: Nutzer `en` versehentlich löschen ⇒ No-op in eigener Unterklasse + Gegenprobe-Test.

### Technical Approach
- Ein Wegwerf-Nutzer reicht nicht (`_empfaenger_passt` verlangt `+en@`, Adresse gehört dem festen Nutzer `en`). Bei `--lang en`: Login mit `GZ_E2E_EN_USER/PASS`, Trip bzw. Orte+Preset darunter anlegen, senden, Validator mit `--lang en --to-contains "+en@"`, danach nur selbst angelegte Objekte löschen.
- `loesche_nutzer` bei `en` strukturell No-op (eigene Unterklasse statt Flag), kein Weg zu `/api/auth/account/delete` mit dem en-Passwort.
- Reste-Meldung mit Objekt-Kennungen wie beim Wegwerf-Nutzer; Trip-Kontingent (free: 3) bleibt geschützt, da Trips im `finally` gelöscht werden.
- Netzrand/Validator-Runner bleiben injizierbar ⇒ Tests ohne Mocks gegen Ersatz-Staging.
- Der Vertretungshinweis (#1563) bleibt per Unit-Test belegt; dieses Ticket schließt nur die Sprachlücke im Nachweis.

### Dependencies
- Upstream: Staging-`.env` (`GZ_E2E_EN_*`, `GZ_CORE_SHARED_SECRET`, IMAP), `scripts/staging_e2e_user_en.py`.
- Downstream: `staging_gate.py --write-verdict --langs de,en`, `/e2e-verify` 3b; #1563 wartet darauf.

### Open Questions
- [ ] Spec erweitern oder neue Spec? (Empfehlung: `fix_2774_staging_mailweg.md` erweitern, ein Werkzeug)
- [ ] `--lang` nur einzeln, kein `de,en` in einem Lauf (Empfehlung: zwei Aufrufe, Gate fasst je Sprache zusammen)
