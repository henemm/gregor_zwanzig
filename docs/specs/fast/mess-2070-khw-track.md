# Mini-Spec: #2070 KHW-Trip gegen die Track-Auflösung messen

## Was ändert sich

- Nichts am Produktivcode. Reine **Read-only-Messung** gegen den Prod-Stand.
- Je Etappe des KHW-Trips (`KHW 403`, user `henning`) wird `resolve_stage_track_km()`
  (`src/services/track_resolution.py`, `DEFAULT_TOLERANCE_M = 10.0`) aufgerufen.
- Ergebnis als Tabelle ans Issue #2070: *Etappe · Datum · auflösbar ja/nein · km-Spanne ·
  größter gemessener Wegpunkt-Abstand in m · Grund*.

## Was darf sich nicht ändern

- **Der Prod-Trip-Bestand.** Gemessen wird gegen eine Kopie im Session-Scratchpad,
  `resolve_stage_track_km()` direkt — **nie** `backfill_stage_distances(persist=True)`.
- Der GPX-Bestand unter `/var/lib/gregor/users/henning/gpx/` bleibt unangetastet.
- Keine Änderung an der Trip-Konfiguration des PO.
- Die Auflösungslogik selbst wird nicht angefasst (das ist #2036 / #2073).

## Manuelle Test-Schritte

1. Prod-Daten (Trip-JSON + GPX-Verzeichnis) read-only ins Scratchpad kopieren.
2. Messskript gegen die Kopie laufen lassen.
3. md5-Summen des Prod-GPX-Bestands vor/nach der Messung vergleichen — müssen identisch sein.
4. Tabelle ans Issue #2070 hängen.

## Inline-Test

- [ ] Gegenprobe: Prod-GPX-Bestand nach der Messung unverändert (md5 aller Dateien)
- [ ] Gegenprobe: Prod-Trip-JSON nach der Messung unverändert (md5)
