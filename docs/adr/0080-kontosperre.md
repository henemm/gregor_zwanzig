# ADR-0080: Konten werden per Profilfeld gesperrt, und die Sperre wirkt auf allen Wegen

- **Status:** Akzeptiert
- **Datum:** 2026-09-30
- **Bezug:** GitHub-Issue #2155 (Scheibe S3, Epic #2138), Spec
  `docs/specs/modules/admin_rolle_s3_admin_api.md`, baut auf ADR-0078 (Admin-Rolle) und
  ADR-0079 (Betriebsstatus-Token)

## Kontext

Ein Admin kann bisher weder Nutzer sehen noch ein Konto sperren. Eine Sperre, die nur den
Web-Login stoppt, wäre eine Scheinsperre: Briefings und Alarme liefen weiter, Befehle per
E-Mail, Telegram oder Premium-SMS würden weiter ausgeführt. Fast alle Schreiber auf
`user.json` laden das Profil typisiert und schreiben es per `SaveUser` komplett zurück; ein
nur roh gesetztes Feld ginge dort verloren. Es gibt keinen Pro-Nutzer-Lock auf `user.json`.

## Entscheidung

- Die Sperre ist das typisierte Profilfeld `model.User.Disabled` (`disabled`, `omitempty`).
  Der Admin schreibt es per Roh-Merge (`SetUserDisabled`), unbekannte Felder bleiben erhalten.
- Sie wirkt auf allen Wegen: Session-Ausgabe (`issueSessionWithoutVerificationGate`, deckt
  Passwort, Magic-Link, Passkey, OAuth, Passwort ändern; 403 `account_disabled`, Ladefehler
  fail-closed), bestehende Sitzungen (`ClearSessions`), Scheduler-Fan-out
  (`filterOutTestUsers`, Ladefehler fail-open wie bisher), Premium-SMS-Zuordnung und
  E-Mail-/Telegram-Inbound (stumm verwerfen, nach dem Lookup).
- Reihenfolge beim Sperren: Flag setzen, dann `ClearSessions`, dann Read-after-Write.
  Scheitert `ClearSessions`, bleibt das Flag (sicherer Zustand), Wiederholung ist idempotent.
- Selbstsperre ist verboten (409); die Admin-Liste in `GZ_ADMIN_USER_IDS` bleibt unverändert.
- Bewusst nicht gefiltert: `address_owner` und die Telegram-Eindeutigkeitsprüfung. Adressen
  gesperrter Konten bleiben vergeben.

## Verworfene Alternativen

- **Nur Session-Sperre** — Scheinsperre, widerspricht der Kanal-Parität.
- **Flag nur roh, nicht im Modell** — ginge beim nächsten `SaveUser` verloren.
- **Neuer Lock auf `user.json`** — ohne Mitwirkung aller ca. 20 `SaveUser`-Aufrufer kein Schutz.

## Konsequenzen

- **Positiv:** Eine gesperrte Person bekommt nichts mehr und kann nichts mehr auslösen.
- **Negativ / Preis:** Restrisiko Lost Update: ein typisierter Schreiber, der `user.json` vor
  dem Admin-Schreiben lädt und danach speichert, kann `disabled` zurücksetzen. Mildernd: nach
  dem Sperren sind alle Sitzungen gelöscht; die Liste zeigt den Ist-Zustand, die Sperre lässt
  sich wiederholen.
- **Folgepflichten:** Neue Wege, die Sitzungen ausstellen oder Nutzer zuordnen, müssen
  `Disabled` beachten (Guard-Test `session_issuance_test.go`).
