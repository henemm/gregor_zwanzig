---
entity_id: fix_1275_sms_th_mismatch
type: bugfix
created: 2026-07-16
updated: 2026-07-16
status: implemented
version: "1.0"
tags: [bug, sms, thunder, email, telegram]
---

# Fix #1275: SMS/E-Mail/Telegram Gewitter-Risiko-Mismatch (TH+ nutzt falsche Etappe)

## Approval

- [x] Approved

## Purpose

Die E-Mail-Outlook-Tabelle zeigt für die morgige Etappe korrekt "hoch ab 4 Uhr"
Gewitterrisiko, während SMS `TH+:-` und Telegram im selben Report "kein
Gewitter" melden — für dieselbe fachliche Aussage ("Gewitterrisiko morgen").
Grund: Zwei unabhängige, konkurrierende Berechnungen existieren im selben
Trip-Report. Dieser Fix vereinheitlicht die Datengrundlage, sodass alle drei
Kanäle (SMS, Telegram, E-Mail-Vorschau-Block) dieselbe, korrekte Aussage wie
die Outlook-Tabelle treffen.

## Source

- **File:** `src/services/trip_report_scheduler.py`
- **Identifier:** `def _build_thunder_forecast` (Zeile 1392-1453), `def _build_stage_trend` (Zeile 1263-1390), Aufrufstelle Zeile 743-750

> **Schicht-Hinweis:** Betroffener Code liegt in `src/services/` (Python-Core/Domain-Backend,
> FastAPI Core). Kein Go-API-, kein Frontend-Anteil. Downstream-Konsumenten
> (`src/output/renderers/sms_trip.py`, `src/output/renderers/email/html.py`,
> `src/services/notification_service.py`) bleiben unverändert — sie konsumieren
> nur den bereits bestehenden `thunder_forecast`-Dict-Vertrag (Level + Text je
> `+1`/`+2`), der sich nicht ändert.

## Estimated Scope

- **LoC:** ~30-50 (Refactor/Extraktion in `trip_report_scheduler.py`) + Test-LoC
- **Files:** 1 Produktionsdatei (Kern), 1 neuer Test, ggf. minimale Anpassung an
  bestehenden Trend-Tests
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `_build_stage_trend()` (`trip_report_scheduler.py:1263`) | function | Korrekte, bereits erprobte Datengrundlage (frischer Fetch je Folge-Etappe, TZ-korrekte Aggregation über alle Segmente) — wird als primäre Quelle für `thunder_forecast["+1"]` wiederverwendet |
| `_convert_trip_to_segments()`, `_fetch_weather()`, `aggregate_stage()` | function | Bereits vorhandene, in `_build_stage_trend` erprobte Fetch-/Aggregations-Kette; Basis für den Fallback-Helper bei deaktiviertem Trend (typischerweise Morning-Reports) |
| `src/output/renderers/sms_trip.py:216-229` | consumer | SMS-Pfad: mappt `thunder_forecast["+1"]["level"]` auf `TH+:{L\|M\|H}` bzw. `TH+:-` — unverändert |
| `src/output/renderers/email/html.py:1082-1093` | consumer | E-Mail "⚡ Gewitter-Vorschau"-Textblock — konsumiert denselben Dict — unverändert |
| `src/services/notification_service.py:222` | consumer | Telegram-Pfad über `request.thunder_forecast` — unverändert |
| `src/services/report_config_resolver.py:131` | config | `multi_day_trend_reports` steuert, ob `show_multi_day_trend` (und damit `_build_stage_trend`) für den jeweiligen Report-Typ aktiv ist — Default: nur `evening` |
| `tests/tdd/test_bug_874_th_plus_sms.py` | test | Format-Layer-Test (Dict rein → SMS-Token raus) — muss unverändert grün bleiben |
| `tests/integration/test_multi_day_trend.py` | test | Bestehende Trend-Tests — dürfen durch den Refactor nicht brechen |

## Implementation Details

**Root Cause:** `_build_thunder_forecast()` (Zeile 1392-1453) wird mit
`segment_weather[-1]` aufgerufen (Zeile 743-745) — dem LETZTEN Segment der
HEUTIGEN Etappe, nicht der tatsächlichen morgigen Etappe. Es durchsucht dessen
bereits geladene Zeitreihe nach Punkten, deren `dp.ts.date() == target_date+1`
ist, ohne TZ-Konvertierung vor `.date()` (Zeile 1421). Liegt das
Gewitter-Ereignis an einem anderen Waypoint als dem letzten Segment von heute
(wie im Bug-Fall: Ereignis in der morgigen Etappe), wird es nicht erfasst.
`_build_stage_trend()` (Zeile 1263-1390) macht es dagegen richtig: frischer,
unabhängiger Fetch der tatsächlichen Folge-Etappe (`_convert_trip_to_segments`
+ `_fetch_weather`), Aggregation über ALLE deren Segmente
(`aggregate_stage().thunder_level_max`), TZ-korrekt via `local_hour()`.

**Ansatz — Reihenfolge umkehren, eine gemeinsame Datengrundlage:**

1. In der Aufrufstelle (aktuell Zeile 743-750) `_build_stage_trend()` VOR
   `_build_thunder_forecast()` auswerten, wenn `render_options.show_multi_day_trend`
   aktiv ist (Default: Evening-Reports).
2. Ist ein Trend vorhanden, `thunder_forecast["+1"]` (und optional `"+2"`) aus
   `multi_day_trend[0]` (bzw. `[1]`) ableiten statt separat zu fetchen:
   - `level` aus `trend_row["thunder"]` (Name-String "NONE"/"MED"/"HIGH") zurück
     auf `ThunderLevel`-Enum mappen.
   - `text` bei MED/HIGH mit Uhrzeit "ab HH:MM" aus `trend_row["hourly_thunder"]`
     ableiten (frühester `HourlyValue.hour` mit dem Maximalwert der Etappe) —
     analog der bisherigen Textform in `_build_thunder_forecast`.
   - `date` aus dem Datum der jeweiligen Trend-Zeile (`stage.date`, nicht
     `target_date + offset` blind rechnen — siehe Known Limitations zu Lücken
     in `future_stages`).
   - Dadurch: keine doppelte Datenbeschaffung im Mehrheitsfall (Trend läuft im
     Evening-Default ohnehin), ein gemeinsamer, konsistenter Datenpfad für
     E-Mail-Outlook-Tabelle UND SMS/Telegram/E-Mail-Vorschau-Block.
3. Ist kein Trend vorhanden (Trend deaktiviert bzw. leer — typischerweise
   Morning-Reports ohne `show_multi_day_trend`), extrahierten Fallback-Helper
   nutzen: eigener, einzelner Fetch NUR der Folge-Etappe(n)
   (`_convert_trip_to_segments(trip, target_date + timedelta(days=offset))` +
   `_fetch_weather` + `aggregate_stage().thunder_level_max`) — dieselbe
   Fetch-/Aggregations-Logik wie in `_build_stage_trend`, aber ohne den
   3-Etappen-Trend-Overhead. Kein zusätzlicher API-Call im Default-Evening-Pfad;
   nur im selteneren Morning-mit-TH+-Pfad ein zusätzlicher Einzel-Etappen-Fetch.
4. **Fail-soft:** Fetch-Fehler pro Etappe dürfen den Gesamt-Report nicht
   blockieren — analog `_build_stage_trend`s `try/except` je Etappe (Zeile
   1295/1386-1388). Bei Fehler: entsprechender Key (`"+1"`/`"+2"`) fehlt im
   `thunder_forecast`-Dict → SMS zeigt `TH+:-`, E-Mail-Vorschau-Block zeigt den
   Eintrag nicht — kein Crash, kein blockierter Versand.
5. `_build_thunder_forecast()` als eigenständige Ein-Segment-Funktion entfällt
   bzw. wird zum reinen Fallback-Helper umgebaut; ihre Signatur/ihr
   Rückgabeformat (Dict mit `"+1"`/`"+2"` → `{date, level, text}`) bleibt
   erhalten, damit alle drei Downstream-Konsumenten unverändert bleiben.

## Expected Behavior

- **Input:** `trip`, `target_date`, `segment_weather` (Liste der Segmente der
  HEUTIGEN Etappe), `render_options.show_multi_day_trend` (bool), `trip_tz`.
- **Output:** `thunder_forecast`-Dict (`{"+1": {date, level, text}, "+2": {...}}`
  oder `None`), das für die tatsächliche(n) Folge-Etappe(n) berechnet ist —
  über ALLE Segmente dieser Etappe aggregiert, TZ-korrekt. Dasselbe Dict
  fließt unverändert in SMS (`TH+:`), Telegram und den E-Mail-Vorschau-Block.
  Die E-Mail-Outlook-Tabelle (`multi_day_trend`) bleibt fachlich identisch zum
  bisherigen Wert (keine Regression an der bereits korrekten Quelle).
- **Side effects:** Bei aktivem Trend (Evening-Default) kein zusätzlicher
  API-Call gegenüber heute (Trend wird ohnehin gebaut, nur die Reihenfolge
  ändert sich). Bei deaktiviertem Trend (Morning) ein zusätzlicher
  Einzel-Etappen-Fetch, wo vorher (fehlerhaft) gar kein Fetch nötig war.

## Acceptance Criteria

- **AC-1:** Given ein Trip mit Multi-Segment-Etappen, bei dem das
  Gewitter-Ereignis (HIGH) morgen an einem Waypoint der morgigen Etappe liegt
  (NICHT im letzten Segment der heutigen Etappe) / When ein Evening-Trip-Report
  für heute erzeugt wird (Trend aktiv) / Then zeigt sowohl die SMS (`TH+:H`)
  als auch die E-Mail-Outlook-Tabellenzeile für morgen dasselbe Gewitter-Level
  (HIGH) — keine widersprüchliche Aussage zwischen den beiden Kanälen im
  selben Report.
  - Test: Multi-Segment-Fixture (mind. 2 Segmente pro Etappe) mit echten
    `SegmentWeatherData`/`ForecastDataPoint`-Objekten bauen, bei dem
    `thunder_level=HIGH` ausschließlich im ersten Segment der morgigen Etappe
    auftritt (letztes Segment heute + alle anderen Segmente: `NONE`). Report
    für beide Kanäle rendern (SMS-String und E-Mail-HTML/-Outlook-Zeile) und
    prüfen, dass beide "Gewitter hoch/HIGH für morgen" ausdrücken — bewusst
    KEIN reiner Dict-Inhalts-Check, sondern Vergleich der beiden gerenderten
    Ausgaben gegeneinander.

- **AC-2:** Given denselben Trip-Report / When das `thunder_forecast`-Dict für
  Telegram (`notification_service.py` → `request.thunder_forecast`) abgeleitet
  wird / Then stimmt der Telegram-Kurzstil-Text mit dem SMS- und
  E-Mail-Ergebnis überein (dritter Konsument derselben Datengrundlage, keine
  eigene vierte Berechnung).
  - Test: Denselben Fixture-Trip aus AC-1 durch den Telegram-Formatierungspfad
    schicken und den resultierenden Text/Token auf dasselbe Gewitter-Level wie
    SMS/E-Mail prüfen.

- **AC-3:** Given ein Fetch-Fehler beim Beschaffen der Wetterdaten für die
  Folge-Etappe (z. B. Provider-Timeout) / When der Trip-Report trotzdem erzeugt
  wird / Then bricht der Report nicht ab — SMS zeigt `TH+:-`, die
  E-Mail-Vorschau enthält keinen "+1"-Eintrag, der Versand läuft fail-soft
  weiter (analog `_build_stage_trend`s Verhalten bei Fetch-Fehlern je Etappe).
  - Test: Fixture, bei der der Fetch für die Folge-Etappe eine Exception wirft
    (echte Fehlerbedingung im Fetch-Pfad, kein Mock-Theater — z. B. leere
    Segmentliste oder ungültige Koordinaten, die den bestehenden
    Fehlerbehandlungspfad auslösen); Report wird trotzdem vollständig erzeugt
    und versendet, `TH+:-` erscheint in der SMS.

- **AC-4:** Given die bestehende Test-Suite `tests/tdd/test_bug_874_th_plus_sms.py`
  (Format-Layer: `thunder_forecast`-Dict → SMS-Token) / When die
  Produktionsänderung dieses Fixes eingespielt ist / Then bleiben alle
  bestehenden Tests dieser Datei unverändert grün — der Dict-Vertrag
  (`{"+1": {date, level, text}}` → `TH+:{L|M|H|-}`) ändert sich nicht.
  - Test: `uv run pytest tests/tdd/test_bug_874_th_plus_sms.py` läuft grün ohne
    Anpassung der Testdatei selbst.

- **AC-5:** Given die bestehende Test-Suite `tests/integration/test_multi_day_trend.py`
  (Outlook-Tabellen-Trend) / When `_build_stage_trend()` durch diesen Fix als
  vorgezogene, wiederverwendete Quelle für `thunder_forecast` eingebunden wird
  / Then bleiben alle bestehenden Trend-Tests grün — die Outlook-Tabelle zeigt
  weiterhin dieselben fachlichen Werte wie vor dem Fix.
  - Test: `uv run pytest tests/integration/test_multi_day_trend.py` läuft grün.

## Known Limitations

- **Offene Frage aus der Analyse (nicht abschließend geklärt, ggf. während
  Implementierung zu entscheiden):** Ob `trend[0]` (erste zukünftige Etappe)
  für `thunder_forecast["+1"]` bei Evening-Reports exakt mit der bisherigen
  "+1 Tag ab `target_date`"-Semantik übereinstimmt, oder ob explizit über
  `stage.date == target_date + timedelta(days=1)` gematcht werden muss — falls
  `future_stages` Lücken (Ruhetage ohne eigene Etappe) enthält, könnte
  `trend[0]` NICHT dem Kalendertag "+1" entsprechen, sondern der nächsten
  tatsächlich geplanten Etappe. Empfehlung für die Implementierung: explizit
  über `stage.date` matchen statt über den Listenindex, um dieses Risiko
  auszuschließen; falls aus Zeitgründen doch über Index gegangen wird, MUSS
  dies im Implementierungs-Kommentar und im Adversary-Review explizit geprüft
  werden.
- **Bewusst NICHT Teil dieses Fixes (Nebenbefund, separate Triage):** SMS
  verwendet in `sms_trip.py:218` eine eigene `_TH_VAL`-Ordnung
  (`{NONE:0, MED:2, HIGH:3}`) statt der kanonischen `metric_format.thunder_ordinal()`
  — laut Kommentar dort bewusst so belassen ("kein Abweichler", andere
  Wertebedeutung). Dieser Fix ändert daran nichts; er behebt ausschließlich die
  falsche Datenquelle (falsche Etappe/Segment), nicht die Ordnungssystem-Frage.
  Triage nach #1199-Regel, falls weiterverfolgt.
- Der Fallback-Helper (Fetch nur bei deaktiviertem Trend, typischerweise
  Morning-Reports) führt einen zusätzlichen API-Call ein, wo vorher — fehlerhaft
  — keiner nötig war. Das ist eine bewusste Verhaltensänderung (Korrektheit vor
  Performance) und kein Regressionsrisiko im Sinne dieses Fixes, aber ein
  Nebeneffekt, der beim Staging-Verify auf Latenz/Rate-Limits zu beachten ist.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Der Fix führt kein neues Architekturmuster ein — er
  vereinheitlicht zwei bestehende, konkurrierende Implementierungen derselben
  fachlichen Aussage auf eine bereits vorhandene, bewährte Datenpfad-Logik
  (`_build_stage_trend`s Fetch-/Aggregations-Kette). Es entsteht kein neuer
  Service, keine neue Schnittstelle, kein neues Persistenzformat — lediglich
  eine Reihenfolge-Umkehr und Wiederverwendung innerhalb derselben Datei/Klasse.
  Damit ist keine ADR-würdige Entscheidung berührt (vgl. `docs/reference/sms_format.md`
  §11 "Single Source of Truth", die dieser Fix erst herstellt, nicht neu
  erfindet).

## Changelog

- 2026-07-16: Initial spec created
- 2026-07-16: Implementiert in `src/services/trip_report_scheduler.py`, Adversary VERIFIED
  nach Fix-Loop-Iteration 2 (Runde 1 fand F002/F001, behoben, Runde 2 bestätigte).
  Status → `implemented`, Approval gesetzt.
- **2026-07-17 (ERRATA, nachgetragen aus Workflow `fix-1275-sms-thunder-today`):** Diese Spec
  enthält eine faktisch falsche Behauptung über den Telegram-Kanal. Sie wird hier korrigiert,
  aber **nicht** neu geschrieben — der Fix selbst (`thunder_forecast` aus der Trend-Kette) war
  richtig und bleibt gültig.
  - **AC-2** („das `thunder_forecast`-Dict … für Telegram") wurde **nie gegen den echten
    Renderpfad geprüft** und ist für Telegram unerfüllbar formuliert:
    `render_telegram_bubbles()` (`narrow.py:359-371`) hat **kein** `thunder_forecast`-Argument,
    und `trip_report.py:189-201` übergibt auch keins. `request.thunder_forecast` fließt
    ausschließlich in `render_email()` (`trip_report.py:154`) und `format_sms()` (`:231`).
    Kein Test dieses Fixes erwähnt Telegram. Siehe Fund A in
    `docs/specs/bugfix/fix_1275_sms_thunder_today.md`.
  - **Dependencies-Tabelle, Zeile 54** (`src/services/notification_service.py:222` — „Telegram-Pfad
    über `request.thunder_forecast`") beschreibt einen Konsumpfad, den es zum Zeitpunkt dieser
    Spec **nicht gab**. Telegram berechnete sein Gewitter-Signal eigenständig aus
    `agg.thunder_level_max` — ungefenstert, und damit abweichend von SMS/E-Mail.
  - **Wirkung:** Die Telegram-Divergenz war durch diese Spec gedeckt geglaubt, aber real
    vorhanden. Behoben wird sie in `fix_1275_sms_thunder_today.md` (AC-4/AC-5), nicht hier.
    Die Wurzelursache — Kanal-Aussagen ohne Prüfung am Aufrufbaum spezifizieren — ist jetzt in
    ADR-0025 (Entscheidung 5 + Folgepflichten) geregelt.
