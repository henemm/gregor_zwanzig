# Context: #1395 S5 — Rückbau settle()/applyCascade-Wartblock

## Request Summary
S1–S4 aus #1395 sind live: `api.ts` serialisiert jeden `PUT /api/trips/{id}` über eine
Schreib-Warteschlange je Tour (`enqueueTripWrite`) und hängt den aktuellen ETag als
`If-Match` an — ein veralteter Schreibvorgang wird vom Server abgelehnt (412) statt
still übernommen. Der clientseitige Wartemechanismus `settle()`/`SETTLE_TIMEOUT_MS` in
`EditStagesPanelNew.svelte`s `applyCascade()` diente demselben Zweck (verhindern, dass
ein Kaskaden-Schreibvorgang einen noch laufenden Auto-Save überholt) und ist jetzt
redundant. Er soll zurückgebaut werden.

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | Definiert `SETTLE_TIMEOUT_MS` (Z. 19-28) und `settle()` (Z. 143-166) — beide entfallen |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Einziger Aufrufer: `await saveController.settle()` in `applyCascade()` (Z. 423), gerahmt von Begründungskommentaren (Z. 377-381, 405-422); Kommentar Z. 269 referenziert `SETTLE_TIMEOUT_MS` beiläufig |
| `frontend/src/lib/stores/__tests__/saveStatus.test.ts` | Importiert `SETTLE_TIMEOUT_MS`/`settle()` (Z. 53); drei dedizierte Tests: „wartet auf laufenden Speichervorgang" (Z. 272), „No-Op ohne Inflight" (Z. 306), „F002: wartet nicht ewig" (Z. 315-331) |
| `frontend/src/lib/api.ts` | Zeigt, WARUM `settle()` jetzt redundant ist: `request()` (Z. 101-112) serialisiert jeden `PUT` auf `/api/trips/{id}` via `enqueueTripWrite(tripId, run)` — unabhängig vom Aufrufer |
| `frontend/src/lib/etagRegistry.ts` | Trägt die Warteschlange (`enqueueTripWrite`) und ETag-Registry, auf die `api.ts` zugreift |

## Existing Patterns
- **Serialisierung ist bereits zentral, nicht lokal:** `buildStagesSave()` (Auto-Save,
  Z. 184-189) und `applyCascade()`s direkter `api.put`-Aufruf (Z. 429-433) laufen
  BEIDE über `api.put('/api/trips/${tripId}', ...)` → beide durchlaufen dieselbe
  `enqueueTripWrite`-Warteschlange derselben Tour. Ein späterer Aufruf wartet dort
  automatisch auf einen früheren, unabhängig davon, ob der Aufrufer selbst wartet.
- Das Muster deckt sich mit der PO-Entscheidung im Issue-Kommentar (2026-07-27, S3):
  „Kann weg, aber erst mit der Warteschlange: settle(), SETTLE_TIMEOUT_MS, der
  Wartblock in applyCascade — zusammen 40–60 Zeilen. Die Ordnungslogik wandert aus
  einem Panel an die eine Stelle, durch die alle Aufrufe laufen." Genau dieser
  Zustand ist jetzt erreicht (S3 ist live, Commit `1df5675d`).

## Dependencies
- Upstream: `settle()` liest `SaveStatus._inflight`, das von `doSave()` gesetzt wird —
  bleibt unverändert bestehen (wird für andere Zwecke weiter gebraucht, s.u.).
- Downstream: Kein anderer Aufrufer von `settle()`/`SETTLE_TIMEOUT_MS` im Repo
  (grep bestätigt: nur `saveStatusStore.svelte.ts` selbst + der eine Aufruf in
  `EditStagesPanelNew.svelte` + der Test). `saveStatusStore.svelte.ts` wird von
  Trip- UND Compare-Editor geteilt (`createSaveStatus()`) — der Compare-Editor ruft
  `settle()` aber nirgends auf (grep-bestätigt), ist also nicht betroffen.

## Existing Specs
- `docs/specs/modules/issue_1395_s3_etag_registry.md` — beschreibt die Warteschlange,
  die S5 als Ersatz für `settle()` referenziert
- `docs/specs/modules/issue_1395_s4_conflict_retry.md` — angrenzende Scheibe, S4 live
- ADR: `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md`

## Was IM Panel bestehen bleibt (laut Issue-Kommentar, explizit NICHT Teil von S5)
- `defer()` — stellt einen Save zurück, wenn eine Rückfrage offen ist (Absicht, kein Wettlauf-Schutz)
- Doppeltipp-Riegel `cascadeBusy` (Z. 259-261, 382) — lokale Idempotenz, unabhängig vom Netz
- `saveController.setSaving()`/Sperre während des Schreibens — reine UI-Rückmeldung
- `beforeNavigate`-Flush (#1376)
- `saveController.cancel()` (Z. 417) — verwirft einen noch NICHT abgeschickten Debounce, anderer Zweck als `settle()` (das auf einen BEREITS laufenden Request wartete)

## Risks & Considerations
- **Timeout-Semantik geht verloren, ist aber jetzt unnötig:** `settle()` deckelte die
  Wartezeit auf 8s und schrieb danach BEWUSST TROTZDEM (Kommentar Z. 20-27, Bug #1389
  F002: unbegrenztes Warten legte die Kaskade im Funkloch für immer still). Die
  Warteschlange in `api.ts` hat KEINEN Timeout — sie wartet, bis der vorherige Request
  antwortet (oder scheitert). Das ist kein Rückschritt: `CASCADE_WRITE_TIMEOUT_MS`
  (15s, Z. 270) deckelt bereits den GESAMTEN Kaskaden-Schreibvorgang inkl. Warten in
  der Queue (AbortController, Z. 426-427) — die alte 8s-Grenze war ohnehin nur ein
  Teil-Deckel innerhalb dieses 15s-Fensters. Zu prüfen: liegt der `AbortController`
  auch über der Wartezeit IN der Queue, nicht nur über dem eigentlichen `fetch`? Ja —
  `ctrl.signal` wird erst beim `api.put`-Aufruf übergeben, der VOR dem Queue-Eintritt
  gebaut wird; `fetch` selbst läuft aber erst nach dem Dequeuing. Muss in der Analyse
  geklärt werden, ob `AbortController.abort()` einen noch in der Queue wartenden
  Request überhaupt erreichen kann, oder ob nur der aktive `fetch` abgebrochen wird.
- Kommentar Z. 269 („15s liegt weit über … SETTLE_TIMEOUT_MS (8s)") muss mit-entfernt
  bzw. umformuliert werden — sonst zeigt der verbleibende Kommentar auf eine
  gelöschte Konstante.
- Drei Tests in `saveStatus.test.ts` (Z. 272, 306, 315-331) testen `settle()` direkt
  und müssen gelöscht werden — kein Ersatztest nötig, da die Warteschleife in
  `etagRegistry.ts`/`api.ts` bereits eigene Tests hat (S3).
- LoC-Rahmen (600/Scheibe, PO-Entscheidung 2026-07-26) — Rückbau ist reine Löschung,
  sollte klar darunter bleiben.

## Analyse-Ergebnis (Standard-Track: Kontext + Analyse kombiniert)

**Empfohlener Ansatz:** Entfernen von `SETTLE_TIMEOUT_MS`, `settle()` (samt Kommentaren)
aus `saveStatusStore.svelte.ts`; Entfernen von `await saveController.settle();` (Z. 423)
und der zugehörigen Begründungskommentare aus `applyCascade()`; Anpassung des
Kommentars Z. 269 (Referenz auf `SETTLE_TIMEOUT_MS` entfernen); Löschen der drei
`settle()`-Tests in `saveStatus.test.ts`. Kein Ersatzmechanismus nötig — die
Serialisierung läuft bereits vollständig über `api.ts`s `enqueueTripWrite`.

**Kein Alternativweg geprüft nötig:** Es gibt keine zweite plausible Umsetzung — die
Frage ist nicht "wie", sondern "was genau darf weg, ohne ein Verhalten zu verlieren,
das nicht schon anderswo abgedeckt ist". Das ist oben beantwortet.

**Klärung (am Code verifiziert, kein offener Punkt mehr):** `CASCADE_WRITE_TIMEOUT_MS`
deckelt bereits die GESAMTE Wartezeit inkl. Queue, nicht nur den `fetch`. Der
`AbortController` (Z. 426-427) wird VOR dem `api.put`-Aufruf gestartet, sein `signal`
läuft ungeachtet dessen weiter, ob der Request gerade in `enqueueTripWrite` wartet
oder schon fetcht. `enqueueTripWrite` (`etagRegistry.ts:131-148`) ruft `fn` erst nach
Auflösung von `previous` auf; ist `ctrl.signal` bis dahin bereits `aborted`, lehnt
`fetch()` sofort mit `AbortError` ab, statt erst zu starten. Ein hängender Vorgänger
in der Queue kann den Kaskaden-Schreibvorgang also NICHT unbegrenzt blockieren — nach
15s bricht er so oder so ab, mit oder ohne `settle()`. Kein zusätzliches AC nötig,
aber gehört als Begründung in die Spec, damit der Rückbau nicht als Regression
missverstanden wird.
