# Kontext: fix-2231-slot-reparatur (Issue #2231, Epic #2505)

## Ausgangslage

- PR #2514 (main) liefert `docs/specs/modules/fail_closed_versand_defaults.md`. Dort legt AC-5 fest:
  beschädigte `briefing_slots.json` => kein Versand, Datei bleibt byte-identisch.
- Folge: Dauersperre aller Briefings dieses Nutzers bis zum manuellen Eingriff. Es gibt keinen
  automatischen Weg heraus, und der Wanderer merkt nichts (Alarme laufen weiter, Briefings
  bleiben stumm).
- PO-Entscheid 2026-10-06 („Reparatur nachliefern“): statt Dauersperre reparieren. Eine zweite
  Sitzung hatte die Reparatur parallel gebaut (alter Branch `worktree-spicy-shimmying-lake`,
  Spec `fix_2231_fail_closed_versand.md`, AC-10..AC-17); deren AC-1..AC-9 sind auf main schon
  anders gelöst und werden nicht übernommen.

## Ist-Stand auf main (gelesen, nicht angenommen)

- `src/services/briefing_slots.py`: `_load()` liefert bei JSONDecodeError/OSError/Nicht-Objekt den
  Sentinel `_UNREADABLE` und loggt ERROR. Leser (`is_recorded`, `is_recorded_or_claimed`) geben
  dann `True`; `_update()` gibt `False` zurück und schreibt nichts.
- `_log_bezeugt_versand()` leitet aus `briefing_log.json` nur ab, solange `briefing_slots.json`
  NICHT existiert (PO-Regel 2026-08-11, enge Lesart). `_log_traegt_versand()` ohne diese
  Bedingung wird für die Übernahme verwaister Claims genutzt. Beschädigtes Log => dort still
  `False` (fail-open, kein ERROR).
- `src/services/trip_report_scheduler.py`: `_collect_due_trips` (Z. ~587) filtert über
  `is_recorded_or_claimed`; ein beschädigter Speicher liefert dort `True`, der Trip wird also nie
  fällig und `reserve()` nie erreicht. **Ein Reparaturschritt nur in `_update` käme deshalb nie
  zum Zug** — der Scheduler muss die Reparatur vor der Fälligkeitsprüfung anstoßen.
- `_append_briefing_log` (Z. ~2162) macht `json.loads(path.read_text())` ungeschützt: ein
  beschädigtes `briefing_log.json` lässt den Schreibvorgang NACH dem Versand abstürzen.

## Entscheidungen

1. Reparatur nur unter der Sidecar-Sperre (gleiche Closure-Mechanik wie `_update`), nie im
   lock-freien Leser. Leser bleiben unverändert (`True`, kein Umbenennen).
2. Kaputte Datei wird umbenannt (`briefing_slots.json.corrupt-<UTC>`), nie gelöscht, nie
   überschrieben. Namenskollision => Zähler-Suffix.
3. Neue Datei trägt Top-Level-Marker `rebuilt_from_log_at` (ISO-UTC). Mit Marker gilt die
   Ableitung aus dem Versandprotokoll wie bei fehlender Datei; gültige Datei ohne Marker =>
   altes Verhalten (PO 2026-08-11).
4. Beschädigtes `briefing_log.json` wird ebenso beiseitegelegt (`.corrupt-<UTC>`), ERROR,
   Versandprotokoll startet neu. Preis: Der Protokoll-Zeuge für diesen Tag ist weg — ein
   einmaliger Doppelversand im selben Nachholfenster ist möglich, wenn BEIDE Dateien
   beschädigt sind. Bewusst akzeptiert gegen den Dauerausfall.
5. Scheduler ruft einmal je Sammellauf `store.repair_if_corrupt(moment=now_utc)` vor
   `_collect_due_trips`-Schleife auf.

## Betroffene Dateien

- `src/services/briefing_slots.py` (Reparatur, Marker, Ableitungsbedingung, Log-Leser)
- `src/services/trip_report_scheduler.py` (Reparatur-Aufruf, `_append_briefing_log` robust)
- `tests/test_briefing_slot_fail_closed.py` (AC-5-Fälle entfallen), neue Tests
  `tests/test_briefing_slot_reparatur.py`, `tests/test_briefing_log_beschaedigt.py`

## Hinweis

Die Vorlage vom alten Branch (Spec, Code, Tests) war in dieser Sitzung nicht lesbar
(kein Shell-Zugriff); die Spec ist gegen den Stand auf main und den Auftrag geschrieben.
Der Entwickler gleicht die Testfälle beim Umsetzen mit dem alten Branch ab.
