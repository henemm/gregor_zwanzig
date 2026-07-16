# Context: fix-1275-sms-th-mismatch

## Request Summary
Issue #1275: Die E-Mail zeigt für die Etappe "morgen" ein Gewitter-Risiko "hoch ab 4 Uhr" in der Stundentabelle, während dieselbe Trip-Benachrichtigung per SMS `TH+:-` (kein Gewitterrisiko) meldet. Beide Kanäle widersprechen sich für denselben Report.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:743` | Baut `thunder_forecast = self._build_thunder_forecast(segment_weather[-1], target_date, tz=trip_tz)` — Eingabe für **sowohl** SMS TH+ als auch E-Mail-Gewitter-Vorschau |
| `src/services/trip_report_scheduler.py:1392-1449` | `_build_thunder_forecast()` — scannt NUR `last_segment.timeseries.data` (ein einziges Segment) nach `dp.thunder_level` für `target_date+1`/`+2` |
| `src/services/trip_report_scheduler.py:655` | `segment_weather = self._fetch_weather(segments)` — Liste ALLER Segmente der Etappe; `_build_thunder_forecast` bekommt aber nur `segment_weather[-1]` (letztes Segment) |
| `src/output/renderers/sms_trip.py:216-229` | SMS-Pfad: mappt `thunder_forecast["+1"]["level"]` auf `TH+:{L\|M\|H}` bzw. `TH+:-` |
| `src/output/renderers/email/html.py:1082-1093` | E-Mail "⚡ Gewitter-Vorschau"-Textblock — konsumiert **denselben** `thunder_forecast`-Dict wie SMS |
| `src/services/trip_report_scheduler.py:1263-1391` | `_build_stage_trend()` — **KORREKTE dritte Quelle:** frischer, unabhängiger Fetch je Folge-Etappe (`_convert_trip_to_segments` + `_fetch_weather`), `aggregate_stage().thunder_level_max` über ALLE Segmente dieser Etappe, TZ-korrekt via `local_hour()` |
| `src/output/renderers/email/html.py:1195-1240` | **Das ist die vom User gezeigte breite Tabelle** ("Ausblick"/Outlook-Tabelle, Spalte "Gew", Text z.B. "hoch @4") — rendert `multi_day_trend` aus `_build_stage_trend()`, NICHT aus `thunder_forecast` |
| `src/services/report_config_resolver.py:131` | `multi_day_trend_reports=["evening"]` — `_build_stage_trend()` läuft standardmäßig nur bei Evening-Reports; bei Morning-Reports ist `multi_day_trend=None` |
| `src/services/risk_engine.py:121-129` | `_check_thunder()` — separate Risk-Klassifikation (HIGH/MED) aus `agg.thunder_level_max`, aggregiert über alle Segmente |
| `src/output/metric_format.py:202` | `thunder_ordinal()` — kanonische Ordnungsquelle für Thunder-Level; laut Kommentar in `sms_trip.py:218` bewusst NICHT von der SMS-Kodierung verwendet (eigene `_TH_VAL`-Map) |

## Existing Patterns
- **Zwei unabhängige, strukturell verschiedene Berechnungen für "Gewitter morgen" im selben Report:**
  1. **Quelle A (korrekt), `_build_stage_trend()`:** frischer Fetch der tatsächlichen Folge-Etappe, Aggregation über alle deren Segmente, TZ-korrekt → speist NUR die E-Mail-Outlook-Tabelle.
  2. **Quelle B (fehlerhaft), `_build_thunder_forecast()`:** durchsucht die bereits geladene, mehrtägige Zeitreihe des LETZTEN Segments der HEUTIGEN Etappe nach Punkten von morgen — falsche Etappe, ein Segment, ohne erkennbare TZ-Konvertierung → speist SMS `TH+` UND den kleinen E-Mail-Block "⚡ Gewitter-Vorschau".
- Bug #874 (`docs/specs/modules/bug_874_th_plus_sms.md`) hat die Verdrahtung `thunder_forecast["+1"] → TH+:` spezifiziert und mit Unit-Tests (`tests/tdd/test_bug_874_th_plus_sms.py`) abgesichert — aber nur auf Formatierungsebene (Dict rein, Token raus). Kein Test prüft, ob `_build_thunder_forecast()` selbst die richtige Etappe/richtigen Segmente abtastet.
- `sms_trip.py:218` dokumentiert bewusst eine SMS-eigene Kodierung parallel zur "kanonischen" `metric_format.thunder_ordinal` — als Nebenbefund vermerkt, nicht ursächlich für #1275.
- `docs/reference/sms_format.md` §11 "Single Source of Truth": "Implementationen, die SMS-Text und E-Mail-Subject/Content getrennt erzeugen, sind als Bug zu betrachten." — die aktuelle Zwei-Quellen-Situation verletzt dieses Prinzip direkt.

## Dependencies
- **Upstream:** `_fetch_weather(segments)` liefert `segment_weather` (Liste, pro Segment eine `SegmentWeatherData` mit `.timeseries.data` von `dp.thunder_level`-Werten je Provider-Zeitpunkt). Provider-Normalisierung: `src/providers/openmeteo.py`.
- **Downstream:** `thunder_forecast`-Dict wird injiziert in `format_sms()` (SMS), `render_html()`/`plain.py` (E-Mail-Vorschau-Block) sowie `notification_service.py:222` (Telegram-Pfad über `request.thunder_forecast`). Ein Fix an `_build_thunder_forecast()` wirkt also auf **alle drei Kanäle** gleichzeitig.

## Existing Specs
- `docs/specs/modules/bug_874_th_plus_sms.md` — Spec für die bestehende TH+-Verdrahtung (Format-Layer, nicht Daten-Beschaffung)
- `docs/reference/sms_format.md` — SMS-Wire-Format inkl. `TH+:` Token-Bedeutung
- `docs/specs/tests/issue_759_669_email_ampel_gewitter_tests.md`, `docs/specs/modules/*` — weitere Gewitter-bezogene Specs (Ampel/Badge in E-Mail)

## Risks & Considerations
- **Hauptverdacht:** `_build_thunder_forecast(segment_weather[-1], ...)` betrachtet nur EIN Segment (das letzte) der Etappe, während die Stundentabelle über ALLE Segmente/Waypoints rendert. Liegt das Gewitter-Ereignis (04:00) an einem anderen Waypoint als dem letzten, wird es von `TH+` nicht erfasst — strukturelle Unvollständigkeit, kein reiner Zeitzonen-Bug.
- **Sekundärverdacht:** `dp.ts.date() == fc_date`-Filterung in `_build_thunder_forecast` vergleicht ohne erkennbare TZ-Konvertierung vor `.date()` — bei einem Ereignis um 04:00 lokal ist ein UTC/Lokalzeit-Grenzfall (Datum kippt) nicht auszuschließen und müsste in der Analyse-Phase geprüft werden.
- Fix betrifft eine gemeinsam genutzte Funktion (SMS + E-Mail-Vorschau + Telegram) — Blast Radius bestätigt hoch; Tests müssen alle drei Konsum-Pfade abdecken, nicht nur SMS.
- Kein Mock erlaubt (Projektregel) — Reproduktion muss mit echten/aufgezeichneten `SegmentWeatherData`-Fixtures erfolgen, die ein Multi-Segment-Szenario mit Gewitter NICHT im letzten Segment abbilden.
- Nebenbefund für spätere Triage (nicht Teil dieses Fixes): SMS verwendet eigene `_TH_VAL`-Ordnung statt `metric_format.thunder_ordinal` (`sms_trip.py:218`) — nicht ursächlich für #1275 (siehe Analyse), aber weiter als Zwei-Ordnungssysteme-Altlast vermerkt.

## Analysis

### Type
Bug — bestätigt durch Code-Verifikation (nicht nur Symptom-Beschreibung des Users). Zwei unabhängige, konkurrierende Implementierungen derselben fachlichen Aussage ("Gewitterrisiko morgen") sind vorhanden; sie können und tun divergieren.

### Root Cause (verifiziert)
`_build_thunder_forecast()` (`trip_report_scheduler.py:1392-1449`), Eingabe für SMS `TH+` (`sms_trip.py:216-229`), Telegram (`notification_service.py:222`) und den E-Mail-Block "Gewitter-Vorschau" (`html.py:1082-1093`), fragt die FALSCHE Datengrundlage ab: die bereits geladene Zeitreihe des LETZTEN Segments der HEUTIGEN Etappe (`segment_weather[-1]`, Zeile 743), gefiltert per `dp.ts.date() == fc_date` ohne erkennbare TZ-Konvertierung.

Die vom User in der E-Mail gezeigte "hoch ab 4 Uhr"-Aussage stammt dagegen aus der Outlook-Tabelle (`html.py:1195-1240`), gespeist von `_build_stage_trend()` (Zeile 1263), die für die tatsächliche morgige Etappe einen frischen, korrekten Fetch macht (`_convert_trip_to_segments` + `_fetch_weather` + `aggregate_stage().thunder_level_max`, TZ-korrekt via `local_hour()`).

Verletzt `docs/reference/sms_format.md` §11 (Single Source of Truth) und §3.2/§9 (TH+ soll "wie TH, aber +1 Tag" sein — vollwertige Etappen-Aggregation, nicht Ein-Segment-Restdaten von heute).

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|--------------|
| `src/services/trip_report_scheduler.py` | MODIFY | Gemeinsamen Helper extrahieren (analog `_build_stage_trend`-Fetch-Logik); `_build_thunder_forecast()` durch Aufruf dieses Helpers ersetzen bzw. — wenn `multi_day_trend` bereits berechnet wurde (Evening-Default) — dessen Ergebnis für `+1` wiederverwenden statt doppelt zu fetchen; fail-soft bei Fetch-Fehler (wie `_build_stage_trend`s try/except je Etappe) |
| `tests/tdd/test_bug_1275_sms_th_mismatch.py` (bzw. finaler Modul-Testname) | CREATE | Roter Bug-Beweis-Test: Trip mit unterschiedlichem Gewitter heutige-letztes-Segment vs. morgige-Etappe → SMS `TH+` und Outlook-"Gew" müssen konsistent sein |
| `tests/tdd/test_bug_874_th_plus_sms.py` | KEEP (grün halten) | Format-Layer-Test bleibt unverändert gültig (Dict rein → Token raus) |
| `tests/integration/test_multi_day_trend.py` | KEEP (grün halten) | Bestehende Trend-Tests dürfen durch Refactor nicht brechen |

### Scope Assessment
- Files: 1 Produktionsdatei (Kern), 1 neuer Test, ggf. minimale Anpassung an bestehenden Trend-Tests
- Estimated LoC: ~30-50 (Refactor/Extraktion), + Test-LoC
- Risk Level: MEDIUM — Blast Radius bleibt hoch (3 Kanäle betroffen), aber Fix nutzt bereits vorhandene, bewährte Logik statt Neuentwicklung; kein neuer API-Call im Default-Evening-Pfad (Trend läuft dort ohnehin), nur im selteneren Morning-mit-TH+-Pfad ein zusätzlicher Einzel-Etappen-Fetch

### Technical Approach
Empfehlung (aus Plan/Sonnet-Bewertung): Reihenfolge umkehren — `_build_stage_trend()` zuerst aufrufen (wenn `show_multi_day_trend` aktiv), `thunder_forecast["+1"]` aus dessen erster Trend-Zeile ableiten. Nur wenn Trend deaktiviert/leer ist (typischerweise Morning-Reports), fällt ein extrahierter Helper auf einen eigenen, einzelnen Fetch der Folge-Etappe zurück (kein 3-Etappen-Trend nötig). Damit: keine doppelte Datenbeschaffung im Mehrheitsfall, ein Konsistenz garantierender gemeinsamer Datenpfad für alle drei Kanäle, fail-soft bei Fetch-Fehler statt Report-Blockade.

### Dependencies
- Upstream: `_convert_trip_to_segments()`, `_fetch_weather()`, `aggregate_stage()` (bereits vorhanden, in `_build_stage_trend` erprobt)
- Downstream: SMS (`sms_trip.py`), Telegram (`notification_service.py`), E-Mail-Vorschau-Block (`html.py`) — alle drei bleiben unverändert, da sie nur den `thunder_forecast`-Dict-Vertrag konsumieren (Level + Text je `+1`/`+2`), der sich nicht ändert

### Open Questions
- [ ] Reicht `trend[0]` (erste zukünftige Etappe) für `thunder_forecast["+1"]` bei Evening-Reports exakt überein mit der bisherigen "+1 Tag ab target_date"-Semantik, oder muss über `stage.date` explizit gematcht werden (falls `future_stages` Lücken/Ruhetage enthält)?
- [ ] Soll der Nebenbefund (SMS-eigene `_TH_VAL`-Ordnung statt `thunder_ordinal`) in diesem Fix mit bereinigt werden, oder separat nach #1199-Triage-Regel behandelt werden? (Empfehlung: separat, da nicht ursächlich für #1275)
