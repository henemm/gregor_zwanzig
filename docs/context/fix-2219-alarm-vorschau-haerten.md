# Context: fix-2219-alarm-vorschau-haerten

## Request Summary
Die Alarm-Vorschau (`POST /api/trips/{id}/alert-preview`, auch über `/api/briefings/{id}/alert-preview?kind=route`)
ist das Prüfwerkzeug für Black-Box-Validatoren und den Alarme-Reiter. Sie soll bei Fehleingaben sauber mit 422
antworten statt HTTP 500 und dort, wo sie rendert, dasselbe zeigen wie der Versandpfad. Bündel aus #1199:
C5-18, C5-19, C5-28, C5-46, C5-52 plus Nachzug B2-72 (Issue-Kommentar 2026-09-08).

## Befunde (Code-Stand origin/main 5dd49a173, nachgemessen 2026-11-13)

| ID | Fundstelle (aktuell) | Befund | Status |
|----|----------------------|--------|--------|
| C5-52 | `api/routers/validator.py:221` (`ChangePayload.severity: str`), `src/services/validator_render_service.py:220` (`ChangeSeverity(c.severity)`) | Freies `str`; `"HIGH"` (Kanalschwellen-/RiskLevel-Wort) wirft `ValueError` im Service → HTTP 500. `ChangeSeverity` kennt nur `minor/moderate/major` (`src/app/models.py:579`). Frontend mappt korrekt (`alertPreviewHelpers.ts:85` `SEVERITY_MAP`), Fehler kommt von externen Aufrufern (KHW-Bereitschaftstest). | noch da |
| C5-28 | `api/routers/validator.py` `NowcastFramePayload.timestamp: str`; `validator_render_service.py:_render_nowcast_replay` `datetime.fromisoformat(f.timestamp)` | Zonenlose Zeitstempel ergeben naive `datetime`; `RadarNowcastService._derive_result(..., now=aware)` vergleicht naive vs. aware → `TypeError` → 500. Kein tzinfo-Check. | noch da |
| C5-19 | `src/output/renderers/alert/project.py:229-242` `_onset_shift_text` | Bei `delta == 0` (bzw. Betrag rundet auf 0) → „0 h früher". Versandpfad schließt `delta == 0` und Unterschwelle aus (`weather_change_detection.py:_onset_change`, `if delta == 0: return None`; `abs(delta) < threshold`). Nur über Vorschau erreichbar. | noch da |
| C5-46 | `src/output/renderers/alert/render.py:1048-1070` `_sms_onset_time` | `day_offset != 0` und `weekday is None` → nackte Uhrzeit, Tagesbezug still verschluckt (widerspricht dem eigenen Docstring „über die Anzeige entscheidet der Versatz"). Versandpfad setzt Kürzel immer mit (`project.py:652-656`). Über die Vorschau-API erreichbar (`OnsetPayload.onset_day_offset` ohne `onset_weekday`); analog `event_end_day_offset` ohne `event_end_weekday`. | noch da |
| B2-72 | `validator_render_service.py:_render_nowcast_replay` (`onset_ns`, ~Z. 377) | Replay-Namespace setzt `event_end_day_offset/_weekday`, aber kein `onset_day_offset/onset_weekday` → Beginn ohne Tagesbezug, Ende mit. Identisch mit offenem **#2085** (dort ausführlich reproduziert: `R0.8@0:23 >@Sa0:38`). | noch da |
| C5-18 | `validator_render_service.py:66-80` `_stub_segment` | Stub-Segmente mit `GPXPoint(lat=0, lon=0)`; `project._tz_for_location(match.start_point, tz)` löst 0/0 zu einer UTC-Zone auf statt auf den Trip-Zonen-Fallback → Beginn-Uhrzeiten der Abweichungs-Vorschau (nur Zweig ohne frische Reihen) in falscher Zone. | noch da |

## Related Files
| File | Relevance |
|------|-----------|
| `api/routers/validator.py` | Payload-Modelle (`ChangePayload`, `OnsetPayload`, `NowcastFramePayload`), Eingangsprüfung `_validate_change_*`, `api_fehler(422, …)` |
| `src/services/validator_render_service.py` | `_stub_segment`, `render_alert_preview`, `_render_nowcast_replay` |
| `src/output/renderers/alert/project.py` | `_onset_shift_text`, `_tz_for_location`, Versandpfad-Vorbild für Onset-Tagesbezug (`day_offset` + `_de_weekday_short`) |
| `src/output/renderers/alert/render.py` | `_sms_onset_time` (Kurzform Tagesbezug) |
| `src/services/weather_change_detection.py` | Invariante des Versandpfads für Beginn-Verschiebung |
| `src/utils/timezone.py` | `day_offset`, `local_fmt`, `tz_for_coords` |
| i18n-Katalog | Fehlertexte für neue 422-Gründe (`api_fehler`-Schlüssel, DE/EN, ADR-0104) |

## Existing Patterns
- 422 mit lokalisiertem Schlüssel über `api_fehler(422, "<key>", user_id, …)` (`metrik_unbekannt`, `segment_unbekannt`).
- Replay-Zweig leitet Anzeigewerte über **geteilte Anzeigefassungen** ab (`event_end_display`, `source_reach_display`) — B2-72 analog, kein zweiter Rechenweg.
- Versandpfad: `_onset_offset = day_offset(now, onset_dt, tz)`; `onset_weekday = _de_weekday_short(local_dt(onset_dt, tz)) if offset else None`.

## Dependencies
- Upstream: `RadarNowcastService._derive_result`, `to_alert_message`, Renderer `render_sms/telegram/email`.
- Downstream: Alarme-Reiter (Frontend `alertPreviewHelpers.ts`), External/Staging-Validatoren, KHW-Bereitschaftstest; `briefing_alert_preview kind=route` delegiert.

## Existing Specs
- `docs/specs/modules/feat_2054_onset_wochentagskuerzel.md` (Kürzel-Schreibweise, AC-10 „Versatz entscheidet")
- `docs/specs/modules/fix_1948_s4_nowcast_sms_zielbild.md`, `preview_service.md`

## Abgrenzung
- **#2069** (Stub- statt echter Segmente, km/Distanz/Höhe blind): NICHT Teil hiervon. C5-18 behebt nur die Zeitzone der Stubs (Koordinaten aus dem Trip statt 0/0) — kompatibel mit einem späteren Umbau auf echte Segmente.
- **#2085** = B2-72: wird hier mitgelöst; #2085 anschließend als Duplikat mit Verweis schließen.

## Risks & Considerations
- `_sms_onset_time` ist Versandpfad-Code (SMS/Premium-SMS/Telegram-Kurzform): Änderung nur für den Fall offset≠0 ∧ weekday=None, Normalfall byte-identisch halten (Golden-/Kanal-Tests).
- Strengere Eingangsprüfung darf bestehende Aufrufer (Frontend, Tests, Validatoren) nicht brechen: Frontend sendet `minor/moderate/major` und zonierte Zeitstempel? → in Analyse prüfen.
- Zwei-Nutzer-Pflicht gilt für datenbewegende Endpoints; hier reine Render-Vorschau, user-scoped Laden bleibt unverändert.

## Analysis

### Type
Bug (Bündel aus #1199: C5-52, C5-28, C5-19, C5-46, B2-72, C5-18)

### Investigation-Ergebnisse (Bug-Intake + Plan/Sonnet, 2026-11-13)
- **Aufrufer-Kompatibilität:** Kein Aufrufer im Repo bricht. Frontend mappt info/warning/critical→minor/moderate/major (`alertPreviewHelpers.ts:35-39`) und sendet keine `nowcast_frames`; alle Tests senden zonierte Zeitstempel (`now = datetime.now(timezone.utc)`). Validatoren/Skripte rufen `alert-preview` nicht auf. „HIGH" kommt nur vom externen KHW-Bereitschaftstest.
- **„HIGH" ist reines Ausgabe-Token** (`deviation_alert_engine.py:286-292` `_highest_severity`), kein Rück-Mapping im Versandpfad ⇒ Ablehnen ist korrekt, Abbilden wäre neue Semantik.
- **C5-46:** Im Versandpfad tritt offset≠0 ∧ weekday=None nie auf (`project.py:652-656`, `trip_alert.py:2761-2763`, `event_end_display` `project.py:38-75`). Nur über Vorschau-Payload erreichbar.
- **B2-72:** Keine geteilte Beginn-Anzeigefassung vorhanden; Beginn wird inline abgeleitet (`trip_alert.py:~2735-2763`, `project.py:~640-656`). Replay (`validator_render_service.py:~363-377`) setzt nur `onset_time`.
- **C5-18 widerlegt:** `tz_for_coords(0,0)` = `UTC`, `resolve_location_tz(lat=0, lon=0)` = `None` (UTC gilt als „nicht auflösbar", `src/utils/timezone.py:52-77`) ⇒ `_tz_for_location` (`project.py:531-544`) fällt per `or fallback_tz` auf `alert_tz` aus `_alert_tz_for_trip` zurück = Trip-Zone. Die Prämisse „0/0 → UTC statt Fallback" stimmt nicht. Nur Regressionstest, kein Code-Fix.
- **Compare-Zweig** `compare_alert_preview_service.py:121` hat dasselbe `ChangeSeverity(c["severity"])` ⇒ mitprüfen.

### Entscheidungen (Tech Lead)
| Befund | Entscheidung | Begründung |
|---|---|---|
| C5-52 | `severity: str` bleibt, eigene Prüfung `_validate_change_severity` → `api_fehler(422, "schwere_unbekannt", …)` mit erlaubten Werten; gleiche Prüfung im Compare-Zweig | Fehlerformat konsistent zu `metrik_unbekannt` (lokalisiert), statt pydantic-`detail[]` |
| C5-28 | Router-Prüfung der `nowcast_frames[].timestamp`: ungültiges ISO oder `tzinfo is None` → 422 (`zeitstempel_ohne_zone`) | 500 → 422; Service unverändert |
| C5-46 | 422 bei `onset_day_offset≠0` ohne `onset_weekday` bzw. `event_end_day_offset≠0` ohne `event_end_weekday` (`onset_tagesbezug_unvollstaendig`); `_sms_onset_time` bleibt unverändert | Versandpfad erzeugt den Fall nie; Versandcode byte-identisch; Vorschau soll nichts erfinden |
| C5-19 | 422 bei Beginn-Verschiebung 0 bzw. unter der Schwelle (`onset_shift_null`); Schwelle aus derselben Quelle wie `_onset_change`, kein zweiter Wert; kein Renderer-Guard | Vorschau bildet nur Versandzustände ab |
| B2-72 | Neue geteilte `onset_display(now_utc, onset_minutes, tz) -> (hhmm, offset, weekday)` neben `event_end_display` in `project.py`; nur im Replay genutzt; Versandstellen unverändert (Refactor ggf. Folge-Ticket) | Kein zweiter Rechenweg im Replay, kein Byte-Risiko im Versand. Slice `local_fmt(...)[-5:]` einheitlich zu `event_end_display` handhaben |
| C5-18 | Nur Regressionstest (Trip Europe/Berlin, Stub-Zweig ohne frische Reihen → Beginn in Berliner Zeit) | Befund nicht reproduzierbar (siehe oben) |

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `api/routers/validator.py` | MODIFY | Prüfungen Severity, Zeitstempel-Zone, Tagesbezug-Vollständigkeit, Shift≠0 (~+60 LoC) |
| `src/services/validator_render_service.py` | MODIFY | Replay `onset_ns` über `onset_display` (~+10 LoC) |
| `src/output/renderers/alert/project.py` | MODIFY | neue Funktion `onset_display` (~+20 LoC, nichts Bestehendes geändert) |
| `src/services/compare_alert_preview_service.py` | MODIFY | Severity-Prüfung (~+5 LoC) |
| `src/i18n/messages/de/api.json`, `en/api.json` | MODIFY | 4 neue `api.fehler.*`-Schlüssel (DE/EN, ADR-0104) |
| `docs/reference/api_contract.md` | MODIFY | neue 422-Gründe, Changelog |
| `tests/tdd/test_fix_2219_*.py` | CREATE | RED-Tests je Befund inkl. Replay `R0.8@0:23 >@Sa0:38` und C5-18-Regression |

### Scope Assessment
- Files: ~8 (davon 1–2 Testdateien neu)
- Estimated LoC: +150 bis +250 (etwa die Hälfte Tests)
- Risk Level: LOW–MEDIUM — Versandpfad (`render.py`, `trip_alert.py`, `weather_change_detection.py`) bleibt unberührt; Risiko liegt bei bestehenden Tests, die jetzt verbotene Eingaben senden könnten.

### Technical Approach
Reihenfolge: (1) B2-72 `onset_display` + Replay, (2) C5-52/C5-28 Eingangsprüfung, (3) C5-46/C5-19 Eingangsprüfung, (4) C5-18 Regressionstest, (5) i18n-Schlüssel gesammelt anlegen, Contract-Doku, Drift-/Paritätstests.

### Dependencies
- Tests: `test_i18n_api_katalog_paritaet.py`, `tests/tdd/test_api_fehler_nutzersprache.py`, `test_api_contract_drift.py`, `test_alert_preview_input_validation.py`, `test_alert_preview_onset_payload.py`, `test_alert_preview_nowcast_replay.py`, `test_alert_preview_compare_paritaet*.py`, `test_onset_wochentagskuerzel.py`.
- Nach Abschluss: #2085 als Duplikat mit Verweis schließen.

### Open Questions (technisch, in Phase 3 klären — keine PO-Frage)
- [ ] Welches Payload-Feld trägt die Beginn-Verschiebung für C5-19, und wo liegt die Schwelle von `_onset_change` (gemeinsame Konstante)?
- [ ] Senden bestehende Tests `onset_day_offset≠0` ohne Kürzel oder Shift 0? (`rg` vor RED) — ggf. Testeingaben anpassen.
