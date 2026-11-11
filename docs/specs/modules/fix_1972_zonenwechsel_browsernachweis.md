---
entity_id: fix_1972_zonenwechsel_browsernachweis
type: bugfix
created: 2026-11-11
updated: 2026-11-11
status: draft
version: "1.0"
workflow: fix-1972-zonenwechsel-browsernachweis
tags: [e2e, playwright, zeitzone, konto, scheduler, "#1972", "#2729"]
---

# AC-7 nachholen: Zonenwechsel der Scheduler-Zeit „Nächste Prüfung" im echten Browser belegen

## Approval

- [ ] Approved

## Purpose

Die Konto-Seite zeigt die Zeile „Nächste Prüfung" in der Zeitzone des Browsers, mit Zonenkürzel. Bisher ist das nur im Unit-Test belegt; der Browsernachweis (AC-7 aus `fix_1727_s5e_sperrcache_anzeige.md`) wurde am 2026-08-19 vom PO zurückgestellt, weil Staging wegen #1329 keinen echten Termin liefert. Diese reine Test-Scheibe holt den Nachweis nach, ohne Produktänderung: Der Browsertest ersetzt bei clientseitiger Navigation in der SvelteKit-Datenantwort den Nullwert durch einen festen Wintertermin, die echte Seite formatiert ihn dann in der Browserzone.

## Source

- **File:** `frontend/e2e/konto-naechste-pruefung.staging.spec.ts`
- **Identifier:** neuer Test „Zonenwechsel Wien / New York" (AC-7), neben dem bestehenden AC-4/AC-9-Test

> **Schicht-Hinweis:** Betroffen ist ausschließlich die Frontend-E2E-Schicht (`frontend/e2e/`) plus Doku (`docs/specs/`). Kein Go-Code (`internal/`), kein Python-Core, kein Produktcode unter `frontend/src/`.

> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** nicht betroffen (Konto-Seite hat kein Compare-Pendant, es entsteht keine neue Komponente).
> - **Mandantentrennung:** Es entsteht kein neuer Datenweg und kein Endpunkt; der Test liest die ohnehin nutzergebundene Antwort des angemeldeten Staging-Testnutzers und verändert nur, was sein eigener Browser empfängt. Ein Zwei-Nutzer-Test entfällt mangels Datenbewegung.
> - **Kanäle:** nicht betroffen (keine Briefing- oder Alarm-Inhalte).

## Estimated Scope

- **LoC:** ca. +80/-15
- **Files:** 3 (1 Test, 2 Doku)
- **Effort:** low

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| SvelteKit-Clientnavigation (Sidebar-Benutzermenü → „Konto", `Sidebar.svelte`) | Frontend-Mechanik | holt `/account/__data.json` im Browser statt per SSR; einzige abfangbare Stelle |
| `formatNextRun` in `frontend/src/lib/utils/schedulerTime.ts` | Funktion (unverändert) | formatiert in Browserzone mit `timeZoneName: 'short'`, Nullwert → „—"; Prüfgegenstand |
| `frontend/src/routes/account/+page.svelte` (`imBrowser` in `onMount`) | Komponente (unverändert) | rendert die Zeile erst im Browser, Serverzone wird nie sichtbar |
| Go `StatusForUser` (`internal/scheduler/scheduler.go`) | Quelle (unverändert) | liefert auf Staging den echten Nullwert `0001-01-01T00:00:00Z` |
| Staging-Gate #1329 (`scheduler_gate.go`) | Rahmenbedingung | Scheduler auf Staging aus; bleibt aus |
| `frontend/e2e/prodUrlGuard` (`assertNotProdBaseURL`) | Schutz | Test läuft nie gegen Produktion |
| `frontend/e2e/playwright.konto-naechste-pruefung.staging.config.ts` | Testkonfiguration | gleicher Login und gleiche Config wie der bestehende Test |
| `fix_1727_s5e_sperrcache_anzeige.md` | Ursprungs-Spec | AC-4/AC-7/AC-9; Nachweisort AC-7 wird dort nachgetragen |

## Implementation Details

Reiner Testcode, Ablauf je Zone (Europe/Vienna und America/New_York), jeweils in einem eigenen Browser-Kontext mit `timezoneId` (der Kontext erbt `use`-Optionen nicht, Login/Sprache werden wie im bestehenden Test gesetzt):

1. Route `**/account/__data.json*` registrieren, bevor irgendetwas navigiert wird (Preload beim Überfahren des Menüs kann die Datenantwort schon vorab holen).
2. Die echte Antwort per `route.fetch()` holen, im Antworttext den exakten String `0001-01-01T00:00:00Z` durch den festen Wintertermin `2026-12-15T05:00:00Z` ersetzen (String-Ersetzung, kein Parsing des devalue-Formats), per `route.fulfill()` ausliefern. Jede tatsächlich erfolgte Ersetzung erhöht einen Zähler.
3. Startseite laden, Benutzermenü öffnen, „Konto" anklicken (clientseitige Navigation, nicht `page.goto('/account')`), Zeile „Nächste Prüfung" lesen.
4. Zusicherungen: (a) Zähler > 0, sonst Fehlschlag mit klarem Text („Abfang hat nicht gegriffen, kein Nachweis"); (b) Wien-Zeile zeigt 06:00 und das Wiener Zonenkürzel, New-York-Zeile 00:00 und das New-York-Kürzel; (c) die Uhrzeiten beider Zonen sind verschieden; (d) die Sollwerte sind konkret (05:00Z → 06:00 Wien, 00:00 New York), nicht nur „verschieden".

Die Kürzel hängen von Zone und Sprache des Testnutzers ab (DE, #2652). Erwartet wird das für die Zone und Sprache gültige Kürzel; es wird in /40 einmal gemessen und danach fest erwartet (keine Raten-Liste im Test). Die Erwartung läuft über das Kürzel, nicht über eine feste Stundendifferenz.

Der Kopfkommentar „WAS HIER BEWUSST NICHT GEPRUEFT WIRD" im Testfile wird angepasst: AC-7 ist jetzt belegt; der echte Nullwert für AC-9 bleibt im bestehenden Test unverändert der Nachweis. In der Ursprungs-Spec wird bei AC-7 und in den Known Limitations der Nachweisort (dieser Test, Issue #1972) nachgetragen.

Mutations-Gegenproben (in /50 per String-Ersetzung mit externer Sicherungskopie, nie `git checkout/stash/reset`):
- `timeZone: 'UTC'` in `formatNextRun` erzwungen → beide Zonen gleich → Test rot.
- `timeZoneName` entfernt → Kürzel fehlt → Test rot.
- Route-Muster falsch (greift nicht) → Zusicherung (a) rot.

## Expected Behavior

- **Input:** Staging-Testnutzer (DE) öffnet per Sidebar-Menü die Konto-Seite in einem Browser mit gesetzter Zeitzone; die Datenantwort enthält den abgefangenen Wintertermin.
- **Output:** Die Zeile „Nächste Prüfung" zeigt den Termin in der jeweiligen Browserzone mit passendem Kürzel.
- **Side effects:** keine. Kein Produktcode, kein Staging-Scheduler, keine neuen Endpunkte, kein Open-Meteo-Verbrauch, kein Versand.

## Acceptance Criteria

- **AC-1:** Given ein Browser mit Zeitzone Europe/Vienna und eine Konto-Seite, deren Scheduler-Termin den festen Wintertermin 05:00 UTC liefert / When der Nutzer über das Benutzermenü zur Konto-Seite navigiert / Then zeigt die Zeile „Nächste Prüfung" die konkrete Sollzeit 06:00 zusammen mit dem für Wien und die Nutzersprache gültigen Zonenkürzel.
  - Test: Playwright-Browsertest auf Staging, Kontext mit `timezoneId: 'Europe/Vienna'`, Zeile auslesen und auf 06:00 plus fest gemessenes Wiener Kürzel prüfen.

- **AC-2:** Given ein Browser mit Zeitzone America/New_York und derselbe feste Wintertermin 05:00 UTC / When der Nutzer über das Benutzermenü zur Konto-Seite navigiert / Then zeigt die Zeile „Nächste Prüfung" die konkrete Sollzeit 00:00 zusammen mit dem für New York und die Nutzersprache gültigen Zonenkürzel.
  - Test: Playwright-Browsertest auf Staging, Kontext mit `timezoneId: 'America/New_York'`, Zeile auslesen und auf 00:00 plus fest gemessenes New-York-Kürzel prüfen.

- **AC-3:** Given beide Zonenläufe haben denselben Termin angezeigt / When die beiden ausgelesenen Zeilen verglichen werden / Then unterscheiden sich die Uhrzeiten und die Zonenkürzel, und die Abweichung entspricht den konkreten Sollwerten aus AC-1 und AC-2 und nicht nur der Tatsache „verschieden".
  - Test: Vergleich der Texte beider Läufe im selben Browsertest; gleiche Uhrzeit in beiden Zonen lässt den Test fehlschlagen.

- **AC-4:** Given der Abfang der Datenantwort hat nicht gegriffen (falsches Route-Muster, geändertes Datenformat oder kein Nullwert in der Antwort) / When der Test läuft / Then schlägt er mit einem klaren Fehltext fehl („Abfang hat nicht gegriffen") und wird nicht still grün.
  - Test: Zähler der tatsächlich ersetzten Antworten wird vor allen Zeitzusicherungen geprüft (Zähler > 0); Mutations-Gegenprobe mit falschem Route-Muster macht genau diese Zusicherung rot.

- **AC-5:** Given der bestehende Test für „Nächste Prüfung: —" bei echtem Staging-Nullwert (AC-9 der Ursprungs-Spec) / When die gesamte Datei `konto-naechste-pruefung.staging.spec.ts` läuft / Then bleibt dieser Test unverändert grün, und der Nullwert wird weiterhin ungestubbt als „—" angezeigt.
  - Test: bestehender Test läuft unverändert mit; sein Abfang-Code wird nicht angefasst und der neue Abfang gilt nur im neuen Test.

- **AC-6:** Given die Änderung ist umgesetzt / When der Diff geprüft wird / Then ist ausschließlich Testcode und Doku betroffen: kein Produktcode unter `frontend/src/`, `internal/` oder `src/`, kein gestarteter Staging-Scheduler (#1329) und kein neuer Endpunkt.
  - Test: Verhaltensnachweis über den Testlauf: der AC-5-Test liefert auf Staging weiterhin den echten, ungestubbten Nullwert „—" (Scheduler aus). Die Beschränkung auf `frontend/e2e/…` und `docs/specs/…` ist ein Review-Schritt am Pull Request, kein Verhaltenstest.

- **AC-7:** Given der Test wird mit einer Basis-URL gestartet, die auf Produktion zeigt / When der Test anläuft / Then bricht er sofort über `assertNotProdBaseURL` ab und greift nie auf Produktion zu.
  - Test: der neue Test ruft denselben Schutz wie der bestehende Test vor jeder Navigation auf; Probelauf mit Produktions-URL bricht ab.

- **AC-8:** Given die drei Mutationen `timeZone: 'UTC'` erzwungen, `timeZoneName` entfernt und falsches Route-Muster / When der Test je Mutation gegen die verfälschte Umgebung läuft / Then ist er jedes Mal rot (zeitgleiche Uhrzeiten, fehlendes Kürzel, Abfang nicht gegriffen).
  - Test: Mutationsläufe in /50 per String-Ersetzung mit externer Sicherungskopie; alle drei Verfälschungen müssen den Test rot machen, danach wird der Originalzustand wiederhergestellt und der Test ist grün.

## Scope

**In Scope:**
- Neuer Browsertest „Zonenwechsel Wien / New York" in `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` (gleiche Config `frontend/e2e/playwright.konto-naechste-pruefung.staging.config.ts`, gleicher Login).
- Angepasster Kopfkommentar „WAS HIER BEWUSST NICHT GEPRUEFT WIRD" im selben Testfile.
- Nachtrag des Nachweisorts für AC-7 (und Known Limitations) in `docs/specs/modules/fix_1727_s5e_sperrcache_anzeige.md`.

**Out of Scope:**
- Jede Änderung an Produktcode (`frontend/src/`, `internal/`, `api/`, `src/`).
- Staging-Scheduler einschalten oder Trockenlauf-Schalter (#1329 bleibt unangetastet).
- Neue Endpunkte, Staging-Seeds oder clientseitiges Nachladen des Scheduler-Status.
- Ausgabetest dafür, dass die Serverzone (`Etc/UTC`) nie sichtbar wird (bleibt Bauweise-Vorgabe, siehe Known Limitations).

## Definition of Done

- AC-1 bis AC-8 sind erfüllt und durch die genannten Tests belegt.
- Der neue Browsertest ist gegen Staging grün; der bestehende AC-4/AC-9-Test in derselben Datei ist unverändert grün.
- Alle drei Mutations-Gegenproben (AC-8) waren rot, der Originalzustand danach wieder grün.
- Die Ursprungs-Spec `fix_1727_s5e_sperrcache_anzeige.md` nennt bei AC-7 den Nachweisort (dieser Test, #1972).
- Der Pull Request enthält ausschließlich Dateien unter `frontend/e2e/` und `docs/`.

## Test Plan

| Test | Ebene | Belegt |
|------|-------|--------|
| `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` — neuer Test „Zonenwechsel Wien / New York" | Playwright-Browsertest gegen Staging (Live-E2E-Schicht) | AC-1, AC-2, AC-3, AC-4, AC-7 |
| `frontend/e2e/konto-naechste-pruefung.staging.spec.ts` — bestehender Test „Nächste Prüfung" / Nullwert „—" | Playwright-Browsertest gegen Staging, unverändert | AC-5, AC-6 (Scheduler bleibt aus) |
| Mutationsläufe (`timeZone: 'UTC'`, `timeZoneName` entfernt, falsches Route-Muster) | Adversary-Gegenprobe in /50 per String-Ersetzung mit externer Sicherungskopie | AC-8, AC-4 |
| Bestehende Unit-Tests `frontend/src/lib/utils/__tests__/schedulerTime*.test.ts` | Kern-Schicht (`node --test`), unverändert | Formatierung bleibt grün (Regression) |

RED-Nachweis in /40: Ohne Abfang (bzw. mit Route-Muster, das nicht greift) zeigt Staging den Nullwert „—", der neue Test ist rot mit dem Fehltext „Abfang hat nicht gegriffen" bzw. an den fehlenden Sollzeiten 06:00 / 00:00.

## Known Limitations

- **Datenquelle ist gestellt, nicht echt:** Der Termin stammt aus dem Abfang, nicht aus einem laufenden Scheduler. Das ist für AC-7 unerheblich (Prüfgegenstand ist die Zonenumrechnung im Browser), belegt aber nicht, dass Produktion den Termin korrekt liefert; das deckt der Scheduler-Test ab.
- **Format-Abhängigkeit:** Die Ersetzung setzt voraus, dass der Nullwert im `__data.json` (devalue-Format von SvelteKit) als exakter String `0001-01-01T00:00:00Z` vorkommt. Ändert ein SvelteKit-Update das Format, wird Zusicherung (a) rot (kein stilles Grün) und die Ersetzung muss nachgezogen werden.
- **SSR-Erstaufruf nicht abgefangen:** Ein direkter `page.goto('/account')` lädt serverseitig; dort greift `page.route()` nicht. Der Test nutzt deshalb bewusst die clientseitige Navigation (der echte Nutzerweg über das Menü).
- **Serverzone-Nichtsichtbarkeit weiterhin nur durch Bauweise:** Dass der Node-Server (`Etc/UTC`) nie eine Zeit rendert (`imBrowser` erst in `onMount`), wird durch diesen Test nicht eigens geprüft, weil der Erstaufruf nicht abfangbar ist; es bleibt eine Bauweise-Vorgabe wie in der Ursprungs-Spec.
- **Zonenkürzel sind sprach- und Browserabhängig:** Die exakten Kürzel (DE-Testnutzer) werden in /40 einmal gemessen und dann fest erwartet; ändern sich Browser- oder ICU-Daten, muss die Erwartung bewusst angepasst werden.
- **Preload:** Wurde die Datenantwort durch Hover-Preload vorab geholt, greift nur eine vorher registrierte Route; deshalb wird die Route vor jeder Navigation gesetzt.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Reine Testmaßnahme innerhalb der bestehenden Test-Politik (Browsertest auf Staging, kein Produktcode); es wird keine Entscheidungsfläche (Kanäle, Provider, Datenmodell, Auth, Test-/Deploy-Strategie) verändert. Das Staging-Gate #1329 bleibt unangetastet.

## Changelog

- 2026-11-11: Initial spec created (Issue #1972, Epic #2729)
- 2026-11-11: Pflicht-Sektionen Scope, Definition of Done, Test Plan ergänzt (CI-Spec-Gate)
