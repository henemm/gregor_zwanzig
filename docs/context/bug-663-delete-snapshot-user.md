# Context: bug-663-delete-snapshot-user

## Request Summary
Trip-Befehle (`ruhetag`, `startdatum`, `abbruch`) eines **nicht-`default`**-Nutzers
schreiben/löschen im falschen Nutzer-Verzeichnis (`data/users/default/`), weil der
verändernde Pfad im `TripCommandProcessor` die `user_id` ignoriert. Verstoß gegen
die Mandantentrennungs-Pflicht.

## Befund: Defekt ist breiter als das Issue beschreibt
Issue #663 nennt nur `_delete_snapshot()`. Tatsächlich ignoriert der **gesamte
verändernde Pfad** die `user_id` — `_find_trip()` lädt zwar korrekt mit `msg.user_id`,
aber zurückgeschrieben/gelöscht wird beim Default-Nutzer:

| Aufrufer | Zeile | Aufruf | Folge bei Nicht-`default`-Nutzer |
|----------|-------|--------|----------------------------------|
| `_apply_ruhetag` | 550 | `save_trip(new_trip)` | geänderter Trip landet in `users/default/trips/` (Datenverlust + Cross-User) |
| `_apply_ruhetag` | 551 | `_delete_snapshot(trip.id)` | eigener Snapshot bleibt stale, default-Snapshot fälschlich gelöscht |
| `_apply_ruhetag` | 552/522 | `_append_command_log` / `_is_already_applied` | Idempotenz-Log im default-Nutzer |
| `_shift_start` | 624 | `save_trip(new_trip)` | wie oben |
| `_shift_start` | 625 | `_delete_snapshot(trip.id)` | wie oben |
| `_cancel_trip` | 700 | `save_trip(new_trip)` | wie oben |

`_trigger_report` (Z. 209) reicht `msg.user_id` bereits durch; `_handle_query`/
`_handle_drilldown`/`_show_status` sind read-only und korrekt.

## Related Files
| File | Relevance |
|------|-----------|
| `src/services/trip_command_processor.py` | Defekt: alle verändernden Handler + Helpers |
| `src/app/loader.py:722` | `get_snapshots_dir(user_id="default")` |
| `src/app/loader.py:707` | `get_data_dir(user_id="default")` |
| `src/app/loader.py:1078` | `save_trip(trip, user_id="default", ...)` |
| `tests/tdd/test_trip_command_processor.py` | Bestehende Tests (default-Nutzer, echtes FS) |

## Existing Patterns
- `InboundMessage.user_id: str = "default"` existiert bereits (Z. 38).
- `process()` hat `msg.user_id` und reicht es an `_find_trip` und `_trigger_report` durch.
- Test-Isolation: echtes `data/users/`, kein Mock; `save_trip(trip, user_id=...)`
  schreibt nutzergetrennt. `list_all_user_ids` ignoriert `test*`/`_*`-Verzeichnisse.

## Dependencies
- Upstream: `loader.get_*`-Helper akzeptieren alle `user_id`.
- Downstream: Inbound-Gate/Router setzen `msg.user_id` aus dem Auth-/Kanal-Kontext.

## Risks & Considerations
- Reine Signatur-Erweiterung (user_id durchreichen), default bleibt rückwärtskompatibel.
- TDD-Pflicht: mit **zwei** Nutzern testen (A schickt `ruhetag` → nur As Trip/Snapshot/
  Log betroffen, Bs gleicher `trip_id`-Bestand unberührt).
- LoC klein (< 30), reine Backend-Korrektheit, kein UI-Scope.
