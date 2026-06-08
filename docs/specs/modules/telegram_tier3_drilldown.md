---
entity_id: telegram_tier3_drilldown
type: module
created: 2026-06-07
updated: 2026-06-08
status: live
version: "2.0"
tags: [telegram, drilldown, weather, epic-639]
---

# Telegram Tier-3 Single-Metric-Drilldown (stündlich)

## Approval

- [x] Approved (PO 'go' 2026-06-08; v2.0-Integration PO-bestätigt: alle 3 Metriken)

## Purpose

Liefert den **stündlichen** Drilldown-Inhalt **einer** Wetter-Metrik (Gewitter, Wind,
Niederschlag) für einen Tag (heute/morgen) — der Inhalt hinter den Drilldown-Buttons,
die #651 (Tier-1/2) bereits emittiert (`callback_data=dd_<metric>_<day>`). Teil 5/6
von Epic #639 (Tier 3). Klickbar verdrahtet wird es durch #655 (callback_query).

## Revisions-Hinweis (v2.0)

v1.0 plante einen eigenständigen `hg`-Freitext-Befehl. Während der Umsetzung wurde
**#651 nach main gemerged** und hat (a) `/hg` für eine **Tages**-Gewitter-Glance belegt
und (b) die Drilldown-**Buttons** `dd_thunder_<day>` / `dd_wind_<day>` / `dd_precip_<day>`
auf der Timeline gebaut — denen nur der stündliche **Inhalt** fehlt. v2.0 integriert
#654 deshalb in #651s vorhandenen Query-Dispatch statt einen kollidierenden Befehl
einzuführen. Die **Verhaltens-ACs bleiben** (stündliche Liste, „Zurück"-Button,
Leerzustand) — nur der Trigger ist jetzt epik-nativ der Drilldown-Button-Callback.

## Source

- **File:** `src/services/trip_command_processor.py`
- **Identifier:** `TripCommandProcessor._handle_drilldown`, `_format_drilldown`, `_DRILLDOWN_PATTERN`, `_DRILLDOWN_METRICS`

## Estimated Scope

- **LoC:** ~110
- **Files:** 1 Source (`trip_command_processor.py`) + 1 Test + 1 Spec + 1 Test-Manifest
- **Effort:** medium

## Dependencies

| Entity | Type | Purpose |
|--------|------|---------|
| `WeatherExtractor.drilldown` (#652) | upstream | Stündliche Serie je Metrik aus Snapshot |
| #651 Query-Dispatch (`process()`, `_QUERY_KEYS`) | host | Einhängepunkt für `dd_<metric>_<day>` |
| #651 Timeline-Buttons (`_timeline_buttons`) | caller | emittiert `callback_data=dd_<metric>_<day>` bereits |
| `ForecastDataPoint` Felder | data | `thunder_level` (ThunderLevel), `wind10m_kmh`, `precip_1h_mm` |
| #655 (callback_query) | downstream | macht die Buttons klickbar (nicht Teil #654) |

## Implementation Details

```
_DRILLDOWN_PATTERN = re.compile(r"^dd_(thunder|wind|precip)_(today|tomorrow)$")

_DRILLDOWN_METRICS = {
  "thunder": ("thunder_level", "⛈️ Gewitter", _thunder_label),   # ⚪ keins / 🟡 mäßig / 🔴 hoch
  "wind":    ("wind10m_kmh",  "💨 Wind",      _num_label("km/h")),# "23 km/h"
  "precip":  ("precip_1h_mm", "🌧 Niederschlag", _num_label("mm")),# "1.4 mm"
}

process(): im Query-Dispatch-Zweig zusätzlich:
  if _DRILLDOWN_PATTERN.match(actual_key):  # actual_key aus "### query: <k>" ODER direkt "### <k>"
      trip = _find_trip(...); if not trip -> Trip-nicht-gefunden
      return _handle_drilldown(trip, metric, day_token, received_at, user_id)

_handle_drilldown(trip, metric, day_token, received_at, user_id):
  field, header, fmt = _DRILLDOWN_METRICS[metric]
  if day_token == "today":  from_time, hours = received_at, 12
  else:                     from_time = (received_at+1d) @ 00:00 (gleiche tz), hours = 24
  res = WeatherExtractor(user_id).drilldown(trip.id, field, from_time=from_time, hours=hours)
  if not res.available -> CommandResult(success=False, Leerzustand-Text, KEIN Button)
  body = _format_drilldown(res, header, fmt)
  back = "tl_today" if day_token=="today" else "tl_tomorrow"
  markup = {"inline_keyboard": [[{"text": "⬅️ Zurück", "callback_data": back}]]}
  return CommandResult(success=True, command=f"dd_{metric}_{day_token}",
                       confirmation_subject=f"[{trip.name}] {header} stündlich",
                       confirmation_body=body, reply_markup=markup, trip_name=trip.name)

_format_drilldown(res, header, fmt):
  lines = [f"{header} — stündlich"]
  for pt in res.points: lines.append(f"{pt.ts.astimezone():%H:%M}  {fmt(pt.value)}")
  return "\n".join(lines)   # >4096 wird vom TelegramOutput abgeschnitten (Button bleibt)
```

KEINE Änderung an `inbound_telegram_reader.py` (Trigger ist Button/Callback → #655).

## Expected Behavior

- **Input:** Query `### query: dd_thunder_today` (bzw. `dd_wind_*`, `dd_precip_*`, `*_tomorrow`) — von #655 aus dem Button-`callback_data` erzeugt.
- **Output:** Telegram-Nachricht mit stündlicher Metrik-Liste + Inline-Keyboard „⬅️ Zurück" (callback `tl_<day>`).
- **Side effects:** Keine (read-only Query, kein save/delete).

## Acceptance Criteria

**AC-1:** Given ein Drilldown-Aufruf `dd_thunder_today` bei aktivem Trip mit Snapshot,
When der Processor antwortet, Then enthält die Nachricht eine **stündliche** Liste der
nächsten 6–12 h speziell für `thunder_level` (≥6 Zeilen, je Uhrzeit + Risiko-Stufe),
unabhängig davon ob die Metrik in der Übersicht ausgeblendet ist.
  - Test: mock-frei, echter Snapshot via `WeatherSnapshotService.save`; `process(InboundMessage(body="### query: dd_thunder_today"))`; Assertion ≥6 HH:MM-Zeilen + Stufen-Labels.

**AC-2:** Given die Drilldown-Antwort, When sie erzeugt wird, Then trägt sie ein
`reply_markup`-Inline-Keyboard mit einem als „Zurück" beschrifteten Button (callback
`tl_today`/`tl_tomorrow`).
  - Test: `result.reply_markup.inline_keyboard` enthält Button mit text „Zurück".

**AC-3:** Given ein aktiver Trip ohne Snapshot/Stundendaten, When `dd_thunder_today`
aufgerufen wird, Then klare Leerzustand-Meldung (kein Crash, keine leere Liste).
  - Test: Trip ohne Snapshot → `success=False`, Leerzustand-Text.

**AC-4:** Given `dd_wind_today` bzw. `dd_precip_today` bei vorhandenem Snapshot, When
der Processor antwortet, Then enthält die Liste die jeweilige Metrik mit Einheit
(`km/h` bzw. `mm`) — keine toten Buttons aus #651.
  - Test: je ein Smoke-Test für Wind und Niederschlag mit erwarteter Einheit im Text.
