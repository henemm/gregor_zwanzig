# Context/Analyse: feat-1250-s3-auto-pause

## Request Summary
Scheibe 3 von Epic #1250 (Phase 3): Wenn ein Compare-Preset sein `end_date` überschreitet,
wird es **automatisch pausiert** (`paused_at` gesetzt, Hub-Hinweis „Laufzeit überschritten"),
idempotent, **kein** Auto-Archiv/-Löschen. ACs: AC-10/AC-11/AC-12 der Programm-Spec
`docs/specs/modules/issue_1250_briefing_subscription.md`.

## Zentrale Befunde (2 parallele Recherchen)
1. **Versand ist bei `end_date < today` bereits gestoppt** — `presets_due_for_hour`
   (`src/services/compare_slot_scheduler.py:82-84`) `continue`t solche Presets (reine Funktion,
   kein Schreib-Seiteneffekt). `paused_at` dient hier also dem **Hub-Status**, nicht dem Versand-Stopp.
2. **Die reine Funktion VERBIRGT die Kandidaten** (Zeile 83) — der einzige Daily-Aufrufer
   `run_compare_presets_daily` (`scheduler_dispatch_service.py:66`) sieht end_date-überschrittene
   Presets nie in `due`. → Der Aufrufer braucht einen **eigenen Durchlauf** über `presets` für die Auto-Pause.
3. **Cross-Language-Falle (bestätigt):** Go `NormalizeComparePreset` (`internal/store/compare_preset.go:41-43`)
   löscht `paused_at` für `schedule != "manual"` bei JEDEM Load/GET (`:90`, `handler:200/393`).
   Ein Python-`paused_at` bei einem non-manual Preset wäre beim nächsten Go-Load weg.
4. **Status ist reine FE-Ableitung** (`subscriptionHelpers.ts:72-77` `deriveStatusFromPreset`,
   3 Werte active/paused/draft). Hub (#1229) ist FE-only, **kein** Backend-Status-/Hinweis-Feld.
   `paused_at` UND `end_date` sind beide am Preset (`types.ts:480/501`) → Hinweis rein ableitbar.
5. **Pause-Contract (`schedule=manual` + `previous_schedule` sichern)** lebt heute nur im FE
   (`subscriptionHelpers.ts:297-306` `computePauseToggle`) + Go-Handler-Preserve (`compare_preset.go:285-287`).
   Kein Python-Code setzt `paused_at` bisher (bestätigt).

## Design-Entscheidung (Analyse) — „Auto-Pause = server-seitige Manuell-Pause"
Die Auto-Pause schreibt denselben konsistenten Zustand wie eine manuelle Pause:
`schedule="manual"`, `previous_schedule=<alter schedule>` (falls alt ≠ manual/leer), `paused_at=<jetzt UTC ISO>`.

- **Warum:** übersteht die Go-Normalisierung (schedule=manual → paused_at bleibt), **kein Go-Change nötig**,
  respektiert die S2-Invariante voll. `paused_at` wird real persistiert (AC-10/AC-11).
- **Idempotenz (AC-11) natürlich:** beim Folgelauf greift der bestehende `schedule=="manual"`-Guard
  (`compare_slot_scheduler.py:75`) VOR der end_date-Prüfung → Preset ist kein Kandidat mehr, kein Re-Write.
  Zusätzlich expliziter „schon pausiert"-Guard (`paused_at` gesetzt) vor dem Schreiben (Muster
  `trip_report_scheduler.py:410`).
- **Kein Archiv/Löschen (AC-12):** nur der Pause-Zustand wird gesetzt, `archived_at` unberührt.
- **Hub-Hinweis (AC-12):** FE-Ableitung in `subscriptionHelpers.ts` — `paused_at` gesetzt ∧ `end_date < heute`
  → „Laufzeit überschritten", gerendert neben der Status-Pille / im Monitoring-Streifen. Kein neues Feld.
- **Reaktivieren:** bestehende FE-Logik stellt `schedule` aus `previous_schedule` wieder her.

**Verworfene Alternativen:** (b) nur `paused_at` + Go-Normalize aufweichen → ändert die S2-Invariante
vorzeitig, koppelt Normalize an Datums-/Zeitzonen-Logik (S5-Thema). (c) reine FE-Ableitung ohne Persistenz
→ widerspricht AC-10/AC-11 („paused_at gesetzt") und ist Sackgasse fürs Konvergenzziel.

**PO-Offenlegung (AC-12-Wortlaut):** AC-12 sagt „nur `paused_at` gesetzt". Das Design setzt zusätzlich
`schedule="manual"` + `previous_schedule` — das ist die Transitions-Ära-Repräsentation einer Pause
(S2: `schedule=="manual"` ⇔ pausiert) und erfüllt AC-12s Absicht (kein Archiv/Löschen). Mechanismus-Abweichung,
im Slice-Go offengelegt.

## Related Files
| File | Rolle |
|------|------|
| `src/services/scheduler_dispatch_service.py:27-95` | `run_compare_presets_daily` — Auto-Pause-Durchlauf hier (nach dem `due`-Loop), pro User über `presets` |
| `src/services/scheduler_dispatch_service.py:98-131` | `save_compare_preset_status` — RMW-Muster (rohes JSON, id-Match, Merge, zurückschreiben). Neuer RMW `save_compare_preset_pause` analog |
| `src/services/compare_slot_scheduler.py:75-84` | reine Guards; Kandidat = `end_date < today` (Zeile 83). Funktion bleibt rein/unverändert |
| `frontend/src/lib/components/compare/subscriptionHelpers.ts:72-77` | `deriveStatusFromPreset`; neuer Helfer `isRuntimeExceeded(preset)` (paused_at ∧ end_date<heute) |
| `frontend/src/lib/components/compare/CompareStatusPill.svelte` + `CompareTabs.svelte:665-712` | Hinweis-Rendering neben Pille / Monitoring-Streifen |
| `frontend/src/lib/components/compare/CompareTile.svelte:61/146` | Listen-Kachel (Hinweis optional) |
| Datenmodell | `schedule`/`previous_schedule`/`end_date`/`paused_at`/`archived_at` in `models.py:863-899`, Datei `data/users/<id>/compare_presets.json` |

## Tests (Andockpunkte)
- `tests/tdd/test_compare_preset_slot_dispatch.py` — reine Funktion (Kandidaten-Erkennung).
- `tests/tdd/test_issue_461_compare_preset_dispatch.py` + `test_compare_preset_send.py` — `run_compare_presets_daily` (Auto-Pause-Schreibpfad, Idempotenz, kein Versand).
- `tests/tdd/test_issue_995_scheduler_pause.py` — `paused_at`-Pause-Muster (Trip-Referenz).
- FE: neue co-located `__tests__/`-Datei für den Hinweis-Helfer + `deriveStatusFromPreset`.

## Risks & Considerations
- **Cross-Language-Konsistenz:** Python schreibt einen self-konsistenten Zustand (schedule=manual + paused_at),
  den Go-Normalize akzeptiert — kein Ping-Pong. Aber: die Pause-Repräsentation liegt jetzt in 3 Stellen
  (FE `computePauseToggle`, Go-Handler, Python-Scheduler) — Konvergenz-Smell, S5 vereinheitlicht.
- **Reaktivieren eines abgelaufenen Presets ohne end_date-Verlängerung** → nächster Daily-Lauf pausiert es
  wieder (korrekt, aber Edge-Test).
- **Datums-Semantik-Divergenz (Agent-Risiko):** Python `date < date.today()` (Versand-Stopp) vs. FE `end_date<heute`
  (Hinweis) — 1-Tag-Fuzz an der Grenze, kosmetisch; Hinweis primär an `paused_at` koppeln.
- **`save_compare_preset_pause` schreibt rohes JSON direkt** (kein `preset.raw`-Problem, wie `save_compare_preset_status`).
- **Daten-Schema-Rework:** RMW mit Merge (nur die 3 Felder ändern), niemals Replace (BUG-DATALOSS-GR221).

## Existing Specs
- `docs/specs/modules/issue_1250_briefing_subscription.md` — Programm-Spec, S3 = AC-10/AC-11/AC-12. Wird wiederverwendet.
- `docs/context/feat-1250-s2-pause-konvergenz.md` — S2-Handoff (die Normalize-Falle stammt von dort).
