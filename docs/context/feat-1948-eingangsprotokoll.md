# Context: feat-1948-eingangsprotokoll (Scheibe 1 aus #1948)

**Issue:** #1948 · **Scheibe:** S1 Debug-Eingangs-Protokoll (PO-Reihenfolge: „Daten sammeln ist der erste Schritt")
**Konzept (PO-freigegeben, alle Entscheidungen gefallen):** `docs/analysis/alarm-format-konzept-2026-08.md`

## Was gebaut wird

Rollierendes Protokoll des ROHEN Eingangszustands jeder verarbeiteten Alarm-Meldung, für alle
drei Alarm-Zweige — damit nachvollziehbar wird, aus welchen Eingangsdaten welche Nachricht
wurde (PO-Befund: der API-Eingang wird heute nirgends geloggt), und damit Scheibe 2
(Testmeldungs-Einspeisung) echte aufgezeichnete Meldungen wiedereinspielen kann.

## Einhängepunkte je Zweig (aus der Ist-Inventur, verifiziert)

| Zweig | Einhängepunkt | Fundstelle |
|---|---|---|
| (a) Δ-Alarm | nach Delta-Berechnung, vor `_send_alert` | `src/services/trip_alert.py` (~Z. 352) |
| (b) amtliche Warnung | HTTP-Layer `warn_egress.cached_fetch` — deckt GeoSphere+MeteoAlarm+DPC | `src/services/official_alerts/geosphere_warn.py:99`; letzter Roh-Payload `:167` |
| (c) Nowcast | vor `_derive_result` | `src/services/radar_service.py` (~Z. 167–210) |

## Bestehende Bausteine (erweitern, NICHT neu bauen)

- `src/services/alert_log.py` (#1459): geteiltes ENTSCHEIDUNGS-Protokoll aller drei Zweige
  (`reason` ∈ forecast_change/nowcast/official_alert). Lücke: kein Eingangszustand.
  → Eingangs-Protokoll als Begleit-Log, verknüpfbar mit dem `alert_log`-Eintrag (Kern des
  PO-Wunsches: Eingang ↔ Ausgang zuordenbar).
- Retention-Vorlage: `WeatherSnapshotService._prune_dated_snapshots`
  (`src/services/weather_snapshot.py:154/165` — behält 7, sortiert `st_mtime`).

## Constraints (PFLICHT)

- Multi-User: Ablage unter `data/users/<user_id>/…`, niemals `"default"`-Fallback.
- Keine Secrets/Tokens im Mitschnitt.
- Observability: neuer Schreiber braucht `last_run`-Sichtbarkeit (CLAUDE.md-Regel).
- #1944 geht in dieser Scheibe auf (Kommentar dort existiert). #1929 läuft parallel
  (`official_alerts.py:1896-2104` nicht anfassen — hier ohnehin nicht nötig).
- Ortsvergleich zurückgestellt — Compare-Zweige nur mitschneiden, wenn es über dieselben
  geteilten Dienste ohne Zusatzaufwand mitfällt; kein Compare-spezifischer Bau.

## Affected Files (erwartet)

- NEU: `src/services/alert_input_capture.py` (o. ä. — Name folgt Verhalten)
- `src/services/trip_alert.py` (Einhängung a)
- `src/services/official_alerts/geosphere_warn.py` (Einhängung b, `warn_egress`-Naht)
- `src/services/radar_service.py` (Einhängung c)
- Tests (neu, deterministischer Kern)

## Analyse-Kurzfassung (Phase 2)

Wurzelbefund und Gesamtbild stehen im Konzept-Dokument (§1–§9): drei unabhängig gewachsene
Zweige ohne gemeinsame Beobachtbarkeit; `alert_log` protokolliert Entscheidungen, niemand
protokolliert Eingänge; Einspeisung (S2) braucht die Aufzeichnungen aus dieser Scheibe.
Historie der PO-Entscheidungen: Issue #1948, Kommentare vom 2026-08-17.
