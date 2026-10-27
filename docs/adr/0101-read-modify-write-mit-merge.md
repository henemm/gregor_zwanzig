# ADR-0101: Persistenz-Änderungen erhalten Bestandsdaten — Read-Modify-Write mit Merge, niemals Replace

- **Status:** Akzeptiert (rückwirkend dokumentiert 2026-10-21 — gelebte Praxis seit BUG-DATALOSS-GR221, Commit `79d9f94c1`, 2026-05-01)
- **Datum:** 2026-10-21
- **Bezug:** Issue #102 (BUG-DATALOSS-GR221), CLAUDE.md §„Daten-Schema-Reworks (PFLICHT!)", Hook `.claude/hooks/data_schema_backup.py` (in `.claude/settings.json` eingehängt), `docs/reference/operations_playbook.md` (Migration, Roundtrip-Test, Rollback), Code-Belege z. B. `internal/model/trip.go:376`; ADR-0031 (dateibasierte Persistenz), ADR-0083 (gemeinsame Schreibsperre)

## Kontext

Bei einem Refactor verschwanden 3 von 4 Etappen des GR221-Trips (#102). Ein Pre-Snapshot existierte
nicht; die Wiederherstellung gelang nur, weil GPX-Dateien zufällig in einem ungetrackten Stash
überlebt hatten (Docstring `data_schema_backup.py`). Ursache war ein Replace: ein Objekt wurde mit
dem Stand des Clients überschrieben, Felder, die der Client nicht kannte, gingen verloren.

## Entscheidung

1. **Bestandsdaten bleiben bei Persistenz-Änderungen erhalten.** Gespeichert wird per
   Read-Modify-Write mit Merge: bestehendes Objekt laden, nur geänderte Felder überschreiben.
   **Niemals Replace.**
2. **Pre-Snapshot-Hook:** Edits an schema-relevanten Dateien (`src/app/models.py`,
   `src/app/trip.py`, `src/app/loader.py`, `internal/model/*.go`, `internal/store/store.go`) lösen
   vorab `data_schema_backup.py` aus — `tar.gz` von `data/users/` nach `.backups/`, Retention 20.
3. **Verhältnis zu ADR-0031/0083:** ADR-0031 ist nur in der Aussage „Go einzige
   Schreib-Autorität" durch ADR-0083 abgelöst. Diese Regel hing nie an dieser Aussage und gilt
   **unabhängig weiter** — für jeden schreibenden Prozess, Go wie Python. Die Schreibsperre aus
   ADR-0083 verhindert parallele Überschreibungen; Read-Modify-Write verhindert den Verlust
   unbekannter Felder. Beides ist nötig.

## Verworfene Alternativen

- **Replace mit vollständigem Client-Objekt:** verworfen — Ursache von #102.
- **Nur Backups ohne Merge-Pflicht:** verworfen — ein Backup macht Verlust umkehrbar, verhindert
  ihn aber nicht.

## Konsequenzen

- **Positiv:** Felder, die ein Client oder Endpoint nicht kennt, überleben jede Speicherung.
- **Negativ / Preis:** Jeder Schreibpfad muss laden und mergen; Schema-Edits erzeugen Snapshots.
- **Folgepflichten:** Schema-Änderungen kommen mit Migration und Roundtrip-Test
  (`operations_playbook.md`). Tests sichern den Erhalt ab (z. B. `internal/model/alert_sync_test.go`,
  `internal/model/alert_delta_817_test.go`).
