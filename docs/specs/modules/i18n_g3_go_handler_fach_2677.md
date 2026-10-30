---
entity_id: i18n_g3_go_handler_fach_2677
type: module
created: 2026-10-30
updated: 2026-10-30
status: approved
version: "1.0"
tags: [i18n, epic-2644, issue-2677, go, model-haiku]
---

# i18n G3: Go-Handler Fachlogik, Middleware und Resolver auf WriteError mit Katalog umstellen

**Issue:** #2677 · **Epic:** #2644 · **Modell:** Haiku · **Konventionen:** docs/features/epic-i18n-de-en-konventionen.md Abschnitte 2, 5

## Approval

- [x] Approved (PO-Freigabe 2026-10-30)

## Purpose

Wer Trips, Ortsvergleiche, Orte, Briefings oder Wetterabfragen bearbeitet, sieht Fehlermeldungen der Go-API in seiner Sprache: der Stand-geändert-Hinweis beim Speichern, die Kontingent-Meldung („Du hast bereits 1 von 1 Trips …"), die Fehler der Orts-Auflösung und die Versand-Fehler der Go-Seite. Deutsche Texte bleiben wörtlich wie heute, englische kommen aus dem Katalog `fach`. Antworten des Python-Cores werden unverändert durchgereicht; deren Sprache stellt P11 (#2674) um.

## Source

- **File:** `internal/handler/{briefing_send,send_proxy,preview_proxy,briefing_subscription,briefing_history,briefing_preview,compare_preset,trip,location,location_resolve,quota,etag,schreibsperre,forecast,weather_config,metric_preset,group,proxy,premium_sms_link_code,telegram_connect,data_export}.go`, `internal/middleware/{auth,admin,ratelimit}.go`, `internal/resolver/{resolver,coords,komoot,googlemaps}.go`
- **Identifier:** `writeSendError`, `writeBriefingKindRequired`, `writeSaveError`, `writePreconditionFailed`, `quotaResource.detail`, `quotaAllows`, `lockBriefingOr503`, `ResolveLocationHandler`, `resolver.ResolveError`, `AuthMiddleware`, `RequireAdmin`, `IPRateLimiter`

> **Schicht-Hinweis:** Go-API (`internal/`). Kein Python-Code, kein Frontend-Code. `internal/store` und `internal/model` enthalten laut Messung (`grep` auf `"error":`/`errors.New`) keinen Nutzertext: Store-Fehler sind Sentinels (`ErrKindConflict`, `ErrBriefingLockTimeout`), die der Handler auf einen Code abbildet; es gibt dort nichts umzustellen.
>
> **Nicht umgestellt (Maschinen-Endpunkte, englische Klartexte ohne Nutzer):** alles unter `/api/internal/` (`premium_sms_connect.go`, `PostTelegramConnectHandler`), `/api/webhooks/` (`inbound_webhooks.go`, `telegram_webhook.go`), `localhost_guard.go`, `staging_*.go`, `scheduler_status.go`. Der Wächter (G5) meldet dort nichts, weil die Texte weder Umlaute noch deutsche Signalwörter tragen.
>
> **Querschnitts-Prüfpunkte:**
> - **Trip/Ortsvergleich-Teilung:** Fehlertexte, die beide Flächen betreffen, existieren **einmal**: `id_conflict`, `precondition_failed`, `quota_exceeded_*`, `busy`, `kind_required` liegen in `fach.fehler.*` bzw. `fehler.*`; Trip- und Compare-Handler rufen dieselben Schlüssel. Go hat keinen Bereich `allgemein`.
> - **Mandantentrennung:** Die `user_id` kommt weiter aus `middleware.UserIDFromContext`; die Sprache aus dem Kontext (G1). Zwei Nutzer (`de`/`en`) in einem Testlauf (AC-4).
> - **Kanäle:** Berührt sind nur Go-seitige Fehlerantworten. Versand-Ergebnisse der Kanäle E-Mail, Telegram, SMS und Premium-SMS entstehen im Python-Core (`send_outcomes.py`) und werden durchgereicht, nicht übersetzt.

### Affected Files

Zwei Teil-PRs (Entscheidung dieser Spec, weil die Zahl der Stellen die 250-LoC-Grenze überschreitet): **G3a** Handler Fachlogik, **G3b** Middleware, Resolver, Proxy und übrige Nutzer-Handler. G3a zuerst; Issue #2677 schließt nach G3b.

| Datei | CREATE/MODIFY | Zweck |
|---|---|---|
| **G3a** `internal/handler/briefing_send.go` | MODIFY | `writeSendError` und die vier `sendDetail…`-Konstanten entfallen; `WriteError` mit Variante (siehe Tabelle) |
| G3a `internal/handler/send_proxy.go`, `preview_proxy.go` | MODIFY | Go-eigene Fehler (`proxy_error`, `upstream unreachable` → `upstream_unreachable`) über `WriteError`; Python-Antwort bleibt Durchreichen |
| G3a `internal/handler/briefing_subscription.go` | MODIFY | `writeBriefingKindRequired` → `WriteError(…, "kind_required", nil)`; restliche direkte Fehlerstellen (`bailIf` ist seit G1 fertig) |
| G3a `internal/handler/briefing_history.go`, `briefing_preview.go` | MODIFY | Klartext-`http.Error` („unauthorized", „internal error") → `WriteError` |
| G3a `internal/handler/compare_preset.go` | MODIFY | ca. 13 Stellen; `writePreconditionFailed` über Katalog |
| G3a `internal/handler/trip.go` | MODIFY | ca. 29 Stellen, `writeSaveError`, die zwei `id_conflict`-Texte, `validateTrip`-Fehler als `detail` |
| G3a `internal/handler/location.go`, `location_resolve.go` | MODIFY | 24 + 4 Stellen; `conflict`, `location_in_use`, `bad_request` mit Variante `input` |
| G3a `internal/handler/quota.go` | MODIFY | `quotaResource.detail` entfällt; `quota_exceeded` mit `WriteErrorWith` (Zusatzfelder `resource`, `limit`, `current`) |
| G3a `internal/handler/etag.go` | MODIFY | `preconditionFailedDetail` entfällt; `writePreconditionFailed` behält den Rumpf-Drain und ruft `i18n.ErrorBody` |
| G3a `internal/handler/schreibsperre.go` | MODIFY | `busy` über Katalog, `Retry-After: 5` bleibt |
| G3a `internal/handler/forecast.go`, `weather_config.go`, `metric_preset.go`, `group.go` | MODIFY | 14 + 13 + 13 + 16 Stellen |
| G3a `internal/i18n/messages/{de,en}/fach.json` | MODIFY | Schlüssel `fach.fehler.*` (Tabelle unten) |
| G3a `internal/handler/testdata/wortgleich_de/*.txt` | CREATE | Golden: heutige deutsche Texte, **vor** der Umstellung aus dem Code kopiert |
| G3a `internal/handler/fach_fehler_zweisprachig_test.go` | CREATE | Tests zu AC-1 bis AC-4 |
| **G3b** `internal/handler/proxy.go` | MODIFY | 17 Go-eigene Fehlerstellen (`core_unavailable`, `proxy_error`, `upstream unreachable` → `upstream_unreachable`, `unauthorized`) |
| G3b `internal/handler/premium_sms_link_code.go`, `telegram_connect.go` (nur `GetTelegramLinkHandler`, `GetTelegramStatusHandler`), `data_export.go` | MODIFY | Nutzer-nahe Klartext-`http.Error` → `WriteError` (Übersetzung der Klartexte in Codes siehe unten) |
| G3b `internal/middleware/auth.go`, `admin.go`, `ratelimit.go` | MODIFY | privater Helfer `writeError(w, r, status, code)` über `i18n.ErrorBody(i18n.FromRequest(r, nil), code, nil)`; `RequireAdmin` und `IPRateLimiter` laufen nach der Sprach-Middleware und nutzen `FromContext`; `status_token.go` (Betriebs-Log) bleibt |
| G3b `internal/resolver/resolver.go`, `coords.go`, `komoot.go`, `googlemaps.go` | MODIFY | `ResolveError` bekommt `Key string` und `Args i18n.Args` (`json:"-"`); `Message` bleibt als deutscher Text erhalten (`i18n.T(i18n.De, Key, Args)`) |
| G3b `internal/resolver/testdata/meldungen_de.json` | CREATE | Golden aller 21 deutschen Resolver-Meldungen, vor der Umstellung erzeugt |
| G3b `internal/resolver/meldungen_zweisprachig_test.go` | CREATE | Tests zu AC-5 |
| G3b `internal/i18n/messages/{de,en}/fach.json` | MODIFY | `fach.resolver.*` (21 Schlüssel) |
| G3b `docs/reference/api_contract.md`, `docs/reference/i18n_glossar.md` | MODIFY | Fehlertabellen der Abschnitte 10, 10.1, 11, 13, 15.5, 16 auf neue Codes; Glossar-Zeile `Tarif` → `plan` |
| G3b `internal/middleware/sprache_zwei_nutzer_test.go` | MODIFY | Fälle zu AC-6 (Datei kommt aus G1) |
| beide PRs: bestehende Go-Tests | MODIFY | Tests mit Alt-Wort `upstream unreachable` (`preview_proxy_test.go`, `stage_weather_proxy_test.go`, `internal/router/sms_fidelity_preview_test.go`) erwarten `upstream_unreachable` |

## Estimated Scope

- **LoC:** G3a ca. +130/-330 geänderte Zeilen, G3b ca. +110/-60; Katalogdaten ca. 90 Schlüssel je Sprache zusätzlich. Je Teil-PR `loc_limit_override 500` einplanen (G3a liegt über 250).
- **Files:** G3a 20, G3b 14 (ohne Bestandstests)
- **Effort:** medium bis high

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| #2675 (G1) | Paket | `WriteError`, `WriteErrorWith`, `ErrorBody` (Varianten), `bailIf` mit `r` (Voraussetzung) |
| #2646 (S1) | Paket | Sprachfeld am Nutzer |
| #2674 (P11) | Paket | Python-Antworten (`detail` der Versand-Fehler) in Nutzersprache; Go reicht nur durch |
| #2679 (G5) | Paket | Wächter; Einträge der G3-Dateien werden entfernt |
| `internal/resolver`, `internal/middleware`, `internal/store` | Modul | Resolver und Middleware werden umgestellt, Store nicht |
| `docs/reference/i18n_glossar.md` | Doku | bindende Wortwahl und Verbotsliste |
| ADR-0104 | ADR | Sprache am Nutzer |

## Implementation Details

**Muster.** Siehe G1: `WriteError(w, r, status, code, args)`; Zusatzfelder über `WriteErrorWith`. Das Alt-Feld `error` bleibt gleich `code`, daher bleiben `store_error`, `not_found`, `bad_request` … für Clients identisch. Wo ein Code heute **mehrere deutsche Texte** trägt oder der Text nur in einem Teilfall gilt, steht `args["variante"]` (Suchkette aus G1: `fach.fehler.<code>_<variante>` zuerst).

**Beispiel-Umstellung** `internal/handler/trip.go:166-175` (`writeSaveError`), vorher:

```go
func writeSaveError(w http.ResponseWriter, err error) {
	if errors.Is(err, store.ErrKindConflict) {
		writeJSON(w, http.StatusConflict, map[string]string{
			"error":  "id_conflict",
			"detail": "Diese Kennung ist bereits durch einen Trip oder Ortsvergleich belegt — bitte anderen Namen wählen.",
		})
		return
	}
	writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "store_error"})
}
```

nachher (die Funktion bekommt `r`, alle Aufrufer ebenso):

```go
func writeSaveError(w http.ResponseWriter, r *http.Request, err error) {
	if errors.Is(err, store.ErrKindConflict) {
		WriteError(w, r, http.StatusConflict, "id_conflict", nil)
		return
	}
	WriteError(w, r, http.StatusInternalServerError, "store_error", nil)
}
```

Der zweite Text in `trip.go:249-252` („Ein Ortsvergleich trägt bereits diese Kennung …") wird `WriteError(w, r, http.StatusConflict, "id_conflict", i18n.Args{"variante": "vergleich"})`.

**Technische `detail`-Texte bleiben.** `validateTrip` und die Validatoren in `compare_preset.go`/`location.go` liefern englische Entwickler-Klartexte (`name required`, `hour_to must be >= hour_from`) und schreiben sie heute in `detail`. Sie werden nicht übersetzt (kein deutscher Altzustand): `WriteError(w, r, 400, "validation_error", i18n.Args{"detail": err.Error()})`. Die `message` ist dann der allgemeine Katalogtext „Die Eingabe ist ungültig.", das Alt-Feld `detail` trägt unverändert den technischen Text. Gleiches gilt für die englischen `detail`-Texte in `forecast.go` (z. B. `lat must be between -90 and 90`).

**Schlüssel `fach.fehler.*` (de | en; de bei vorhandenem Altzustand wörtlich, Quelle in Klammern).**

| Schlüssel | de | en |
|---|---|---|
| `fach.fehler.precondition_failed` | Der Stand wurde zwischenzeitlich an anderer Stelle geaendert. Bitte neu laden und die Aenderung erneut vornehmen. (etag.go:32) | The data was changed elsewhere in the meantime. Please reload and make your change again. |
| `fach.fehler.id_conflict` | Diese Kennung ist bereits durch einen Trip oder Ortsvergleich belegt — bitte anderen Namen wählen. (trip.go:170) | This ID is already used by a trip or location comparison. Please choose a different name. |
| `fach.fehler.id_conflict_vergleich` | Ein Ortsvergleich trägt bereits diese Kennung — bitte anderen Namen wählen. (trip.go:251) | A location comparison already uses this ID. Please choose a different name. |
| `fach.fehler.conflict` | Ort mit dieser ID existiert bereits (location.go:104) | A location with this ID already exists. |
| `fach.fehler.location_in_use` | Dieser Ort wird noch von mindestens einem Ortsvergleich verwendet. | This location is still used by at least one location comparison. |
| `fach.fehler.busy` | Datei gerade gesperrt, bitte erneut versuchen (schreibsperre.go:23) | The file is locked at the moment. Please try again. |
| `fach.fehler.quota_exceeded_trips` | Du hast bereits {current} von {limit} Trips in deinem Tarif. Archiviere oder lösche einen Trip, um einen neuen anzulegen. (quota.go:95) | You already have {current} of {limit} trips on your plan. Archive or delete a trip to create a new one. |
| `fach.fehler.quota_exceeded_compare_presets` | Du hast bereits {current} von {limit} Ortsvergleichen in deinem Tarif. Archiviere oder lösche einen Ortsvergleich, um einen neuen anzulegen. (quota.go:97) | You already have {current} of {limit} location comparisons on your plan. Archive or delete a location comparison to create a new one. |
| `fach.fehler.quota_exceeded_locations` | Du hast bereits {current} von {limit} Orten in deinem Tarif. Lösche einen Ort, um einen neuen anzulegen. (quota.go:99) | You already have {current} of {limit} locations on your plan. Delete a location to create a new one. |
| `fach.fehler.validation_error_kennung` | Ungültige Briefing-Kennung (briefing_send.go:31) | Invalid briefing ID |
| `fach.fehler.proxy_error_versand` | Versand konnte nicht gestartet werden — bitte später erneut versuchen (briefing_send.go:32) | Sending could not be started. Please try again later. |
| `fach.fehler.upstream_unreachable_versand` | Versanddienst nicht erreichbar — bitte später erneut versuchen (briefing_send.go:33) | The sending service is not reachable. Please try again later. |
| `fach.fehler.bad_request_input` | Feld 'input' fehlt (location_resolve.go:19) | The field 'input' is missing. |
| `fach.fehler.proxy_error` | Die Anfrage konnte nicht an den Dienst weitergeleitet werden. | The request could not be forwarded to the service. |
| `fach.fehler.upstream_unreachable` | Der Dienst ist nicht erreichbar. | The service is not reachable. |
| `fach.fehler.core_unavailable` | Der Hintergrunddienst ist gerade nicht erreichbar. | The backend service is currently not reachable. |
| `fach.fehler.name_required` | Der Name fehlt. | The name is required. |
| `fach.fehler.name_exists` | Dieser Name ist bereits vergeben. | This name is already in use. |
| `fach.fehler.invalid_params` | Die Parameter sind ungültig. | The parameters are invalid. |
| `fach.fehler.budget_exceeded` | Das Tageskontingent für Wetterabfragen ist aufgebraucht. | The daily quota for forecast requests is used up. |
| `fach.fehler.provider_error` | Der Wetteranbieter ist nicht erreichbar. | The weather provider is not reachable. |
| `fach.fehler.unknown_format` | Das Format wurde nicht erkannt. | The format was not recognized. |
| `fach.fehler.unsupported_url` | Diese Adresse wird nicht unterstützt. | This address is not supported. |
| `fach.fehler.resolve_failed` | Die Auflösung ist fehlgeschlagen. | The lookup failed. |

Der Quelltext in Klammern gehört nicht in den Katalogwert, er nennt nur die Fundstelle. `kind_required` und `validation_error` (ohne Variante) liegen seit G1 in `fehler.json`; `Form A` des Handversands (`{"detail","code"}`) bleibt erhalten, weil `ErrorBody` `code` und `detail` liefert. Die vier Versand-Aufrufe in `briefing_send.go`: `kind_required` → `WriteError(…, 400, "kind_required", nil)`; ungültige Kennung → `WriteError(…, 400, "validation_error", Args{"variante":"kennung"})`; `proxy_error` und `upstream_unreachable` mit Variante `versand`.

**Quota mit Zusatzfeldern** (`quota.go:175-181`), nachher:

```go
WriteErrorWith(w, r, http.StatusConflict, "quota_exceeded",
	i18n.Args{"variante": string(res), "current": current, "limit": limit},
	map[string]any{"resource": string(res), "limit": limit, "current": current})
```

`string(res)` ist `trips`, `compare_presets` oder `locations` und passt zu den drei Schlüsseln. Der Schlüssel ohne Variante `fach.fehler.quota_exceeded` wird **nicht** angelegt (jeder Aufruf trägt eine Variante).

**Klartext-`http.Error` in Nutzer-Handlern** werden `WriteError` mit diesen Codes (ändert den Content-Type von Text auf JSON): `unauthorized` → `unauthorized`; `internal error` → `internal_error`; `save failed`, `load failed`, `lookup failed`, `list users failed` → `store_error`; `user not found` → `not_found`; `bad request` → `bad_request`; `token store unavailable`, `TELEGRAM_BOT_USERNAME not configured` → `service_unavailable`. Betrifft `briefing_history.go:43,57`, `trip.go:662,699`, `premium_sms_link_code.go`, `telegram_connect.go:196-250` (Nutzer-Teil).

**Resolver (G3b).** Jede `ResolveError{Code, Message: "…"}` wird `newResolveError(code, key)`; `Message` füllt der Konstruktor mit `i18n.T(i18n.De, key, nil)`, `Key` hält den Schlüssel. `ResolveLocationHandler` (Zeile 41-45) schreibt:

```go
body := i18n.ErrorBody(i18n.FromContext(r.Context()), resolveErr.Code, nil)
body["message"] = i18n.T(i18n.FromContext(r.Context()), resolveErr.Key, resolveErr.Args)
writeJSON(w, 422, body)
```

Die 422-Antwort behält damit `code` und `message` (bisher Struct-Felder `code`/`message`) und gewinnt die Alt-Felder. Schlüssel `fach.resolver.<name>`; der deutsche Text wird **wörtlich** aus der Quellzeile in das Golden `meldungen_de.json` und in `de/fach.json` kopiert (zuerst Golden, dann Umstellung). Maßgeblich für die Vollständigkeit ist `grep -n "Message:" internal/resolver/*.go` vor Beginn:

| Schlüssel | Quelle | en |
|---|---|---|
| `fach.resolver.format` | resolver.go:60 | The format was not recognized. Please enter a Komoot highlight URL, a Google Maps link or coordinates. |
| `fach.resolver.maps_aufloesen` | googlemaps.go:23 | The Google Maps link could not be resolved. |
| `fach.resolver.komoot_sammlung` | komoot.go:38 | Komoot routes and collections are not supported. Please use a Komoot highlight link. |
| `fach.resolver.komoot_url` | komoot.go:46 | Komoot URL not recognized. Please use a Komoot highlight link. |
| `fach.resolver.komoot_anfrage` | komoot.go:54 | The Komoot request could not be created. |
| `fach.resolver.komoot_api` | komoot.go:62 | Komoot API not reachable. |
| `fach.resolver.komoot_antwort` | komoot.go:75 | The Komoot response could not be read. |
| `fach.resolver.komoot_ohne_koordinaten` | komoot.go:91 | The Komoot highlight contains no coordinates. |
| `fach.resolver.decimal_unbekannt` | coords.go:22 | Could not recognize decimal coordinates. |
| `fach.resolver.decimal_parse` | coords.go:27 | Decimal coordinates could not be parsed. |
| `fach.resolver.bereich` | coords.go:32 | Coordinates are outside the valid range (lat ∈ [-90,90], lon ∈ [-180,180]). |
| `fach.resolver.dms_unbekannt` | coords.go:45 | DMS format not recognized. |
| `fach.resolver.dms_bereich` | coords.go:68 | DMS coordinates are outside the valid range. |
| `fach.resolver.utm_unbekannt` | coords.go:80 | UTM format not recognized. |
| `fach.resolver.utm_band` | coords.go:89 | Invalid UTM band. |
| `fach.resolver.utm_easting` | coords.go:93 | Easting could not be parsed. |
| `fach.resolver.utm_northing` | coords.go:97 | Northing could not be parsed. |
| `fach.resolver.utm_konvertierung` | coords.go:104 | UTM conversion returned invalid coordinates. |
| `fach.resolver.gpx_unbekannt` | coords.go:181 | GPX waypoint not recognized. |
| `fach.resolver.gpx_parse` | coords.go:186 | The GPX waypoint could not be parsed. |
| `fach.resolver.gpx_bereich` | coords.go:189 | GPX coordinates are outside the valid range. |

**Middleware (G3b).** `middleware/auth.go` Zeilen 72, 78, 90, 98, 102: `http.Error(w, `{"error":"unauthorized"}`, 401)` wird `writeError(w, r, http.StatusUnauthorized, "unauthorized")` bzw. 503 `service_unavailable`. `writeError` steht in `middleware/lang.go` oder einer neuen Datei `middleware/httperr.go` und ruft `i18n.ErrorBody(i18n.FromRequest(r, nil), code, nil)`; `middleware` darf `handler` nicht importieren.

**Allowlist-Einträge (G5), die dieses Paket entfernt:** `internal/handler/briefing_send.go`, `internal/handler/trip.go`, `internal/handler/quota.go`, `internal/handler/etag.go`, `internal/handler/schreibsperre.go`, `internal/handler/location_resolve.go`, `internal/resolver/`. (`auth_oauth.go` und `account_delete_code.go` entfernt G4.) Der Veraltet-Test des Wächters meldet jeden vergessenen Eintrag.

**Golden (vor der Umstellung erzeugen).** `internal/handler/testdata/wortgleich_de/` enthält je eine Datei pro bisher deutschem Text (Name = Schlüssel ohne Präfix, z. B. `precondition_failed.txt`); die Quota-Texte als gerenderte Beispiele mit `current=1`, `limit=1`.

## Expected Behavior

- **Input:** Anfragen an Briefing-, Trip-, Ortsvergleich-, Orts-, Wetter-, Gruppen- und Metrik-Preset-Endpunkte sowie an geschützte Routen ohne Sitzung.
- **Output:** gleicher Status wie bisher; Body mit `code`, `message` in Nutzersprache, Alt-Feldern `error`/`detail` und den bisherigen Zusatzfeldern (`resource`, `limit`, `current`, `compare_presets`). Python-Antworten unverändert.
- **Side effects:** keine; `Retry-After` und der fehlende ETag bei 412 bleiben.

## Acceptance Criteria

- **AC-1:** Given ein angemeldeter Nutzer mit Sprache `en` / When er `PUT /api/briefings/{id}?kind=vergleich` mit veraltetem `If-Match` sendet / Then antwortet die API mit 412, `code` `precondition_failed`, der englischen `message` „The data was changed elsewhere in the meantime. Please reload and make your change again." und ohne `ETag`-Header.
  - Test: internal/handler/fach_fehler_zweisprachig_test.go — echter Router mit Sitzung und Temp-Datenverzeichnis, Stand per erstem GET geholt, dann zweite Änderung zwischendurch, dann PUT mit altem Stempel.

- **AC-2:** Given Nutzer mit Sprache `de` / When dieselben Fehlerfälle ausgelöst werden (412, Kennung belegt durch Trip und durch Ortsvergleich, Ort existiert bereits, Datei gesperrt, Kontingent erreicht, ungültige Briefing-Kennung) / Then sind `message` und `detail` wortgleich zu den heutigen Texten aus dem Golden-Verzeichnis, Status und Zusatzfelder (`resource`, `limit`, `current`) unverändert.
  - Test: internal/handler/fach_fehler_zweisprachig_test.go — Vergleich byte-genau gegen `testdata/wortgleich_de/*.txt` (vor der Umstellung aus den Konstanten erzeugt); `de`-Nutzer.

- **AC-3:** Given ein Nutzer im Tarif „free" mit Sprache `en`, der sein Kontingent erreicht hat / When er einen weiteren Trip, bzw. Ortsvergleich, bzw. Ort anlegt / Then antwortet die API mit 409 `quota_exceeded`, der englischen Meldung mit den korrekten Zahlen („You already have 1 of 1 trips on your plan …") und den Zusatzfeldern `resource`, `limit`, `current`.
  - Test: internal/handler/fach_fehler_zweisprachig_test.go — drei Ressourcen, echte Anlege-Handler hinter `QuotaPolicyMiddleware`; Trip und Ortsvergleich nutzen dieselbe Katalog-Mechanik.

- **AC-4:** Given zwei Nutzer A (`en`) und B (`de`), jeder mit eigenem Trip gleicher Kennung / When beide gleichzeitig den Trip des jeweils anderen per ID abrufen / Then bekommt jeder 404 `not_found` in seiner Sprache und sieht keine Daten des anderen.
  - Test: internal/handler/fach_fehler_zweisprachig_test.go — zwei Sitzungen, parallele Anfragen auf `GET /api/briefings/{id}?kind=route`; Mandantentrennung über `user_id` aus dem Auth-Kontext.

- **AC-5:** Given ein Nutzer sendet eine Komoot-Sammlungs-Adresse, ein Koordinatenpaar außerhalb des Bereichs oder einen unbekannten Text an `POST /api/locations/resolve` / When die Auflösung scheitert / Then antwortet die API mit 422, dem unveränderten `code` (`unsupported_url`, `unknown_format`) und der Meldung in Nutzersprache; bei `de` ist jede der 21 Resolver-Meldungen wortgleich zum Golden, bei `en` ist jede vorhanden und nicht leer.
  - Test: internal/resolver/meldungen_zweisprachig_test.go — tabellengetrieben über alle Auslöser, Vergleich gegen `testdata/meldungen_de.json`; Handler-Test mit `en`-Nutzer.

- **AC-6:** Given ein Besucher ohne Sitzung / When er eine geschützte Route aufruft, einmal mit `Accept-Language: en` und einmal ohne / Then antwortet die API mit 401, `code` `unauthorized`, `application/json` und der Meldung auf Englisch bzw. Deutsch.
  - Test: internal/middleware/sprache_zwei_nutzer_test.go — echte `AuthMiddleware`; zusätzlich 403 `forbidden` über `RequireAdmin` für einen `en`-Nutzer.

- **AC-7:** Given der Wächter aus G5 / When `go test ./internal/i18n/...` läuft / Then ist er grün, die oben genannten Allowlist-Einträge sind entfernt und in der Allowlist bleiben nur noch die Einträge der Mail-Dateien aus G4 (`internal/mail/`, `account_delete_code.go`, `auth_oauth.go`).
  - Test: internal/i18n/hardcode_guard_test.go (Ratschentest, `# doc-compliance-test`) — unverändert ausgeführt, kein neuer Test.

## Known Limitations

- **Annahme (Code behalten):** Die Issue-Skizze nennt `etag_mismatch`. Der bestehende Code `precondition_failed` ist in Frontend-Tests und `api_contract.md` verankert und bleibt; er ist der „stabile Code".
- **Annahme (Entwickler-Klartexte):** Englische technische `detail`-Texte aus den Validatoren werden nicht übersetzt; sie bleiben als `detail` erhalten, die `message` ist ein allgemeiner Katalogtext.
- **Annahme (Content-Type):** Klartext-Antworten in Nutzer-Handlern (`http.Error`) werden JSON. Vor der Umstellung per `grep` prüfen, dass das Frontend sie nicht als Text liest; sonst bleibt die Stelle unverändert und wird als Nebenbefund notiert.
- **Annahme (Glossar):** „Tarif" ergänzt dieses Paket als Zeile `Tarif | plan`.
- Der bestehende deutsche Resolver-Hinweis zu Komoot-Sammlungen (komoot.go:38) enthält einen Begriff, der im Produkt sonst nicht vorkommt. Er bleibt wörtlich (Golden); die englische Fassung sagt *routes*.
- `store` und `model` haben keine Nutzertexte; sollte eine spätere Änderung welche einführen, fängt der Wächter (G5) sie.
- Die Sprache der Python-Antworten (Versand-Ergebnisse) liegt bei P11; bis dahin kann eine Antwort gemischt sein (Go-Fehler `en`, durchgereichter Python-Text `de`).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0104
- **Rationale:** Texte der Go-API folgen der Nutzersprache; der unveränderte `code` bleibt die Schnittstelle und deutsche Bestandstexte bleiben wörtlich.

## Changelog

- 2026-10-30: Initial spec created (Planung Epic #2644)
