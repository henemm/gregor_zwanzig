# ADR-0092: Nutzer-Testmail an die bestätigte Profiladresse über den echten Versandweg

- **Status:** Akzeptiert
- **Datum:** 2026-10-16
- **Bezug:** GitHub-Issue #2521 Scheibe S2, Spec `docs/specs/modules/onboarding_willkommen_checkliste.md`;
  löst die #198-Regel „Testmail nie über Resend" (`docs/specs/_archive/bugfix/bug_198_notify_test_resend.md:20-22`)
  **für echte Nutzer** ab; Bezug ADR-0087 (Empfängerschutz), ADR-0066 (E-Mail-Bestätigung)

## Kontext

Der Testmail-Knopf (`POST /api/notify/test`, Kanal `email`) lenkte seit #198 jede Mail über
`for_testing()` an den Stalwart-Test-Postausgang. Für externe Nutzer scheitert das am
Lokal-Guard (nur `@henemm.com`); fehlt `user.json`, fällt `with_user_profile` auf die globale
Betreiber-Adresse zurück. Ein neu eingeladener Nutzer kann so seine Zustellung nicht prüfen.

## Entscheidung

1. Für echte Nutzer geht die Testmail über die normale Versandkette (Resend, Allowlist,
   ADR-0087) an die bestätigte Profiladresse dieses Nutzers.
2. Testnutzer (`is_test_user`) und Staging bleiben über `force_test` auf Stalwart.
3. Der Dienst sperrt selbst und sendet nichts, mit deutschem Fehlertext, wenn `user_id` leer
   oder `"default"` ist, `user.json` fehlt, `email_verified_at` fehlt oder die Profil-`mail_to`
   leer ist. Es wird nie an die Betreiber-Adresse gesendet.
4. Der Telegram-Zweig bleibt unverändert.

## Konsequenzen

- Eine echte Mail pro Klick; `test_mail_sent_at` belegt Annahme, nicht Zustellung.
- Abgelöst: AC-11-Satz „E-Mail-Zweig des Test-Knopfs bleibt unverändert (#198)" in
  `fix_1412_s4a_empfaengervertrag_telegram.md`.
