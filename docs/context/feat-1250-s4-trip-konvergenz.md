# Context/Analyse: feat-1250-s4-trip-konvergenz

## Request Summary
Scheibe 4 von Epic #1250: der Trip bekommt dieselben FLACHEN Slot-/Kanal-Felder wie der
ComparePreset (per Dual-Read aus `report_config`) + serverseitige `end_date`-Materialisierung
(`max(stage.date)`). Additiv, **verhaltensneutral** (AC-15 Golden-Mail). ACs: AC-13/AC-14/AC-15.

## Zentrale Befunde (2 parallele Recherchen)
1. **Trip hat KEINE flachen Felder und KEIN `end_date`-Feld.** `end_date`/`start_date` sind
   berechnete `@property` (`src/app/trip.py:210-218`, `max(stage.date)`), nicht persistiert.
   Go-Trip (`internal/model/trip.go:101-138`): nur `ReportConfig map[string]interface{}` (Z.109, opak),
   `PausedAt` (121), `ArchivedAt` (122); **keine Extra-/Catch-all-Map** (Roundtrip-Verlust-Risiko).
2. **Versand liest `end_date` NICHT** — Renderer/Scheduler gehen ausschließlich über
   `resolve_report_render_options(trip.report_config, …)` (`trip_report.py:87-89`, RENDER_NEUTRAL). ⇒
   Materialisierung ist fürs Briefing rein additiv. **ABER `src/services/trip_alert.py:315`** liest
   `trip.end_date` (`if trip.end_date < today: Skip`) — die Property MUSS Single-Source bleiben.
3. **ComparePreset-Vorbild** (flache Zielfelder): `morning_enabled/morning_time/evening_enabled/`
   `evening_time/end_date` + `send_telegram/send_sms` (Go `compare_preset.go:86-98`, Python `models.py:895-901`,
   FE `types.ts:492-501`).
4. **report_config-Mapping:** `morning_time`/`evening_time`/`send_email`/`send_sms`/`send_telegram` liegen
   in der Map (`models.py:719-728`). **Nur EIN `enabled`-Flag** (keine getrennten morning/evening) → Ableitung nötig.
   `_trip_to_dict` baut `report_config` feldweise neu (`loader.py:1373-1402`) — NICHT anfassen.
5. **FE `computeTripEnd`** = `VersandTab.svelte:169-181` (max stage.date, `.split('T')[0]`, Ausgabe DD.MM.YYYY).
   AC-14-Vergleich auf ISO-normalisiertem Wert, nicht auf dem formatierten String.

## Design-Entscheidung (Analyse) — „flache Felder = abgeleitet, nicht autoritativ"
`report_config` (Slots/Kanäle) und die `end_date`-Property (max stage.date) bleiben die **einzige Wahrheit**.
Die flachen Felder sind eine additive, beim Laden abgeleitete Sicht — verhaltensneutral, S5 dreht die Autorität um.

- **Go** (`internal/model/trip.go` nach Z.136): additive omitempty-Pointer-Felder `EndDate/MorningTime/`
  `EveningTime/MorningEnabled/EveningEnabled/SendEmail/SendSms/SendTelegram`. Ableitung in
  `normalizeTrip` (`internal/store/trip.go:29-44`, läuft bei jedem Load, In-Memory) aus `report_config` +
  `max(stage.date)` — **frisch bei jedem Load** (überschreibt stale persistierte Werte). Struct-Felder
  sind nötig, sonst gehen die JSON-Keys beim Go-Roundtrip verloren (keine Extra-Map).
- **Python** (`src/app/loader.py`): `_parse_trip` leitet die flachen Slot-/Kanal-Felder aus `report_config`
  ab; `_trip_to_dict` emittiert sie additiv mit omitempty-Guards (`if trip.<feld> is not None:`, Vorbild
  `official_alerts_enabled` `loader.py:1278-1280`). **`end_date` bleibt `@property`** (`trip.py:216`) — KEIN
  verdeckendes Dataclass-Feld; `_trip_to_dict` emittiert `end_date` aus der Property. So liest
  `trip_alert.py:315` weiter den frischen `max(stage.date)`-Wert (Risiko i entschärft).
- **FE** (`frontend/src/lib/types.ts` nach Z.295): additive optionale flache Felder am `Trip`-Interface
  (Vorbild ComparePreset Z.492-501). Werte kommen abgeleitet aus der API.
- **`morning_enabled`/`evening_enabled`:** `report_config` hat nur ein `enabled` → Ableitung
  `morning_enabled = evening_enabled = report_config.enabled` (beide Slots teilen den Trip-Schalter);
  **gegen die Scheduler-Slot-Logik verifizieren** (`_get_active_trips`), damit die Ableitung das
  bestehende Verhalten spiegelt.
- **`end_date` (AC-14):** Server materialisiert `max(stage.date)`, ISO-normalisiert (`.split('T')[0]`),
  identisch zu `computeTripEnd`. Vergleich auf ISO.

## Risiken & Gegenmaßnahmen
- **(i) `end_date`-Property nicht verdecken** — kein Dataclass-/Struct-Feld, das `trip.end_date` (Python-Property)
  überschattet; `trip_alert.py:315` muss den berechneten Wert behalten. Go darf ein `EndDate`-Feld haben,
  weil Go es in `normalizeTrip` frisch aus Stages ableitet (nie stale).
- **(ii) `report_config` bytegleich (AC-13)** — den `_trip_to_dict`-report_config-Block (`loader.py:1373-1402`)
  NICHT anfassen; flache Felder als separate Top-Level-Keys.
- **(iii) Doppelquelle Kanäle** — flache Kanal-Felder sind ABGELEITET aus `report_config.send_*` (können nicht
  driften); der Versand liest weiter `report_config`. S5 macht flach autoritativ. Transitions-Zustand, dokumentiert.
- **(iv) Go-Roundtrip-Verlust** — Struct-Felder in `trip.go` sind Pflicht (keine Extra-Map), sonst gehen additive
  Keys verloren (analog Corridors/OfficialWarnings).
- **(v) AC-14-Formatfalle** — Server ISO vs. FE DD.MM.YYYY; Stage-Datum ggf. mit Zeitanteil → `.split('T')[0]`.

## Related Files
| File | Rolle |
|------|------|
| `internal/model/trip.go:101-138` | additive flache Felder (nach Z.136) |
| `internal/store/trip.go:29-44` | `normalizeTrip` — Ableitung aus report_config + stages (In-Memory, jeder Load) |
| `src/app/loader.py:402-596` (`_parse_trip`) / `:1211-1409` (`_trip_to_dict`) | Ableitung + additive Emission (omitempty-Guards), report_config-Block Z.1373-1402 UNBERÜHRT |
| `src/app/trip.py:210-218` | `end_date`/`start_date` @property — bleibt Single Source |
| `frontend/src/lib/types.ts:275-296` | `Trip`-Typ additiv erweitern |
| `frontend/src/lib/components/shared/VersandTab.svelte:169-181` | `computeTripEnd` — AC-14-Referenz |
| `src/services/trip_alert.py:315` | liest `trip.end_date` (Property) — NICHT verdecken |

## Tests (Andockpunkte)
- Trip-Roundtrip: `tests/tdd/test_bug_805_789_roundtrip.py`, `test_issue_991_roundtrip_extra_fields.py`.
- AC-13/14: neuer Test — Fixture-Trip mit `report_config` laden → flache Felder abgeleitet, `report_config` bytegleich; `end_date == max(stage.date) == computeTripEnd`.
- AC-15 Golden: `tests/tdd/test_issue_930_golden_gate.py`, `test_briefing_mail_inhalt.py` — Versand-Payload vor/nach S4 bytegleich.

## Existing Specs
- `docs/specs/modules/issue_1250_briefing_subscription.md` — S4 = AC-13/14/15. Wiederverwendet.
- Konvergenz-Ziel: S5 macht die flachen Felder autoritativ + migriert nach `briefings/<id>.json`.

## Umfang
~250 LoC (Go-Felder + normalizeTrip-Ableitung + Python-Ableitung/Emission + FE-Typ + Tests) — **LoC-Override
auf 500 nötig** (Spec markiert S4 als Override-Kandidat); PO-Permission bei der ACs-Freigabe einholen.
