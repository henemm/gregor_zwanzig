---
entity_id: testkonto_profilfeld
type: module
created: 2026-09-17
updated: 2026-09-17
status: draft
version: "1.0"
tags: [testkonto, auth, scheduler, mail, epic-2138]
---

# Testkonto-Status über Profilfeld statt Namens-Heuristik

## Approval

- [ ] Approved

## Purpose

Der Testkonto-Status eines Nutzers wird künftig ausschließlich über ein persistiertes
Profilfeld (`is_test_user`) bestimmt, nicht mehr über eine Namens-Heuristik
(„test"/„tdd"-Substring, case-insensitive). Die Heuristik trifft echte Nutzer mit
solchen Namen (False Positive: kein Versand, kein Adress-Eigentum, Mail über Test-SMTP)
und verfehlt echte Testkonten mit neutralem Namen (False Negative: `admin`,
`validator-issue110`). Einzige feste Ausnahme bleibt die dokumentierte
Telegram-E2E-Fixture-Konstante `tg-live-e2e`.

## Source

- **File:** `internal/model/user.go`, `internal/model/test_user.go`,
  `internal/scheduler/scheduler.go`, `internal/store/address_owner.go`,
  `internal/store/user.go`, `internal/mail/sender.go`, `internal/handler/auth.go`,
  `src/app/config.py`, `src/app/loader.py`
- **Identifier:** `model.User.IsTestUser`, `model.IsTestUserID`, `filterOutTestUsers`,
  `mail.IsTestUser`, `is_test_user_id`, `Settings.with_user_profile`, `list_all_user_ids`

> **Schicht-Hinweis:** Diese Änderung betrifft ZWEI Schichten parallel — Go-API
> (`internal/`, Fan-out/Scheduler/Mail-Routing/Persistenz) UND Python-Core (`src/app/`,
> Kanal-Versand-Credentials/Nutzerliste). Beide Schichten müssen dasselbe Prädikat
> (Profilfeld ODER `tg-live-e2e`) tragen, sonst driften sie erneut auseinander.

## Estimated Scope

- **LoC:** ~+180/-90 (Produktivcode ~90, Tests ~100)
- **Files:** ~16 (8 Go, 3 Python, 4 Tests, 2 Docs)
- **Effort:** medium
- **Hinweis:** `loc_limit_override 500` bei Bedarf setzen — die Arbeit wird NICHT in
  Scheiben geschnitten, da Feld, Prädikat-Ersetzung und alle Leseorte an derselben
  Zusicherung hängen (siehe Technical Approach).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/store` (`LoadUser`/`SaveUser`) | reference-pattern | `filterOutTestUsers` braucht Store-Zugriff, um das Profilfeld zu lesen; `address_owner.go`/`user.go` haben das Profil bereits geladen vorliegen |
| `src/app/loader.py` (`get_data_root`) | dependency | `is_test_user_id` liest das Profil relativ zur konfigurierten Datenwurzel, nicht zu einem hartkodierten Pfad |
| `tests/tdd/_telegram_live_fixture.py:250` | reference-pattern | setzt `is_test_user` bereits als Fixture-Flag — bleibt mit der neuen Prädikat-Semantik kompatibel |
| ADR-0028 (Known Limitation, Zeile 64) | supersedes | wird durch ADR-0072 aus dieser Spec abgelöst |
| `docs/specs/modules/password_reset_mail.md:249` (`IsTestUser`-Substring-Match, akzeptierter False Positive) | supersedes | wird mit dieser Spec revidiert — der akzeptierte False Positive entfällt für alle Konten mit persistiertem Profilfeld |

## Implementation Details

**1. Feld zuerst (`internal/model/user.go`).** Neues Feld `IsTestUser bool` mit
`json:"is_test_user,omitempty"`, analog zu `PremiumSmsReplyAt` (Z. 37-38). Erst danach
verschluckt `SaveUser` (Replace-Semantik) das Feld nicht mehr beim nächsten Speichern
— Daten-Schema-Rework-Regel (BUG-DATALOSS-GR221): Roundtrip-Test Pflicht, Bestandsfelder
bleiben unberührt.

**2. Prädikat ERSETZEN, nicht als Fallback behalten.** `internal/model/test_user.go`:
`IsTestUserID` liest künftig NICHT mehr die Namens-Heuristik, sondern das geladene
Profil-Flag ODER die feste Fixture-Konstante `tg-live-e2e`. Ein Fallback „Heuristik,
wenn Feld fehlt" würde „protester" weiterhin fangen (das Feld fehlt bei ihm ja) — die
Ersetzung muss vollständig sein. `IsTestUserIDSubstringOnly` (bisher exportiert für
`internal/mail`) entfällt oder wird zur reinen Doku-Konstante; `mail.IsTestUser` bekommt
eine neue Signatur, die das geladene `*model.User`/Flag statt eines rohen Namens-Strings
nimmt (Aufrufer `handler/auth.go:371,1225`, `auth_oauth.go:352` laden das Profil vorher).

**3. `filterOutTestUsers` braucht Store-Zugriff.** Aktuell (`scheduler.go:496-500`,
Aufrufer Z. 310) ist die Funktion rein namensbasiert und bekommt nur `allUserIDs`. Sie
muss künftig je ID `s.store.LoadUser(id)` aufrufen und `u.IsTestUser` prüfen (plus
`id == "tg-live-e2e"` als feste Ausnahme) — Signaturänderung, Aufrufer Z. 310 übergibt
den Store.

**4. Bereits geladenes Profil wiederverwenden.** `internal/store/address_owner.go:53`
(`forEachRealAccount`) und `internal/store/user.go:482`
(`FindUserByTelegramChatID`) laden `u` bereits, bevor sie aktuell `model.IsTestUserID(id)`
gegen die rohe ID prüfen — dort wird auf `u.IsTestUser` umgestellt, keine zusätzliche
Ladeoperation nötig.

**5. Flag bei Anlage setzen.** `internal/handler/auth.go` Register-Handler akzeptiert ein
optionales Request-Feld `is_test_user` und persistiert es beim Anlegen. Ohne dieses
Setzen an der Anlagestelle reißt der Schutz bei jedem neuen Testkonto erneut (die
False-Negative-Richtung aus ADR-0028). `scripts/setup-validator-user.sh:20-23` und
`frontend/e2e/global.setup.ts` werden entsprechend ergänzt, damit `validator-issue110`
und die Playwright-Testkonten (`admin` u.a.) das Feld beim Anlegen mitbekommen.

**6. Python-Seite (`src/app/config.py:56-78`, `380`).** `is_test_user_id` verliert die
„test"/„tdd"-Substring-Prüfung; übrig bleiben die feste Konstante `tg-live-e2e` und das
Profilfeld-Lesen (das existiert dort bereits, Z. 74). Der Wrapper `_is_test_user` (Z.
378-380) und darüber `with_user_profile` (Aufrufer der Weiche `force_test`) bleiben
strukturell unverändert — nur die Quelle der Wahrheit wird enger. Der Lesepfad nutzt
weiterhin `get_data_dir(user_id)` (respektiert Testisolation, Issue #1265), keine
hartkodierte Wurzel.

**7. `src/app/loader.py:1209-1211` (`list_all_user_ids`).** Der zusätzliche
`not d.name.startswith("test")`-Vorfilter vor dem eigentlichen `is_test_user_id`-Split
entfällt — er blendet Konten wie „testarossa" bereits beim Verzeichnis-Listing aus,
bevor das Prädikat überhaupt greift, und widerspricht damit derselben Regel, die diese
Spec für die Heuristik durchsetzt.

**8. Bestehende Tests auf Flag-Semantik umstellen.** `internal/mail/sender_test.go`
(`TestIsTestUser_Boundary`, dokumentiert aktuell `IsTestUser("contest") == true` als
gewollten False Positive — entfällt), `internal/mail/sender_allowlist_test.go:215-254`,
`tests/tdd/test_issue_1013_telegram_test_isolation.py:180-260`,
`tests/tdd/test_telegram_chat_id_ownership.py:216-217` pinnen aktuell die
Substring-Heuristik fest und müssen auf das Flag umgestellt werden — sonst bleibt ein
grüner Testlauf, der die alte, jetzt falsche Erwartung weiter bewacht.

**9. Kein Migrations-Skript.** Staging trägt aktuell `default`, `tg-live-e2e`,
`validator-issue110`; nur `tg-live-e2e` braucht Testkonto-Status und bleibt Konstante.
`migrate_1257`/`migrate_1258` sind One-Shot-CLIs, kein Startup-Muster — hier nicht
reaktiviert. Der Prod-Bestand ist für diese Sitzung nicht lesbar; im Deploy-Schritt wird
die Nutzer-ID-Liste gegen die alte Heuristik geprüft und nur bei echtem Treffer ein
Feld einmalig per Datei nachgetragen.

## Expected Behavior

- **Input:** Ein Nutzerkonto mit beliebigem Namen, optional mit persistiertem
  `is_test_user: true` im Profil, oder die feste ID `tg-live-e2e`.
- **Output:** Genau die Konten mit gesetztem Flag oder der ID `tg-live-e2e` werden vom
  Scheduler-Fan-out übersprungen, laufen im Mail-Versand über Test-SMTP/Test-Postfach
  und werden aus `forEachRealAccount`/`FindUserByTelegramChatID`/Adress-Lookup
  ausgeschlossen. Alle anderen Konten — unabhängig vom Namen — laufen den vollen
  Produktivpfad.
- **Side effects:** `POST /api/auth/register` mit `is_test_user: true` schreibt das
  Feld dauerhaft in `user.json`; `list_all_user_ids` sortiert weiterhin reale Nutzer vor
  Testkonten, jetzt aber ohne den zusätzlichen Namens-Vorfilter.

## Acceptance Criteria

- **AC-1:** Given ein Nutzerkonto mit der ID „protester" ohne `is_test_user`-Feld im
  Profil / When der Go-Scheduler den nächsten Fan-out-Lauf durchführt / Then wird
  „protester" NICHT aus der Nutzerliste gefiltert, sondern regulär bedient.
  - Test: `internal/scheduler/test_user_flag_scheduler_test.go` → prüft
    `filterOutTestUsers` mit echtem Store (`store.LoadUser`), nicht isoliert gegen die
    reine ID-Liste — der bisherige Aufruf ohne Store-Zugriff deckt diesen Pfad nicht ab

- **AC-2:** Given ein Nutzerkonto „protester" ohne `is_test_user`-Feld / When
  `Settings.with_user_profile("protester")` aufgerufen wird / Then liefert die
  zurückgegebene `Settings`-Instanz die Produktiv-Credentials (Resend-SMTP), nicht die
  Test-Credentials aus `for_testing()`.
  - Test: `tests/tdd/test_settings_test_user_flag_routing.py` → ruft
    `with_user_profile("protester")` gegen ein Fixture-Profil ohne Flag auf und prüft
    `is_test_mode is False` / SMTP-Host entspricht dem Prod-Wert

- **AC-3:** Given ein Nutzerkonto mit neutralem Namen (z. B. „mitarbeiter42") und
  `is_test_user: true` im Profil / When der Go-Scheduler den Fan-out-Lauf durchführt /
  Then wird dieses Konto übersprungen, obwohl der Name keine Test-Substring enthält.
  - Test: `internal/scheduler/test_user_flag_scheduler_test.go` → Gegenprobe zu AC-1 mit
    gesetztem Flag

- **AC-4:** Given dasselbe Konto „mitarbeiter42" mit `is_test_user: true` / When
  `Settings.with_user_profile("mitarbeiter42")` aufgerufen wird / Then werden die
  Stalwart-Test-Credentials verwendet.
  - Test: `tests/tdd/test_settings_test_user_flag_routing.py` → Gegenprobe zu AC-2

- **AC-5:** Given die feste Fixture-ID „tg-live-e2e" ohne gesetztes Profilfeld / When
  Go-`IsTestUserID` bzw. Python-`is_test_user_id` aufgerufen werden / Then liefern beide
  weiterhin `true`, unverändert gegenüber dem bisherigen Verhalten.
  - Test: `internal/model/test_user_test.go` (neue/erweiterte Datei) und
    `tests/tdd/test_is_test_user_id_fixture_constant.py` → `tg-live-e2e` bleibt
    Testkonto ohne Flag

- **AC-6:** Given ein Passwort-Reset für den Nutzer „protester" (kein `is_test_user`-Flag)
  / When die Reset-Mail versendet wird / Then läuft der Versand über die
  Resend-Konfiguration (Produktiv-SMTP), nicht über Gmail/Test-SMTP.
  - Test: `internal/mail/sender_test.go` → `TestIsTestUser_Boundary` wird ersetzt durch
    einen Test, der ein `*model.User{ID: "protester"}` ohne Flag gegen die neue
    `mail.IsTestUser`-Signatur prüft und `false` erwartet

- **AC-7:** Given der Nutzer „protester" hat eine Kontaktadresse und eine
  Telegram-Chat-ID hinterlegt, ohne `is_test_user`-Flag / When
  `forEachRealAccount`/`ResolveAddressOwner` bzw. `FindUserByTelegramChatID` laufen /
  Then wird „protester" als Adress-Eigentümer erkannt bzw. per Chat-ID gefunden.
  - Test: `internal/store/address_owner_test.go` und `internal/store/user_test.go`
    (erweitert) → Konto mit Test-Substring im Namen, aber ohne Flag, wird NICHT
    übersprungen

- **AC-8:** Given `POST /api/auth/register` mit `"is_test_user": true` im Request-Body
  / When die Registrierung verarbeitet wird / Then enthält die gespeicherte `user.json`
  das Feld `is_test_user: true`; bei fehlendem Feld im Request ist es `false` oder
  abwesend. Ein anschließendes `LoadUser`/`SaveUser`-Roundtrip erhält das Feld UND alle
  übrigen Profilfelder unverändert.
  - Test: `internal/handler/auth_test.go` (erweitert) → Registrierung mit und ohne
    `is_test_user`, gefolgt von einem Vorher/Nachher-Vergleich aller Nachbarfelder nach
    einem `SaveUser`-Roundtrip (Muster `passkey_angebot_banner.md` AC-6)

- **AC-9:** Given ein Datenverzeichnis mit einem Konto „testarossa" (Name beginnt mit
  „test", aber ohne Flag) / When `list_all_user_ids()` aufgerufen wird / Then erscheint
  „testarossa" in der zurückgegebenen Liste (kein Ausschluss mehr durch den
  `startswith("test")`-Vorfilter).
  - Test: `tests/tdd/test_list_all_user_ids_no_name_prefix_filter.py` → Verzeichnis mit
    „testarossa" ohne Flag, Assertion dass die ID in der Rückgabe enthalten ist

- **AC-10:** Given die bestehenden Tests, die die Namens-Heuristik festpinnen
  (`internal/mail/sender_allowlist_test.go:215-254`,
  `tests/tdd/test_issue_1013_telegram_test_isolation.py:180-260`,
  `tests/tdd/test_telegram_chat_id_ownership.py:216-217`) / When die Testsuite nach der
  Umstellung läuft / Then erwarten diese Tests Flag-Semantik statt Namens-Substring und
  sind grün.
  - Test: dieselben Dateien, inhaltlich umgestellt (kein neuer Dateiname) — Nachweis via
    `uv run pytest tests/tdd/test_issue_1013_telegram_test_isolation.py
    tests/tdd/test_telegram_chat_id_ownership.py` und
    `go test ./internal/mail/... -run TestSenderAllowlist`

## Known Limitations

- Der Prod-Bestand ist für diese Sitzung nicht lesbar. Die Gegenprüfung (welche
  Prod-Konten der alten Heuristik entsprächen und nachträglich ein Flag bräuchten)
  erfolgt im Deploy-Schritt anhand der Nutzer-ID-Liste, nicht vorab in dieser Spec.
- Keine Migration: Es gibt kein Startup-Skript, das Bestandskonten automatisch mit dem
  Feld nachrüstet. Ein Konto, das bislang zufällig über die Heuristik als Testkonto lief
  (Namens-Substring) und weiterhin so behandelt werden soll, braucht das Flag manuell
  nachgetragen — sonst kippt es beim Deploy von „übersprungen" auf „bedient".
  `tg-live-e2e` ist die einzige Ausnahme, die als Konstante weiterhin ohne Flag greift.
- Die 409-Übergangslösung aus dem Ticket wird bewusst NICHT umgesetzt — sie würde
  Projekt-Testkonten am Registrierungspfad blockieren und griffe auf der falschen
  Quelle (Namen statt Flag).
- `internal/mail/sender_allowlist_test.go`, die beiden Python-Telegram-Tests und
  `TestIsTestUser_Boundary` ändern ihre dokumentierte Erwartung von „Substring-Match ist
  ein akzeptierter False Positive" zu „nur das Flag bzw. `tg-live-e2e` entscheiden" —
  das ist eine bewusste Verhaltensänderung, kein Kollateralschaden.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0072 (wird in der Implementierung angelegt, nicht in dieser Spec)
- **Rationale:** ADR-0072 „Testkonto-Status ausschließlich über Profilfeld" löst die in
  ADR-0028 (Zeile 64) dokumentierte Known Limitation ab, wonach `IsTestUserID` das
  Profil-Flag bewusst nicht liest. Zusätzlich revidiert diese Spec den in
  `docs/specs/modules/password_reset_mail.md:249` als akzeptiert dokumentierten False
  Positive der Substring-Heuristik — beide bisherigen Festlegungen werden durch diese
  Spec bewusst abgelöst, nicht stillschweigend überschrieben.

## Changelog

- 2026-09-17: Initial spec created (#2152)
- 2026-09-18: Implementiert (#2152)
