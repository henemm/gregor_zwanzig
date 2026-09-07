# Kontext: #2140 Scheibe 2 — Entitäts-IDs gegen Pfad-Traversal

Workflow: `fix-2140-entitaets-id-pfadsperre` · Issue: #2140 · Vorgänger: Scheibe 1 (Nutzer-Kennungen, live seit `37559f9f`)

## Analysis

### Type

Bug (Sicherheit, Schwere Blocker). Fortsetzung von #2140; Scheibe 1 deckte ausschließlich **Nutzer**-Kennungen ab.

### Befund

Client-gesetzte **Entitäts**-IDs (Trip, Ort, Ortsvergleichs-Preset) fließen ungeprüft in Dateipfade.
Zwei Einlasswege: ID im **Request-Body** (`POST /api/trips`, `POST /api/locations`) und ID im
**URL-Pfad-Parameter** (`PUT`/`PATCH`/`DELETE`/`GET` auf `/{id}`). Router ist `chi` mit
Ein-Segment-Mustern (`internal/router/router.go:135-192`); ein rohes `..`-Segment matcht dort als
gewöhnlicher Wert.

Wirkung: `POST /api/trips` mit `{"id":"../../bob/user"}` überschreibt die `user.json` eines fremden
Kontos — das Ziel ist danach nicht mehr anmeldbar. Lesend und löschend gilt derselbe Weg.

Eine Entitäts-ID-Validierung existiert **nirgends** — weder in Go noch in Python. `validateTrip`
(`internal/handler/trip.go:89-91`) und `validateLocation` (`internal/handler/location.go:45-56`)
prüfen ausschließlich auf Leerstring.

### Warum die im Issue vorgeschlagene ASCII-Whitelist ausscheidet

Das Issue verlangt ein Pendant zu `VALID_USER_ID_RE` (`^[a-zA-Z0-9_-]+$`). Für Nutzer-Kennungen war
das korrekt, für Entitäts-IDs bricht es Produktivdaten. Gemessen in `/var/lib/gregor/users/henning/locations/`:

```
hochfügen.json · mühlbach.json · pollença.json
berstation-hochfügen.json · serfaus-schöngamp-berg.json · übergangsjoch-zillertal-arena.json
```

Diese Orte sind aktiv (`alert_state/zillertal:hochfügen.json` u. a.). Der Weg zu ihnen ist lückenlos
belegt: `frontend/src/routes/locations/+page.svelte:49,71` ruft Bearbeiten und Löschen mit der
**Original-ID vom Datenträger** auf, `internal/handler/location.go:123,178,234,256` reicht sie direkt
an `LoadLocation`/`SaveLocation`/`DeleteLocation` durch. Eine ASCII-Whitelist im Store-Join würde
diese sechs Orte unerreichbar machen. Zusätzlich erhält die Slug-Bildung im Frontend
(`LocationForm.svelte:22`, `/[^a-z0-9äöüß]+/g`) Umlaute **absichtlich** — jeder neue Ort mit
deutschem Namen bekäme eine ID, die das eigene Backend mit 400 abwiese.

Für Trip-IDs gilt die Whitelist zwar praktisch (Bestand ist ASCII), aber **nicht** aus dem Grund
„das Frontend vergibt Hex": `validateTrip` erzwingt serverseitig gar kein Muster, und ein zweiter
Frontend-Erzeuger (`frontend/src/routes/gpx-upload/+page.svelte:77`) leitet die ID aus dem Namen ab.
Die ASCII-Reinheit ist Konvention, keine Invariante — deshalb wäre ein zweites, strengeres Muster
nur für Trips eine Sonderregel ohne Fundament.

### Der wirksame Ansatz

Der Ausbruch entsteht bei Entitäts-IDs **ausschließlich über einen Pfad-Trenner im ID-Wert**. Alle
betroffenen Store-Methoden joinen `id+".json"` (nie einen rohen Verzeichnis-Join wie `UserDir` in
Scheibe 1), verifiziert über alle `filepath.Join`-Stellen in `internal/store/`. Ein blankes `..`
wird dadurch zu `"...json"` — schräg, aber harmlos.

Also: **Pfadsegment-Prüfung statt Zeichen-Whitelist.** `ValidEntityID` verlangt: nicht leer · kein
`/` · kein `\` · kein NUL-Byte · nicht `.` und nicht `..` · kein führender Punkt. Unicode-Buchstaben
bleiben zulässig. Geprüft und ohne Bypass: Unicode-Homoglyphen (U+FF0F, U+2215 sind auf Linux keine
Trenner), `filepath.Clean` (ohne `/` bleibt alles ein Segment), Windows-Semantik (`\` trotzdem
gesperrt). Nicht empirisch getestet, nur aus Go-Stdlib-Semantik hergeleitet: überlange
UTF-8-Sequenzen dekodieren nicht zu ASCII `/`.

Sitz der Prüfung wie in Scheibe 1: **im Store an jedem Pfad-Join** (Verteidigung in der Tiefe, fängt
künftige Aufrufer) **plus Pre-Check im Handler** für den sauberen Statuscode.

### Fehlerverhalten

**400 mit klarer Meldung**, nicht byte-identisch zu „existiert nicht". Scheibe 1 musste bei den
öffentlichen Auth-Routen Konto-Enumeration verhindern; hier sind es authentifizierte, user-scoped
Routen auf **eigene** Daten — es gibt nichts zu enumerieren. Passt zum bestehenden
`validation_error`-Muster (`trip.go:163-171`, `location.go:74-82`).

### Zweiter Prozess: der Python-Kern hat dieselbe Lücke

Weder Issue noch erste Analyse deckten das ab. Der Python-Kern baut dieselben Pfade ohne Guard:

| Stelle | Entität | Richtung | von außen erreichbar über |
|---|---|---|---|
| `src/services/preview_service.py:67-68` | Trip-ID | lesend | `GET /api/preview/{trip_id}/email\|sms\|telegram` (`api/routers/preview.py:30,56,129`) |
| `api/routers/validator.py:52` | Trip-ID | lesend | `POST /api/trips/{trip_id}/alert-preview` (`api/routers/validator.py:332`) |
| `src/app/loader.py:1332`, `:1391` | Orts-ID | schreibend/löschend | kein Python-Endpoint gefunden (CLI/Go-Pfad) |
| `src/app/loader.py:1748`, `:1802` | Trip-ID | schreibend/löschend | interne Kommando-/Scheduler-Pfade |
| `src/services/alert_state.py:58-59` | Entitäts-ID | schreibend/lesend/löschend | Aufrufketten nicht vollständig zurückverfolgt |

Der Go-Proxy spliced die ID **roh** in den Python-URL-Pfad (`internal/handler/proxy.go:169,261,304`,
`preview_proxy.go:38,76`). Die Nutzer-Kennung wird dabei korrekt aus der Session gesetzt
(`appendUserID`, `proxy.go:147-159`) — die Entitäts-ID nicht geprüft.

Offen und **empirisch zu messen statt zu vermuten**: ob ein URL-kodierter Trenner (`%2F`) durch
chi + Go-Proxy + Starlette bis in den Pfadbau durchkommt. Das gehört in die RED-Phase, nicht in eine
Annahme.

Python hat bereits `VALID_USER_ID_RE` (`src/app/loader.py:1150`) für Nutzer-Kennungen und einen
Paritätstest gegen die Go-Seite (`tests/unit/test_user_id_pattern_parity.py`) — die Bauart für ein
Entitäts-Pendant liegt vor.

Nicht betroffen: GPX-Upload — der Client-Dateiname wird über `Path(filename).name` auf den Basename
reduziert (`src/services/gpx_processing.py:66-67`, Fix zu #1352). Alarm-Zustandsschlüssel mit
Doppelpunkt (`zillertal:hochfügen`) laufen nicht über die Go-Store-Pfade.

### Affected Files (with changes)

| File | Change Type | Description |
|------|-------------|-------------|
| `internal/store/pathsafe.go` | MODIFY | `ValidEntityID`, `ErrInvalidEntityID` neben bestehendem `ValidUserID` |
| `internal/store/trip.go` | MODIFY | Guard in `SaveTrip`, `LoadTrip`, `DeleteTrip` |
| `internal/store/location.go` | MODIFY | Guard in `SaveLocation`, `LoadLocation`, `DeleteLocation` |
| `internal/store/compare_preset.go` | MODIFY | Guard in `Save`/`Load`/`DeleteComparePreset` |
| `internal/store/briefing_fingerprint.go` | MODIFY | Guard in `BriefingFingerprint` (Trip und Preset) |
| `internal/handler/trip.go` | MODIFY | Pre-Check in 5 Handlern + `validateTrip` |
| `internal/handler/location.go` | MODIFY | Pre-Check in 4 Handlern + `validateLocation` |
| `internal/handler/compare_preset.go` | MODIFY | Pre-Check in 4 Handlern (via `bailIf`) |
| `internal/handler/weather_config.go` | MODIFY | Pre-Check in 4 Handlern |
| `internal/handler/briefing_subscription.go` | MODIFY | Pre-Check in 2 Handlern (via `bailIf`) |
| `src/app/loader.py` | MODIFY | `VALID_ENTITY_ID_RE` + Guard in Orts-/Trip-Pfadbau |
| `src/services/preview_service.py` | MODIFY | Guard vor Trip-Pfadbau |
| `api/routers/validator.py` | MODIFY | Guard vor Trip-Pfadbau |
| `internal/store/entity_id_test.go` | CREATE | Guard-Einheitstests inkl. Unicode-Positivkontrolle |
| `internal/handler/entity_traversal_test.go` | CREATE | Zwei-Nutzer-Traversal-Tests über die Routen |
| `tests/unit/test_entity_id_pattern_parity.py` | CREATE | Go/Python-Musterparität |

### Scope Assessment

- Dateien: 13 MODIFY, 3 CREATE
- Geschätztes LoC-Delta Produktivcode: **~175** (Go ~135, Python ~40) — Limit 250
- Risiko: MEDIUM (Sicherheitsfix an breiter Fläche; Bestandsdaten nachweislich unberührt)

### Zuschnitt-Entscheidungen

1. **Compare-Preset-IDs sind mit drin**, obwohl der Auftrag „Trip- und Orts-IDs" lautet: sie liegen
   im selben Verzeichnis, teilen `BriefingFingerprint` und `briefingsDir`, und `DeleteTrip` prüft
   bereits Presets mit. Sie auszulassen hinterließe eine bekannte offene Lücke derselben Klasse.
   Das ist Sicherheitsarbeit, keine Ortsvergleichs-Produktarbeit — die Zurückstellung von
   Ortsvergleichs-Themen greift hier nicht.
2. **Der Python-Kern ist mit drin.** Eine Sperre, die nur einen von zwei Prozessen deckt, ist die
   Art halber Schutz, den später jemand für vollständig hält. Dieselbe Zusicherung, dasselbe
   Muster, Paritätstest als Vorlage vorhanden.
3. **Kein Split nach Layer** (Store vs. Handler) — das erzeugte einen Zwischenstand mit sicherem
   Store, aber 500 statt 400. Falls die 250-Grenze real anschlägt, wird nach **Entität** geschnitten.

### Risiko: was könnte brechen

- Bestandsorte mit Umlaut: laufen durch (kein Trenner, kein führender Punkt) — **der** Grund für die
  Segment- statt Whitelist-Prüfung. Gehört als Positivkontrolle in die Tests.
- Migrationen `migrate_1257.go:39`, `migrate_1258.go:85,124` rekonstruieren IDs aus dem
  Verzeichnislisting — reine ASCII-Hex, unkritisch. Restrisiko: ein pathologischer Dateiname wie
  `..json` (→ ID `.`) würde übersprungen statt migriert. Kein solcher Name im Bestand.
- Vollscans (`LoadTrips`, `LoadLocations`, `LoadComparePresets`) rekonstruieren keine IDs und rufen
  den Guard nicht auf — kein Risiko, keine Deckung nötig.
- Symlinks im Datenverzeichnis: außerhalb dieser Klasse, durch ID-Validierung nicht schließbar.

### Open Questions

- [ ] Kommt `%2F` durch chi + Go-Proxy + Starlette bis in den Python-Pfadbau? → in RED messen,
      nicht annehmen.
