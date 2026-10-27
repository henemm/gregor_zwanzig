# ADR-0083: Gemeinsame Schreibsperre Go/Python per `flock` auf `<id>.json.lock`

- **Status:** Akzeptiert
- **Datum:** 2026-10-05
- **Bezug:** GitHub-Issue #2158 (Epic #2138 Multi-User), Spec
  `docs/specs/bugfix/fix_2158_schreibsperren.md`; löst ADR-0031 ab; ergänzt ADR-0036
  (Inhalts-Fingerabdruck) und ADR-0076 (internes Kontingent-Gate)

## Kontext

ADR-0031 nannte den Go-Store „einzige Schreib-Autorität". Das stimmt nicht: Der Python-Kern
schreibt `briefings/<id>.json` ebenfalls (Telegram-/SMS-Kommandos, `skip_next`-Verbrauch,
Distanz-Backfill, Compare-Preset-Status). Zusätzlich fehlten in Go Sperren für Orte, Gruppen
(`groups.json`, inkl. Migration beim Lesen) und Metrik-Vorlagen (`metric_presets.json`). Folge:
Lost Updates — eine von zwei gleichzeitigen Änderungen ging still verloren.

## Entscheidung

- **Gemeinsame Sperrdatei** `data/users/<uid>/briefings/<id>.json.lock` für Trips und
  Compare-Presets. Go (`syscall.Flock`, `LOCK_EX|LOCK_NB`, 20-ms-Poll) und Python
  (`fcntl.flock` über `src/services/file_lock.py`) sperren dieselbe Datei. Sie liegt neben dem
  Ziel, weil `rename` die Inode des Ziels tauscht. Der Pfad ist Vertrag und wird auf beiden
  Seiten literal getestet.
- **Go:** `LockBriefing`/`LockBriefingErr` nehmen erst den prozessinternen Mutex, dann den
  flock. Frist ca. 5 s; Fristablauf ⇒ Handler antworten **503 + `Retry-After`**, es wird nichts
  geschrieben. Nie Rückfall auf ungesperrtes Schreiben.
- **Orte** (je Nutzer+Ort), **Gruppen** und **Metrik-Vorlagen** (je Nutzer, Sammeldateien):
  prozessinterne Sperren. `migrateGroups` läuft beim GET unter der Gruppen-Sperre über
  `loadGroupsLocked` (keine Reentranz).
- **Lock-Reihenfolge (verbindlich, deadlock-frei):** Quota → Gruppen/Vorlagen (je Nutzer) →
  Ort → Briefing-Mutex → Datei-flock. Nie umgekehrt; `DeleteGroup` darf nach der Gruppen-Sperre
  Orte sperren.
- **Python-Timeouts:** Kommando: nichts schreiben, Antwort „bitte erneut senden";
  `_skip_next_verbrauchen`: Trip in diesem Lauf nicht senden; Backfill: nicht persistieren;
  Compare-Schreiber: Warn-Log, `False`. Kein Pfad schreibt ungesperrt.
- **Sperrdateien sind keine Nutzerdaten:** Listen filtern bereits `*.json`; Export und
  `scripts/cleanup_1708c_dead_trips.py` überspringen `*.lock`.
- **`telegram_tokens.json`** ist bereits atomar und gesperrt (#2160); unverändert.

## Verworfene Alternativen

- **Neuer Go-Schreib-Endpunkt für Python** — hielte ADR-0031 aufrecht, schafft aber eine neue
  Cross-User-Angriffsfläche (`requireLocalOnly` wäre alleiniger Schutz, #2159 offen).
- **ETag allein** — schützt den Browser, nicht den Python-Schreiber mit veraltetem Objekt.
- **SQLite/Datenbank** — siehe ADR-0031, unverhältnismäßiger Betriebsaufwand.

## Konsequenzen

- **Positiv:** Alle Änderungen bleiben erhalten, bei Dauerbelegung klare Fehlermeldung statt
  stillem Verlust; keine Verklemmung, da kein Go-Handler die Briefing-Sperre während eines
  synchronen Python-Aufrufs hält.
- **Negativ / Annahme:** `flock` gilt nur auf lokalem Dateisystem (kein NFS/SMB). Wird
  `data/users/` je verlagert, ist diese ADR neu zu bewerten. Ein Skript, das die Sperrdatei
  nicht nutzt, wird nicht geschützt.
- **Folgepflichten:** Neue Schreiber auf `briefings/` müssen dieselbe Sperrdatei nehmen und
  atomar schreiben; die Lock-Reihenfolge ist einzuhalten.
