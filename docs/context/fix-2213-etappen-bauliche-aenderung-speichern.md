# Context: fix-2213-etappen-bauliche-aenderung-speichern

## Request Summary
Issue #2213 (aus #1199 B2-03/B2-04/B2-07): Im Etappen-Editor gehen Änderungen verloren, weil sie im
Auto-Save-Modus nicht gespeichert werden. B2-03 (Umsortieren) und B2-04 (Touch-Drag) sind durch #2288
(743c17e5c) erledigt — offen ist B2-07 und, wie die Kontextsuche zeigt, dieselbe Fehlerklasse bei
weiteren Handlern.

## Befund: Handler, die `stages` ändern und NICHT speichern
Datei: `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`

| Handler | Zeile | UI-Auslöser | Speichert? |
|---|---|---|---|
| `handleMobileAddPause` | :86 | Mobil „+ Etappe" → Pausentag (:705) | nein |
| `handlePauseInsert` | :522 | Desktop Strip-Lücke (:756) | nein |
| `confirmRemoveStage` | :530 | Lösch-Dialog (:906) | nur `if (saveController?.hasPending) deferSave()` :557 |
| `handleAddStage` | :560 | Strip „+ Etappe" (:758), Mobil (:704) | nein |
| `handleProfileAdd` | :568 | Klick ins Höhenprofil (:840) | nein |
| `makeRenameHandler` (Wegpunkt) | :609 | WaypointCard (:864) | nein |
| `makeDeleteHandler` (Wegpunkt) | :623 | WaypointCard (:865) | nein |

Speichern tun bereits: `handleDateChange` :266 (scheduleSave / deferSave bei offener Kaskade),
`handleStartTimeChange` :320, `handleStageRename` :602 (scheduleSave), `handleReorderEnd` :496
(#2288: cancel+doSave, deferSave bei offener Kaskade, kein zweiter PUT, wenn settleMootCascade schon schrieb),
`applyCascade` :335, `dismissCascade` :443.

Folge: Im Auto-Save-Modus (Trip-Detail, `saveController` gesetzt) ist der Speichern-Knopf ausgeblendet
(:878-882, `showSave && !saveController`). Die Änderung ist auch nicht vorgemerkt (`hasPending` false),
also flusht weder `beforeNavigate` noch der Tab-Wechsel → stiller Datenverlust beim Verlassen. Gespeichert
wird sie nur zufällig mit, wenn danach eine speichernde Aktion folgt (`buildStagesSave` liest `stages` erst
beim Auslösen, :142-147).

## Related Files
| File | Relevance |
|------|-----------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | Einziger Änderungsort (Handler oben) |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | Controller: `doSave` :222, `hasPending` :372, `schedule` :386 (700 ms), `flush` :399, `defer` :416, `cancel` :452 |
| `frontend/src/routes/trips/[id]/+page.svelte:57` + `stores/ausstehendeSpeicherungSichern.ts:36` | beforeNavigate-Flush (nur bei `hasPending`) |
| `frontend/src/lib/components/trip-detail/TripTabs.svelte:166-171,198` | Tab-Wechsel-Flush; bindet EditStagesSection mit saveController |
| `frontend/src/lib/components/trip-new/TripNewEditor.svelte:854,1153` | Nutzt Panel OHNE tripId/saveController — muss unberührt bleiben |
| `internal/handler/trip.go:299,115-138,473-480` | PUT ersetzt Stages komplett; Validierung nur id/name und Wegpunkt 0/0 → leere Etappe `date:""`, `waypoints:[]` wird angenommen (Beleg `internal/handler/trip_write_test.go:63`) |

## Existing Patterns
- **Diskrete Handlung = sofort schreiben:** `handleReorderEnd` :496-515 — bei offener Kaskade `deferSave()`,
  sonst `saveController.cancel(); void saveController.doSave(buildStagesSave())`. Vorlage für Löschen/Hinzufügen/Pause.
- **Texteingabe = entprellt:** `handleStageRename` → `scheduleSave()`; ohne Controller `void save()`.
- **Kaskaden-Rückfrage** (`cascade && !cascade.done`, :216): ein Save wird zurückgestellt (`defer`), feuert erst mit
  der Antwort oder beim Flush. `cascadeBusy` :219 sperrt bauliche Handler, NICHT aber `handleProfileAdd` und die Wegpunkt-Handler.
- `settleMootCascade` :477 → `dismissCascade` schreibt bereits (cancel+doSave) — kein zweiter PUT im selben Tick (#2288-Lehre).

## Dependencies
- Upstream: `saveController` (SaveStatus), `baueTripSpeicherung`, Go `UpdateTripHandler`.
- Downstream: Trip-Detail Etappen-Tab (Desktop Strip + Mobil StageCardM-Liste); TripNewEditor (ohne Save-Pfad).

## Existing Specs
- `docs/specs/modules/etappen_strip_sortable_list.md:286-289` (#2288) — Speichern beim Ablegen, regelt Hinzufügen/Pause/Löschen nicht
- `docs/specs/modules/trip_stage_date_editing.md` (#1375/#1376) — nur Datum
- `docs/specs/_archive/modules/bug_708_etappe_delete_confirm.md:35f` — „Persistenz beim regulären Speichern" (Knopf-Ära)
- `docs/specs/feature/stage_reorder.md:107` — Knopf-Speichern
- Ergebnis: Speichern baulicher Änderungen im Auto-Save-Modus ist nirgends festgelegt.

## Tests (Vorlagen)
- Kern (node --test): `frontend/src/lib/components/trip-detail/__tests__/trip_etappen_kaskade_412_nochmal_speichern.test.ts`
  mit `tripMehrreiterPruefstand.ts` (wertet echtes Instanz-Skript per AST aus, echter SaveStatus + `fakeTripServer.ts`;
  Handler direkt aufrufbar, z.B. `inst.u.handleAddStage()`). Passt für „Handler schreibt PUT / merkt vor".
- Playwright: `frontend/e2e/mobile-etappen-sortieren-speichert.spec.ts` (#2288, PUT-Zählung) als kompakteste Vorlage;
  `issue-498-stage-date-autosave.spec.ts` (Route-Abfang, Reload/Tab-Wechsel).

## Risks & Considerations
- **Kaskade offen:** Löschen/Hinzufügen bei offener Rückfrage muss `deferSave` nutzen (sonst wird die Rückfrage übergangen).
  Löschen kann die Kaskade gegenstandslos machen → `settleMootCascade` schreibt schon → kein doppelter PUT.
- **Wegpunkt-Handler/Profil-Klick** sind nicht durch `cascadeBusy` gesperrt — Schreiben während `applyCascade` läuft könnte
  gegen den Kaskaden-PUT laufen (412/Stand-Konflikt). Entscheidung in Analyse: sperren oder vormerken.
- **Wegpunkt umbenennen** ist Texteingabe (`prompt`) → einmalige Handlung, sofort schreiben ok.
- **TripNewEditor** ohne tripId/saveController darf nicht plötzlich speichern; Knopf-Modus (`showSave`, kein Controller)
  soll weiter nur per Knopf speichern.
- Scope-Erweiterung gegenüber Issue-Text (Wegpunkt-Handler, Profil-Klick, Pausentag) — gleiche Fehlerklasse, gleiche Datei;
  nach Regel „themenweise abschließen" im selben Ticket.

## Analysis

### Type
Bug (stiller Datenverlust, nutzersichtbar). B2-03/B2-04 durch #2288 erledigt; offen B2-07 + gleiche Fehlerklasse.

### Geprüfte Annahmen (Phase 2, 2026-10-18)
1. **Keine Parallelarbeit:** `git log HEAD..origin/main --grep "#2213"` leer.
2. **Kein Zurückschreiben aus der Server-Antwort:** `TripTabs.svelte:59` setzt `localStages` EINMAL aus `trip.stages`;
   `onTripUpdate` (`routes/trips/[id]/+page.svelte:282`) ersetzt nur `trip` im Elternteil, nicht die gebundene Etappen-Liste.
   Eine Änderung während eines laufenden PUT wird also nicht von dessen (älterer) Antwort überschrieben.
3. **Eigene PUTs kollidieren nicht (kein 412 durch Doppel-Schreiben):** `doSave` selbst serialisiert nicht
   (`saveStatusStore.svelte.ts:222`), ABER Trip-PUTs laufen pro Trip durch `enqueueTripWrite` (`api.ts:248`), und das
   If-Match wird erst innerhalb der Warteschlange gelesen (`api.ts:110-112`, `:205`). Zwei schnell aufeinanderfolgende
   Speichervorgänge laufen nacheinander mit jeweils frischem Stempel.
4. **Nebenbefund (selbe Datei, selbes Thema → im Ticket):** `confirmRemoveStage` :557 `if (saveController?.hasPending) deferSave()`
   wandelt ohne offene Rückfrage einen entprellten Save (z.B. Datum geändert) in einen zurückgestellten ohne Timer um —
   der feuert dann erst beim Verlassen der Seite. Die neue Logik ersetzt diese Zeile.
5. **Sperre:** `cascadeBusy` sperrt Strip (`locked` :754), Löschen-Dialog (:906), Mobil-„+ Etappe" (:697) sichtbar.
   Profil-Klick (`handleProfileAdd`) und Wegpunkt-Karten (Umbenennen/Löschen) haben WEDER Riegel NOCH sichtbare Sperre.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte` | MODIFY | Ein Helfer `speichereBaulicheAenderung(warOffen)` mit den drei Zweigen aus `handleReorderEnd`; Aufruf aus Reorder-Ende, Löschen, Hinzufügen (Strip+Mobil), Pausentag (Strip+Mobil), Profil-Klick, Wegpunkt umbenennen/löschen. `:557` ersetzt. `cascadeBusy`-Riegel + sichtbare Sperre für Profil/Wegpunkt-Karten. |
| `frontend/src/lib/components/trip-detail/__tests__/<verhalten>.test.ts` | CREATE | Kern-Tests über `tripMehrreiterPruefstand.ts` + `fakeTripServer.ts` (PUT-Zählung, Inhalt, Rückfrage-Fälle, Datum→Löschen) |
| `frontend/e2e/etappen-bauliche-aenderung-speichert.spec.ts` | CREATE | Playwright (Vorlage `mobile-etappen-sortieren-speichert.spec.ts`): Hinzufügen/Löschen → Reload → Stand da |
| ggf. WaypointCard / Profil-Komponente | MODIFY | nur falls die Sperre ein `disabled`-Prop braucht |

### Scope Assessment
- Files: 2–4 · Estimated LoC: produktiv ca. +40/-10, Tests ca. +200 (Tests zählen nicht ins LoC-Limit)
- Risk Level: **MEDIUM** — einzige Datei, aber verzahnt mit der Kaskaden-Rückfrage (#1389/#1390/#1393-Historie mit vielen Adversary-Runden)

### Variantenvergleich: sofort vs. entprellt
| Kriterium | A: sofort (`cancel` + `doSave`, wie #2288) | B: entprellt (`schedule`, 700 ms) |
|---|---|---|
| Datenverlust beim Verlassen | keiner | keiner (`hasPending` → Flush bei Navigation/Tab) |
| Konsistenz mit Umsortieren (#2288) | gleich | abweichend (zwei Regeln für „abgeschlossene Handlung") |
| Serie von Profil-Klicks (5 Punkte) | 5 PUTs, seriell, kein 412 (Befund 3) | ~1 PUT |
| Unload-Fenster (Tab schließen < 700 ms) | PUT läuft schon | nur per `flush({keepalive})` gerettet |
| Code-Pfade | ein Pfad | zwei Pfade (Reorder sofort, Rest entprellt) |

### Befunde gegen den Plan
- Mehr PUTs bei Profil-Klick-Serien (Variante A) — unkritisch dank Warteschlange, nur Netzlast.
- Kaskaden-Fallunterscheidung beim Löschen ist fehleranfällig (Auslöser-Etappe gelöscht ⇒ `cascade=null` OHNE Schreiben ⇒ MUSS speichern;
  Folge-Etappe gelöscht ⇒ `settleMootCascade` schreibt evtl. schon ⇒ KEIN zweiter PUT). Muss je Fall getestet werden.

### Technical Approach (Empfehlung)
**Variante A — sofort schreiben, ein gemeinsamer Helfer.**
1. Jeder bauliche Handler liest `warOffen = cascade !== null && !cascade.done` VOR der Änderung, ändert `stages`, ruft dann den Helfer.
2. Helfer (aus `handleReorderEnd` herausgelöst, dieser nutzt ihn ebenfalls):
   - kein `saveController`/`tripId` → nichts (Knopf-Modus und TripNewEditor bleiben unberührt)
   - Rückfrage weiterhin offen → `deferSave()` (aktueller Stand neu vorgemerkt)
   - Rückfrage war offen und wurde durch `settleMootCascade`→`dismissCascade` geschrieben → nichts (kein Doppel-PUT)
   - sonst (inkl. „Auslöser-Etappe gelöscht, Rückfrage verworfen ohne Schreiben") → `cancel()` + `doSave(buildStagesSave())`
   Die Unterscheidung „dismiss hat geschrieben" vs. „cascade=null ohne Schreiben" wird explizit gemacht (Rückgabewert/Flag), nicht aus `warOffen` erraten.
3. `confirmRemoveStage` :557 entfällt zugunsten des Helfers (Nebenbefund 4).
4. **Profil-Klick und Wegpunkt-Handler:** `if (cascadeBusy) return` wie die Strip-Handler, PLUS sichtbare Sperre der Profil-Fläche
   und Wegpunkt-Aktionen während `cascadeBusy` — sonst wäre ein ignorierter Klick derselbe stille Verlust. Begründung gegen „Vormerken nach
   der Kaskade": `applyCascade` schreibt aus einer festgehaltenen Grundlage und ruft im Fehlerfall `cancel()` — ein in dieses Fenster
   gelegter Save würde verworfen bzw. gegen den Kaskaden-Stand laufen; Sperren ist die etablierte Linie (R5-F001) und das Fenster ist kurz (≤ 15 s Deckel).
5. Wegpunkt umbenennen (`prompt`) ist eine abgeschlossene Handlung → sofort, nicht entprellt (Etappe umbenennen bleibt wie es ist).

### Dependencies
`SaveStatus` (unverändert), `baueTripSpeicherung`, `enqueueTripWrite`; Go `UpdateTripHandler` nimmt leere Etappe an (`trip_write_test.go:63`) — keine Backend-Änderung.

### Testplan (für /40)
Kern: je Handler „PUT erfolgt mit neuem Stand, ohne Navigation"; Knopf-Modus/ohne Controller ⇒ kein PUT; Rückfrage offen ⇒ kein PUT, `hasPending`;
Auslöser-Etappe gelöscht ⇒ genau 1 PUT ohne die Etappe; letzte Folge-Etappe gelöscht ⇒ genau 1 PUT; Datum ändern → Etappe löschen ⇒ PUT ohne Navigation;
`cascadeBusy` ⇒ Profil-/Wegpunkt-Handler ändern nichts. Playwright: Hinzufügen und Löschen → Reload → Stand erhalten (Desktop + Mobil).

### Open Questions
- keine für den PO (alle Punkte technisch entschieden, s.o.)
