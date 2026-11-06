---
entity_id: fix_2223_nachtfenster_ortszeit
type: bugfix
created: 2026-11-06
updated: 2026-11-06
status: draft
version: "1.0"
workflow: "fix-2223-nachtfenster-ortszeit"
tags: [nachtwetter, zeitzone, provider-kontingent, segment-weather]
---

# Fix 2223 — Nachtfenster am Ziel in Ortszeit statt UTC

## Approval

- [ ] Approved

## Purpose

`fetch_night_weather` bildet das Ende des Nachtfensters („06:00 Folgetag") über den
UTC-Kalendertag der Ankunft. Dadurch endet das Fenster in Europa 1–2 Stunden nach
06:00 Ortszeit und springt bei Ankunft nach UTC-Mitternacht (westliche Zonen, Ortsabend)
von ca. 10 h auf ca. 29 h — bis zu 2,5× so viele Provider-Stunden (Kontingent, Nähe #2150).
Das Fenster soll um 06:00 **Ortszeit am Ziel** am Ortsdatum der Ankunft + 1 Tag enden.

## Source

- **File:** `src/services/segment_weather.py`
- **Identifier:** `fetch_night_weather` (Zeilen ~608–614)

Schicht: Python-Core (`src/services/`). Versand (`trip_report_scheduler._fetch_night_weather`)
und Vorschau (`preview_service`) rufen dieselbe Funktion — ein Fix wirkt auf beide. Keine
Mail-Inhalts-Datei, das Renderer-Gate greift nicht. Trip/Ortsvergleich: die Funktion ist
Trip-Briefing-Pfad, ein Compare-Pendant existiert nicht; die Zeitzone kommt aus dem bereits
geteilten Auflöser `utils/timezone.py`. Kanäle: der Nachtteil ist Datengrundlage aller vier
Kanäle (E-Mail · Telegram · SMS · Premium-SMS); die Korrektur wirkt vor der Kanalverzweigung,
der Inhalt bleibt kanalgleich. Mandantentrennung: `user_id` wird unverändert durchgereicht.

## Scope

- **Enthalten:** Berechnung des Fensterendes in `fetch_night_weather` (Ortszeit statt UTC).
- **Nicht enthalten:** Verhalten bei Nachtankunft vor 06:00 Ortszeit, Renderer (`_extract_night_rows`), Provider-Kontingentlogik (#2150).

## Definition of Done

- Bei Ankunft am Ortsabend nach UTC-Mitternacht umfasst die Nachtprognose rund 10 statt rund 29 Stunden.
- In Europa endet das Fenster um 06:00 Ortszeit.
- Alle Tests aus dem Test Plan sind grün; Versand und Vorschau liefern dasselbe Fenster.

## Test Plan

- Datei: `tests/tdd/test_night_window_ortszeit.py` (Kern-Schicht, deterministisch, ohne Netz, Provider-Stub zählt Stunden, kein Mock-Theater).
- Fälle: UTC−5 Ortsabend (AC-1), Mallorca/Korsika Sommer und Winter (AC-2), Sommerzeit-Umstellung (AC-3), nicht auflösbare Zone (AC-4), Versand = Vorschau (AC-5).
- Rot-Nachweis: AC-1 und AC-2 scheitern vor dem Fix am heutigen UTC-Ende.

## Estimated Scope

- **LoC:** ~15 Code, ~80 Test
- **Files:** 2 (1 Code, 1 Test)
- **Effort:** low

### Affected Files

| File | Change Type | Description |
|------|-------------|-------------|
| `src/services/segment_weather.py` | MODIFY | Fensterende = 06:00 Ortszeit am Ortsdatum(Ankunft)+1, danach nach UTC |
| `tests/tdd/test_night_window_ortszeit.py` | CREATE | Verhaltenstests mit echtem Provider-Stub, der die angefragten Stunden zählt |

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `utils.timezone.location_tz` / `local_dt` | Funktion | einziger Zeitzonen-Auflöser, UTC-Rückfall bei nicht auflösbarer Zone |
| `app.day_window.display_end_time` | Funktion | liefert die UTC-aware Ankunft |
| `SegmentWeatherService.fetch_segment_weather` | Service | Cache/Kontingent `briefing_nacht` |

## Implementation Details

```
tz = location_tz(seg.end_point)                      # UTC-Rückfall
local_arr = local_dt(arrival, tz)
end_local = datetime.combine(local_arr.date() + 1 Tag, time(6, 0), tzinfo=tz)
next_morning = end_local.astimezone(timezone.utc)
```

ZoneInfo löst Sommerzeit-Wechsel selbst auf (kein Rechnen mit festem Offset).
Ankunft vor 06:00 Ortszeit (Nachtankunft) bleibt bewusst wie bisher „Folgetag 06:00":
der Renderer ankert ebenfalls auf Ankunftsdatum+1, eine Änderung wäre eine
Verhaltensänderung außerhalb dieses Tickets.

## Expected Behavior

- **Input:** letztes Segment mit Ziel-Koordinaten und Ankunftszeit (UTC)
- **Output:** Zeitreihe von Ankunft bis 06:00 Ortszeit des Folgetags am Ortsdatum
- **Side effects:** weniger angefragte Provider-Stunden bei Ankunft nach UTC-Mitternacht

## Acceptance Criteria

- **AC-1:** Given ein Trip-Ziel in UTC−5 und eine Ankunft um 20:00 Ortszeit (01:00 UTC des Folgetags) / When das Nachtwetter geholt wird / Then endet das Fenster um 06:00 Ortszeit des Folgetags (ca. 10 Stunden), nicht erst am übernächsten Tag (ca. 29 Stunden).
  - Test: Provider-Stub zählt die angefragten Stunden; erwartet ca. 10, nicht ca. 29.

- **AC-2:** Given ein Ziel auf Mallorca oder Korsika (Sommer UTC+2, Winter UTC+1) / When das Nachtwetter geholt wird / Then endet das Fenster um 06:00 Ortszeit (04:00 bzw. 05:00 UTC), nicht um 06:00 UTC.
  - Test: Endzeit der angefragten Zeitreihe wird in Ortszeit geprüft, je ein Sommer- und ein Wintertermin.

- **AC-3:** Given eine Ankunft in der Nacht der Sommerzeit-Umstellung / When das Nachtwetter geholt wird / Then endet das Fenster trotzdem exakt um 06:00 Ortszeit des Folgetags.
  - Test: Ankunft am Abend vor der Umstellung (Europe/Madrid), Ende in Ortszeit == 06:00.

- **AC-4:** Given ein Ziel, dessen Zeitzone nicht aufgelöst werden kann / When das Nachtwetter geholt wird / Then gilt der bisherige UTC-Rückfall (06:00 UTC am UTC-Datum+1) und es entsteht kein Fehler.
  - Test: Ziel mit nicht auflösbarer Zone liefert das bisherige Ende.

- **AC-5:** Given Versand und Vorschau / When beide das Nachtwetter holen / Then nutzen beide dieselbe Funktion und erhalten dasselbe Fenster für dieselbe Ankunft.
  - Test: Aufruf über den Scheduler-Delegator und über die Vorschau-Pipeline liefert gleiches Fensterende.

## Known Limitations

- Nachtankunft vor 06:00 Ortszeit behält „Folgetag 06:00" (ca. 30 h); bewusst unverändert.

## Architektur-Entscheidung (ADR)

- **ADR-Nr.:** keine
- **Rationale:** Fehlerkorrektur auf Basis des bestehenden Zeitzonen-Auflösers; keine neue Entscheidungsfläche.

## Changelog

- 2026-11-06: Initial spec created (Issue #2223)
