---
entity_id: fix_923_sms_fidelity_backend
type: bugfix
created: 2026-08-06
updated: 2026-08-06
status: corrected
version: "1.0"
tags: [sms, validator, frontend, trip-detail, editor, issue-923, adr-0011]
---

# Briefing-SMS-Fidelity über Backend-Feed (Issue #923)

> **Korrektur (#923b, 2026-08-06):** Der hier beschriebene Endpoint war korrekt
> gebaut, wurde aber gegen `ChannelFidelitySMS.svelte`/`ChannelPreviewCard.svelte`
> verdrahtet — tote Komponenten, nie von einer Route importiert (nur über den
> Organisms-Barrel erreichbar). Die Trip-Editor-Route rendert tatsächlich
> `WeatherV2MailPreview.svelte`, die bis #923b weiterhin ihre eigene, veraltete
> SMS-Simulation zeigte. Live wirksam ist die Backend-Anbindung erst ab #923b, das
> den Endpoint an `WeatherV2MailPreview.svelte` anschließt und die fünf toten
> Komponenten löscht. Details: `docs/specs/modules/fix_923b_wire_live_sms_preview.md`.

## Approval

- [x] Approved

## Purpose

`ChannelFidelitySMS.svelte` und `ChannelPreviewCard.svelte` (die Metrik-Editor-Vorschau für den
SMS-Kanal) rendern die SMS-Kurzform heute mit einer eigenen, hartcodierten TypeScript-Logik
(`SMS_TOK`/`smsRender`, **doppelt kopiert** in beiden Dateien) statt mit dem echten
Backend-Renderer — ein Verstoß gegen ADR-0011 (ein einziger Backend-Renderer, kein zweiter
im Frontend). Die Kopie ist zusätzlich sachlich ungenau: das reale SMS-Format
(`docs/reference/sms_format.md` §6) kürzt nach einer festen Prioritäts-Reihenfolge, nicht nach
Nutzer-Auswahlreihenfolge wie die TS-Simulation heute suggeriert; sie unterstellt zudem ein
140-Zeichen-Limit und einen Präfix/Anhang (`KHW03:` / `Z:WATCH:2447`), die im echten Format
nicht existieren (dokumentiertes Limit: 160 Zeichen, `sms_format.md` Zeile 26). Diese Scheibe
ersetzt beide Kopien durch einen gemeinsamen, zustandslosen Backend-Endpoint, der dieselben
Funktionen aufruft wie der Versandpfad.

## Source

- **File:** `api/routers/validator.py`
- **Identifier:** neuer Endpoint `POST /api/_validator/sms-fidelity-preview`

Mehrschichtige Änderung — betrifft **Python-Core** (`api/routers/validator.py`,
`src/services/validator_render_service.py`, `src/output/tokens/render.py`) und
**Frontend/User-UI** (`frontend/src/lib/components/trip-detail/ChannelFidelitySMS.svelte`,
`frontend/src/lib/components/trip-detail/ChannelPreviewCard.svelte`).

> **Korrektur 2026-08-06:** „Kein Go-Anteil" war falsch. Das Frontend ruft den neuen
> Endpoint über `api.post()` auf, was über die Go-API (Port 8090) läuft — ohne
> dedizierte Proxy-Route in `internal/router/router.go` (analog
> `CompareEmailPreviewProxyHandler`) wäre der Aufruf im Browser mit 404
> fehlgeschlagen. Nachgetragen, betrifft zusätzlich `internal/router/router.go` und
> `internal/handler/proxy.go`.

Der neue Endpoint braucht **keine** `user_id` — konsistent mit dem bestehenden
`alert-preview`/`compare-email-preview`-Muster in derselben Datei (Zeilen 243–264,
316–327): zustandslos, beispielwertbasiert, kein Zugriff auf Trip- oder Nutzerdaten. Die
Mandantenfähigkeits-Pflicht aus `CLAUDE.md` ("echte `user_id` durchreichen, niemals `default`")
greift bei datenbewegenden/-lesenden Endpoints — dieser Endpoint bewegt keine Nutzerdaten,
vgl. AC-3.

## Estimated Scope

- **LoC:** ~150 netto (Backend-Ergänzungen additiv ~90 Zeilen; beide Svelte-Dateien verlieren
  ihre `SMS_TOK`/Kürzungslogik-Kopie und gewinnen dafür Fetch-Code — grob neutral bis leicht
  rückläufig)
- **Files:** 5
- **Effort:** medium (mehrschichtig — Backend + zwei Frontend-Komponenten — aber jede
  Einzeländerung für sich klein)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `output.tokens.builder.build_token_line()` | upstream | baut die `TokenLine` aus Beispiel-Vorhersage + `MetricSpec`-Liste — identische Funktion wie im Versandpfad |
| `output.tokens.render.render_line()` | upstream | wendet §6-Kürzung an, liefert den fertigen String; wird um eine additive Variante ergänzt, die zusätzlich die überlebenden Symbole zurückgibt |
| `output.renderers.sms_trip.SMS_SYMBOL_BY_METRIC` / `SMS_MULTI_SYMBOLS_BY_METRIC` | upstream | einzige Quelle der Zuordnung `metric_id -> SMS-Symbol(e)` — dieselbe Tabelle, die `trip_report.py:283-307` für den echten Versand nutzt, hier wiederverwendet statt zweimal gepflegt |
| `app.metric_catalog.sms_code` | upstream | bereits über `/api/metrics` an `metricById` ausgeliefert; unterscheidet im Frontend "kein Code" von "Zeichenlimit" (kein neues Feld vom Endpoint nötig) |
| `api/routers/validator.py::alert_preview()` (#918) | pattern | Vorbild für zustandslosen Validator-Endpoint ohne `user_id`, gleiche Datei |
| `frontend/.../alerts-tab/AlertPreviewCard.svelte` | pattern | Vorbild für das Lade/Fehler-`api.post()`-Muster im Frontend |
| `output.renderers.sms_trip.SMSTripFormatter.format_sms()` | sibling (unverändert) | echter Versand-Renderer — bleibt unangetastet, ruft intern ebenfalls `build_token_line()`+`render_line()` |
| `frontend/.../trip-detail/ChannelPreviewBlock.svelte` | parent (unverändert) | bindet beide geänderten Komponenten ein; bewusst NICHT angefasst — beide Kinder rufen unabhängig denselben Endpoint auf |

## Implementation Details

### Neuer Endpoint

```
POST /api/_validator/sms-fidelity-preview
Body:     {"metric_ids": ["temperature", "wind", "gust", "rain_probability", "thunder", ...]}
Response: {"line": str, "char_count": int, "max_length": int, "carried_ids": [str, ...]}
```

Kein `user_id`-Query-Parameter (siehe Source). `metric_ids` ist die flache Liste
`[...primary, ...secondary]` aus dem Editor-Zustand.

### `src/services/validator_render_service.py` — neue Funktion

Baut aus `metric_ids` eine `MetricSpec`-Liste nach demselben Muster wie
`trip_report.py:283-307`: für jedes bekannte SMS-Symbol aus `SMS_SYMBOL_BY_METRIC` /
`SMS_MULTI_SYMBOLS_BY_METRIC`, dessen `metric_id` **nicht** in `metric_ids` enthalten ist, wird
eine `MetricSpec(symbol=sym, enabled=False)` als `disabled_specs`-Eintrag geführt — exakt die
Logik, die im Versandpfad SD/SL/N/K/D/... bei Abwahl unterdrückt (Bug #944, #1415). Eine feste
Beispiel-`NormalizedForecast`/`DailyForecast` liefert die Werte (wiederverwendbar aus den
bereits vorhandenen `SAMPLE_BY_ID`/`SAMPLE_HOURS`-Konstanten in `ChannelFidelityEmail.svelte`,
serverseitig neu als Python-Konstanten). Die Funktion ruft `build_token_line()` und die neue
additive Render-Funktion (s.u.) **direkt** auf — **kein Umbau von
`output.renderers.sms_trip.py`**, der Versand-Renderer bleibt unangetastet.

### `src/output/tokens/render.py` — additive Funktion

Eine zweite, kleine Funktion neben `render_line()` (~10-15 Zeilen), die dieselben privaten
Kürzungs-Helfer (`_truncate`, `_fuse`, `_draw`) wiederverwendet und zusätzlich die Menge der
nach der Kürzung **überlebenden Token-Symbole** zurückgibt. `render_line()` selbst bleibt
unverändert — die neue Funktion ruft dieselben Helfer nur zusätzlich auf und liest ihr Ergebnis
mit; kein Produktivpfad (E-Mail/Telegram/SMS-Versand) importiert die neue Funktion.

### `ChannelFidelitySMS.svelte`

`SMS_TOK`/`smsRender`/`SMS_TOKEN_MEANING`/`SMS_PREFIX`/`SMS_TAIL`/`SMS_MAX` entfallen komplett.
`api.post('/api/_validator/sms-fidelity-preview', {metric_ids})` nach dem Lade/Fehler-Muster
von `AlertPreviewCard.svelte`. Angezeigt werden `line` (statt der lokal simulierten Zeile) und
`{char_count}/{max_length} Zeichen` (statt der hartcodierten `140`). "Mit SMS-Code" /
"fallen weg" wird aus `carried_ids` vs. `metric_ids` abgeleitet; "kein Code" vs. "Zeichenlimit"
weiterhin über das vorhandene `metricById[id]?.sms_code`.

### `ChannelPreviewCard.svelte`

Eigenes `SMS_TOK`/`smsCounters`/`SMS_PREFIX`/`SMS_TAIL`/`SMS_MAX` entfällt. Eigener
`api.post(...)` an denselben Endpoint (zwei Requests statt einem — bewusst in Kauf genommen,
siehe Known Limitations); `smsCount.carried`/`smsCount.dropped` werden aus
`carried_ids.length` bzw. `metric_ids.length - carried_ids.length` der Serverantwort abgeleitet.

### Was sich ausdrücklich NICHT ändert

- `output.renderers.sms_trip.py` / `SMSTripFormatter.format_sms()` — echter Versandpfad
- `render_line()` selbst (nur eine neue Nachbar-Funktion, kein Umbau)
- `ChannelPreviewBlock.svelte` (Elternteil) — beide Kinder bleiben unabhängig
- `ChannelFidelityEmail.svelte` / `ChannelFidelityBubble.svelte` — nicht Teil dieser Scheibe

## Expected Behavior

- **Input:** Liste ausgewählter `metric_id`-Strings (Primary + Secondary aus dem Editor,
  ungespeichert, live editiert).
- **Output:** Die tatsächliche SMS-Zeile inkl. §6-Kürzung, die tatsächlich verwendete
  Zeichengrenze, und die Liste der `metric_ids`, deren Symbol die Kürzung überlebt hat.
- **Side effects:** keine (kein Trip-/Wetterdaten-Fetch, kein Versand, keine Persistenz).

## Test Plan

### Automated Tests (TDD RED)

**Backend — `api/routers/validator.py` / `src/services/validator_render_service.py`**
- [ ] Test 1 (AC-1): GIVEN eine Metrik-Auswahl ohne nötige Kürzung WHEN der Endpoint aufgerufen
  wird THEN ist `line` bytegleich zum direkten Aufruf von `render_line(build_token_line(...))`
  mit denselben Eingaben.
- [ ] Test 2 (AC-2): GIVEN alle SMS-fähigen Metriken gleichzeitig ausgewählt (erzwingt Kürzung)
  WHEN der Endpoint aufgerufen wird THEN ist `line` weiterhin bytegleich zum direkten Aufruf
  derselben Funktionen, und `carried_ids` entspricht genau den nach §6-Kürzung in `line`
  verbliebenen Symbolen.
- [ ] Test 3 (AC-3): GIVEN kein `user_id`-Parameter und kein existierender Trip WHEN der
  Endpoint mit nur `metric_ids` aufgerufen wird THEN antwortet er mit 200 und valider
  Response-Shape.
- [ ] Test 4 (AC-4): GIVEN eine Metrik ohne `sms_code` in der Auswahl WHEN der Endpoint
  aufgerufen wird THEN fehlt ihre `metric_id` in `carried_ids`.
- [ ] Test 5 (AC-5): GIVEN der Endpoint antwortet WHEN die Response ausgewertet wird THEN ist
  `max_length == 160` (dokumentierter Wert aus `sms_format.md`, nicht die alte `140`).

**Backend-Regression — `src/output/tokens/render.py`**
- [ ] Test 6 (AC-9): GIVEN ein bestehender Testfall aus dem Versandpfad, der `render_line()`
  bereits vor dieser Änderung mit einer kürzungspflichtigen TokenLine aufruft WHEN derselbe
  Aufruf nach dieser Änderung erfolgt THEN ist die Ausgabe bytegleich zum Stand vor der
  Änderung (Byte-Vergleich vor/nach + bestehende E-Mail/Telegram/SMS-Versandpfad-Tests bleiben
  unverändert grün).

**Frontend — `ChannelFidelitySMS.svelte`**
- [ ] Test 7 (AC-6): GIVEN `api.post` liefert gemockt eine `line`, die von einer plausiblen
  clientseitigen Neuberechnung abweichen würde WHEN die Komponente rendert THEN erscheint
  exakt dieser Server-Text im DOM (mutations-tauglich — fängt eine stillschweigend
  wiederbelebte `smsRender()`-Restlogik).
- [ ] Test 8 (AC-5 Teil Frontend): GIVEN `api.post` liefert `max_length` abweichend von `140`
  WHEN die Komponente rendert THEN übernimmt die Zeichenzähler-Anzeige exakt diesen
  Server-Wert.

**Frontend — `ChannelPreviewCard.svelte`**
- [ ] Test 9 (AC-7): GIVEN `api.post` liefert gemockt eine `carried_ids`-Liste, die von einer
  plausiblen clientseitigen Neuberechnung abweichen würde WHEN die Kachel rendert THEN zeigt
  sie "X als Code" / "Y fallen weg" exakt nach den Server-Zahlen (X = `carried_ids.length`,
  Y = `metric_ids.length - carried_ids.length`), nicht nach einer Eigenberechnung.

**Frontend — Konsistenz beider Komponenten**
- [ ] Test 10 (AC-8): GIVEN beide Komponenten mit derselben Primary/Secondary-Auswahl und
  derselben gemockten Endpoint-Antwort gerendert WHEN ihre DOM-Ausgaben verglichen werden THEN
  stimmt die Anzahl "als Code" in `ChannelPreviewCard` exakt mit der Länge der "mit SMS-Code"-
  Liste in `ChannelFidelitySMS` überein.

## Acceptance Criteria

- **AC-1:** Given eine Metrik-Auswahl, deren volle Token-Zeile unter dem dokumentierten Limit
  bleibt (kein Kürzen nötig) / When der Endpoint mit dieser Auswahl aufgerufen wird / Then ist
  `line` bytegleich zu dem, was ein direkter Aufruf von `render_line(build_token_line(...), ...)`
  mit derselben Beispiel-Vorhersage und derselben Metrik-Auswahl liefert — denselben Funktionen,
  die auch der echte Versandpfad aufruft.
  - Test: Endpoint-Response vs. direkter Python-Aufruf derselben Funktionen mit identischen
    Eingaben, String-Vergleich.

- **AC-2:** Given eine große Metrik-Auswahl (alle SMS-fähigen Metriken gleichzeitig), deren
  volle Token-Zeile die Zeichengrenze überschreitet / When der Endpoint aufgerufen wird / Then
  ist `line` erneut bytegleich zum direkten Aufruf derselben Funktionen (inklusive angewendeter
  §6-Kürzung), und `carried_ids` enthält genau die `metric_ids`, deren SMS-Symbol nach dieser
  Kürzung noch in `line` vorkommt — in der dokumentierten Prioritäts-Reihenfolge aus
  `sms_format.md` §6, nicht in Auswahlreihenfolge.
  - Test: wie AC-1, zusätzlich `carried_ids` gegen die tatsächlich in `line` vorkommenden
    Symbole geprüft. Vor dem Fix simuliert die Frontend-Kopie eine Auswahlreihenfolge-Kürzung —
    dieser Test macht die Abweichung sichtbar.

- **AC-3:** Given kein `user_id`-Parameter und kein existierender Trip / When der Endpoint mit
  nur `metric_ids` aufgerufen wird / Then antwortet er mit 200 und einer validen Antwort — kein
  401/422 wegen fehlender `user_id` (zustandslos wie `alert-preview`/`compare-email-preview`).
  - Test: HTTP-Aufruf ohne `user_id`-Query-Parameter, Status-Code und Response-Shape geprüft.

- **AC-4:** Given eine Metrik ohne SMS-Code in der Auswahl (z.B. eine reine Tabellen-Metrik) /
  When der Endpoint aufgerufen wird / Then fehlt ihre `metric_id` in `carried_ids`, obwohl sie
  angefragt wurde — das Frontend unterscheidet "kein Code" vs. "Zeichenlimit" weiterhin über
  das bereits vorhandene `sms_code`-Feld aus `/api/metrics`, ohne dass der Endpoint dafür ein
  eigenes Grund-Feld braucht.
  - Test: `metric_ids` enthält eine Metrik mit leerem `sms_code`, `carried_ids` enthält sie
    nicht.

- **AC-5:** Given der Endpoint antwortet / When das Frontend die Zeichenzähler-Anzeige baut /
  Then stammt `max_length` aus der Serverantwort (dokumentierter Wert 160 aus
  `sms_format.md`), nicht aus der alten lokalen Konstante `140` — beide Frontend-Komponenten
  verwenden ausschließlich den vom Server gelieferten Wert.
  - Test: Endpoint-Response `max_length == 160`; Komponententest prüft, dass die angezeigte
    Zeichenzahl-Anzeige (`{char_count}/{max_length}`) den Server-Wert übernimmt, auch wenn er
    versuchsweise auf einen anderen Wert als 140 gesetzt wird.

- **AC-6:** Given der Backend-Endpoint liefert eine `line`, die von dem abweicht, was die
  frühere clientseitige `smsRender()`-Simulation berechnet hätte / When `ChannelFidelitySMS`
  mit dieser Server-Antwort rendert / Then zeigt die Komponente exakt den vom Server gelieferten
  Text an — keine eigene Kürzungsberechnung mehr im Client.
  - Test: `api.post` in der Komponente gemockt mit einer bewusst "unrealistischen" `line`
    (die eine clientseitige Neuberechnung nie erzeugen würde), Component-Test prüft, dass genau
    dieser Text im DOM erscheint. Fängt eine Regression, bei der ein Rest der alten
    `smsRender()`-Logik stillschweigend weiter mitrechnet.

- **AC-7:** Given der Backend-Endpoint liefert `carried_ids` mit weniger Einträgen als
  angefragt / When `ChannelPreviewCard` mit dieser Server-Antwort rendert / Then zeigt die
  Kachel "X als Code" mit X = `carried_ids.length` und "Y fallen weg" mit
  Y = `metric_ids.length - carried_ids.length` — beide Zahlen aus der Serverantwort, nicht aus
  einer lokal nachgerechneten Kopie.
  - Test: `api.post` gemockt mit einer `carried_ids`-Liste, die von dem abweicht, was die
    frühere `smsCounters()`-Kopie berechnet hätte; Component-Test prüft die angezeigten Zahlen
    gegen die Mock-Antwort, nicht gegen eine plausible Eigenberechnung.

- **AC-8:** Given dieselbe Primary/Secondary-Auswahl wird in `ChannelFidelitySMS` und
  `ChannelPreviewCard` gleichzeitig verwendet / When beide Komponenten denselben Endpoint mit
  denselben `metric_ids` aufrufen / Then stimmt die Anzahl der in `ChannelPreviewCard` als "als
  Code" gezeigten Metriken exakt mit der Länge der in `ChannelFidelitySMS` angezeigten
  "mit SMS-Code"-Liste überein — keine der beiden Komponenten führt mehr eine eigenständige
  Berechnung, die von der anderen abweichen könnte.
  - Test: beide Komponenten mit derselben gemockten Endpoint-Antwort gerendert, Zahlen aus
    beiden DOM-Ausgaben verglichen.

- **AC-9:** Given ein bestehender Testfall aus dem Versandpfad, der `render_line()` bereits vor
  dieser Änderung mit einer TokenLine aufruft, die gekürzt werden muss / When derselbe Aufruf
  nach dieser Änderung erfolgt / Then ist die Ausgabe bytegleich zum Stand vor der Änderung —
  die neue additive Funktion ändert nichts am bestehenden Verhalten von `render_line()`.
  - Test: bestehende `render_line()`-Tests (E-Mail/Telegram/SMS-Versandpfad) laufen unverändert
    grün; zusätzlich ein Byte-Vergleich vor/nach für einen Kürzungsfall.

## Known Limitations

- **Zwei Requests statt einem.** `ChannelPreviewBlock.svelte` (gemeinsamer Elternteil) wird
  nicht angefasst — beide Kinder rufen unabhängig denselben zustandslosen Endpoint auf.
  Zusammenlegen (ein gemeinsamer State im Elternteil) ist ein trivialer Folge-Schritt, kein
  Blocker dieser Scheibe.
- **Ladezustand bei jedem Checkbox-Toggle.** Mit Backend-Anbindung entsteht ein kurzer
  Ladezustand bei jeder Änderung der Primary/Secondary-Auswahl (heute clientseitig instant).
  Debounce (250-400ms) ist ein Implementierungsdetail für `/50-implement`, kein Acceptance
  Criterion dieser Spec.
- **Fiktiver Präfix/Anhang entfällt sichtbar.** Die alte Vorschau zeigte `KHW03:` als Präfix
  und `Z:WATCH:2447` als Anhang — beides frei erfundene Platzhalter ohne Entsprechung im echten
  Renderer. Nach dieser Änderung zeigt die Vorschau nur noch die reale Token-Zeile
  (`{Etappe}: {Tokens}`). Das ist eine gewollte Korrektur, keine Regression — die Vorschau
  entspricht damit erstmals dem, was tatsächlich versendet wird.
- **Nur Abend-Version, kein Morgen/Abend-Umschalter.** PO-Entscheidung 2026-08-05 — kein Delta
  in dieser Scheibe.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine neue — setzt ADR-0011 (ein einziger Backend-Renderer, kein zweiter im
  Frontend) für den SMS-Kanal um, analog zur bereits umgesetzten Alert-Vorschau (#918).
- **Rationale:** Kein neues Entscheidungsfeld; die Scheibe entfernt eine bestehende
  ADR-0011-Abweichung, die bislang nur für Alert-Vorschauen (nicht für die Metrik-Editor-
  Vorschau) geschlossen war.

## Changelog

- 2026-08-06: Status auf `corrected` gesetzt — die beschriebene Verdrahtung war
  gegen tote Komponenten gebaut (nie live). Korrektur: #923b, Spec
  `docs/specs/modules/fix_923b_wire_live_sms_preview.md`.
- 2026-08-06: Go-Proxy-Route bestätigt gemergt (`SmsFidelityPreviewProxyHandler` in
  `internal/handler/proxy.go`, Route in `internal/router/router.go`), per
  End-to-End-Test gegen den vollen Produktions-Router (inkl. Auth-Pflicht)
  verifiziert. Status auf `implemented` gesetzt.
- 2026-08-06: Fehlende Go-Proxy-Route nachgetragen (`internal/router/router.go`,
  `internal/handler/proxy.go`) — die Source-Sektion nannte fälschlich „Kein
  Go-Anteil"; ohne die Route war der Endpoint vom Frontend aus nicht erreichbar
  (404). PO-Entscheidung: sofort beheben, nicht als Folge-Issue.
- 2026-08-06: Test Plan-Sektion ergänzt (Validator-Anforderung).
- 2026-08-06: Initial spec created (Issue #923, abgespalten aus #918 Slice 3).
