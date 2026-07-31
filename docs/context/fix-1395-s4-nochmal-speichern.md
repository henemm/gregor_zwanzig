# Context: fix-1395-s4-nochmal-speichern

## Request Summary
Issue #1395, Scheibe S4: Wenn ein Speichervorgang mit `412` (ETag-Konflikt,
seit S3 live) abgelehnt wird, soll der Speicher-Anzeiger dem Nutzer eine
Handlung anbieten statt nur "Fehler beim Speichern" zu zeigen — laut S2-
Kommentar konkret "Nochmal speichern" (frisch holen, denselben Vorgang erneut
versuchen), laut S3-Spec-Übergabe offener formuliert ("Reload-und-Retry-
Mechanismus, der den Nutzer entscheiden laesst, ob sein Stand verworfen oder
erneut versucht wird"). Der genaue Zuschnitt (ein Button vs. zwei Optionen)
ist eine offene Entscheidung fuer die Analyse-Phase.

## Related Files

| File | Relevance |
|------|-----------|
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | `SaveStatus`-Klasse. `SaveState = 'idle'\|'dirty'\|'saving'\|'error'` — S3-Spec kündigt an, dass S4 hier einen eigenen Zustand/ein Flag für "Konflikt" braucht. `doSave()` setzt `_pendingFn = null` sofort beim Start — die fehlgeschlagene `saveFn` wird aktuell NIRGENDS für einen Retry aufgehoben. |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | Reine Anzeige-Komponente, rendert `controller.state`/`controller.error`. Fixes Overlay unten rechts. Bekommt vermutlich den neuen Retry-Button. |
| `frontend/src/lib/api.ts` | `send()` ruft bei `res.status === 412` `discardEtag(tripId)` auf — danach läuft der NÄCHSTE Versuch ohne `If-Match` (Server nimmt fehlenden Header an!). Ein simples "saveFn nochmal aufrufen" ohne vorheriges Refresh würde also den soeben erkannten Konflikt **unconditional überschreiben** — genau das Verhalten, das #1395 verhindern soll. |
| `frontend/src/lib/etagRegistry.ts` | Modul-Singleton-Registry (pro Tour, nicht pro Editor-Instanz). `getKnownEtag`/`setKnownEtag`/`discardEtag`/`etagVersion`. Ein GET auf `/api/trips/{id}` würde über `setKnownEtagIfUnchanged` einen frischen Stempel eintragen. |
| `frontend/src/lib/types.ts:347-357` | `ApiError.status?: number` — **extra für S4 angelegt** ("genutzt ab S4"), um `412` von `400`/`500` zu unterscheiden. `extractMessage()` bleibt unverändert (liest `detail`). |
| `frontend/src/routes/trips/[id]/+page.svelte` | EIN `tripSaveCtl = createSaveStatus()` für die ganze Trip-Seite (Header + alle Tabs teilen sich denselben Controller — ein SaveIndicator pro Trip-Editor). `handleTripUpdate(updated) { trip = updated; }` — volles Replace, kein Merge. |
| `frontend/src/lib/components/shared/WeatherMetricsTab.svelte:664-703` | Beispiel für `saveController.schedule(async () => { await api.put(...); ... })` — Closures lesen `$state`-Variablen (`reportConfig`, `smsThresholds`, …) zur AUSFÜHRUNGSZEIT, nicht zum Schedule-Zeitpunkt. Ein Retry über dieselbe Closure sendet automatisch den aktuellen (weiterhin ungespeicherten) lokalen Stand — kein manuelles "Body merken" nötig. |
| `frontend/src/lib/components/edit/EditStagesPanelNew.svelte`, `.../shared/AlarmeTab.svelte`, `.../shared/VersandTab.svelte`, `.../trip-detail/BriefingScheduleTab.svelte`, `.../trip-detail/AlarmeScheduleTab.svelte`, `.../shared/corridor-editor/*` | Weitere Aufrufer von `saveController.schedule(...)` auf demselben geteilten `tripSaveCtl` — ein genereller Retry-Mechanismus in `SaveStatus` deckt sie automatisch mit ab, ohne pro Tab Code anzufassen. |
| `frontend/src/lib/components/compare/*`, `frontend/src/routes/compare/[id]/+page.svelte` | Ortsvergleich hat eigene `createSaveStatus()`-Instanz(en). `PUT /api/briefings/{id}?kind=vergleich` trägt laut S3-Spec noch KEIN ETag/If-Match (das ist S6) — S4 betrifft dort also nur den generischen `SaveStatus`/`SaveIndicator`-Mechanismus, nicht den 412-Sonderfall (der kann dort noch gar nicht auftreten). |
| `frontend/src/lib/stores/__tests__/saveStatus.test.ts` | Bestehende Tests für `SaveStatus` — Fundort für Testmuster (kein bestehender Retry-Test). |
| `frontend/src/lib/__tests__/apiTripEtagConflict.test.ts`, `apiTripEtagHeaders.test.ts`, `apiKeepaliveSkipsIfMatch.test.ts` | Bestehende S3-Tests für `api.ts`/`etagRegistry.ts` — zeigen das Testmuster für ETag-Verhalten (Fetch-Mock, Statuscode-Sequenzen). |

## Existing Patterns
- **Ein Controller pro Editor-Oberfläche, nicht pro Feld/Tab** (`createSaveStatus()`, Issue #758 AC-6 — kein modul-globaler Singleton). Retry-Zustand gehört also in die `SaveStatus`-Instanz, nicht in die Registry.
- **`extractMessage()` liest `detail` bevorzugt** — die deutsche Servermeldung (z. B. "Der Stand wurde zwischenzeitlich an anderer Stelle geaendert...") erscheint bereits heute ohne Frontend-Änderung.
- **Fehlender `If-Match` = Server nimmt an** (S2-Entscheidung, Rollout-Politik). Das ist die Falle für einen naiven Retry: nach `discardEtag()` sendet der nächste Versuch ohne Vorbedingung.
- **`onTripUpdate`/`trip = updated` ist ein volles Replace**, kein Merge — ein GET-Refresh vor dem Retry würde denselben Mechanismus nutzen können wie ein erfolgreicher Save.

## Dependencies
- **Upstream (was S4 nutzt):** S2 (Server: `ETag`/`If-Match`, `412`), S3 (`etagRegistry.ts`, `api.ts`-Warteschlange, `ApiError.status`).
- **Downstream (was S4 beeinflusst):** Alle Aufrufer von `saveController.schedule(...)` über den geteilten `SaveStatus`/`SaveIndicator` — Trip-Editor UND (eingeschränkt) Compare-Editor.

## Existing Specs
- `docs/specs/modules/issue_1395_s2_etag_ifmatch.md` — Server-Vertrag, `412`-Verhalten.
- `docs/specs/modules/issue_1395_s3_etag_registry.md` — Abschnitt "Was S4/S5/S6 erben" (Zeile 474+) benennt die S4-Erwartung explizit; Abschnitt "Known Limitations" (Zeile 456+) hält fest, dass es aktuell KEINEN Konflikt-Zustand gibt.
- `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md` — Grundsatzentscheidung Fingerabdruck statt Versionsfeld.

## Risks & Considerations
- **Kritischer Design-Punkt:** Ein Retry-Button, der einfach nur die alte `saveFn` erneut aufruft, ist bei einem `412` GEFÄHRLICH — ohne vorheriges Refresh des ETags läuft der Request ohne `If-Match` und wird unconditional akzeptiert (silent overwrite). Ein "Nochmal speichern" bei Konflikt MUSS zuerst den Stempel auffrischen (z. B. GET auf `/api/trips/{id}`, das über `setKnownEtagIfUnchanged` die Registry aktualisiert), erst danach den ursprünglichen Speichervorgang wiederholen.
- **Nicht jeder Fehler ist ein Konflikt.** `ApiError.status` unterscheidet `412` von `400`/`500`/Netzwerkfehlern — ob ein generischer Fehler ebenfalls einen Retry-Button bekommt (ohne GET-Refresh, einfach `saveFn` nochmal) oder nur der Konfliktfall, ist zu klären.
- **Zuschnitt "ein Button" vs. "Nutzer entscheidet reload/retry"** — S2-Kommentar und S3-Spec-Übergabe formulieren das leicht unterschiedlich (s. Request Summary). Für die Analyse-Phase klären, ggf. beim PO nachfragen, falls die ACs das nicht eindeutig hergeben.
- **Geteilter Controller (`tripSaveCtl`) über mehrere Tabs:** Ein GET-Refresh vor dem Retry aktualisiert `trip` global (`handleTripUpdate` ersetzt das ganze Objekt) — das kann Formularfelder in ANDEREN, gerade unbeobachteten Tabs beeinflussen, falls die dortigen `$state`-Variablen beim Mount aus `trip` initialisiert werden und sich bei einem Prop-Wechsel nicht automatisch nachziehen. Muss in der Analyse geprüft werden, bevor ein GET-Refresh als generischer Mechanismus in `SaveStatus` landet.
- **Ortsvergleich hat noch kein `412`** (S6 offen) — S4 darf dort keine tote/falsche Konflikt-UI erzeugen, nur den allgemeinen Fehler-Retry (falls dieser Scope ist).
- **Zeilenrahmen:** PO hat für S1–S6 pauschal 600 LoC je Scheibe freigegeben (bei Bedarf anhebbar, wie bei S2/S3 geschehen) — bei Bedarf früh ansprechen, nicht erst am Ende.

## Analysis

### Type
Feature (Erweiterung eines bestehenden, bereits geplanten Mechanismus — keine Fehlermeldung eines Nutzers).

### Offene Fragen — geklärt

**1. Ist ein `trip = updated`-Replace vor dem Retry sicher?** Explore-Recherche über alle Tab-Komponenten (`WeatherMetricsTab`, `AlarmeTab`, `VersandTab`, `BriefingScheduleTab`, `AlarmeScheduleTab`, `EditStagesPanelNew`/`TripTabs`): durchgängig **"Mount-once"-Muster** — lokale `$state`-Variablen werden ausschließlich beim Komponenten-Erstellen (`$state(trip?.xxx)`-Initializer bzw. `onMount`) aus `trip` befüllt, kein einziger `$effect`, der bei `trip`-Wechsel resynchronisiert. Ein `trip = updated`-Replace würde ungespeicherte lokale Edits also NICHT zurücksetzen. **Trotzdem gewählte Lösung (sicherer als nötig):** Der Refresh-Mechanismus fasst `trip` erst gar nicht an (s. Punkt 2) — die Frage ist damit für S4 irrelevant, bleibt aber als Fakt für spätere Scheiben (S5/S6) im Gedächtnis. Einzige Restbeobachtung: `WeatherMetricsTab.buildWeatherPayload()` liest `trip!.display_config` LIVE zur Speicherzeit (Z. 620) — betrifft aber nur, falls `trip` doch ersetzt würde; im gewählten Design nicht der Fall.

**2. GET-Refresh-Mechanismus:** Neue Funktion `refreshTripEtag(tripId)` in `frontend/src/lib/api.ts` — dünner Wrapper um `api.get(\`/api/trips/${tripId}\`)`, der NUR den Seiteneffekt in `etagRegistry.ts` nutzt (jeder erfolgreiche Request mit `tripId` aktualisiert die Registry bereits heute über `send()`, Z. 90–96, inkl. F001-Schutz gegen verspätete Antworten via `setKnownEtagIfUnchanged`). Die Trip-Antwort selbst wird **verworfen**, NICHT an `handleTripUpdate`/`trip = updated` weitergereicht. Damit bleibt der sichtbare `trip`-State im gesamten Retry-Flow unberührt — kein Risiko für andere Tabs, unabhängig von Frage 1.

**3. UI-Zuschnitt:** EIN Button „Nochmal speichern" (automatischer Refresh+Retry), strikt gegated auf `status===412`. Erfüllt sowohl den S2-Kommentar (wörtlich: "frisch holen, denselben Vorgang erneut senden") als auch die S3-Spec-Formulierung ("Nutzer entscheidet, ob verworfen oder erneut versucht") — "Verwerfen" ist ein normaler Browser-Reload (bereits ohne Zusatzcode möglich, im Konflikttext erklärt), "Erneut versuchen" ist der Button. Kein zweiter UI-Zustand nötig.

**4. Generische Fehler (400/500):** Bleiben unverändert `state==='error'`, KEIN Retry-Button — ein automatisches Neusenden würde bei z.B. Validierungsfehlern nichts beheben und den echten Fehler verschleiern. Nur `412` bekommt den neuen `'conflict'`-Zustand.

### Technical Approach
- `SaveState` um `'conflict'` erweitern: `'idle'|'dirty'|'saving'|'error'|'conflict'`.
- `SaveStatus` optional mit `tripId` konstruieren (`createSaveStatus(tripId?: string)`); ohne `tripId` (Compare-Seite vor S6) bleibt Verhalten unverändert — `412` kann dort noch nicht auftreten.
- `doSave()`-Catch-Zweig: bei `(e as ApiError).status === 412 && this._tripId` → `_lastFailed = { fn, init }` merken, Zustand `'conflict'` statt `'error'`.
- Neue Methode `retryConflict()`: no-op außer bei `state==='conflict'`; ruft `refreshTripEtag(tripId)`, DANACH `doSave(_lastFailed.fn, _lastFailed.init)` erneut. Schlägt der Refresh selbst fehl → `'error'`, kein Resend-Versuch. Läuft ein GET verspätet ein oder gibt es einen weiteren fremden Schreibvorgang dazwischen, greift der bestehende F001-Schutz — schlimmstenfalls erneuter `412` → wieder `'conflict'`, nie ein stilles Überschreiben.
- `SaveIndicator.svelte`: neuer `'conflict'`-Branch mit Button, der `controller.retryConflict()` aufruft.
- `etagRegistry.ts` bleibt unangetastet (bestehender Seiteneffekt wird nur wiederverwendet).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `frontend/src/lib/api.ts` | MODIFY | + `refreshTripEtag(tripId)` (~10 LoC) |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` | MODIFY | `'conflict'`-State, `_lastFailed`, `retryConflict()`, `tripId`-Konstruktorparameter (~50 LoC) |
| `frontend/src/lib/components/ui/SaveIndicator.svelte` | MODIFY | `'conflict'`-Branch + Button (~30 LoC) |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | `createSaveStatus(trip.id)` (~2 LoC) |
| Tests (`saveStatus.test.ts`, neue `api`-Tests) | MODIFY/CREATE | Store-Transitions, `refreshTripEtag`, Indicator-Render (~150–250 LoC) |

### Scope Assessment
- Files: 4 Produktivdateien + Tests
- Estimated LoC: ~240–340 (Produktivcode ~90, Rest Tests) — deutlich unter dem PO-Budget von 600 Zeilen/Scheibe
- Risk Level: **LOW** — reine Erweiterung bestehender, gut getesteter Mechanismen (S3-Registry, S3-`ApiError.status`), kein Eingriff in Server/Backend, kein `trip`-Replace, Ortsvergleich unberührt (kein `tripId` → kein `412` möglich)

### Dependencies
- Upstream: S2 (`412`, Server-Vertrag), S3 (`etagRegistry.ts`, `api.ts`-Warteschlange, `ApiError.status`-Feld — beide bereits extra für S4 vorbereitet)
- Reihenfolge: (1) `refreshTripEtag` in `api.ts`, isoliert testbar → (2) `saveStatusStore.svelte.ts`-Erweiterung darauf aufbauend → (3) `+page.svelte` verdrahtet `tripId` → (4) `SaveIndicator.svelte` rendert neuen Zustand
- Downstream: S5 (Rückbau `settle()`/`applyCascade`-Wartblock) bleibt unberührt von S4; S6 (Ortsvergleich) kann denselben `'conflict'`-Zustand/`retryConflict()`-Mechanismus später wiederverwenden, sobald dort `tripId`-Äquivalent + ETag existiert

### Open Questions
- [x] GET-Refresh-Mechanismus sicher gegen andere Tabs? → gelöst durch "Registry-only"-Refresh ohne `trip`-Replace
- [x] Ein Button oder Wahlmöglichkeit? → ein Button, deckt beide Vorgaben ab
- [x] Gilt Retry auch für generische Fehler? → nein, nur `412`

## Next Step
Weiter mit `/30-write-spec`.
