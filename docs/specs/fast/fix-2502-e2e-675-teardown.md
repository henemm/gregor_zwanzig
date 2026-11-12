# Mini-Spec: fix-2502-e2e-675-teardown

Issue: #2502 · Refs #1196 · Refs #2947 (Umfangserweiterung 2026-11-12)

## Ausgangslage
- `frontend/e2e/issue-675-stage-start-time.spec.ts` legt im `beforeEach` den Trip `e2e-675-starttime` an, räumt ihn aber nie ab.
- Endet ein Lauf (rot oder grün), bleibt der Trip im Konto des Test-Nutzers stehen. Das Trip-Kontingent liegt bei 3; ein liegengebliebener Trip lässt den Seed folgender Suites mit HTTP 409 scheitern, ohne erklärende Meldung.
- Punkt 2 des Issues (AC-3/AC-4 gegen den abgeschafften „Etappen speichern"-Button) ist mit #2243 bereits erledigt: beide Testfälle sind entfernt.
- **Beim Umsetzen gefunden (#2947):** Der Testfall „Geleertes Feld fällt auf 08:00 zurück" war rot. Teils veraltete Bedienfolge (seit #2881 meldet das Uhrzeitfeld ein geleertes Feld erst beim Verlassen), teils echter Produktfehler: Wer eine Startzeit mit zweistelliger Stunde (10–23) leert, bekommt die Zehnerziffer gespeichert (15:00 → 01:00) statt des Standards 08:00. Ursache in `frontend/src/lib/components/molecules/UhrzeitFeld.svelte`: Nach der ersten Rücktaste wird „01:00" als offener Zwischenwert zurückgehalten; das anschließende Leeren verwirft ihn nicht, beim Verlassen wird er gemeldet und gespeichert. Das gewünschte Verhalten (geleert ⇒ 08:00) ist seit #675 festgelegt.

## Was ändert sich
- `test.afterEach` löscht den Trip `e2e-675-starttime` per `DELETE /api/trips/{id}` — läuft auch nach einem roten Test (Playwright führt `afterEach` immer aus). Fehler beim Löschen (z. B. 404) brechen den Lauf nicht ab.
- Testfall AC-5 der Suite: Bedienfolge um „Feld verlassen" ergänzt; die Zusicherung (08:00) bleibt unverändert.
- `UhrzeitFeld`: Wird das Feld vollständig geleert, verwirft es einen zurückgehaltenen Zwischenwert und meldet beim Verlassen „leer". Eng begrenzte Korrektur in `UhrzeitFeld.svelte` (ggf. `segmentFeldMeldung.ts`), dazu ein deterministischer Komponententest (`node --test`), der den Fall 15:00 → leeren → „leer" abdeckt.

## Was darf sich nicht ändern
- Die vier Testfälle (AC-1, AC-2, AC-5, AC-7) prüfen inhaltlich dasselbe wie vorher.
- `beforeEach` behält das vorsorgliche Löschen vor dem Seed.
- Das Uhrzeitfeld verhält sich bei normaler Eingabe unverändert: Tippen einer Uhrzeit, Teil-Eingaben während des Tippens werden weiterhin nicht vorzeitig gespeichert, Leeren aus 07:30 (Design-System-Test DS-2) bleibt grün.
- Keine weitere Produktdatei außer den oben genannten.

## Acceptance Criteria
- **AC-1:** Given ein Lauf der Suite `issue-675-stage-start-time` gegen Staging, in dem mindestens ein Testfall rot endet, When der Lauf vorbei ist, Then existiert der Trip `e2e-675-starttime` im Konto des Test-Nutzers nicht mehr (`GET /api/trips/e2e-675-starttime` → 404).

- **AC-2:** Given ein vollständig grüner Lauf derselben Suite gegen Staging, When der Lauf vorbei ist, Then existiert der Trip `e2e-675-starttime` ebenfalls nicht mehr und alle vier Testfälle sind grün.

- **AC-3:** Given eine Etappe mit Startzeit 15:00 im Etappen-Editor, When der Nutzer im Stunden-Segment zweimal die Rücktaste drückt und das Feld verlässt, Then wird keine Startzeit 01:00 gespeichert, und die Ankunftszeit des ersten Wegpunkts zeigt 08:00.

- **AC-4:** Given das Uhrzeitfeld mit Wert 07:30 (Design-System-Seite), When der Nutzer es wie bisher leert, Then verhält es sich unverändert (Test DS-2 bleibt grün), und eine normal getippte Uhrzeit wird weiterhin unverändert übernommen.

## Manuelle Test-Schritte
1. Suite per `playwright.675.config.ts` gegen Staging (nach Deploy der Korrektur) laufen lassen: vier Fälle grün; danach `GET /api/trips/e2e-675-starttime` als Test-Nutzer → 404.
2. Gegenprobe rot: einen Testfall vorübergehend per String-Ersetzung verfälschen (externe Sicherungskopie), Lauf rot, danach wieder 404.
3. Gegenprobe Mutation: `afterEach` entfernen → nach dem Lauf liefert der GET 200; Korrektur im Uhrzeitfeld entfernen → Komponententest und AC-5 rot.

## Inline-Test
- [ ] Die Prüfung „Trip nach dem Lauf weg" geschieht aus Nutzersicht über die API gegen Staging, kein Dateiinhalt-Check.
- [ ] Der Leeren-Fall ist im Komponententest (deterministisch) und im E2E-Fall AC-5 (Staging) abgedeckt.
