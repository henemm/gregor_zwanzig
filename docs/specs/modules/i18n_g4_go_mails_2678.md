---
entity_id: i18n_g4_go_mails_2678
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2678, go, e2e, model-haiku]
---

# i18n G4: Konto- und Transaktions-Mails der Go-API zweisprachig (Katalogschlüssel je Zeile, Marker X-GZ-Lang)

**Issue:** #2678 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2, 5, 6

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer sich mit Sprache `en` registriert, sein Passwort zurücksetzt, einen Einmalcode anfordert, sein Konto löschen will oder Google mit seinem Konto verknüpft, bekommt die zugehörige Mail auf Englisch; Nutzer mit `de` oder ohne Einstellung bekommen sie unverändert auf Deutsch (byte-gleich). Jede von Go versandte Mail trägt den Header `X-GZ-Lang`, damit Prüfwerkzeuge die Sprache erkennen. Die Mail an den Betreiber beim Level-Antrag bleibt deutsch.

## Source

- **File:** `internal/mail/{sender,verify,reset,magic,tier_change}.go`, `internal/handler/{auth,auth_magic,auth_oauth,account_delete_code}.go`, `internal/i18n/messages/{de,en}/mail.json`
- **Identifier:** `mail.Mail`, `dialAndSend`, `BuildVerificationMail`, `BuildResetMail`, `BuildMagicLinkMail`, `BuildTierChangeRequestMail`, `buildDeleteCodeMail`, `sendDeleteCodeMail`, `buildGoogleLinkNoticeMail`, `sendGoogleLinkNotice`, `dispatchVerificationMail`

> **Schicht-Hinweis:** Go-API (`internal/mail`, `internal/handler`). Kein Python-Code (Briefing-, Alarm- und Vergleichs-Mails sind P2 bis P6) und kein Frontend-Code.
>
> **Abweichung von der Issue-Liste, belegt per Messung:** (1) Zwei Nutzer-Mails werden nicht in `internal/mail` gebaut, sondern im Handler: `buildDeleteCodeMail` (`account_delete_code.go:131`) und `buildGoogleLinkNoticeMail` (`auth_oauth.go:334`); sie gehören zu diesem Paket. (2) `internal/notify/mq.go` ist die Nachrichtenleitung zwischen Entwicklungs-Instanzen (`claude-mq`), enthält keinen Nutzertext und bleibt unverändert. (3) `internal/scheduler/scheduler.go` versendet nur Betriebs-Meldungen an den Betreiber (Heartbeat, Laufbudget, Erholungs-Hinweise) über `notify.SendMQ`, keine Mail an Nutzer; diese deutschen Texte sind Betreiber-Texte und bleiben, der Wächter (G5) prüft das Verzeichnis nicht. (4) Eine „Einladungs-Mail" gibt es nicht: Einladungen erzeugen einen Link (`admin_invites.go`), den der Admin selbst weitergibt. (5) Die SMS-Bestätigungs-Nachricht (`sms_verify.go`) entsteht im Python-Core und ist nicht Teil dieses Pakets.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht betroffen, Konto-Mails kennen weder Trip noch Ortsvergleich.
> - **Mandantentrennung:** Die Sprache ist die des **Empfänger-Nutzers** (`i18n.Parse(user.Language)`, leer = `de`), nie die einer globalen Variable und nie die Sprache einer fremden Anfrage; zwei Nutzer mit verschiedenen Sprachen im selben Prozess (AC-4).
> - **Kanäle:** Alle Mails dieses Pakets sind Konto-Mails und laufen nur über E-Mail. Briefing- und Alarm-Inhalte (E-Mail, Telegram, SMS, Premium-SMS) sind nicht berührt und bleiben unverändert.

### Affected Files

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| `internal/mail/sender.go` | MODIFY | `Mail` bekommt `Lang i18n.Lang`; der MIME-Aufbau aus `dialAndSend` (Zeilen 510-534) wird in `buildPayload(from, to, boundary string, msg Mail) []byte` ausgelagert (testbar) und schreibt `X-GZ-Lang: <lang>` (leer = `de`) nach `MIME-Version` |
| `internal/mail/verify.go` | MODIFY | `BuildVerificationMail(lang i18n.Lang, publicHost, userID, token string)` |
| `internal/mail/reset.go` | MODIFY | `BuildResetMail(lang i18n.Lang, publicHost, username, token string)` |
| `internal/mail/magic.go` | MODIFY | `BuildMagicLinkMail(lang i18n.Lang, code string)` |
| `internal/mail/tier_change.go` | MODIFY | Betreiber-Mail bleibt deutsch: Funktionskommentar mit `// i18n-log` (Betreiber-Text, ADR-0104), `Lang: i18n.De` im Rückgabewert; Signatur unverändert |
| `internal/handler/account_delete_code.go` | MODIFY | `buildDeleteCodeMail(lang, code)`, `sendDeleteCodeMail(cfg, lang, to, code)`; `RequestDeleteCodeHandler` übergibt `i18n.Parse(user.Language)` |
| `internal/handler/auth_oauth.go` | MODIFY | `buildGoogleLinkNoticeMail(lang)`; `sendGoogleLinkNotice` übergibt die Sprache aus dem geladenen `user` |
| `internal/handler/auth.go` | MODIFY | Aufrufer: Zeile 530 `BuildResetMail`, Zeile 1574 `BuildVerificationMail` (Sprache aus dem geladenen `user`), Zeile 1817 `BuildTierChangeRequestMail` unverändert |
| `internal/handler/auth_magic.go` | MODIFY | Zeile 123: `lang := i18n.FromContext(r.Context())` (Anfragesprache, siehe Known Limitations) |
| `internal/i18n/messages/de/mail.json`, `internal/i18n/messages/en/mail.json` | MODIFY | Schlüssel `mail.*` aller fünf Nutzer-Mails (Tabellen unten) |
| `internal/mail/testdata/golden/{verify,reset,magic}.{de,en}.{txt,html}` | CREATE | 12 Golden-Dateien: heutige deutsche Ausgabe (vor der Umstellung erzeugt) und englische Ausgabe als Review-Hilfe |
| `internal/handler/testdata/golden/{delete_code,google_link}.{de,en}.{txt,html}` | CREATE | 8 Golden-Dateien für die zwei Handler-Mails |
| `internal/mail/konto_mails_zweisprachig_test.go` | CREATE | Tests zu AC-2, AC-6, AC-7 (Golden, Header, Katalog) |
| `internal/handler/konto_mails_sprache_test.go` | CREATE | Tests zu AC-1, AC-3, AC-4, AC-5, AC-6 |
| `internal/mail/sender_test.go`, `sender_integration_test.go`, `tier_change_test.go`, weitere Bestandstests mit den vier Builder-Aufrufen | MODIFY | mechanisch: neues erstes Argument `i18n.De` |

## Estimated Scope

- **LoC:** ca. 190 geänderte oder neue Code-Zeilen ohne Katalogdaten (ca. 150 Zeilen JSON je Sprache) und ohne Tests. Unter dem Limit von 250.
- **Files:** 9 Code-Dateien, 2 Katalogdateien, 20 Golden-Dateien, 2 neue Testdateien, Bestandstests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2675 (G1) | Paket | `internal/i18n` (`T`, `Parse`, `FromContext`), leere `mail.json` (Voraussetzung) |
| #2646 (S1) | Paket | `model.User.Language`; Registrierung speichert die mitgesandte Sprache, bevor die Bestätigungs-Mail gebaut wird |
| #2663 (PV) | Paket | Marker `X-GZ-Lang` ist dort für die Python-Mails festgelegt; Go setzt denselben Header (Abschnitt 4 der Konventionen) |
| #2679 (G5) | Paket | Wächter; Allowlist-Einträge der Mail-Dateien werden entfernt |
| `internal/mail` | Modul | Mail-Typ, Versand mit Empfängerschutz (unverändert) |
| `docs/reference/i18n_glossar.md` | Doku | bindende Wortwahl und Verbotsliste |
| ADR-0104 | ADR | Sprache am Nutzer, Admin-Mails an den Betreiber bleiben deutsch |

## Implementation Details

**Technik-Entscheidung (Issue verlangt Begründung): Schlüssel je Zeile, keine `text/template` je Sprache.** Gründe: ein einheitlicher Paritätstest für alle Kataloge (G1), kein zweiter Template-Mechanismus, und die heutigen Mails sind kurze Zeilenfolgen mit `fmt.Sprintf`. Die HTML-Gerüste (Tags, Style) bleiben im Go-Code; der Katalog trägt nur Satztext.

**Schlüsselschema.** `mail.<art>.betreff`, `mail.<art>.plain.z<n>` (Reihenfolge im Klartext-Body) und `mail.<art>.html.z<n>`; `<art>` ∈ `verify`, `reset`, `magic`, `delete`, `google_link`. Der Klartext- und der HTML-Teil haben **eigene** Schlüssel, weil die heutigen Texte sich unterscheiden (Klartext teils mit ae/ue-Umschrift, HTML mit Entities `&auml;` …, `magic` im Klartext mit echten Umlauten). Die deutschen HTML-Werte enthalten die Entities **wörtlich wie heute**, aber keine Tags; die englischen Werte enthalten weder Tags noch Entities (außer den Anführungszeichen-Entities in `google_link`). Hervorgehobene Satzteile (`<strong>`) werden als eigener Schlüssel (`…html.betont`, `…html.dauer`) übersetzt und als Platzhalter (`{betont}`, `{dauer}`) in den Satz eingesetzt; die Tags setzt der Go-Code.

**Zusammenbau, byte-gleich zum heutigen Klartext** (am Beispiel `verify`, `verify.go:15-20`), vorher:

```go
plain := fmt.Sprintf(
	"Hallo,\n\nBitte bestaetige deine neue E-Mail-Adresse fuer Gregor 20.\n\n"+
		"Oeffne diesen Link, um die Bestaetigung abzuschliessen (gueltig 24 Stunden):\n\n%s\n\n"+
		"Falls du das nicht angefordert hast, ignoriere diese E-Mail.\n", link)
```

nachher:

```go
t := func(k string) string { return i18n.T(lang, "mail.verify.plain."+k, nil) }
plain := t("z1") + "\n\n" + t("z2") + "\n\n" + t("z3") + "\n\n" + link + "\n\n" + t("z4") + "\n"
```

Der Rückgabewert trägt `Lang: lang`. Die Links (`link`) und der Code werden wie heute unverändert eingesetzt, nicht durch `T`; ein Code im Satz (`{code}`) geht als Argument an `T`.

**Katalog `verify` (de | en)**, vollständig:

| Schlüssel | de | en |
|---|---|---|
| `mail.verify.betreff` | Bestätige deine E-Mail-Adresse für Gregor 20 | Confirm your email address for Gregor 20 |
| `mail.verify.plain.z1` | Hallo, | Hello, |
| `mail.verify.plain.z2` | Bitte bestaetige deine neue E-Mail-Adresse fuer Gregor 20. | Please confirm your new email address for Gregor 20. |
| `mail.verify.plain.z3` | Oeffne diesen Link, um die Bestaetigung abzuschliessen (gueltig 24 Stunden): | Open this link to complete the confirmation (valid for 24 hours): |
| `mail.verify.plain.z4` | Falls du das nicht angefordert hast, ignoriere diese E-Mail. | If you did not request this, ignore this email. |
| `mail.verify.html.z1` | Hallo, | Hello, |
| `mail.verify.html.z2` | Bitte best&auml;tige deine neue E-Mail-Adresse f&uuml;r Gregor 20. | Please confirm your new email address for Gregor 20. |
| `mail.verify.html.z3` | E-Mail best&auml;tigen | Confirm email |
| `mail.verify.html.z4` | Der Link ist 24 Stunden g&uuml;ltig. | The link is valid for 24 hours. |
| `mail.verify.html.z5` | Oder kopiere diesen Link in den Browser: | Or copy this link into your browser: |
| `mail.verify.html.z6` | Falls du das nicht angefordert hast, ignoriere diese E-Mail. | If you did not request this, ignore this email. |

**Katalog `reset`** (Zusammenbau Klartext: `z1 \n\n z2 \n\n z3 \n\n link \n\n z4 \n`; HTML wie `verify` mit Knopf `z3`, Gültigkeit `z4`, Kopierhinweis `z5`, Fußzeile `z6`):

| Schlüssel | de | en |
|---|---|---|
| `mail.reset.betreff` | Gregor 20 — Passwort zuruecksetzen | Gregor 20 — Reset your password |
| `mail.reset.plain.z2` | Du hast eine Passwort-Zuruecksetzung fuer Gregor 20 angefordert. | You requested a password reset for Gregor 20. |
| `mail.reset.plain.z3` | Oeffne diesen Link, um ein neues Passwort zu setzen (gueltig 30 Minuten): | Open this link to set a new password (valid for 30 minutes): |
| `mail.reset.html.z2` | Du hast eine Passwort-Zur&uuml;cksetzung f&uuml;r Gregor 20 angefordert. | You requested a password reset for Gregor 20. |
| `mail.reset.html.z3` | Neues Passwort setzen | Set new password |
| `mail.reset.html.z4` | Der Link ist 30 Minuten g&uuml;ltig. | The link is valid for 30 minutes. |

`plain.z1`/`z4` und `html.z1`/`z5`/`z6` lauten wie bei `verify` (eigene Schlüssel `mail.reset.…`, gleiche Texte).

**Katalog `magic`** (Klartext: `z1 \n\n z2 \n\n z3 \n z4 \n\n z5 \n`, `{code}` in `z2`; HTML: `z2` mit `{betont}` = `<strong>Gregor 20</strong>`, `z3` mit `{dauer}` = `<strong>` + `html.dauer` + `</strong>`):

| Schlüssel | de | en |
|---|---|---|
| `mail.magic.betreff` | Gregor 20 — Dein Einmalcode | Gregor 20 — Your one-time code |
| `mail.magic.plain.z2` | Dein Einmalcode für Gregor 20: {code} | Your one-time code for Gregor 20: {code} |
| `mail.magic.plain.z3` | Der Code ist 15 Minuten gültig. | The code is valid for 15 minutes. |
| `mail.magic.plain.z4` | Gib ihn auf der Anmeldeseite ein. | Enter it on the sign-in page. |
| `mail.magic.plain.z5` | Falls du diesen Code nicht angefordert hast, ignoriere diese E-Mail. | If you did not request this code, ignore this email. |
| `mail.magic.html.z2` | Dein Einmalcode f&uuml;r {betont}: | Your one-time code for {betont}: |
| `mail.magic.html.z3` | Der Code ist {dauer} g&uuml;ltig. | The code is valid for {dauer}. |
| `mail.magic.html.dauer` | 15 Minuten | 15 minutes |

**Katalog `delete`** (Klartext `z1 \n\n z2 \n\n z3 \n\n z4 \n`; `{code}` in `z2`; die HTML-Fußzeile ist kürzer als die Klartext-Fußzeile, daher eigene Schlüssel; HTML-`z3` setzt `{betont}` = `<strong>` + `html.betont` + `</strong>`):

| Schlüssel | de | en |
|---|---|---|
| `mail.delete.betreff` | Gregor 20 — Dein Lösch-Code | Gregor 20 — Your deletion code |
| `mail.delete.plain.z2` | Dein Lösch-Code für Gregor 20: {code} | Your deletion code for Gregor 20: {code} |
| `mail.delete.plain.z3` | Mit diesem Code wird dein Konto unwiderruflich gelöscht. Der Code ist 15 Minuten gültig. | This code permanently deletes your account. The code is valid for 15 minutes. |
| `mail.delete.plain.z4` | Falls du die Löschung nicht angefordert hast, ignoriere diese E-Mail und ändere dein Passwort — jemand hat Zugriff auf eine deiner Anmeldungen. | If you did not request the deletion, ignore this email and change your password — someone has access to one of your sign-ins. |
| `mail.delete.html.z3` | Mit diesem Code wird dein Konto {betont}. Der Code ist 15 Minuten g&uuml;ltig. | This code {betont}. The code is valid for 15 minutes. |
| `mail.delete.html.betont` | unwiderruflich gel&ouml;scht | permanently deletes your account |
| `mail.delete.html.z4` | Falls du die L&ouml;schung nicht angefordert hast, ignoriere diese E-Mail und &auml;ndere dein Passwort. | If you did not request the deletion, ignore this email and change your password. |

`html.z1` (`Hallo,`) und `html.z2` (`Dein L&ouml;sch-Code f&uuml;r {betont}:` | `Your deletion code for {betont}:`, `{betont}` = `<strong>Gregor 20</strong>`) ergänzen den HTML-Teil; der Code selbst steht wie heute in einem eigenen Absatz.

**Katalog `google_link`** (Klartext `z1 \n\n z2 \n\n z3 \n`):

| Schlüssel | de | en |
|---|---|---|
| `mail.google_link.betreff` | Google-Anmeldung mit deinem Gregor-20-Konto verknüpft | Google sign-in linked to your Gregor 20 account |
| `mail.google_link.plain.z2` | dein Gregor-20-Konto wurde soeben mit einer Google-Anmeldung verknuepft. Du kannst dich ab jetzt auch mit "Mit Google anmelden" anmelden. | Your Gregor 20 account was just linked to a Google sign-in. From now on you can also sign in with "Sign in with Google". |
| `mail.google_link.plain.z3` | Warst du das nicht, melde dich bitte umgehend bei uns. | If this wasn't you, please contact us right away. |
| `mail.google_link.html.z2` | dein Gregor-20-Konto wurde soeben mit einer Google-Anmeldung verkn&uuml;pft. Du kannst dich ab jetzt auch mit &bdquo;Mit Google anmelden&ldquo; anmelden. | Your Gregor 20 account was just linked to a Google sign-in. From now on you can also sign in with &ldquo;Sign in with Google&rdquo;. |
| `mail.google_link.html.z3` | Warst du das nicht, melde dich bitte umgehend bei uns. | If this wasn't you, please contact us right away. |

**Header.** `buildPayload` schreibt `X-GZ-Lang: de|en`. Auch die Betreiber-Mail trägt `X-GZ-Lang: de`. Der Header wird nach dem Muster der Python-Mails (PV) gesetzt; die vier Mail-Validatoren prüfen diese Go-Mails nicht (sie prüfen Briefing-, Vergleichs-, Warn- und Radar-Mails).

**Empfängersprache.** Verifikation und Reset: `i18n.Parse(user.Language)` des **geladenen** Empfänger-Nutzers (leer = `de`; nicht die Anfragesprache). Lösch-Code und Google-Hinweis: Sprache des angemeldeten Nutzers `user`. Magic-Link: es gibt zum Zeitpunkt des Versands kein Konto (`MagicLinkRequestHandler` löst erst beim Einlösen auf), deshalb gilt die Anfragesprache `i18n.FromContext(r.Context())` (Cookie, `Accept-Language`, sonst `de`).

**Allowlist-Einträge (G5), die dieses Paket entfernt:** `internal/mail/` (verify.go, reset.go, magic.go, tier_change.go; falls der Wächter in `sender.go` etwas meldet, bekommt die betroffene Funktion `// i18n-log`), `internal/handler/account_delete_code.go`, `internal/handler/auth_oauth.go`. Danach ist die Allowlist insgesamt leer; die Endabnahme macht G5 Teil 2.

**Golden vor der Umstellung erzeugen.** Ein kurzer Wegwerf-Test (nicht einchecken) schreibt aus den **heutigen** Buildern mit festen Eingaben (`publicHost=https://example.invalid`, `user=golden-de`, `token=tok123`, `code=123456`) je Fall `<fall>.de.txt` (erste Zeile `Subject: <Betreff>`, Leerzeile, Klartext-Body) und `<fall>.de.html`. Erst dann wird umgestellt. Die `*.en.*`-Dateien entstehen aus der umgestellten Ausgabe und dienen als Review-Hilfe.

## Expected Behavior

- **Input:** Auslöser: Registrierung, Profil-Änderung der E-Mail, „Passwort vergessen", Magic-Link-Anforderung, Lösch-Code-Anforderung, Google-Verknüpfung, Level-Antrag.
- **Output:** Mail mit Betreff, Klartext- und HTML-Teil in der Empfängersprache, Header `X-GZ-Lang`; deutsche Mails byte-gleich zu heute.
- **Side effects:** keine zusätzlichen Mails, keine geänderten Empfänger oder Guards; Logzeilen unverändert.

## Acceptance Criteria

- **AC-1:** Given eine Registrierung mit `language` `en` / When die Bestätigungs-Mail gebaut und versandt wird / Then lautet der Betreff „Confirm your email address for Gregor 20", Klartext und HTML sind englisch, der Bestätigungs-Link ist unverändert, und der Header `X-GZ-Lang` ist `en`.
  - Test: internal/handler/konto_mails_sprache_test.go — echter `RegisterHandlerWithInvites` mit Temp-Datenverzeichnis, die Versand-Naht `sendVerificationMailFn` fängt die fertige Mail ab; zusätzlich `buildPayload` über `net/mail.ReadMessage` auf den Header geprüft.

- **AC-2:** Given ein Nutzer mit Sprache `de` oder ohne gespeicherte Sprache / When eine der fünf Mails (Bestätigung, Passwort zurücksetzen, Einmalcode, Lösch-Code, Google-Hinweis) gebaut wird / Then sind Betreff, Klartext und HTML byte-gleich zur heutigen Ausgabe (Golden), und der Header ist `X-GZ-Lang: de`.
  - Test: internal/mail/konto_mails_zweisprachig_test.go und internal/handler/konto_mails_sprache_test.go — Vergleich gegen `testdata/golden/*.de.*` (vor der Umstellung erzeugt), Fall „keine Sprache" und Fall `de`.

- **AC-3:** Given ein Nutzer mit Sprache `en` beantragt ein anderes Level / When der Antrag gespeichert wird / Then geht die Betreiber-Mail weiter auf Deutsch („Gregor 20 — Level-Wechsel-Antrag von <Kennung>") mit `X-GZ-Lang: de` an die konfigurierte Betreiber-Adresse, und die API-Antwort `{"status":"ok","po_notified":…}` bleibt unverändert.
  - Test: internal/handler/konto_mails_sprache_test.go — echter `RequestTierChangeHandler`, `sendTierChangeMailFn` fängt die Mail ab; eine Bestätigungs-Mail an den Nutzer existiert nicht und wird nicht neu eingeführt.

- **AC-4:** Given zwei Nutzer A (`en`) und B (`de`), die im selben Prozess gleichzeitig „Passwort vergessen" auslösen / When beide Mails gebaut werden / Then erhält A die englische und B die deutsche Mail an jeweils die eigene Adresse, ohne Vermischung von Sprache oder Empfänger.
  - Test: internal/handler/konto_mails_sprache_test.go — zwei Nutzer im Temp-Datenverzeichnis, parallele Aufrufe des echten `ForgotPasswordHandler`, `sendResetMailFn` fängt beide Mails ab; Prüfung von Empfänger, Betreff und Body.

- **AC-5:** Given ein Besucher ohne Konto fordert einen Einmalcode an, einmal mit `Accept-Language: en` und einmal ohne Angabe / When die Mail gebaut wird / Then ist sie beim ersten Mal englisch („Gregor 20 — Your one-time code") und beim zweiten Mal deutsch und byte-gleich zu heute.
  - Test: internal/handler/konto_mails_sprache_test.go — echter `MagicLinkRequestHandler` hinter der echten `Lang`-Middleware, Abfangen über `sendVerificationMailFn`.

- **AC-6:** Given Lösch-Code- und Google-Hinweis-Mail eines Nutzers mit Sprache `en` / When sie gebaut werden / Then sind beide englisch, der Code erscheint unverändert im Text, und die englischen Texte enthalten weder Umlaute noch HTML-Entities für Umlaute noch deutsche Signalwörter.
  - Test: internal/handler/konto_mails_sprache_test.go — `RequestDeleteCodeHandler` und `sendGoogleLinkNotice` mit abgefangenem Versand; Textprüfung auf `[äöüß]`, `&[aou]uml;` und Signalwörter in den `en`-Werten (Katalogprüfung zusätzlich in `internal/mail/konto_mails_zweisprachig_test.go`).

- **AC-7:** Given der Katalog `mail` und der Wächter aus G5 / When `go test ./internal/i18n/... ./internal/mail/...` läuft / Then haben alle Schlüssel jeder Mail-Art beide Sprachen mit gleichen Platzhaltern, und die Allowlist enthält keinen der Einträge `internal/mail/`, `account_delete_code.go`, `auth_oauth.go` mehr (sie ist insgesamt leer).
  - Test: internal/i18n/katalog_paritaet_test.go und internal/i18n/hardcode_guard_test.go (Paritäts- und Ratschentest, `# doc-compliance-test`) — unverändert ausgeführt; zusätzlich zählt `internal/mail/konto_mails_zweisprachig_test.go` für jede Mail-Art die vorhandenen `plain.z*`- und `html.z*`-Schlüssel gegen die im Code gelesenen.

- **AC-8:** Given der Staging-Server und ein Nutzer, der über `POST /api/auth/register` mit `language` `en` angelegt wurde / When die Bestätigungs-Mail zugestellt wird / Then liegt sie im Stalwart-Test-Postfach (Subadresse `+en`) mit Betreff „Confirm your email address for Gregor 20" und Header `X-GZ-Lang: en`, und eine Registrierung mit `de` liefert den deutschen Betreff.
  - Test: Live-Schritt in `/e2e-verify` gegen Staging — echte Zustellung, Abruf per IMAP aus dem Test-Postfach, Prüfung von Betreff und Header; ein Validator-Skript gibt es für diese Go-Mails nicht (die vier Validatoren prüfen nur Briefing-, Vergleichs-, Warn- und Radar-Mails).

## Known Limitations

- **Annahme (Magic-Link):** Ohne Konto zum Versandzeitpunkt gilt die Anfragesprache, nicht eine Nutzersprache; ein Nutzer mit `en` im Konto, der sich vom Browser mit deutschem `Accept-Language` einen Code schickt, bekommt den Code deutsch. Das ist die kleinste Lösung ohne Kontozugriff vor der Codeeingabe.
- **Annahme (Entities im Katalog):** Die deutschen HTML-Werte enthalten Entities (`&auml;`), damit die Ausgabe byte-gleich bleibt. Das ist die einzige Abweichung von „kein HTML im Katalog"; Tags stehen nie im Katalog.
- **Annahme (Eigenname):** „Gregor 20" steht als Wort im Katalogtext (Produktname, kein Kanal, Provider oder Ort); in Komposita („Gregor-20-Konto") bleibt die deutsche Schreibweise wörtlich.
- **Annahme (Signaturänderung):** Die Builder bekommen `lang` als erstes Argument statt einer zweiten Funktionsfamilie; Bestandstests werden mechanisch mit `i18n.De` angepasst.
- Die Betreiber-Mail beim Level-Antrag und die Betriebs-Meldungen des Schedulers bleiben deutsch (ADR-0104, Epic-Ausschluss).
- Die SMS-Bestätigung entsteht im Python-Core; der Text dort fällt unter P8/P11, nicht unter dieses Paket.
- Englische Texte sind länger; es gibt in diesen Mails keine Zeichenbegrenzung.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Die Sprache gehört dem Empfänger-Nutzer, Mails tragen sie im Marker `X-GZ-Lang`, und Betreiber-Mails bleiben deutsch.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
