---
entity_id: trip_empty_metric_selection
type: bugfix
created: 2026-07-31
updated: 2026-07-31
version: "1.0"
tags: [trip, shared, metrics, leerauswahl, bugfix]
---

<!-- Issue #1394 — Trip-Gegenstück zu #1366 (Ortsvergleich, ausgeliefert 2026-07-26/27) -->

# Leerauswahl heißt leer (Trip-Briefing)

## Approval

- [x] Approved — PO-Freigabe 2026-07-31 („go"), alle 8 ACs unverändert.

## Purpose

Wählt ein Nutzer im Trip alle Wettergrößen bewusst ab, zeigt das Briefing an
mehreren Stellen trotzdem Werte — teils Größen, die er nie ausgewählt hat.
Die im Ortsvergleich bereits gebaute Regel (#1366) wird auf die Trip-Seite
übertragen, nicht neu erfunden:

> Feld fehlt = Altbestand → bisheriges Verhalten (alle Größen).
> Feld vorhanden, auch leer = bewusste Nutzerwahl → wird geehrt.

Anders als beim Ortsvergleich speichert der Trip die Auswahl nicht als Liste
aktiver Schlüssel, sondern als vollständige Metrik-Liste mit `enabled`-Flags.
„Leer" entsteht daher auf zwei Wegen, die heute ununterscheidbar
zusammenfallen: **Fall A** (Altbestand — `display_config.metrics` fehlt
ganz, `dc.metrics == []`) und **Fall B** (bewusste Leerauswahl —
`dc.metrics` hat Einträge, alle mit `enabled=False`). Gemessen am
Produktivdatenstand 2026-07-31: 13 von 19 Briefings sind Fall A (davon 5
echte Nutzer-Touren) — diese dürfen sich unter keinen Umständen ändern.

## Kritischer Befund: Warum die vier gemeldeten Fundstellen allein nicht reichen

Die vier ursprünglich gemeldeten Fundstellen (T1 `html.py`, T2 `plain.py`,
T2b `compact.py`, T3 `day_comparison.py`) beheben jeweils eine Ersatzliste
bzw. einen Falsy-Check — funktionieren aber nur, wenn `dc.metrics`, wie es
in diesen Dateien ankommt, Fall A noch von Fall B unterscheidet. Das ist für
den tatsächlichen Versandweg (Morgen-/Abendbriefing) **nicht der Fall**:

`TripReportFormatter.format_email()` (`trip_report.py:113-119`) ersetzt
`dc.metrics` für `report_type in ("morning", "evening")` **immer** durch das
Ergebnis von `dc.get_metrics_for_channel("email", report_type)`
(`models.py:650-682`), bevor `render_email()` — und darüber `render_html()`,
`render_plain()`, `render_compact()` (`email/__init__.py:123-181`, Compact-
Zweig `:96-113`) — überhaupt aufgerufen wird. Diese Kaskade fällt (keine
Konfiguration hat `per_channel_layouts`/`per_report_layouts` gesetzt, 0 von
19 Briefings) auf Ebene 3 zurück: `get_metrics_for_report_type()` →
`_filter_metrics_by_report_type()` (`models.py:554-581`), die schlicht nach
`mc.enabled` filtert. Für Fall A (`dc.metrics == []`) liefert das eine leere
Liste, weil die Schleife nichts zu iterieren hat. Für Fall B (`dc.metrics`
nicht leer, aber jeder Eintrag `enabled=False`) liefert dieselbe Filterung
**ebenfalls** eine leere Liste, weil `elif mc.enabled:` nie zutrifft. Beide
Fälle kommen also identisch als `dc.metrics == []` bei `html.py`/`plain.py`/
`compact.py` an — genau der Zustand, den T1/T2/T2b eigentlich unterscheiden
sollen, ist zu diesem Zeitpunkt bereits zerstört. Eine Prüfung, die
ausschließlich innerhalb von `html.py`/`plain.py`/`compact.py` auf
`len(dc.metrics)`  schaut, kann Fall A und Fall B strukturell nicht mehr
auseinanderhalten — sie träfe entweder die heutige falsche Entscheidung
(beide zeigen alles) oder eine neue falsche Entscheidung (beide zeigen
nichts, was Fall A für 13 Bestandstrips regressieren würde).

**Konsequenz:** Diese Spec ergänzt eine fünfte Fundstelle, **T0**, die vor
der kanal-spezifischen Kollabierung ansetzt und das Altbestand-Signal explizit
bis zu den drei Renderern durchreicht (siehe Implementation Details). Ohne
T0 wären T1–T4 zwar lokal korrekt implementiert, würden den gemeldeten Bug
für das tatsächlich zugestellte Morgen-/Abendbriefing aber nicht beheben —
sie griffen nur bei Direktaufrufen von `render_html()`/`render_plain()`/
`render_compact()` außerhalb des Versandpfads (z. B. den heutigen
Unit-Tests, die `dc` unkollabiert übergeben).

## Source

- **File:** `src/output/renderers/trip_metric_ids.py` (NEU) —
  `resolve_trip_active_metrics()`, `DEFAULT_TRIP_METRIC_IDS`
- **File:** `src/output/renderers/trip_report.py` —
  `TripReportFormatter.format_email()` (T0)
- **File:** `src/output/renderers/email/__init__.py` — `render_email()`
- **File:** `src/output/renderers/email/html.py` — `render_html()` (T1)
- **File:** `src/output/renderers/email/plain.py` — `render_plain()` (T2)
- **File:** `src/output/renderers/email/compact.py` — `render_compact()` (T2b)
- **File:** `src/services/day_comparison.py` — `summarize_day_comparison()` (T3)
- **File:** `src/app/loader.py` — `_parse_display_config()` (T4)

## Estimated Scope

- **LoC:** ~220–290 netto (Quelle ~100–110, Tests ~120–180) — über dem
  250-LoC-Standardlimit, hauptsächlich wegen T0 (neues Modul +
  Parameter-Durchreichung durch vier Funktionssignaturen) und dem
  End-to-End-Nachweis über den echten Versandpfad.
  **PO-Entscheidung 2026-07-31: eine Scheibe, `loc_limit_override = 350`
  gesetzt.** Begründung: alle Fundstellen hängen an einer Ursache; jede
  Aufteilung liefert einen halb behobenen Zustand aus (z. B. HTML-Teil
  korrekt, Klartext-Teil derselben Mail noch falsch).
- **Files:** 1 neue + 7 geänderte Quelldateien; ~6–8 Testdateien (überwiegend
  Ergänzungen bestehender Suiten, eine neue Datei für den Resolver)
- **Effort:** medium-high (Symptom-Fixes selbst sind klein; T0 erfordert
  sorgfältiges Durchreichen durch die Aufrufkette, um Fall A/B nicht doch
  wieder zu vermischen)

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `resolve_trip_active_metrics()` (`trip_metric_ids.py`, NEU) | intern (CREATE) | Einzige Regel-Quelle: Fall A → `DEFAULT_TRIP_METRIC_IDS`, Fall B → `[]`, normal → aktive IDs. Ersetzt die bisher zweifach duplizierte Siebener-Liste (`html.py`, `plain.py`) und die fehlende Ersatzliste in `compact.py`. |
| `TripReportFormatter.format_email()` (`trip_report.py`) | intern (MODIFY) | T0 — misst das Altbestand-Signal VOR der Kanal-Kollabierung und reicht es an `render_email()` durch. Einziger Ort, an dem die Original-Konfiguration noch ungefiltert vorliegt. |
| `render_email()` (`email/__init__.py`) | intern (MODIFY) | reicht das Altbestand-Signal an alle drei Renderer durch (voller Pfad + Compact-Zweig) |
| `render_html()` / `render_plain()` / `render_compact()` | intern (MODIFY) | T1/T2/T2b — neuer optionaler Parameter, Default `True` (rückwärtskompatibel für Direktaufrufer wie Bestandstests); rufen `resolve_trip_active_metrics()` auf statt eigener Ersatzliste |
| `summarize_day_comparison()` (`day_comparison.py`) | intern (MODIFY) | T3 — trennt `None` (Altbestand → Legacy-Text), bewusst leer (→ keine Zeile) und gefüllt (→ metrik-getriebener Text) |
| `_parse_display_config()` (`loader.py`) | intern (MODIFY) | T4 — kanal-spezifische Leerauswahl (alle Kanal-Listen leer) wird nicht mehr auf `None` zurückgefallen |
| `get_metrics_for_channel()` / `_filter_metrics_by_report_type()` (`models.py:554-581, 650-682`) | intern (bestehend, unverändert) | Ursache der Fall-A/B-Vermischung (Kritischer Befund) — Verhalten bleibt wie es ist, weil Telegram/SMS bereits korrekt darauf aufbauen; T0 kompensiert davor, statt hier einzugreifen |
| `.claude/hooks/renderer_mail_gate.py` (Issue #811) | Gate | greift, weil `html.py`/`plain.py`/`compact.py` Mail-Inhalts-Dateien sind — Pflicht-Nachweis vor Commit |
| `.claude/hooks/briefing_mail_validator.py` | Gate | Trip-Mail-Validator gegen echt zugestellte Staging-Mail — kann eine bewusste Leerauswahl-Mail strukturell nicht abnehmen (siehe Test Plan) |

## Implementation Details

### T0 (neu) — Altbestand-Signal vor der Kanal-Kollabierung messen

In `TripReportFormatter.format_email()` wird direkt nach
`dc = display_config or build_default_display_config()` (`trip_report.py:113`)
und noch vor der bestehenden `if report_type in ("morning", "evening")`-
Kollabierung (`:114-119`) ein lokales Flag `_trip_metrics_altbestand =
len(dc.metrics) == 0` gemessen — der einzige Zeitpunkt, an dem die
Original-Konfiguration noch unverändert vorliegt. Das Flag wird als neuer
Keyword-Parameter `trip_metrics_altbestand` an `render_email()` (Aufruf
`:181`) durchgereicht. `render_email()` reicht ihn unverändert an
`render_html()`, `render_plain()` (voller Pfad, `email/__init__.py:123-181`)
und `render_compact()` (Compact-Zweig, `:96-113`) weiter. Alle drei Renderer
bekommen den Parameter mit Default `True`, damit bestehende Direktaufrufer
(Unit-Tests, die `dc` unkollabiert übergeben) unverändert das heutige
Verhalten erhalten, ohne den neuen Parameter zu kennen.

### Gemeinsamer Resolver: `trip_metric_ids.py` (neu)

`resolve_trip_active_metrics(metrics, *, altbestand=True)` kapselt die Regel
an einer Stelle: aktive IDs (`mc.enabled`) sammeln; ist das Ergebnis leer
UND `altbestand=True`, `DEFAULT_TRIP_METRIC_IDS` (die bisher doppelt
verdrahtete Siebener-Liste: `temperature, wind, gust, precipitation,
thunder, freezing_level, visibility`) zurückgeben; sonst das (ggf. leere)
Ergebnis unverändert. Bauart analog `compare_hourly_metric_ids.py::
resolve_hourly_metrics()` (#1366) — eine Funktion, mehrere Aufrufer, keine
pro-Renderer-Zweitentscheidung (Trip/Compare-Teilungsinvariante, CLAUDE.md).

**Falle, gemessen 2026-07-31:** `DEFAULT_TRIP_METRIC_IDS` darf NICHT aus
`build_default_display_config()` (`metric_catalog.py:644`) abgeleitet werden.
Deren aktive Menge ist eine andere: zehn Größen (`temperature`,
`temperature_cold`, `wind_chill`, `wind`, `gust`, `precipitation`, `thunder`,
`snowfall_limit`, `cloud_total`, `sunshine` — alle `MetricDefinition` ohne
explizites `default_enabled=False`, Feld-Default ist `True`, `:37`). Sie
überschneidet sich nur teilweise mit der heute im Überblick gezeigten
Siebener-Liste (`freezing_level` und `visibility` fehlen dort, fünf andere
kämen hinzu). Für Fall A zählt allein, was heute tatsächlich in der Mail
steht — die Siebener-Liste wird deshalb als eigene Konstante geführt.

**Ebenfalls verworfen (geprüft, nicht gangbar):** die Fall-A-Auffüllung
schon in `format_email()` in `dc.metrics` zu materialisieren, statt ein Flag
durchzureichen. Das erspart zwar den neuen Parameter, ändert aber für die 13
Fall-A-Bestandstrips mehr als den Überblicksblock: `dc.metrics` speist auch
`_extract_hourly_rows()` (`trip_report.py:127`) und `build_friendly_keys()`
(`:122`), sodass plötzlich Stundentabellen-Spalten erschienen, wo heute
keine sind — ein Bruch von Invariante 1.

### T1 `email/html.py:1337-1343` + Vortagszeile `:1371-1376`

Der Ersatzlisten-Block wird durch einen Aufruf von
`resolve_trip_active_metrics(dc.metrics, altbestand=trip_metrics_altbestand)`
ersetzt. Für die Vortagszeile wird die ROHE aktive Liste (`[mc.metric_id for
mc in dc.metrics if mc.enabled]`, ohne Default-Auffüllung) separat gebildet
und nur dann als `None` an `summarize_day_comparison()` übergeben, wenn sie
leer UND `trip_metrics_altbestand` ist — sonst wird sie (auch leer)
unverändert übergeben. Der Default-Satz selbst darf hier NICHT einfließen,
weil `None` einen eigenen Legacy-Berechnungspfad auslöst
(`_summarize_legacy`), der sich von einer metrik-getriebenen Berechnung mit
den sieben Default-IDs unterscheidet — nur `None` reproduziert das
bestehende Fall-A-Verhalten (siehe AC-5).

### T2 `email/plain.py:154-160` + Vortagszeile `:144-148`

Wortgleich zu T1.

### T2b `email/compact.py:146-163`

Bislang gibt es hier keine Ersatzliste, aber die Überschrift
`== Metriken-Ueberblick ==` (`:163`) wird unbedingt gesetzt. Zwei
Korrekturen: (1) `metric_ids` wird über denselben Resolver aufgelöst —
damit zeigt das Kurzformat für Fall A **erstmals** den Standard-Satz statt
einer leeren Überschrift (Bugfix, kein reiner Regressionsschutz); (2)
Überschrift und Pillen-Schleife werden nur noch gerendert, wenn `pills`
nicht leer ist — analog Compare-Commit `9ae845d8` („STUNDENVERLAUF nur noch
mit Stundenzeilen"). Für Fall B entfällt der Block dadurch vollständig.

### T3 `services/day_comparison.py:178`

`if not selected_metrics: return _summarize_legacy(comparison)` fängt
`None` und `[]` im selben Zweig ab. Die Signatur
(`Optional[List[str]] = None`, `:156-169`) trennt beide bereits sauber und
dokumentiert die Bedeutung. Der naheliegende Fix wäre `if selected_metrics
is None:` — das allein reicht jedoch nicht: `_summarize_metric_driven(
comparison, [])` (`:262-315`) iteriert über eine leere Liste, findet keine
salienten Deltas und gibt unbedingt „heute ähnliches Wetter wie gestern"
zurück (`:305-306`) — **unabhängig davon, wie groß die realen Deltas sind**.
Das ist exakt der Fehler, den `tests/tdd/test_issue_790_briefing_simplify.py:
370-385` (`test_empty_metrics_list_falls_back_to_legacy`, Bug #800) bereits
verhindert: „`selected_metrics=[]` darf NICHT 'ähnliches Wetter' liefern,
wenn echte Deltas existieren." Der korrekte Fix hat daher drei Zweige:

```
if selected_metrics is None:
    return _summarize_legacy(comparison)
if not selected_metrics:
    return ""
return _summarize_metric_driven(comparison, selected_metrics)
```

Eine bewusst leere Auswahl (Fall B) liefert damit **keine** Vortagszeile —
weder die irreführende „ähnliches Wetter"-Aussage noch eine auf abgewählte
Größen gestützte Legacy-Aussage. Das erhält die Kern-Garantie aus Bug #800
(niemals eine falsche Ähnlichkeits-Behauptung), auch wenn der konkrete
Rückgabewert für `[]` sich ändert (siehe Test Plan, Bestandstest-Anpassung).

### T4 `app/loader.py:792-801`

Die Teilbedingung `and any(raw_channel_layouts.values())` (`:800`) wird
entfernt. Danach entscheidet nur noch, ob `raw_channel_layouts` ein
nicht-leeres Dict ist — eine vollständig leere Kanal-Konfiguration (alle
Kanal-Listen `[]`) wird dann als `per_channel_layouts` mit leeren Listen je
Kanal übernommen, statt auf `None` (globaler Fallback) zurückzufallen. Das
entspricht dem in `models.py:603-606` dokumentierten Vertrag, den
`get_metrics_for_channel()` (`:650-682`) bereits korrekt umsetzt. Kein
Bestandstrip hat heute `channel_layouts` gesetzt (0 von 19) — keine
Datenwirkung, rein vorbeugend.

## Expected Behavior

- **Input:** Trip mit `display_config.metrics` in einem von drei Zuständen:
  Feld fehlt/leer (Fall A, Altbestand), Feld enthält Einträge mit
  `enabled=False` für alle (Fall B, bewusste Leerauswahl), Feld enthält
  Einträge mit mindestens einer aktiven Metrik (normal).
- **Output:** Morgen-/Abendbriefing (HTML, Klartext, Kurzformat derselben
  oder alternativer Zustellung) sowie Telegram und SMS respektieren „Feld
  fehlt → Standard-Satz" und „Feld vorhanden und leer → nichts" identisch.
  Die Vortagszeile entfällt bei Fall B vollständig statt eine irreführende
  oder auf abgewählte Größen gestützte Aussage zu zeigen.
- **Side effects:** Keine Datenmigration, keine Änderung an
  Bestandsverhalten für Trips ohne gespeicherte Auswahl (Fall A). Neuer
  optionaler Parameter `trip_metrics_altbestand` (Default `True`) an vier
  bestehenden Funktionssignaturen — rückwärtskompatibel.

## Acceptance Criteria

- **AC-1:** Given ein Nutzer hat im Trip alle Wettergrößen bewusst
  abgewählt (gespeichert mit `enabled=False` für jede Größe) / When sein
  Morgen- oder Abendbriefing als E-Mail erzeugt und zugestellt wird / Then
  enthält der HTML-Teil keinen Metriken-Überblick-Block mehr — weder die
  sieben Standardgrößen noch eine leere Überschrift.

- **AC-2:** Given dieselbe bewusste Leerauswahl wie AC-1 / When das
  Briefing erzeugt wird / Then zeigt auch der Klartext-Teil derselben Mail
  keinen Metriken-Überblick-Block.

- **AC-3:** Given dieselbe bewusste Leerauswahl wie AC-1 / When das
  Briefing im Kurzformat erzeugt wird / Then enthält es ebenfalls keinen
  Metriken-Überblick-Block — weder Überschrift noch Pillen.

- **AC-4:** Given ein Nutzer hat alle Wettergrößen abgewählt, obwohl sich
  das Wetter gegenüber dem Vortag real und deutlich unterscheidet / When
  das Briefing erzeugt wird / Then enthält es keine Vortag-Vergleichszeile
  — weder die generische „ähnliches Wetter"-Aussage noch eine auf die
  abgewählten Größen gestützte Aussage.

- **AC-5:** Given ein Trip, für den noch nie eine Metrik-Auswahl
  gespeichert wurde (Feld fehlt ganz) / When sein Morgen- oder
  Abendbriefing als E-Mail (HTML- und Klartext-Teil) erzeugt wird / Then
  zeigen beide Teile weiterhin die sieben Standardgrößen und die bisherige
  Vortagszeilen-Logik — exakt wie vor dieser Änderung.

- **AC-6:** Given derselbe Trip ohne je gespeicherte Metrik-Auswahl wie
  AC-5 / When das Briefing im Kurzformat erzeugt wird / Then zeigt auch das
  Kurzformat jetzt die sieben Standardgrößen — statt bisher einer leeren
  Überschrift ohne Inhalt.

- **AC-7:** Given ein Nutzer hat im Editor für jeden einzelnen Kanal
  (E-Mail, Telegram, SMS) die Metrik-Liste bewusst geleert / When sein
  Briefing für einen dieser Kanäle erzeugt wird / Then wird diese
  kanal-spezifische Leerauswahl übernommen, statt auf die globale
  Metrik-Liste zurückzufallen.

- **AC-8:** Given dieselbe bewusste Leerauswahl wie AC-1 / When sein
  Briefing per Telegram bzw. als SMS zugestellt wird / Then enthalten auch
  diese beiden Kanäle keine der abgewählten Wettergrößen — konsistent mit
  E-Mail (HTML, Klartext, Kurzformat).

## Invarianten

Sechs Eigenschaften, die dieser Eingriff nicht brechen darf:

1. **Fall A bleibt exakt wie heute** — die zentrale Invariante. 13 von 19
   Bestandsbriefings (davon 5 echte Nutzer-Touren) dürfen ihren
   Metriken-Überblick nicht verlieren.
2. **Roundtrip-Verhalten von `loader.py`** (schema-relevant, CLAUDE.md) —
   T4 betrifft 0 Bestandstrips; ein Roundtrip-Test sichert das ab.
3. **Stundentabellen-Verhalten** (`_allowed_col_keys_for_horizon`,
   `html.py:861-884`) bleibt vollständig unangetastet — eigener,
   unabhängiger Mechanismus (siehe Abgrenzung).
4. **Reihenfolge** der Metriken bleibt Erstvorkommen in `dc.metrics` — kein
   Sortier-Eingriff in `resolve_trip_active_metrics()`.
5. **Rückwärtskompatibilität der Renderer-Signaturen** —
   `render_html()`/`render_plain()`/`render_compact()` bleiben für
   bestehende Direktaufrufer ohne den neuen Parameter unverändert nutzbar
   (Default `True`).
6. **Bug-#800-Garantie** — eine leere Metrik-Auswahl darf niemals „heute
   ähnliches Wetter wie gestern" behaupten, wenn reale Deltas bestehen. Nur
   der konkrete Rückgabewert ändert sich (Legacy-Text → keine Zeile), die
   Garantie selbst bleibt bestehen.

## Abgrenzung

Nicht in dieser Scheibe:

- **`_allowed_col_keys_for_horizon`** (`html.py:861-884`) — der
  Stundentabellen-Spaltenfilter hat dieselbe Fehlerklasse (`keys or None`
  behandelt Fall A und Fall B heute identisch: beide → kein Filter, alle
  Spalten sichtbar), ist aber ein eigenständiger, von den T0–T4-Fixes
  unberührter Mechanismus. Sammel-Eintrag statt eigenes Issue (#1199), da
  kosmetisch/nicht blockierend.
- **Telegram/SMS-Code selbst** wird nicht geändert — `get_metrics_for_
  channel()` setzt den dokumentierten Vertrag für sie bereits korrekt um
  (AC-8 ist ein Regressionsnachweis, kein Fix).
- **Frontend-Editor** — das Setzen der `enabled=False`-Flags beim Abwählen
  ist bereits vorhanden und funktioniert (anders als #1366 F1/F2 im
  Ortsvergleich, wo das Speichern selbst kaputt war); keine
  Frontend-Änderung in dieser Scheibe.
- **Report-Typen außerhalb `morning`/`evening`** (`update`, `compare`) —
  die Kollabierung in `trip_report.py:114` betrifft sie nicht, sie erhalten
  `dc` unkollabiert und profitieren bereits vom renderer-internen Resolver
  mit Default `altbestand=True`.

## Test Plan

Test-Politik (CLAUDE.md „Zwei Schichten"): Kern-Tests deterministisch ohne
Netz/Live-Dienste sind Pflicht und müssen 100 % grün sein; der Nachweis aus
Nutzersicht kommt zusätzlich aus der Live-Schicht. Keine neuen Testdateien
mit Issue-Nummer im Namen — die neue Resolver-Datei bekommt einen
verhaltensbenannten Test (`test_trip_metric_ids.py`).

### Bestandstests, die angepasst werden müssen

- `tests/tdd/test_issue_790_briefing_simplify.py:370-385` —
  `test_empty_metrics_list_falls_back_to_legacy` (Bug #800) — die Zeile
  `assert line_empty == line_none` (`:380-382`) wird nach T3 **falsch**:
  `selected_metrics=[]` liefert jetzt `""`, nicht mehr denselben Text wie
  `None`. Umzuschreiben auf: `summarize_day_comparison(comp,
  selected_metrics=[]) == ""` UND (Kern-Garantie erhalten)
  `"ähnliches Wetter" not in line_empty` bleibt als Assertion bestehen
  (jetzt trivial wahr, weil `line_empty == ""`).

- `tests/tdd/test_issue_429_channel_layouts.py:139-151` —
  `test_ac1_all_empty_channel_layouts_treated_as_none` (beim Schreiben der
  RED-Tests gefunden, 2026-07-31). Dieser Test zementiert **exakt das
  Gegenteil von AC-7**: `assert dc.per_channel_layouts is None`, wenn alle
  Kanal-Listen leer sind. Er stammt aus #429 und hält die dortige
  Ausgangsannahme fest, die #1394 bewusst revidiert (der Vertrag in
  `models.py:603-606` sagt seither das Gegenteil). T4 macht ihn zwangsläufig
  rot. Umzuschreiben auf: `per_channel_layouts` ist ein Dict mit leeren
  Listen je Kanal; Testname und Docstring auf das geltende Verhalten
  ziehen. **Nicht stilllegen, nicht überspringen** — der Fall bleibt
  abgedeckt, nur mit umgekehrter Erwartung.

### Unverändert grün bleiben muss

- `tests/tdd/test_issue_790_briefing_simplify.py:224-251` —
  `test_empty_metrics_uses_default_set_html`/`_plain` (AC-6, Fall A) —
  bleiben grün, weil Direktaufrufe von `render_html()`/`render_plain()`
  ohne den neuen Parameter den Default `altbestand=True` erhalten.
- `tests/tdd/test_issue_790_briefing_simplify.py:296-328` — Vortagszeilen-
  Tests, die `summarize_day_comparison()` ohne `selected_metrics` aufrufen
  → bleiben bei `None`, unverändert korrekt (AC-5).
- `tests/tdd/test_issue_790_briefing_simplify.py:392-419` (Bug #798,
  `_allowed_col_keys_for_horizon`) — nicht Teil dieser Scheibe (siehe
  Abgrenzung), bleibt unverändert.
- `tests/tdd/test_issue_429_channel_layouts.py:146,277` — bestehende
  Channel-Layout-Tests mit gefüllten Kanal-Listen bleiben unberührt, nur
  der „alle Kanal-Listen leer"-Fall ändert sich (neuer Test, s.u.).

### Neue Kern-Tests

- `trip_metric_ids.py`: `resolve_trip_active_metrics([], altbestand=True)
  == list(DEFAULT_TRIP_METRIC_IDS)`; `resolve_trip_active_metrics([alle
  enabled=False], altbestand=False) == []`; aktive Auswahl bleibt
  unabhängig von `altbestand` unverändert (AC-1–AC-3, AC-5–AC-6 auf
  Resolver-Ebene).
- `email/html.py`/`plain.py`/`compact.py`: Direktaufruf mit `dc.metrics`
  = alle `enabled=False` UND `trip_metrics_altbestand=False` → kein
  Metriken-Überblick-Block (AC-1–AC-3); dieselbe leere Konfiguration mit
  `trip_metrics_altbestand=True` (Default) → weiterhin Standard-Satz
  (Regressionsschutz Fall A, AC-5–AC-6).
- `day_comparison.py`: `summarize_day_comparison(comp, selected_metrics=[])
  == ""` bei realen, großen Deltas (AC-4); `selected_metrics=None`
  weiterhin Legacy-Text (AC-5, unverändert).
- `loader.py`: `_parse_display_config()` mit
  `channel_layouts={"email": [], "telegram": [], "sms": []}` →
  `per_channel_layouts` ist ein Dict mit leeren Listen je Kanal, nicht
  `None` (AC-7).
- **End-to-End über den echten Versandpfad (Pflicht, beweist den
  Kritischen Befund ist behoben):** `TripReportFormatter.format_email()`
  mit `report_type="morning"` bzw. `"evening"` und einem `display_config`,
  dessen `metrics` nicht-leer, aber vollständig `enabled=False` ist →
  `email_html`/`email_plain` enthalten keinen Metriken-Überblick-Block.
  Ein Test, der stattdessen nur `render_html()`/`render_plain()` direkt
  aufruft, beweist den Fix für den Versandpfad NICHT (siehe Kritischer
  Befund) und ist als alleiniger Nachweis unzureichend.
- Telegram/SMS: `render_telegram_bubbles()` bzw. `SMSTripFormatter.
  format_sms()` mit vollständiger Leerauswahl → keine der abgewählten
  Wettergrößen erscheint (AC-8, Regressionsnachweis für bereits korrektes
  Verhalten).

### Live-E2E (Staging, Pflicht vor „E2E bestanden")

`.claude/hooks/briefing_mail_validator.py:399-400` verlangt eine
sequenzielle Stundentabelle mit ≥2 Stundenzeilen, `:357-361` zusätzlich
eine bei 390px UND 1000px sichtbare Wetterdaten-Tabelle. Eine korrekte
Leerauswahl-Mail hat beides nicht (die Stundentabelle selbst ist von dieser
Scheibe nicht betroffen, siehe Abgrenzung — aber der Metriken-Überblick-
Block fehlt bewusst). Der Pflicht-Validator kann eine solche Mail
strukturell nicht abnehmen. Daraus folgt:

- Der Gate-Lauf für das Renderer-Commit-Gate #811 wird mit einem
  **normalen** Briefing (nicht-leere Auswahl) geführt — Nachweis: keine
  Regression am Regelfall.
- Der Nutzersicht-Nachweis der Leerauswahl läuft über eine **zweite**,
  separat per IMAP abgerufene Staging-Mail mit gesonderter, hier benannter
  Prüfung: Überblicksblock fehlt vollständig (kein Fragment, keine leere
  Überschrift) im HTML- **und** im Klartext-Teil, keine Vortagszeile, keine
  der sieben Ersatzgrößen — an einem Trip mit über das Editor-UI
  gespeicherter vollständiger Leerauswahl (nicht nur synthetisch im Test
  konstruiert).
- Der Validator selbst wird **nicht** geändert (Projektregel:
  Validator-Änderungen sind ein eigener Workflow).

## Known Limitations

- Die Unterscheidung Fall A/Fall B hängt an einem neuen, explizit
  durchgereichten Boolean-Parameter (`trip_metrics_altbestand`), nicht an
  einer Eigenschaft von `dc` selbst — wird eine der vier Funktionen künftig
  von einer neuen Stelle aus aufgerufen, muss dieser Parameter bewusst
  korrekt gesetzt werden; der sichere Default (`True`) verhindert dabei nur
  die Fall-A-Regression, nicht das (weniger schädliche) Symptom „Fall B
  zeigt fälschlich den Standard-Satz".
- `_allowed_col_keys_for_horizon` bleibt in derselben Fehlerklasse wie vor
  dieser Änderung (siehe Abgrenzung) — Sammel-Eintrag #1199.
- Der End-to-End-Test deckt `report_type in ("morning", "evening")` ab;
  `update`/`compare` sind strukturell unbetroffen, aber nicht separat
  durchgetestet (siehe Abgrenzung).

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Diese Scheibe korrigiert Renderer und Formatter auf die
  Bedeutung, die `models.py:603-606` bereits dokumentiert, und führt keine
  neue Architektur-, Datenmodell- oder Persistenzentscheidung ein — kein
  neuer Kanal, keine Schema-Änderung. Der neue Parameter
  `trip_metrics_altbestand` ist eine lokale Durchreichung, kein
  Architekturprinzip.

## Changelog

- 2026-07-31: Initial spec erstellt — Issue #1394, Trip-Gegenstück zu
  #1366. Kritischer Befund ergänzt (T0, Kollabierung in
  `trip_report.py:113-119` zerstört Fall-A/B-Unterscheidung vor Erreichen
  der Renderer) und Bug-#800-Testkonflikt bei T3 identifiziert.
