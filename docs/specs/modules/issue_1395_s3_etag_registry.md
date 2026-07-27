---
entity_id: issue_1395_s3_etag_registry
type: module
created: 2026-07-27
updated: 2026-07-27
status: draft
version: "1.0"
tags: [frontend, svelte, trip, weather-config, concurrency, etag, if-match]
---

<!-- Issue #1395 Scheibe S3 — Frontend fuehrt den Stempel: ETag-Registry + Schreib-Warteschlange im Trichter -->

# Issue #1395 Scheibe S3 — Frontend fuehrt den Stempel (ETag-Registry + Schreib-Warteschlange)

## Approval

- [ ] Approved

## Purpose

S2 hat `ETag`/`If-Match` am Server verdrahtet, aber KEIN Client sendet
`If-Match` — der Schutz ist scharf gestellt, aber unbenutzt. Diese Scheibe ist
der Umschaltpunkt: Der zentrale Anfrage-Trichter des Frontends
(`frontend/src/lib/api.ts`) merkt sich je Tour den zuletzt vom Server
erhaltenen `ETag`, schickt ihn automatisch als `If-Match` bei jedem folgenden
`PUT` auf dieselbe Tour mit und uebernimmt bei Erfolg sofort den neuen
`ETag` aus der Antwort. Ab hier wird ein veralteter Schreibvorgang real mit
`412` abgelehnt statt kommentarlos zu gewinnen — die in ADR-0036 beschriebene
Fehlerklasse (#1389/#1390/#1393) bekommt erstmals einen echten, serverseitig
durchgesetzten Schutz, nicht mehr nur clientseitige Eigenkonstruktionen.

## Source

- **File:** `frontend/src/lib/etagRegistry.ts` (NEU) — Registry (Stand je
  Tour-ID) und Schreib-Warteschlange (je Tour-ID)
- **File:** `frontend/src/lib/api.ts` — `request()` faengt `ETag` aus
  GET/PUT-Antworten auf Trip-Pfade ab, haengt `If-Match` an PUT-Anfragen auf
  Trip-Pfade an, fuehrt Trip-PUTs durch die Warteschlange, reichert den
  geworfenen Fehler um den Statuscode an
- **File:** `frontend/src/lib/types.ts` — `ApiError` um `status?: number`
  ergaenzt
- **File:** `frontend/src/routes/trips/[id]/+page.server.ts` — `load()` reicht
  den `ETag`-Header der Server-Antwort durch
- **File:** `frontend/src/routes/trips/[id]/+page.svelte` — uebernimmt den
  Stempel aus `data` in die Registry; `sendStateUpdate()` verwirft ihn nach
  erfolgreichem `PATCH /state`
- **File:** `frontend/src/routes/trips/+page.svelte` — die drei
  `PATCH /state`-Aufrufer (Reaktivieren, Archivieren, Pause-Toggle) verwerfen
  den Stempel nach Erfolg
- **File:** `frontend/src/routes/archiv/+page.svelte` — der
  `PATCH /state`-Aufrufer verwirft den Stempel nach Erfolg (nur fuer
  `item.type === 'trip'`)

## Estimated Scope

- **LoC:** ~800 von 1200 freigegebenen Zeilen (siehe „Zeilenrahmen")
- **Files:** 7 Produktivdateien (1 neu, 6 geaendert), 5 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `internal/handler/etag.go` (S2) | Go-Handler-Helfer | Liefert den serverseitigen `412`-Vertrag, den diese Scheibe erstmals real ausloest |
| `GET/PUT /api/trips/{id}`, `GET/PUT /api/trips/{id}/weather-config` (S2) | HTTP-Vertrag | `ETag`-Header bei GET und erfolgreichem PUT, `If-Match`-Pruefung bei PUT |
| `frontend/src/lib/api.ts` (Bestand) | TS-Modul | Einziger Trichter fuer alle Trip-Schreibvorgaenge — Ansatzpunkt dieser Scheibe |
| `frontend/src/lib/stores/saveStatusStore.svelte.ts` (Bestand, #758/#1376/#1389) | TS-Modul | `extractMessage()` liest bereits `detail` bevorzugt — die deutsche `412`-Meldung erscheint ohne Aenderung an dieser Datei |
| `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md` | ADR | Grundsatzentscheidung „Inhalts-Fingerabdruck statt Versionsfeld" — diese Scheibe ist eine der dort benannten „kuenftigen Konsumenten", die denselben Header-Vertrag uebernehmen, statt einen eigenen Stempel-Mechanismus zu erfinden |
| `docs/specs/modules/issue_1395_s2_etag_ifmatch.md` | Spec | Server-Vertrag, auf dem diese Scheibe direkt aufbaut |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `frontend/src/lib/etagRegistry.ts` | CREATE | `Map<tripId, etag>` (Modul-Singleton — bewusst KEIN Pattern wie `saveStatusStore`, siehe „Implementation Details"), `getKnownEtag`/`setKnownEtag`/`discardEtag`, `extractTripId(path)`, `enqueueTripWrite(tripId, fn)` |
| `frontend/src/lib/api.ts` | MODIFY | `request()`: ETag-Capture aus GET/PUT-Antworten, `If-Match`-Injektion bei PUT (feldweises Header-Merge), Trip-PUTs durch die Warteschlange, `status` am geworfenen Fehlerobjekt |
| `frontend/src/lib/types.ts` | MODIFY | `ApiError.status?: number` |
| `frontend/src/routes/trips/[id]/+page.server.ts` | MODIFY | `ETag`-Header der GET-Antwort in `load()` mitgeben |
| `frontend/src/routes/trips/[id]/+page.svelte` | MODIFY | Stempel bei Mount uebernehmen; `sendStateUpdate()` verwirft ihn nach Erfolg |
| `frontend/src/routes/trips/+page.svelte` | MODIFY | Drei `/state`-Aufrufer verwerfen den Stempel nach Erfolg |
| `frontend/src/routes/archiv/+page.svelte` | MODIFY | `/state`-Aufrufer verwirft den Stempel nach Erfolg (nur Trip-Zweig) |
| `frontend/src/lib/__tests__/etagRegistryQueue.test.ts` | CREATE | Registry + Warteschlange isoliert |
| `frontend/src/lib/__tests__/apiTripEtagHeaders.test.ts` | CREATE | Trichter: Capture, Injektion, Header-Merge, `status` am Fehler |
| `frontend/src/lib/__tests__/apiTripEtagConflict.test.ts` | CREATE | Kernfall (Doppel-PUT) + Zwei-Fenster-Fall + Queue-Serialisierung gegen Mock-Fetch |
| `frontend/src/lib/__tests__/apiKeepaliveSkipsIfMatch.test.ts` | CREATE | Flush-beim-Verlassen sendet ohne `If-Match` |
| `frontend/src/lib/__tests__/tripStateDiscardsEtag.test.ts` | CREATE | Alle **fuenf** `/state`-Aufrufer verwerfen den Stempel nach Erfolg |

### Estimated Changes

- Files: 12 (7 Produktiv, 5 Tests)
- LoC: +780/-15 (Schaetzung, siehe „Zeilenrahmen")

## Implementation Details

### Die Registry ist bewusst ein Modul-Singleton

`saveStatusStore.svelte.ts` verbietet ausdruecklich modul-globale
`$state`-Exporte, weil dort jede Editor-Oberflaeche ihre EIGENE UI-Anzeige
braucht. Die ETag-Registry hat einen anderen Zweck: Sie ist ein
Daten-Frischezustand, der zur RESSOURCE gehoert (der Tour-ID), nicht zur
Editor-Instanz. Genau das braucht der Kernfall — `WeatherMetricsTab`s zwei
aufeinanderfolgende PUTs MUESSEN denselben Stand sehen, und `AlarmeTab`s
unabhaengiger Auto-Save auf DERSELBEN Tour-Seite ebenso. Ein Speicher je
Komponente wuerde genau die Faelle verfehlen, die diese Scheibe loesen soll.
Zwei Browser-Tabs/-Fenster sind ohnehin getrennte JS-Realms mit je eigener
Registry-Instanz — der Schutz zwischen ihnen kommt vollstaendig vom Server
(S2), nicht von dieser Registry.

### `extractTripId(path)` — welche Pfade zaehlen

Nur exakt `/api/trips/{id}` und `/api/trips/{id}/weather-config` matchen.
`/api/trips/{id}/state`, `/waypoints/{wp}/confirm` und alle sonstigen
Unterpfade matchen bewusst NICHT — sonst wuerde `If-Match` an Pfaden
angehaengt, die der Server laut S2 (AC-15) gar nicht prueft, oder — schlimmer
— die Capture-Logik wuerde einen `ETag` von einem Pfad uebernehmen, der gar
keinen liefert.

### Ablauf in `api.ts::request()`

**Die Reihenfolge ist der Kern dieser Scheibe. Sie muss GENAU so sein:**

1. `tripId = extractTripId(path)` bestimmen. Ist keine ermittelbar (alle
   Nicht-Trip-Pfade), laeuft alles unveraendert wie vor S3 — direkt zu
   Schritt 4.
2. **Einreihen VOR dem Nachschlagen.** Bei `method === 'PUT'` UND ermittelter
   Tour-ID UND `extra?.keepalive !== true` laeuft der GESAMTE Rest
   (Schritte 3–6) durch `enqueueTripWrite(tripId, () => ...)`. Er reiht sich
   hinter jeden bereits laufenden Schreibvorgang auf dieselbe Tour-ID ein,
   unabhaengig davon, welche Komponente ihn ausgeloest hat. Ein
   fehlgeschlagener Vorgaenger bricht die Kette NICHT ab (kein Domino).
3. **Erst INNERHALB der Warteschlange den Stand nachschlagen** und `If-Match`
   ergaenzen, sofern einer bekannt ist.

   > **Diese Reihenfolge ist nicht verhandelbar.** Wuerde der Stand vor dem
   > Einreihen gelesen, haetten beide Schreibvorgaenge des Wetter-Reiters
   > denselben — den alten — Wert bereits eingefroren, bevor der erste
   > ueberhaupt losgelaufen ist. Der zweite scheiterte dann mit `412`,
   > obwohl er ordentlich gewartet hat. Die Warteschlange waere wirkungslos
   > und AC-3 nicht erfuellbar. Der Stand muss zu dem Zeitpunkt gelesen
   > werden, zu dem die Anfrage tatsaechlich losgeht.

   Header werden FELDWEISE zusammengefuehrt
   (`{ 'Content-Type': 'application/json', ...(extra?.headers ?? {}), ...(ifMatch ? { 'If-Match': ifMatch } : {}) }`)
   — nie der ganze `headers`-Block per Spread ersetzt (die S2-Analyse hat
   diese Falle explizit benannt: `extra` wird heute NACH `headers` gespreizt
   und wuerde den `Content-Type` mitreissen).
4. `fetch` wie bisher.
5. Bei `res.ok`: liefert die Antwort einen `ETag`-Header UND ist eine Tour-ID
   ermittelt: `setKnownEtag(tripId, wert)` — gilt fuer GET UND PUT
   gleichermassen. **Noch INNERHALB der Warteschlange**, damit der naechste
   wartende Vorgang den frischen Wert vorfindet.
6. Bei `!res.ok`: wie bisher `res.json()` parsen, zusaetzlich
   `{ ...err, status: res.status }` werfen statt des rohen `err`. Bestehende
   Felder (`error`, `detail`) bleiben unveraendert — `extractMessage()` in
   `saveStatusStore.svelte.ts` liest weiterhin `detail` zuerst und aendert
   sich nicht.

   **Bei `412` zusaetzlich: den gemerkten Stand fuer diese Tour VERWERFEN.**
   Er ist nachweislich veraltet, und die `412`-Antwort traegt laut S2
   bewusst keinen neuen mit. Bliebe er stehen, scheiterte jeder weitere
   Versuch endlos am selben veralteten Wert — der Nutzer kaeme aus dem
   Zustand nicht mehr heraus, ohne die Seite neu zu laden. Nach dem
   Verwerfen geht der naechste Versuch ohne Vorbedingung durch (Verhalten
   wie vor S3). Das ist bewusst die nachgiebige Richtung: **einmal** melden,
   dann nicht mehr im Weg stehen.

### Der Flush beim Verlassen umgeht BEIDES: Warteschlange und `If-Match`

`{ keepalive: true }` wird im gesamten Repo AUSSCHLIESSLICH von
`beforeNavigate`s `willUnload`-Zweig gesetzt (`routes/trips/[id]/+page.svelte:32`)
— verifiziert, kein zweiter Aufrufer. Diese Scheibe nutzt dieses bereits
vorhandene, eindeutige Signal, um bei genau diesem Aufruf KEIN `If-Match`
anzuhaengen: Ein Nutzer, der die Seite verlaesst, soll seine letzte Aenderung
nicht durch einen unsichtbaren `412` verlieren — er sieht die Ablehnung nie,
weil die Seite schon weg ist. Kein neuer Parameter noetig, keine neue
Kopplung zwischen `SaveFn` und der Registry.

**Ebenso wichtig und leicht zu uebersehen: dieser Aufruf wird auch NICHT
eingereiht.** Ein `keepalive`-Vorgang hat nur ein sehr kurzes Zeitfenster,
bevor der Browser die Seite abraeumt. Laege er hinter einem noch laufenden
Schreibvorgang in der Warteschlange, ginge er womoeglich nie los — und die
letzte Aenderung waere verloren, also genau der Schaden, den dieser Pfad
verhindern soll. Er laeuft SOFORT und ohne Vorbedingung. Der Preis ist
bekannt und akzeptiert: Dieser eine Vorgang kann eine fremde Aenderung
ueberschreiben. Beim Verlassen der Seite ist „die Aenderung des Nutzers
retten" wichtiger als „einen theoretischen Konflikt vermeiden" — und es ist
exakt das Verhalten von heute, also keine Verschlechterung.

Bekannter Preis: sollte
`keepalive` kuenftig fuer einen anderen Zweck als „Seite verlassen" verwendet
werden, erbt dieser automatisch dasselbe Verhalten — als Known Limitation
dokumentiert.

### Die fuenf `/state`-Aufrufer und der bewusst gewaehlte Weg

**FUENF** Stellen sprechen `PATCH /api/trips/{id}/state` per rohem `fetch`
an, am Trichter vorbei — nachgezaehlt am Code, nicht geschaetzt:

| # | Stelle | Kontext |
|---|---|---|
| 1 | `routes/trips/[id]/+page.svelte:68` | `sendStateUpdate` auf der Detailseite — **die kritischste**, weil sie auf DERSELBEN Seite liegt wie die Editor-Reiter |
| 2 | `routes/trips/+page.svelte:172` | Archivierung aufheben (Listenseite) |
| 3 | `routes/trips/+page.svelte:190` | `handleArchive` (Listenseite) |
| 4 | `routes/trips/+page.svelte:207` | `handlePauseToggle` (Listenseite) |
| 5 | `routes/archiv/+page.svelte:53` | Archivseite, URL an `:50` — **nur der `item.type === 'trip'`-Zweig**; der Zwilling an `:51` betrifft Orts-Vergleiche und bleibt unberuehrt (S6) |

Jeder erfolgreiche Aufruf veraendert die
Tourdatei und damit den Fingerabdruck, liefert aber laut S2 (AC-15) KEINEN
`ETag` zurueck — ein zuvor gemerkter Stand wird dadurch still veraltet.

**Gewaehlter Weg: expliziter `discardEtag(tripId)`-Aufruf nach Erfolg an
allen fuenf Stellen — NICHT die Umleitung dieser Aufrufer durch den Trichter.**
Begruendung: Jeder dieser Aufrufer hat eine eigene, bereits bestehende
Fehlerbehandlung, die den Antwortkoerper feingranular auswertet (z. B.
`routes/trips/[id]/+page.svelte:78-80`: eigenes `res.json()` mit
`errBody.detail`-Uebersetzung fuer die Statusanzeige). Diese Behandlung durch
`api.patch()` zu ersetzen wuerde Verhalten aendern, das ausserhalb des
Scopes von #1395 liegt, und das Risiko einer Regression an einer Stelle
schaffen, die mit ETag/If-Match nichts zu tun hat. Zwei Zeilen
(`discardEtag(id)` nach `if (res.ok)`) pro Stelle sind der kleinere,
risikoaermere Eingriff und erfuellen die Anforderung vollstaendig: Der
naechste Schreibvorgang auf diese Tour findet keinen bekannten Stand mehr vor
und wird — wie in S2 spezifiziert — ohne `If-Match` angenommen.

### Server-Naht: `+page.server.ts` — uebernimmt nur beim ERSTEN Mal

Nachtrag aus der Umsetzung: Die Naht darf den Stempel **nicht bedingungslos**
uebernehmen. `data.etag` stammt aus dem Lade-`GET`; laeuft `load()` erneut
(Invalidierung, erneute Navigation), waehrend ein Speichervorgang unterwegs
ist, traegt es den Stand VOR dem Speichern — derselbe Rueckschritt wie bei
einer verspaeteten Leseantwort, nur durch einen anderen Eingang. Heute nicht
ausloesbar (die Detailseite ruft selbst kein `invalidateAll()`), aber ein
Aktualisieren-Knopf liesse es still aufleben.

`adoptEtagFromPageLoad(tripId, etag)` uebernimmt deshalb nur, solange die Tour
in dieser Sitzung **noch nie** einen Stempel gefuehrt hat (Zaehlerstand 0). Ist
bereits einer bekannt, ist er mindestens so jung wie der aus dem Ladevorgang.

Ausserdem haengt die Uebernahme ausschliesslich an `data`, **nicht** am
veraenderlichen `trip`-Zustand der Seite: `sendStateUpdate()` setzt am Ende
`trip = updated`, ein daran haengender Effekt haette also unmittelbar nach dem
Verwerfen den alten Stempel wieder abgelegt — AC-5 waere auf der Detailseite
exakt ins Gegenteil verkehrt worden.

### Server-Naht: der Lesevorgang selbst

```ts
const etag = res.headers.get('ETag');
const trip = await res.json();
return { trip, etag: etag ?? undefined };
```

`routes/trips/[id]/+page.svelte` uebernimmt `data.etag` bei Mount
(`$effect`, einmalig) in die Registry via `setKnownEtag(trip.id, data.etag)`
— nur wenn `data.etag` vorhanden ist (Rueckfallposition: fehlt er, bleibt die
Registry fuer diese Tour leer, naechster Schreibvorgang laeuft wie vor S3).

## Expected Behavior

- **Input:** `GET /api/trips/{id}` liefert `ETag: "<stempel>"` → Registry
  merkt sich `<id> -> <stempel>` ohne sichtbaren Effekt fuer den Nutzer
- **Input:** `PUT /api/trips/{id}` bzw. `.../weather-config`, Stand bekannt →
  Anfrage traegt automatisch `If-Match: "<stempel>"`
- **Input:** zwei PUTs auf dieselbe Tour kurz hintereinander (gleiche
  Browser-Sitzung) → laufen serialisiert, der zweite verwendet automatisch
  den vom ersten zurueckgegebenen neuen Stempel
- **Output:** eine `412`-Antwort erscheint am Speicher-Anzeiger als die vom
  Server gelieferte deutsche Meldung, nicht als generischer Fehler
- **Side effects:** keine zusaetzliche Persistenz, keine zusaetzlichen
  Netzwerk-Anfragen — die Registry lebt nur im Speicher des Browser-Tabs

## Warum das der gefaehrlichste Schnitt ist

Alle 19 identifizierten Trip-Schreibstellen (17 auf `/api/trips/{id}`, 2 auf
`/weather-config`) laufen durch DIESELBE `request()`-Funktion in `api.ts`.
Ein Fehler in dieser Scheibe bricht nicht eine einzelne Funktion, sondern
JEDES Speichern in der gesamten Anwendung — vom einzelnen Etappen-Edit bis
zum Wetter-Reiter. Die eingebaute Rueckfallposition ist deshalb zentral fuer
die Sicherheit dieser Scheibe: **Ist fuer eine Tour-ID kein Stand bekannt,
wird KEIN `If-Match` gesendet und der Schreibvorgang verhaelt sich exakt wie
vor dieser Scheibe** (S2-Rollout-Politik: fehlender Header = angenommen).
Jeder Fehler in der Capture-Logik (ETag wird nicht gemerkt) fuehrt also
bestenfalls dazu, dass der Schutz fuer diese eine Tour nicht greift — nicht
dazu, dass ein legitimer Schreibvorgang faelschlich blockiert wird. Die
gefaehrliche Fehlerrichtung waere umgekehrt (ein falscher oder veralteter
Stempel wird faelschlich gesendet und blockiert legitimes Speichern) — genau
dagegen sichert der Kernfall-Test (`WeatherMetricsTab`s Doppel-PUT) und der
Warteschlangen-Test ab.

## Testplan

Alle Tests unter `node --test` (`--import ./test-lib-loader.mjs
--experimental-strip-types`, `$lib`-Mapping via Loader). Fetch wird per
`globalThis.fetch = async (...) => ...` gemockt (kein bisheriger Test im
Repo mockt `fetch` — dieser Trichter ist bislang ungetestet, S3 liefert die
ersten echten Tests dafuer). Namen nach Verhalten, nicht nach Issue-Nummer.

### `frontend/src/lib/__tests__/etagRegistryQueue.test.ts`

| Test | Deckt |
|---|---|
| `test_getSetDiscard_roundtrip` | Grundfunktion der Registry |
| `test_extractTripId_matchesOnlyTripAndWeatherConfigPaths` | Pfadfilter (State/Waypoints/Sub-Ressourcen matchen NICHT) |
| `test_enqueueTripWrite_serializesSameTripId` | AC-9 — zweiter Aufruf startet nachweislich erst, wenn der erste aufgeloest ist |
| `test_enqueueTripWrite_differentTripIds_runConcurrently` | Warteschlange blockiert NICHT ueber Tour-Grenzen hinweg |
| `test_enqueueTripWrite_continuesAfterRejectedPredecessor` | kein Domino-Abbruch bei fehlgeschlagenem Vorgaenger |

### `frontend/src/lib/__tests__/apiTripEtagHeaders.test.ts`

| Test | Deckt |
|---|---|
| `test_get_capturesEtagFromResponse` | AC-1 |
| `test_put_attachesIfMatch_whenStampKnown` | AC-2 |
| `test_put_omitsIfMatch_whenStampUnknown` | AC-7 |
| `test_put_mergesHeadersFieldwise_contentTypeSurvives` | Header-Merge-Falle aus der Analyse — `extra.headers` darf `Content-Type` NICHT loeschen |
| `test_put_neverAttachesIfMatch_onStateOrWaypointPaths` | Pfadfilter am Trichter |
| `test_thrownError_carriesStatusAlongsideExistingFields` | AC-8 (Vorbedingung: Status muss ankommen) |
| `test_extractMessage_unaffectedByNewStatusField` | Regressionsschutz — `saveStatusStore.svelte.ts` bleibt unveraendert im Verhalten |

### `frontend/src/lib/__tests__/apiTripEtagConflict.test.ts`

Mock-Fetch simuliert den S2-Vertrag: `PUT` ohne/mit passendem `If-Match` →
`200` + neuer `ETag`; mit falschem `If-Match` → `412`.

| Test | Deckt |
|---|---|
| `test_weatherMetricsTab_sequentialDoublePut_bothSucceed` | AC-3 (Kernfall) — zwei `api.put`-Aufrufe hintereinander wie in `handleSave()`, zweiter uebernimmt automatisch den neuen Stempel des ersten |
| `test_twoRealms_secondArrivalRejected_notOverwritten` | AC-4 — zwei unabhaengige Registry-Instanzen (simulieren zwei Tabs), der zeitlich zweite PUT beim Server bekommt `412` |
| `test_concurrentAutoSaveAcrossTabs_sameTripId_bothSucceedSerialized` | AC-9 — zwei gleichzeitig ausgeloeste `api.put`-Aufrufe auf dieselbe Tour-ID gelingen beide, weil sie serialisiert ankommen |
| `test_withoutKnownStamp_writeSucceeds_asBefore` | AC-7 |

### `frontend/src/lib/__tests__/apiKeepaliveSkipsIfMatch.test.ts`

| Test | Deckt |
|---|---|
| `test_keepaliveFlush_omitsIfMatch_evenWithKnownStamp` | AC-6 |
| `test_nonKeepaliveCall_stillAttachesIfMatch` | Abgrenzung — nur der Keepalive-Fall ist die Ausnahme |

### `frontend/src/lib/__tests__/tripStateDiscardsEtag.test.ts`

Quelltext-Verhaltenspruefung (analog `weatherMetricsTabDayWindowSave.test.ts`):
prueft je Aufrufer, dass nach dem `if (res.ok)`-Zweig ein `discardEtag(...)`-
Aufruf mit der jeweils richtigen Tour-ID-Variable steht.

| Test | Deckt |
|---|---|
| `test_tripDetailPage_sendStateUpdate_discardsEtagOnSuccess` | AC-5 |
| `test_tripsListPage_allThreeStateCallers_discardEtagOnSuccess` | AC-5, AC-10 |
| `test_archivPage_tripStateCaller_discardsEtag_compareUnaffected` | AC-10 — Compare-Zweig (`item.type !== 'trip'`) bleibt unberuehrt (S6) |

### `frontend/src/routes/trips/[id]/__tests__/pageServerEtagPassthrough.test.ts`

| Test | Deckt |
|---|---|
| `test_load_passesEtagHeaderIntoPageData` | AC-1 |
| `test_load_missingEtagHeader_dataEtagIsUndefined` | AC-7 (Rueckfallposition auf Server-Naht-Ebene) |

## Acceptance Criteria

- **AC-1:** Given eine Tour-Seite wird erstmals in dieser Browsersitzung geladen / When der Server das Trip-Dokument liefert / Then merkt sich das Frontend den zugehoerigen Stand automatisch, ohne zusaetzlichen Request oder sichtbare Verzoegerung
  - Test: `test_get_capturesEtagFromResponse`, `test_load_passesEtagHeaderIntoPageData`

- **AC-2:** Given eine Tour wurde bereits geladen / When der Nutzer eine Aenderung an ihr speichert / Then traegt die Speicher-Anfrage automatisch den zuletzt bekannten Stand, ohne dass eine einzelne Editor-Komponente dafuer Code enthalten muss
  - Test: `test_put_attachesIfMatch_whenStampKnown`

- **AC-3 (Kernfall):** Given der Wetter-Reiter loest beim Speichern zwei aufeinanderfolgende Schreibvorgaenge derselben Tour aus / When beide nacheinander abgeschickt werden / Then gelingen beide — der zweite verwendet automatisch den durch den ersten aktualisierten Stand
  - Test: `test_weatherMetricsTab_sequentialDoublePut_bothSucceed`

- **AC-4:** Given zwei Browser-Reiter oder -Fenster haben dieselbe Tour geladen / When beide unabhaengig voneinander speichern und die Aenderung des einen zuerst beim Server ankommt / Then wird der zeitlich zweite, jetzt veraltete Schreibvorgang abgelehnt statt die bereits gespeicherte Aenderung zu ueberschreiben
  - Test: `test_twoRealms_secondArrivalRejected_notOverwritten`

- **AC-5:** Given eine Tour wurde soeben pausiert oder archiviert / When der Nutzer danach in einem Editor-Reiter derselben Tour speichert / Then gelingt dieses Speichern, ohne dass die eigene Anwendung sich selbst einen Konflikt erzeugt hat
  - Test: `test_tripDetailPage_sendStateUpdate_discardsEtagOnSuccess`, `test_tripsListPage_allThreeStateCallers_discardEtagOnSuccess`

- **AC-6:** Given der Nutzer verlaesst die Seite mit einer noch ausstehenden Aenderung / When der Browser den Abschluss-Speichervorgang beim Entladen abschickt / Then geht dieser Vorgang unabhaengig vom zuletzt bekannten Stand durch — kein unsichtbarer `412` verhindert das letzte Sicherheitsnetz
  - Test: `test_keepaliveFlush_omitsIfMatch_evenWithKnownStamp`

- **AC-7:** Given fuer eine Tour ist in dieser Browsersitzung noch kein Stand bekannt / When eine Aenderung an ihr gespeichert wird / Then verhaelt sich der Schreibvorgang exakt wie vor dieser Scheibe — er wird unabhaengig vom tatsaechlichen Dateizustand angenommen
  - Test: `test_put_omitsIfMatch_whenStampUnknown`, `test_withoutKnownStamp_writeSucceeds_asBefore`, `test_load_missingEtagHeader_dataEtagIsUndefined`

- **AC-8:** Given ein Speichervorgang wird wegen eines veralteten Standes vom Server abgelehnt / When die Ablehnung am Speicher-Anzeiger erscheint / Then zeigt sie die vom Server gelieferte deutsche Meldung — nicht die generische „Fehler beim Speichern"-Meldung und nicht den rohen Statuscode
  - Test: `test_thrownError_carriesStatusAlongsideExistingFields`, `test_extractMessage_unaffectedByNewStatusField`

- **AC-9:** Given zwei Editor-Reiter derselben Tour-Seite loesen unabhaengig voneinander (je eigener Auto-Save-Debounce) nahezu gleichzeitig einen eigenen Schreibvorgang auf dieselbe Tour aus / When beide abgeschickt werden / Then laufen sie serialisiert nacheinander statt gleichzeitig beim Server anzukommen, und beide gelingen
  - Test: `test_enqueueTripWrite_serializesSameTripId`, `test_concurrentAutoSaveAcrossTabs_sameTripId_bothSucceedSerialized`

- **AC-10:** Given eine Tour wurde ausschliesslich ueber die Listen- oder Archiv-Seite pausiert/archiviert, aber nie ueber die Detailseite geladen / When danach ein Schreibvorgang auf sie ausgeloest wird / Then wird er nicht blockiert — die Tour hat nie einen Stand in der Registry gehabt, das Verhalten entspricht AC-7
  - Test: `test_archivPage_tripStateCaller_discardsEtag_compareUnaffected`, `test_tripsListPage_allThreeStateCallers_discardEtagOnSuccess`

## Was nicht kaputtgehen darf

Alle folgenden Bestandstests pruefen den Quelltext des Anfrageweges oder das
Verhalten des Speicher-Anzeigers und muessen UNVERAENDERT gruen bleiben, weil
diese Scheibe keine Aufruf-Syntax an den Call-Sites aendert, nur `api.ts`-
interne Logik ergaenzt:

- `frontend/src/lib/stores/__tests__/saveStatus.test.ts` — `defer()`/
  `cancel()`/`settle()`/`flush()`-Idempotenz aus #1389 bleibt unberuehrt;
  `extractMessage()` wird dort nicht geprueft, siehe eigener Regressionstest
  oben
- `frontend/src/lib/components/shared/__tests__/weatherMetricsTabDayWindowSave.test.ts` —
  Quelltext-Grep verlangt u. a. `api.put<Trip>(\`/api/trips/${trip!.id}\`` als
  literalen Aufruf; diese Scheibe aendert den Call-Site-Text nicht, nur was
  `api.put` intern tut
- `frontend/src/lib/components/shared/__tests__/alarme_delivery_consolidated_save.test.ts`
- `frontend/src/lib/components/shared/__tests__/alarme_save_single_writer.test.ts`
- `frontend/src/lib/components/alerts-tab/issue_850_alert_metrics_stale.test.ts`
  (Quelltext-Grep auf `api.put<Trip>`)
- `frontend/src/lib/components/shared/__tests__/OutputLayoutEditor.test.ts`
  (Negativ-Grep — die Komponente darf weiterhin KEINE `api.put(`-Aufrufe
  enthalten; unberuehrt, da trip-agnostisch)

## Known Limitations

- **Ein nicht-serialisierter Vorgang kann einen juengeren Stempel nie durch
  einen aelteren ersetzen — das ist eine Invariante, kein Zufall.** Umgesetzt
  ueber einen Aenderungszaehler je Tour (`etagVersion`), der bei JEDER
  Veraenderung hochzaehlt, Setzen wie Verwerfen. `send()` merkt sich den Stand
  beim Losschicken; **bedingungslos** setzen darf nur ein serialisierter
  Schreibvorgang, alles andere (Lesevorgang, Entlade-Flush, Server-Naht) geht
  ueber `setKnownEtagIfUnchanged` und wird verworfen, wenn sich der Zaehler
  seither bewegt hat.

  Der urspruenglich naheliegende Weg — „Stempel aus einem Lesevorgang nur
  uebernehmen, solange die Warteschlange leer ist" — waere **wirkungslos**
  gewesen und ist per roter Messung verworfen: Im gemeldeten Ablauf laeuft der
  Schreibvorgang KOMPLETT durch, bevor die Leseantwort eintrifft. Die
  Warteschlange ist dann leer, die Bedingung erfuellt, der veraltete Stempel
  wuerde gesetzt.

- **`clearEtagRegistry()` darf zur Laufzeit nicht aufgerufen werden**, solange
  noch Anfragen unterwegs sein koennen. Sie setzt den Zaehler auf 0 zurueck;
  passieren an derselben Tour danach zufaellig wieder genau so viele
  Aenderungen wie zuvor, haelt ein Nachzuegler seinen laengst veralteten Stand
  fuer aktuell und kommt durch. Heute folgenlos — die Funktion hat **keinen
  Aufrufer im Produktivcode** und dient nur der Testisolation. Wer einen
  Zuruecksetzen bei Nutzerwechsel braucht, muss den Zaehler monoton lassen oder
  laufende Anfragen ungueltig machen. Als Warnung am Funktionskommentar
  hinterlegt.

- **Nach einem erfolgreichen Entlade-Flush kann die Registry veraltet sein.**
  Der Flush ist bewusst nicht serialisiert; laeuft parallel ein normaler
  Schreibvorgang durch, wird das Ergebnis des Flush beim Eintreffen verworfen,
  obwohl er die Datei serverseitig sehr wohl veraendert hat. Praktisch
  folgenlos: `keepalive` wird ausschliesslich beim Verlassen der Seite gesetzt
  — die Registry existiert danach nicht mehr lange genug, um mit dem veralteten
  Wert noch etwas anzurichten. Praezisiert die bereits dokumentierte Zusage,
  dass dieser eine Vorgang eine fremde Aenderung ueberschreiben darf.

- **`keepalive` als Ausnahme-Signal ist an einen heutigen Ist-Zustand
  gekoppelt.** Nur `beforeNavigate`s `willUnload`-Zweig setzt
  `{ keepalive: true }` (verifiziert, ein einziger Aufrufer). Sollte
  `keepalive` kuenftig fuer einen anderen Zweck verwendet werden, wuerde
  dieser automatisch ebenfalls ohne `If-Match` senden — kein Schaden im
  heutigen Zustand, aber ein Kopplungspunkt fuer kuenftige Aenderungen.
- **Kein Konflikt-Zustand am Speicher-Anzeiger.** `SaveState` bleibt
  `'idle' | 'dirty' | 'saving' | 'error'` — eine `412`-Ablehnung erscheint wie
  jeder andere Fehler als `'error'` mit deutschem Text. Eine dedizierte
  „Konflikt, bitte neu laden"-UI mit Wiederholungs-Aktion ist S4.
- **Kein Aufraeumen der Registry beim Loeschen einer Tour.** Ein geloeschter
  Tour-Eintrag bleibt bis zum Reload des Tabs in der Registry stehen —
  harmlos, weil eine geloeschte Tour-ID praktisch nie wiederverwendet wird und
  kein GET/PUT mehr auf sie folgt.
- **Kein Rueckbau von `settle()`/`SETTLE_TIMEOUT_MS`/dem Wartblock in
  `applyCascade`** (`EditStagesPanelNew.svelte:423`) — bleibt in dieser
  Scheibe unangetastet, folgt in S5, nachdem der Server-Schutz produktiv
  gelaufen ist.
- **Kein Ortsvergleich.** `PUT /api/briefings/{id}?kind=vergleich` ist nicht
  im Scope — S6, siehe „Offene Punkte" in der S2-Spec zur
  Wiedereintrittsfaehigkeits-Falle von `LockBriefing`.

## Was S4/S5/S6 erben

- **S4 („Nochmal speichern"):** braucht einen eigenen `SaveState`-Wert (oder
  ein zusaetzliches Flag neben `error`) fuer „Konflikt, nicht generischer
  Fehler" — unterscheidbar am neuen `status`-Feld dieser Scheibe (`412` vs.
  `400`/`500`). Braucht einen Reload-und-Retry-Mechanismus, der den Nutzer
  entscheiden laesst, ob sein Stand verworfen oder erneut versucht wird.
- **S5 (Rueckbau der clientseitigen Warteschutz-Konstruktionen):** kann erst
  beginnen, wenn diese Scheibe produktiv gelaufen ist und die Registry sich
  als zuverlaessig erwiesen hat. Betrifft `settle()`, `SETTLE_TIMEOUT_MS`,
  den Wartblock in `applyCascade` (`EditStagesPanelNew.svelte`).
- **S6 (Ortsvergleich):** uebernimmt denselben `ETag`/`If-Match`-Vertrag fuer
  `kind=vergleich` — inklusive der in S2 dokumentierten
  `LockBriefing`-Wiedereintritts-Falle. Kann auf dieselbe `etagRegistry.ts`
  zurueckgreifen, sofern der Compare-Pfad ebenfalls ueber `/api/trips/{id}`
  bzw. eine analoge Route laeuft (zu pruefen bei Scheiben-Start, siehe
  Trip/Compare-Code-Teilungsvorgabe).

## Zeilenrahmen

1200 Zeilen, vom PO vorab freigegeben (analog zur zweimaligen Anhebung bei
S2 — Nachweise fuer diese Fehlerklasse sind erfahrungsgemaess umfangreicher
als der Produktivcode, weil jeder Test eine echte Serialisierungs- oder
Kopfzeilen-Eigenschaft nachweist statt nur einen Rueckgabewert).

| Bereich | Schaetzung |
|---|---|
| Produktivcode (`etagRegistry.ts` neu, `api.ts`, `types.ts`, `+page.server.ts`, drei `.svelte`-Aenderungen) | ~200 |
| Tests (5 neue Testdateien) | ~600 |
| **Summe** | **~800 von 1200** |

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0036 (kein neues ADR)
- **Rationale:** Diese Scheibe setzt die in ADR-0036 bereits getroffene
  Grundsatzentscheidung um — „kuenftige Konsumenten des Fingerabdrucks (z. B.
  das Frontend in S3) uebernehmen denselben Header-Vertrag, statt einen
  eigenen Stempel-Mechanismus zu erfinden" (ADR-0036, Abschnitt
  „Konsequenzen"). Es gibt keine neue schwer umkehrbare oder
  mehrere Systemteile betreffende Entscheidung zu treffen — die
  Implementierungsfragen dieser Scheibe (Modul-Singleton vs. Instanz,
  `keepalive` als Ausnahme-Signal, expliziter `discardEtag` statt
  Trichter-Umleitung) sind lokale Umsetzungsentscheidungen innerhalb des
  bereits beschlossenen Vertrags, keine Architektur-Entscheidungen.

## Changelog

- 2026-07-27: Initial spec erstellt — Issue #1395 Scheibe S3, aufbauend auf S1/S2 (Commits d3bb4b8f, 603601ef)
