# ADR-0105: E-Mail-Adresse als Login-Identifier — opake stabile ID plus E-Mail-Lookup

- **Status:** Akzeptiert (Spec-Freigabe 2026-11-02)
- **Datum:** 2026-11-02
- **Bezug:** Issue #2194, Epic #2138 (Multi-User-Readiness), Spec `docs/specs/modules/email_login_identifier.md`; ergänzt ADR-0066 (Verify-Gate), ADR-0067 (Adress-Eindeutigkeit), ADR-0072, ADR-0078 (Admin-ID-Liste), ADR-0084 (Einladungen)
- **Ergänzt durch:** [ADR-0113](0113-anmelde-haertung-adress-limits-testkonto-herkunftspruefung.md) (Punkt 9: Bremsen zusätzlich je Zieladresse, Einmal-Code 8 Ziffern)

## Kontext

Bisher meldet sich ein Nutzer mit einem selbst gewählten Benutzernamen an. Dieser Name ist
zugleich die Konto-ID und der Ordnername unter `data/users/<id>/`. Nutzer müssen sich so einen
zweiten Bezeichner neben ihrer E-Mail-Adresse merken. Für ein Multi-User-Produkt (Epic #2138)
soll die Anmeldung mit der E-Mail-Adresse funktionieren, ohne Ordner, Sitzungen, Passkeys,
Admin-Liste und Einladungen umzubauen und ohne personenbezogene Adressen in Pfade oder Logs
zu schreiben.

## Entscheidung

1. **Opake stabile ID plus E-Mail-Lookup.** Der Ordnername bleibt die Konto-ID; der Login sucht
   das Konto über die E-Mail-Adresse. E-Mail als Ordnername ist verworfen: Verstoß gegen das
   ID-Muster `^[a-zA-Z0-9_-]+$`, personenbezogene Daten in Pfaden/Logs/Backups, ein Adresswechsel
   wäre ein Ordner-Umzug und bräche Session-Cookie, WebAuthn-UserHandle, Admin-Liste
   (ADR-0078) und Einladungen (ADR-0084). Keine Datenmigration.
2. **Lookup-Schlüssel nur `email`, nicht `mail_to`.** `ResolveAddressOwner` ist für den Login
   ungeeignet, weil er `mail_to` mitprüft (Magic-Link-Übernahme-Semantik). Neu ist
   `Store.FindUsersByLoginEmail(addr)`: vergleicht nur `u.Email` (normalisiert: Trim,
   Kleinschreibung), schließt Testkonten aus, liefert alle Treffer, ist fail-closed bei
   unlesbarer `user.json`. Die Eindeutigkeit echter Adressen sichert ADR-0067.
3. **Weiche am `@`.** Eine Eingabe mit `@` führt zum E-Mail-Lookup, ohne `@` bleibt der
   bisherige ID-Pfad unverändert (`@` ist in IDs verboten, die Weiche ist eindeutig). Gilt für
   Login, Passwort vergessen, Verify-Resend, Passkey-Login mit Kennung und
   `staging_verify_token`.
4. **Der ID-Pfad bleibt dauerhaft** (Testkonten, Fixture `tg-live-e2e`, Validator-Konto,
   Bestandskonten ohne `email`). Die Oberfläche fragt nur noch nach der E-Mail-Adresse; das
   Eingabefeld nimmt weiterhin eine ID an.
5. **Mehrfachtreffer gelten als kein Treffer:** Dummy-bcrypt-Vergleich (`burnDummyCompare`,
   #2163), 401 `invalid_credentials`, Log nur mit Anzahlen. Bei 0, 1 und n Treffern läuft genau
   ein bcrypt-Vergleich, die Antwort ist identisch. Ausweg für Betroffene bleibt der ID-Login.
6. **Neue Konten** (Passwort-Registrierung, öffentliche Passkey-Registrierung, Einladungs-Redeem
   nach ADR-0084) erhalten eine generierte ID `u-<8hex>` (`store.NewOpaqueUserID`, crypto/rand,
   Kollisionsprüfung mit Wiederholung, nie Überschreiben). Ein `username` im Registrier-Body wird
   nur für Testkonten (`is_test_user=true`) übernommen.
7. **Reset- und Verify-Links bleiben `?user=<id>`** (keine E-Mail-Adresse in URL oder Referer).
   Das Verify-Gate nach ADR-0066 gilt für den E-Mail-Pfad unverändert.
8. **Login-Antwort** `{"id": <aufgelöste Konto-ID>}` statt Echo der Eingabe.
9. **Rate-Limits** bleiben IP-basiert; ID und E-Mail teilen sich dasselbe Kontingent.

**Bezug ADR-0072 (Testkonto-Status nur über `is_test_user`):** Testkonten sind vom
E-Mail-Lookup ausgeschlossen (`model.IsTestAccount`) und nur per ID erreichbar; ein frei
gewählter `username` bei der Registrierung wird ausschließlich mit `is_test_user=true`
übernommen.

## Konsequenzen

- Bestandskonten behalten ihre selbst gewählten IDs und können sich per E-Mail oder per ID
  anmelden. Konten ohne `email` und Testkonten sind nur per ID erreichbar.
- Entstehen künftig doppelte echte Adressen, scheitert der E-Mail-Login für diese Adresse; der
  ID-Login bleibt der Ausweg (Messung 2026-11-01: keine Duplikate).
- E2E-Hilfen, Validator-Skript und Staging-Hilfen loggen Testkonten weiter per ID ein.
- Nicht Teil dieser Entscheidung: Kopplung `email`/`mail_to` beim Adresswechsel, Härtung von
  `is_test_user` bei der Registrierung (heute ohne Admin-Recht setzbar, bekannter Ist-Zustand).

## Verworfene Alternativen

- **E-Mail-Adresse als Ordnername/Konto-ID:** siehe Entscheidung 1.
- **Gegen alle Passwörter der Mehrfachtreffer prüfen:** die Laufzeit verriete die Anzahl der
  Konten, die Reihenfolge entschiede über den Treffer.
- **Lookup über `ResolveAddressOwner` (inkl. `mail_to`):** eine abweichende Zustelladresse ist
  keine Anmeldekennung.
