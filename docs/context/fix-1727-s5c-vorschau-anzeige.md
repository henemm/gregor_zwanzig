# Context: #1727 S5c — Vorschau, Anzeige, Sofort-Vergleich folgen dem Ortstag

- **Workflow:** `fix-1727-s5c-vorschau-anzeige` (Full Process)
- **Basis:** `e2b5269b`
- **Vorgänger:** S5a (`dbad9614`, live), S5b (`b26d88a9`, live)
- **Epic:** #1722 · **ADR:** 0044 (Kalendertage folgen der Ortszeit), 0051 (Drei Zeitbegriffe, Regel 3)

## Request Summary

Die vierte Scheibe von #1727 stellt die Vorschau-, Anzeige- und Sofort-Vergleichs-Pfade vom
Servertag auf den Ortstag um. Sieben Fundstellen in fünf Dateien, alle im Wächter
`tests/test_output_timezone_guard.py` als „Muster A" (Umgebungsuhr) geführt.

## Die sieben Fundstellen — gemessen, nicht übernommen

| Datei:Zeile | Funktion | Wirkung | Zone am Fundort verfügbar? |
|---|---|---|---|
| `src/services/preview_service.py:94` | `_resolve_target_date` | Vorschau (3 GET-Endpunkte), **kein Versand** | **JA** — `trip` ist bereits Parameter |
| `src/services/compare_preview_service.py:258` | `_resolve_target_date` | Vorschau (`POST /api/preview/compare/{id}`), **kein Versand** | **JA** — `locations` steht in `_prepare()` bei `:147` vor dem Aufruf `:148` |
| `api/routers/compare.py:53` | `run_comparison` | „jetzt" für die 14:00-Schwelle | **JA** — `selected` steht bei `:41/:44` fest |
| `api/routers/compare.py:55` | `run_comparison` | Zieltag „heute" | JA (s.o.) |
| `api/routers/compare.py:58` | `run_comparison` | Zieltag „morgen" | JA (s.o.) |
| `src/services/comparison_engine.py:407` | `dict_to_comparison_result` | **kein Aufrufer** | — |
| `src/output/renderers/email/compare_html.py:1443` | `_compute_next_send` | **versendete Mail**, Footer „Nächster Versand" | **JA** — `header_tz` bei `:1604`, aber Signaturänderung nötig |

**Vollständigkeit geprüft:** Die fünf Dateien enthalten genau sieben Umgebungsuhr-Aufrufe —
deckungsgleich mit den sieben Wächter-Einträgen. Keine `utcnow()`-Blindstelle wie in S5b
(der Wächter erkennt nur `.today()` und `.now()` ohne `tz`, siehe „Wächter" unten).

## Die drei Befunde, die den Zuschnitt verändern

### 1. Vier der sieben Fundstellen hängen an Code, den niemand aufruft

- **`dict_to_comparison_result` ist produktiv tot.** Kein Aufruf in `src/`, `api/`, `tests/`,
  `frontend/`, `internal/`, `cmd/`. Der einzige Testbezug ist ein `hasattr`-Strukturtest
  (`tests/refactor/test_epic_129a_1_module_structure.py:36,45-46`).
  Zwei Code-Kommentare behaupten aktive Nutzung — `compare_html.py:643` nennt den
  „Validator-Render-Pfad" als Nutzer, aber `validator_render_service.py:151-184` baut
  `ComparisonResult` direkt (`:168-172`) und ruft die Funktion nicht. `user.py:144` nennt sie
  als Beispiel-Aufrufer ohne aktiven Aufruf.
- **`GET /api/compare` hat keinen Frontend-Aufrufer.** Suche in `frontend/src` nach dem
  bloßen Pfad: null Treffer; alle Treffer sind `/api/compare/metrics` bzw.
  `/api/compare/presets/…`. Der aktive Weg ist `POST /api/preview/compare/{preset_id}`
  (`api/routers/preview.py:96`). Zwei Tests treffen den Endpunkt
  (`test_sport_aware_scoring.py:251`, `test_hail_flag_metrics_catalog_and_compare_api.py:103`),
  beide ohne `target_date` und ohne Prüfung der 14:00-Regel.

**Daraus folgt eine Produktfrage, keine technische:** Zeitzonen-Korrektur an unbenutztem Code
oder ersatzlos entfernen? Vier von sieben Fundstellen und die gesamte 14:00-Heuristik hängen
daran.

### 2. Die 14:00-Heuristik ist nirgends spezifiziert

`api/routers/compare.py:49-58` entscheidet „vor 14:00 → heute, sonst morgen". Die Schwelle
kommt an keiner anderen Stelle im Code vor (keine Konstante, kein zweiter Fundort), und in
`docs/` steht keine Spezifikation dazu. Einzige „Spezifikation" ist der Query-Docstring
(`:28`, „defaults to today/tomorrow based on time"). Kein Test prüft sie.

Sie hat **zwei** zonenabhängige Teile, die getrennt zu entscheiden sind: die Stunde
(`now.hour`, `:53`) und den Tag (`date.today()`, `:55`/`:58`).

### 3. Zwei konkurrierende „erster Ort"-Auflösungen in derselben Mail

Beide berufen sich auf #1378 AC-4:

| Ort | Auflösung | Verhalten bei nicht auflösbarem erstem Ort |
|---|---|---|
| Kopfzeile, `compare_html.py:1604` | `location_tz(locations[0].location)` | fällt still auf **UTC** |
| Zieltag im Versand, `scheduler_dispatch_service.py:441` | `first_resolvable_tz(locations)` | überspringt ihn, nimmt den **nächsten** auflösbaren |

Sie fallen genau dann auseinander, wenn der erste Ort keine auflösbare Zone trägt: Die
Kopfzeile derselben Mail zeigt dann Weltzeit, während ihr Zieltag in der Zone des zweiten Orts
gerechnet wurde. Genau die Falle, für die `first_resolvable_tz` in #1726 gebaut wurde — die
Kopfzeile hat den Fix nie bekommen. **Steht in keiner Restliste und in keinem Wächter**
(`location_tz` ist keine Umgebungsuhr, also kein Muster A).

Für `_compute_next_send` ist damit zu entscheiden, welche der beiden Zonen der Footer erbt.

## Related Files

| Datei | Relevanz |
|---|---|
| `src/services/preview_service.py` | Fundstelle; `:217-222` dokumentiert die S5b-Entscheidung, diesen Fund an S5c zu delegieren; `:222` löst bereits `jetzt_utc` auf, aber in einer anderen Methode |
| `src/services/compare_preview_service.py` | Fundstelle; `_prepare()` `:129-176` hat die Orte vor dem Datumsaufruf |
| `api/routers/compare.py` | Fundstelle ×3; Alt-Bestand ohne Frontend-Aufrufer |
| `src/services/comparison_engine.py` | Fundstelle; `dict_to_comparison_result` ohne Aufrufer |
| `src/output/renderers/email/compare_html.py` | Fundstelle im **versendeten** Mail-Footer; `:1604` zweite Zonen-Auflösung |
| `src/services/trip_day.py` | Baustein `trip_local_today(trip, now_utc)` (`:90-96`) — Domänenschicht |
| `src/utils/timezone.py` | Baustein `first_resolvable_tz(locations)` (`:77-99`), `local_dt`, `location_tz` |
| `src/services/scheduler_dispatch_service.py` | Vorbild aus S5b (`:439-442`): Zone auflösen, dann `local_dt(now, zone).date()` |
| `tests/test_output_timezone_guard.py` | Der Wächter; Schrumpf-Test + Ordinal-Schlüssel |

## Existing Patterns

- **Der S5b-Griff:** Zone am Aufrufort auflösen, `local_dt(now_utc, zone).date()` statt
  `date.today()`. Vorbild `scheduler_dispatch_service.py:439-442`.
- **Zone nie doppelt auflösen** (ADR-0044): Ein zweiter Auflöser in derselben Kette ist ein
  Regelverstoß. Bei `preview_service` ist deshalb zu prüfen, ob das vorhandene `trip_tz`
  (`:226`) und ein neues `trip_local_today` aus **einer** Auflösung kommen.
- **Regel 3 (ADR-0051):** „Jetzt" wird als Parameter hereingereicht. In S5b bewusst
  funktionsintern gelassen, wo die Auflösung unmittelbar vor jedem Netzabruf steht.
- **`# gz-main-path:`-Muster (#1409)** als Vorbild für begründete Zeilen-Ausnahmen, wenn UTC
  die richtige Antwort ist.

## Dependencies

- **Upstream:** `trip_day.trip_local_today`, `utils.timezone.{first_resolvable_tz, local_dt,
  location_tz}` — alle vorhanden, kein neuer Baustein nötig.
- **Downstream:** drei Vorschau-Endpunkte (`/api/preview/{id}/{email,sms,telegram}`), die
  Compare-Vorschau (`POST /api/preview/compare/{id}`), der Footer jeder versendeten
  Vergleichs-Mail.

## Existing Specs

- `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` — Restliste „Vorschau, Werkzeuge"
- `docs/adr/0051-drei-zeitbegriffe-zone-an-den-daten.md` — Regel 2 und Regel 3
- `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md`, `…s5b_versandpfade_ortstag.md`
- `docs/context/fix-1697-ortstag-statt-servertag.md` — Fundstellen-Karte nach Wirkung

## Risks & Considerations

1. **Die ADR-Restliste ist zum fünften Mal unvollständig.** ADR-0044 nennt für S5c
   `preview_service._resolve_target_date`, `api/routers/debug.py` und
   `tools/weather_validation.py`. Davon gehört nach dem Zuschnitt vom 2026-08-14 nur die erste
   zu S5c; `debug.py` steht dort unter S5d, und **`tools/weather_validation.py` kommt in keiner
   Scheibe vor** — die Datei existiert und hat einen offenen Fund (`:288`), den der Wächter
   nicht scannt (`tools/` liegt außerhalb seines Geltungsbereichs). Umgekehrt fehlt
   `compare_preview_service._resolve_target_date` in der ADR-Liste, obwohl der Wächter sie
   führt. Das ADR warnt an genau dieser Stelle selbst davor: „Sie war nicht falsch, sondern
   unvollständig — und eine unvollständige Restliste liest sich wie eine vollständige."
2. **Die Testfläche kann den Fehler strukturell kaum zeigen.** 23 von 24 Fixtur-Dateien liegen
   in Mitteleuropa. Für die Compare-Seite braucht es Orte mit exotischen Zonen; Vorlagen:
   `_trip_two_zones` (`tests/tdd/test_drilldown_day_window_local_date.py:415-431`) und die
   Drei-Zonen-Fixtur aus S5a (Pago Pago / Korsika / Kiritimati).
3. **`freeze_time` macht Parameter-gegen-Systemuhr unfalsifizierbar** (S5a-Befund F001): Jeder
   Test setzt `freeze_time(X)` gegen einen abweichenden Parameterwert `Y`.
4. **Die Ordinal-Verschiebung geht in beide Richtungen** (S5b): Werden in
   `run_comparison` nicht alle drei Funde gemeinsam behoben, verschieben sich die Ordinale der
   verbleibenden — der Wächter meldet dieselbe Stelle dann gleichzeitig als veraltet und als
   neuen Verstoß.
5. **Kein bestehender Test bewacht die Umstellung.** Für `preview_service._resolve_target_date`
   gibt es einen Test, der nur `is not None` prüft; `compare_preview_service._resolve_target_date`
   hat null direkte Tests; der einzige Footer-Test
   (`test_issue_1110_compare_mail_v2.py:680-696`) prüft nur, dass kein `—`-Platzhalter
   erscheint. Die Umstellung bricht keinen davon — der Nachweis muss vollständig neu entstehen.
6. **Der Wächter ist blind für `utcnow()`** (`_AMBIENT_CLOCK_ATTRS = {"now", "today"}`,
   `tests/test_output_timezone_guard.py:141-145`) — bewusst so, weil `utcnow()` ausdrücklich
   Weltzeit liefert. Für die fünf S5c-Dateien nachgemessen: keine `utcnow()`-Stelle.

## Analysis

### Type

Bug (Fehlerklasse des Epics #1722: Kalendertag folgt der Serveruhr statt dem Ortstag).

### Zwei Befunde dieses Kontext-Dokuments haben der Nachmessung nicht standgehalten

Beide oben in „Die drei Befunde" formuliert, beide vom `analysis-challenger` gekippt und am
Code gegengeprüft. **Gemeinsames Muster: aus einer unvollständigen Suche auf eine
Wirkungsaussage geschlossen** — dieselbe Klasse, die dieses Epic bereits fünfmal getroffen hat.

1. **„`GET /api/compare` hat keinen Aufrufer" ist falsch.** Die Suche deckte nur
   `frontend/src` ab. Der Endpunkt ist im Go-Stack verdrahtet: `internal/router/router.go:156`
   registriert ihn mit einem eigens gebauten `CompareProxyHandler`
   (`internal/handler/proxy.go:73-100`) — 60 Sekunden Timeout „because the comparison fetches
   weather data for multiple locations", inklusive `appendUserID` für die Mandantentrennung.
   Er ist über die öffentliche API erreichbar. **Er wird repariert, nicht entfernt** —
   Entfernen wäre ein stiller Breaking Change am öffentlichen API-Vertrag.
2. **„Die Kopfzeilen-Auflösung `location_tz(locations[0].location)` ist fehlerhaft" ist
   falsch.** Sie ist die wörtliche Umsetzung von PO-freigegebenem AC-4 aus #1378
   (`docs/specs/modules/issue_1378_compare_zeitbasis.md:262-271`): Zeitbasis ist der
   **erstgenannte** Ort der konfigurierten Reihenfolge, ausdrücklich nicht der erste
   auflösbare. AC-7 (`:292-299`) verlangt nur einen **sichtbaren** UTC-Rückfall — geleistet
   durch `local_stamp()` (`src/utils/timezone.py:132-137`). `first_resolvable_tz` wurde in
   #1726 für eine andere fachliche Frage gebaut (Ruhezeit, Zähler, Fälligkeit).
   **Die Kopfzeile bleibt unangetastet**; sie umzustellen wäre eine Regression gegen AC-4.

Bestehen bleibt Befund 1 (`dict_to_comparison_result` ohne Aufrufer) — vom Challenger per
Volltextsuche im ganzen Repo bestätigt: einziger Treffer ist die Definition selbst.

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/preview_service.py` | MODIFY | `_resolve_target_date` nimmt `now_utc` (Pflicht) und rechnet über `trip_local_today`; `_build_report` erbt dasselbe `now_utc` statt der eigenen Auflösung bei `:223` |
| `src/services/compare_preview_service.py` | MODIFY | `_resolve_target_date(given, locations, now_utc)`; Zone über `first_resolvable_tz(locations)` in `_prepare()` |
| `api/routers/compare.py` | MODIFY | alle drei Funde gemeinsam: Zone aus `selected`, Stunde **und** Tag in Ortszeit |
| `src/services/comparison_engine.py` | DELETE | `dict_to_comparison_result` (`:394-439`) ersatzlos — 0 Aufrufer |
| `src/output/renderers/email/compare_html.py` | MODIFY | `tz` an `_render_abo_footer` und `_compute_next_send` durchreichen; Quelle ist das bereits aufgelöste `header_tz` (`:1604`) |
| `tests/refactor/test_epic_129a_1_module_structure.py` | MODIFY | `hasattr`-Zeile für die gelöschte Funktion entfällt |
| `tools/weather_validation.py` | MODIFY | begründete Zeilen-Ausnahme (`:288`), kein Verhaltens-Fix |
| `tests/test_output_timezone_guard.py` | MODIFY | sechs Einträge entfallen (drei durch Fix, drei durch Löschung/Umstellung) |

### Scope Assessment

- Dateien: 8 (davon 2 Tests, 1 Werkzeug)
- Produktivcode: geschätzt **+50/−60** (Löschungen überwiegen an einer Stelle)
- Testcode: geschätzt **+200**
- Risiko: **MEDIUM** — eine Fundstelle wirkt auf versendete Mails, drei auf einen öffentlich
  erreichbaren Endpunkt

Das LoC-Limit (250) reicht ohne Override. *(Der Plan-Agent berichtet getrennte Budgets für
Produktiv- und Testcode à 250/500 aus dem Gate-Quellcode — **nicht nachgeprüft**, da die
Schätzung ohnehin unter dem strengeren Wert aus CLAUDE.md liegt.)*

### Technical Approach

**F1 `preview_service`** — `now_utc` wird **Pflichtparameter** (Regel 3). Kosten ausgezählt:
3 Produktiv-Aufrufer (alle in derselben Datei, `:324/:351/:377`) und 5 direkte Test-Aufrufe
(`tests/tdd/test_epic_140_preview_endpoints.py:89,456,503,518,532`). Die 14 Testdateien, die
nur die öffentlichen `render_*_preview`-Methoden benutzen, sind **nicht** betroffen.
Zusätzlich entfällt die zweite Zeitauflösung bei `:223` — das eine `now_utc` speist beide.

**Zwei Zonen-Auflösungen bleiben bestehen, und das ist Absicht:** `trip_local_today` löst über
`anchor_tz` die Zone der Etappe am **Weltzeit**-Tag auf; `trip_tz` in `_build_report`
(`:170`) löst die Zone der **Ziel**-Etappe auf. Sie beantworten verschiedene Fragen (welcher
Tag ist „heute" vs. welche Zone rendert diesen Tag) und können an einer Etappengrenze
auseinanderfallen. Das ist die bereits PO-akzeptierte Näherung aus `anchor_tz` („Known
Limitation, PO 2026-08-10"), die der Versandpfad genauso lebt. **Die Spec benennt das
ausdrücklich, statt stillschweigend Gleichheit zu unterstellen.**

**F2 `compare_preview_service`** — Zone über `first_resolvable_tz(locations)` in `_prepare()`
auflösen (die Orte stehen bei `:147` fest, der Aufruf folgt bei `:148`), `now_utc` als
Pflichtparameter. Kosten: 1 Produktiv-Aufrufer, **0 Test-Aufrufer**. Damit spiegelt die
Vorschau exakt das Muster, das der Compare-**Versand** seit S5b nutzt
(`scheduler_dispatch_service.py:441-442`) — Parität entsteht, sie bricht nicht.

**F3–F5 `run_comparison`** — Zone aus `selected` (steht bei `:41/:44` fest), dann **Stunde und
Tag aus derselben Ortszeit**:
```python
zone = first_resolvable_tz(selected, context_label="Sofort-Vergleich")
local_now = local_dt(datetime.now(timezone.utc), zone)
td = local_now.date() if local_now.hour < 14 else local_now.date() + timedelta(days=1)
```
`now_utc` bleibt **funktionsintern** — ein FastAPI-Query-Handler ist kein sinnvoller Ort für
einen Pflichtparameter, den kein Aufrufer von außen setzen kann. **Alle drei Funde müssen im
selben Commit fallen** (Ordinal-Risiko, s. Risiken).

**F6 `dict_to_comparison_result`** — ersatzlos entfernen. Der `hasattr`-Test zieht mit; ohne
die Anpassung wird er laut rot, meldet sich also selbst.

**F7 `_compute_next_send`** — `tz` durchreichen, Quelle ist das bereits aufgelöste `header_tz`.
`_render_abo_footer` und `_compute_next_send` haben je genau **einen** Aufrufer, `local_dt` ist
bereits importiert, und die **öffentliche Signatur von `render_compare_html`/
`render_compare_email` bleibt unangetastet** — keine der ~90 Testdateien, die diese Funktionen
aufrufen, ist betroffen. Günstigste Fundstelle der Scheibe.

**F8 `tools/weather_validation.py:288`** — kein Fix, sondern eine begründete Zeilen-Ausnahme
im Muster `# gz-main-path:` (#1409). Begründung ist am Code belegt: Das Werkzeug fragt seine
Referenzdaten selbst ausdrücklich mit `"timezone": "UTC"` ab (`:31`), um die unverfälschte
Anbieter-Antwort gegen die ortszeit-transformierte Pipeline zu halten. Ein Ortstag-Default
erzeugte einen Widerspruch **innerhalb desselben Skripts**. Sie wird **jetzt** eingetragen,
damit sie nicht ein sechstes Mal durch die Restliste fällt.

### Nachweisführung

- **Vorbedingungs-Anker ist inzwischen geteilt:** `_anker(now_utc, zone, erwarteter_ortstag)`
  liegt seit #1795 in `tests/tdd/conftest.py:88-109` — S5c importiert ihn, statt die
  S5a-Inline-Fassung zu kopieren.
- **Trip-Fixtur mit zwei Zonen:** `trip_two_zones` (`tests/tdd/conftest.py:56-76`,
  Wellington UTC+12 / Korsika UTC+2).
- **Ort mit exotischer Zone:** `SavedLocation(..., timezone=None)` mit Koordinaten, die
  `tz_for_coords` auflöst — Muster aus `tests/tdd/test_compare_local_time_basis.py:88-92`;
  für einen großen Versatz Pago Pago (`lat=-14.28, lon=-170.70`, UTC−11) aus
  `tests/tdd/test_befehlspfade_folgen_ortszone.py:56-57`.
- **Parameter gegen Systemuhr** (S5a-Befund F001) ist Pflicht für F1 und F2, weil beide einen
  Pflichtparameter bekommen: `freeze_time(X)` gegen `now_utc=Y`, Muster in
  `tests/tdd/test_befehlspfade_folgen_ortszone.py:591-652`. Für F7 ist die Probe strukturell
  unmöglich (kein exponierter Parameter) — dort trägt der Vorbedingungs-Anker allein.
- **Golden-Test-Risiko am Footer gemessen, nicht vermutet:** Der einzige Footer-Test
  (`tests/tdd/test_issue_1110_compare_mail_v2.py:680-698`) prüft nur die Anwesenheit der
  Beschriftung und die Abwesenheit des `—`-Platzhalters, keine Datumszeichenkette und kein
  `freeze_time`. Er bricht durch die Umstellung nicht.

### Risiken

1. **Ordinal-Verschiebung bei drei Funden in einer Funktion.** `run_comparison::0/1/2` teilen
   sich einen Funktionsraum; das Ordinal ist der zeilensortierte Index
   (`tests/test_output_timezone_guard.py:279-280`). Werden nur zwei behoben, meldet der
   Wächter den dritten gleichzeitig als veraltet **und** als neuen Verstoß.
2. **Der Löschpfad zieht Tests mit.** `dict_to_comparison_result` zu entfernen erfordert die
   Anpassung des `hasattr`-Tests. Der Endpunkt bleibt, also bleiben seine zwei Tests
   unangetastet.
3. **Die Testfläche liegt zu 23/24 in Mitteleuropa** — jede Fixtur muss ausdrücklich eine
   Zone wählen, in der Ortstag und Servertag auseinanderfallen, und der Anker muss das
   **zuerst** messen.

### Nebenbefund (nicht in dieser Scheibe)

Footer und Compare-**Versand**-Zieltag lösen „erster Ort" verschieden auf
(`location_tz(locations[0])` vs. `first_resolvable_tz(locations)`) und divergieren, wenn der
erste Ort keine auflösbare Zone trägt. Beides ist für sich regelkonform — AC-4 für die
Anzeige, #1726 AC-15 für die Fälligkeit. Ob dieselbe Mail zwei Tagesbegriffe tragen darf, ist
eine eigene Frage und gehört nicht in eine Zeitzonen-Aufräumscheibe. **Kein Muster A, in
keinem Wächter** → eigener Befund.

### Open Questions

Keine blockierenden. Die im Kontext offenen Punkte sind entschieden: Endpunkt bleibt (Go-Proxy
belegt), Kopfzeile bleibt (AC-4 belegt), `dict_to_comparison_result` entfällt (0 Aufrufer),
`weather_validation` bekommt eine Ausnahme statt eines Fixes. Alle vier stehen in der Spec zur
PO-Freigabe.

## Wächter-Restliste (Stand nach S5b)

59 Einträge gesamt: **14 × Muster A**, 23 × `raw_astimezone`, 2 × dauerhaft, 20 ×
aufrufseitig abgesichert.

Die 14 offenen Muster-A-Einträge: `api/routers/compare.py` (3), `compare_html.py` (1),
`compare_preview_service.py` (1), `comparison_engine.py` (1), `preview_service.py` (1) — das
sind die **sieben von S5c** — sowie `api/routers/debug.py` (1), `gpx_processing.py` (3),
`massif_closure.py` (2), `meteo_forets.py` (1) — die **sieben von S5d**.

**Nach S5c und S5d ist die Muster-A-Liste leer.** Es bleiben die 23 `raw_astimezone`-Einträge,
der Detektor Muster 3, die ungescannten Stellen (`openmeteo.py`, `tools/weather_validation.py`)
und das Frontend — alles S5e.
