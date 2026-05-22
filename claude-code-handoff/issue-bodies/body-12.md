<!-- gregor-zwanzig-handoff: stable_id=backend-naismith-and-waypoint-suggestions -->
## Background

Two implicit requirements from `docs/specs/user_stories_foundation.md` US-1 are not yet supported by the backend, but the frontend designs (Issues #06, #11) depend on them:

### 1. Algorithmic waypoint suggestions

> Wegpunktvorschläge (Wetterscheiden) werden **algorithmisch berechnet** — aus GPX-Profil (Höhenpunkte, Exponiertheit, Etappenlänge), nicht per KI/ML.
> Vorschläge sind orange gestrichelt dargestellt — User bestätigt oder verwirft.

On GPX upload, the backend should analyze the track and add suggested waypoints at significant points (peaks, ridges, exposure changes, valley bottoms). Each waypoint gets:
- `origin: 'algorithm' | 'manual'`
- `confirmed: boolean` (suggestions start `confirmed = false`)
- `suggestion_reason: 'peak' | 'ridge' | 'exposure_change' | 'valley' | ...` (for UI explanation text)

### 2. Naismith arrival times

> **Ankunftszeiten werden vom System aus dem GPX errechnet** (Distanz + Höhenmeter → geschätzte Uhrzeit pro Wegpunkt) — nicht manuell eingetragen. Der User kann die berechneten Zeiten anpassen, nicht von Null eingeben.

Per waypoint, the backend should compute:
- `arrival_calculated: string (HH:MM)` — based on Naismith's Rule (or Swiss Hiking Formula, or configurable per activity profile)
- `arrival_override: string | null` — user-set value that overrides the calculated one

Formula reference (Naismith): time = (distance_km / 5) + (elevation_gain_m / 600) hours. Add a configurable pace multiplier per activity profile (e.g. Skitouren slower than Trail-Running).

## Spec callout

`user_stories_foundation.md` already flags this as an open question:

> Vor Implementierung von Epic #136 muss geklärt werden:
> - Welche Berechnungsmethode (Naismith, Swiss Formula, individuell)?
> - Speicherung: berechnete Zeit als eigenes Feld `calculated_arrival` neben manuellem `time_window`?
> - Wird die Berechnung server-seitig beim GPX-Import getriggert?

This issue is the **decision + implementation** for those questions.

## Recommended decisions (for review)

| Question | Recommendation |
|---|---|
| Method | Naismith with per-activity-profile multiplier |
| Storage | New fields `arrival_calculated` + `arrival_override` (not overwriting `time_window`) |
| Trigger | Server-side on GPX upload AND on any waypoint coordinate/elevation change |
| Granularity | Per waypoint, not just per stage |

## Required backend changes

### Data model additions

```python
# Waypoint
origin: Literal['manual', 'algorithm'] = 'manual'
confirmed: bool = True  # algorithmic waypoints start False
suggestion_reason: str | None = None
arrival_calculated: time | None = None   # auto-computed
arrival_override: time | None = None      # user-set
```

### New service module

`app/services/route_analyzer.py`:
- `extract_significant_points(gpx_track) -> list[SuggestedWaypoint]`
- Detects: peaks (local elevation maxima > X m above surroundings), ridges (sustained high points), exposure changes (treeline crossings if data available), valley bottoms, hut waypoints (if matched against a points-of-interest database — optional)

`app/services/naismith.py`:
- `compute_arrival_times(stage: Stage, start_time: time, profile: ActivityProfile) -> dict[wp_id, time]`
- Activity profile carries pace_multiplier (Trekking = 1.0, Skitouren = 1.3, etc.)

### API changes

- `POST /api/trips/.../gpx` — after parsing, run `extract_significant_points`, persist waypoints with `origin='algorithm', confirmed=False`
- `PATCH /api/trips/.../stages/:id/waypoints/:wp_id/confirm` — flip `confirmed=true`, recalculate arrival times
- `PATCH /api/trips/.../stages/:id/waypoints/:wp_id` — when coordinates change, recompute `arrival_calculated` for all subsequent waypoints in the stage

## Acceptance criteria (backend)

- [ ] GPX upload produces suggested waypoints at significant points.
- [ ] Each waypoint has `origin`, `confirmed`, `suggestion_reason`, `arrival_calculated`, `arrival_override` fields in the API response.
- [ ] Confirming/discarding a suggestion is a one-call API.
- [ ] Naismith calculation respects per-activity-profile pace multiplier.
- [ ] Changing one waypoint's coordinates recomputes subsequent waypoints' arrival times.
- [ ] Backend unit tests cover: Naismith calculation, peak detection (synthetic GPX), confirmed/unconfirmed lifecycle.

## Frontend prerequisite

Once this backend is shipped, the frontend in Issue #06 can render real suggestions. Until then, the frontend can mock with hardcoded suggestion data so design + interaction can be validated.

## Note on scope

This is a **backend-only** issue. Frontend consumption is in Issues #06 (waypoint map editor) and #11 (wizard step 2 etappen).