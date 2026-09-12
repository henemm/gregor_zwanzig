# ADR-0066: Die Anmeldung setzt eine bestätigte E-Mail-Adresse voraus — die öffentliche Passkey-Registrierung stellt keine Sitzung mehr aus

- **Status:** Akzeptiert (PO-Freigabe 2026-09-12 zur Spec `email_verify_scharfschaltung_2271.md`)
- **Datum:** 2026-09-12
- **Bezug:** GitHub-Issue #2271 (Scheibe 2 von 2 aus #2146, Epic #2138), Spec
  `docs/specs/modules/email_verify_scharfschaltung_2271.md`, Vorbedingung aus #2304 (S1);
  schreibt [ADR-0060](0060-dauerhafte-anmeldung-mit-widerrufsliste.md) fort und nimmt die
  Zusage „alle sechs Anmeldewege stellen ein Merkmal aus" aus
  `docs/specs/modules/session_allowlist.md` (AC-13/AC-18) teilweise zurück.

## Kontext

ADR-0060 hat die dauerhafte Anmeldung eingeführt: sechs Anmeldewege, eine gemeinsame
Ausstellungsstelle (`issueSession`), ein widerrufbares Merkmal auf einer Gästeliste. Ob die
E-Mail-Adresse des Kontos jemals bestätigt wurde, spielte dabei keine Rolle — der
Double-Opt-In aus #1219/#1226 verschickte die Bestätigungsmail, hatte aber keine Wirkung auf
die Anmeldung. Ein unbestätigtes Konto war ein voll nutzbares Konto.

Für ein Mehrnutzer-Produkt mit offener Registrierung (PO-Entscheid 2026-09-09: Registrierung
bleibt offen, Bestätigung wird Pflicht) ist das die falsche Reihenfolge: Wer eine fremde
Adresse einträgt, bekommt heute ein Konto samt Sitzung, und die fremde Adresse bekommt
Post von einem Dienst, mit dem sie nichts zu tun hat. Scheibe 1 (#2304) hat die Vorbedingung
geschaffen — Selbstheilung bei Magic-Link/Google, Resend-Endpunkt, Nachtrag für Bestandskonten
(Prod 3/3, Staging 63/63 bestätigt). Ohne diesen Nachlauf hätte die Scharfschaltung
Bestandsnutzer ausgesperrt.

## Entscheidung

1. **Die Sitzungsausstellung setzt eine bestätigte E-Mail-Adresse voraus.** Die Prüfung sitzt
   **in** `issueSession` (`internal/handler/auth.go`), auf einem frisch per `LoadUser`
   geladenen Nutzer — ohne Parameter der Aufrufer. Kein Anmeldeweg kann sie vergessen oder
   umgehen; ein künftiger siebter Weg erbt sie automatisch.
2. **Von sechs Anmeldewegen stellen künftig fünf ein Merkmal aus, drei davon nur bedingt.**
   Passwort-Login, Passkey-Login (mit und ohne Kennungseingabe) stellen nur bei bestätigter
   Adresse aus; Magic-Link und Google-OAuth stellen aus, sobald die Adresse bestätigt ist oder
   sich im selben Request selbst heilt. Die öffentliche Passkey-Registrierung stellt **gar
   kein** Merkmal mehr aus.
3. **Die Reihenfolge ist Teil der Entscheidung, nicht Implementierungsdetail.** Die
   Selbstheilung läuft **vor** dem Gate (sonst weist das Gate das Konto ab, das sich gerade
   heilt); das Gate läuft **nach** der Geheimnisprüfung (sonst verrät ein 403 die Existenz
   eines Kontos an jemanden, der das Passwort nicht kennt).
4. **Antwortform je Fluss.** JSON-Wege antworten `403 {"error":"email_not_verified"}` ohne
   Cookie. Der Google-Redirect-Fluss antwortet ausschließlich über den `Location`-Header
   (`/login?error=email_not_verified`) — Erfolg und Ablehnung sind dort beide `302`.
5. **Genau eine dokumentierte Ausnahme:** `ChangePasswordHandler` nutzt eine eigene, anders
   benannte Funktion ohne Gate (`issueSessionWithoutVerificationGate`). Wer gerade seine
   Adresse geändert hat, steht auf `EmailVerifiedAt == nil`; mit Gate könnte er sein Passwort
   nicht mehr ändern und verlöre im selben Zug seine Sitzung.

## Verworfene Alternativen

- **Ein Parameter an `issueSession`** (`issueSession(..., skipGate bool)`) — wäre genau die
  Umgehungslücke, die das zentrale Gate verhindern soll: unsichtbar im Aufruf, leicht
  versehentlich gesetzt. Zwei Funktionen mit sprechenden Namen machen die Ausnahme lesbar.
- **Das Gate je Anmeldeweg im Handler** — sechs Stellen, sechs Gelegenheiten, eine zu
  vergessen; und ein siebter Weg erbte nichts.
- **Die Prüfung auf einer mitgereichten `model.User`-Struct** — `selfHealEmailVerification`
  schreibt per `SaveUser` auf die Platte, nicht in die Struct des Aufrufers. Das Gate sähe den
  im selben Request geheilten Stand nicht und sperrte genau das Konto aus, das sich heilt.
- **Der Registrierung ein Konto erst nach Bestätigung anlegen** — größerer Umbau, und der
  PO-Entscheid vom 2026-09-09 hält die Registrierung ausdrücklich offen.
- **Ein `401` statt `403` bei unbestätigter Adresse** — wäre für den rechtmäßigen Nutzer
  nicht von „falsches Passwort" unterscheidbar und machte den Resend-Weg unauffindbar.

## Konsequenzen

- **Positiv:** Eine fremd eingetragene Adresse führt zu keiner nutzbaren Sitzung. Die
  Zusicherung hängt an einer einzigen Stelle und ist dort mutierbar prüfbar. Der Wegfall des
  Auto-Logins bei der öffentlichen Passkey-Registrierung bringt diesen Weg auf dieselbe Linie
  wie `RegisterHandler`, der nie ein Auto-Login hatte.
- **Negativ / Preis:**
  - Wer ein geleaktes Passwort ausprobiert, erfährt bei einem unbestätigten Konto zusätzlich,
    dass Kennung und Passwort stimmen (403 statt 401). Bewusst getragen zugunsten einer für
    den rechtmäßigen Nutzer verständlichen Meldung; gegenüber jemandem ohne Passwort entsteht
    kein neues Leck, weil das Gate erst nach der Passwortprüfung antwortet.
  - Magic-Link und Google-OAuth sperren künftig dort, wo die nachgewiesene Adresse von der
    effektiven Kontaktadresse des Kontos **abweicht** — die Selbstheilung greift dann nicht
    (Adressvergleich in `selfHealEmailVerification`). Für den Bestand folgenlos (Prod 3/3,
    Staging 63/63 bestätigt), aber es ist eine Verhaltensänderung gegenüber S1, wo kein Weg
    sperrte.
  - Ein neu per Google angelegtes Konto durchläuft den Double-Opt-In und kommt deshalb im
    **Anlage-Request** nicht mehr direkt hinein; es landet einmalig auf
    `/login?error=email_not_verified`. Der **zweite** Anlauf gelingt: `createOAuthUser` setzt
    `MailTo` auf die von Google bestätigte Adresse, beim nächsten Callback greift der
    Bestands-Zweig, die Selbstheilung stimmt zu und das Konto kommt durch. Ein Umweg von einem
    Klick, keine Aussperrung.
- **Folgepflichten:**
  - Jeder neue Anmeldeweg geht über `issueSession`. Wer
    `issueSessionWithoutVerificationGate` aufruft, braucht dafür eine dokumentierte
    Begründung im ADR-Bestand — heute gibt es genau einen Aufrufer.
  - Automatisierte Testkonten (Playwright) müssen ihre Adresse über den staging-only Testweg
    bestätigen, bevor sie sich anmelden; die Reihenfolge „registrieren → Token holen →
    bestätigen → anmelden" ist zwingend.
  - `session_allowlist.md` (AC-13/AC-18) ist entsprechend fortgeschrieben — die Sechs-Wege-
    Zusage gilt nur noch für die Form des Merkmals, nicht mehr für die Frage, ob eines
    ausgestellt wird.
