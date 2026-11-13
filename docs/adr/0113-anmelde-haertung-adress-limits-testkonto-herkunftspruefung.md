# ADR-0113: Anmelde-Härtung — Einmal-Code mit Bremsen je Zieladresse und 8 Ziffern, Testkonto-Schalter nur Staging/Fixture/Admin, Herkunftsprüfung schreibender Anfragen in Go

- **Status:** Akzeptiert (PO-Auftrag 2026-11-12: alle Befunde des Sicherheits-Reviews beheben)
- **Datum:** 2026-11-12
- **Bezug:** GitHub-Issue #2961, Spec `docs/specs/modules/security_haertung_2026_11_go_anmeldung.md`; ergänzt [ADR-0105](0105-email-als-login-identifier.md) (Punkt 9 Rate-Limits), [ADR-0072](0072-testkonto-status-ausschliesslich-ueber-profilfeld.md) (Testkonto-Flag bei der Registrierung), [ADR-0060](0060-dauerhafte-anmeldung-mit-widerrufsliste.md) (Sitzungs-Cookie), [ADR-0078](0078-admin-rolle-ueber-env-liste-statt-profilfeld.md) (Admin-Kennungen)
- **Ergänzt durch:** —

## Kontext

Ein Sicherheits-Review (2026-11) der Go-API fand im Anmelde- und Sitzungsbereich mehrere
Schwächen, die einzeln klein, zusammen aber relevant sind:

- Der Einmal-Code per Mail war nur je IP gebremst. Eine neue Anforderung ersetzte den
  laufenden Code und setzte den Fehlversuchszähler zurück; der Zähler wurde erst geprüft und
  danach erhöht. Der Code hatte sechs Ziffern.
- Der Testkonto-Schalter `is_test_user` war bei der öffentlichen Registrierung frei setzbar und
  erlaubte damit eine selbst gewählte Konto-Kennung, auch in Produktion. Ein vorhandener
  Kontoordner ohne `user.json` galt als frei; die Anlage war nicht exklusiv.
- Schreibende Anfragen waren gegen fremde Webseiten nur über `SameSite=Lax` des
  Sitzungs-Cookies geschützt; Go prüfte weder Herkunft noch Inhaltstyp noch Rumpfgröße.

## Entscheidung

1. **Einmal-Code (ergänzt ADR-0105 Punkt 9).** Zusätzlich zur IP-Bremse gelten Bremsen je
   Zieladresse: höchstens 5 Fehlversuche in jedem 15-Minuten-Intervall (gleitendes Fenster,
   kein Rücksetzen an einem festen Zeitrand), danach ist die Code-Anmeldung dieser
   Adresse 15 Minuten gesperrt (neutrale Antwort, auch für den richtigen Code); der Zähler
   überlebt eine Neuanforderung und wird vor dem Vergleich erhöht. Höchstens 5 Code-Mails je
   Adresse und Stunde, darüber neutrale Erfolgsantwort ohne Versand. Ein noch gültiger Code
   wird bei erneuter Anforderung erneut zugestellt statt ersetzt. Der Code hat 8 Ziffern,
   gleichverteilt aus `crypto/rand`, und wird in konstanter Zeit verglichen. IPv6-Absender
   zählen im IP-Limiter je /64-Netz; die Limiter-Tabelle ist begrenzt.
2. **Testkonto-Schalter (ergänzt ADR-0072).** `is_test_user` (und damit die frei wählbare
   Kennung) wird bei der Registrierung nur angenommen, wenn `GZ_ENV=staging`, der
   Fixture-Modus aktiv ist (`GZ_TEST_FIXTURE_DIR`) oder der Aufrufer eine gültige
   Admin-Sitzung hat; sonst `400 validation_failed`. Reservierte Kennungen (`default`,
   `admin`, `root`, `system`) sind nie registrierbar; Kennungen aus `GZ_ADMIN_USER_IDS` und
   `GZ_QUOTA_EXEMPT_USER_IDS` (beide ohne Groß-/Kleinschreibung verglichen) belegt eine
   Registrierung auch im Staging/Fixture-Modus nur mit gültiger Admin-Sitzung. Ein vorhandener Kontoordner gilt als
   belegt, auch ohne `user.json`; die Anlage ist exklusiv. Beim Start wird jede Kennung aus
   `GZ_ADMIN_USER_IDS`/`GZ_QUOTA_EXEMPT_USER_IDS` ohne Konto als Warnung geloggt (ergänzt
   ADR-0078).
3. **Herkunftsprüfung in Go (ergänzt ADR-0060).** Eine globale Schutzschicht vor der
   Anmeldeprüfung weist schreibende Anfragen (`POST/PUT/PATCH/DELETE` unter `/api/`) mit
   fremdem `Origin` oder einem `Sec-Fetch-Site` außer `same-origin`/`none` mit
   `403 origin_forbidden` ab. Erlaubt ist der aus `GZ_PUBLIC_HOST` abgeleitete Ursprung (plus
   die Passkey-Ursprungsliste), im Staging, im Fixture-Modus und bei lokalem `GZ_PUBLIC_HOST`
   zusätzlich localhost. Fehlen beide Header (Server-zu-Server), wird durchgelassen.
   Rümpfe müssen `application/json` sein (`415`), ausgenommen der GPX-Upload (multipart).
   Rümpfe sind auf 1 MB begrenzt (GPX-Upload 10 MB, `413`). Ausgenommen sind Webhooks,
   interne Pfade, der Maschinen-Status und der OAuth-Rückruf.
4. **Zugriffslog und Webhook-Rümpfe.** Das Zugriffslog maskiert Pfadgeheimnisse der Webhooks
   und geheime Query-Werte (`code`, `state`, `token`, `id_token`, `access_token`, `invite`,
   `secret`, `password`), abgeleitet aus der geparsten URL. Der Telegram-Eingang liest
   höchstens 1 MB Rumpf.
5. **Maschinen-Geheimnisse.** `GZ_STATUS_TOKEN` und die selbst gewählten Webhook-Secrets
   sollen mindestens 32 Zeichen haben; ein kürzerer gesetzter Wert erzeugt beim Start eine
   Warnzeile, der Endpunkt bleibt mit diesem Wert in Betrieb. Der Seven-Signierschlüssel
   (vom Anbieter vergeben) ist ausgenommen.

## Verworfene Alternativen

- **CSRF-Token je Formular** — verlangt Änderungen an jedem schreibenden Frontend-Aufruf und
  an den Server-Routen; die Herkunftsprüfung erreicht dasselbe Schutzziel für Browser
  ohne Frontend-Umbau.
- **Testkonto-Schalter ganz entfernen** — Staging-Validator, Fixture-Stack und E2E-Zweitnutzer
  brauchen feste Kennungen; die Beschränkung auf Staging/Fixture/Admin genügt.
- **Startabbruch oder geschlossener Endpunkt bei zu kurzen Maschinen-Geheimnissen** — ein
  Deploy darf weder Produktion noch einen Eingangskanal (Telegram-/SMS-/Mail-Webhook,
  Betriebsstatus) still ausfallen lassen; die Längen der Betriebswerte sind vorab nicht
  prüfbar. Stattdessen: Warnzeile beim Start, der Endpunkt arbeitet mit dem konfigurierten
  Wert weiter; fail-closed bleibt nur „kein Geheimnis gesetzt“.

## Konsequenzen

- **Positiv:** Code-Raten über viele IPs oder durch Neuanforderungen scheitert an der
  Adress-Bremse; ein Fremder kann den laufenden Code eines Nutzers nicht entwerten. Keine
  Produktions-Registrierung mit frei gewählter Kennung. Fremde Webseiten können keine
  schreibenden Aktionen im Namen eines angemeldeten Nutzers auslösen.
- **Negativ / Preis:** Nach 5 Fehlversuchen wartet auch der echte Nutzer bis zu 15 Minuten.
  Die Bremsen sind prozessintern (Neustart setzt sie zurück). Skripte, die schreibend ohne
  `Content-Type: application/json` aufrufen, bekommen `415`.
- **Folgepflichten:** `GZ_PUBLIC_HOST` muss in jeder Umgebung der öffentliche Ursprung sein;
  der Reverse-Proxy reicht `Origin` unverändert durch. Neue Browser-Ursprünge (zweite
  Domain) gehören in `GZ_PUBLIC_HOST`/`GZ_WEBAUTHN_RP_ORIGINS`. Ein Testkonto in Produktion
  entsteht nur über eine Admin-Sitzung.
