# Context: fix-1244-corridors-null

## Request Summary

Ein über `POST /api/trips` angelegter Trip wird mit `"corridors": null` persistiert. Der Python-Loader iteriert über dieses Feld, wirft `TypeError: 'NoneType' object is not iterable`, und `load_all_trips()` überspringt den Trip stillschweigend. Nutzersicht: Der Trip ist in der Liste sichtbar, bekommt aber **nie** ein Briefing; der Sende-Endpoint antwortet `404 Trip not found`.

## Root Cause (zweiseitig)

**Schreibseite (Go):** `internal/handler/trip.go:100-134` (`CreateTripHandler`) dekodiert den Request-Body ohne DTO direkt in `var trip model.Trip`. Jedes Slice-Feld, das im Body fehlt, bleibt `nil` und wird als JSON `null` geschrieben. `internal/store/trip.go:100-104` (`SaveTrip`) besitzt bereits eine Nil-Coercion — aber nur für `AlertRules` (Issue #205 F002). `Corridors`, `Stages` und `Stage.Waypoints` fehlen dort.

**Leseseite (Python):** `src/app/loader.py:455` nutzt `data.get("corridors", [])`. Bei JSON-`null` greift der Default **nicht** — `.get()` liefert `None`.

## Related Files

| Datei | Relevanz |
|------|-----------|
| `internal/store/trip.go:94-129` | `SaveTrip` — einziger Trip-Schreibpfad (alle 5 Aufrufer). Nil-Coercion-Block bei :100-104, deckt nur `AlertRules` ab. **Zentraler Fix-Ort.** |
| `internal/model/trip.go:97,104,110,114` | Slice-Felder ohne `omitempty`: `Stage.Waypoints`, `Stages`, `AlertRules`, `Corridors`. Kommentar :111-113 dokumentiert den Kontrakt „immer `[]`, nie `null`" — der beim Create verletzt wird. |
| `internal/handler/trip.go:100-134` | `CreateTripHandler`, kein DTO, direkte Dekodierung in `model.Trip`. |
| `internal/store/compare_preset.go:75-88` | `SaveComparePresets` — normalisiert nur das äußere Slice, nicht `Corridors` auf Feldebene. |
| `internal/handler/compare_preset.go:173-240` | `CreateComparePresetHandler` normalisiert `LocationIDs` und `Empfaenger`, aber **nicht** `Corridors` → `"corridors": null` in `compare_presets.json`. |
| `src/app/loader.py:305-490` | `_parse_trip`. Anfällige Stellen: :308 (`stages`), :310 (`waypoints`), :410 (`display_config`), :455 (`corridors`), :472 (`avalanche_regions`), :531 (`metrics`), :652 (`sms_metrics`), :166 (`channels` in `_alert_rule_from_dict`). |
| `src/app/loader.py:1086-1099` | `load_all_trips` schluckt die Exception als `logger.warning("Skipping corrupt trip …")` — der Trip verschwindet lautlos aus allen Konsumenten (Scheduler, Alerts, Inbound-Reader, Command-Processor). |
| `scripts/migrate_1231_corridors.py` | Vorbild-Muster für Migration: Dry-Run-Default, zweiphasig (`_collect_plan` → `_apply`), Idempotenz-Check, tar.gz-Backup, Iteration über `data/users/*/trips/*.json`. **Heilt `corridors: null` NICHT** (Zeile 176 verwirft leere Pläne). |

## Existing Patterns

- **Nil-Coercion in der Store-Schicht** ist das etablierte Muster (`internal/store/trip.go:100-104`, Issue #205 F002). Der Test-Kommentar in `internal/model/corridor_test.go:58-62` benennt die Store-Schicht ausdrücklich als Vertragsort für die „Immer-nicht-null"-Garantie.
- **`or []`-Idiom auf der Leseseite** wird im Compare-Pfad bereits konsequent genutzt: `src/services/report_config_resolver.py:216` (`preset.get("corridors") or []`), `compare_alert.py:254`. Auch im Loader selbst an einzelnen Stellen (`loader.py:222`, `:196`). Der Trip-Ladepfad ist die Lücke.
- **Migration** nach dem Muster von `scripts/migrate_1231_corridors.py` (s.o.).

## Dependencies

- **Upstream:** Go-Handler → `store.SaveTrip` → JSON-Datei `data/users/{user_id}/trips/{trip_id}.json`
- **Downstream:** `load_all_trips()` speist `trip_report_scheduler.py:263,397`, `trip_alert.py:278,611`, `inbound_email_reader.py:238`, `inbound_telegram_reader.py:359`, `trip_command_processor.py:427`, `shortcode.py:16` — alle sehen einen `null`-Trip überhaupt nicht.

## Bestehende Tests

- `internal/handler/trip_corridors_write_test.go` — PUT-Roundtrip + RMW-Preserve. **Kein POST-Test, kein `null`-Test.**
- `internal/model/corridor_test.go:63-80` — prüft nur `json.Marshal` einer leeren Slice, nicht die persistierte Datei.
- `tests/tdd/test_corridor_persistence.py` — Roundtrip `save_trip`/`load_trip`.
- **Kein einziger Test prüft, dass die geschriebene JSON-Datei `[]` statt `null` enthält.** Genau diese Lücke hat den Bug durchgelassen.

## Risks & Considerations

- **Scope-Erweiterung ist notwendig, nicht optional:** Ein POST ohne `stages` erzeugt `"stages": null` und tötet den Trip auf exakt demselben Weg. Nur `corridors` zu fixen, würde denselben Bug beim nächsten Feld wieder auftreten lassen.
- **Bestandsdaten:** Drei Trips auf Staging sind dauerhaft unladbar. Prod muss geprüft werden. Migration ist ein eigener Deploy-Schritt pro Host (Trip-Dateien liegen außerhalb von Git), als `claude-gregor`, idempotent, mit Backup.
- **Stiller Datenverlust ohne Alarm:** Der `logger.warning`-Pfad nennt zwar Datei und Fehler, aber nichts macht darauf aufmerksam. Ein unladbarer Trip sollte nicht nur geloggt, sondern beobachtbar sein — mindestens `logger.error`.
- **Kein `omitempty` als Fix:** Würde den in `model/trip.go:111-113` dokumentierten Kontrakt brechen und von `AlertRules` divergieren.
