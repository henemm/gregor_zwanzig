# Context: feat-1439-starkregen-minutely15

## Request Summary

Issue #1439: Starkregen-Kurzfristhinweis im **planmäßigen** Trip-Briefing (Morgen-/
Abend-Mail + Telegram). Deadline 20.8.2026 (KHW-Wanderung AT/IT), `priority:critical`,
PO-Entscheidung 2026-08-05 „machen VOR der Tour". Einzige Vorbedingung (#1492) ist seit
heute (2026-08-07) geschlossen.

**Modus-Korrektur gegenüber Issue-Text:** AENDERUNG, nicht NEU. Das Issue beschreibt
Stufe A als Neubau auf Basis von Open-Meteo `minutely_15` — diese Infrastruktur existiert
bereits produktiv seit #656 (`RadarNowcastService`). Zu bauen ist die fehlende
**Einbindung in den planmäßigen Briefing-Pfad**, nicht der Nowcast selbst.

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/radar_service.py` | `RadarNowcastService`, `INTENSITY_HEAVY="Starker Regen"` bei `mm_per_h>=4.0` (Z.68,147-149) — das ist bereits die im Issue geforderte Starkregen-Schwelle. Mehrschichtige Provider-Kaskade RADOLAN→INCA→DPC/ARPAE→AROME-FR→ICON-D2→`minutely_15` (`_fetch_frames_with_fallback`, Z.280), Fail-soft nach ADR-0018. `format_now_text()` (Z.224) liefert bereits das im Issue gewünschte Format „Starker Regen ab ca. HH:MM (in ~N Min)" |
| `src/services/trip_alert.py:763,775,783-848` | Einziger heutiger Aufrufer im planmäßigen Takt: 15-Min-Cron ruft `radar_svc.get_nowcast(..., priority="polling")`, gated durch `alert_daily_limit.is_allowed(..., reason="nowcast")` (Budget-Gate, #1555-Reserve seit heute live). Danach Konsistenzprüfung gegen `WeatherSnapshotService.load_dated()` + `_briefing_precip_for_onset` mit drei Wortlaut-Zuständen (#1310-Präzedenz: „bereits angekündigt — jetzt akut" / „bereits angekündigt" / „nicht angekündigt") |
| `src/services/trip_report_scheduler.py` | Baut `TripReportRequest` für das planmäßige Briefing — **ruft `radar_service` heute NICHT auf** (grep bestätigt). Das ist die Lücke, die #1439 schließen soll |
| `src/services/radar_cache.py` | TTL 300s (5 Min) — bei 15-Min-Polling-Kadenz meist kein Cache-Hit; ein zweiter unabhängiger Aufrufort würde reale Zusatzkosten erzeugen |
| `src/output/renderers/email/unavailable_hint.py` | Vorbild-Muster für eine orthogonale Hinweis-Zeile: `any_..._unavailable()`-Gate + `render_..._html/plain()`, bewusst NICHT unter `renderers/alert/` (triggert sonst das Warn-Renderer-Mail-Gate) |
| `docs/specs/data_sources.md` | Enthält aktuell KEINEN Eintrag für `minutely_15` — Governance-Nachtrag nötig (Parameter läuft seit #656 in Prod, ist aber nie eingetragen worden). Als Nachtrag bestehender Nutzung, nicht als Neuantrag |
| `openspec/changes/` | Existiert NICHT in diesem Repo — projekteigene Struktur ist `.claude/workflows/<name>.json` + `docs/specs/modules/<entity>.md` |

## Existing Patterns

- **Budget-Gate wiederverwenden, nicht danebenstellen:** jeder neue Nowcast-Zugriff MUSS
  durch `alert_daily_limit.is_allowed(..., reason="nowcast")` laufen (`trip_alert.py:763`)
  — ein zweiter, unabhängiger Aufrufort würde den am selben Tag geschlossenen #1555-Fix
  sofort wieder unterlaufen.
- **Konsistenz mit dem Alert-Pfad:** der neue Briefing-Hinweis muss gegen denselben
  Snapshot-/Alert-State geprüft werden wie `trip_alert.py:787-848`, sonst kann Briefing
  „kein Starkregen" sagen während 15 Min später der Alert „jetzt akut" auslöst (oder
  umgekehrt) — Wortlaut-Präzedenz #1310 gilt analog.
- **Zeitfenster-Guard:** `_fetch_openmeteo_15` deckt 24h ab (`forecast_minutely_15=96`).
  „Starkregen jetzt" ist für ein Abend-vorher-Briefing bedeutungslos — der Hinweis darf
  nur erscheinen, wenn der Onset nah am nächsten aktiven Segment liegt.
- **Fail-soft** (ADR-0018): Provider/Region ohne Abdeckung → Hinweis-Zeile entfällt still,
  Briefing geht normal raus.

## Dependencies

- **Upstream:** #656 (RadarNowcastService, live), #1555 (Nowcast-Reserve/Budget-Gate,
  heute 2026-08-07 geschlossen), #1492 (Gewitter S4 Fallback-Kette, heute geschlossen —
  einzige Vorbedingung aus der Issue-Historie), #1310 (Akut-Wording-Präzedenz).
- **Downstream:** keine bekannten Abnehmer außer E-Mail/Telegram-Renderer für das
  planmäßige Briefing. Compare/Ortsvergleich ist NICHT im Scope (Trip-Briefing-only,
  Pendant-Gate `pendant_gate.py` beachten falls doch Compare-Bedarf entsteht).

## Existing Specs

- Kein bestehendes Spec-Modul für Nowcast-im-Briefing. `docs/specs/modules/ampel_schwellen_katalog.md`
  dient als Struktur-Vorbild.

## Scope Assessment

- **Files:** ~4 (`trip_report_scheduler.py` MODIFY, neues Hinweis-Modul CREATE analog
  `unavailable_hint.py`, Einbindung in `html.py`/`plain.py` + Telegram-Renderer MODIFY)
- **Estimated LoC:** ~50-70 — realistisch NUR wenn kein eigener Fetch-/Throttle-Code
  entsteht, sondern der bestehende gegatete Aufruf wiederverwendet/minimal erweitert wird
- **Risk Level:** MEDIUM — Budget-Gate-Umgehung und Alert/Briefing-Widerspruch sind reale,
  am selben Tag erst geschlossene Fehlerklassen (#1555), keine hypothetischen Risiken

## Technical Approach

Bestehenden `RadarNowcastService`-Pfad aus `trip_alert.py` als Vorbild wiederverwenden,
NICHT neu implementieren. Drei Pflicht-Korrekturen (siehe Risks) fließen als eigene ACs
in die Spec ein. MVP-Scope: E-Mail + Telegram, SMS zurückgestellt (Token-Format eigener
Aufwand, Deadline spricht für kleinen Schnitt — als Folge-Issue vormerken).

## Open Questions

Keine offenen technischen Fragen mehr — SMS-Scope-Entscheidung (MVP ohne SMS) und
Architektur-Ansatz (Budget-Gate-Wiederverwendung) sind getroffen. Verbleibt: PO-Freigabe
der ACs in `/30-write-spec` (Pflicht-Halt).

## Risks & Considerations

1. **Budget-Gate-Pflicht:** neuer Nowcast-Zugriff MUSS `alert_daily_limit.is_allowed(...,
   reason="nowcast")` durchlaufen (`trip_alert.py:763`) — sonst Umgehung des #1555-Fixes
   vom selben Tag.
2. **Konsistenz-Pflicht:** Hinweis-Rendering MUSS gegen denselben Snapshot-/Alert-State
   geprüft werden wie `trip_alert.py:787-848` (#1310-Wording-Präzedenz), sonst Widerspruch
   zwischen Briefing und Alert möglich.
3. **Zeitfenster-Guard-Pflicht:** Hinweis nur bei Onset innerhalb eines definierten
   Nähe-Fensters zum nächsten aktiven Segment — sonst zeigt ein Abend-Briefing Regen für
   Stunden später als „jetzt".
4. **Renderer-Mail-Gate:** liegt das neue Hinweis-Modul unter
   `src/output/renderers/email/*.py`, triggert automatisch `renderer_mail_gate.py` —
   vor Commit `tests/tdd/test_issue_811_mode_matrix.py` grün + frischer
   `briefing_mail_validator.py`-Lauf nötig.
5. **Governance:** `data_sources.md`-Nachtrag ist reine Doku, kein Gate-Blocker — parallel
   zur Implementierung, nicht davor.
