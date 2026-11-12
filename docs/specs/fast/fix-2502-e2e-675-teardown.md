# Mini-Spec: fix-2502-e2e-675-teardown

Issue: #2502 · Refs #1196

## Ausgangslage
- `frontend/e2e/issue-675-stage-start-time.spec.ts` legt im `beforeEach` den Trip `e2e-675-starttime` an, räumt ihn aber nie ab.
- Endet ein Lauf (rot oder grün), bleibt der Trip im Konto des Test-Nutzers stehen. Das Trip-Kontingent liegt bei 3; ein liegengebliebener Trip lässt den Seed folgender Suites mit HTTP 409 scheitern, ohne erklärende Meldung.
- Punkt 2 des Issues (AC-3/AC-4 gegen den abgeschafften „Etappen speichern"-Button) ist mit #2243 bereits erledigt: beide Testfälle sind entfernt.

## Was ändert sich
- `test.afterEach` löscht den Trip `e2e-675-starttime` per `DELETE /api/trips/{id}` — läuft auch nach einem roten Test (Playwright führt `afterEach` immer aus).
- Fehler beim Löschen (z. B. 404, weil der Trip schon fehlt) brechen den Lauf nicht ab.

## Was darf sich nicht ändern
- Die vier verbleibenden Testfälle (AC-1, AC-2, AC-5, AC-7) prüfen inhaltlich dasselbe wie vorher.
- `beforeEach` behält das vorsorgliche Löschen vor dem Seed (Schutz gegen Reste aus abgebrochenen Läufen, z. B. Prozessabbruch, bei dem kein `afterEach` mehr läuft).
- Kein Produktcode, keine andere Testdatei.

## Acceptance Criteria
**AC-1:** Given ein Lauf der Suite `issue-675-stage-start-time` gegen Staging, in dem mindestens ein Testfall rot endet, When der Lauf vorbei ist, Then existiert der Trip `e2e-675-starttime` im Konto des Test-Nutzers nicht mehr (`GET /api/trips/e2e-675-starttime` → 404).

**AC-2:** Given ein vollständig grüner Lauf derselben Suite gegen Staging, When der Lauf vorbei ist, Then existiert der Trip `e2e-675-starttime` ebenfalls nicht mehr und alle vier Testfälle sind grün.

## Manuelle Test-Schritte
1. Suite per `playwright.675.config.ts` gegen Staging laufen lassen; danach `GET /api/trips/e2e-675-starttime` als Test-Nutzer → 404.
2. Gegenprobe rot: einen Testfall vorübergehend per String-Ersetzung verfälschen (externe Sicherungskopie), Lauf rot, danach wieder 404. Verfälschung zurücknehmen.
3. Gegenprobe Mutation: `afterEach` entfernen → nach dem Lauf liefert der GET 200 (Nachweis, dass die Prüfung die Wirkung sieht).

## Inline-Test
- [ ] Die Prüfung „Trip nach dem Lauf weg" geschieht aus Nutzersicht über die API gegen Staging (Schritte 1–3), kein Dateiinhalt-Check.
