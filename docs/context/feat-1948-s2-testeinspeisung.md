# Context: feat-1948-s2-testeinspeisung

## Request Summary

Issue #1948, Scheibe S2 (PO-Konzept 2026-08-17): Testmeldungs-Einspeisung — dem System
aufgezeichnete Meldungen (S1-Rohmitschnitte) oder frei formulierte Testmeldungen übergeben,
um zu sehen, wie sie über alle Kanäle gerendert würden. Konkret: der zustandslose Endpoint
`POST /api/trips/{trip_id}/alert-preview` bekommt den fehlenden Zweig b (amtliche Warnung)
und die drei S1-Aufzeichnungsformate werden einspeisbar. Format-Scheiben S3+ werden damit
gegen echte Eingangsdaten verifiziert.

## Related Files

| File | Relevance |
|------|-----------|
| `api/routers/validator.py:237-264` | `AlertPreviewBody` (changes+segment_times ODER onset), 422-Guard, Endpoint |
| `src/services/validator_render_service.py:89` | `render_alert_preview()` — Render-Sequenz aller Kanäle, `_stub_segment()` (Z. 57) |
| `src/services/alert_input_capture.py` | S1-Mitschnitt: `capture_user_scoped` (Z. 51), `capture_system` (Z. 91), Hüllen-Felder |
| `src/services/trip_alert.py:98-109,354-357` | Zweig-a-Capture: `_change_to_capture_dict` spiegelt `ChangePayload` 1:1; KEINE `segment_times` |
| `src/services/official_alerts/warn_egress.py:390-400` | Zweig-b-Capture: `{"body": resp.json(), service, host, cache_key, status}` — nur JSON-Provider |
| `src/services/radar_service.py:653-676,521` | Zweig-c-Capture (`source`+Frames `timestamp`/`precip_mm_h`) · `_derive_result(frames,…)` |
| `src/output/renderers/alert/official_alerts.py` | Zweig-b-Renderer: Subject (883), HTML (1446), Plain (1522), Telegram (1834), SMS (2038), DTO-Builder `build_official_alert_notices` (2139) |
| `src/services/notification_service.py:829-882` | `send_official_alert` — Render-Sequenz-Vorlage (Versand, für Preview spiegeln, nicht aufrufen) |
| `src/services/official_alerts/models.py:15` | `OfficialAlert`: source, hazard, level:int, label, valid_from, valid_to, url, region_label, dedup_id |
| `internal/router/router.go:167` · `internal/handler/proxy.go:297-335` | Go-Proxy: `AlertPreviewProxyHandler` mit user_id-Injektion; kein Catch-all — neue Routen brauchen Registrierung |

## Existing Patterns

- **Mehrkanal-Preview in EINEM Abruf** (ADR-0011): alert-preview liefert `subject/email_html/email_plain/telegram/sms` — neuer Zweig b MUSS dieselbe Antwortform liefern.
- **Zustandsloser Validator-Endpoint ohne Seiteneffekte:** kein SMTP, kein Throttle-Write (Tests `test_issue_221_validator_endpoints.py:246-320`, `test_issue_918_alert_preview_4ch.py`).
- **Exklusiv-Guard im Body:** heute `onset` XOR `changes+segment_times` (422 sonst) — wird auf drei Typen erweitert.
- **Payload-Schema-Nahtstelle S1↔S2 per Test bewiesen:** `test_alert_input_capture_payload_schema.py` konstruiert `ChangePayload(**capture_felder)` echt.

## Befund: Abstand S1-Mitschnitt → heutiger Preview-Body

| Zweig | Deckung | Lücke |
|---|---|---|
| a (Δ) | `changes` 1:1 deckungsgleich | Capture enthält KEINE `segment_times` → 422-Guard schlägt heute fehl |
| b (amtlich) | — | Payload-Typ fehlt komplett; Capture ist ROHER Provider-Body (nur JSON-Provider: geosphere_warn, vigilance, meteo_forets, meteoalarm_feed:*; DPC/CAP-XML werfen bei `resp.json()` und werden fail-open verschluckt) |
| c (Nowcast) | Frames vorhanden | `_derive_result` liefert onset_minutes/intensity_label; FEHLEND im Mitschnitt: `is_convective` je Frame, `km_from`/`km_to` (Trip-Geometrie), `source_label` (Mapping `_SOURCE_LABELS` radar_service.py:223), `cooldown_display` |

## Dependencies

- Upstream: `build_official_alert_notices`, Renderer in `official_alerts.py`, `_derive_result`, `_alert_tz_for_trip`, `_stub_segment`
- Downstream: S3+ (SMS-Sofortfix, Formatscheiben) verifizieren Formatänderungen über diesen Einspeiseweg; Frontend nutzt den Endpoint heute nicht direkt (Validator-Fläche)

## Existing Specs

- `docs/specs/modules/alarm_eingangsprotokoll.md` — S1 (AC-9 dokumentiert die Zweig-c-Limitation bewusst)
- `docs/specs/modules/issue_221_validator_observability_endpoints.md` — Ursprungs-Spec alert-preview + Proxy
- `docs/specs/modules/fix_923_sms_fidelity_backend.md` — Muster zustandsloser Preview ohne user_id
- Zweig-b-Format: `warnmail_official_alert_display.md`, `sms_official_alert_tokens.md`, `fix_1796_official_alert_gsm7_extension.md`

## Risks & Considerations

- **#1929-Sperrzone `official_alerts.py:1896-2104`:** Der SMS-Renderpfad (`_tag_hour`…`render_official_alert_sms`) liegt KOMPLETT darin. S2 darf ihn AUFRUFEN, aber keine Zeile darin ändern.
- **Roh-Body-Replay Zweig b hieße 4 Provider-Parser anbinden** (`geosphere_warn._extract_alerts`, `meteo_forets._extract_alert`, `meteoalarm._extract_alerts_from_cap`, `dpc._alerts_for_zone`) — sprengt die Scheibe. Alternative: strukturierte `OfficialAlert`-Felder als Payload (Testmeldungen frei formulierbar; Roh-Replay ggf. Folgescheibe).
- **Mandantentrennung:** bestehender Endpoint erzwingt user_id-Query + 404 bei Fremd-Trip — bleibt für alle neuen Typen unverändert (Test mit 2 Nutzern PFLICHT).
- **Kein Versand:** neuer Zweig darf keinerlei Throttle-/Log-/Versand-Seiteneffekt haben.
- **`resp.json()`-Lücke Zweig b (DPC/CAP)** ist ein S1-Nebenbefund, nicht S2-Blocker.

## Analyse: Design-Optionen (Tech-Lead-Empfehlung ➜ in Spec ausformulieren)

1. **Zweig b als dritter exklusiver Payload-Typ `official`** am bestehenden Endpoint (Liste von
   `OfficialAlertPayload` ≙ `OfficialAlert`-Felder + betroffene `segment_ids`), Render-Sequenz aus
   `notification_service.py:846-882` in `validator_render_service.py` gespiegelt. ➜ EMPFOHLEN.
2. **Zweig-a-Replay:** `segment_times` optional machen und aus dem bereits geladenen Trip
   (Segment-Zeiten der in `changes` genannten `segment_id`s) synthetisieren — S1-Format bleibt
   unverändert, Capture-Datei ist 1:1 einspeisbar. ➜ EMPFOHLEN.
3. **Zweig-c-Replay:** neuer exklusiver Payload-Typ `nowcast_frames` (`source` + Frames wie im
   Mitschnitt), serverseitig `_derive_result` → OnsetEvent; `km_from/km_to` aus Trip oder Body,
   `source_label` über `_SOURCE_LABELS`. S1 additiv um `is_convective` je Frame erweitern.
   ➜ Umfang prüfen — ggf. als S2b abtrennen, wenn LoC-Rahmen kippt.
4. **Einspeise-Mechanik:** Capture-JSON wird clientseitig (curl/jq-Rezept, dokumentiert) an den
   Endpoint gegeben — KEIN serverseitiges Datei-Lesen per Pfad (Path-Traversal-/Tenancy-Risiko).
