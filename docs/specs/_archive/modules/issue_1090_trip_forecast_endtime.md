# Spec: Issue #1090 — TripForecast Endzeit nie invertiert

created: 2026-07-07

## Problem
`_waypoint_time_window` erzeugt beim letzten Wegpunkt via `.time()`-Truncate ein invertiertes Fenster (`end < start`) wenn die Ankunft >= 22:00 liegt → Provider-Absturz. Regression aus #1005.

## Acceptance Criteria

**AC-1:** Given eine Etappe, deren letzter Wegpunkt eine effektive SSoT-Zeit >= 22:00 hat (z.B. arrival_override="23:00"),
When `TripForecastService` das Wetterfenster dieses Wegpunkts bestimmt,
Then ist das Ende ECHT nach dem Start (`end > start`) — kein invertiertes/leeres Fenster (real: +2h rollt über Mitternacht ODER wird sauber geklemmt).

**AC-2:** Given irgendeine Etappe/Wegpunkt-Konstellation (jede Startzeitquelle, jede Tageszeit, 1..n Wegpunkte),
When das Wetterfenster bestimmt wird,
Then gilt IMMER `end > start` und es wird nie `start > end` an den Provider übergeben.

**AC-3:** Given die bestehende SSoT-Startzeitkette aus #1005 (override > start_time > calculated > Default 08:00),
When der Fix angewandt ist,
Then bleibt die Startzeit-Priorität unverändert (keine Regression an #1005-Verhalten).

## Out of Scope
- F002 (Ganztag-Fallback-Divergenz bei wp_time=None) — separater LOW-Nebenbefund, nicht Teil dieses Fixes.
