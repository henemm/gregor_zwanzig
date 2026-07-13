# Context: feat-1250-s1-preset-kontrakt-v2

Scheibe 1 von #1250 (Epic #1230, Phase 3) — Neuanlauf nach PO-Reset des ersten
S1-Versuchs (`feat-1250-s1-preset-kontrakt`, verworfen, State liegt unarchiviert).

## Request Summary

`ComparePreset` als Python-Dataclass (analog `Trip`) plus EIN zentraler Loader
ersetzt die heute 4-fach duplizierten rohen `json.loads`-Dict-Loads von
`data/users/<uid>/compare_presets.json`. Verhaltensneutral (Golden-Vergleich
vor/nach), Grundlage für Scheibe 2 (`paused_at`) und Scheibe 5 (gemeinsames Modell).

## Related Files

| File | Relevance |
|------|-----------|
| `src/services/compare_alert.py:291` | `_load_presets()` — Dup 1 (identischer Code in 3 Alert-Services) |
| `src/services/compare_radar_alert.py:179` | `_load_presets()` — Dup 2 |
| `src/services/compare_official_alert.py:184` | `_load_presets()` — Dup 3 |
| `src/services/scheduler_dispatch_service.py:38` | Daily-Lauf lädt roh — Dup 4 (in der Programm-Spec genannt) |
| `src/services/scheduler_dispatch_service.py:99` | **Zusätzlich, nicht in Programm-Spec:** Read-Modify-Write Status-Update (`letzter_versand`) — SCHREIBT die Datei |
| `src/services/scheduler_dispatch_service.py:242` | **Zusätzlich, nicht in Programm-Spec:** Einzelversand (`POST .../send`, #627) lädt roh |
| `src/app/trip.py:169` | Vorbild-Dataclass `Trip` (Programm-Spec sagt models.py:168 — tatsächlich trip.py) |
| `src/app/loader.py:251` | Vorbild `load_trip()` + `LoaderError`; `_corridor_from_dict:186` wiederverwendbar |
| `src/services/compare_slot_scheduler.py:58` | `presets_due_for_hour()` konsumiert Presets als Dicts (9 `.get(`-Zugriffe) |
| `internal/model/compare_preset.go` | Go-Feldreferenz (SSoT der Feldliste inkl. Deprecated-Felder) |
| `internal/store/compare_preset.go:12` | Go schreibt dieselbe Datei — Python-Seite darf Schema nicht verändern |

## Existing Patterns

- **Trip-Loader-Pattern:** `load_trip(path)` / `load_trip_from_dict(data)` →
  `_parse_trip`, Fehlerklasse `LoaderError`, tolerantes Parsen mit Defaults.
- **Fail-soft bei Korruption:** Alle 4 Load-Stellen loggen Warning und geben
  `[]` zurück (bzw. Einzelversand: `KeyError`). Muss erhalten bleiben.
- **RMW-Schreibpfad (BUG-DATALOSS-GR221):** `_update_preset_status` (Zeile 99)
  lädt roh, mutiert 2 Felder, schreibt zurück — bewahrt unbekannte Felder.
  **Eine Dataclass-Roundtrip-Serialisierung würde hier Felder verlieren**
  (Go-seitige Felder wie `display_config`, `previous_schedule`, …).

## Dependencies

- Upstream: `json`, `pathlib`; künftig `src/app/models.py`/`loader.py`.
- Downstream (Konsumenten der geladenen Presets): 3 Alert-Services iterieren
  Presets per `preset.get(...)`; `presets_due_for_hour` (Dicts);
  `send_one_compare_preset`; Renderer-Kette. Wie tief Attribute statt
  `.get()` gezogen werden, entscheidet die Spec (Scope-Grenze 250 LoC).

## Existing Specs

- `docs/specs/modules/issue_1250_briefing_subscription.md` — Programm-Spec
  (8 Scheiben); Scheibe-1-Definition Zeile 106-114. Status: draft (Programm-
  Ebene), Scheiben-ACs entstehen je Workflow (Muster #1231).
- `docs/specs/modules/compare_preset_zeitplan.md`, `versand_tab_vergleich.md` —
  Slot-Semantik (`morning_time`/`evening_time`/`end_date`, #1232).

## Risks & Considerations

1. **Feldverlust beim Schreiben:** Loader darf den RMW-Schreibpfad NICHT auf
   Dataclass-Serialisierung umstellen — Scheibe 1 ist Lese-Kontrakt.
   Schreibpfade bleiben Dict-basiert (oder Dataclass trägt Raw-Passthrough).
2. **Scope-Abweichung zur Programm-Spec:** 6 statt 4 Load-Stellen im
   Dispatch-Service (Zeile 99 + 242 zusätzlich). Spec-Phase muss entscheiden:
   alle Lese-Stellen umstellen (konsequent) vs. nur die 4 genannten.
3. **Verhaltensneutralität:** `schedule=="manual"` = Pause u. a. lebende
   Legacy-Semantik (KL-3) — Dataclass muss Deprecated-Felder tragen, nicht
   normalisieren.
4. **Schema-Dateien:** `models.py`/`loader.py` triggern `data_schema_backup`-
   Hook; Go-Seite bleibt unberührt (Schema-Owner bleibt Go bis Scheibe 5).
5. **Alt-Workflow-Leiche:** `feat-1250-s1-preset-kontrakt` steht unarchivierbar
   auf phase6b (Adversary-Gate) — bewusst liegen gelassen, nicht manipuliert.
