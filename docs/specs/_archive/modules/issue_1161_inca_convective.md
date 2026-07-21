---
entity_id: issue_1161_inca_convective
type: feature
created: 2026-07-09
updated: 2026-07-09
status: draft
version: "1.0"
tags: [providers, alerts, weather, nowcast, radar, convective, inca, geosphere]
---

# INCA-Nowcast: Gewitter/Hagel-Erkennung für Österreich (Issue #1161)

## Approval

- [ ] Approved

## Purpose

Schließt die in `docs/specs/modules/radar_convective_stage.md` (Issue #660) dokumentierte Known Limitation: Der GeoSphere-INCA-Pfad (`_fetch_geosphere_inca`) setzt `RadarFrame.is_convective` aktuell nie, weil das INCA-NOWCAST-Produkt kein Gewitter-/Blitz-Feld liefert. AT-Orte verlieren dadurch die Eskalationsstufe „Starker Hagel/Gewitter", obwohl sie über eine amtliche 1-km-Nowcast-Quelle laufen. Diese Spec ergänzt einen Open-Meteo-Sidecar-Call, der ausschließlich das Konvektions-Flag liefert (Regen-Intensität bleibt weiter INCA-basiert), und macht einen fehlgeschlagenen Sidecar-Call gemäß ADR-0018 sichtbar statt ihn als „geprüft, kein Gewitter" zu kaschieren.

## Source

- **File:** `src/services/radar_service.py`
- **Identifier:** `RadarNowcastService._fetch_geosphere_inca`, `RadarNowcastService._fetch_openmeteo_15`, `RadarNowcastService._derive_result`, `RadarNowcastService.format_now_text`, `NowcastResult`
- **Schicht:** Python-Backend (`src/services/`) — kein Go, kein Frontend. Reiner Nowcast-Pfad; `src/services/risk_engine.py` (CAPE-basierter mehrtägiger Pfad) ist explizit **nicht** betroffen.

## Estimated Scope

- **LoC:** ~120–180 (Sidecar-Merge + Toleranz-Match + `convective_checked`-Feld/Propagierung + Text-Hinweis + Tests)
- **Files:** 1 produktiv (`src/services/radar_service.py`) + 2 Testdateien (`tests/tdd/test_feature_770_inca_nowcast_fix.py`, `tests/tdd/test_feature_660_convective_stage.py`); optional `tests/tdd/test_feature_656_radar_nowcast.py` nur falls dort `is_convective=False` für INCA hart asserted wird
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `RadarNowcastService._fetch_openmeteo_15(lat, lon, models=None)` | internal helper (bereits produktiv) | Liefert global `best_match`-Frames inkl. `is_convective` (WMO 95/96/99) — wird hier als Sidecar für den Konvektions-Indikator wiederverwendet, ohne neuen HTTP-Client-Code |
| `providers.geosphere.GeoSphereProvider.fetch_nowcast` | provider (unverändert) | Bleibt alleinige Quelle für Regen-Intensität/Onset im INCA-Pfad |
| `providers.brightsky.RadarFrame` | model (unverändert) | Trägt bereits additiv `is_convective: bool = False` — keine Änderung nötig |
| `services.trip_alert.TripAlertService.check_radar_alerts` | downstream consumer | Konsumiert `NowcastResult.is_convective`; muss `convective_checked` nicht zwingend auswerten (optional, kein Muss-Scope dieser Spec), aber Regressionscheck erforderlich |
| ADR-0018 (Nicht-Kaschieren-Invariante) | Architekturentscheidung | Verbietet stillen Fallback auf `is_convective=False` bei Sidecar-Ausfall |

## Implementation Details

### `NowcastResult` (Dataclass-Erweiterung)
Additives Feld `convective_checked: bool = True` (Default `True` — radar/AROME-FR/ICON-D2/`minutely_15` prüfen Konvektion bereits inhärent über ihre eigenen `weather_code`-Auswertung bzw. besitzen kein Konvektionsfeld und liefern konsistent `is_convective=False`, was kein Sidecar-Fail ist). `False` ausschließlich im INCA-Pfad, wenn der Open-Meteo-Sidecar-Call scheitert.

### `_fetch_geosphere_inca(lat, lon)` (erweitert)
1. Baut wie bisher die INCA-`RadarFrame`-Liste aus `GeoSphereProvider.fetch_nowcast()` (Regen-Intensität, Timestamps — **unverändert**).
2. Ruft zusätzlich `self._fetch_openmeteo_15(lat, lon)` auf (kein `models=`-Parameter → globaler `best_match`, liefert Frames mit `is_convective`).
3. **Erfolgsfall:** Für jeden INCA-Frame wird das zeitlich nächste Sidecar-Frame gesucht; liegt dessen Timestamp-Abstand ≤ 5 Minuten, wird `is_convective` vom Sidecar-Frame auf das INCA-Frame gemerged (`inca_frame.is_convective = sidecar_frame.is_convective`). Kein Match innerhalb der Toleranz → INCA-Frame bleibt `is_convective=False` (konservativ, kein Fehlalarm).
4. **Fail-Soft-Fall:** Liefert `_fetch_openmeteo_15` eine leere Liste (Exception intern bereits abgefangen, Fail-Soft-Vertrag unverändert), werden die INCA-Regen-Frames unverändert zurückgegeben (Regen-Funktionalität bleibt bestehen — kein Totalausfall), aber die Methode signalisiert den fehlenden Konvektions-Check an den Aufrufer (z. B. via Rückgabe eines zusätzlichen Flags/Tupel-Elements oder Instanzattribut, das `_derive_result` ausliest — Umsetzungsdetail für die Implementierungsphase, Vertrag: `convective_checked=False` muss bis in `NowcastResult` durchgereicht werden).
5. Rückgabe/Rückgabetyp bleibt für alle bestehenden Aufrufer der Source-Chain (`_fetch_frames_with_fallback`) kompatibel — reine Erweiterung, kein Breaking Change an der `list`-Rückgabe der Frames selbst.

### Toleranzfenster
±5 Minuten für den Timestamp-Match zwischen INCA-Frame und Sidecar-Frame (INCA liefert 15-Minuten-Schritte, Open-Meteo `minutely_15` ebenfalls 15-Minuten-Schritte, aber mit potenziell leicht versetztem Raster — z. B. INCA auf `:00/:15/:30/:45`, Open-Meteo ggf. relativ zum Abrufzeitpunkt). Kein exaktes `==`.

### `_derive_result(frames, source)`
Unverändert in der Kernlogik (Onset/Intensity/`is_convective`-Aggregation über das Zeitfenster). Erweitert um Propagierung von `convective_checked` in den `NowcastResult` — Default `True`, außer die Frame-Quelle hat explizit `convective_checked=False` signalisiert (nur INCA-Pfad bei Sidecar-Fail).

### `format_now_text(result, ...)`
Bei `result.convective_checked is False` wird eine zusätzliche Zeile angehängt: **„Gewitter-Check nicht verfügbar."** — direkt nach der Intensitäts-/Onset-Zeile, vor der optionalen Quellen-Zeile. Bei `convective_checked=True` (Default, alle bestehenden Pfade) ändert sich der Text nicht — keine Regression.

## Expected Behavior

- **Input:** AT-Koordinaten (innerhalb der INCA-Bounding-Box, z. B. Innsbruck `47.2692, 11.4041`) für `get_nowcast()` bzw. den Alert-Tick.
- **Output:** Bei konvektiver Wetterlage laut Open-Meteo-Sidecar zeigt der INCA-Pfad dieselbe Eskalationsstufe „Starker Hagel/Gewitter" wie der globale Open-Meteo-Pfad. Bei Sidecar-Ausfall bleibt die Regen-Nowcast (Onset/Intensität) voll funktionsfähig, aber Text/Ergebnis weisen sichtbar aus, dass der Gewitter-Check nicht möglich war.
- **Side effects:** Ein zusätzlicher HTTP-Call (Open-Meteo) pro INCA-Nowcast-Anfrage. Kein zusätzlicher State, kein neuer Alert-Typ — bestehende Alert-Throttle-Logik in `trip_alert.py` bleibt unverändert.

## Acceptance Criteria

- **AC-1:** Given ein INCA-Frame mit Timestamp `T` und ein Open-Meteo-Sidecar-Frame mit Timestamp innerhalb `T ± 5 Min` und `weather_code ∈ {95, 96, 99}` / When `_fetch_geosphere_inca(lat, lon)` (bzw. der interne Merge-Schritt) läuft / Then trägt das zurückgegebene INCA-`RadarFrame` `is_convective=True`, während `precip_mm_h` weiterhin aus der INCA-Regen-Quelle stammt (unverändert).
  - Test: DI-Seam mit echten (nicht gemockten) INCA- und Open-Meteo-`RadarFrame`-Objekten durch den Merge-Helper/die Methode geschickt (Pattern aus `test_feature_660_convective_stage.py`); assert `is_convective=True` und `precip_mm_h` bleibt der INCA-Wert. Kein Mock/patch/MagicMock.

- **AC-2:** Given ein INCA-Frame ohne zeitlich passendes konvektives Sidecar-Frame (Sidecar liefert `weather_code` außerhalb {95,96,99} oder kein Match innerhalb ±5 Min) / When derselbe Merge-Schritt läuft / Then bleibt `is_convective=False` und das bestehende 4-Stufen-Verhalten (`intensity_to_text` ohne Konvektions-Override) ist bit-identisch zum Vor-Feature-Zustand — Regressionsschutz für den Nicht-Gewitter-Fall.
  - Test: Gleiches DI-Pattern wie AC-1 mit nicht-konvektiven Sidecar-Frames; assert `is_convective=False` und `intensity_to_text(max_rate, is_convective=False)` liefert dieselbe Stufe wie vor dieser Änderung (Vergleich gegen bestehende Assertions aus `test_feature_660_convective_stage.py`/`test_feature_770_inca_nowcast_fix.py`).

- **AC-3:** Given der Open-Meteo-Sidecar-Call schlägt fehl (z. B. durch eine absichtlich ungültige/nicht erreichbare Konfiguration im Testkontext, real ausgelöst, kein Mock der Exception) / When `_fetch_geosphere_inca` bzw. `get_nowcast` läuft / Then bleibt die INCA-Regen-Nowcast (Onset/Intensität) unverändert nutzbar, `NowcastResult.convective_checked == False`, `is_convective` wird NICHT stillschweigend als geprüftes `False` behandelt, und `format_now_text(result)` enthält den Hinweis „Gewitter-Check nicht verfügbar.".
  - Test: Realer Fehlerpfad — z. B. echter HTTP-Call gegen eine bewusst ungültige Open-Meteo-URL/Timeout-Konfiguration (kein `Mock()`/`patch()`), der den bestehenden `_fetch_openmeteo_15`-Fail-Soft-Zweig (`except Exception` → `[]`) real auslöst; assert `convective_checked=False` im `NowcastResult` und der Hinweistext ist in `format_now_text`-Output enthalten. Belegt echtes Verhalten, kein Dateiinhalt-Check.

- **AC-4:** Given eine reale AT-Koordinate innerhalb der INCA-Bounding-Box (z. B. Innsbruck `47.2692, 11.4041`) ohne injizierten `frame_source` (also über die echte Source-Chain) / When `RadarNowcastService().get_nowcast(lat, lon)` läuft / Then liefert das Ergebnis ein `NowcastResult` mit `source == "INCA"` (sofern INCA erreichbar; Fail-Soft-Kette bleibt sonst unverändert aktiv) und einem gesetzten `convective_checked`-Feld (`True` oder `False`, je nach tatsächlicher Sidecar-Erreichbarkeit zum Testzeitpunkt) — end-to-end echter HTTP-Verhaltensnachweis, kein Dateiinhalt-Check.
  - Test: Echter Aufruf ohne DI-Seam gegen die produktive Source-Chain (analog zu bestehenden Live-API-Tests in `test_feature_770_inca_nowcast_fix.py`); assert `NowcastResult` hat Attribut `convective_checked` vom Typ `bool` (keine feste Erwartung des konkreten Werts, da wetterabhängig — Test beweist Vorhandensein/Propagierung des Signals end-to-end, nicht eine bestimmte Wetterlage).

## AC-Test-Mapping (Test-Plan)

| AC | Testfunktion (vorgeschlagen) | Testdatei |
|----|------------------------------|-----------|
| AC-1 | `test_ac1_inca_merges_convective_flag_from_sidecar` | `tests/tdd/test_feature_660_convective_stage.py` |
| AC-2 | `test_ac2_inca_non_convective_sidecar_unchanged` | `tests/tdd/test_feature_660_convective_stage.py` |
| AC-3 | `test_ac3_inca_sidecar_failure_sets_convective_checked_false` | `tests/tdd/test_feature_770_inca_nowcast_fix.py` |
| AC-4 | `test_ac4_inca_live_get_nowcast_has_convective_checked_field` | `tests/tdd/test_feature_770_inca_nowcast_fix.py` |

## Known Limitations

- Der Sidecar-Call verdoppelt die HTTP-Last pro INCA-Anfrage (ein zusätzlicher Open-Meteo-Call). Bei sehr hoher Anfragefrequenz (z. B. viele parallele Alert-Ticks für AT-Trips) potenziell relevantes, aber bewusst akzeptiertes Trade-off gegen die Sicherheitsrelevanz der Gewitter-Erkennung.
- Toleranz ±5 Min ist ein bewusst gewählter, nicht empirisch kalibrierter Wert (INCA und Open-Meteo `minutely_15` sind beide 15-Minuten-Raster, aber mit potenziell leicht versetztem Ankerpunkt). Sollte sich in der Praxis zeigen, dass Matches regelmäßig knapp scheitern oder zu großzügig sind, ist eine Nachjustierung als separates Issue vorzunehmen.
- `convective_checked=False` wird aktuell nur im Text (`format_now_text`) und im `NowcastResult`-Feld sichtbar gemacht — keine eigene Health-Metrik/BetterStack-Eskalation analog ADR-0018 Punkt 3 (Health-Aggregat für `fetch_forecast`-Fallbacks). Das ist bewusst außerhalb des Scopes dieser Spec; falls PO ein wachsendes Ausfall-Signal für den Sidecar wünscht, ist das ein Folge-Issue.
- Downstream-Konsumenten (`trip_alert.check_radar_alerts`, `trip_command_processor`) müssen `convective_checked` nicht zwingend auswerten, um weiterhin korrekt zu funktionieren (additives Feld, Default `True`) — eine explizite Sichtbarmachung im Alert-Text selbst ist nicht Teil dieser Spec, nur im Ad-hoc-`format_now_text`-Pfad.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** ADR-0018 (Nicht-Kaschieren-Invariante bei Provider-/Quell-Ausfall)
- **Rationale:** ADR-0018 verbietet explizit stille Fallbacks, die einen Ausfall als „grün"/„geprüft" erscheinen lassen. Ein stiller `is_convective=False` bei gescheitertem Sidecar-Call wäre strukturell identisch zu dem in ADR-0018 beschriebenen Muster (erfolgreicher Fallback verdeckt den eigentlichen Ausfall) — hier sogar sicherheitsrelevanter, da ein unentdecktes Gewitter/Hagel-Ereignis die Konsequenz wäre. Diese Spec wendet dieselbe Nicht-Kaschieren-Logik an: sichtbares additives Signal (`convective_checked`) statt Kaschieren, analog zu `fallback_model`/`fallback_reason` in ADR-0018. Kein neues ADR nötig — bestehendes ADR-0018 deckt das Muster inhaltlich ab; diese Spec ist eine Anwendung, keine neue Architekturentscheidung.

## Changelog

- 2026-07-09: Initial spec created (Issue #1161)
