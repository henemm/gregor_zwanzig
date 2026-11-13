---
entity_id: security_haertung_2026_11_kontoaenderungen
type: module
created: 2026-11-13
updated: 2026-11-13
status: implemented
version: "1.0"
tags: [security, auth, go-api, account, reauth, passkey, issue-2961]
---

# Sicherheits-Härtung Kontoänderungen (Issue #2961, Welle 2, Paket „Kontoänderungen absichern“)

## Approval

- [x] Approved — PO-Auftrag 2026-11-12 (Issue #2961): alle Befunde des Sicherheits-Reviews ohne Rückfrage beheben; dieser Auftrag ist die Vorgabe.

## Purpose

Schließt die Befunde GA2, GA3, GA6 und GA9 des Sicherheits-Reviews 2026-11: Eine erbeutete Sitzung
reicht nicht mehr, um Adresse, Login-Kennung oder Passkeys eines Kontos dauerhaft zu übernehmen;
jede solche Änderung meldet sich per Mail; ein Passwort-Reset kann alle fremden Zugangswege auf
einmal entfernen; vorab mit fremder Adresse angelegte Konten blockieren nichts mehr; parallele
Schreiber setzen Sicherheitswerte nicht zurück. Architektur-Entscheidung: ADR-0115.

## Source

- **Files:** `internal/handler/account_reauth.go` (neu), `internal/handler/account_notice.go` (neu),
  `internal/handler/account_unbestaetigt.go` (neu), `internal/handler/account_delete_code.go`,
  `internal/handler/auth.go`, `internal/handler/auth_magic.go`, `internal/handler/auth_oauth.go`,
  `internal/handler/passkey.go`, `internal/store/user.go`, `internal/store/user_lock.go` (neu),
  `internal/store/user_unbestaetigt.go` (neu), `internal/router/router.go`, `cmd/server/main.go`,
  `internal/i18n/messages/{de,en}/{auth,mail}.json`,
  `frontend/src/routes/account/+page.svelte`, `frontend/src/routes/account/nachweis.ts` (neu),
  `frontend/src/lib/passkey.ts`, `frontend/src/routes/reset-password/+page.svelte`,
  `frontend/src/routes/reset-password/+page.server.ts`,
  `frontend/src/lib/i18n/messages/{de,en}/{konto,auth}.json`
- **Schicht:** Go-API und SvelteKit-Frontend (Konto-Seite, Passwort-Reset-Seite). Kein Python-Core
  (der Core liest `user.json` nur).

> **Querschnitts-Prüfpunkte:** Keine Trip-/Ortsvergleich-Bausteine betroffen. Mandantentrennung:
> Nachweise, Codes, Sperren und Bremsen sind je Nutzer (und Sitzung) geschlüsselt; jeder
> datenbewegende Weg ist mit zwei Nutzern getestet. Keine Briefing-/Alarm-Inhalte betroffen.

## Estimated Scope

- **LoC:** ~1.600 (davon ~55 % Tests)
- **Files:** ~45 (Code, Tests, Doku)
- **Effort:** high

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| Lösch-Code (ADR-0081) | Go-Baustein | wird zum allgemeinen Konto-Code verallgemeinert |
| `MailFloodLimiter`, `attemptGuard` | Go-Typen | Bremsen für Codes, Nachweise und Hinweis-Mails |
| Store-Reaper (`StartStoreReaper`) | Go | räumt zusätzlich abgelaufene unbestätigte Anmeldungen |
| ADR-0060, ADR-0066, ADR-0067, ADR-0081, ADR-0087, ADR-0105 | ADR | werden durch ADR-0115 ergänzt |

## Implementation Details

1. **Nachweis (GA3).** `POST /api/auth/reauth` prüft Passwort (höchstens 5 Fehlversuche je Nutzer
   und 15 Minuten) oder einen Code aus einem eigenen Store (`reauthCodeStore`, gleicher Aufbau wie
   der Lösch-Code: 15 Minuten, 3 Versuche, einmalig). `POST /api/auth/reauth/code` verschickt den
   Code an die bisherige wirksame Adresse. Ein Erfolg vermerkt (Nutzer, Sitzung) → Ablauf
   +10 Minuten; jede neu ausgestellte Sitzung trägt den Vermerk ebenfalls. Hüllen an den Routen:
   `RequireFreshReauth` (Passkey begin/finish/entfernen) und `RequireReauthForAddressChange`
   (Profil-PUT nur, wenn `email`/`mail_to` sich normalisiert ändern). Antwort ohne Nachweis:
   `403 reauth_required`.
2. **Hinweis-Mails.** `notifyAccountChange` baut aus `mail.hinweis.*` (DE/EN) Betreff, Satz, ggf.
   Zusatzzeilen und eine Warnung mit Link zu „Passwort vergessen“; Versand wie die
   Google-Hinweis-Mail (Testkonten Google-Weg, sonst enger Verifikationsweg), asynchron,
   fail-soft, `MailFloodLimiter(5, 1h)` je Nutzer. Die Google-Hinweis-Mail läuft über denselben Weg.
3. **Passwort-Reset.** `remove_other_access` (Vorgabe `true`); `UpdateUser` setzt Hash und leert
   bei Wahl oder unbestätigtem Konto Passkeys und `oauth_provider`/`oauth_sub`; Hinweis-Mail mit
   Liste des Entfernten. Reset-Seite: Kästchen (Vorgabe an) plus Marke, damit die Action ein
   abgewähltes Kästchen von einem fehlenden Feld unterscheidet.
4. **Unbestätigte Anmeldungen (GA2).** Behandelt wird nur ein Kontoordner ohne Nutzinhalte
   (`IsAccountDirPristine`, Positivliste siehe AC-15); er wird nie gelöscht, sondern per Rename in
   die Ablage `<Datenwurzel>/.entfernt-unbestaetigt/` verschoben (`QuarantineUser`) und vom
   Reaper erst nach 30 Tagen entfernt (`PurgeAblage`). `store.IsUnconfirmedSignup` (kein Testkonto, unbestätigt,
   keine ausstehende Änderung, angelegt ab 2026-09-12, Bestätigungstoken vorhanden).
   `ReplaceableAddressHolders` liefert die Halter einer Adresse und ob alle ersetzbar sind;
   Registrierung (Passwort, öffentlicher Passkey im Finish unter Adress-Sperre) löscht sie dann über
   `deleteAccountCascade` und legt das neue Konto an. Reaper: höchstens stündlich,
   Token-Ablauf + 24 h, unter Adress-Sperre mit Nachprüfung. Bestätigungsmail-Text DE/EN ergänzt.
5. **Login-Kennung (GA9).** `UpdateProfileHandler`: neue `email` eines bestätigten Kontos geht
   immer in `pending_contact_*` (Feld `email`, Adresse = neue `email`), auch bei gleichem `mail_to`.
6. **Sperre und Sicherheitsfelder (GA6).** `lockUserJSON` (paketweit je Nutzer) um `SaveUser`,
   `UpdateUser`, alle Merge-Setter und `DeleteUser`. `SaveUser` übernimmt bei vorhandener Datei
   die Sicherheitsfelder vom Plattenstand; Schreiber dieser Felder (Passwort, Reset, Passkey
   anlegen/entfernen/benutzen, Magic-Link-/Google-Übernahme, Google-Verknüpfung, Bestätigung,
   Selbstheilung) laufen über `UpdateUser`. Grep über `src/` und `api/`: Python schreibt `user.json`
   nicht.
7. **Konto-Seite.** Bei `reauth_required` öffnet sich der Dialog der Kontolöschung im
   Nachweis-Modus (Passwort oder Code); danach wird gespeichert bzw. der Passkey entfernt; beim
   Passkey-Anlegen öffnet sich der Anlegen-Dialog erneut (frischer Klick für die Geräteabfrage).
   Der Dialog „Auf allen Geräten abmelden“ nennt die Zahl der weiter gültigen Passkeys.

## Expected Behavior

- **Input:** Profil-PUT, Passkey-Aufrufe, Nachweis-Aufrufe, Passwort-Reset, Registrierung,
  Reaper-Takt.
- **Output:** 403 `reauth_required` ohne Nachweis, sonst wie bisher; Hinweis-Mails an die
  bestätigte bzw. alte Adresse; Reset ohne fremde Zugangswege; Registrierung ersetzt
  unbestätigte Anmeldungen.
- **Side effects:** Löschen unbestätigter Anmeldungen samt Ordner; Mails.

## Acceptance Criteria

**AC-1:** Given ein bestätigtes Konto mit Sitzung ohne frischen Nachweis / When es `mail_to` oder `email` ändert, einen Passkey anlegen (begin oder finish) oder entfernen will / Then antwortet der Dienst 403 `reauth_required` mit Katalogtext und ändert nichts; ein Profil-Speichern ohne Adressänderung (auch mit unverändertem `mail_to` in anderer Schreibweise) geht ohne Nachweis durch.
  - Test: `internal/router/konto_reauth_2961_test.go` (`TestKontoaenderung_AdresswechselOhneNachweis_403`, `…PasskeyHinzufuegenUndEntfernenBrauchenNachweis`, `…ProfilOhneAdressaenderungBrauchtKeinenNachweis`)

**AC-2:** Given ein Nutzer erbringt in einer Sitzung den Nachweis mit dem richtigen Passwort / When er in den folgenden 10 Minuten nacheinander Adresse und Passkeys ändert / Then gelingen alle Änderungen ohne erneute Abfrage; eine andere Sitzung desselben Nutzers und ein anderer Nutzer haben dadurch keinen Nachweis, und nach 10 Minuten ist er abgelaufen.
  - Test: `TestKontoaenderung_NachweisGiltZehnMinutenFuerDieseSitzung`, `TestReauth_NachweisLaeuftNachZehnMinutenAb`

**AC-3:** Given ein Konto ohne Passwort / When es den Nachweis per Code an die bisherige Adresse erbringt / Then gilt der Code genau einmal, nur für dieses Konto, ein Lösch-Code wird nicht als Nachweis angenommen und umgekehrt; ein Passwort am passwortlosen Konto wird abgelehnt.
  - Test: `TestReauth_CodeWegGetrenntVomLoeschCode`, `TestReauth_OhneSitzungUndOhneNachweis`

**AC-4:** Given eine frisch ausgestellte Sitzung (Anmeldung) / When der Nutzer direkt danach seine Adresse ändert / Then gelingt das ohne weiteren Nachweis, während eine ältere Sitzung desselben Nutzers weiter 403 `reauth_required` bekommt.
  - Test: `TestKontoaenderung_FrischeAnmeldungGiltAlsNachweis`

**AC-5:** Given ein bestätigtes Konto / When das Passwort geändert oder zurückgesetzt, ein Passkey hinzugefügt oder entfernt oder Google verknüpft wird / Then geht genau eine Hinweis-Mail an die aktuelle bestätigte Adresse dieses Kontos (nicht an andere Konten), ein Mailfehler bricht die Änderung nicht ab, und ein unbestätigtes Konto bekommt keine.
  - Test: `internal/handler/account_notice_test.go` (`TestHinweis_PasswortGeaendert_NurAnDasEigeneKonto`, `…MailfehlerBrichtAenderungNichtAb`, `…UnbestaetigtesKontoBekommtKeine`, `…PasskeyHinzugefuegtUndEntfernt`), Google: `google_login_address_linking_test.go`

**AC-6:** Given ein bestätigtes Konto mit ausstehendem Adresswechsel / When der Bestätigungslink eingelöst wird / Then geht eine Hinweis-Mail mit der neuen Adresse an die ALTE bestätigte Adresse.
  - Test: `TestHinweis_AdresswechselGehtAnDieAlteAdresse`

**AC-7:** Given ein Nutzer / When mehr als fünf Hinweis-Mails binnen einer Stunde anfallen / Then werden nur fünf versendet, und ein anderer Nutzer bekommt seine Hinweis-Mail weiterhin.
  - Test: `TestHinweis_MengenbremseFuenfJeNutzerUndStunde`

**AC-8:** Given ein Konto mit Passkeys und Google-Verknüpfung / When das Passwort per Reset-Link zurückgesetzt wird und die Auswahl „Alle anderen Zugangswege entfernen“ aktiv ist (Vorgabe, auch wenn das Feld fehlt) / Then sind Passkeys und Google-Verknüpfung entfernt, alle Sitzungen beendet, ein anderes Konto unberührt, und die Hinweis-Mail nennt das Entfernte; bei abgewählter Auswahl bleiben sie bei einem bestätigten Konto, bei einem unbestätigten Konto werden sie trotzdem entfernt.
  - Test: `internal/handler/password_reset_zugangswege_test.go`, Frontend `reset-password/__tests__/andere_zugangswege.test.ts`

**AC-9:** Given eine Adresse, die nur eine unbestätigte Anmeldung mit leerem Kontoordner hält / When jemand sich mit dieser Adresse registriert / Then entsteht ein neues Konto mit neuen Zugangsdaten und neuem Bestätigungstoken, der alte Kontoordner (samt Zugangsdaten und Passkeys) ist aus `users/` in die Ablage verschoben (nicht gelöscht), und unbeteiligte Konten bleiben; hält ein bestätigtes Konto, ein Bestandskonto von vor der Bestätigungspflicht, ein Konto ohne Token oder eine unbestätigte Anmeldung mit Nutzinhalten die Adresse, bleibt es bei 409 und der Ordner unangetastet.
  - Test: `internal/handler/unbestaetigte_konten_test.go` (`TestRegistrierung_*`), angepasst `address_uniqueness_write_paths_test.go` (AC-6, AC-13a/b: genau ein Halter)

**AC-10:** Given unbestätigte Anmeldungen mit seit mehr bzw. weniger als 24 Stunden abgelaufenem Token, eine reife Anmeldung mit Nutzinhalten, ein Bestandskonto von vor der Bestätigungspflicht, ein Testkonto, ein bestätigtes Konto und ein Konto ohne Token / When der Reaper läuft / Then verschiebt er genau die leeren Anmeldungen mit seit mehr als 24 Stunden abgelaufenem Token in die Ablage; die Anmeldung mit Nutzinhalten bleibt mit Warn-Logzeile (maskierte Kennung) stehen.
  - Test: `TestReaper_LoeschtNurAbgelaufeneUnbestaetigteAnmeldungen`, `TestUnbestaetigt_NichtLeererOrdnerBleibtUnangetastet`

**AC-15:** Given ein Kontoordner / When geprüft wird, ob er leer ist / Then gilt er nur als leer, wenn er ausschließlich `user.json`, `sessions.json`, `email_verification.json`, `password_reset.json` und die leeren Standardverzeichnisse `locations/`, `gpx/`, `weather_snapshots/` enthält; jede andere Datei, jeder andere oder nicht leere Ordner und jeder Verweis heißt „nicht leer“, und ein nicht leerer Ordner wird nie verschoben.
  - Test: `internal/store/user_ablage_test.go`

**AC-16:** Given ein in die Ablage `<Datenwurzel>/.entfernt-unbestaetigt/<kennung>-<UTC-Zeitstempel>/` verschobenes Konto / When Nutzerliste und Adress-Eindeutigkeit abgefragt werden, der Ordner zurückgeschoben wird bzw. der Reaper vor und nach 30 Tagen läuft / Then sieht kein Leser die Ablage, das zurückgeschobene Konto ist mit allen Feldern wieder da, und die Ablage wird erst nach 30 Tagen endgültig entfernt.
  - Test: `TestAblage_DreissigTageZurueckholbarUndUnsichtbar`

**AC-11:** Given eine Bestätigungsmail / When sie in Deutsch oder Englisch gebaut wird / Then sagt sie, dass sie zu ignorieren ist, wer sich nicht selbst registriert und die Adresse nicht selbst eingetragen hat.
  - Test: `TestBestaetigungsmail_NenntFremdausgeloesteRegistrierung`, Goldens `internal/mail/testdata/golden/verify.*`

**AC-12:** Given ein bestätigtes Konto mit gesetztem `mail_to` / When es eine neue `email` (Login-Kennung) speichert / Then bleibt die alte Kennung wirksam, die neue wartet auf den Bestätigungslink an die neue Adresse und wird erst damit wirksam, und bis dahin kann sich jemand anderes mit dieser Adresse registrieren.
  - Test: `internal/handler/profile_kennung_bestaetigung_test.go`, angepasst `TestAC6_NeueLoginKennungWartetAufBestaetigung`

**AC-13:** Given veraltete Profil-Schreiber laufen parallel zu einem Passwort-Reset und einer Admin-Sperre für zwei Nutzer / When alle fertig sind / Then tragen beide Konten den neuen Passwort-Hash, keine Passkeys und die Sperre, und keines enthält Werte des anderen (auch mit `-race`).
  - Test: `internal/store/user_sicherheitsfelder_test.go`

**AC-14:** Given die Konto-Seite / When das Speichern oder ein Passkey-Aufruf mit 403 `reauth_required` antwortet / Then erkennt die Seite den Fall (Profil-Fehlerobjekt und `$lib/passkey`), öffnet den Nachweis-Dialog und übersetzt dessen Fehler verständlich in DE/EN; der Dialog „Auf allen Geräten abmelden“ nennt die Zahl der weiter gültigen Passkeys.
  - Test: `frontend/src/routes/account/__tests__/nachweis_vor_kontoaenderung.test.ts`, Kataloganker `f4KatalogAnker.ts`

## Known Limitations

- Nachweise, Codes und Bremsen leben im Arbeitsspeicher; ein Neustart verlangt den Nachweis erneut.
- Eine sitzungsgebundene Google-Verknüpfen-/Lösen-Funktion gibt es nicht; die Verknüpfung entsteht
  beim Google-Login mit Adressnachweis (Hinweis-Mail), gelöst wird über den Passwort-Reset.
- Restrisiko: Wer eine fremd ausgelöste Registrierung per Klick bestätigt, bestätigt das Konto eines
  Dritten (ADR-0115, Konsequenzen).
- Ändern `email` und `mail_to` gleichzeitig, wartet nur `mail_to`; die neue `email` wird nicht
  übernommen (eine ausstehende Änderung je Konto).
- Die Staging-E2E-Specs für Passkeys erbringen den Nachweis vorab per Passwort
  (`bestaetigeKontoaenderung` in `frontend/e2e/helpers.ts`); ein E2E-Durchlauf des
  Nachweis-Dialogs im Browser fehlt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0115
- **Rationale:** Ändert Entscheidungsflächen Auth (Re-Auth aus ADR-0081, Login-Kennung aus
  ADR-0105, Adress-Eindeutigkeit aus ADR-0067) und das Datenmodell-Prinzip für `user.json`.

## Changelog

- 2026-11-13: Erstfassung und Umsetzung (Issue #2961, Welle 2).
- 2026-11-13: Nachbesserung „Bestandsdaten bleiben erhalten“: nur leere Kontoordner, Ablage statt Löschen, 30 Tage zurückholbar (AC-9, AC-10 geändert; AC-15, AC-16 neu).
