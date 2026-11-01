# RED-Notizen für /50-implement (#2587)

Testdatei: `tests/tdd/test_compare_briefing_nachholen.py` — 14 rot (AC-1..AC-13 positive Fälle), 6 grün als Bestandsabsicherung (AC-2 no_channels/no_weather, AC-3 on_demand + Handversand, AC-4 Gegenrichtung, AC-9b).
Go: `TestBriefingHealthCountsMixedTripAndCompareEntries` in `internal/scheduler/briefing_health_test.go` ist bereits grün (erwartet, kein Go-Produktivcode). `go` liegt unter `/usr/local/go/bin/go`.

## Schnittstellen-Annahmen der Tests (die Implementierung muss sie erfüllen)

1. Compare-Vermerk: `kind:"vergleich"`, `preset_id`, KEIN `trip_id`, `report_type` "morning"/"evening", `date` ISO-Zieltag, `slot_hour` int, `reason:"dispatch_error"`, `attempts` 0 bei neuem Vermerk, `created_at` ISO-String MIT Zeitzone (naives `utcnow()` lässt AC-6 mit TypeError scheitern).
2. `send_one_compare_preset` / `_dispatch_due_preset` werden in AC-3-Gegenprobe und AC-11 OHNE neue Keyword-Argumente aufgerufen; `report_type` wird dort aus `tage_ab_ortstag` abgeleitet (0 = morning). Neue Parameter nur optional.
3. Ein gescheiterter Nachholversuch schreibt einen frischen Vermerk mit den Werten des Originals (`report_type`, `date`, `slot_hour`), nicht neu berechnet (AC-12 hängt daran).
4. **AC-9a geht vor Implementation Details §2:** Ein erfolgreicher regulärer Versand räumt die `dispatch_error`-Vermerke desselben Presets mit `(preset_id, report_type)` UND zusätzlich Vermerke desselben Presets mit demselben Zieltag (`date`) — sonst bleibt der offene Abend-Vermerk für D nach dem erfolgreichen Morgen-Versand für D liegen. Die freigegebene AC ist maßgeblich; Test nicht aufweichen. Die Spec-Formulierung in §2 im Zuge der Implementierung entsprechend präzisieren (Changelog-Zeile).
5. Hinweis-Text per Regex `Nachgeliefert — die Zustellung um 0?7:00 ist fehlgeschlagen`. AC-5 nennt „07:00“; der Trip baut heute `f"{slot_hour}:00"` („7:00“). Empfehlung: geteilter Baustein mit `f"{slot_hour:02d}:00"` für beide (AC-Wortlaut), Trip-Tests dabei gegenprüfen. Plain + Telegram beginnen mit dem Hinweis; im HTML steht er vor dem ersten Ortsnamen.
6. AC-4 vergleicht den Eintrag (JSON mit sortierten Schlüsseln), nicht die Datei-Bytes.
7. AC-8 liest `briefing_log.json`: Eintrag mit `entity_id == preset_id` muss `kind == "evening"`, `on_demand == False`; Betreff/Zieltag = D.
8. AC-7 nutzt Koordinaten (Auckland, Los Angeles) für die Zeitzone, weil der Loader `SavedLocation.timezone` nicht speichert.
