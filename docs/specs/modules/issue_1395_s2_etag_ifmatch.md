---
entity_id: issue_1395_s2_etag_ifmatch
type: module
created: 2026-07-27
updated: 2026-07-27
status: draft
version: "1.0"
tags: [go, trip, weather-config, concurrency, etag, if-match]
---

<!-- Issue #1395 Scheibe S2 — Nebenlaeufigkeitsschutz: ETag/If-Match auf Trip-Schreibpfaden -->

# Issue #1395 Scheibe S2 — ETag/If-Match fuer Trip- und Wetter-Konfig-Schreibpfade

## Approval

- [ ] Approved

## Purpose

`UpdateTripHandler` und die vier anderen Trip-Schreibpfade machen heute ein reines
Read-Modify-Write ohne Versionsbegriff: Treffen zwei Schreibvorgaenge zeitlich
zusammen, gewinnt der, der ZULETZT ANKOMMT — nicht der, der zuletzt abgeschickt
wurde. Diese Scheibe verdrahtet den in S1 gebauten Inhalts-Fingerabdruck
(`Store.BriefingFingerprint`) und die Briefing-Sperre (`Store.LockBriefing`) als
HTTP-Vertrag: `GET` liefert einen `ETag`-Header, `PUT` prueft optional `If-Match`
und lehnt einen veralteten Schreibvorgang mit `412 Precondition Failed` ab, statt
ihn kommentarlos anzunehmen. Ohne `If-Match` verhaelt sich jeder Aufruf exakt wie
heute — S2 schaltet von aussen nichts scharf, das folgt erst mit dem Frontend in
S3.

## Source

- **File:** `internal/handler/trip.go` — `TripHandler` (ETag setzen), `UpdateTripHandler`
  (If-Match pruefen + Sperre), `CreateTripHandler`, `UpdateTripStateHandler`,
  `ConfirmWaypointHandler` (Sperre, keine If-Match-Pruefung)
- **File:** `internal/handler/weather_config.go` — `GetTripWeatherConfigHandler`
  (ETag setzen), `PutTripWeatherConfigHandler` (If-Match pruefen + Sperre)
- **File:** `internal/handler/etag.go` (NEU) — geteilter Helfer: `If-Match`-Header
  parsen (Liste, Anfuehrungszeichen, `*`), gegen einen Fingerabdruck pruefen,
  `412`-Antwortkoerper schreiben
- **File:** `openapi.yaml` — `/api/trips/{id}` (GET/PUT) um `ETag`/`If-Match`
  ergaenzt, `/api/trips/{id}/weather-config` (GET/PUT) neu aufgenommen
- **Identifier:** `store.BriefingFingerprint` (S1, unveraendert), `store.LockBriefing`
  (S1, wird hier erstmals verdrahtet)

## Estimated Scope

- **LoC:** ~590 von 600 freigegebenen Zeilen (siehe „Zeilenrahmen")
- **Files:** 4 Produktivdateien (2 geaendert, 1 neu, 1 Doku-Contract), 2 neue Testdateien
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `store.BriefingFingerprint` (S1, `internal/store/briefing_fingerprint.go`) | Go-Funktion | Liefert den sha256-Hex-Fingerabdruck der `briefings/<id>.json`-Rohbytes; Basis fuer `ETag` |
| `store.LockBriefing` (S1, `internal/store/briefing_lock.go`) | Go-Funktion | Sperre je Nutzer+Briefing ueber den gesamten Lesen-Pruefen-Schreiben-Zyklus |
| `middleware.UserIDFromContext` | Go-Funktion | Mandantentrennung — Sperrschluessel und Fingerabdruck-Pfad haengen an der echten UserID |
| `internal/handler/briefing_subscription.go` (`UpdateBriefingHandler`) | Go-Handler | `PUT /api/briefings/{id}?kind=route` reicht per `ServeHTTP` an `UpdateTripHandler` durch — automatisch mit abgesichert, kein eigener Code noetig |
| `docs/specs/modules/go_trip_write.md` | Spec | Dokumentiert den bisherigen Ist-Stand „kein ETag/If-Match" — wird durch S2 falsch (siehe „Offene Punkte") |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/handler/trip.go` | MODIFY | `TripHandler` setzt `ETag`; `UpdateTripHandler`, `CreateTripHandler`, `UpdateTripStateHandler`, `ConfirmWaypointHandler` **und `DeleteTripHandler`** nehmen `LockBriefing`; `UpdateTripHandler` prueft `If-Match`. Zusaetzlich in allen Handlern `s = s.WithUser(...)` → `s := s.WithUser(...)` (behebt einen echten Datenwettlauf, siehe „Known Limitations") |
| `internal/handler/weather_config.go` | MODIFY | `GetTripWeatherConfigHandler` setzt `ETag`; `PutTripWeatherConfigHandler` nimmt `LockBriefing` und prueft `If-Match` |
| `internal/handler/etag.go` | CREATE | Geteilter If-Match-Parser/-Vergleich + 412-Antwortkoerper, genutzt von `trip.go` und `weather_config.go` |
| `openapi.yaml` | MODIFY | `ETag`/`If-Match` an `/api/trips/{id}`; `/api/trips/{id}/weather-config` neu dokumentiert |
| `internal/handler/trip_etag_ifmatch_test.go` | CREATE | Testfaelle fuer Trip-GET/PUT/POST/PATCH-Pfade |
| `internal/handler/weather_config_etag_ifmatch_test.go` | CREATE | Testfaelle fuer `/weather-config`-GET/PUT |

### Estimated Changes

- Files: 6 (4 Produktiv/Doku, 2 Tests)
- LoC: +560/-30 (Schaetzung, siehe Aufschluesselung unten)

## Implementation Details

### Ablauf in den PUT-Handlern (`UpdateTripHandler`, `PutTripWeatherConfigHandler`)

1. `unlock := s.LockBriefing(id); defer unlock()`
2. `oldFp, err := s.BriefingFingerprint(id)` — Fehler hier (echter Lesefehler, nicht
   „Datei fehlt") → `500 store_error`
3. `existing, err := s.LoadTrip(id)` — wie bisher, `404` wenn `nil`
4. **If-Match pruefen** — GENAU HIER, VOR dem Lesen des Rumpfes: stimmt die
   Vorbedingung nicht, ist der Rumpf irrelevant.
   - Header fehlt oder leer → weiter (angenommen)
   - `If-Match: *` → weiter, sofern der Trip existiert (Schritt 3 hat das schon
     sichergestellt)
   - sonst: Liste der angegebenen Werte gegen `oldFp` vergleichen (Anfuehrungszeichen
     abstreifen); passt keiner → `412` mit `{"error":"precondition_failed","detail":"<deutsch>"}`,
     KEIN `ETag`-Header in dieser Antwort, Funktion endet hier — nichts wird
     geschrieben
5. Rumpf dekodieren (`400` bei Fehler), mergen/validieren (`400` bei Validierungsfehler)
   wie bisher
6. `s.SaveTrip(existing)` — wie bisher, `500` bei Fehler
7. `newFp, fpErr := s.BriefingFingerprint(id)` — schlaegt das fehl, wird der
   `ETag`-Header WEGGELASSEN, trotzdem `200`: ein geglueckter Schreibvorgang darf
   nicht nachtraeglich zu `500` werden (Fail-soft, siehe AC-16)
8. Bei Erfolg: `w.Header().Set("ETag", `"`+newFp+`"`)`, dann Antwortkoerper wie bisher

### Ablauf in den GET-Handlern (`TripHandler`, `GetTripWeatherConfigHandler`)

Nach dem `LoadTrip`, VOR dem Antwortkoerper: `fp, err := s.BriefingFingerprint(id)`.
Schlaegt das fehl: `ETag`-Header weglassen, Antwort wie bisher ausliefern (kein
harter Fehler fuer einen Lesevorgang, der sonst erfolgreich waere). Die Sperre wird
auch bei GET genommen (`LockBriefing`/`defer unlock()`), damit der ausgelieferte
`ETag` garantiert zur ausgelieferten Fassung passt — sonst koennte ein
gleichzeitiger PUT zwischen Fingerabdruck-Lesen und Rumpf-Serialisierung die Datei
aendern, und der Client haelt einen Stempel einer anderen Fassung als den Rumpf.

### Ablauf in den PATCH-Handlern und in `CreateTripHandler`

`CreateTripHandler`, `UpdateTripStateHandler`, `ConfirmWaypointHandler` nehmen
`LockBriefing`/`defer unlock()` um ihren bestehenden Lesen-Pruefen-Schreiben-Zyklus
(bei `CreateTripHandler`: um den Schreibvorgang, da vorher noch nichts existiert),
pruefen aber **keinen** `If-Match`-Header. Das ist bewusst: eine Pruefung dort
wuerde S3 zwingen, auch fuer diese Pfade ETags zu fuehren; das ist nicht beauftragt
und wuerde von aussen etwas scharf schalten, das nicht spezifiziert ist. Die
Sperre allein reicht, um zu verhindern, dass ein `PATCH` mitten in einen laufenden
`PUT` hineinschreibt. `CreateTripHandler` liefert bewusst KEINEN `ETag` — nach dem
Anlegen holt der Client ohnehin frisch (Schritt „`GET`").

### If-Match-Parsing (`internal/handler/etag.go`)

```go
func ifMatchAllows(header, current string) bool {
    header = strings.TrimSpace(header)
    if header == "" || header == "*" {
        return true // *: angenommen, da der Aufrufer die Existenz schon geprueft hat
    }
    for _, part := range strings.Split(header, ",") {
        if strings.Trim(strings.TrimSpace(part), `"`) == current {
            return true
        }
    }
    return false
}
```

`writePreconditionFailed(w, detail string)` setzt `Content-Type: application/json`,
Status `412`, Rumpf `{"error":"precondition_failed","detail":detail}` — KEIN
`ETag`-Header.

### openapi.yaml

- `/api/trips/{id}` `get:` → neuer `headers:`-Block an der `200`-Response mit
  `ETag` (`schema: {type: string}`, Beispiel `"a1b2c3..."`)
- `/api/trips/{id}` `put:` → neuer `parameters:`-Eintrag `If-Match`
  (`in: header`, `required: false`), `headers:`-Block mit `ETag` an der `200`-Response,
  neue `"412":`-Response mit Schema analog `Error`/`ValidationError`
  (`error: precondition_failed`)
- `/api/trips/{id}/weather-config` **neu**: `get:` (200 mit `ETag`-Header, 404) und
  `put:` (`If-Match`-Parameter, 200 mit `ETag`-Header, 404, 412) — bisher komplett
  undokumentiert, wird hier erstmals aufgenommen, weil der If-Match-Vertrag sonst
  fuer diesen Pfad unsichtbar bliebe

## Expected Behavior

- **Input:** `GET /api/trips/{id}` → Antwort traegt `ETag: "<64-stelliger Hex-Wert>"`,
  sofern die Tour existiert und der Fingerabdruck lesbar ist
- **Input:** `PUT /api/trips/{id}` ohne `If-Match` → wie bisher angenommen
- **Input:** `PUT /api/trips/{id}` mit `If-Match: "<veralteter Stempel>"` →
  `412 {"error":"precondition_failed","detail":"..."}`, Datei auf Platte
  nachweislich unveraendert
- **Output:** jeder erfolgreiche `PUT` auf `/api/trips/{id}` oder
  `/api/trips/{id}/weather-config` liefert den NEUEN `ETag` im Antwort-Header
- **Side effects:** keine — die Sperre ist prozessintern (S1), es entsteht keine
  zusaetzliche Datei, kein zusaetzlicher Persistenz-Zustand

## Warum ein Inhalts-Fingerabdruck statt eines Versionsfelds

Ausfuehrliche Begruendung: `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md`.
Kurzfassung: Der Python-Kern schreibt dieselben `briefings/<id>.json`-Dateien
(`src/app/loader.py:1581-1648` `save_trip`) und bewahrt unbekannte Felder
ausdruecklich (`_deep_merge_preserve_unknown`, `loader.py:124-137`). Ein
`version`- oder `updated_at`-Feld, das nur Go pflegt, ueberlebt einen
Python-Schreibvorgang (Telegram-/SMS-Kommandos, `skip_next`-Verbrauch,
Migrationsskripte) unveraendert — genau der Fall, den diese Scheibe schliessen
soll, bliebe offen und unsichtbar. Der Inhalts-Fingerabdruck aus S1 liest die
tatsaechlichen Bytes auf Platte und erkennt jede Aenderung, unabhaengig davon,
welcher Prozess sie geschrieben hat. Folge: keine Schema-Aenderung, keine
Migration, keine Python-Aenderung — jede Bestandsdatei hat ab dem ersten `GET`
automatisch einen gueltigen Fingerabdruck.

## Zeilenrahmen

Urspruenglich 600 Zeilen (Regelrahmen je Scheibe). **Zweimal vom PO angehoben,
zuletzt auf 1100** — beide Male, weil der Ueberhang praktisch vollstaendig in den
Nachweisen steckt und kein Testfall gestrichen werden sollte.

| Bereich | Schaetzung | Ist |
|---|---|---|
| Produktivcode (`trip.go`, `weather_config.go`, `etag.go` neu) | ~220 | 210 |
| Tests (`trip_etag_ifmatch_test.go`, `weather_config_etag_ifmatch_test.go`) | ~290 | 702 |
| `openapi.yaml` | ~80 | 136 |
| **Summe** | **~590** | **1047** |

Der Produktivcode traf die Schaetzung; die Tests haben sie um das Zweieinhalbfache
gerissen. Grund: Jeder Nachweis prueft die **Datei auf Platte** vorher/nachher statt
nur den Statuscode — bei einer Fehlerklasse, an der #1389/#1390/#1393 sechs
Pruefrunden lang gescheitert sind, ist genau das der Punkt. Von 950 auf 1100 stieg
der Rahmen ein zweites Mal durch die Nachbesserung aus der Adversary-Runde
(Sperre im Loeschpfad, 10 Zeilen Produktivcode + 2 Tests).

## Testplan

Alle Tests in `internal/handler/`, echte Dateien via `t.TempDir()`-gestuetztem
`Store` (Bestandsmuster aus `trip_write_test.go`), kein Mock. Namen nach
Verhalten, nicht nach Issue-Nummer.

### `internal/handler/trip_etag_ifmatch_test.go`

| Test | Deckt |
|---|---|
| `TestTripHandler_ReturnsETag` | AC-1 |
| `TestTripHandler_ETagStableAcrossReads` | AC-2 |
| `TestUpdateTripHandler_NoIfMatch_Accepted` | AC-3, AC-14 |
| `TestUpdateTripHandler_MatchingIfMatch_Accepted` | AC-4 |
| `TestUpdateTripHandler_StaleIfMatch_Returns412_FileUnchanged` | AC-5 |
| `TestUpdateTripHandler_ReturnsNewETag_SecondPutSucceeds` | AC-6 |
| `TestUpdateTripHandler_ConcurrentWrites_SecondWithStaleETagLoses` | AC-7 |
| `TestUpdateTripHandler_TenantIsolation_ETagNotSharedAcrossUsers` | AC-9 |
| `TestUpdateTripHandler_IfMatchWildcard_Accepted` | AC-10 |
| `TestUpdateTripHandler_MultipleIfMatchValues_AnyMatchAccepted` | AC-14 |
| `TestCreateTripHandler_NoETagInResponse` | AC-12 |
| `TestUpdateTripHandler_412Response_NoETagHeader_GermanDetail` | AC-13 |
| `TestUpdateTripStateHandler_NoIfMatchCheck_LockOnly` | AC-15 |
| `TestConfirmWaypointHandler_NoIfMatchCheck_LockOnly` | AC-15 |
| `TestSetETagHeader_OmitsHeaderWhenFingerprintUnavailable` | AC-16 — **eingeschraenkt, siehe unten** |
| `TestDeleteTripHandler_WaitsForBriefingLock` | Sperre im Loeschpfad (Nachtrag) |
| `TestDeleteAndPutConcurrently_NoResurrectedOrHalfWrittenTrip` | Invariante zum Loeschpfad (Nachtrag) |
| `TestExistingTripWriteTests_StillGreen` (Regressionsvermerk, kein neuer Testkoerper — siehe „Was nicht kaputtgehen darf") | AC-11 |

**AC-16 ist bewusst nur auf Helfer-Ebene geprueft.** Der urspruenglich geplante
Handler-Test (`..._FingerprintReadFailsAfterSave_...`) existiert NICHT, weil seine
Vorbedingung nachweislich nicht herstellbar ist: Das Lesen VOR dem Speichern, das
`LoadTrip` und das Lesen NACH dem Speichern greifen auf **denselben Pfad mit
denselben Rechten** zu. Gemessen: bei Dateirechten `0000` scheitern
`BriefingFingerprint` und `LoadTrip` mit demselben `permission denied` — der
Handler ist dann bei `500` bzw. `404` raus, lange bevor gespeichert wird. Jede
Bedingung, die das Nachlesen scheitern liesse, laesst also schon das Vorher-Lesen
scheitern; `SaveTrip` selbst stellt den lesbaren Zustand her (tmp + `chmod 0644`
+ `rename`), und ein Dazwischenfunken Dritter schliesst die Sperre aus.

Der Fail-soft-Zweig bleibt trotzdem im Code — als Verteidigung gegen kuenftige
Umbauten, nicht gegen einen heute erreichbaren Zustand. Die Konsequenz ist
ehrlich zu benennen: Der Adversary hat belegt, dass **alle Tests gruen bleiben**,
wenn man diesen Zweig durch ein `500` ersetzt. Ein Test kann Verhalten pruefen,
aber nicht die Abwesenheit kuenftigen Codes, dessen Ausloeser nicht herstellbar
ist — dafuer ist Review das Werkzeug, nicht eine Attrappe (projektweit verboten).

### Nachtrag: Sperre im Loeschpfad

Aus der Adversary-Runde: `DeleteTripHandler` veraenderte dieselbe Datei wie alle
Schreibpfade, ohne die Sperre zu nehmen. Damit war die Zusage „jeder HTTP-Pfad,
der `briefings/<id>.json` veraendert, nimmt die Sperre" schlicht falsch, und es
blieb genau die Luecke offen, um die es in #1395 geht: Ein `DELETE` mitten in
einem laufenden `PUT` laesst die geloeschte Tour wieder auferstehen (der `PUT`
schreibt sie aus seinem bereits geladenen Stand zurueck). Mit Sperre sind nur die
beiden unbedenklichen Reihenfolgen moeglich. `DeleteTripHandler` hat weiterhin
**keine** `If-Match`-Pruefung — analog zu den PATCH-Pfaden (AC-15).

Von den beiden Tests dazu ist der **erste** der Beweis (er haelt die Sperre selbst
und ist deterministisch), der **zweite** eine Invariante ueber 25 Durchlaeufe: Er
war schon vor dem Fix gruen, weil das Zeitfenster im Mikrosekundenbereich liegt —
das steht so im Testkommentar und ist ausdruecklich kein Beweis.

### `internal/handler/weather_config_etag_ifmatch_test.go`

| Test | Deckt |
|---|---|
| `TestGetTripWeatherConfigHandler_ReturnsETag` | AC-8 |
| `TestPutTripWeatherConfigHandler_NoIfMatch_Accepted` | AC-8 |
| `TestPutTripWeatherConfigHandler_StaleIfMatch_Returns412_FileUnchanged` | AC-8 |
| `TestPutTripWeatherConfigHandler_ReturnsNewETag` | AC-8 |

## Acceptance Criteria

- **AC-1:** Given eine gespeicherte Tour existiert / When `GET /api/trips/{id}` aufgerufen wird / Then traegt die Antwort einen `ETag`-Header mit dem Fingerabdruck des aktuellen Standes
  - Test: `TestTripHandler_ReturnsETag` — echter HTTP-Response-Header wird gelesen, nicht der Store-Rueckgabewert

- **AC-2:** Given eine Tour wurde seit dem letzten Lesen nicht veraendert / When zweimal hintereinander `GET /api/trips/{id}` aufgerufen wird / Then sind beide `ETag`-Werte identisch
  - Test: `TestTripHandler_ETagStableAcrossReads`

- **AC-3:** Given ein Client sendet KEINEN `If-Match`-Header / When er `PUT /api/trips/{id}` aufruft / Then wird der Schreibvorgang wie bisher angenommen und die Aenderung ist danach per `GET` sichtbar
  - Test: `TestUpdateTripHandler_NoIfMatch_Accepted`

- **AC-4:** Given ein Client sendet den zuletzt erhaltenen `ETag`-Wert als `If-Match` / When er `PUT /api/trips/{id}` aufruft / Then wird der Schreibvorgang angenommen
  - Test: `TestUpdateTripHandler_MatchingIfMatch_Accepted`

- **AC-5:** Given ein Client sendet einen `If-Match`-Wert, der nicht dem aktuellen Stand entspricht / When er `PUT /api/trips/{id}` aufruft / Then antwortet der Server mit `412 Precondition Failed` und die gespeicherte Datei ist nachweislich unveraendert geblieben
  - Test: `TestUpdateTripHandler_StaleIfMatch_Returns412_FileUnchanged` — prueft den Dateiinhalt NACH dem abgelehnten Aufruf gegen den Stand VOR dem Aufruf

- **AC-6:** Given ein erfolgreicher `PUT` liefert einen neuen `ETag` zurueck (auch wenn die Datei durch serverseitige Heilung minimal von der gesendeten Fassung abweicht) / When derselbe Client sofort einen zweiten `PUT` mit genau diesem neuen `ETag` als `If-Match` sendet / Then wird auch dieser zweite Schreibvorgang angenommen
  - Test: `TestUpdateTripHandler_ReturnsNewETag_SecondPutSucceeds`

- **AC-7:** Given zwei Clients haben denselben Ausgangsstand gelesen und beide moechten schreiben / When Client A zuerst erfolgreich schreibt und Client B danach mit dem inzwischen veralteten `If-Match`-Wert schreiben will / Then verliert Client B mit `412` statt Client A's Aenderung zu ueberschreiben
  - Test: `TestUpdateTripHandler_ConcurrentWrites_SecondWithStaleETagLoses`

- **AC-8:** Given dieselbe Vorbedingungs-Logik gilt fuer `/api/trips/{id}/weather-config` / When `GET` einen `ETag` liefert und `PUT` mit passendem, fehlendem oder veraltetem `If-Match` aufgerufen wird / Then verhaelt sich der Pfad analog zu AC-1/AC-3/AC-5/AC-6
  - Test: `TestGetTripWeatherConfigHandler_ReturnsETag`, `TestPutTripWeatherConfigHandler_NoIfMatch_Accepted`, `TestPutTripWeatherConfigHandler_StaleIfMatch_Returns412_FileUnchanged`, `TestPutTripWeatherConfigHandler_ReturnsNewETag`

- **AC-9:** Given zwei verschiedene Nutzer haben je eine eigene Tour mit derselben Trip-ID / When Nutzer A einen `ETag` fuer seine Tour erhaelt und diesen als `If-Match` gegen die Tour von Nutzer B sendet / Then greift die Pruefung nicht ueber die Mandantengrenze — Nutzer B's Schreibvorgang wird ausschliesslich gegen Nutzer B's eigenen Stand geprueft
  - Test: `TestUpdateTripHandler_TenantIsolation_ETagNotSharedAcrossUsers` — zwei `Store`-Instanzen mit unterschiedlicher `UserID`

- **AC-10:** Given eine Tour existiert / When ein Client `If-Match: *` sendet / Then wird der Schreibvorgang unabhaengig vom konkreten Fingerabdruck angenommen
  - Test: `TestUpdateTripHandler_IfMatchWildcard_Accepted`

- **AC-11:** Given alle bestehenden Trip-Schreibtests senden heute keinen `If-Match`-Header / When diese Scheibe implementiert ist / Then bleiben alle diese Tests unveraendert gruen (siehe „Was nicht kaputtgehen darf")
  - Test: bestehende Suiten laufen unveraendert; kein neuer Testkoerper noetig, wird im CI-Lauf der Scheibe mitgeprueft

- **AC-12:** Given ein Client legt eine neue Tour an / When `POST /api/trips` antwortet / Then traegt die Antwort KEINEN `ETag`-Header
  - Test: `TestCreateTripHandler_NoETagInResponse`

- **AC-13:** Given ein `PUT` wird wegen veraltetem `If-Match` abgelehnt / When die `412`-Antwort ausgewertet wird / Then enthaelt sie KEINEN `ETag`-Header und im Rumpf ein `detail`-Feld mit einer nutzerlesbaren, deutschen Fehlermeldung
  - Test: `TestUpdateTripHandler_412Response_NoETagHeader_GermanDetail`

- **AC-14:** Given ein Client sendet mehrere `If-Match`-Werte durch Komma getrennt / When mindestens einer davon dem aktuellen Stand entspricht / Then wird der Schreibvorgang angenommen
  - Test: `TestUpdateTripHandler_MultipleIfMatchValues_AnyMatchAccepted`

- **AC-15:** Given `PATCH /api/trips/{id}/state` und `PATCH /api/trips/{id}/waypoints/{waypointId}/confirm` nehmen dieselbe Sperre wie die PUT-Pfade / When ein Client dort einen `If-Match`-Header mitschickt / Then wird dieser ignoriert — die Anfrage wird unabhaengig vom Header-Wert angenommen, solange die Tour existiert
  - Test: `TestUpdateTripStateHandler_NoIfMatchCheck_LockOnly`, `TestConfirmWaypointHandler_NoIfMatchCheck_LockOnly`

- **AC-16:** Given ein `PUT` speichert erfolgreich, aber das anschliessende Lesen des neuen Fingerabdrucks schlaegt fehl / When die Antwort ausgeliefert wird / Then ist der Status `200` (nicht `500`) und der `ETag`-Header fehlt schlicht — ein geglueckter Schreibvorgang wird nicht nachtraeglich zum Fehler
  - Test: `TestUpdateTripHandler_FingerprintReadFailsAfterSave_Returns200WithoutETag`

## Was nicht kaputtgehen darf

Alle folgenden Bestandstests senden heute KEINEN `If-Match`-Header und muessen
unveraendert gruen bleiben (schaerfster Beleg fuer die Rollout-Politik „ohne
Header = angenommen"):

- `internal/handler/trip_test.go`
- `internal/handler/trip_write_test.go` (11 Tests)
- `internal/handler/weather_config_test.go`
- `internal/handler/weather_config_701_test.go`
- `internal/handler/weather_config_1151_test.go`
- `internal/handler/weather_config_1257_test.go`
- `internal/handler/trip_official_warnings_test.go`
- `internal/handler/trip_alert_channels_test.go`
- `internal/handler/trip_corridors_write_test.go`
- `internal/handler/trip_stage_id_test.go`
- `internal/handler/trip_day_window_write_seam_test.go`
- `internal/handler/bug_601_roundtrip_test.go`
- `internal/handler/config_merge_structure_test.go`
- `internal/router/briefing_subscription_test.go`

## Known Limitations

- Kein Umgehungsweg-Gap: `PUT /api/briefings/{id}?kind=route` reicht per
  `ServeHTTP` direkt an `UpdateTripHandler` durch und ist damit automatisch mit
  abgesichert — der Merge-Zweig fuer `kind=vergleich` (Ortsvergleich) ist NICHT
  im Scope dieser Scheibe (S6).
- Der Python-Kern schreibt `briefings/<id>.json` weiterhin nicht atomar
  (`src/app/loader.py:1644` `open(path, "w")`); in einem theoretischen
  Zeitfenster kann Go dort einen Fingerabdruck einer halb geschriebenen Datei
  lesen. Bleibt offen — S1/S2 beheben nur die Go-Seite.
- Kein Frontend: `frontend/` fuehrt in dieser Scheibe keinen `If-Match` und liest
  keinen `ETag` — folgt in S3 (ETag-Registry + Schreib-Warteschlange in `api.ts`).
- `PATCH`- und `DELETE`-Endpunkte pruefen `If-Match` nicht — siehe AC-15 und
  Begruendung im Abschnitt „Implementation Details".
- AC-16 ist nur auf Helfer-Ebene abgesichert; die Vorbedingung ist nachweislich
  nicht herstellbar. Ausfuehrlich im Testplan.
- **Nebenbefund, in dieser Scheibe behoben (Issue #1396):** Alle Handler
  ueberschrieben mit `s = s.WithUser(...)` eine von der Closure GETEILTE
  Variable — `net/http` ruft denselben Handler-Wert je Anfrage aus einer eigenen
  Goroutine auf. Zwei gleichzeitige Anfragen konnten sich damit die `UserID`
  gegenseitig ueberschreiben (Datenwettlauf mit Cross-User-Risiko, vom
  Wettlauf-Detektor an `trip.go` gemeldet). In `trip.go` (alle 7 Handler) und
  fuer die beiden Trip-Handler in `weather_config.go` auf `:=` umgestellt.
  **26 weitere Stellen in `internal/handler/*.go` bleiben offen** — eigenes
  Ticket #1396 (`bug`, `priority:critical`).
- **In dieser Scheibe behoben (Adversary-Befund F002, HIGH):** Zwei Handler
  schrieben ein geladenes Trip-Objekt zurueck, ohne `ID` auf den URL-Parameter zu
  setzen — `PutTripWeatherConfigHandler` und `ConfirmWaypointHandler`. Da
  `store.SaveTrip` nach `briefings/<trip.ID>.json` schreibt, landete der
  Schreibvorgang bei einer Datei mit abweichender innerer Kennung in einer
  **fremden Tour**: `PUT /api/trips/aussen/weather-config` antwortete `200`,
  `aussen.json` blieb byte-identisch, und `briefings/innen-anders.json` wurde mit
  dem kompletten Datensatz von `aussen` ueberschrieben.

  Warum das kein Nebenbefund ist, obwohl der Schreibpfad-Fehler aelter ist als
  S2: **Vor S2 gab `PUT` keinen `ETag` zurueck.** Der Client konnte also gar
  nicht auf einen falschen Vertrauensanker hereinfallen. Mit S2 bekommt er einen
  formal korrekten Stempel (er gehoert ja zur unveraenderten Datei) und haelt ihn
  fuer den Beleg eines geglueckten Speicherns. Diese Scheibe verschaerft die
  Fehlerklasse also, statt sie zu schliessen — und AC-8 verspricht ausdruecklich,
  dass der `/weather-config`-Pfad die **angefragte** Ressource veraendert.

  Lehre fuer den Testzuschnitt, gemessen: Im roten Lauf schlug die Pruefung
  „zurueckgegebener `ETag` passt zum Fingerabdruck der angefragten Datei"
  **nicht** an — der Stempel war korrekt, weil die Datei unveraendert blieb. Ein
  Test, der nur den Stempel prueft, laesst diesen Schaden durch. Gefangen wird er
  erst von „die Aenderung ist bei der angefragten Tour angekommen" UND „es wurde
  keine fremde Datei angelegt".

  Ungeprueft geblieben: Dasselbe Muster steht in
  `GetLocationWeatherConfigHandler`/`PutLocationWeatherConfigHandler`
  (`loc.ID` wird vor `SaveLocation` nicht gesetzt). Orte liegen auf einer anderen
  Datei-Ebene und waren ausserhalb des Scheibenschnitts — zu pruefen, sobald Orte
  an der Reihe sind.

## Offene Punkte

- **Warnung fuer S6 (Ortsvergleich):** `store.LockBriefing` liefert eine
  `sync.Mutex`-basierte Sperre — sie ist NICHT wiedereintrittsfaehig. Wer in S6
  eine Sperre am Anfang von `UpdateBriefingHandler`
  (`internal/handler/briefing_subscription.go:182`) nimmt, erzeugt fuer
  `kind=route` einen sicheren Selbst-Blockierer: dieser Handler reicht per
  `ServeHTTP` an `UpdateTripHandler` durch (`:190`), der dieselbe Sperre fuer
  dieselbe `<Nutzer, ID>` erneut nimmt. Die Sperre gehoert dort ausschliesslich
  in den `kind=vergleich`-Zweig, nicht an den Handler-Anfang.
- `docs/specs/modules/go_trip_write.md` behauptet an Zeile 34 („Out of Scope:
  Conflict Detection (kein ETag/If-Match)") und Zeile 188 („Known Limitations:
  Keine Conflict Detection (kein ETag)") einen Ist-Stand, der durch diese
  Scheibe FALSCH wird. Diese Spec wird NICHT im Zuge von S2 nachgezogen —
  gehoert in Phase 7 (Dokumentations-Pflege nach Implementierung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0036
- **Rationale:** Die Wahl „Inhalts-Fingerabdruck statt Versionsfeld" ist
  schwer umkehrbar (beruehrt den gemeinsamen Datei-Vertrag mit dem Python-Kern)
  und betrifft mehrere Systemteile (Go-API, Python-Kern, kuenftig Frontend in
  S3) — siehe `docs/adr/0036-nebenlaeufigkeitsschutz-inhalts-fingerabdruck.md`.

## Changelog

- 2026-07-27: Initial spec erstellt — Issue #1395 Scheibe S2, aufbauend auf S1 (Commit d3bb4b8f)
