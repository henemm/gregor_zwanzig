---
entity_id: fix_1297_sms_preview_thunder
type: bugfix
created: 2026-07-17
updated: 2026-07-17
status: draft
version: "1.0"
workflow: fix-1297-sms-preview-thunder
tags: [bug, sms, preview, thunder, email, adr-0025]
---

# Fix #1297: SMS-Vorschau zeigt immer `TH+:-` — Vorschau-Pfad war nicht Teil von ADR-0025

## Approval

- [ ] Approved

## Purpose

Die SMS-Vorschau (`PreviewService.render_sms_preview()`) zeigt für die Folgeetappe
strukturell immer `TH+:-`, unabhängig vom tatsächlichen Wetter — während die
tatsächlich versendete SMS für dieselbe Etappe den echten Gewitter-Wert trägt. Ursache:
`preview_service.py` berechnet `thunder_forecast` (und `multi_day_trend`, von dem
`thunder_forecast` im Regelfall abgeleitet wird) nirgends und übergibt es folglich auch
nicht an `format_email()` — beide Parameter bleiben `None`, egal was in Wirklichkeit
vorhergesagt ist. ADR-0025 („eine Gewitter-Quelle für alle Briefing-Kanäle") hat genau
diesen Fehlermodus für SMS/Telegram/E-Mail im **Versandweg** beseitigt; der
**Vorschau-Pfad** war explizit nicht im Scope (siehe Kontext-Dokument) und trägt den
strukturell selben Defekt bis heute. Dieser Fix dehnt die ADR-0025-Invariante auf die
Vorschau aus, ohne den bereits korrekten und adversary-verifizierten Versandweg
anzufassen.

**Nebenfund, gleiche Ursache:** Weil `multi_day_trend` in der Vorschau ebenfalls nie
berechnet wird, fehlt in der **E-Mail-Vorschau** nicht nur der Gewitter-Ausblick-Text,
sondern die gesamte Mehrtages-Ausblick-Tabelle (Outlook), sofern `show_multi_day_trend`
aktiv wäre. Da beide Werte (`multi_day_trend`, `thunder_forecast`) aus derselben
Erzeugungskette stammen und derselbe eine Wiring-Fix beide behebt, wird dieser Nebenfund
hier mitbehoben, nicht als eigenes Ticket ausgelagert (Bündelungsregel PO-go 2026-07-09).

## Source

- **File:** `src/services/preview_service.py`
- **Identifier:** `PreviewService._build_report()` (Zeile 120-204),
  `PreviewService._render_email()` (Zeile 206-232)

> **Schicht-Hinweis:** Betroffener Code liegt ausschließlich im Vorschau-Service
> (`src/services/preview_service.py`, Python-Core). Kein Go-API-, kein Frontend-Anteil.
> `src/services/trip_report_scheduler.py` wird **nicht verändert** — seine bestehenden
> Methoden werden aus `preview_service.py` heraus wiederverwendet.

## Estimated Scope

- **LoC:** ~90-140 (Source `preview_service.py` ~20-25 Zeilen + Tests
  `test_sms_preview_matches_sent.py` ~70-115 Zeilen; ADR-Changelog-Eintrag in `docs/`
  zählt nicht mit). Kein Override erwartet, wird bei Bedarf am tatsächlichen Diff
  geprüft.
- **Files:** 3 (2 MODIFY Source/Test, 1 MODIFY Doku/ADR-Changelog)
- **Effort:** low-medium — reine Wiring-Ergänzung, keine neue Logik, kein Eingriff in
  den Versandweg. Aufwandtreiber ist der mock-freie Testnachweis (echte Zeitreihe mit
  Gewitter durch den echten Vorschau-Einstiegspunkt).

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `TripReportSchedulerService._build_stage_trend()` (`trip_report_scheduler.py:1361`) | method | Erzeugt `multi_day_trend`; wird von `preview_service.py` direkt aufgerufen (dieselbe Instanz, die dort bereits für Segmente/Wetter genutzt wird) — keine Kopie der Logik |
| `TripReportSchedulerService._build_thunder_forecast_from_trend_or_fetch()` (`trip_report_scheduler.py:1495-1540`) | method | Erzeugt `thunder_forecast` aus dem Trend (Primärpfad) bzw. per Fallback-Fetch; identischer Aufruf wie im Versandweg (`trip_report_scheduler.py:846-848`) |
| `resolve_report_render_options()` (`report_config_resolver.py`) | function | Liefert `render_options.show_multi_day_trend`; wird in `_build_report()` bereits berechnet und muss die Trend-Berechnung genauso gaten wie im Versandweg (`trip_report_scheduler.py:837`) |
| `TripReportFormatter.format_email()` (`trip_report.py:56-79`) | function | Nimmt `thunder_forecast`/`multi_day_trend` bereits als Parameter entgegen (Default `None`) — unverändert, wird nur ab jetzt aus der Vorschau mit echten Werten gefüttert |
| `SMSTripFormatter.format_sms()` (`sms_trip.py:186-297`) | function | Konsumiert `thunder_forecast["+1"]` für `TH+:` — unverändert; Beweisfläche für AC-1/AC-2 |
| `render_email()` / E-Mail-Renderer (`src/output/renderers/email/html.py`, `plain.py`) | function | Konsumiert `thunder_forecast` für den Gewitter-Ausblick-Text in der E-Mail — unverändert; Beweisfläche für AC-6 |
| `render_telegram_bubbles()` (`narrow.py:359-371`) | function | Konsumiert `thunder_forecast` **nicht** — Telegram-Fußzeile/Übersicht lesen bereits gefensterte `dp.thunder_level`-Werte aus `seg_tables`, die in der Vorschau schon korrekt ankommen (ADR-0025-Tabelle). Kein Änderungsbedarf, wird nur als Beleg für AC-6 referenziert |
| `report.sms_text` / `report.email_html` (`TripReport`-DTO) | field | Preview gibt bereits (seit #954) exakt diese Felder zurück statt eines eigenen Renderpfads — der Fix erweitert nur, WAS in diese Felder einfließt, nicht WIE sie zurückgegeben werden |
| `tests/tdd/test_sms_preview_matches_sent.py` | test | Bestehender Wächter „Vorschau == Versand"; laut eigenem Kommentar (Zeile 11, 39-41) bewusst ohne `thunder`-Metrik aufgebaut — wird um den Gewitter-Fall erweitert |
| `tests/tdd/test_thunder_forecast_trend_reuse.py` | test | Mock-freies Vorbild: `TripReportSchedulerService()._build_thunder_forecast_from_trend_or_fetch(trip, target, tz, multi_day_trend=<Zeilen>)` direkt aufrufbar, ohne Live-Fetch — Muster für den neuen Testfall |
| `PreviewService._load_trip()` (`preview_service.py:54-82`) | method | Nimmt `user_id` bereits als Pflichtparameter entgegen — unverändert; Fix führt **keinen** `"default"`-Fallback ein |

## Scope

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/preview_service.py` | MODIFY | In `_build_report()`: nach der bestehenden `render_options`-Berechnung `multi_day_trend` via `scheduler._build_stage_trend(trip, target, tz=trip_tz)` (gegated auf `render_options.show_multi_day_trend`, exakt wie im Versandweg) und `thunder_forecast` via `scheduler._build_thunder_forecast_from_trend_or_fetch(trip, target, tz=trip_tz, multi_day_trend=multi_day_trend)` berechnen. Beide Werte zusätzlich an `_render_email()` übergeben, dort als neue Parameter `multi_day_trend=`/`thunder_forecast=` an `format_email()` durchreichen. Keine neue Berechnungslogik — ausschließlich Aufruf bereits existierender Scheduler-Methoden über die bereits im Service vorhandene `scheduler`-Instanz. |
| `tests/tdd/test_sms_preview_matches_sent.py` | MODIFY | Neuer Testfall (oder Erweiterung des bestehenden Fixture-Aufbaus) mit **aktivierter** `thunder`-Metrik und einer echten Zeitreihe mit `dp.thunder_level=HIGH` auf einer Folgeetappe (2-Etappen-Trip, damit `_build_stage_trend`/`_build_thunder_forecast_from_trend_or_fetch` einen `+1`-Wert liefern). Assertion: `render_sms_preview()`-Token enthält denselben `TH+`-Wert wie `report.sms_text` — analog zum bestehenden Muster `token_line == report.sms_text`, diesmal MIT Gewitter statt es auszuschließen. |
| `docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md` | MODIFY | Changelog-Eintrag: Vorschau-Pfad war beim initialen ADR nicht im Scope (Kontext-Dokument #1297), Entscheidungen 1-5 gelten jetzt nachweislich auch für `preview_service.py`. Kein neuer ADR nötig — Erweiterung einer bestehenden, unveränderten Invariante (siehe Abschnitt „Architektur-Entscheidung" unten). |

## Implementation Details

**Ein Wiring-Fix, keine neue Logik (Lehre aus #1275: bewährte Quelle wiederverwenden).**
`preview_service.py` instanziiert in `_build_report()` bereits
`scheduler = TripReportSchedulerService(self.settings)` und ruft darauf mehrere private
Methoden direkt auf (`_convert_trip_to_segments`, `_fetch_weather`,
`_compute_stage_stats`) — dieses Muster ist im Code bereits etabliert. Der Fix folgt
demselben Muster für zwei bisher fehlende Aufrufe:

1. `multi_day_trend = scheduler._build_stage_trend(trip, target, tz=trip_tz)` — nur wenn
   `render_options.show_multi_day_trend` (identisches Gate wie
   `trip_report_scheduler.py:837`).
2. `thunder_forecast = scheduler._build_thunder_forecast_from_trend_or_fetch(trip,
   target, tz=trip_tz, multi_day_trend=multi_day_trend)` — unbedingt, identisch zu
   `trip_report_scheduler.py:846-848`.

Beide Werte fließen in denselben `format_email()`-Aufruf, den die Vorschau ohnehin schon
macht. Es entsteht **keine** zweite Implementierung der Trend-/Gewitter-Berechnung im
`preview_service` — genau die Parallel-Implementierung, die ADR-0025 verbietet, wird
vermieden, indem die Scheduler-Methoden direkt wiederverwendet statt nachgebaut werden.
Der Versandweg (`trip_report_scheduler.py`, `notification_service.py`) wird nicht
angefasst.

**Warum keine Extraktion nötig ist:** Der Kontext hielt eine mögliche Extraktion in eine
gemeinsame, freistehende Funktion für nötig, falls die Kette „nicht als aufrufbare
Einheit exponiert" ist. Sie ist es bereits — `_build_stage_trend()` und
`_build_thunder_forecast_from_trend_or_fetch()` sind aufrufbare Instanzmethoden auf
`TripReportSchedulerService`, und `preview_service.py` hält bereits eine Instanz davon.
Eine Extraktion würde bestehenden, korrekten Code im gate-relevanten Scheduler anfassen,
ohne einen Vorteil gegenüber dem direkten Aufruf zu bieten — höheres Regressionsrisiko
für denselben Effekt.

**Fallback-Fetch-Kosten in der Vorschau:** Deckt der Trend einen Offset nicht ab, löst
`_build_thunder_forecast_from_trend_or_fetch()` einen echten Zusatz-Fetch aus
(`_collect_future_stage_weather()`), der in `demo=True`-Vorschauen **keinen**
`FixtureProvider` übergeben bekommt (Signatur `_fetch_weather(segments, provider=None)`
wird dort ohne `provider=` aufgerufen) — das ist bestehendes Verhalten der
wiederverwendeten Methode, nicht neu eingeführt durch diesen Fix. Für Trips mit
Abend-Report und vorhandenem Trend (Regelfall) greift der Primärpfad ohne Zusatz-Fetch.

## Expected Behavior

- **Input:** Ein Trip mit mindestens zwei Etappen, dessen Folgeetappen-Wetterdaten
  (real oder `demo=True`/FixtureProvider) einen Gewitter-Zeitpunkt (`dp.thunder_level`)
  enthalten.
- **Output:** `render_sms_preview()` liefert einen Token-Text mit `TH+:{level}@{h}`,
  identisch zu `report.sms_text` derselben `_build_report()`-Ausführung.
  `render_email_preview()` zeigt denselben Gewitter-Ausblick-Text wie die tatsächlich
  versendete E-Mail für dieselbe Etappe. Ohne Gewitter in der Folgeetappe bleibt
  `TH+:-` (unverändert, kein Fehlsignal).
- **Side effects:** Vorschau-Aufrufe mit `render_options.show_multi_day_trend=True` und
  fehlendem Trend-Offset können einen zusätzlichen (Fallback-)Wetter-Fetch auslösen —
  identisches Verhalten zum Versandweg, in der Vorschau bisher nie beobachtbar, weil
  `thunder_forecast`/`multi_day_trend` dort nie berechnet wurden. Kein zusätzlicher
  API-Call im Trend-Primärpfad.

## Acceptance Criteria

- **AC-1:** Given ein Trip, dessen Folgeetappe (Tag +1) laut Wetterdaten ein
  Gewitter-Ereignis trägt (`dp.thunder_level=HIGH` zu einer bestimmten Stunde) / When
  sowohl die SMS-Vorschau (`render_sms_preview()`) als auch der Versand-Renderpfad
  (`report.sms_text`) für dieselbe Etappe im selben `_build_report()`-Lauf erzeugt
  werden / Then zeigen beide denselben `TH+`-Wert (Level und Stunde) — kein `TH+:-` in
  der Vorschau bei tatsächlichem Gewitter im Versand.

- **AC-2:** Given ein Trip, dessen Folgeetappe während der gesamten Zeitreihe kein
  Gewitter über `NONE` trägt / When die SMS-Vorschau für diese Etappe erzeugt wird /
  Then zeigt sie weiterhin `TH+:-` — kein neu erfundenes Gewitter-Signal, Bestandsverhalten
  bleibt erhalten (Regressionsschutz gegen den bestehenden Testfall ohne Gewitter).

- **AC-3:** Given den Quellcode von `preview_service.py` nach dem Fix / When geprüft
  wird, welche Funktion `thunder_forecast` (und `multi_day_trend`) dort erzeugt / Then
  ist es exakt dieselbe Methode (`TripReportSchedulerService._build_stage_trend()` bzw.
  `._build_thunder_forecast_from_trend_or_fetch()`), die auch der Versandweg
  (`trip_report_scheduler.py:836-848`) aufruft — keine zweite, im `preview_service`
  lokal nachgebaute Berechnung.

- **AC-4:** Given den bestehenden Wächter-Test `tests/tdd/test_sms_preview_matches_sent.py`
  (der laut Setup-Kommentar die `thunder`-Metrik bisher bewusst ausschließt) / When er um
  einen Fall mit aktivierter `thunder`-Metrik und echtem Gewitter-Datenpunkt erweitert
  wird / Then schlägt dieser neue Testfall vor dem Fix fehl (RED, weil `TH+:-` statt des
  echten Werts) und nach dem Fix grün (GREEN) — der Wächter ist ab jetzt nicht mehr
  strukturell blind für die Metrik, die divergierte.

- **AC-5:** Given den bestehenden Versandweg (`trip_report_scheduler.py`,
  `notification_service.py`) / When dieser Fix implementiert ist / Then bleiben alle
  bestehenden Versand-relevanten Tests (u. a. `test_thunder_forecast_trend_reuse.py`,
  `test_thunder_forecast_stage_consistency.py`) unverändert grün und keine Zeile in
  `trip_report_scheduler.py` oder `notification_service.py` wird verändert — der
  Versandweg bleibt exakt der seit #1275 adversary-verifizierte Stand.

- **AC-6:** Given denselben Trip mit Gewitter-Ereignis auf der Folgeetappe / When
  `render_email_preview()`, `render_sms_preview()` und `render_telegram_preview()` für
  dieselbe Etappe erzeugt werden / Then zeigen E-Mail-Vorschau und SMS-Vorschau
  denselben Gewitter-Wert (E-Mail: Ausblick-Text mit `thunder_forecast`; SMS: `TH+`);
  die Telegram-Vorschau bleibt für die aktuell berichtete Etappe unverändert korrekt, da
  sie `thunder_forecast` strukturell nicht konsumiert (bereits gefensterte
  `dp.thunder_level`-Werte über `seg_tables`, ADR-0025-Tabelle) — dieser Unterschied
  zwischen den drei Kanälen ist beabsichtigt und wird im Test explizit als solcher
  belegt, nicht stillschweigend vorausgesetzt.

## Known Limitations

- Der Fallback-Fetch in `_build_thunder_forecast_from_trend_or_fetch()` nutzt in
  `demo=True`-Vorschauen keinen `FixtureProvider` (siehe Implementation Details) — bei
  fehlendem Trend-Offset kann eine Demo-Vorschau serverseitig einen echten
  Live-API-Call auslösen. Bestehendes Verhalten der wiederverwendeten Methode, durch
  diesen Fix erstmals in der Vorschau sichtbar. Kein Fix-Gegenstand dieser Spec — wird
  nur dokumentiert, damit es nicht als neue Regression missverstanden wird.
- `render_telegram_preview()` bekommt durch diesen Fix `multi_day_trend` erstmals
  korrekt durchgereicht (weil `format_email()` es intern an
  `render_telegram_bubbles()` weiterreicht). Das kann in Telegram-Bubbles, die
  Mehrtages-Trend-Inhalte zeigen, zusätzliche Inhalte gegenüber dem bisherigen
  (fehlerhaften) Vorschau-Zustand sichtbar machen — konsistent mit dem Versandweg, aber
  eine sichtbare Änderung für Vorschau-Nutzer, die bisher eine unvollständige
  Telegram-Vorschau gesehen haben.

## Out of Scope

- **Versandweg** (`trip_report_scheduler.py`, `notification_service.py`) — bleibt
  unverändert, ist seit #1275 korrekt und adversary-verifiziert.
- **Extraktion einer neuen freistehenden Funktion** aus dem Scheduler — nicht nötig, da
  die Kette bereits als aufrufbare Instanzmethode existiert (siehe Implementation
  Details, „Warum keine Extraktion nötig ist").
- **`user_id="default"`-Fallback** — wird nicht eingeführt; `_load_trip()` verlangt
  bereits einen echten `user_id`-Parameter, unverändert.
- **Compact-Summary-Kopfzeile in der E-Mail-Vorschau** (`compact_summary.py`,
  ADR-0025-Changelog 2026-07-17 „vierter Rechenweg") — konsumiert `thunder_level_max`,
  nicht `thunder_forecast`, und war bereits Gegenstand des #1275-Fixes im Versandweg;
  die Vorschau nutzt denselben `_render_email()`/`format_email()`-Aufruf und profitiert
  davon ohne weitere Änderung in diesem Fix.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0025
- **Rationale:** Kein neuer ADR nötig. ADR-0025 legt fest, dass Gewitter-Aussagen über
  alle Briefing-Kanäle aus derselben gefensterten Rohdatenquelle und derselben
  kanonischen Skala abgeleitet werden — die Entscheidungen 1-5 sind kanal- und
  code-pfad-unabhängig formuliert und treffen strukturell exakt auf den Vorschau-Pfad
  zu, der beim initialen ADR nicht im Scope war (siehe Kontext-Dokument
  `docs/context/fix-1297-sms-preview-thunder.md`). Dieser Fix ist eine Erweiterung der
  bestehenden Invariante auf einen bisher unbehandelten Aufrufer derselben Funktionen,
  keine neue architektonische Entscheidung. Der ADR erhält lediglich einen
  Changelog-Eintrag, der den zuvor ungeprüften Vorschau-Pfad als jetzt abgedeckt
  vermerkt — analog zu den bereits bestehenden Nachtrags-Einträgen vom 2026-07-17.

## Changelog

- 2026-07-17: Initial spec created — deckt den in ADR-0025 explizit ausgeklammerten
  Vorschau-Pfad (`preview_service.py`) ab. Fix-Ansatz: Wiederverwendung der bereits
  existierenden `TripReportSchedulerService`-Methoden `_build_stage_trend()` und
  `_build_thunder_forecast_from_trend_or_fetch()` statt Extraktion oder
  Parallel-Implementierung.
