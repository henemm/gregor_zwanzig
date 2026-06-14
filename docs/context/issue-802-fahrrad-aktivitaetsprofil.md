# Context: Issue #802 — Aktivitätsprofil Fahrrad (fahrrad_NN) bei Segment-/Zeitberechnung

## Request Summary
Fahrrad-Trips (`activity = "fahrrad_20"`) werden in der **Python**-Segment-/Zeitberechnung
mit fester Wandergeschwindigkeit (4 km/h) getaktet → falsche Zeitfenster → falsche
Wetter-Zuordnung pro Segment. Die Bike-Geschwindigkeiten existieren bereits in Go (#674),
fehlen aber komplett im Python-Pfad.

## Kernbefund (Root Cause)
1. **Python `Trip` trägt kein `activity`-Feld.** `src/app/trip.py` Dataclass kennt es nicht,
   `loader.py::_parse_trip` (Z.392) liest `activity` nicht aus dem JSON, `_trip_to_dict`
   (Z.953) serialisiert es nicht. → Latentes Datenverlust-Risiko (CLAUDE.md #102): ein
   Python-`save_trip` würde `activity` aus dem JSON **löschen**.
2. **`_interpolate_arrival_time`** (`trip_report_scheduler.py:655`) ist hart auf
   Wandertempo verdrahtet: `dist/4.0`, Aufstieg `/300`, Abstieg `/500`. Liest die
   Aktivität nie.
3. Der Scheduler nutzt **ausschließlich** `_convert_trip_to_segments` →
   `_interpolate_arrival_time`. `segment_builder.build_segments`/`EtappenConfig` werden
   im Versandpfad NICHT verwendet → **ein einziger Fixpunkt**.

## Wann feuert der buggy Pfad?
Prioritätskette in `_convert_trip_to_segments` (Z.728-Kommentar):
`time_window > arrival_override > stage.start_time (i==0) > arrival_calculated (Go-Naismith persistiert) > Python-Interpolation`.
Go persistiert `arrival_calculated` für ALLE Wegpunkte bei jedem PUT (`ComputeStageArrivals`,
`naismith.go:104`). Für über die Frontend-PUT-Route editierte Bike-Trips sind die Zeiten
also bereits korrekt. **Die Python-Interpolation feuert nur, wenn `arrival_calculated`
fehlt** (z.B. GPX-Import ohne Recompute, Altdaten vor #674) — und produziert dann
Wandertempo-Fenster.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_report_scheduler.py:655` | `_interpolate_arrival_time` — hartes Wandertempo, der Fixpunkt |
| `src/services/trip_report_scheduler.py:686` | `_convert_trip_to_segments` — ruft Interpolation, hat das Trip-Objekt |
| `src/app/trip.py:173` | `Trip` Dataclass — braucht `activity`-Feld |
| `src/app/loader.py:392` | `_parse_trip` — `activity` aus JSON lesen |
| `src/app/loader.py:953` | `_trip_to_dict` — `activity` serialisieren (Round-Trip-Erhalt) |
| `internal/model/naismith.go:38` | Go `ActivitySpeed` — die zu spiegelnde Quelle |

## Existing Patterns (Single Source of Behavior = Go)
- Go `ActivitySpeed(activity)`: `fahrrad_15`→15/600/1000, `fahrrad_20`→20/600/1000,
  `fahrrad_25`→25/600/1000, sonst Wanderer 4/300/500 (km/h, Hm/h Aufstieg/Abstieg).
- Go `naismithHours` = **SUMME** (dist/flat + asc/up + desc/down).
- Python `_interpolate_arrival_time` = **MAX**(flat-Zeit, elev-Zeit) — bewusst divergente
  Grobschätzung (#296-Kommentar); die persistierte `arrival_calculated` trägt den
  exakten SUM-Wert.

## Dependencies
- Upstream: `_convert_trip_to_segments` muss die Aktivität an `_interpolate_arrival_time`
  durchreichen (Trip-Objekt ist vorhanden).
- Downstream: Segment-Zeitfenster → Wetterabruf pro Segment → Briefing-Mail/SMS.

## Existing Specs
- `docs/specs/modules/issue_674_aktivitaetstyp_fahrrad.md` — Go/Frontend-Bike-Speeds.
  Erklärt **Python explizit als OUT OF SCOPE** → #802 schließt genau diese Lücke.
- `docs/specs/modules/issue_296_be_naismith_arrival.md` — Go-Naismith, persistierte Zeiten.

## Risks & Considerations
- **Kein Default-Bruch für Wander-Trips** (Issue-Vorgabe): Default-Speeds unverändert,
  MAX-Formel beibehalten (Wechsel auf SUM würde Wander-Fallback-Zeiten ändern).
- **Konsistenz mit Go:** Python-Bike-Speeds exakt aus Go spiegeln (fixe 15/20/25 + Default),
  damit Fallback == Go-persistierte Werte. Kein generisches `fahrrad_NN`-Parsing (würde
  von Go divergieren).
- **Mandanten-/profilneutral:** `activity` ist ein Trip-Feld, kein User-/Profil-Feld.
- **Datenverlust-Vorsorge:** `activity` muss im Python-Round-Trip erhalten bleiben.
