# ADR-0006: Keine gemockten Tests; echte E2E-Verifikation gegen Staging

- **Status:** Akzeptiert
- **Datum:** 2026-04-26 (E2E-gegen-Staging-Grundsatz, Issue #339)
- **Bezug:** `CLAUDE.md` → „KEINE MOCKED TESTS", „E2E-Verifikation"; GitHub-Issues #339, #521, #564

## Kontext

Gemockte Tests beweisen, dass Code *gegen das Mock-Verhalten* funktioniert — nicht, dass er gegen
echte E-Mail-Server, echte Wetter-APIs oder die echte laufende App funktioniert. In einem Produkt,
dessen Kern „Briefing wird korrekt gerendert und tatsächlich zugestellt" ist, geben Mocks ein
falsches Sicherheitsgefühl. Ebenso beweist ein lokaler Neustart des Live-Servers nichts über den
deployten Stand (lokale Maschine = Produktion).

## Entscheidung

1. **Keine gemockten Tests** für E-Mail- und API-Verhalten. E-Mail-Tests senden echte Mails (über
   das Stalwart-Test-Postfach) und prüfen den Inhalt per IMAP; API-Tests machen echte API-Calls.
   Auch reine Dateiinhalt-Checks (`assert 'x' in file.read_text()`) sind kein Verhaltensnachweis.
   Mindestens ein Test muss den Bug aus **Nutzerperspektive** reproduzieren (rot vor Fix, grün danach).
   *Ausnahme:* Dokumentations-Compliance-Tests, markiert mit `# doc-compliance-test`.
2. **Echte E2E-Verifikation läuft nach dem Push gegen Staging** (`staging.gregor20.henemm.com`) —
   nie durch lokalen Neustart des Live-Servers. Der Prod-Deploy ist über `e2e_verified.json`
   (`verified_commit` + `staging_verdict`) als **Hard Gate** abgesichert (#521); nach dem Deploy
   verifiziert ein Post-Deploy-Selftest gegen Produktion (#564).

## Verworfene Alternativen

- **Unit-Tests mit Mocks für Mail/API** — verworfen: testen das Mock, nicht das echte Verhalten;
  haben in der Vergangenheit Defekte durchrutschen lassen.
- **Verifikation durch lokalen Live-Server-Neustart** — verworfen: gefährdet die Produktion und
  sagt nichts über den deployten Stand aus.

## Konsequenzen

- **Positiv:** Tests beweisen echtes Verhalten end-to-end; das Deploy-Gate verhindert, dass ein
  unverifizierter oder falscher Commit Produktion erreicht.
- **Negativ / Preis:** Tests sind langsamer und brauchen echte Infrastruktur (Test-Postfach,
  Staging, Credentials); die Verifikationskette ist aufwändiger als ein lokaler Testlauf.
- **Folgepflichten:** Test-Mails gehen nur an `gregor-test@henemm.com`; kein Sammelversand. Der
  jeweils passende Mail-Validator muss vor „E2E bestanden" Exit 0 liefern (siehe
  `docs/reference/mail_validators.md`).
