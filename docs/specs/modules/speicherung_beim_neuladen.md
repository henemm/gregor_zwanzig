---
entity_id: speicherung_beim_neuladen
type: module
created: 2026-09-14
updated: 2026-09-14
status: implemented
version: "1.0"
tags: [pwa, autosave, frontend, issue-2317, epic-2127]
---

# Speicherung und Anzeige beim Neuladen

Issue #2317 · Epic #2127 · Nachfolger von #1376 (`trip_stage_date_editing.md`) und #2316
(`pwa_update_erkennung.md`)

## Approval

- [ ] Approved

## Purpose

Ändert der Nutzer auf der Trip-Detailseite (`/trips/[id]`) oder der Ortsvergleich-Detailseite
(`/compare/[id]`) einen Wert und lädt die Seite neu, bevor der Speicher-Takt (700 ms) abgelaufen
ist, muss der Wert zuverlässig auf dem Server ankommen UND nach dem Neuladen sofort angezeigt
werden. Heute geht bei Wertebereichen, Alarmen und Wetter-Metriken die Speicherung beim Entladen
nicht als `keepalive`-Anfrage raus, sondern als normale Anfrage, die der Browser beim Entladen
abbrechen darf — der Nutzer hält seine Eingabe für verloren. Selbst mit korrektem `keepalive`
bleibt ein Zeitfenster, in dem die neu geladene Seite noch den alten Stand zeigt, weil Go GET und
PUT je Trip serialisiert und die Reihenfolge zwischen SSR-GET und Speicher-PUT nicht garantiert
ist. Diese Spec behebt beides: zuverlässiges Speichern beim Entladen und eine Anzeige-Korrektur
nach dem Neuladen.

## Source

- **File:** `frontend/src/lib/stores/ausstehendeSpeicherungSichern.ts` (gemeinsamer Wächter)
- **Weitere Dateien:** `frontend/src/lib/stores/nachEntladenNachladen.ts` [CREATE],
  `frontend/src/lib/stores/aktiveSpeicherung.ts` [CREATE],
  `frontend/src/lib/components/shared/tripSpeicherung.ts` [CREATE],
  `frontend/src/lib/components/compare/korridorCommit.ts` [CREATE],
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditor.svelte`,
  `frontend/src/lib/components/shared/corridor-editor/CorridorEditorMobile.svelte`,
  `frontend/src/lib/components/shared/AlarmeTab.svelte`,
  `frontend/src/lib/components/shared/WeatherMetricsTab.svelte`,
  `frontend/src/lib/components/compare/CompareTabs.svelte`,
  `frontend/src/lib/api.ts` (`getMitFassung`),
  `frontend/src/lib/stores/saveStatusStore.svelte.ts` (Getter `laufendeSpeicherung`),
  `frontend/src/routes/trips/[id]/+page.svelte`, `frontend/src/routes/compare/[id]/+page.svelte`,
  `frontend/src/routes/+layout.svelte`, `frontend/src/lib/pwa/serviceWorkerUpdate.ts`,
  `frontend/src/lib/pwa/geraetespeicher.ts`
- **Schicht:** Frontend (SvelteKit). Kein Go-Anteil, kein Python-Anwendungscode. Go liefert nur
  ETag und If-Match wie bisher (`internal/handler/trip.go`, `internal/handler/etag.go`).

## Estimated Scope

- **LoC:** Produktiv ~+150–200, Tests ~+120–150 (Summe innerhalb `loc_limit_override 500`)
- **Files:** ~16 (12 Produktiv-/Verdrahtungsdateien, 3 Testdateien, 1 CI-Ratsche +
  `docs/specs/modules/pwa_update_erkennung.md`)
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `saveStatusStore.svelte.ts` (`schedule`, `defer`, `hasPending`, `flush(init)`) | Upstream | Speicher-Takt, den alle Reiter melden |
| `ausstehendeSpeicherungSichern.ts` (`willUnload` → `flush({keepalive:true})`) | Upstream | Gemeinsamer Wächter, wird um den Merker erweitert |
| `frontend/src/lib/etagRegistry.ts` (`enqueueTripWrite`, `adoptEtagFromPageLoad`) | Upstream | If-Match-Schutz; Nachladen braucht einen Übernahmeweg für „neuere Fassung vom Server" |
| `frontend/src/lib/pwa/geraetespeicher.ts` | Upstream | Mandantengetrennter Gerätespeicher, räumt beim Abmelden |
| `docs/specs/modules/pwa_update_erkennung.md` (#2316) | Upstream | „Aktualisieren"-Ablauf, den Baustein 2 um ein Warten ergänzt |
| `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts` | Downstream | Bestehender E2E-Fall bekommt Anzeige-Assert statt Kommentar |
| `.github/ci_e2e_specs.txt`, `.github/workflows/ci.yml` (`E2E_MIN_EXECUTED_HAUPT`/`_PWA`) | Downstream | Ratsche muss mit dem erweiterten Testkörper mitwachsen |

## Implementation Details

**Baustein 1 — Speichern verlässlich:**
```
CorridorEditor.svelte / CorridorEditorMobile.svelte / AlarmeTab.svelte / WeatherMetricsTab.svelte:
saveFn erhält den init-Parameter und reicht ihn an api.put(url, body, init) weiter, statt ihn zu
verschlucken. WeatherMetricsTab: bei init?.keepalive beide PUTs (/weather-config, /api/trips/{id})
sofort und unabhängig voneinander absetzen; ohne keepalive bleibt die heutige Reihenfolge
(erst /weather-config, dann /api/trips/{id}) unverändert, weil die lokale Übernahme von
alert_rules darauf angewiesen ist (#850).
```

**Baustein 2 — „Aktualisieren" wartet:**
```
+layout.svelte stellt per Svelte-Context eine Anmeldestelle bereit (z.B. setContext
'aktive-speicherung'), an der trips/[id]/+page.svelte und compare/[id]/+page.svelte ihren
SaveStatus beim Mount an- und beim Unmount abmelden (Kontext fließt nur Eltern→Kind, deshalb
Anmeldestelle statt direktem Zugriff). serviceWorkerUpdate.ts ruft vor SKIP_WAITING eine
awaitPendingSave()-Funktion auf, die — falls ein SaveStatus angemeldet ist und hasPending true
ist — flush() OHNE keepalive und MIT If-Match ausführt und auf das Ergebnis wartet. Schlägt der
flush fehl (412, Netzwerkfehler), bricht awaitPendingSave ab, kein SKIP_WAITING, die bestehende
Fehler-/Konfliktanzeige des Reiters bleibt sichtbar.
```

**Baustein 3 — Anzeige nach Browser-Neuladen:**
```
ausstehendeSpeicherungSichern.ts setzt im willUnload-Flush zusätzlich einen Merker über
geraetespeicher.ts: { typ: 'trip'|'vergleich', id } — keine Werte, nur die Kennung.
nachEntladenNachladen.ts liest beim Mount der jeweiligen Detailseite den Merker für die eigene
Kennung, löscht ihn sofort, und startet bei Treffer bis zu 6 Versuche im Abstand von 500 ms
(≈3 Sekunden), den aktuellen Server-Stand zu holen. Er übernimmt eine Antwort nur, wenn (a) sie
sich vom ausgelieferten Stand unterscheidet (Trip: ETag-Vergleich; Ortsvergleich: Inhaltsvergleich,
da kein ETag existiert), UND (b) saveStatus.hasPending === false (keine neu geplante, noch nicht
abgesetzte Speicherung), UND (c) der Nutzer seit dem Laden der Seite nichts geändert hat (eigener
"seit Laden verändert"-Merker, unabhängig von hasPending). Bei Übernahme auf dem Trip wird
zusätzlich adoptEtagFromPageLoad-artig die Registry auf den übernommenen ETag gesetzt, damit die
nächste Speicherung nicht fälschlich mit 412 kollidiert.
```

### Verworfene Alternativen

- **Nur die Anzeige korrigieren, ohne Baustein 1:** würde einen tatsächlich verlorenen Wert als
  „korrekt angezeigt" ausgeben, weil er nie beim Server ankam — verdeckt den Datenverlust statt
  ihn zu beheben.
- **Inhalt statt Kennung in `sessionStorage` spiegeln:** könnte nach einem gescheiterten Speichern
  einen ungespeicherten Wert als gespeichert zeigen; widerspricht dem Leitsatz mandantengetrennter
  Gerätespeicher ohne fachliche Notwendigkeit.
- **Rückfrage vor dem Verlassen der Seite:** vom PO am 2026-07-25 ausdrücklich abgelehnt (#1376),
  gilt unverändert.
- **Aufteilung in Scheiben:** das Ticket ist erst mit allen drei Bausteinen behoben — Baustein 3
  würde ohne Baustein 1 einen nie gespeicherten Wert nachladen.

## Expected Behavior

- **Input:** Eingabe in Wertebereiche/Alarme/Wetter-Metriken/Ortsvergleich-Idealwerte, Entladen
  der Seite (Browser-Neuladen, Navigation weg, „Aktualisieren"-Tippen aus #2316), Abmelden.
- **Output:** Beim Entladen geht jede ausstehende Speicherung als `keepalive`-Anfrage raus (Browser-
  Neuladen) bzw. wird vorher regulär abgeschlossen („Aktualisieren"). Nach dem Neuladen zeigt die
  Detailseite spätestens nach 3 Sekunden den tatsächlichen Server-Stand, ohne einen neueren lokalen
  Tippvorgang zu überschreiben.
- **Side effects:** Zusätzliche GET-Anfragen nur, wenn ein Merker vorliegt (höchstens 6, im Abstand
  von 500 ms); `sessionStorage`-Merker mit reiner Kennung, mandantengetrennt geräumt beim Abmelden;
  ETag-Registry-Stand kann durch das Nachladen aktualisiert werden.

## Acceptance Criteria

- **AC-1:** Given der Nutzer ändert auf der Trip-Detailseite (`/trips/[id]`) im Reiter
  Wertebereiche am Desktop eine Ober- oder Untergrenze / When er die Eingabe stehen lässt (unter
  700 ms) und die Seite per Browser neu lädt / Then ist der neue Wert beim Server gespeichert und
  wird nach dem Neuladen binnen 3 Sekunden angezeigt.
  - Nachweis: E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`

- **AC-2:** Given der Nutzer ändert am Handy (Mobil-Ansicht, `CorridorEditorMobile.svelte`) im
  Reiter Wertebereiche eine Ober- oder Untergrenze / When er die Seite innerhalb von 700 ms neu
  lädt / Then ist der neue Wert gespeichert und wird nach dem Neuladen binnen 3 Sekunden angezeigt.
  - Nachweis: E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`, Mobil-Viewport

- **AC-3:** Given der Nutzer ändert im Reiter Alarme eine Schwelle / When er innerhalb von 700 ms
  die Seite neu lädt / Then ist die Schwelle gespeichert und wird nach dem Neuladen binnen
  3 Sekunden angezeigt.
  - Nachweis: E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`

- **AC-4:** Given der Nutzer ändert im Reiter Wetter-Metriken eine Metrikauswahl oder eine
  Report-Einstellung / When er innerhalb von 700 ms die Seite neu lädt / Then sind beide
  zugehörigen Server-Stände (Wetter-Metriken und Report-Einstellungen) gespeichert und werden nach
  dem Neuladen binnen 3 Sekunden angezeigt.
  - Nachweis: E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`

- **AC-5:** Given der Nutzer trägt auf der Ortsvergleich-Detailseite (`/compare/[id]`) im Reiter
  Idealwerte eine Zahl ein, ohne das Feld zu verlassen / When er die Seite neu lädt / Then ist der
  Wert gespeichert und wird nach dem Neuladen binnen 3 Sekunden angezeigt.
  - Nachweis: E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`

- **AC-6:** Given der Update-Hinweis aus #2316 wird angezeigt und es liegt eine noch nicht
  übertragene Eingabe vor / When der Nutzer auf „Aktualisieren" tippt / Then wird die ausstehende
  Speicherung zuerst regulär (mit If-Match, ohne keepalive) abgeschlossen, erst danach übernimmt
  die App die neue Fassung, und der eingegebene Wert bleibt sichtbar.
  - Nachweis: E2E `frontend/e2e/pwa-update-erkennung.spec.ts`

- **AC-7:** Given der Update-Hinweis wird angezeigt, das Gerät ist offline oder die ausstehende
  Speicherung scheitert mit einem Konflikt / When der Nutzer auf „Aktualisieren" tippt / Then lädt
  die Seite NICHT neu, die bestehende Fehler- bzw. Konfliktanzeige bleibt sichtbar, und die Eingabe
  geht nicht verloren.
  - Nachweis: Unit `node --test` (`frontend/src/lib/pwa/serviceWorkerUpdate.test.ts`, erweitert)

- **AC-8:** Given nach dem Neuladen läuft gerade das begrenzte Nachladen / When der Nutzer in
  dieser Zeit selbst einen neuen Wert einträgt / Then überschreibt das Nachladen diese neue
  Eingabe nicht.
  - Nachweis: Unit `node --test` (`frontend/src/lib/stores/__tests__/nachEntladenNachladen.test.ts`, neu)

- **AC-9:** Given die Seite wird normal geladen, ohne dass zuvor eine Speicherung beim Entladen
  gemeldet wurde (kein Merker vorhanden) / When die Trip- oder Ortsvergleich-Detailseite öffnet /
  Then löst der Nachlade-Baustein keine einzige zusätzliche Anfrage aus.
  - Nachweis: Unit `node --test` (`frontend/src/lib/stores/__tests__/nachEntladenNachladen.test.ts`, neu)

- **AC-10:** Given ein Merker liegt vor, der Server liefert aber dauerhaft denselben Stand wie die
  ausgelieferte Seite / When die Detailseite lädt / Then unternimmt der Nachlade-Baustein höchstens
  6 Versuche im Abstand von 500 ms (rund 3 Sekunden) und hört danach still auf, ohne die Anzeige zu
  verändern.
  - Nachweis: Unit `node --test` (`frontend/src/lib/stores/__tests__/nachEntladenNachladen.test.ts`, neu)

- **AC-11:** Given eine neuere Server-Fassung wurde durch das Nachladen auf dem Trip übernommen /
  When der Nutzer direkt danach etwas ändert und speichert / Then wird diese Speicherung nicht
  durch einen fälschlichen Konflikt-Hinweis (412) blockiert.
  - Nachweis: E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`

- **AC-12:** Given ein anderes Gerät hat denselben Trip nach dem Nachladen erneut geändert / When
  der Nutzer auf diesem Gerät jetzt speichert / Then erkennt die App den echten Konflikt weiterhin
  zuverlässig (If-Match-Schutz bleibt wirksam).
  - Nachweis: Unit `node --test` (`frontend/src/lib/__tests__/apiKeepaliveSkipsIfMatch.test.ts` erweitert)

- **AC-13:** Given eine Speicherung ging beim Entladen als Merker in den Gerätespeicher / When der
  Merker gelesen wird / Then enthält er ausschließlich die Kennung (Trip- bzw. Vergleichs-ID und
  Art), keinerlei eingegebene Werte.
  - Nachweis: Unit `node --test` (`frontend/src/lib/stores/__tests__/ausstehendeSpeicherungSichern.test.ts`)

- **AC-14:** Given ein Merker liegt im Gerätespeicher / When sich der Nutzer abmeldet / Then ist
  der Merker gelöscht.
  - Nachweis: Unit `node --test` (`frontend/src/lib/pwa/geraetespeicher.test.ts`, neu)

- **AC-15:** Given Nutzer A hinterlässt einen Merker und meldet sich ab, Nutzer B meldet sich auf
  demselben Gerät an / When Nutzer B eine Detailseite mit derselben Trip- oder Vergleichs-Kennung
  öffnet / Then löst das kein Nachladen fremder Daten aus, weil der Merker beim Abmelden geräumt
  wurde.
  - Nachweis: Unit `node --test` (`frontend/src/lib/pwa/geraetespeicher.test.ts`, neu)

- **AC-16:** Given eine Speicherung ist beim Verlassen oder Entladen der Seite noch ausstehend /
  When der Nutzer die Seite verlässt oder neu lädt / Then erscheint keine Rückfrage, unverändert
  seit #1376/#2316.
  - Nachweis: E2E `frontend/e2e/speicherung-ueberlebt-neuladen.spec.ts`

- **AC-17:** Given der Nutzer speichert im Reiter Wetter-Metriken regulär (Feld verlassen, kein
  Neuladen) / When die Speicherung ausgelöst wird / Then gehen die beiden PUTs
  (Wetter-Metriken, dann Trip) weiterhin nacheinander raus, nicht gleichzeitig.
  - Nachweis: Unit `node --test` (`frontend/src/lib/components/shared/__tests__/wetter_metriken_speichern_beim_entladen.test.ts`, neu)

## Known Limitations

- Speichern beim Browser-Entladen bleibt Best-Effort (`keepalive`) — der Browser kann auch diese
  Anfrage in seltenen Fällen (z.B. Prozess-Kill) nicht mehr absetzen. Für den regulären
  „Aktualisieren"-Weg (Baustein 2) besteht dieses Risiko nicht, dort wird vor dem Fassungswechsel
  gewartet.
  Bei Wetter-Metriken mit vollem `display_config` ist die browserseitige 64-KB-Grenze für
  `keepalive`-Anfragen zu beachten; bei Annäherung ist ein eigenes Issue nötig.
- Der Ortsvergleich hat keinen ETag — das Nachladen erkennt eine neuere Fassung dort über
  Inhaltsvergleich, nicht über einen Fassungsstempel wie beim Trip.
- Im Ortsvergleich speichern Name, Region und Profil weiterhin direkt per `api.put`, ohne über
  `schedule()` zu laufen — sie sind vom Wächter und vom Nachlade-Baustein NICHT erfasst. Das ist
  vor #2317 schon der Fall und bleibt außerhalb dieses Tickets (kein gemeldeter Datenverlust dort).
- Nach den bis zu 6 Nachlade-Versuchen wird still aufgehört; bleibt der Server-Stand danach älter
  als erwartet, zeigt die Seite weiterhin den zuletzt ausgelieferten Stand — kein Fehlerhinweis.
- „Aktualisieren" bleibt gesperrt, solange auf der Detailseite ein ungelöster Speicherfehler oder
  Konflikt steht — auch wenn gerade nichts aussteht. Ein ungelöster Fehler heißt: eine Eingabe ist
  nicht beim Server angekommen, der Fassungswechsel würde sie verwerfen (AC-7). Die Sperre löst sich
  mit dem nächsten erfolgreichen Speichern bzw. „Wiederholen"; beim nächsten Kaltstart übernimmt die
  App die neue Fassung ohnehin (Adversary-Befund F005, bewusst beibehalten).
- Kein neuer Hinweistext in der Oberfläche für den Nachlade-Vorgang (bewusst schlank gehalten).
  Bis zum Nachladen, also höchstens rund 3 Sekunden, ist nach dem Neuladen noch der alte Wert zu sehen.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue; Fortschreibung von ADR-0003, ADR-0036 und ADR-0061 §3
- **Rationale:** ADR-0003 (mandantengetrennter Gerätespeicher) bleibt unverändert gültig — der
  Merker trägt nur die Kennung und wird beim Abmelden geräumt, keine neue Ausnahme nötig. ADR-0036
  (Nebenläufigkeitsschutz per Inhalts-Fingerabdruck/If-Match) bleibt unangetastet: das Nachladen
  setzt die ETag-Registry nur auf die tatsächlich übernommene Server-Fassung, schwächt den Schutz
  gegen fremde Änderungen nicht. ADR-0061 §3 (Update-Ablauf aus #2316) wird um das Warten auf eine
  ausstehende Speicherung vor SKIP_WAITING ergänzt, ohne die dortige Bauform zu ändern.

## Changelog

- 2026-09-14: Initial spec created (Issue #2317)
- 2026-09-14: Known Limitation zur Aktualisieren-Sperre bei ungelöstem Speicherfehler ergänzt (Adversary F005)
- 2026-09-14: Umsetzung abgeschlossen (Status `implemented`); Source-Liste um tatsächlich neue
  Dateien ergänzt (`tripSpeicherung.ts`, `aktiveSpeicherung.ts`, `korridorCommit.ts`,
  `CompareTabs.svelte`, `api.ts::getMitFassung`, `saveStatusStore.svelte.ts::laufendeSpeicherung`)
