# ADR-0084: Admin-Einladungslinks als globale Token-Datei mit Hash-Speicherung

- **Status:** Akzeptiert
- **Datum:** 2026-10-06
- **Bezug:** GitHub-Issue #2519, Spec `docs/specs/modules/admin_einladungslinks_2519.md`;
  baut auf ADR-0066 (E-Mail-Bestätigungspflicht) und ADR-0078 (Admin-Rolle) auf

## Kontext

Ein Admin soll einzelne externe Personen einladen und ihnen beim Registrieren direkt ein Level
(Free/Standard/Premium) mitgeben, ohne Tier-Antrag. Die offene Registrierung bleibt daneben
bestehen, die E-Mail-Bestätigung bleibt Pflicht.

## Entscheidung

- **Globale Ablage `data/invites.json`** statt `data/users/<user_id>/`: eine Einladung gehört
  keinem Nutzer, der Eingeladene existiert beim Erstellen noch nicht. Bewusste Abweichung von
  ADR-0031/0083 (Pro-Nutzer-Ablage); Muster `TelegramTokenStore` (Mutex, atomares Schreiben).
- **Token:** 32 Byte `crypto/rand`, base64url. Gespeichert wird nur SHA-256; der Link
  `/register?invite=<token>` wird nur einmal in der Antwort auf das Erstellen gezeigt.
- **Einlösung nur über die Formular-Registrierung.** Google-OAuth, Passkey und Magic-Link kennen
  keine Einladung; die Register-Seite blendet den Google-Knopf bei Einladungslink aus.
- **Atomare Einlösung:** alle Validierungen vor dem Einlösen (ein Tippfehler verbrennt die
  Einladung nicht), dann Reservierung unter Mutex vor `SaveUser`, Rollback bei Fehlschlag.
  Ungültiges Token -> 400 `invite_invalid`, nie ein stilles Free-Konto. Die Atomarität gilt
  innerhalb eines gregor-api-Prozesses.
- **Kein Ablaufdatum** in v1; Widerruf durch den Admin. Öffentlicher Vorab-Check
  `GET /api/auth/invite/{token}` rate-limited, ohne Unterscheidung benutzt/widerrufen/unbekannt.

## Verworfene Alternativen

- Pro-Nutzer-Ablage (kein Eigentümer), Klartext-Token (Dateileck), Einlösen nach `SaveUser`
  (Race: zwei Konten), Einladung über OAuth/Passkey/Magic-Link (v1-Umfang).

## Folgen

Mehrere gregor-api-Prozesse auf derselben Datei sind nicht abgesichert. Ein nie bestätigtes
Konto verbraucht die Einladung trotzdem.
