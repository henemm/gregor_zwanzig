# Context: fix-2359-etag-schluesselraum

## Request Summary
Issue #2359: Trips und Ortsvergleiche teilen Namens- und ETag-Schlüsselraum. Gleiche Kennung ⇒
Frontend-ETag-Registry verwechselt Stempel. Letztes offenes Ticket aus Epic #2507.

## Kernbefund der Kontextphase (gewichtiger als das Ticket)
Es geht nicht nur um den Browser-Stempel: **beide Arten liegen in DERSELBEN Datei**
`data/users/<uid>/briefings/<id>.json` (ADR-0023, ein Modell, ein Ordner, Diskriminator `kind`).

**Datenverlust-Lücke (Code gelesen, nicht ausgeführt):** `POST /api/trips` übernimmt die Kennung aus dem
Request-Rumpf (`internal/handler/trip.go:162-244`, `validateTrip` :115-123 prüft nur Format).
Die Existenzprüfung `s.LoadTrip(trip.ID)` (`trip.go:214`) liefert für eine `kind:"vergleich"`-Datei `nil`
(`internal/store/trip.go:218`) ⇒ gilt als „nicht vorhanden“ ⇒ `SaveTrip` (`trip.go:233`,
store `trip.go:246/295`) **überschreibt den Ortsvergleich still mit einem Trip** (+ verbraucht Trip-Quote).
Kein Test deckt das. Gegenrichtung: Compare-Anlage vergibt immer Server-ID `cp-<16hex>`
(`internal/handler/compare_preset.go:83-89,203`) — kollidiert praktisch nie mit Trip-IDs; PUT/PATCH
behält URL-ID (:320), aber dort läuft der kind-geschützte Load davor.

**ID-Quellen Frontend:** TripNewEditor `crypto.randomUUID().slice(0,8)` (`tripNewLogic.ts:186-202`, Kollision
unwahrscheinlich); GPX-Upload baut einen **Namens-Slug** (`routes/gpx-upload/+page.svelte:77-98`) ⇒ ein
ASCII-Trip-Name gleich einem Alt-Compare-Slug (z. B. „Zillertal“ ⇒ `zillertal`) trifft die Datei des
Ortsvergleichs. Jeder API-Client kann beliebige IDs senden.

## Die zwei Messungen aus dem Ticket
1. **Kollision im Bestand:** `NOT_MEASURABLE` aus dieser Sitzung — `/var/lib/gregor` gehört
   `claude-gregor`, für `hem` kein Lesezugriff (Mandantenschutz, bewusst nicht per sudo umgangen).
   Strukturell gilt aber: auf der Platte kann es pro Kennung nur EINE Datei geben — eine „bestehende
   Kollision“ wäre bereits ein vollzogener Überschreib-Verlust, kein Nebeneinander.
   Die S5-Migration bricht bei ID-Kollision ab (`scripts/migrate_1250_briefings.py:34-40,77-109`),
   zur Laufzeit gibt es danach keinen Schutz.
2. **Fremder Stempel am Server:** sicher. Fingerprint = sha256 der Datei-Bytes
   (`internal/store/briefing_fingerprint.go:27-47`), Vergleich `ifMatchAllows` (`internal/handler/etag.go:52-65`).
   PUT auf die falsche Art liefert 404 **vor** der If-Match-Prüfung (`handler/trip.go:336` vor `:345`).
   ⇒ Der Server-Schutz trägt; das Registry-Problem reduziert sich auf falsche Konflikte im Browser,
   und auch die setzen eine (vorher durch die Lücke oben entstandene) gleiche Kennung voraus.

## Related Files
| File | Relevance |
|------|-----------|
| `internal/handler/trip.go:162-244` | POST /api/trips — Überschreib-Lücke (Existenzprüfung kind-blind) |
| `internal/store/trip.go:195-319` | LoadTrip/SaveTrip/DeleteTrip, kind-Wächter :218 |
| `internal/store/compare_preset.go:176-309` | LoadComparePreset/Save/Delete, kind-Wächter :198 |
| `internal/store/briefing_subscription.go:11-20` | `briefingsDir()`, gemeinsame Ablage |
| `internal/handler/compare_preset.go:83-89,203,320` | Compare-ID-Vergabe `cp-` |
| `internal/handler/etag.go`, `internal/store/briefing_fingerprint.go` | ETag = Datei-Hash |
| `frontend/src/lib/etagRegistry.ts:13-97` | Registry, ein Schlüsselraum, irreführender Restkommentar :67-78 |
| `frontend/src/lib/api.ts:118-337` | Registry-Aufrufer, `refreshResourceEtag(id, kind)` |
| `frontend/src/routes/gpx-upload/+page.svelte:77-98` | Slug-ID aus Trip-Namen |
| `frontend/src/lib/components/trip-new/tripNewLogic.ts:186-202` | Zufalls-ID |

## Existing Patterns
- Arttrennung per `kind`-Feld in jeder Load/Delete-Funktion („fremde Art ⇒ nil, nil“).
- Konflikt-/Fehlerantworten im Handler als JSON mit `error`-Code (z. B. `store_error`, 412 `writePreconditionFailed`).
- Quota-Lock vor Briefing-Lock beim Anlegen (#2482).

## Dependencies
- Upstream: Store-Layer, `ValidEntityID`, Quota (#2482), Briefing-Lock.
- Downstream: Frontend-Anlegewege (TripNewEditor, GPX-Upload, Duplizieren?), Python-Core liest `briefings/`.

## Existing Specs / ADRs
- `docs/adr/0023-briefing-subscription-shared-model.md` — ein Modell, gemeinsamer ID-Raum by design.
- `docs/adr/0036-…` — Fingerprint aus Datei-Bytes.
- `docs/specs/modules/issue_1395_s6_ortsvergleich_etag.md:91,228-234` — falsche Zusicherung „cp- schließt Kollision aus“.
- `docs/specs/modules/rework_2276_s1_netz_und_fundament.md:144-155,515-530` — Befund + Abgrenzung.
- `docs/specs/modules/issue_1395_s2_etag_ifmatch.md:375-390` (F002) — gleiche Fehlerklasse.

## Tests (Bestand)
- Go: `internal/handler/*etag*_test.go`, `internal/store/compare_preset_briefings_test.go:69,178`,
  `internal/store/store_trip_briefings_test.go:169` (nur Load/Delete-Arttrennung, kein Anlege-Fall).
- Frontend (`node --test`): `frontend/src/lib/__tests__/etagRegistryQueue.test.ts`, `apiTripEtag*`,
  `stores/__tests__/saveStatusConflictRetry.test.ts:354-357`.

## Risks & Considerations
- Fix-Richtung offen für /20: (a) POST /api/trips weist fremde Art ab (409) — minimal, schließt den Verlust;
  (b) zusätzlich Registry nach Art schlüsseln — erst nötig, wenn gleiche IDs legal werden; mit (a) nicht mehr.
- Upsert-Semantik von POST (Überschreiben eigener Trip, AC-6 #2482) darf nicht brechen.
- Frontend-Anlegeweg GPX-Upload: Fehlermeldung bei 409 muss nutzerverständlich sein (oder ID-Vergabe ändern).
- Zwei-Nutzer-Test Pflicht (Endpoint nutzerbezogen).

## Analysis

### Type
Bug (Datenverlust-Lücke, Triage b) — der im Ticket beschriebene Stempel-Befund ist nur das Symptom.

### Kernbefund (verifiziert, Code gelesen)
- Einziger Eingang, der eine NEUE ID mit fremder Art treffen kann: `POST /api/trips`
  (`internal/handler/trip.go:214-235`). Alle anderen `SaveTrip`-Aufrufer (`trip.go:483,586,669`,
  `weather_config.go:125`) laden vorher per kind-gefiltertem `LoadTrip` ⇒ nur eigene Art.
- `SaveComparePreset`-Aufrufer (`compare_preset.go:284` Server-ID `cp-`, `:436`, `:558`,
  `briefing_subscription.go:285`) laden vorher bzw. vergeben Server-ID ⇒ praktisch kollisionsfrei.
- Migrationen `migrate_1257.go:44`, `migrate_1258.go:102,143` laden kind-gefiltert ⇒ vom Wächter unberührt.
- `SaveBriefing` (`store/briefing_subscription.go:56`) ohne produktiven Aufrufer (tot, ADR-0023) — nicht anfassen.
- Python `save_trip` (`src/app/loader.py:1962`) ohne produktiven Aufrufer ⇒ kein Wächter nötig.
  Python-Scheduler schreibt nur RMW auf bestehende Dateien / Zustandsdateien außerhalb `briefings/<id>.json`.
- Quote (`handler/quota.go:131`) zählt zum Prüfzeitpunkt per `LoadTrips`, kein Verbrauchszähler.
  Aber: eine Quota-Ablehnung würde den Kollisionsfall maskieren ⇒ Kollisionsprüfung VOR Quota.
- Frontend: Anlegewege `TripNewEditor.svelte:463` (Zufalls-ID) und `routes/gpx-upload/+page.svelte:77-110`
  (Slug aus Name — realistischer Kollisionsweg). GPX-Fehleranzeige zeigt `e.detail ?? e.error` ⇒ deutscher
  `detail`-Text erreicht den Nutzer. `api.ts:197` markiert nur 412 als Konflikt ⇒ 409 löst keinen Konflikt-Banner aus.

### Antworten auf die Ticket-Fragen
1. **Bestandskollision:** `NOT_MEASURABLE` (keine Leserechte auf `/var/lib/gregor`). Strukturell kann es pro
   Kennung nur EINE Datei geben — „Kollision im Bestand" wäre ein bereits vollzogener stiller Verlust.
   Unterscheider (für eine spätere Messung durch berechtigte Instanz): ID aus altem `compare_presets.json`,
   deren `briefings/<id>.json` heute `kind≠vergleich` trägt. Keine Aussage „keine Kollision".
2. **Fremder Stempel am Server:** sicher — PUT auf fremde Art ⇒ 404 vor If-Match (`trip.go:336` vor `:345`).
   Wird per Test bewacht (bisher nur gelesen).
3. **Registry nach Art schlüsseln?** Nein. Die Ablage erzwingt einen gemeinsamen ID-Raum (ADR-0023);
   der Fix macht die Eindeutigkeit über beide Arten zur Server-Invariante ⇒ Registry-Schlüssel reicht.
   Kein neues ADR nötig (Wächter setzt die bestehende Ablage-Entscheidung durch).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/trip.go` | MODIFY | Sentinel `ErrKindConflict`; `SaveTrip` verweigert, wenn Zieldatei `kind=="vergleich"` (kind leer = Trip, fail-open bei fehlender/korrupter Datei wie `DeleteComparePreset`) |
| `internal/store/compare_preset.go` | MODIFY | Symmetrisch: `SaveComparePreset` verweigert, wenn Zieldatei existiert mit `kind!="vergleich"` |
| `internal/store/` (Helfer) | MODIFY | kleiner Helfer „ID belegt durch fremde Art?" für den Vorab-Check |
| `internal/handler/trip.go` | MODIFY | POST: Vorab-Check nach `LoadTrip` (:214), VOR Quota ⇒ 409 `{"error":"id_conflict","detail":"<deutsch>"}`; Sentinel aus `SaveTrip` ebenfalls ⇒ 409 (TOCTOU-Absicherung unter Briefing-Lock) |
| `internal/handler/compare_preset.go` | MODIFY | Sentinel aus `SaveComparePreset` ⇒ 409 statt 500 (Symmetrie) |
| `internal/handler/*_test.go`, `internal/store/*_test.go` | CREATE | Kollisions-, Zwei-Nutzer-, Fremdstempel-, Upsert-Regressionstests |
| `frontend/src/lib/etagRegistry.ts` | MODIFY | Kommentar :67-78: Eindeutigkeit wird serverseitig erzwungen (Verweis Wächter + Test) |
| `docs/specs/modules/issue_1395_s6_ortsvergleich_etag.md` | MODIFY | falsche Zusicherung „`cp-` schließt Kollision aus" (:228-234) korrigieren |

### Scope Assessment
- Files: ~5 Produktivdateien + Tests + 2 Doku-Stellen
- Estimated LoC: ~+60 Code, ~+150 Tests
- Risk Level: LOW–MEDIUM (zentraler Speicherpfad, aber Wächter greift nur bei fremder Art)

### Technical Approach
Doppelter Riegel: (1) Handler-Vorab-Check in POST /api/trips direkt nach `LoadTrip`, vor Quota ⇒ 409 mit
nutzerverständlichem deutschen `detail` (z. B. „Ein Ortsvergleich trägt bereits diese Kennung — bitte
anderen Namen wählen."). (2) Store-Wächter in `SaveTrip`/`SaveComparePreset` als Invariante unter dem
Briefing-Lock (schließt TOCTOU und schützt künftige Aufrufer). Fail-open bei fehlender/leer/korrupter
Zieldatei; `kind==""` zählt als Trip.

### Testplan (Zusicherung dort prüfen, wo sie wirkt)
- Ortsvergleich mit Slug-ID über `SaveComparePreset` anlegen (Produktpfad, kein handgeschriebenes JSON);
  POST Trip gleiche ID ⇒ 409 `id_conflict`; danach `LoadComparePreset` unverändert (Bytes/Fingerprint gleich),
  `LoadTrips` zählt keinen neuen Trip.
- Zwei Nutzer: A hat Ortsvergleich `x`; B POST Trip `x` ⇒ 201; A POST Trip `x` ⇒ 409.
- Upsert eigener Trip (AC-6 #2482) bleibt 201; Alt-Trip-Datei ohne `kind` ⇒ Upsert 201.
- Store direkt: `SaveTrip` auf vergleich-Datei ⇒ `ErrKindConflict`, Datei unverändert; symmetrisch `SaveComparePreset`
  auf route-Datei. Leere/korrupte Zieldatei ⇒ Save erlaubt.
- Kollision vor Quota: Nutzer am Trip-Limit + Kollision ⇒ 409, nicht Quota-Fehler.
- Fremdstempel: `PUT /api/trips/<compareId>` mit ETag des Ortsvergleichs ⇒ 404, Bytes unverändert; Gegenrichtung
  `PUT /api/compare/presets/<tripId>` ⇒ 404.

### Dependencies
Store-Layer (`ValidEntityID`, Briefing-Lock, `LockQuota` #2482), Frontend nur Doku-Kommentar.

### Nebenbefund (eigenes Issue, Triage b)
GPX-Upload (`routes/gpx-upload/+page.svelte:77-110`) erzeugt die ID als Slug des Namens und POSTet ohne
Existenzprüfung ⇒ ein gleichnamiger **eigener** Trip wird still überschrieben (Upsert-Semantik AC-6).
Nicht Scope von #2359 — gebucht als #2612.

### Open Questions
- keine fachlichen; Wortlaut der 409-Meldung legt die Spec fest.
