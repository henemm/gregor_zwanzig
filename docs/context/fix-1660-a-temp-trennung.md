# Context: fix-1660-a-temp-trennung

## Request Summary

Issue #1660 Slice A (PO-beauftragt 2026-08-09): Tages-Tief, Tages-Hoch und
Nacht-Tief sollen — jeweils für gemessene UND gefühlte Temperatur — unabhängig
voneinander wählbar sein und in allen Kanälen (SMS zuerst, konsistent auch
Mail/Telegram) wirken. Vorbild: #1484 hat exakt das für die gemessene
Nacht-Tiefsttemperatur (`temperature_night`, Token `N`) geliefert; die
gefühlte Nacht (`FN`) wurde dort als Folgeschnitt ausdrücklich abgegrenzt
(`feat_1484_night_temp_metric.md`, Abgrenzung 1).

## Zwei Mechanismen, keine neuen UI-Flächen

1. **Nacht-Abspaltung gefühlt (`FN`):** neuer Katalogeintrag analog
   `temperature_night` — Muster 1:1 aus #1484 übertragbar.
2. **Tages-Tief ↔ Tages-Hoch (`K`↔`D`, `FK`↔`FD`):** über die BESTEHENDE
   Aggregations-Auswahl (`MetricConfig.aggregations`, UI seit #1357:
   `frontend/.../weather-metrics-tab/aggregationSelection.ts`). Die
   E-Mail-Pfade lesen sie seit #1357 (`email/compact.py:174`,
   `email/plain.py:203`, `email/html.py:1430`) — die SMS-Kette liest sie
   NICHT. PO-Vorgabe aus #1660: keine neue Editor-Fläche bauen; die
   Pro-Kanal-Kaskade (#429/#434) liefert `MetricConfig` inkl. `aggregations`
   bereits kanalgenau (`models.py::get_metrics_for_channel`, von
   `trip_report.py:291` für SMS gelesen).

## Related Files

| File | Relevance |
|------|-----------|
| `src/app/metric_catalog.py:139-150` | Vorbild `temperature_night`; neuer Eintrag `wind_chill_night` daneben |
| `src/output/renderers/sms_trip.py:118-123` | `SMS_MULTI_SYMBOLS_BY_METRIC`: `wind_chill: (FN,FK,FD,WC)` aufteilen |
| `src/output/renderers/trip_report.py:285-333` | SMS-Spec-Aufbau aus Kanal-Kaskade; hier muss die Aggregations-Gate-Logik für K/D/FK/FD rein |
| `src/output/tokens/builder.py:262-304` | Sechs Temperatur-Token; je Symbol eigene `MetricSpec` — Schichtgrenze: importiert nichts aus `src/app/` |
| `src/services/segment_weather.py:395-407` | `night_weather_needed()`: um `wind_chill_night` erweitern (#1484 AC-8-Analogon) |
| `src/output/renderers/compact_summary.py:195-198,338-347` | Gefühlte Nacht-Untergrenze hängt an `wind_chill` → auf `wind_chill_night` umbinden |
| `src/output/renderers/narrow.py:501-522` | Telegram-Abendübersicht: Nachtwert für `wind_chill` → an neue Größe binden |
| `src/output/renderers/trip_metric_ids.py` | Bestandsdaten-Ableitung (#1484-Muster `derived=True`) — `wind_chill_night` ergänzen |
| `frontend/.../weather-metrics-tab/aggregationSelection.ts` | Bestehende min/max-Auswahl — KEINE Änderung erwartet, nur Verifikation |
| `internal/model/alert_metric_mapping.generated.json` | Paritätstest bedienen (kein `alert_metrics` am neuen Eintrag → kein Mapping-Eintrag) |

## Existing Patterns

- **#1484 komplett als Blaupause:** Katalogeintrag ohne `summary_fields`/
  `alert_metrics`, Bestandsableitung beim Lesen (aktiviert gdw. Elternmetrik
  aktiv, `derived=True`, nie serialisiert), `night_weather_needed()` teilt
  Versand/Vorschau, Abend-Gate bleibt in `builder.py` (`evening_only`).
- **Aggregations-Lesen:** `{mc.metric_id: mc.aggregations for mc in ...}` —
  Muster aus `email/html.py:1430`; für SMS analog aus
  `get_metrics_for_channel("sms", report_type)` ableitbar.
- **Kürzel-Ratsche:** `tests/unit/test_sms_token_symbol_register_ratchet.py`
  sichert Register↔`tokens/`-Literale; `builder.py` bleibt literal.

## Dependencies

- Upstream: Kanal-Kaskade (#429/#434/#1575), Nachtfenster-Berechnung
  (`day_window.night_wind_chill_min_c`), Aggregations-Persistenz (#1357).
- Downstream: SMS-Fidelity-Vorschau (`carried_ids`, vgl. #923b), Telegram-
  Kurzform (= SMS-Prüfweg), `briefing_mail_validator` (Mail-Pfad),
  Golden-E-Mail-Tests (dürfen bit-identisch bleiben, solange Default-
  Aggregationen unverändert).

## Existing Specs

- `docs/specs/modules/feat_1484_night_temp_metric.md` — Vorbild + Abgrenzung 1
- `docs/specs/modules/night_temp_evening_only.md` — Abend-Gate (DEC-1/DEC-2)
- `docs/specs/modules/sms_daywindow_aggregation.md` — Tagesfenster-Werte
- `docs/specs/modules/sms_format.md` — Token-Grammatik v2.x

## Risks & Considerations

- **WC (Wintersport-Tageskennzahl)** hängt mit an `wind_chill` — bei der
  Aufteilung entscheiden, ob WC bei `wind_chill` bleibt (empfohlen: ja, es
  ist ein Tageswert) — sonst Regression #1450.
- **Default-Aggregationen:** `temperature`/`wind_chill` haben heute
  `("min","max")` als Default → Bestands-Trips zeigen K+D/FK+FD weiter beide;
  nur eine BEWUSSTE Abwahl im Editor darf ein Token entfernen (kein stiller
  Verlust, Analogie #1484 AC-6/AC-7).
- **`aggregations` enthält ggf. auch "avg"** (Temperatur-Default war mal
  min/max/avg) — Gate darf nur min→K, max→D abbilden, avg ignorieren.
- **Kanal-Konsistenz:** Die Aggregations-Abwahl wirkt in Mail seit #1357 —
  nach diesem Schnitt zusätzlich in SMS; Telegram-Kurzform folgt dem SMS-Weg.
  Prüfen, dass narrow/compact_summary (eigene Untergrenzen-Logik) nicht
  widersprechen.
- **Schichtgrenze `output/tokens/`:** keine Register-Importe; Steuerung
  ausschließlich über `MetricSpec.enabled` je Symbol (bestehender Weg über
  `disabled_specs` in `trip_report.py`).
