# Context: fix-2982-onset-event-baustein

## Request Summary
Issue #2982 (Folge aus Paritäts-Bestandsaufnahme #1986, Spec `docs/specs/modules/paritaets_bestandsaufnahme.md:54`, Priorität high):
`OnsetEvent` (Alarm-Beginn) wird an vier Stellen getrennt gebaut. Zusammenführen zu EINEM Baustein, damit
neue Felder nicht still auf einem Pfad fehlen (Muster der Vergangenheit: #2009, #2046, #2050, #2051, #2054
mussten je Feld an mehreren Stellen nachgezogen werden).

## Related Files
| File | Relevance |
|------|-----------|
| `src/output/renderers/alert/model.py:113` | `OnsetEvent` (frozen dataclass, 7 Pflicht- + ~22 optionale Felder bis `stage_number` ~232) |
| `src/services/notification_service.py:1914/1932` | **N** – Trip-Radar `send_radar_alert`, kopiert alle Felder aus `RadarAlertRequest` (Dataclass :239, gebaut nur `trip_alert.py:2759`), plus `stage_number` |
| `src/output/renderers/alert/project.py:564/662` | **P** – `to_multi_location_onset_alert_message` (Ortsvergleich-Bündel); berechnet Zeiten selbst aus `NowcastResult` via `event_end_display`(:38), `source_reach_display`(:95), `location_sharpness_display`(:115), `day_offset`, `_de_weekday_short`; km=0, `location_label` nur hier |
| `src/services/validator_render_service.py:164/201` | **V** – Vorschau/Replay `render_alert_preview`; liest `body.onset` (pydantic `OnsetPayload`, `api/routers/validator.py:242`, oder Replay-SimpleNamespace) per `getattr`; fehlt `gap_km`, `stage_number`, `briefing_context` |
| `src/services/radar_alert_service.py:~42/69` | **R** – `build_onset_alert_message`, veraltete Vor-#2009-Form (nur Pflichtfelder + `day_offset`); **kein Produktionsaufrufer**, nur Tests (`test_alarm_intensitaet_logik_unveraendert.py`, `test_profil_ampel_kette.py`, `test_s1c4b_einstiege_loesen_das_abo_auf.py`, `test_issue_919_radar_alert_canonical.py`) und ein Kommentar in `scripts/send_gate_test_mails.py:345` |
| `src/services/trip_alert.py:2759/2928` | baut `RadarAlertRequest`, ruft N |
| `src/services/compare_radar_alert.py:432`, `compare_alert_preview_service.py:185` | Aufrufer von P (Versand und Vorschau Ortsvergleich) |

## Feld-Matrix (Kurzfassung)
- N ist die vollständigste Fassung (alle Felder außer `location_label`).
- V = N ohne `gap_km`, `stage_number`, `briefing_context` → mögliche stille Lücke Vorschau vs. Versand (zu prüfen in Analyse: Absicht oder Lücke?).
- P = eigene Berechnung, ohne `segment_id`, `km_measured`, `rain_zones`, `gap_km`, `stage_number`, `briefing_context` (km immer 0 im Ortsvergleich, laut Kommentar Absicht).
- R = Altform; Kandidat zum Umstellen auf den Baustein oder Entfernen.

## Existing Patterns
- Geteilte „Fassungen" in `project.py` (`event_end_display` usw.) = bestehendes Muster für Trip/Vergleich-Teilung (ADR-0021).
- `RadarAlertRequest` ist bereits ein Feld-Bündel 1:1 zu OnsetEvent plus request-only Felder (`tz`, `addendum_reference`, `verschaerfung`, `segment_date`).

## Dependencies
- Upstream: NowcastResult (Radar), RadarAlertRequest, OnsetPayload, Zeit-Helfer (`src/utils/timezone.py:170 day_offset`, `official_alerts.py:1028 _de_weekday_short`).
- Downstream: alle Alarm-Renderer (E-Mail, Telegram, SMS, Premium-SMS) über `AlertMessage.events`.

## Parity Tests
Kein Test prüft heute den Feldsatz aller Baustellen. Feature-spezifische Paritätstests (bleiben als Regressionswächter):
`test_onset_callsite_timezone_guard.py`, `tdd/test_onset_ende_kanalparitaet.py`, `tdd/test_regen_ausdehnung_kanalparitaet.py`,
`tdd/test_multi_location_onset_alert.py`, `tdd/test_onset_wochentagskuerzel.py`, `tdd/test_onset_kurzform_menge.py`,
`tdd/test_onset_reichweite_guete_sms.py`, `tdd/test_fix_2219_onset_replay_tagesbezug.py`, u. a.

## Existing Specs
- `docs/specs/modules/paritaets_bestandsaufnahme.md` (Quelle), `fix_1744_alarm_format_angleichen.md`, `feat_2051_s1_dauer_und_ende.md`, `feat_2051_s3_reichweite_und_guete.md`, `feat_2050_s4b2_wortebene_kennzeichnung.md`
- ADR-0021 `docs/adr/0021-shared-deviation-alert-engine.md` (Trip und Ortsvergleich teilen die Ausgabe)

## Risks & Considerations
- Kritischer Pfad: Alarme an alle vier Kanäle. Reiner Umbau, Ausgabe muss byte-identisch bleiben (bestehende Renderer-/Paritätstests als Netz).
- Bewusste Unterschiede (km=0 + `location_label` im Ortsvergleich) dürfen nicht weg-vereinheitlicht werden; der Baustein muss sie als Eingabe tragen.
- V-Lücken (`gap_km`, `stage_number`) entscheiden: Angleichung wäre sichtbare Verhaltensänderung der Vorschau → nur, wenn Payload sie liefert; sonst als eigenes Folge-Issue.
- Neuer Wächter sinnvoll: Test, der sicherstellt, dass `OnsetEvent(` nur noch im Baustein gebaut wird (Ratsche), statt Feldsatz-Parität.
- Renderer-Commit-Gate kann greifen, falls Dateien unter `src/output/renderers/` geändert werden.

## Analysis

### Type
Feature (reiner Umbau/Entdopplung, keine sichtbare Verhaltensänderung)

### Ist-Befund (verifiziert 2026-11-17)
Die Doppelung hat ZWEI Ebenen:
1. **Ableitung NowcastResult → Anzeigefelder** (Beginn HH:MM/Versatz/Kürzel, Ende, Reichweite, Ortsschärfe,
   already_running, Menge, convective_checked) existiert DREIMAL: Trip `trip_alert.py:~2585-2817` (füllt
   `RadarAlertRequest`), Ortsvergleich `project.py:564 to_multi_location_onset_alert_message`, Replay
   `validator_render_service.py:449 _render_nowcast_replay` (SimpleNamespace, nutzt schon `project.onset_display:78`).
2. **Feld-für-Feld-Kopien:** `notification_service.py:1932 send_radar_alert` (Request → OnsetEvent + stage_number),
   `validator_render_service.py:201 render_alert_preview` (Payload/Namespace → OnsetEvent per getattr).
3. Altform `radar_alert_service.py:42 build_onset_alert_message` ohne Produktionsaufrufer (nur 3 Testdateien:
   `test_alarm_intensitaet_logik_unveraendert.py`, `tdd/test_profil_ampel_kette.py` inkl. Zähltabelle :899,
   `tdd/test_s1c4b_einstiege_loesen_das_abo_auf.py`).
4. `scripts/send_gate_test_mails.py:351` synthetische Fixture.

**Divergenz:** Trip bildet den Beginnzeitpunkt über `alert_log.nowcast_onset_at` (laufend → JETZT), Ortsvergleich
und Replay über `now + onset_minutes` auch bei `already_running`. Ausgabe-neutral: alle Textformen
(`_onset_wann_kopf`, `_onset_wann_zeile`, SMS `render.py:~1333`) verzweigen vor `onset_time`; einziger weiterer
Leser `api/routers/validator.py:506` prüft nur Kürzel-gegen-Versatz-Konsistenz (bleibt konsistent, da beide aus
demselben Zeitpunkt). Sortierschlüssel `project.py:~710` behandelt laufend bereits als 0; `onset_minutes` selbst
bleibt `nc.onset_minutes or 0`.

**Bewusste Pfad-Unterschiede (Eingaben, NICHT vereinheitlichen):** Labels (Trip: Intensität klein +
`radar_svc.source_label`; Vergleich: `nc.intensity_label` + `nc.source` roh; Replay: `_SOURCE_LABELS`), Zeitzone
(Trip `tz`, Vergleich `loc_tz` je Ort, Replay `alert_tz`), km=0 + `location_label` nur Vergleich;
`rain_zones`/`gap_km`/`km_measured`/`segment_id`/`briefing_context`/`stage_number` nur Trip.

### Affected Files (with changes)
| File | Change Type | Description |
|------|-------------|-------------|
| `src/output/renderers/alert/project.py` | MODIFY | neuer Baustein `onset_event_from_nowcast(nc, *, now_utc, tz, intensity_label, source_label, km_from=0.0, km_to=0.0, **ortskontext)` (Beginn über `nowcast_onset_at` + `onset_display`) und `onset_event_from_fields(obj)` (generisch über `dataclasses.fields(OnsetEvent)`, Defaults aus der Dataclass); Ortsvergleich nutzt ersteren |
| `src/services/trip_alert.py` | MODIFY | Ableitung durch Baustein ersetzen; Request-Spiegelfelder generisch aus dem Event füllen |
| `src/services/notification_service.py` | MODIFY | `send_radar_alert`: `onset_event_from_fields(request)` + `stage_number` statt Handkopie; `RadarAlertRequest` bleibt (Variante ii-b) |
| `src/services/validator_render_service.py` | MODIFY | Replay baut über Baustein; Vorschau über `onset_event_from_fields(body.onset)` (rain_zones-Umwandlung beachten) |
| `src/services/radar_alert_service.py` | MODIFY | `build_onset_alert_message` entfernen |
| `scripts/send_gate_test_mails.py` | MODIFY | Fixture über `onset_event_from_fields` oder Ausnahme in der Ratsche |
| 3 Testdateien (s. o.) | MODIFY | Umstellung wegen Entfernen der Altform |
| `tests/tdd/test_onset_event_baustein.py` | CREATE | Baustein-Verhalten, Golden-Master Alarmtexte 4 Kanäle × (Trip, Vergleich, Replay) × (laufend, künftig), Feld-Parität `fields(OnsetEvent) ⊆ RadarAlertRequest ∪ Ausnahmeliste`, AST-Ratsche `OnsetEvent(` in `src/` + `api/` nur in `project.py` |

### Scope Assessment
- Files: ~6 Produktiv + 4 Test
- Estimated LoC: +~180 / -~330 (netto ≈ −150)
- Risk Level: MEDIUM (kritischer Alarmpfad aller vier Kanäle; durch Golden-Master und bestehende Paritätstests abgesichert)

### Technical Approach
Variante ii-b (Plan/Sonnet-Bewertung + eigene Prüfung): `RadarAlertRequest` behält seine Felder (10 Testdateien
konstruieren ihn, `trip_alert` liest `.is_convective/.already_running/.verschaerfung` nach dem Bau); Variante ii-a
(`onset: OnsetEvent` im Request) wäre sauberer, kostet aber ~10 Testdateien bei geringem Zusatzgewinn. Die
Feld-Parität-Ratsche verhindert, dass ein neues OnsetEvent-Feld still auf dem Trip-Pfad fehlt.
Reihenfolge: Golden-Master zuerst (RED-Phase friert heutige Ausgabe ein), Baustein, Vergleich, Replay+Vorschau,
Trip+Versand, Altform weg, Ratschen, Golden-Master erneut.
Renderer-Commit-Gate kann greifen (`src/output/renderers/alert/project.py`) — Modus-Matrix + Validator müssen frisch grün sein.

### Dependencies
`alert_log.nowcast_onset_at`, `project.onset_display/event_end_display/source_reach_display/location_sharpness_display`,
`utils.timezone.day_offset/local_fmt/local_dt`, `official_alerts._de_weekday_short`, `RainZone`. Downstream: alle
Alarm-Renderer über `AlertMessage.events`.

### Open Questions
- keine Produktfrage. Vorschau-Lücken (`gap_km`, `stage_number`) bleiben unverändert, da der Vorschau-Payload sie nicht trägt (keine sichtbare Änderung in diesem Ticket).
- Nebenbefund: `OnsetPayload` hat kein Feld `already_running` → API-Vorschau kann den Laufend-Fall nicht zeigen (nur Replay). Für Nebenbefund-Triage notieren, nicht in diesem Ticket.
