# ADR-0081: Kontolöschung nur mit Re-Auth (Passwort oder Lösch-Code) und vollständiger Restebereinigung

- **Status:** Akzeptiert
- **Datum:** 2026-10-03
- **Bezug:** GitHub-Issue #2160 (Epic #2138 Multi-User), Spec
  `docs/specs/modules/account_deletion.md` v2.0, Analyse
  `docs/context/fix-2160-account-loeschung-reste.md`; baut auf ADR-0060 (Sitzungs-Allowlist),
  ADR-0066 (bestätigte Adresse) und ADR-0067 (Adress-Eindeutigkeit)

## Kontext

`DELETE /api/auth/account` löschte ein Konto allein mit einer gültigen Sitzung — ein
gestohlenes Cookie genügte. Außerdem blieben Daten mit Nutzerbezug außerhalb des
Nutzerordners liegen: Telegram-Deep-Link-Tokens in `data/telegram_tokens.json` und offene
Login-OTPs im Speicher, mit denen nach der Löschung sofort ein neues Konto unter derselben
Adresse entstehen konnte. Konten ohne Passwort (Magic-Link, Passkey-only, Google-only) sind
regulär; eine reine Passwort-Abfrage hätte sie ausgesperrt.

## Entscheidung

- **Neuer Endpunkt `POST /api/auth/account/delete`** mit Body `{password?, code?}`; der alte
  `DELETE /api/auth/account` entfällt ersatzlos (DELETE mit Body ist semantisch undefiniert,
  die Auth-Endpunkte sind POST-Stil).
- **Re-Auth (Sudo-Mode):** Nachweis ist das Passwort (bcrypt) ODER ein **Lösch-Code**.
  Passwortlose Konten können nur den Lösch-Code nutzen; ein mitgeschicktes Passwort wird dort
  mit 403 abgelehnt. Der Passwortweg berührt den Lösch-Code nie.
- **Lösch-Code:** `POST /api/auth/account/delete-code` erzeugt einen 6-stelligen Code, schickt
  ihn ausschließlich an `EffectiveContactAddress` (`mail_to`, sonst `email` — nie an die
  ausstehende Adresse) und speichert ihn erst nach erfolgreichem Versand in einem **eigenen
  Store, Schlüssel UserID**. TTL 15 Minuten, max. 3 Fehlversuche (Zähler vor dem Vergleich),
  einmalig. Login-OTP und Lösch-Code sind getrennte Welten.
- **Restebereinigung** in einer gemeinsamen Aufräumfunktion unter `telegramConnectMu`:
  Telegram-Tokens des Nutzers (persistiert), Login-OTPs für `Email`, `MailTo`,
  `PendingContactAddress`, der Lösch-Code, dann der Nutzerordner. Scheitert die
  Token-Persistierung, antwortet der Server 500 und der Ordner bleibt — wiederholbar.
- **Telegram-Token-Store** schreibt atomar (Temp-Datei + Rename, 0600) und gibt Fehler zurück;
  die Link-Erzeugung antwortet bei Speicherfehler 500 statt eines nie gespeicherten Tokens.
  Telegram-Connect lädt den Nutzer erst unter `telegramConnectMu` (kein Zombie-Ordner).
- **Reaper:** `gc(now)` für Login-OTPs, Lösch-Codes und Telegram-Tokens, gestartet als Ticker
  aus `cmd/server/main.go` (nie aus Konstruktoren). Gesperrte OTPs bleiben bis zum Ablauf.
- **Rate-Limits:** `IPRateLimiter(5, 15min)` auf `/account/delete`; `IPRateLimiter(3, 15min)`
  plus Mindestpause je Nutzer/Adresse (`MailFloodLimiter(1, 1min)`) auf `/account/delete-code`.

## Konsequenzen

- Ein Sitzungsdieb kann ein Konto nicht mehr löschen, ohne Passwort oder Postfach zu
  kontrollieren. Bei bestätigten Konten ist die wirksame Adresse nur über Bestätigung änderbar.
- Kein Konto wird ausgesperrt: Jedes Konto hat eine Adresse, der Lösch-Code steht immer offen.
- Das Profil liefert `has_password` (immer vorhanden, nie der Hash), damit der Dialog weiß,
  ob er ein Passwortfeld zeigt.
- Beide 429-Fälle (geteilte IP-Middleware und Mindestpause je Nutzer) antworten mit
  demselben Fehlercode `rate_limit_exceeded` wie der Rest der Codebasis.
- Passkey ist kein eigener Nachweis (Passkey-Konten nutzen den Lösch-Code); PII in Log-Zeilen
  bleibt ein eigenes Thema.

## Alternativen

- **Nur Passwort:** verworfen — sperrt passwortlose Konten aus.
- **Login-OTP als Nachweis wiederverwenden:** verworfen — vermischt Anmeldung und Löschung,
  ein Login-Code darf kein Konto löschen.
- **Passkey-Zeremonie als Nachweis:** zurückgestellt — eigener WebAuthn-Ablauf, Lösch-Code
  deckt diese Konten bereits ab.
