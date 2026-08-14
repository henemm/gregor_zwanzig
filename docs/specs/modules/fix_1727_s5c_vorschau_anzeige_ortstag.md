---
entity_id: fix_1727_s5c_vorschau_anzeige_ortstag
type: bugfix
created: 2026-08-14
updated: 2026-08-14
status: draft
version: "1.0"
tags: [timezone, preview-service, compare-preview-service, compare-router, comparison-engine, compare-html, issue-1727, issue-1722, adr-0044, adr-0051]
workflow: fix-1727-s5c-vorschau-anzeige
---

# Fix #1727 S5c — Vorschau, Anzeige, Sofort-Vergleich folgen dem Ortstag

## Approval

- [x] Approved — PO-Freigabe 2026-08-14 („go")

## Purpose

Sieben Fundstellen in fünf Dateien bestimmen den Kalendertag der Trip- und Compare-Vorschau
sowie des Sofort-Vergleichs (`GET /api/compare`) weiterhin über die Serveruhr
(`date.today()`/`datetime.now()` ohne Zone) statt über den Ortstag der Tour bzw. des
Preset-Orts — ein Verstoß gegen die bereits akzeptierte ADR-0044. Anders als S5b (Versandpfade)
wirken die Fundstellen dieser Scheibe primär auf **Vorschau- und Anzeige-Pfade** — mit einer
Ausnahme: `compare_html.py::_compute_next_send` sitzt im Footer einer tatsächlich versendeten
Ortsvergleichs-Mail. Diese Scheibe schließt sechs der sieben Fundstellen, indem sie an jeder den
geteilten Baustein `trip_local_today(trip, now_utc)` bzw. `first_resolvable_tz(locations)`
einsetzt — keine eigene Kopie der Zonen-Auflösung. Die siebte Fundstelle
(`dict_to_comparison_result`) wird ersatzlos entfernt, weil sie keinen Aufrufer hat.

Zusätzlich entscheidet diese Scheibe zwei Produktfragen, die das Kontext-Dokument als offen
markiert hatte, aber der `analysis-challenger` am Code widerlegt hat: `GET /api/compare` bleibt
bestehen (Go-Proxy `CompareProxyHandler` verdrahtet ihn öffentlich, `internal/router/router.go:156`),
und die Kopfzeilen-Zeitbasis der Compare-Mail (`location_tz(locations[0].location)`) bleibt
unangetastet (wörtliche Umsetzung von #1378 AC-4). Beide sind damit keine offenen Fragen mehr,
sondern in dieser Spec entschiedener Rahmen.

## Source

- **File:** `src/services/preview_service.py`
  **Identifier:** `_resolve_target_date` (Zeile 84, Verstoß Zeile 94), `_build_report`
  (Zeile 120, zweite Zeitauflösung Zeile 223)
- **File:** `src/services/compare_preview_service.py`
  **Identifier:** `_resolve_target_date` (Modulfunktion, Zeile 255, Verstoß Zeile 258),
  `_prepare` (Zeile 129, Orte stehen bei Zeile 147 fest, Aufruf folgt Zeile 148)
- **File:** `api/routers/compare.py`
  **Identifier:** `run_comparison` (Zeile 26, drei Verstöße Zeile 53/55/58)
- **File:** `src/services/comparison_engine.py`
  **Identifier:** `dict_to_comparison_result` (Zeile 394–439, Verstoß Zeile 407) — wird entfernt
- **File:** `src/output/renderers/email/compare_html.py`
  **Identifier:** `_compute_next_send` (Zeile 1438, Verstoß Zeile 1443), `_render_abo_footer`
  (Zeile 1457, einziger Aufrufer Zeile 1670), `render_compare_html` (Zeile 1526, `header_tz`
  bereits aufgelöst Zeile 1604)
- **File:** `tools/weather_validation.py`
  **Identifier:** Punkt-Validierungsmodus, Zeile 288 (Zeilen-Ausnahme, kein Fix)
- **Zonen-Auflösung (unverändert nutzen):** `src/services/trip_day.py::trip_local_today(trip,
  now_utc)` (Zeile 90–96) und `::anchor_tz` (Zeile 55–71), `src/utils/timezone.py::
  first_resolvable_tz(locations, context_label="")` (Zeile 77–99), `::local_dt(dt, tz)`
  (Zeile 109–111)
- **Öffentlicher Aufrufer von `GET /api/compare` (Go-Seite, unverändert):**
  `internal/router/router.go:156` (`handler.CompareProxyHandler`), `internal/handler/proxy.go:73-100`
- **Zeilennummern gemessen am Basis-HEAD `e2b5269b`** (2026-08-14); vgl. ADR-0044s eigene Lehre
  aus veralteten Zeilenangaben — die `KNOWN_VIOLATIONS`-Kommentare im Wächter selbst tragen zum
  Teil noch ältere Zeilennummern (`:1377` statt der aktuellen `:1443` bei `compare_html.py`), das
  ist normale Drift und kein Fund dieser Scheibe.

## Estimated Scope

- **LoC:** Produktivcode ~+50/−60 (Löschungen überwiegen an einer Stelle — `comparison_engine.py`
  verliert ~45 Zeilen), Testcode ~+200 (Zahlen aus der Kartierung übernommen, nicht neu
  geschätzt). Das LoC-Limit (250) reicht ohne Override.
- **Files:** 8 laut Kartierung (5 Fundstellendateien inkl. Löschziel, 1 Wächterdatei MODIFY,
  1 Strukturtestdatei MODIFY, 1 Werkzeugdatei MODIFY) plus neue Verhaltenstestdatei(en) und
  mechanisch mitgezogene Bestandstestdateien (s. u.)
- **Effort:** medium — Risiko laut Kartierung **MEDIUM** (eine Fundstelle wirkt auf versendete
  Mails, drei auf einen öffentlich erreichbaren Endpunkt)

**Direkt am Code nachgemessen, nicht im Kontext-Dokument beziffert:** `_build_report`
(`preview_service.py:120`) verliert seine eigene `jetzt_utc = datetime.now(timezone.utc)`
(Zeile 223) und bekommt `now_utc` als Pflichtparameter — zusätzlich zu den 3 Produktiv-Aufrufern
(`:325/:352/:378`, dieselben drei Stellen wie bei `_resolve_target_date`) binden das neun
Bestandstest-Aufrufstellen in sechs Dateien: `tests/unit/test_preview_night_block.py` (3×,
Zeile 221/265/309), `tests/tdd/test_thunder_night_addendum_parity.py` (1×, Zeile 233),
`tests/tdd/test_sms_preview_matches_sent.py` (1×, Zeile 82),
`tests/tdd/test_epic_140_preview_endpoints.py` (2×, Zeile 471/486),
`tests/tdd/test_preview_parity_without_outlook.py` (1×, Zeile 170),
`tests/tdd/test_preview_render_options_parity.py` (1×, Zeile 108) — je eine mechanische
`now_utc=`-Ergänzung, analog zum S5b-Muster „~20 Bestandstestdateien, je eine Zeile".

### Affected Files

| Datei | Änderung | Beschreibung |
|---|---|---|
| `src/services/preview_service.py` | MODIFY | `_resolve_target_date` nimmt `now_utc` (Pflicht) und rechnet über `trip_local_today` statt `date.today()`; `_build_report` erbt dasselbe `now_utc` statt der eigenen Auflösung bei `:223` — beide Funktionen speist EIN `now_utc`, das jeder der drei öffentlichen `render_*_preview`-Methoden einmal bindet |
| `src/services/compare_preview_service.py` | MODIFY | `_resolve_target_date(given, locations, now_utc)`; Zone über `first_resolvable_tz(locations)`, aufgelöst in `_prepare()` aus den dort bereits geladenen Orten (`:147`); `given is not None`-Zweig unverändert |
| `api/routers/compare.py` | MODIFY | `run_comparison`: alle drei Funde (Stunde, Zieltag heute, Zieltag morgen) im selben Commit auf `first_resolvable_tz(selected)` + `local_dt(...)` umgestellt; `now_utc` bleibt funktionsintern (Query-Handler, kein sinnvoller externer Pflichtparameter); Endpunkt selbst bleibt bestehen |
| `src/services/comparison_engine.py` | DELETE | `dict_to_comparison_result` (`:394-439`) ersatzlos — 0 Aufrufer im gesamten Repo (Volltextsuche, Definition ausgenommen) |
| `src/output/renderers/email/compare_html.py` | MODIFY | `_compute_next_send` und `_render_abo_footer` bekommen `tz` als Parameter; Quelle ist das in `render_compare_html` bereits aufgelöste `header_tz` (`:1604`) — analog zum bestehenden Muster `render_undelivered_html(undelivered, tz=header_tz)` (`:1665`). Öffentliche Signatur von `render_compare_html`/`render_compare_email` bleibt unangetastet |
| `tests/refactor/test_epic_129a_1_module_structure.py` | MODIFY | `hasattr(mod, "dict_to_comparison_result")`-Zeile (`:45-46`) entfällt bzw. wird auf Abwesenheit geprüft |
| `tools/weather_validation.py` | MODIFY | begründete Zeilen-Ausnahme (`:288`) im Muster `# gz-main-path:` (#1409), kein Verhaltens-Fix |
| `tests/test_output_timezone_guard.py` | MODIFY | sieben `KNOWN_VIOLATIONS`-Einträge entfallen (s. AC-7) |
| `docs/adr/0044-kalendertage-folgen-der-ortszeit.md` | MODIFY | „Umgesetzt"/„Noch nicht umgesetzt" nachziehen: die Restliste „Vorschau, Werkzeuge" (`:169-174`) nennt aktuell `preview_service._resolve_target_date`, `api/routers/debug.py` UND `tools/weather_validation.py` in einem Satz — nach dieser Scheibe gehört nur noch `api/routers/debug.py` dorthin (S5d), `weather_validation.py` trägt eine dokumentierte Ausnahme statt offen zu sein |
| ~6 Bestandstestdateien (`_build_report`-Aufrufer) | MODIFY | 9 Aufrufstellen, je eine Zeile `now_utc=` ergänzt (s. o.) |
| `tests/tdd/test_<verhalten>.py` | CREATE | Verhaltenstests aller sieben Fundstellen inkl. Vorbedingungs-Anker, nach Verhalten benannt |

## Dependencies

| Entity | Type | Purpose |
|---|---|---|
| `services.trip_day.trip_local_today(trip, now_utc)` | module function | Ersetzt `date.today()` an F1 (`preview_service`) |
| `utils.timezone.first_resolvable_tz(locations, context_label="")` | module function | Zonenwahl bei mehreren Compare-Orten (F2, F3–F5) — dasselbe Muster wie #1726 und S5b |
| `utils.timezone.local_dt(dt, tz)` | module function | Ortszeit aus `now_utc` + aufgelöster Zone (F2, F3–F5, F7) |
| `header_tz` (bereits aufgelöst in `render_compare_html`, `:1604`) | local variable | Quelle für F7 — keine zweite Auflösung (ADR-0044) |
| ADR-0044 (Akzeptiert) | decision | Verlangt Ortstag statt Servertag; die Restliste „Vorschau, Werkzeuge" wird durch diese Scheibe präzisiert (Nebenbefund: die Liste war zum fünften Mal unvollständig) |
| ADR-0051 (Vorgeschlagen), Regel 2 + Regel 3 | decision | Regel 2 (Zone gehört an die Daten) begründet `first_resolvable_tz`/`trip_local_today` statt Server-/Prozesszone; Regel 3 (keine Umgebungsuhr) begründet `now_utc` als Pflichtparameter an F1/F2 |
| `CompareProxyHandler` (`internal/handler/proxy.go:73-100`), `internal/router/router.go:156` | consumer (Go) | Belegt den öffentlichen Aufrufer von `GET /api/compare` — der Endpunkt bleibt, wird nicht entfernt |
| `tests/refactor/test_epic_129a_1_module_structure.py::test_comparison_engine` | guard | Hasattr-Test auf `dict_to_comparison_result` — wird mit F6 angepasst, sonst rot |
| `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` | guard | Die sieben Einträge müssen im selben Commit entfallen, sonst rot (s. AC-7) |
| `docs/specs/modules/fix_1727_s5a_befehlspfade_ortstag.md`, `…s5b_versandpfade_ortstag.md` | pattern | Vorgängerscheiben — Vorbild für Aufbau, Nachweisform, `_anker` |
| `_anker` (`tests/tdd/conftest.py:88-109`), `trip_two_zones` (`:56-76`) | test fixture | Geteilter Vorbedingungs-Anker und Zwei-Zonen-Trip-Fixtur (seit #1795) — keine dritte Kopie |
| `SavedLocation(..., timezone=None)` mit Pago-Pago-Koordinaten (`lat=-14.28, lon=-170.70`) | test fixture | Muster aus `tests/tdd/test_befehlspfade_folgen_ortszone.py:56-57` — Ort mit über `tz_for_coords` aufgelöster exotischer Zone, für F2/F3-F5 |

## Implementation Details

Ein Muster, sechsmal angewandt (F6 ist Löschung, kein Umbau) — kein neuer Baustein:

| Lage am Fundort | Vorgehen | Fundstellen |
|---|---|---|
| `trip` vorhanden, drei öffentliche Aufrufer im selben Modul | `now_utc` Pflichtparameter in `_resolve_target_date` UND `_build_report`, `trip_local_today(trip, now_utc)` | F1 |
| Mehrere Orte statt eines Trips, Orte vor dem Datumsaufruf bereits geladen | `now_utc` Pflichtparameter, Zone über `first_resolvable_tz(locations)` | F2 |
| Weder `trip` noch persistente Zone am Fundort, FastAPI-Query-Handler | `now_utc` bleibt funktionsintern, Zone aus den bereits aufgelösten `selected`-Orten | F3–F5 |
| Funktion ohne Aufrufer | ersatzlos entfernen, abhängigen Struktur-Test mitziehen | F6 |
| Zone bereits eine Ebene höher aufgelöst (`header_tz`) | `tz` durchreichen statt zweiter Auflösung | F7 |
| Werkzeug fragt seine Referenz selbst mit `"timezone": "UTC"` ab | begründete Zeilen-Ausnahme statt Fix | F8 |

**F1 — `preview_service.py`, EIN `now_utc` speist zwei Funktionen:**
```python
def _resolve_target_date(self, trip: "Trip", given_date: str | None, now_utc: datetime) -> date:
    if given_date:
        return date.fromisoformat(given_date)
    today = trip_local_today(trip, now_utc)
    ...  # unveraendert: sortierte Etappensuche ab `today`

def _build_report(self, trip: "Trip", target: date, report_type: str, now_utc: datetime,
                   demo: bool = False):
    ...
    # Zeile 223 entfaellt: kein eigenes `jetzt_utc = datetime.now(timezone.utc)` mehr
    if segment_weather and render_options.show_multi_day_trend:
        trend_result = scheduler._build_stage_trend(trip, target, now_utc=now_utc, tz=trip_tz)
```
Alle drei öffentlichen Methoden (`render_email_preview`, `render_sms_preview`,
`render_telegram_preview`) binden `now_utc = datetime.now(timezone.utc)` einmal und reichen es an
beide Aufrufe durch — damit bestimmen `_resolve_target_date` (welche Etappe ist "heute") und
`_build_report`s Trend-/Ausblicks-Beschaffung (welcher Tag gilt beim Wetterabruf) garantiert
denselben Ortstag, statt zweier potenziell auseinanderfallender `date.today()`-Momentaufnahmen.

**F2 — `compare_preview_service.py`, Zone aus bereits geladenen Orten:**
```python
def _resolve_target_date(given: str | date | None, locations: list, now_utc: datetime) -> date:
    if given is None or given == "":
        zone = first_resolvable_tz(locations, context_label="Compare-Vorschau")
        return local_dt(now_utc, zone).date()
    if isinstance(given, date):
        return given
    return date.fromisoformat(str(given))

# in _prepare():
locations = self._resolve_locations(preset, user_id=user_id)          # :147, unveraendert
resolved_date = _resolve_target_date(target_date, locations, datetime.now(timezone.utc))
```
Damit spiegelt die Vorschau exakt das Muster, das der Compare-**Versand** seit S5b nutzt
(`scheduler_dispatch_service.py:441-442`) — Parität entsteht, sie bricht nicht. 0 Test-Aufrufer
(`_resolve_target_date` wird nur aus `_prepare()` heraus aufgerufen).

**F3–F5 — `api/routers/compare.py::run_comparison`, alle drei Funde im selben Commit:**
```python
if target_date:
    td = date.fromisoformat(target_date)
else:
    zone = first_resolvable_tz(selected, context_label="Sofort-Vergleich")
    local_now = local_dt(datetime.now(timezone.utc), zone)
    td = local_now.date() if local_now.hour < 14 else local_now.date() + timedelta(days=1)
```
`now_utc` bleibt funktionsintern — ein FastAPI-Query-Handler ist kein sinnvoller Ort für einen
von außen gesetzten Pflichtparameter. Werden nicht alle drei Funde gemeinsam behoben, verschiebt
sich das Ordinal der verbleibenden im Wächter (Risiko, s. u.) — deshalb ist die Atomarität selbst
Teil von AC-3.

**F6 — `comparison_engine.py`, ersatzlose Löschung:**
`dict_to_comparison_result` (`:394-439`) entfällt vollständig. Der zugehörige Struktur-Test
(`tests/refactor/test_epic_129a_1_module_structure.py:45-46`) prüft danach NICHT mehr
`hasattr(mod, "dict_to_comparison_result") == True`; entweder die Assertion entfällt oder sie
wird auf `False` gedreht — beides macht die Absicht (Symbol existiert nicht mehr) explizit statt
den Test kommentarlos still zu lassen.

**F7 — `compare_html.py`, `tz` durchreichen statt zweiter Auflösung:**
```python
def _compute_next_send(schedule, weekday, tz) -> Optional[str]:
    if not schedule:
        return None
    today = local_dt(datetime.now(timezone.utc), tz).date()
    ...  # Rest unveraendert

def _render_abo_footer(preset_name, preset_schedule, preset_weekday, location_count, sig, tz) -> str:
    next_send = _compute_next_send(preset_schedule, preset_weekday, tz) or "—"
    ...

# in render_compare_html():
abo_html = _render_abo_footer(preset_name, preset_schedule, preset_weekday, len(locations), sig,
                               header_tz)
```
`header_tz` liegt bei Aufruf bereits vor (`:1604`) — exakt das Muster, das
`render_undelivered_html(undelivered, tz=header_tz)` (`:1665`) schon nutzt. `_render_abo_footer`
und `_compute_next_send` haben je genau einen Aufrufer; die öffentliche Signatur von
`render_compare_html`/`render_compare_email` ändert sich nicht — keine der ~90 Testdateien, die
diese Funktionen aufrufen, ist betroffen.

**F8 — `tools/weather_validation.py:288`, begründete Ausnahme statt Fix:**
```python
if args.lat and args.lon:
    target_date = args.date or date.today().isoformat()  # gz-main-path: Werkzeug fragt seine
    # Referenzdaten selbst mit "timezone": "UTC" ab (Zeile 31) -- ein Ortstag-Default erzeugte
    # einen Widerspruch INNERHALB desselben Skripts.
```
Kein Code-Verhalten ändert sich; die Zeile trägt danach eine für den Wächter lesbare Begründung
(`tools/` liegt außerhalb von dessen Geltungsbereich, die Ausnahme ist trotzdem dokumentiert,
damit sie nicht ein sechstes Mal unvollständig durch eine ADR-Restliste fällt).

## Nicht in dieser Scheibe

- **Die Kopfzeilen-Auflösung `location_tz(locations[0].location)`** (`compare_html.py:1604`)
  bleibt unverändert — sie ist die wörtliche Umsetzung von PO-freigegebenem AC-4 aus #1378
  (`docs/specs/modules/issue_1378_compare_zeitbasis.md:262-271`): Zeitbasis ist der
  **erstgenannte** Ort der konfigurierten Reihenfolge, ausdrücklich nicht der erste auflösbare.
  Sie umzustellen wäre eine Regression gegen AC-4, kein Fix.
- **Die Divergenz zwischen Footer-Zone und Compare-Versand-Zieltag.** `_compute_next_send`
  bekommt mit F7 `header_tz` (= `location_tz(locations[0])`, fällt bei nicht auflösbarem ersten
  Ort still auf UTC), während der Compare-**Versand** seinen Zieltag über
  `first_resolvable_tz(locations)` (überspringt einen nicht auflösbaren ersten Ort) bestimmt
  (`scheduler_dispatch_service.py:441`). Beide sind für sich regelkonform — AC-4 für die
  Kopfzeile/den Footer, #1726 AC-15 für die Fälligkeit. Sie divergieren nur, wenn der erste Ort
  keine auflösbare Zone trägt. Ob dieselbe Mail zwei verschiedene "erster Ort"-Auflösungen tragen
  darf, ist eine eigene fachliche Frage und gehört nicht in diese Zeitzonen-Aufräumscheibe.
- **`api/routers/debug.py`** (Debug-Auslöser für Radar-Alarme) und **`gpx_processing.py`/
  `massif_closure.py`/`meteo_forets.py`** — die verbleibenden sieben offenen Muster-A-Einträge
  des Wächters, S5d.
- **Der Wächter bleibt blind für `datetime.utcnow()`** (`_AMBIENT_CLOCK_ATTRS = {"now", "today"}`,
  `tests/test_output_timezone_guard.py:145`) — für die fünf S5c-Dateien nachgemessen: keine
  `utcnow()`-Stelle vorhanden, der Detektor selbst wird hier nicht erweitert (S5e).
- **`send_on_demand_report`** (`trip_report_scheduler.py:966`) und die Go-Seite — unverändert aus
  S5b übernommene offene (b)-Folgescheibe bzw. eigener Befund außerhalb des Epics.

## Zwei bewusst nebeneinander bestehende Zonen-Auflösungen in `preview_service`

`_resolve_target_date`/`_build_report` nutzen nach dieser Scheibe **zwei** Zonen-Auflösungen, und
das ist Absicht, keine Inkonsistenz:

- `trip_local_today(trip, now_utc)` (über `anchor_tz`, `trip_day.py:55-71`) beantwortet „welcher
  Kalendertag ist gerade?" — Zone ist die der Etappe am **Weltzeit**-Tag. Das ist der bewusst
  gewählte Anker, weil die naive Alternative „erste Etappe der Tour" bei einer Tour über mehrere
  Zonen bis zu zehn Stunden danebenlag (`anchor_tz`-Docstring). Restfehler: die Zonendifferenz
  zweier **benachbarter** Etappen an einem Wechseltag — „Known Limitation, PO 2026-08-10",
  unverändert akzeptiert.
- `trip_tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)`
  (`_build_report:170`) beantwortet eine andere Frage: „in welcher Zone wird die **Ziel**-Etappe
  gerendert?" — Zone der ersten Segment-Koordinate von `target`, nicht der Weltzeit-Etappe.

Beide Fragen können an einer Etappengrenze auseinanderfallen; das ist dieselbe Näherung, die der
Versandpfad seit S5b lebt. **Diese Spec benennt das ausdrücklich** — eine stillschweigende
Gleichsetzung beider Zonen wäre der Fehler, den diese Scheibe nicht macht.

## Nachweisführung

Vollständig **offline** belegbar (Kern-Schicht): `freeze_time` + In-Memory-`Trip`/`Stage`/
`Waypoint`/`SavedLocation`-Fixturen. Für F1–F6 keine Staging-Mail nötig (Vorschau- bzw.
Struktur-Pfad). Für F7 genügt der Render-Aufruf gegen den fertigen HTML-String — kein Versand
nötig, geprüft wird die Tagesbestimmung, nicht der Transport.

Verfügbare Mehrzonen-Fixturen (aus S5a/S5b übernommen, keine vierte Kopie):

- `trip_two_zones` (`tests/tdd/conftest.py:56-76`) — Wellington (UTC+12) + Korsika (UTC+2)
- `SavedLocation(..., timezone=None)` mit Koordinaten, die `tz_for_coords` auflöst (Muster
  `tests/tdd/test_compare_local_time_basis.py:88-92`); für einen großen Versatz Pago Pago
  (`lat=-14.28, lon=-170.70`, UTC−11) aus `tests/tdd/test_befehlspfade_folgen_ortszone.py:56-57`
- Vorbedingungs-Anker `_anker(now_utc, zone, erwarteter_ortstag)`
  (`tests/tdd/conftest.py:88-109`, seit #1795 geteilt) — S5c importiert ihn, statt eine eigene
  Fassung zu schreiben

**Parameter gegen Systemuhr** (Muster S5a-F001) ist **Pflicht überall dort, wo ein
Pflichtparameter entsteht** — F1 (`_resolve_target_date` UND `_build_report`) und F2
(`_resolve_target_date`): `freeze_time(X)` gegen `now_utc=Y` mit unterschiedlichen Ortstagen;
eine Implementierung, die den Parameter entgegennimmt, im Rumpf aber `date.today()` benutzt,
liefert den Ortstag von X und macht den Test rot. Ohne diese Probe ist „Parameter behalten, im
Rumpf ignoriert" strukturell nicht falsifizierbar (S5a-Befund F001).

**Für F3–F5 und F7 ist diese Probe strukturell unmöglich** — `now_utc` bleibt an beiden Stellen
funktionsintern (kein exponierter Parameter, den man der Uhr entgegenstellen könnte). Dort trägt
ausschließlich (a): unter `freeze_time` liefert eine Zone mit deutlichem Offset einen anderen
Ortstag als den Servertag — belegt durch den Vorbedingungs-Anker.

**Golden-Test-Risiko am Footer gemessen, nicht vermutet:** Der einzige Footer-Test
(`tests/tdd/test_issue_1110_compare_mail_v2.py:680-698`) prüft nur die Anwesenheit der
Beschriftung „Nächster Versand" und die Abwesenheit des `—`-Platzhalters, keine Datumszeichenkette
und kein `freeze_time`. Er bricht durch die F7-Umstellung nicht — der Nachweis für F7 muss
vollständig neu entstehen.

## Testbenennung

Testdateien nach Verhalten benennen, nicht nach Issue-Nummer — durchgesetzt von
`test_naming_gate.py`, das neue issue-nummerierte Testdateien hart blockiert. Kein
`test_issue_1727*`-Name. Vorschlag (analog S5a/S5b):
`tests/tdd/test_vorschau_anzeige_folgen_ortszone.py` als Sammel-Datei für alle sieben
Fundstellen; eine Aufteilung je Fundstelle ist ebenso zulässig.

## Expected Behavior

Beispiel: Eine Tour in Neuseeland (`Pacific/Auckland`, UTC+12), Server auf Weltzeit,
Abruf am 20.08.2026 um 14:00 UTC — am Ort ist es bereits der 21.08., 02:00 Uhr.

| Was der Nutzer tut | Bisher | Nach dieser Scheibe |
|---|---|---|
| Trip-Vorschau ohne Datum öffnen | Etappe des **20.08.** (Servertag) | Etappe des **21.08.** (Ortstag) |
| Ortsvergleichs-Vorschau ohne Datum öffnen | Vergleich für den **Servertag** | Vergleich für den **Ortstag des ersten auflösbaren Orts** |
| `GET /api/compare` ohne `target_date` | Schwelle „vor 14:00" an der **Serverstunde**, Tag vom Server — Stunde und Tag können aus verschiedenen Tagesbegriffen stammen | Stunde **und** Tag aus **derselben** Ortszeit |
| Vergleichs-Mail lesen, Fußzeile „Nächster Versand" | Datum vom **Servertag** berechnet, während die Kopfzeile derselben Mail bereits Ortszeit zeigt | Datum aus **derselben Zone wie die Kopfzeile** |

Unverändert bleibt jeder Aufruf **mit** ausdrücklichem Datum: Wer ein Datum angibt, bekommt
genau dieses — der `given is not None`-Zweig wird nicht angefasst.

## Acceptance Criteria

- **AC-1:** Given eine Trip-Vorschau (`render_email_preview`/`render_sms_preview`/
  `render_telegram_preview`, `preview_service.py`) wird OHNE explizites `target_date` für eine
  Tour in einer Zone mit deutlichem UTC-Offset aufgerufen (Fixtur `trip_two_zones`, Wellington
  UTC+12), sodass Ortstag und Servertag zum Aufrufzeitpunkt auseinanderfallen / When
  `_resolve_target_date(trip, given_date=None, now_utc)` (`:84`) die Etappe wählt und
  anschließend `_build_report(trip, target, report_type, now_utc, ...)` (`:120`) denselben
  `now_utc` für die Trend-/Ausblicks-Beschaffung verwendet / Then bestimmen BEIDE Funktionen
  „heute" über `trip_local_today(trip, now_utc)`, NICHT über je eine eigene
  `date.today()`-Auflösung — die zweite, bislang bei `:223` liegende Auflösung entfällt
  ersatzlos, ein einziges `now_utc` speist beide Entscheidungen.
  - Test: **Parameter gegen Systemuhr** (Muster S5a-F001) — `freeze_time(X)` gegen `now_utc=Y`
    mit unterschiedlichen Ortstagen derselben Trip-Zone; Assertion, dass das gewählte
    Vorschau-Datum dem Ortstag von Y folgt, nicht dem von X. Vorbedingungs-Anker `_anker` davor
    Pflicht.

- **AC-2:** Given eine Compare-Vorschau (`POST /api/preview/compare/{preset_id}`) wird OHNE
  explizites `target_date` für ein Preset mit mehreren Orten unterschiedlicher Zonen
  aufgerufen, dessen ERSTER konfigurierter Ort keine auflösbare Zone trägt / When `_prepare()`
  (`compare_preview_service.py:129`) die Orte auflöst (`:147`) und danach
  `_resolve_target_date(None, locations, now_utc)` (Modulfunktion, `:255`) aufruft / Then
  bestimmt die Funktion das Ergebnis über `first_resolvable_tz(locations)` (überspringt den
  unauflösbaren ersten Ort) und das übergebene `now_utc`, NICHT über `date.today()`; der
  `given is not None`-Zweig (explizites Datum von der UI) bleibt dabei unverändert.
  - Test: Parameter gegen Systemuhr (wie AC-1) plus Vorbedingungs-Anker, Fixtur mit zwei Orten
    (erster ohne auflösbare Zone, zweiter mit deutlichem Offset); Assertion auf das gelieferte
    Datum gegen die Zone des zweiten Orts.

- **AC-3:** Given `GET /api/compare` (öffentlich erreichbar über den Go-Proxy
  `CompareProxyHandler`, `internal/router/router.go:156`) wird OHNE `target_date` für
  `location_ids` aufgerufen, deren erster auflösbarer Ort in einer Zone liegt, in der die
  Ortszeit kurz vor bzw. kurz nach 14:00 Uhr steht, während die Serveruhr in einem anderen
  Fenster steht / When `run_comparison` (`api/routers/compare.py:26`, Verstöße `:53/:55/:58`)
  sowohl die 14:00-Schwelle als auch den Zieltag „heute"/„morgen" bestimmt / Then beruhen BEIDE
  Entscheidungen auf DERSELBEN Ortszeit (`local_dt(datetime.now(timezone.utc),
  first_resolvable_tz(selected))`) statt auf der naiven, zonenlosen Serveruhr — alle drei
  Fundstellen ändern sich im selben Commit; bliebe eine davon auf Servertag stehen, wäre die
  14:00-Schwelle in sich widersprüchlich (Stunde einer Zone, Tag einer anderen).
  - Test: zwei Szenarien unter `freeze_time` — Ortszeit 13:xx Uhr (→ `td` = heutiger Ortstag) und
    Ortszeit 14:xx Uhr (→ `td` = Ortstag + 1) — bei einer Serveruhr, die jeweils im anderen
    Fenster steht als die Ortszeit; Assertion auf `td` im JSON-Response von `run_comparison`.
    Vorbedingungs-Anker davor Pflicht.

- **AC-4:** Given `services.comparison_engine.dict_to_comparison_result` (`:394-439`) hat außer
  der eigenen Definition und dem Struktur-Test `tests/refactor/test_epic_129a_1_module_structure
  .py::test_comparison_engine` keinen Aufrufer in `src/`, `api/`, `tests/`, `frontend/`,
  `internal/`, `cmd/` (Volltextsuche, Definitionsstelle ausgenommen) / When die Funktion
  ersatzlos entfernt wird / Then gelingt `import services.comparison_engine` weiterhin,
  `hasattr(mod, "dict_to_comparison_result")` liefert `False`, und der Struktur-Test prüft NICHT
  mehr auf Anwesenheit, sondern auf Abwesenheit (oder die Assertion entfällt ersatzlos) — kein
  verbleibender Muster-A-Fund für eine tote Funktion.
  - Test: `tests/refactor/test_epic_129a_1_module_structure.py::test_comparison_engine`
    angepasst; `tests/test_output_timezone_guard.py::test_known_violations_only_shrink`/
    `::test_no_unlisted_output_timezone_violations` bleiben grün, nachdem der zugehörige Eintrag
    entfernt wurde.

- **AC-5:** Given eine versendete Ortsvergleichs-Mail, deren Kopfzeile bereits
  `header_tz = location_tz(locations[0].location)` aufgelöst hat (`compare_html.py:1604`), und
  deren Abo-Preset ein `weekly`- oder `daily`-Schedule trägt, in einer Zone mit deutlichem
  Offset zur Serveruhr / When `render_compare_html` über `_render_abo_footer` (`:1457`) den
  Footer-Text „Nächster Versand" via `_compute_next_send(schedule, weekday, tz)` (`:1438`)
  berechnet / Then erhält `_compute_next_send` `tz` als zusätzlichen Parameter, dessen Quelle
  DAS BEREITS AUFGELÖSTE `header_tz` ist (`local_dt(datetime.now(timezone.utc), tz).date()`
  statt `date.today()`), und `_render_abo_footer` reicht `tz` unverändert durch — analog zum
  bestehenden Muster `render_undelivered_html(undelivered, tz=header_tz)` (`:1665`). Die
  öffentliche Signatur von `render_compare_html`/`render_compare_email` bleibt unangetastet.
  - Test: Für F7 ist die Parameter-gegen-Systemuhr-Probe strukturell unmöglich (kein von außen
    exponierter Parameter) — stattdessen Vorbedingungs-Anker + `freeze_time` gegen eine Zone mit
    deutlichem Offset; Assertion auf das im gerenderten Footer-HTML enthaltene Datum, je einmal
    für `weekly`- und `daily`-Schedule.

- **AC-6:** Given `tools/weather_validation.py:288` löst
  `target_date = args.date or date.today().isoformat()` im Punkt-Validierungsmodus
  (`--lat`/`--lon` ohne `--date`) auf, während dasselbe Werkzeug seine Referenzdaten in
  `fetch_openmeteo` ausdrücklich mit `"timezone": "UTC"` abfragt (`:31`) / When diese Zeile im
  Zuge der Scheibe bewertet wird / Then bekommt sie KEINEN Verhaltens-Fix, sondern eine
  begründete Zeilen-Ausnahme im Muster `# gz-main-path:` (#1409) mit einer fachlichen Begründung
  von mindestens 15 sinnvollen Zeichen, die auf die UTC-Abfrage der Referenzdaten verweist — ein
  Ortstag-Default erzeugte sonst einen Widerspruch INNERHALB desselben Skripts (Validierungsziel
  UTC, Validierungs-Default Ortszeit).
  - Test: nicht automatisierbar — `tools/` liegt außerhalb des Geltungsbereichs von
    `tests/test_output_timezone_guard.py`; im QA-Bericht die Kommentarzeile am Fundort zitieren.

- **AC-7:** Given alle sechs umgestellten bzw. entfernten Fundstellen dieser Scheibe
  (`preview_service._resolve_target_date`, `compare_preview_service._resolve_target_date`,
  `api/routers/compare.py::run_comparison` dreifach, `comparison_engine.dict_to_comparison_result`,
  `compare_html._compute_next_send`) sind umgesetzt / When
  `tests/test_output_timezone_guard.py::test_known_violations_only_shrink` und
  `::test_no_unlisted_output_timezone_violations` laufen / Then sind die SIEBEN zugehörigen
  `KNOWN_VIOLATIONS`-Einträge entfernt: `api/routers/compare.py::run_comparison::0`,
  `::run_comparison::1`, `::run_comparison::2`,
  `src/output/renderers/email/compare_html.py::_compute_next_send::0`,
  `src/services/compare_preview_service.py::_resolve_target_date::0`,
  `src/services/comparison_engine.py::dict_to_comparison_result::0`,
  `src/services/preview_service.py::_resolve_target_date::0` — und beide Tests bleiben grün. Da
  alle drei `run_comparison`-Einträge im selben Commit entfallen (statt nur einzelne), entsteht
  KEINE Ordinal-Verschiebung für verbleibende Einträge derselben Funktion — anders als bei einer
  Teilbehebung (Risiko, s. u.).
  - Test: `tests/test_output_timezone_guard.py::test_known_violations_only_shrink`,
    `::test_no_unlisted_output_timezone_violations`.

- **AC-8:** Given eine neue Testfunktion dieser Scheibe behauptet, dass Ortstag und Servertag bei
  ihrer Fixtur auseinanderfallen — der Vorbedingungs-Anker ist Pflicht, keine Kür / When der Test
  seine Hauptzusicherung prüft / Then belegt er das ZUVOR mit dem geteilten Vorbedingungs-Anker
  `_anker(now_utc, zone, erwarteter_ortstag)` (`tests/tdd/conftest.py:88-109`) — ohne ihn ist die
  Hauptzusicherung strukturell nie falsifizierbar (#1726 F002). An F1 und F2 tritt zusätzlich die
  Parameter-gegen-Systemuhr-Probe aus AC-1/AC-2 hinzu, sie ersetzt den Anker nicht; an F3–F5 und
  F7 ist diese Probe strukturell unmöglich (kein exponierter Parameter) — dort trägt der Anker
  allein.
  - Test: nicht automatisierbar; im QA-Bericht zu belegen, dass jede neue Testfunktion dieser
    Scheibe den geteilten Anker importiert und aufruft (Muster: fix_1727_s5a/s5b AC-9).

## Known Limitations

- **Die Divergenz Footer-Zone vs. Compare-Versand-Zieltag bleibt offen.** Siehe „Nicht in dieser
  Scheibe" — eigene fachliche Frage, kein Zeitzonen-Bug im Sinne dieser Scheibe.
- **`api/routers/debug.py`, `gpx_processing.py`, `massif_closure.py`, `meteo_forets.py`** — die
  verbleibenden sieben Muster-A-Einträge des Wächters gehören zu S5d. Nach S5c und S5d ist die
  Muster-A-Liste vollständig leer.
- **Der Wächter bleibt blind für `datetime.utcnow()`.** Für die fünf Dateien dieser Scheibe
  nachgemessen: keine `utcnow()`-Stelle vorhanden. Der Detektor selbst (`_AMBIENT_CLOCK_ATTRS`)
  wird nicht erweitert — S5e.
- **Mehrzonen-Touren:** Restfehler = Zonendifferenz zweier benachbarter Etappen an einem
  Wechseltag. Unverändert bewusst offen (ADR-0044, PO-Entscheidung 2026-08-10, s. „Zwei
  Zonen-Auflösungen" oben).
- **`send_on_demand_report`** (`trip_report_scheduler.py:966`) und die Go-Seite (225 ×
  `time.Now()`) — unverändert aus S5b übernommene offene (b)-Folgescheibe bzw. eigener Befund
  außerhalb des Epics.
- **`tools/weather_validation.py`** bekommt mit dieser Scheibe erstmals eine dokumentierte
  Ausnahme statt eines stillen Fehlens in jeder ADR-Restliste; ein etwaiger sechster Fund an
  anderer Stelle desselben Werkzeugs ist damit nicht ausgeschlossen — nur diese eine Zeile ist
  geprüft.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0044 (Akzeptiert), ADR-0051 (Vorgeschlagen, Regel 2 + Regel 3)
- **Rationale:** Setzt die bereits akzeptierte ADR-0044-Entscheidung an sechs weiteren, in dessen
  Restliste teils fehlenden Stellen um und entfernt eine siebte (F6) als toten Code — kein
  offene Produktfrage, ein Bug gegen eine getroffene Entscheidung. Regel 2 aus ADR-0051 (Zone
  gehört an die Daten) begründet `first_resolvable_tz`/`trip_local_today` statt einer
  Server-/Prozesszone; Regel 3 (keine Umgebungsuhr) begründet `now_utc` als Pflichtparameter an
  F1/F2. An F3–F5 und F7 bleibt „jetzt" bewusst funktionsintern (kein sinnvoller externer
  Pflichtparameter möglich bzw. keine zweite Auflösung nötig, weil die Zone bereits vorliegt) —
  diese Scheibe trifft dazu keine neue Design-Entscheidung, sondern übernimmt die in der
  Kartierung getroffene Kosten-Nutzen-Abwägung.

## Changelog

- 2026-08-14: Spec erstellt nach Kartierung `docs/context/fix-1727-s5c-vorschau-anzeige.md`
  (Basis-HEAD `e2b5269b`), Vorbild `docs/specs/modules/fix_1727_s5b_versandpfade_ortstag.md`.
- 2026-08-14: Wächter-Restliste direkt gegen `tests/test_output_timezone_guard.py` nachgemessen:
  SIEBEN (nicht sechs) `KNOWN_VIOLATIONS`-Einträge sind von dieser Scheibe betroffen —
  deckungsgleich mit den sieben Fundstellen des Kontext-Dokuments (`api/routers/compare.py` ×3,
  `compare_html.py` ×1, `compare_preview_service.py` ×1, `comparison_engine.py` ×1,
  `preview_service.py` ×1).
- 2026-08-14: Zusätzliche, im Kontext-Dokument nicht bezifferte Testkosten direkt am Code
  nachgemessen: `_build_report` bekommt mit F1 ebenfalls `now_utc` als Pflichtparameter (nicht
  nur `_resolve_target_date`); neun Bestandstest-Aufrufstellen in sechs Dateien betroffen (s.
  Estimated Scope).
