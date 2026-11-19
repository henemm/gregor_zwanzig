# Mini-Spec: fix-2973-hub-anker-warten

Issue #2973 (Epic #2913). Der Staging-Abnahme-Lauf des Elementlisten-Abgleichs liest in der Gegenrichtung die Hub-Anker (Kopf `[data-seite="hub"][data-abschnitt="kopf"]`, Reiterfläche) einmalig; bei langsamer Staging-Antwort fehlt ein Anker kurzzeitig, der Lauf wird rot („Hub-Marker fehlt“), die Wiederholung ist grün.

## Was ändert sich
- Neue reine Funktion `warteAufHubAnker(zaehle, warte, opt)` in `frontend/e2e/elementliste_abgleich_logik.ts`: ruft `zaehle()` bis `pruefeHubAnker(anker) === null` oder bis die Versuche aufgebraucht sind (Vorgabe 10 Versuche, 500 ms Abstand = ~5 s), wartet zwischen den Versuchen mit `warte(ms)` und gibt den letzten Anker-Befund zurück.
- `texteUnterHub` in `frontend/e2e/elementliste-abgleich.staging.spec.ts` nutzt sie (zählen per `page.evaluate(zaehleAnker, …)`, warten per `page.waitForTimeout`) vor dem Lesen der Texte.

## Was darf sich nicht ändern
- Fail-closed: Fehlt ein Anker auch nach allen Versuchen, bleibt die Gegenrichtung „nicht prüfbar“ (`ohneHub`) und der Abnahme-Lauf rot — kein stilles „kein zusaetzlich“.
- Erscheinen die Anker sofort, wird nicht gewartet (kein zusätzlicher Zeitverlust).
- Keine Änderung an Liste, Besitzerliste, Bewertung oder Exit-Logik.

## Acceptance Criteria
- **AC-1:** Given die Hub-Anker erscheinen erst beim dritten Zählen / When `warteAufHubAnker` läuft / Then liefert es den vollständigen Anker-Befund nach genau drei Zählungen und zwei Wartepausen.
- **AC-2:** Given ein Anker fehlt bei jedem Zählen / When `warteAufHubAnker` mit 4 Versuchen läuft / Then gibt es nach 4 Zählungen den unvollständigen Befund zurück, `pruefeHubAnker` meldet weiter den fehlenden Anker (fail-closed).
- **AC-3:** Given beide Anker sind sofort da / When `warteAufHubAnker` läuft / Then zählt es genau einmal und wartet nicht.
- **AC-4:** Given der Staging-Lauf / When `texteUnterHub` die Gegenrichtung liest / Then wartet es über `warteAufHubAnker` auf die Anker, bevor es die Texte liest.

## Manuelle Test-Schritte
1. `cd frontend && npm test -- src/lib/__tests__/elementliste_hub_anker_2973.test.ts`
2. Staging: `npm run elementliste:abgleich -- --scope uebersicht` läuft grün durch.

## Inline-Test (wird während Implementierung geschrieben)
- [ ] `frontend/src/lib/__tests__/elementliste_hub_anker_2973.test.ts`: AC-1 bis AC-3 mit echten Zähl-/Wartefunktionen (Zähler-Liste, Warte-Protokoll), ohne Mocks; AC-4 über Verdrahtungsprüfung analog `elementliste_abgleich_verdrahtung.test.ts`.
