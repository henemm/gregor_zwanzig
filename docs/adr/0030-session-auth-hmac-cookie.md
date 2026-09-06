# ADR-0030: Session-Auth über HMAC-signiertes Cookie (kein JWT, keine Server-Session-Tabelle)

- **Status:** Abgelöst durch [ADR-0060](0060-dauerhafte-anmeldung-mit-widerrufsliste.md) (2026-09-05, Issue #2129) — ursprünglich akzeptiert, rückwirkend dokumentiert 2026-07-22 (gelebte Praxis seit der Auth-Einführung, Issue #1343)

> **Nachtrag 2026-09-05:** Die unten unter „Verworfene Alternativen" genannte
> Begründung, eine serverseitige Sitzungsverwaltung sei „bei 24h-TTL und
> Passwortwechsel als Notweg" verzichtbar, traf nicht zu: Der Passwortwechsel
> hat bestehende Sitzungen nie invalidiert. Es gab also keinen Notweg.
> ADR-0060 ersetzt die TTL durch eine dateibasierte Liste gültiger Sitzungen.
- **Datum:** 2026-07-22
- **Bezug:** `internal/middleware/auth.go`, `docs/reference/api_contract.md` (Session-Cookie-Format)

## Kontext

Das Produkt braucht Mandantentrennung (ADR-0003) mit einfacher, selbst
gehosteter Auth ohne externe Identity-Provider-Pflicht. Nutzerzahl ist klein
(derzeit keine aktiven Produktiv-User außer dem PO), Betrieb auf einem
einzelnen VServer.

## Entscheidung

Sessions sind ein HMAC-signiertes Cookie `gz_session` im Format
`{userId}.{timestamp}.{hmacSig}` — HttpOnly, SameSite=Lax, MaxAge 86400,
Secure auf HTTPS (`internal/middleware/auth.go`). Es gibt keine serverseitige
Session-Tabelle: Gültigkeit = Signatur + TTL. Login-Wege: Passwort, Passkey
(WebAuthn), Magic-Link, Google OAuth (feature-gated), Telegram-Link.

## Verworfene Alternativen

- **JWT** — bringt Standard-Overhead (Key-Rotation, Claim-Semantik) ohne
  Mehrwert bei einem einzigen Backend; Cookie+HMAC ist gleich sicher und
  kleiner.
- **Serverseitige Session-Tabelle** — ermöglicht Einzel-Session-Revocation,
  kostet aber Persistenz-/Sync-Aufwand; bei 24h-TTL und Passwortwechsel als
  Notweg bewusst verzichtet.

## Konsequenzen

- **Positiv:** Stateless, kein Session-Store, trivialer Restart.
- **Negativ / Preis:** Keine Einzel-Session-Invalidierung vor Ablauf; Schutz
  hängt am HMAC-Secret (Server-Secret-Hygiene!).
- **Folgepflichten:** Cookie-Format ist API-Vertrag (Validator/E2E nutzen es);
  Änderungen nur mit neuem ADR + Migrationspfad.
